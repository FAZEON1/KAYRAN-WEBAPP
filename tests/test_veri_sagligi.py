# -*- coding: utf-8 -*-
"""Veri sağlığı sayfası (shared/veri_sagligi.py, Ekim 2026).

Dağınık veri kontrolleri tek ekranda; salt okunur. Her kontrol mevcut fonksiyonları kullanır,
"Düzelt" düğmesi düzeltmenin yapıldığı mevcut ekrana götürür. Herkes yetkili olduğu modüllerin
kontrollerini görür, sistem kontrolleri yalnız yöneticiye.
"""
from datetime import date
from pathlib import Path

import shared.veri_sagligi as V
from shared.gezinme import hedef

KOK = Path(__file__).resolve().parent.parent


def test_kategorisiz_markasiz():
    r = V.kategorisiz_markasiz([{"sku": "A", "urun_adi": "a", "kategori": "", "marka": "X"},
                                {"sku": "B", "kategori": "Kasa", "marka": None},
                                {"sku": "C", "kategori": "Kasa", "marka": "Y"},
                                {"sku": "", "kategori": ""}])
    assert [(x["SKU"], x["Eksik"]) for x in r] == [("A", "kategori"), ("B", "marka")]


def test_mukerrer_kartlar():
    r = V.mukerrer_kartlar([{"kanonik": "MIO1", "kartlar": [{"sku": "Mio1", "bizim_stok": 3},
                                                            {"sku": "MIO1", "bizim_stok": "5"}]}])
    assert r == [{"SKU": "MIO1", "Kart sayısı": 2, "Yazımlar": "Mio1 · MIO1", "Toplam stok": 8}]


def test_maliyetsiz_satislar_paçaldan_onarilir_ve_ithalatsiz():
    sat = [{"sku": "A", "adet": 2, "birim_maliyet": 0}, {"sku": "A", "adet": 1, "birim_maliyet": None},
           {"sku": "B", "adet": 5, "birim_maliyet": 0}, {"sku": "C", "adet": 1, "birim_maliyet": 10},
           {"sku": "D", "adet": 0, "birim_maliyet": 0}]
    r = V.maliyetsiz_satislar(sat, {"A": 7.5}, lambda s: s)
    assert [(x["SKU"], x["Satır"], x["Adet"], x["Durum"]) for x in r] == \
        [("A", 2, 3, "paçaldan onarılır"), ("B", 1, 5, "ithalatı yok")]


def test_anormal_tarih():
    sat = [{"sku": "A", "tarih": "2026-10-04"}, {"sku": "B", "tarih": "2026-10-03"},
           {"sku": "C", "tarih": "2023-01-01"}, {"sku": "D", "tarih": ""}]
    r = V.anormal_tarihli_satislar(sat, date(2026, 10, 3))
    assert {x["SKU"]: x["Neden"] for x in r} == {"A": "gelecek tarih", "C": "çok eski", "D": "tarih yok"}


def test_eksi_stok_ve_zararina():
    d = [{"sku": "A", "toplam_stok": -2, "kar_durum": "zarar"}, {"sku": "B", "toplam_stok": 4, "kar_durum": "normal"},
         {"sku": "C", "toplam_stok": "x"}]
    assert [x["SKU"] for x in V.eksi_stok(d)] == ["A"]
    assert [x["SKU"] for x in V.zararina_urunler(d)] == ["A"]


def test_satilabilir_farklari_mevcut_kontrolu_kullanir():
    from kayranpm.database import satilabilir_kontrol
    u = [{"sku": "A", "bizim_stok": 40, "depo_kirilim": {"MERKEZ DEPO": 30, "HAPPY LIFE": 4}},
         {"sku": "B", "bizim_stok": 34, "depo_kirilim": {"MERKEZ DEPO": 30, "HAPPY LIFE": 4}},
         {"sku": "C", "bizim_stok": 5, "depo_kirilim": {}}]
    r = V.satilabilir_farklari(u, satilabilir_kontrol)
    assert [(x["SKU"], x["Kırılımdan"], x["Kayıtlı"]) for x in r] == [("A", 34, 40)]


def test_eslesmeyen_rapor_kodlari():
    rows = [{"sku": "HB1", "urun_adi": "x", "firma": "HB"}, {"sku": "HB1", "firma": "VATAN"},
            {"sku": "OK", "firma": "HB"}, {"sku": "IKI", "firma": "HB"}]
    meta = {"HB1": {"kart_kaynak": ""}, "OK": {"kart_kaynak": "sku"}, "IKI": {"kart_kaynak": "belirsiz"}}
    r = V.eslesmeyen_rapor_kodlari(rows, meta)
    assert [(x["Rapor kodu"], x["Firma"], x["Durum"]) for x in r] == \
        [("HB1", "HB, VATAN", "kart yok"), ("IKI", "HB", "birden çok aday")]


def test_iade_ve_teslim():
    assert [x["SKU"] for x in V.iadesi_satisini_asan([{"sku": "A", "net_adet": -2}, {"sku": "B", "net_adet": 0}])] == ["A"]
    assert V.teslim_bekleyen([{"dosya_no": "D1", "teslim_deposu": "MERKEZ DEPO", "kalem_sayisi": 2,
                               "toplam_adet": 10}]) == [{"Dosya": "D1", "Teslim deposu": "MERKEZ DEPO", "Kalem": 2,
                                                         "Adet": 10}]


def test_son_gunler():
    k = [{"zaman": "2026-10-01T10:00"}, {"zaman": "2026-09-20T10:00"}]
    assert V.son_gunler(k, "zaman", "2026-10-03") == [k[0]]


# ── Görünürlük ve bağlantılar ───────────────────────────────────────
def test_herkes_kendi_modulunu_yonetici_hepsini_gorur():
    sat = {k[0] for k in V.gorunur_kontroller({"satis": True}, False)}
    assert sat == {"maliyetsiz", "tarih", "iade"}
    assert {k[0] for k in V.gorunur_kontroller({}, True)} == {k[0] for k in V.KONTROLLER}
    assert "sistem" not in {k[0] for k in V.gorunur_kontroller({m: True for m in ("satis", "kayranpm", "depo",
                                                                                   "ithalat")}, False)}


def test_her_duzelt_hedefi_gecerli_sayfa():
    for k in V.KONTROLLER:
        if k[4]:
            assert hedef(k[4][0]), (k[0], k[4][0])


def test_salt_okunur_kayit_fonksiyonu_cagirmaz():
    src = (KOK / "shared" / "veri_sagligi.py").read_text(encoding="utf-8")
    for yaz in ("mukerrer_sku_birlestir", "teslim_stok_isle", "satis_maliyet_tazele_uygula", ".insert(",
                ".update(", ".delete(", ".upsert("):
        assert yaz not in src, yaz


def test_sayfa_kayitli():
    from shared.gezinme import SISTEM
    assert any(x[0] == "veri_sagligi" for x in SISTEM)
    a = (KOK / "app.py").read_text(encoding="utf-8")
    assert 'args=("veri_sagligi",)' in a and 'elif aktif == "veri_sagligi":' in a
