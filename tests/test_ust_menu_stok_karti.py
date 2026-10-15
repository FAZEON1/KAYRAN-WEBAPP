# -*- coding: utf-8 -*-
"""Üst menü (tek şerit) + Ürün Yön. Stok Kartı kutusu yeniden tasarımı (01.10.2026)."""
from pathlib import Path

from kayranpm.stok_ara import stok_karti_ara  # noqa: E402

KOK = Path(__file__).resolve().parent.parent

LISTE = [
    {"sku": "X24F100", "urun_adi": 'FAZEON X24F100 24" 100HZ IPS', "marka": "FAZEON"},
    {"sku": "X24F100S", "urun_adi": 'FAZEON X24F100S 24" 165HZ VA', "marka": "FAZEON"},
    {"sku": "AX24F", "urun_adi": "ADAPTÖR", "marka": "DİĞER"},
    {"sku": "F14PA750BWQ", "urun_adi": "FAZEON F14 PLUS 750W BEYAZ KASA", "marka": "FAZEON"},
    {"sku": "IŞIK1", "urun_adi": "ŞERİT IŞIK ÇUBUĞU", "marka": None},
]


def _skular(q):
    return [r["sku"] for r in stok_karti_ara(LISTE, q)]


def test_cok_kelime_sira_onemsiz():
    assert _skular("x24 ips") == ["X24F100"]
    assert _skular("ips x24") == ["X24F100"]
    assert _skular("beyaz 750") == ["F14PA750BWQ"]


def test_siralama_tam_sonra_baslayan_sonra_iceren():
    assert _skular("x24f100") == ["X24F100", "X24F100S"]
    assert _skular("X24F") == ["X24F100", "X24F100S", "AX24F"]


def test_turkce_harf_ve_bos():
    assert _skular("isik") == ["IŞIK1"] and _skular("şerit") == ["IŞIK1"]
    assert _skular("  ") == [] and _skular("yokboyle") == []


def test_urun_yonetiminde_ayri_arama_kutusu_yok():
    """Ekim 2026 (kullanıcı: "soldaki arama penceresini kaldırabiliriz"): stok kartı üst şeritteki düğme ve
    Ctrl+K ile açılır; Ürün Yönetimi'ndeki ayrı kutu aynı pencereyi açıyordu, kalktı (CSS'i ve bileşeniyle)."""
    kod = (KOK / "kayranpm/main.py").read_text(encoding="utf-8")
    assert "stok_karti_kutusu" not in kod and "stok_karti_kutu" not in kod and "pm_arac" not in kod
    assert "sk_sonuc" not in kod and "goster(" not in kod and 'pop("_stok_gec_sku"' not in kod
    p = (KOK / "shared/palet.py").read_text(encoding="utf-8")
    assert "def stok_karti_kutusu(" not in p and "_KUTU_" not in p
    assert "window.__kayranPaletAc = ac;" in p and '.querySelector(".tetik").addEventListener("click", () => ac())' in p
    sm = (KOK / "shared/sol_menu.py").read_text(encoding="utf-8")
    assert "stok_karti_kutu" not in sm and "pm_arac{{" not in sm


def test_ust_menu_tek_serit():
    src = (KOK / "app.py").read_text(encoding="utf-8")
    g = src[src.index("def ust_navigasyon"):src.index("\ndef ", src.index("def ust_navigasyon") + 10)]
    assert '("Ürün Yönetimi", "kayranpm"' in g and '("Hesap Makinesi", "hesap_makinesi"' in g   # kısaltma yok
    assert "border:0 !important;background:transparent !important" in g                         # çerçevesiz sekme
    assert ":has(.st-key-top_yonetim){{margin-left:6px" in g                                    # grup ayracı
    assert ":has(.st-key-top_hesap_makinesi){{margin-left:auto" in g                            # sağa yaslı
    assert "flex:0 0 auto !important" in g and "flex:1 0 auto" not in g                          # eşit genişlik yok
