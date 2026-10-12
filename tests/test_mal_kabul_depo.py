# -*- coding: utf-8 -*-
"""Mal kabulde giriş deposu seçimi + iade kaydı (Ekim 2026, kullanıcı kararı A).

Müşteriden alınan iade doğrudan satılacaksa İADE DEPO yerine MERKEZ / HAPPY LIFE seçilir; ürün
satılabilir stoğa girer. İade türündeki kabul Satış › İade'ye manuel iade olarak da yazılır (P&L iadeyi
düşer, ay sonu Excel'i mükerrer saymaz). Aylık iade Excel'i görevi takvimden kalktı."""
import re
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


# ── Saf: giriş deposu çözümü ───────────────────────────────────────────
@pytest.mark.parametrize("metin, arayuz, beklenen", [
    ("", "iade", "İADE DEPO"), ("", "teknik", "TEKNİK DEPO"), (None, "iade", "İADE DEPO"),
    ("MERKEZ DEPO", "iade", "MERKEZ DEPO"), ("merkez", "iade", "MERKEZ DEPO"), ("Merkez Depo", "teknik", "MERKEZ DEPO"),
    ("happy life", "iade", "HAPPY LIFE"), ("iade", "teknik", "İADE DEPO"), ("ASEL", "iade", "ASEL DEPO"),
    ("teknik servis", "iade", "TEKNİK DEPO"),
    ("OUTLET DEPO", "iade", None),      # listede yok: mal kabulde seçilemez
    ("yok böyle depo", "iade", None),
    ("", "", None),
])
def test_giris_depo_coz(metin, arayuz, beklenen):
    from teknikservis.stok import giris_depo_coz
    assert giris_depo_coz(metin, arayuz) == beklenen


def test_giris_deposu_kayittan():
    from teknikservis.stok import giris_deposu
    assert giris_deposu({"arayuz": "iade"}) == "İADE DEPO"
    assert giris_deposu({"arayuz": "iade", "giris_depo": "MERKEZ DEPO"}) == "MERKEZ DEPO"
    assert giris_deposu({"arayuz": "teknik", "giris_depo": "HAPPY LIFE"}) == "HAPPY LIFE"
    assert giris_deposu({"arayuz": "iade", "giris_depo": "OUTLET DEPO"}) == "İADE DEPO"   # geçersiz → varsayılan
    assert giris_deposu({"arayuz": "", "giris_depo": ""}) is None


@pytest.mark.parametrize("metin, beklenen", [
    ("", 0.0), (None, 0.0), ("1234.56", 1234.56), ("1.234,56", 1234.56), ("1,5", 1.5), ("$ 99", 99.0),
    ("abc", None), ("12.3.4", None),
])
def test_tutar_coz(metin, beklenen):
    from teknikservis.stok import tutar_coz
    assert tutar_coz(metin) == beklenen


# ── Stok hareketi seçilen depoya ───────────────────────────────────────
def test_mal_kabul_girisi_secilen_depoya(monkeypatch):
    import teknikservis.stok as S
    hareket = []
    monkeypatch.setattr(S, "_uygula", lambda sku, ad, depo, delta: (hareket.append((sku, depo, delta)) or (True, "ok")))
    assert S.mal_kabul_girisi({"arayuz": "iade", "stok_kodu": "SKU1", "stok_adi": "A"})[0]
    assert S.mal_kabul_girisi({"arayuz": "iade", "stok_kodu": "SKU2", "giris_depo": "MERKEZ DEPO"})[0]
    assert S.mal_kabul_girisi({"arayuz": "teknik", "stok_kodu": "SKU3", "giris_depo": "HAPPY LIFE"})[0]
    assert hareket == [("SKU1", "İADE DEPO", 1), ("SKU2", "MERKEZ DEPO", 1), ("SKU3", "HAPPY LIFE", 1)]
    ok, msg = S.mal_kabul_girisi({"arayuz": "", "stok_kodu": "X"})
    assert not ok and "arayüz" in msg


def test_gonderildi_ve_transfer_giris_deposundan(monkeypatch):
    """Depoya transfer edilmemiş kayıt: çıkış / transfer kaynağı mal kabulde girdiği depo."""
    import teknikservis.stok as S
    hareket = []
    monkeypatch.setattr(S, "_uygula", lambda sku, ad, depo, delta: (hareket.append((depo, delta)) or (True, "")))
    k = {"arayuz": "iade", "stok_kodu": "S", "giris_depo": "MERKEZ DEPO"}
    assert S.gonderildi_cikisi(k)[0] and hareket[-1] == ("MERKEZ DEPO", -1)
    assert S.depoya_transfer(k, "outlet")[0]
    assert hareket[-2:] == [("MERKEZ DEPO", -1), ("OUTLET DEPO", 1)]
    assert S.depoya_transfer(dict(k, depo="iade"), "merkez")[0]              # transfer edilmişse o depo
    assert hareket[-2:] == [("İADE DEPO", -1), ("MERKEZ DEPO", 1)]


# ── İade kaydı: Satış › İade'ye manuel iade, stok BURADA işlenmez ─────────
def test_iade_kaydi_yaz_manuel_iade(monkeypatch):
    import teknikservis.stok as S
    import satis.database as D
    cagri = []

    def _ekle(tarih, kanal, sku, urun_adi, adet, **kw):
        cagri.append((tarih, kanal, sku, urun_adi, adet, kw))
        return True, "✅"
    monkeypatch.setattr(D, "ekle_iade", _ekle)
    k = {"arayuz": "iade", "stok_kodu": "SKU9", "stok_adi": "Ürün", "firma_bilgisi": "VATAN A.Ş.",
         "giris_depo": "MERKEZ DEPO", "iade_net": "123.4"}
    ok, msg = S.iade_kaydi_yaz(k, tarih="2026-10-12")
    assert ok and "SKU9" in msg and "123,40" in msg
    assert cagri == [("2026-10-12", "VATAN A.Ş.", "SKU9", "Ürün", 1,
                      {"iade_net": 123.4, "depo": "MERKEZ DEPO", "kaynak": "manuel", "stok_isle": False})]
    # teknik servis kaydı: iade değil, hiçbir şey yapmaz
    assert S.iade_kaydi_yaz({"arayuz": "teknik", "stok_kodu": "T"}) == (True, "") and len(cagri) == 1
    # tutar girilmedi: 0 ile yazılır, mesaj söyler
    ok, msg = S.iade_kaydi_yaz({"arayuz": "iade", "stok_kodu": "SKU0", "firma_bilgisi": "X"}, tarih="2026-10-12")
    assert ok and cagri[-1][5]["iade_net"] == 0.0 and "tutar girilmedi" in msg
    monkeypatch.setattr(D, "ekle_iade", lambda *a, **k: (False, "❌ Hata"))
    assert not S.iade_kaydi_yaz(k)[0]


def test_ekle_iade_stok_isle_kapali_ve_yukleme_bildirimi(monkeypatch):
    """stok_isle=False: iadeler'e yazar, stoğa dokunmaz; aktif yükleme varsa eklenen satırı bildirir."""
    import satis.database as D

    class _Tbl:
        def __init__(self, kayit):
            self.kayit = kayit

        def insert(self, k):
            self.kayit.append(k)
            return self

        def execute(self):
            class _R:
                data = [dict(self.kayit[-1], id=77)]
            return _R()

    yazilan, stok = [], []

    class _Cli:
        def table(self, ad):
            assert ad == "iadeler"
            return _Tbl(yazilan)
    monkeypatch.setattr(D, "_get_client", lambda: _Cli())
    monkeypatch.setattr(D, "_stok_uygula_depolu", lambda m, yon: stok.append((m, yon)))
    monkeypatch.setattr(D, "_kart_sku", lambda s, h=None: s)
    monkeypatch.setattr(D, "_temizle", lambda: None)
    eklenen = []

    class _Yk:
        def eklenen(self, tablo, satirlar, beklenen=None):
            eklenen.append((tablo, [r["id"] for r in satirlar], beklenen))
    monkeypatch.setattr(D, "_aktif_yukleme", lambda: _Yk())
    ok, _ = D.ekle_iade("2026-10-12", "VATAN", "SKU1", "A", 1, iade_net=10, depo="MERKEZ DEPO",
                        kaynak="manuel", stok_isle=False)
    assert ok and yazilan[-1]["kaynak"] == "manuel" and yazilan[-1]["depo"] == "MERKEZ DEPO"
    assert stok == [] and eklenen == [("iadeler", [77], 1)]
    ok, _ = D.ekle_iade("2026-10-12", "VATAN", "SKU1", "A", 2, depo="HAPPY LIFE")   # varsayılan: stok işlenir
    assert ok and stok == [([("SKU1", 2, "HAPPY LIFE")], 1)]


def test_toplu_mal_kabul_geri_alma_iadeleri_kapsar():
    from shared.yukleme_gecmisi import GERI_ALINABILIR
    assert "iadeler" in GERI_ALINABILIR["toplu_mal_kabul"] and "ts_kayitlar" in GERI_ALINABILIR["toplu_mal_kabul"]


# ── Ekran ve takvim ───────────────────────────────────────────────────
def test_ekran_depo_secimi_ve_iade_kaydi():
    m = _oku("teknikservis/main.py")
    assert 'key="mk_giris_depo"' in m and 'key="mk_iade_net"' in m
    assert '"giris_depo": giris_depo' in m and "_stok.iade_kaydi_yaz(data)" in m
    assert '"Giren Depo", "İade Net Tutar"' in m                     # toplu Excel şablonu
    g = m[m.index("def kapi_mal_kabul("):]
    assert g.index("ekle_kayit(") < g.index("mal_kabul_girisi(") < g.index("iade_kaydi_yaz(")
    assert "giris_depo_coz(_depo_t, _tur)" in g and "tutar_coz(_net_t)" in g
    d = _oku("teknikservis/database.py")
    assert '"giris_depo", "iade_net"' in d                            # kolon yoksa onlarsız yazar
    sql = _oku("veritabani/27_mal_kabul_depo.sql")
    assert "giris_depo" in sql and "iade_net" in sql


def test_aylik_iade_gorevi_kalkti():
    from shared import yukleme_takvimi as Y
    assert "iade_aylik" not in {k["anahtar"] for k in Y.KAYNAKLAR} and "iade_aylik" not in Y._OKUYUCU
    s = _oku("satis/main.py")
    assert 'serit("iade_aylik")' not in s and 'kaydet("iade_aylik"' not in s
    assert re.search(r'"iade_excel": dict\(', _oku("shared/dosya_kapisi.py"))   # Excel yüklemesi isteğe bağlı kaldı
