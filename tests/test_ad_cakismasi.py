# -*- coding: utf-8 -*-
"""Fonksiyon içi içe aktarma, modül düzeyindeki bir adı GÖLGELEMESİN (Ekim 2026).

Python'da fonksiyon içinde `from x import y as _ad` yazmak `_ad`ı bütün fonksiyon (ve
içindeki iç fonksiyonlar) için yerel yapar. ithalat/main.py'de `from shared.tablo import
tablo as _tablo` modüldeki `_tablo` yardımcısını gölgeledi; dosya detay penceresi
`TypeError: tablo() got an unexpected keyword argument 'para'` ile kırıldı (tarayıcıda
yakalandı, testler görmemişti)."""
import ast
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
ATLA = ("tests", ".git", "__pycache__", "deploy", "otonom")


def test_fonksiyon_ici_ice_aktarma_modul_adini_golgelemez():
    bulgu = []
    for f in sorted(KOK.rglob("*.py")):
        rel = f.relative_to(KOK).as_posix()
        if any(rel.startswith(a) or f"/{a}/" in rel for a in ATLA):
            continue
        t = ast.parse(f.read_text(encoding="utf-8"))
        modul = set()
        for n in t.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                modul.add(n.name)
            elif isinstance(n, ast.Assign):
                modul.update(x.id for x in n.targets if isinstance(x, ast.Name))
        for fn in ast.walk(t):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for n in ast.walk(fn):
                if isinstance(n, (ast.Import, ast.ImportFrom)):
                    for a in n.names:
                        ad = a.asname or a.name.split(".")[0]
                        if ad in modul and ad != fn.name:
                            bulgu.append(f"{rel}:{n.lineno} '{ad}'")
    assert not bulgu, "Modül adını gölgeleyen fonksiyon içi içe aktarma: " + ", ".join(sorted(set(bulgu))[:15])


def test_ortak_tablo_takma_adi():
    for d in ("ithalat/main.py", "satis/main.py", "kayranpm/stok_karti.py"):
        assert "import tablo as _tablo" not in (KOK / d).read_text(encoding="utf-8"), d
