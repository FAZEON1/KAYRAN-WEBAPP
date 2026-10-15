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


def test_stok_karti_kutusu_yapisi():
    """Ekim 2026 (kullanıcı seçimi "A"): kutu yalnız Ctrl+K penceresini ürün kipinde açar; kendi kart açma
    yolu (_stok_gec_sku, sonuç düğmeleri, goster çağrısı) yok — kart açıkken başka kod arayınca pencere açılıp
    kapanıyordu."""
    kod = (KOK / "kayranpm/main.py").read_text(encoding="utf-8")
    i = kod.index("# ── STOK KARTI — hızlı erişim")
    blok = kod[i:kod.index("st.markdown(", i)]
    assert 'st.container(key="stok_karti_kutu"' in blok and "stok_karti_kutusu()" in blok
    assert "goster(" not in blok and 'pop("_stok_gec_sku"' not in kod and "st.text_input" not in blok
    p = (KOK / "shared/palet.py").read_text(encoding="utf-8")
    assert 'window.__kayranPaletAc("urun")' in p and 'ac("urun")' in p
    # Kenar çubuğu kalktı (Eki 2026): kutu her sayfanın sağ üstünde, sonuçlar açılır liste
    assert 'html body .st-key-stok_karti_kutu {' in kod and 'html body .st-key-sk_sonuc {' in kod
    assert '_pm_arac = (_serit_kabi() or st).container(key="pm_arac"' in kod     # sekme şeridinin sağında


def test_ust_menu_tek_serit():
    src = (KOK / "app.py").read_text(encoding="utf-8")
    g = src[src.index("def ust_navigasyon"):src.index("\ndef ", src.index("def ust_navigasyon") + 10)]
    assert '("Ürün Yönetimi", "kayranpm"' in g and '("Hesap Makinesi", "hesap_makinesi"' in g   # kısaltma yok
    assert "border:0 !important;background:transparent !important" in g                         # çerçevesiz sekme
    assert ":has(.st-key-top_yonetim){{margin-left:6px" in g                                    # grup ayracı
    assert ":has(.st-key-top_hesap_makinesi){{margin-left:auto" in g                            # sağa yaslı
    assert "flex:0 0 auto !important" in g and "flex:1 0 auto" not in g                          # eşit genişlik yok


def test_stok_karti_yazilar_ust_uste_binmez():
    """Canlıda başlık arama kutusunun altında kalıyor, 'Son açılanlar' listeye
    yapışıyor, sonuçlar ayrı kutular gibi görünüyordu (01.10.2026)."""
    kod = (KOK / "kayranpm/main.py").read_text(encoding="utf-8")
    # Streamlit'in -1rem telafi boşluğu kutudaki yazı bloklarında sıfır
    assert ('.st-key-stok_karti_kutu [data-testid="stMarkdown"] [data-testid="stMarkdownContainer"] {\n'
            '        margin-bottom: 0 !important;') in kod
    # İpucu kabı (tam ürün adı) zemin/çerçeve almıyor
    assert '.st-key-stok_karti_kutu [data-testid="stTooltipIcon"],' in kod
    i = kod.index('.st-key-stok_karti_kutu [data-testid="stTooltipIcon"],')
    assert "background: transparent !important; border: 0 !important;" in kod[i:i + 400]
