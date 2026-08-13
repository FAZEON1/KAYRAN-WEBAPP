# -*- coding: utf-8 -*-
"""
Maliyet önceliği ve kâr hesabı testleri — satis/database.py
  get_pacal_map : ithalat paçalı > yurt içi alis_fiyati önceliği
  satir_kar     : tek satır kâr formülü
  ozet_hesapla  : toplam = satır bazlı kâr toplamı (net ciro − COGS DEĞİL)

get_pacal_map DB'ye gider; iki kaynağı (ithalat özeti + ürün kartları)
monkeypatch ile sahtelenir. satir_kar / ozet_hesapla zaten saf.
"""

import pytest

import ithalat.database as idb
import satis.database as sdb


# ═══════════════════════════════════════════════════════════
#  get_pacal_map — maliyet önceliği
# ═══════════════════════════════════════════════════════════

def _pacal_kur(monkeypatch, ithalat_ozet, urun_kartlari):
    """İki maliyet kaynağını sahtele.
    ithalat_ozet : {sku: pacal_final}
    urun_kartlari: [{sku, alis_fiyati}, ...]"""
    monkeypatch.setattr(
        idb, "get_sku_maliyet_ozet",
        lambda: {k: {"pacal_final": v} for k, v in ithalat_ozet.items()})
    monkeypatch.setattr(sdb, "_urunler_hepsi", lambda secim: urun_kartlari)


def test_pacal_ithalat_yurticinden_ustundur(monkeypatch):
    """Ürünün ithalatı VARSA landed maliyet kazanır; alis_fiyati ezemez."""
    _pacal_kur(monkeypatch,
               {"X1": 10.0},
               [{"sku": "X1", "alis_fiyati": 99.0}])
    assert sdb.get_pacal_map() == {"X1": 10.0}


def test_pacal_sifirsa_yurtici_devreye_girer(monkeypatch):
    """Paçal 0 (ör. masrafsız/bozuk dosya) → alis_fiyati boşluğu doldurmalı."""
    _pacal_kur(monkeypatch,
               {"X1": 0.0},
               [{"sku": "X1", "alis_fiyati": 7.5}])
    assert sdb.get_pacal_map() == {"X1": 7.5}


def test_pacal_ithalati_olmayan_urun_yurticinden_gelir(monkeypatch):
    """Kaspersky / mouse pad senaryosu: ithalat dosyası hiç yok."""
    _pacal_kur(monkeypatch,
               {},
               [{"sku": "KSP1", "alis_fiyati": 12.0}])
    assert sdb.get_pacal_map() == {"KSP1": 12.0}


def test_pacal_alis_fiyati_sifirsa_maliyet_sifir_kalir(monkeypatch):
    """İki kaynak da boşsa maliyet 0 kalmalı (maliyetsiz sayacına düşer)."""
    _pacal_kur(monkeypatch,
               {"X1": 0.0},
               [{"sku": "X1", "alis_fiyati": 0}])
    assert sdb.get_pacal_map() == {"X1": 0.0}


def test_pacal_anahtarlar_sku_anahtar_ile_normalize(monkeypatch):
    """'Fazeon X24F165S' ithalat kaydı 'X24F165S' anahtarına inmeli —
    yoksa satıştaki normalize SKU maliyeti bulamaz, kâr şişer."""
    _pacal_kur(monkeypatch,
               {"Fazeon X24F165S": 20.0},
               [])
    assert sdb.get_pacal_map() == {"X24F165S": 20.0}


def test_pacal_oneksiz_kayit_onekliye_ustundur(monkeypatch):
    """Aynı anahtara inen iki kayıt: İLK gelen (öneksiz/gerçek) korunmalı."""
    # dict sırası: öneksiz önce gelirse önekli onu ezmemeli
    _pacal_kur(monkeypatch,
               {"X24F165S": 20.0, "Fazeon X24F165S": 5.0},
               [])
    assert sdb.get_pacal_map() == {"X24F165S": 20.0}


def test_pacal_yurtici_anahtari_da_normalize(monkeypatch):
    """Ürün kartındaki SKU önekli yazılmışsa bile anahtar normalize olmalı."""
    _pacal_kur(monkeypatch,
               {},
               [{"sku": "fazeon abc123", "alis_fiyati": 3.0}])
    assert sdb.get_pacal_map() == {"ABC123": 3.0}


# ═══════════════════════════════════════════════════════════
#  satir_kar — tek satır formülü
# ═══════════════════════════════════════════════════════════

def _satis(adet=1, satis=0.0, maliyet=0.0, firma_destek=0.0, ek_destek=0.0):
    return {"adet": adet, "birim_satis": satis, "birim_maliyet": maliyet,
            "birim_firma_destek": firma_destek, "birim_ek_destek": ek_destek}


def test_satir_kar_dokumdaki_ornek():
    """Docstring'deki örnek: 1 − 5,10/(12−3) = %43,3."""
    k = sdb.satir_kar(_satis(adet=1, satis=12.0, maliyet=5.10, firma_destek=3.0))
    assert k["ciro"] == 12.0
    assert k["destek"] == 3.0
    assert k["net_satis"] == 9.0
    assert k["net_kar"] == pytest.approx(3.90)
    assert k["marj"] == pytest.approx(43.333, abs=0.01)


def test_satir_kar_destekler_toplanir():
    k = sdb.satir_kar(_satis(adet=2, satis=10.0, maliyet=4.0,
                             firma_destek=1.0, ek_destek=0.5))
    assert k["destek"] == 3.0            # 2 × (1 + 0.5)
    assert k["net_kar"] == 9.0           # 20 − 3 − 8


def test_satir_kar_net_satis_sifirsa_marj_sifir():
    """Bedelsiz/tamamı destekli satırda bölme hatası olmamalı."""
    k = sdb.satir_kar(_satis(adet=1, satis=5.0, maliyet=2.0, firma_destek=5.0))
    assert k["net_satis"] == 0.0
    assert k["marj"] == 0.0


def test_satir_kar_metin_girdiler_sayiya_cevrilir():
    """Excel'den gelen değerler metin olabiliyor."""
    k = sdb.satir_kar({"adet": "2", "birim_satis": "10", "birim_maliyet": "3",
                       "birim_firma_destek": "", "birim_ek_destek": None})
    assert k["ciro"] == 20.0 and k["maliyet"] == 6.0 and k["destek"] == 0.0


# ═══════════════════════════════════════════════════════════
#  ozet_hesapla — toplam, SATIR BAZLI kâr toplamıdır
# ═══════════════════════════════════════════════════════════

SATISLAR = [
    dict(_satis(adet=2, satis=10.0, maliyet=4.0, firma_destek=1.0),
         kanal="VATAN", sku="A1", urun_adi="Ürün A"),
    dict(_satis(adet=1, satis=50.0, maliyet=30.0),
         kanal="VATAN", sku="B2", urun_adi="Ürün B"),
    dict(_satis(adet=3, satis=5.0, maliyet=6.0),          # zararına satır
         kanal="İTOPYA", sku="A1", urun_adi="Ürün A"),
]


def test_ozet_toplam_satir_karlarinin_toplamidir():
    top, _, _ = sdb.ozet_hesapla(SATISLAR)
    beklenen = sum(sdb.satir_kar(s)["net_kar"] for s in SATISLAR)
    assert top["net_kar"] == pytest.approx(beklenen)
    # sağlama: bu örnekte toplam formülle de aynı çıkar,
    # ama tanım gereği doğru olan satır toplamıdır
    assert top["net_kar"] == pytest.approx(10.0 + 20.0 + (-3.0))


def test_ozet_ciro_adet_destek_toplamlari():
    top, _, _ = sdb.ozet_hesapla(SATISLAR)
    assert top["ciro"] == pytest.approx(20 + 50 + 15)
    assert top["maliyet"] == pytest.approx(8 + 30 + 18)
    assert top["destek"] == pytest.approx(2.0)
    assert top["adet"] == 6


def test_ozet_marj_net_satisa_gore():
    """Marj = net kâr / (ciro − destek)."""
    top, _, _ = sdb.ozet_hesapla(SATISLAR)
    assert top["marj"] == pytest.approx(27.0 / 83.0 * 100)


def test_ozet_kanal_kirilimi():
    _, kanal, _ = sdb.ozet_hesapla(SATISLAR)
    assert set(kanal) == {"VATAN", "İTOPYA"}
    assert kanal["VATAN"]["net_kar"] == pytest.approx(30.0)
    assert kanal["İTOPYA"]["net_kar"] == pytest.approx(-3.0)
    assert kanal["VATAN"]["adet"] == 3


def test_ozet_sku_kirilimi_ayni_skuyu_birlestirir():
    _, _, urun = sdb.ozet_hesapla(SATISLAR)
    assert urun["A1"]["adet"] == 5                       # 2 + 3
    assert urun["A1"]["net_kar"] == pytest.approx(7.0)   # 10 − 3


def test_ozet_bos_liste():
    top, kanal, urun = sdb.ozet_hesapla([])
    assert top["net_kar"] == 0.0 and top["marj"] == 0.0
    assert kanal == {} and urun == {}


def test_net_ciro_iade_dusumu():
    """Merdivenin ilk basamağı: brüt ciro − iade = net ciro.
    (UI'daki hesap: _net_ciro = top['ciro'] − _itop['i_tutar'])"""
    top, _, _ = sdb.ozet_hesapla(SATISLAR)
    i_tutar = 15.0
    assert top["ciro"] - i_tutar == pytest.approx(70.0)
