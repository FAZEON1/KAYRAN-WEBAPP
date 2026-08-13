# -*- coding: utf-8 -*-
"""
Paçal maliyet — yoldaki partilerin hariç tutulması (ithalat/database.py)

Talep #Gokhan (12.08.2026): Gümrükte/antrepodaki siparişler bitmiş ithalat
gibi sayılıp maliyetleri FOB olarak paçala giriyordu.

KÖK NEDEN: get_sku_maliyet_ozet dosya DURUMUNA bakmıyordu. Yoldaki partide
ardiye/antrepo/müşavirlik masrafları henüz girilmemiş olduğu için dosya
yüzdesi 0 çıkıyor, final = FOB oluyor ve parti paçalı AŞAĞI çekiyordu.

Veritabanı yok: get_dosyalar / get_tum_kalemler sahteleniyor, gerçek hesap
zinciri (dosya_hesapla → kategori_yuzde_map → kalem_yuzde) koşuyor.
"""

import pytest

import ithalat.database as idb


def _dosya(did, durum="", masraf=None, tarih="2026-01-01"):
    """Masrafsız dosya → yüzde 0 → final = FOB (yoldaki partinin tipik hâli)."""
    return {"id": did, "durum": durum, "tarih": tarih,
            "masraflar": masraf or {}, "fatura_indirim": 0}


def _kalem(did, sku, adet, fob, kategori="GENEL"):
    return {"dosya_id": did, "sku": sku, "adet": adet,
            "birim_fob": fob, "kategori": kategori}


@pytest.fixture
def ithalat_kur(monkeypatch):
    def kur(dosyalar, kalemler):
        monkeypatch.setattr(idb, "get_dosyalar", lambda: dosyalar)
        monkeypatch.setattr(idb, "get_tum_kalemler", lambda: kalemler)
    return kur


# ═══════════════════════════════════════════════════════════
#  Ana kural: yoldaki parti paçala girmez
# ═══════════════════════════════════════════════════════════

@pytest.mark.parametrize("durum", ["Üretimde", "Yolda", "Gümrükte", "Antrepoda"])
def test_yoldaki_parti_pacala_girmez(ithalat_kur, durum):
    """Teslim alınmış parti 10 USD landed; yoldaki parti 6 USD çıplak FOB.
    Yoldaki sayılırsa paçal 8'e düşer — talepteki hatanın ta kendisi."""
    ithalat_kur(
        [_dosya(1, "Teslim Alındı", {"navlun": 500.0}),   # 100×5=500 FOB + 500 masraf → %100 → 10
         _dosya(2, durum)],                               # masrafsız, henüz girilmemiş
        [_kalem(1, "X1", 100, 5.0),
         _kalem(2, "X1", 100, 6.0)],
    )
    ozet = idb.get_sku_maliyet_ozet()
    assert ozet["X1"]["pacal_final"] == pytest.approx(10.0)   # yalnız teslim alınan
    assert ozet["X1"]["toplam_adet"] == 100
    assert ozet["X1"]["dosya_sayisi"] == 1


def test_teslim_alinan_parti_normal_hesaplanir(ithalat_kur):
    ithalat_kur([_dosya(1, "Teslim Alındı", {"navlun": 500.0})],
                [_kalem(1, "X1", 100, 5.0)])
    ozet = idb.get_sku_maliyet_ozet()
    assert ozet["X1"]["pacal_fob"] == pytest.approx(5.0)
    assert ozet["X1"]["pacal_final"] == pytest.approx(10.0)


def test_bos_durum_eski_kayitlar_haric_tutulmaz(ithalat_kur):
    """KRİTİK: durum alanı sonradan eklendi, eski dosyaların çoğunda BOŞ.
    Bunlar elenirse paçal tamamen boşalır ve tüm ürünler %100 marj gösterir."""
    ithalat_kur([_dosya(1, "", {"navlun": 500.0})],
                [_kalem(1, "X1", 100, 5.0)])
    ozet = idb.get_sku_maliyet_ozet()
    assert "X1" in ozet
    assert ozet["X1"]["pacal_final"] == pytest.approx(10.0)


def test_bilinmeyen_durum_haric_tutulmaz(ithalat_kur):
    """Listede olmayan bir durum yazılmışsa (elle/eski veri) mal yok sayılmaz."""
    ithalat_kur([_dosya(1, "Beklemede", {"navlun": 500.0})],
                [_kalem(1, "X1", 100, 5.0)])
    assert "X1" in idb.get_sku_maliyet_ozet()


def test_durum_bosluklu_yazilmis_olsa_da_elenir(ithalat_kur):
    ithalat_kur([_dosya(1, "Teslim Alındı", {"navlun": 500.0}),
                 _dosya(2, "  Gümrükte  ")],
                [_kalem(1, "X1", 100, 5.0), _kalem(2, "X1", 100, 6.0)])
    assert idb.get_sku_maliyet_ozet()["X1"]["pacal_final"] == pytest.approx(10.0)


# ═══════════════════════════════════════════════════════════
#  Sınır durumlar
# ═══════════════════════════════════════════════════════════

def test_tum_partiler_yoldaysa_sku_hic_donmez(ithalat_kur):
    """Maliyet uydurmaktansa boş dönmek yeğdir: get_pacal_map bu durumda
    ürün kartındaki alis_fiyati'na düşer (yurt içi maliyet yedeği)."""
    ithalat_kur([_dosya(1, "Gümrükte")], [_kalem(1, "X1", 100, 6.0)])
    assert idb.get_sku_maliyet_ozet() == {}


def test_son_maliyet_de_yoldakini_secmez(ithalat_kur):
    """'son_final' en yeni TARİHLİ dosyadan gelir. Yoldaki parti daha yeni
    tarihli olduğu için filtre olmasaydı 'son' onu gösterirdi."""
    ithalat_kur(
        [_dosya(1, "Teslim Alındı", {"navlun": 500.0}, tarih="2026-01-01"),
         _dosya(2, "Antrepoda", tarih="2026-08-01")],
        [_kalem(1, "X1", 100, 5.0), _kalem(2, "X1", 100, 6.0)],
    )
    ozet = idb.get_sku_maliyet_ozet()
    assert ozet["X1"]["son_final"] == pytest.approx(10.0)
    assert ozet["X1"]["son_tarih"] == "2026-01-01"


def test_diger_skular_etkilenmez(ithalat_kur):
    """Yoldaki dosyada başka SKU varsa yalnız o elenir, diğerleri kalır."""
    ithalat_kur(
        [_dosya(1, "Teslim Alındı", {"navlun": 500.0}), _dosya(2, "Yolda")],
        [_kalem(1, "X1", 100, 5.0), _kalem(2, "YENI", 50, 8.0)],
    )
    ozet = idb.get_sku_maliyet_ozet()
    assert set(ozet) == {"X1"}


def test_kalem_yoksa_bos_doner(ithalat_kur):
    ithalat_kur([], [])
    assert idb.get_sku_maliyet_ozet() == {}


def test_agirlikli_ortalama_adete_gore(ithalat_kur):
    """İki teslim alınmış parti: paçal adet-ağırlıklı ortalama olmalı."""
    ithalat_kur(
        [_dosya(1, "Teslim Alındı", {"navlun": 300.0}),   # 100 × 3 FOB → %100 → 6
         _dosya(2, "Teslim Alındı", {"navlun": 0.0})],    # 300 × 4 FOB → %0   → 4
        [_kalem(1, "X1", 100, 3.0), _kalem(2, "X1", 300, 4.0)],
    )
    ozet = idb.get_sku_maliyet_ozet()
    assert ozet["X1"]["toplam_adet"] == 400
    assert ozet["X1"]["pacal_final"] == pytest.approx((6.0 * 100 + 4.0 * 300) / 400)
