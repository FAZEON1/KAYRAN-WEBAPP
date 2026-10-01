# -*- coding: utf-8 -*-
"""Firma Çekleri — ödenmiş çekte "Kalan" 0 görünmeli (30.09.2026).

Hata: üstte "Toplam Kalan ₺0" yazarken tablo her satırda kalan = meblağ
gösteriyordu. Bankanın dökümündeki "kalan" sütunu ödenmiş çekte de meblağı
taşıyor; tablo onu ham basıyordu. Ayrıca 'Ödendi'.lower() → 'ödendi' olduğu için
"odendi" araması hiç tutmuyor, satır yeşillenmiyor, ✓ ÖDENDİ rozeti çıkmıyordu.
Çözüm: özet, tablo ve arşiv TEK kuraldan (database.cek_tutarlari) okur.
"""
import re
from pathlib import Path

from kayranacc.database import cek_durum_norm, cek_tutarlari

KOK = Path(__file__).resolve().parent.parent


def test_odenmis_cekte_kalan_sifir():
    t = cek_tutarlari({"meblagh": 500000, "odenen": 500000, "kalan": 500000, "durum": "Ödendi"})
    assert t == {"meblag": 500000.0, "odenen": 500000.0, "kalan": 0.0, "odendi": True}


def test_odenmis_sayilan_diger_durumlar():
    for d in ("ÖDENDİ", "Tahsil Edildi", "İptal", "Portföyden Çıktı", " odendi "):
        t = cek_tutarlari({"meblagh": 100, "odenen": 0, "kalan": 100, "durum": d})
        assert t["odendi"] and t["kalan"] == 0 and t["odenen"] == 100, d


def test_bekleyen_cekte_kalan():
    # kalan sütunu tutarlı → o kullanılır
    assert cek_tutarlari({"meblagh": 1000, "odenen": 400, "kalan": 600, "durum": "Bekliyor"})["kalan"] == 600
    # kalan sütunu güncellenmemiş (meblağ kalmış) → meblağ − ödenen
    assert cek_tutarlari({"meblagh": 1000, "odenen": 400, "kalan": 1000, "durum": "Bekliyor"})["kalan"] == 600
    # boş/bozuk değerler patlatmaz
    t = cek_tutarlari({"meblagh": "", "odenen": None, "kalan": "x", "durum": None})
    assert t == {"meblag": 0.0, "odenen": 0.0, "kalan": 0.0, "odendi": False}
    # ciro edilmiş çek borç sayılmaya devam eder
    assert not cek_tutarlari({"meblagh": 50, "kalan": 50, "durum": "Ciro Edildi"})["odendi"]


def test_durum_normu_turkce_harf():
    assert cek_durum_norm("Ödendi") == "odendi"
    assert cek_durum_norm("GECİKMİŞ") == "gecikmis"


def test_ekranlar_ortak_kurali_kullanir():
    kod = (KOK / "kayranacc/main.py").read_text(encoding="utf-8")
    i = kod.index('elif sayfa == "📋 Firma Çekleri":')
    j = kod.index("# 6) ÖDENENLEr", i)
    sayfa = kod[i:j]
    assert "cek_tutarlari(c)" in sayfa
    # tablo ham "kalan"/"odenen" sütununu basmıyor
    assert not re.search(r'c\.get\("(kalan|odenen)"', sayfa)
    # arşiv (Ekim 2026: kayranacc/gecmis_ekran.py) da ortak kuraldan
    g = (KOK / "kayranacc/gecmis_ekran.py").read_text(encoding="utf-8")
    assert "ct = cek_tutarlari(c)" in g and "ct['kalan']" in g
    assert not re.search(r'c\.get\("(kalan|odenen)"', g)
    assert "fmt(c.get('kalan')" not in kod
    # ÖDENDİ rozetinde zemin ile yazı aynı renk değil
    assert "background:var(--k-yesil2);color:var(--k-yesil2)" not in kod
