# -*- coding: utf-8 -*-
"""Sol menü (Ekim 2026, yeni tasarım): modüller açılır, sayfalar grup başlıklarıyla alt alta.

Masaüstünde (769 px ve üstü) Streamlit'in kenar çubuğunda çizilir; üst şeritteki modül düğmeleri
ve sayfa sekmeleri o genişlikte gizlenir (app.py, SOL_CSS). Tablet ve telefonda bugünkü düzen
(üst şerit / alt menü) aynen kalır, kenar çubuğu gizlidir.

Gezinme yeni bir yol açmaz: tıklama app._sayfaya_git(modül, sayfa_kodu) ile aynı oturum
anahtarlarına yazar; sayfa sekmeleri, komut paleti ve adres çubuğu ile birebir aynı sonuç.
Geri almak için shared/gezinme.py → MENU_SOL = False.

Saf fonksiyon (test edilir): menu_yapisi.
"""
import html as _h

from shared.gezinme import MODULLER, sayfa_kodu

DAR_ANAHTAR = "_sol_menu_dar"


def _tr_buyuk(s):
    """Türkçe büyük harf (Python'un upper'ı 'Cari' → 'CARI' yazar)."""
    return str(s).replace("i", "İ").replace("ı", "I").upper()


def menu_yapisi(yetkiler, ozel, kullanici, kosul):
    """Görünen modüller ve sayfaları.
    [{kod, ad, ikon, sayfalar: [{kod, ad, grup}]}] — grup: başlık metni ya da None (başlıksız).
    Görünürlük paletle aynı: özel modül özel yetkiyle, diğerleri modül yetkisiyle; koşullu sayfa
    (kâr, toplam aktifler) kosul(ad, kullanici) ile. Ana sayfa herkese açık. Yetkisiz modül gösterilmez
    (telefondaki alt menü gibi; üst şerit hepsini gösterip tıklanınca uyarıyordu)."""
    out = []
    for m in MODULLER:
        k = m["kod"]
        if k == "anasayfa":
            gor = True
        elif m.get("ozel"):
            gor = m["ozel"] in (ozel or set())
        else:
            gor = bool((yetkiler or {}).get(k))
        if not gor:
            continue
        izinli = [(kod, ad) for _sec, kod, ad, ks in (m.get("sayfalar") or [])
                  if not ks or kosul(ks, kullanici)]
        adlar = dict(izinli)
        sayfalar = []
        if m.get("gruplar"):
            for _gk, gad, kodlar in m["gruplar"]:
                ss = [kd for kd in kodlar if kd in adlar]
                if not ss:
                    continue
                # tek sayfalı ve sayfayla aynı adlı grup (Genel bakış, Toplu işlemler) başlıksız
                baslik = None if (len(ss) == 1 and adlar[ss[0]] == gad) else gad
                sayfalar += [{"kod": kd, "ad": adlar[kd], "grup": baslik} for kd in ss]
            # gruba yazılmamış sayfa kaybolmasın
            sayfalar += [{"kod": kd, "ad": ad, "grup": None} for kd, ad in izinli
                         if all(s["kod"] != kd for s in sayfalar)]
        else:
            sayfalar = [{"kod": kd, "ad": ad, "grup": None} for kd, ad in izinli]
        out.append({"kod": k, "ad": m["ad"], "ikon": m["ikon"], "sayfalar": sayfalar,
                    "anahtar": m.get("anahtar")})
    return out


def secili_sayfa(modul, oturum):
    """Modülün açık sayfasının kodu (oturumdaki menü değerinden); yoksa ilk sayfa."""
    sec = oturum.get(modul.get("anahtar")) if modul.get("anahtar") else None
    kod = sayfa_kodu(modul["kod"], sec) if sec else None
    if kod and any(s["kod"] == kod for s in modul["sayfalar"]):
        return kod
    return modul["sayfalar"][0]["kod"] if modul["sayfalar"] else None


def konum_adi(aktif):
    """Modül dışı sayfaların adı (hesap sayfaları: Soru sor, İzinler…)."""
    from shared.gezinme import SISTEM
    return next((ad for kod, ad, _i, _o in SISTEM if kod == aktif), {"arama": "Arama"}.get(aktif, ""))


def _daralt():
    import streamlit as st
    st.session_state[DAR_ANAHTAR] = not st.session_state.get(DAR_ANAHTAR, False)


# Masaüstü eşiği: Streamlit kenar çubuğunu 768 px ve altında kendiliğinden kapatır
_MASA = "@media (min-width:769px)"
_K = "html body .stApp section[data-testid=\"stSidebar\"] .st-key-sol_menu"


def _css_metin(s):
    """CSS content: içine güvenli metin."""
    return "".join(c if (c.isalnum() or c in " ·›-,.()") else f"\\{ord(c):x} " for c in str(s))


def css(dar=False, konum=""):
    """Sol menünün ve masaüstünde gizlenen üst şerit parçalarının kuralları.
    konum: üst şeridin solundaki yer bilgisi ("Muhasebe › Bu hafta")."""
    gen = 72 if dar else 248
    # daraltılmış: yalnız ikonlar (yazılar, logo ve aç/kapa okları gizli)
    dar_css = (f'{_K} button p{{display:none !important;}}'
               f'{_K} [data-testid="stElementContainer"]:has(.k-sol-ust){{display:none !important;}}'
               f'{_K} button[data-testid]{{justify-content:center !important;padding:0 !important;}}'
               f'{_K} button::after{{display:none !important;}}') if dar else ""
    N = "html body .stApp .st-key-ustnav"
    return f"""<style>
{_MASA}{{
  html body section[data-testid="stSidebar"]{{display:flex !important;width:{gen}px !important;
    min-width:{gen}px !important;max-width:{gen}px !important;}}
  html body section[data-testid="stSidebar"] > div,
  html body [data-testid="stSidebarContent"]{{width:{gen}px !important;min-width:{gen}px !important;
    max-width:{gen}px !important;transform:none !important;}}
  html body section[data-testid="stSidebar"] [data-testid="stSidebarContent"]{{padding:0 !important;}}
  html body section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{{width:100% !important;
    box-sizing:border-box !important;padding:14px 12px 24px !important;}}
  html body [data-testid="stSidebarHeader"]{{display:none !important;}}
  /* üst şeritte modül düğmeleri sol menüde; Ara · Dosya · Talep · kişi kalır */
  {N} [data-testid="stColumn"]:has([class*="st-key-top_"]):not(:has(.st-key-top_arama)){{display:none !important;}}
  /* üst şerit: kutu değil, altı çizgili ince bar; solda konum, sağda Ara · Dosya · Talep · kişi */
  {N}{{padding:6px 0 10px !important;margin-bottom:14px !important;border-bottom:1px solid var(--k-kenar) !important;}}
  {N} [data-testid="stHorizontalBlock"]{{background:transparent !important;border:0 !important;padding:0 !important;
    box-shadow:none !important;}}
  {N} [data-testid="stHorizontalBlock"]:not([class*="st-key-"])::before{{content:"{_css_metin(konum)}";flex:1 1 auto;min-width:0;
    align-self:center;font-size:13.5px;font-weight:600;color:var(--k-metin);white-space:nowrap;overflow:hidden;
    text-overflow:ellipsis;padding-left:2px;}}
  html body .stApp .st-key-ustnav [data-testid="stColumn"]:has(.st-key-ust_talep){{position:static !important;
    box-shadow:none !important;background:transparent !important;}}
  /* sayfa sekmeleri sol menüde (şeridin sağındaki araçlar, ör. stok kartı araması, kalır) */
  html body .st-key-sayfa_seridi [data-testid="stElementContainer"]:has([data-testid="stRadio"]),
  html body .st-key-sayfa_seridi .st-key-sayfa_alt{{display:none !important;}}
  html body .st-key-sayfa_seridi{{margin:0 0 6px !important;}}
  /* yalnız sekme taşıyan şerit boş kalır → kabı da akıştan çıkar (araç koyan modül: anahtarı "_arac" ile
     biten kap, ör. Ürün yönetimi pm_arac; CSS iç içe :has kabul etmediği için anahtardan tanınır) */
  html body [data-testid="stLayoutWrapper"]:has(> .st-key-sayfa_seridi):not(:has([class*="_arac"])){{display:none !important;}}
  /* kenar çubuğunda yalnız sol menü: modüllerin eski kenar çubuğu parçaları (önceden kenar çubuğu
     bütünüyle gizliydi, görünmüyorlardı) gizli kalır */
  html body [data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"]:has(> [data-testid="stLayoutWrapper"] > .st-key-sol_menu)
    > :not(:has(> .st-key-sol_menu)){{display:none !important;}}
}}
@media (max-width:768px){{
  html body section[data-testid="stSidebar"]{{display:none !important;}}
}}
[data-testid="stSidebarCollapseButton"],[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapsedControl"]{{display:none !important;}}
{_K}{{gap:1px !important;}}
{_K} [data-testid="stMarkdownContainer"]:has(.k-sol-grup, .k-sol-ust){{margin:0 !important;}}
{_K} .st-key-sol_ust{{align-items:center !important;flex-wrap:nowrap !important;margin-bottom:12px !important;}}
{_K} .st-key-sol_ust [data-testid="stElementContainer"]{{width:auto !important;}}
{_K} .st-key-sol_ust [data-testid="stElementContainer"]:has(.k-sol-ust){{flex:1 1 auto !important;min-width:0;}}
{_K} .st-key-sol_daralt button[data-testid]{{width:28px !important;min-width:28px !important;height:28px !important;
  min-height:28px !important;padding:0 !important;justify-content:center !important;}}
{_K} .st-key-sol_daralt button p{{display:none !important;}}
{_K} .k-sol-ust{{display:flex;align-items:center;gap:10px;padding:2px 4px;}}
{_K} .k-sol-ust svg{{width:28px;height:28px;flex-shrink:0;}}
{_K} .k-sol-ust b{{font-size:15px;font-weight:700;letter-spacing:1.2px;color:var(--k-metin);}}
{_K} .k-sol-grup{{font-size:10.5px !important;font-weight:500 !important;letter-spacing:.08em;
  color:var(--k-silik) !important;opacity:.85;margin:12px 0 3px 34px;}}
{_K} [data-testid="stElementContainer"]{{width:100% !important;}}
{_K} [data-testid="stElementContainer"]:has(.k-sol-mod){{display:none !important;}}
{_K} button[data-testid]{{width:100% !important;justify-content:flex-start !important;min-height:34px !important;
  height:34px !important;padding:0 10px !important;border:0 !important;border-radius:8px !important;
  background:transparent !important;box-shadow:none !important;color:var(--k-soluk) !important;
  transform:none !important;gap:10px !important;}}
{_K} button > div, {_K} button span[data-has-shortcut]{{justify-content:flex-start !important;width:100%;}}
{_K} button p{{font-size:14px !important;font-weight:500 !important;color:inherit !important;margin:0 !important;
  white-space:nowrap !important;overflow:hidden !important;text-overflow:ellipsis !important;}}
{_K} button [data-testid="stIconMaterial"]{{font-size:19px !important;color:var(--k-silik) !important;}}
{_K} button span:has(> [data-testid="stIconMaterial"]){{display:inline-flex !important;}}
{_K} button:hover{{background:var(--k-ortu2) !important;color:var(--k-metin) !important;}}
{_K} button:focus-visible{{outline:2px solid var(--k-mor) !important;outline-offset:-2px !important;}}
/* modül satırı: açık modül hafif zeminli; sağda aç/kapa oku */
{_K} [class*="st-key-sol_m_"] button[kind="primary"],{_K} [class*="st-key-sol_m_"] button[data-testid="stBaseButton-primary"]{{
  background:color-mix(in srgb,var(--k-mor) 13%,var(--k-yuzey1)) !important;color:var(--k-metin) !important;}}
{_K} [class*="st-key-sol_m_"] button[kind="primary"] p,{_K} [class*="st-key-sol_m_"] button[data-testid="stBaseButton-primary"] p{{font-weight:650 !important;}}
{_K} [class*="st-key-sol_m_"] button[kind="primary"] [data-testid="stIconMaterial"],
{_K} [class*="st-key-sol_m_"] button[data-testid="stBaseButton-primary"] [data-testid="stIconMaterial"]{{color:var(--k-mor) !important;}}
{_K} [class*="st-key-sol_m_"]:has(.k-sol-acilir) button::after{{content:"expand_more";font-family:"Material Symbols Rounded";font-size:18px;
  margin-left:auto;color:var(--k-silik);font-feature-settings:"liga";}}
{_K} [class*="st-key-sol_m_"]:has(.k-sol-acilir) button[kind="primary"]::after,
{_K} [class*="st-key-sol_m_"]:has(.k-sol-acilir) button[data-testid="stBaseButton-primary"]::after{{content:"expand_less";}}
/* sayfa satırı: girintili, ince sol çizgi; seçili sayfa mor çizgi + zemin */
{_K} .st-key-sol_sayfalar{{margin:2px 0 8px 20px !important;padding-left:8px !important;
  border-left:1px solid var(--k-kenar2) !important;gap:0 !important;}}
{_K} .st-key-sol_sayfalar button{{min-height:30px !important;height:30px !important;padding:0 10px !important;}}
{_K} .st-key-sol_sayfalar button p{{font-size:13px !important;color:var(--k-soluk) !important;}}
/* seçili sayfa: kutu yok — yazı belirgin, soldaki kılavuz çizginin üstünde kısa mor parça */
{_K} .st-key-sol_sayfalar button[data-testid]{{border-radius:0 6px 6px 0 !important;margin-left:-9px !important;
  width:calc(100% + 9px) !important;padding-left:19px !important;}}
{_K} .st-key-sol_sayfalar button[data-testid]:hover{{background:color-mix(in srgb,var(--k-metin) 4%,transparent) !important;}}
{_K} .st-key-sol_sayfalar button[data-testid]:hover p{{color:var(--k-metin) !important;}}
{_K} .st-key-sol_sayfalar button[data-testid="stBaseButton-primary"],
{_K} .st-key-sol_sayfalar button[kind="primary"]{{background:transparent !important;
  box-shadow:inset 2px 0 0 var(--k-mor) !important;}}
{_K} .st-key-sol_sayfalar button[data-testid="stBaseButton-primary"] p,
{_K} .st-key-sol_sayfalar button[kind="primary"] p{{color:var(--k-metin) !important;font-weight:600 !important;}}
{_K} .st-key-sol_sayfalar .k-sol-grup{{margin-left:10px !important;}}
{dar_css}
</style>"""


def ciz(aktif, git, yapi, oturum):
    """Kenar çubuğuna menüyü çizer. git(modul, sayfa_kodu=None): app._sayfaya_git."""
    import streamlit as st
    from shared.tasarim import kayran_logo_svg
    dar = bool(oturum.get(DAR_ANAHTAR, False))
    with st.sidebar:
        with st.container(key="sol_menu"):
            with st.container(key="sol_ust", horizontal=True, gap="small"):
                st.markdown(f'<div class="k-sol-ust">{kayran_logo_svg(28)}<b>KAYRAN</b></div>',
                            unsafe_allow_html=True)
                st.button("Menüyü genişlet" if dar else "Menüyü daralt", key="sol_daralt",
                          icon=":material/chevron_right:" if dar else ":material/chevron_left:",
                          help="Menüyü genişlet" if dar else "Menüyü daralt", on_click=_daralt)
            konum = "Ana sayfa" if aktif == "anasayfa" else ""
            for m in yapi:
                acik = m["kod"] == aktif
                sinif = "k-sol-mod k-sol-acilir" if m["sayfalar"] else "k-sol-mod"
                with st.container(key=f"sol_m_{m['kod']}"):
                    st.markdown(f'<span class="{sinif}" hidden></span>', unsafe_allow_html=True)
                    st.button(m["ad"], key=f"sol_{m['kod']}", icon=f":material/{m['ikon']}:", help=m["ad"] if dar else None,
                              type="primary" if acik else "secondary", on_click=git, args=(m["kod"],))
                if acik:
                    sec = secili_sayfa(m, oturum)
                    sad = next((x["ad"] for x in m["sayfalar"] if x["kod"] == sec), None)
                    konum = f"{m['ad']} › {sad}" if sad else m["ad"]
                if acik and m["sayfalar"] and not dar:
                    onceki = object()
                    with st.container(key="sol_sayfalar"):
                        for s in m["sayfalar"]:
                            if s["grup"] and s["grup"] != onceki:
                                st.markdown(f'<div class="k-sol-grup">{_h.escape(_tr_buyuk(s["grup"]))}</div>',
                                            unsafe_allow_html=True)
                            onceki = s["grup"]
                            st.button(s["ad"], key=f"sol_{m['kod']}__{s['kod']}",
                                      type="primary" if s["kod"] == sec else "secondary",
                                      on_click=git, args=(m["kod"], s["kod"]))
        # Kurallar menü çizildikten SONRA (kenar çubuğunda, ana alanda boşluk açmasın): çizim yarıda
        # kalırsa üst şeritteki düğmeler gizlenmez
        st.markdown(css(dar, konum or konum_adi(aktif)), unsafe_allow_html=True)
