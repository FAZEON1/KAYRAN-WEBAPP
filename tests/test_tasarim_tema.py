# -*- coding: utf-8 -*-
"""Aşama 1 · tema katmanı, düğme hiyerarşisi, Tasarım Rehberi."""
import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from shared import tasarim as T  # noqa: E402


def test_temalar_ayni_anahtarlari_tasir():
    assert set(T.RENK) == set(T.RENK_ACIK)
    assert set(T.ORTU["koyu"]) == set(T.ORTU["acik"])


def test_kontrast_olcer_dogru():
    assert round(T.kontrast("#000000", "#FFFFFF"), 1) == 21.0
    assert round(T.kontrast("#FFFFFF", "#FFFFFF"), 1) == 1.0


def test_iki_temada_metin_okunur():
    """Metin tonları kart zemininde WCAG AA (4.5), anlam renkleri 3.0 eşiğini geçmeli."""
    for ad, palet in T.TEMALAR.items():
        kart = palet["yuzey1"]
        for k in ("metin", "soluk", "silik"):
            assert T.kontrast(palet[k], kart) >= 4.5, (ad, k)
        for k in ("mor", "yesil", "kirmizi", "amber", "cyan", "mor2", "yesil2",
                  "kirmizi2", "amber2", "cyan2", "mavi", "pembe"):
            assert T.kontrast(palet[k], kart) >= 3.0, (ad, k)


def test_ana_dugme_yazisi_okunur():
    for tema in ("koyu", "acik"):
        o = T.ORTU[tema]
        assert T.kontrast(o["dolgu-metin"], o["dolgu"]) >= 4.4, tema


def test_cekirdek_bilesenleri_degisken_kullanir():
    """Çekirdek CSS'teki bileşen kuralları sabit renk değil değişken kullanmalı;
    yoksa açık temada koyu kalırlar."""
    src = (KOK / "shared" / "tasarim.py").read_text(encoding="utf-8")
    a, b = src.index("def _streamlit_normalize"), src.index("def islem_gosterge_css")
    blok = src[a:b]
    assert not re.search(r"\{R\['\w+'\]\}", blok)
    css = T.cekirdek_css()
    assert ".k-tema-acik{" in css and "--k-dolgu:" in css


def test_bilesenler_tema_degiskeniyle():
    assert "var(--k-yesil)" in T.kpi_serit([{"etiket": "a", "deger": "1", "renk": "yesil"}])
    assert "var(--k-amber)" in T.rozet("x", "amber")
    assert "#" not in T.rozet("x", "amber").split("style=")[1].split(">")[0]
    assert T.rv("yok_boyle") == "var(--k-mor)"


def test_dugme_hiyerarsisi():
    css = T.DUGME_CSS
    for tip in ("stBaseButton-primary", "stBaseButton-secondary", "stBaseButton-tertiary"):
        assert tip in css
    assert ':not(.st-key-ustnav *)' in css          # üst menü kendi stilinde
    assert '[class*="_sil"]' in css                 # silme düğmeleri kırmızı
    assert "min-height:44px" in css                 # telefonda dokunma hedefi


def test_bos_durum_ve_mesaj_kacirir():
    assert "<b>" not in T.bos_durum("<b>x</b>", "<i>y</i>")
    assert "<script>" not in T.mesaj("hata", "<script>")
    assert "var(--k-kirmizi)" in T.mesaj("hata", "x")


def test_rehber_sayfasi_bagli_ve_yetkili():
    src = (KOK / "app.py").read_text(encoding="utf-8")
    assert 'elif aktif == "tasarim_rehberi":' in src
    blok = src[src.index('elif aktif == "tasarim_rehberi":'):][:400]
    assert 'ozel_yetki(' in blok and '"kullanici_yonetimi"' in blok
    assert "from shared.rehber import goster" in blok
