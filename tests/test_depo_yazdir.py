# -*- coding: utf-8 -*-
"""Depo Stok › Yazdır (Ekim 2026): ekrandaki liste = kâğıttaki liste."""
from pathlib import Path

import pytest

from depo.yazdir import liste_hazirla

KOK = Path(__file__).resolve().parent.parent
U = [{"sku": "C32W", "urun_adi": "FAZEON C32W KAVISLI MONITÖR", "adet": 88},
     {"sku": "F14PLUS", "urun_adi": "FAZEON F14 PLUS KASA", "adet": 120},
     {"sku": "A120", "urun_adi": "AERO 120 SOĞUTUCU", "adet": 88}]


def test_arama_i_ve_I_ayni_sayilir():
    """Ekran adları marka yazımıyla noktasız I'lı büyütüyor ('MONITÖR');
    'monitör' / 'MONİTÖR' / 'monıtör' hepsi bulmalı."""
    for a in ("monitör", "MONİTÖR", "monıtör", "c32w"):
        assert [u["sku"] for u in liste_hazirla(U, a)] == ["C32W"], a


def test_siralamalar():
    assert [u["sku"] for u in liste_hazirla(U, "", "adet")] == ["F14PLUS", "A120", "C32W"]  # eşitte SKU
    assert [u["sku"] for u in liste_hazirla(U, "", "sku")] == ["A120", "C32W", "F14PLUS"]
    assert [u["sku"] for u in liste_hazirla(U, "", "urun")] == ["A120", "C32W", "F14PLUS"]


def test_pdf_uretilir_ve_turkce_icerir():
    pytest.importorskip("reportlab")
    from depo.yazdir import depo_stok_pdf
    b = depo_stok_pdf("HAPPY LIFE", liste_hazirla(U), "İbrahim", sayim_sutunu=True, not_metni="Ekim sayımı")
    assert b[:5] == b"%PDF-" and len(b) > 2000


def test_ekranda_yazdir_dugmesi_ve_ayni_liste():
    src = (KOK / "depo/main.py").read_text(encoding="utf-8")
    g = src[src.index("def _sayfa_stok():"):src.index("# ═════════════════════ 🚚 DEPOLAR ARASI SEVK")]
    assert 'popover("Yazdır"' in g and "depo_stok_pdf(_di_depo, _liste" in g
    assert "data=_pdf" in g            # PDF yalnız tıklanınca üretilir (her çizimde değil)
    assert "_liste = liste_hazirla(" in g and "for u in _liste" in g    # tablo da aynı listeden
