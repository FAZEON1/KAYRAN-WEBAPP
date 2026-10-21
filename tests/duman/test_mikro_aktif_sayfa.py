# -*- coding: utf-8 -*-
"""Sayfa testi · Toplam Aktifler + Mikro defter kalemleri (kayranacc/mikro_aktif_ekran.py, Ekim 2026).

Açıkken: döküm bölümü çizilir, toplam Mikro kalemleriyle hesaplanır ve Mikro'dan da gelen manuel kalem (SGK)
toplama girmez. Kapalıyken: bir kerelik onay kutusu, toplam eskisi gibi. Yalnız gerçek Streamlit kuruluyken."""
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


def _ac(acik):
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
    if acik:
        sahte_db.TABLOLAR["sistem_ayarlari"] = [{"anahtar": "mikro_aktif_durum", "deger": '{"acik": true}'}]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    for k, v in {"giris_yapildi": True, "aktif_kullanici": sahte_db.KULLANICI, "aktif_uygulama": "kayranacc",
                 "acc_sayfa": "💰 Toplam Aktifler"}.items():
        at.session_state[k] = v
    try:
        at.run()
    finally:
        os.environ.pop("DUMAN_ONBELLEK_TEMIZLE", None)
    return at


def test_acikken_dokum_ve_cift_sayim_yok():
    at = _ac(True)
    assert not [e for e in at.exception], [e.value for e in at.exception]
    etiket = [e.label for e in at.expander]
    assert any(e.startswith("Mikro defter kalemleri: + $") and "· − $" in e for e in etiket), etiket
    metin = _metin(at)
    assert "Mikro'dan da geldiği için toplama girmeyen manuel kalemler: Eylül SGK" in metin
    # manuel SGK (300 $) toplamdan çıkarılmadı: döküm çipinde "Manuel çıkarma" yok, Mikro SGK'sı var
    assert "Manuel çıkarma" not in metin and "Mikro defter (KDV, vergi, SGK…)" in metin


def test_kapaliyken_onay_kutusu():
    at = _ac(False)
    assert not [e for e in at.exception], [e.value for e in at.exception]
    assert any(e.label.startswith("Kasa, avans, KDV") for e in at.expander), [e.label for e in at.expander]
    assert "Mikro defter (KDV" not in _metin(at)
