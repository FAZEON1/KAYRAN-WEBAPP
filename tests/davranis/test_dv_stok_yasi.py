# -*- coding: utf-8 -*-
"""Davranış kilidi — kayranpm.stok_yasi (FIFO stok yaşı, depoya giriş tarihinden).

Kural: en eski parti önce satılır, elde kalan stok EN YENİ partilerdendir. Parti tarihi = teslim
tarihi (yoksa belge tarihi); yalnız 'Teslim Alındı' dosyalar; aynı ürünün SKU yazımları birleşik.
Bugün sabit: 14.10.2026.

Gün hesapları (elle):
  24.09.2026 → 14.10 = 6 + 14            = 20 gün
  01.07.2026 → 14.10 = 30 + 31 + 30 + 14 = 105 gün
  01.02.2026 → 14.10 = 27+31+30+31+30+31+31+30+14 = 255 gün
  15.08.2026 → 14.10 = 16 + 30 + 14      = 60 gün
  01.10.2026 → 14.10                     = 13 gün
"""
from datetime import date

import pytest

from kayranpm import stok_yasi as sy

BUGUN = date(2026, 10, 14)

DOSYALAR = [
    {"id": 1, "dosya_no": "IT-1", "tarih": "2026-01-10", "teslim_tarihi": "2026-02-01", "durum": "Teslim Alındı",
     "alim_turu": "ithalat", "masraflar": {}},
    {"id": 2, "dosya_no": "YI-2", "tarih": "2026-07-01", "teslim_tarihi": None, "durum": "Teslim Alındı",
     "alim_turu": "yurtici", "masraflar": {}},
    {"id": 3, "dosya_no": "IT-3", "tarih": "2026-09-01", "teslim_tarihi": "2026-09-24", "durum": "Teslim Alındı",
     "masraflar": {}},
    {"id": 4, "dosya_no": "IT-4", "tarih": "2026-10-01", "durum": "Yolda", "masraflar": {}},
]
KALEMLER = [
    {"id": 11, "dosya_id": 1, "sku": "X24", "adet": 100, "birim_fob": 1, "urun_grubu": "A"},
    {"id": 12, "dosya_id": 1, "sku": "Y1", "adet": 10, "birim_fob": 1, "urun_grubu": "A"},
    {"id": 21, "dosya_id": 2, "sku": "Fazeon X24", "adet": 30, "birim_fob": 1, "urun_grubu": "A"},
    {"id": 31, "dosya_id": 3, "sku": "x24", "adet": 20, "birim_fob": 1, "urun_grubu": "A"},
    {"id": 41, "dosya_id": 4, "sku": "X24", "adet": 500, "birim_fob": 1, "urun_grubu": "A"},
]
URUNLER = [
    {"sku": "X24", "urun_adi": "Monitör", "kategori": "Monitör", "marka": "", "bizim_stok": 45},
    {"sku": "Fazeon X24", "urun_adi": "Monitör eski kart", "kategori": "Monitör", "marka": "", "bizim_stok": 5},
    {"sku": "Y1", "urun_adi": "Kasa", "kategori": "KASA", "marka": "", "bizim_stok": 50},
    {"sku": "YP1", "urun_adi": "Vida", "kategori": "Yedek Parça", "marka": "", "bizim_stok": 5},
    {"sku": "Z0", "urun_adi": "Bitti", "kategori": "KASA", "marka": "", "bizim_stok": 0},
]


# ── Saf ───────────────────────────────────────────────────────────────
def test_fifo_kalan_en_yeniler_elde_kalir():
    """Partiler 01.02 (100), 01.07 (30), 24.09 (20); stok 45 → 24.09'dan 20, 01.07'den 25.
       Sonuç ESKİ→YENİ sırada; kapsanmayan 0. Geçersiz partiler (adet 0, tarihsiz) atlanır."""
    p = [{"tarih": "2026-02-01", "adet": 100}, {"tarih": "2026-09-24", "adet": 20},
         {"tarih": "2026-07-01", "adet": 30}, {"tarih": "", "adet": 9}, {"tarih": "2026-10-01", "adet": 0}]
    kal, kaps = sy.fifo_kalan(p, 45)
    assert [(k["tarih"], k["kalan"]) for k in kal] == [("2026-07-01", 25.0), ("2026-09-24", 20.0)]
    assert kaps == 0.0


def test_fifo_sinirlar_kapsanmayan_ve_sifir_stok():
    """Stok partilerden fazla: 50 stok, tek parti 10 → kapsanmayan 40 (yaş uydurulmaz).
       Stok 0 / eksi → boş. Aynı tarihli iki partide sonra gelen önce elde kalır (kararlı sıra)."""
    assert sy.fifo_kalan([{"tarih": "2026-02-01", "adet": 10}], 50) == ([{"tarih": "2026-02-01", "adet": 10,
                                                                          "kalan": 10.0}], 40.0)
    assert sy.fifo_kalan([{"tarih": "2026-02-01", "adet": 10}], -3) == ([], 0.0)
    kal, _ = sy.fifo_kalan([{"tarih": "2026-05-05", "adet": 5, "b": "ilk"},
                            {"tarih": "2026-05-05", "adet": 5, "b": "ikinci"}], 6)
    assert [(k["b"], k["kalan"]) for k in kal] == [("ilk", 1.0), ("ikinci", 5.0)]


def test_yas_ozeti_agirlikli_ortalama_ve_gruplar():
    """Kalan 25 @105 gün + 20 @20 gün, kapsanmayan 5:
       ort = (25×105 + 20×20) / 45 = 3.025 / 45 = 67,22 gün ; en eski 105 (01.07), en yeni 20
       gruplar: 0–30 → 20 ; 91–180 → 25 ; 'Giriş kaydı yok' → 5 ; stok 50, kapsanan 45."""
    o = sy.yas_ozeti([{"tarih": "2026-07-01", "kalan": 25}, {"tarih": "2026-09-24", "kalan": 20}], 5, BUGUN)
    assert o["ort_gun"] == pytest.approx(3025 / 45)
    assert (o["stok"], o["kapsanan"], o["kapsanmayan"]) == (50, 45, 5)
    assert (o["en_eski_gun"], o["en_eski_tarih"], o["en_yeni_gun"]) == (105, "2026-07-01", 20)
    assert o["gruplar"] == {"0–30 gün": 20, "31–60 gün": 0, "61–90 gün": 0, "91–180 gün": 25,
                            "180+ gün": 0, "Giriş kaydı yok": 5}
    # grup sınırları: 30 → 0–30, 31 → 31–60, 180 → 91–180, 181 → 180+
    assert [sy.grup_adi(g) for g in (0, 30, 31, 90, 91, 180, 181)] == [
        "0–30 gün", "0–30 gün", "31–60 gün", "61–90 gün", "91–180 gün", "91–180 gün", "180+ gün"]


def test_musteri_partileri_firma_eslesmesi():
    """VATAN'a satışlar: 15.08 (10), 01.10 (5); müşteri stoğu 8 → 01.10'dan 5 (13 gün), 15.08'den 3 (60 gün)
       ort = (5×13 + 3×60) / 8 = 245 / 8 = 30,625 ; 0–30: 5, 31–60: 3.
       Kanal adı Türkçe/boşluk farkıyla ('vatan  ') eşleşir; raporu olmayan müşteri (EERA) atlanır."""
    from shared.utils import normalize_tr, sku_anahtar
    bul = sy.firma_cozucu(["VATAN"], lambda k: "VATAN BİLGİSAYAR A.Ş.", normalize_tr)
    mp = sy.musteri_partileri([
        {"tarih": "2026-08-15", "kanal": "vatan  ", "sku": "Fazeon X24", "adet": 10, "siparis_no": "S1"},
        {"tarih": "2026-10-01", "kanal": "VATAN BİLGİSAYAR A.Ş.", "sku": "X24", "adet": 5},
        {"tarih": "2026-10-02", "kanal": "EERA", "sku": "X24", "adet": 7},
    ], bul, sku_anahtar)
    assert set(mp) == {"VATAN"} and len(mp["VATAN"]["X24"]) == 2
    oz, _ = sy.urun_yasi(8, mp["VATAN"]["X24"], BUGUN)
    assert oz["ort_gun"] == pytest.approx(30.625)
    assert (oz["gruplar"]["0–30 gün"], oz["gruplar"]["31–60 gün"]) == (5, 3)


# ── hesapla (uçtan uca, sahte veritabanı) ─────────────────────────────
@pytest.fixture
def hesap(sahte_db, monkeypatch):
    import ithalat.database as idb
    import kayranpm.database as pdb
    from shared.utils import sku_anahtar
    db = sahte_db(ithalat_dosyalari=DOSYALAR, ithalat_kalemleri=KALEMLER, urunler=URUNLER)
    monkeypatch.setattr(idb, "_get_client", lambda: db)
    monkeypatch.setattr(pdb, "get_client", lambda: db)
    monkeypatch.setattr(sy, "_bugun", lambda: BUGUN)
    monkeypatch.setattr(sy, "ayar_oku", lambda: sy.ayar_birlestir({}))
    bul = sy.firma_cozucu(["VATAN"], lambda k: k, lambda s: str(s or "").upper())
    mp = sy.musteri_partileri([{"tarih": "2026-08-15", "kanal": "VATAN", "sku": "X24", "adet": 10},
                               {"tarih": "2026-10-01", "kanal": "VATAN", "sku": "X24", "adet": 5}], bul, sku_anahtar)
    monkeypatch.setattr(sy, "_musteri_oku", lambda: ({"VATAN": {"X24": 8, "YP1": 3, "Y1": 0}}, mp))
    return sy.hesapla()


def test_hesapla_bizim_stok_fifo(hesap):
    """X24: iki kart (X24 45 + 'Fazeon X24' 5) → stok 50. Partiler (yazımlar birleşik, yoldaki D4 hariç):
         24.09 x24 20 → 20 @20 gün ; 01.07 'Fazeon X24' 30 (teslim tarihi yok → belge tarihi) → 30 @105
         ort = (20×20 + 30×105) / 50 = 3.550 / 50 = 71,0 ; 0–30: 20, 91–180: 30 ; kapsanmayan 0
       Y1: stok 50, tek parti 01.02 10 adet → 10 @255 gün (180+), kapsanmayan 40, ort 255.
       YP1 'Yedek Parça' → hariç ; Z0 stok 0 → listede yok."""
    b = hesap["bizim"]
    assert set(b) == {"X24", "Y1"}
    ox, kx, ux = b["X24"]
    assert ux["sku"] == "X24"                                   # ilk kart
    assert (ox["stok"], ox["kapsanmayan"]) == (50, 0)
    assert ox["ort_gun"] == pytest.approx(71.0)
    assert [(k["tarih"], k["kalan"], k["tur"]) for k in kx] == [("2026-07-01", 30.0, "yurtici"),
                                                              ("2026-09-24", 20.0, "ithalat")]
    oy = b["Y1"][0]
    assert (oy["stok"], oy["kapsanan"], oy["kapsanmayan"], oy["ort_gun"]) == (50, 10, 40, 255)
    assert oy["gruplar"]["180+ gün"] == 10 and oy["gruplar"]["Giriş kaydı yok"] == 40


def test_hesapla_toplam_ve_musteri(hesap):
    """Toplam: stok 100, kapsanan 60, kapsanmayan 40 ; ort = (71×50 + 255×10) / 60 = 6.100 / 60 = 101,67.
       Müşteri VATAN X24 8 → ort 30,625 ; YP1 (hariç kategori) ve stoğu 0 olan Y1 yok."""
    t = sy.toplam_ozet([v[0] for v in hesap["bizim"].values()])
    assert (t["stok"], t["kapsanan"], t["kapsanmayan"]) == (100, 60, 40)
    assert t["ort_gun"] == pytest.approx(6100 / 60)
    assert set(hesap["musteri"]["VATAN"]) == {"X24"}
    assert hesap["musteri"]["VATAN"]["X24"][0]["ort_gun"] == pytest.approx(30.625)


def test_yasli_satirlar_deger_pacalla(hesap):
    """Eşik 90 gün, paçal X24 44,5 / Y1 7:
       X24: 90+ gün 30 adet (105 gün) → değer 30 × 44,5 = 1.335 ; 180+ 0
       Y1 : 90+ gün 10 adet (255 gün) → 70 ; 180+ 10. Sıra: değer azalan."""
    r = sy.yasli_satirlar(hesap["bizim"], {"X24": 44.5, "Y1": 7}, BUGUN, 90)
    assert [(x["SKU"], x["90+ gün adet"], x["180+ gün adet"], x["Yaşlı değer ($)"], x["Toplam stok"])
            for x in r] == [("X24", 30.0, 0, 1335.0, 50), ("Y1", 10.0, 10.0, 70.0, 50)]
