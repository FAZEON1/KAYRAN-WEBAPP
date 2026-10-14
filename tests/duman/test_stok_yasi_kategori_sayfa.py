# -*- coding: utf-8 -*-
"""Sayfa testi · Stok yaşı › Müşterilerdeki stok › Kategori süzgeci (Ekim 2026): kategori seçilince müşteri
özeti yalnız o kategorinin stoğunu gösterir. Yalnız gerçek Streamlit kuruluyken çalışır."""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_stok_yasi_veri import VERI, _sorunlar  # noqa: E402
from test_sayfalar import BETIK, SURE  # noqa: E402


def _ac(monkeypatch, kategori=None):
    import sahte_db
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("DUMAN_ONBELLEK_TEMIZLE", "1")
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    for t, rows in VERI.items():
        sahte_db.TABLOLAR[t] = [dict(r) for r in rows]
    sahte_db.TABLOLAR["firma_stok"] = sahte_db.TABLOLAR["firma_stok"] + [
        {"id": 2, "firma": "VATAN", "sku": "FAZE1", "stok_miktari": 7, "yukleme_tarihi": "2026-09-27"}]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    for k, v in {"giris_yapildi": True, "aktif_kullanici": sahte_db.KULLANICI, "aktif_uygulama": "kayranpm",
                 "pm_sayfa": "Stok Yaşı"}.items():
        at.session_state[k] = v
    if kategori:
        at.session_state["sy_m_kategori"] = kategori
    at.run()
    return at


def test_kategori_secenekleri_ve_suzme(monkeypatch):
    at = _ac(monkeypatch)
    assert not _sorunlar(at), _sorunlar(at)
    sec = at.selectbox(key="sy_m_kategori")
    assert sec.options[0] == "Tüm kategoriler" and {"Monitör (25 adet)", "Mouse Pad (7 adet)"} <= set(sec.options)
    at = _ac(monkeypatch, "Mouse Pad")
    assert not _sorunlar(at), _sorunlar(at)
    yazi = " ".join(str(c.value) for c in at.caption)
    assert "Yalnız **Mouse Pad** · 7 adet · 1 müşteri" in yazi
