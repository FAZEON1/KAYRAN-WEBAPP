# -*- coding: utf-8 -*-
"""Sayfa gövdeleri run()'dan ayrı fonksiyonlarda (Ekim 2026, mimari) — geri dönüş koruması.

kayranacc / satis / kayranpm'de run() 1.300–2.900 satırlık "her şeyi yapan" fonksiyonlardı; sayfa
seçimi uzun bir `elif sayfa == "..."` zinciriydi ve bütün sayfalar run()'ın yerel adlarını gizlice
paylaşıyordu (nonlocal). Artık her sayfa modül düzeyinde kendi `_sayfa_*` fonksiyonunda; run()
içindeki _sayfa_parcasi (st.fragment) yalnız "menü seçeneği → sayfa fonksiyonu" sözlüğü. Sayfanın
run()'dan ihtiyaç duyduğu her ad (yardımcı fonksiyon, sabit) açık anahtar sözcük parametresiyle geçer.
Taşıma saf: sayfaların öğe ağacı (tür, anahtar, etiket, değer) taşımadan önceki kodla birebir aynı
olduğu AppTest ile karşılaştırılarak doğrulandı.
"""
import ast
import builtins
import symtable
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
MODULLER = {"kayranacc": ("kayranacc/main.py", "sayfa"),
            "satis": ("satis/main.py", "_ssayfa"),
            "kayranpm": ("kayranpm/main.py", "sayfa")}


def _kaynak(yol):
    return (KOK / yol).read_text(encoding="utf-8")


def _run_ve_parca(src):
    agac = ast.parse(src)
    run = next(n for n in agac.body if isinstance(n, ast.FunctionDef) and n.name == "run")
    parca = next(n for n in run.body if isinstance(n, ast.FunctionDef) and n.name == "_sayfa_parcasi")
    return agac, run, parca


def _eslesme(src):
    """_sayfa_parcasi içindeki sözlük: {seçenek: (fonksiyon adı, [geçen anahtar sözcükler])}."""
    _, _, parca = _run_ve_parca(src)
    sozluk = [n for n in ast.walk(parca) if isinstance(n, ast.Dict)]
    assert len(sozluk) == 1, "parçada tek sayfa sözlüğü bekleniyor"
    out = {}
    for k, v in zip(sozluk[0].keys, sozluk[0].values):
        assert isinstance(k, ast.Constant) and isinstance(v, ast.Lambda), ast.unparse(v)
        cagri = v.body
        assert isinstance(cagri, ast.Call) and isinstance(cagri.func, ast.Name) and not cagri.args
        for kw in cagri.keywords:
            assert isinstance(kw.value, ast.Name) and kw.value.id == kw.arg, ast.unparse(kw)
        out[k.value] = (cagri.func.id, [kw.arg for kw in cagri.keywords])
    return out


@pytest.mark.parametrize("mod", MODULLER)
def test_run_icinde_sayfa_zinciri_yok(mod):
    yol, degisken = MODULLER[mod]
    _, run, parca = _run_ve_parca(_kaynak(yol))
    zincir = [n for n in ast.walk(run) if isinstance(n, ast.Compare) and isinstance(n.left, ast.Name)
              and n.left.id == degisken and isinstance(n.comparators[0], ast.Constant)]
    assert not zincir, f"{yol}: run() içinde yine `{degisken} == ...` dalı var"
    assert len(parca.body) <= 3, f"{yol}: _sayfa_parcasi yalnız sözlük + çağrı olmalı"
    assert not any(isinstance(n, ast.Nonlocal) for n in ast.walk(parca)), f"{yol}: paylaşılan yerel kalmamalı"


@pytest.mark.parametrize("mod", MODULLER)
def test_her_menu_secenegi_kendi_sayfa_fonksiyonuna_bagli(mod):
    from shared.gezinme import secenekler
    yol, _ = MODULLER[mod]
    src = _kaynak(yol)
    es = _eslesme(src)
    assert set(es) == set(secenekler(mod)), f"{yol}: menü ↔ sayfa sözlüğü farklı"
    ust = {n.name: n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)}
    adlar = [fn for fn, _ in es.values()]
    assert len(set(adlar)) == len(adlar), "iki seçenek aynı fonksiyona gidiyor"
    for fn in adlar:
        assert fn.startswith("_sayfa_") and fn in ust, f"{yol}: {fn} modül düzeyinde yok"


@pytest.mark.parametrize("mod", MODULLER)
def test_parametreler_imzayla_ve_run_yerelleriyle_birebir(mod):
    """Sözlükte geçen her ad sayfanın imzasında (yalnız anahtar sözcük) ve run()'ın yerel adı."""
    yol, _ = MODULLER[mod]
    src = _kaynak(yol)
    ust = {n.name: n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)}
    tablo = symtable.symtable(src, yol, "exec")
    run_t = next(c for c in tablo.get_children() if c.get_name() == "run")
    run_yerel = {s.get_name() for s in run_t.get_symbols() if s.is_local()}
    for secenek, (fn, gecen) in _eslesme(src).items():
        a = ust[fn].args
        assert not a.args and not a.posonlyargs and not a.vararg and not a.kwarg, fn
        assert not any(a.kw_defaults), f"{fn}: varsayılan değerli parametre olmamalı"
        assert sorted(gecen) == sorted(x.arg for x in a.kwonlyargs), f"{fn}: imza ↔ çağrı farklı"
        assert set(gecen) <= run_yerel, f"{fn}: run() yerelinde olmayan ad geçiyor: {set(gecen) - run_yerel}"


def _ortuk_globaller(t):
    out = set()
    for s in t.get_symbols():
        if s.is_global() and not s.is_declared_global() and s.is_referenced():
            out.add(s.get_name())
    for c in t.get_children():
        out |= _ortuk_globaller(c)
    return out


@pytest.mark.parametrize("mod", MODULLER)
def test_sayfa_fonksiyonunda_tanimsiz_ad_yok(mod):
    """Sayfa gövdesinin kullandığı her ad ya kendi yereli, ya parametresi, ya modülde tanımlı, ya
    yerleşik. Taşımada run()'dan bir ad geçirilmeyi unutulursa canlıda NameError olurdu."""
    yol, _ = MODULLER[mod]
    src = _kaynak(yol)
    tablo = symtable.symtable(src, yol, "exec")
    modul = {s.get_name() for s in tablo.get_symbols() if s.is_assigned() or s.is_imported() or s.is_namespace()}
    yerlesik = set(dir(builtins))
    for fn, _ in _eslesme(src).values():
        ft = next(c for c in tablo.get_children() if c.get_name() == fn)
        eksik = _ortuk_globaller(ft) - modul - yerlesik
        assert not eksik, f"{yol}:{fn} tanımsız ad kullanıyor: {sorted(eksik)}"
