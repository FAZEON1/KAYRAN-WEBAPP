# -*- coding: utf-8 -*-
"""
Sipariş takvimi — yoldaki malın stok kapsamına dahil edilmesi
(kayranpm/analitik.py · siparis_takvimi_hesapla)

Talep #Gokhan: Yolda/antrepoda/gümrükte mal varken program yine sipariş
önerisi veriyordu (örn. F1 siyah/beyaz kasa).

KÖK NEDEN: siparis_takvimi_hesapla yalnız depo+firma stoğunu görüyordu.
siparis_miktari_oneri ise yoldakini düşüyordu — iki fonksiyon çelişiyor,
öneri listesi (siparis_durum'a göre filtreliyor) ürünü yine ACİL sayıyordu.

Hepsi saf fonksiyon testi; veritabanı yok.
"""

import pytest

from kayranpm.analitik import siparis_takvimi_hesapla, siparis_miktari_oneri

US = 135          # üretim süresi (gün) — testlerde sabit veriyoruz
HAFTALIK = 40     # haftalık satış → günlük ~5.71


# ═══════════════════════════════════════════════════════════
#  Ana kural: yoldaki mal kapsama girer
# ═══════════════════════════════════════════════════════════

def test_antrepodaki_mal_acil_uyarisini_kaldirir():
    """F1 senaryosu: depoda 50, antrepoda 800.
    Yoldaki sayılmazsa 'ACİL — 8g'de biter' çıkıyordu."""
    _, _, durum_yoldakisiz, _ = siparis_takvimi_hesapla(50, HAFTALIK, US, 0)
    assert durum_yoldakisiz == "acil"            # eski (hatalı) davranış

    _, _, durum, _ = siparis_takvimi_hesapla(50, HAFTALIK, US, 800)
    assert durum != "acil"


def test_yoldaki_stok_bitis_gununu_uzatir():
    bitis_az, _, _, _ = siparis_takvimi_hesapla(50, HAFTALIK, US, 0)
    bitis_cok, _, _, _ = siparis_takvimi_hesapla(50, HAFTALIK, US, 800)
    assert bitis_az == 8
    assert bitis_cok == 148


def test_yoldaki_depo_stoguyla_ayni_agirlikta():
    """Kapsam = depo + yoldaki. 850 adedin nerede durduğu takvimi değiştirmemeli."""
    a = siparis_takvimi_hesapla(850, HAFTALIK, US, 0)
    b = siparis_takvimi_hesapla(50, HAFTALIK, US, 800)
    c = siparis_takvimi_hesapla(0, HAFTALIK, US, 850)
    assert a == b == c


@pytest.mark.parametrize("yoldaki", [0, None])
def test_yoldaki_yoksa_eski_davranis_korunur(yoldaki):
    """Yoldaki mal olmayan ürünlerde hiçbir şey değişmemeli."""
    assert siparis_takvimi_hesapla(50, HAFTALIK, US, yoldaki) == \
           (8, -127, "acil", "ACİL — 8g'de biter")


def test_varsayilan_parametre_geriye_uyumlu():
    """Eski çağrı biçimi (4. argüman yok) çalışmaya devam etmeli."""
    assert siparis_takvimi_hesapla(50, HAFTALIK, US) == \
           siparis_takvimi_hesapla(50, HAFTALIK, US, 0)


# ═══════════════════════════════════════════════════════════
#  Eşik davranışları bozulmamalı
# ═══════════════════════════════════════════════════════════

def test_yoldaki_yetersizse_hala_acil():
    """Antrepoda az mal varsa aciliyet KAYBOLMAMALI — yama fazla iyimser olmasın."""
    _, _, durum, _ = siparis_takvimi_hesapla(50, HAFTALIK, US, 100)
    assert durum == "acil"


@pytest.mark.parametrize("yoldaki, beklenen", [
    (800, "yaklasıyor"),    # 148g − 135g = 13g → 30 gün içinde
    (1000, "planlama"),     # 183g − 135g = 48g → 60 gün içinde
    (1500, "normal"),       # 271g − 135g = 136g → rahat
])
def test_esik_gecisleri(yoldaki, beklenen):
    _, _, durum, _ = siparis_takvimi_hesapla(50, HAFTALIK, US, yoldaki)
    assert durum == beklenen


def test_satis_verisi_yoksa_oneri_yapilmaz():
    """Yoldaki mal olsa da olmasa da satış verisi yoksa hesap yapılamaz."""
    assert siparis_takvimi_hesapla(50, 0, US, 800) == \
           (None, None, "veri_yok", "Satış verisi yok")


# ═══════════════════════════════════════════════════════════
#  İki fonksiyon artık çelişmiyor
# ═══════════════════════════════════════════════════════════

def test_takvim_ve_miktar_onerisi_tutarli():
    """Asıl hata buydu: miktar önerisi 'yeterli stok var' derken
    takvim 'ACİL' diyordu ve liste ürünü yine gösteriyordu."""
    yoldaki = 2000
    _, _, durum, _ = siparis_takvimi_hesapla(50, HAFTALIK, US, yoldaki)
    miktar, mesaj = siparis_miktari_oneri(50, HAFTALIK, "stabil", 0, yoldaki, US)
    assert miktar == 0
    assert durum == "normal"        # ikisi de "sipariş gerekmiyor" diyor


def test_gercekten_stok_yoksa_ikisi_de_uyarir():
    """Ters yön: yoldaki mal yokken uyarı kaybolmamalı."""
    _, _, durum, _ = siparis_takvimi_hesapla(50, HAFTALIK, US, 0)
    miktar, _ = siparis_miktari_oneri(50, HAFTALIK, "stabil", 0, 0, US)
    assert durum == "acil"
    assert miktar > 0
