# -*- coding: utf-8 -*-
"""Sayfa gövdeleri parça (st.fragment) olarak çalışır — geri dönüş koruması.

Ölçüm (150 ms ağ gecikmesi): Yönetim'de görünüm filtresi 1,5 → 1,0 sn
(önbellek ısınınca 0,84 → 0,21), filtre değişiminde tam çalışma 1 → 0.
Sol menüden sayfa değişimi ve kayıt sonrası st.rerun() tam çalışma kalır.
"""
import ast
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
MODULLER = ["satis/main.py", "kayranpm/main.py", "kayranacc/main.py", "depo/main.py",
            "ithalat/main.py", "teknikservis/main.py", "hesap_makinesi/main.py", "yonetim.py"]


def _yerel_adlar(nodes):
    """Fonksiyon seviyesinde bağlanan adlar (iç fonksiyon ve comprehension'a inmez)."""
    s = set()

    def gez(n):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            s.add(n.name)
            return
        if isinstance(n, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            return
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            s.add(n.id)
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                s.add((a.asname or a.name).split(".")[0])
        if isinstance(n, ast.ExceptHandler) and n.name:
            s.add(n.name)
        for c in ast.iter_child_nodes(n):
            gez(c)
    for n in nodes:
        gez(n)
    return s


def _run_ve_parca(yol):
    agac = ast.parse((KOK / yol).read_text(encoding="utf-8"))
    run = next(n for n in agac.body if isinstance(n, ast.FunctionDef) and n.name == "run")
    parca = [n for n in run.body if isinstance(n, ast.FunctionDef) and n.name == "_sayfa_parcasi"]
    return run, parca


def test_her_modulun_sayfa_govdesi_parca():
    for yol in MODULLER:
        run, parca = _run_ve_parca(yol)
        assert len(parca) == 1, f"{yol}: run() içinde _sayfa_parcasi yok"
        p = parca[0]
        assert any("fragment" in ast.unparse(d) for d in p.decorator_list), f"{yol}: @st.fragment yok"
        # parça tanımından sonra yalnız çağrısı gelir (sayfa gövdesi tamamen içeride)
        idx = run.body.index(p)
        kalan = [ast.unparse(n) for n in run.body[idx + 1:]]
        assert kalan == ["_sayfa_parcasi()"], f"{yol}: parçadan sonra başka ifade var: {kalan}"


def test_nonlocal_listesi_paylasilan_degiskenlerle_birebir():
    """Sayfa gövdesi run()'ın yerel değişkenlerinden birini YAZIYORSA nonlocal
    olmalı (yoksa UnboundLocalError ya da sessiz kopya). Liste otomatik
    hesaplanır; sayfaya yeni bir paylaşılan değişken girince bu test yakalar."""
    for yol in MODULLER:
        run, (p,) = _run_ve_parca(yol)
        idx = run.body.index(p)
        once = _yerel_adlar(run.body[:idx]) | {a.arg for a in run.args.args}
        icerde = _yerel_adlar(p.body)
        beklenen = sorted(once & icerde)
        yazili = sorted(ad for n in p.body if isinstance(n, ast.Nonlocal) for ad in n.names)
        assert yazili == beklenen, f"{yol}: nonlocal {yazili} ≠ hesaplanan {beklenen}"


def test_parca_icinde_global_yok():
    for yol in MODULLER:
        run, (p,) = _run_ve_parca(yol)
        assert not any(isinstance(n, ast.Global) for n in ast.walk(p)), yol
