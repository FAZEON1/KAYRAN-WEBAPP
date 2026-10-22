# -*- coding: utf-8 -*-
"""Sayfa testi · Toplam aktifler ayrıntısı Yönetim panosunda (kayranacc/toplam_aktif_ekran.py, 22.10.2026).

Muhasebe › Toplam Aktifler sayfası kalktı; toplam eşitleme turunda hesaplanır. Yönetim › Özet'te pencerenin altında
Toplam Aktifler yetkilisi Mikro defter dökümünü ve manuel kalemleri görür; Mikro'dan da gelen manuel kalem (SGK)
"Mikro'dan geliyor, sayılmadı" diye işaretlenir. Yalnız gerçek Streamlit kuruluyken."""
import json
import os

import pytest

pytest.importorskip("streamlit.testing.v1")

from test_sayfalar import BETIK, SURE  # noqa: E402
from test_stok_yasi_veri import _metin  # noqa: E402

KAYIT = {"kalemler": [{"ad": "Kasa", "tl": 49600.0, "hesaplar": {"100.001": 49600.0}},
                      {"ad": "Ödenecek SGK", "tl": -24800.0, "hesaplar": {"361.01.001": -24800.0}}],
         "satis_maliyeti": {"oran": 0.02, "satis_tl": 100000.0, "masraf_tl": 2000.0, "donem": "10.2025 – 09.2026",
                            "kalemler": [{"kod": "770.03.018", "ad": "KARGO VE POSTA GİDERLERİ", "tl": 2000.0}]}}
SNAP = {"toplam": 1000.0, "kur": 49.6, "tarih": "2026-10-22", "stok": 500.0, "stok_carpan": 1.0,
        "defter_arti": 1000.0, "defter_eksi": 500.0, "satis_maliyeti": 10.0}


def _ac(acik=True, sayfa="Özet"):
    import sahte_db
    from streamlit.testing.v1 import AppTest
    os.environ["DUMAN_ONBELLEK_TEMIZLE"] = "1"
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    sahte_db.TABLOLAR["aktif_excel_verileri"] = [{"kullanici": "_SHARED_", "dosya_tipi": "mikro_defter",
                                                  "veri_json": json.dumps({"veri": KAYIT, "son_yukleyen": "Mikro",
                                                                           "yukleme_zamani": "2026-10-21"})}]
    sahte_db.TABLOLAR["aktif_manuel_kalemler"] = [
        {"id": 1, "kullanici": "ortak", "aciklama": "Eylül SGK", "tutar": 300, "para_birimi": "USD", "tip": "cikar"}]
    sahte_db.TABLOLAR["sistem_ayarlari"] = [{"anahtar": "toplam_aktif_snapshot", "deger": json.dumps(SNAP)}] + (
        [{"anahtar": "mikro_aktif_durum", "deger": '{"acik": true}'}] if acik else [])
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    for k, v in {"giris_yapildi": True, "aktif_kullanici": sahte_db.KULLANICI, "aktif_uygulama": "yonetim",
                 "yon_sayfa": sayfa}.items():
        at.session_state[k] = v
    try:
        at.run()
    finally:
        os.environ.pop("DUMAN_ONBELLEK_TEMIZLE", None)
    return at


def test_yonetimde_ayrinti_dokum_ve_cakisan_manuel():
    at = _ac(True)
    assert not [e for e in at.exception], [e.value for e in at.exception]
    etiket = [e.label for e in at.expander]
    assert any(e.startswith("Toplam aktifler ayrıntısı") for e in etiket), etiket
    metin = _metin(at)
    assert "Eylül SGK" in metin and "Mikro'dan geliyor, sayılmadı" in metin
    assert "Mikro defterinden gelen kalemler" in metin
    assert "Mikro defter (KDV, vergi, SGK…)" in metin                       # panodaki döküm


def test_defter_kapaliyken_ayrinti_acilir():
    at = _ac(False)
    assert not [e for e in at.exception], [e.value for e in at.exception]
    assert "Mikro defter kalemleri kapalı." in _metin(at)
