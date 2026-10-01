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
    kod = (KOK / "kayranpm/main.py").read_text(encoding="utf-8")
    i = kod.index("# ── STOK KARTI — hızlı erişim")
    blok = kod[i:kod.index("_stok_goster(_hedef)", i)]
    assert 'with st.container(key="stok_karti_kutu"):' in blok      # tek kap (kopuk başlık yok)
    assert "st.selectbox" not in blok                               # eski hata 1: ilk karakter siliniyordu
    assert 'icon=":material/search:"' in blok
    # Enter'da otomatik açılış yalnız arama METNİ değiştiyse (yoksa her yenilemede açılır)
    assert 'st.session_state.get("_sk_acilan") != _q' in blok and 'st.session_state["_sk_acilan"] = _q' in blok
    assert '"_sk_son"' in blok and "[:4]" in blok                     # son açılanlar
    assert 'html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu {' in kod


def test_ust_menu_tek_serit():
    src = (KOK / "app.py").read_text(encoding="utf-8")
    g = src[src.index("def ust_navigasyon"):src.index("\ndef ", src.index("def ust_navigasyon") + 10)]
    assert '("Ürün Yönetimi", "kayranpm"' in g and '("Hesap Makinesi", "hesap_makinesi"' in g   # kısaltma yok
    assert "border:0 !important;background:transparent !important" in g                         # çerçevesiz sekme
    assert ":has(.st-key-top_yonetim){{margin-left:6px" in g                                    # grup ayracı
    assert ":has(.st-key-top_hesap_makinesi){{margin-left:auto" in g                            # sağa yaslı
    assert "flex:0 0 auto !important" in g and "flex:1 0 auto" not in g                          # eşit genişlik yok
