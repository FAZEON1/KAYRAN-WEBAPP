# -*- coding: utf-8 -*-
"""Sol menü (shared/sol_menu.py, Ekim 2026): menü yapısı paletle aynı görünürlük kuralıyla, gruplar başlıklı,
masaüstünde kenar çubuğu açık / telefonda gizli; geri dönüş anahtarı."""
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from shared import sol_menu as SM  # noqa: E402
from shared import gezinme as G  # noqa: E402

TAM = {m["kod"]: True for m in G.MODULLER}


def _kosul_yok(ad, kullanici):
    return False


def _kosul_var(ad, kullanici):
    return True


def _mod(yapi, kod):
    return next(m for m in yapi if m["kod"] == kod)


def test_gorunurluk_paletle_ayni():
    yapi = SM.menu_yapisi({"kayranacc": True, "satis": False}, set(), "ali", _kosul_var)
    assert [m["kod"] for m in yapi] == ["anasayfa", "kayranacc"]      # yetkisiz modül (Hesap makinesi dahil) yok
    yapi = SM.menu_yapisi({"hesap_makinesi": True}, set(), "ali", _kosul_var)
    assert [m["kod"] for m in yapi] == ["anasayfa", "hesap_makinesi"]
    yapi = SM.menu_yapisi(TAM, {"yonetim"}, "ali", _kosul_var)
    kodlar = [m["kod"] for m in yapi]
    assert "yonetim" in kodlar and "ekip" not in kodlar            # Ekip yalnız kullanıcı yönetimi yetkisiyle
    assert kodlar == [m["kod"] for m in G.MODULLER if m["kod"] != "ekip"]   # sıra kayıt defteriyle aynı


def test_kosullu_sayfalar_suzulur():
    yok = _mod(SM.menu_yapisi(TAM, set(), "ali", _kosul_yok), "kayranacc")
    var = _mod(SM.menu_yapisi(TAM, set(), "ali", _kosul_var), "kayranacc")
    assert "toplam_aktifler" not in [s["kod"] for s in yok["sayfalar"]]
    assert "toplam_aktifler" in [s["kod"] for s in var["sayfalar"]]
    assert "pnl" not in [s["kod"] for s in _mod(SM.menu_yapisi(TAM, set(), "ali", _kosul_yok), "satis")["sayfalar"]]


def test_gruplar_basliklari_ve_sirasi():
    m = _mod(SM.menu_yapisi(TAM, set(), "ali", _kosul_var), "kayranacc")
    assert [(s["kod"], s["grup"]) for s in m["sayfalar"]][:6] == [
        ("genel_bakis", None),                                       # sayfayla aynı adlı tek sayfalı grup başlıksız
        ("bu_hafta", "Ödemeler"), ("cekler", "Ödemeler"), ("ertelenen", "Ödemeler"), ("odenenler", "Ödemeler"),
        ("banka", "Nakit")]
    assert ("cari_ekstre", "Cari") in [(s["kod"], s["grup"]) for s in m["sayfalar"]]
    assert len(m["sayfalar"]) == len(G.MODULLER[2]["sayfalar"])     # hiçbir sayfa kaybolmaz
    d = _mod(SM.menu_yapisi(TAM, set(), "ali", _kosul_var), "depo")
    assert all(s["grup"] is None for s in d["sayfalar"]) and len(d["sayfalar"]) == 6   # + Satılamayan stok


def test_secili_sayfa_oturumdan_yoksa_ilk():
    m = _mod(SM.menu_yapisi(TAM, set(), "ali", _kosul_var), "kayranacc")
    assert SM.secili_sayfa(m, {"acc_sayfa": "🏦 Banka Bakiyeleri"}) == "banka"
    assert SM.secili_sayfa(m, {}) == "genel_bakis"
    assert SM.secili_sayfa(m, {"acc_sayfa": "uydurma"}) == "genel_bakis"
    hm = _mod(SM.menu_yapisi(TAM, set(), "ali", _kosul_var), "hesap_makinesi")
    assert SM.secili_sayfa(hm, {}) is None


def test_turkce_buyuk_harf_ve_css_metni():
    assert SM._tr_buyuk("Cari") == "CARİ" and SM._tr_buyuk("Veri ve raporlar") == "VERİ VE RAPORLAR"
    m = SM._css_metin('Muhasebe › Bu "hafta" \\ x')
    assert '"' not in m and "\\22 " in m and "\\5c " in m and "›" in m


def test_masaustunde_acik_telefonda_gizli():
    c = SM.css(False, "Muhasebe › Bu hafta")
    masa, tel = c.split("@media (max-width:768px){", 1)
    assert "@media (min-width:769px){" in masa and 'section[data-testid="stSidebar"]{display:flex !important;width:248px' in masa
    assert 'section[data-testid="stSidebar"]{display:none !important;}' in tel.split("}}", 1)[0] + "}"
    # masaüstünde üst şeridin modül düğmeleri ve sayfa sekmeleri sol menüde (Ara / Dosya / Talep / kişi kalır)
    assert ':has([class*="st-key-top_"]):not(:has(.st-key-top_arama)){display:none' in masa
    assert '.st-key-sayfa_seridi [data-testid="stElementContainer"]:has([data-testid="stRadio"])' in masa
    assert 'content:"Muhasebe › Bu hafta"' in masa
    assert "width:72px" in SM.css(True) and "button p{display:none" in SM.css(True)


def test_geri_donus_anahtari_ve_cagri():
    assert G.MENU_SOL is True
    app = (KOK / "app.py").read_text(encoding="utf-8")
    assert "if not (MENU_SOL and MENU_UST and ak):" in app
    assert "_sol_menu()                                     # masaüstünde sol menü" in app
    # tıklama yeni yol açmaz: üst şerit ve paletle aynı _sayfaya_git
    assert "_sm.ciz(st.session_state.get(\"aktif_uygulama\", \"anasayfa\"), _sayfaya_git, _yapi, st.session_state)" in app
    # CSS çizimden sonra basılır: çizim yarıda kalırsa üst şerit gizlenmez
    k = (KOK / "shared" / "sol_menu.py").read_text(encoding="utf-8")
    assert k.index("st.button(s[\"ad\"]") < k.index("st.markdown(css(dar")


def test_stok_karti_aramasi_ust_cubukta():
    """Ürün yönetiminin stok kartı araması sol menü düzeninde üst çubuğun araç yuvasında: masaüstünde çubuğun
    solunda (sayfa başlığındaki düğmelerin üstüne binmez, kaydırınca da görünür), dar çubukta / telefonda tam genişlik."""
    app = (KOK / "app.py").read_text(encoding="utf-8")
    assert 'ust_arac_kur(st.container(key="ust_arac"))' in app
    g = (KOK / "shared" / "gezinme.py").read_text(encoding="utf-8")
    assert 'if MENU_SOL and c is not None and getattr(c, "_kayran_ust_arac", None) is not None:' in g
    c = SM.css(False, "x")
    masa = c.split("@container ustnav", 1)[0]
    assert ".st-key-ustnav .st-key-ust_arac{position:absolute !important;left:0;top:4px;" in masa
    assert ".st-key-ust_arac .st-key-pm_arac{margin:0 !important;width:100% !important;overflow:visible !important;}" in c
    tel = c.split("@media (max-width:640px){", 1)[1]
    assert ".st-key-ustnav:has(.st-key-ust_arac .st-key-stok_karti_kutu){display:block !important;" in tel


def test_kenar_cubugu_icerigin_ustune_binmez():
    """Streamlit'in genişlik tutamacı kabı (kenar çubuğunun ikinci çocuğu) akışta kalınca içeriğin solunu (x 248–496)
    görünmez biçimde kaplıyordu: oradaki çiplere (Tüm markalar, Tüm müşteriler…) tıklanmıyor, tekerlek sayfayı
    kaydırmıyordu (Ekim 2026, kullanıcı bildirdi). Kap genişliksiz ve tıklamasız olmalı."""
    masa = SM.css(False, "x").split("@media (max-width:768px){", 1)[0]
    assert 'section[data-testid="stSidebar"] > div:not([data-testid="stSidebarContent"]){position:absolute !important;' in masa
    assert "width:0 !important;height:0 !important;overflow:hidden !important;\n    pointer-events:none !important;" in masa
    assert '[data-testid="stSidebarResizeHandle"]{display:none !important;}' in masa
