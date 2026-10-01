# -*- coding: utf-8 -*-
"""İthalat modülü yenileme (Ekim 2026).

  • Geçmiş İthalatlar: düz tablo yerine Akış (aşama sütunları, tahmini varış) ·
    Liste (aya göre) · Toplu işlem (eski çoklu seçim tablosu, korunur).
    Kart/satır → MEVCUT detay penceresi (iş kurallarına dokunulmadı).
  • Masraf Detayları: "Masraf Türü" ve "Tutar" sütunları BOŞ görünüyordu
    (ortak tablo adında 'masraf' geçen sütunu para sanıp metni boş bırakıyordu;
    tutara da hazır metin gidiyordu).
  • Model Sorgu: birim maliyet 6 hane ("$13,327142") → en çok 4.
  • Büyük harfli etiketler cümle düzenine.
"""
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


def test_varis_metni():
    from ithalat.ithalat_ekran import varis_metni
    b = date(2026, 10, 1)
    assert varis_metni({"tahmini_varis": "2026-10-13"}, b) == ("varış 12 gün sonra", "cyan")
    assert varis_metni({"tahmini_varis": "2026-10-02"}, b) == ("varış yarın", "amber")
    assert varis_metni({"tahmini_varis": "2026-09-20"}, b) == ("varış 11 gün gecikti", "kirmizi")
    assert varis_metni({}, b)[0] == "varış tarihi yok"


def test_gecmis_gorunumler_ve_mevcut_pencere():
    m = _oku("ithalat/main.py")
    assert '["Akış", "Liste", "Toplu işlem"]' in m
    assert '_B.detay_istendi("ith")' in m
    assert "def _dlg_dosya_detay():" in m and "did = dosyalar_goster[_sel[0]][\"id\"]" in m   # pencere aynı
    assert 's.get("_skus", "")).lower()' in m          # arama SKU'yu da kapsar
    e = _oku("ithalat/ithalat_ekran.py")
    assert "B.tiklanir(" in e and 'AKIS_ASAMALARI = ["Üretimde", "Yolda", "Gümrükte", "Antrepoda"]' in e


def test_masraf_detaylari_sutunlari_dolu():
    m = _oku("ithalat/main.py")
    a = m.index("def _masraf_detaylari"); b = m.index("def run():", a)
    g = m[a:b]
    assert '"Tür": s["Masraf Türü"]' in g and '"Tutar": round(s["Tutar"], 2)' in g
    assert '"Masraf Türü": s["Masraf Türü"],\n        "Tutar": f"' not in g
    from shared.tasarim import _tablo_kolon_tipi as t
    assert t("Tür") is None and t("Masraf Türü") == "para"     # neden ad değişti


def test_model_sorgu_dort_hane_ve_buyuk_harf_yok():
    m = _oku("ithalat/main.py")
    assert '_pacal = f"${_tam(pacal_ort, 4)}"' in m
    assert "uppercase" not in m
