# -*- coding: utf-8 -*-
"""Manuel satış: paçal maliyet kartın yazımından bağımsız bulunur (Ekim 2026).

Canlıda 'Mio MiVue J30' manuel satışı maliyet 0 ile kaydedildi ("1 maliyetsiz", kâr %100) — ürünün
iki ithalat partisi var. get_pacal_map kanonik anahtarlıdır ('MIO MIVUE J30'); manuel satış penceresi
kartın yazımıyla arıyordu. Aynı sebeple SKU listesinde ürün iki kez görünüyordu.
"""
from pathlib import Path

from satis.database import pacal_bul, satis_sku_listesi

KOK = Path(__file__).resolve().parent.parent
PACAL = {"MIO MIVUE J30": 41.2, "X24F165S": 80.0, "ESKI-KOD": 12.0}   # get_pacal_map: kanonik anahtarlar
KARTLAR = {"Mio MiVue J30": {}, "X24F165S": {}, "Faze2": {}}


def test_kartin_yazimiyla_paçal_bulunur():
    assert pacal_bul(PACAL, "Mio MiVue J30") == 41.2
    assert pacal_bul(PACAL, "Fazeon X24F165S") == 80.0
    assert pacal_bul(PACAL, "Faze2") == 0.0 and pacal_bul(None, "x") == 0.0


def test_sku_listesinde_urun_bir_kez():
    assert satis_sku_listesi(KARTLAR, PACAL) == ["ESKI-KOD", "Faze2", "Mio MiVue J30", "X24F165S"]


def test_manuel_satis_ortak_aramayi_kullanir():
    s = (KOK / "satis" / "main.py").read_text(encoding="utf-8")
    assert "pacal.get(_sku" not in s and "_pacal = pacal_bul(pacal, _sku)" in s
    assert "set(pacal.keys())" not in s and "tum_sku = satis_sku_listesi(urun_map, pacal)" in s
