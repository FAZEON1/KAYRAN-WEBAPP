# -*- coding: utf-8 -*-
"""Sayfa testi · Mikro eşitlemeleri açıkken Toplam Aktifler sadeleşir (kullanıcı kararı 22.10.2026).

Açıkken: Excel durum kartları ("Yüklenmedi · üst menü › Dosya") ve "Yüklenen verileri temizle" düğmesi yok,
yerine tek satır kaynak notu. Kapalıyken: eski kartlar ve düğme. Yalnız gerçek Streamlit kuruluyken."""
import os

import pytest

pytest.importorskip("streamlit.testing.v1")

from test_sayfalar import BETIK, SURE  # noqa: E402
from test_stok_yasi_veri import _metin  # noqa: E402

NOT = "Stok, ithalat ödenen ve cari Mikro'dan, 15 dakikada bir."


def _ac(acik, sayfa="💰 Toplam Aktifler"):
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


def test_toplam_aktifler_mikro_acikken_kart_ve_temizle_yok():
    at = _ac(True)
    assert not [e for e in at.exception], [e.value for e in at.exception]
    metin = _metin(at)
    assert NOT in metin
    assert "Yüklenmedi · üst menü › Dosya" not in metin and "Henüz hesaplanmadı" not in metin
    assert "Stok değeri uygulamadan otomatik gelir" not in metin           # ikinci (tekrar) not yok
    assert "Yüklenen verileri temizle" not in _dugmeler(at)


def test_toplam_aktifler_mikro_kapaliyken_eski_ekran():
    at = _ac(False)
    assert not [e for e in at.exception], [e.value for e in at.exception]
    metin = _metin(at)
    assert NOT not in metin and "Yüklenmedi · üst menü › Dosya" in metin
    assert "Yüklenen verileri temizle" in _dugmeler(at)


def test_banka_bakiyeleri_mikro_acikken_acilir():
    at = _ac(True, "🏦 Banka Bakiyeleri")
    assert not [e for e in at.exception], [e.value for e in at.exception]
