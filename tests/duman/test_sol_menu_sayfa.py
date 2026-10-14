# -*- coding: utf-8 -*-
"""Sayfa testi: sol menü (shared/sol_menu.py, Ekim 2026) gerçek uygulamada çizilir ve tıklanınca modüle /
sayfaya gider (üst şeritle aynı oturum anahtarları); MENU_SOL = False eski düzeni geri getirir."""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_sayfalar import BETIK, SURE  # noqa: E402


def _uygulama():
    import sahte_db
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    st.cache_data.clear()
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = "anasayfa"
    return at


def _dugme(at, key):
    return next((b for b in at.sidebar.button if b.key == key), None)


def test_sol_menu_modul_ve_sayfaya_gider():
    at = _uygulama()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    for k in ("sol_anasayfa", "sol_kayranacc", "sol_satis", "sol_depo", "sol_daralt"):
        assert _dugme(at, k) is not None, k
    assert _dugme(at, "sol_kayranacc__banka") is None              # kapalı modülün sayfaları çizilmez
    _dugme(at, "sol_kayranacc").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["aktif_uygulama"] == "kayranacc"
    _dugme(at, "sol_kayranacc__banka").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["acc_sayfa"] == "🏦 Banka Bakiyeleri"
    assert _dugme(at, "sol_kayranacc__banka").proto.type == "primary"   # seçili sayfa vurgulu
    _dugme(at, "sol_depo").click().run()
    _dugme(at, "sol_depo__bekleyen").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert (at.session_state["aktif_uygulama"], at.session_state["depo_sayfa"]) == ("depo", "📦 Bekleyen Sevk Takibi")


def test_daraltinca_yalniz_moduller(monkeypatch):
    at = _uygulama()
    at.session_state["aktif_uygulama"] = "kayranacc"
    at.run()
    assert _dugme(at, "sol_kayranacc__bu_hafta") is not None
    _dugme(at, "sol_daralt").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert _dugme(at, "sol_kayranacc__bu_hafta") is None and _dugme(at, "sol_kayranacc") is not None


def test_geri_donus_anahtari(monkeypatch):
    from shared import gezinme
    monkeypatch.setattr(gezinme, "MENU_SOL", False)
    at = _uygulama()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert _dugme(at, "sol_kayranacc") is None
    assert any(b.key == "top_kayranacc" for b in at.button)             # üst şerit yerinde
