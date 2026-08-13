# -*- coding: utf-8 -*-
"""
Stok hareketi ve depo kanonikleştirme testleri — kayranpm/database.py

Hepsi SAF fonksiyon testi: veritabanına gitmez, sahte sözlüklerle çalışır.
"""

import pytest

from kayranpm.database import (
    depo_kanonik,
    _kirilim_kanonik,
    _bizim_stok_hesapla,
    _sevk_uygula,
    _SATILABILIR_DEPOLAR,
)


# ═══════════════════════════════════════════════════════════
#  depo_kanonik — yazım farkları tek isme inmeli
# ═══════════════════════════════════════════════════════════

@pytest.mark.parametrize("girdi, beklenen", [
    ("MERKEZ", "MERKEZ DEPO"),          # kısa yazım genişletilir
    ("MERKEZDEPO", "MERKEZ DEPO"),      # boşluksuz
    ("merkez depo", "MERKEZ DEPO"),     # küçük harf
    ("  merkez   depo  ", "MERKEZ DEPO"),  # fazla boşluk
    ("HAPPY LIFE", "HAPPY LIFE"),
    ("HAPPY LİFE", "HAPPY LIFE"),       # noktalı İ — Excel'den böyle geliyor
    ("happylife", "HAPPY LIFE"),
    ("HAPPY", "HAPPY LIFE"),
    ("ASEL", "ASEL DEPO"),
    ("TEKNIK", "TEKNİK DEPO"),          # çıktı noktalı İ ile
])
def test_depo_kanonik_bilinen_yazimlar(girdi, beklenen):
    assert depo_kanonik(girdi) == beklenen


def test_depo_kanonik_bilinmeyen_depo_normalize_edilir():
    """Bilinmeyen depo kaybolmaz; en azından tutarlı yazıma çevrilir."""
    assert depo_kanonik("Bilinmeyen Depo") == "BILINMEYEN DEPO"
    assert depo_kanonik("İkinci El Depo") == "IKINCI EL DEPO"


def test_depo_kanonik_bos_girdi():
    assert depo_kanonik(None) == ""
    assert depo_kanonik("") == ""


def test_depo_kanonik_kendi_ciktisinda_sabit():
    """İki kez uygulamak sonucu değiştirmemeli (idempotent).
    Değiştirseydi kırılım her kaydedişte başka bir anahtara kayardı."""
    for ad in ["MERKEZ", "happy life", "Bilinmeyen Depo", "TEKNIK"]:
        bir = depo_kanonik(ad)
        assert depo_kanonik(bir) == bir


# ═══════════════════════════════════════════════════════════
#  _kirilim_kanonik — mükerrer anahtarlar birleşmeli
# ═══════════════════════════════════════════════════════════

def test_kirilim_ayni_depo_farkli_yazim_toplanir():
    """'MERKEZ' ve 'Merkez Depo' aynı depo — ayrı satır kalırsa stok ikiye bölünür."""
    sonuc = _kirilim_kanonik({"MERKEZ": 5, "Merkez Depo": 3, "MERKEZDEPO": 2})
    assert sonuc == {"MERKEZ DEPO": 10}


def test_kirilim_metin_sayilar_cevrilir():
    """Excel'den gelen adetler metin olabiliyor."""
    assert _kirilim_kanonik({"HAPPY LIFE": "2"}) == {"HAPPY LIFE": 2}
    assert _kirilim_kanonik({"MERKEZ": 3.0}) == {"MERKEZ DEPO": 3}


def test_kirilim_bozuk_deger_sifir_olur_depo_kaybolmaz():
    """Sayıya çevrilemeyen değer 0 sayılır ama depo satırı silinmez."""
    assert _kirilim_kanonik({"MERKEZ": "abc"}) == {"MERKEZ DEPO": 0}
    assert _kirilim_kanonik({"HAPPY LIFE": None}) == {"HAPPY LIFE": 0}


def test_kirilim_bos_girdi():
    assert _kirilim_kanonik(None) == {}
    assert _kirilim_kanonik({}) == {}


# ═══════════════════════════════════════════════════════════
#  _bizim_stok_hesapla — iade / ikinci el hariç
# ═══════════════════════════════════════════════════════════

def test_bizim_stok_satilabilir_depolarin_toplami():
    assert _bizim_stok_hesapla({"MERKEZ DEPO": 10, "HAPPY LIFE": 5}) == 15


def test_bizim_stok_iade_ve_ikinci_el_haric():
    """Fiziksel takipteki mal satılabilir stoğa girmemeli."""
    kirilim = {"MERKEZ DEPO": 10, "IADE DEPO": 7, "IKINCI EL DEPO": 3}
    assert _bizim_stok_hesapla(kirilim) == 10


def test_bizim_stok_kisa_depo_yazimi_da_sayilir():
    """'MERKEZ' kısa yazımı satılabilir sayılmazsa stok eksik görünür —
    bu hata bir kez yaşandı, testi o yüzden var."""
    assert _bizim_stok_hesapla({"MERKEZ": 10, "HAPPYLIFE": 5}) == 15


def test_bizim_stok_teknik_ve_asel_satilabilir_degil():
    assert _bizim_stok_hesapla({"TEKNİK DEPO": 4, "ASEL DEPO": 6}) == 0


def test_bizim_stok_bos_girdi():
    assert _bizim_stok_hesapla(None) == 0
    assert _bizim_stok_hesapla({}) == 0


def test_satilabilir_depo_listesi_beklenen_iceriktedir():
    """Liste değişirse bizim_stok sessizce başka bir rakam üretir."""
    assert _SATILABILIR_DEPOLAR == {"MERKEZ DEPO", "HAPPY LIFE"}


# ═══════════════════════════════════════════════════════════
#  _sevk_uygula — sevkte toplam korunmalı
# ═══════════════════════════════════════════════════════════

def test_sevk_toplam_korunur():
    """Sevkin tek değişmezi bu: mal taşınır, yoktan var olmaz."""
    once = {"MERKEZ DEPO": 10, "HAPPY LIFE": 5}
    sonra, hata = _sevk_uygula(once, "MERKEZ DEPO", "HAPPY LIFE", 4)
    assert hata == ""
    assert sum(sonra.values()) == sum(once.values())
    assert sonra == {"MERKEZ DEPO": 6, "HAPPY LIFE": 9}


def test_sevk_girdiyi_degistirmez():
    """Saf olmalı: çağıran taraftaki sözlük bozulursa geri alma çalışmaz."""
    once = {"MERKEZ DEPO": 10}
    _sevk_uygula(once, "MERKEZ DEPO", "HAPPY LIFE", 4)
    assert once == {"MERKEZ DEPO": 10}


def test_sevk_yazim_farki_engel_degil():
    """Kaynak 'MERKEZ', kırılımda 'MERKEZ DEPO' — eşleşmeli."""
    sonra, hata = _sevk_uygula({"MERKEZ DEPO": 10}, "MERKEZ", "happy life", 3)
    assert hata == ""
    assert sonra == {"MERKEZ DEPO": 7, "HAPPY LIFE": 3}


def test_sevk_hedef_depo_yoksa_olusturulur():
    sonra, hata = _sevk_uygula({"MERKEZ DEPO": 10}, "MERKEZ DEPO", "ASEL DEPO", 2)
    assert hata == ""
    assert sonra["ASEL DEPO"] == 2


def test_sevk_yetersiz_stok_reddedilir():
    sonra, hata = _sevk_uygula({"MERKEZ DEPO": 2}, "MERKEZ DEPO", "HAPPY LIFE", 5)
    assert sonra is None
    assert "Yetersiz stok" in hata


def test_sevk_eksi_stok_uretmez():
    """Olmayan depodan sevk denenirse 0 kabul edilip reddedilmeli."""
    sonra, hata = _sevk_uygula({"MERKEZ DEPO": 5}, "ASEL DEPO", "MERKEZ DEPO", 1)
    assert sonra is None
    assert "Yetersiz stok" in hata


@pytest.mark.parametrize("adet", [0, -3])
def test_sevk_gecersiz_adet_reddedilir(adet):
    sonra, hata = _sevk_uygula({"MERKEZ DEPO": 10}, "MERKEZ DEPO", "HAPPY LIFE", adet)
    assert sonra is None
    assert hata


def test_sevk_ayni_depo_reddedilir():
    sonra, hata = _sevk_uygula({"MERKEZ DEPO": 10}, "MERKEZ", "MERKEZ DEPO", 1)
    assert sonra is None
    assert "aynı olamaz" in hata


def test_sevk_satilabilir_stogu_dogru_degistirir():
    """Merkez → İade sevki bizim_stok'u düşürmeli; Merkez → Happy Life düşürmemeli."""
    kirilim = {"MERKEZ DEPO": 10}
    assert _bizim_stok_hesapla(kirilim) == 10

    happy, _ = _sevk_uygula(kirilim, "MERKEZ DEPO", "HAPPY LIFE", 4)
    assert _bizim_stok_hesapla(happy) == 10      # ikisi de satılabilir

    iade, _ = _sevk_uygula(kirilim, "MERKEZ DEPO", "IADE DEPO", 4)
    assert _bizim_stok_hesapla(iade) == 6        # iade satılabilir değil
