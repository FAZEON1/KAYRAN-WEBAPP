# -*- coding: utf-8 -*-
"""Sayfa testi, ÖRNEK VERİYLE: Yönetim › Şirket belgeleri (Ekim 2026). Süre uyarısı, sürümler,
toplu indirme ve künye (kaydedilmemişse e-Defter ayarlarından dolu) çizilmeli."""
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("streamlit.testing.v1")

from test_sayfalar import BETIK, SURE  # noqa: E402


def _calistir(tablolar):
    import sahte_db
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    st.cache_data.clear()                              # önceki testin belge listesi önbellekte kalmasın
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    for t, rows in tablolar.items():
        sahte_db.TABLOLAR[t] = rows
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = "yonetim"
    at.session_state["yon_sayfa"] = "Şirket belgeleri"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_sirket_belgeleri_ornek_veriyle():
    bugun = datetime.now(timezone(timedelta(hours=3))).date()
    g = lambda n: (bugun + timedelta(days=n)).isoformat()   # noqa: E731
    belgeler = [
        {"id": 1, "zaman": g(-200), "tur": "Oda faaliyet belgesi", "ad": "faaliyet_eski.pdf", "yol": "a/1.pdf",
         "boyut": 120000, "belge_tarihi": g(-200), "bitis_tarihi": g(-20), "yukleyen": "ibrahim"},
        {"id": 2, "zaman": g(-10), "tur": "Oda faaliyet belgesi", "ad": "faaliyet_yeni.pdf", "yol": "a/2.pdf",
         "boyut": 130000, "belge_tarihi": g(-10), "bitis_tarihi": g(12), "yukleyen": "ibrahim"},
        {"id": 3, "zaman": g(-90), "tur": "Vergi levhası", "ad": "vergi_levhasi.pdf", "yol": "b/3.pdf",
         "boyut": 90000, "belge_tarihi": g(-90), "yukleyen": "ibrahim", "notu": "2025 yılı"},
        {"id": 4, "zaman": g(-400), "tur": "SGK borcu yoktur yazısı", "ad": "sgk.pdf", "yol": "c/4.pdf",
         "boyut": 50000, "belge_tarihi": g(-400), "bitis_tarihi": g(-370), "yukleyen": "ibrahim"},
    ]
    edefter = [{"id": 1, "unvan": "G5F TEKNOLOJI SANAYI TICARET ANONIM SIRKETI", "vkn": "3881881884",
                "telefon": "02164662888", "adres_cadde": "YUKARI DUDULLU MAH.", "adres_il": "İSTANBUL"}]
    at = _calistir({"sirket_belgeleri": belgeler, "edefter_ayarlar": edefter})
    metin = " ".join(str(m.value) for m in at.markdown)
    assert "Şirket belgeleri" in metin
    assert "SGK borcu yoktur yazısı: süresi" in metin and "doldu" in metin
    assert "Oda faaliyet belgesi: süresi" in metin and "12 gün kaldı" in metin
    assert "faaliyet_yeni.pdf" in metin and "Vergi levhası" in metin
    assert [e.label for e in at.expander] == ["Eski sürümler (1)"]
    assert "Künye henüz kaydedilmedi" in metin
    girdi = {t.label: t.value for t in at.text_input}
    assert girdi["Vergi no"] == "3881881884" and girdi["Ticari unvan"].startswith("G5F")
    assert "Vergi no: 3881881884" in at.code[0].value


def test_sirket_belgeleri_kurulmadan_ve_bos():
    at = _calistir({})
    metin = " ".join(str(m.value) for m in at.markdown)
    assert "Henüz belge yok" in metin or "Belge arşivi kurulmamış" in metin
