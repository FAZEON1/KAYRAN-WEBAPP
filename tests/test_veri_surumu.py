# -*- coding: utf-8 -*-
"""Veri sürümü (shared/veri_surumu.py) ve tek urunler okuması (Ekim 2026).

Ağır ekran önbellekleri (Tüm Ürünler, Genel bakış, paçal) uzun tutulur; veri değişince
veritabanı sayacı (veri_surumu, tetikleyiciyle) artar, tazelik_kontrol önbellekleri temizler.
"""
import ast
import re
from pathlib import Path

import pytest

import shared.veri_surumu as V

KOK = Path(__file__).resolve().parent.parent


@pytest.fixture
def ortam(monkeypatch):
    durum = {"surum": None, "temizlik": 1000.0}
    temiz = []
    sayac = {"v": {"urunler": 1}}
    monkeypatch.setattr(V, "_surec_durumu", lambda: durum)
    monkeypatch.setattr(V, "_surumler", lambda: sayac["v"])
    monkeypatch.setattr(V, "bagimlilari_temizle", lambda: temiz.append(1) or 0)
    return durum, temiz, sayac


# ── Tazelik kuralı ──────────────────────────────────────────────────
def test_ilk_okumada_temizlemez_sonra_ayni_kalirsa_temizlemez(ortam):
    durum, temiz, _ = ortam
    assert V.tazelik_kontrol(simdi=1001) == "ilk"
    assert V.tazelik_kontrol(simdi=5000) == "ayni"
    assert temiz == []


def test_sayac_degisince_temizler(ortam):
    durum, temiz, sayac = ortam
    V.tazelik_kontrol(simdi=1001)
    sayac["v"] = {"urunler": 2}                       # biri ürün kartını değiştirdi
    assert V.tazelik_kontrol(simdi=1002) == "degisti"
    assert len(temiz) == 1
    assert V.tazelik_kontrol(simdi=1003) == "ayni" and len(temiz) == 1


def test_izlenmeyen_tablo_temizletmez(ortam):
    durum, temiz, sayac = ortam
    V.tazelik_kontrol(simdi=1001)
    sayac["v"] = {"urunler": 1, "baska_tablo": 9}
    assert V.tazelik_kontrol(simdi=1002) == "ayni" and temiz == []


def test_tablo_yoksa_eski_bes_dakika_davranisi(ortam):
    durum, temiz, sayac = ortam
    sayac["v"] = None
    assert V.tazelik_kontrol(simdi=1000 + V.YEDEK_SURE_SN - 1) == "bekle" and temiz == []
    assert V.tazelik_kontrol(simdi=1000 + V.YEDEK_SURE_SN) == "yedek" and len(temiz) == 1


def test_hata_firlatmaz(monkeypatch):
    def patla():
        raise RuntimeError("x")
    monkeypatch.setattr(V, "_surec_durumu", patla)
    assert V.tazelik_kontrol() == "bekle"


def test_bagimlilari_temizle_yuklu_fonksiyonlari_temizler(monkeypatch):
    import kayranpm.database as pdb
    cagri = []
    monkeypatch.setattr(pdb.get_uretim_suresi, "clear", lambda: cagri.append(1), raising=False)
    assert V.bagimlilari_temizle() >= 1 and cagri == [1]


# ── Liste tutarlılığı ───────────────────────────────────────────────
def test_bagimlilar_gercek_fonksiyonlar():
    import importlib
    eksik = [f"{m}.{a}" for m, a in V.BAGIMLILAR if not hasattr(importlib.import_module(m), a)]
    assert not eksik, eksik


def _uzun_onbellekli():
    """Dekoratör satırında 'shared.veri_surumu' notu olan fonksiyonlar (UZUN_TTL)."""
    out = set()
    for p in KOK.rglob("*.py"):
        if any(x in p.parts for x in ("tests", ".git", ".venv", "__pycache__")):
            continue
        satirlar = p.read_text(encoding="utf-8").splitlines()
        for i, s in enumerate(satirlar[1:], start=1):
            m = re.match(r"def (\w+)\(", s)
            if m and "shared.veri_surumu" in satirlar[i - 1] and "cache_data" in satirlar[i - 1]:
                mod = ".".join(p.relative_to(KOK).with_suffix("").parts)
                out.add((mod, m.group(1)))
    return out


def test_uzun_onbellekli_her_fonksiyon_izleniyor():
    """Uzun önbellek yalnız veri sürümüyle tazelenen fonksiyonda olabilir."""
    uzun = _uzun_onbellekli()
    assert len(uzun) >= 10
    izlenen = set(V.BAGIMLILAR) | set(V.SATIS_BAGIMLILAR)
    assert not (uzun - izlenen), sorted(uzun - izlenen)
    for mod, ad in uzun:
        src = (KOK / (mod.replace(".", "/") + ".py")).read_text(encoding="utf-8")
        assert re.search(rf"ttl={V.UZUN_TTL}, show_spinner=False\)[^\n]*\ndef {ad}\(", src), (mod, ad)


def test_sql_ayni_tablolari_izler():
    sql = (KOK / "veritabani" / "11_veri_surumu.sql").read_text(encoding="utf-8")
    dizi = re.search(r"FOREACH t IN ARRAY ARRAY\[([^\]]+)\]", sql).group(1)
    assert tuple(re.findall(r"'(\w+)'", dizi)) == V.IZLENEN_TABLOLAR


def test_app_sayfadan_once_tazelik_kontrol_eder():
    a = (KOK / "app.py").read_text(encoding="utf-8")
    assert a.index("tazelik_kontrol()") < a.index("# Sayfa dispatch")


def test_urun_karti_yazmasi_ithalat_onbellegini_de_temizler():
    """Eskiden kayranpm/satis/depo grubu ithalat'ı kapsamıyordu: ürün kartı değişince İthalat'ın
    katalog / kategori / barkod haritası TTL dolana kadar eski kalıyordu."""
    a = (KOK / "app.py").read_text(encoding="utf-8")
    t = ast.parse(a)
    gruplar = next(ast.literal_eval(n.value) for n in ast.walk(t)
                   if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "_CACHE_GRUPLARI")
    for g in ("satis", "kayranpm", "depo"):
        assert "ithalat" in gruplar[g], g


# ── Tek urunler okuması ─────────────────────────────────────────────
URUNLER = [{"sku": "A1", "urun_adi": "kasa", "marka": "FAZEON", "kategori": "kasa", "alis_fiyati": 5},
           {"sku": "B2", "urun_adi": "fan", "marka": "", "kategori": None, "alis_fiyati": 0}]


def test_urunler_okumalari_tek_kaynaktan(monkeypatch):
    import kayranpm.database as pdb
    import satis.database as sdb
    monkeypatch.setattr(pdb, "urunler_skuya_gore", lambda: [dict(r) for r in URUNLER])
    assert sdb._urunler_hepsi("sku, alis_fiyati") == [{"sku": "A1", "alis_fiyati": 5}, {"sku": "B2", "alis_fiyati": 0}]
    assert sdb._urunler_hepsi("*") == URUNLER
    assert [r["sku"] for r in pdb.get_tum_sku_listesi()] == ["A1", "B2"]
    assert set(pdb.get_tum_sku_listesi()[0]) == {"sku", "urun_adi", "marka"}
    assert pdb.get_urun_marka_kategori()["B2"] == {"marka": "", "kategori": "", "urun_adi": "fan"}


def test_agir_ekranlar_urunleri_ortak_okumadan_alir():
    an = (KOK / "kayranpm" / "analitik.py").read_text(encoding="utf-8")
    govde = an[an.index("def tum_urunler_listesi("):an.index("def dashboard_hesapla(")]
    assert "urunler_ada_gore()" in govde and 'table("urunler")' not in govde
    db = (KOK / "kayranpm" / "database.py").read_text(encoding="utf-8")
    ham = db[db.index("def _dashboard_ham("):db.index("def get_all_dashboard_data(")]
    assert "urunler_ada_gore()" in ham and '_hepsi("urunler"' not in ham
