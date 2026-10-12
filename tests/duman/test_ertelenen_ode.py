# -*- coding: utf-8 -*-
"""Sayfa testi · Muhasebe › Ertelenen Ödemeler (Ekim 2026): satıra tıklayınca Bu Hafta'daki ödeme penceresi
açılır, ertelenen ödeme buradan ödendi işaretlenir (eskiden satırlar yalnız yazıydı, içine girilemiyordu).
Yalnız gerçek Streamlit kuruluyken çalışır (CI: "Sayfa testi")."""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_dosya_kapisi import _sorunlar  # noqa: E402
from test_sayfalar import BETIK, SURE  # noqa: E402


def test_ertelenen_odeme_tiklaninca_odeme_penceresi_acilir():
    import sahte_db
    from streamlit.testing.v1 import AppTest
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    sahte_db.TABLOLAR["bankalar"] = [{"id": 1, "hesap_adi": "Örnek TL", "para_birimi": "TL", "bakiye": 5_000_000.0}]
    sahte_db.TABLOLAR["odemeler"] = [{
        "id": 41, "hafta_id": 7, "firma": "Lccgame", "aciklama": "YOLDAKİ ÜRÜNLER VERGİSİ", "kategori": "ithalat",
        "vade": "2026-12-31", "orijinal_vade": "2026-08-24", "ertelendi_sayisi": 2, "tutar_tl": 1_350_000.0,
        "tutar_usd": 0, "durum": "bekliyor"}]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = "kayranacc"
    at.session_state["acc_sayfa"] = "⏳ Ertelenen Ödemeler"
    at.run()
    assert not _sorunlar(at), _sorunlar(at)
    at.button(key="tkb_satir_ert41").click().run()            # satıra tıkla → ödeme penceresi
    assert not _sorunlar(at), _sorunlar(at)
    # Bu Hafta'daki ödeme penceresi açıldı: banka seçimi ve "Ödendi" düğmesi bu ödeme için çizildi
    assert at.selectbox(key="od_banka_41") is not None
    ode = at.button(key="od_ode_41")
    assert ode.disabled                                       # banka seçilmeden ödenmez (açık karar)
