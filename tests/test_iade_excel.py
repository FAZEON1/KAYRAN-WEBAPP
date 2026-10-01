# -*- coding: utf-8 -*-
"""Satış › İade — Excel çıktısı (devir notu madde 6). İade sayfasında indirme yoktu."""
import io
from pathlib import Path

import pandas as pd

from satis.main import iade_excel_bytes

KOK = Path(__file__).resolve().parent.parent

OZET = [{"sku": "A1", "urun_adi": "Ürün A", "s_adet": 10, "i_adet": 2, "net_adet": 8,
         "s_ciro": 1000.456, "i_tutar": 200.0, "net_ciro": 800.456, "s_kar": 150.0}]
IADE = [{"tarih": "2026-09-30T00:00:00", "kanal": "VATAN", "sku": "A1", "urun_adi": "Ürün A", "iade_adet": 2,
         "iade_brut": 220, "iade_iskonto": 10, "iade_masraf": 10, "iade_net": 200, "depo": "MERKEZ DEPO", "kaynak": "excel"},
        {"tarih": "2026-09-29", "kanal": "", "sku": "B2", "urun_adi": None, "iade_adet": 1,
         "iade_net": "5.5", "depo": None, "kaynak": "manuel"}]


def test_dort_sayfa_ve_ham_sayilar():
    x = pd.read_excel(io.BytesIO(iade_excel_bytes(OZET, IADE, "2026-01-01", "2026-12-31")), sheet_name=None)
    assert list(x) == ["SKU Net", "Firma", "SKU + Firma", "Kayıtlar"]
    sn = x["SKU Net"]
    assert sn.loc[0, "Net adet"] == 8 and abs(sn.loc[0, "Satış ciro ($)"] - 1000.46) < 1e-9
    assert pd.api.types.is_numeric_dtype(sn["Satış ciro ($)"])          # metin değil, toplanabilir
    f = x["Firma"]
    assert set(f["Firma / Cari"]) == {"VATAN", "(cari belirsiz)"} and f["İade adet"].sum() == 3
    k = x["Kayıtlar"]
    assert list(k["Tarih"]) == ["2026-09-30", "2026-09-29"] and k.loc[1, "İade net ($)"] == 5.5
    assert k.loc[1, "Giren depo"] == "" or pd.isna(k.loc[1, "Giren depo"])


def test_bos_donem_patlamaz():
    x = pd.read_excel(io.BytesIO(iade_excel_bytes([], [], "2026-01-01", "2026-01-31")), sheet_name=None)
    assert len(x) == 4 and "kayıt yok" in str(x["SKU Net"].iloc[0, 0])


def test_iade_sayfasinda_indirme_var():
    kod = (KOK / "satis/main.py").read_text(encoding="utf-8")
    i = kod.index('elif _ssayfa == "↩️ İade":')
    assert 'key="iade_dl_xlsx"' in kod[i:] and "iade_excel_bytes(_satirlar, _ix_iadeler" in kod[i:]
