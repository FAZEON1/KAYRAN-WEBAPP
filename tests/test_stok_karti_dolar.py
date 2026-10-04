# -*- coding: utf-8 -*-
"""Stok kartı mesajlarında iki "$" tutar Streamlit markdown'da LaTeX formülü sanılıyordu:
"son alım $39,47 vs önceki ort. $42,05" → dolar işaretleri kayboluyor, aradaki metin formül
yazısıyla çiziliyordu. Markdown'a giden tutarlar "\\$" ile kaçışlı olmalı (_usd_md)."""
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def test_markdown_mesajlarinda_kacissiz_dolar_yok():
    src = (KOK / "kayranpm" / "stok_karti.py").read_text(encoding="utf-8")
    kotu = re.findall(r'st\.(?:warning|success|info|error|caption|markdown|write)\(f"[^"\n]*\{_usd\(', src)
    assert not kotu, kotu


def test_usd_md_kacis_yapar():
    import sys
    sys.path.insert(0, str(KOK))
    from kayranpm.stok_karti import _usd_md
    assert _usd_md(39.47) == "\\$39,47"
