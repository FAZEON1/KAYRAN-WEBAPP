# -*- coding: utf-8 -*-
"""Aşama 2 · Sayı, tarih ve dil standardı (Türkçe)."""
import glob
import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from shared.tasarim import (tr_sayi, para, adet, oran, tarih,  # noqa: E402
                            _tr_oran, menu_etiketi)


def _oku(p):
    return (KOK / p).read_text(encoding="utf-8")


def test_bicimleyiciler():
    assert para(678033) == "$678.033"
    assert para(1240500.5, "₺", 2) == "₺1.240.500,50"
    assert para(-1234) == "-$1.234"
    assert para(None) == "—"
    assert adet(12500) == "12.500"
    assert oran(30.94) == "%30,9"
    assert tr_sayi(1234.5, 2) == "1.234,50"
    assert tr_sayi(7.29384, 4) == "7,2938"
    assert tarih("2026-09-30") == "30.09.2026"
    assert tarih("2026-09-30T14:05:11", saat=True) == "30.09.2026 14:05"
    assert tarih(None) == "—"


def test_oran_binlik_hatasi_duzeldi():
    # Eskiden "%1,234,50" üretiyordu
    assert _tr_oran(1234.5) == "%1.234,50"


ARAYUZ = [f for f in glob.glob(str(KOK / "**" / "*.py"), recursive=True)
          if not any(p in f.replace("\\", "/") for p in
                     ("/tests/", "/bekleyen/", "/otonom/", "/deploy/", "/.git/"))
          and not f.endswith(("telegram_brifing.py", "gunluk.py", "migrate_passwords.py",
                              "shared/tasarim.py"))]


def test_ingilizce_sayi_bicimi_geri_gelmedi():
    """f"{x:,.2f}" İngilizce biçim üretir ($1,234.50). Yalnız hemen ardından
    TR'ye çeviren .replace zinciri olan eski satırlara izin var."""
    kotu = []
    for f in ARAYUZ:
        for i, s in enumerate(open(f, encoding="utf-8"), 1):
            for m in re.finditer(r"\{[^{}]*?:,(?:\.\d)?f?\}|[\"']\{:,", s):
                if not re.search(r"\.replace\(\s*[\"'],[\"']", s[m.end():]):
                    kotu.append(f"{Path(f).relative_to(KOK)}:{i}")
    assert not kotu, "Türkçe biçim kullan (tr_sayi/para/adet/oran): " + ", ".join(kotu[:10])


def test_pf_okunan_degerler_korunur():
    """Ürün Yön. kampanya tablosu bu iki değeri _pf() ile GERİ OKUYUP renk
    seçiyor; _pf virgülü siler. TR biçime çevrilirse 1.234,50 → 1.23450 olur.
    Bu yüzden bu blok bilerek İngilizce biçimde bırakıldı."""
    src = _oku("kayranpm/main.py")
    assert '"Net Kar/Adet ($)": f"${net_kar_birim:.2f}"' in src
    assert '"Toplam Net Kar ($)": f"${toplam_net_urun:.0f}"' in src


def test_grafik_ayraci_turkce():
    src = _oku("app.py")
    assert '"separators": ",."' in src and "kayran_tr" in src


def test_sayfa_dili_turkce():
    """lang="tr" olmadan büyük harf 'Gecikmiş' → 'GECIKMIŞ' oluyordu."""
    assert 'doc.documentElement.lang = "tr"' in _oku("app.py")


def test_tablo_tarihleri_turkce():
    for f in ARAYUZ:
        s = open(f, encoding="utf-8").read()
        assert 'format="YYYY-MM-DD"' not in s and 'format="DD-MM-YYYY"' not in s, f


def test_menude_ingilizce_yok():
    assert menu_etiketi("📊  Dashboard").endswith("Genel Bakış")
    assert '"Dashboard", aciklama' not in _oku("kayranacc/main.py")
    assert '"Dashboard", aciklama' not in _oku("kayranpm/main.py")


def test_patron_panosu_turkce_rakam():
    from shared.ui import patron_panosu_html
    h = patron_panosu_html({"ay_ciro": 678033, "ay_kar": 209639, "ay_marj": 30.94,
                            "toplam_aktif": 849220})
    assert "678.033" in h and "678,033" not in h
    assert "%30,9" in h
