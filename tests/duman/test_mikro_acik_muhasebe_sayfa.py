# -*- coding: utf-8 -*-
"""Sayfa testi · Mikro eşitlemeleri açıkken Muhasebe sayfaları açılır. Toplam Aktifler sayfası 22.10.2026'da
Muhasebe'den kalktı (toplam eşitleme turunda hesaplanır, Yönetim panosunda; tests/duman/test_mikro_aktif_sayfa.py).
Yalnız gerçek Streamlit kuruluyken."""
import os

import pytest

pytest.importorskip("streamlit.testing.v1")

from test_sayfalar import BETIK, SURE  # noqa: E402
from test_stok_yasi_veri import _metin  # noqa: E402



def _ac(acik, sayfa="🏦 Banka Bakiyeleri"):
    import sahte_db
    from streamlit.testing.v1 import AppTest
    os.environ["DUMAN_ONBELLEK_TEMIZLE"] = "1"
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    if acik:
        sahte_db.TABLOLAR["sistem_ayarlari"] = [
            {"anahtar": a, "deger": '{"acik": true}'}
            for a in ("mikro_aktif_durum", "mikro_muhasebe_durum", "mikro_stok_degeri_durum")]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    for k, v in {"giris_yapildi": True, "aktif_kullanici": sahte_db.KULLANICI, "aktif_uygulama": "kayranacc",
                 "acc_sayfa": sayfa}.items():
        at.session_state[k] = v
    try:
        at.run()
    finally:
        os.environ.pop("DUMAN_ONBELLEK_TEMIZLE", None)
    return at


def _dugmeler(at):
    return [b.label for b in at.button]


def test_toplam_aktifler_muhasebede_yok():
    at = _ac(True)
    assert not [e for e in at.exception], [e.value for e in at.exception]
    from shared.gezinme import secenekler
    assert "💰 Toplam Aktifler" not in secenekler("kayranacc")


def test_banka_bakiyeleri_mikro_acikken_acilir():
    at = _ac(True, "🏦 Banka Bakiyeleri")
    assert not [e for e in at.exception], [e.value for e in at.exception]
