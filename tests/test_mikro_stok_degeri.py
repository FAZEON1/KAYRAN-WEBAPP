# -*- coding: utf-8 -*-
"""Toplam Aktifler · stok değeri uygulama verisinden (kayranacc/mikro_stok_degeri.py, Ekim 2026).

Excel'in (Stok değeri raporu) kaydı [usd_stok, {pazaryeri: $}]; usd_stok bütün depolardaki stoğun değeri,
Toplam Aktifler × 1,20 ile katar. Uygulama karşılığı: depo kırılımı × paçal (satis.database.get_pacal_map),
müşterideki stok × paçal (bilgi). Tutarlar USD; her testin başında hesap elle yazılıdır.
"""
import contextlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

from kayranacc import mikro_stok_degeri as M

KOK = Path(__file__).resolve().parent.parent

# Paçal haritası KANONİK anahtarlı (sku_anahtar): kart 'Fazeon X24F240P' yazsa da X24F240P bulunur
PACAL = {"X24F240P": 100.0, "A2120TRA": 5.0, "FAZE3": 1.65}


def test_depo_degeri_butun_depolar_ve_yazim_birlesik():
    """20.10 Excel'i bütün depoları sayıyordu (yalnız Merkez + Happy Life 616.564 ↔ Excel 764.472; bütün depolar
    737.742). Hesap:
         'Fazeon X24F240P'  Merkez 10 × 100 = 1.000 ; İade 2 × 100 = 200 ; Teknik 1 × 100 = 100
         A2120TRA           Happy Life 100 × 5 = 500 ; İkinci el 4 × 5 = 20
         FAZE3              Merkez 1.000 × 1,65 = 1.650
         RMAFC005 (paçalsız) Happy Life 265 → 0, listede
       Merkez 2.650 · Happy Life 500 · İade 200 · Teknik 100 · İkinci el 20 → toplam 3.470"""
    urunler = [{"sku": "Fazeon X24F240P", "depo_kirilim": {"MERKEZ DEPO": 10, "İADE DEPO": 2, "TEKNİK DEPO": 1}},
               {"sku": "A2120TRA", "depo_kirilim": {"HAPPY LIFE": 100, "İKİNCİ EL DEPO": 4}},
               {"sku": "Faze3", "depo_kirilim": {"MERKEZ DEPO": 1000, "OUTLET DEPO": 0}},
               {"sku": "RMAFC005", "depo_kirilim": {"HAPPY LIFE": 265}},
               {"sku": "BOS", "depo_kirilim": None}]
    d = M.depo_degerleri(urunler, PACAL)
    assert d["deger"] == {"HAPPY LIFE": 500.0, "MERKEZ DEPO": 2650.0, "TEKNİK DEPO": 100.0, "İADE DEPO": 200.0,
                          "İKİNCİ EL DEPO": 20.0}
    assert d["adet"]["HAPPY LIFE"] == 365 and "OUTLET DEPO" not in d["adet"]
    assert d["pacalsiz"] == [("RMAFC005", "HAPPY LIFE", 265)]
    assert M.kayit_yap(d, {})[0] == pytest.approx(3470.0)


def test_kanal_degeri_paçalla_sifir_ve_eksi_stok_sayilmaz():
    """VATAN: X24F240P 3 × 100 + FAZE3 10 × 1,65 = 316,50 ; NEG -5 ve bilinmeyen kod 0 $.
       HB: yalnız 0 adet → firma yazılmaz."""
    kanal = {"VATAN": {"X24F240P": 3, "FAZE3": 10, "A2120TRA": -5, "BILINMEYEN": 7}, "HB": {"X24F240P": 0}}
    assert M.kanal_degerleri(kanal, PACAL) == {"VATAN": 316.5}


def test_excel_kaydi_ile_ayni_ise_yazilmaz_kurus_gurultusu_dahil():
    eski = [764472.8400000001, {"VATAN": 1118287.1}]
    assert M.esit_mi(eski, [764472.84, {"VATAN": 1118287.10}])
    assert not M.esit_mi(eski, [764472.84, {"VATAN": 1118287.10, "HB": 1.0}])
    assert not M.esit_mi(eski, [764472.85, {"VATAN": 1118287.10}])
    assert not M.esit_mi(None, [1.0, {}])


def test_plan_paçal_okunamazsa_bos_yazmaz():
    """get_pacal_map hata olunca {} döner: değer 0 çıkar ve Toplam Aktifler'den stok düşerdi."""
    urunler = [{"sku": "X24F240P", "depo_kirilim": {"MERKEZ DEPO": 10}}]
    p = M.plan_yap(urunler, {}, {}, [764472.84, {}])
    assert p["bos"] and p["kayit"][0] == 0
    assert M.uygula(p) is False


def test_plan_ve_uygula_yalniz_degisince_mikro_adiyla_yazar(monkeypatch):
    """Eski Excel kaydı 764.472,84; uygulama 1.000 → yazılır ('Mikro', 'stok', [1000.0, {'VATAN': 300.0}]).
    Aynı veriyle ikinci tur yazmaz."""
    from kayranacc import database as db
    yazilan = []
    monkeypatch.setattr(db, "aktif_excel_kaydet", lambda k, t, v: yazilan.append((k, t, v)) or True)
    urunler = [{"sku": "X24F240P", "depo_kirilim": {"MERKEZ DEPO": 10}}]
    kanal = {"VATAN": {"X24F240P": 3}}
    p = M.plan_yap(urunler, kanal, PACAL, [764472.84, {"VATAN": 1118287.1, "HEPSIBURADA": 301852.5}])
    assert p["once"] == pytest.approx(764472.84) and p["degisir"] and not p["bos"]
    assert M.uygula(p) is True
    assert yazilan == [("Mikro", "stok", [1000.0, {"VATAN": 300.0}])]
    p2 = M.plan_yap(urunler, kanal, PACAL, yazilan[0][2])
    assert not p2["degisir"] and M.uygula(p2) is False
    assert len(yazilan) == 1


def test_kanal_karsilastirmasi_excel_adlarini_koda_cevirir():
    """Excel 'HEPSIBURADA' ve 'EERA' yazıyordu; uygulama firma kodu (HB, ITOPYA) — aynı satıra düşmeli."""
    k = M.kanal_karsilastir({"HEPSIBURADA": 301852.5, "VATAN": 1118287.1, "EERA": 298114.2},
                            {"HB": 204346.45, "ITOPYA": 197346.57, "VATAN": 822257.52, "MONDAY": 22277.86})
    assert k == [("HB", 301852.5, 204346.45), ("ITOPYA", 298114.2, 197346.57), ("MONDAY", None, 22277.86),
                 ("VATAN", 1118287.1, 822257.52)]


def test_otomatik_kapaliyken_ve_ayni_aktarimda_calismaz(monkeypatch):
    from kayranacc import database as db
    ayar = {}
    monkeypatch.setattr(db, "get_ayar", lambda a, v=None: ayar.get(a, v))
    monkeypatch.setattr(db, "set_ayar", lambda a, v: ayar.__setitem__(a, dict(v)) or True)
    monkeypatch.setattr(M, "son_aktarim", lambda: "2026-10-21 16:11:02")
    plan = {"bos": False, "degisir": True, "kayit": [1.0, {}]}
    monkeypatch.setattr(M, "plan_hazirla", lambda: plan)
    yazilan = []
    monkeypatch.setattr(db, "aktif_excel_kaydet", lambda k, t, v: yazilan.append(v) or True)
    assert M.otomatik() is None and not yazilan                       # kapalı
    M.ac("ibrahim")
    assert M.otomatik() is True and yazilan == [[1.0, {}]]
    assert ayar[M.DURUM_ANAHTAR]["son_calisma"] == "2026-10-21 16:11:02"
    assert M.otomatik() is None and len(yazilan) == 1                 # aynı aktarım: yeniden hesaplanmaz


# ── Uçtan uca: sahte veritabanında get_pacal_map + kanal stoğu zinciri ──────────
def _sahte_db_sinifi():
    yol = KOK / "tests" / "davranis" / "conftest.py"
    spec = importlib.util.spec_from_file_location("dv_conftest_stok_degeri", yol)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SahteDB


def test_plan_hazirla_uctan_uca(monkeypatch):
    """İthalat dosyası D1 (Teslim Alındı): X24F240P 10 × 50 FOB, masraf 100 → yüzde 100/500 = %20 → paçal 60.
       Yoldaki D2 paçala girmez. FAZE3 ithalatsız, kart alış 1,65 (yurt içi yedek).
       Depo: 'Fazeon X24F240P' Merkez 5 + İade 1 → 6 × 60 = 360 ; FAZE3 Merkez 100 × 1,65 = 165 → 525.
       Kanal: VATAN'ın son raporu (18.10) X24F240P 4 → 240; eski rapor (11.10) 99 adet sayılmaz.
       Kayıt: [525.0, {'VATAN': 240.0}]; mevcut Excel kaydı (764.472,84) okunur."""
    SahteDB = _sahte_db_sinifi()
    db = SahteDB(
        ithalat_dosyalari=[{"id": 1, "dosya_no": "2026-01", "tarih": "2026-03-01", "durum": "Teslim Alındı",
                            "masraflar": {"navlun": 100}},
                           {"id": 2, "dosya_no": "2026-09", "tarih": "2026-09-20", "durum": "Yolda", "masraflar": {}}],
        ithalat_kalemleri=[{"id": 11, "dosya_id": 1, "sku": "X24F240P", "adet": 10, "birim_fob": 50,
                            "urun_grubu": "MONİTÖR"},
                           {"id": 21, "dosya_id": 2, "sku": "X24F240P", "adet": 100, "birim_fob": 1,
                            "urun_grubu": "MONİTÖR"}],
        urunler=[{"sku": "Fazeon X24F240P", "urun_adi": "Fazeon 24", "alis_fiyati": 0,
                  "depo_kirilim": {"MERKEZ DEPO": 5, "İADE DEPO": 1}},
                 {"sku": "FAZE3", "urun_adi": "Mouse pad", "alis_fiyati": 1.65, "depo_kirilim": {"MERKEZ DEPO": 100}}],
        firma_stok=[{"firma": "VATAN", "sku": "X24F240P", "stok_miktari": 4, "yukleme_tarihi": "2026-10-18"},
                    {"firma": "VATAN", "sku": "X24F240P", "stok_miktari": 99, "yukleme_tarihi": "2026-10-11"}],
        aktif_excel_verileri=[{"kullanici": "_SHARED_", "dosya_tipi": "stok", "veri_json": json.dumps(
            {"veri": [764472.84, {"VATAN": 1118287.1}], "son_yukleyen": "serdar", "yukleme_zamani": "2026-10-20"})}],
    )
    import ithalat.database as idb
    import kayranpm.database as pdb
    import kayranacc.database as adb
    monkeypatch.setattr(idb, "_get_client", lambda: db)
    monkeypatch.setattr(pdb, "get_client", lambda: db)
    monkeypatch.setattr(adb, "get_client", lambda: db)
    p = M.plan_hazirla()
    assert p["kayit"] == [525.0, {"VATAN": 240.0}]
    assert p["depo"]["deger"] == {"MERKEZ DEPO": 465.0, "İADE DEPO": 60.0}
    assert p["once"] == pytest.approx(764472.84) and p["degisir"]


# ── Açıkken Excel kalkar ─────────────────────────────────────────────
def _acik_sahte(monkeypatch):
    sahte = types.ModuleType("kayranacc.mikro_stok_degeri")
    sahte.acik_mi = lambda: True
    monkeypatch.setitem(sys.modules, "kayranacc.mikro_stok_degeri", sahte)


def test_acikken_stok_degeri_hatirlatmasi_cikmaz(monkeypatch):
    from shared import yukleme_takvimi as Y
    _acik_sahte(monkeypatch)
    monkeypatch.setattr(Y, "_ayar", lambda anahtar, varsayilan: varsayilan)
    monkeypatch.setattr(Y, "_OKUYUCU", {})
    assert "aktif_stok" not in {d["anahtar"] for d in Y.durumlar()}


class _SahteSt:
    """_kapi_aktif'in kullandığı yüzey: Kaydet düğmesine basılmış sayılır."""

    def __init__(self):
        self.info_mesaj, self.session_state = [], {"aktif_kullanici": "serdar"}

    def info(self, m, *a, **k):
        self.info_mesaj.append(m)

    def container(self, *a, **k):
        return contextlib.nullcontext()

    def button(self, *a, **k):
        return True

    def __getattr__(self, ad):
        return lambda *a, **k: None


def test_acikken_stok_degeri_raporu_yuklemesi_kaydedilmez(monkeypatch):
    """Açıkken dosya kapısındaki Stok değeri raporu kaydedilmemeli: aksi halde 15 dakikalık hesap ile elle
    yüklenen dosya birbirini ezer."""
    from kapi_ornekleri import ORNEKLER
    if "requests" not in sys.modules:          # CI'da requests kurulu değil; kayranacc.main yalnız içe aktarır
        monkeypatch.setitem(sys.modules, "requests", types.ModuleType("requests"))
    import kayranacc.main as A
    import kayranacc.aktif_excel as AE
    import shared.yukleme_takvimi as Y
    _acik_sahte(monkeypatch)
    st = _SahteSt()
    monkeypatch.setattr(A, "st", st)
    monkeypatch.setattr(Y, "serit", lambda *a, **k: None)
    kayit = []
    monkeypatch.setattr(AE, "aktif_kaydet", lambda *a, **k: kayit.append(a) or True)
    ad, veri = ORNEKLER["aktif_stok"]()
    dosya = types.SimpleNamespace(name=ad, getvalue=lambda: veri)
    kapi = types.SimpleNamespace(anahtar=lambda s: s, bitti=lambda *a, **k: None)
    A._kapi_aktif(dosya, kapi, "stok")
    assert kayit == []
    assert any("kaydedilmez" in m for m in st.info_mesaj)


def test_esitleme_isleri_stoktan_sonra_stok_degeri():
    """Stok değeri depo kırılımından hesaplanır: aynı turda depo stoğu eşitlemesinden SONRA çalışmalı."""
    yol = KOK / "otonom" / "mikro_esitle.py"
    spec = importlib.util.spec_from_file_location("otonom_mikro_esitle_sd", yol)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    moduller = [m for _a, m, _f in mod.ISLER]
    assert moduller.index("kayranacc.mikro_stok_degeri") > moduller.index("kayranpm.mikro_stok")
    app = (KOK / "app.py").read_text(encoding="utf-8")
    govde = app.split("def _mikro_esitle_dene():", 1)[1].split("\ndef ", 1)[0]
    assert govde.index("_stok_degeri_otomatik()") > govde.index("_stok_otomatik()")
