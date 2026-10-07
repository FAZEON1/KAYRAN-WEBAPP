# -*- coding: utf-8 -*-
"""Sayfa testi, ÖRNEK VERİYLE: Yönetim › Asistanlar ve İthalat › Gümrük danışmanı (Ekim 2026)."""
from datetime import datetime, timezone

import pytest

pytest.importorskip("streamlit.testing.v1")

from test_sayfalar import BETIK, SURE  # noqa: E402


def _calistir(tablolar, uygulama, anahtar, secim):
    import sahte_db
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    st.cache_data.clear()
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    for t, rows in tablolar.items():
        sahte_db.TABLOLAR[t] = rows
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = uygulama
    at.session_state[anahtar] = secim
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_asistanlar_ornek_veriyle():
    s = datetime.now(timezone.utc).isoformat()
    at = _calistir({
        "sistem_ayarlari": [{"anahtar": "telegram_webhook_gizli", "deger": "x" * 64},
                            {"anahtar": "telegram_kullanicilar", "deger": '{"123456789": "ibrahim"}'}],
        "asistan_rapor": [{"id": 1, "zaman": s, "asistan": "pazar", "baslik": "6-12 Ekim · panel fiyatı arttı",
                           "ozet": "27 inç panel fiyatı %6 arttı.", "icerik": "## Öne çıkanlar\n- Panel fiyatı arttı"}],
    }, "yonetim", "yon_sayfa", "Asistanlar")
    metin = " ".join(str(m.value) for m in at.markdown)
    assert "Asistanlar" in metin and "Bağlı hesaplar" in metin and "123456789" in metin and "ibrahim" in metin
    assert "Veritabanı kurulumu eksik" not in metin
    assert "Öne çıkanlar" in metin and "27 inç panel fiyatı" in metin
    assert [e.label for e in at.expander][-1].endswith("6-12 Ekim · panel fiyatı arttı")


def test_gumruk_danismani_ornek_veriyle():
    s = datetime.now(timezone.utc).isoformat()
    sonuc = {"gtip": "852852910000", "gtip_aciklama": "Bilgisayara bağlanan monitörler",
             "oranlar": {"gumruk_vergisi": 0, "ilave_gumruk_vergisi": 20, "kdv": 20},
             "ek_vergiler": [], "belgeler": ["TAREKS ürün güvenliği denetimi"], "uyarilar": ["Menşe teyit edilmeli"],
             "kaynaklar": ["https://www.ticaret.gov.tr"], "guven": "orta"}
    at = _calistir({"gumruk_sorgulari": [
        {"id": 2, "zaman": s, "urun": "27 inç IPS monitör", "mense": "Çin", "birim_fiyat": 100, "para": "USD",
         "adet": 50, "navlun": 400, "sigorta": 100, "durum": "tamam", "sonuc": sonuc,
         "ozet": "GTİP 8528.52.91; İGV %20."},
        {"id": 3, "zaman": s, "urun": "Kablosuz klavye", "mense": "Çin", "durum": "bekliyor"},
        {"id": 4, "zaman": s, "urun": "Bilinmeyen parça", "durum": "hata", "ozet": "Ürün tarifi yetersiz."},
    ]}, "ithalat", "ith_sayfa", "Gümrük danışmanı")
    metin = " ".join(str(m.value) for m in at.markdown)
    assert "Gümrük danışmanı" in metin and "8528.52.91.00.00" in metin
    assert "İlave gümrük vergisi %20" in metin and "TAREKS" in metin and "Ürün tarifi yetersiz." in metin
    # Vergi tablosu çizildi (kısa tablo st.html ile çizilir, AppTest okumaz; tutarlar test_asistanlar'da)
    assert any("Ek vergiler (damping vb.)" in str(c.value) for c in at.caption)
    assert any(b.label == "Yeniden dene" for b in at.button) and any(b.label == "Yenile" for b in at.button)
