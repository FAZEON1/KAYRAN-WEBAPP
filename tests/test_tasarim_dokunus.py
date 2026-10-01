# -*- coding: utf-8 -*-
"""Tasarım dokunuşları (Ekim 2026) — geri dönüş korumaları.

1. Sol menü / sayfa içi radyolar: Streamlit 1.64 seçenekleri bir kabın içine
   aldı (radiogroup > div > label[data-testid=stRadioOption]). Yalnız
   'radiogroup > label' arayan kurallar HİÇ tutmuyordu: menüde yuvarlak seçim
   düğmeleri çıkıyor, seçili sayfa öne çıkmıyordu.
2. Kişi adı: 'ibrahim'.capitalize() → 'Ibrahim' (noktasız I).
3. Ana sayfada üst menü sekmeleri kutu kutu: ipucu kabına (.stTooltipIcon)
   verilen çerçeve.
4. Giriş ekranı arka planı z-index:-1 ile sayfa zemininin ARKASINDA kalıyordu.
"""
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _oku(yol):
    return (KOK / yol).read_text(encoding="utf-8")


def _tasarim():
    import importlib
    return importlib.import_module("shared.tasarim")


# ── 1. Radyo seçicileri ──────────────────────────────────────────────
def test_menu_kurallari_iki_streamlit_yapisini_da_tanir():
    T = _tasarim()
    css = T.SIDEBAR_CSS
    assert '[data-testid="stRadioOption"]' in css, "1.64 yapısı (stRadioOption) tanınmıyor"
    assert '[role="radiogroup"] > label' in css, "eski yapı tanınmıyor"
    # Yuvarlak seçim düğmesi her iki yapıda gizlenir
    assert '[data-testid="stRadioOption"] > div > div:first-child' in css
    # Sol menü ve sayfa içi radyolar ayrı ayrı biçimlenir
    assert 'section[data-testid="stSidebar"]' in css and 'section[data-testid="stMain"]' in css
    # Kurallar çekirdek CSS'e bağlı (her sayfada basılır)
    assert "SIDEBAR_CSS" in _oku("shared/tasarim.py").split("def cekirdek_css", 1)[1]


def test_segmented_control_menu_kuralina_yakalanmaz():
    """segmented_control da role=radiogroup kullanır; menü kuralı onu alt alta
    dizip 'Ko…' diye kesiyordu (Koyu/Açık seçimi). Kurallar stRadio ile sınırlı."""
    css = _tasarim().SIDEBAR_CSS
    for satir in css.splitlines():
        if "radiogroup" in satir and "{" in satir:
            assert 'stRadio' in satir, satir


def test_hicbir_dosya_yalniz_eski_radyo_secicisini_kullanmaz():
    """'radiogroup > label' tek başına 1.64'te tutmaz; yanında stRadioOption
    olmayan kural yazılmasın."""
    desen = re.compile(r'radiogroup"?\]\s*>\s*label')
    hatali = []
    for p in KOK.rglob("*.py"):
        if "tests" in p.parts or ".git" in p.parts:
            continue
        for i, satir in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if desen.search(satir) and "stRadioOption" not in satir and "_OPT" not in satir \
                    and "_DAIRE" not in satir and not satir.lstrip().startswith(("#", '"""')):
                hatali.append(f"{p.relative_to(KOK)}:{i}")
    # docstring içindeki tarihçe notu (shared/tarih.py) kural değildir
    hatali = [h for h in hatali if not h.startswith("shared/tarih.py")]
    assert not hatali, "Yalnız eski yapıyı tanıyan radyo kuralı: " + ", ".join(hatali)


# ── 2. Türkçe ad ─────────────────────────────────────────────────────
def test_kisi_adi_turkce_buyuk_harf():
    T = _tasarim()
    assert T.kisi_adi("ibrahim") == "İbrahim"
    assert T.kisi_adi("IŞIL") == "Işıl"
    assert T.kisi_adi("ayşe nur") == "Ayşe Nur"
    assert T.kisi_adi("") == ""
    assert T.bas_harf("ibrahim") == "İ"
    assert T.bas_harf("ılgaz") == "I"


def test_gorunen_adlar_capitalize_kullanmaz():
    src = _oku("app.py")
    for kalip in ("{aktif_kullanici.capitalize()}", "{k_adi.capitalize()}",
                  "{_kg.capitalize()}", '_bm.get("gonderen") or "Sistem").capitalize()'):
        assert kalip not in src, kalip
    assert ".capitalize()" not in _oku("shared/utils.py").split("def sidebar_kullanici", 1)[1].split("\ndef ", 1)[0]


# ── 3. Üst menü çerçevesi ────────────────────────────────────────────
def test_ana_sayfa_ipucu_kabina_cerceve_vermez():
    src = _oku("app.py")
    govde = src[src.index("def portal_css():"):src.index("def giris_ekrani():")]
    govde = re.sub(r"/\*.*?\*/", "", govde, flags=re.S)   # yorumlar kural değil
    kurallar = [k for k in govde.split("}") if "stTooltipIcon" in k.split("{")[0]]
    assert not kurallar, "portal_css .stTooltipIcon'a stil veriyor (üst menü kutu kutu görünür)"


# ── 4. Giriş ekranı ──────────────────────────────────────────────────
def test_giris_arka_plani_gorunur_katmanda():
    src = _oku("app.py")
    css = src[src.index("def login_css():"):src.index("def portal_css():")]
    css = css[css.index('css_tek_satir("""'):]            # yalnız CSS'in kendisi
    assert "z-index: -1" not in css and "z-index:-1" not in css
    assert "blobMove" not in css, "görünmeyen, işlemci yoran leke animasyonu geri gelmiş"
    assert "prefers-reduced-motion" in css


def test_giris_ve_ana_sayfa_tek_ikon_dili():
    src = _oku("app.py")
    giris = src[src.index("def giris_ekrani():"):src.index("def ust_navigasyon():")]
    for emo in ("💰", "🧾", "🚢", "📦", "🏬", "🛠️", "🔐"):
        assert emo not in giris, emo
    ana = src[src.index("def anasayfa():"):src.index("def sistem_kayitlari():")]
    for emo in ("⚡ Hızlı Erişim", "👑", 'st.button("Aç →"', ">Sistem Aktif<"):
        assert emo not in ana, emo


# ── Modül kartı ve kısayol ───────────────────────────────────────────
def test_modul_karti_tamami_tiklanir():
    src = _oku("app.py")
    ana = src[src.index("def anasayfa():"):src.index("def sistem_kayitlari():")]
    assert 'key=f"hz_{_mk}"' in ana and 'key=f"home_open_{_mk}"' in ana
    css = src[src.index("def _ana_css():"):src.index("def giris_ekrani():")]
    assert "position:absolute" in css and "opacity:0" in css   # görünmez, kartı kaplayan düğme
    assert ":has(button:focus-visible)" in css                 # klavye odağı görünür


def test_arama_kisayolu():
    src = _oku("app.py")
    assert "__kayranKisayol" in src and ".st-key-top_arama button" in src
    assert "(Ctrl+K)" in src


def test_modul_cipi_rakamli_ikon_adini_da_cizer():
    """'inventory_2' gibi rakamlı ikon adı düz yazı olarak basılıyordu."""
    h = _tasarim().sidebar_modul_html("inventory_2", "Ürün Yönetimi", "pembe")
    assert 'class="k-ikon"' in h and ">inventory_2</span>" in h
    # Emoji (eski çağrı) yazı tipi ikonu sayılmaz
    assert 'class="k-ikon"' not in _tasarim().sidebar_modul_html("📦", "X")
