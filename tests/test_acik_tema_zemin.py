# -*- coding: utf-8 -*-
"""Açık tema turu (30.09.2026) — canlıda bulunan okunmaz kutular geri gelmesin.

Bulunanlar: Muhasebe Bu Hafta alarm kartları, Toplam Aktifler kartı ve yeşil
kutu, Veri Yükleme aktif hafta kartı, e-Defter uyarısı, sidebar kur kutusu,
Ürün Yön. "Çıkış Yap" düğmesi, her sayfada "kutu içinde kutu" uyarılar.
Ortak neden: arka plana koyu SABİT renk (#2D0A0F gibi) yazılmıştı; açık temada
yazı rengi koyulaşınca koyu zemin üstünde koyu yazı kaldı.
"""
import os
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent

# CI sözdizimi adımıyla aynı ölü klasörler + ekran DIŞI çıktılar
# (e-posta/PDF raporları temadan bağımsız, kendi açık zeminleri var).
OLU = ("(", "/shared/shared", "/shared/kayran", "/shared/satis", "/shared/depo",
       "/shared/ithalat", "/shared/teknik", "/kayranpm/kayranpm", "/satis/satis",
       "_tek.py", "/.git", "/tests/", "/otonom/", "telegram", "bildirim.py",
       "rapor.py", "pdf", "excel", "__pycache__")

# Bilerek koyu kalan marka zeminleri — üstlerindeki yazı SABİT beyaz.
IZINLI = {
    "#3730A3",   # kayranacc Toplam Aktifler kartı (mavi→mor marka gradyanı, beyaz yazı)
}

_ZEMIN = re.compile(r"(background(?:-color)?\s*:[^;\"']*?|linear-gradient\([^)]*?)"
                    r"(#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b)")


def _parlaklik(h):
    h = h[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _canli_dosyalar():
    for k, _, fs in os.walk(KOK):
        for f in fs:
            p = os.path.join(k, f).replace(os.sep, "/")
            if f.endswith(".py") and not any(x in p for x in OLU):
                yield Path(p)


def test_ekranda_koyu_sabit_zemin_yok():
    sorun = []
    for yol in _canli_dosyalar():
        for no, satir in enumerate(yol.read_text(encoding="utf-8").splitlines(), 1):
            for m in _ZEMIN.finditer(satir):
                hx = m.group(2).upper()
                # var(--k-x,#hex) içindeki yedek değer tema değişkeni tanımsızsa
                # devreye girer; zemin yine temadan gelir.
                if re.search(r"var\(--k-[a-z0-9-]+,\s*$", satir[:m.start(2)]):
                    continue
                if _parlaklik(hx) < 0.25 and hx not in IZINLI:
                    sorun.append(f"{yol.relative_to(KOK)}:{no}  {hx}")
    assert not sorun, (
        "Açık temada okunmaz kalacak koyu SABİT zemin(ler). var(--k-yuzey*) ya da "
        "color-mix(in srgb,var(--k-renk) 10%,var(--k-yuzey1)) kullan:\n  "
        + "\n  ".join(sorun))


def _oku(p):
    return (KOK / p).read_text(encoding="utf-8")


def test_uyari_kutusu_tek_katman():
    """Çerçeve+zemin stAlertContainer'da; dış stAlert çerçevesiz. Metnin altındaki
    Streamlit -1rem boşluğu sıfırlanmış olmalı (yoksa kutu 5px'e iner)."""
    t = _oku("shared/tasarim.py")
    assert 'div[data-testid="stAlertContainer"],div[data-testid="stNotification"]' in t
    assert re.search(r'div\[data-testid="stAlert"\]\{\{margin:6px 0 !important;padding:0 !important;\s*'
                     r'border:0 !important', t)
    assert '[data-testid="stMarkdownContainer"]{{margin-bottom:0 !important;}}' in t

    acc = _oku("kayranacc/main.py")
    # İç içerik katmanına zemin verilirse ince şerit geri gelir
    assert not re.search(r'div\[data-testid="stAlertContent(Info|Success|Warning|Error)"\]\s*[,{]', acc)
    assert "div.stAlert:has(" not in acc


def test_toplam_aktifler_karti_beyaz_yazi():
    acc = _oku("kayranacc/main.py")
    i = acc.index("💎 TOPLAM AKTİFLER (GENEL TOPLAM)")
    blok = acc[i - 400:i + 600]
    assert "var(--k-metin)" not in blok and "var(--k-mor2)" not in blok
    assert "color:#FFFFFF" in blok
