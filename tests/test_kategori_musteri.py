# -*- coding: utf-8 -*-
"""Müşteri Satışları › Kategori × Müşteri (Ekim 2026): müşterilerdeki stok kategori ve müşteri kırılımında,
adet ve paçal maliyetle değer ($). Stok = her (müşteri, SKU) için aralıktaki SON rapor (Kanal stoğu kuralı)."""
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent


def _r(firma, sku, stok, tarih="2026-10-05", magaza=0):
    return {"firma": firma, "sku": sku, "stok_miktari": stok, "stok_magaza": magaza,
            "haftalik_satis": 1, "yukleme_tarihi": tarih}


META = {"X24": {"kategori": "Monitör", "kart_sku": "X24"}, "Fazeon X27": {"kategori": "Monitör", "kart_sku": "X27"},
        "K100": {"kategori": "Klavye", "kart_sku": "K100"}, "Z9": {}}
PACAL = {"X24": 50.0, "X27": 80.0, "K100": 10.0}


def test_son_rapor_kategori_ve_musteri_kirilimi():
    from kayranpm.musteri_hesap import kategori_musteri
    rows = [_r("VATAN", "X24", 30, "2026-09-28"), _r("VATAN", "X24", 10),          # son rapor 10 (toplanmaz)
            _r("VATAN", "Fazeon X27", 4, magaza=1), _r("ITOPYA", "X24", 6),
            _r("ITOPYA", "K100", 20), _r("ITOPYA", "Z9", 3), _r("VATAN", "K100", 0)]
    m = kategori_musteri(rows, META, PACAL, sku_fn=lambda s: str(s).upper())
    s = {x["kategori"]: x for x in m["satirlar"]}
    assert s["Monitör"]["hucre"] == {"VATAN": (15, 10 * 50 + 5 * 80.0), "ITOPYA": (6, 300.0)}
    assert s["Monitör"]["adet"] == 21 and s["Monitör"]["usd"] == 1200.0
    assert s["Klavye"]["hucre"] == {"ITOPYA": (20, 200.0)}                     # 0 stoklu satır yok
    assert s["Kategorisiz"]["hucre"] == {"ITOPYA": (3, 0.0)} and m["maliyetsiz"] == ["Z9"]
    assert [x["kategori"] for x in m["satirlar"]] == ["Monitör", "Klavye", "Kategorisiz"]   # adede göre
    assert m["firmalar"] == ["ITOPYA", "VATAN"] and m["toplam"]["VATAN"] == (15, 900.0)
    assert m["adet"] == 44 and m["usd"] == pytest.approx(1400.0)


def test_kart_sku_ile_pacal_bulunur():
    """Rapor 'Fazeon X27' yazsa da kart SKU'su X27'nin paçalı kullanılır."""
    from kayranpm.musteri_hesap import kategori_musteri
    m = kategori_musteri([_r("VATAN", "Fazeon X27", 2)], META, PACAL, sku_fn=lambda s: str(s).upper())
    assert m["usd"] == 160.0 and not m["maliyetsiz"]


def test_bos():
    from kayranpm.musteri_hesap import kategori_musteri
    m = kategori_musteri([], {}, {})
    assert m["satirlar"] == [] and m["adet"] == 0 and m["firmalar"] == []


def test_matris_tablolari_toplam_satiri_ve_gorunen_ad():
    from kayranpm.musteri_hesap import kategori_musteri
    from kayranpm.musteri_ekran import matris_tablolari
    rows = [_r("VATAN", "X24", 10), _r("ITOPYA", "K100", 20)]
    m = kategori_musteri(rows, META, PACAL, sku_fn=lambda s: str(s).upper())
    adet, deger = matris_tablolari(m, ad_fn=lambda f: {"VATAN": "VATAN BİLGİSAYAR"}.get(f, f))
    assert list(adet[0]) == ["Kategori", "ITOPYA", "VATAN BİLGİSAYAR", "Toplam"]
    assert adet[0] == {"Kategori": "Klavye", "ITOPYA": 20, "VATAN BİLGİSAYAR": 0, "Toplam": 20}
    assert adet[-1] == {"Kategori": "Toplam", "ITOPYA": 20, "VATAN BİLGİSAYAR": 10, "Toplam": 30}
    assert deger[-1] == {"Kategori": "Toplam", "ITOPYA": 200.0, "VATAN BİLGİSAYAR": 500.0, "Toplam": 700.0}


def test_ekranda_gorunum():
    s = (KOK / "kayranpm/musteri_ekran.py").read_text(encoding="utf-8")
    assert '"Kategori × Müşteri": "matris"' in s and "_kategori_musteri(rows, meta, c3, bas, bit)" in s
    assert "get_pacal_map()" in s
