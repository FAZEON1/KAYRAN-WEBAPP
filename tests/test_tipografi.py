# -*- coding: utf-8 -*-
"""Tipografi (Ekim 2026): ölçek örneğe yaklaştı, rakamlar kod fontu değil Inter.

Kullanıcı karşılaştırdığı panelde rakamlar metnin kendi fontuyla, yazılar bir-iki punto büyüktü;
bizde rakamlar JetBrains Mono (kod fontu), etiketler 10–11px'ti. Font ailesi Inter kalır.
"""
import re
from pathlib import Path

from shared import tasarim as T

KOK = Path(__file__).resolve().parent.parent


def _px(v):
    return float(str(v).replace("px", ""))


def test_olcek_buyudu_en_kucuk_yazi_12px():
    F = T.FONT
    assert min(_px(v) for v in F.values()) >= 12
    assert (_px(F["govde"]), _px(F["baslik"]), _px(F["deger"]), _px(F["hero"])) == (14, 18, 22, 28)


def test_rakam_fontu_inter_kod_fontu_degil():
    assert "Inter" in T.MONO and "Mono" not in T.MONO and "monospace" not in T.MONO
    assert ".stApp{font-variant-numeric:tabular-nums;}" in T._streamlit_normalize().replace("{{", "{").replace("}}", "}")


def test_ekranlarda_jetbrains_kalmadi():
    """Rakam gösteren yerler var(--k-mono) kullanır; font tek yerden (shared.tasarim.MONO) değişir.
    E-posta / PDF şablonları (CSS değişkeni yok) bu taramanın dışında."""
    kalan = []
    for p in KOK.rglob("*.py"):
        r = p.relative_to(KOK).as_posix()
        if r.startswith(("tests/", ".venv/")) or "/." in r:
            continue
        if re.search(r"JetBrains Mono['\"]?\s*,", p.read_text(encoding="utf-8", errors="ignore")):
            kalan.append(r)
    assert kalan == []
