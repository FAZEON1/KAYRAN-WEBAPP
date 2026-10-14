# -*- coding: utf-8 -*-
"""Ürün yüzü (Ekim 2026), gerçek Streamlit'le: eski KAYRANTS&W adresi (?s=kayrantsw) çökmeden açılır ve
var olan modüllere yönlendirir; ana sayfanın alt bilgisinde sürüm görünür."""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_sayfalar import _ac  # noqa: E402


def test_eski_tsw_adresi_depoya_goturur():
    at = _ac("kayrantsw", None, None)
    assert not at.exception
    etiketler = [b.label for b in at.button]
    assert "Depo" in etiketler and "Teknik servis" in etiketler and "Ana sayfa" in etiketler
    assert not any("YAKINDA" in str(m.value) for m in at.markdown)
    next(b for b in at.button if b.label == "Depo").click().run()
    assert not at.exception
    assert at.session_state["aktif_uygulama"] == "depo"


def test_ana_sayfada_surum():
    from shared.surum import surum_etiketi
    at = _ac("anasayfa", None, None)
    assert not at.exception
    assert any(surum_etiketi() in str(m.value) for m in at.markdown)
