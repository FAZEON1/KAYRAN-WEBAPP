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
RENK = {
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
    "silik":    "#64748B",   # placeholder · boş durum
}

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
def sayfa_baslik(ikon: str, ad: str, alt: str = "") -> str:
    """26px kalın başlık + soluk alt açıklama + gradyan çizgi (tek standart)."""
    h = (f'<div style="font-size:26px;font-weight:800;color:{RENK["metin"]};'
         f'margin:2px 0 2px">{ikon} {ad}</div>')
    if alt:
        h += (f'<div style="color:{RENK["soluk"]};font-size:13px;'
              f'margin-bottom:6px">{alt}</div>')
    h += ('<div style="height:1px;background:linear-gradient(90deg,#6366F1,transparent);'
          'margin:6px 0 16px"></div>')
    return h


# ─────────────────────────────────────────────────────────────────────
# PENCERE — sabit yükseklik + iç scroll'lu kart (kompaktlığın çekirdeği)
# ─────────────────────────────────────────────────────────────────────
def pencere_css() -> str:
    """Pencere içi ince scrollbar stili — sayfada bir kez basılır."""
    return """<style>
.kyr-pencere-icerik{overflow-y:auto;padding-right:6px;}
.kyr-pencere-icerik::-webkit-scrollbar{width:6px;}
.kyr-pencere-icerik::-webkit-scrollbar-track{background:rgba(255,255,255,0.03);border-radius:3px;}
.kyr-pencere-icerik::-webkit-scrollbar-thumb{background:rgba(148,163,184,0.35);border-radius:3px;}
.kyr-pencere-icerik::-webkit-scrollbar-thumb:hover{background:rgba(148,163,184,0.55);}
</style>"""


def pencere(baslik: str, renk: str, icerik_html: str,
            rozet: str = "", yukseklik: int = 250, min_genislik: int = 300) -> str:
    """Başlık + (isteğe bağlı rozet) + iç scroll'lu içerik alanı olan kart.

    `pencere_grid()` içine konur; yan yana dizilir, dar ekranda alta sarar.
    """
    roz = ""
    if rozet:
        roz = (f'<span style="background:{renk}26;color:{renk};padding:1px 9px;'
               f'border-radius:20px;font-size:11.5px;font-weight:700;">{rozet}</span>')
    return (
        f'<div style="flex:1;min-width:{min_genislik}px;background:rgba(255,255,255,0.02);'
        f'border:1px solid {renk}40;border-left:3px solid {renk}99;border-radius:14px;'
        f'padding:12px 14px;display:flex;flex-direction:column;">'
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;flex-shrink:0;">'
        f'<span style="font-size:13px;font-weight:800;color:{renk};letter-spacing:.3px;">{baslik}</span>'
        f'{roz}</div>'
        f'<div class="kyr-pencere-icerik" style="max-height:{yukseklik}px;">{icerik_html}</div>'
        f'</div>'
    )


def pencere_grid(*penceler: str, alt_bosluk: int = 4) -> str:
    """Pencereleri yan yana dizen esnek kapsayıcı (dar ekranda alta sarar)."""
    return (f'<div style="display:flex;gap:12px;flex-wrap:wrap;align-items:stretch;'
            f'margin:10px 0 {alt_bosluk}px;">' + "".join(penceler) + '</div>')


def pencere_satiri(sol_html: str, sag_html: str = "") -> str:
    """Pencere içinde kompakt liste satırı: solda metin, sağda rozet/değer."""
    sag = ""
    if sag_html:
        sag = (f'<div style="display:flex;gap:12px;flex-shrink:0;margin-left:10px;'
               f'align-items:center;">{sag_html}</div>')
    return (f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:5px 10px;margin:3px 0;border-radius:6px;'
            f'background:rgba(255,255,255,0.03);">{sol_html}{sag}</div>')


def bos_durum(mesaj: str) -> str:
    """Pencere boşken düzeni koruyan sakin placeholder."""
    return (f'<div style="color:{RENK["silik"]};font-size:12px;'
            f'padding:14px 4px;">✓ {mesaj}</div>')


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
@keyframes kyr-puls{0%,100%{box-shadow:0 6px 22px rgba(99,102,241,.45)}50%{box-shadow:0 6px 30px rgba(34,211,238,.65)}}
div[data-testid="stStatusWidget"]::before{
  content:"";position:fixed;top:0;left:0;right:0;height:3px;z-index:999999;
  background:linear-gradient(90deg,#6366F1,#22D3EE,#818CF8,#6366F1);
  background-size:200% 100%;animation:kyr-akan-bar 1.1s linear infinite;}
div[data-testid="stStatusWidget"]{
  position:fixed !important;top:14px !important;left:50% !important;
  transform:translateX(-50%) !important;z-index:999998 !important;
  background:rgba(15,23,42,.96) !important;border:1px solid rgba(99,102,241,.55) !important;
  border-radius:999px !important;padding:7px 18px !important;
  animation:kyr-puls 1.3s ease-in-out infinite;}
div[data-testid="stStatusWidget"]::after{
  content:"⏳ İşleniyor — lütfen bekleyin";color:#C7D2FE;font-size:13px;
  font-weight:700;letter-spacing:.3px;white-space:nowrap;}
div[data-testid="stStatusWidget"] > *{display:none !important;}
div[data-stale="true"]{opacity:.35 !important;transition:opacity .25s ease;}
</style>"""


def genel_tema_css() -> str:
    """Uygulama geneli görsel cila — app.py'de bir kez basılır.
    • Dialog başlıkları: zarif, kompakt, tutarlı
    • st.dataframe kapsayıcısı: kart hissi (yuvarlak köşe + ince çerçeve)
    • Sekme ve caption rafinesi
    Tablo İÇİ font/renk/grid çizgileri .streamlit/config.toml temasından gelir
    (canvas tabanlı olduğu için CSS ile değil tema ile yönetilir)."""
    return """<style>
/* ── Dialog başlıkları ── */
div[data-testid="stDialog"] h1, div[data-testid="stDialog"] h2,
div[data-testid="stDialog"] h3, div[data-testid="stDialog"] [data-testid="stHeading"]{
  font-family:Inter,sans-serif !important;
  font-size:17px !important; font-weight:800 !important;
  letter-spacing:-0.2px !important; color:#E2E8F0 !important;
  padding-bottom:2px !important;
}
div[data-testid="stDialog"] > div:first-child{
  border:1px solid rgba(129,140,248,0.22) !important;
  border-radius:18px !important;
  box-shadow:0 24px 64px rgba(0,0,0,0.55) !important;
}
/* ── Tablolar: kapsayıcıya kart hissi ── */
div[data-testid="stDataFrame"]{
  border-radius:12px !important;
  overflow:hidden !important;
  border:1px solid rgba(148,163,184,0.10) !important;
}
/* ── Sekmeler: alt çizgi yerine yumuşak aktif dolgu ── */
button[data-baseweb="tab"]{
  font-family:Inter,sans-serif !important; font-weight:600 !important;
  border-radius:9px 9px 0 0 !important;
}
button[data-baseweb="tab"][aria-selected="true"]{
  background:rgba(99,102,241,0.10) !important;
}
/* ── Caption'lar biraz daha okunur ── */
div[data-testid="stCaptionContainer"] p{ color:#8B98B8 !important; }
</style>"""
