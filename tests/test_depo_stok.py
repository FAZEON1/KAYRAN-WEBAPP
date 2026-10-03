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
    assert depo_kanonik("Şube Deposu") == "SUBE DEPOSU"


@pytest.mark.parametrize("girdi,beklenen", [
    # Teknik servis entegrasyonuyla TANINAN depolar haline geldi.
    # 'İkinci El Depo' eskiden bu testte "bilinmeyen" örneğiydi; artık
    # kanonik yazıma (Türkçe İ ile) çevrilir ve stok ekranlarında tek
    # isimle görünür.
    ("İkinci El Depo",  "İKİNCİ EL DEPO"),
    ("ikinci el",       "İKİNCİ EL DEPO"),
    ("2.el",            "İKİNCİ EL DEPO"),
    ("Servis Depo",     "TEKNİK DEPO"),      # servis = teknik, aynı fiziksel yer
    ("teknik servis",   "TEKNİK DEPO"),
    ("iade",            "İADE DEPO"),
    ("outlet",          "OUTLET DEPO"),
    ("hurda",           "HURDA DEPO"),
])
def test_depo_kanonik_teknik_servis_depolari(girdi, beklenen):
    assert depo_kanonik(girdi) == beklenen


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


# ═══════════════════════════════════════════════════════════
#  depo_dagilimi — G5F depo kırılımı rozetleri (Ekim 2026)
#  Tüm Ürünler detayı ve stok kartı kırılımı HAM adlarla çiziyordu:
#  'MERKEZ' + 'MERKEZ DEPO' iki ayrı rozet; Tüm Ürünler'de int("3.0") → çökme.
# ═══════════════════════════════════════════════════════════

def test_depo_dagilimi_ayni_depoyu_birlestirir_sirali_doner():
    from kayranpm.database import depo_dagilimi
    satirlar, toplam = depo_dagilimi({"MERKEZ": 5, "Merkez Depo": "3.0", "HAPPY LIFE": 12, "ASEL": 0})
    assert satirlar == [("HAPPY LIFE", 12), ("MERKEZ DEPO", 8)]     # sıfır depo yok, adede göre azalan
    assert toplam == 20


def test_depo_dagilimi_bozuk_ve_bos_deger_cokertmez():
    from kayranpm.database import depo_dagilimi
    assert depo_dagilimi({"MERKEZ": "abc", "HAPPY LIFE": None, "ASEL": "4"}) == ([("ASEL DEPO", 4)], 4)
    assert depo_dagilimi(None) == ([], 0)
    assert depo_dagilimi("bozuk") == ([], 0)


def test_ekranlar_kirilimi_depo_dagilimi_ile_ciziyor():
    """Ham sözlük üzerinde dönen rozet kodu geri gelmesin (çift depo + int('3.0') çökmesi)."""
    import pathlib
    kok = pathlib.Path(__file__).resolve().parent.parent / "kayranpm"
    main = (kok / "main.py").read_text(encoding="utf-8")
    kart = (kok / "stok_karti.py").read_text(encoding="utf-8")
    assert "depo_dagilimi(" in main and "sorted(_dk.items()" not in main
    assert "depo_dagilimi(" in kart and "for d, m in (_depo_kirilim or {}).items() if _f(m) != 0" not in kart


# ═══════════════════════════════════════════════════════════
#  satilabilir_kontrol — kırılım ↔ kayıtlı bizim_stok (Ekim 2026)
#  Tüm Ürünler'deki "Satılabilir (Merkez + Happy Life) = toplam stok" notu
#  kırılımdan değil kayıtlı bizim_stok'tan geliyordu; ikisi ayrı zamanda
#  yazılınca rozetlerle tutmayan sayı sessizce gösteriliyordu.
# ═══════════════════════════════════════════════════════════

def test_satilabilir_kontrol_tutarsa_fark_sifir():
    from kayranpm.database import satilabilir_kontrol
    k = satilabilir_kontrol({"MERKEZ": 40, "MERKEZ DEPO": 310, "HAPPY LIFE": 1892, "İADE": 7}, 2242)
    assert k == {"hesap": 2242, "kayitli": 2242, "fark": 0}            # İADE satılabilir değil


def test_satilabilir_kontrol_farki_isaretli_doner():
    from kayranpm.database import satilabilir_kontrol
    assert satilabilir_kontrol({"HAPPY LIFE": 100, "ASEL": 50}, 130) == {"hesap": 100, "kayitli": 130, "fark": -30}
    assert satilabilir_kontrol({"MERKEZ": "12.0"}, "10") == {"hesap": 12, "kayitli": 10, "fark": 2}


def test_satilabilir_kontrol_kirilim_yoksa_fark_aranmaz():
    """Kırılım hiç yüklenmemişse karşılaştıracak şey yok → fark None (uyarı çıkmaz)."""
    from kayranpm.database import satilabilir_kontrol
    assert satilabilir_kontrol({}, 50) == {"hesap": None, "kayitli": 50, "fark": None}
    assert satilabilir_kontrol(None, None) == {"hesap": None, "kayitli": 0, "fark": None}


def test_ekranlar_satilabilir_farkini_gosteriyor():
    import pathlib
    kok = pathlib.Path(__file__).resolve().parent.parent / "kayranpm"
    for ad in ("main.py", "stok_karti.py"):
        s = (kok / ad).read_text(encoding="utf-8")
        assert "import satilabilir_kontrol as _sat_kontrol" in s and "_sat_kontrol(" in s, ad
