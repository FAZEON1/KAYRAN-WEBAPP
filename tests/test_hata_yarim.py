# -*- coding: utf-8 -*-
"""Hata ve yarım kalanlar (Ekim 2026).

1) Kâr / P&L süzgeçli iade kârı paçalı SKU'yu .upper() ile arıyordu: 'Fazeon X…' yazılmış iadede
   önek atılmadığından maliyet 0 bulunuyor, iade kârı olduğundan büyük düşülüyordu. Kampanyada da
   güncel paçal ham SKU ile aranıyordu ('Mio MiVue J30' ↔ kanonik anahtar).
2) st.metric: Streamlit yazıyı stMarkdownContainer > p içine koyuyor; gövde metni kuralı daha özgül
   olduğu için rakam 22px yerine 14px, etiket soluk/küçük değil düz metin çıkıyordu.
3) Kart boşlukları yazı ölçeği büyüyünce sıkışık kalmıştı.
"""
from pathlib import Path

import pytest

from test_satis_pnl import _p

KOK = Path(__file__).resolve().parent.parent


def test_suzgecli_iade_kari_onekli_skuda_pacali_bulur():
    from shared.utils import sku_anahtar
    r = _p(kanal="VATAN", iadeler=[{"kanal": "VATAN", "sku": "Fazeon K1", "iade_net": 50, "iade_adet": 1}],
           pacal={sku_anahtar("K1"): 30.0})
    assert r["itop"]["i_tutar"] == pytest.approx(50) and r["itop"]["i_kar"] == pytest.approx(20)


def test_kampanya_guncel_pacali_yazimdan_bagimsiz_bulur():
    from shared.utils import sku_anahtar
    from kayranpm.kampanya_hesap import kampanya_ozet
    kamp = {"id": 1, "baslangic_tarihi": "2026-09-01", "bitis_tarihi": "2026-09-30"}
    urun = [{"sku": "Mio MiVue J30", "satis_fiyati": 57, "pacal_maliyet": 0, "satilan_adet": 1,
             "birim_firma_destek": 0, "birim_ek_destek": 0}]
    o = kampanya_ozet(kamp, urun, {sku_anahtar("Mio MiVue J30"): 41.7})
    assert o["eksik_pacal"] == 0
    s = (KOK / "kayranpm/kampanya.py").read_text(encoding="utf-8")
    assert 'pacal = {sku_anahtar(u["sku"])' in s and 'pacal.get(sku_anahtar(u.get("sku")), 0)' in s


def test_metrik_yazisi_paragrafa_ulasir():
    from shared import tasarim as T
    css = T._streamlit_normalize().replace("{{", "{").replace("}}", "}")
    assert '.stApp [data-testid="stMetricValue"] [data-testid="stMarkdownContainer"] p' in css
    assert '.stApp [data-testid="stMetricLabel"] [data-testid="stMarkdownContainer"] p' in css
    assert 'div[data-testid="stMetricValue"],div[data-testid="stMetricValue"] div{' not in css


def test_kart_bosluklari_genisledi():
    from shared import tasarim as T
    y = T.YOGUNLUK["sik"]
    assert (y["kart_pad"], y["grid_gap"], y["serit_alt"]) == ("13px 17px", "12px", "16px")
