# -*- coding: utf-8 -*-
"""Paçal Mikro'nun giriş paçalından (kayranpm/mikro_maliyet.py, 22.10.2026).

Kullanıcı: "Mikro'da ürünlerin maliyeti paçalı vs neyse programda da ona göre revize olsun" ve iki rakam yan yana
gösterildikten sonra "A ile yap": Σ giriş maliyeti (USD) ÷ Σ giren adet; masraf / değer farkı dahil, transfer hariç.
Canlı örnekler (mikro_stok_maliyet, 22.10.2026): F1M650BBM 39,53 $ (Mikro'nun satış maliyeti 28,37 $ idi),
Faze3 1,70 $ (yurt içi değer farkı faturalarıyla 1,7045 $).
"""
import pytest

from kayranpm import mikro_maliyet as M


def _r(kod, yil, cins, giris, alt):
    return {"stok_kod": kod, "yil": yil, "hareket_cins": cins, "giris": giris, "alt_giris": alt}


F1M = [_r("F1M650BBM", 2025, 0, 0, 0), _r("F1M650BBM", 2025, 3, 0, 12544.18), _r("F1M650BBM", 2025, 5, 0, 0),
       _r("F1M650BBM", 2025, 6, 710, 24567.57), _r("F1M650BBM", 2025, 10, 28, 1310.68),
       _r("F1M650BBM", 2025, 12, 8981, 310828.40), _r("F1M650BBM", 2026, 3, 0, 61461.38),
       _r("F1M650BBM", 2026, 6, 70, 3538.13), _r("F1M650BBM", 2026, 11, 10, 446.08),
       _r("F1M650BBM", 2026, 12, 5605, 191475.00)]
FAZE3 = [_r("Faze3", 2025, 0, 10060, 16599.00), _r("Faze3", 2026, 6, 3120, 4744.53), _r("Faze3", 2026, 9, 0, 547.98)]


def test_giris_pacali_masraf_dahil_transfer_haric():
    p = M.pacal_hesapla(F1M + FAZE3 + [_r("Fazeon X24F165S", 2026, 12, 10, 500), _r("BOS", 2026, 3, 0, 100),
                                         _r("SADECE_TRANSFER", 2026, 6, 5, 50)])
    beklenen = (12544.18 + 1310.68 + 310828.40 + 61461.38 + 446.08 + 191475.00) / (28 + 8981 + 10 + 5605)
    assert p["F1M650BBM"] == pytest.approx(round(beklenen, 4)) and p["F1M650BBM"] == pytest.approx(39.53, abs=0.01)
    assert p["FAZE3"] == pytest.approx(round((16599 + 547.98) / 10060, 4))       # değer farkı dahil, transfer yok
    assert p["X24F165S"] == 50.0                                                 # 'Fazeon ' öneki: kart SKU'su
    assert "BOS" not in p and "SADECE_TRANSFER" not in p                          # adet yok → paçal yok


def test_get_pacal_map_mikro_once(monkeypatch):
    import ithalat.database as idb
    import satis.database as sdb
    import kayranpm.mikro_maliyet as mm
    monkeypatch.setattr(idb, "get_sku_maliyet_ozet", lambda: {"F1M650BBM": {"pacal_final": 31.0},
                                                               "ESKI": {"pacal_final": 7.0}})
    monkeypatch.setattr(sdb, "_urunler_hepsi", lambda *_: [{"sku": "KART", "alis_fiyati": 3.0}])
    monkeypatch.setattr(mm, "_oku", lambda: F1M)
    monkeypatch.setattr(mm, "durum", lambda: {})
    for f in (sdb.get_pacal_map, getattr(sdb, "_mikro_pacal", None)):
        getattr(f, "clear", lambda: None)()
    p = sdb.get_pacal_map()
    assert p["F1M650BBM"] == pytest.approx(39.53, abs=0.01)       # Mikro, İthalat paçalının (31) yerine
    assert p["ESKI"] == 7.0 and p["KART"] == 3.0                  # Mikro'da olmayan: eski hesap yedek
    monkeypatch.setattr(mm, "durum", lambda: {"acik": False})
    for f in (sdb.get_pacal_map, getattr(sdb, "_mikro_pacal", None)):
        getattr(f, "clear", lambda: None)()
    assert sdb.get_pacal_map()["F1M650BBM"] == 31.0                # kapatılınca eski hesap
