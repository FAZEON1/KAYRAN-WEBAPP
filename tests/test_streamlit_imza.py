# -*- coding: utf-8 -*-
"""
Streamlit çağrılarının parametre kontrolü.

NEDEN: PR #18'de `st.segmented_control(use_container_width=...)` canlıda
TypeError verdi ve site açılmadı. O parametre Streamlit'te yoktu; testler
sahte streamlit ile koştuğu için kimse fark etmedi.

NE YAPAR: Tüm canlı .py dosyalarını okur (çalıştırmaz), her Streamlit
çağrısını bulur ve GERÇEK Streamlit'in imzasıyla karşılaştırır:
  - olmayan fonksiyon      (st.segmnted_control)       → hata
  - olmayan parametre adı  (use_container_width=...)   → hata
  - fazla sıralı argüman                               → hata

Yakalanan çağrı biçimleri:
  st.x(...)   _st.x(...)   st.sidebar.x(...)   st.column_config.X(...)
  c1.x(...)   cols[0].x(...)   tab.x(...)   — st.columns / st.tabs /
  st.container / st.expander / st.popover / st.form / st.empty ile
  oluşturulan değişkenler (atama ya da `with ... as ad`).

ÇALIŞMA KOŞULU: Gerçek streamlit kurulu değilse ATLANIR (CI böyle).
Teslimattan önce yerelde gerçek streamlit'le çalıştır:
    pip install "streamlit==1.64.*"
    cd tests && python -m pytest -q test_streamlit_imza.py
"""

import ast
import inspect
import os
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent

# CI sözdizimi adımıyla aynı ölü klasör listesi (.github/workflows/testler.yml)
OLU = ("(", "/shared/shared", "/shared/kayran", "/shared/satis", "/shared/depo",
       "/shared/ithalat", "/shared/teknik", "/kayranpm/kayranpm", "/satis/satis",
       "_tek.py", "/.git", "/tests/", "__pycache__")

ST_ADLARI = {"st", "_st"}
KAP_URETENLER = {"columns", "tabs", "container", "expander", "popover",
                 "form", "empty", "status", "chat_message"}


def _gercek_streamlit():
    """Gerçek paket kuruluysa döndür; conftest'in sahtesiyse None."""
    try:
        import streamlit as st
    except ImportError:
        return None
    if not hasattr(st, "__version__") or not hasattr(st, "delta_generator"):
        return None
    return st


def _dosyalar():
    for k, _, fs in os.walk(KOK):
        for f in fs:
            p = os.path.join(k, f)
            if f.endswith(".py") and not any(x in p.replace(os.sep, "/") for x in OLU):
                yield Path(p)


def _st_zinciri(dugum):
    """`st.a.b` → ["a", "b"]; Streamlit'e ait değilse None."""
    parcalar = []
    while isinstance(dugum, ast.Attribute):
        parcalar.append(dugum.attr)
        dugum = dugum.value
    if isinstance(dugum, ast.Name) and dugum.id in ST_ADLARI:
        return list(reversed(parcalar))
    return None


def _hedef_adlari(hedef):
    if isinstance(hedef, ast.Name):
        yield hedef.id
    elif isinstance(hedef, (ast.Tuple, ast.List)):
        for e in hedef.elts:
            yield from _hedef_adlari(e)
    elif isinstance(hedef, ast.Starred):
        yield from _hedef_adlari(hedef.value)


KAPSAM = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _kapsam_dugumleri(kapsam):
    """Kapsamın kendi düğümleri — iç fonksiyonlara inmeden."""
    yigin = list(ast.iter_child_nodes(kapsam))
    while yigin:
        d = yigin.pop()
        yield d
        if not isinstance(d, KAPSAM):
            yigin.extend(ast.iter_child_nodes(d))


def _kap_turu(deger):
    """st.status(...) → "status"; diğer kap üreticiler → "dg"; değilse None."""
    if not isinstance(deger, ast.Call):
        return None
    z = _st_zinciri(deger.func)
    if not z or z[-1] not in KAP_URETENLER:
        return None
    return "status" if z[-1] == "status" else "dg"


def _baglamalar(kapsam):
    """Kapsamda ad → {atanan değer türleri} ("dg", "status", "diger")."""
    b = {}

    def ekle(hedef, tur):
        for ad in _hedef_adlari(hedef):
            b.setdefault(ad, set()).add(tur)

    for d in _kapsam_dugumleri(kapsam):
        if isinstance(d, ast.Assign):
            tur = _kap_turu(d.value) or "diger"
            for h in d.targets:
                ekle(h, tur)
        elif isinstance(d, (ast.AnnAssign, ast.AugAssign)) and d.value is not None:
            ekle(d.target, "diger")
        elif isinstance(d, (ast.For, ast.AsyncFor, ast.comprehension)):
            ekle(d.target, "diger")
        elif isinstance(d, (ast.With, ast.AsyncWith)):
            for it in d.items:
                if it.optional_vars is not None:
                    ekle(it.optional_vars, _kap_turu(it.context_expr) or "diger")
        elif isinstance(d, ast.NamedExpr):
            ekle(d.target, "diger")
    if isinstance(kapsam, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        a = kapsam.args
        for x in a.posonlyargs + a.args + a.kwonlyargs + [a.vararg, a.kwarg]:
            if x is not None:
                b.setdefault(x.arg, set()).add("diger")
    return b


def _cagrilar(yol):
    """(çağrı, görünen_ad, hedef) üretir.
    hedef: ("st", [..]) · ("dg", metot) · ("status", metot)."""
    agac = ast.parse(yol.read_text(encoding="utf-8"), filename=str(yol))

    def gez(kapsam, st_adlari, kaplar):
        b = _baglamalar(kapsam)
        # Yerelde başka bir şeye atanan "st"/"_st" artık Streamlit değil
        st_adlari = {a for a in st_adlari if a not in b}
        kaplar = {a: t for a, t in kaplar.items() if a not in b}
        for ad, turler in b.items():
            if len(turler) == 1 and next(iter(turler)) in ("dg", "status"):
                kaplar[ad] = next(iter(turler))
        for d in _kapsam_dugumleri(kapsam):
            if isinstance(d, KAPSAM):
                yield from gez(d, st_adlari, kaplar)
                continue
            if not isinstance(d, ast.Call) or not isinstance(d.func, ast.Attribute):
                continue
            z = _st_zinciri(d.func)
            kok_ad = d.func
            while isinstance(kok_ad, ast.Attribute):
                kok_ad = kok_ad.value
            if z and kok_ad.id in st_adlari:
                # st.session_state.get / st.query_params.clear gibi sözlük işlemleri
                if z[0] in ("session_state", "query_params", "secrets", "context"):
                    continue
                yield d, "st." + ".".join(z), ("st", z)
                continue
            kok = d.func.value
            if isinstance(kok, ast.Subscript):
                kok = kok.value
            if isinstance(kok, ast.Name) and kok.id in kaplar:
                yield d, f"{kok.id}.{d.func.attr}", (kaplar[kok.id], d.func.attr)

    yield from gez(agac, set(ST_ADLARI), {})


def _cozumle(st, hedef):
    tur, yol = hedef
    if tur == "dg":
        return getattr(st.delta_generator.DeltaGenerator, yol, None)
    if tur == "status":
        from streamlit.elements.lib.mutable_status_container import StatusContainer
        return getattr(StatusContainer, yol, None)
    nesne = st
    for i, parca in enumerate(yol):
        # st.sidebar.x → DeltaGenerator metodu
        if parca == "sidebar" and i == 0:
            nesne = st.delta_generator.DeltaGenerator
            continue
        nesne = getattr(nesne, parca, None)
        if nesne is None:
            return None
    return nesne


def _imza_hatasi(fn, cagri):
    try:
        imza = inspect.signature(fn)
    except (TypeError, ValueError):
        return None                       # imzası okunamıyor → kontrol dışı
    p = list(imza.parameters.values())
    if p and p[0].name == "self":
        p = p[1:]
    kw_serbest = any(x.kind == x.VAR_KEYWORD for x in p)
    sira_serbest = any(x.kind == x.VAR_POSITIONAL for x in p)

    hatalar = []
    if not kw_serbest:
        gecerli = {x.name for x in p if x.kind in (x.POSITIONAL_OR_KEYWORD, x.KEYWORD_ONLY)}
        for kw in cagri.keywords:
            if kw.arg is not None and kw.arg not in gecerli:
                hatalar.append(f"'{kw.arg}' diye parametre yok")
    if not sira_serbest and not any(isinstance(a, ast.Starred) for a in cagri.args):
        sirali = [x for x in p if x.kind in (x.POSITIONAL_ONLY, x.POSITIONAL_OR_KEYWORD)]
        if len(cagri.args) > len(sirali):
            hatalar.append(f"{len(cagri.args)} sıralı argüman verilmiş, en fazla {len(sirali)}")
    return "; ".join(hatalar) or None


def test_streamlit_cagrilari_gercek_imzaya_uyuyor():
    st = _gercek_streamlit()
    if st is None:
        pytest.skip("Gerçek streamlit kurulu değil (CI). Yerelde kurup çalıştır.")

    sorunlar, sayac = [], 0
    for yol in sorted(_dosyalar()):
        try:
            cagrilar = list(_cagrilar(yol))
        except SyntaxError:
            continue                      # sözdizimini CI ayrı adımda kontrol ediyor
        for cagri, ad, hedef in cagrilar:
            sayac += 1
            fn = _cozumle(st, hedef)
            yer = f"{yol.relative_to(KOK)}:{cagri.lineno}  {ad}(...)"
            if fn is None:
                sorunlar.append(f"{yer}  → Streamlit {st.__version__}'te böyle bir şey yok")
                continue
            if not callable(fn):
                continue
            h = _imza_hatasi(fn, cagri)
            if h:
                sorunlar.append(f"{yer}  → {h}")

    assert sayac > 1000, f"Yalnız {sayac} çağrı bulundu — tarayıcı bozulmuş olabilir"
    assert not sorunlar, (
        f"Streamlit {st.__version__} ile uyumsuz {len(sorunlar)} çağrı "
        f"(canlıda TypeError/AttributeError verir):\n  " + "\n  ".join(sorunlar)
    )


def test_tarayici_pr18_hatasini_yakalar():
    """Testin kendisinin testi: PR #18'deki hatalı çağrıyı gerçekten yakalıyor mu?"""
    st = _gercek_streamlit()
    if st is None:
        pytest.skip("Gerçek streamlit kurulu değil (CI).")
    kod = ast.parse("st.segmented_control('Tema', ['Koyu','Açık'], use_container_width=True)")
    cagri = kod.body[0].value
    fn = _cozumle(st, ("st", ["segmented_control"]))
    assert _imza_hatasi(fn, cagri), "PR #18 hatası yakalanmadı — imza kontrolü çalışmıyor"
