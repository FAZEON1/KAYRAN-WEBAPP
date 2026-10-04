# -*- coding: utf-8 -*-
"""Ürün karnesi (Ekim 2026): yedi ölçü → A–F not ve öneri (kayranpm/urun_karnesi.py).

Ağırlık ve eşikler kullanıcı onaylı: kârlılık %25, sermaye verimi %20, satış hızı %20, stok yaşı %15,
arıza %10, iade %5, kampanya bağımlılığı %5. Rakamlar mevcut hesaplardan (P&L satır kuralı, iade kârı
= iade_net − adet × paçal, stok yaşı FIFO); karne yalnız okur.
"""
from datetime import date
from pathlib import Path

import pytest

import kayranpm.urun_karnesi as U

KOK = Path(__file__).resolve().parent.parent
BUGUN = date(2026, 10, 4)


def test_agirliklar_onaylanan_gibi():
    assert {a: w for a, _ad, w, _n in U.OLCULER} == {"marj": 25, "gmroi": 20, "devir": 20, "yasli": 15,
                                                    "ariza": 10, "iade": 5, "kampanya": 5}
    assert sum(w for _a, _ad, w, _n in U.OLCULER) == 100


@pytest.mark.parametrize("a, deger, beklenen", [
    ("marj", 25, 100), ("marj", 20, 100), ("marj", 15, 80), ("marj", 10, 60), ("marj", 0, 20), ("marj", -20, 0),
    ("gmroi", 3, 100), ("gmroi", 1, 55), ("gmroi", 0.25, 10), ("gmroi", -1, 0),
    ("devir", 30, 100), ("devir", 90, 70), ("devir", 180, 25), ("devir", float("inf"), 0),
    ("yasli", 0, 100), ("yasli", 25, 50), ("yasli", 80, 0),
    ("ariza", 0.5, 100), ("ariza", 3, 60), ("ariza", 10, 0),
    ("iade", 1, 100), ("iade", 5.5, 50), ("iade", 12, 0),
    ("kampanya", 10, 100), ("kampanya", 80, 20), ("kampanya", 100, 10),
])
def test_puan_esikleri(a, deger, beklenen):
    assert U.puan(a, deger) == pytest.approx(beklenen)


def test_puan_veri_yoksa_none():
    assert U.puan("marj", None) is None


IYI = {"marj": 25, "gmroi": 4, "devir": 30, "yasli": 0, "ariza": 0.5, "iade": 0.5, "kampanya": 10}


def test_iyi_urun_A_buyut():
    k = U.karne(IYI)
    assert k["not"] == "A" and k["oneri"] == "Büyüt" and k["toplam"] == pytest.approx(100)
    assert k["dusurenler"] == []


def test_olu_stok_F_birak():
    # Stok var, 12 ayda satış yok: marj / iade / kampanya veri yok; satış hızı 0, sermaye 0, stok yaşlı
    o = {"marj": None, "gmroi": 0.0, "devir": float("inf"), "yasli": 100, "ariza": None, "iade": None,
         "kampanya": None}
    k = U.karne(o)
    assert k["not"] == "F" and k["oneri"] == "Bırak"
    assert set(k["eksik"]) == {"marj", "ariza", "iade", "kampanya"}


def test_yavas_ve_verimsiz_urun_iyi_notla_bile_birak():
    o = dict(IYI, devir=240, gmroi=0.8)
    assert U.oneri("B", o) == "Bırak"


def test_stoku_bitmis_urun_talebe_gore():
    """Stok yok: son 90 günde sattıysa Büyüt; hiç satmadıysa (eski model, stok bitmiş) Koru —
    satışsızlık talepten değil stok yokluğundan."""
    o = dict(IYI, devir=None, gmroi=None, yasli=None)
    assert U.oneri("A", dict(o, _son90=50)) == "Büyüt"
    assert U.oneri("A", dict(o, _son90=0)) == "Koru"


def test_eksik_olcunun_agirligi_dagitilir():
    o = dict(IYI, ariza=None)                 # servise hiç gelmemiş: puanı düşürmez
    assert U.karne(o)["toplam"] == pytest.approx(100)


def test_dusurenler_agirlik_ve_kayba_gore():
    o = dict(IYI, devir=200, yasli=40)        # satış hızı (%20) ve stok yaşı (%15) zayıf
    assert U.karne(o)["dusurenler"] == ["devir", "yasli"]


def test_veri_hic_yoksa_not_yok():
    assert U.karne({a: None for a, *_ in U.OLCULER})["not"] is None


# ── Ölçüler mevcut hesaplarla aynı ──────────────────────────────────
SAT = [
    {"tarih": "2026-09-20", "kanal": "VATAN", "sku": "Fazeon K1", "adet": 10, "birim_satis": 50, "birim_maliyet": 30,
     "birim_firma_destek": 0, "birim_ek_destek": 0},
    {"tarih": "2026-03-01", "kanal": "EERA", "sku": "K1", "adet": 30, "birim_satis": 50, "birim_maliyet": 30,
     "birim_firma_destek": 2, "birim_ek_destek": 0},
    {"tarih": "2026-08-01", "kanal": "EERA", "sku": "M1", "adet": 5, "birim_satis": 200, "birim_maliyet": 150,
     "birim_firma_destek": 0, "birim_ek_destek": 0},
]
IADE = [{"sku": "K1", "iade_adet": 2, "iade_net": 90}]
KARTLAR = {"K1": {"sku": "K1", "bizim_stok": 60}, "M1": {"sku": "M1", "bizim_stok": 0},
           "OLU": {"sku": "OLU", "bizim_stok": 40}}
PACAL = {"K1": 30.0, "M1": 150.0, "OLU": 10.0}


def _anahtar(s):
    from shared.utils import sku_anahtar
    return sku_anahtar(s)


def _pf():
    from satis.database import satir_kar
    return U.portfoy_hesapla(SAT, IADE, KARTLAR, PACAL, {"K1": (15.0, 60.0), "OLU": (40.0, 40.0)},
                             {"K1": 2.0}, {"K1": 20.0}, BUGUN, satir_kar, _anahtar)


def test_portfoy_olculeri_kaynak_kurallarla():
    from satis.database import satir_kar, ozet_hesapla
    pf = _pf()
    k1 = pf["K1"]
    top = ozet_hesapla([s for s in SAT if _anahtar(s["sku"]) == "K1"])[0]
    i_kar = 90 - 2 * 30                                         # iade kârı: P&L'deki süzgeçli iade kuralı
    net_kar = top["net_kar"] - i_kar
    net_satis = top["ciro"] - top["destek"] - 90
    assert k1["olc"]["marj"] == pytest.approx(net_kar / net_satis * 100)
    assert k1["olc"]["gmroi"] == pytest.approx(net_kar / (60 * 30))
    assert k1["olc"]["devir"] == pytest.approx(60 / (10 / 90))   # son 90 günde 10 adet (yazım farkı: 'Fazeon K1')
    assert k1["olc"]["yasli"] == pytest.approx(25)
    assert k1["olc"]["iade"] == pytest.approx(2 / 40 * 100)
    assert k1["olc"]["kampanya"] == pytest.approx(20 / 40 * 100)
    assert k1["olc"]["ariza"] == 2.0
    assert sum(satir_kar(s)["adet"] for s in SAT if _anahtar(s["sku"]) == "K1") == 40


def test_portfoyde_satissiz_stoklu_urun_ve_stoksuz_urun():
    pf = _pf()
    assert pf["OLU"]["karne"]["oneri"] == "Bırak"               # 12 ayda satış yok, stok yaşlı
    assert pf["M1"]["olc"]["devir"] is None and pf["M1"]["olc"]["gmroi"] is None   # stok yok


def test_baglam_sermaye_ve_kar_payi():
    pf = _pf()
    b = U.baglam(pf, "OLU")
    assert b["sermaye_pay"] == pytest.approx(400 / (60 * 30 + 400) * 100)
    assert b["kar_pay"] == 0 and b["urun_sayisi"] == 3


def test_kart_kar_gizliyken_kar_rakami_yok():
    pf = _pf()
    h = U.kart_html(pf["K1"], U.baglam(pf, "K1"), kar_acik=False)
    assert "net marj" not in h and "kâr/yıl" not in h and "kârın %" not in h and "gizli" in h
    h2 = U.kart_html(pf["K1"], U.baglam(pf, "K1"), kar_acik=True)
    assert "net marj" in h2 and "Ürün karnesi" in h2


def test_stok_kartina_bagli_ve_salt_okur():
    s = (KOK / "kayranpm" / "stok_karti.py").read_text(encoding="utf-8")
    t5 = s[s.index("    with t5:"):s.index("    with t6:")]
    assert t5.index("_karne_ciz(sku)") < t5.index("# Marj sağlığı")          # Analiz'in en üstünde
    kod = (KOK / "kayranpm" / "urun_karnesi.py").read_text(encoding="utf-8")
    # Veritabanına doğrudan erişim yok (yalnız mevcut okuma fonksiyonları); ayar yazımı yok
    for yasak in (".table(", "get_client(", "set_ayar(", "_temizle("):
        assert yasak not in kod, yasak
