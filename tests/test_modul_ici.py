# -*- coding: utf-8 -*-
"""Modül içi görsel dil (Ekim 2026): emoji → çizgi ikon, BÜYÜK HARF → cümle düzeni.

Sayfa başlıkları (tasarim.baslik), pencere kartları (ui.pencere / tasarim.kart)
ve KPI etiketleri (kpi_serit / utils.metrik_satiri) TEK yerden geçtiği için
modül dosyalarına dokunmadan tüm sayfalar aynı dile geçer.
"""
import importlib
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _T():
    return importlib.import_module("shared.tasarim")


def test_cumle_duzeni():
    c = _T().cumle_duzeni
    assert c("BU AY NET KÂR") == "Bu ay net kâr"
    assert c("TOPLAM AKTİF (USD)") == "Toplam aktif (USD)"
    assert c("30 GÜN İÇİNDE SİPARİŞ") == "30 gün içinde sipariş"     # rakamla başlar: büyütme yok
    assert c("SKU'LAR VE KDV") == "SKU'lar ve KDV"
    assert c("ISLAK İMZA") == "Islak imza"                             # Türkçe I/İ
    assert c("P&L ÖZETİ") == "P&L özeti"
    # Bilinçli yazılmış karışık metne dokunmaz
    assert c("Paçal (Final)") == "Paçal (Final)"
    assert c("Stok Devir (DIO)") == "Stok Devir (DIO)"


def test_emoji_ayir():
    e = _T().emoji_ayir
    assert e("⚠️ 30 GÜN İÇİNDE SİPARİŞ") == ("warning", "30 GÜN İÇİNDE SİPARİŞ")   # U+FE0F dahil
    assert e("🛍️ MÜŞTERİ STOĞU") == ("shopping_bag", "MÜŞTERİ STOĞU")
    assert e("Kâr / P&L") == (None, "Kâr / P&L")
    assert e("(USD) Toplam") == (None, "(USD) Toplam")                   # parantez emoji değil
    ik, govde = e("🟡 Planlama")                                          # tanınmayan emoji: atılır
    assert ik is None and govde == "Planlama"


def test_kpi_etiketi_emoji_ve_buyuk_harf_atar():
    k = _T().kpi_etiketi
    assert k("🔴 Acil Sipariş") == "Acil Sipariş"
    assert k("NET CİRO") == "Net ciro"
    h = _T().kpi_serit([{"etiket": "BU AY CİRO", "deger": "$1"}])
    assert ">Bu ay ciro<" in h


def test_baslik_emoji_yerine_ikon_karosu():
    h = _T().baslik("📥 Teknik Servis", "Mal Kabül")
    assert 'class="k-ikon"' in h and ">move_to_inbox<" in h
    assert "📥" not in h


def test_kart_basligi_ikon_ve_cumle_duzeni():
    h = _T().kart("🚨 ACİL SİPARİŞ", "kirmizi", "<p>x</p>")
    assert ">notification_important<" in h and ">Acil sipariş<" in h and "🚨" not in h


def test_ortak_stillerde_buyuk_harf_yok():
    src = (KOK / "shared/tasarim.py").read_text(encoding="utf-8")
    assert "text-transform:uppercase" not in src
    assert "text-transform:uppercase" not in (KOK / "yonetim.py").read_text(encoding="utf-8")


def test_pencere_ortak_kart_ve_cumle_duzeni():
    ui = (KOK / "shared/ui.py").read_text(encoding="utf-8")
    govde = ui[ui.index("def pencere(baslik"):ui.index("def pencere_grid(")]
    assert "emoji_ayir" in govde and "cumle_duzeni" in govde
    assert "linear-gradient" not in govde, "pencere kartında eski degrade zemin"
