# -*- coding: utf-8 -*-
"""Sayfa testi · Ürün Yönetimi › Müşteri Satışları › Kategori × Müşteri (Ekim 2026): müşterilerdeki stok
kategori × müşteri tablosu, adet ve paçal değer ($). Yalnız gerçek Streamlit kuruluyken çalışır."""
from datetime import date, timedelta

import pytest

pytest.importorskip("streamlit.testing.v1")

from test_dosya_kapisi import _sorunlar  # noqa: E402
from test_sayfalar import BETIK, SURE  # noqa: E402


def test_kategori_musteri_tablosu(monkeypatch):
    import sahte_db
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("DUMAN_ONBELLEK_TEMIZLE", "1")
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    t = str(date.today() - timedelta(days=date.today().weekday() + 7))     # geçen haftanın pazartesi
    sahte_db.TABLOLAR["urunler"] = [
        {"sku": "X24F165S", "urun_adi": "FAZEON 24 MONITOR", "kategori": "Monitör", "alis_fiyati": 50.0},
        {"sku": "K100", "urun_adi": "KLAVYE", "kategori": "Klavye", "alis_fiyati": 10.0}]
    sahte_db.TABLOLAR["firma_stok"] = [
        {"firma": "VATAN", "sku": "X24F165S", "urun_adi": "FAZEON 24 MONITOR", "stok_miktari": 12,
         "haftalik_satis": 3, "yukleme_tarihi": t},
        {"firma": "ITOPYA", "sku": "K100", "urun_adi": "KLAVYE", "stok_miktari": 20, "haftalik_satis": 5,
         "yukleme_tarihi": t}]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    for k, v in {"giris_yapildi": True, "aktif_kullanici": sahte_db.KULLANICI, "aktif_uygulama": "kayranpm",
                 "pm_sayfa": "📈  Müşteri Satışları", "mhs_gorunum": "Kategori × Müşteri"}.items():
        at.session_state[k] = v
    at.run()
    assert not _sorunlar(at), _sorunlar(at)
    df = at.dataframe[0].value
    assert list(df.columns)[0] == "Kategori" and list(df.columns)[-1] == "Toplam"
    assert df.iloc[-1]["Kategori"] == "Toplam" and int(df.iloc[-1]["Toplam"]) == 32
    assert any("32 adet · $800,00" in c.value for c in at.caption)          # 12×50 + 20×10
    at.session_state["mhs_matris_birim"] = "Değer ($)"
    at.run()
    assert not _sorunlar(at), _sorunlar(at)
    assert float(at.dataframe[0].value.iloc[-1]["Toplam"]) == 800.0
