# -*- coding: utf-8 -*-
"""Canlı paçal maliyet (Ekim 2026, kullanıcı kararı A): paçal maliyet (bütün partilerin ortalaması)
kalır; yanında yalnız ELDEKİ malın (bizim + müşteri stoğu) maliyeti gösterilir. Eldeki adetler en yeni
TESLİM ALINMIŞ partiden geriye dağıtılır; yoldaki / antrepodaki partiler girmez. Yalnız gösterim."""
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


def _p(giris, adet, final, belge="", did=None):
    return {"giris": giris, "adet": adet, "final": final, "belge": belge, "dosya_id": did}


def test_kullanici_ornegi_yeni_parti_ve_kalan_eski():
    """300 adet elde: 200'ü yeni partiden ($40), 100'ü önceki partiden ($50) → $43,33.
    En eski parti ($60) tamamen satılmış sayılır, ortalamaya girmez."""
    from kayranpm.canli_pacal import hesapla
    r = hesapla([_p("2026-01-10", 500, 60, "ESKI"), _p("2026-05-01", 400, 50, "ORTA"),
                 _p("2026-09-01", 200, 40, "YENI")], 300, yedek=52)
    assert r["pacal"] == pytest.approx(43.3333, abs=1e-4) and r["durum"] == "tamam" and r["kayitsiz"] == 0
    assert [(k["belge"], k["kalan"], k["final"]) for k in r["kalanlar"]] == [("YENI", 200, 40), ("ORTA", 100, 50)]


def test_stok_tek_partiye_sigarsa_o_partinin_maliyeti():
    from kayranpm.canli_pacal import hesapla
    assert hesapla([_p("2026-01-10", 500, 60), _p("2026-09-01", 200, 40)], 150)["pacal"] == 40.0


def test_stok_kayitlardan_fazlaysa_fazlasi_paçalla():
    from kayranpm.canli_pacal import hesapla
    r = hesapla([_p("2026-09-01", 100, 40)], 150, yedek=52)
    assert r["kayitsiz"] == 50 and r["pacal"] == pytest.approx((100 * 40 + 50 * 52) / 150)


def test_stok_yoksa_son_partinin_maliyeti():
    from kayranpm.canli_pacal import hesapla
    r = hesapla([_p("2026-01-10", 500, 60), _p("2026-09-01", 100, 40, did=1), _p("2026-09-01", 10, 0, did=1)], 0)
    assert r["durum"] == "stok_yok" and r["pacal"] == pytest.approx(4000 / 110, abs=1e-4)   # bedelsiz adet ortalamaya girer


def test_parti_yoksa_paçal():
    from kayranpm.canli_pacal import hesapla
    r = hesapla([], 20, yedek=12.5)
    assert r["durum"] == "parti_yok" and r["pacal"] == 12.5


def test_ayni_gun_partileri_sirasi_kararli():
    from kayranpm.canli_pacal import hesapla
    a = hesapla([_p("2026-09-01", 10, 30, did=2), _p("2026-09-01", 10, 20, did=1)], 10)
    b = hesapla([_p("2026-09-01", 10, 20, did=1), _p("2026-09-01", 10, 30, did=2)], 10)
    assert a["pacal"] == b["pacal"]


def test_teslim_partileri_yoldaki_girmez_ve_sku_yazimi_birlesir():
    from kayranpm.canli_pacal import teslim_partileri
    from shared.utils import sku_anahtar
    p = teslim_partileri([
        {"sku": "X24F165S", "adet": 100, "final": 40, "giris": "2026-06-19", "tarih": "2026-01-01", "yolda": False},
        {"sku": "Fazeon X24F165S", "adet": 50, "final": 45, "tarih": "2026-02-01", "yolda": False},   # giris yoksa tarih
        {"sku": "X24F165S", "adet": 900, "final": 30, "giris": "2026-10-01", "yolda": True},          # antrepoda
    ])
    assert [(x["giris"], x["adet"]) for x in p[sku_anahtar("X24F165S")]] == [("2026-06-19", 100), ("2026-02-01", 50)]


def test_eldeki_stok_bizim_arti_musteri():
    from kayranpm.canli_pacal import eldeki_stoklar
    from shared.utils import sku_anahtar
    k = sku_anahtar("X24F165S")
    s = eldeki_stoklar([{"sku": "X24F165S", "bizim_stok": 90}, {"sku": "Fazeon X24F165S", "bizim_stok": 10},
                        {"sku": "K100", "bizim_stok": -3}],
                       {"VATAN": {k: 40}, "ITOPYA": {k: 15, sku_anahtar("K100"): 5}})
    assert s[k] == (100, 55) and s[sku_anahtar("K100")] == (0, 5)


def test_harita_hesapla_ucundan():
    from kayranpm.canli_pacal import harita_hesapla
    from shared.utils import sku_anahtar
    k = sku_anahtar("A1")
    h = harita_hesapla(
        [{"sku": "A1", "adet": 500, "final": 50, "giris": "2026-01-01", "belge": "ESKI"},
         {"sku": "A1", "adet": 200, "final": 40, "giris": "2026-09-01", "belge": "YENI"},
         {"sku": "A1", "adet": 1000, "final": 10, "giris": "2026-10-01", "yolda": True}],
        [{"sku": "A1", "bizim_stok": 250}], {"VATAN": {k: 50}}, {k: 47.14, sku_anahtar("YI"): 8})
    assert h[k]["pacal"] == pytest.approx((200 * 40 + 100 * 50) / 300, abs=1e-4)
    assert h[k]["bizim"] == 250 and h[k]["musteri"] == 50
    assert h[sku_anahtar("YI")]["durum"] == "parti_yok" and h[sku_anahtar("YI")]["pacal"] == 8


def test_aciklama():
    from kayranpm.canli_pacal import aciklama
    assert aciklama({"durum": "tamam", "stok": 9397, "bizim": 9000, "musteri": 397, "kayitsiz": 0}) == \
        "eldeki 9.397 adet (bizim 9.000 + müşteri 397)"
    assert aciklama({"durum": "stok_yok"}) == "stok yok · son teslim alınan parti"
    assert aciklama(None) == ""


def test_parti_satirlari_giris_ve_belge(monkeypatch):
    import ithalat.database as idb
    monkeypatch.setattr(idb, "get_dosyalar", lambda: [
        {"id": 1, "dosya_no": "GTS1", "tarih": "2025-12-01", "teslim_tarihi": "2026-01-15", "durum": "Teslim Alındı"},
        {"id": 2, "dosya_no": "GTS2", "tarih": "2026-02-01", "durum": "Antrepoda"}])
    monkeypatch.setattr(idb, "get_tum_kalemler", lambda: [
        {"dosya_id": 1, "sku": "A1", "adet": 10, "birim_fob": 5}, {"dosya_id": 2, "sku": "A1", "adet": 3, "birim_fob": 4}])
    fn = getattr(idb._parti_satirlari_hesapla, "__wrapped__", idb._parti_satirlari_hesapla)
    p = {r["dosya_id"]: r for r in fn()}
    assert (p[1]["giris"], p[1]["belge"], p[1]["yolda"]) == ("2026-01-15", "GTS1", False)
    assert (p[2]["giris"], p[2]["yolda"]) == ("2026-02-01", True)       # teslim tarihi yoksa belge tarihi


def test_ekranlar_ve_rapor():
    m = _oku("kayranpm/main.py")
    assert '"label": "Canlı paçal maliyet"' in m and '"Canlı paçal ($)"' in m
    sk = _oku("kayranpm/stok_karti.py")
    assert '_kart("Canlı Paçal"' in sk and "Eldeki stoğun partileri" in sk
    assert '("Canlı Paçal Maliyet ($)", "Canlı Paçal ($)")' in _oku("kayranpm/rapor.py")
    from kayranpm.urun_hesap import urun_satiri
    assert urun_satiri({"sku": "A", "canli_pacal": 43.33})["Canlı Paçal ($)"] == 43.33
    assert urun_satiri({"sku": "A"})["Canlı Paçal ($)"] is None
    from shared.veri_surumu import BAGIMLILAR
    assert ("kayranpm.canli_pacal", "harita") in BAGIMLILAR


def test_paçal_degismez():
    """Canlı paçal yalnız gösterim: satışa yazılan maliyetin tek kapısı get_pacal_map ona bakmaz."""
    s = _oku("satis/database.py")
    g = s[s.index("def get_pacal_map("):s.index("def pacal_bul(")]
    assert "canli" not in g
