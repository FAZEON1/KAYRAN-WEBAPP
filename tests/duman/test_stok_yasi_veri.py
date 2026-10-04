# -*- coding: utf-8 -*-
"""Sayfa testi, ÖRNEK VERİYLE: Stok yaşı ve Yurt içi alış sayfaları (Ekim 2026).

Boş veritabanıyla açılan genel sayfa testi (test_sayfalar.py) hesap yollarını çalıştırmaz. Burada
bir ithalat partisi, bir yurt içi alım, antrepoda bekleyen bir dosya, müşteri stoğu ve satışlar
olan küçük bir veriyle iki sayfa gerçek Streamlit'te çizilir; hata çıkmamalı, yaş rakamları ekranda
görünmeli. Yalnız gerçek Streamlit kuruluyken çalışır (CI: "Sayfa testi").
"""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_sayfalar import BETIK, SURE  # noqa: E402

VERI = {
    "urunler": [
        {"sku": "FAZE1", "urun_adi": "Fazeon faze1 Mouse Pad", "kategori": "Mouse pad", "bizim_stok": 120,
         "depo_kirilim": {"MERKEZ DEPO": 120}, "alis_fiyati": 0},
        {"sku": "X24F165S", "urun_adi": "Fazeon 24 Monitör", "kategori": "Monitör", "bizim_stok": 60,
         "depo_kirilim": {"MERKEZ DEPO": 40, "HAPPY LIFE": 20}},
    ],
    "ithalat_dosyalari": [
        {"id": 1, "dosya_no": "IT-1", "durum": "Teslim Alındı", "tarih": "2026-03-01", "teslim_tarihi": "2026-05-02",
         "teslim_deposu": "MERKEZ DEPO", "doviz": "USD", "kur": 1, "masraflar": {"navlun": 100}},
        {"id": 2, "dosya_no": "YI-20260701", "durum": "Teslim Alındı", "tarih": "2026-07-01",
         "teslim_tarihi": "2026-07-03", "teslim_deposu": "MERKEZ DEPO", "doviz": "TL", "kur": 40,
         "masraflar": {"nakliye": 10}, "alim_turu": "yurtici", "tedarikci": "Yerel Tedarik"},
        {"id": 3, "dosya_no": "IT-2", "durum": "Antrepoda", "tarih": "2025-12-01", "teslim_tarihi": None},
    ],
    "ithalat_kalemleri": [
        {"id": 1, "dosya_id": 1, "sku": "X24F165S", "adet": 100, "birim_fob": 80},
        {"id": 2, "dosya_id": 2, "sku": "FAZE1", "adet": 100, "birim_fob": 1.0},
        {"id": 3, "dosya_id": 3, "sku": "X24F165S", "adet": 50, "birim_fob": 80},
    ],
    "satislar": [
        {"id": 1, "tarih": "2026-08-10", "kanal": "VATAN", "sku": "X24F165S", "adet": 30, "birim_satis": 120},
        {"id": 2, "tarih": "2026-09-15", "kanal": "VATAN", "sku": "Fazeon X24F165S", "adet": 10, "birim_satis": 120},
    ],
    "firma_stok": [
        {"id": 1, "firma": "VATAN", "sku": "X24F165S", "stok_miktari": 25, "yukleme_tarihi": "2026-09-27"},
    ],
}


def _ac(secenek):
    import os
    import sahte_db
    from streamlit.testing.v1 import AppTest
    os.environ["DUMAN_ONBELLEK_TEMIZLE"] = "1"   # önceki sayfa testlerinin BOŞ veriyle doldurduğu önbellek
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    for t, rows in VERI.items():
        sahte_db.TABLOLAR[t] = [dict(r) for r in rows]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = "kayranpm"
    at.session_state["pm_sayfa"] = secenek
    try:
        at.run()
    finally:
        os.environ.pop("DUMAN_ONBELLEK_TEMIZLE", None)
    return at


def _sorunlar(at):
    s = [f"yakalanmamış: {e.value}" for e in at.exception]
    s += list(at.session_state["_duman_hatalar"]) if "_duman_hatalar" in at.session_state else []
    s += [m.value[:200] for m in at.error]
    return s


def _metin(at):
    return " ".join(str(m.value) for m in list(at.markdown) + list(at.caption) + list(at.warning) + list(at.info))


def test_stok_yasi_sayfasi_veriyle():
    at = _ac("Stok Yaşı")
    assert not _sorunlar(at), _sorunlar(at)
    m = _metin(at)
    assert "Satılabilir stok" in m and "Ağırlıklı ort. yaş" in m
    assert "180" in m or "gün" in m
    assert [t.label for t in at.tabs][:2] == ["Bizim stok", "Müşterilerdeki stok"]
    etiket = [d.label for d in at.get("download_button")]
    assert "Excel: tümü" in etiket and "Excel: tüm müşteriler" in etiket


def test_yurtici_alis_sayfasi_veriyle():
    at = _ac("💵  Yurt İçi Alış")
    assert not _sorunlar(at), _sorunlar(at)
    assert [t.label for t in at.tabs][:2] == ["Yeni alım", "Kayıtlı alımlar"]
    assert "Yedek maliyet" not in [t.label for t in at.tabs]
    assert "Yurt içi satın alma" in [t.value for t in at.text_input]          # tür sabit, seçim yok
