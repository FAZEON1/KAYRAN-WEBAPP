# -*- coding: utf-8 -*-
"""Sayfa testi · Sistem › Mikro bağlantısı (shared/mikro_saglik_ekran.py, Ekim 2026).

Aktarıcı yazıyorsa "normal", 45 dakikadır yazmadıysa kritik sorun görünür; sayfa boş veritabanıyla da açılır.
Yalnız gerçek Streamlit kuruluyken çalışır."""
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("streamlit.testing.v1")

from test_sayfalar import BETIK, SURE  # noqa: E402
from test_stok_yasi_veri import _metin, _sorunlar  # noqa: E402


def _ac(senk):
    import os
    import sahte_db
    from streamlit.testing.v1 import AppTest
    os.environ["DUMAN_ONBELLEK_TEMIZLE"] = "1"
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    sahte_db.TABLOLAR["mikro_senk_durum"] = senk
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    for k, v in {"giris_yapildi": True, "aktif_kullanici": sahte_db.KULLANICI,
                 "aktif_uygulama": "mikro_baglanti"}.items():
        at.session_state[k] = v
    try:
        at.run()
    finally:
        os.environ.pop("DUMAN_ONBELLEK_TEMIZLE", None)
    return at


def _satir(dk):
    t = (datetime.now(timezone.utc) - timedelta(minutes=dk)).isoformat()
    return {"tablo": "mikro_satis_satir", "son_cekim": t, "son_kayit_sayisi": 0, "son_hata": None, "guncelleme": t}


def test_aktarici_yaziyorsa_normal():
    at = _ac([_satir(5)])
    assert not _sorunlar(at), _sorunlar(at)
    assert any("Aktarım ve eşitleme normal" in e.value for e in at.success)
    assert not at.error


def test_aktarici_durduysa_kritik_sorun():
    at = _ac([_satir(120)])
    # sayfadaki tek kırmızı kutu beklenen sorun (çökme yok)
    assert _sorunlar(at) == ["Aktarıcı son kez 2 sa önce yazdı; Mikro'dan veri gelmiyor (sunucu 10.0.1.11)."]


def test_bos_veritabaninda_acilir():
    at = _ac([])
    assert not _sorunlar(at), _sorunlar(at)
    assert any("hiç veri gelmemiş" in e.value for e in at.warning)
    assert "Henüz kayıtlı tur yok" in _metin(at)
