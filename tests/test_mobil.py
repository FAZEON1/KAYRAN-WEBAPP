# -*- coding: utf-8 -*-
"""Aşama 3 · Mobil katman — telefonda her sayfanın uyduğu ortak kurallar."""
import glob
import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from shared import tasarim as T  # noqa: E402


def test_mobil_katman_cekirdekte():
    css = T.cekirdek_css()
    assert "@media (max-width:640px)" in css
    assert T.MOBIL_CSS.strip()[:30] in css or "grid-template-columns:repeat(2,minmax(0,1fr))" in css


def test_ios_yakinlastirma_onlenir():
    # iOS 16px'ten küçük yazılı kutuya dokununca sayfayı yakınlaştırır
    assert "font-size:16px !important" in T.MOBIL_CSS


def test_dokunma_hedefleri():
    m = T.MOBIL_CSS
    assert "min-height:44px" in m and "stNumberInputStepUp" in m
    assert "min-height:44px" in T.DUGME_CSS


def test_sabit_izgaralar_ve_tablolar_tasmaz():
    m = T.MOBIL_CSS
    assert 'grid-template-columns:repeat(4' in m and "repeat(2,minmax(0,1fr))" in m
    assert "overflow-x:auto" in m and "white-space:nowrap" in m


def test_kisalan_metin_mobilde_sarar():
    """Telefonda 'üstüne gel' yok; kısalan ad 2 satıra sarmalı."""
    assert "-webkit-line-clamp:2" in T.MOBIL_CSS
    assert 'class="k-urun-ad"' in T.urun_etiketi("uzun ad", "SKU1")


def test_talep_dugmesi_kendi_stilinde():
    """Aşama 1'de ✉️ düğmesi genel düğme kuralına yakalanıp silik bir kutuya
    dönüşmüştü. Hiyerarşi ve mobil tam-genişlik kuralları onu hariç tutmalı."""
    assert ":not(.st-key-fab_talep *)" in T.DUGME_CSS
    assert ":not(.st-key-fab_talep *)" in T.MOBIL_CSS


def test_tarih_kutulari_turkce():
    """st.date_input varsayılanı 2026/09/30 gösterir; hepsi GG.AA.YYYY olmalı."""
    eksik = []
    for f in glob.glob(str(KOK / "**" / "*.py"), recursive=True):
        if any(p in f.replace("\\", "/") for p in ("/tests/", "/bekleyen/", "/otonom/", "/deploy/")):
            continue
        s = open(f, encoding="utf-8").read()
        for m in re.finditer(r"\.date_input\(", s):
            if "format=" not in s[m.end():m.end() + 600].split(")\n")[0]:
                eksik.append(f"{Path(f).relative_to(KOK)}:{s[:m.start()].count(chr(10)) + 1}")
    assert not eksik, eksik[:10]


def test_eski_dagitik_mobil_blok_kaldirildi():
    src = (KOK / "app.py").read_text(encoding="utf-8")
    assert '[data-testid="stDataFrame"] { font-size: 0.72rem' not in src
