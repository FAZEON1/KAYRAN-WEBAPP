# -*- coding: utf-8 -*-
"""Sayfa testi · Bu Hafta: ödeme listesi Mikro'dan her pazartesi (kullanıcı kararı 22.10.2026).

Açıkken (varsayılan): "Mikro'dan yenile" ve "Firma vadeleri" düğmeleri, "Mikro'dan öneri" yok; iki düğme de
boş veritabanında çökmeden çalışır. Kapalıyken eski "Mikro'dan öneri". Yalnız gerçek Streamlit kuruluyken."""
import os

import pytest

pytest.importorskip("streamlit.testing.v1")

from test_sayfalar import BETIK, SURE  # noqa: E402


def _ac(kapali=False):
    import sahte_db
    from streamlit.testing.v1 import AppTest
    os.environ["DUMAN_ONBELLEK_TEMIZLE"] = "1"
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    if kapali:
        sahte_db.TABLOLAR["sistem_ayarlari"] = [{"anahtar": "mikro_odeme_durum", "deger": '{"acik": false}'}]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    for k, v in {"giris_yapildi": True, "aktif_kullanici": sahte_db.KULLANICI, "aktif_uygulama": "kayranacc",
                 "acc_sayfa": "💳 Bu Hafta"}.items():
        at.session_state[k] = v
    at.run()
    return at


def _dugme(at, etiket):
    return [b for b in at.button if b.label == etiket]


def _hatasiz(at):
    assert not [e for e in at.exception], [e.value for e in at.exception]


def test_mikro_acikken_yenile_ve_firma_vadeleri():
    try:
        at = _ac()
        _hatasiz(at)
        assert _dugme(at, "Mikro'dan yenile") and _dugme(at, "Firma vadeleri")
        assert not _dugme(at, "Mikro'dan öneri")
        _dugme(at, "Firma vadeleri")[0].click().run()
        _hatasiz(at)
        _dugme(at, "Mikro'dan yenile")[0].click().run()
        _hatasiz(at)
    finally:
        os.environ.pop("DUMAN_ONBELLEK_TEMIZLE", None)


def test_mikro_kapaliyken_eski_oneri_dugmesi():
    try:
        at = _ac(kapali=True)
        _hatasiz(at)
        assert _dugme(at, "Mikro'dan öneri") and not _dugme(at, "Mikro'dan yenile")
    finally:
        os.environ.pop("DUMAN_ONBELLEK_TEMIZLE", None)
