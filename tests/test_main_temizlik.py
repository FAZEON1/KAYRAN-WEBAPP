# -*- coding: utf-8 -*-
"""kayranpm/main.py temizliği (Ekim 2026).

52 pyflakes uyarısı vardı (49 kullanılmayan içe aktarma, 3 kullanılmayan değişken);
temizlendi. Bu testler:
  1) main.py içe aktarılabiliyor mu — test paketinde main.py'yi yükleyen tek test
     yoktu, kırık bir içe aktarma CI'dan sessizce geçerdi.
  2) Modül düzeyindeki içe aktarmalar kullanılıyor mu — eski bir sürüm yüklenince
     ölü içe aktarmalar geri gelirse yakalar. CI pyflakes kurmadığı için ast ile.
"""
import ast
import pathlib

MAIN = pathlib.Path(__file__).resolve().parent.parent / "kayranpm" / "main.py"


def test_main_ice_aktarilir_ve_run_var():
    import kayranpm.main as m
    assert callable(m.run)


def test_main_modul_duzeyi_ice_aktarmalari_kullaniliyor():
    agac = ast.parse(MAIN.read_text(encoding="utf-8"))
    alinan = {}
    for dugum in agac.body:                                   # yalnız modül düzeyi
        if isinstance(dugum, (ast.Import, ast.ImportFrom)):
            for a in dugum.names:
                ad = (a.asname or a.name).split(".")[0]
                alinan[ad] = dugum.lineno
    kullanilan = {d.id for d in ast.walk(agac) if isinstance(d, ast.Name)}
    olu = {ad: satir for ad, satir in alinan.items() if ad not in kullanilan}
    assert not olu, f"main.py'de kullanılmayan içe aktarma (eski sürüm mü yüklendi?): {olu}"
