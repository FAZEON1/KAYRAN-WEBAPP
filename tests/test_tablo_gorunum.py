# -*- coding: utf-8 -*-
"""Tabloların 3. adımı (Ekim 2026): ikinci tablo çekirdeği (tablo_html / df_tablo_html)
ortak tablo bileşeniyle aynı görünüme gelir (A seçeneği: yalnız CSS, çağrılar aynı).
tablo_ciz'in tek kullanımı doğrudan ortak bileşene geçer."""
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def test_geri_alma_anahtari_tek_satir():
    src = (KOK / "shared" / "tasarim.py").read_text(encoding="utf-8")
    assert len(re.findall(r"^TABLO_YENI = (True|False)\s", src, re.M)) == 1


def test_gorunum_esitlenir():
    from shared.tasarim import cekirdek_css
    css = cekirdek_css()
    i = css.index("/* ── Tablo çekirdeği (tablo_html) ortak görünümde")
    g = css[i:i + 1600]
    assert ".k-tb tbody tr:nth-child(even) td{background:transparent" in g      # zebra yok
    assert ".k-tb .sayi{font-family:inherit" in g                                   # mono yok
    assert ".k-tbw{border-radius:12px" in g


def test_satir_vurgusu_korunur():
    from shared.tasarim import tablo_html
    h = tablo_html(["Tarih", ("Bakiye", "para", "₺")], [{"Tarih": "01.10", "Bakiye": -5}],
                   vurgu=lambda r: "kirmizi")
    assert 'data-vurgu="kirmizi"' in h and "neg" in h


def test_satis_ozet_ortak_tabloda():
    src = (KOK / "satis" / "main.py").read_text(encoding="utf-8")
    assert "tablo_ciz(_tablo" not in src
