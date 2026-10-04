# -*- coding: utf-8 -*-
"""Paçal karşılaştırması (ithalat/pacal_hesap) — ana veri entegrasyonu Faz 2a.

Karşılaştırmanın değeri "eski" değerlerin bugünkü ekranlarla BİREBİR aynı çıkmasına
bağlı. İlk testler bunu gerçek fonksiyonlara karşı kanıtlar (get_sku_maliyet_ozet,
get_sku_alim_detay, get_pacal_map); sonrakiler yeni tanımı ve sebepleri sınar.
Veritabanı yok: get_dosyalar / get_tum_kalemler sahtelenir, gerçek hesap zinciri koşar.
"""
import pytest

import ithalat.database as idb
from ithalat import pacal_hesap as P
from shared.utils import sku_anahtar


def _dosya(did, durum="", masraf=None, tarih="2026-01-01"):
    return {"id": did, "durum": durum, "tarih": tarih, "masraflar": masraf or {}, "fatura_indirim": 0}


def _kalem(did, sku, adet, fob, kategori="GENEL"):
    return {"dosya_id": did, "sku": sku, "adet": adet, "birim_fob": fob, "kategori": kategori}


DOSYALAR = [
    _dosya(1, "Teslim Alındı", {"navlun": 500.0}, "2026-01-01"),    # X1 100×5 + 500 masraf → %100 → 10
    _dosya(2, "Yolda", None, "2026-03-01"),                          # masrafsız → final = FOB 6
    _dosya(3, "Teslim Alındı", {"navlun": 2000.0}, "2026-02-01"),   # 2 kalem × 1000 + 2000 → %100 → 20
    _dosya(4, "Teslim Alındı", {"navlun": 500.0}, "2026-01-15"),    # X24 100×5 + 500 → %100 → 10
]
KALEMLER = [
    _kalem(1, "X1", 100, 5.0),                 # X1: teslim 100 @10 + yolda 100 @6
    _kalem(2, "X1", 100, 6.0),
    _kalem(3, "Fazeon X24", 100, 10.0),        # X24 iki yazımla: 'Fazeon X24' 100 @20,
    _kalem(3, "X24", 100, 10.0),               #   'X24' 100 @20 (dosya 3) + 100 @10 (dosya 4)
    _kalem(4, "X24", 100, 5.0),                #   → ham 'X24' ort 15; birleşik (20+20+10)/3
]


@pytest.fixture
def veri(monkeypatch):
    monkeypatch.setattr(idb, "get_dosyalar", lambda: DOSYALAR)
    monkeypatch.setattr(idb, "get_tum_kalemler", lambda: KALEMLER)
    return idb.get_parti_satirlari()


def test_parti_satirlari_yolda_isareti_ve_final(veri):
    x1 = sorted((s["yolda"], round(s["final"], 6)) for s in veri if s["sku"] == "X1")
    assert x1 == [(False, 10.0), (True, 6.0)]


def test_eski_tum_urunler_onceki_rakamlar(veri):
    """Faz 2b'den ÖNCEKİ Tüm Ürünler davranışı (ham SKU, yoldaki hariç) — karşılaştırma
    tablosunun 'önceki' sütunu bunu gösterir; değerler sabit tutulur."""
    assert P.eski_tum_urunler(veri) == pytest.approx({"X1": 10.0, "Fazeon X24": 20.0, "X24": 15.0})


def test_ozet_artik_yeni_tanimi_veriyor(veri):
    """Faz 2b: get_sku_maliyet_ozet tek tanım — anahtar sku_anahtar, yazımlar birleşik."""
    ozet = idb.get_sku_maliyet_ozet()
    yeni = P.yeni_pacal(veri, {}, sku_anahtar)
    assert set(ozet) == set(yeni) == {"X1", "X24"}
    for k in yeni:
        assert ozet[k]["pacal_final"] == pytest.approx(yeni[k])
    assert ozet["X24"]["toplam_adet"] == 300 and ozet["X24"]["dosya_sayisi"] == 2
    assert ozet["X24"]["son_tarih"] == "2026-02-01" and ozet["X24"]["son_final"] == pytest.approx(20.0)
    assert ozet["X1"]["toplam_adet"] == 100                  # yoldaki 100 adet yok


def test_eski_stok_karti_alim_detay_ortalamasiyla_birebir(veri):
    for sku in ("X1", "X24", "Fazeon X24"):
        al = idb.get_sku_alim_detay(sku)
        adet = sum(a["adet"] for a in al)
        beklenen = sum(a["final_birim"] * a["adet"] for a in al) / adet   # stok_karti.py'deki formül
        assert P.eski_stok_karti(veri)[sku] == pytest.approx(beklenen)


def test_eski_pnl_onceki_rakamlar(veri):
    """Faz 2b'den ÖNCEKİ P&L: yazımlardan yalnız ilki ('Fazeon X24' → 20) + yurt içi."""
    eski = P.eski_pnl(veri, {"AV1": 7.0, "X1": 99.0}, sku_anahtar)
    assert eski == pytest.approx({"X1": 10.0, "X24": 20.0, "AV1": 7.0})


def test_get_pacal_map_yeni_tanimla_birebir(veri, monkeypatch):
    """Faz 2b: P&L / Teknik Servis / Tüm Ürünler / ürün kartı = tek tanım."""
    import satis.database as sdb
    kartlar = [{"sku": "AV1", "alis_fiyati": 7.0}, {"sku": "X1", "alis_fiyati": 99.0}]
    monkeypatch.setattr(sdb, "_urunler_hepsi", lambda secim: kartlar)
    gercek = sdb.get_pacal_map()
    yeni = P.yeni_pacal(veri, {k["sku"]: k["alis_fiyati"] for k in kartlar}, sku_anahtar)
    assert set(gercek) == set(yeni)
    for k in yeni:
        assert gercek[k] == pytest.approx(yeni[k])


def test_yeni_tanim(veri):
    y = P.yeni_pacal(veri, {"AV1": 7.0, "X1": 99.0}, sku_anahtar)
    assert y["X1"] == pytest.approx(10.0)                         # yoldaki hariç; kart alışı ezemez
    assert y["X24"] == pytest.approx((100 * 20 + 100 * 20 + 100 * 10) / 300)   # tüm yazımlar birleşik
    assert y["AV1"] == pytest.approx(7.0)                         # yurt içi


def test_karsilastirma_sebepleri(veri):
    kartlar = [{"sku": "X1", "urun_adi": "Ürün 1", "alis_fiyati": 0},
               {"sku": "X24", "urun_adi": "Monitör 24", "alis_fiyati": 0},
               {"sku": "AV1", "urun_adi": "Kaspersky", "alis_fiyati": 7.0}]
    rows, oz = P.karsilastir(veri, kartlar, sku_anahtar)
    r = {x["SKU"]: x for x in rows}
    assert r["X1"]["Önceki ürün kartı maliyeti"] == pytest.approx(8.0) and r["X1"]["Önceki Tüm Ürünler maliyeti"] == pytest.approx(10.0)
    assert P.SEBEP_YOLDA in r["X1"]["Sebep"] and "100 adet" in r["X1"]["Sebep"]
    assert P.SEBEP_YAZIM in r["X24"]["Sebep"] and "Fazeon X24 · X24" in r["X24"]["Sebep"]
    assert r["X24"]["Önceki Tüm Ürünler maliyeti"] == pytest.approx(15.0) and r["X24"]["Şimdiki maliyet"] == pytest.approx(50 / 3)
    assert P.SEBEP_YURTICI in r["AV1"]["Sebep"] and r["AV1"]["Önceki Tüm Ürünler maliyeti"] is None
    assert oz["urun"] == 3 and oz["farkli"] == 3 and oz["sebep"][P.SEBEP_YOLDA] == 1


def test_tutarli_urun_listede_yok(monkeypatch):
    monkeypatch.setattr(idb, "get_dosyalar", lambda: [_dosya(1, "Teslim Alındı", {"navlun": 100.0})])
    monkeypatch.setattr(idb, "get_tum_kalemler", lambda: [_kalem(1, "Z9", 10, 10.0)])
    rows, oz = P.karsilastir(idb.get_parti_satirlari(), [{"sku": "Z9", "urun_adi": "z"}], sku_anahtar)
    assert rows == [] and oz == {"urun": 1, "farkli": 0, "sebep": {}}


def test_kart_sku_yazimi_farkli(monkeypatch):
    monkeypatch.setattr(idb, "get_dosyalar", lambda: [_dosya(1, "Teslim Alındı", {"navlun": 100.0})])
    monkeypatch.setattr(idb, "get_tum_kalemler", lambda: [_kalem(1, "X24F165S", 10, 10.0)])
    rows, _ = P.karsilastir(idb.get_parti_satirlari(), [{"sku": "x24f165s ", "urun_adi": "m"}], sku_anahtar)
    assert rows[0]["Önceki Tüm Ürünler maliyeti"] is None and rows[0]["Şimdiki maliyet"] == pytest.approx(20.0)
    assert P.SEBEP_KART in rows[0]["Sebep"]


def test_paçal_tek_kapi_korumasi():
    """Faz 2b: ekranlar paçalı kendileri hesaplamasın, tek kapıdan alsın."""
    import pathlib
    kok = pathlib.Path(__file__).resolve().parent.parent
    kart = (kok / "kayranpm" / "stok_karti.py").read_text(encoding="utf-8")
    assert 'sum(_f(a["final_birim"]) * _f(a["adet"]) for a in alimlar)' not in kart   # yoldakiler dahil eski ortalama
    assert "get_pacal_map" in kart
    ana = (kok / "kayranpm" / "analitik.py").read_text(encoding="utf-8")
    assert ana.count("_pcl_map.get(_skn_a(sku)") == 2 and "_ith_map.get(sku)" not in ana
    ith = (kok / "ithalat" / "database.py").read_text(encoding="utf-8")
    oz = ith[ith.index("def get_sku_maliyet_ozet"):ith.index("def get_sku_ithalat_partileri")]
    assert "get_parti_satirlari()" in oz and "sku_anahtar" in oz
