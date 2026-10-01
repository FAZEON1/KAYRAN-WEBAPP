# -*- coding: utf-8 -*-
"""Muhasebe — son paket (Ekim 2026): Ödenenler & Geçmiş · Toplam Aktifler ·
Cari Ekstre · e-Defter · Genel Bakış · Ertelenen (veritabanı denetimi).

Bulunan hatalar:
  • Geçmiş haftalarda "Sil" haftayı TÜM ödemeleriyle ONAYSIZ siliyordu
  • "Ödenen Ödemeler" sekmesi ödeme yoksa st.stop() ile sayfayı durduruyor,
    "Geçmiş Haftalar" ve "Çek Arşivi" boş kalıyordu
  • Çek arşivindeki çöp kutusu onaysız siliyordu
  • Toplam Aktifler her açılışta sonucu Yönetim Panosu'na YAZIYORDU — Excel'ler
    eksikken de (eksikler 0) → panodaki toplam eksik değerle eziliyordu
  • Cari Ekstre / e-Defter'de başlık iki kez; Cari Ekstre ham kategori anahtarı
  • e-Defter fişi boşken "Fark" kırmızı (hata gibi) görünüyordu
"""
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


def test_gecmis_silmeler_onayli_ve_st_stop_yok():
    g = _oku("kayranacc/gecmis_ekran.py")
    assert "st.stop()" not in g and "st.tabs(" not in g
    assert g.count("B.onayli_sil(") >= 3                       # hafta · çek · tüm çekler
    assert "ödemesiyle sil" in g                               # kaç ödemenin gideceği yazıyor
    m = _oku("kayranacc/main.py")
    assert "from .gecmis_ekran import render_gecmis" in m
    assert 'if st.button("Sil", key=f"sil_{h[\'id\']}"' not in m


def test_toplam_aktif_eksik_dosyada_panoya_yazilmaz():
    m = _oku("kayranacc/main.py")
    assert "if _snap_eksik:" in m and 'raise RuntimeError("eksik dosya: "' in m
    assert "_snap_ok = True if _snap_ayni else set_ayar(" in m       # aynıysa tekrar yazmaz
    assert "Veriler işlendi ve kaydedildi. Yönetim Panosu'na da yansıdı" not in m


def test_cift_baslik_ve_kategori_adi():
    c = _oku("kayranacc/cari_ekstre.py")
    assert "🧾 Cari Ekstre & Vade Yaşlandırma" not in c and "_KAT_AD.get(" in c
    e = _oku("kayranacc/edefter.py")
    assert "e-Defter (Genel Muhasebe)</div>" not in e
    import kayranacc.odeme_hesap as H
    assert H.KATEGORI_AD["kart"] == "K.Kartı" and len(H.KATEGORI_AD) == 13


def test_edefter_bos_fis_notr():
    e = _oku("kayranacc/edefter.py")
    assert 'trenk("soluk") if _tb == 0 and _ta == 0 else' in e


def test_genel_bakis_buyuk_harf_yok():
    m = _oku("kayranacc/main.py")
    a = m.index('if sayfa == "📊 Dashboard":')
    b = m.index('elif sayfa == "💳 Bu Hafta":')
    assert "uppercase" not in m[a:b]
    assert "text-transform: uppercase !important" not in m          # stMetricLabel


def test_ertelenen_veritabani_denetimi():
    d = _oku("kayranacc/database.py")
    assert "def erteleme_sutunlari_var(" in d
    assert "erteleme_sutunlari_var()" in _oku("kayranacc/odeme_ekran.py")
