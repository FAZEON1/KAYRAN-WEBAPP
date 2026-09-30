# -*- coding: utf-8 -*-
"""Kamerayla barkod okuma."""
import io
import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from shared import barkod as B  # noqa: E402


def _oku(p):
    return (KOK / p).read_text(encoding="utf-8")


def test_seri_no_icin_ean_sona():
    """Etikette EAN (ürün kodu) + Code128 (seri no) varsa seri no önce."""
    s = B.sirala([("8691234567890", "EAN-13"), ("SN24F14P0012345", "Code 128")])
    assert s[0][0] == "SN24F14P0012345"
    s = B.sirala([("036000291452", "UPC-A"), ("F14P|SN1", "QR Code")])
    assert s[0][1] == "QR Code"


def test_okuyucu_formun_ustunde():
    """Form içindeki alan ancak kaydedince güncellenir; okuyucu formdan ÖNCE
    çağrılmalı yoksa okunan numara alana yazılamaz."""
    src = _oku("teknikservis/main.py")
    for hedef, form in (('barkod_okuyucu("mk_seri"', 'st.form("mk_form"'),
                        ('barkod_okuyucu("ev_seri"', 'st.form("ev_form"')):
        assert hedef in src
        assert src.index(hedef) < src.index(form)
    assert 'barkod_okuyucu(f"ts_ara_{arayuz}"' in src


def test_yeni_kayitta_okuyucu_temizlenir():
    src = _oku("teknikservis/main.py")
    assert src.count('barkod_temizle("mk_seri")') == 2
    assert 'barkod_temizle("ev_seri")' in src


def test_kutuphane_gereksinimde():
    assert "zxing-cpp" in _oku("requirements.txt")


def test_bozuk_dosya_cokmez():
    pytest.importorskip("zxingcpp")
    assert B.coz(b"bu bir resim degil") == []


def test_telefon_fotosu_gibi_bozuk_goruntuden_okur():
    """Eğik, bulanık, karanlık, JPEG sıkıştırılmış fotoğraf."""
    zx = pytest.importorskip("zxingcpp")
    np = pytest.importorskip("numpy")
    from PIL import Image, ImageEnhance, ImageFilter
    for metin, bicim in (("SN24F14P0012345", zx.BarcodeFormat.Code128),
                         ("F14P-8256G|SN0001", zx.BarcodeFormat.QRCode)):
        im = Image.fromarray(np.array(zx.write_barcode_to_image(zx.create_barcode(metin, bicim), scale=3))).convert("RGB")
        zemin = Image.new("RGB", (im.width + 400, im.height + 300), (185, 178, 165))
        zemin.paste(im, (200, 150))
        z = zemin.rotate(7, expand=True, fillcolor=(120, 110, 100)).filter(ImageFilter.GaussianBlur(1.2))
        z = ImageEnhance.Contrast(ImageEnhance.Brightness(z).enhance(0.75)).enhance(0.8)
        b = io.BytesIO()
        z.save(b, "JPEG", quality=60)
        assert B.coz(b.getvalue())[0][0] == metin
