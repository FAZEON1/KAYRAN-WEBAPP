# -*- coding: utf-8 -*-
"""Talep #43 (Serkan, 22.10.2026): "Stoktan depo seçmeden tüm stokların olduğu ürün listesi karşıma gelsin,
sonra ürüne tıkladığımda yanında tüm depoların stoklarını göstersin." Depo Stok › "Tüm depolar" (varsayılan)."""
from pathlib import Path

from depo.depo_hesap import TUM_DEPOLAR, tum_depo_stok
from depo.depo_masasi import stok_masa_verisi
from kayranpm.database import depo_dagilimi

KOK = Path(__file__).resolve().parent.parent


def test_tum_depolar_toplam_ve_depo_kirilimi():
    urunler = [{"sku": "X24F182S", "urun_adi": "Monitör", "depo_kirilim": {"MERKEZ DEPO": 120, "HAPPY LIFE": 40,
                                                                          "İADE DEPO": 0}},
               {"sku": "x24f182s ", "urun_adi": "", "depo_kirilim": {"OUTLET": 3}},       # aynı SKU, ikinci kart
               {"sku": "BOS", "urun_adi": "Stoksuz", "depo_kirilim": {"MERKEZ DEPO": 0}},
               {"sku": "K1", "urun_adi": "Kasa", "depo_kirilim": {"MERKEZ DEPO": 5}}]
    r = tum_depo_stok(urunler, depo_dagilimi)
    assert [x["sku"] for x in r] == ["X24F182S", "K1"]                     # stoksuz yok, adet azalan
    x = r[0]
    assert x["adet"] == 163 and x["urun_adi"] == "Monitör"
    assert x["depolar"][0][1] == 120 and len(x["depolar"]) == 3            # sıfır depo atılır


def test_masa_depolar_sutunu_ve_yan_panel():
    liste = [{"sku": "X24F182S", "urun_adi": "Monitör", "adet": 163,
              "depolar": [("MERKEZ DEPO", 120), ("HAPPY LIFE", 40), ("OUTLET", 3)]}]
    v = stok_masa_verisi(TUM_DEPOLAR, liste)
    s = v["satirlar"][0]
    assert s["_detay"] == [["MERKEZ DEPO", "120 adet"], ["HAPPY LIFE", "40 adet"], ["OUTLET", "3 adet"]]
    assert "depo_m" in [c["alan"] for c in v["sutunlar"]] and s["_buyuk_alt"] == "3 depoda"
    tek = stok_masa_verisi("MERKEZ DEPO", [{"sku": "A", "urun_adi": "", "adet": 1}])
    assert "depo_m" not in [c["alan"] for c in tek["sutunlar"]] and "_detay" not in tek["satirlar"][0]


def test_varsayilan_tum_depolar():
    s = (KOK / "depo" / "main.py").read_text(encoding="utf-8")
    assert '[TUM_DEPOLAR] + list(_depolar), key="dpo_icerik_depo"' in s
    assert "get_tum_depo_stok() if _tum" in s
