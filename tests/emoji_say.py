# -*- coding: utf-8 -*-
"""Ekranda görünebilecek emojili metinleri dosya başına sayar (test_emoji_siniri).
Docstring, Telegram/otonom betikleri, durum noktaları (🔴🟢…) ve tipografik
işaretler (✓ • ▲) sayılmaz."""
import ast
import pathlib
import re

KOK = pathlib.Path(__file__).resolve().parent.parent
_E = "\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF\u2139\u21A9\u21AA"
_EMO = re.compile(f"[{_E}]")
_SAYILMAZ = set("🔴🟠🟡🟢🔵🟣⚪⚫🟤✓✗✕✖•●○■□▲▼◆◇★☆")
ATLA = ("telegram_brifing.py", "otonom", "migrate_passwords.py", "deploy", "tests")


def say():
    out = {}
    for f in sorted(KOK.rglob("*.py")):
        rel = f.relative_to(KOK).as_posix()
        if "pycache" in rel or rel.startswith(ATLA):
            continue
        t = ast.parse(f.read_text(encoding="utf-8"))
        doc = set()
        for n in ast.walk(t):
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and n.body \
                    and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant):
                doc.add(id(n.body[0].value))
        n_say = sum(1 for n in ast.walk(t)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc
                    and any(c not in _SAYILMAZ for c in _EMO.findall(n.value)))
        if n_say:
            out[rel] = n_say
    return out
