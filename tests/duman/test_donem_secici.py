# -*- coding: utf-8 -*-
"""Dönem seçici gerçek Streamlit'le (Ekim 2026): pencereden hazır dönem seçilir, oklar kaydırır,
takvimden özel aralık girilir; dönen (bas, bit) ve düğme yazısı buna uyar."""
import os
from datetime import date

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _uygulama(kok):
    import sys as _s
    import streamlit as st
    _s.path.insert(0, kok)
    import datetime as _dt
    from shared import tarih
    tarih._bugun = lambda: _dt.date(2026, 10, 7)
    bas, bit = tarih.hizli_tarih_araligi("t", varsayilan="Son 30 gün")
    st.write(f"SONUC={bas.isoformat()}|{bit.isoformat()}")


def _ac():
    return AppTest.from_function(_uygulama, args=(KOK,), default_timeout=60).run()


def _sonuc(at):
    m = [e.value for e in at.markdown if str(e.value).startswith("SONUC=")]
    b, e = m[-1][6:].split("|")
    return date.fromisoformat(b), date.fromisoformat(e)


def _dugme(at, key):
    return next(b for b in at.button if b.key == key)


def test_hazir_donem_ok_ve_takvim():
    at = _ac()
    assert not at.exception
    assert _sonuc(at) == (date(2026, 9, 8), date(2026, 10, 7))
    bu_ay = next(b for b in at.button if b.label == "Bu ay")
    bu_ay.click().run()
    assert _sonuc(at) == (date(2026, 10, 1), date(2026, 10, 7))
    _dugme(at, "t_geri").click().run()
    assert _sonuc(at) == (date(2026, 9, 1), date(2026, 9, 30))
    _dugme(at, "t_ileri").click().run()
    assert _sonuc(at) == (date(2026, 10, 1), date(2026, 10, 7))     # geri + ileri = yine bu ay
    at.date_input(key="t_ozel").set_value((date(2026, 8, 3), date(2026, 8, 20))).run()
    assert _sonuc(at) == (date(2026, 8, 3), date(2026, 8, 20))
    assert _dugme(at, "t_geri").disabled                   # özel aralık kaydırılmaz
