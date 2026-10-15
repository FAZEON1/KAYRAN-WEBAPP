# -*- coding: utf-8 -*-
"""Depo › Satılamayan stok (depo/satilamayan.py) ve stok yaşı "ilk görülme" tarihinin korunması
(kayranpm.database.stok_yas_ilk_gorulen, veritabani/35_stok_yas_ilk_tarih.sql) — Ekim 2026."""
import sys
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

BUGUN = date(2026, 10, 15)


def _kanonik(d):
    from kayranpm.database import depo_kanonik
    return depo_kanonik(d)


def _anahtar(s):
    from shared.utils import sku_anahtar
    return sku_anahtar(s)


def _satirlar(urunler, iadeler=(), hareketler=(), pacal=None):
    from depo import satilamayan as S
    from kayranpm.database import depo_dagilimi, _SATILABILIR_DEPOLAR
    pmap = S.partiler(list(iadeler), list(hareketler), _kanonik, _anahtar)
    pacal = pacal or {}
    return S.satirlar(urunler, pmap, BUGUN, kirilim=lambda dk: depo_dagilimi(dk)[0],
                      satilabilir=_SATILABILIR_DEPOLAR, anahtar=_anahtar,
                      birim=lambda s: pacal.get(_anahtar(s), 0), ad=lambda s, y: y or s)


def test_yalniz_satilamayan_depolar_ve_paçal_degeri():
    rows = _satirlar([{"sku": "X24", "urun_adi": "Monitör",
                       "depo_kirilim": {"MERKEZ DEPO": 50, "HAPPY LIFE": 3, "İADE DEPO": 4, "teknik": 2,
                                        "OUTLET": 0}}],
                     pacal={"X24": 60.0})
    assert [(r["depo"], r["adet"], r["deger"]) for r in rows] == [("İADE DEPO", 4, 240.0), ("TEKNİK DEPO", 2, 120.0)]


def test_iade_deposu_fifo_iade_tarihinden_kalan_en_yeniler():
    """İade deposunda 5 adet; iadeler 3 (Haziran) + 4 (Ekim) → elde kalan 4 Ekim + 1 Haziran.
    Defterdeki 'giris' (toplu aktarım günü) iade deposu için sayılmaz."""
    rows = _satirlar([{"sku": "X24", "depo_kirilim": {"İADE DEPO": 5}}],
                     iadeler=[{"sku": "x24", "iade_adet": 3, "tarih": "2026-06-01", "depo": "iade"},
                              {"sku": "X24", "iade_adet": 4, "tarih": "2026-10-05", "depo": "İADE DEPO"},
                              {"sku": "X24", "iade_adet": 9, "tarih": "2026-01-01", "depo": ""}],   # merkeze girdi
                     hareketler=[{"sku": "X24", "depo": "İADE DEPO", "degisim": 7, "tur": "giris",
                                  "zaman": "2026-09-30T10:00:00", "basarili": True}])
    r, = rows
    assert r["en_eski_tarih"] == "2026-06-01" and r["kayitsiz"] == 0
    assert r["ort_gun"] == round((4 * 10 + 1 * 136) / 5)
    assert r["yasli"] == 1 and r["grup"] == "91–180 gün"


def test_diger_depolar_defter_girisi_kaydi_olmayan_ayri():
    """Teknik depoda 10 adet; defterde 3 giriş + 1 sevk girişi; aktarım (sayım farkı) ve çıkış sayılmaz."""
    rows = _satirlar([{"sku": "K1", "depo_kirilim": {"TEKNİK DEPO": 10}}],
                     hareketler=[{"sku": "K1", "depo": "teknik", "degisim": 3, "tur": "giris",
                                  "zaman": "2026-10-02T09:00:00", "basarili": True},
                                 {"sku": "K1", "depo": "TEKNİK DEPO", "degisim": 1, "tur": "sevk",
                                  "zaman": "2026-10-10T09:00:00", "basarili": True},
                                 {"sku": "K1", "depo": "TEKNİK DEPO", "degisim": 50, "tur": "aktarim",
                                  "zaman": "2026-10-12T09:00:00", "basarili": True},
                                 {"sku": "K1", "depo": "TEKNİK DEPO", "degisim": 5, "tur": "giris",
                                  "zaman": "2026-10-11T09:00:00", "basarili": False}])
    r, = rows
    assert (r["adet"], r["kayitsiz"], r["en_eski_tarih"]) == (10, 6, "2026-10-02")


def test_depo_ozeti_toplamlar():
    from depo.satilamayan import depo_ozeti
    rows = _satirlar([{"sku": "A", "depo_kirilim": {"İADE DEPO": 2, "OUTLET DEPO": 1}},
                      {"sku": "B", "depo_kirilim": {"İADE DEPO": 3}}],
                     iadeler=[{"sku": "A", "iade_adet": 2, "tarih": "2026-05-01", "depo": "İADE DEPO"}],
                     pacal={"A": 10.0, "B": 20.0})
    oz = {o["depo"]: o for o in depo_ozeti(rows)}
    assert (oz["İADE DEPO"]["adet"], oz["İADE DEPO"]["deger"], oz["İADE DEPO"]["cesit"]) == (5, 80.0, 2)
    assert (oz["İADE DEPO"]["yasli_adet"], oz["İADE DEPO"]["yasli_deger"], oz["İADE DEPO"]["kayitsiz"]) == (2, 20.0, 3)
    assert oz["OUTLET DEPO"]["deger"] == 10.0


def test_sayfa_depo_menusunde():
    from shared.gezinme import MODULLER
    depo = next(m for m in MODULLER if m["kod"] == "depo")
    assert "Satılamayan stok" in [s[0] for s in depo["sayfalar"]]
    assert 'elif _dsayfa == "Satılamayan stok":' in (KOK / "depo" / "main.py").read_text(encoding="utf-8")


# ── Stok yaşı: ilk görülme tarihi korunur ──────────────────────────
class _Kayit:
    def __init__(self):
        self.cagri = []

    def table(self, ad):
        kayit = self

        class _S:
            def upsert(self, veri, **k):
                kayit.cagri.append((ad, veri, k))
                return self

            def execute(self):
                return None
        return _S()


def test_stok_yas_yalniz_yeni_urune_yazilir():
    """Var olan tarih ezilmez: upsert ignore_duplicates=True (ON CONFLICT DO NOTHING). Eski: her ürün
    kaydında / G5F aktarımında tarih bugüne çekiliyordu."""
    from kayranpm.database import stok_yas_ilk_gorulen
    sb = _Kayit()
    stok_yas_ilk_gorulen(sb, ["A", "A", "", "B"], "2026-10-15")
    (ad, veri, k), = sb.cagri
    assert ad == "stok_yas" and veri == [{"sku": "A", "ilk_gorulen_tarih": "2026-10-15"},
                                         {"sku": "B", "ilk_gorulen_tarih": "2026-10-15"}]
    assert k.get("ignore_duplicates") is True, "ilk görülme tarihi eziliyor"


def test_stok_yas_yazimlari_tek_yardimcidan():
    """kayranpm/database.py içinde stok_yas'a yalnız yardımcı yazar (ezen upsert kalmadı)."""
    kod = (KOK / "kayranpm" / "database.py").read_text(encoding="utf-8")
    assert kod.count('table("stok_yas").upsert(') == 1, "stok_yas'a yardımcı dışında yazım var"
    assert kod.count("stok_yas_ilk_gorulen(sb,") == 4      # tanım + 3 çağrı


def test_g5f_sql_ilk_tarihi_ezmez_ve_onarir():
    sql = (KOK / "veritabani" / "35_stok_yas_ilk_tarih.sql").read_text(encoding="utf-8")
    assert "CREATE OR REPLACE FUNCTION g5f_stok_aktar(" in sql and "ON CONFLICT (sku) DO NOTHING" in sql
    assert "DO UPDATE SET ilk_gorulen_tarih" not in sql
    assert "u.ilk_giris_tarihi < y.ilk_gorulen_tarih" in sql            # yalnız geriye çeker


def test_g5f_eski_yol_ilk_gorulme_tarihini_ezmez(monkeypatch):
    """G5F'nin ürün ürün yolu (tek işlem fonksiyonu kurulu değilken) stok_yas'ı ezmemeli.
    Eski kod: upsert(..., on_conflict='sku') — var olan tarihi bugüne çekiyordu."""
    import kayranpm.database as pmdb
    cagri = []

    class _Q:
        def __init__(self, ad):
            self.ad = ad

        def select(self, *a, **k):
            return self

        def eq(self, *a, **k):
            return self

        def update(self, *a, **k):
            return self

        def insert(self, *a, **k):
            return self

        def upsert(self, veri, **k):
            cagri.append((self.ad, k))
            return self

        def execute(self):
            return type("R", (), {"data": [{"urun_adi": "X", "ilk_giris_tarihi": "2026-06-01",
                                            "depo_kirilim": {}}] if self.ad == "urunler" else []})()
    monkeypatch.setattr(pmdb, "get_client", lambda: type("C", (), {"table": lambda s, ad: _Q(ad)})())
    monkeypatch.setattr(pmdb, "_cache_temizle", lambda: None)
    monkeypatch.setattr(pmdb, "get_today", lambda: "2026-10-15")
    monkeypatch.setattr(pmdb, "_defter", lambda: type("D", (), {"yaz_fark": staticmethod(lambda *a, **k: None)})())
    pmdb.upsert_g5f_stok("X24", "X", 5, {"MERKEZ DEPO": 5})
    yas = [k for ad, k in cagri if ad == "stok_yas"]
    assert yas and all(k.get("ignore_duplicates") is True for k in yas), "G5F ilk görülme tarihini eziyor"
