# -*- coding: utf-8 -*-
"""Sipariş yükleme · eksik stoğu başka depodan tamamlama, gerçek Streamlit'le (Ekim 2026).
Eksik ürün, stoğu olan depolar adetleriyle listelenir; seçilen depolardan plan çıkar."""
import os

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
BURASI = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(os.path.dirname(BURASI))


def _uygulama(kok, burasi):
    import sys
    for p in (kok, burasi):
        if p not in sys.path:
            sys.path.insert(0, p)
    import sahte_db
    sahte_db.kur()
    import streamlit as st
    import kayranpm.database as KD
    KD.get_satis_depolari = lambda sku=None: ["MERKEZ DEPO", "HAPPY LIFE", "İADE DEPO"]
    KD.get_sku_depo_dagilim = lambda sku: {"X24F240P": {"MERKEZ DEPO": 5, "HAPPY LIFE": 12, "İADE DEPO": 2},
                                           "X27F300": {"MERKEZ DEPO": 40}}.get(sku, {})
    from satis.main import _sg_depo_sec
    sec, plan = _sg_depo_sec("t", [{"sku": "X24F240P", "adet": 8}, {"sku": "X27F300", "adet": 10}])
    st.write("PLAN=" + repr(sorted(plan.items())))


def _plan(at):
    return next(m.value for m in at.markdown if str(m.value).startswith("PLAN="))


def test_eksik_urun_depodan_tamamlanir():
    at = AppTest.from_function(_uygulama, args=(KOK, BURASI), default_timeout=90).run()
    assert not at.exception
    assert len(at.multiselect) == 1                       # yalnız eksik olan X24F240P
    ms = at.multiselect[0]
    assert "X24F240P" in ms.label and "3 eksik" in ms.label
    assert ms.options == ["HAPPY LIFE (12 adet)", "İADE DEPO (2 adet)"]
    assert _plan(at) == "PLAN=[]"
    ms.set_value(["İADE DEPO", "HAPPY LIFE"]).run()
    assert _plan(at) == "PLAN=[(('MERKEZ DEPO', 'X24F240P'), [('İADE DEPO', 2.0), ('HAPPY LIFE', 1.0)])]"
    assert any("eksik tamamlandı" in str(c.value) for c in at.caption)
