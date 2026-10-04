# -*- coding: utf-8 -*-
"""Ortak detay kartı ve mesaj kutusu (Eki 2026) — modüllerin elle yazdığı renkli kutuların yerine."""
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from shared import tasarim as T  # noqa: E402


def test_detay_karti_iki_sutun_ve_ana_deger():
    h = T.detay_karti("Alım detayı", "PI-1", sol=[("Tarih", "01.01.2026")], sag=[("Adet", "5")],
                      ana=("Final birim maliyet", "$3,10"))
    assert 'class="k-detay"' in h and "Alım detayı" in h and "PI-1" in h
    assert h.count('class="k-detay-sutun"') == 2
    assert "k-detay-ana" in h and "$3,10" in h
    assert h.index("Adet") < h.index("Final birim maliyet")       # ana değer sağ sütunun altında


def test_detay_karti_anlam_rengi():
    assert "k-detay-ana k-kotu" in T.detay_karti("Satış", ana=("Net kâr", "-$1", "kotu"))
    assert "k-detay-ana k-" not in T.detay_karti("Satış", ana=("Net kâr", "$1"))


def test_detay_karti_css_cekirdekte():
    assert ".k-detay-satir" in T.cekirdek_css() and ".k-detay-ana.k-kotu" in T.cekirdek_css()


def test_mesaj_varsayilan_kacis_ham_istenirse_html():
    assert "&lt;b&gt;" in T.mesaj("uyari", "<b>x</b>")
    assert "<b>x</b>" in T.mesaj("uyari", "<b>x</b>", ham=True)


def test_ithalatta_elle_renkli_deger_kutusu_kalmadi():
    src = (KOK / "ithalat" / "main.py").read_text(encoding="utf-8")
    assert "def _metrik_satiri(" not in src                       # ortak metrik_satiri kullanılır
    assert "font-family:\\'JetBrains Mono\\',monospace\">{_tam(" not in src
    assert src.count("font-family:monospace;margin-bottom:8px") == 0
