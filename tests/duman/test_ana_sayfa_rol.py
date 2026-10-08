# -*- coding: utf-8 -*-
"""Sayfa testi, ÖRNEK VERİYLE: rol bazlı ana sayfa (Ekim 2026) — Kısayollarım, Bugün panelinde teknik servis /
ithalat / depo işleri, telefona kurulum düğmesi."""
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("streamlit.testing.v1")

from test_sayfalar import BETIK, SURE  # noqa: E402


def test_ana_sayfa_rol_bazli():
    import sahte_db
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    st.cache_data.clear()
    s = datetime.now(timezone.utc)
    eski = (s - timedelta(days=20)).isoformat()
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR.update({
        "kullanici_yetkileri": [dict(r) for r in sahte_db.YETKI],
        "bt_olcum": [{"id": i, "zaman": s.isoformat(), "modul": "satis", "sayfa": "satislar",
                      "kullanici": sahte_db.KULLANICI, "ms": 900} for i in range(3)]
                    + [{"id": 9, "zaman": s.isoformat(), "modul": "depo", "sayfa": "stok",
                        "kullanici": sahte_db.KULLANICI, "ms": 800}],
        "ts_kayitlar": [{"id": 1, "mevcut_durum": "teknisyende", "mal_kabul_tarihi": eski, "stok_adi": "Monitör A"}],
        "ithalat_dosyalari": [{"id": 1, "dosya_no": "IT-77", "durum": "Antrepoda",
                               "tahmini_varis": (s - timedelta(days=5)).date().isoformat()}],
        "depo_manuel_takip": [{"id": 1, "firma": "EERA", "fatura_adet": 10, "sevk_edilen": 2}],
    })
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = "anasayfa"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    metin = " ".join(str(m.value) for m in at.markdown)
    assert "Kısayollarım" in metin
    etiketler = [b.label for b in at.button]
    assert "Satış · Satışlar" in etiketler and "Depo · Depo stok" in etiketler
    assert etiketler.index("Satış · Satışlar") < etiketler.index("Depo · Depo stok")      # en çok açılan önce
    for baslik in ("Teknisyende 7 günü geçen cihaz", "Tahmini varışı geçmiş ithalat", "Sevki tamamlanmamış kayıt"):
        assert baslik in metin, baslik
    assert "Telefona kur" in etiketler
    # Telefon alt menüsü (masaüstünde CSS ile gizli): Ana sayfa · Modüller · Ara · Talep · Ben
    for d in ("Ana sayfa", "Ara", "Talep"):
        assert d in etiketler, d
    assert sum(1 for b in at.button if b.key and b.key.startswith("alt_mod_")) >= 7     # yetkili modüller
    assert "Telefona kur" in etiketler and etiketler.count("Telefona kur") == 2         # üst + alt menüdeki Ben
