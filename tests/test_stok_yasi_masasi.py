# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Stok yaşı › Tüm ürünler salt okur liste masası (Ekim 2026, ortak masa shared/masa.py).

Satırlar ve rakamlar stok_yasi.urun_satirlari'ndan (FIFO, değer = adet × paçal); sıra eski tabloyla aynı
(ortalama yaş, en yaşlı üstte). Yan panel eskiden tablonun altında açılan parti listesini taşır. İşlem yok.
"""
from datetime import date

from kayranpm import stok_yasi as Y
from kayranpm import stok_yasi_masasi as M
from shared.masa import istek_al, kosul_uyar

BUGUN = date(2026, 10, 14)
P = lambda t, a, b="B", tur="ithalat": {"tarih": t, "adet": a, "belge": b, "tur": tur}  # noqa: E731


def _bizim():
    out = {}
    for k, ad, kat, stok, partiler in [
            ("A", "Ürün A", "ssd", 30, [P("2026-01-10", 20, "ITH-1"), P("2026-09-20", 15, "YI-1", "yurtici")]),
            ("B", "Ürün B", "monitör", 8, [P("2026-10-01", 5)]),                 # 3 adet kaydı yok
            ("C", "", "", 4, [P("2026-10-10", 10)])]:
        oz, kal = Y.urun_yasi(stok, partiler, BUGUN)
        out[k] = (oz, kal, {"sku": k, "urun_adi": ad, "kategori": kat})
    return out


PACAL = {"A": 10.0, "B": 2.5}


def test_satirlar_urun_satirlari_ile_ayni():
    bizim = _bizim()
    v = M.masa_verisi(bizim, PACAL, BUGUN)
    eski = Y.urun_satirlari(bizim, PACAL)
    assert [s["id"] for s in v["satirlar"]] == [r["_id"] for r in eski] == ["A", "B", "C"]
    a = {s["id"]: s for s in v["satirlar"]}["A"]
    ra = eski[0]
    assert a["stok_m"] == "30" and a["ort_m"] == f"{ra['Ort. yaş (gün)']} gün" and a["eski_m"] == "277 gün"
    assert a["yasli"] == sum(ra[g] for g in ("91–180 gün", "180+ gün")) == 15 and a["deger_m"] == "$300,00"
    assert ["10.01.2026 · ITH-1", "15 adet · 277 gün · İthalat"] in a["_detay"]
    assert ["20.09.2026 · YI-1", "15 adet · 24 gün · Yurt içi"] in a["_detay"]
    b = {s["id"]: s for s in v["satirlar"]}["B"]
    assert b["kayitsiz"] == 3 and b["kayitsiz_m"] == "3" and [Y.KAYITSIZ, "3 adet"] in b["_detay"]
    c = {s["id"]: s for s in v["satirlar"]}["C"]
    assert c["ad"] == "C" and c["deger_m"] == "$0,00"


def test_suzgec_ve_salt_okur():
    v = M.masa_verisi(_bizim(), PACAL, BUGUN)
    assert [o["k"] for o in v["secimler"][0]["secenekler"]] == ["monitör", "ssd"]
    an = {a["k"]: a["f"] for a in v["anahtarlar"]}
    assert [s["id"] for s in v["satirlar"] if kosul_uyar(s, an["yasli"])] == ["A"]
    assert [s["id"] for s in v["satirlar"] if kosul_uyar(s, an["kayitsiz"])] == ["B"]
    assert v["islemler"] == [] and "Bilinmeyen" in istek_al(v, {"islem": "ac", "ids": ["A"]})[1]
    assert not M.yurutucu()({"islem": "x", "ids": ["A"]})["ok"]


def test_panelde_parti_siniri():
    bizim = {"A": (*Y.urun_yasi(100, [P(f"2026-0{1 + i % 9}-1{i % 9}", 3, f"P{i}") for i in range(40)], BUGUN),
                   {"sku": "A", "urun_adi": "Çok partili"})}
    s = M.masa_verisi(bizim, {}, BUGUN)["satirlar"][0]
    parti = [d for d in s["_detay"] if " · P" in d[0]]
    assert len(parti) == M.PANEL_PARTI and "İlk 25 parti" in s["_not"]
