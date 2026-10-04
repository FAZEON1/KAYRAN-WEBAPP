# -*- coding: utf-8 -*-
"""Sayfa testi betiği: stok kartını (Analiz sekmesindeki ürün karnesiyle) sahte veritabanıyla açar."""
import os
import sys

_BURASI = os.path.dirname(os.path.abspath(__file__))
_KOK = os.path.dirname(os.path.dirname(_BURASI))
for _y in (_KOK, _BURASI):
    if _y not in sys.path:
        sys.path.insert(0, _y)

import sahte_db  # noqa: E402

sahte_db.kur()

import streamlit as st  # noqa: E402
import shared.hata_log as _hl  # noqa: E402


def _kaydet(yer, hata=None, *a, **k):
    st.session_state.setdefault("_duman_hatalar", []).append(f"{yer}: {type(hata).__name__}: {str(hata)[:300]}")
    return True


_hl.kaydet = _kaydet
st.cache_data.clear()
for _ad in ("shared.tablo", "shared.islem"):
    _m = sys.modules.get(_ad)
    if _m is not None and hasattr(_m, "_BILESEN"):
        _m._BILESEN = None
from kayranpm.urun_karnesi import portfoy  # noqa: E402
portfoy.clear()
from kayranpm.stok_karti import goster  # noqa: E402
goster(os.environ.get("KARNE_SKU", "X24F165S"))
