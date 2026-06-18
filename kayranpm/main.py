"""
KAYRAN — Ürün & Stok Yönetim Sistemi
Modüler olarak KAYRAN portal içinden çağrılır.

Kullanım:
    from kayranpm.main import run
    run()
"""
import streamlit as st
import logging
_log = logging.getLogger(__name__)
# Türkiye saat dilimi için ortak yardımcılar
from shared.utils import tr_today, tr_now, tr_now_str, tr_tomorrow, tr_yesterday as _tr_today_iso_dummy
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os, sys
from datetime import datetime, date
from io import BytesIO

# Modül bazlı importlar (relative)
from .database import (initialize_db, onayla_siparis, reddet_siparis,
                      get_siparis_onerileri, ekle_siparis_onerisi,
                      get_gecmis_satis_firma_bazli, get_urun_detay,
                      ekle_satin_alma, guncelle_satin_alma, sil_satin_alma,
                      get_satin_alma_gecmisi, get_tum_tedarikciler,
                      ekle_kampanya, get_kampanyalar, get_kampanya,
                      guncelle_kampanya, kapat_kampanya, sil_kampanya,
                      ekle_kampanya_urun, get_kampanya_urunler,
                      guncelle_kampanya_urun, sil_kampanya_urun,
                      sil_urun, get_tum_sku_listesi, get_client,
                      get_gecmis_satis_tum_firmalar,
                      get_kampanya_destek_ortalamalari)
from .analitik import dashboard_hesapla, genel_analiz_hesapla, tum_urunler_listesi, siparis_onerisi_listesi
from .excel_islemler import (excel_yukle_ana_stok, excel_yukle_firma_stoklari,
                            excel_yukle_yoldaki_urunler, create_sample_excel_bytes)
from .bildirim import (get_bildirim_ayarlari, kaydet_bildirim_ayarlari, email_gonder)


def render_renkli_tablo(df, para=None, yuzde=None, kar=None, sol=None,
                        kisalt=None, gizle=None, satir_durum=None):
    """Bir DataFrame'i KAYRAN renkli HTML tablo temasinda (salt-okunur) cizer."""
    para = set(para or []); yuzde = set(yuzde or []); kar = set(kar or [])
    sol = set(sol or []); kisalt = kisalt or {}; gizle = set(gizle or [])
    if df is None or len(df) == 0:
        st.info("Gosterilecek veri yok.")
        return
    durum_kolon, durum_harita = (satir_durum or (None, {}))
    kolonlar = [c for c in df.columns if c not in gizle]

    def _isnum(c):
        try:
            return pd.api.types.is_numeric_dtype(df[c])
        except Exception:
            return False

    def _sag(c):
        return (c in para or c in yuzde or _isnum(c)) and c not in sol

    def _fmt(c, v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "\u2014"
        try:
            if c in para:
                return f"${float(v):,.2f}"
            if c in yuzde:
                return f"%{float(v):.1f}"
            if _isnum(c):
                fv = float(v)
                return f"{int(fv):,}" if fv == int(fv) else f"{fv:,.2f}"
        except Exception:
            pass
        s = str(v)
        mx = kisalt.get(c)
        return (s[:mx-1] + "\u2026") if (mx and len(s) > mx) else s

    rows_html = ""
    for _, row in df.iterrows():
        drenk = durum_harita.get(str(row.get(durum_kolon, "")), "") if durum_kolon else ""
        tds = ""
        for c in kolonlar:
            v = row[c]
            base = "rk-num" if _sag(c) else "rk-txt"
            cls = base
            if c in kar:
                try:
                    fv = float(v)
                    cls = "rk-pos" if fv > 0 else ("rk-neg" if fv < 0 else "rk-num")
                except Exception:
                    cls = "rk-num"
            elif drenk:
                cls = base + " " + drenk
            full = str(v)
            mx = kisalt.get(c)
            ttl = f' title="{full.replace(chr(34), "&quot;")}"' if (mx and len(full) > mx) else ""
            tds += f'<td class="{cls}"{ttl}>{_fmt(c, v)}</td>'
        rows_html += f"<tr>{tds}</tr>"

    ths = "".join(f'<th class="{"" if _sag(c) else "l"}">{c}</th>' for c in kolonlar)
    css = (
        "<style>"
        ".rkw{overflow-x:auto;border-radius:12px;box-shadow:0 2px 14px rgba(0,0,0,0.25);margin:4px 0}"
        ".rkt{width:100%;border-collapse:collapse;font-family:Inter,sans-serif}"
        ".rkt thead tr{background:linear-gradient(135deg,#1E293B,#0F172A)}"
        ".rkt thead th{padding:10px 12px;color:#CBD5E1;font-size:10px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;white-space:nowrap;text-align:right}"
        ".rkt thead th.l{text-align:left}"
        ".rkt tbody{background:#131C35}"
        ".rkt td{padding:8px 12px;font-size:11.5px;max-width:300px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
        ".rkt tbody tr{border-bottom:1px solid rgba(255,255,255,0.05)}"
        ".rkt tbody tr:hover{background:rgba(99,102,241,0.06)}"
        ".rk-txt{text-align:left;color:#CBD5E1}"
        ".rk-num{text-align:right;color:#CBD5E1;font-family:'JetBrains Mono',monospace}"
        ".rk-pos{text-align:right;color:#4ADE80 !important;font-weight:700;font-family:'JetBrains Mono',monospace}"
        ".rk-neg{text-align:right;color:#F87171 !important;font-weight:700;font-family:'JetBrains Mono',monospace}"
        ".rk-red{color:#F87171 !important;font-weight:600}.rk-org{color:#FB923C !important;font-weight:600}"
        ".rk-yel{color:#FCD34D !important;font-weight:600}.rk-grn{color:#4ADE80 !important;font-weight:600}.rk-dim{color:#64748B !important}"
        "</style>"
    )
    st.html(css + f'<div class="rkw"><table class="rkt"><thead><tr>{ths}</tr></thead><tbody>' + rows_html + "</tbody></table></div>")


def run():
    """KAYRAN ana çalıştırıcı. Portal tarafından çağrılır."""
    initialize_db()
    st.markdown("""
    <style>
    /* ── GLOBAL ─────────────────────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    html, body, .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        background: #0A0F1E !important;
    }

    /* ── ALERT BOX'LARI (warning/error/info/success) ─────────────────── */
    /* Streamlit'in default renkleri dark tema'da okunmuyor. Manuel override. */
    div[data-testid="stAlert"] {
        border-radius: 10px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        padding: 0 !important;
        border: 1px solid transparent !important;
        box-shadow: none !important;
    }
    div[data-testid^="stAlertContent"] {
        background: transparent !important;
        border: none !important;
        padding: 11px 15px !important;
        color: #E2E8F0 !important;
    }
    div.stAlert:has([data-testid="stAlertContentWarning"]) {
        background: rgba(245,158,11,0.07) !important;
        border: 1px solid rgba(245,158,11,0.20) !important;
        border-left: 3px solid rgba(245,158,11,0.60) !important;
    }
    div.stAlert:has([data-testid="stAlertContentError"]) {
        background: rgba(239,68,68,0.07) !important;
        border: 1px solid rgba(239,68,68,0.20) !important;
        border-left: 3px solid rgba(239,68,68,0.60) !important;
    }
    div.stAlert:has([data-testid="stAlertContentInfo"]) {
        background: rgba(59,130,246,0.06) !important;
        border: 1px solid rgba(59,130,246,0.20) !important;
        border-left: 3px solid rgba(59,130,246,0.55) !important;
    }
    div.stAlert:has([data-testid="stAlertContentSuccess"]) {
        background: rgba(34,197,94,0.06) !important;
        border: 1px solid rgba(34,197,94,0.20) !important;
        border-left: 3px solid rgba(34,197,94,0.50) !important;
    }
    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] span,
    div[data-testid="stAlert"] strong,
    div[data-testid="stAlert"] div {
        color: #E2E8F0 !important;
    }
    div[data-testid="stAlert"] strong,
    div[data-testid="stAlert"] b {
        font-weight: 700 !important;
    }
    
    /* ── METRIC KARTLARI (özet barlar) ── eski 'metric-container' + yeni 'stMetric' */
    [data-testid="metric-container"],
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(255,255,255,0.07) 0%, rgba(255,255,255,0.03) 100%);
        border-radius: 14px;
        padding: 16px 18px;
        border: 1px solid rgba(255,255,255,0.10);
        transition: border-color 0.2s;
        min-width: 0;
        overflow: hidden;
    }
    [data-testid="metric-container"]:hover,
    [data-testid="stMetric"]:hover { border-color: rgba(66,165,245,0.4); }
    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] * {
        color: #78909C !important; font-size:11.5px !important; font-weight:700 !important;
        letter-spacing:0.5px; text-transform:uppercase;
        white-space:nowrap !important; overflow:hidden !important; text-overflow:ellipsis !important;
    }
    [data-testid="stMetricValue"],
    [data-testid="stMetricValue"] * {
        color: #ECEFF1 !important; font-weight: 800 !important; font-size:24px !important;
        white-space:nowrap !important; overflow:hidden !important; text-overflow:ellipsis !important;
        line-height:1.15 !important;
    }
    [data-testid="stMetricDelta"] { font-size:12px !important; }
    
    /* ── BAŞLIK STİLLERİ ─────────────────────────────────────────────────── */
    .baslik {
        font-size: 22px;
        font-weight: 800;
        color: #ECEFF1;
        margin-bottom: 2px;
        letter-spacing: -0.3px;
    }
    .alt-baslik {
        font-size: 12px;
        color: #546E7A;
        margin-bottom: 24px;
        font-weight: 500;
        letter-spacing: 0.3px;
    }
    .sayfa-baslik-cizgi {
        height: 3px;
        background: linear-gradient(90deg, #1565C0, #42A5F5, transparent);
        border-radius: 2px;
        margin-bottom: 24px;
    }
    
    /* ── ETİKET KUTUCUKLARI ──────────────────────────────────────────────── */
    .tag-kirmizi { background:#7F0000; color:#FFCDD2; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:700; }
    .tag-turuncu { background:#BF360C; color:#FFE0B2; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:700; }
    .tag-sari    { background:#F57F17; color:#FFF9C4; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:700; }
    .tag-yesil   { background:#1B5E20; color:#C8E6C9; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:700; }
    .tag-mavi    { background:#0D47A1; color:#BBDEFB; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:700; }
    .tag-gri     { background:#263238; color:#90A4AE; padding:3px 10px; border-radius:20px; font-size:11px; }
    
    /* ── BİLGİ KUTULARI ─────────────────────────────────────────────────── */
    .uyari-box {
        background: linear-gradient(135deg,#3E1800,#2E1200);
        border-left: 3px solid #FF6F00;
        color: #FFE0B2;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
        font-size: 13px;
        font-weight: 500;
    }
    .info-box {
        background: linear-gradient(135deg,#0A1929,#071526);
        border-left: 3px solid #42A5F5;
        color: #BBDEFB;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
        font-size: 13px;
        font-weight: 500;
    }
    .basari-box {
        background: linear-gradient(135deg,#0F2910,#091E0A);
        border-left: 3px solid #66BB6A;
        color: #C8E6C9;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
        font-size: 13px;
        font-weight: 500;
    }
    
    /* ── SIDEBAR ─────────────────────────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #050B16 0%, #0A1628 100%) !important;
        border-right: 1px solid rgba(255,255,255,0.06) !important;
    }
    section[data-testid="stSidebar"] * { color: #CFD8DC !important; }
    section[data-testid="stSidebar"] .stRadio label {
        color: #90A4AE !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        padding: 4px 0 !important;
        transition: color 0.15s;
    }
    section[data-testid="stSidebar"] .stRadio label:hover { color: #ECEFF1 !important; }
    section[data-testid="stSidebar"] .stButton button {
        background: linear-gradient(135deg,#1A3A5C,#1565C0) !important;
        color: #ECEFF1 !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }
    section[data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.08) !important;
        margin: 12px 0 !important;
    }
    
    /* ── BUTONLAR ────────────────────────────────────────────────────────── */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        transition: all 0.2s !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg,#1565C0,#1E88E5) !important;
        border: none !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(21,101,192,0.3) !important;
    }
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 6px 20px rgba(21,101,192,0.5) !important;
        transform: translateY(-1px) !important;
    }
    
    /* ── FORM ALANLARI ───────────────────────────────────────────────────── */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div {
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        border-radius: 8px !important;
        color: #ECEFF1 !important;
        font-size: 13px !important;
    }
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {
        border-color: #42A5F5 !important;
        box-shadow: 0 0 0 2px rgba(66,165,245,0.15) !important;
    }
    label[data-testid="stWidgetLabel"] p {
        color: #78909C !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        letter-spacing: 0.3px !important;
    }
    
    /* ── EXPANDER ────────────────────────────────────────────────────────── */
    .streamlit-expanderHeader {
        background: rgba(255,255,255,0.04) !important;
        border-radius: 10px !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        color: #90CAF9 !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }
    .streamlit-expanderContent {
        background: rgba(255,255,255,0.02) !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-top: none !important;
        border-radius: 0 0 10px 10px !important;
    }
    
    /* ── TABS ────────────────────────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255,255,255,0.03) !important;
        border-radius: 10px !important;
        padding: 4px !important;
        gap: 2px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        color: #78909C !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        padding: 6px 16px !important;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(21,101,192,0.4) !important;
        color: #90CAF9 !important;
    }
    
    /* ── DATAFRAME ───────────────────────────────────────────────────────── */
    .stDataFrame { border-radius: 10px !important; overflow: hidden !important; }
    .stDataFrame [data-testid="stDataFrameResizable"] {
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 10px !important;
    }
    
    /* ── DIVIDER ─────────────────────────────────────────────────────────── */
    hr { border-color: rgba(255,255,255,0.06) !important; margin: 20px 0 !important; }
    
    /* ── TABLO HÜCRE RENKLERİ ────────────────────────────────────────────── */
    .hucre-acil    { background:#7F0000 !important; color:#FFCDD2 !important; font-weight:700; }
    .hucre-turuncu { background:#BF360C !important; color:#FFE0B2 !important; font-weight:600; }
    .hucre-sari    { background:#827717 !important; color:#F9A825 !important; font-weight:600; }
    .hucre-yesil   { background:#1B5E20 !important; color:#A5D6A7 !important; font-weight:600; }
    .hucre-gri     { background:#263238 !important; color:#CFD8DC !important; }
    .fcp-vurgu { color:#FFD54F; font-weight:800; font-size:15px; }
    
    /* ── SCROLLBAR ───────────────────────────────────────────────────────── */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: rgba(255,255,255,0.02); }
    ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.25); }
    </style>
    """, unsafe_allow_html=True)
    
    # ── Yardımcı fonksiyonlar ────────────────────────────────────────────
    STOK_YAS_ETIKET = {
        "kirmizi": '<span class="tag-kirmizi">🔴 {g} gün</span>',
        "turuncu": '<span class="tag-turuncu">🟠 {g} gün</span>',
        "sari":    '<span class="tag-sari">🟡 {g} gün</span>',
        "yesil":   '<span class="tag-yesil">🟢 {g} gün</span>',
        "yok":     '<span class="tag-gri">—</span>',
    }
    GUN_ETIKET = {
        "kirmizi": '<span class="tag-kirmizi">🔴 {g} gün</span>',
        "turuncu": '<span class="tag-turuncu">🟠 {g} gün</span>',
        "yesil":   '<span class="tag-yesil">🟢 {g} gün</span>',
        "yok":     '<span class="tag-gri">—</span>',
    }
    PERF_ETIKET = {
        "Çok İyi": '<span class="tag-yesil">⭐ Çok İyi</span>',
        "İyi":     '<span class="tag-sari">👍 İyi</span>',
        "Düşük":   '<span class="tag-kirmizi">📉 Düşük</span>',
        "veri yok":'<span class="tag-gri">—</span>',
    }
    YOL_ETIKET = {
        "yesil":   "🟢",
        "sari":    "🟡",
        "kirmizi": "🔴",
        "yok":     "—",
    }
    
    def stok_yas_html(renk, gun):
        return STOK_YAS_ETIKET.get(renk, STOK_YAS_ETIKET["yok"]).format(g=gun)
    
    def gun_html(renk, gun):
        if gun is None: return '<span class="tag-gri">—</span>'
        return GUN_ETIKET.get(renk, GUN_ETIKET["yok"]).format(g=gun)
    
    def perf_html(perf):
        return PERF_ETIKET.get(perf, PERF_ETIKET["veri yok"])
    
    # ── Sidebar navigasyon ───────────────────────────────────────────────
    with st.sidebar:
        st.markdown('<script>var sidebarEl=window.parent.document.querySelector("[data-testid=stSidebar] > div");if(sidebarEl)sidebarEl.scrollTop=0;</script>', unsafe_allow_html=True)
        aktif_kullanici = st.session_state.get("aktif_kullanici", "")
        st.markdown(f"""
        <div style="padding:6px 4px 8px; text-align:center;">
            <div style="font-size:26px; margin-bottom:4px;">📦</div>
            <div style="font-size:9px; color:#37474F; letter-spacing:1.5px; margin-top:2px; text-transform:uppercase;">Ürün Yönetim Sistemi</div>
            <div style="height:1px; background:linear-gradient(90deg,transparent,rgba(21,101,192,0.6),transparent); margin-top:14px;"></div>
        </div>
        """, unsafe_allow_html=True)
    
        if aktif_kullanici:
            st.markdown(f"""
            <div style="background:rgba(21,101,192,0.15); border:1px solid rgba(21,101,192,0.25);
                        border-radius:10px; padding:10px 14px; margin-bottom:10px;">
              <div style="color:#546E7A; font-size:10px; font-weight:600; letter-spacing:0.5px; margin-bottom:2px;">OTURUM AÇIK</div>
              <div style="color:#90CAF9; font-weight:700; font-size:13px;">👤 {aktif_kullanici}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Çıkış Yap", use_container_width=True):
                st.session_state.giris_yapildi = False
                st.session_state.aktif_kullanici = ""
                st.rerun()
    
        st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)
        sayfa = st.radio("Sayfa", [
            "📊  Dashboard",
            "🔍  Ürün Detay",
            "📈  Genel Analiz",
            "📋  Tüm Ürünler",
            "🛒  Satın Alma Geçmişi",
            "🎯  Kampanya Takip",
            "📦  Sipariş Önerisi",
            "📂  Veri Yükleme",
            "📄  Raporlar",
            "🔔  Bildirim Ayarları",
        ], label_visibility="collapsed")
        st.markdown(f"""
        <div style="text-align:center; margin-top:20px; padding-bottom:8px;">
            <div style="color:#263238; font-size:10px;">🕐 {tr_now().strftime('%d.%m.%Y  %H:%M')}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # ════════════════════════════════════════════════════════════════════
    # 1) DASHBOARD
    # ════════════════════════════════════════════════════════════════════
    if sayfa == "📊  Dashboard":
        st.markdown('<div class="baslik">📊 Dashboard</div>', unsafe_allow_html=True)
        st.markdown('<div class="alt-baslik">Stok durumu · Satış performansı · Uyarılar</div>', unsafe_allow_html=True)
        st.markdown('<div class="sayfa-baslik-cizgi"></div>', unsafe_allow_html=True)
    
        # Veri yükle (seçici için SKU listesi gerekli)
        try:
            veri = dashboard_hesapla()
        except Exception as e:
            _log.error("Dashboard veri hatası: %s", e)
            st.error(f"Veri yüklenemedi: {e}")
            st.stop()

        # Filtreler
        _kat_list_d = sorted({(u.get("kategori") or "").strip() for u in veri if (u.get("kategori") or "").strip()})
        col_f1, col_f2, col_f3, col_f4 = st.columns([1.5, 1.5, 1.8, 0.9])
        with col_f1:
            filtre_firma = st.selectbox("Firma Filtresi", ["Tüm Firmalar", "ITOPYA", "HB", "VATAN", "MONDAY", "KANAL", "DİĞER"])
        with col_f2:
            filtre_kat = st.selectbox("Kategori", ["Tüm Kategoriler"] + _kat_list_d, key="dash_kat")
        with col_f3:
            _sku_secenek = ["Tüm Ürünler"] + sorted({u["sku"] for u in veri})
            arama_sku = st.selectbox("🔍 Ürün (SKU) — yazarak ara", _sku_secenek, key="dash_sku")
        with col_f4:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 Yenile", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
    
        # Filtrele
        gosterilecek = []
        for urun in veri:
            # Stoku olan firmalar
            firmali_satirlar = [fd for fd in urun["firma_detay"] if fd.get("stok", 0) > 0]
    
            # Firma filtresi varsa sadece o firmayı göster
            if filtre_firma != "Tüm Firmalar":
                hedef = filtre_firma.replace("İ","I").replace("Ğ","G").replace("Ü","U").replace("Ş","S").replace("Ç","C").replace("Ö","O")
                firmali_satirlar = [fd for fd in firmali_satirlar if hedef in fd["firma"].replace("İ","I").replace("Ğ","G").replace("Ü","U").replace("Ş","S").replace("Ç","C").replace("Ö","O")]
    
            # Ürün (SKU) filtresi
            if arama_sku and arama_sku != "Tüm Ürünler":
                if urun["sku"] != arama_sku:
                    continue

            # Kategori filtresi
            if filtre_kat != "Tüm Kategoriler" and (urun.get("kategori") or "").strip() != filtre_kat:
                continue
    
            if firmali_satirlar:
                # Firmada stok var — her firma için ayrı satır
                for fd in firmali_satirlar:
                    gosterilecek.append((urun, fd))
            else:
                # Hiçbir firmada stok yok — ürünü yine de göster (sadece G5F depo bilgisiyle)
                if filtre_firma == "Tüm Firmalar":
                    # Boş bir firma satırı oluştur
                    bos_fd = {"firma": "—", "stok": 0, "haftalik_satis": 0,
                              "siparis_uyarisi": False, "muadil_gerekli": False}
                    gosterilecek.append((urun, bos_fd))
    
        # İstatistik kartları
        toplam_sku = len(set(u["sku"] for u in veri))
        acil_urunler = [u for u in veri if u.get("siparis_durum") == "acil"]
        yaklasan_urunler = [u for u in veri if u.get("siparis_durum") == "yaklasıyor"]
        planlama_urunler = [u for u in veri if u.get("siparis_durum") == "planlama"]
        uyari_sayisi = sum(1 for u, fd in gosterilecek if fd.get("siparis_uyarisi"))
        kritik_sayisi = sum(1 for u in veri if u.get("stok_renk") == "kirmizi")
    
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📦 Toplam Ürün", toplam_sku)
        m2.metric("🔴 Acil Sipariş", len(acil_urunler))
        m3.metric("🟠 Yaklaşıyor", len(yaklasan_urunler))
        m4.metric("🟡 Planlama", len(planlama_urunler))
    
        # ACİL SİPARİŞ BANNER — şık tasarım
        if acil_urunler:
            acil_items_list = []
            for u in acil_urunler:
                gun = u.get('stok_bitis_gun', '?')
                toplam = u.get('toplam_stok', u.get('bizim_stok', 0))
                ad = u['urun_adi']
                ad_kisalt = (ad[:60] + '...') if len(ad) > 60 else ad
                acil_items_list.append(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'padding:8px 12px;margin:4px 0;border-radius:6px;background:rgba(255,255,255,0.03);">'
                    f'<span style="color:#E2E8F0;font-weight:600;font-size:13px;">⚡ {ad_kisalt}</span>'
                    f'<div style="display:flex;gap:16px;flex-shrink:0;margin-left:12px;">'
                    f'<span style="color:#94A3B8;font-size:12px;">📦 {toplam:,} adet</span>'
                    f'<span style="color:#F87171;font-size:12px;font-weight:700;">{gun} günde biter</span>'
                    f'</div></div>'
                )
            acil_items = "".join(acil_items_list)
            st.markdown(
                f'<div style="background:rgba(239,68,68,0.07);border-radius:12px;padding:16px 20px;margin:12px 0;border:1px solid rgba(239,68,68,0.22);border-left:3px solid rgba(239,68,68,0.6);">'
                f'<div style="display:flex;align-items:center;margin-bottom:12px;">'
                f'<span style="font-size:16px;font-weight:800;color:#F87171;">🚨 ACİL SİPARİŞ GEREKİYOR!</span>'
                f'<span style="background:rgba(239,68,68,0.18);color:#FCA5A5;padding:2px 10px;border-radius:20px;'
                f'font-size:13px;font-weight:700;margin-left:12px;">{len(acil_urunler)} ürün</span>'
                f'</div>{acil_items}</div>',
                unsafe_allow_html=True
            )
    
        if yaklasan_urunler:
            yak_items_list = []
            for u in yaklasan_urunler[:5]:
                gun = u.get('siparis_son_gun', u.get('stok_bitis_gun', '?'))
                ad = u['urun_adi']
                ad_kisalt = (ad[:55] + '...') if len(ad) > 55 else ad
                yak_items_list.append(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'padding:6px 12px;margin:3px 0;border-radius:6px;background:rgba(255,255,255,0.03);">'
                    f'<span style="color:#E2E8F0;font-size:13px;">📌 {ad_kisalt}</span>'
                    f'<span style="color:#FBBF24;font-size:12px;font-weight:600;flex-shrink:0;margin-left:12px;">'
                    f'{gun}g içinde sipariş</span></div>'
                )
            yak_items = "".join(yak_items_list)
            kalan = f'<span style="color:#FBBF24;font-size:12px;"> + {len(yaklasan_urunler)-5} ürün daha</span>' if len(yaklasan_urunler) > 5 else ""
            st.markdown(
                f'<div style="background:rgba(245,158,11,0.06);border-radius:12px;padding:14px 20px;margin:8px 0;border:1px solid rgba(245,158,11,0.22);border-left:3px solid rgba(245,158,11,0.6);">'
                f'<div style="display:flex;align-items:center;margin-bottom:10px;">'
                f'<span style="font-size:14px;font-weight:700;color:#FBBF24;">⚠️ 30 Gün İçinde Sipariş Verilmeli</span>'
                f'<span style="background:rgba(245,158,11,0.16);color:#FCD34D;padding:2px 8px;border-radius:20px;'
                f'font-size:12px;font-weight:700;margin-left:10px;">{len(yaklasan_urunler)} ürün</span>{kalan}'
                f'</div>{yak_items}</div>',
                unsafe_allow_html=True
            )
    
        # Tarayıcı bildirimi (JS)
        if acil_urunler:
            st.markdown(f"""
            <script>
            if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {{
                new Notification('🚨 Stok Yönetimi', {{
                    body: '{len(acil_urunler)} ürün için ACİL sipariş gerekiyor!',
                    icon: '📦'
                }});
            }} else if (typeof Notification !== 'undefined' && Notification.permission !== 'denied') {{
                Notification.requestPermission().then(function(p) {{
                    if (p === 'granted') {{
                        new Notification('🚨 Stok Yönetimi', {{
                            body: '{len(acil_urunler)} ürün için ACİL sipariş gerekiyor!',
                        }});
                    }}
                }});
            }}
            </script>
            """, unsafe_allow_html=True)
    
        st.markdown("---")
    
        # Renk açıklaması
        st.markdown("""
        <div style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:12px;">
          <span class="tag-kirmizi">🔴 ACİL / 90+ gün stok yaşı</span>
          <span class="tag-turuncu">🟠 Yaklaşıyor / 60-90 gün</span>
          <span class="tag-sari">🟡 Planlama / 30-60 gün</span>
          <span class="tag-yesil">🟢 Normal / Sağlıklı</span>
        </div>
        """, unsafe_allow_html=True)
    
        if not gosterilecek:
            st.info("Gösterilecek veri bulunamadı. Lütfen önce 'Veri Yükleme' sekmesinden veri yükleyin.")
        else:
            satirlar = []
            for urun, fd in gosterilecek:
                y = urun["yayilim"]
                yayilim = f"TY:{y.get('TRENDYOL',0)} | HB:{y.get('HB',0)} | IT:{y.get('ITOPYA',0)} | VT:{y.get('VATAN',0)}"
                yol_renk = urun.get("yol_renk", "yok")
                yol_mesaj = urun.get("yol_mesaj", "")
                yol_miktar = urun.get("yol_miktar", 0)
                yol_metin = f"{YOL_ETIKET.get(yol_renk,'—')} {yol_miktar} adet | {yol_mesaj}" if yol_renk != "yok" else "—"
                uyari = "⚠️ SİPARİŞ ÖNER!" if fd.get("siparis_uyarisi") else ""
                olu_durum = urun.get("olu_stok_durum", "normal")
                olu_mesaj = urun.get("olu_stok_mesaj", "")
                satirlar.append({
                    "SKU": urun["sku"],
                    "Ürün Adı": urun["urun_adi"],
                    "Kategori": urun["kategori"],
                    "Bizim Stok": urun["bizim_stok"],
                    "Toplam Stok": urun.get("toplam_stok", urun["bizim_stok"]),
                    "Ort. Hft. Satış": round(urun.get("ortalama_haftalik_satis", 0)),
                    "Satış Trendi": urun.get("trend_mesaji", "—"),
                    "Trend Yön": urun.get("trend_yon", "yetersiz_veri"),
                    "📋 Sipariş Takvimi": urun.get("siparis_mesaj", "—"),
                    "Sipariş Durum": urun.get("siparis_durum", "veri_yok"),
                    "📦 Önerilen Sipariş": f"{urun.get('oneri_miktar',0)} adet" if urun.get("oneri_miktar",0) > 0 else "✅ Yeterli",
                    "⚡ Risk Skoru": urun.get("risk_skor", 0),
                    "Risk Etiketi": urun.get("risk_etiketi", "—"),
                    "🪦 Stok Durumu": olu_mesaj if olu_mesaj else "—",
                    "Ölü Durum": olu_durum,
                    "Firma": fd.get("firma", "—"),
                    "Firma Stok": fd.get("stok", 0),
                    "Haftalık Satış": fd.get("satis", 0),
                    "Stok Yaşı": f"{urun.get('stok_gun', 0)} gün",
                    "Stok Renk": urun.get("stok_renk", "yok"),
                    "Performans": fd.get("performans", "veri yok"),
                    "Yoldaki Durum": yol_metin,
                    "Yol Renk": yol_renk,
                    "Stok Yayılımı": yayilim,
                    "Uyarı": uyari,
                    "_sku": urun["sku"], "_firma": fd.get("firma",""), "_urun_adi": urun["urun_adi"],
                    "_siparis_uyarisi": fd.get("siparis_uyarisi", False), "_muadil_gerekli": fd.get("muadil_gerekli", False),
                })
    
            df = pd.DataFrame(satirlar)
    
            def renk_uygula(df_goster):
                if df_goster is None or df_goster.empty:
                    st.info("Gösterilecek veri yok.")
                    return
                sp_map  = {"acil":"d-red","yaklasıyor":"d-org","planlama":"d-yel","normal":"d-grn","veri_yok":"d-dim"}
                yas_map = {"kirmizi":"d-red","turuncu":"d-org","sari":"d-yel","yesil":"d-grn","yok":"d-dim"}
                tr_map  = {"yukseliyor":"d-grn","dusuyor":"d-red","stabil":"d-yel","yetersiz_veri":"d-dim"}
                yol_map = {"yesil":"d-grn","sari":"d-yel","kirmizi":"d-red","yok":"d-dim"}
                def _cd(v, m):
                    return m.get(str(v), "d-dim")
                def _risk_cls(s):
                    try:
                        s = float(s)
                    except Exception:
                        return "d-dim"
                    if s >= 70: return "d-red"
                    if s >= 45: return "d-org"
                    if s >= 25: return "d-yel"
                    return "d-grn"

                rows_html = ""
                for _, row in df_goster.iterrows():
                    ad = str(row.get("Ürün Adı", "") or "")
                    ad_k = ad if len(ad) <= 44 else ad[:43] + "…"
                    ad_t = ad.replace(chr(34), "&quot;")
                    yol = str(row.get("Yoldaki Durum", "") or "")
                    yol_k = yol if len(yol) <= 26 else yol[:25] + "…"
                    yol_t = yol.replace(chr(34), "&quot;")
                    sip = str(row.get("📋 Sipariş Takvimi", "") or "")
                    sip_k = sip if len(sip) <= 26 else sip[:25] + "…"
                    sip_t = sip.replace(chr(34), "&quot;")
                    risk = row.get("⚡ Risk Skoru", 0)
                    rows_html += (
                        "<tr>"
                        f'<td class="d-sku">{row.get("SKU","")}</td>'
                        f'<td class="d-name" title="{ad_t}">{ad_k}</td>'
                        f'<td class="d-kat">{row.get("Kategori","")}</td>'
                        f'<td class="d-tot">{row.get("Toplam Stok","")}</td>'
                        f'<td class="d-num">{row.get("Bizim Stok","")}</td>'
                        f'<td class="d-firma">{row.get("Firma","")}</td>'
                        f'<td class="d-num">{row.get("Firma Stok","")}</td>'
                        f'<td class="d-num">{row.get("Ort. Hft. Satış","")}</td>'
                        f'<td class="d-st {_cd(row.get("Trend Yön",""), tr_map)}">{row.get("Satış Trendi","")}</td>'
                        f'<td class="d-st {_cd(row.get("Stok Renk",""), yas_map)}">{row.get("Stok Yaşı","")}</td>'
                        f'<td class="d-st {_cd(row.get("Sipariş Durum",""), sp_map)}" title="{sip_t}">{sip_k}</td>'
                        f'<td class="d-st">{row.get("📦 Önerilen Sipariş","")}</td>'
                        f'<td class="d-num {_risk_cls(risk)}">{risk}</td>'
                        f'<td class="d-st {_cd(row.get("Yol Renk",""), yol_map)}" title="{yol_t}">{yol_k}</td>'
                        "</tr>"
                    )
                css = (
                    "<style>"
                    ".dw{overflow-x:auto;border-radius:12px;box-shadow:0 2px 14px rgba(0,0,0,0.25);margin:2px 0}"
                    ".dt{width:100%;border-collapse:collapse;font-family:Inter,sans-serif}"
                    ".dt thead tr{background:linear-gradient(135deg,#1E293B,#0F172A)}"
                    ".dt thead th{padding:10px 11px;color:#CBD5E1;font-size:10px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;white-space:nowrap;text-align:right}"
                    ".dt thead th.l{text-align:left}"
                    ".dt tbody{background:#131C35}"
                    ".dt td{padding:8px 11px;font-size:11.5px}"
                    ".dt tbody tr{border-bottom:1px solid rgba(255,255,255,0.05)}"
                    ".dt tbody tr:hover{background:rgba(99,102,241,0.06)}"
                    ".d-sku{color:#E2E8F0;font-family:'JetBrains Mono',monospace;font-weight:600;white-space:nowrap}"
                    ".d-name{color:#CBD5E1;max-width:240px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
                    ".d-kat{color:#94A3B8;font-size:11px}"
                    ".d-firma{color:#CBD5E1;font-size:11px;white-space:nowrap}"
                    ".d-num{text-align:right;color:#CBD5E1;font-family:'JetBrains Mono',monospace}"
                    ".d-tot{text-align:right;color:#93C5FD;font-weight:700;font-family:'JetBrains Mono',monospace}"
                    ".d-st{text-align:left;color:#CBD5E1;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:170px}"
                    ".d-red{color:#F87171 !important;font-weight:600}"
                    ".d-org{color:#FB923C !important;font-weight:600}"
                    ".d-yel{color:#FCD34D !important;font-weight:600}"
                    ".d-grn{color:#4ADE80 !important;font-weight:600}"
                    ".d-dim{color:#64748B !important}"
                    "</style>"
                )
                head = (
                    '<div class="dw"><table class="dt"><thead><tr>'
                    '<th class="l">SKU</th><th class="l">Ürün Adı</th><th class="l">Kategori</th>'
                    "<th>Toplam</th><th>Bizim</th>"
                    '<th class="l">Firma</th><th>Firma Stok</th><th>Ort. Hft.</th>'
                    '<th class="l">Satış Trendi</th><th class="l">Stok Yaşı</th>'
                    '<th class="l">📋 Sipariş Takvimi</th><th class="l">📦 Önerilen</th>'
                    "<th>⚡ Risk</th>"
                    '<th class="l">Yoldaki Durum</th>'
                    "</tr></thead><tbody>"
                )
                st.html(css + head + rows_html + "</tbody></table></div>")
    
            tab1, tab2, tab3, tab4 = st.tabs(["⚡ En Riskli","📈 En Çok Satan","📉 En Az Satan","🕐 Stok Yaşına Göre"])
            with tab1:
                st.caption("Risk skoru en yüksek ürünler önce")
                renk_uygula(df.drop_duplicates("SKU").sort_values("⚡ Risk Skoru", ascending=False))
            with tab2:
                st.caption("4 haftalık ortalamaya göre en çok satan ürünler")
                renk_uygula(df.drop_duplicates("SKU").sort_values("Ort. Hft. Satış", ascending=False))
            with tab3:
                st.caption("En az satan / yavaş hareket eden ürünler")
                renk_uygula(df.drop_duplicates("SKU").sort_values("Ort. Hft. Satış", ascending=True))
            with tab4:
                st.caption("En eski stok yaşına sahip ürünler önce")
                renk_uygula(df.drop_duplicates("SKU").sort_values("Stok Yaşı", ascending=False))
    
            # ── DASHBOARD GRAFİKLERİ ──────────────────────────────────────
            st.markdown("---")
            st.markdown("### 📊 Stok & Satış Grafikleri")
    
            # Ürün başına tek satır (firma tekrarı olmadan)
            sku_tek = {}
            for u, fd in gosterilecek:
                if u["sku"] not in sku_tek:
                    sku_tek[u["sku"]] = u
    
            urun_listesi_tek = list(sku_tek.values())
    
            gcol1, gcol2 = st.columns(2)
    
            # ── GRAFİK 1: Toplam Stok Dağılımı (Firma Bazlı) ──
            with gcol1:
                # Tüm firmalardaki toplam stok
                firma_stok_toplam = {}
                for u in urun_listesi_tek:
                    y = u.get("yayilim", {})
                    for firma in ["ITOPYA","HB","VATAN","MONDAY","KANAL","DIGER"]:
                        firma_stok_toplam[firma] = firma_stok_toplam.get(firma, 0) + y.get(firma, 0)
                firma_stok_toplam["G5F DEPO"] = sum(u["bizim_stok"] for u in urun_listesi_tek)
    
                df_dag = pd.DataFrame([
                    {"Kanal": k, "Stok": v}
                    for k, v in firma_stok_toplam.items() if v > 0
                ])
                if not df_dag.empty:
                    fig_dag = px.pie(
                        df_dag, names="Kanal", values="Stok",
                        title="📦 Toplam Stok Dağılımı (Kanal Bazında)",
                        color_discrete_sequence=["#42A5F5","#66BB6A","#FFA726","#EF5350","#AB47BC","#26C6DA","#D4E157","#FF7043"],
                        hole=0.35,
                    )
                    fig_dag.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)", font_color="#CFD8DC", title_font_color="#90CAF9", legend=dict(font=dict(color="#90A4AE")), margin=dict(t=40,b=0,l=0,r=0))
                    fig_dag.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_dag, use_container_width=True)
                else:
                    st.info("Stok dağılımı için veri yok.")
    
            # ── GRAFİK 2: Sipariş Takvimi Özeti ──
            with gcol2:
                durum_sayisi = {"🔴 ACİL": 0, "🟠 Yaklaşıyor": 0, "🟡 Planlama": 0, "🟢 Normal": 0, "⚪ Veri Yok": 0}
                durum_map = {"acil": "🔴 ACİL", "yaklasıyor": "🟠 Yaklaşıyor", "planlama": "🟡 Planlama", "normal": "🟢 Normal", "veri_yok": "⚪ Veri Yok"}
                for u in urun_listesi_tek:
                    etiket = durum_map.get(u.get("siparis_durum", "veri_yok"), "⚪ Veri Yok")
                    durum_sayisi[etiket] += 1
    
                df_sip = pd.DataFrame([{"Durum": k, "Ürün Sayısı": v} for k, v in durum_sayisi.items() if v > 0])
                if not df_sip.empty:
                    renk_map = {
                        "🔴 ACİL": "#FFCCCC", "🟠 Yaklaşıyor": "#FFE0B2",
                        "🟡 Planlama": "#FFF9C4", "🟢 Normal": "#C8E6C9", "⚪ Veri Yok": "#F0F0F0"
                    }
                    fig_sip = px.bar(
                        df_sip, x="Durum", y="Ürün Sayısı",
                        title="📋 Sipariş Takvimi Özeti",
                        color="Durum",
                        color_discrete_map=renk_map,
                        text="Ürün Sayısı",
                    )
                    fig_sip.update_traces(textposition='outside', marker_line_color='rgba(0,0,0,0.2)', marker_line_width=1)
                    fig_sip.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(7,13,26,0.8)",
                                          showlegend=False, margin=dict(t=40,b=0,l=0,r=0))
                    st.plotly_chart(fig_sip, use_container_width=True)
    
            gcol3, gcol4 = st.columns(2)
    
            # ── GRAFİK 3: Satış Trendi (Top 5 ürün) ──
            with gcol3:
                top5 = sorted(urun_listesi_tek, key=lambda x: x.get("ortalama_haftalik_satis", 0), reverse=True)[:5]
                if top5:
                    df_top = pd.DataFrame([{
                        "Ürün": u["urun_adi"][:18] + ("..." if len(u["urun_adi"]) > 18 else ""),
                        "Ort. Hft. Satış": u.get("ortalama_haftalik_satis", 0),
                        "Trend": u.get("trend_yon", "stabil")
                    } for u in top5])
                    trend_renk = {"yukseliyor": "#2E7D32", "dusuyor": "#C62828", "stabil": "#F57C00", "yetersiz_veri": "#9E9E9E"}
                    fig_top = px.bar(
                        df_top, x="Ort. Hft. Satış", y="Ürün",
                        title="📈 En Çok Satan 5 Ürün",
                        orientation="h",
                        color="Trend",
                        color_discrete_map=trend_renk,
                        text="Ort. Hft. Satış",
                    )
                    fig_top.update_traces(textposition='outside')
                    fig_top.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(7,13,26,0.8)",
                                          showlegend=True, margin=dict(t=40,b=0,l=0,r=0),
                                          legend_title="Trend")
                    st.plotly_chart(fig_top, use_container_width=True)
    
            # ── GRAFİK 4: Stok Yaşı Dağılımı ──
            with gcol4:
                yas_gruplari = {"🟢 0-30 Gün": 0, "🟡 30-60 Gün": 0, "🟠 60-90 Gün": 0, "🔴 90+ Gün": 0}
                for u in urun_listesi_tek:
                    g = u.get("stok_gun", 0)
                    if g < 30: yas_gruplari["🟢 0-30 Gün"] += 1
                    elif g < 60: yas_gruplari["🟡 30-60 Gün"] += 1
                    elif g < 90: yas_gruplari["🟠 60-90 Gün"] += 1
                    else: yas_gruplari["🔴 90+ Gün"] += 1
    
                df_yas = pd.DataFrame([{"Stok Yaşı": k, "Ürün Sayısı": v} for k, v in yas_gruplari.items() if v > 0])
                if not df_yas.empty:
                    renk_yas = {
                        "🟢 0-30 Gün": "#C8E6C9", "🟡 30-60 Gün": "#FFF9C4",
                        "🟠 60-90 Gün": "#FFE0B2", "🔴 90+ Gün": "#FFCCCC"
                    }
                    fig_yas = px.pie(
                        df_yas, names="Stok Yaşı", values="Ürün Sayısı",
                        title="🕐 Stok Yaşı Dağılımı",
                        color="Stok Yaşı",
                        color_discrete_map=renk_yas,
                        hole=0.35,
                    )
                    fig_yas.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)", font_color="#CFD8DC", title_font_color="#90CAF9", legend=dict(font=dict(color="#90A4AE")), margin=dict(t=40,b=0,l=0,r=0))
                    fig_yas.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_yas, use_container_width=True)
    
    # ════════════════════════════════════════════════════════════════════
    # 2) ÜRÜN DETAY
    # ════════════════════════════════════════════════════════════════════
    elif sayfa == "🔍  Ürün Detay":
        st.markdown('<div class="baslik">🔍 Ürün Detay</div>', unsafe_allow_html=True)
        st.markdown('<div class="alt-baslik">Satış analizi · Trend · Sipariş takvimi</div>', unsafe_allow_html=True)
        st.markdown('<div class="sayfa-baslik-cizgi"></div>', unsafe_allow_html=True)
    
        # Ürün seçimi
        try:
            veri = dashboard_hesapla()
        except Exception as e:
            _log.error("Hata: %s", e)
            st.error(f"Veri yüklenemedi: {e}")
            st.stop()
    
        if not veri:
            st.info("Önce 'Veri Yükleme' sekmesinden veri yükleyin.")
            st.stop()
    
        sku_listesi = {u['sku']: u['sku'] for u in veri}
    
        # Aranabilir ürün seçici (kutuya yazarak ara, seç) — sadece SKU
        st.markdown('<div style="font-size:11px;font-weight:700;color:#94A3B8;letter-spacing:1px;text-transform:uppercase;margin:2px 0 6px;text-align:center;">🔎 Ürün Ara / Seç</div>', unsafe_allow_html=True)
        _sl_ud, sec_col, _sr_ud = st.columns([1.6, 2.0, 1.6])
        with sec_col:
            secim = st.selectbox("Ürün Seç", list(sku_listesi.keys()), label_visibility="collapsed", key="ud_sku")
    
        secilen_sku = sku_listesi[secim]
        urun = next(u for u in veri if u["sku"] == secilen_sku)
    
        st.markdown("---")
    
        # Üst bilgi kartları
        c1, c2, c3, c4, c5 = st.columns(5)
        toplam_stok_ud = urun.get("toplam_stok", urun.get("bizim_stok", 0))
        c1.metric("📦 Toplam Stok", toplam_stok_ud)
        c2.metric("📊 Ort. Hft. Satış", round(urun.get("ortalama_haftalik_satis", 0)))
        c3.metric("⚡ Risk Skoru", f"{urun.get('risk_skor',0)}/100")
        stok_bitis = urun.get('stok_bitis_gun')
        stok_bitis_str = f"{stok_bitis} gün" if stok_bitis is not None and stok_bitis != 0 else "Satış verisi yok"
        c4.metric("📅 Stok Biter", stok_bitis_str)
        c5.metric("📦 Sipariş Önerisi", f"{urun.get('oneri_miktar',0)} adet")
    
        # Sipariş durumu banner (yumuşak, tek katman)
        siparis_durum = urun.get("siparis_durum", "veri_yok")
        siparis_mesaj = urun.get("siparis_mesaj", "")
        _oneri_mesaj = urun.get("oneri_mesaj", "")
        _durum_stil = {
            "acil":       ("rgba(239,68,68,0.07)", "rgba(239,68,68,0.55)", "🚨", "#F87171"),
            "yaklasıyor": ("rgba(245,158,11,0.07)", "rgba(245,158,11,0.5)", "⚠️", "#FBBF24"),
            "planlama":   ("rgba(59,130,246,0.07)", "rgba(59,130,246,0.5)", "📋", "#93C5FD"),
            "veri_yok":   ("rgba(34,197,94,0.06)", "rgba(34,197,94,0.45)", "✅", "#4ADE80"),
        }
        _bg, _brd, _ik, _tc = _durum_stil.get(siparis_durum, _durum_stil["veri_yok"])
        _detay = f' <span style="color:#94A3B8;font-weight:400;">· {_oneri_mesaj}</span>' if _oneri_mesaj else ""
        st.markdown(
            f'<div style="background:{_bg};border-left:3px solid {_brd};border-radius:8px;padding:11px 15px;margin:6px 0;font-size:13px;">'
            f'<span style="color:{_tc};font-weight:700;">{_ik} {siparis_mesaj}</span>{_detay}</div>',
            unsafe_allow_html=True
        )
    
        st.markdown("---")
    
        # Geçmiş satış verileri
        gecmis_raw = get_gecmis_satis_tum_firmalar(secilen_sku)
    
        if not gecmis_raw:
            st.info("Bu ürün için henüz geçmiş satış verisi bulunmuyor. Haftalık veri yükledikçe grafikler oluşacak.")
        else:
            df_gecmis = pd.DataFrame(gecmis_raw)
            tarihler = sorted(df_gecmis["yukleme_tarihi"].unique())
            firmalar = sorted(df_gecmis["firma"].unique())
    
            # TAB 1: Toplam satış trendi
            # TAB 2: Firma bazında satış
            # TAB 3: Stok seviyeleri
            gtab1, gtab2, gtab3 = st.tabs(["📈 Satış Trendi", "🏪 Firma Bazlı", "📦 Stok Seviyeleri"])
    
            with gtab1:
                # Haftalık toplam satış
                toplam_df = df_gecmis.groupby("yukleme_tarihi")["haftalik_satis"].sum().reset_index()
                toplam_df.columns = ["Tarih", "Toplam Satış"]
                toplam_df = toplam_df.sort_values("Tarih")
    
                fig = go.Figure()
    
                # Satış çizgisi
                fig.add_trace(go.Scatter(
                    x=toplam_df["Tarih"],
                    y=toplam_df["Toplam Satış"],
                    mode="lines+markers",
                    name="Haftalık Satış",
                    line=dict(color="#42A5F5", width=2.5),
                    marker=dict(size=8),
                ))
    
                # 4 haftalık ortalama çizgisi
                if len(toplam_df) >= 2:
                    ort = toplam_df["Toplam Satış"].mean()
                    fig.add_hline(
                        y=ort,
                        line_dash="dash",
                        line_color="#FF6F00",
                        annotation_text=f"4 Hft Ort: {ort:.1f}",
                        annotation_position="right"
                    )
    
                # Trend yönü rengi
                trend_yon = urun.get("trend_yon", "stabil")
                trend_renk = {"yukseliyor": "#2E7D32", "dusuyor": "#C62828", "stabil": "#F57C00"}.get(trend_yon, "#666")
    
                fig.update_layout(
                    title=dict(text=f"Haftalık Toplam Satış Trendi — {urun['urun_adi']}", font=dict(size=15, color="#90CAF9")),
                    xaxis_title="Hafta", xaxis=dict(color="#546E7A", gridcolor="rgba(255,255,255,0.05)"),
                    yaxis_title="Satış Adedi", yaxis=dict(color="#546E7A", gridcolor="rgba(255,255,255,0.05)"),
                    font=dict(color="#CFD8DC"),
                    height=380,
                    plot_bgcolor="rgba(255,255,255,0.03)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    hovermode="x unified",
                    showlegend=True,
                    annotations=[dict(
                        x=0.01, y=0.97, xref="paper", yref="paper",
                        text=f"Trend: {urun.get('trend_mesaji','—')}",
                        showarrow=False,
                        font=dict(size=13, color="#CFD8DC"),
                        bgcolor="rgba(7,13,26,0.9)",
                        bordercolor=trend_renk,
                        borderwidth=1,
                        borderpad=4,
                    )]
                )
                st.plotly_chart(fig, use_container_width=True)
    
                # Haftalık tablo
                with st.expander("📋 Haftalık Satış Tablosu"):
                    st.dataframe(toplam_df.sort_values("Tarih", ascending=False), use_container_width=True)
    
            with gtab2:
                # Firma bazında satış karşılaştırması
                fig2 = go.Figure()
    
                renkler = {
                    "ITOPYA": "#1F4E79",
                    "HB": "#FF6F00",
                    "VATAN": "#2E7D32",
                    "MONDAY": "#7B1FA2",
                    "KANAL": "#C62828",
                    "DIGER": "#546E7A",
                }
    
                for firma in firmalar:
                    firma_df = df_gecmis[df_gecmis["firma"] == firma].sort_values("yukleme_tarihi")
                    if firma_df["haftalik_satis"].sum() == 0:
                        continue
                    fig2.add_trace(go.Bar(
                        x=firma_df["yukleme_tarihi"],
                        y=firma_df["haftalik_satis"],
                        name=firma,
                        marker_color=renkler.get(firma, "#888"),
                    ))
    
                fig2.update_layout(
                    title=dict(text=f"Firma Bazında Haftalık Satış — {urun['urun_adi']}", font=dict(size=15, color="#90CAF9")),
                    xaxis_title="Hafta", yaxis_title="Satış Adedi",
                    barmode="group", height=380,
                    font=dict(color="#CFD8DC"), xaxis=dict(color="#546E7A", gridcolor="rgba(255,255,255,0.05)"), yaxis=dict(color="#546E7A", gridcolor="rgba(255,255,255,0.05)"), legend=dict(font=dict(color="#90A4AE")), plot_bgcolor="rgba(255,255,255,0.03)", paper_bgcolor="rgba(0,0,0,0)",
                    hovermode="x unified",
                )
                st.plotly_chart(fig2, use_container_width=True)
    
                # Firma performans özeti
                st.markdown("**Firma Performans Özeti (Toplam Satış)**")
                firma_ozet = df_gecmis.groupby("firma")["haftalik_satis"].agg(["sum","mean"]).reset_index()
                firma_ozet.columns = ["Firma", "Toplam Satış", "Ort. Haftalık"]
                firma_ozet = firma_ozet.sort_values("Toplam Satış", ascending=False)
                firma_ozet["Ort. Haftalık"] = firma_ozet["Ort. Haftalık"].round(1)
                st.dataframe(firma_ozet, use_container_width=True, hide_index=True)
    
            with gtab3:
                # Bizim stok + firma stok seviyeleri
                fig3 = go.Figure()
    
                # Bizim stok (depo)
                bizim_stok_df = df_gecmis.groupby("yukleme_tarihi")["stok_miktari"].sum().reset_index()
                bizim_stok_df = bizim_stok_df.sort_values("yukleme_tarihi")
    
                for firma in firmalar:
                    firma_df = df_gecmis[df_gecmis["firma"] == firma].sort_values("yukleme_tarihi")
                    if firma_df["stok_miktari"].sum() == 0:
                        continue
                    fig3.add_trace(go.Scatter(
                        x=firma_df["yukleme_tarihi"],
                        y=firma_df["stok_miktari"],
                        mode="lines+markers",
                        name=f"{firma} Stok",
                        line=dict(color=renkler.get(firma, "#888"), width=2),
                        marker=dict(size=6),
                    ))
    
                fig3.update_layout(
                    title=dict(text=f"Firma Stok Seviyeleri — {urun['urun_adi']}", font=dict(size=15, color="#90CAF9")),
                    xaxis_title="Hafta", yaxis_title="Stok Adedi",
                    height=380,
                    font=dict(color="#CFD8DC"), xaxis=dict(color="#546E7A", gridcolor="rgba(255,255,255,0.05)"), yaxis=dict(color="#546E7A", gridcolor="rgba(255,255,255,0.05)"), legend=dict(font=dict(color="#90A4AE")), plot_bgcolor="rgba(255,255,255,0.03)", paper_bgcolor="rgba(0,0,0,0)",
                    hovermode="x unified",
                )
                st.plotly_chart(fig3, use_container_width=True)
    
        st.markdown("---")
    
        # Yoldaki durum
        st.subheader("🚢 Yoldaki Ürün Durumu")
        yol_renk = urun.get("yol_renk", "yok")
        if yol_renk == "yesil":
            st.success(f"🟢 {urun.get('yol_miktar',0)} adet yolda | {urun.get('yol_mesaj','')}")
        elif yol_renk == "sari":
            st.warning(f"🟡 {urun.get('yol_miktar',0)} adet yolda | {urun.get('yol_mesaj','')}")
        elif yol_renk == "kirmizi":
            st.error(f"🔴 {urun.get('yol_mesaj','')}")
        else:
            st.info("Yolda ürün kaydı bulunmuyor.")
    
    
    
    # ════════════════════════════════════════════════════════════════════
    # 3) GENEL ANALİZ
    # ════════════════════════════════════════════════════════════════════
    elif sayfa == "📈  Genel Analiz":
        st.markdown('<div class="baslik">📈 Genel Analiz</div>', unsafe_allow_html=True)
        st.markdown('<div class="alt-baslik">Sipariş önceliklendirme · Ölü stok · Kategori & Marka</div>', unsafe_allow_html=True)
        st.markdown('<div class="sayfa-baslik-cizgi"></div>', unsafe_allow_html=True)
        st.markdown('<div class="alt-baslik">Sipariş önceliklendirme · Ölü stok · Kategori & Marka analizi</div>', unsafe_allow_html=True)
    
        try:
            analiz = genel_analiz_hesapla()
        except Exception as e:
            _log.error("Hata: %s", e)
            st.error(f"Analiz yüklenemedi: {e}")
            st.stop()
    
        urunler = analiz["urunler"]
        if not urunler:
            st.info("Veri bulunamadı. Lütfen önce veri yükleyin.")
            st.stop()
    
        # Özet kartlar
        toplam_urun = len(urunler)
        acil_sayisi = sum(1 for u in urunler if u.get("siparis_durum") == "acil")
        olu_sayisi = sum(1 for u in urunler if u.get("olu_stok_durum") == "olu")
        yavas_sayisi = sum(1 for u in urunler if u.get("olu_stok_durum") == "yavas")
        toplam_siparis_oneri = sum(u.get("oneri_miktar", 0) for u in urunler)
    
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("📦 Toplam Ürün", toplam_urun)
        m2.metric("🚨 Acil Sipariş", acil_sayisi)
        m3.metric("🪦 Ölü Stok", olu_sayisi)
        m4.metric("🐢 Yavaş Satan", yavas_sayisi)
        m5.metric("📋 Toplam Öneri", f"{toplam_siparis_oneri:,} adet")
    
        st.markdown("---")
    
        atab2, atab3, atab4 = st.tabs([
            "🪦 Ölü & Yavaş Stok",
            "📂 Kategori Analizi",
            "🏷️ Marka Analizi",
        ])
    
        # TAB 2 ─────────────────────────────────────────────────────────
        with atab2:
            olu_urunler = [u for u in urunler if u.get("olu_stok_durum") in ("olu","yavas")]
            if not olu_urunler:
                st.markdown('<div class="basari-box">✅ Ölü veya yavaş hareket eden stok tespit edilmedi.</div>', unsafe_allow_html=True)
            else:
                rows_olu = []
                for u in olu_urunler:
                    rows_olu.append({
                        "SKU": u["sku"],
                        "Ürün Adı": u["urun_adi"],
                        "Kategori": u.get("kategori",""),
                        "Marka": u.get("marka",""),
                        "Bizim Stok": u["bizim_stok"],
                        "Ort. Hft. Satış": round(u.get("ortalama_haftalik_satis",0),1),
                        "Stok Yaşı (Gün)": u.get("stok_gun",0),
                        "Durum": u.get("olu_stok_mesaj",""),
                        "_olu": u.get("olu_stok_durum",""),
                    })
    
                df_olu = pd.DataFrame(rows_olu)
    
                def olu_rengi(row):
                    d = row.get("_olu","")
                    cols = list(row.index)
                    if "_olu" in cols:
                        idx = cols.index("_olu")
                    if d == "olu":
                        return ["background-color:#7F0000; color:#FFCDD2; font-weight:700" for _ in row]
                    if d == "yavas":
                        return ["background-color:#BF360C; color:#FFE0B2; font-weight:600" for _ in row]
                    return ["" for _ in row]
    
                goster_olu = ["SKU","Ürün Adı","Kategori","Marka","Bizim Stok","Ort. Hft. Satış","Stok Yaşı (Gün)","Durum"]
                styled_olu = df_olu[goster_olu+["_olu"]].style.apply(olu_rengi, axis=1)
                styled_olu = styled_olu.hide(axis="columns", subset=["_olu"])
                st.dataframe(styled_olu, use_container_width=True, height=400, hide_index=True)
    
                st.markdown("""
                <div class="uyari-box">
                💡 <b>Öneri:</b> Ölü stok ürünler için indirim kampanyası veya paket satış değerlendirilebilir.
                </div>
                """, unsafe_allow_html=True)
    
        # TAB 3 ─────────────────────────────────────────────────────────
        with atab3:
            kategori_ozet = analiz["kategori_ozet"]
            if not kategori_ozet:
                st.info("Kategori verisi bulunamadı.")
            else:
                df_kat = pd.DataFrame([{
                    "Kategori": k,
                    "Ürün Sayısı": v["urun_sayisi"],
                    "Toplam Stok": v["toplam_stok"],
                    "Ort. Hft. Satış": round(v["toplam_satis"],1),
                    "Acil Sipariş": v["acil_sayisi"],
                    "Ölü/Yavaş": v["olu_sayisi"],
                    "Ort. Risk": v["ort_risk"],
                } for k, v in kategori_ozet.items()]).sort_values("Ort. Risk", ascending=False)
    
                def kat_rengi(row):
                    styles = [""] * len(row)
                    cols = list(row.index)
                    if "Acil Sipariş" in cols and row.get("Acil Sipariş",0) > 0:
                        styles[cols.index("Acil Sipariş")] = "background-color:#7F0000; color:#FFCDD2; font-weight:700"
                    if "Ort. Risk" in cols:
                        r = row.get("Ort. Risk",0)
                        if r >= 70: styles[cols.index("Ort. Risk")] = "background-color:#7F0000; color:#FFCDD2; font-weight:700"
                        elif r >= 45: styles[cols.index("Ort. Risk")] = "background-color:#BF360C; color:#FFE0B2"
                        elif r >= 25: styles[cols.index("Ort. Risk")] = "background-color:#827717; color:#FFF176"
                        else: styles[cols.index("Ort. Risk")] = "background-color:#1B5E20; color:#A5D6A7"
                    return styles
    
                st.dataframe(df_kat.style.apply(kat_rengi, axis=1), use_container_width=True, hide_index=True)
    
                if len(df_kat) > 1:
                    fig_kat = px.bar(
                        df_kat, x="Kategori", y="Ort. Hft. Satış",
                        title="Kategori Bazında Haftalık Satış",
                        color="Ort. Risk",
                        color_continuous_scale=[[0,"#1B5E20"],[0.4,"#827717"],[0.7,"#BF360C"],[1,"#7F0000"]],
                        height=350, text="Ort. Hft. Satış",
                    )
                    fig_kat.update_traces(textposition="outside", textfont_color="white")
                    fig_kat.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        font_color="white", title_font_color="#90CAF9",
                        coloraxis_colorbar=dict(tickfont=dict(color="white"), title=dict(text="Risk", font=dict(color="white")))
                    )
                    st.plotly_chart(fig_kat, use_container_width=True)
    
        # TAB 4 ─────────────────────────────────────────────────────────
        with atab4:
            marka_ozet = analiz["marka_ozet"]
            if not marka_ozet:
                st.info("Marka verisi bulunamadı.")
            else:
                df_marka = pd.DataFrame([{
                    "Marka": m,
                    "Ürün Sayısı": v["urun_sayisi"],
                    "Ort. Hft. Satış": round(v["toplam_satis"],1),
                    "Acil Sipariş": v["acil_sayisi"],
                } for m, v in marka_ozet.items()]).sort_values("Ort. Hft. Satış", ascending=False)
    
                def marka_rengi(row):
                    styles = [""] * len(row)
                    cols = list(row.index)
                    if "Acil Sipariş" in cols and row.get("Acil Sipariş",0) > 0:
                        styles[cols.index("Acil Sipariş")] = "background-color:#7F0000; color:#FFCDD2; font-weight:700"
                    if "Ort. Hft. Satış" in cols:
                        styles[cols.index("Ort. Hft. Satış")] = "background-color:#0D2744; color:#90CAF9; font-weight:600"
                    return styles
    
                col_m1, col_m2 = st.columns([1, 1])
                with col_m1:
                    st.dataframe(df_marka.style.apply(marka_rengi, axis=1),
                                 use_container_width=True, hide_index=True)
                with col_m2:
                    if len(df_marka) > 1:
                        fig_marka = px.pie(
                            df_marka, names="Marka", values="Ort. Hft. Satış",
                            title="Marka Bazında Satış Dağılımı",
                            height=350,
                            color_discrete_sequence=["#42A5F5","#66BB6A","#FFA726","#EF5350","#AB47BC","#26C6DA","#D4E157"],
                        )
                        fig_marka.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)",
                            font_color="white",
                            title_font_color="#90CAF9",
                            legend=dict(font=dict(color="white")),
                        )
                        fig_marka.update_traces(textfont_color="white")
                        st.plotly_chart(fig_marka, use_container_width=True)
    
    
    # ════════════════════════════════════════════════════════════════════
    # 4) KAR MARJI ANALİZİ
    # ════════════════════════════════════════════════════════════════════
    elif sayfa == "📋  Tüm Ürünler":
        st.markdown('<div class="baslik">📋 Tüm Ürünler</div>', unsafe_allow_html=True)
        st.markdown('<div class="alt-baslik">FOB Price · Cost · Cost Price · Final Cost Price (Paçal) · Stok Dağılımı</div>', unsafe_allow_html=True)
        st.markdown('<div class="sayfa-baslik-cizgi"></div>', unsafe_allow_html=True)
    
        # ── YENİ ÜRÜN EKLE ──────────────────────────────────────────────
        with st.expander("➕ Yeni Ürün Ekle", expanded=False):
            with st.form("manuel_urun_form", clear_on_submit=True):
                st.markdown("**Temel Bilgiler**")
                fc1, fc2, fc3 = st.columns(3)
                with fc1:
                    m_sku = st.text_input("SKU *", placeholder="örn: X24F165S")
                    m_kategori = st.text_input("Kategori", placeholder="örn: MONİTÖR")
                with fc2:
                    m_urun_adi = st.text_input("Ürün Adı *", placeholder="Tam ürün adı")
                    m_marka = st.text_input("Marka", placeholder="örn: FAZEON")
                with fc3:
                    m_satis = st.number_input("Satış Fiyatı ($)", min_value=0.0, value=0.0, step=0.01, format="%.2f")
                    m_alis = st.number_input("Alış Fiyatı / FOB ($)", min_value=0.0, value=0.0, step=0.01, format="%.2f")
                    m_maliyet_yuzdesi = st.number_input("% Masraf (navlun+gümrük)", min_value=0.0, max_value=100.0, value=0.0, step=0.1, format="%.2f", help="Navlun, gümrük vb. tüm masrafların toplamı")
                    if m_alis > 0 and m_maliyet_yuzdesi > 0:
                        _cost_prev = m_alis * (1 + m_maliyet_yuzdesi / 100)
                        st.info(f"Hesaplanan Maliyet: **${_cost_prev:.2f}** (FOB ${m_alis:.2f} × {1+m_maliyet_yuzdesi/100:.4f})")
    
                st.markdown("**Stok & Hedef**")
                fs1, fs2, fs3 = st.columns(3)
                with fs1:
                    m_stok = st.number_input("Bizim Stok (adet)", min_value=0, value=0, step=1)
                    m_hedef_kar = st.number_input("Hedef Kar Marjı (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.5, format="%.1f")
                with fs2:
                    m_yoldaki = st.number_input("Yoldaki Miktar (adet)", min_value=0, value=0, step=1)
                    m_varis = st.date_input("Tahmini Varış Tarihi", value=None)
                with fs3:
                    m_tedarikci = st.text_input("Yoldaki Tedarikçi", placeholder="örn: ABC Elektronik")
                    m_ozellikler = st.text_area("Özellikler / Notlar", placeholder="Opsiyonel notlar", height=68)
    
                kaydet_btn = st.form_submit_button("💾 Ürünü Kaydet", type="primary", use_container_width=True)
    
            if kaydet_btn:
                if not m_sku.strip():
                    st.error("SKU zorunludur.")
                elif not m_urun_adi.strip():
                    st.error("Ürün Adı zorunludur.")
                    from .database import upsert_urun, upsert_yoldaki_urun, ekle_satin_alma
                    from excel_islemler import normalize_sku
                    sku_temiz = normalize_sku(m_sku.strip())
                    _katsayi = 1 + m_maliyet_yuzdesi / 100
                    _cost_price = round(m_alis * _katsayi, 2) if m_alis > 0 else 0.0
                    _ozellik_str = m_ozellikler.strip()
                    if m_maliyet_yuzdesi > 0:
                        _ozellik_str = (f"Masraf: %{m_maliyet_yuzdesi:.2f} | " + _ozellik_str).strip(" | ")
                    upsert_urun(sku_temiz, m_urun_adi.strip(), m_kategori.strip(),
                               m_marka.strip(), m_satis, _cost_price, m_hedef_kar,
                               _ozellik_str, m_stok, 0)
                    if m_maliyet_yuzdesi > 0 and m_alis > 0:
                        ekle_satin_alma(sku_temiz, m_urun_adi.strip(), "Manuel Giriş",
                                        date.today(), m_stok if m_stok > 0 else 1,
                                        m_alis, m_maliyet_yuzdesi, _ozellik_str)
                    if m_yoldaki > 0 or m_varis:
                        upsert_yoldaki_urun(sku_temiz, m_urun_adi.strip(), m_yoldaki,
                                           str(m_varis) if m_varis else "", m_tedarikci.strip())
                    st.cache_data.clear()
                    st.toast(f"✅ **{sku_temiz}** — {m_urun_adi.strip()} eklendi!")
                    st.rerun()
    
        # Ürün verilerini yükle
        try:
            urun_data = tum_urunler_listesi()
        except Exception as e:
            _log.error("Hata: %s", e)
            st.error(f"Veri yüklenemedi: {e}")
            st.stop()
    
        if not urun_data:
            st.info("Henüz ürün yüklenmemiş. 'Veri Yükleme' sekmesinden G5F STOK dosyasını yükleyin.")
            st.stop()
    
        # Özet metrikler
        toplam_stok_degeri = sum(u.get("stok_degeri_fcp", 0) for u in urun_data)
        toplam_satis_degeri = sum(u.get("stok_degeri_satis", 0) for u in urun_data)
        toplam_genel_stok = sum(u.get("toplam_stok", u.get("bizim_stok", 0)) for u in urun_data)
    
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📦 Toplam Ürün", len(urun_data))
        m2.metric("🏭 Toplam Stok (Tüm Kanallar)", f"{toplam_genel_stok:,} adet")
        m3.metric("💰 Depo Stok Değeri (Cost)", f"${toplam_stok_degeri:,.0f}")
        m4.metric("💵 Depo Stok Değeri (Satış)", f"${toplam_satis_degeri:,.0f}")
    
        st.markdown("---")
    
        # SKU arama + ürün seçimi
        st.markdown('<div style="font-size:11px;font-weight:700;color:#94A3B8;letter-spacing:1px;text-transform:uppercase;margin:2px 0 6px;text-align:center;">🔎 Ürün Ara / Seç</div>', unsafe_allow_html=True)
        _sl_tu, col_sec, _sr_tu = st.columns([1.6, 2.0, 1.6])
        with col_sec:
            sku_secenekler = {u['sku']: u['sku'] for u in urun_data}
            secim = st.selectbox("Ürün Seç", list(sku_secenekler.keys()),
                                 label_visibility="collapsed", key="tu_sku")
    
        secilen_sku = sku_secenekler[secim]
        secilen = next(u for u in urun_data if u["sku"] == secilen_sku)
        firma_st = secilen.get("firma_stoklari", {})
    
        # ── Ürün Başlığı (modern kart) ──
        st.markdown(f"""<div style="display:flex;align-items:center;gap:16px;padding:15px 18px;margin:4px 0 14px;background:linear-gradient(135deg,rgba(99,102,241,0.10),rgba(59,130,246,0.04));border:1px solid rgba(99,102,241,0.18);border-radius:16px;">
 <div style="width:48px;height:48px;border-radius:13px;flex-shrink:0;background:linear-gradient(135deg,#6366F1,#7C3AED);display:flex;align-items:center;justify-content:center;font-size:22px;box-shadow:0 6px 18px rgba(99,102,241,0.35);">📦</div>
 <div style="min-width:0;">
 <div style="font-family:'Manrope','Inter',sans-serif;font-size:18px;font-weight:800;color:#F8FAFC;line-height:1.3;letter-spacing:-0.3px;">{secilen["urun_adi"]}</div>
 <div style="margin-top:7px;"><span style="display:inline-block;padding:3px 11px;border-radius:7px;background:rgba(99,102,241,0.15);border:1px solid rgba(99,102,241,0.25);color:#A5B4FC;font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;letter-spacing:0.5px;">{secilen["sku"]}</span></div>
 </div></div>""", unsafe_allow_html=True)
    
        bizim_stok = secilen.get("bizim_stok", 0)
        toplam_firma = secilen.get("toplam_firma_stok", 0)
        toplam = secilen.get("toplam_stok", bizim_stok + toplam_firma)
    
        # Stok kartları — sadece stoku > 0 olan firmalar
        firma_cards_list = []
        for firma, adet in firma_st.items():
            if adet > 0:
                firma_cards_list.append(
                    f'<div style="background:rgba(27,90,42,0.3); border:1px solid rgba(102,187,106,0.2); border-radius:8px; padding:12px; text-align:center;">'
                    f'<div style="color:#81C784; font-size:10px; font-weight:600; margin-bottom:4px; letter-spacing:0.5px;">{firma}</div>'
                    f'<div style="color:#ECEFF1; font-size:22px; font-weight:800;">{adet:,}</div>'
                    f'<div style="color:#546E7A; font-size:10px;">adet</div>'
                    f'</div>'
                )
        firma_cards = "".join(firma_cards_list)
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:20px; margin-bottom:16px; border:1px solid rgba(255,255,255,0.08)">'
            f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">'
            f'<span style="color:#78909C; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:1.5px;">STOK DAĞILIMI</span>'
            f'<span style="color:#FFD54F; font-size:18px; font-weight:800;">{toplam:,} adet</span>'
            f'</div>'
            f'<div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap:8px;">'
            f'<div style="background:rgba(21,101,192,0.25); border:1px solid rgba(21,101,192,0.3); border-radius:8px; padding:12px; text-align:center;">'
            f'<div style="color:#90CAF9; font-size:10px; font-weight:600; margin-bottom:4px; letter-spacing:0.5px;">G5F DEPO</div>'
            f'<div style="color:#ECEFF1; font-size:22px; font-weight:800;">{bizim_stok:,}</div>'
            f'<div style="color:#546E7A; font-size:10px;">adet</div></div>'
            f'{firma_cards}'
            f'</div></div>',
            unsafe_allow_html=True
        )
    
        # Fiyat ve karlılık kartı
        fob = secilen.get("fob_price") or secilen.get("son_fob") or 0
        cost = secilen.get("cost") or secilen.get("son_cost") or 0
        cost_price = secilen.get("cost_price") or secilen.get("son_cost_price") or 0
        fcp = secilen.get("final_cost_price") or 0
        satis = secilen.get("satis_fiyati") or 0
        mal_y = secilen.get("mal_yuzde") or secilen.get("son_mal_yuzde") or 0
    
        if fob > 0 or fcp > 0:
            satis_html = f'<div style="background:#1a2a3a; border-radius:8px; padding:12px; text-align:center;"><div style="color:#90A4AE; font-size:11px; margin-bottom:4px;">SATIŞ FİYATI</div><div style="color:#29B6F6; font-size:18px; font-weight:700;">${satis:,.2f}</div></div>' if satis > 0 else ""
            kar_html = f'<div style="background:#1B3A2A; border-radius:8px; padding:12px; text-align:center;"><div style="color:#81C784; font-size:11px; margin-bottom:4px;">KAR</div><div style="color:#A5D6A7; font-size:18px; font-weight:700;">${satis-fcp:,.2f} (%{((satis-fcp)/satis*100):.1f})</div></div>' if (satis > 0 and fcp > 0) else ""
            st.markdown(
                f'<div style="background:rgba(255,255,255,0.05); border-radius:12px; padding:20px; margin-bottom:16px; border:1px solid rgba(255,255,255,0.1)">'
                f'<div style="color:#90CAF9; font-size:13px; font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-bottom:14px;">FİYAT ANALİZİ</div>'
                f'<div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap:10px;">'
                f'<div style="background:#1a2a3a; border-radius:8px; padding:12px; text-align:center;"><div style="color:#90A4AE; font-size:11px; margin-bottom:4px;">FOB PRICE</div><div style="color:#FFFFFF; font-size:18px; font-weight:700;">${fob:,.2f}</div></div>'
                f'<div style="background:#1a2a3a; border-radius:8px; padding:12px; text-align:center;"><div style="color:#90A4AE; font-size:11px; margin-bottom:4px;">COST (%{mal_y:.1f})</div><div style="color:#FFA726; font-size:18px; font-weight:700;">${cost:,.2f}</div></div>'
                f'<div style="background:#1a2a3a; border-radius:8px; padding:12px; text-align:center;"><div style="color:#90A4AE; font-size:11px; margin-bottom:4px;">COST PRICE</div><div style="color:#FFFFFF; font-size:18px; font-weight:700;">${cost_price:,.2f}</div></div>'
                f'<div style="background:#1a3a00; border-radius:8px; padding:12px; text-align:center; border:1px solid #FFD54F;"><div style="color:#FFD54F; font-size:11px; font-weight:700; margin-bottom:4px;">⭐ FINAL COST PRICE</div><div style="color:#FFD54F; font-size:22px; font-weight:800;">${fcp:,.2f}</div><div style="color:#A5D6A7; font-size:10px;">Paçal maliyet</div></div>'
                f'{satis_html}{kar_html}'
                f'</div></div>',
                unsafe_allow_html=True
            )
    
        st.markdown("---")
        # Tüm ürünler özet tablosu
        st.markdown("#### 📊 Tüm Ürünler Özet")
        _kat_oz = sorted({(u.get("kategori") or "").strip() for u in urun_data if (u.get("kategori") or "").strip()})
        _mar_oz = sorted({(u.get("marka") or "").strip() for u in urun_data if (u.get("marka") or "").strip()})
        _ozf1, _ozf2, _ozf3, _ozf4 = st.columns([1.3, 1.3, 1.7, 1.1])
        with _ozf1:
            f_kat_oz = st.selectbox("Kategori", ["Tümü"] + _kat_oz, key="oz_kat")
        with _ozf2:
            f_mar_oz = st.selectbox("Marka", ["Tümü"] + _mar_oz, key="oz_mar")
        with _ozf3:
            f_sira_oz = st.selectbox("Sırala", ["Stok Yaşı (gün)", "Net Kâr ($)", "Net Marj (%)", "Maliyet %", "Toplam Stok", "Satış ($)", "FOB ($)", "Risk Skoru", "SKU (A-Z)"], key="oz_sira")
        with _ozf4:
            f_yon_oz = st.selectbox("Yön", ["Azalan", "Artan"], key="oz_yon")
        _sira_map_oz = {"Stok Yaşı (gün)": "_stok_yas", "Net Kâr ($)": "Net Kar ($)", "Net Marj (%)": "Net Marj (%)", "Maliyet %": "Maliyet %", "Toplam Stok": "Toplam", "Satış ($)": "Satış ($)", "FOB ($)": "FOB ($)", "Risk Skoru": "_risk", "SKU (A-Z)": "SKU"}
        rows_oz = []
        for u in urun_data:
            fs = u.get("firma_stoklari", {})
            satis = u.get('satis_fiyati') or 0
            fcp = u.get('final_cost_price') or 0
            fob = u.get('fob_price', u.get('son_fob', 0)) or 0
            maliyet_yuzde = ((fcp / fob - 1) * 100) if (fob > 0 and fcp > 0) else None
            net_kar = (satis - fcp) if (satis > 0 and fcp > 0) else None
            net_marj = ((net_kar / satis) * 100) if (net_kar is not None and satis > 0) else None
            rows_oz.append({
                "SKU": u["sku"],
                "Ürün Adı": u.get("urun_adi", ""),
                "Kategori": u.get("kategori", ""),
                "Marka": u.get("marka", ""),
                "_stok_yas": int(u.get("stok_gun", 0) or 0),
                "_risk": float(u.get("risk_skor", 0) or 0),
                "G5F Depo": int(u.get("bizim_stok", 0) or 0),
                "ITOPYA": int(fs.get("ITOPYA", 0) or 0),
                "HB": int(fs.get("HB", 0) or 0),
                "VATAN": int(fs.get("VATAN", 0) or 0),
                "MONDAY": int(fs.get("MONDAY", 0) or 0),
                "KANAL": int(fs.get("KANAL", 0) or 0),
                "Toplam": int(u.get("toplam_stok", u.get("bizim_stok", 0)) or 0),
                "FOB ($)": float(fob or 0),
                "Maliyet %": float(maliyet_yuzde) if maliyet_yuzde is not None else None,
                "Final Cost ($)": float(fcp or 0),
                "Satış ($)": float(satis or 0),
                "Net Marj (%)": float(net_marj) if net_marj is not None else None,
                "Net Kar ($)": float(net_kar) if net_kar is not None else None,
            })
        # Filtre + sıralama uygula
        if f_kat_oz != "Tümü":
            rows_oz = [r for r in rows_oz if (r.get("Kategori") or "").strip() == f_kat_oz]
        if f_mar_oz != "Tümü":
            rows_oz = [r for r in rows_oz if (r.get("Marka") or "").strip() == f_mar_oz]
        _sk_oz = _sira_map_oz.get(f_sira_oz, "_stok_yas")
        _rev_oz = (f_yon_oz == "Azalan")
        if _sk_oz == "SKU":
            rows_oz.sort(key=lambda r: str(r.get("SKU") or "").lower(), reverse=_rev_oz)
        else:
            _dolu = [r for r in rows_oz if r.get(_sk_oz) not in (None, "")]
            _bos = [r for r in rows_oz if r.get(_sk_oz) in (None, "")]
            _dolu.sort(key=lambda r: float(r.get(_sk_oz) or 0), reverse=_rev_oz)
            rows_oz = _dolu + _bos

        df_oz = pd.DataFrame(rows_oz)
        if df_oz.empty:
            st.info("Henüz ürün yok.")
        else:
            def _fmt_para(v):
                try:
                    return f"${float(v):,.2f}" if v not in (None, "") and float(v) != 0 else "—"
                except Exception:
                    return "—"
            def _fmt_int(v):
                try:
                    return f"{int(v):,}" if v not in (None, "") else "0"
                except Exception:
                    return "0"
            def _fmt_pct(v):
                try:
                    return f"%{float(v):.1f}" if v not in (None, "") else "—"
                except Exception:
                    return "—"
            def _stok_cls(v):
                try:
                    return "c-num" if (v and int(v) > 0) else "c-muted"
                except Exception:
                    return "c-muted"

            satir_html = ""
            for r in rows_oz:
                ad = str(r.get("Ürün Adı", "") or "")
                ad_kisa = ad if len(ad) <= 46 else ad[:45] + "…"
                ad_title = ad.replace(chr(34), "&quot;")
                nk = r.get("Net Kar ($)")
                if nk is None:
                    nk_cls, nk_txt = "c-muted", "—"
                elif nk > 0:
                    nk_cls, nk_txt = "c-pos", f"${nk:,.2f}"
                elif nk < 0:
                    nk_cls, nk_txt = "c-neg", f"${nk:,.2f}"
                else:
                    nk_cls, nk_txt = "c-num", f"${nk:,.2f}"
                nm = r.get("Net Marj (%)")
                if nm is None:
                    nm_cls, nm_txt = "c-muted", "—"
                elif nm > 0:
                    nm_cls, nm_txt = "c-pos", f"%{nm:.1f}"
                elif nm < 0:
                    nm_cls, nm_txt = "c-neg", f"%{nm:.1f}"
                else:
                    nm_cls, nm_txt = "c-num", f"%{nm:.1f}"
                tot = r.get("Toplam") or 0
                tot_cls = "c-tot" if tot else "c-muted"
                fcp = r.get("Final Cost ($)") or 0
                fcp_cls = "c-fcp" if fcp else "c-muted"
                fob_v = r.get("FOB ($)") or 0
                fob_cls = "c-num" if fob_v else "c-muted"
                satis = r.get("Satış ($)") or 0
                satis_cls = "c-money" if satis else "c-muted"
                mal = r.get("Maliyet %")
                mal_cls = "c-mal" if (mal is not None) else "c-muted"
                _kanallar = []
                for _kn, _kl in (("ITOPYA", "IT"), ("HB", "HB"), ("VATAN", "VT"), ("MONDAY", "MN"), ("KANAL", "KN")):
                    _kv = r.get(_kn) or 0
                    if _kv:
                        _kanallar.append(f"{_kl}:{int(_kv)}")
                kanal_str = " · ".join(_kanallar) if _kanallar else "—"
                kanal_title = kanal_str.replace(chr(34), "&quot;")
                satir_html += (
                    "<tr>"
                    f'<td class="c-sku">{r.get("SKU","")}</td>'
                    f'<td class="c-name" title="{ad_title}">{ad_kisa}</td>'
                    f'<td class="c-kat">{r.get("Kategori","")}</td>'
                    f'<td class="{_stok_cls(r.get("G5F Depo"))}">{_fmt_int(r.get("G5F Depo"))}</td>'
                    f'<td class="c-kanal" title="{kanal_title}">{kanal_str}</td>'
                    f'<td class="{tot_cls}">{_fmt_int(tot)}</td>'
                    f'<td class="{fob_cls}">{_fmt_para(fob_v)}</td>'
                    f'<td class="{mal_cls}">{_fmt_pct(mal)}</td>'
                    f'<td class="{fcp_cls}">{_fmt_para(fcp)}</td>'
                    f'<td class="{satis_cls}">{_fmt_para(satis)}</td>'
                    f'<td class="{nm_cls}">{nm_txt}</td>'
                    f'<td class="{nk_cls}">{nk_txt}</td>'
                    "</tr>"
                )
            css = (
                "<style>"
                ".urun-wrap{overflow-x:auto;border-radius:14px;box-shadow:0 2px 16px rgba(0,0,0,0.25);margin-top:6px}"
                ".urun-tbl{width:100%;table-layout:fixed;border-collapse:collapse;font-family:Inter,sans-serif}"
                ".urun-tbl thead tr{background:linear-gradient(135deg,#1E293B,#0F172A)}"
                ".urun-tbl thead th{padding:8px 6px;color:#CBD5E1;font-size:9.5px;font-weight:700;letter-spacing:.2px;text-transform:uppercase;white-space:normal;line-height:1.2;text-align:center;vertical-align:middle}"
                ".urun-tbl thead th.l{text-align:left}"
                ".urun-tbl tbody{background:#131C35}"
                ".urun-tbl td{padding:7px 8px;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
                ".urun-tbl tbody tr{border-bottom:1px solid rgba(255,255,255,0.05)}"
                ".urun-tbl tbody tr:hover{background:rgba(99,102,241,0.06)}"
                ".c-sku{color:#E2E8F0;font-family:'JetBrains Mono',monospace;font-weight:600;white-space:nowrap}"
                ".c-name{color:#CBD5E1;max-width:300px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
                ".c-kat{color:#94A3B8;font-size:11px}"
                ".c-kanal{text-align:left;color:#94A3B8;font-family:'JetBrains Mono',monospace;font-size:11px;max-width:175px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
                ".c-num{text-align:right;color:#CBD5E1;font-family:'JetBrains Mono',monospace}"
                ".c-dim{text-align:right;color:#94A3B8;font-family:'JetBrains Mono',monospace}"
                ".c-money{text-align:right;color:#E2E8F0;font-family:'JetBrains Mono',monospace;font-weight:600}"
                ".c-mal{text-align:right;color:#C4B5FD;font-family:'JetBrains Mono',monospace}"
                ".c-pos{text-align:right;color:#4ADE80;font-weight:700;font-family:'JetBrains Mono',monospace}"
                ".c-neg{text-align:right;color:#F87171;font-weight:700;font-family:'JetBrains Mono',monospace}"
                ".c-fcp{text-align:right;color:#FBBF24;font-weight:600;font-family:'JetBrains Mono',monospace}"
                ".c-tot{text-align:right;color:#93C5FD;font-weight:700;font-family:'JetBrains Mono',monospace}"
                ".c-muted{text-align:right;color:#475569;font-family:'JetBrains Mono',monospace}"
                "</style>"
            )
            thead = (
                '<div class="urun-wrap"><table class="urun-tbl">'
                '<colgroup>'
                '<col style="width:7%"><col style="width:18%"><col style="width:7%">'
                '<col style="width:6%"><col style="width:12%"><col style="width:7%">'
                '<col style="width:7%"><col style="width:7%"><col style="width:8%">'
                '<col style="width:7%"><col style="width:7%"><col style="width:8%">'
                '</colgroup>'
                '<thead><tr>'
                '<th class="l">SKU</th><th class="l">Ürün Adı</th><th class="l">Kategori</th>'
                '<th>G5F</th><th class="l">Kanal Stok</th><th>Toplam</th>'
                "<th>FOB</th><th>Maliyet %</th><th>⭐ Final Cost</th><th>Satış</th>"
                "<th>📊 Net Marj %</th><th>💰 Net Kâr $</th>"
                "</tr></thead><tbody>"
            )
            st.html(css + thead + satir_html + "</tbody></table></div>")
            st.caption("💡 Maliyet % = (Final Cost / FOB − 1) × 100  ·  Net Kâr $ = Satış − Final Cost  ·  Net Marj % = Net Kâr / Satış × 100")

            with st.expander("✏️ Ürün Düzenle", expanded=False):
                st.caption("Açılır listeden ürünü seç, alanları düzenle, **Kaydet**'e bas.")
                _sec_list = {f'{u["sku"]} — {(u.get("urun_adi") or "")[:50]}': u["sku"] for u in urun_data}
                if _sec_list:
                    _sec_label = st.selectbox("Düzenlenecek ürün", list(_sec_list.keys()), key="urun_duzen_sec")
                    _sec_sku = _sec_list[_sec_label]
                    _u = next((x for x in urun_data if x["sku"] == _sec_sku), {})
                    with st.form("urun_duzen_form"):
                        fc1, fc2, fc3, fc4 = st.columns([3, 1.5, 1.2, 1])
                        with fc1:
                            d_ad = st.text_input("Ürün Adı", value=_u.get("urun_adi", "") or "")
                        with fc2:
                            d_kat = st.text_input("Kategori", value=_u.get("kategori", "") or "")
                        with fc3:
                            d_satis = st.number_input("Satış ($)", value=float(_u.get("satis_fiyati", 0) or 0), min_value=0.0, step=1.0, format="%.2f")
                        with fc4:
                            d_stok = st.number_input("G5F Depo", value=int(_u.get("bizim_stok", 0) or 0), min_value=0, step=1)
                        if st.form_submit_button("💾 Kaydet", type="primary", use_container_width=True):
                            from .database import upsert_urun as _upsert_urun
                            try:
                                _upsert_urun(
                                    _sec_sku, d_ad.strip(), d_kat.strip(),
                                    _u.get("marka", "") or "", float(d_satis or 0),
                                    float(_u.get("alis_fiyati", 0) or 0), float(_u.get("hedef_kar_marji", 0) or 0),
                                    _u.get("ozellikler", "") or "", int(d_stok or 0),
                                    int(_u.get("trendyol_stok", 0) or 0),
                                )
                                st.cache_data.clear()
                                st.success(f"✅ {_sec_sku} güncellendi.")
                                st.rerun()
                            except Exception as _e:
                                st.error(f"Kaydedilemedi: {_e}")
    
        # ── Ürün Silme ────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### 🗑️ Ürün Sil")
        st.caption("Seçilen ürünü ve tüm ilgili kayıtlarını (firma stok, satın alma geçmişi, sipariş önerileri) siler. Bu işlem geri alınamaz.")
    
        tum_sku = get_tum_sku_listesi()
        if tum_sku:
            sil_col1, sil_col2 = st.columns([3, 1])
            with sil_col1:
                # SKU arama ile filtrele
                sil_ara = st.text_input("SKU veya ürün adı ile ara", placeholder="Aramak için yaz...", key="sil_ara")
                if sil_ara:
                    filtrelenmis_sil = [u for u in tum_sku if u["sku"].upper().startswith(sil_ara.upper()) or sil_ara.lower() in (u.get("urun_adi","") or "").lower()]
                else:
                    filtrelenmis_sil = tum_sku
    
                sil_secenekler = {f"{u['sku']} — {(u.get('urun_adi') or '')[:50]}": u["sku"] for u in filtrelenmis_sil}
                if sil_secenekler:
                    sil_secim = st.selectbox("Silinecek Ürün", list(sil_secenekler.keys()), key="sil_secim")
                    sil_sku = sil_secenekler[sil_secim]
                else:
                    st.info("Eşleşen ürün bulunamadı.")
                    sil_sku = None
    
            with sil_col2:
                st.markdown("<br><br>", unsafe_allow_html=True)
                if sil_sku:
                    # Onay mekanizması
                    onay = st.checkbox(f"Silmeyi onaylıyorum", key="sil_onay")
                    if st.button("🗑️ Sil", type="primary", use_container_width=True, disabled=not onay):
                        sil_urun(sil_sku)
                        st.cache_data.clear()
                        st.toast(f"✅ {sil_sku} silindi.")
                        st.rerun()
    
    
    elif sayfa == "🛒  Satın Alma Geçmişi":
        st.markdown('<div class="baslik">🛒 Satın Alma Geçmişi</div>', unsafe_allow_html=True)
        st.markdown('<div class="alt-baslik">Tedarikçi · FOB Price · Cost Price · Paçal hesabı</div>', unsafe_allow_html=True)
        st.markdown('<div class="sayfa-baslik-cizgi"></div>', unsafe_allow_html=True)
    
        with st.expander("➕ Yeni Satın Alma Ekle", expanded=False):
            _urunler_sa = tum_urunler_listesi()
            _sa_map = {f'{u["sku"]} — {u.get("urun_adi","")}': u for u in _urunler_sa}
            _sa_label = st.selectbox("Ürün *", list(_sa_map.keys()) or ["—"], key="sa_ekle_urun")
            _sa_urun = _sa_map.get(_sa_label, {})
            _sa_sku = _sa_urun.get("sku", "")
            _sa_urun_adi = _sa_urun.get("urun_adi", "")
    
            # Manuel veya Excel seçimi
            ekle_tab1, ekle_tab2 = st.tabs(["📝 Manuel Giriş", "📊 Excel ile Toplu Yükle"])
    
            with ekle_tab1:
                onceki = get_tum_tedarikciler()
                with st.form("tu_satin_alma_form", clear_on_submit=True):
                    fc1, fc2 = st.columns(2)
                    with fc1:
                        tedarikci = st.text_input("Tedarikçi *",
                            help=f"Önceki: {', '.join(onceki[:4])}" if onceki else "")
                        satin_alma_tarihi = st.date_input("Tarih *", value=tr_today())
                        notlar = st.text_area("Notlar")
                    with fc2:
                        adet = st.number_input("Adet *", min_value=1, value=100, step=1)
                        fob_price = st.number_input("FOB Price ($) *", min_value=0.0, value=0.0, step=0.01, format="%.2f")
                        maliyet_yuzdesi = st.number_input("Ek Maliyet (%)", min_value=0.0, max_value=200.0, value=0.0, step=0.5, format="%.1f",
                            help="Nakliye+gümrük+diğer masrafların FOB'a oranı")
                        if fob_price > 0:
                            cost = fob_price * maliyet_yuzdesi / 100
                            cp = fob_price + cost
                            st.markdown(f'<div class="info-box" style="font-size:12px">FOB: ${fob_price:.2f} + Cost: ${cost:.2f} = <b>Cost Price: ${cp:.2f}</b><br>Toplam: ${cp * adet:,.0f}</div>', unsafe_allow_html=True)
                    submitted = st.form_submit_button("💾 Kaydet", type="primary", use_container_width=True)
    
                if submitted:
                    if not tedarikci.strip(): st.error("Tedarikçi zorunludur.")
                    elif fob_price <= 0: st.error("FOB Price girilmesi zorunludur.")
                    else:
                        ekle_satin_alma(_sa_sku, _sa_urun_adi, tedarikci.strip(),
                                        str(satin_alma_tarihi), adet, fob_price, maliyet_yuzdesi, notlar.strip())
                        cp = fob_price * (1 + maliyet_yuzdesi/100)
                        st.success(f"✅ Kaydedildi! Cost Price: ${cp:.2f}/adet")
                        st.cache_data.clear()
                        st.rerun()
    
            with ekle_tab2:
                # Şablon indir
                st.caption("Şablonu indirip doldurun, ardından yükleyin.")
    
                import io
                sablon_data = {
                    "SKU": [_sa_sku, ""],
                    "Tedarikçi": ["MASTER", ""],
                    "Tarih": [str(tr_today()), ""],
                    "Adet": [100, ""],
                    "FOB Price ($)": [0.0, ""],
                    "Cost %": [0.0, ""],
                    "Notlar": ["", ""],
                }
                df_sablon = pd.DataFrame(sablon_data)
                sablon_buf = io.BytesIO()
                with pd.ExcelWriter(sablon_buf, engine="openpyxl") as writer:
                    df_sablon.to_excel(writer, index=False, sheet_name="Satın Alma")
                sablon_buf.seek(0)
                st.download_button(
                    "📥 Excel Şablonunu İndir",
                    sablon_buf,
                    "satin_alma_sablon.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    
                st.markdown("---")
                excel_file = st.file_uploader("Excel Dosyası Yükle", type=["xlsx","xls"], key="tu_sa_excel")
                if excel_file:
                    try:
                        df_yukle = pd.read_excel(excel_file)
                        # Kolon normalize
                        df_yukle.columns = [str(c).strip() for c in df_yukle.columns]
    
                        # Önizleme
                        st.markdown("**📋 Önizleme:**")
                        st.dataframe(df_yukle, use_container_width=True, hide_index=True)
    
                        if st.button("⬆️ Tümünü Yükle", type="primary", key="tu_sa_yukle"):
                            basarili = 0
                            hatali = 0
                            hatalar = []
                            for _, row in df_yukle.iterrows():
                                try:
                                    r_sku = str(row.get("SKU", _sa_sku)).strip() or _sa_sku
                                    r_ted = str(row.get("Tedarikçi", "")).strip()
                                    r_tarih = str(row.get("Tarih", str(tr_today()))).strip()[:10]
                                    r_adet = int(row.get("Adet", 0) or 0)
                                    r_fob = float(row.get("FOB Price ($)", 0) or 0)
                                    r_cost = float(row.get("Cost %", 0) or 0)
                                    r_not = str(row.get("Notlar", "") or "").strip()
    
                                    if not r_sku or r_sku == "nan": continue
                                    if r_fob <= 0: 
                                        hatalar.append(f"{r_sku}: FOB Price sıfır")
                                        hatali += 1
                                        continue
    
                                    # Ürün adını bul
                                    r_urun = next((u["urun_adi"] for u in urun_data if u["sku"] == r_sku), r_sku)
    
                                    ekle_satin_alma(r_sku, r_urun, r_ted, r_tarih,
                                                   r_adet, r_fob, r_cost, r_not)
                                    basarili += 1
                                except Exception as e:
                                    hatali += 1
                                    hatalar.append(str(e))
    
                            st.cache_data.clear()
                            if basarili > 0:
                                st.success(f"✅ {basarili} kayıt başarıyla yüklendi!")
                            if hatali > 0:
                                st.warning(f"⚠️ {hatali} kayıt atlandı: {' | '.join(hatalar[:3])}")
                            st.rerun()
                    except Exception as e:
                        _log.error("Hata: %s", e)
                        st.error(f"Dosya okunamadı: {e}")
        st.markdown("---")
        tum_kayitlar = get_satin_alma_gecmisi()
    
        if not tum_kayitlar:
            st.info("Henüz satın alma kaydı yok. Yukarıdaki '➕ Yeni Satın Alma Ekle' bölümünden ekleyebilirsiniz.")
            st.stop()
    
        # Filtreler
        fc1, fc2, fc3, fc4 = st.columns([1, 2, 2, 1])
        with fc1:
            sku_ara_sg = st.text_input("🔍 SKU Ara", placeholder="SKU yaz...", key="sg_sku_ara")
        with fc2:
            try:
                urun_data_f = tum_urunler_listesi()
                if sku_ara_sg:
                    filtre_urunler = [u for u in urun_data_f if u["sku"].upper().startswith(sku_ara_sg.upper()) or sku_ara_sg.lower() in u["urun_adi"].lower()]
                else:
                    filtre_urunler = urun_data_f
                sku_filtre_options = ["Tüm Ürünler"] + [f"{u['sku']} — {u['urun_adi']}" for u in filtre_urunler]
            except Exception:
                sku_filtre_options = ["Tüm Ürünler"]
            sku_filtre = st.selectbox("Ürün", sku_filtre_options, key="sg_sku", label_visibility="collapsed")
        with fc3:
            ted_filtre = st.text_input("Tedarikçi Ara", placeholder="Tedarikçi adı...", key="sg_ted")
        with fc4:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄", use_container_width=True, key="sg_yenile"):
                st.rerun()
    
        # Filtrele
        kayitlar = tum_kayitlar
        if sku_filtre != "Tüm Ürünler":
            filtre_sku = sku_filtre.split(" — ")[0]
            kayitlar = [k for k in kayitlar if k["sku"] == filtre_sku]
        if ted_filtre:
            kayitlar = [k for k in kayitlar if ted_filtre.lower() in (k.get("tedarikci","") or "").lower()]
    
        # Özet metrikler
        tm1, tm2, tm3, tm4 = st.columns(4)
        tm1.metric("📋 Toplam Kayıt", len(kayitlar))
        tm2.metric("📦 Toplam Adet", f"{sum(k.get('adet',0) for k in kayitlar):,}")
        toplam_fob_tutar = sum((k.get('alis_fiyati') or k.get('birim_alis_fiyati') or 0) * (k.get('adet') or 0) for k in kayitlar)
        toplam_cp_tutar = sum(k.get('toplam_maliyet') or 0 for k in kayitlar)
        tm3.metric("💵 Toplam FOB Tutar", f"${toplam_fob_tutar:,.0f}")
        tm4.metric("💰 Toplam Cost Tutar", f"${toplam_cp_tutar:,.0f}")
    
        st.markdown("---")
    
        # Düzenlenebilir tablo
        rows_sg = []
        for k in kayitlar:
            fob = k.get("alis_fiyati") or k.get("birim_alis_fiyati") or 0
            mal_y = k.get("maliyet_yuzdesi") or 0
            rows_sg.append({
                "ID": k["id"],
                "Tarih": k.get("satin_alma_tarihi",""),
                "SKU": k["sku"],
                "Ürün Adı": k.get("urun_adi",""),
                "Tedarikçi": k.get("tedarikci","") or "",
                "Adet": int(k.get("adet",0) or 0),
                "FOB ($)": float(fob),
                "Cost %": float(mal_y),
                "Notlar": k.get("notlar","") or "",
            })
    
        df_sg = pd.DataFrame(rows_sg)
    
        st.caption("✏️ Hücreye tıklayarak düzenle, ardından **Değişiklikleri Kaydet** butonuna bas.")
    
        edited_df = st.data_editor(
            df_sg.drop(columns=["ID"]),
            use_container_width=True,
            hide_index=True,
            height=400,
            column_config={
                "Tarih": st.column_config.TextColumn("Tarih", help="YYYY-MM-DD formatında"),
                "SKU": st.column_config.TextColumn("SKU", disabled=True),
                "Ürün Adı": st.column_config.TextColumn("Ürün Adı", disabled=True),
                "Tedarikçi": st.column_config.TextColumn("Tedarikçi"),
                "Adet": st.column_config.NumberColumn("Adet", min_value=0, step=1, format="%d"),
                "FOB ($)": st.column_config.NumberColumn("FOB ($)", min_value=0.0, format="$%.2f"),
                "Cost %": st.column_config.NumberColumn("Cost %", min_value=0.0, max_value=100.0, format="%.1f%%"),
                "Notlar": st.column_config.TextColumn("Notlar"),
            },
            key="sg_editor"
        )
    
        if st.button("💾 Değişiklikleri Kaydet", type="primary", use_container_width=False, key="sg_kaydet"):
            degisen = 0
            for i, (orig, edit) in enumerate(zip(rows_sg, edited_df.to_dict("records"))):
                kayit_id = orig["ID"]
                # Tarih string'e çevir
                tarih_val = str(edit.get("Tarih", orig["Tarih"]))
                if tarih_val == "None" or tarih_val == "nan":
                    tarih_val = orig["Tarih"]
                guncelle_satin_alma(
                    kayit_id,
                    edit.get("Tedarikçi", orig["Tedarikçi"]),
                    tarih_val,
                    int(edit.get("Adet", orig["Adet"]) or 0),
                    float(edit.get("FOB ($)", orig["FOB ($)"]) or 0),
                    float(edit.get("Cost %", orig["Cost %"]) or 0),
                    edit.get("Notlar", orig["Notlar"]) or ""
                )
                degisen += 1
            st.cache_data.clear()
            st.toast(f"✅ {degisen} kayıt güncellendi!")
            st.rerun()
    
        # Silme
        with st.expander("🗑️ Kayıt Sil"):
            sil_options = {f"#{k['id']} | {k.get('satin_alma_tarihi','')} | {k['sku']} | {k.get('adet',0)} adet": k['id'] for k in kayitlar}
            sil_secim = st.selectbox("Silinecek Kayıt", list(sil_options.keys()), key="sg_sil_sec")
            if st.button("🗑️ Sil", key="sg_sil_btn", type="secondary"):
                sil_satin_alma(sil_options[sil_secim])
                st.cache_data.clear()
                st.toast("Kayıt silindi.")
                st.rerun()
    
        # Tedarikçi bazında özet grafik
        if len(kayitlar) > 1:
            ted_tutar = {}
            for k in kayitlar:
                t = k.get("tedarikci","Diğer") or "Diğer"
                fob = k.get("alis_fiyati") or k.get("birim_alis_fiyati") or 0
                mal_y = k.get("maliyet_yuzdesi") or 0
                cp = fob * (1 + mal_y/100)
                ted_tutar[t] = ted_tutar.get(t,0) + cp * (k.get("adet") or 0)
            df_ted = pd.DataFrame([{"Tedarikçi":k,"Tutar ($)":v} for k,v in ted_tutar.items()])
            fig_ted = px.pie(df_ted, names="Tedarikçi", values="Tutar ($)",
                             title="Tedarikçi Bazında Cost Tutar Dağılımı",
                             height=300, color_discrete_sequence=["#42A5F5","#66BB6A","#FFA726","#EF5350","#AB47BC","#26C6DA","#D4E157","#FF7043"])
            fig_ted.update_layout(paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_ted, use_container_width=True)
    
    
    elif sayfa == "🎯  Kampanya Takip":
        st.markdown('<div class="baslik">🎯 Kampanya Takip</div>', unsafe_allow_html=True)
        st.markdown('<div class="alt-baslik">Firma desteği · Net kar · Kampanya performansı</div>', unsafe_allow_html=True)
        st.markdown('<div class="sayfa-baslik-cizgi"></div>', unsafe_allow_html=True)
    
        FIRMA_LISTESI_K = ["ITOPYA", "HB", "VATAN", "MONDAY", "KANAL", "DİĞER"]
    
        # Ürün verisi (paçal maliyet için)
        try:
            urun_data_k = tum_urunler_listesi()
            urun_dict_k = {u["sku"]: u for u in urun_data_k}
            sku_listesi_k = {f"{u['sku']} — {u['urun_adi']}": u['sku'] for u in urun_data_k}
        except Exception:
            urun_data_k = []
            urun_dict_k = {}
            sku_listesi_k = {}
    
        # ── Sekmeler ─────────────────────────────────────────────────────
        ktab1, ktab2 = st.tabs(["📢 Aktif Kampanyalar", "📁 Geçmiş Kampanyalar"])
    
        # ─────────────────────────────────────────────────────────────────
        # TAB 1: AKTİF KAMPANYALAR
        # ─────────────────────────────────────────────────────────────────
        with ktab1:
            # Yeni kampanya oluştur
            with st.expander("➕ Yeni Kampanya Oluştur", expanded=False):
                with st.form("yeni_kampanya_form", clear_on_submit=True):
                    kf1, kf2 = st.columns(2)
                    with kf1:
                        k_adi = st.text_input("Kampanya Adı *", placeholder="örn: Hepsiburada Mart Kampanyası")
                        k_firma = st.selectbox("Firma *", FIRMA_LISTESI_K)
                    with kf2:
                        k_bas = st.date_input("Başlangıç Tarihi *", value=tr_today())
                        k_bit = st.date_input("Bitiş Tarihi *", value=tr_today())
                    k_not = st.text_area("Notlar", placeholder="Kampanya hakkında notlar...")
                    if st.form_submit_button("🚀 Kampanya Oluştur", type="primary", use_container_width=True):
                        if not k_adi.strip():
                            st.error("Kampanya adı zorunludur.")
                        else:
                            yeni_id = ekle_kampanya(k_adi.strip(), k_firma, str(k_bas), str(k_bit), k_not.strip())
                            st.cache_data.clear()
                            st.toast(f"✅ '{k_adi}' kampanyası oluşturuldu! (ID: {yeni_id})")
                            st.rerun()
    
            # Aktif kampanyaları listele
            aktif_kampanyalar = get_kampanyalar(durum="aktif")
            if not aktif_kampanyalar:
                st.info("Aktif kampanya yok. Yukarıdan yeni kampanya oluşturabilirsiniz.")
            else:
                # ── KAMPANYA PANOSU (üstte hızlı özet) ──
                _bugun = tr_today()
                _pano = []
                for _k in aktif_kampanyalar:
                    _ku = get_kampanya_urunler(_k["id"])
                    _sat = 0
                    _net = 0.0
                    for _x in _ku:
                        _p = _x.get("pacal_maliyet") or 0
                        _s = _x.get("satis_fiyati") or 0
                        _fd = _x.get("birim_firma_destek") or 0
                        _ed = _x.get("birim_ek_destek") or 0
                        _ad = _x.get("satilan_adet") or 0
                        if _s > 0 and _p > 0:
                            _net += ((_s - _p) - (_fd + _ed)) * _ad
                        _sat += _ad
                    try:
                        _bit = date.fromisoformat(_k["bitis_tarihi"]) if _k.get("bitis_tarihi") else None
                        _kalan = (_bit - _bugun).days if _bit else None
                    except Exception:
                        _kalan = None
                    if _kalan is None:
                        _kalan_txt = "—"
                    elif _kalan < 0:
                        _kalan_txt = f"🔴 {abs(_kalan)}g geçti"
                    elif _kalan < 7:
                        _kalan_txt = f"🔴 {_kalan}g kaldı"
                    elif _kalan < 30:
                        _kalan_txt = f"🟠 {_kalan}g kaldı"
                    else:
                        _kalan_txt = f"🟢 {_kalan}g kaldı"
                    _pano.append({
                        "Kampanya": _k["kampanya_adi"],
                        "Firma": _k["firma"],
                        "Kalan": _kalan_txt,
                        "Ürün": len(_ku),
                        "Satılan": _sat,
                        "Net Kâr ($)": round(_net, 2),
                    })
                st.markdown('<div style="font-size:13px;font-weight:700;color:#E2E8F0;margin:4px 0 6px;">📊 Kampanya Panosu — tüm aktif kampanyalar tek bakışta</div>', unsafe_allow_html=True)
                render_renkli_tablo(
                    pd.DataFrame(_pano),
                    para=["Net Kâr ($)"],
                    kar=["Net Kâr ($)"],
                    sol=["Kampanya", "Firma", "Kalan"],
                    kisalt={"Kampanya": 32},
                )
                st.markdown("---")
                for kamp in aktif_kampanyalar:
                    kid = kamp["id"]
                    k_urunler = get_kampanya_urunler(kid)
    
                    # Kampanya başlık kartı
                    st.markdown(f"""
                    <div style="background:rgba(255,255,255,0.05); border-radius:12px; padding:16px 20px;
                                margin:12px 0 8px; border-left:5px solid #42A5F5;">
                      <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                          <span style="color:#90CAF9; font-size:18px; font-weight:800;">📢 {kamp["kampanya_adi"]}</span>
                          <span style="background:#1F4E79; color:#90CAF9; padding:2px 10px; border-radius:10px;
                                      font-size:12px; margin-left:10px; font-weight:600;">{kamp["firma"]}</span>
                          <span style="background:#1B5E20; color:#A5D6A7; padding:2px 10px; border-radius:10px;
                                      font-size:12px; margin-left:6px;">● AKTİF</span>
                        </div>
                        <span style="color:#90A4AE; font-size:12px;">
                          {kamp["baslangic_tarihi"]} → {kamp["bitis_tarihi"]}
                        </span>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
    
                    # Kampanya düzenleme
                    with st.expander(f"✏️ Kampanya Bilgilerini Düzenle — {kamp['kampanya_adi']}"):
                        # ── Kampanya Genel Bilgileri ──
                        st.markdown("**📋 Kampanya Bilgileri**")
                        with st.form(f"duzenle_kamp_{kid}"):
                            dk1, dk2 = st.columns(2)
                            with dk1:
                                dk_adi = st.text_input("Kampanya Adı", value=kamp["kampanya_adi"], key=f"dk_adi_{kid}")
                                dk_firma = st.selectbox("Firma", FIRMA_LISTESI_K,
                                    index=FIRMA_LISTESI_K.index(kamp["firma"]) if kamp["firma"] in FIRMA_LISTESI_K else 0,
                                    key=f"dk_firma_{kid}")
                            with dk2:
                                dk_bas = st.date_input("Başlangıç Tarihi", value=date.fromisoformat(kamp["baslangic_tarihi"]) if kamp["baslangic_tarihi"] else tr_today(), key=f"dk_bas_{kid}")
                                dk_bit = st.date_input("Bitiş Tarihi", value=date.fromisoformat(kamp["bitis_tarihi"]) if kamp["bitis_tarihi"] else tr_today(), key=f"dk_bit_{kid}")
                            dk_not = st.text_area("Notlar", value=kamp.get("notlar","") or "", key=f"dk_not_{kid}")
                            dc1_k, dc2_k, dc3_k = st.columns(3)
                            with dc1_k:
                                if st.form_submit_button("💾 Kampanyayı Güncelle", use_container_width=True, type="primary"):
                                    guncelle_kampanya(kid, dk_adi, dk_firma, str(dk_bas), str(dk_bit), dk_not)
                                    st.cache_data.clear()
                                    st.toast("✅ Kampanya güncellendi!")
                                    st.rerun()
                            with dc2_k:
                                kapat_flag = st.form_submit_button("🔒 Kampanyayı Kapat", use_container_width=True)
                            with dc3_k:
                                if st.form_submit_button("🗑️ Kampanyayı Sil", use_container_width=True):
                                    sil_kampanya(kid)
                                    st.cache_data.clear()
                                    st.warning("Kampanya silindi.")
                                    st.rerun()
    
                        # Kampanya kapat — adet sor (kapat_flag form içinden geliyor, güvenli)
                        if locals().get('kapat_flag', False):
                            st.session_state[f"kapat_onay_{kid}"] = True
    
                        if st.session_state.get(f"kapat_onay_{kid}"):
                            st.markdown("---")
                            st.markdown("**🔒 Kampanyayı Kapat — Satış Adetlerini Gir**")
                            st.caption("Kampanya kapanmadan önce her ürün için satılan adeti girin.")
                            with st.form(f"kapat_form_{kid}", clear_on_submit=True):
                                adet_girisleri = {}
                                for ku in k_urunler:
                                    kf1, kf2, kf3 = st.columns([2, 2, 1])
                                    with kf1:
                                        st.markdown(f'<span style="color:#90CAF9; font-size:13px; font-weight:600;">{ku["sku"]}</span>'
                                                   f'<span style="color:#546E7A; font-size:11px;"> — {ku.get("urun_adi","")[:40]}</span>',
                                                   unsafe_allow_html=True)
                                    with kf2:
                                        adet_girisleri[ku["id"]] = st.number_input(
                                            "Satılan Adet",
                                            value=int(ku.get("satilan_adet",0) or 0),
                                            min_value=0, step=1,
                                            key=f"kapat_adet_{kid}_{ku['id']}",
                                            label_visibility="collapsed"
                                        )
                                    with kf3:
                                        st.markdown(f'<span style="color:#78909C; font-size:11px;">mevcut: {ku.get("satilan_adet",0)}</span>', unsafe_allow_html=True)
    
                                kk1, kk2 = st.columns(2)
                                with kk1:
                                    if st.form_submit_button("✅ Kaydet ve Kapat", type="primary", use_container_width=True):
                                        for ku_id_k, adet_k in adet_girisleri.items():
                                            ku_bilgi = next((x for x in k_urunler if x["id"] == ku_id_k), {})
                                            guncelle_kampanya_urun(ku_id_k,
                                                ku_bilgi.get("satis_fiyati",0),
                                                ku_bilgi.get("birim_firma_destek",0),
                                                ku_bilgi.get("birim_ek_destek",0),
                                                adet_k,
                                                ku_bilgi.get("notlar",""))
                                        kapat_kampanya(kid)
                                        st.session_state.pop(f"kapat_onay_{kid}", None)
                                        st.cache_data.clear()
                                        st.toast("🔒 Kampanya kapatıldı ve satış adetleri kaydedildi!")
                                        st.rerun()
                                with kk2:
                                    if st.form_submit_button("İptal", use_container_width=True):
                                        st.session_state.pop(f"kapat_onay_{kid}", None)
                                        st.rerun()
    
                        # ── Ürün Bazında Düzenleme ──
                        if k_urunler:
                            st.markdown("---")
                            st.markdown("**🛍️ Ürün Bilgilerini Düzenle**")
                            st.caption("Her ürün için SKU, satış fiyatı, birim destek ve satılan adeti ayrı ayrı düzenleyebilirsiniz.")
    
                            for ku in k_urunler:
                                ku_id = ku["id"]
                                pacal_ku = ku.get("pacal_maliyet") or 0
                                # Paçal 0 ise güncel değer
                                if pacal_ku == 0:
                                    pacal_ku = urun_dict_k.get(ku["sku"], {}).get("final_cost_price", 0)
    
                                with st.form(f"urun_gun_{kid}_{ku_id}", clear_on_submit=False):
                                    st.markdown(f'<div style="background:rgba(255,255,255,0.04); border-radius:8px; padding:10px 14px; margin-bottom:6px;">'
                                                f'<span style="color:#90CAF9; font-weight:700; font-size:13px;">📦 {ku.get("urun_adi","")}</span>'
                                                f'<span style="color:#546E7A; font-size:11px; margin-left:8px;">SKU: {ku["sku"]}</span>'
                                                f'</div>', unsafe_allow_html=True)
    
                                    ug1, ug2, ug3, ug4 = st.columns(4)
                                    with ug1:
                                        ug_satis = st.number_input(
                                            "Müşteriye Fiyat ($)",
                                            value=float(ku.get("satis_fiyati", 0) or 0),
                                            step=0.01, format="%.2f",
                                            key=f"ug_s_{kid}_{ku_id}"
                                        )
                                    with ug2:
                                        ug_fd = st.number_input(
                                            "Birim Firma Desteği ($)",
                                            value=float(ku.get("birim_firma_destek", 0) or 0),
                                            step=0.01, format="%.2f",
                                            key=f"ug_fd_{kid}_{ku_id}"
                                        )
                                    with ug3:
                                        ug_ed = st.number_input(
                                            "Birim Ek Destek ($)",
                                            value=float(ku.get("birim_ek_destek", 0) or 0),
                                            step=0.01, format="%.2f",
                                            key=f"ug_ed_{kid}_{ku_id}"
                                        )
                                    with ug4:
                                        ug_satilan = st.number_input(
                                            "Satılan Adet",
                                            value=int(ku.get("satilan_adet", 0) or 0),
                                            min_value=0, step=1,
                                            key=f"ug_sa_{kid}_{ku_id}"
                                        )
    
                                    # Canlı hesap göster
                                    if pacal_ku > 0 and ug_satis > 0:
                                        toplam_destek = ug_fd + ug_ed
                                        net_kar = (ug_satis - pacal_ku) - toplam_destek
                                        net_marj = (net_kar / ug_satis * 100) if ug_satis > 0 else 0
                                        toplam_net = net_kar * ug_satilan
                                        renk = "#A5D6A7" if net_kar >= 0 else "#FFCDD2"
                                        st.markdown(
                                            f'<div class="info-box" style="font-size:12px; margin:4px 0;">'
                                            f'⭐ Paçal: <b>${pacal_ku:.2f}</b> &nbsp;|&nbsp; '
                                            f'Net Kar/Adet: <span style="color:{renk}; font-weight:700;">${net_kar:.2f} (%{net_marj:.1f})</span> &nbsp;|&nbsp; '
                                            f'Toplam Net: <span style="color:{renk}; font-weight:700;">${toplam_net:.0f}</span>'
                                            f'</div>',
                                            unsafe_allow_html=True
                                        )
    
                                    ub1, ub2 = st.columns([3, 1])
                                    with ub2:
                                        if st.form_submit_button("💾 Güncelle", use_container_width=True, type="primary"):
                                            guncelle_kampanya_urun(ku_id, ug_satis, ug_fd, ug_ed, ug_satilan, ku.get("notlar",""))
                                            st.cache_data.clear()
                                            st.toast(f"✅ Güncellendi!")
                                            st.rerun()
    
                    # Ürün ekleme formu
                    with st.expander(f"➕ Ürün Ekle — {kamp['kampanya_adi']}"):
                        if not sku_listesi_k:
                            st.warning("Önce 'Veri Yükleme' sekmesinden ürün yükleyin.")
                        else:
                            with st.form(f"urun_ekle_{kid}", clear_on_submit=True):
                                uf1, uf2 = st.columns(2)
                                with uf1:
                                    u_secim = st.selectbox("Ürün *", list(sku_listesi_k.keys()), key=f"u_sec_{kid}")
                                    u_sku = sku_listesi_k.get(u_secim, "")
                                    u_bilgi = urun_dict_k.get(u_sku, {})
                                    pacal = u_bilgi.get("final_cost_price", 0)
    
                                    # Top-down margin hesaplama yardımcısı
                                    if pacal > 0:
                                        hedef_marj_giris = st.number_input(
                                            "Hedef Net Marj % (opsiyonel)",
                                            min_value=0.0, max_value=99.0, value=0.0, step=0.5, format="%.1f",
                                            help="Top-down hesap: Satış = Paçal / (1 - marj%). Örn: %20 → $100 paçal → $125 satış",
                                            key=f"u_marj_{kid}"
                                        )
                                        if hedef_marj_giris > 0:
                                            onerilen_satis = pacal / (1 - hedef_marj_giris / 100)
                                            st.markdown(f"""<div class="info-box" style="font-size:12px">
                                            💡 %{hedef_marj_giris:.1f} marj için önerilen satış: <b>${onerilen_satis:.2f}</b>
                                            </div>""", unsafe_allow_html=True)
    
                                    u_satis = st.number_input("Satış Fiyatı ($) *", min_value=0.0, value=0.0, step=0.01, format="%.2f", key=f"u_satis_{kid}")
                                    u_not = st.text_area("Notlar", key=f"u_not_{kid}")
                                with uf2:
                                    u_firma_destek = st.number_input("Birim Firma Desteği ($)", min_value=0.0, value=0.0, step=0.01, format="%.2f",
                                        help="Firma tarafından ürün başına verilen destek tutarı", key=f"u_fd_{kid}")
                                    u_ek_destek = st.number_input("Birim Ek Destek ($)", min_value=0.0, value=0.0, step=0.01, format="%.2f",
                                        help="Ek destek tutarı (ürün başına)", key=f"u_ed_{kid}")
    
                                    # Seçilen ürünün paçal maliyetini göster
                                    if pacal > 0:
                                        toplam_destek = u_firma_destek + u_ek_destek
                                        net_kar_birim = (u_satis - pacal) - toplam_destek if u_satis > 0 else 0
                                        net_marj = (net_kar_birim / u_satis * 100) if u_satis > 0 else 0  # Top-down: kar/satış
                                        st.markdown(f"""
                                        <div class="info-box" style="font-size:12px">
                                        ⭐ Paçal: <b>${pacal:.2f}</b><br>
                                        💸 Toplam Destek: <b>${toplam_destek:.2f}</b><br>
                                        📈 Net Kar/Adet: <b>${net_kar_birim:.2f} (%{net_marj:.1f})</b>
                                        </div>
                                        """, unsafe_allow_html=True)
                                    else:
                                        st.info(f"⭐ Paçal: Henüz satın alma kaydı yok")
    
                                if st.form_submit_button("➕ Ürünü Kampanyaya Ekle", type="primary", use_container_width=True):
                                    if not u_secim or u_satis <= 0:
                                        st.error("Ürün ve satış fiyatı zorunludur.")
                                    else:
                                        ekle_kampanya_urun(
                                            kid, u_sku, u_bilgi.get("urun_adi", u_sku),
                                            pacal,
                                            u_satis, u_firma_destek, u_ek_destek, u_not
                                        )
                                        st.toast("✅ Ürün eklendi!")
                                        st.rerun()
    
                    # Kampanya ürünleri tablosu
                    if k_urunler:
                        st.markdown(f"**Kampanya Ürünleri ({len(k_urunler)} ürün)**")
    
                        # Özet hesaplar
                        toplam_net_kar = 0
                        toplam_destek_verilen = 0
                        toplam_satilan = 0
    
                        rows_ku = []
                        for ku in k_urunler:
                            pacal = ku.get("pacal_maliyet") or 0
    
                            # Paçal 0 ise güncel değeri çek ve güncelle
                            if pacal == 0:
                                u_bilgi_c = urun_dict_k.get(ku["sku"], {})
                                pacal_guncel = u_bilgi_c.get("final_cost_price", 0)
                                if pacal_guncel > 0:
                                    from .database import get_connection as _gc_k
                                    _conn_k = _gc_k(); _c_k = _conn_k.cursor()
                                    _c_k.execute("UPDATE kampanya_urunler SET pacal_maliyet=? WHERE id=?",
                                                (pacal_guncel, ku["id"]))
                                    _conn_k.commit(); _conn_k.close()
                                    pacal = pacal_guncel
    
                            satis = ku.get("satis_fiyati") or 0
                            fd = ku.get("birim_firma_destek") or 0
                            ed = ku.get("birim_ek_destek") or 0
                            satilan = ku.get("satilan_adet") or 0
                            toplam_destek_birim = fd + ed
                            # Top-down margin: kar/satış (gross margin)
                            net_kar_birim = (satis - pacal) - toplam_destek_birim if satis > 0 and pacal > 0 else 0
                            net_marj = (net_kar_birim / satis * 100) if satis > 0 else 0  # Top-down gross margin
                            toplam_destek_urun = toplam_destek_birim * satilan
                            toplam_net_urun = net_kar_birim * satilan
    
                            toplam_net_kar += toplam_net_urun
                            toplam_destek_verilen += toplam_destek_urun
                            toplam_satilan += satilan
    
                            rows_ku.append({
                                "ID": ku["id"],
                                "SKU": ku["sku"],
                                "Ürün": ku.get("urun_adi",""),
                                "⭐ Paçal ($)": f"${pacal:.2f}" if pacal else "—",
                                "Satış ($)": f"${satis:.2f}",
                                "Firma Destek ($)": f"${fd:.2f}",
                                "Ek Destek ($)": f"${ed:.2f}",
                                "Net Kar/Adet ($)": f"${net_kar_birim:.2f}",
                                "Net Marj (%)": f"%{net_marj:.1f}",
                                "Satılan Adet": satilan,
                                "Toplam Destek ($)": f"${toplam_destek_urun:.0f}",
                                "Toplam Net Kar ($)": f"${toplam_net_urun:.0f}",
                                "Notlar": ku.get("notlar","") or "",
                            })
    
                        def _pf(x):
                            try:
                                return float(str(x).replace("$", "").replace("%", "").replace(",", "").strip())
                            except Exception:
                                return 0.0
                        k_rows = ""
                        for rk in rows_ku:
                            urun = str(rk.get("Ürün", "") or "")
                            urun_k = urun if len(urun) <= 40 else urun[:39] + "…"
                            urun_t = urun.replace(chr(34), "&quot;")
                            nkb = _pf(rk.get("Net Kar/Adet ($)"))
                            nkb_cls = "kc-pos" if nkb > 0 else ("kc-neg" if nkb < 0 else "kc-num")
                            tnk = _pf(rk.get("Toplam Net Kar ($)"))
                            tnk_cls = "kc-pos" if tnk > 0 else ("kc-neg" if tnk < 0 else "kc-num")
                            notlar = str(rk.get("Notlar", "") or "")
                            notlar_k = notlar if len(notlar) <= 24 else notlar[:23] + "…"
                            notlar_t = notlar.replace(chr(34), "&quot;")
                            k_rows += (
                                "<tr>"
                                f'<td class="kc-sku">{rk.get("SKU","")}</td>'
                                f'<td class="kc-name" title="{urun_t}">{urun_k}</td>'
                                f'<td class="kc-gold">{rk.get("⭐ Paçal ($)","")}</td>'
                                f'<td class="kc-money">{rk.get("Satış ($)","")}</td>'
                                f'<td class="kc-dim">{rk.get("Firma Destek ($)","")}</td>'
                                f'<td class="kc-dim">{rk.get("Ek Destek ($)","")}</td>'
                                f'<td class="{nkb_cls}">{rk.get("Net Kar/Adet ($)","")}</td>'
                                f'<td class="kc-dim">{rk.get("Net Marj (%)","")}</td>'
                                f'<td class="kc-num">{rk.get("Satılan Adet","")}</td>'
                                f'<td class="kc-dim">{rk.get("Toplam Destek ($)","")}</td>'
                                f'<td class="{tnk_cls}">{rk.get("Toplam Net Kar ($)","")}</td>'
                                f'<td class="kc-note" title="{notlar_t}">{notlar_k}</td>'
                                "</tr>"
                            )
                        k_css = (
                            "<style>"
                            ".kw{overflow-x:auto;border-radius:12px;box-shadow:0 2px 14px rgba(0,0,0,0.25);margin:4px 0}"
                            ".kt{width:100%;border-collapse:collapse;font-family:Inter,sans-serif}"
                            ".kt thead tr{background:linear-gradient(135deg,#1E293B,#0F172A)}"
                            ".kt thead th{padding:9px 11px;color:#CBD5E1;font-size:10px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;white-space:nowrap;text-align:right}"
                            ".kt thead th:nth-child(1),.kt thead th:nth-child(2),.kt thead th:last-child{text-align:left}"
                            ".kt tbody{background:#131C35}"
                            ".kt td{padding:8px 11px;font-size:11.5px}"
                            ".kt tbody tr{border-bottom:1px solid rgba(255,255,255,0.05)}"
                            ".kt tbody tr:hover{background:rgba(99,102,241,0.06)}"
                            ".kc-sku{color:#E2E8F0;font-family:'JetBrains Mono',monospace;font-weight:600;white-space:nowrap}"
                            ".kc-name{color:#CBD5E1;max-width:220px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
                            ".kc-note{color:#78909C;max-width:160px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:11px}"
                            ".kc-num{text-align:right;color:#CBD5E1;font-family:'JetBrains Mono',monospace}"
                            ".kc-dim{text-align:right;color:#94A3B8;font-family:'JetBrains Mono',monospace}"
                            ".kc-money{text-align:right;color:#E2E8F0;font-family:'JetBrains Mono',monospace;font-weight:600}"
                            ".kc-gold{text-align:right;color:#FFD54F;font-weight:600;font-family:'JetBrains Mono',monospace}"
                            ".kc-pos{text-align:right;color:#4ADE80;font-weight:700;font-family:'JetBrains Mono',monospace}"
                            ".kc-neg{text-align:right;color:#F87171;font-weight:700;font-family:'JetBrains Mono',monospace}"
                            "</style>"
                        )
                        k_head = (
                            '<div class="kw"><table class="kt"><thead><tr>'
                            "<th>SKU</th><th>Ürün</th><th>⭐ Paçal</th><th>Satış</th><th>Firma Destek</th>"
                            "<th>Ek Destek</th><th>Net Kar/Adet</th><th>Net Marj</th><th>Satılan</th>"
                            "<th>Toplam Destek</th><th>Toplam Net Kar</th><th>Notlar</th>"
                            "</tr></thead><tbody>"
                        )
                        st.html(k_css + k_head + k_rows + "</tbody></table></div>")
    
                        # Kampanya özet metrikleri
                        sm1, sm2, sm3, sm4 = st.columns(4)
                        sm1.metric("📦 Toplam Satılan", f"{toplam_satilan:,} adet")
                        sm2.metric("💸 Toplam Destek Verilen", f"${toplam_destek_verilen:,.0f}")
                        sm3.metric("📈 Toplam Net Kar", f"${toplam_net_kar:,.0f}",
                                   delta="Kârlı" if toplam_net_kar > 0 else "Zararlı",
                                   delta_color="normal" if toplam_net_kar > 0 else "inverse")
                        sm4.metric("🏪 Firma", kamp["firma"])
    
                        # Ürün düzenleme
                        with st.expander("✏️ Ürün Bilgilerini Güncelle"):
                            st.caption("Satılan adet, fiyat veya destek tutarlarını güncelleyebilirsiniz.")
                            guncelle_id = st.selectbox(
                                "Güncellenecek Ürün",
                                [f"ID:{r['ID']} — {r['Ürün']}" for r in rows_ku],
                                key=f"gun_sec_{kid}"
                            )
                            g_id = int(guncelle_id.split(":")[1].split(" ")[0])
                            g_urun = next(ku for ku in k_urunler if ku["id"] == g_id)
    
                            with st.form(f"gun_form_{kid}_{g_id}"):
                                gf1, gf2 = st.columns(2)
                                with gf1:
                                    g_satis = st.number_input("Satış Fiyatı ($)", value=float(g_urun.get("satis_fiyati",0) or 0), step=0.01, format="%.2f", key=f"g_s_{kid}_{g_id}")
                                    g_fd = st.number_input("Birim Firma Desteği ($)", value=float(g_urun.get("birim_firma_destek",0) or 0), step=0.01, format="%.2f", key=f"g_fd_{kid}_{g_id}")
                                with gf2:
                                    g_ed = st.number_input("Birim Ek Destek ($)", value=float(g_urun.get("birim_ek_destek",0) or 0), step=0.01, format="%.2f", key=f"g_ed_{kid}_{g_id}")
                                    g_satilan = st.number_input("Satılan Adet", value=int(g_urun.get("satilan_adet",0) or 0), min_value=0, step=1, key=f"g_sa_{kid}_{g_id}")
                                g_not = st.text_area("Notlar", value=g_urun.get("notlar","") or "", key=f"g_not_{kid}_{g_id}")
    
                                gf_c1, gf_c2 = st.columns(2)
                                with gf_c1:
                                    if st.form_submit_button("💾 Güncelle", type="primary", use_container_width=True):
                                        guncelle_kampanya_urun(g_id, g_satis, g_fd, g_ed, g_satilan, g_not)
                                        st.cache_data.clear()
                                        st.toast("Güncellendi!")
                                        st.rerun()
                                with gf_c2:
                                    if st.form_submit_button("🗑️ Ürünü Sil", use_container_width=True):
                                        sil_kampanya_urun(g_id)
                                        st.cache_data.clear()
                                        st.warning("Ürün kaldırıldı.")
                                        st.rerun()
                    else:
                        st.info("Bu kampanyaya henüz ürün eklenmemiş.")
    
                    st.markdown("---")
    
        # ─────────────────────────────────────────────────────────────────
        # TAB 2: GEÇMİŞ KAMPANYALAR
        # ─────────────────────────────────────────────────────────────────
        with ktab2:
            gecmis = get_kampanyalar(durum="kapali")
            if not gecmis:
                st.info("Henüz kapatılmış kampanya yok.")
            else:
                for kamp in gecmis:
                    kid = kamp["id"]
                    k_urunler = get_kampanya_urunler(kid)
    
                    # Özet hesaplar
                    toplam_net = sum(
                        ((ku.get("satis_fiyati",0) or 0) - (ku.get("pacal_maliyet",0) or 0)
                         - (ku.get("birim_firma_destek",0) or 0) - (ku.get("birim_ek_destek",0) or 0))
                        * (ku.get("satilan_adet",0) or 0)
                        for ku in k_urunler
                    )
                    toplam_destek = sum(
                        ((ku.get("birim_firma_destek",0) or 0) + (ku.get("birim_ek_destek",0) or 0))
                        * (ku.get("satilan_adet",0) or 0)
                        for ku in k_urunler
                    )
                    toplam_satilan = sum(ku.get("satilan_adet",0) or 0 for ku in k_urunler)
    
                    net_renk = "#A5D6A7" if toplam_net >= 0 else "#FFCDD2"
                    net_bg = "#1B5E20" if toplam_net >= 0 else "#7F0000"
    
                    st.markdown(f"""
                    <div style="background:rgba(255,255,255,0.04); border-radius:12px; padding:16px 20px;
                                margin:10px 0; border-left:5px solid #546E7A;">
                      <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:10px;">
                        <div>
                          <span style="color:#CFD8DC; font-size:16px; font-weight:700;">📁 {kamp["kampanya_adi"]}</span>
                          <span style="background:#263238; color:#90A4AE; padding:2px 8px; border-radius:8px; font-size:11px; margin-left:8px;">{kamp["firma"]}</span>
                          <span style="background:#37474F; color:#CFD8DC; padding:2px 8px; border-radius:8px; font-size:11px; margin-left:4px;">● KAPALI</span>
                          <div style="color:#78909C; font-size:12px; margin-top:4px;">{kamp["baslangic_tarihi"]} → {kamp["bitis_tarihi"]}</div>
                        </div>
                        <div style="display:flex; gap:12px; flex-wrap:wrap;">
                          <div style="text-align:center; background:#1a2a3a; padding:8px 14px; border-radius:8px;">
                            <div style="color:#90A4AE; font-size:10px;">SATILAN</div>
                            <div style="color:#FFFFFF; font-size:16px; font-weight:700;">{toplam_satilan:,} adet</div>
                          </div>
                          <div style="text-align:center; background:#1a2a3a; padding:8px 14px; border-radius:8px;">
                            <div style="color:#90A4AE; font-size:10px;">TOPLAM DESTEK</div>
                            <div style="color:#FFA726; font-size:16px; font-weight:700;">${toplam_destek:,.0f}</div>
                          </div>
                          <div style="text-align:center; background:{net_bg}; padding:8px 14px; border-radius:8px;">
                            <div style="color:{net_renk}; font-size:10px; opacity:0.8;">NET KAR</div>
                            <div style="color:{net_renk}; font-size:16px; font-weight:800;">${toplam_net:,.0f}</div>
                          </div>
                        </div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
    
                    if k_urunler:
                        with st.expander(f"📋 Detaylar — {kamp['kampanya_adi']}"):
                            rows_g = []
                            for ku in k_urunler:
                                pacal = ku.get("pacal_maliyet") or 0
                                # Paçal 0 ise güncel değeri çek
                                if pacal == 0:
                                    pacal = urun_dict_k.get(ku["sku"], {}).get("final_cost_price", 0)
                                satis = ku.get("satis_fiyati") or 0
                                fd = ku.get("birim_firma_destek") or 0
                                ed = ku.get("birim_ek_destek") or 0
                                satilan = ku.get("satilan_adet") or 0
                                toplam_d = (fd + ed) * satilan
                                # Top-down margin: kar/satış
                                net_b = (satis - pacal) - (fd + ed) if satis > 0 else 0
                                net_t = net_b * satilan
                                rows_g.append({
                                    "SKU": ku["sku"],
                                    "Ürün": ku.get("urun_adi",""),
                                    "⭐ Paçal ($)": f"${pacal:.2f}" if pacal else "—",
                                    "Satış ($)": f"${satis:.2f}",
                                    "Firma D. ($)": f"${fd:.2f}",
                                    "Ek D. ($)": f"${ed:.2f}",
                                    "Net Kar/Adet ($)": f"${net_b:.2f}",
                                    "Satılan": satilan,
                                    "Top. Destek ($)": f"${toplam_d:.0f}",
                                    "Top. Net Kar ($)": f"${net_t:.0f}",
                                })
                            st.dataframe(pd.DataFrame(rows_g), use_container_width=True, hide_index=True)
    
                            if st.button(f"🗑️ Kampanyayı Sil", key=f"sil_gecmis_{kid}"):
                                sil_kampanya(kid)
                                st.cache_data.clear()
                                st.warning("Silindi.")
                                st.rerun()
    
    
    elif sayfa == "📦  Sipariş Önerisi":
        st.markdown('<div class="baslik">📦 Sipariş Önerisi</div>', unsafe_allow_html=True)
        st.markdown('<div class="alt-baslik">135 günden az stok kalan ürünler · Otomatik öneri</div>', unsafe_allow_html=True)
        st.markdown('<div class="sayfa-baslik-cizgi"></div>', unsafe_allow_html=True)
    
        try:
            siparis_listesi = siparis_onerisi_listesi()
            urun_data = tum_urunler_listesi()
            urun_dict = {u["sku"]: u for u in urun_data}
        except Exception as e:
            _log.error("Hata: %s", e)
            st.error(f"Veri yüklenemedi: {e}")
            st.stop()
    
        if not siparis_listesi:
            st.success("✅ Tüm ürünlerde 135 günden fazla stok var, sipariş gerekmüyor!")
            st.stop()
    
        # Özet
        acil = [u for u in siparis_listesi if u.get("siparis_durum") == "acil"]
        yaklasan = [u for u in siparis_listesi if u.get("siparis_durum") == "yaklasıyor"]
        planlama = [u for u in siparis_listesi if u.get("siparis_durum") == "planlama"]
    
        m1, m2, m3 = st.columns(3)
        m1.metric("🔴 ACİL", len(acil))
        m2.metric("🟠 Yaklaşıyor (30 gün)", len(yaklasan))
        m3.metric("🟡 Planlama (60 gün)", len(planlama))
    
        st.markdown("---")
    
        for urun in siparis_listesi:
            durum = urun.get("siparis_durum","")
            mesaj = urun.get("siparis_mesaj","")
            oneri = urun.get("oneri_miktar",0)
            oneri_mesaj = urun.get("oneri_mesaj","")
            sku = urun["sku"]
            ud = urun_dict.get(sku, {})
            fcp = ud.get("final_cost_price", 0)
            satis = ud.get("satis_fiyati", 0)
    
            # Stoku olan firmaları (kompakt)
            firma_detay = urun.get("firma_detay", [])
            firma_kisa = " · ".join(f'{fd["firma"]}:{fd["stok"]}' for fd in firma_detay if fd.get("stok", 0) > 0)

            if durum == "acil":
                brd, ik, dt = "rgba(239,68,68,0.6)", "🔴", "rgba(239,68,68,0.07)"
            elif durum == "yaklasıyor":
                brd, ik, dt = "rgba(245,158,11,0.6)", "🟠", "rgba(245,158,11,0.06)"
            else:
                brd, ik, dt = "rgba(234,179,8,0.55)", "🟡", "rgba(234,179,8,0.06)"

            alt = [f'📅 {mesaj}', f'G5F: {urun["bizim_stok"]}', f'Hft: {urun.get("ortalama_haftalik_satis",0):.1f}']
            if firma_kisa:
                alt.append(firma_kisa)
            if fcp > 0:
                alt.append(f'💵 ${fcp:,.0f}→${satis:,.0f}')
            alt_str = "  ·  ".join(alt)

            c1, c2, c3 = st.columns([6, 1.2, 1.7])
            with c1:
                st.markdown(
                    f'<div style="background:{dt};border-left:3px solid {brd};border-radius:8px;padding:8px 13px;">'
                    f'<div style="font-size:13px;font-weight:600;color:#E2E8F0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                    f'{ik} {urun["urun_adi"]} <span style="color:#94A3B8;font-size:11px;font-family:monospace;">{sku}</span></div>'
                    f'<div style="font-size:11px;color:#94A3B8;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                    f'{alt_str}  ·  <span style="color:#FBBF24;font-weight:600;">💡 {oneri} adet</span></div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            with c2:
                miktar = st.number_input("Miktar", min_value=1, value=max(oneri, 1),
                                         key=f"sp_miktar_{sku}", label_visibility="collapsed")
            with c3:
                if st.button("📦 Sipariş Ekle", key=f"sp_btn_{sku}", use_container_width=True):
                    from .database import ekle_siparis_onerisi
                    ekle_siparis_onerisi("G5F", sku, urun["urun_adi"], miktar)
                    st.cache_data.clear()
                    st.toast(f"✅ {urun['urun_adi']} için {miktar} adet sipariş önerisi oluşturuldu!")
                    st.rerun()
    
        # Onaylanan/Bekleyen geçmiş
        st.markdown("---")
        st.markdown("#### 📋 Sipariş Önerisi Geçmişi")
        from .database import get_siparis_onerileri
        onceki = get_siparis_onerileri()
        if onceki:
            rows_sp = []
            for sp in onceki:
                rows_sp.append({
                    "ID": sp["id"],
                    "SKU": sp["sku"],
                    "Ürün": sp.get("urun_adi",""),
                    "Miktar": sp["oneri_miktari"],
                    "Durum": sp["durum"],
                    "Tarih": sp["olusturma_tarihi"],
                    "Onay": sp.get("onay_tarihi","") or "",
                })
            df_sp = pd.DataFrame(rows_sp)
    
            def sp_rengi(row):
                d = row.get("Durum","")
                if d == "onaylandi":   return ["background-color:#1B5E20; color:#A5D6A7"]*len(row)
                if d == "reddedildi":  return ["background-color:#7F0000; color:#FFCDD2"]*len(row)
                return ["background-color:#827717; color:#FFF176"]*len(row)
    
            render_renkli_tablo(
                df_sp,
                kisalt={"Ürün": 42},
                satir_durum=("Durum", {"onaylandi": "rk-grn", "reddedildi": "rk-red", "bekliyor": "rk-yel"}),
                gizle=["ID"],
            )
    
            col_o1, col_o2 = st.columns(2)
            with col_o1:
                onayla_id = st.number_input("Onaylanacak ID", min_value=1, step=1, key="onayla_id")
                if st.button("✅ Onayla", key="onayla_btn", use_container_width=True):
                    from .database import onayla_siparis
                    onayla_siparis(int(onayla_id))
                    st.toast("Onaylandı!")
                    st.rerun()
            with col_o2:
                reddet_id = st.number_input("Reddedilecek ID", min_value=1, step=1, key="reddet_id")
                if st.button("❌ Reddet", key="reddet_btn", use_container_width=True):
                    from .database import reddet_siparis
                    reddet_siparis(int(reddet_id))
                    st.warning("Reddedildi.")
                    st.rerun()
    
    
    elif sayfa == "📂  Veri Yükleme":
        st.markdown('<div class="baslik">📂 Veri Yükleme</div>', unsafe_allow_html=True)
        st.markdown('<div class="alt-baslik">Excel yükle · Geçmiş yüklemeleri gör · Veriyi yönet</div>', unsafe_allow_html=True)
        st.markdown('<div class="sayfa-baslik-cizgi"></div>', unsafe_allow_html=True)
    
        # Şablon indir
        with st.expander("📋 Excel Şablonunu İndir (ilk kez kullanıyorsanız buradan başlayın)", expanded=False):
            st.markdown('<div style="color:#94A3B8;font-size:12px;line-height:1.6;margin-bottom:6px">Aşağıdaki butona tıklayıp örnek şablonu indir, doldur ve yükle.</div>', unsafe_allow_html=True)
            sablon_bytes = create_sample_excel_bytes()
            st.download_button("📥 Şablonu İndir", sablon_bytes, "SABLON_STOK_TAKIP.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
        st.markdown("---")
    
        st.markdown('<div style="font-size:13px;font-weight:700;color:#A5B4FC;letter-spacing:1px;text-transform:uppercase;margin:8px 0 8px;display:flex;align-items:center;gap:9px"><span style="width:5px;height:16px;border-radius:3px;background:linear-gradient(180deg,#6366F1,#A78BFA);display:inline-block"></span>📤 G5F Stok · Haftalık Veri Yükleme</div>', unsafe_allow_html=True)
        st.markdown('<div style="color:#94A3B8;font-size:12px;line-height:1.6;margin-bottom:12px">Tek Excel dosyasında tüm sekmeler: <b style="color:#CBD5E1">G5F STOK</b> (bizim depo) · <b style="color:#CBD5E1">ITOPYA, HB, VATAN, MONDAY, KANAL, DIGER</b> (firma stokları) · <b style="color:#CBD5E1">YOLDAKI</b> (yoldaki ürünler)</div>', unsafe_allow_html=True)
    
        dosya = st.file_uploader("Excel Dosyasını Seç", type=["xlsx","xls"], key="tek_dosya")
        if dosya:
            if st.button("⬆️ Tüm Veriyi Yükle", type="primary", use_container_width=True):
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                    tmp.write(dosya.read())
                    tmp_path = tmp.name
    
                sonuclar = []
    
                # G5F STOK (ana stok + yoldaki)
                basari, mesaj = excel_yukle_ana_stok(tmp_path)
                sonuclar.append(("G5F STOK", basari, mesaj))
    
                # Firma stokları
                basari2, mesaj2 = excel_yukle_firma_stoklari(tmp_path)
                sonuclar.append(("Firma Stokları", basari2, mesaj2))
    
                os.unlink(tmp_path)
    
                # Cache temizle — yeni veri yüklendiğinde eski cache geçersiz
                st.cache_data.clear()
    
                for baslik, basari, mesaj in sonuclar:
                    if basari:
                        st.success(f"**{baslik}:** {mesaj}")
                    else:
                        st.warning(f"**{baslik}:** {mesaj}")
    
        st.markdown("---")
        st.markdown('<div style="font-size:12px;font-weight:700;color:#94A3B8;letter-spacing:1px;text-transform:uppercase;margin:6px 0 10px">📋 Excel Sekme Yapısı</div>', unsafe_allow_html=True)
        st.markdown("""<div style="display:flex;flex-direction:column;gap:10px;margin-bottom:4px">
 <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:14px 16px">
 <div style="color:#90CAF9;font-size:12px;font-weight:700;letter-spacing:.4px;margin-bottom:6px">G5F STOK <span style="color:#64748B;font-weight:500">· bizim depo + yoldaki</span></div>
 <div style="color:#94A3B8;font-size:11.5px;line-height:1.7">SKU · Ürün Adı · Kategori · Marka · Satış Fiyatı ($) · Alış Fiyatı ($) · Hedef Kar Marjı (%) · Bizim Stok · Yoldaki Miktar · Tahmini Varış Tarihi · Yoldaki Tedarikçi</div>
 </div>
 <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:14px 16px">
 <div style="color:#F9A8D4;font-size:12px;font-weight:700;letter-spacing:.4px;margin-bottom:6px">ITOPYA / HB / VATAN / MONDAY / KANAL / DIGER <span style="color:#64748B;font-weight:500">· firma stokları</span></div>
 <div style="color:#94A3B8;font-size:11.5px;line-height:1.7">SKU · Ürün Adı · Stok Miktarı · Haftalık Satış</div>
 </div>
 </div>""", unsafe_allow_html=True)
    
        st.markdown("---")
        st.markdown('<div style="font-size:13px;font-weight:700;color:#A5B4FC;letter-spacing:1px;text-transform:uppercase;margin:8px 0 8px;display:flex;align-items:center;gap:9px"><span style="width:5px;height:16px;border-radius:3px;background:linear-gradient(180deg,#6366F1,#A78BFA);display:inline-block"></span>📅 Geçmiş Yüklemeler</div>', unsafe_allow_html=True)
        st.markdown('<div style="color:#94A3B8;font-size:12px;line-height:1.6;margin-bottom:8px">Hangi tarihlerde veri yüklendiğini gör, gerekirse sil.</div>', unsafe_allow_html=True)
    
        try:
            sb_vy = get_client()
    
            # Firma stok yükleme tarihleri
            firma_tarihler = sb_vy.table("firma_stok").select("yukleme_tarihi, firma").execute().data or []
            tarih_firma = {}
            for r in firma_tarihler:
                t = r["yukleme_tarihi"]
                if t not in tarih_firma:
                    tarih_firma[t] = set()
                tarih_firma[t].add(r["firma"])
    
            # Ürün yükleme tarihleri
            urun_tarihler = sb_vy.table("urunler").select("guncelleme_tarihi").execute().data or []
            urun_tarih_set = set(r["guncelleme_tarihi"] for r in urun_tarihler if r.get("guncelleme_tarihi"))
    
            if not tarih_firma and not urun_tarih_set:
                st.info("Henüz veri yüklenmemiş.")
            else:
                tum_tarihler = sorted(set(list(tarih_firma.keys()) + list(urun_tarih_set)), reverse=True)
    
                rows_vy = []
                for t in tum_tarihler:
                    firmalar = ", ".join(sorted(tarih_firma.get(t, [])))
                    urun_sayisi = len([r for r in urun_tarihler if r.get("guncelleme_tarihi") == t])
                    firma_kayit = sum(1 for r in firma_tarihler if r["yukleme_tarihi"] == t)
                    rows_vy.append({
                        "Tarih": t,
                        "Yüklenen Ürün": urun_sayisi,
                        "Firma Kayıt Sayısı": firma_kayit,
                        "Firmalar": firmalar or "—",
                    })
    
                df_vy = pd.DataFrame(rows_vy)
                render_renkli_tablo(df_vy, sol=["Firmalar"], kisalt={"Firmalar": 60})
    
                # Tarih seçip sil
                with st.expander("🗑️ Belirli Bir Tarihin Firma Stok Verisini Sil"):
                    st.caption("⚠️ Seçilen tarihe ait firma stok verileri silinir. Ürün listesi ve satın alma geçmişi etkilenmez.")
                    sil_tarih = st.selectbox("Silinecek Tarih", sorted(tarih_firma.keys(), reverse=True), key="vy_sil_tarih")
                    if st.button("🗑️ Bu Tarihin Verisini Sil", type="secondary", key="vy_sil_btn"):
                        sb_vy.table("firma_stok").delete().eq("yukleme_tarihi", sil_tarih).execute()
                        st.toast(f"✅ {sil_tarih} tarihli firma stok verisi silindi.")
                        st.rerun()
    
        except Exception as e:
            _log.warning("Hata: %s", e)
            st.warning(f"Geçmiş yüklemeler yüklenemedi: {e}")
    
    
    
    
    # ════════════════════════════════════════════════════════════════════
    # 8) RAPORLAR
    # ════════════════════════════════════════════════════════════════════
    elif sayfa == "📄  Raporlar":
        st.markdown('<div class="baslik">📄 Raporlar</div>', unsafe_allow_html=True)
        st.markdown('<div class="alt-baslik">Excel & PDF rapor oluştur · İndir</div>', unsafe_allow_html=True)
        st.markdown('<div class="sayfa-baslik-cizgi"></div>', unsafe_allow_html=True)
    
        col1, col2 = st.columns(2)
    
        with col1:
            st.subheader("📊 Excel Raporu")
            st.write("Dashboard, Stok Yayılımı ve Sipariş Önerileri — 3 sekme, renkli, tam detaylı.")
            if st.button("📊 Excel Raporu Oluştur", use_container_width=True, type="primary"):
                from rapor import excel_rapor_olustur
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                    tmp_path = tmp.name
                basari, mesaj = excel_rapor_olustur(tmp_path)
                if basari:
                    with open(tmp_path, "rb") as f:
                        st.download_button(
                            "⬇️ Excel İndir",
                            f.read(),
                            f"Stok_Raporu_{tr_now().strftime('%Y%m%d_%H%M')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )
                    os.unlink(tmp_path)
                else:
                    st.error(mesaj)
    
        with col2:
            st.subheader("📑 PDF Raporu")
            st.write("A4 yatay formatta yazdırmaya hazır özet rapor.")
            if st.button("📑 PDF Raporu Oluştur", use_container_width=True):
                from rapor import pdf_rapor_olustur
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp_path = tmp.name
                basari, mesaj = pdf_rapor_olustur(tmp_path)
                if basari:
                    with open(tmp_path, "rb") as f:
                        st.download_button(
                            "⬇️ PDF İndir",
                            f.read(),
                            f"Stok_Raporu_{tr_now().strftime('%Y%m%d_%H%M')}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
                    os.unlink(tmp_path)
                else:
                    st.error(mesaj)
    
    # ════════════════════════════════════════════════════════════════════
    # 9) BİLDİRİM AYARLARI
    # ════════════════════════════════════════════════════════════════════
    elif sayfa == "🔔  Bildirim Ayarları":
        st.markdown('<div class="baslik">🔔 Bildirim Ayarları</div>', unsafe_allow_html=True)
        st.markdown('<div class="alt-baslik">Günlük e-posta bildirimi için SMTP ayarlarını yapın</div>', unsafe_allow_html=True)
    
        mevcut = get_bildirim_ayarlari()
    
        with st.expander("📧 E-posta Ayarları", expanded=True):
            st.caption("Gmail kullanıyorsanız: smtp_host=smtp.gmail.com, port=587, uygulama şifresi gereklidir.")
    
            col1, col2 = st.columns(2)
            with col1:
                email = st.text_input("Bildirim Gönderilecek E-posta", value=mevcut.get("email","") if mevcut else "")
                smtp_host = st.text_input("SMTP Host", value=mevcut.get("smtp_host","smtp.gmail.com") if mevcut else "smtp.gmail.com")
                smtp_port = st.number_input("SMTP Port", value=int(mevcut.get("smtp_port",587)) if mevcut else 587)
            with col2:
                smtp_user = st.text_input("SMTP Kullanıcı (Gönderen E-posta)", value=mevcut.get("smtp_user","") if mevcut else "")
                smtp_pass = st.text_input("SMTP Şifre / Uygulama Şifresi", type="password", value=mevcut.get("smtp_pass","") if mevcut else "")
                aktif = st.checkbox("Günlük bildirimleri aktif et", value=bool(mevcut.get("aktif",0)) if mevcut else False)
    
            if mevcut and mevcut.get("son_gonderim"):
                st.info(f"Son gönderim: {mevcut['son_gonderim']}")
    
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("💾 Ayarları Kaydet", type="primary", use_container_width=True):
                    if email and smtp_user and smtp_pass:
                        kaydet_bildirim_ayarlari(email, smtp_host, smtp_port, smtp_user, smtp_pass, int(aktif))
                        st.success("Ayarlar kaydedildi!")
                    else:
                        st.error("E-posta, kullanıcı adı ve şifre zorunludur.")
            with col_b:
                if st.button("📧 Test E-postası Gönder", use_container_width=True):
                    veri = dashboard_hesapla()
                    ok, msg = email_gonder(veri)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
    
        st.markdown("---")
        st.subheader("📋 Sipariş Takvimi Özeti")
        st.caption("Tüm ürünlerin sipariş durumu — 135 gün üretim süresi baz alınarak hesaplanmıştır.")
    
        try:
            veri = dashboard_hesapla()
            # Ürün başına tek satır (firma tekrarı olmasın)
            sku_goruldu = set()
            ozetler = []
            for u in veri:
                if u["sku"] not in sku_goruldu:
                    sku_goruldu.add(u["sku"])
                    ozetler.append(u)
    
            durum_sirasi = {"acil": 0, "yaklasıyor": 1, "planlama": 2, "normal": 3, "veri_yok": 4}
            ozetler.sort(key=lambda x: durum_sirasi.get(x.get("siparis_durum","veri_yok"), 4))
    
            df_ozet = pd.DataFrame([{
                "SKU": u["sku"],
                "Ürün Adı": u["urun_adi"],
                "Bizim Stok": u["bizim_stok"],
                "Hft. Satış": u.get("toplam_haftalik_satis", 0),
                "Stok Biter (Gün)": u.get("stok_bitis_gun", "-") or "-",
                "Sipariş Son Gün": u.get("siparis_son_gun", "-") or "-",
                "Durum": u.get("siparis_mesaj", "—"),
            } for u in ozetler])
    
            def ozet_rengi(row):
                durum = row.get("Durum","")
                if "ACİL" in str(durum): return ["background-color:#FFCCCC"]*len(row)
                if "🟠" in str(durum): return ["background-color:#FFE0B2"]*len(row)
                if "🟡" in str(durum): return ["background-color:#FFF9C4"]*len(row)
                if "🟢" in str(durum): return ["background-color:#E8F5E9"]*len(row)
                return [""]*len(row)
    
            st.dataframe(df_ozet.style.apply(ozet_rengi, axis=1), use_container_width=True, height=400)
        except Exception as e:
            _log.error("Hata: %s", e)
            st.error(f"Veri yüklenemedi: {e}")
