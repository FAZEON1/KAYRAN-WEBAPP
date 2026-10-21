# -*- coding: utf-8 -*-
"""Mikro eşitleme sağlamlığı (21.10.2026 denetimi).

1) Mikro açıkken uygulama içi banka (ödendi, kısmi ödeme, virman, para girişi) ve stok (satış, teknik servis,
   ithalat teslimi) hareketleri miktar / bakiye YAZMAZ: aynı hareket Mikro'dan da geliyor; yazılsaydı ya iki kez
   düşer ya da 15 dakika sonra ezilirdi.
2) Aynı SKU anahtarına düşen fazladan stok kartının stoğu sıfırlanır (iki kez sayılmasın).
3) Eşitleme turu kilitli: kilidi alamayan tur hiçbir iş çalıştırmaz.
4) Mikro eşitleme iş parçacığı çalışırken bayat modül tazelemesi modülleri silmez (21.10 11:49 'deadlock' hataları).
"""
import importlib.util
import sys
import threading
import types
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent


# ── 1a) Banka ─────────────────────────────────────────────────────
class _Sorgu:
    def __init__(self, db, tablo):
        self.db, self.tablo, self.islem, self.veri = db, tablo, "select", None

    def select(self, *a, **k):
        return self

    def update(self, veri):
        self.islem, self.veri = "update", veri
        return self

    def insert(self, veri):
        self.islem, self.veri = "insert", veri
        return self

    def eq(self, *a, **k):
        return self

    def execute(self):
        if self.islem != "select":
            self.db.yazilan.append((self.tablo, self.islem, self.veri))
        data = [{"id": 7, "bakiye": 100.0, "para_birimi": "TL", "hesap_adi": "Ana"}] if self.tablo == "bankalar" else []
        return types.SimpleNamespace(data=data)


class _Db:
    def __init__(self):
        self.yazilan = []

    def table(self, ad):
        return _Sorgu(self, ad)


@pytest.mark.parametrize("mikro", [False, True])
def test_mikro_yonetirken_tahsilat_bakiyeye_yazmaz(monkeypatch, mikro):
    import kayranacc.database as D
    db = _Db()
    monkeypatch.setattr(D, "get_client", lambda: db)
    monkeypatch.setattr(D, "_cache_temizle", lambda: None)
    import kayranacc.mikro_muhasebe as MM
    monkeypatch.setattr(MM, "durum", lambda: {"acik": mikro, "bagli_bankalar": [7]})
    ok, mesaj = D.tahsilat_ekle(7, 50, kaynak="müşteri", tarih="2026-10-21")
    assert ok
    bakiye = [v for t, i, v in db.yazilan if t == "bankalar"]
    assert bakiye == ([] if mikro else [{"bakiye": 150.0}])
    assert [t for t, _i, _v in db.yazilan if t == "tahsilatlar"] == ["tahsilatlar"]    # kayıt yine tutulur
    assert ("Mikro'ya da gir" in mesaj) is mikro


def test_bagli_olmayan_hesaba_yazilir(monkeypatch):
    import kayranacc.mikro_muhasebe as MM
    monkeypatch.setattr(MM, "durum", lambda: {"acik": True, "bagli_bankalar": [3]})
    assert MM.bagli_banka_mi(3) and not MM.bagli_banka_mi(7)
    monkeypatch.setattr(MM, "durum", lambda: {"acik": False, "bagli_bankalar": [3]})
    assert not MM.bagli_banka_mi(3)


def test_tum_bakiye_yazimlari_mikro_kapisindan_gecer():
    kaynak = (KOK / "kayranacc" / "database.py").read_text(encoding="utf-8")
    govde = kaynak.split("def _bakiye_yaz(", 1)[1]
    assert govde.count('table("bankalar").update({"bakiye"') == 1        # yalnız kapının içinde


def test_mikro_muhasebe_bagli_hesaplari_kaydeder(monkeypatch):
    import kayranacc.mikro_muhasebe as MM
    import kayranacc.database as D
    durum = {"acik": True}
    monkeypatch.setattr(MM, "durum", lambda: dict(durum))
    monkeypatch.setattr(MM, "_durum_yaz", lambda d: durum.update(d))
    monkeypatch.setattr(MM, "_cli", lambda: _Db())
    monkeypatch.setattr(D, "_cache_temizle", lambda: None)
    plan = {"banka": [{"id": 3, "mikro_kod": "B1", "degisir": False}, {"id": 9, "mikro_kod": "", "degisir": False}],
            "cek_degisir": False, "cek": [], "cari_degisir": False, "ithalat_degisir": False}
    MM.uygula(plan)
    assert durum["bagli_bankalar"] == [3]


# ── 1b) Stok ──────────────────────────────────────────────────────
def test_mikro_stok_aciksa_uygulama_stoga_yazmaz(monkeypatch):
    import kayranpm.database as P
    monkeypatch.setattr(P, "_mikro_stok_yonetir", lambda: True)
    monkeypatch.setattr(P, "_stok_atomik", lambda *a, **k: pytest.fail("Mikro yönetirken stok yazıldı"))
    monkeypatch.setattr(P, "_stok_hareket_coklu_eski", lambda *a, **k: pytest.fail("Mikro yönetirken stok yazıldı"))
    assert P.stok_hareket_coklu({"X24F240P": -2, "FAZE3": 0, "": 5}, "MERKEZ DEPO") == (1, [])
    assert P.stok_hareket_gruplu([("MERKEZ DEPO", {"A": 1}), ("İADE DEPO", {"B": -1, "C": 2})]) == (3, [])


def test_mikro_stok_kapaliyken_eski_yol(monkeypatch):
    import kayranpm.database as P
    monkeypatch.setattr(P, "_mikro_stok_yonetir", lambda: False)
    monkeypatch.setattr(P, "_stok_atomik", lambda *a, **k: (5, []))
    assert P.stok_hareket_coklu({"A": 1}) == (5, [])


# ── 2) Fazladan kart ─────────────────────────────────────────────
def test_ayni_anahtara_dusen_fazla_kartin_stogu_sifirlanir():
    from kayranpm.mikro_stok import farklar
    urunler = [{"sku": "X24F240P", "depo_kirilim": {"MERKEZ DEPO": 5}},
               {"sku": "Fazeon X24F240P", "depo_kirilim": {"MERKEZ DEPO": 40}}]
    out = farklar({"X24F240P": {"MERKEZ DEPO": 7}}, urunler)
    assert ("X24F240P", {"MERKEZ DEPO": 5}, {"MERKEZ DEPO": 7}) in out
    assert ("Fazeon X24F240P", {"MERKEZ DEPO": 40}, {}) in out


# ── 3) Kilit ──────────────────────────────────────────────────────
def _otonom():
    spec = importlib.util.spec_from_file_location("otonom_mikro_esitle_kilit", KOK / "otonom" / "mikro_esitle.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_kilidi_alamayan_tur_is_calistirmaz(monkeypatch):
    import shared.mikro_kilit as K
    mod = _otonom()
    monkeypatch.setattr(K, "al", lambda sahip, sure_sn=600: False)
    monkeypatch.setattr(mod, "calistir", lambda isler=None: pytest.fail("kilitsiz tur çalıştı"))
    assert mod.tur("github") == mod.KILITLI


def test_kilit_alinip_birakilir(monkeypatch):
    import shared.mikro_kilit as K
    import shared.mikro_saglik as S
    mod = _otonom()
    olay = []
    monkeypatch.setattr(K, "al", lambda sahip, sure_sn=600: olay.append("al") or True)
    monkeypatch.setattr(K, "birak", lambda sahip: olay.append("birak"))
    monkeypatch.setattr(mod, "calistir", lambda isler=None: olay.append("is") or [("Satış", "yeni veri yok / kapalı")])
    gunluk = []
    monkeypatch.setattr(S, "denetle_ve_bildir", lambda isler, kaynak=None: gunluk.append(kaynak))
    mod.tur("uygulama-arka", gunluk_her_zaman=False)
    assert olay == ["al", "is", "birak"] and gunluk == []          # boş tur günlüğe yazılmaz
    mod.tur("github")
    assert gunluk == ["github"]


def test_kilit_fonksiyonu_yoksa_tur_durmaz():
    import shared.mikro_kilit as K

    class _Cli:
        def rpc(self, *a, **k):
            raise RuntimeError("function mikro_kilit_al does not exist")
    assert K.al("x", cli=_Cli()) is True


def test_kilit_rpc_sonucu_okunur():
    import shared.mikro_kilit as K

    class _Cli:
        def __init__(self, v):
            self.v = v

        def rpc(self, *a, **k):
            return types.SimpleNamespace(execute=lambda: types.SimpleNamespace(data=self.v))
    assert K.al("x", cli=_Cli(False)) is False and K.al("x", cli=_Cli(True)) is True
    assert K.al("x", cli=_Cli([{"mikro_kilit_al": False}])) is False


def test_uygulama_ayni_listeyi_ve_kilidi_kullanir():
    app = (KOK / "app.py").read_text(encoding="utf-8")
    govde = app.split("def _mikro_esitle_dene():", 1)[1].split("\ndef ", 1)[0]
    assert "_mod.tur(" in govde and "_mod.ISLER" in govde
    assert "_muhasebe_otomatik()" not in govde                          # eski ayrı liste kalktı


def test_kilit_semasi():
    sema = (KOK / "veritabani" / "52_mikro_tur_kilidi.sql").read_text(encoding="utf-8")
    assert "mikro_kilit_al" in sema and "WHERE k.bitis < now()" in sema and "GERİ ALMA" in sema


# ── 4) Bayat modül ↔ arka iş parçacığı ───────────────────────────
def test_arka_is_suruyorken_moduller_silinmez(tmp_path, monkeypatch):
    from shared import modul_tazele as T
    dur = threading.Event()
    t = threading.Thread(target=dur.wait, name="mikro_esitle", daemon=True)
    t.start()
    try:
        f = tmp_path / "m.py"
        f.write_text("x = 1")
        moduller = {"m": types.SimpleNamespace(__file__=str(f))}
        kayit = {"m": 0.0}                                   # dosya "değişmiş" görünür
        assert T.bayatlari_tazele(moduller, str(tmp_path), kayit) == []
        assert "m" in moduller
    finally:
        dur.set()
        t.join()
    assert T.bayatlari_tazele(moduller, str(tmp_path), kayit) == ["m"] and "m" not in moduller
    sys.modules.pop("m", None)


# ── 5) Mikro esas: uygulamada yeni satış satırı açılmaz ──────────
@pytest.mark.parametrize("acik,tarih,beklenen", [(True, "2026-10-21", True), (True, "2026-06-30", False),
                                                  (False, "2026-10-21", False)])
def test_mikro_esas_mi(monkeypatch, acik, tarih, beklenen):
    import satis.database as SD
    import satis.mikro_esitle as ME
    monkeypatch.setattr(ME, "durum", lambda: {"acik": acik, "baslangic": "2026-07-01"})
    assert SD.mikro_esas_mi(tarih) is beklenen


def test_mikro_esasken_elle_siparis_ve_satis_yazilmaz(monkeypatch):
    import satis.database as SD
    monkeypatch.setattr(SD, "mikro_esas_mi", lambda t: True)
    monkeypatch.setattr(SD, "_get_client", lambda: pytest.fail("Mikro esasken satış yazıldı"))
    ok, mesaj, n = SD.ekle_siparis("2026-10-21", "EERA", "2847", "", [{"sku": "A", "adet": 1, "birim_satis": 1}])
    assert not ok and n == 0 and "Mikro" in mesaj
    ok, mesaj = SD.ekle_satis("2026-10-21", "EERA", "A", "", 1, 1, 1)
    assert not ok and "Mikro" in mesaj


def test_teknik_servis_satisi_mikro_esasken_satisa_yazilmaz_akis_surer(monkeypatch):
    import satis.database as SD
    from teknikservis import stok as TS
    monkeypatch.setattr(SD, "mikro_esas_mi", lambda t: True)
    monkeypatch.setattr(SD, "ekle_satis", lambda *a, **k: pytest.fail("Mikro esasken TS satış satırı yazıldı"))
    ok, mesaj = TS.satis_kaydi_yaz({"sku": "X24F165S", "servis_form_no": "G5F00399"}, 49, tarih="2026-10-12")
    assert ok and "Mikro" in mesaj


def test_elle_siparis_penceresi_mikro_esasken_kayit_yerine_yonlendirir():
    kaynak = (KOK / "satis" / "main.py").read_text(encoding="utf-8")
    govde = kaynak.split("def _satis_manuel_dialog():", 1)[1][:1500]
    assert '_mikrodan_geliyor("Satışlar ve siparişler"' in govde and "return" in govde
