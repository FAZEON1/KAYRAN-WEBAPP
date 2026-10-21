# -*- coding: utf-8 -*-
"""Mikro → depo stoğu (kayranpm/mikro_stok.py). Depo numaraları ve adlar Mikro'daki gibi (21.10.2026)."""
import sys
import types

from kayranpm import mikro_stok as M

DEPOLAR = {1: "MERKEZ DEPO", 3: "SERVİS DEPO", 4: "HAPPY LİFE", 5: "OUTLET", 9: "İADE DEPO "}


def test_kirilim_sku_ve_depo_ortak_kurala_gore():
    """Mikro 'Fazeon X24F240P' yazıyor, uygulama 'X24F240P'; 'SERVİS DEPO' uygulamada TEKNİK DEPO. Eşleşmezse
    aynı ürün iki kart olur ya da stok yanlış depoya düşerdi."""
    s = [{"sto_kod": "Fazeon X24F240P", "sto_isim": "FAZEON 24", "depo": 1, "miktar": 2051},
         {"sto_kod": "Fazeon X24F240P", "depo": 3, "miktar": 2},
         {"sto_kod": "FAZEON A2120TRA", "depo": 4, "miktar": 9360},
         {"sto_kod": "FAZEON A2120TRA", "depo": 1, "miktar": 36},
         {"sto_kod": "X27F182S", "depo": 1, "miktar": 0},
         {"sto_kod": "N50602", "depo": 9, "miktar": -50}]
    kir, adlar = M.kirilim_yap(s, DEPOLAR)
    assert kir == {"X24F240P": {"MERKEZ DEPO": 2051, "TEKNİK DEPO": 2},
                   "A2120TRA": {"HAPPY LIFE": 9360, "MERKEZ DEPO": 36},
                   "N50602": {"İADE DEPO": -50}}
    assert adlar["X24F240P"] == "FAZEON 24"


def test_farklar_yalniz_degisenler_ve_mikroda_olmayan_sifirlanir():
    kir = {"FAZE3": {"MERKEZ DEPO": 6284}, "X24F240P": {"MERKEZ DEPO": 2051}}
    urunler = [{"sku": "Faze3", "depo_kirilim": {"MERKEZ DEPO": 6287}},
               {"sku": "X24F240P", "depo_kirilim": {"MERKEZ DEPO": 2051, "HAPPY LIFE": 0}},
               {"sku": "RMAFM001", "depo_kirilim": {"MERKEZ DEPO": 50}},
               {"sku": "BOS", "depo_kirilim": {}}]
    f = M.farklar(kir, urunler)
    assert f == [("Faze3", {"MERKEZ DEPO": 6287}, {"MERKEZ DEPO": 6284}),
                 ("RMAFM001", {"MERKEZ DEPO": 50}, {})]


def test_bos_mikro_verisi_yazmaz():
    """Aktarıcı boş dönerse sayım bütün depo stoğunu sıfırlardı."""
    assert M.uygula({"bos": True, "kirilim": {}, "adlar": {}, "fark": [("X", {"MERKEZ DEPO": 1}, {})]}) == 0


def test_depo_ozeti():
    assert M.depo_ozeti([{"MERKEZ DEPO": 2, "HAPPY LIFE": 1}, {"MERKEZ DEPO": 3}, None]) == \
        {"HAPPY LIFE": 1, "MERKEZ DEPO": 5}


def test_stok_eslesmesi_acikken_g5f_hatirlatmasi_cikmaz(monkeypatch):
    from shared import yukleme_takvimi as Y
    sahte = types.ModuleType("kayranpm.mikro_stok")
    sahte.acik_mi = lambda: True
    monkeypatch.setitem(sys.modules, "kayranpm.mikro_stok", sahte)
    monkeypatch.setattr(Y, "_ayar", lambda anahtar, varsayilan: varsayilan)
    monkeypatch.setattr(Y, "_OKUYUCU", {})
    assert "g5f_sayim" not in {d["anahtar"] for d in Y.durumlar()}


def test_otonom_esitleme_bir_is_cokse_digerleri_surer(monkeypatch):
    """Saatlik GitHub işi (otonom/mikro_esitle.py): bir eşitleme hata verirse diğerleri yine çalışmalı."""
    import importlib.util
    from pathlib import Path
    yol = Path(__file__).resolve().parent.parent / "otonom" / "mikro_esitle.py"
    spec = importlib.util.spec_from_file_location("otonom_mikro_esitle", yol)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sahte = types.ModuleType("sahte_esitle")
    sahte.bozuk = lambda: 1 / 0
    sahte.bos = lambda: None
    sahte.dolu = lambda: 3
    monkeypatch.setitem(sys.modules, "sahte_esitle", sahte)
    out = mod.calistir((("A", "sahte_esitle", "bozuk"), ("B", "sahte_esitle", "bos"), ("C", "sahte_esitle", "dolu")))
    assert out[0][1].startswith("HATA ZeroDivisionError")
    assert out[1] == ("B", "yeni veri yok / kapalı")
    assert out[2] == ("C", "tamam: 3")
    # İş listesindeki her fonksiyon gerçekten var (adı değişirse iş sessizce boşa dönmesin)
    for _ad, modul, fonk in mod.ISLER:
        assert callable(getattr(importlib.import_module(modul), fonk))
