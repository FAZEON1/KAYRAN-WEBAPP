# -*- coding: utf-8 -*-
"""Stok toplamı tek tanım (Ekim 2026).

Sorun: Tüm Ürünler detayında "Stok dağılımı" ile "Toplam Stok" farklıydı
(625 / 614). Kök neden: kanal stoğu iki kuralla okunuyordu —
  • pano: her kanalın SON raporu (doğru; rapordan düşen ürün = 0)
  • liste + stok kartı: her ürünün EN SON GÖRÜLDÜĞÜ satır (eski haftanın adedi kalıyordu)
Karar: "toplam stok" = bizim satılabilir depolar (Merkez + Happy Life).
Kanaldaki stok ayrı; sipariş hesabı "kanal dahil" (zincir_stok) kullanır.
"""
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent

URUNLER = [
    {"sku": "A", "urun_adi": "Kasa", "bizim_stok": 600, "trendyol_stok": 0,
     "depo_kirilim": {"MERKEZ DEPO": 590, "HAPPY LIFE": 10, "IADE DEPO": 4}},
    {"sku": "B", "urun_adi": "Fan", "bizim_stok": 20, "trendyol_stok": 0, "depo_kirilim": {}},
]
FIRMA_STOK = [
    # Vatan'ın eski raporunda A var; son raporunda A yok (satılıp bitti)
    {"firma": "VATAN", "sku": "A", "stok_miktari": 11, "haftalik_satis": 3, "yukleme_tarihi": "2026-09-20"},
    {"firma": "VATAN", "sku": "B", "stok_miktari": 5, "haftalik_satis": 1, "yukleme_tarihi": "2026-09-27"},
    {"firma": "ITOPYA", "sku": "A", "stok_miktari": 14, "haftalik_satis": 2, "yukleme_tarihi": "2026-09-27"},
]


class _Yanit:
    def __init__(self, data):
        self.data = data


class _Sorgu:
    def __init__(self, satirlar):
        self._s = [dict(r) for r in satirlar]
        self._lim = None
        self._sira = None

    def select(self, *a, **k):
        return self

    def eq(self, kol, deger):
        self._s = [r for r in self._s if r.get(kol) == deger]
        return self

    def order(self, kol, desc=False):
        self._sira = (kol, desc)
        return self

    def limit(self, n):
        self._lim = n
        return self

    def range(self, a, b):
        return self

    def execute(self):
        s = self._s
        if self._sira:
            s = sorted(s, key=lambda r: str(r.get(self._sira[0]) or ""), reverse=self._sira[1])
        if self._lim is not None:
            s = s[:self._lim]
        return _Yanit(s)


class _Istemci:
    def __init__(self, tablolar):
        self._t = tablolar

    def table(self, ad):
        return _Sorgu(self._t.get(ad, []))


@pytest.fixture
def sahte_db(monkeypatch):
    from kayranpm import analitik, database
    ist = _Istemci({"urunler": URUNLER, "firma_stok": FIRMA_STOK})
    monkeypatch.setattr(database, "get_client", lambda: ist)
    monkeypatch.setattr(analitik, "get_client", lambda: ist)
    monkeypatch.setattr(analitik, "get_all_dashboard_data", database._dashboard_ham)
    monkeypatch.setattr(analitik, "_ithalat_maliyet_map", lambda: {})
    monkeypatch.setattr(analitik, "_ithalat_partiler_map", lambda: {})
    return analitik


def _bul(rows, sku):
    return next(r for r in rows if r["sku"] == sku)


# ── Kanal kuralı ────────────────────────────────────────────────────
def test_kanal_son_raporu_esas_alinir():
    from kayranpm.stok_hesap import kanal_stoklari
    k = kanal_stoklari(FIRMA_STOK)
    assert k["VATAN"].get("A", 0) == 0          # son raporda yok → 0
    assert k["VATAN"]["B"] == 5
    assert k["ITOPYA"]["A"] == 14


def test_kanal_tek_urun_satirlari_genel_son_tarihle():
    """Stok kartı yalnız bir ürünün satırlarını okur; kanalın son rapor
    tarihi dışarıdan verilmezse eski satır son sanılır."""
    from kayranpm.stok_hesap import kanal_stoklari
    a_satirlari = [r for r in FIRMA_STOK if r["sku"] == "A"]
    k = kanal_stoklari(a_satirlari, son_tarih={"VATAN": "2026-09-27", "ITOPYA": "2026-09-27"})
    assert sum(v.get("A", 0) for v in k.values()) == 14


def test_stok_ozeti_tanimlar():
    from kayranpm.stok_hesap import stok_ozeti
    o = stok_ozeti(600, {"ITOPYA": 14, "VATAN": 0})
    assert o == {"toplam_stok": 600, "kanal_stok": 14, "zincir_stok": 614}


# ── Liste ve pano aynı sayıyı verir ─────────────────────────────────
def test_liste_ve_pano_ayni_toplam(sahte_db):
    liste = _bul(sahte_db.tum_urunler_listesi(), "A")
    pano = _bul(sahte_db.dashboard_hesapla(), "A")
    assert liste["toplam_stok"] == pano["toplam_stok"] == 600   # kanal yok, iade depo yok


def test_liste_eski_kanal_raporunu_saymaz(sahte_db):
    liste = _bul(sahte_db.tum_urunler_listesi(), "A")
    assert liste["firma_stoklari"]["VATAN"] == 0
    assert liste["kanal_stok"] == 14 and liste["zincir_stok"] == 614


def test_siparis_hesabi_kanal_dahil(sahte_db):
    pano = _bul(sahte_db.dashboard_hesapla(), "A")
    assert pano["zincir_stok"] == 614 and pano["kanal_stok"] == 14


# ── Genel Bakış: toplam bizim stok, kapsama kanal dahil ─────────────
def test_genel_bakis_kpi():
    from kayranpm.genel_hesap import kpi
    rows = [{"toplam_stok": 600, "zincir_stok": 614, "bizim_stok": 600}]
    k = kpi(rows, [("h1", 10), ("h2", 10)], None)
    assert k["stok"] == 600 and k["kanal_dahil"] == 614
    assert k["kapsama_hafta"] == 61.4


# ── Liste satırı ────────────────────────────────────────────────────
def test_urun_satiri_kanal_dahil_sutunu():
    from kayranpm.urun_hesap import urun_satiri
    r = urun_satiri({"sku": "A", "bizim_stok": 600, "toplam_stok": 600, "zincir_stok": 614,
                     "firma_stoklari": {"ITOPYA": 14}})
    assert r["G5F Depo"] == 600 and r["Kanal dahil"] == 614 and "Toplam" not in r


# ── Kaynak denetimleri (arayüz) ─────────────────────────────────────
def test_stok_karti_ortak_kurali_kullanir():
    src = (KOK / "kayranpm" / "stok_karti.py").read_text(encoding="utf-8")
    assert "kanal_stoklari(" in src and "firma_son_tarihleri(" in src
    assert "toplam_stok = _g5f_toplam + _firma_toplam" not in src   # tüm depolar + kanal
    assert "stok_degeri = toplam_stok * pacal_final" in src        # toplam artık bizim satılabilir


def test_detay_yanlis_siparis_notu_yok():
    src = (KOK / "kayranpm" / "main.py").read_text(encoding="utf-8")
    assert "Sipariş önerisinde kullanılan stok" not in src


# ── SKU yazım farkı (Ekim 2026) ─────────────────────────────────────
# Müşteri raporu yüklenirken SKU sku_anahtar ile BÜYÜK harfe çevrilir ('MIO MIVUE J30');
# Mio kartları karışık harfle kayıtlı ('Mio MiVue J30'). Liste, pano ve stok kartı kanal
# stoğunu ham SKU ile aradığı için VATAN'daki Mio stoğu 0 görünüyordu (canlıda 10 ürün, 172 adet).
URUNLER_MIO = [{"sku": "Mio MiVue J30", "urun_adi": "Mio J30", "bizim_stok": 10, "trendyol_stok": 0,
                "depo_kirilim": {"MERKEZ DEPO": 10}}]
FIRMA_STOK_MIO = [
    {"firma": "VATAN", "sku": "MIO MIVUE J30", "stok_miktari": 40, "haftalik_satis": 2, "yukleme_tarihi": "2026-09-20"},
    {"firma": "VATAN", "sku": "MIO MIVUE J30", "stok_miktari": 45, "haftalik_satis": 3, "yukleme_tarihi": "2026-09-27"},
]


@pytest.fixture
def sahte_db_mio(monkeypatch):
    from kayranpm import analitik, database
    ist = _Istemci({"urunler": URUNLER_MIO, "firma_stok": FIRMA_STOK_MIO})
    monkeypatch.setattr(database, "get_client", lambda: ist)
    monkeypatch.setattr(analitik, "get_client", lambda: ist)
    monkeypatch.setattr(analitik, "get_all_dashboard_data", database._dashboard_ham)
    monkeypatch.setattr(analitik, "_ithalat_maliyet_map", lambda: {})
    monkeypatch.setattr(analitik, "_ithalat_partiler_map", lambda: {})
    return analitik


def test_liste_kanal_stogu_sku_yazimindan_bagimsiz(sahte_db_mio):
    r = _bul(sahte_db_mio.tum_urunler_listesi(), "Mio MiVue J30")
    assert r["firma_stoklari"]["VATAN"] == 45
    assert r["kanal_stok"] == 45 and r["zincir_stok"] == 55


def test_pano_kanal_stogu_ve_satis_gecmisi_sku_yazimindan_bagimsiz(sahte_db_mio):
    r = _bul(sahte_db_mio.dashboard_hesapla(), "Mio MiVue J30")
    assert r["kanal_stok"] == 45 and r["zincir_stok"] == 55
    assert [h["satis"] for h in r["gecmis_satislar"]] == [2, 3]


def test_stok_karti_firma_stok_satirlari_sku_yazimindan_bagimsiz(monkeypatch):
    from kayranpm import database

    class _S(_Sorgu):
        def ilike(self, kol, desen):
            import re
            rx = "^" + re.escape(desen).replace("%", ".*").replace("_", ".") + "$"
            self._s = [r for r in self._s if re.match(rx, str(r.get(kol) or ""), re.I)]
            return self

    diger = [{"firma": "VATAN", "sku": "MIO MIVUE J300", "stok_miktari": 9, "yukleme_tarihi": "2026-09-27"}]
    monkeypatch.setattr(database, "get_client",
                        lambda: type("I", (), {"table": lambda s, ad: _S(FIRMA_STOK_MIO + diger)})())
    rows = database.firma_stok_satirlari("Mio MiVue J30")
    assert sorted(r["stok_miktari"] for r in rows) == [40, 45]
