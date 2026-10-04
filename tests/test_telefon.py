# -*- coding: utf-8 -*-
"""Telefon görünümü (Ekim 2026) — Depo ve Teknik servis telefondan kullanılıyor.

1. Kenar çubuğu her ekranda AÇIK başlıyordu ("expanded"): telefonda her sayfa açılışında menü
   içeriğin üstünü kapatıyordu. "auto": telefonda kapalı, bilgisayarda açık.
2. Üst şerit telefonda: Talep düğmesi yalnız ikon (yazısı modül adlarını kesiyordu).
3. Depo stok aramasında kamerayla barkod okutma; okunan EAN ürün kartındaki barkoddan SKU'ya çevrilir.
4. Şeridin üstündeki görünmez bileşenler (çeviri, ipucu) telefonda 2 × 16 px boşluk bırakıyordu.
"""
import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))


def _oku(p):
    return (KOK / p).read_text(encoding="utf-8")


def test_kenar_cubugu_telefonda_kapali_baslar():
    a = _oku("app.py")
    m = re.search(r'initial_sidebar_state="(\w+)"', a)
    assert m and m.group(1) == "auto", m and m.group(1)


def _mobil_css():
    from shared.tasarim import MOBIL_CSS
    return MOBIL_CSS


def test_talep_telefonda_yalniz_ikon():
    css = _mobil_css()
    assert ".st-key-ust_talep button p" in css and "display:none" in css


def test_gorunmez_bilesenler_aralik_birakmaz():
    css = _mobil_css()
    for k in ("kayran_ceviri", "kayran_ipucu", "kayran_islem_gos"):
        assert f".st-key-{k}" in css, k
    assert "position:absolute" in css


def test_barkod_okuyucu_yalniz_telefonda():
    """Bilgisayarda el okuyucusu zaten kutuya yazar; kamera düğmesi yalnız telefonda görünür."""
    from shared.tasarim import cekirdek_css
    css = cekirdek_css()
    assert re.search(r"@media \(min-width:641px\)\{\{?[^@]*\.st-key-bk_dpo_ara_ac", css)


def test_barkoddan_sku():
    from depo.depo_hesap import barkoddan_sku
    bm = {"FZ-SSD-1TB": "8690000000001", "XS-PAD": ""}
    assert barkoddan_sku("8690000000001", bm) == "FZ-SSD-1TB"
    assert barkoddan_sku(" 8690000000001 ", bm) == "FZ-SSD-1TB"
    assert barkoddan_sku("fazeon", bm) == "fazeon"            # barkod değilse arama aynen kalır
    assert barkoddan_sku("", bm) == ""                        # boş barkodlu kart her şeyle eşleşmez
    assert barkoddan_sku("123", {}) == "123"


def test_depo_stok_kamera_ve_barkod_eslesmesi_bagli():
    d = _oku("depo/main.py")
    g = d[d.index("def _sayfa_stok"):]
    g = g[:g.index("\ndef ", 10)]
    assert 'barkod_okuyucu("dpo_ara"' in g
    assert "barkoddan_sku(" in g and "get_barkod_map()" in g
    assert g.index('barkod_okuyucu("dpo_ara"') < g.index('key="dpo_ara"')   # okuyucu kutudan ÖNCE
