# -*- coding: utf-8 -*-
"""
KAYRAN — Ortak UI / Tasarım Katmanı
Tek tasarım sözlüğü: renk tokenları · sayfa başlığı · scroll'lu pencere kartı ·
kompakt tablo yüksekliği · boş durum.

Tasarım ilkeleri (proje standardı):
  1. KOMPAKT   — sayfa boyu içerik sayısından bağımsız kalır; uzun listeler
                 pencere/tablo İÇİNDE kayar, sayfayı uzatmaz.
  2. MODAL     — detay veriler sayfanın altında değil st.dialog penceresinde açılır.
  3. TEK PALET — renk sadece RENK sözlüğünden seçilir, serbest hex yazılmaz.

Kullanım:
    from shared.ui import (RENK, sayfa_baslik, pencere_css, pencere,
                           pencere_grid, pencere_satiri, bos_durum, tablo_h)

    st.markdown(pencere_css(), unsafe_allow_html=True)          # sayfada 1 kez
    st.markdown(sayfa_baslik("📊", "Dashboard", "alt açıklama"), unsafe_allow_html=True)
    st.markdown(pencere_grid(
        pencere("🚨 ACİL", RENK["kirmizi"], satirlar_html, rozet="4 ürün"),
        pencere("⚠️ YAKLAŞAN", RENK["amber"], satirlar_html2, rozet="9 ürün"),
    ), unsafe_allow_html=True)
    st.dataframe(df, height=tablo_h(len(df)), use_container_width=True)
"""

# ─────────────────────────────────────────────────────────────────────
# RENK TOKENLARI — serbest hex yerine daima buradan
# ─────────────────────────────────────────────────────────────────────
from shared.tasarim import renk as trenk  # aktif temanın rengi (hex)
from shared.tasarim import tr_sayi, TemaRenk  # TR sayı biçimi · tema duyarlı sözlük
from shared.tasarim import kisi_adi as _kisi_adi  # Türkçe büyük harf (ibrahim → İbrahim)
# Tema duyarlı: RENK["x"] aktif temanın rengini verir (bkz. tasarim.TemaRenk)
RENK = TemaRenk({
    "mor":      "#818CF8",   # birincil vurgu / marka / nötr metrik
    "mor2":     "#A5B4FC",   # mor'un açık tonu (rozet/ikincil)
    "yesil":    "#34D399",   # pozitif · satılabilir · başarı
    "kirmizi":  "#F87171",   # acil · hata · negatif
    "kirmizi2": "#FCA5A5",   # kırmızının açık tonu (rozet metni)
    "amber":    "#FBBF24",   # uyarı · yaklaşan · beklemede
    "amber2":   "#FCD34D",   # amberin açık tonu (rozet metni)
    "cyan":     "#22D3EE",   # bilgi · oran · ölçüm
    "mavi":     "#7DD3FC",   # ithalat / lojistik teması
    "pembe":    "#F9A8D4",   # ürün yönetimi teması
    "metin":    "#E2E8F0",   # ana metin
    "soluk":    "#94A3B8",   # ikincil metin / etiket
    "silik":    "#7B8AA0",   # placeholder · boş durum
    # ── Yüzey katmanları (derinlik) — en koyudan açığa ──
    "yuzey0":   "#0B1120",   # en dip zemin (sayfa arka planı)
    "yuzey1":   "#0F172A",   # kart zemini (1. katman)
    "yuzey2":   "#152036",   # öne çıkan kart / hover (2. katman)
    "yuzey3":   "#1C2A44",   # en öndeki eleman (3. katman)
    "kenar":    "rgba(148,163,184,0.10)",  # ince ayırıcı kenar
    "kenar2":   "rgba(148,163,184,0.18)",  # belirgin kenar
})

# ═══════════════════════════════════════════════════════════════════
#  DESIGN TOKENS — tüm görünümün tek kaynağı.
#  Renk dışındaki her görsel karar (boşluk, yuvarlaklık, gölge,
#  tipografi) burada tanımlı. Bir değeri buradan değiştir → her yer
#  tutarlı değişir. Elle gömülü px değerleri yerine bunları kullan.
# ═══════════════════════════════════════════════════════════════════

# Boşluk ritmi — 4px tabanlı skala (4/8/12/16/24/32)
BOSLUK = {
    "xs": "4px", "sm": "8px", "md": "12px", "lg": "16px",
    "xl": "24px", "2xl": "32px",
}

# Yuvarlaklık skalası
RADIUS = {
    "sm": "8px", "md": "12px", "lg": "16px", "pill": "999px",
}

# Tipografik skala — 5 boyut, göz farkı hisseder (11/13/15/19/23)
FONT = {
    "xs":  "11px",   # etiket · caption · rozet
    "sm":  "13px",   # gövde metni · tablo
    "md":  "15px",   # alt başlık · vurgulu satır
    "lg":  "19px",   # sayfa başlığı
    "xl":  "23px",   # büyük metrik değeri
    "mono": "'JetBrains Mono', ui-monospace, monospace",  # sayısal değerler
}
FONT_AGIRLIK = {"normal": "400", "orta": "600", "kalin": "700", "cok_kalin": "800"}

# Gölge / yükseltme — dark UI'da ışık kenarı + alt gölge katmanı verir
GOLGE = {
    "kart":  "0 1px 2px rgba(0,0,0,0.30), inset 0 1px 0 rgba(255,255,255,0.03)",
    "one":   "0 4px 16px rgba(0,0,0,0.40), inset 0 1px 0 rgba(255,255,255,0.05)",
    "parlak": "0 0 0 1px rgba(129,140,248,0.30), 0 6px 20px rgba(99,102,241,0.18)",
}

# Geçiş süreleri — micro-interaction tutarlılığı
GECIS = {"hizli": "0.12s ease", "normal": "0.2s ease", "yavas": "0.35s ease"}


def _t(sozluk, anahtar, varsayilan=""):
    """Token erişimi — güvenli (anahtar yoksa varsayılan)."""
    return sozluk.get(anahtar, varsayilan)

#: st.dataframe için üst sınır (px) — pencere hissi, sayfayı uzatmaz
TABLO_MAKS = 320


def tablo_h(n_satir: int, maks: int = TABLO_MAKS) -> int:
    """Kompakt tablo yüksekliği: içerik kadar, en fazla `maks` px.

    Az satırda boşluk bırakmaz, çok satırda tablo kendi içinde kayar.
        st.dataframe(df, height=tablo_h(len(df)), use_container_width=True)
    """
    try:
        n = max(1, int(n_satir))
    except Exception:
        n = 1
    return int(min(maks, 40 + 35 * n))


# ─────────────────────────────────────────────────────────────────────
# SAYFA BAŞLIĞI — tüm modüllerde tek stil
# ─────────────────────────────────────────────────────────────────────
_MODUL_ADI = {"kayranacc": "Muhasebe", "kayranpm": "Ürün Yönetimi", "depo": "Depo",
              "ithalat": "İthalat", "teknikservis": "Teknik Servis", "satis": "Satış",
              "yonetim": "Yönetim", "hesap_makinesi": "Hesap Makinesi"}


def sayfa_baslik(ikon: str, ad: str, alt: str = "") -> str:
    """Sayfa başlığı — artık TEK STANDART: shared/tasarim.baslik.

    Eskiden iki ayrı başlık bileşeni vardı (bu büyük olan + tasarim.baslik
    kompakt olan); modüller karışık kullandığı için her sayfa farklı
    görünüyordu, Muhasebe'de ikisi birden çıkıyordu. Bu fonksiyon geriye
    uyumluluk için duruyor ve standart başlığı üretiyor: "ikon Modül › Sayfa",
    altında açıklama satırı."""
    import streamlit as st
    from shared.tasarim import baslik
    _mod = _MODUL_ADI.get(st.session_state.get("aktif_uygulama", ""), "")
    return baslik(f"{ikon} {_mod}".strip() if ikon else _mod, ad, aciklama=alt)


# ─────────────────────────────────────────────────────────────────────
# PENCERE — sabit yükseklik + iç scroll'lu kart (kompaktlığın çekirdeği)
# ─────────────────────────────────────────────────────────────────────
def pencere_css() -> str:
    """Pencere içi ince scrollbar stili — sayfada bir kez basılır."""
    return """<style>
.kyr-pencere-icerik{overflow-y:auto;padding-right:8px;}
.kyr-pencere-icerik::-webkit-scrollbar{width:6px;}
.kyr-pencere-icerik::-webkit-scrollbar-track{background:color-mix(in srgb,var(--k-metin) 3%,transparent);border-radius:3px;}
.kyr-pencere-icerik::-webkit-scrollbar-thumb{background:color-mix(in srgb,var(--k-soluk) 35%,transparent);border-radius:3px;}
.kyr-pencere-icerik::-webkit-scrollbar-thumb:hover{background:color-mix(in srgb,var(--k-soluk) 55%,transparent);}
</style>"""


def pencere(baslik: str, renk: str, icerik_html: str,
            rozet: str = "", yukseklik: int = 250, min_genislik: int = 300) -> str:
    """Başlık + (isteğe bağlı rozet) + iç scroll'lu içerik alanı olan kart.

    `pencere_grid()` içine konur; yan yana dizilir, dar ekranda alta sarar.
    Başlıktaki emoji ('🚨 ACİL SİPARİŞ') ikon karosuna çevrilir, BÜYÜK HARF
    başlık cümle düzenine iner ('Acil sipariş'); ortak k-kart görünümü
    (eskiden degrade zemin, 16px köşe, gölge ve renkli büyük harf başlık).
    """
    from shared.tasarim import emoji_ayir, cumle_duzeni, ikon_html
    _ik, _bas = emoji_ayir(baslik)
    _ik_html = ""
    if _ik:
        _ik_html = (f'<span style="width:26px;height:26px;border-radius:7px;flex-shrink:0;display:flex;'
                    f'align-items:center;justify-content:center;'
                    f'background:color-mix(in srgb,{renk} 15%,transparent)">{ikon_html(_ik, 16, renk)}</span>')
    roz = ""
    if rozet:
        roz = (f'<span style="background:color-mix(in srgb,{renk} 14%,transparent);color:{renk};'
               f'padding:3px 9px;border-radius:999px;font-size:11px;font-weight:600;'
               f'white-space:nowrap">{rozet}</span>')
    return (
        f'<div class="kyr-kart k-kart" data-akscent style="flex:1;min-width:{min_genislik}px;'
        f'border-left-color:{renk};padding:12px 16px;">'
        f'<div style="display:flex;align-items:center;gap:9px;margin-bottom:10px;flex-shrink:0;">'
        f'{_ik_html}<span style="font-size:14px;font-weight:650;color:var(--k-metin);'
        f'letter-spacing:-.1px">{cumle_duzeni(_bas)}</span>{roz}</div>'
        f'<div class="kyr-pencere-icerik" style="max-height:{yukseklik}px;">{icerik_html}</div>'
        f'</div>'
    )


def pencere_grid(*penceler: str, alt_bosluk: int = 4) -> str:
    """Pencereleri yan yana dizen esnek kapsayıcı (dar ekranda alta sarar)."""
    return (f'<div style="display:flex;gap:12px;flex-wrap:wrap;align-items:stretch;'
            f'margin:8px 0 {alt_bosluk}px;">' + "".join(penceler) + '</div>')


def pencere_satiri(sol_html: str, sag_html: str = "") -> str:
    """Pencere içinde kompakt liste satırı: solda metin, sağda rozet/değer."""
    sag = ""
    if sag_html:
        sag = (f'<div style="display:flex;gap:12px;flex-shrink:0;margin-left:8px;'
               f'align-items:center;">{sag_html}</div>')
    return (f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:4px 12px;margin:4px 0;border-radius:6px;'
            f'background:color-mix(in srgb,var(--k-metin) 3%,transparent);">{sol_html}{sag}</div>')


def bos_durum(mesaj: str) -> str:
    """Pencere boşken düzeni koruyan sakin placeholder."""
    return (f'<div style="color:{RENK["silik"]};font-size:13px;'
            f'padding:12px 4px;">✓ {mesaj}</div>')


# ─────────────────────────────────────────────────────────────────────
# İŞLEM GÖSTERGESİ — uygulama genelinde "çalışıyor" geri bildirimi
# ─────────────────────────────────────────────────────────────────────
def islem_gosterge_css() -> str:
    """Streamlit'in gözden kaçan sağ üst 'Running' ibaresini, her işlemde
    kendiliğinden beliren belirgin bir göstergeye dönüştürür:

      • Ekranın en üstünde akan gradyan progress çubuğu
      • Üst-ortada nabız atan "⏳ İşleniyor" kapsülü
      • Rerun sırasında eski içeriğin soluklaşması (bayat veri hissi)

    CSS tabanlıdır → dosya yükleme, kaydetme, silme, sayfa geçişi, dialog…
    İSTİSNASIZ her işlemde otomatik devreye girer; buton başına kod gerekmez.
    app.py'de bir kez basılır, tüm modüller kapsanır.
    """
    return """<style>
@keyframes kyr-akan-bar{0%{background-position:0% 0}100%{background-position:200% 0}}
@keyframes kyr-puls{0%,100%{box-shadow:0 6px 22px color-mix(in srgb,var(--k-mor) 45%,transparent)}50%{box-shadow:0 6px 30px color-mix(in srgb,var(--k-cyan) 65%,transparent)}}
div[data-testid="stStatusWidget"]::before{
  content:"";position:fixed;top:0;left:0;right:0;height:3px;z-index:999999;
  background:linear-gradient(90deg,var(--k-mor),var(--k-cyan),var(--k-mor),var(--k-mor));
  background-size:200% 100%;animation:kyr-akan-bar 1.1s linear infinite;}
div[data-testid="stStatusWidget"]{
  position:fixed !important;top:14px !important;left:50% !important;
  transform:translateX(-50%) !important;z-index:999998 !important;
  background:color-mix(in srgb,var(--k-yuzey1) 96%,transparent) !important;border:1px solid color-mix(in srgb,var(--k-mor) 55%,transparent) !important;
  border-radius:999px !important;padding:8px 16px !important;
  animation:kyr-puls 1.3s ease-in-out infinite;}
div[data-testid="stStatusWidget"]::after{
  content:"⏳ İşleniyor — lütfen bekleyin";color:var(--k-mor2);font-size:13px;
  font-weight:700;letter-spacing:.3px;white-space:nowrap;}
div[data-testid="stStatusWidget"] > *{display:none !important;}
div[data-stale="true"]{opacity:.35 !important;transition:opacity .25s ease;}

/* ── Araç çubuğu gizli olsa bile çalışan KÖK gösterge ──
   Streamlit, script çalışırken uygulama köküne data-test-script-state="running"
   basar; bu her modda (Cloud izleyici dahil) mevcuttur. */
div[data-testid="stApp"][data-test-script-state="running"]::before{
  content:"";position:fixed;top:0;left:0;right:0;height:3px;z-index:999999;
  background:linear-gradient(90deg,var(--k-mor),var(--k-cyan),var(--k-mor),var(--k-mor));
  background-size:200% 100%;animation:kyr-akan-bar 1.1s linear infinite;}
div[data-testid="stApp"][data-test-script-state="running"]::after{
  content:"⏳ İşleniyor — lütfen bekleyin";
  position:fixed;top:14px;left:50%;transform:translateX(-50%);z-index:999998;
  background:color-mix(in srgb,var(--k-yuzey1) 96%,transparent);border:1px solid color-mix(in srgb,var(--k-mor) 55%,transparent);
  border-radius:999px;padding:8px 16px;
  color:var(--k-mor2);font-size:13px;font-weight:700;letter-spacing:.3px;white-space:nowrap;
  font-family:Inter,sans-serif;
  animation:kyr-puls 1.3s ease-in-out infinite;}
</style>"""


def token_css() -> str:
    """Tüm design token'ları CSS değişkeni olarak :root'a basar.
    app.py'de bir kez çağrılır. Bundan sonra hem CSS'te hem inline HTML'de
    var(--kyr-...) kullanılabilir → tek kaynaktan tema yönetimi."""
    _degiskenler = []
    for k, v in RENK.items():
        _degiskenler.append(f"--kyr-{k}:{v};")
    for k, v in BOSLUK.items():
        _degiskenler.append(f"--kyr-bosluk-{k}:{v};")
    for k, v in RADIUS.items():
        _degiskenler.append(f"--kyr-radius-{k}:{v};")
    for k, v in FONT.items():
        _degiskenler.append(f"--kyr-font-{k}:{v};")
    for k, v in GOLGE.items():
        _degiskenler.append(f"--kyr-golge-{k}:{v};")
    for k, v in GECIS.items():
        _degiskenler.append(f"--kyr-gecis-{k}:{v};")
    return "<style>:root{" + "".join(_degiskenler) + "}</style>"


def genel_tema_css() -> str:
    """Uygulama geneli görsel cila — app.py'de bir kez basılır.
    • Dialog başlıkları: zarif, kompakt, tutarlı
    • st.dataframe kapsayıcısı: kart hissi (yuvarlak köşe + ince çerçeve)
    • Sekme ve caption rafinesi
    Tablo İÇİ font/renk/grid çizgileri .streamlit/config.toml temasından gelir
    (canvas tabanlı olduğu için CSS ile değil tema ile yönetilir)."""
    return """<style>
/* ── Kart hover: hafif yükselme + gölge derinleşmesi (micro-interaction) ── */
.kyr-kart:hover{
  transform:translateY(-2px);
  box-shadow:0 6px 20px rgba(0,0,0,0.45), inset 0 1px 0 color-mix(in srgb,var(--k-metin) 6%,transparent) !important;
}
/* ── Dialog başlıkları ── */
div[data-testid="stDialog"] h1, div[data-testid="stDialog"] h2,
div[data-testid="stDialog"] h3, div[data-testid="stDialog"] [data-testid="stHeading"]{
  font-family:Inter,sans-serif !important;
  font-size:16px !important; font-weight:700 !important;
  letter-spacing:-0.2px !important; color:var(--k-metin) !important;
  padding-bottom:0px !important;
}
div[data-testid="stDialog"] > div:first-child{
  border:1px solid color-mix(in srgb,var(--k-mor) 22%,transparent) !important;
  border-radius:18px !important;
  box-shadow:0 24px 64px rgba(0,0,0,0.55) !important;
}
/* ── Tablolar: kapsayıcıya kart hissi ── */
div[data-testid="stDataFrame"]{
  border-radius:12px !important;
  overflow:hidden !important;
  border:1px solid color-mix(in srgb,var(--k-soluk) 10%,transparent) !important;
}
/* ── Sekmeler: alt çizgi yerine yumuşak aktif dolgu ── */
button[data-baseweb="tab"]{
  font-family:Inter,sans-serif !important; font-weight:600 !important;
  border-radius:9px 9px 0 0 !important;
}
button[data-baseweb="tab"][aria-selected="true"]{
  background:color-mix(in srgb,var(--k-mor) 10%,transparent) !important;
}
/* ── Caption'lar biraz daha okunur ── */
div[data-testid="stCaptionContainer"] p{ color:var(--k-soluk) !important; }
</style>"""


# Patron panosu Ekim 2026'da shared/patron.py'ye taşındı (yeniden tasarım).
