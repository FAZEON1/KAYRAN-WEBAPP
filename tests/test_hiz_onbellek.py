# -*- coding: utf-8 -*-
"""Hız ve önbellek kuralları (Ekim 2026).

- Paçal (ithalat parti satırları) önbellekli; hata önbelleğe girmez.
- Silen / yazan fonksiyon @st.cache_data ile sarılmaz (sil_firma_stok_tarihi sarılıydı:
  aynı tarih 5 dk içinde yeniden silinince silme çalışmadan eski sayı dönebiliyordu).
- Bir fonksiyon iki kez @st.cache_data ile sarılmaz (get_sku_kategori_map 60 + 300 sn idi).
"""
import ast
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
_YAZAN = ("sil_", "ekle_", "kaydet", "guncelle_", "upsert_", "set_")


def _onbellekli_fonksiyonlar(yol):
    agac = ast.parse(yol.read_text(encoding="utf-8"))
    for n in ast.walk(agac):
        if isinstance(n, ast.FunctionDef):
            say = sum(1 for d in n.decorator_list if "cache_data" in ast.unparse(d))
            if say:
                yield n.name, say


def _canli_dosyalar():
    for p in KOK.rglob("*.py"):
        if any(x in p.parts for x in ("tests", ".git", ".venv", "__pycache__")):
            continue
        yield p


def test_yazan_fonksiyon_onbellege_alinmaz():
    bulgu = [f"{p.relative_to(KOK)}:{ad}" for p in _canli_dosyalar()
             for ad, _ in _onbellekli_fonksiyonlar(p) if ad.startswith(_YAZAN)]
    assert not bulgu, f"veri yazan/silen fonksiyon önbellekli: {bulgu}"


def test_cift_onbellek_yok():
    bulgu = [f"{p.relative_to(KOK)}:{ad}" for p in _canli_dosyalar()
             for ad, say in _onbellekli_fonksiyonlar(p) if say > 1]
    assert not bulgu, f"iki kez @st.cache_data: {bulgu}"


def test_parti_satirlari_onbellekli_govdeden_gelir(monkeypatch):
    import ithalat.database as idb
    ad = dict(_onbellekli_fonksiyonlar(KOK / "ithalat" / "database.py"))
    assert "_parti_satirlari_hesapla" in ad, "paçal parti hesabı önbellekli olmalı"
    monkeypatch.setattr(idb, "_parti_satirlari_hesapla", lambda: [{"sku": "A"}])
    assert idb.get_parti_satirlari() == [{"sku": "A"}]


def test_parti_satirlari_hatada_bos_doner(monkeypatch):
    """Hata gövdeden FIRLAR (önbelleğe girmez), dış fonksiyon [] döner."""
    import ithalat.database as idb

    def patla():
        raise RuntimeError("bağlantı yok")
    monkeypatch.setattr(idb, "_parti_satirlari_hesapla", patla)
    assert idb.get_parti_satirlari() == []
