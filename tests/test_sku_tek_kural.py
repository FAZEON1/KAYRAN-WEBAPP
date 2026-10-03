# -*- coding: utf-8 -*-
"""SKU eşleştirme tek kural — shared.utils.sku_anahtar (Ekim 2026, ana veri Faz 3).

Eskiden 5 ayrı kural vardı: excel normalize_sku (yazım), satış _normalize_sku_yerel,
depo _hl_norm_sku ('FAZEON ' önekini atmıyordu), otonom _nsku (tire/boşluk siliyordu,
öneki atmıyordu), stok kartı satış araması (%{sku} ile yalnız sondan eşliyordu).
"""
import pathlib

import pytest

from shared.utils import sku_anahtar

KOK = pathlib.Path(__file__).resolve().parent.parent
ORNEK = ["X24F165S", "Fazeon X24F165S", "FAZEON X24F165S", " x24f165s ", "FaZeOn X24",
         "X24  F165", "X24-F165S", "FAZEON", "Fazeon  X24", "i5-ab"]


@pytest.mark.parametrize("s", ORNEK)
def test_yazim_ve_satis_normallestirmesi_sku_anahtar_ile_ayni(s):
    from kayranpm.excel_islemler import normalize_sku
    from satis.database import _normalize_sku_yerel
    assert normalize_sku(s) == _normalize_sku_yerel(s) == sku_anahtar(s)


def test_bos_sku_none_yazilmaz():
    """normalize_sku(None) eskiden 'NONE' döndürüyordu; Excel'deki boş hücre bir SKU sanılırdı."""
    from kayranpm.excel_islemler import normalize_sku
    from satis.database import _normalize_sku_yerel
    assert normalize_sku(None) == "" and _normalize_sku_yerel(None) == ""


def test_onceki_kuralla_fark_yalniz_uc_durumlarda():
    """Yazım tarafı değişikliği mevcut kayıtlarla eşleşmeyi BOZMAZ: eski normalize_sku ile
    yalnız 'FaZeOn' gibi karışık harfli önek ve boş değer farklı."""
    def eski(sku):
        sku = str(sku).strip()
        for p in ["FAZEON ", "Fazeon ", "fazeon "]:
            if sku.startswith(p):
                sku = sku[len(p):]
                break
        return sku.strip().upper()
    farkli = [s for s in ORNEK if eski(s) != sku_anahtar(s)]
    assert farkli == ["FaZeOn X24"]


def test_otonom_olcum_uygulamayla_ayni_eslesir():
    from otonom.olcum import _nsku
    assert _nsku("Fazeon X24F165S") == _nsku("X24F165S") == "X24F165S"   # önek atılır
    assert _nsku("X24-F165S") != _nsku("X24F165S")                       # uygulama tireyi eşlemez


def test_get_sku_kategori_normalize_anahtarli(monkeypatch):
    import satis.database as sdb
    monkeypatch.setattr(sdb, "_urunler_hepsi", lambda secim: [
        {"sku": "Fazeon X24", "kategori": ""}, {"sku": "X24", "kategori": "monitör"},
        {"sku": "k1 ", "kategori": "kasa"}])
    km = sdb.get_sku_kategori()
    assert km["X24"] == "monitör"            # boş olan ilk yazım dolu olanı ezmez
    assert km["K1"] == "kasa" and km.get(sku_anahtar("Fazeon X24")) == "monitör"


def test_pnl_kategori_suzgeci_onekli_satis_skusunu_bulur():
    """Satış 'Fazeon K1', kart 'K1' → P&L kategori süzgeci satışı kaybetmemeli."""
    from satis.pnl_hesap import satis_pnl
    import tests.test_satis_pnl as T
    sat = [dict(T.SAT[0], sku="Fazeon K1"), T.SAT[1]]
    r = satis_pnl("2026-09-01", "2026-09-30", "Tümü", "Kasa",
                  T.Sahte(satislar=sat, katmap={"K1": "KASA", "F1": "FAN"}))
    assert not r.get("bos")


def test_tek_kural_korumasi():
    """Bir dosya kendi SKU normalleştirmesini yeniden yazarsa CI kızarsın."""
    yasak = {
        "kayranpm/excel_islemler.py": 'for prefix in ["FAZEON ", "Fazeon ", "fazeon "]',
        "satis/database.py": 'for p in ("FAZEON ", "Fazeon ", "fazeon ")',
        "depo/main.py": "def _hl_norm_sku(s):",
        "otonom/olcum.py": 're.sub(r"[^A-Z0-9]"',
        "kayranpm/stok_karti.py": 'ilike("sku", f"%{sku}")',
    }
    geri = [y for y, kalip in yasak.items() if kalip in (KOK / y).read_text(encoding="utf-8")]
    assert not geri, f"Ayrı SKU kuralı geri gelmiş (eski sürüm mü yüklendi?): {geri}"
