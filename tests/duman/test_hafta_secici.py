# -*- coding: utf-8 -*-
"""Sayfa testi · Muhasebe üst satırındaki hafta düğmesi (Ekim 2026): tıklanınca haftalar listelenir, bir
haftaya basınca o hafta aktif olur (eskiden yalnız etiketti; geçmiş haftaya Ödenenler & Geçmiş'ten
geçiliyordu). Yalnız gerçek Streamlit kuruluyken çalışır (CI: "Sayfa testi")."""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_dosya_kapisi import _sorunlar  # noqa: E402
from test_sayfalar import BETIK, SURE  # noqa: E402


def test_hafta_dugmesi_tek_tikla_haftayi_degistirir(monkeypatch):
    monkeypatch.setenv("DUMAN_ONBELLEK_TEMIZLE", "1")   # önceki sayfa testlerinin (boş veri) önbelleği örtmesin
    import sahte_db
    from streamlit.testing.v1 import AppTest
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    sahte_db.TABLOLAR["haftalar"] = [
        {"id": 7, "hafta_adi": "05.10.2026 GÜNCEL ÖDEME LİSTESİ", "yuklendi_tarih": "05.10.2026", "aktif": 0},
        {"id": 8, "hafta_adi": "12.10.2026 GÜNCEL ÖDEME LİSTESİ", "yuklendi_tarih": "12.10.2026", "aktif": 1}]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = "kayranacc"
    at.session_state["acc_sayfa"] = "💳 Bu Hafta"
    at.run()
    assert not _sorunlar(at), _sorunlar(at)
    aktif, eski = at.button(key="acc_hafta_8"), at.button(key="acc_hafta_7")
    assert aktif.disabled and not eski.disabled
    assert "12.10.2026" in aktif.label and "05.10.2026" in eski.label
    import kayranacc.database as D
    cagri = []
    monkeypatch.setattr(D, "hafta_aktif_yap", lambda i: cagri.append(i))
    eski.click().run()
    assert not _sorunlar(at), _sorunlar(at)
    assert cagri == [7]
