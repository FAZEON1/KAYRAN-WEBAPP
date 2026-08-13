# -*- coding: utf-8 -*-
"""
Kategori adı uyuşmazlığı — kayranpm/ref_no.py · kategori_kanonik

SORUN: Ref kaydına/Excel'e 'MOUSEPAD', ürün kartına 'Mouse Pad' yazılıyor.
İkisi ayrı anahtar üretince Ref No desteği kategori filtresinde bulunamıyor,
ayrı bir satır olarak kalıyordu.

YÖNTEM: elle alias listesi yok — katalogla (KATEGORI_LISTE) boşluksuz
karşılaştırma. Belirsiz adlar (SOĞUTUCU) bilerek ÇEVRİLMEZ.
"""

import pytest

from kayranpm.ref_no import kategori_kanonik, _kat_liste, _tr_upper
from kayranpm.database import KATEGORI_LISTE


# ═══════════════════════════════════════════════════════════
#  Boşluk farkı — asıl şikâyet
# ═══════════════════════════════════════════════════════════

@pytest.mark.parametrize("yazim", [
    "MOUSEPAD", "MOUSE PAD", "Mouse Pad", "mousepad",
    "mouse  pad", "  Mouse Pad  ",
])
def test_mousepad_tum_yazimlar_ayni_anahtara_iner(yazim):
    assert kategori_kanonik(yazim) == "MOUSE PAD"


def test_excel_ve_katalog_yazimi_artik_bulusuyor():
    """Hatanın kendisi: bu iki değer eşit olmadığı için destek kayboluyordu."""
    excel = kategori_kanonik("MOUSEPAD")        # ref kaydında yazılan
    katalog = kategori_kanonik("Mouse Pad")     # üründeki kategori
    assert excel == katalog


def test_eski_yontem_bulusturmuyordu():
    """Karşılaştırma noktası — yalnız _tr_upper yetmiyordu."""
    assert _tr_upper("MOUSEPAD") != _tr_upper("Mouse Pad")


# ═══════════════════════════════════════════════════════════
#  Belirsiz adlar ÇEVRİLMEZ
# ═══════════════════════════════════════════════════════════

def test_sogutucu_belirsiz_oldugu_icin_cevrilmez():
    """Katalogda üç soğutucu kategorisi var; hangisi olduğu bilinemez.
    Tahmin etmek desteği YANLIŞ kategoriye yazar — olduğu gibi kalır."""
    assert kategori_kanonik("SOĞUTUCU") == "SOĞUTUCU"
    assert kategori_kanonik("soğutucu") == "SOĞUTUCU"


def test_katalogdaki_sogutucular_kendi_adlariyla_eslesir():
    assert kategori_kanonik("cpu soğutucu") == "CPU SOĞUTUCU"
    assert kategori_kanonik("CPUSOĞUTUCU") == "CPU SOĞUTUCU"
    assert kategori_kanonik("Kule Soğutucu") == "KULE SOĞUTUCU"


def test_katalogda_olmayan_kategori_korunur():
    """Kataloğa henüz girmemiş kategori KAYBOLMAZ, kendi adıyla raporlanır."""
    assert kategori_kanonik("SELLOUT") == "SELLOUT"
    assert kategori_kanonik("Yeni Ürün Grubu") == "YENİ ÜRÜN GRUBU"


# ═══════════════════════════════════════════════════════════
#  Türkçe ve sınır durumlar
# ═══════════════════════════════════════════════════════════

def test_turkce_buyuk_harf_dogru():
    """'monitör' → 'MONİTÖR' (noktalı İ). upper() kullanılsaydı MONITÖR olurdu."""
    assert kategori_kanonik("monitör") == "MONİTÖR"
    assert kategori_kanonik("ekran kartı") == "EKRAN KARTI"


def test_idempotent():
    for s in ["MOUSEPAD", "Mouse Pad", "SOĞUTUCU", "monitör"]:
        bir = kategori_kanonik(s)
        assert kategori_kanonik(bir) == bir


def test_bos_girdi():
    assert kategori_kanonik(None) == ""
    assert kategori_kanonik("") == ""
    assert kategori_kanonik("   ") == ""


def test_katalog_yazimlari_kendileriyle_eslesir():
    """Katalogdaki her kategori kendi kanonik hâline gitmeli (kayma olmasın)."""
    for kat in KATEGORI_LISTE:
        assert kategori_kanonik(kat) == _tr_upper(kat)


# ═══════════════════════════════════════════════════════════
#  _kat_liste — çok kategorili kayıtlar
# ═══════════════════════════════════════════════════════════

def test_kat_liste_kanoniklestirir():
    assert _kat_liste("MOUSEPAD · monitör") == ["MOUSE PAD", "MONİTÖR"]


def test_kat_liste_bos_parcalari_atar():
    assert _kat_liste("MOUSEPAD ·  · ") == ["MOUSE PAD"]
    assert _kat_liste("") == []
    assert _kat_liste(None) == []


def test_kat_liste_tek_kategori():
    assert _kat_liste("KASA") == ["KASA"]
