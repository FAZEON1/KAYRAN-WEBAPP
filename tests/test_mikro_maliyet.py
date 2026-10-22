# -*- coding: utf-8 -*-
"""Paçal Mikro'nun giriş paçalından (kayranpm/mikro_maliyet.py, 22.10.2026).

Kullanıcı: "Mikro'da ürünlerin maliyeti paçalı vs neyse programda da ona göre revize olsun" ve iki rakam yan yana
gösterildikten sonra "A ile yap": Σ giriş maliyeti (USD) ÷ Σ giren adet; masraf / değer farkı dahil, transfer hariç.
Canlı örnekler (mikro_stok_maliyet, 22.10.2026): F1M650BBM 39,53 $ (Mikro'nun satış maliyeti 28,37 $ idi),
Faze3 1,70 $ (yurt içi değer farkı faturalarıyla 1,7045 $).
"""
from pathlib import Path

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


# ── Sevkiyat paçalı: antrepodan parça parça çekim (22.10.2026) ─────────
# Canlı örnek P251031: 3 konteyner, 2'si çekildi (VANEX-015, masraf 29.361 ve 31.180 $; bunun 23.417 ve 24.868 $'ı
# demuraj + liman / antrepo ardiyesi), 1'i antrepoda. F21E650BWM satışları masrafsız (FOB 37,34 $) kaydedilmişti.
def _dosya(i, pi, durum, masraf=None):
    return {"id": i, "pi_no": pi, "dosya_no": pi, "durum": durum, "doviz": "USD", "masraflar": masraf or {}}


DOSYA = [_dosya(1, "P251031-29-ST", "Teslim Alındı", {"navlun": 5254.82, "demuraj": 12697.36, "liman_ardiye": 9346.21,
                                                       "antrepo_ardiye": 1373.5, "diger": 689.11}),
         _dosya(2, "P251031-30-ST", "Antrepoda"),
         _dosya(3, "P251031-31-ST", "Teslim Alındı", {"navlun": 5580.4, "demuraj": 13484.08, "liman_ardiye": 9925.3,
                                                       "antrepo_ardiye": 1458.61, "diger": 732.61}),
         _dosya(4, "PIFAZ1-1", "Teslim Alındı", {"navlun": 100.0, "demuraj": 50.0})]          # kapalı sevkiyat
KALEM = [{"dosya_id": 1, "sku": "F21E650BBM", "adet": 1050, "birim_fob": 35.5},
         {"dosya_id": 2, "sku": "F21E650BBM", "adet": 1050, "birim_fob": 35.5},
         {"dosya_id": 3, "sku": "F21E650BWM", "adet": 1050, "birim_fob": 37.72},
         {"dosya_id": 4, "sku": "KAPALI", "adet": 10, "birim_fob": 100}]


def test_sevkiyat_pacali_bekleme_antrepodakilere_de_yayilir():
    dz = M.sevkiyat_duzeltmesi(DOSYA, KALEM)
    fob_cek, fob_tum = 1050 * 35.5 + 1050 * 37.72, 1050 * 35.5 * 2 + 1050 * 37.72
    bek = 12697.36 + 9346.21 + 1373.5 + 13484.08 + 9925.3 + 1458.61
    normal = 5254.82 + 689.11 + 5580.4 + 732.61
    bwm_yeni = 1050 * 37.72 * (normal / fob_cek + bek / fob_tum)
    bwm_eski = 5580.4 + 13484.08 + 9925.3 + 1458.61 + 732.61
    assert dz["F21E650BWM"]["fark"] == pytest.approx(bwm_yeni - bwm_eski)
    assert dz["F21E650BWM"]["bekleme"] == pytest.approx(1050 * 37.72 * bek / fob_tum)
    assert dz["KAPALI"] == {"fark": 0.0, "bekleme": 50.0}               # sevkiyat bitti: Mikro'daki dağılım kalır
    # Mikro: 1060 adet, FOB 39.585 $ + masraf 29.919 $ → 65,57; sevkiyat paçalı ≈ 57,9 $ (bekleme ≈ 15,8 $/adet)
    mikro = [_r("F21E650BWM", 2026, 12, 1060, 39585.0), _r("F21E650BWM", 2026, 3, 0, 29918.94)]
    p, b = M.pacal_hesapla_sevkiyatli(mikro, dz)
    assert M.pacal_hesapla(mikro)["F21E650BWM"] == pytest.approx(65.57, abs=0.01)
    assert p["F21E650BWM"] == pytest.approx(57.9, abs=0.1) and b["F21E650BWM"] == pytest.approx(15.8, abs=0.1)
    assert M.sevkiyat_anahtari({"pi_no": "2511S07-4"}) == "2511S07"


def test_pnl_bekleme_ayri_satir():
    import tests.test_satis_pnl as T

    class S(T.Sahte):
        def bekleme_payi(self):
            return {"K1": 2.5}
    r = T._p(S())
    assert r["bekleme"] == pytest.approx(10 * 2.5)                     # 10 adet K1 × 2,5 $
    assert T._p()["bekleme"] == 0.0                                     # kaynak bilmiyorsa 0
    m = (Path(__file__).resolve().parent.parent / "satis" / "main.py").read_text(encoding="utf-8")
    assert "antrepo / liman bekleme maliyeti" in m
