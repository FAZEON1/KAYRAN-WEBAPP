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
    # ── Yüzey katmanları (derinlik) — en koyudan açığa ──
    "yuzey0":   "#0B1120",   # en dip zemin (sayfa arka planı)
    "yuzey1":   "#0F172A",   # kart zemini (1. katman)
    "yuzey2":   "#152036",   # öne çıkan kart / hover (2. katman)
    "yuzey3":   "#1C2A44",   # en öndeki eleman (3. katman)
    "kenar":    "rgba(148,163,184,0.10)",  # ince ayırıcı kenar
    "kenar2":   "rgba(148,163,184,0.18)",  # belirgin kenar
}

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
def sayfa_baslik(ikon: str, ad: str, alt: str = "") -> str:
    """Profesyonel sayfa başlığı: küçük ikon karosu + 19px başlık + hizalı
    alt yazı + kısa indigo aksanlı ince ayraç. Tüm modüllerde tek standart."""
    h = (
        '<div style="display:flex;align-items:center;gap:11px;margin:2px 0 0">'
        '<div style="width:30px;height:30px;border-radius:9px;flex-shrink:0;'
        'background:linear-gradient(135deg,rgba(99,102,241,0.28),rgba(139,92,246,0.16));'
        'border:1px solid rgba(129,140,248,0.28);display:flex;align-items:center;'
        f'justify-content:center;font-size:14px">{ikon}</div>'
        '<div style="font-family:Inter,sans-serif;font-size:19px;font-weight:750;'
        f'color:#F1F5F9;letter-spacing:-0.3px;line-height:1.25">{ad}</div>'
        '</div>'
    )
    alt_txt = alt or ""
    h += (
        '<div style="font-size:12.5px;color:#7C8AA0;font-weight:450;letter-spacing:.1px;'
        'margin:7px 0 18px;padding:0 0 12px 41px;position:relative;'
        'border-bottom:1px solid rgba(148,163,184,0.10)">'
        '<span style="position:absolute;left:41px;bottom:-1px;width:40px;height:2px;'
        'border-radius:2px;background:linear-gradient(90deg,#6366F1,#8B5CF6)"></span>'
        f'{alt_txt}</div>'
    )
    return h


# ─────────────────────────────────────────────────────────────────────
# PENCERE — sabit yükseklik + iç scroll'lu kart (kompaktlığın çekirdeği)
# ─────────────────────────────────────────────────────────────────────
def pencere_css() -> str:
    """Pencere içi ince scrollbar stili — sayfada bir kez basılır."""
    return """<style>
.kyr-pencere-icerik{overflow-y:auto;padding-right:8px;}
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
        roz = (f'<span style="background:{renk}26;color:{renk};padding:4px 8px;'
               f'border-radius:20px;font-size:11px;font-weight:700;">{rozet}</span>')
    return (
        f'<div class="kyr-kart" style="flex:1;min-width:{min_genislik}px;'
        f'background:linear-gradient(180deg,{RENK["yuzey2"]},{RENK["yuzey1"]});'
        f'border:1px solid {renk}33;border-left:3px solid {renk};border-radius:16px;'
        f'padding:12px 16px;display:flex;flex-direction:column;'
        f'box-shadow:{GOLGE["kart"]};transition:transform {GECIS["hizli"]},box-shadow {GECIS["hizli"]};">'
        f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;flex-shrink:0;">'
        f'<span style="font-size:13px;font-weight:800;color:{renk};letter-spacing:.3px;">{baslik}</span>'
        f'{roz}</div>'
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
            f'background:rgba(255,255,255,0.03);">{sol_html}{sag}</div>')


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
@keyframes kyr-puls{0%,100%{box-shadow:0 6px 22px rgba(99,102,241,.45)}50%{box-shadow:0 6px 30px rgba(34,211,238,.65)}}
div[data-testid="stStatusWidget"]::before{
  content:"";position:fixed;top:0;left:0;right:0;height:3px;z-index:999999;
  background:linear-gradient(90deg,#6366F1,#22D3EE,#818CF8,#6366F1);
  background-size:200% 100%;animation:kyr-akan-bar 1.1s linear infinite;}
div[data-testid="stStatusWidget"]{
  position:fixed !important;top:14px !important;left:50% !important;
  transform:translateX(-50%) !important;z-index:999998 !important;
  background:rgba(15,23,42,.96) !important;border:1px solid rgba(99,102,241,.55) !important;
  border-radius:999px !important;padding:8px 16px !important;
  animation:kyr-puls 1.3s ease-in-out infinite;}
div[data-testid="stStatusWidget"]::after{
  content:"⏳ İşleniyor — lütfen bekleyin";color:#C7D2FE;font-size:13px;
  font-weight:700;letter-spacing:.3px;white-space:nowrap;}
div[data-testid="stStatusWidget"] > *{display:none !important;}
div[data-stale="true"]{opacity:.35 !important;transition:opacity .25s ease;}

/* ── Araç çubuğu gizli olsa bile çalışan KÖK gösterge ──
   Streamlit, script çalışırken uygulama köküne data-test-script-state="running"
   basar; bu her modda (Cloud izleyici dahil) mevcuttur. */
div[data-testid="stApp"][data-test-script-state="running"]::before{
  content:"";position:fixed;top:0;left:0;right:0;height:3px;z-index:999999;
  background:linear-gradient(90deg,#6366F1,#22D3EE,#818CF8,#6366F1);
  background-size:200% 100%;animation:kyr-akan-bar 1.1s linear infinite;}
div[data-testid="stApp"][data-test-script-state="running"]::after{
  content:"⏳ İşleniyor — lütfen bekleyin";
  position:fixed;top:14px;left:50%;transform:translateX(-50%);z-index:999998;
  background:rgba(15,23,42,.96);border:1px solid rgba(99,102,241,.55);
  border-radius:999px;padding:8px 16px;
  color:#C7D2FE;font-size:13px;font-weight:700;letter-spacing:.3px;white-space:nowrap;
  font-family:Inter,sans-serif;
  animation:kyr-puls 1.3s ease-in-out infinite;}
</style>"""


def tema_tipi() -> str:
    """Aktif tema: 'light' | 'dark'. Kullanıcının ⋮ → Settings seçimini
    st.context.theme ile algılar (Streamlit ≥1.46). Algılanamazsa 'dark'."""
    try:
        _t = getattr(st.context, "theme", None)
        if _t is not None and getattr(_t, "type", "dark") == "light":
            return "light"
    except Exception:
        pass
    return "dark"


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
  box-shadow:0 6px 20px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.06) !important;
}
/* ── Dialog başlıkları ── */
div[data-testid="stDialog"] h1, div[data-testid="stDialog"] h2,
div[data-testid="stDialog"] h3, div[data-testid="stDialog"] [data-testid="stHeading"]{
  font-family:Inter,sans-serif !important;
  font-size:17px !important; font-weight:800 !important;
  letter-spacing:-0.2px !important; color:#E2E8F0 !important;
  padding-bottom:0px !important;
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


# ─────────────────────────────────────────────────────────────────────
# PATRON PANOSU — sabah kokpiti (yalnız yetkili kullanıcıya render edilir)
# ─────────────────────────────────────────────────────────────────────
import streamlit as st


@st.cache_data(ttl=120, show_spinner=False)
def patron_verisi_topla():
    """Tüm modüllerden sabah kokpiti verisini HATAYA DAYANIKLI toplar.
    Her blok kendi try/except'inde — biri patlasa panel yine açılır.
    Döner: dict (aşağıdaki anahtarlar; eksik olan None kalır)."""
    import datetime as _dt
    v = {}

    # ── İş nabzı: bu ay ciro/kâr/marj — TEK KAYNAK: v_satis_pnl (yoksa Python) ──
    try:
        from satis.database import (get_satislar, ozet_hesapla,
                                    get_satis_pnl_view, ozet_from_view)
        _bugun = _dt.date.today()
        _ay_ilk = _bugun.replace(day=1).isoformat()
        _vr_p = get_satis_pnl_view(_ay_ilk, _bugun.isoformat())
        if _vr_p is not None:
            _top, _kanal, _ = ozet_from_view(_vr_p)
        else:
            _top, _kanal, _ = ozet_hesapla(get_satislar(_ay_ilk, _bugun.isoformat()))
        v["ay_ciro"] = float(_top.get("ciro", 0) or 0)
        v["ay_kar"] = float(_top.get("net_kar", 0) or 0)
        v["ay_marj"] = float(_top.get("marj", 0) or 0)
    except Exception:
        pass

    # ── Toplam aktifler (muhasebe snapshot) ──
    try:
        from kayranacc.database import get_ayar
        _snap = get_ayar("toplam_aktif_snapshot")
        if _snap:
            v["toplam_aktif"] = float(_snap.get("toplam", 0) or 0)
            v["toplam_aktif_tarih"] = str(_snap.get("tarih", ""))[:10]
    except Exception:
        pass

    # ── Acil sipariş + kritik stoklar (ürün yönetimi) ──
    try:
        from kayranpm.analitik import dashboard_hesapla
        _veri = dashboard_hesapla() or []
        _acil = [u for u in _veri if u.get("siparis_durum") == "acil"]
        v["acil_sayi"] = len(_acil)
        v["acil_liste"] = [{"ad": (u.get("urun_adi") or u.get("sku") or "—")[:40],
                            "gun": u.get("stok_bitis_gun", "?"),
                            "stok": u.get("toplam_stok", u.get("bizim_stok", 0))}
                           for u in _acil[:6]]
        _yak = [u for u in _veri if u.get("siparis_durum") == "yaklasıyor"]
        v["yaklasan_sayi"] = len(_yak)
    except Exception:
        pass

    # ── Bugün vadeli + gecikmiş ödemeler (muhasebe) ──
    try:
        from kayranacc.database import get_aktif_odemeler
        from shared.utils import vade_durumu
        _odm, _ = get_aktif_odemeler()
        _bek = [o for o in (_odm or []) if o.get("durum") == "bekliyor"]
        v["odeme_bugun"] = sum(1 for o in _bek if vade_durumu(o.get("vade")) == "bugun")
        v["odeme_gecikmis"] = sum(1 for o in _bek if vade_durumu(o.get("vade")) == "gecmis")
        _bugvad = [o for o in _bek if vade_durumu(o.get("vade")) in ("bugun", "gecmis")]
        v["odeme_liste"] = [{"firma": o.get("firma", "—"),
                             "durum": vade_durumu(o.get("vade")),
                             "tl": float(o.get("tutar_tl") or 0),
                             "usd": float(o.get("tutar_usd") or 0)} for o in _bugvad[:6]]
    except Exception:
        pass

    # ── Gümrükte/yolda ithalatlar ──
    try:
        from ithalat.database import get_dosyalar, IN_TRANSIT_DURUMLAR
        _dos = get_dosyalar() or []
        _yolda = [d for d in _dos if str(d.get("durum", "")).strip() in IN_TRANSIT_DURUMLAR]
        v["ithalat_yolda"] = len(_yolda)
        _durum_say = {}
        for d in _yolda:
            _du = str(d.get("durum", "")).strip()
            _durum_say[_du] = _durum_say.get(_du, 0) + 1
        v["ithalat_durum"] = _durum_say
    except Exception:
        pass

    # ── Teknik servis: SLA aşan (21 iş günü) açık işler ──
    try:
        from teknikservis.database import get_kayitlar, is_gunu_farki, BITMIS_DURUMLAR
        _tsk = get_kayitlar() or []
        _acik_ts = [k for k in _tsk if str(k.get("durum", "")) not in BITMIS_DURUMLAR]
        _sla_asan = []
        for k in _acik_ts:
            try:
                _g = is_gunu_farki(k.get("mal_kabul_tarihi") or k.get("kayit_tarihi"))
                if _g is not None and _g > 21:
                    _sla_asan.append({"no": k.get("servis_no", "—"),
                                      "firma": (k.get("firma", "") or "—")[:24], "gun": _g})
            except Exception:
                continue
        v["ts_acik"] = len(_acik_ts)
        v["ts_sla_asan"] = sorted(_sla_asan, key=lambda x: -x["gun"])[:6]
    except Exception:
        pass

    # ── Hatalı veri: %100 marjlı (maliyetsiz) satış + eksi stok ──
    try:
        from satis.database import get_satislar, get_pacal_map
        import re as _re2
        def _nsku(x):
            return _re2.sub(r"[^A-Z0-9]", "", str(x or "").upper())
        _pacal = {}
        try:
            for _k, _pv in (get_pacal_map() or {}).items():
                _pacal[_nsku(_k)] = _pv
        except Exception:
            _pacal = {}
        _bugun = _dt.date.today()
        _yil_ilk = _bugun.replace(month=1, day=1).isoformat()
        _sat = get_satislar(_yil_ilk, _bugun.isoformat()) or []
        _mz_onarilir = 0   # maliyet 0 AMA paçalı biliniyor → tek tıkla düzelir
        _mz_ithalatsiz = 0  # maliyet 0 VE paçalı yok → ithalat/eşleşme sorunu
        for s in _sat:
            if float(s.get("birim_maliyet") or 0) <= 0 and int(s.get("adet") or 0) > 0:
                if float(_pacal.get(_nsku(s.get("sku")), 0) or 0) > 0:
                    _mz_onarilir += 1
                else:
                    _mz_ithalatsiz += 1
        v["maliyetsiz_satis"] = _mz_onarilir + _mz_ithalatsiz
        v["maliyetsiz_onarilir"] = _mz_onarilir
        v["maliyetsiz_ithalatsiz"] = _mz_ithalatsiz
    except Exception:
        pass
    try:
        from kayranpm.analitik import dashboard_hesapla
        _veri = v.get("_dash_cache") or (dashboard_hesapla() or [])
        v["eksi_stok"] = sum(1 for u in _veri if float(u.get("toplam_stok", 0) or 0) < 0)
    except Exception:
        pass

    # ── Kritik değişiklikler (son 24 saat audit log) ──
    try:
        from shared.audit import get_loglar
        _bugun = _dt.date.today()
        _dun = (_bugun - _dt.timedelta(days=1)).isoformat()
        _loglar = get_loglar(limit=200, baslangic=_dun) or []
        _kritik = []
        for l in _loglar:
            _islem = str(l.get("islem", "")).lower()
            _tablo = str(l.get("tablo", "")).lower()
            _detay = str(l.get("detay", ""))
            _onemli = (
                "sil" in _islem or
                ("yükle" in _islem or "import" in _islem or "toplu" in _islem) or
                (_tablo in ("odemeler", "satislar", "cekler", "bankalar") and "güncelle" in _islem)
            )
            if _onemli:
                _kritik.append({
                    "zaman": str(l.get("zaman", ""))[:16],
                    "kullanici": (l.get("kullanici", "") or "?").capitalize(),
                    "islem": l.get("islem", ""),
                    "modul": l.get("modul", "") or l.get("tablo", ""),
                    "detay": _detay[:60],
                })
        v["kritik_sayi"] = len(_kritik)
        v["kritik_liste"] = _kritik[:8]
    except Exception:
        pass

    # ── Günlük trend (mv_gunluk_pnl — son 30 gün) ──
    try:
        from satis.database import get_gunluk_pnl
        _tr = get_gunluk_pnl(30)
        if _tr:
            v["trend"] = [{"tarih": str(r.get("tarih"))[:10],
                           "ciro": float(r.get("ciro") or 0),
                           "net_kar": float(r.get("net_kar") or 0)} for r in _tr]
            if len(_tr) >= 2:
                v["trend_bugun_ciro"] = float(_tr[-1].get("ciro") or 0)
                v["trend_dun_ciro"] = float(_tr[-2].get("ciro") or 0)
    except Exception:
        pass

    # ── Kanal büyüme içgörüsü (mv_kanal_ay_pnl — bu ay vs geçen ay) ──
    # ── Büyüme içgörüsü KALDIRILDI (kullanıcı talebi: En Çok Büyüyen/Gerileyen
    #    kartları gösterilmesin). get_kanal_buyume 2 aylık satış taraması yapan
    #    ağır bir sorguydu — kaldırılması ana sayfayı da hızlandırır.

    return v


def patron_panosu_html(v):
    """patron_verisi_topla çıktısını kompakt kokpit HTML'ine çevirir.
    st.markdown(..., unsafe_allow_html=True) ile basılır."""
    def _fmt(x):
        try:
            return f"{float(x):,.0f}"
        except Exception:
            return "0"

    # ── Üst şerit: iş nabzı (4 metrik) ──
    _nabiz = []
    if "ay_ciro" in v:
        _kr = RENK["yesil"] if v.get("ay_kar", 0) >= 0 else RENK["kirmizi"]
        _nabiz.append(("BU AY CİRO", f"${_fmt(v['ay_ciro'])}", RENK["mor2"]))
        _nabiz.append(("BU AY NET KÂR", f"${_fmt(v['ay_kar'])}", _kr))
        _nabiz.append(("MARJ", f"%{v.get('ay_marj', 0):.1f}", _kr))
    if "toplam_aktif" in v:
        _nabiz.append(("TOPLAM AKTİF", f"${_fmt(v['toplam_aktif'])}", RENK["cyan"]))
    _nabiz_html = "".join(
        f'<div class="kyr-kart" style="flex:1;min-width:120px;text-align:center;padding:12px 8px;'
        f'background:linear-gradient(180deg,{RENK["yuzey2"]},{RENK["yuzey1"]});border:1px solid {c}2E;border-radius:12px;box-shadow:{GOLGE["kart"]};transition:transform {GECIS["hizli"]}">'
        f'<div style="font-size:11px;color:{RENK["soluk"]};letter-spacing:1px;'
        f'text-transform:uppercase;font-weight:700;margin-bottom:4px">{lbl}</div>'
        f'<div style="color:{c};font-size:23px;font-weight:800;'
        f'font-family:JetBrains Mono,monospace;letter-spacing:-0.5px">{val}</div></div>'
        for lbl, val, c in _nabiz)

    def _pencere(baslik, renk, ic, rozet=""):
        return pencere(baslik, renk, ic, rozet=rozet, yukseklik=190)

    def _satir(sol, sag_html):
        return pencere_satiri(
            f'<span style="color:{RENK["metin"]};font-size:13px;font-weight:600">{sol}</span>',
            sag_html)

    # ── Pencere 1: Acil sipariş ──
    if v.get("acil_liste"):
        _ic = "".join(_satir(
            f'⚡ {a["ad"]}',
            f'<span style="color:{RENK["soluk"]};font-size:11px">📦 {_fmt(a["stok"])}</span>'
            f'<span style="color:{RENK["kirmizi"]};font-size:11px;font-weight:700">{a["gun"]}g</span>')
            for a in v["acil_liste"])
        _p1 = _pencere("🔴 ACİL SİPARİŞ", RENK["kirmizi"], _ic,
                       rozet=f"{v.get('acil_sayi', 0)} ürün")
    else:
        _p1 = _pencere("🔴 ACİL SİPARİŞ", RENK["kirmizi"],
                       bos_durum("Acil sipariş gereken ürün yok"), rozet="0")

    # ── Pencere 2: Ödemeler ──
    if v.get("odeme_liste"):
        _ic = "".join(_satir(
            ("🚨 " if o["durum"] == "gecmis" else "⚠️ ") + o["firma"],
            f'<span style="color:{RENK["amber"] if o["durum"]=="bugun" else RENK["kirmizi"]};'
            f'font-size:11px;font-weight:700">'
            f'{("₺"+_fmt(o["tl"])) if o["tl"] else ("$"+_fmt(o["usd"]))}</span>')
            for o in v["odeme_liste"])
        _rz = f"{v.get('odeme_gecikmis',0)} geç · {v.get('odeme_bugun',0)} bugün"
        _p2 = _pencere("💳 VADELİ ÖDEMELER", RENK["amber"], _ic, rozet=_rz)
    else:
        _p2 = _pencere("💳 VADELİ ÖDEMELER", RENK["amber"],
                       bos_durum("Bugün/gecikmiş ödeme yok"), rozet="0")

    # ── Pencere 3: İthalat ──
    if v.get("ithalat_durum"):
        _ic = "".join(_satir(
            f'🚢 {du}',
            f'<span style="color:{RENK["mavi"]};font-size:13px;font-weight:700">{n}</span>')
            for du, n in sorted(v["ithalat_durum"].items(), key=lambda x: -x[1]))
        _p3 = _pencere("🚢 YOLDA İTHALAT", RENK["mavi"], _ic,
                       rozet=f"{v.get('ithalat_yolda', 0)} dosya")
    else:
        _p3 = _pencere("🚢 YOLDA İTHALAT", RENK["mavi"],
                       bos_durum("Yolda/gümrükte dosya yok"), rozet="0")

    # ── Pencere 4: Teknik servis SLA ──
    if v.get("ts_sla_asan"):
        _ic = "".join(_satir(
            f'🔧 {t["firma"]} · {t["no"]}',
            f'<span style="color:{RENK["kirmizi"]};font-size:11px;font-weight:700">{t["gun"]}g</span>')
            for t in v["ts_sla_asan"])
        _p4 = _pencere("🔧 SLA AŞAN SERVİS", RENK["pembe"], _ic,
                       rozet=f"{len(v['ts_sla_asan'])} iş")
    else:
        _p4 = _pencere("🔧 SLA AŞAN SERVİS", RENK["pembe"],
                       bos_durum("21 iş gününü aşan servis yok"), rozet="0")

    # ── Hatalı veri şeridi ──
    _hata_parca = []
    if v.get("maliyetsiz_onarilir"):
        _hata_parca.append(f'<span style="color:{RENK["amber2"]}">🔧 {v["maliyetsiz_onarilir"]:,} '
                           f'satış tek tıkla onarılır (Kâr/P&L → Maliyeti 0 düzelt)</span>')
    if v.get("maliyetsiz_ithalatsiz"):
        _hata_parca.append(f'<span style="color:{RENK["kirmizi2"]}">🚫 {v["maliyetsiz_ithalatsiz"]:,} '
                           f'satış ithalatsız/eşleşmiyor (%100 marj — ithalat gir ya da SKU düzelt)</span>')
    if v.get("eksi_stok"):
        _hata_parca.append(f'<span style="color:{RENK["kirmizi2"]}">📉 {v["eksi_stok"]:,} '
                           f'ürün eksi stokta</span>')
    _hata_html = ""
    if _hata_parca:
        _hata_html = (f'<div style="background:rgba(248,113,113,0.06);border:1px solid '
                      f'{RENK["kirmizi"]}30;border-radius:10px;padding:8px 16px;margin:4px 0 0;'
                      f'font-size:13px">⚠️ <b style="color:{RENK["kirmizi2"]}">Dikkat:</b> '
                      + " &nbsp;·&nbsp; ".join(_hata_parca) + '</div>')

    # ── Kritik değişiklikler şeridi (son 24 saat) ──
    _kritik_html = ""
    if v.get("kritik_liste"):
        _kr_ic = "".join(
            pencere_satiri(
                f'<span style="color:{RENK["metin"]};font-size:11px;font-weight:600">'
                f'{k["kullanici"]} · <span style="color:{RENK["soluk"]}">{k["islem"]} '
                f'· {k["modul"]}</span></span>',
                f'<span style="color:{RENK["silik"]};font-size:11px">{k["zaman"]}</span>')
            for k in v["kritik_liste"])
        _kritik_html = pencere_grid(
            pencere("🔔 SON 24 SAAT — KRİTİK İŞLEMLER", RENK["cyan"], _kr_ic,
                    rozet=f"{v.get('kritik_sayi', 0)} işlem", yukseklik=170))

    # ── 📈 30 günlük ciro trendi (sparkline + değer etiketleri) ──
    _trend_html = ""
    if v.get("trend") and len(v["trend"]) >= 2:
        _pts = v["trend"]
        _cirolar = [p["ciro"] for p in _pts]
        _mx = max(_cirolar) or 1
        _mn = min(_cirolar)
        _rng = (_mx - _mn) or 1
        _W, _H = 680, 96          # etiketlere yer açmak için yükseklik artırıldı
        _UST = 26                 # üstte etiket bandı
        _n = len(_pts)
        _coords = []
        for _i, _c in enumerate(_cirolar):
            _x = (_i / (_n - 1)) * _W
            _y = _H - ((_c - _mn) / _rng) * (_H - _UST - 8) - 4
            _coords.append((_x, _y))
        _poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in _coords)
        _alan = f"0,{_H} " + _poly + f" {_W},{_H}"
        _son_x, _son_y = _coords[-1]

        # Değer etiketleri: her günün cirosu kompakt formatta ("12.4K" / "980").
        # Üst üste binmesin diye iki sırada dönüşümlü (zikzak) yerleştirilir.
        def _kfmt(_c):
            if _c >= 100000:
                return f"{_c/1000:,.0f}K"
            if _c >= 1000:
                return f"{_c/1000:.1f}K".replace(".0K", "K")
            return f"{_c:,.0f}"
        _lbl = ""
        for _i, ((_x, _y), _c) in enumerate(zip(_coords, _cirolar)):
            if _c <= 0:
                continue                      # sıfır gün etiketi kalabalık yapmasın
            _ly = _y - (7 if _i % 2 == 0 else 17)   # zikzak: iki sıra
            _ly = max(_ly, 8)                       # üstten taşma
            _anchor = "start" if _i == 0 else ("end" if _i == _n - 1 else "middle")
            _lbl += (f'<text x="{_x:.1f}" y="{_ly:.1f}" text-anchor="{_anchor}" '
                     f'font-size="8" font-family="JetBrains Mono,monospace" '
                     f'fill="#94A3B8">{_kfmt(_c)}</text>')

        # dün vs bugün delta
        _db = v.get("trend_bugun_ciro", 0); _dd = v.get("trend_dun_ciro", 0)
        _delta_html = ""
        if _dd:
            _dp = (_db - _dd) / _dd * 100
            _dc = RENK["yesil"] if _dp >= 0 else RENK["kirmizi"]
            _delta_html = (f'<span style="color:{_dc};font-size:13px;font-weight:700">'
                           f'{"▲" if _dp>=0 else "▼"} %{abs(_dp):.0f} <span style="color:{RENK["silik"]};'
                           f'font-weight:400;font-size:11px">düne göre</span></span>')
        _trend_html = (
            f'<div class="kyr-kart" style="background:linear-gradient(180deg,{RENK["yuzey2"]},{RENK["yuzey1"]});border:1px solid {RENK["kenar2"]};'
            f'border-radius:16px;padding:12px 16px;margin:4px 0 12px;box-shadow:{GOLGE["kart"]}">'
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">'
            f'<span style="font-size:11px;color:{RENK["soluk"]};letter-spacing:1px;text-transform:uppercase;'
            f'font-weight:700">📈 Son 30 Gün — Günlük Ciro</span>{_delta_html}</div>'
            f'<svg viewBox="0 0 {_W} {_H}" preserveAspectRatio="xMidYMid meet" '
            f'style="display:block;width:100%;height:auto">'
            f'<defs><linearGradient id="kyr-trend-g" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="#6366F1" stop-opacity="0.35"/>'
            f'<stop offset="100%" stop-color="#6366F1" stop-opacity="0"/></linearGradient></defs>'
            f'<polygon points="{_alan}" fill="url(#kyr-trend-g)"/>'
            f'<polyline points="{_poly}" fill="none" stroke="#818CF8" stroke-width="2" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
            f'{_lbl}'
            f'<circle cx="{_son_x:.1f}" cy="{_son_y:.1f}" r="3.5" fill="#22D3EE"/>'
            f'</svg></div>')

    # 🚀/📉 Büyüyen-Gerileyen firma kartları kullanıcı talebiyle kaldırıldı.

    return (
        '<div style="margin:0 0 24px">'
        '<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">'
        f'<span style="font-size:19px;font-weight:800;color:{RENK["metin"]}">👑 Patron Panosu</span>'
        f'<span style="color:{RENK["silik"]};font-size:11px">yalnızca sana özel · sabah kokpiti</span>'
        '</div>'
        + (f'<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:8px">{_nabiz_html}</div>'
           if _nabiz_html else "")
        + _trend_html
        + pencere_grid(_p1, _p2)
        + pencere_grid(_p3, _p4)
        + _hata_html
        + _kritik_html
        + '</div>'
    )
