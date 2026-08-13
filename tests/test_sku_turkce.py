# -*- coding: utf-8 -*-
"""
SKU / kategori eşleşmesi ve Türkçe karakter testleri
  sku_anahtar (shared/utils.py)      : kanonik SKU anahtarı
  tr_buyuk    (shared/utils.py)      : İngilizce tarzı BÜYÜK (i→I noktasız)
  _tr_upper   (kayranpm/ref_no.py)   : Türkçe-farkında BÜYÜK (i→İ noktalı)

İkisi FARKLI iş yapar ve karıştırılırsa kategori eşleşmesi sessizce kopar:
  "monitör".upper()      → "MONITÖR"  (noktasız I — Python Türkçe bilmez)
  _tr_upper("monitör")   → "MONİTÖR"  (kategori anahtarları böyle)
"""

import pytest

from shared.utils import sku_anahtar, tr_buyuk
from kayranpm.ref_no import _tr_upper


# ═══════════════════════════════════════════════════════════
#  sku_anahtar — kanonik SKU
# ═══════════════════════════════════════════════════════════

@pytest.mark.parametrize("girdi, beklenen", [
    ("Fazeon X24F165S", "X24F165S"),    # devir notundaki ana örnek
    ("FAZEON X24F165S", "X24F165S"),
    ("fazeon x24f165s", "X24F165S"),
    ("x24f165s", "X24F165S"),           # önek yoksa yalnız BÜYÜK + kırp
    ("  X24F165S  ", "X24F165S"),
    ("N50502-08D6X", "N50502-08D6X"),   # tire/karakter korunur
])
def test_sku_anahtar_ornekler(girdi, beklenen):
    assert sku_anahtar(girdi) == beklenen


def test_sku_anahtar_bos_girdi():
    assert sku_anahtar(None) == ""
    assert sku_anahtar("") == ""
    assert sku_anahtar("   ") == ""


def test_sku_anahtar_yalniz_bastaki_onek_atilir():
    """'FAZEON' kelimesi SKU'nun ortasında geçiyorsa dokunulmaz."""
    assert sku_anahtar("X-FAZEON-1") == "X-FAZEON-1"


def test_sku_anahtar_tek_kelime_fazeon_korunur():
    """SKU'nun kendisi 'FAZEON' ise silinip boş kalmamalı."""
    assert sku_anahtar("FAZEON") == "FAZEON"
    assert sku_anahtar("Fazeon ") == "FAZEON"


def test_sku_anahtar_idempotent():
    """Normalize edilmiş SKU tekrar normalize edilince değişmemeli —
    kaynak + rapor katmanı arka arkaya çağırıyor."""
    for s in ["Fazeon X24F165S", "N50502-08D6X", "abc123"]:
        bir = sku_anahtar(s)
        assert sku_anahtar(bir) == bir


def test_sku_uyusmazligi_ornekleri_esitlenmez():
    """Açık işlerdeki 27 üründen ikisi: bunlar GERÇEKTEN farklı SKU'lar,
    normalize onları eşitlemez (veri düzeltmesi ayrı iş). Test, normalize'ın
    'fazla akıllılık' yapıp yanlış birleştirmediğini garanti eder."""
    assert sku_anahtar("F11PA650BWM") != sku_anahtar("F11PA650BBM")
    assert sku_anahtar("N50502-08D6X") != sku_anahtar("N50502-08D6")


# ═══════════════════════════════════════════════════════════
#  Türkçe BÜYÜK harf — iki fonksiyon, iki farklı amaç
# ═══════════════════════════════════════════════════════════

def test_python_upper_turkce_bilmez():
    """Testin varlık sebebi: sorunun kendisi. Bu davranış değişirse
    (ör. locale etkisi) aşağıdaki testlerin bağlamı da değişir."""
    assert "monitör".upper() == "MONITÖR"      # noktasız I!


def test_tr_upper_noktali_i_uretir():
    """Kategori anahtarları noktalı İ ile: 'monitör' → 'MONİTÖR'."""
    assert _tr_upper("monitör") == "MONİTÖR"
    assert _tr_upper("bilgisayar") == "BİLGİSAYAR"


def test_tr_upper_i_ve_noktasiz_i_ayrimi():
    assert _tr_upper("i") == "İ"
    assert _tr_upper("ı") == "I"
    assert _tr_upper("ığdır") == "IĞDIR"


def test_tr_upper_tum_turkce_harfler():
    assert _tr_upper("çğıöşü") == "ÇĞIÖŞÜ"
    assert _tr_upper("soğutucu") == "SOĞUTUCU"


def test_tr_upper_idempotent():
    for s in ["monitör", "MONİTÖR", "Işık", "soğutucu"]:
        bir = _tr_upper(s)
        assert _tr_upper(bir) == bir


def test_tr_upper_bos_girdi():
    assert _tr_upper(None) == ""
    assert _tr_upper("") == ""


def test_tr_buyuk_marka_tarzi_noktasiz():
    """tr_buyuk KASITLI olarak İngilizce tarzıdır (marka/model adları):
    'Mio Mivue' → 'MIO MIVUE'. _tr_upper ile karıştırılmamalı."""
    assert tr_buyuk("Mio Mivue 802") == "MIO MIVUE 802"
    assert tr_buyuk("misafir") == "MISAFIR"          # i → I (noktasız)


def test_tr_buyuk_turkceye_ozgu_harfler_korunur():
    assert tr_buyuk("Fazeon Soğutucu") == "FAZEON SOĞUTUCU"
    assert tr_buyuk("çğöşü") == "ÇĞÖŞÜ"


def test_tr_buyuk_noktali_buyuk_i_sadelesir():
    """Girdide zaten 'İ' varsa noktasız 'I'ya iner (marka tarzı tutarlılık)."""
    assert tr_buyuk("İstanbul") == "ISTANBUL"


def test_iki_fonksiyon_ayni_girdide_farkli_sonuc():
    """Bilerek farklılar — biri diğerinin yerine kullanılırsa
    kategori destek eşleşmesi kopar (ref_no'daki gerçek hata buydu)."""
    assert _tr_upper("monitör") == "MONİTÖR"
    assert tr_buyuk("monitör") == "MONITÖR"
    assert _tr_upper("monitör") != tr_buyuk("monitör")
