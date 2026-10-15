# -*- coding: utf-8 -*-
"""Kanal stoğu — pazaryeri kodlu raporlar (Ekim 2026). HB ve AVASYA stok raporunu kendi kodlarıyla
gönderiyor ('HBCV0000GNT2JZ', 'MON24FAZX24F240PZ'); kanal_stoklari SKU'yu karta birebir bağladığı için
bu stok hiçbir ürüne düşmüyor ve Ürünler ekranının müşteri süzgecinde bu müşteriler çıkmıyordu.
kanal_kod_karsilastir salt okunur: bugünkü (eski) ve önerilen (Müşteri Satışları kuralı) bağlamayı
yan yana verir, hiçbir şey yazmaz."""

KARTLAR = {
    "X27F182S": {"urun_adi": "FAZEON X27F182S 27\" 180HZ"},
    "X24F240P": {"urun_adi": "FAZEON X24F240P 24\" 240HZ"},
    "X27F300S": {"urun_adi": "FAZEON X27F300S 27\" 300HZ"},
    "X27F300B": {"urun_adi": "FAZEON X27F300B 27\" 300HZ BEYAZ"},
    "A2120TRA": {"urun_adi": "FAZEON A2120TRA SOGUTUCU"},
}


def _r(firma, sku, adet, ad="", t="2026-10-11"):
    return {"firma": firma, "sku": sku, "urun_adi": ad, "stok_miktari": adet, "yukleme_tarihi": t}


ROWS = [
    _r("VATAN", "X27F182S", 400, "FAZEON X27F182S"),
    _r("VATAN", "X27F182S", 999, "FAZEON X27F182S", t="2026-10-04"),     # eski rapor: sayılmaz
    _r("HB", "HBCV0000GNT2JZ", 299, "Fazeon X27F182S 27# 180Hz 0.5ms Fast IPS"),
    _r("HB", "HBCV00007TAN7S", 567, "FAZEON X27F300 27\" 300Hz"),       # iki karta önek: belirsiz
    _r("HB", "HBCV0000ZZZZZZ", 5, "Bilinmeyen ürün"),
    _r("AVASYA", "MON24FAZX24F240PZ", 388, "Fazeon 23.8\" 240Hz Oyuncu Monitörü X24F240P"),
    _r("ITOPYA", "A2120TRA", 8101, "FAZEON A2120TRA"),
    _r("ITOPYA", "V90", 35, "EXCAVATOR V90 9cm"),
]


def _k(**kw):
    from kayranpm.stok_hesap import kanal_kod_karsilastir
    return kanal_kod_karsilastir(ROWS, KARTLAR, **kw)


def test_bugunku_kanal_stoklari_pazaryeri_kodunu_karta_baglamaz():
    """Sorunun kendisi: HB'nin X27F182S stoğu (299) kart anahtarında yok."""
    from kayranpm.stok_hesap import kanal_stoklari
    from shared.utils import sku_anahtar
    k = kanal_stoklari(ROWS)
    assert sku_anahtar("X27F182S") not in k["HB"]
    assert k["VATAN"][sku_anahtar("X27F182S")] == 400


def test_kodlar_eski_ve_yeni_kart():
    kod = {(k["firma"], k["kod"]): k for k in _k()["kodlar"]}
    assert kod[("VATAN", "X27F182S")]["durum"] == "bagli"
    assert kod[("VATAN", "X27F182S")]["adet"] == 400                    # yalnız son rapor
    hb = kod[("HB", "HBCV0000GNT2JZ")]
    assert (hb["eski_kart"], hb["yeni_kart"], hb["durum"], hb["kaynak"]) == ("", "X27F182S", "yeni", "addaki model kodu")
    av = kod[("AVASYA", "MON24FAZX24F240PZ")]
    assert (av["yeni_kart"], av["durum"]) == ("X24F240P", "yeni")
    bel = kod[("HB", "HBCV00007TAN7S")]
    assert (bel["yeni_kart"], bel["durum"]) == ("", "belirsiz")         # program seçim yapmaz
    assert sorted(bel["adaylar"]) == ["X27F300B", "X27F300S"]
    assert kod[("HB", "HBCV0000ZZZZZZ")]["durum"] == "yok"
    assert kod[("ITOPYA", "V90")]["durum"] == "yok"


def test_onayli_eslesme_tablosu_once_gelir():
    kod = {(k["firma"], k["kod"]): k for k in _k(eslesme={"HBCV00007TAN7S": "X27F300S"})["kodlar"]}
    k = kod[("HB", "HBCV00007TAN7S")]
    assert (k["yeni_kart"], k["durum"], k["kaynak"]) == ("X27F300S", "yeni", "onaylı eşleme")


def test_musteri_ve_urun_toplamlari():
    s = _k()
    m = {x["firma"]: x for x in s["musteriler"]}
    assert (m["HB"]["toplam"], m["HB"]["eski"], m["HB"]["yeni"], m["HB"]["bagsiz"]) == (871, 0, 299, 572)
    assert (m["AVASYA"]["eski"], m["AVASYA"]["yeni"]) == (0, 388)
    assert (m["VATAN"]["eski"], m["VATAN"]["yeni"], m["VATAN"]["bagsiz"]) == (400, 400, 0)
    assert (m["ITOPYA"]["eski"], m["ITOPYA"]["yeni"], m["ITOPYA"]["bagsiz"]) == (8101, 8101, 35)
    assert s["toplam"] == {"toplam": 400 + 871 + 388 + 8136, "eski": 8501, "yeni": 8501 + 299 + 388,
                           "bagsiz": 572 + 35}
    u = {x["kart"]: x for x in s["urunler"]}
    assert (u["X27F182S"]["eski"], u["X27F182S"]["yeni"]) == (400, 699)
    assert (u["X24F240P"]["eski"], u["X24F240P"]["yeni"]) == (0, 388)
    assert "A2120TRA" not in u                                          # değişmeyen ürün listelenmez
    assert [x["kart"] for x in s["urunler"]] == ["X24F240P", "X27F182S"]  # fark büyükten küçüğe


def test_bos_veri():
    from kayranpm.stok_hesap import kanal_kod_karsilastir
    s = kanal_kod_karsilastir([], {})
    assert s["kodlar"] == [] and s["toplam"] == {"toplam": 0, "eski": 0, "yeni": 0, "bagsiz": 0}
