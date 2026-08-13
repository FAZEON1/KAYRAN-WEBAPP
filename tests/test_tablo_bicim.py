# -*- coding: utf-8 -*-
"""
Tablo biçimlendirme testleri — shared/tasarim.py (+ satis/main.py'deki _usd)
  _tablo_kolon_tipi : kolon adından para/adet/oran ayrımı
  _tr_para/_tr_adet/_tr_oran : TR ayraçlı gösterim, akıllı ondalık (2-4)
  _usd              : USD gösterim, akıllı ondalık (2-4)

_usd, satis/main.py içinde tanımlı; o dosya modül düzeyinde UI kodu
çalıştırdığı için import EDİLMEZ — yalnız fonksiyonun kaynağı çıkarılıp
derlenir (yardımcısı yok, kendi kendine yeterli).
"""

import pathlib

import pytest

from shared.tasarim import _tablo_kolon_tipi, _tr_para, _tr_adet, _tr_oran


def _usd_yukle():
    """satis/main.py'den YALNIZ _usd fonksiyonunu çıkarır (UI'yı çalıştırmadan)."""
    kok = pathlib.Path(__file__).resolve().parent.parent
    kaynak = (kok / "satis" / "main.py").read_text(encoding="utf-8")
    bas = kaynak.index("def _usd")
    son = kaynak.index("\ndef ", bas + 5)
    kapsam = {}
    exec(compile(kaynak[bas:son], "satis/main.py::_usd", "exec"), kapsam)
    return kapsam["_usd"]


_usd = _usd_yukle()


# ═══════════════════════════════════════════════════════════
#  _tablo_kolon_tipi — para / adet / oran ayrımı
# ═══════════════════════════════════════════════════════════

@pytest.mark.parametrize("kolon, tip", [
    ("Ciro", "para"),
    ("Net Kâr", "para"),
    ("Birim Fiyat", "para"),
    ("Maliyet", "para"),
    ("Adet", "adet"),
    ("Stok", "adet"),
    ("Marj", "oran"),
    ("Kârlılık", "oran"),
    ("Yüzde", "oran"),
])
def test_kolon_tipi_temel_ayrimlar(kolon, tip):
    assert _tablo_kolon_tipi(kolon) == tip


def test_kolon_tipi_turkce_yumusama():
    """'destek' → 'desteği' (k→ğ), 'alacak' → 'alacağı'.
    Yumuşamış hâl listede yoksa 'Ref No desteği' para sayılmaz ve
    biçimlenmezdi — testin varlık sebebi bu gerçek hata."""
    assert _tablo_kolon_tipi("Ref No desteği") == "para"
    assert _tablo_kolon_tipi("Alacağı") == "para"
    assert _tablo_kolon_tipi("Destek") == "para"
    assert _tablo_kolon_tipi("Alacak") == "para"


def test_kolon_tipi_toplam_satis_adet_sayilir():
    """'Toplam Satış' sell-out raporunda ADET taşır; içinde 'satış' geçiyor
    diye para sanıp $ koymak rakamı yanlış gösteriyordu. Adet önceliği
    para listesinden ÖNCE kontrol edilmeli."""
    assert _tablo_kolon_tipi("Toplam Satış") == "adet"
    assert _tablo_kolon_tipi("Satış Adedi") == "adet"
    assert _tablo_kolon_tipi("İade Adet") == "adet"
    # ama yalın 'Satış' para kalmalı
    assert _tablo_kolon_tipi("Satış") == "para"


def test_kolon_tipi_metin_kolonlarina_dokunulmaz():
    """None → biçimlendirme yok. Metin kolonuna sayı biçimi uygulanırsa
    kâr gizleme maskesi ('•••') bozulur."""
    assert _tablo_kolon_tipi("Ürün Adı") is None
    assert _tablo_kolon_tipi("SKU") is None
    assert _tablo_kolon_tipi("Kanal") is None


def test_kolon_tipi_bos_girdi():
    assert _tablo_kolon_tipi("") is None
    assert _tablo_kolon_tipi(None) is None


def test_kolon_tipi_buyuk_kucuk_harf_duyarsiz():
    assert _tablo_kolon_tipi("CIRO") == "para"
    assert _tablo_kolon_tipi("marj") == "oran"


# ═══════════════════════════════════════════════════════════
#  _tr_para — TR ayraç + akıllı ondalık (en az 2, en fazla 4)
# ═══════════════════════════════════════════════════════════

def test_tr_para_binlik_nokta_ondalik_virgul():
    assert _tr_para(1616061.27) == "$1.616.061,27"


def test_tr_para_kurus_alti_basamak_korunur():
    """Birim fiyat 7,2938 → 4 hane korunmalı; 2'ye yuvarlanırsa
    adetle çarpımda toplam tutmaz."""
    assert _tr_para(7.2938) == "$7,2938"


def test_tr_para_gereksiz_sifirlar_atilir_ama_en_az_iki_hane():
    assert _tr_para(7.5) == "$7,50"
    assert _tr_para(1200) == "$1.200,00"


def test_tr_para_eksi_isaret_birimden_once():
    assert _tr_para(-5) == "-$5,00"


def test_tr_para_farkli_birim():
    assert _tr_para(1000, birim="₺") == "₺1.000,00"


def test_tr_para_sabit_basamak_istenirse_uygulanir():
    assert _tr_para(7.2938, basamak=2) == "$7,29"


def test_tr_para_sayi_olmayan_girdi_bos_doner():
    assert _tr_para("abc") == ""
    assert _tr_para(None) == ""


# ═══════════════════════════════════════════════════════════
#  _tr_adet / _tr_oran
# ═══════════════════════════════════════════════════════════

def test_tr_adet_binlik_ayrac_nokta():
    assert _tr_adet(1234567) == "1.234.567"


def test_tr_adet_yuvarlama_ve_bos():
    assert _tr_adet(3.6) == "4"
    assert _tr_adet("x") == ""


def test_tr_oran_virgullu():
    assert _tr_oran(43.333) == "%43,33"


# ═══════════════════════════════════════════════════════════
#  _usd (satis/main.py) — US ayraç + akıllı ondalık (2-4)
# ═══════════════════════════════════════════════════════════

def test_usd_akilli_ondalik():
    assert _usd(7.29) == "$7.29"
    assert _usd(7.2938) == "$7.2938"
    assert _usd(1200) == "$1,200.00"


def test_usd_eksi_ve_gecersiz():
    assert _usd(-3.5) == "-$3.50"
    assert _usd("abc") == "$0.00"     # _tr_para'dan farklı: boş değil $0.00
