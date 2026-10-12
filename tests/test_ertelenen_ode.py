# -*- coding: utf-8 -*-
"""Ertelenen Ödemeler satırları tıklanır; Bu Hafta'daki ödeme penceresi açılır (Ekim 2026)."""
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def test_ertelenen_satirlari_odeme_penceresini_acar():
    s = (KOK / "kayranacc/odeme_ekran.py").read_text(encoding="utf-8")
    g = s[s.index("def render_ertelenenler("):]
    assert 'B.tiklanir(\n            f"ert{o[\'id\']}"' in g and "_ac, (o[\"id\"],)" in g
    assert 'B.detay_istendi("od")' in g and "_odeme_dialog(o, kategoriler" in g
    m = (KOK / "kayranacc/main.py").read_text(encoding="utf-8")
    assert "render_ertelenenler(KATEGORILER, get_bankalar() or [], get_kur())" in m
