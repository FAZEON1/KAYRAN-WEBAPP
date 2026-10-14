# -*- coding: utf-8 -*-
"""Davranış kilidi — satis.database.get_pacal_map (TÜM maliyetlerin tek kapısı).

Veri sahte Supabase'den (tests/davranis/conftest.py) okunur: ithalat_dosyalari, ithalat_kalemleri,
urunler. Böylece get_dosyalar / get_tum_kalemler / _kategori_doldur / get_parti_satirlari /
get_sku_maliyet_ozet / yurt içi alış yedeği zinciri UÇTAN UCA çalışır; iç düzen değişse de
(sayfalama, önbellek, atomik okuma) sayılar aynı kalmalı.

Her testin başında hesap elle yazılıdır. Tutarlar USD.
"""
import pytest


def _kur(monkeypatch, db):
    import ithalat.database as idb
    import kayranpm.database as pdb
    monkeypatch.setattr(idb, "_get_client", lambda: db)
    monkeypatch.setattr(pdb, "get_client", lambda: db)


def _pacal(monkeypatch, db):
    _kur(monkeypatch, db)
    from satis.database import get_pacal_map
    return get_pacal_map()


# ── Ortak veri ────────────────────────────────────────────────────────
D1 = {"id": 1, "dosya_no": "2026-01", "tarih": "2026-03-01", "durum": "Teslim Alındı",
      "masraflar": {"navlun": 300, "gv": 100, "diger": 50}, "fatura_indirim": 100}
D1_KALEM = [
    {"id": 11, "dosya_id": 1, "sku": "X24F165S", "adet": 10, "birim_fob": 50, "urun_grubu": "MONİTÖR"},
    {"id": 12, "dosya_id": 1, "sku": "K1", "adet": 5, "birim_fob": 100, "urun_grubu": "MONİTÖR"},
]
# Eski kayıt: masraflar JSONB boş, sabit kolonlar dolu; durum BOŞ (eski kayıt → paçala girer)
D2 = {"id": 2, "dosya_no": "2025-07", "tarih": "2026-05-01", "durum": "",
      "masraflar": None, "navlun": 20, "gumruk": 30, "sigorta": 0, "nakliye": 10, "diger": 0}
D2_KALEM = [{"id": 21, "dosya_id": 2, "sku": "Fazeon X24F165S", "adet": 20, "birim_fob": 30,
             "urun_grubu": "MONİTÖR"}]
# Yoldaki parti: paçala GİRMEZ
D3 = {"id": 3, "dosya_no": "2026-09", "tarih": "2026-09-20", "durum": "Yolda", "masraflar": {}}
D3_KALEM = [{"id": 31, "dosya_id": 3, "sku": "X24F165S", "adet": 100, "birim_fob": 10, "urun_grubu": "MONİTÖR"},
            {"id": 32, "dosya_id": 3, "sku": "Y1", "adet": 50, "birim_fob": 4, "urun_grubu": "MONİTÖR"}]


def _db(sahte_db, urunler=(), dosyalar=(D1, D2, D3), kalemler=None):
    if kalemler is None:
        kalemler = D1_KALEM + D2_KALEM + D3_KALEM
    return sahte_db(ithalat_dosyalari=list(dosyalar), ithalat_kalemleri=list(kalemler), urunler=list(urunler))


# ══════════════════════════════════════════════════════════════════════
def test_ithalat_pacali_jsonb_indirim_eski_kolon_yolda_haric(sahte_db, monkeypatch):
    """D1 (JSONB masraf + fatura altı indirim):
         brüt FOB = 10×50 + 5×100 = 1.000 ; indirim 100 → net 900 (oran %10)
         masraf = 300 + 100 + 50 = 450 → yüzde = 450 / 900 = %50
         X24F165S: fob 50×0,9 = 45 → final 45×1,5 = 67,50
         K1      : fob 100×0,9 = 90 → final 135,00
       D2 (eski sabit kolonlar navlun 20 + gumruk 30 + nakliye 10 = 60; durum boş → dahil):
         'Fazeon X24F165S' 20×30 = 600 → yüzde 60/600 = %10 → final 33,00
       D3 'Yolda' → hariç (100 adet × 10 paçalı aşağı çekmez).
       Paçal X24F165S (yazımlar birleşik) = (10×67,5 + 20×33) / 30 = 1.335 / 30 = 44,50"""
    p = _pacal(monkeypatch, _db(sahte_db))
    assert p["X24F165S"] == pytest.approx(44.5)
    assert p["K1"] == pytest.approx(135.0)
    assert "FAZEON X24F165S" not in p          # anahtar kanonik
    assert "Y1" not in p                       # yalnız yoldaki partisi var, yurt içi alışı yok
    assert set(p) == {"X24F165S", "K1"}


def test_maliyet_ozeti_son_parti_ve_adet(sahte_db, monkeypatch):
    """get_sku_maliyet_ozet (paçalın kaynağı):
         X24F165S pacal_fob = (10×45 + 20×30)/30 = 1.050/30 = 35,00 ; pacal_final 44,50
         son parti = yoldaki olmayanlar içinde en yeni TARİHLİ dosya = D2 (2026-05-01):
           son_fob 30, son_final 33 ; toplam_adet 30 (D3'ün 100'ü yok) ; dosya_sayisi 2"""
    _kur(monkeypatch, _db(sahte_db))
    from ithalat.database import get_sku_maliyet_ozet
    o = get_sku_maliyet_ozet()["X24F165S"]
    assert o["pacal_fob"] == pytest.approx(35.0)
    assert o["pacal_final"] == pytest.approx(44.5)
    assert o["son_fob"] == pytest.approx(30.0)
    assert o["son_final"] == pytest.approx(33.0)
    assert o["son_tarih"] == "2026-05-01"
    assert o["toplam_adet"] == pytest.approx(30)
    assert o["dosya_sayisi"] == 2


def test_yurt_ici_alis_yedek_ve_oncelik(sahte_db, monkeypatch):
    """Ürün kartı alis_fiyati YALNIZ paçalı olmayan / sıfır olan SKU'ya yazılır:
         'x24f165s' kartı alis 99   → ithalat paçalı (44,50) kazanır
         'Kaspersky' alis 12,5      → ithalatı yok → 12,50 (anahtar KASPERSKY)
         'Y1' alis '8'              → yalnız yoldaki partisi var → 8,00 (metin sayı da okunur)
         'Z0' alis 3; ithalatta birim_fob 0 → paçal 0 → 3,00
         'MP1' alis 0               → haritaya girmez
       Z0 D1'e 0 FOB'la eklenince D1 yüzdesi değişmez (mal bedeli 0 eklenir)."""
    urunler = [{"sku": "x24f165s", "alis_fiyati": 99}, {"sku": "Kaspersky", "alis_fiyati": 12.5},
               {"sku": "Y1", "alis_fiyati": "8"}, {"sku": "Z0", "alis_fiyati": 3},
               {"sku": "MP1", "alis_fiyati": 0}]
    kalem = D1_KALEM + [{"id": 13, "dosya_id": 1, "sku": "Z0", "adet": 5, "birim_fob": 0,
                         "urun_grubu": "MONİTÖR"}] + D2_KALEM + D3_KALEM
    p = _pacal(monkeypatch, _db(sahte_db, urunler=urunler, kalemler=kalem))
    assert p == pytest.approx({"X24F165S": 44.5, "K1": 135.0, "KASPERSKY": 12.5, "Y1": 8.0, "Z0": 3.0})


def test_grup_masraf_dagitimi_hacim_ozel_ortak(sahte_db, monkeypatch):
    """Çoklu grup dosya D4 (indirim yok), gruplar kalem sırasıyla MONİTÖR, KASA:
         MONİTÖR: M1 10×100 = 1.000 FOB, cbm 2 ; KASA: K2 20×25 = 500 FOB, cbm 6
         navlun 300 → __hacim__ : MONİTÖR 300×2/8 = 75, KASA (son, kalan) 225
         gv 120     → 'MONİTÖR' (özel)
         banka_komisyonu 30 → ortak (FOB payı): MONİTÖR 30×1.000/1.500 = 20, KASA kalan 10
         MONİTÖR masraf = 120+20+75 = 215 → %21,5 → M1 final 100×1,215 = 121,50
         KASA    masraf = 10+225     = 235 → %47   → K2 final 25×1,47   = 36,75
       Dosya ortalaması (450/1.500 = %30) KULLANILMAZ."""
    d4 = {"id": 4, "dosya_no": "2026-04", "tarih": "2026-04-01", "durum": "Teslim Alındı",
          "masraflar": {"navlun": 300, "gv": 120, "banka_komisyonu": 30},
          "grup_masraf_atama": {"navlun": "__hacim__", "gv": "MONİTÖR"},
          "grup_cbm": {"MONİTÖR": 2, "KASA": 6}}
    kal = [{"id": 41, "dosya_id": 4, "sku": "M1", "adet": 10, "birim_fob": 100, "urun_grubu": "MONİTÖR"},
           {"id": 42, "dosya_id": 4, "sku": "K2", "adet": 20, "birim_fob": 25, "urun_grubu": "KASA"}]
    p = _pacal(monkeypatch, _db(sahte_db, dosyalar=[d4], kalemler=kal))
    assert p["M1"] == pytest.approx(121.5)
    assert p["K2"] == pytest.approx(36.75)


def test_bos_kategori_karttan_dolar_dosyadaki_yazimi_alir(sahte_db, monkeypatch):
    """Kalemin urun_grubu BOŞ; kartın kategorisi küçük harf 'monitör'. Dosyanın masraf ataması
    'MONİTÖR' yazımında → kalem 'MONİTÖR' grubuna girer (noktasız 'MONITÖR' ayrı grup OLMAZ):
         M3 (boş grup → MONİTÖR) 10×100 = 1.000 ; K3 'KASA' 10×100 = 1.000
         gv 200 → MONİTÖR (özel) ; navlun 100 → ortak: MONİTÖR 50, KASA 50
         MONİTÖR %25 → M3 125,00 ; KASA %5 → K3 105,00
       Yazım tutmasaydı gv ortağa düşer, ikisi de %15 → 115 olurdu."""
    d5 = {"id": 5, "dosya_no": "2026-05", "tarih": "2026-06-01", "durum": "Teslim Alındı",
          "masraflar": {"gv": 200, "navlun": 100}, "grup_masraf_atama": {"gv": "MONİTÖR"}}
    kal = [{"id": 51, "dosya_id": 5, "sku": "M3", "adet": 10, "birim_fob": 100, "urun_grubu": ""},
           {"id": 52, "dosya_id": 5, "sku": "K3", "adet": 10, "birim_fob": 100, "urun_grubu": "KASA"}]
    urunler = [{"sku": "M3", "kategori": "monitör", "alis_fiyati": 0},
               {"sku": "K3", "kategori": "Kasa", "alis_fiyati": 0}]
    p = _pacal(monkeypatch, _db(sahte_db, urunler=urunler, dosyalar=[d5], kalemler=kal))
    assert p["M3"] == pytest.approx(125.0)
    assert p["K3"] == pytest.approx(105.0)


def test_bos_veride_bos_harita(sahte_db, monkeypatch):
    """Sınır: hiç dosya/kalem/kart yoksa harita boş (0 maliyet uydurulmaz)."""
    assert _pacal(monkeypatch, sahte_db()) == {}


def test_pacal_bul_kart_yazimiyla_arar(sahte_db, monkeypatch):
    """pacal_bul: kartın yazımıyla ('Fazeon x24f165s') aranınca kanonik anahtar bulunur → 44,50;
    olmayan SKU 0."""
    p = _pacal(monkeypatch, _db(sahte_db))
    from satis.database import pacal_bul
    assert pacal_bul(p, "Fazeon x24f165s") == pytest.approx(44.5)
    assert pacal_bul(p, "YOK-1") == 0.0
