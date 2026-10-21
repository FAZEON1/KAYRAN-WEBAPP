# -*- coding: utf-8 -*-
"""Sayfa testi · Depo › Depolar Arası Sevk, Mikro stok eşitlemesi açıkken (depo/mikro_sevk.py, Ekim 2026).

Açıkken sevk formu yok (kayıt düğmesi çizilmez), Mikro'daki sevkler listelenir; kapalıyken form eskisi gibi.
Yalnız gerçek Streamlit kuruluyken çalışır."""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_sayfalar import BETIK, SURE  # noqa: E402
from test_stok_yasi_veri import VERI, _metin, _sorunlar  # noqa: E402
from test_mikro_depo_sayfa import MIKRO, _h  # noqa: E402

SEVK = "🚚 Depolar Arası Sevk"


def _ac(acik):
    import os
    import sahte_db
    from streamlit.testing.v1 import AppTest
    os.environ["DUMAN_ONBELLEK_TEMIZLE"] = "1"
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    for t, rows in list(VERI.items()) + list(MIKRO.items()):
        sahte_db.TABLOLAR[t] = [dict(r) for r in rows]
    sahte_db.TABLOLAR["mikro_depo_hareket"].append(_h("e", "2026-10-12", 2, 6, 5, giris=4, cikis=1))
    if acik:
        sahte_db.TABLOLAR["sistem_ayarlari"] = [{"anahtar": "mikro_stok_durum", "deger": '{"acik": true}'}]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    for k, v in {"giris_yapildi": True, "aktif_kullanici": sahte_db.KULLANICI, "aktif_uygulama": "depo",
                 "depo_sayfa": SEVK}.items():
        at.session_state[k] = v
    try:
        at.run()
    finally:
        os.environ.pop("DUMAN_ONBELLEK_TEMIZLE", None)
    return at


def test_aciliyken_sevk_formu_yok_mikro_sevkleri_listelenir():
    at = _ac(True)
    assert not _sorunlar(at), _sorunlar(at)
    m = _metin(at)
    assert "sevk Mikro'da" in m and "2 sevk fişi · 2 kalem · 35 adet" in m
    assert not [b for b in at.button if b.key in ("dpo_ekle", "dpo_sevk_hepsi")]
    assert not [s for s in at.selectbox if s.key in ("dpo_kaynak", "dpo_hedef")]


def test_kapaliyken_sevk_formu_eskisi_gibi():
    at = _ac(False)
    assert not _sorunlar(at), _sorunlar(at)
    assert [s for s in at.selectbox if s.key == "dpo_kaynak"]
