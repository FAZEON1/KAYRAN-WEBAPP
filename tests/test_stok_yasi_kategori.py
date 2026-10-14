# -*- coding: utf-8 -*-
"""Stok yaşı › Müşterilerdeki stok: kategori süzgeci (Ekim 2026)."""
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _oz(stok):
    return ({"stok": stok, "ort_gun": 10, "en_eski_gun": 20, "gruplar": {"0–30 gün": stok}, "kapsanmayan": 0}, [])


MUS = {"VATAN": {"X24": _oz(25), "PAD1": _oz(5), "YOK9": _oz(3)},
       "ITOPYA": {"PAD1": _oz(40)}}
KAT = {"X24": "Monitör", "PAD1": "Mouse pad"}


def test_musteri_kategorileri_adede_gore():
    from kayranpm.stok_yasi import musteri_kategorileri, KATEGORISIZ
    assert musteri_kategorileri(MUS, KAT) == [("Mouse pad", 45), ("Monitör", 25), (KATEGORISIZ, 3)]
    assert musteri_kategorileri({}, KAT) == []


def test_kategori_suz_urunu_kalmayan_musteri_duser():
    from kayranpm.stok_yasi import musteri_kategori_suz, KATEGORISIZ
    m = musteri_kategori_suz(MUS, KAT, "Monitör")
    assert list(m) == ["VATAN"] and list(m["VATAN"]) == ["X24"]
    assert set(musteri_kategori_suz(MUS, KAT, "Mouse pad")) == {"VATAN", "ITOPYA"}
    assert list(musteri_kategori_suz(MUS, KAT, KATEGORISIZ)["VATAN"]) == ["YOK9"]
    assert musteri_kategori_suz(MUS, KAT, None) is MUS


def test_musteri_satirlari_kategori_sutunu():
    from kayranpm.stok_yasi import musteri_satirlari
    r = musteri_satirlari(MUS, kat_map=KAT)
    assert {x["SKU"]: x["Kategori"] for x in r if x["Müşteri"] == "VATAN"} == \
        {"X24": "Monitör", "PAD1": "Mouse pad", "YOK9": "Kategorisiz"}
    assert "Kategori" not in musteri_satirlari(MUS)[0]          # eski çağrı aynı kalır


def test_ekranda_suzgec():
    s = (KOK / "kayranpm/stok_yasi_ekran.py").read_text(encoding="utf-8")
    assert 'key="sy_m_kategori"' in s and "Y.musteri_kategori_suz(mus, kat_map, kat)" in s
