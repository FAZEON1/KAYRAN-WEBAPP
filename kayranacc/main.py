"""
Muhasebe & Finans — Ödeme Takip Sistemi
Modüler olarak KAYRAN portal içinden çağrılır.

Kullanım:
    from kayranacc.main import run
    run()
"""
import streamlit as st
# Türkiye saat dilimi için ortak yardımcılar
from shared.utils import tr_today, tr_now, tr_today_iso, tr_now_str, tr_tomorrow, tr_yesterday as _tr_today_iso_dummy
from shared.utils import sidebar_stil, sidebar_baslik, sidebar_kullanici
from shared.utils import metrik_satiri, metric_css
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import os
from datetime import datetime, date, timedelta
from io import BytesIO
from .database import (
    initialize_db, get_tum_haftalar, get_aktif_hafta,
    hafta_ekle, hafta_aktif_yap, hafta_sil,
    get_hafta_odemeler, odeme_ekle_bulk, odeme_ekle_manuel,
        odeme_durum_guncelle, odeme_sil, odeme_kismi_ode, odeme_vade_guncelle, odeme_tutar_guncelle, odeme_kategori_guncelle, odeme_aciklama_guncelle, get_hafta_ozet,
    get_bankalar, banka_ekle, banka_guncelle, banka_sil,
    get_cekler, cek_ekle_bulk, cek_sil, cek_sil_hepsi,
    get_ertelenen_odemeler, get_virmanlar, virman_yap, virman_geri_al,
    tahsilat_ekle, get_tahsilatlar, tahsilat_geri_al,
    aktif_excel_kaydet, aktif_excel_oku, aktif_excel_sil, aktif_excel_meta_oku,
    aktif_manuel_ekle, aktif_manuel_listele, aktif_manuel_sil, get_cek_toplamlari,
    set_ayar, get_ayar,
)
from .excel_islemler import (
    excel_yukle_odeme_listesi, excel_yukle_cek_listesi,
    export_excel, create_sample_excel
)
from .rapor import haftalik_excel_raporu, haftalik_html_raporu, nakit_akis_excel
from .bildirim import (mask_email,
    get_bildirim_ayarlari, email_gonder, baglanti_test,
    vade_bildirimi_olustur, ozet_bildirimi_olustur,
)


def run():
    """Muhasebe & Finans ana çalıştırıcı. Portal tarafından çağrılır."""
    initialize_db()

    # ── Cache kontrol meta etiketleri ────────────────────────────────────
    APP_VERSION = tr_now().strftime("%Y%m%d%H%M")
    st.markdown(f"""
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
    <meta http-equiv="Pragma" content="no-cache" />
    <meta http-equiv="Expires" content="0" />
    <!-- app-version: {APP_VERSION} -->
    """, unsafe_allow_html=True)
    
    # ── CSS ──────────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');
    
    /* ── GLOBAL ── */
    *, *::before, *::after { box-sizing: border-box; }
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        -webkit-font-smoothing: antialiased;
        background: #0A0F1E !important;
        color: #E2E8F0 !important;
    }
    
    .main,
    [data-testid="stApp"],
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    .stApp {
        background: #080C20 !important;
        min-height: 100vh;
    }
    
    /* Scrollbar */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #1A2540; }
    ::-webkit-scrollbar-thumb { background: #2D3F6B; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #4A6FA5; }
    
    /* ── SIDEBAR ── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0F1629 0%, #1A2540 40%, #0F1629 100%) !important;
        border-right: 1px solid rgba(255,255,255,0.06) !important;
    }
    section[data-testid="stSidebar"] > div {
        padding-top: 0 !important;
    }
    section[data-testid="stSidebar"] * {
        color: #E2E8F0 !important;
        font-family: 'Inter', sans-serif !important;
    }
    /* Sidebar nav stili shared/utils.py → sidebar_stil() tarafından yönetilir */
    section[data-testid="stSidebar"] .stNumberInput input {
        background: rgba(255,255,255,0.08) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        color: #F1F5F9 !important;
        border-radius: 8px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 15px !important;
        font-weight: 600 !important;
    }
    section[data-testid="stSidebar"] .stButton button {
        background: rgba(59, 130, 246, 0.15) !important;
        border: 1px solid rgba(59, 130, 246, 0.3) !important;
        color: #93C5FD !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 12px !important;
        transition: all .2s !important;
    }
    section[data-testid="stSidebar"] .stButton button:hover {
        background: rgba(59, 130, 246, 0.25) !important;
        color: #BFDBFE !important;
    }
    section[data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.08) !important;
    }
    section[data-testid="stSidebar"] a {
        color: #60A5FA !important;
    }
    
    /* ── METRİK KARTLARI ── (eski: metric-container, yeni: stMetric) */
    [data-testid="metric-container"],
    [data-testid="stMetric"] {
        background: #131C35 !important;
        border-radius: 14px !important;
        padding: 20px 22px !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.04) !important;
        transition: transform .2s, box-shadow .2s !important;
    }
    [data-testid="metric-container"]:hover,
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08) !important;
    }
    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] * {
        font-size: 11px !important;
        font-weight: 700 !important;
        letter-spacing: .6px !important;
        text-transform: uppercase !important;
        color: #64748B !important;
    }
    [data-testid="stMetricValue"],
    [data-testid="stMetricValue"] * {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 24px !important;
        font-weight: 700 !important;
        color: #E2E8F0 !important;
        letter-spacing: -.5px !important;
    }
    
    /* ── BUTONLAR ── */
    /* Tüm butonlar: beyaz zemin, koyu yazı (eski seçici güncel sürümde
       ikon butonlarda tutmuyordu, siyah çıkıyorlardı). Sidebar kendi
       daha spesifik kuralıyla bunu eziyor, dokunulmaz. */
    .stButton > button,
    [data-testid="stButton"] button,
    [data-testid="stBaseButton-secondary"] {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        border-radius: 10px !important;
        padding: 8px 16px !important;
        transition: all .2s !important;
        letter-spacing: .1px !important;
        background: #1A2744 !important;
        border: 1.5px solid #2D4070 !important;
        color: #94A3B8 !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.2) !important;
    }
    .stButton > button:hover,
    [data-testid="stButton"] button:hover,
    [data-testid="stBaseButton-secondary"]:hover {
        border-color: #94A3B8 !important;
        background: #243358 !important;
        color: #CBD5E1 !important;
    }
    /* Primary (mavi) butonlar — her yerde geçerli */
    .stButton > button[kind="primary"],
    [data-testid="stButton"] button[kind="primary"],
    [data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, #2563EB, #1D4ED8) !important;
        border: none !important;
        box-shadow: 0 2px 8px rgba(37,99,235,0.3) !important;
        color: #FFFFFF !important;
    }
    .stButton > button[kind="primary"]:hover,
    [data-testid="stButton"] button[kind="primary"]:hover,
    [data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(135deg, #1D4ED8, #93C5FD) !important;
        box-shadow: 0 4px 16px rgba(37,99,235,0.4) !important;
        transform: translateY(-1px) !important;
        color: #FFFFFF !important;
    }
    /* Popover / Vadeyi Ötele gibi açılır buton tetikleyicileri */
    [data-testid="stPopover"] button {
        background: rgba(255,255,255,0.05) !important;
        border: 1.5px solid rgba(255,255,255,0.12) !important;
        color: #CBD5E1 !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
    }
    [data-testid="stPopover"] button:hover {
        border-color: #94A3B8 !important;
        background: #151F38 !important;
        color: #E2E8F0 !important;
    }
    
    /* ── INPUT ALANLARI (sidebar hariç) ── */
    .stTextInput input, .stNumberInput input, .stSelectbox select,
    .stDateInput input, .stTextArea textarea {
        font-family: 'Inter', sans-serif !important;
        border-radius: 10px !important;
        border: 1.5px solid #E2E8F0 !important;
        font-size: 13px !important;
        padding: 10px 14px !important;
        transition: border-color .2s, box-shadow .2s !important;
        background: #131C35 !important;
        color: #E2E8F0 !important;
    }
    /* Sidebar'daki inputs için override (yukarıdaki kural ezilsin) */
    section[data-testid="stSidebar"] .stTextInput input,
    section[data-testid="stSidebar"] .stNumberInput input,
    section[data-testid="stSidebar"] .stSelectbox select,
    section[data-testid="stSidebar"] .stDateInput input {
        background: rgba(15,22,41,0.6) !important;
        border: 1px solid rgba(148,163,184,0.25) !important;
        color: #F1F5F9 !important;
        border-radius: 8px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        box-shadow: inset 0 1px 2px rgba(0,0,0,0.2) !important;
    }
    section[data-testid="stSidebar"] .stNumberInput input:focus {
        background: rgba(15,22,41,0.8) !important;
        border-color: rgba(96,165,250,0.5) !important;
        box-shadow: 0 0 0 2px rgba(59,130,246,0.2) !important;
    }
    /* Sidebar number input +/- butonları */
    section[data-testid="stSidebar"] .stNumberInput button {
        background: rgba(15,22,41,0.5) !important;
        border-color: rgba(148,163,184,0.2) !important;
        color: #94A3B8 !important;
    }
    section[data-testid="stSidebar"] .stNumberInput button:hover {
        background: rgba(59,130,246,0.2) !important;
        color: #BFDBFE !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus,
    .stSelectbox select:focus, .stDateInput input:focus {
        border-color: #3B82F6 !important;
        box-shadow: 0 0 0 3px rgba(59,130,246,0.12) !important;
        outline: none !important;
    }
    .stTextInput label, .stNumberInput label, .stSelectbox label,
    .stDateInput label, .stTextArea label {
        font-size: 12px !important;
        font-weight: 600 !important;
        color: #94A3B8 !important;
        letter-spacing: .3px !important;
        margin-bottom: 4px !important;
    }
    
    /* ── EXPANDER ── */
    /* Eski sürüm sınıfı (geriye dönük uyumluluk için kalsın) */
    .streamlit-expanderHeader {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        color: #CBD5E1 !important;
        background: #131C35 !important;
        border-radius: 12px !important;
        border: 1.5px solid #E2E8F0 !important;
        padding: 14px 18px !important;
    }
    .streamlit-expanderContent {
        background: #0A0F1E !important;
        border: 1.5px solid #E2E8F0 !important;
        border-top: none !important;
        border-radius: 0 0 12px 12px !important;
        padding: 16px !important;
    }
    /* Yeni sürüm: [data-testid="stExpander"] + <summary> yapısı */
    [data-testid="stExpander"] details {
        border: 1.5px solid #E2E8F0 !important;
        border-radius: 12px !important;
        background: #131C35 !important;
    }
    [data-testid="stExpander"] summary {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        background: #131C35 !important;
        border-radius: 12px !important;
        padding: 12px 16px !important;
    }
    /* Başlık yazısı — açık zeminde kayboluyordu, koyu yap */
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] summary span,
    [data-testid="stExpander"] summary div,
    [data-testid="stExpander"] summary label {
        color: #CBD5E1 !important;
    }
    /* +/- aç-kapa ikonu görünür olsun */
    [data-testid="stExpander"] summary svg,
    [data-testid="stExpanderToggleIcon"] {
        color: #6366F1 !important;
        fill: currentColor !important;
        opacity: 1 !important;
    }
    /* Expander içeriği */
    [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
        background: #0A0F1E !important;
        border-radius: 0 0 12px 12px !important;
        padding: 8px !important;
    }
    
    /* ── DATAFRAME ── */
    div[data-testid="stDataFrame"] {
        border-radius: 12px !important;
        overflow: hidden !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
    }
    
    /* ── TABS ── */
    .stTabs [data-baseweb="tab-list"] {
        background: #1A2540 !important;
        border-radius: 12px !important;
        padding: 4px !important;
        gap: 2px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        color: #64748B !important;
        padding: 8px 18px !important;
        transition: all .2s !important;
    }
    .stTabs [aria-selected="true"] {
        background: #131C35 !important;
        color: #93C5FD !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08) !important;
    }
    
    /* ── BAŞLIKLAR ── */
    .baslik {
        display: flex !important; align-items: center !important; gap: 11px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 19px !important;
        font-weight: 750 !important;
        color: #F1F5F9 !important;
        letter-spacing: -0.3px !important;
        margin: 2px 0 0 !important;
        line-height: 1.25 !important;
    }
    .baslik-ikon {
        width: 30px; height: 30px; border-radius: 9px; flex-shrink: 0;
        background: linear-gradient(135deg, rgba(99,102,241,0.28), rgba(139,92,246,0.16));
        border: 1px solid rgba(129,140,248,0.28);
        display: flex; align-items: center; justify-content: center;
        font-size: 14px; letter-spacing: 0;
    }
    .alt-baslik {
        font-size: 12.5px !important;
        color: #7C8AA0 !important;
        font-weight: 450 !important;
        letter-spacing: .1px !important;
        margin: 7px 0 18px !important;
        padding: 0 0 12px 41px !important;
        border-bottom: 1px solid rgba(148,163,184,0.10) !important;
        position: relative !important;
    }
    .alt-baslik::before {
        content: ""; position: absolute; left: 41px; bottom: -1px;
        width: 40px; height: 2px; border-radius: 2px;
        background: linear-gradient(90deg, #6366F1, #8B5CF6);
    }
    
    /* ── BADGE / TAG ── */
    .tag-kirmizi { background:#2D0A0A; color:#FCA5A5; padding:4px 12px; border-radius:20px; font-size:11px; font-weight:700; letter-spacing:.3px; border:1px solid #FECACA; }
    .tag-turuncu { background:#2D200A; color:#FDE68A; padding:4px 12px; border-radius:20px; font-size:11px; font-weight:700; letter-spacing:.3px; border:1px solid #FDE68A; }
    .tag-sari    { background:#2D200A; color:#854D0E; padding:4px 12px; border-radius:20px; font-size:11px; font-weight:700; letter-spacing:.3px; border:1px solid #FEF08A; }
    .tag-yesil   { background:#0A2D15; color:#86EFAC; padding:4px 12px; border-radius:20px; font-size:11px; font-weight:700; letter-spacing:.3px; border:1px solid #BBF7D0; }
    .tag-mavi    { background:#0E1A3A; color:#93C5FD; padding:4px 12px; border-radius:20px; font-size:11px; font-weight:700; letter-spacing:.3px; border:1px solid #BFDBFE; }
    .tag-gri     { background: #1A2540; color:#64748B; padding:4px 12px; border-radius:20px; font-size:11px; font-weight:600; border:1px solid rgba(255,255,255,0.12); }
    
    /* ── ALERT KUTULARI ── */
    .uyari-box {
        background: linear-gradient(135deg, #2D200A, #2D200A);
        border-left: 4px solid #F59E0B;
        padding: 12px 16px;
        border-radius: 0 10px 10px 0;
        margin: 8px 0;
        font-size: 13px;
        font-weight: 500;
        color: #FCD34D;
        box-shadow: 0 1px 4px rgba(245,158,11,0.1);
    }
    .info-box {
        background: linear-gradient(135deg, #0E1A3A, #0E1A3A);
        border-left: 4px solid #3B82F6;
        padding: 12px 16px;
        border-radius: 0 10px 10px 0;
        margin: 8px 0;
        font-size: 13px;
        font-weight: 500;
        color: #60A5FA;
        box-shadow: 0 1px 4px rgba(59,130,246,0.1);
    }
    .ok-box {
        background: linear-gradient(135deg, #0A2D15, #0A2D15);
        border-left: 4px solid #22C55E;
        padding: 12px 16px;
        border-radius: 0 10px 10px 0;
        margin: 8px 0;
        font-size: 13px;
        font-weight: 500;
        color: #86EFAC;
        box-shadow: 0 1px 4px rgba(34,197,94,0.1);
    }
    .alarm-box {
        background: linear-gradient(135deg, #2D0A0F, #3D1515);
        border-left: 4px solid #EF4444;
        padding: 12px 16px;
        border-radius: 0 10px 10px 0;
        margin: 8px 0;
        font-size: 13px;
        font-weight: 500;
        color: #FCA5A5;
        box-shadow: 0 1px 4px rgba(239,68,68,0.1);
    }
    
    /* ── FORM ALANLARI ── */
    div[data-testid="stForm"] {
        background: #131C35 !important;
        border-radius: 16px !important;
        padding: 24px !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
    }
    
    /* ── DIVIDER ── */
    hr {
        border: none !important;
        border-top: 1px solid #F1F5F9 !important;
        margin: 20px 0 !important;
    }
    
    /* ── SUCCESS / ERROR / WARNING / INFO ── */
    /* Streamlit'in default st.alert renkleri dark tema'da okunmuyor. Burada manuel ayarlıyoruz. */
    div[data-testid="stAlert"] {
        border-radius: 10px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        padding: 12px 16px !important;
        border: 1px solid transparent !important;
    }
    
    /* Warning (sarı) - okunaklı koyu zemin + açık sarı yazı */
    div[data-testid="stAlert"][data-baseweb="notification"] [data-testid="stAlertContentWarning"],
    div[data-testid="stAlertContentWarning"],
    div[data-testid="stAlert"] div[role="alert"]:has(svg[fill*="warning"]),
    div.stAlert:has([data-testid="stAlertContentWarning"]) {
        background: #1F1A08 !important;
        color: #FCD34D !important;
        border-color: #FCD34D !important;
    }
    
    /* Error (kırmızı) */
    div[data-testid="stAlertContentError"],
    div.stAlert:has([data-testid="stAlertContentError"]) {
        background: #1F0808 !important;
        color: #FCA5A5 !important;
        border-color: #FCA5A5 !important;
    }
    
    /* Info (mavi) */
    div[data-testid="stAlertContentInfo"],
    div.stAlert:has([data-testid="stAlertContentInfo"]) {
        background: #0E1A3A !important;
        color: #60A5FA !important;
        border-color: #93C5FD !important;
    }
    
    /* Success (yeşil) */
    div[data-testid="stAlertContentSuccess"],
    div.stAlert:has([data-testid="stAlertContentSuccess"]) {
        background: #D1FAE5 !important;
        color: #064E3B !important;
        border-color: #6EE7B7 !important;
    }
    
    /* Tüm alert içindeki text - parent'tan inherit etsin */
    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] span,
    div[data-testid="stAlert"] strong,
    div[data-testid="stAlert"] div {
        color: inherit !important;
    }
    
    /* Alert içindeki bold yazıları daha koyu yap */
    div[data-testid="stAlert"] strong,
    div[data-testid="stAlert"] b {
        font-weight: 700 !important;
        color: inherit !important;
    }
    
    /* ── SPINNER ── */
    .stSpinner > div {
        border-top-color: #3B82F6 !important;
    }
    
    /* ── MONO FONT ── */
    .mono {
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 600 !important;
        letter-spacing: -.3px !important;
    }
    
    /* ── KART ── */
    .pro-kart {
        background: #131C35;
        border-radius: 16px;
        padding: 20px 24px;
        border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.04);
        transition: all .2s;
        margin-bottom: 12px;
    }
    .pro-kart:hover {
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        transform: translateY(-1px);
    }
    
    /* ── DOWNLOAD BUTON ── */
    .stDownloadButton button {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
    }
    
    /* ── MARKDOWN ── */
    .stMarkdown p {
        font-family: 'Inter', sans-serif !important;
        font-size: 14px !important;
        color: #CBD5E1 !important;
        line-height: 1.6 !important;
    }
    
    /* ── STREAMLIT ÜST BAR (HEADER) — yüksek kontrast, net ikonlar ── */
    header[data-testid="stHeader"],
    [data-testid="stHeader"] {
        background: #FFFFFF !important;
        backdrop-filter: blur(10px) !important;
        border-bottom: 1px solid #E2E8F0 !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    }
    /* Metin ve linkler koyu olsun (fill'i ZORLA dayatma — ikonları bozuyordu) */
    [data-testid="stHeader"] span,
    [data-testid="stHeader"] a,
    [data-testid="stHeader"] p,
    [data-testid="stToolbar"] span,
    [data-testid="stToolbarActions"] span {
        color: #CBD5E1 !important;
        opacity: 1 !important;
    }
    /* Buton zemini şeffaf, yazı koyu */
    [data-testid="stHeader"] button,
    [data-testid="stToolbar"] button,
    [data-testid="stToolbarActions"] button,
    [data-testid="stMainMenu"] button {
        background: transparent !important;
        color: #CBD5E1 !important;
        border: 1px solid transparent !important;
        border-radius: 8px !important;
        opacity: 1 !important;
    }
    [data-testid="stHeader"] button:hover,
    [data-testid="stToolbar"] button:hover {
        background: #1A2540 !important;
        border-color: #CBD5E1 !important;
        color: #E2E8F0 !important;
    }
    /* İkonlar: yalnızca SVG'yi currentColor ile boya — arka plan şekillerini doldurma */
    [data-testid="stHeader"] svg,
    [data-testid="stToolbar"] svg,
    [data-testid="stToolbarActions"] svg,
    [data-testid="stMainMenu"] svg {
        color: #CBD5E1 !important;
        fill: currentColor !important;
        opacity: 1 !important;
    }
    /* Share / deploy butonu — net çerçeveli, okunur */
    [data-testid="stHeader"] [data-testid="stBaseButton-header"],
    [data-testid="stHeader"] [data-testid="stBaseButton-headerNoPadding"] {
        color: #E2E8F0 !important;
        background: #151F38 !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    
    /* ── DARK MODE OVERRIDE — TÜM YAZILARI ZORLA DÜZELT ── */
    .stApp, .stApp * {
        color-scheme: light !important;
    }
    .stApp {
        background: linear-gradient(135deg, #0E1433 0%, #F8FAFF 50%, #0E1A3A 100%) !important;
    }
    /* Ana içerik yazıları — login sayfasını eziyordu, kaldırıldı */
    /* Yazı renkleri her sayfa için kendi spesifik kurallarında ayarlandı */
    /* Tab yazıları */
    .stTabs [data-baseweb="tab"] span { color: #64748B !important; }
    .stTabs [aria-selected="true"] span { color: #93C5FD !important; }
    /* Info / success / warning / error kutuları */
    /* DataFrame içi */
    .stDataFrame * { color: #E2E8F0 !important; }
    /* Expander */
    .streamlit-expanderHeader p, .streamlit-expanderHeader span { color: #CBD5E1 !important; }
    /* Selectbox, input */
    .stSelectbox div, .stTextInput div, .stNumberInput div { color: #E2E8F0 !important; }
    
    /* ─── LOGIN SAYFASI — global override'ları ez ─── */
    /* Sol panel: tüm elementler default BEYAZ — yüksek specificity */
    .stApp .login-left-panel,
    .stApp .login-left-panel *,
    .stApp .login-left-panel div,
    .stApp .login-left-panel p,
    .stApp .login-left-panel span,
    .stApp .login-left-panel h1,
    .stApp .login-left-panel h2,
    body .login-left-panel,
    body .login-left-panel * {
        color: #FFFFFF !important;
    }
    /* Açık gri (muted) yazılar için ayrı kural */
    .stApp .login-left-panel .login-muted,
    body .login-left-panel .login-muted {
        color: #CBD5E1 !important;
    }
    .stApp .login-left-panel .login-accent,
    body .login-left-panel .login-accent {
        color: #A5B4FC !important;
    }
    /* "profesyonelce" gradient — color:transparent koruyalım */
    .stApp .login-left-panel h1 .login-gradient-text,
    body .login-left-panel h1 .login-gradient-text {
        background: linear-gradient(135deg,#60A5FA,#A5B4FC,#C4B5FD) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
        color: transparent !important;
        display: inline-block !important;
    }
    
    /* Sağ panel kart: BEYAZ kart, içinde KOYU yazılar */
    .stApp .login-right-card,
    .stApp .login-right-card *,
    .stApp .login-right-card div,
    .stApp .login-right-card p,
    .stApp .login-right-card span,
    .stApp .login-right-card h2,
    body .login-right-card,
    body .login-right-card * {
        color: #E2E8F0 !important;
    }
    .stApp .login-right-card .login-card-muted,
    body .login-right-card .login-card-muted { color: #64748B !important; }
    .stApp .login-right-card .login-card-success,
    body .login-right-card .login-card-success { color: #047857 !important; }
    
    /* ── FILE UPLOADER — KARANLIK ALAN DÜZELTMESİ ── */
    [data-testid="stFileUploader"] {
        background: #131C35 !important;
        border-radius: 14px !important;
    }
    [data-testid="stFileUploader"] > div,
    [data-testid="stFileUploader"] section,
    [data-testid="stFileUploader"] section > div {
        background: #131C35 !important;
        border-radius: 12px !important;
    }
    [data-testid="stFileUploader"] section {
        border: 2px dashed #CBD5E1 !important;
        padding: 16px !important;
    }
    [data-testid="stFileUploader"] button {
        background: #0E1A3A !important;
        color: #93C5FD !important;
        border: 1.5px solid #BFDBFE !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }
    [data-testid="stFileUploader"] span,
    [data-testid="stFileUploader"] p,
    [data-testid="stFileUploader"] small,
    [data-testid="stFileUploaderDropzone"] span,
    [data-testid="stFileUploaderDropzone"] p {
        color: #64748B !important;
    }
    [data-testid="stFileUploaderDropzone"] {
        background: #131C35 !important;
        border: 2px dashed #CBD5E1 !important;
        border-radius: 12px !important;
    }
    
    /* ── DOWNLOAD BUTONU ── */
    [data-testid="stDownloadButton"] button {
        background: #131C35 !important;
        border: 1.5px solid #E2E8F0 !important;
        color: #CBD5E1 !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
    }
    [data-testid="stDownloadButton"] button:hover {
        background: #151F38 !important;
        border-color: #CBD5E1 !important;
    }
    
    /* ── SELECTBOX DROPDOWN — Karanlık açılır paneli düzelt ── */
    [data-baseweb="select"] > div {
        background: #131C35 !important;
        color: #E2E8F0 !important;
        border: 1.5px solid #E2E8F0 !important;
        border-radius: 10px !important;
    }
    [data-baseweb="select"] > div:hover {
        border-color: #CBD5E1 !important;
    }
    [data-baseweb="select"] span {
        color: #E2E8F0 !important;
        font-weight: 500 !important;
    }
    [data-baseweb="select"] svg {
        color: #64748B !important;
        fill: #64748B !important;
    }
    
    /* Açılır liste popover */
    [data-baseweb="popover"] {
        background: #131C35 !important;
        border-radius: 10px !important;
        box-shadow: 0 8px 24px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.08) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
    }
    [data-baseweb="popover"] * {
        background-color: transparent !important;
        color: #E2E8F0 !important;
    }
    [data-baseweb="menu"] {
        background: #131C35 !important;
        padding: 4px !important;
        border-radius: 8px !important;
    }
    [data-baseweb="menu"] * {
        color: #E2E8F0 !important;
    }
    [data-baseweb="menu"] li,
    [role="option"] {
        background: #131C35 !important;
        color: #E2E8F0 !important;
        padding: 8px 12px !important;
        border-radius: 6px !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        transition: background .15s !important;
    }
    [data-baseweb="menu"] li:hover,
    [role="option"]:hover,
    [role="option"][aria-selected="true"] {
        background: #0E1A3A !important;
        color: #93C5FD !important;
    }
    [data-baseweb="option"] {
        background: #131C35 !important;
        color: #E2E8F0 !important;
    }
    [data-baseweb="option"]:hover {
        background: #0E1A3A !important;
        color: #93C5FD !important;
    }
    /* Açık bir şekilde koyu renk oluşumlarını engelle */
    ul[role="listbox"] {
        background: #131C35 !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
    }
    ul[role="listbox"] li {
        background: #131C35 !important;
        color: #E2E8F0 !important;
    }
    
    /* ── NUMBER / TEXT / DATE INPUT (sidebar dışı) ── */
    [data-testid="stNumberInput"] input,
    [data-testid="stTextInput"] input,
    [data-testid="stDateInput"] input,
    textarea {
        background: #131C35 !important;
        color: #E2E8F0 !important;
    }
    /* Sidebar'da bu kuralı ez */
    section[data-testid="stSidebar"] [data-testid="stNumberInput"] input,
    section[data-testid="stSidebar"] [data-testid="stTextInput"] input,
    section[data-testid="stSidebar"] [data-testid="stDateInput"] input {
        background: rgba(15,22,41,0.6) !important;
        color: #F1F5F9 !important;
    }
    
    /* ── CHECKBOX ── */
    /* ── CHECKBOX ── (etiket okunur + kutu açık zeminli, siyah çıkmasın) */
    [data-testid="stCheckbox"] label,
    [data-testid="stCheckbox"] label p,
    [data-testid="stCheckbox"] label div,
    [data-testid="stCheckbox"] label span,
    [data-testid="stCheckbox"] [data-testid="stWidgetLabel"] {
        color: #CBD5E1 !important;
    }
    /* Kutucuğun kendisi: beyaz zemin, belirgin kenarlık */
    [data-testid="stCheckbox"] [data-baseweb="checkbox"] span[aria-hidden="true"],
    [data-testid="stCheckbox"] [role="checkbox"] {
        background-color: #FFFFFF !important;
        border: 1.5px solid #94A3B8 !important;
        border-radius: 5px !important;
    }
    /* İşaretliyken mavi dolgu, beyaz tik */
    [data-testid="stCheckbox"] [aria-checked="true"] span[aria-hidden="true"],
    [data-testid="stCheckbox"] [role="checkbox"][aria-checked="true"] {
        background-color: #2563EB !important;
        border-color: #2563EB !important;
        color: #FFFFFF !important;
    }
    [data-testid="stCheckbox"] [aria-checked="true"] svg { fill: #FFFFFF !important; }
    
    /* ── SIDEBAR HARİÇ TUT ── */
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] div,
    section[data-testid="stSidebar"] label {
        color: #E2E8F0 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] * {
        color: #E2E8F0 !important;
        background: rgba(255,255,255,0.08) !important;
    }
    
    /* ── HTML TABLE IN stMarkdown (dark theme) ── */
    .stMarkdown table { border-collapse: collapse !important; width: 100% !important; background: #0F1629 !important; }
    .stMarkdown table tr { background: #131C35 !important; }
    .stMarkdown table tr:nth-child(odd) { background: #0F1629 !important; }
    .stMarkdown table td { color: #CBD5E1 !important; }
    .stMarkdown table th { color: #94A3B8 !important; background: #0A0F1E !important; }
    .stMarkdown table tr:nth-child(even) td { background: rgba(255,255,255,0.03) !important; }
</style>
    """, unsafe_allow_html=True)
    

    # ── ANA İÇERİK ────────────────────────────────────────────────────
    # ── YARDIMCI FONKSİYONLAR ────────────────────────────────────────────
    GUNLER = ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"]
    
    KATEGORILER = {
        "cek":      {"label": "Çek",         "oncelik": 1, "renk": "#dc2626"},
        "kredi":    {"label": "Kredi",        "oncelik": 2, "renk": "#ea580c"},
        "kart":     {"label": "K.Kartı",      "oncelik": 3, "renk": "#d97706"},
        "vergi":    {"label": "Vergi",        "oncelik": 4, "renk": "#7c3aed"},
        "sgk":      {"label": "SGK",          "oncelik": 5, "renk": "#0891b2"},
        "kira":     {"label": "Kira",         "oncelik": 6, "renk": "#059669"},
        "sabit":    {"label": "Sabit Gider",  "oncelik": 7, "renk": "#2563eb"},
        "cari":     {"label": "Cari Hesap",   "oncelik": 8, "renk": "#be185d"},
        "ithalat":  {"label": "İthalat",      "oncelik": 9, "renk": "#0e7490"},
        "ihracat":  {"label": "İhracat",      "oncelik": 10, "renk": "#15803d"},
        "masraf":   {"label": "Masraf",       "oncelik": 11, "renk": "#92400e"},
        "maas":     {"label": "Maaş",         "oncelik": 12, "renk": "#1e40af"},
        "diger":    {"label": "Diğer",        "oncelik": 13, "renk": "#6b7280"},
    }
    
    
    def fmt(n):
        if n is None or (isinstance(n, float) and pd.isna(n)):
            return "-"
        return f"{float(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    
    def fmt_tarih(s):
        if not s:
            return ""
        try:
            d = pd.to_datetime(s)
            return d.strftime("%d-%m-%Y")
        except Exception:
            return str(s)
    
    
    def today_iso():
        return tr_today_iso()
    
    
    def tomorrow_iso():
        return (tr_today() + timedelta(days=1)).isoformat()
    
    
    def kayit_erteleme(odeme, eski_vade, yeni_vade):
        """
        Ertelemeyi session_state'te takip eder. Supabase kolonu gerekmez.
        Sayfa yenilense bile session içinde kalır, kapatınca silinir.
        """
        if "ertelemeler" not in st.session_state:
            st.session_state.ertelemeler = {}  # {odeme_id: {orijinal_vade, son_vade, sayi, son_tarih}}
    
        odeme_id = odeme["id"]
        eski_str = str(eski_vade)[:10] if eski_vade else None
        yeni_str = str(yeni_vade)[:10] if yeni_vade else None
    
        # Aynı tarih ise tracking yapma
        if eski_str == yeni_str:
            return
    
        if odeme_id not in st.session_state.ertelemeler:
            # İlk erteleme — orijinal vadeyi kaydet
            st.session_state.ertelemeler[odeme_id] = {
                "odeme_id": odeme_id,
                "firma": odeme.get("firma", ""),
                "aciklama": odeme.get("aciklama", ""),
                "kategori": odeme.get("kategori") or "diger",
                "tutar_tl": odeme.get("tutar_tl"),
                "tutar_usd": odeme.get("tutar_usd"),
                "orijinal_vade": eski_str,
                "son_vade": yeni_str,
                "sayi": 1,
                "son_tarih": tr_today_iso(),
            }
        else:
            # Tekrar erteleme — sayıyı artır, son_vade'yi güncelle
            kayit = st.session_state.ertelemeler[odeme_id]
            kayit["son_vade"] = yeni_str
            kayit["sayi"] = kayit.get("sayi", 1) + 1
            kayit["son_tarih"] = tr_today_iso()
            # Tutar/firma değişmiş olabilir, güncelle
            kayit["firma"] = odeme.get("firma", kayit.get("firma", ""))
            kayit["aciklama"] = odeme.get("aciklama", kayit.get("aciklama", ""))
            kayit["kategori"] = odeme.get("kategori") or kayit.get("kategori") or "diger"
            kayit["tutar_tl"] = odeme.get("tutar_tl")
            kayit["tutar_usd"] = odeme.get("tutar_usd")
    
    
    def get_kur():
        """
        USD/TL Kurunu döndürür.
        İlk çağrıda (session başladığında) otomatik olarak API'den günceli çeker.
        Başarısız olursa 38.50 fallback kullanır.
        Bir kez çekildikten sonra session boyunca aynı değeri kullanır (manuel güncellenirse değişir).
        """
        if "kur" not in st.session_state:
            # İlk defa çağrılıyor — API'den otomatik çek
            st.session_state.kur = 38.50  # önce fallback değer
            try:
                kur_cekilen, basarili = _fetch_kur_ilk_yukleme()
                if basarili and kur_cekilen and kur_cekilen > 1:
                    st.session_state.kur = kur_cekilen
                    st.session_state.kur_otomatik_cekildi = True
            except Exception:
                pass  # hata olsa da uygulama çalışsın, fallback kullanılır
        return st.session_state.kur
    
    
    def _fetch_kur_ilk_yukleme():
        """İlk yüklemede kur çekmek için ayrı fonksiyon — toast/spinner olmadan sessizce çalışır."""
        apis = [
            ("https://open.er-api.com/v6/latest/USD", lambda d: round(d["rates"]["TRY"], 2)),
            ("https://api.exchangerate-api.com/v4/latest/USD", lambda d: round(d["rates"]["TRY"], 2)),
            ("https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json", lambda d: round(d["usd"]["try"], 2)),
            ("https://api.frankfurter.app/latest?from=USD&to=TRY", lambda d: round(d["rates"]["TRY"], 2)),
        ]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        for url, parser in apis:
            try:
                r = requests.get(url, timeout=5, headers=headers)
                d = r.json()
                kur = parser(d)
                if kur and kur > 1:
                    return kur, True
            except Exception:
                continue
        return 38.50, False
    
    
    def fetch_kur_live():
        """Birden fazla API kaynağından USD/TL kurunu çeker."""
        apis = [
            ("https://open.er-api.com/v6/latest/USD", lambda d: round(d["rates"]["TRY"], 2)),
            ("https://api.exchangerate-api.com/v4/latest/USD", lambda d: round(d["rates"]["TRY"], 2)),
            ("https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json", lambda d: round(d["usd"]["try"], 2)),
            ("https://api.frankfurter.app/latest?from=USD&to=TRY", lambda d: round(d["rates"]["TRY"], 2)),
        ]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        for url, parser in apis:
            try:
                r = requests.get(url, timeout=8, headers=headers)
                d = r.json()
                kur = parser(d)
                if kur and kur > 1:
                    st.session_state.kur = kur
                    return kur, True
            except Exception:
                continue
        return get_kur(), False
    
    
    def get_aktif_odemeler():
        hafta = get_aktif_hafta()
        if not hafta:
            return [], None
        return get_hafta_odemeler(hafta["id"]), hafta
    
    
    def vade_durumu(vade_str):
        """Vade tarihine göre alarm durumu döndürür."""
        if not vade_str:
            return "normal"
        try:
            v = pd.to_datetime(vade_str).date()
            today = tr_today()
            if v < today:
                return "gecmis"
            elif v == today:
                return "bugun"
            elif v == today + timedelta(days=1):
                return "yarin"
            return "normal"
        except Exception:
            return "normal"
    
    
    # ── SIDEBAR ──────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown('<script>var s=window.parent.document.querySelector("[data-testid=stSidebar] > div");if(s)s.scrollTop=0;</script>', unsafe_allow_html=True)
        st.markdown(sidebar_stil(), unsafe_allow_html=True)
        st.markdown(sidebar_baslik("💳", "Muhasebe & Finans", "Ödeme Takip Sistemi"), unsafe_allow_html=True)

        aktif_kullanici = st.session_state.get("aktif_kullanici", "")
        if aktif_kullanici:
            st.markdown(sidebar_kullanici(aktif_kullanici), unsafe_allow_html=True)
            if st.button("🚪 Çıkış Yap", use_container_width=True):
                st.session_state.giris_yapildi = False
                st.session_state.aktif_kullanici = ""
                st.rerun()
    
        st.markdown("---")
    
        # Aktif hafta göster
        hafta = get_aktif_hafta()
        if hafta:
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:8px;
                background:rgba(37,99,235,0.10);
                border:1px solid rgba(59,130,246,0.22);
                border-radius:999px;
                padding:6px 12px;margin-bottom:12px;">
                <span style="font-size:12px">📅</span>
                <span style="font-size:11.5px;color:#93C5FD;font-weight:600;
                    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
                    letter-spacing:.2px">{hafta['hafta_adi'].title()}</span>
            </div>
            """, unsafe_allow_html=True)
    
        # ─── Sayfa listesi (kullanıcıya göre dinamik) ───
        aktif_kullanici_lower = st.session_state.get("aktif_kullanici", "").lower().strip()
        # Toplam Aktifler sayfasına yetkili kullanıcılar (yeni eklemek için bu set'e ekle)
        YETKILI_KULLANICILAR_TOPLAM_AKTIFLER = {"ibrahim", "cem", "yilmaz", "derman", "pamuk"}
        KISITLI_SAYFALAR = ["💰 Toplam Aktifler"]
    
        tum_sayfalar = [
            "📊 Dashboard",
            "💳 Bu Hafta",
            "🏦 Banka Bakiyeleri",
            "💰 Toplam Aktifler",
            "💸 Nakit Akış",
            "📋 Firma Çekleri",
            "🕐 Ödenenler & Geçmiş",
            "💵 Gelenler Geçmişi",
            "⏳ Ertelenen Ödemeler",
            "🧾 Cari Ekstre",
            "📂 Veri Yükleme",
            "📄 Raporlar & Bildirim",
        ]
    
        # Yetkili olmayan kullanıcılar için kısıtlı sayfaları menüden çıkar
        if aktif_kullanici_lower not in YETKILI_KULLANICILAR_TOPLAM_AKTIFLER:
            gosterilen_sayfalar = [s for s in tum_sayfalar if s not in KISITLI_SAYFALAR]
        else:
            gosterilen_sayfalar = tum_sayfalar
    
        sayfa = st.radio("Sayfa", gosterilen_sayfalar, label_visibility="collapsed")
    
        st.markdown("---")
    
        # Kur paneli
        st.markdown("**💱 USD/TL Kur**")
    
        # get_kur() çağır — session yeni ise otomatik API'den çekilir
        mevcut_kur = get_kur()
    
        # İlk otomatik çekim olduysa küçük bildirim
        if st.session_state.get("kur_otomatik_cekildi") and not st.session_state.get("kur_bildirim_gosterildi"):
            st.markdown(
                f'<div style="background:rgba(34,197,94,0.12);border:1px solid rgba(34,197,94,0.3);'
                f'border-radius:8px;padding:8px 8px;margin-bottom:8px;font-size:11px;color:#86EFAC;'
                f'display:flex;align-items:center;gap:8px;">'
                f'<span style="font-size:13px;">✓</span>'
                f'<span>Güncel kur otomatik alındı</span>'
                f'</div>',
                unsafe_allow_html=True
            )
            st.session_state.kur_bildirim_gosterildi = True
    
        yeni_kur = st.number_input("USD/TL Kur",
            value=float(mevcut_kur),
            step=0.01,
            min_value=1.0,
            format="%.2f",
            label_visibility="collapsed",
        )
        st.session_state.kur = yeni_kur
    
        if st.button("🔄 Güncel Kur", use_container_width=True):
            with st.spinner("Alınıyor..."):
                kur_cekilen, basarili = fetch_kur_live()
            if basarili:
                st.session_state.kur = kur_cekilen
                st.success(f"✅ {kur_cekilen} ₺")
                st.rerun()
            else:
                st.error("❌ Bağlanamadı, manuel girin.")
    
        st.markdown(f"<small>🕐 {tr_now().strftime('%d.%m.%Y %H:%M')}</small>", unsafe_allow_html=True)
    
        st.markdown("---")
    
        # ── Uygulamayı Yenile (Browser cache'i temizle + veri yenile) ──
        st.markdown("**⚙️ Sistem**")
        if st.button("🔄 Uygulamayı Yenile", use_container_width=True, help="Verileri ve arayüzü tazele"):
            # Session state'i temizle (kullanıcı bilgisi hariç)
            korunacak = {"giris_yapildi", "aktif_kullanici"}
            for k in list(st.session_state.keys()):
                if k not in korunacak:
                    del st.session_state[k]
            # Streamlit cache'lerini temizle
            try:
                st.cache_data.clear()
            except Exception:
                pass
            # JavaScript ile tarayıcı hard-reload (cache bypass)
            st.markdown("""
            <script>
                if (window.parent && window.parent.location) {
                    window.parent.location.reload(true);
                } else {
                    location.reload(true);
                }
            </script>
            """, unsafe_allow_html=True)
            st.rerun()
    
        # Versiyon bilgisi (küçük, alt köşe)
        st.markdown(
            f'<div style="font-size:11px;color:#64748B;margin-top:8px;text-align:center;'
            f'letter-spacing:.5px;font-family:monospace;opacity:0.6;">v{APP_VERSION}</div>',
            unsafe_allow_html=True
        )
    
    
    # ════════════════════════════════════════════════════════════════════
    # 1) DASHBOARD
    # ════════════════════════════════════════════════════════════════════
    @st.dialog("🔁 Bankalar Arası Virman", width="large")
    def _dlg_virman():
    
        bankalar = get_bankalar()
        kur = get_kur()

        if len(bankalar) < 2:
            st.warning("⚠️ Virman için en az 2 banka hesabınız olmalı. Önce 'Banka Bakiyeleri' sayfasından hesap ekleyin.")
            st.stop()

        # ── 🏦 Banka bakiyeleri (üstte tek bakışta — virman öncesi durumu gör) ──
        _renk_pb_v = {"USD": "#60A5FA", "TL": "#818CF8", "EUR": "#A78BFA"}
        metrik_satiri([{
            "label": b["hesap_adi"],
            "value": (("$" if b["para_birimi"] == "USD" else ("€" if b["para_birimi"] == "EUR" else "₺"))
                      + f"{float(b['bakiye']):,.2f}"),
            "renk": _renk_pb_v.get(b["para_birimi"], "#818CF8"),
            "alt": b["para_birimi"],
        } for b in bankalar])
        _v_tl = sum(float(b["bakiye"]) for b in bankalar if b["para_birimi"] == "TL")
        _v_usd = sum(float(b["bakiye"]) for b in bankalar if b["para_birimi"] == "USD")
        _v_eur = sum(float(b["bakiye"]) for b in bankalar if b["para_birimi"] == "EUR")
        _v_usd_esde = _v_usd + (_v_tl / kur if kur else 0) + (_v_eur * 1.08)
        st.markdown(
            '<div style="background:rgba(99,102,241,0.06);border:1px solid rgba(99,102,241,0.2);'
            'border-radius:10px;padding:8px 16px;margin:8px 0 16px;display:flex;gap:24px;flex-wrap:wrap;'
            'align-items:center;font-size:13px">'
            '<span style="color:#94A3B8;font-weight:700;text-transform:uppercase;font-size:11px;letter-spacing:1px">🏦 Toplam</span>'
            f'<span style="color:#818CF8">TL <b style="color:#E2E8F0;font-family:monospace">₺{_v_tl:,.2f}</b></span>'
            f'<span style="color:#60A5FA">USD <b style="color:#E2E8F0;font-family:monospace">${_v_usd:,.2f}</b></span>'
            + (f'<span style="color:#A78BFA">EUR <b style="color:#E2E8F0;font-family:monospace">€{_v_eur:,.2f}</b></span>' if _v_eur else '')
            + f'<span style="color:#34D399">≈ USD karşılığı <b style="font-family:monospace">${_v_usd_esde:,.2f}</b></span>'
            '</div>', unsafe_allow_html=True)

        # ─── Yeni Virman Formu ───
        st.markdown("### ➕ Yeni Virman")
    
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Kaynak Hesap**")
            kaynak_options = {f"{b['hesap_adi']} ({b['para_birimi']}) — Bakiye: {float(b['bakiye']):,.2f}": b['id'] for b in bankalar}
            kaynak_secim = st.selectbox("Kaynak", list(kaynak_options.keys()), key="virman_kaynak")
            kaynak_id = kaynak_options[kaynak_secim]
            kaynak_banka = next(b for b in bankalar if b['id'] == kaynak_id)
    
        with col2:
            st.markdown("**Hedef Hesap**")
            hedef_options = {f"{b['hesap_adi']} ({b['para_birimi']}) — Bakiye: {float(b['bakiye']):,.2f}": b['id']
                             for b in bankalar if b['id'] != kaynak_id}
            if not hedef_options:
                st.warning("Başka hesap yok.")
                st.stop()
            hedef_secim = st.selectbox("Hedef", list(hedef_options.keys()), key="virman_hedef")
            hedef_id = hedef_options[hedef_secim]
            hedef_banka = next(b for b in bankalar if b['id'] == hedef_id)
    
        # Para birimi farklılığı uyarısı + kur input
        farkli_pb = kaynak_banka['para_birimi'] != hedef_banka['para_birimi']
    
        col_t, col_k = st.columns([2, 1])
        with col_t:
            kaynak_bakiye_val = float(kaynak_banka.get('bakiye') or 0)
            tutar = st.number_input(
                f"Tutar ({kaynak_banka['para_birimi']})",
                min_value=0.0,
                max_value=max(kaynak_bakiye_val, 0.01),  # 0 ise input'u kullanılabilir tut
                step=0.01,
                format="%.2f",
                key="virman_tutar",
                disabled=(kaynak_bakiye_val <= 0)
            )
            if kaynak_bakiye_val <= 0:
                st.caption("⚠️ Bu hesabın bakiyesi 0 veya negatif. Virman yapılamaz.")
        with col_k:
            if farkli_pb:
                kullanilan_kur = st.number_input(
                    f"Kur ({kaynak_banka['para_birimi']}/{hedef_banka['para_birimi']})",
                    value=float(kur),
                    min_value=0.01,
                    step=0.01,
                    format="%.2f",
                    key="virman_kur",
                    help=f"1 USD = {kur} TL kullanılıyor"
                )
            else:
                kullanilan_kur = None
                st.markdown("<br>", unsafe_allow_html=True)
                st.caption("Aynı para birimi, kur gerekmez")
    
        # Hedefe gidecek hesaplanmış tutar (önizleme)
        if farkli_pb and kullanilan_kur and tutar > 0:
            if kaynak_banka['para_birimi'] == "TL" and hedef_banka['para_birimi'] == "USD":
                hedef_tutar_onizleme = tutar / kullanilan_kur
            elif kaynak_banka['para_birimi'] == "USD" and hedef_banka['para_birimi'] == "TL":
                hedef_tutar_onizleme = tutar * kullanilan_kur
            else:
                hedef_tutar_onizleme = tutar
            st.info(f"➡️ Hedef hesaba **{hedef_tutar_onizleme:,.2f} {hedef_banka['para_birimi']}** eklenecek (Kur: {kullanilan_kur})")
        elif tutar > 0:
            st.info(f"➡️ Hedef hesaba **{tutar:,.2f} {hedef_banka['para_birimi']}** eklenecek")
    
        aciklama = st.text_input("Açıklama (opsiyonel)", placeholder="Örn: Maaş ödemeleri için TL transferi", key="virman_aciklama")
    
        if st.button("🔁 Virmanı Yap", type="primary", use_container_width=True):
            if tutar <= 0:
                st.error("Tutar 0'dan büyük olmalı.")
            elif tutar > kaynak_bakiye_val:
                st.error(f"Yetersiz bakiye! Maksimum: {kaynak_bakiye_val:,.2f} {kaynak_banka['para_birimi']}")
            else:
                with st.spinner("İşleniyor..."):
                    basarili, mesaj = virman_yap(kaynak_id, hedef_id, tutar, aciklama, kullanilan_kur)
                if basarili:
                    st.success(mesaj)
                    st.balloons()
                    st.rerun()
                else:
                    st.error(f"❌ {mesaj}")
    
        st.markdown("---")
    
        # ─── Geçmiş Virmanlar ───
        st.markdown("### 📜 Son Virmanlar")
        virmanlar = get_virmanlar(limit=30)
    
        if not virmanlar:
            st.info("Henüz virman kaydı yok.")
        else:
            for v in virmanlar:
                kaynak_pb = v.get('kaynak_para_birimi') or 'TL'
                hedef_pb = v.get('hedef_para_birimi') or 'TL'
                kaynak_sym = "$" if kaynak_pb == "USD" else "₺"
                hedef_sym = "$" if hedef_pb == "USD" else "₺"
    
                # Float dönüşümleri (string olabilir)
                try:
                    v_tutar = float(v.get('tutar') or 0)
                except (TypeError, ValueError):
                    v_tutar = 0.0
                try:
                    v_hedef_tutar = float(v.get('hedef_tutar') or 0)
                except (TypeError, ValueError):
                    v_hedef_tutar = 0.0
                v_kur = v.get('kur_kullanilan')
                try:
                    v_kur_float = float(v_kur) if v_kur else None
                except (TypeError, ValueError):
                    v_kur_float = None
    
                col_a, col_b = st.columns([8, 1])
                with col_a:
                    kur_str = f" • Kur: {v_kur_float:.2f}" if v_kur_float else ""
                    tarih_str = v.get('tarih', '')
                    aciklama_str = f"<br><small style='color:#94A3B8'>📝 {v.get('aciklama')}</small>" if v.get('aciklama') else ""
    
                    st.markdown(f"""
                    <div style="background:#151F38;border:1px solid rgba(255,255,255,0.12);border-radius:10px;padding:12px 16px;margin-bottom:8px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <div>
                                <span style="font-size:13px;font-weight:700;color:#E2E8F0">{v.get('kaynak_hesap_adi','?')}</span>
                                <span style="margin:0 8px;color:#94A3B8;font-size:15px">→</span>
                                <span style="font-size:13px;font-weight:700;color:#E2E8F0">{v.get('hedef_hesap_adi','?')}</span>
                            </div>
                            <div style="text-align:right">
                                <span style="font-family:monospace;color:#DC2626;font-weight:600">-{kaynak_sym}{v_tutar:,.2f}</span>
                                &nbsp;&nbsp;
                                <span style="font-family:monospace;color:#16A34A;font-weight:600">+{hedef_sym}{v_hedef_tutar:,.2f}</span>
                            </div>
                        </div>
                        <div style="font-size:11px;color:#64748B;margin-top:4px">
                            🗓️ {tarih_str}{kur_str}
                            {aciklama_str}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    
                with col_b:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("↩️", key=f"virman_geri_{v['id']}", help="Bu virmanı geri al"):
                        basarili, mesaj = virman_geri_al(v['id'])
                        if basarili:
                            st.success(mesaj)
                            st.rerun()
                        else:
                            st.error(mesaj)
    
    
    # ════════════════════════════════════════════════════════════════════
    # 12) ERTELENEN ÖDEMELER
    # ════════════════════════════════════════════════════════════════════

    if sayfa == "📊 Dashboard":
        st.markdown('<div class="baslik"><span class="baslik-ikon">📊</span>Muhasebe & Finans — Dashboard</div>', unsafe_allow_html=True)
        st.markdown('<div class="alt-baslik">Haftalık ödeme durumu ve finansal özet</div>', unsafe_allow_html=True)
    
        kur = get_kur()
        odemeler, hafta = get_aktif_odemeler()
        bankalar = get_bankalar()
    
        if not odemeler:
            st.info("📂 Henüz veri yüklenmemiş. **'Veri Yükleme'** sekmesinden Excel dosyanızı yükleyin veya manuel ödeme ekleyin.")
            st.stop()
    
        # Alarmlar
        alarmlar = [o for o in odemeler if o["durum"] == "bekliyor" and vade_durumu(o.get("vade")) in ("bugun", "yarin", "gecmis")]
        bugun_alarmlar = [o for o in alarmlar if vade_durumu(o.get("vade")) == "bugun"]
        yarin_alarmlar = [o for o in alarmlar if vade_durumu(o.get("vade")) == "yarin"]
        gecmis_alarmlar = [o for o in alarmlar if vade_durumu(o.get("vade")) == "gecmis"]
    
        if gecmis_alarmlar:
            isimler = ", ".join(o["firma"] for o in gecmis_alarmlar[:3])
            st.markdown(f'''<div style="display:flex;align-items:center;gap:12px;background:rgba(248,113,113,0.1);border:1px solid rgba(248,113,113,0.25);border-left:4px solid #F87171;border-radius:10px;padding:12px 16px;margin-bottom:8px"><div style="width:18px;height:18px;min-width:18px;background:#EF4444;border-radius:50%;display:flex;align-items:center;justify-content:center"><span style="color:#fff;font-size:11px;font-weight:800">!</span></div><div><span style="font-size:11px;font-weight:700;color:#FCA5A5;letter-spacing:0.6px;text-transform:uppercase;font-family:Inter,sans-serif">Gecikmiş Ödeme</span>&nbsp;&nbsp;<span style="font-size:13px;color:#FECACA;font-family:Inter,sans-serif">{len(gecmis_alarmlar)} ödeme vadesi geçmiş: {isimler}</span></div></div>''', unsafe_allow_html=True)
        if bugun_alarmlar:
            isimler = ", ".join(o["firma"] for o in bugun_alarmlar[:3])
            st.markdown(f'''<div style="display:flex;align-items:center;gap:12px;background:rgba(251,191,36,0.1);border:1px solid rgba(251,191,36,0.25);border-left:4px solid #FBBF24;border-radius:10px;padding:12px 16px;margin-bottom:8px"><div style="width:18px;height:18px;min-width:18px;background:#F59E0B;border-radius:50%;display:flex;align-items:center;justify-content:center"><span style="color:#fff;font-size:11px;font-weight:800">!</span></div><div><span style="font-size:11px;font-weight:700;color:#FCD34D;letter-spacing:0.6px;text-transform:uppercase;font-family:Inter,sans-serif">Bugün Vadeli</span>&nbsp;&nbsp;<span style="font-size:13px;color:#FDE68A;font-family:Inter,sans-serif">{len(bugun_alarmlar)} ödeme — {isimler}</span></div></div>''', unsafe_allow_html=True)
        if yarin_alarmlar:
            isimler = ", ".join(o["firma"] for o in yarin_alarmlar[:3])
            st.markdown(f'''<div style="display:flex;align-items:center;gap:12px;background:rgba(96,165,250,0.1);border:1px solid rgba(96,165,250,0.25);border-left:4px solid #60A5FA;border-radius:10px;padding:12px 16px;margin-bottom:8px"><div style="width:18px;height:18px;min-width:18px;background:#3B82F6;border-radius:50%;display:flex;align-items:center;justify-content:center"><span style="color:#fff;font-size:11px;font-weight:800">i</span></div><div><span style="font-size:11px;font-weight:700;color:#93C5FD;letter-spacing:0.6px;text-transform:uppercase;font-family:Inter,sans-serif">Yarın Vadeli</span>&nbsp;&nbsp;<span style="font-size:13px;color:#BFDBFE;font-family:Inter,sans-serif">{len(yarin_alarmlar)} ödeme — {isimler}</span></div></div>''', unsafe_allow_html=True)
    
        # Özet metrikler
        tl_toplam = sum(o["tutar_tl"] or 0 for o in odemeler)
        usd_toplam = sum(o["tutar_usd"] or 0 for o in odemeler)
        odendi_tl = sum(o["tutar_tl"] or 0 for o in odemeler if o["durum"] == "odendi")
        odendi_usd = sum(o["tutar_usd"] or 0 for o in odemeler if o["durum"] == "odendi")
        bekleyen_tl = tl_toplam - odendi_tl
        bekleyen_usd = usd_toplam - odendi_usd
        odendi_cnt = sum(1 for o in odemeler if o["durum"] == "odendi")
        banka_tl = sum(b["bakiye"] for b in bankalar if b["para_birimi"] == "TL")
        banka_usd = sum(b["bakiye"] for b in bankalar if b["para_birimi"] == "USD")
        hafta_sonu_tl = banka_tl - bekleyen_tl - (bekleyen_usd * kur)
        ilerleme_pct = int((odendi_cnt / len(odemeler)) * 100) if odemeler else 0
    
        # ── Bugünün özeti ──
        today = today_iso()
        bugun_odemeler = [o for o in odemeler if (o.get("vade") or "")[:10] == today]
        bugun_tl_toplam  = sum(o.get("tutar_tl") or 0 for o in bugun_odemeler)
        bugun_usd_toplam = sum(o.get("tutar_usd") or 0 for o in bugun_odemeler)
        bugun_odendi_tl  = sum(o.get("tutar_tl") or 0 for o in bugun_odemeler if o["durum"] == "odendi")
        bugun_odendi_usd = sum(o.get("tutar_usd") or 0 for o in bugun_odemeler if o["durum"] == "odendi")
        bugun_kalan_tl   = bugun_tl_toplam - bugun_odendi_tl
        bugun_kalan_usd  = bugun_usd_toplam - bugun_odendi_usd
    
        # ── Profesyonel Metrik Kartları ──
        nakit_bg    = "#6EE7B7" if hafta_sonu_tl >= 0 else "#FCA5A5"
        nakit_renk  = "#6EE7B7" if hafta_sonu_tl >= 0 else "#FCA5A5"
        nakit_label = "Hafta Sonu Kalan" if hafta_sonu_tl >= 0 else "Nakit Açığı"
        nakit_alt   = "Tahmini bakiye" if hafta_sonu_tl >= 0 else "Tahmini açık"
        nakit_emoji = "✅" if hafta_sonu_tl >= 0 else "⚠️"
    
        st.markdown(f"""
        <style>
        .kart-grid {{ display:flex;flex-wrap:wrap;gap:12px;margin-bottom:14px }}
        .kart {{
            flex:1;min-width:150px;
            background:linear-gradient(180deg,rgba(255,255,255,0.030),rgba(255,255,255,0.012));
            border-radius:16px;
            padding:16px 18px;
            border:1px solid rgba(255,255,255,0.055);
            border-left:3px solid #818CF8;
            text-align:left;
            transition:transform .15s ease, border-color .15s ease;
        }}
        .kart:hover {{ transform:translateY(-2px);border-color:rgba(129,140,248,0.35) }}
        .kart-label {{
            font-size:11px;font-weight:700;letter-spacing:.6px;
            text-transform:uppercase;color:#8B97A8;margin-bottom:0px;
        }}
        .kart-deger {{
            font-size:19px;font-weight:800;
            font-variant-numeric:tabular-nums;
            letter-spacing:-0.3px;line-height:1.2;color:#F1F5F9;
        }}
        .kart-alt {{ font-size:11px;margin-top:4px;color:#7C8AA0;font-weight:500 }}
        .section-mini-title {{
            font-size:11px;font-weight:700;letter-spacing:1px;
            text-transform:uppercase;color:#64748B;margin:16px 0 8px;
        }}
        </style>
    
        <div class="section-mini-title">Haftalık özet</div>
        <div class="kart-grid">
    
          <div class="kart" style="border-left-color:#3B82F6">
            <div class="kart-label">Toplam TL</div>
            <div class="kart-deger">₺{fmt(tl_toplam)}</div>
            <div class="kart-alt">Ödendi: ₺{fmt(odendi_tl)}</div>
          </div>
    
          <div class="kart" style="border-left-color:#8B5CF6">
            <div class="kart-label">Toplam USD</div>
            <div class="kart-deger">${fmt(usd_toplam)}</div>
            <div class="kart-alt">≈ ₺{fmt(usd_toplam * kur)}</div>
          </div>
    
          <div class="kart" style="border-left-color:#10B981">
            <div class="kart-label">İlerleme</div>
            <div class="kart-deger" style="color:#34D399">{odendi_cnt} <span style="font-size:15px;color:#94A3B8;font-weight:600">/ {len(odemeler)}</span></div>
            <div style="background:rgba(255,255,255,0.1);border-radius:4px;height:5px;margin-top:8px;overflow:hidden">
              <div style="background:#10B981;height:100%;width:{ilerleme_pct}%"></div>
            </div>
            <div class="kart-alt" style="margin-top:4px">%{ilerleme_pct} tamamlandı</div>
          </div>
    
          <div class="kart" style="border-left-color:#F59E0B">
            <div class="kart-label">Bekleyen TL</div>
            <div class="kart-deger">₺{fmt(bekleyen_tl)}</div>
            <div class="kart-alt">Ödenmesi gereken</div>
          </div>
    
          <div class="kart" style="border-left-color:{'#34D399' if hafta_sonu_tl >= 0 else '#F87171'}">
            <div class="kart-label">{nakit_emoji} {nakit_label}</div>
            <div class="kart-deger" style="color:{'#34D399' if hafta_sonu_tl >= 0 else '#F87171'}">
              ₺{fmt(abs(hafta_sonu_tl))}
            </div>
            <div class="kart-alt">{nakit_alt}</div>
          </div>
    
        </div>
    
        <div class="section-mini-title">Bugünün bekleyen ödemeleri</div>
        <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-bottom:24px">
          <div class="kart" style="border-left-color:#FBBF24">
            <div class="kart-label">Bugün Kalan TL</div>
            <div class="kart-deger">{"₺" + fmt(bugun_kalan_tl) if bugun_kalan_tl else "—"}</div>
            <div class="kart-alt">Ödenmemiş TL</div>
          </div>
          <div class="kart" style="border-left-color:#FB923C">
            <div class="kart-label">Bugün Kalan USD</div>
            <div class="kart-deger">{"$" + fmt(bugun_kalan_usd) if bugun_kalan_usd else "—"}</div>
            <div class="kart-alt">Ödenmemiş USD</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    
        # ── Toplam Varlıklar (Banka Bakiyelerinden) ──
        banka_eur = sum(b["bakiye"] for b in bankalar if b["para_birimi"] == "EUR")
        toplam_varlik_tl = banka_tl + (banka_usd * kur)
        toplam_varlik_usd = banka_usd + (banka_tl / kur if kur > 0 else 0)
        st.markdown('<div style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#64748B;margin-bottom:8px">Toplam Varlıklar</div>', unsafe_allow_html=True)
        metrik_satiri([
            {"label": "Toplam TL Varlık", "value": f"₺{fmt(banka_tl)}", "renk": "#818CF8", "alt": "Tüm TL hesaplar"},
            {"label": "Toplam USD Varlık", "value": f"${fmt(banka_usd)}", "renk": "#818CF8", "alt": f"≈ ₺{fmt(banka_usd * kur)}"},
            {"label": "Toplam Varlık (TL)", "value": f"₺{fmt(toplam_varlik_tl)}", "renk": "#818CF8", "alt": f"≈ ${fmt(toplam_varlik_usd)}"},
            {"label": "Toplam Varlık (USD)", "value": f"${fmt(toplam_varlik_usd)}", "renk": "#818CF8", "alt": f"≈ ₺{fmt(toplam_varlik_tl)}"},
        ])
    
        st.markdown("---")
    
        # Kategori dağılımı ve durum grafikleri
        col1, col2 = st.columns(2)
    
        with col1:
            st.markdown('<div class="section-mini-title" style="margin:4px 0 2px">Kategori Bazında Ödeme Dağılımı</div>', unsafe_allow_html=True)
            kat_data = {}
            for o in odemeler:
                kat = o.get("kategori") or "diger"
                label = KATEGORILER.get(kat, {}).get("label", "Diğer")
                tl = (o.get("tutar_tl") or 0) + (o.get("tutar_usd") or 0) * kur
                kat_data[label] = kat_data.get(label, 0) + tl
    
            if kat_data:
                fig = go.Figure(go.Pie(
                    labels=list(kat_data.keys()),
                    values=list(kat_data.values()),
                    hole=0.72,                              # ince modern halka
                    sort=True, direction="clockwise",
                    marker=dict(
                        colors=[KATEGORILER.get(k, {}).get("renk", "#64748B")
                                    for k in [next((key for key, v in KATEGORILER.items() if v["label"] == lab), "diger")
                                              for lab in kat_data.keys()]],
                        # Dilim arası boşluk hissi: zeminle aynı renkte kalın ayraç
                        line=dict(color="#080C20", width=3),
                    ),
                    textfont=dict(family="Inter, sans-serif", size=12, color="#F1F5F9"),
                    textposition="inside",
                    textinfo="percent",
                    insidetextorientation="horizontal",
                    hovertemplate="<b>%{label}</b><br>₺%{value:,.0f}<br>%{percent}<extra></extra>",
                ))
                _kat_toplam = sum(kat_data.values())
                fig.add_annotation(
                    text=(f"<span style='font-size:11px;color:#8B97A8'>TOPLAM</span><br>"
                          f"<b>₺{_kat_toplam/1e6:,.1f}M</b>" if _kat_toplam >= 1e6 else
                          f"<span style='font-size:11px;color:#8B97A8'>TOPLAM</span><br>"
                          f"<b>₺{_kat_toplam:,.0f}</b>"),
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(size=20, family="Inter, sans-serif", color="#F1F5F9"),
                )
                fig.update_layout(
                    height=330, margin=dict(t=16, b=8, l=8, r=8),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    showlegend=True,
                    legend=dict(
                        font=dict(family="Inter, sans-serif", size=11, color="#B6C2D6"),
                        orientation="h",
                        yanchor="top", y=-0.06,
                        xanchor="center", x=0.5,
                        bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)",
                        itemsizing="constant", itemwidth=30,
                    ),
                    font=dict(family="Inter, sans-serif", color="#E2E8F0"),
                    hoverlabel=dict(bgcolor="#131C35", bordercolor="rgba(129,140,248,0.4)",
                                    font=dict(family="Inter, sans-serif", color="#F1F5F9")),
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    
        with col2:
            st.markdown('<div class="section-mini-title" style="margin:4px 0 2px">Ödeme Durumu</div>', unsafe_allow_html=True)
            odendi_tutar = sum((o.get("tutar_tl") or 0) + (o.get("tutar_usd") or 0) * kur
                               for o in odemeler if o["durum"] == "odendi")
            bekleyen_tutar = sum((o.get("tutar_tl") or 0) + (o.get("tutar_usd") or 0) * kur
                                 for o in odemeler if o["durum"] == "bekliyor")
            fig2 = go.Figure(go.Pie(
                labels=["Ödendi", "Bekliyor"],
                values=[odendi_tutar, bekleyen_tutar],
                hole=0.72,
                marker=dict(
                    colors=["#34D399", "#F59E0B"],
                    line=dict(color="#080C20", width=3),
                ),
                textfont=dict(family="Inter, sans-serif", size=12, color="#F1F5F9"),
                textposition="inside",
                textinfo="percent",
                hovertemplate="<b>%{label}</b><br>₺%{value:,.0f}<br>%{percent}<extra></extra>",
            ))
            fig2.add_annotation(
                text=(f"<span style='font-size:11px;color:#8B97A8'>TAMAMLANAN</span><br>"
                      f"<b>%{ilerleme_pct}</b>"),
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=24, family="Inter, sans-serif", color="#F1F5F9"),
            )
            fig2.update_layout(
                height=330, margin=dict(t=16, b=8, l=8, r=8),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, sans-serif", color="#E2E8F0"),
                showlegend=True,
                legend=dict(
                    font=dict(family="Inter, sans-serif", size=11, color="#B6C2D6"),
                    orientation="h",
                    yanchor="top", y=-0.06,
                    xanchor="center", x=0.5,
                    bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)",
                    itemsizing="constant", itemwidth=30,
                ),
                hoverlabel=dict(bgcolor="#131C35", bordercolor="rgba(129,140,248,0.4)",
                                font=dict(family="Inter, sans-serif", color="#F1F5F9")),
            )
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
    
        # Günlük ödeme takvimi özeti (varsayılan kapalı — simge durumunda)
        from collections import defaultdict
        by_day = defaultdict(list)
        for o in odemeler:
            day = (o.get("vade") or "")[:10] or "?"
            by_day[day].append(o)
    
        tablo_rows = []
        for day in sorted(by_day.keys()):
            try:
                d = pd.to_datetime(day)
                gun_adi = GUNLER[d.dayofweek + 1] if d.dayofweek < 6 else GUNLER[0]
                tarih_str = d.strftime("%d.%m.%Y")
            except Exception:
                gun_adi = ""
                tarih_str = day
    
            gun_odemeler = by_day[day]
            gun_tl = sum(o.get("tutar_tl") or 0 for o in gun_odemeler)
            gun_usd = sum(o.get("tutar_usd") or 0 for o in gun_odemeler)
            gun_odendi = sum(1 for o in gun_odemeler if o["durum"] == "odendi")
            vd = vade_durumu(day)
    
            tablo_rows.append({
                "Gün": gun_adi,
                "Tarih": tarih_str,
                "Ödeme Sayısı": len(gun_odemeler),
                "Ödendi": gun_odendi,
                "Bekliyor": len(gun_odemeler) - gun_odendi,
                "Tutar TL (₺)": f"₺{fmt(gun_tl)}" if gun_tl else "-",
                "Tutar USD ($)": f"${fmt(gun_usd)}" if gun_usd else "-",
                "Firma": ", ".join(sorted(set(o.get("firma") or "-" for o in gun_odemeler))),
                "Açıklama": " | ".join(o.get("aciklama") or "-" for o in gun_odemeler),
                "Durum": "⏰ BUGÜN" if vd == "bugun" else ("📅 YARIN" if vd == "yarin" else ("🚨 GECİKMİŞ" if vd == "gecmis" else "—")),
            })
    
        df_tablo = pd.DataFrame(tablo_rows)

        # ── Profesyonel HTML tablo (siyah bg yerine modern tasarım) ──
        def render_takvim_tablosu(df):
            if df.empty:
                st.info("Veri yok.")
                return

            # Renk kodlaması: Durum sütununa göre satır rengi
            def row_bg(durum):
                if "GECİKMİŞ" in str(durum):
                    return "rgba(239,68,68,0.08)"   # kırmızı tonu
                elif "BUGÜN" in str(durum):
                    return "rgba(245,158,11,0.10)"  # turuncu tonu
                elif "YARIN" in str(durum):
                    return "rgba(59,130,246,0.08)"  # mavi tonu
                return "transparent"

            def durum_badge(durum):
                if "GECİKMİŞ" in str(durum):
                    return f'''<span style="display:inline-flex;align-items:center;gap:4px;padding:4px 8px;background:rgba(239,68,68,0.12);color:#EF4444;border:1px solid rgba(239,68,68,0.3);border-radius:20px;font-size:11px;font-weight:700;letter-spacing:0.3px">🚨 GECİKMİŞ</span>'''
                elif "BUGÜN" in str(durum):
                    return f'''<span style="display:inline-flex;align-items:center;gap:4px;padding:4px 8px;background:rgba(245,158,11,0.12);color:#F59E0B;border:1px solid rgba(245,158,11,0.3);border-radius:20px;font-size:11px;font-weight:700;letter-spacing:0.3px">⏰ BUGÜN</span>'''
                elif "YARIN" in str(durum):
                    return f'''<span style="display:inline-flex;align-items:center;gap:4px;padding:4px 8px;background:rgba(59,130,246,0.12);color:#3B82F6;border:1px solid rgba(59,130,246,0.3);border-radius:20px;font-size:11px;font-weight:700;letter-spacing:0.3px">📅 YARIN</span>'''
                return f'''<span style="color:#94A3B8;font-size:11px">—</span>'''

            rows_html = ""
            for i, row in df.iterrows():
                bg = row_bg(row.get("Durum", ""))
                durum_html = durum_badge(row.get("Durum", ""))
                bekliyor_val = row.get("Bekliyor", 0)
                bekliyor_color = "#EF4444" if bekliyor_val and bekliyor_val > 0 else "#10B981"
                odendi_val = row.get("Ödendi", 0)
                _kisalt = lambda s, n=42: (str(s or "")[:n-1] + "…") if len(str(s or "")) > n else str(s or "")
                firma_disp = _kisalt(row.get("Firma",""))
                acik_disp = _kisalt(row.get("Açıklama",""))
                firma_title = str(row.get("Firma","") or "").replace(chr(34), "&quot;")
                acik_title = str(row.get("Açıklama","") or "").replace(chr(34), "&quot;")
                rows_html += f'''
                <tr style="background:{bg};border-bottom:1px solid rgba(0,0,0,0.06);transition:background 0.15s">
                  <td style="padding:8px 16px;font-weight:600;color:#CBD5E1;font-size:13px">{row.get("Gün","")}</td>
                  <td style="padding:8px 16px;color:#64748B;font-size:13px;font-family:'JetBrains Mono',monospace">{row.get("Tarih","")}</td>
                  <td style="padding:8px 16px;text-align:center;color:#64748B;font-size:13px;font-weight:600">{row.get("Ödeme Sayısı","")}</td>
                  <td style="padding:8px 16px;text-align:center;color:#10B981;font-weight:700;font-size:13px">{odendi_val}</td>
                  <td style="padding:8px 16px;text-align:center;color:{bekliyor_color};font-weight:700;font-size:13px">{bekliyor_val}</td>
                  <td style="padding:8px 16px;text-align:right;color:#E2E8F0;font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600">{row.get("Tutar TL (₺)","")}</td>
                  <td style="padding:8px 16px;text-align:right;color:#E2E8F0;font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600">{row.get("Tutar USD ($)","")}</td>
                  <td class="cell-firma" title="{firma_title}">{firma_disp}</td>
                  <td class="cell-acik" title="{acik_title}">{acik_disp}</td>
                  <td style="padding:8px 16px;text-align:center">{durum_html}</td>
                </tr>'''

            html = f'''
            <style>
              .takvim-tablo-wrap {{ overflow-x:auto; border-radius:14px; box-shadow:0 2px 16px rgba(0,0,0,0.08); }}
              .takvim-tablo {{ width:100%; border-collapse:collapse; font-family:'Inter','Inter',sans-serif; }}
              .takvim-tablo .cell-firma, .takvim-tablo .cell-acik {{ text-align:left; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:240px; padding:8px 16px; }}
              .takvim-tablo .cell-firma {{ color:#CBD5E1; font-size:13px; font-weight:600; }}
              .takvim-tablo .cell-acik {{ color:#94A3B8; font-size:13px; }}
              .takvim-tablo thead tr {{ background:linear-gradient(135deg,#1E293B 0%,#0F172A 100%); }}
              .takvim-tablo thead th {{ padding:12px 16px; color:#CBD5E1; font-size:11px; font-weight:700;
                letter-spacing:1px; text-transform:uppercase; border:none; white-space:nowrap; }}
              .takvim-tablo thead th:first-child {{ border-radius:14px 0 0 0; }}
              .takvim-tablo thead th:last-child {{ border-radius:0 14px 0 0; text-align:center; }}
              .takvim-tablo thead th:nth-child(3),
              .takvim-tablo thead th:nth-child(4),
              .takvim-tablo thead th:nth-child(5) {{ text-align:center; }}
              .takvim-tablo thead th:nth-child(6),
              .takvim-tablo thead th:nth-child(7) {{ text-align:right; }}
              .takvim-tablo tbody {{ background:#131C35; }}
              .takvim-tablo tbody tr:hover {{ background:rgba(99,102,241,0.04) !important; }}
              .takvim-tablo tbody tr:last-child td:first-child {{ border-radius:0 0 0 14px; }}
              .takvim-tablo tbody tr:last-child td:last-child {{ border-radius:0 0 14px 0; }}
            </style>
            <div class="takvim-tablo-wrap">
              <table class="takvim-tablo">
                <thead>
                  <tr>
                    <th>Gün</th><th>Tarih</th><th>Ödeme</th><th>Ödendi</th>
                    <th>Bekliyor</th><th>Tutar TL (₺)</th><th>Tutar USD ($)</th><th>Firma</th><th>Açıklama</th><th>Durum</th>
                  </tr>
                </thead>
                <tbody>{rows_html}</tbody>
              </table>
            </div>'''
            st.html(html)

        @st.dialog("📅 Günlük Ödeme Takvimi", width="large")
        def _dlg_odeme_takvimi():
            render_takvim_tablosu(df_tablo)
        if st.button("📅 Günlük Ödeme Takvimi", key="btn_acc_takvim", use_container_width=True):
            _dlg_odeme_takvimi()
    
    
    # ════════════════════════════════════════════════════════════════════
    # 2) BU HAFTA
    # ════════════════════════════════════════════════════════════════════
    elif sayfa == "💳 Bu Hafta":
        st.markdown('<div class="baslik"><span class="baslik-ikon">💳</span>Bu Hafta Ödemeleri</div>', unsafe_allow_html=True)
    
        kur = get_kur()
        odemeler, hafta = get_aktif_odemeler()
        bankalar = get_bankalar()
    
        # Manuel ödeme ekleme formu
        @st.dialog("➕ Manuel Ödeme Ekle", width="large")
        def _dlg_manuel_odeme():
            with st.form("manuel_form"):
                col1, col2 = st.columns(2)
                with col1:
                    firma = st.text_input("Firma / Kişi Adı *")
                    aciklama = st.text_input("Açıklama")
                    vade = st.date_input("Vade Tarihi *", value=tr_today())
                with col2:
                    kategori = st.selectbox("Kategori", list(KATEGORILER.keys()),
                                            format_func=lambda k: KATEGORILER[k]["label"])
                    tutar_tl = st.number_input("Tutar TL (₺)", min_value=0.0, step=100.0)
                    tutar_usd = st.number_input("Tutar USD ($)", min_value=0.0, step=100.0)
    
                ekle_btn = st.form_submit_button("➕ Ekle", type="primary")
                if ekle_btn:
                    if not firma:
                        st.error("Firma adı zorunludur.")
                    elif tutar_tl == 0 and tutar_usd == 0:
                        st.error("En az bir tutar girilmelidir.")
                    else:
                        if not hafta:
                            hafta_id = hafta_ekle("Manuel Girişler")
                        else:
                            hafta_id = hafta["id"]
                        odeme_ekle_manuel(
                            hafta_id, firma, aciklama, "",
                            vade.isoformat(),
                            tutar_tl if tutar_tl > 0 else None,
                            tutar_usd if tutar_usd > 0 else None,
                            kategori
                        )
                        st.success(f"✅ {firma} ödeme olarak eklendi.")
                        st.rerun()
        if st.button("➕ Manuel Ödeme Ekle", key="btn_acc_manuel", use_container_width=True):
            _dlg_manuel_odeme()
    
        if not odemeler:
            st.info("Veri yok. Veri Yükleme sekmesinden Excel yükleyin veya manuel ödeme ekleyin.")
            st.stop()
    
        # Alarmlar — yan yana pencere kartları (shared/ui standardı)
        gecmis_alarm = [(o, vade_durumu(o.get("vade"))) for o in odemeler if o["durum"] == "bekliyor" and vade_durumu(o.get("vade")) == "gecmis"]
        bugun_alarm  = [(o, vade_durumu(o.get("vade"))) for o in odemeler if o["durum"] == "bekliyor" and vade_durumu(o.get("vade")) == "bugun"]
        if gecmis_alarm or bugun_alarm:
            from shared.ui import RENK as _RENK, pencere_css as _pcss, pencere as _pen, pencere_grid as _pgrid, bos_durum as _bos
            st.markdown(_pcss(), unsafe_allow_html=True)
            _gec_html = "".join(
                f'<div class="alarm-box">🚨 <b>GECİKMİŞ</b> — {o["firma"]} — {"₺"+fmt(o["tutar_tl"]) if o.get("tutar_tl") else "$"+fmt(o["tutar_usd"])}</div>'
                for o, _ in gecmis_alarm
            ) or _bos("Gecikmiş ödeme yok")
            _bug_html = "".join(
                f'<div class="alarm-box" style="border-color:#F59E0B;background:linear-gradient(135deg,#2D200A,#3D2E15);">⚠️ <b>BUGÜN</b> — {o["firma"]} — {"₺"+fmt(o["tutar_tl"]) if o.get("tutar_tl") else "$"+fmt(o["tutar_usd"])}</div>'
                for o, _ in bugun_alarm
            ) or _bos("Bugün vadeli ödeme yok")
            st.markdown(_pgrid(
                _pen("🚨 GECİKMİŞ ÖDEMELER", _RENK["kirmizi"], _gec_html, rozet=f"{len(gecmis_alarm)} ödeme"),
                _pen("⚠️ BUGÜN VADELİ", _RENK["amber"], _bug_html, rozet=f"{len(bugun_alarm)} ödeme"),
            ), unsafe_allow_html=True)

       # Özet
        tl_toplam = sum(o.get("tutar_tl") or 0 for o in odemeler)
        usd_toplam = sum(o.get("tutar_usd") or 0 for o in odemeler)
        odendi_tl = sum(o.get("tutar_tl") or 0 for o in odemeler if o["durum"] == "odendi")
        odendi_usd = sum(o.get("tutar_usd") or 0 for o in odemeler if o["durum"] == "odendi")
        odendi_cnt = sum(1 for o in odemeler if o["durum"] == "odendi")
        kalan_tl = tl_toplam - odendi_tl
        ilerleme = int((odendi_cnt / len(odemeler)) * 100) if odemeler else 0
    
        metrik_satiri([
            {"label": "Toplam TL", "value": f"₺{fmt(tl_toplam)}", "renk": "#60A5FA", "alt": f"Ödendi: ₺{fmt(odendi_tl)}"},
            {"label": "Toplam USD", "value": f"${fmt(usd_toplam)}", "renk": "#A78BFA", "alt": f"Ödendi: ${fmt(odendi_usd)}"},
            {"label": "İlerleme", "value": f"{odendi_cnt}/{len(odemeler)}", "renk": "#34D399", "alt": f"%{ilerleme} tamamlandı"},
            {"label": "Kalan TL", "value": f"₺{fmt(kalan_tl)}", "renk": "#FBBF24", "alt": "Ödenmesi gereken"},
        ])
    
        st.markdown("---")
    
        # ─── KATEGORİ FİLTRESİ (ÇOKLU SEÇİM) ───
        # Mevcut ödemelerde hangi kategoriler var bul
        kategori_sayilari = {}
        for o in odemeler:
            k = o.get("kategori") or "diger"
            kategori_sayilari[k] = kategori_sayilari.get(k, 0) + 1
    
        # Multiselect için listesi — kullanılan kategoriler önceliğe göre sıralı
        filter_opts_multi = sorted(
            kategori_sayilari.keys(),
            key=lambda k: KATEGORILER.get(k, {"oncelik": 99}).get("oncelik", 99)
        )
        filter_labels_multi = {
            k: f"{KATEGORILER.get(k, {}).get('label', k)} ({kategori_sayilari[k]})"
            for k in filter_opts_multi
        }
    
        col_filt1, col_filt2 = st.columns([3, 1])
        with col_filt1:
            secilen_kategoriler = st.multiselect(
                f"🏷️ Kategori Filtresi (Boş bırakırsan tümü gösterilir — {len(odemeler)} ödeme)",
                options=filter_opts_multi,
                format_func=lambda k: filter_labels_multi[k],
                key="bu_hafta_kat_multi_v2",
                placeholder="Bir veya birden fazla kategori seçin (boş = tümü)"
            )
        with col_filt2:
            st.markdown("<br>", unsafe_allow_html=True)
            sadece_bekleyen = st.checkbox("Sadece bekleyenler", key="bu_hafta_sadece_bekleyen")
    
        # Filtre uygula
        filtrelenmis = odemeler
        if secilen_kategoriler:  # boş değilse
            filtrelenmis = [o for o in filtrelenmis if (o.get("kategori") or "diger") in secilen_kategoriler]
        if sadece_bekleyen:
            filtrelenmis = [o for o in filtrelenmis if o["durum"] == "bekliyor"]
    
        if not filtrelenmis:
            st.info("🔍 Seçilen filtrelere uygun ödeme bulunamadı. Filtreyi değiştirin.")
    
        # Gün bazında grupla (filtre boş olsa bile by_day tanımlı kalır, for loop boş çalışır)
        from collections import defaultdict
        by_day = defaultdict(list)
        for o in filtrelenmis:
            day = (o.get("vade") or "")[:10] or "?"
            by_day[day].append(o)
    
        # Öncelik sırala
        def oncelik_sirala(o):
            kat = o.get("kategori") or "diger"
            return KATEGORILER.get(kat, {"oncelik": 9})["oncelik"]
    
        for day in sorted(by_day.keys()):
            try:
                d = pd.to_datetime(day)
                gun_adi = GUNLER[d.dayofweek + 1] if d.dayofweek < 6 else GUNLER[0]
                tarih_str = d.strftime("%d %B %Y")
            except Exception:
                gun_adi = ""
                tarih_str = day
    
            gun_odemeler = sorted(by_day[day], key=oncelik_sirala)
            gun_tl = sum(o.get("tutar_tl") or 0 for o in gun_odemeler)
            gun_usd = sum(o.get("tutar_usd") or 0 for o in gun_odemeler)
            vd = vade_durumu(day)
    
            renk_header = "#0E1A3A" if vd == "bugun" else ("#2D200A" if vd == "yarin" else ("#FEF2F2" if vd == "gecmis" else "#F8F9FB"))
    
            etiket = ""
            if vd == "bugun":
                etiket = " 🔵 BUGÜN"
            elif vd == "yarin":
                etiket = " 🟡 YARIN"
            elif vd == "gecmis":
                etiket = " 🔴 GECİKMİŞ"
    
            with st.expander(f"**{gun_adi}{etiket}** — {tarih_str}  |  {'₺' + fmt(gun_tl) if gun_tl else ''}  {'$' + fmt(gun_usd) if gun_usd else ''}  ({len(gun_odemeler)} ödeme)", expanded=False):
                for o in gun_odemeler:
                    kat = o.get("kategori") or "diger"
                    kat_info = KATEGORILER.get(kat, KATEGORILER["diger"])
                    is_odendi = o["durum"] == "odendi"
    
                    col1, col2, col3, col4, col5 = st.columns([0.2, 3.5, 1.5, 3, 1.8])
    
                    with col1:
                        st.markdown(
                            f'<div style="width:8px;height:40px;background:{kat_info["renk"]};'
                            f'border-radius:4px;margin-top:4px;opacity:{"0.3" if is_odendi else "1"}"></div>',
                            unsafe_allow_html=True
                        )
    
                    with col2:
                        opacity = "opacity:0.4;" if is_odendi else ""
                        st.markdown(
                            f'<div style="{opacity}"><b style="font-size:13px;color:#E2E8F0">{o["firma"]}</b><br>'
                            f'<small style="color:#6b7280">{o.get("aciklama") or ""}</small></div>',
                            unsafe_allow_html=True
                        )
    
                    with col3:
                        st.markdown(
                            f'<span style="background:{kat_info["renk"]};color:white;font-size:11px;'
                            f'padding:0px 8px;border-radius:10px;font-weight:600">{kat_info["label"]}</span>',
                            unsafe_allow_html=True
                        )
    
                    with col4:
                        if o.get("tutar_tl"):
                            tutar_disp = f'<b style="color:#6EE7B7;font-size:15px;white-space:nowrap;font-family:monospace">₺{fmt(o["tutar_tl"])}</b>'
                        elif o.get("tutar_usd"):
                            tutar_disp = f'<b style="color:#93C5FD;font-size:15px;white-space:nowrap;font-family:monospace">${fmt(o["tutar_usd"])}</b>'
                        else:
                            tutar_disp = '<b style="color:#64748B;font-size:13px">—</b>'
                        st.markdown(tutar_disp, unsafe_allow_html=True)
                        sil_key = f"sil_onay_{o['id']}"
                        if not is_odendi:
                            c4b, c4c = st.columns(2)
                            with c4b:
                                edit_key = f"edit_tutar_toggle_{o['id']}"
                                if st.session_state.get(edit_key, False):
                                    if st.button("Kapat", key=f"open_edit_{o['id']}", use_container_width=True):
                                        st.session_state[edit_key] = False
                                        st.rerun()
                                else:
                                    if st.button("Duzenle", key=f"open_edit_{o['id']}", use_container_width=True):
                                        st.session_state[edit_key] = True
                                        st.rerun()
                            with c4c:
                                if st.session_state.get(sil_key, False):
                                    if st.button("❗ Onayla", key=f"sil_confirm_{o['id']}", type="primary", use_container_width=True,
                                                 help="Kaydı kalıcı siler"):
                                        odeme_sil(o["id"])
                                        st.session_state[sil_key] = False
                                        st.rerun()
                                else:
                                    if st.button("🗑 Sil", key=f"sil_btn_{o['id']}", use_container_width=True):
                                        st.session_state[sil_key] = True
                                        st.rerun()
                        else:
                            # Ödenmiş kayıt için de silme (iki adımlı onay)
                            if st.session_state.get(sil_key, False):
                                if st.button("❗ Onayla", key=f"sil_confirm_{o['id']}", type="primary", use_container_width=True,
                                             help="Ödenmiş kaydı kalıcı siler (banka bakiyesi geri YÜKLENMEZ)"):
                                    odeme_sil(o["id"])
                                    st.session_state[sil_key] = False
                                    st.rerun()
                            else:
                                if st.button("🗑 Sil", key=f"sil_btn_{o['id']}", use_container_width=True):
                                    st.session_state[sil_key] = True
                                    st.rerun()
                    
                    with col5:
                        if is_odendi:
                            b_id_col5 = o.get("banka_id")
                            banka_map_col5 = {b["id"]: f"{b['hesap_adi']} ({b['para_birimi']})" for b in bankalar}
                            banka_adi_col5 = banka_map_col5.get(b_id_col5, "—") if b_id_col5 else "—"
                            st.markdown(f'<div style="font-size:11px;color:#94A3B8;font-weight:600;margin-bottom:0px;text-align:center">{banka_adi_col5}</div>', unsafe_allow_html=True)
                            if st.button(f"↩ Geri Al", key=f"geri_{o['id']}"):
                                odeme_durum_guncelle(o["id"], "bekliyor", kur=kur)
                                st.rerun()
                        else:
                            banka_options = {f"{b['hesap_adi']} ({b['para_birimi']})": b["id"] for b in bankalar}
                            banka_options = {"— Seçiniz —": None} | banka_options
                            sec_banka = st.selectbox("Banka Seç", list(banka_options.keys()),
                                                     key=f"banka_{o['id']}", label_visibility="collapsed")
                            c5a, c5b = st.columns([1.3, 1])
                            with c5a:
                                if st.button(f"✅ Ödendi", key=f"od_{o['id']}", type="primary", use_container_width=True):
                                    banka_id = banka_options.get(sec_banka)
                                    odeme_durum_guncelle(o["id"], "odendi", banka_id, kur)
                                    st.rerun()
                            with c5b:
                                _kk = f"kismi_toggle_{o['id']}"
                                if st.button("💸 Kısmi", key=f"kismi_btn_{o['id']}", use_container_width=True,
                                             help="Tutarın bir kısmını öde — kalan bekliyor olarak devam eder"):
                                    st.session_state[_kk] = not st.session_state.get(_kk, False)
                                    st.rerun()

                    # ─── 💸 KISMİ ÖDEME paneli (bekleyenler için) ───
                    if not is_odendi and st.session_state.get(f"kismi_toggle_{o['id']}", False):
                        st.markdown(
                            '<div style="background:#0A2D1E;border:1px solid #34D399;'
                            'border-radius:10px;padding:12px 16px;margin:4px 0 8px 24px;">'
                            '<b style="color:#6EE7B7;font-size:13px">💸 Kısmi Ödeme — ödenen kısım ayrı '
                            '"ödendi" kaydı olur, kalan bekler</b>',
                            unsafe_allow_html=True)
                        kp1, kp2, kp3 = st.columns([2, 2, 1.3])
                        _mev_tl = float(o.get("tutar_tl") or 0)
                        _mev_usd = float(o.get("tutar_usd") or 0)
                        _ks_tl = kp1.number_input(f"Ödenen TL (mevcut ₺{fmt(_mev_tl)})",
                                                  min_value=0.0, max_value=max(0.0, _mev_tl),
                                                  value=0.0, step=100.0, format="%.2f",
                                                  key=f"kismi_tl_{o['id']}",
                                                  disabled=_mev_tl <= 0)
                        _ks_usd = kp2.number_input(f"Ödenen USD (mevcut ${fmt(_mev_usd)})",
                                                   min_value=0.0, max_value=max(0.0, _mev_usd),
                                                   value=0.0, step=100.0, format="%.2f",
                                                   key=f"kismi_usd_{o['id']}",
                                                   disabled=_mev_usd <= 0)
                        with kp3:
                            st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
                            if st.button("💸 Kısmi Öde", key=f"kismi_kaydet_{o['id']}", type="primary",
                                         use_container_width=True, disabled=(_ks_tl <= 0 and _ks_usd <= 0)):
                                _bid = ({f"{b['hesap_adi']} ({b['para_birimi']})": b["id"] for b in bankalar}
                                        .get(st.session_state.get(f"banka_{o['id']}", ""), None))
                                _ok_k, _msg_k = odeme_kismi_ode(o["id"], _ks_tl, _ks_usd, _bid, kur)
                                if _ok_k:
                                    st.session_state[f"kismi_toggle_{o['id']}"] = False
                                    st.success(_msg_k)
                                    st.rerun()
                                else:
                                    st.error(_msg_k)
                        st.caption("Banka düşümü için yukarıdaki **Banka Seç** kutusundan banka seç "
                                   "(seçmezsen bakiye düşülmez). Girilen tutar mevcut tutarı aşamaz.")
                        st.markdown('</div>', unsafe_allow_html=True)
    
                    # ─── Tutar + Kategori Revize Etme (sadece bekleyenler için) ───
                    if not is_odendi and st.session_state.get(f"edit_tutar_toggle_{o['id']}", False):
                        st.markdown(
                            '<div style="background:#2D200A;border:1px solid #FCD34D;'
                            'border-radius:10px;padding:12px 16px;margin:4px 0 8px 24px;">'
                                                        '<b style="color:#FDE68A;font-size:13px">🔶 Tutar / Tarih / Kategori / Açıklama Revize</b>',
                            unsafe_allow_html=True
                        )
                        col_tl, col_usd, col_kat, col_tarih, col_aciklama, col_kaydet = st.columns([2, 2, 2, 2, 3, 1])
                        with col_tl:
                            yeni_tl = st.number_input(
                                "TL (₺)",
                                value=float(o.get("tutar_tl") or 0),
                                min_value=0.0,
                                step=0.01,
                                format="%.2f",
                                key=f"edit_tl_{o['id']}"
                            )
                        with col_usd:
                            yeni_usd = st.number_input(
                                "USD ($)",
                                value=float(o.get("tutar_usd") or 0),
                                min_value=0.0,
                                step=0.01,
                                format="%.2f",
                                key=f"edit_usd_{o['id']}"
                            )
                        with col_kat:
                            # Kategori seçimi
                            kat_keys = list(KATEGORILER.keys())
                            mevcut_kat = o.get("kategori") or "diger"
                            try:
                                kat_idx = kat_keys.index(mevcut_kat)
                            except ValueError:
                                kat_idx = kat_keys.index("diger")
                            yeni_kat = st.selectbox(
                                "Kategori",
                                kat_keys,
                                index=kat_idx,
                                format_func=lambda k: KATEGORILER.get(k, {}).get("label", k),
                                key=f"edit_kat_{o['id']}"
                            )
                        with col_tarih:
                            mevcut_vade_dt = None
                            if o.get("vade"):
                                try:
                                    parsed_dt = pd.to_datetime(o.get("vade"))
                                    if pd.notna(parsed_dt):
                                        mevcut_vade_dt = parsed_dt.date()
                                except Exception:
                                    pass
                            yeni_tarih = st.date_input("Tarih", value=mevcut_vade_dt or tr_today(), key=f"edit_tarih_{o['id']}")
                        with col_aciklama:
                            yeni_aciklama = st.text_input("Açıklama", value=o.get("aciklama") or "", key=f"edit_acik_{o['id']}")
                        with col_kaydet:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("💾 Kaydet", key=f"save_tutar_{o['id']}", type="primary", use_container_width=True):
                                if yeni_tl <= 0 and yeni_usd <= 0:
                                    st.error("En az bir tutar (TL veya USD) 0'dan büyük olmalı.")
                                else:
                                    odeme_tutar_guncelle(
                                        o["id"],
                                        tutar_tl=yeni_tl,
                                        tutar_usd=yeni_usd
                                    )
                                    # Kategori değiştiyse onu da güncelle
                                    if yeni_kat != mevcut_kat:
                                        odeme_kategori_guncelle(o["id"], yeni_kat)
                                    # Vade güncelle
                                    if yeni_tarih and str(yeni_tarih) != str(o.get("vade", ""))[:10]:
                                        odeme_vade_guncelle(o["id"], str(yeni_tarih))
                                    # Açıklama güncelle
                                    if yeni_aciklama.strip() != (o.get("aciklama") or "").strip():
                                        odeme_aciklama_guncelle(o["id"], yeni_aciklama.strip())
    
                    # ─── Vade Öteleme (sadece bekleyenler için) ───
                    if not is_odendi:
                        # Güvenli vade parse
                        mevcut_vade = tr_today()
                        if o.get("vade"):
                            try:
                                parsed = pd.to_datetime(o.get("vade"))
                                if pd.notna(parsed):
                                    mevcut_vade = parsed.date()
                            except Exception:
                                pass
    
                        # Expander yerine toggle (checkbox) — expander içinde expander yasak
                        otele_goster = st.checkbox(
                            "📅 Vadeyi Ötele",
                            key=f"vade_toggle_{o['id']}",
                            value=False
                        )
                        if otele_goster:
                            st.markdown(
                                '<div style="background:#151F38;border:1px solid rgba(255,255,255,0.12);'
                                'border-radius:10px;padding:12px 16px;margin:4px 0 8px 24px;">',
                                unsafe_allow_html=True
                            )
                            col_tarih, col_kaydet = st.columns([3, 1])
                            with col_tarih:
                                yeni_vade = st.date_input(
                                    "Yeni vade tarihi",
                                    value=mevcut_vade,
                                    key=f"vade_{o['id']}",
                                    label_visibility="collapsed"
                                )
                            with col_kaydet:
                                if st.button("💾 Ötele", key=f"vade_save_{o['id']}", type="primary", use_container_width=True):
                                    kayit_erteleme(o, mevcut_vade, yeni_vade)
                                    odeme_vade_guncelle(o["id"], yeni_vade)
                                    st.success(f"Vade {yeni_vade.strftime('%d.%m.%Y')} olarak güncellendi.")
                                    st.rerun()
    
                            # Hızlı öteleme butonları
                            col_h1, col_h2, col_h3, col_h4 = st.columns(4)
                            with col_h1:
                                if st.button("+1 gün", key=f"v1_{o['id']}", use_container_width=True):
                                    yeni_t = mevcut_vade + timedelta(days=1)
                                    kayit_erteleme(o, mevcut_vade, yeni_t)
                                    odeme_vade_guncelle(o["id"], yeni_t)
                                    st.rerun()
                            with col_h2:
                                if st.button("+3 gün", key=f"v3_{o['id']}", use_container_width=True):
                                    yeni_t = mevcut_vade + timedelta(days=3)
                                    kayit_erteleme(o, mevcut_vade, yeni_t)
                                    odeme_vade_guncelle(o["id"], yeni_t)
                                    st.rerun()
                            with col_h3:
                                if st.button("+7 gün", key=f"v7_{o['id']}", use_container_width=True):
                                    yeni_t = mevcut_vade + timedelta(days=7)
                                    kayit_erteleme(o, mevcut_vade, yeni_t)
                                    odeme_vade_guncelle(o["id"], yeni_t)
                                    st.rerun()
                            with col_h4:
                                if st.button("+30 gün", key=f"v30_{o['id']}", use_container_width=True):
                                    yeni_t = mevcut_vade + timedelta(days=30)
                                    kayit_erteleme(o, mevcut_vade, yeni_t)
                                    odeme_vade_guncelle(o["id"], yeni_t)
                                    st.rerun()
                            st.markdown('</div>', unsafe_allow_html=True)
    
                    st.divider()
    
        # Export butonları
        col1, col2 = st.columns(2)
        with col1:
            excel_buf = export_excel(odemeler, hafta["hafta_adi"] if hafta else "", kur)
            st.download_button(
                "📥 Excel İndir",
                data=excel_buf,
                file_name=f"odeme_listesi_{tr_today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    
    
    # ════════════════════════════════════════════════════════════════════
    # 3) BANKA BAKİYELERİ
    # ════════════════════════════════════════════════════════════════════
    elif sayfa == "🏦 Banka Bakiyeleri":
        st.markdown('<div class="baslik"><span class="baslik-ikon">🏦</span>Banka Bakiyeleri</div>', unsafe_allow_html=True)
    
        kur = get_kur()
        bankalar = get_bankalar()
        odemeler, hafta = get_aktif_odemeler()
    
        bekleyen_tl = sum(o.get("tutar_tl") or 0 for o in odemeler if o["durum"] == "bekliyor")
        bekleyen_usd = sum(o.get("tutar_usd") or 0 for o in odemeler if o["durum"] == "bekliyor")
    
        # Hesap kartları — kompakt, ortak tema (para birimine göre renkli sol şerit)
        if bankalar:
            _renk_pb = {"USD": "#60A5FA", "TL": "#818CF8", "EUR": "#A78BFA"}
            _banka_cards = []
            for b in bankalar:
                sym = "$" if b["para_birimi"] == "USD" else ("€" if b["para_birimi"] == "EUR" else "₺")
                if b["para_birimi"] == "TL":
                    net = b["bakiye"] - bekleyen_tl - (bekleyen_usd * kur)
                    net_str = f"{'🟢' if net >= 0 else '🔴'} Hafta sonu: ₺{fmt(net)}"
                elif b["para_birimi"] == "USD":
                    net = b["bakiye"] - bekleyen_usd
                    net_str = f"{'🟢' if net >= 0 else '🔴'} Hafta sonu: ${fmt(net)}"
                else:
                    net_str = ""
                _banka_cards.append({
                    "label": b["hesap_adi"],
                    "value": f"{sym}{fmt(b['bakiye'])}",
                    "renk": _renk_pb.get(b["para_birimi"], "#818CF8"),
                    "alt": net_str,
                })
            metrik_satiri(_banka_cards)
        # === TOPLAM BAKIYE OZETI ===
        if bankalar:
            toplam_tl_hesap = sum(b["bakiye"] for b in bankalar if b["para_birimi"] == "TL")
            toplam_usd_hesap = sum(b["bakiye"] for b in bankalar if b["para_birimi"] == "USD")
            toplam_eur_hesap = sum(b["bakiye"] for b in bankalar if b["para_birimi"] == "EUR")
            toplam_usd_esde = toplam_usd_hesap + (toplam_tl_hesap / kur) + (toplam_eur_hesap * 1.08)
            toplam_html = (
                '<div style="background:linear-gradient(135deg,#0F172A 0%,#1E293B 100%);border:1px solid rgba(99,102,241,0.3);border-radius:14px;padding:16px 24px;margin-top:16px;box-shadow:0 4px 20px rgba(0,0,0,0.3);display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">'
                '<div style="display:flex;align-items:center;gap:8px"><span style="font-size:19px">🏦</span>'
                '<span style="font-size:15px;font-weight:700;color:#E2E8F0">TOPLAM BAKİYE</span></div>'
                '<div style="display:flex;gap:24px;flex-wrap:wrap">'
                f'<div style="text-align:right"><div style="font-size:11px;color:#94A3B8;margin-bottom:0px">Toplam TL</div><div style="font-size:19px;font-weight:800;color:#34D399;font-family:monospace">₺{toplam_tl_hesap:,.2f}</div></div>'
                f'<div style="text-align:right"><div style="font-size:11px;color:#94A3B8;margin-bottom:0px">Toplam USD</div><div style="font-size:19px;font-weight:800;color:#60A5FA;font-family:monospace">${toplam_usd_hesap:,.2f}</div></div>'
                f'<div style="text-align:right;border-left:1px solid rgba(255,255,255,0.1);padding-left:20px"><div style="font-size:11px;color:#94A3B8;margin-bottom:0px">Toplam USD Değeri</div><div style="font-size:19px;font-weight:700;color:#A78BFA;font-family:monospace">${toplam_usd_esde:,.2f}</div></div>'
                '</div></div>'
            )
            st.markdown(toplam_html, unsafe_allow_html=True)

        else:
            st.info("Henüz banka hesabı eklenmemiş.")

        # ── 💰 Gelen Tahsilat (bankaya para girişi) ──
        if bankalar:
            @st.dialog("💰 Tahsilat Ekle — Bankaya Para Girişi", width="large")
            def _dlg_tahsilat():
                st.caption("Müşteriden/dışarıdan gelen ödemeyi seçtiğin banka hesabına ekler.")
                _opts = {f"{b['hesap_adi']} ({b['para_birimi']}) — Bakiye: {float(b['bakiye']):,.2f}": b
                         for b in bankalar}
                _sec = st.selectbox("Hangi hesaba girdi?", list(_opts))
                _bank = _opts[_sec]
                _pb = _bank["para_birimi"]
                _sym = "$" if _pb == "USD" else ("€" if _pb == "EUR" else "₺")

                with st.form("tahsilat_form"):
                    _tutar = st.number_input(f"Tutar ({_pb})", min_value=0.0, step=0.01, format="%.2f")
                    _kaynak = st.text_input("Kimden / Kaynak", placeholder="Örn: Hepsiburada hakediş, ABC Ltd.")
                    _acik = st.text_input("Açıklama (opsiyonel)", placeholder="Örn: Haziran satış ödemesi")
                    _tarih = st.date_input("Tarih", value=tr_today())
                    _onay = st.form_submit_button(f"💰 {_sym} Tahsilatı İşle", type="primary", use_container_width=True)
                    if _onay:
                        if _tutar <= 0:
                            st.error("Tutar 0'dan büyük olmalı.")
                        else:
                            ok, msg = tahsilat_ekle(_bank["id"], _tutar, _kaynak, _acik, _tarih)
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)

                # Son tahsilatlar — geri alma imkânıyla
                _son = get_tahsilatlar(limit=8)
                if _son:
                    st.markdown("---")
                    st.markdown("**Son tahsilatlar**")
                    for t in _son:
                        _ts = "$" if t.get("para_birimi") == "USD" else ("€" if t.get("para_birimi") == "EUR" else "₺")
                        c1, c2 = st.columns([5, 1])
                        _knk = f" · {t['kaynak']}" if t.get("kaynak") else ""
                        c1.markdown(
                            f"<div style='font-size:12.5px'>{str(t.get('tarih',''))[:10]} — "
                            f"<b>{_ts}{float(t.get('tutar') or 0):,.2f}</b> → {t.get('hesap_adi','')}"
                            f"<span style='color:#8B97A8'>{_knk}</span></div>",
                            unsafe_allow_html=True)
                        if c2.button("↩", key=f"tahsilat_geri_{t['id']}", help="Geri al"):
                            ok, msg = tahsilat_geri_al(t["id"])
                            st.toast(msg)
                            st.rerun()

            if st.button("💰 Tahsilat Ekle (Para Girişi)", use_container_width=True, type="primary"):
                _dlg_tahsilat()

    
        st.markdown("---")
    
        # Hesap ekle / düzenle
        col1, col2 = st.columns(2)
    
        with col1:
            st.markdown("**➕ Yeni Hesap Ekle**")
            with st.form("banka_ekle"):
                hesap_adi = st.text_input("Hesap Adı", placeholder="Örn: YKB TL Hesabı")
                bakiye = st.number_input("Bakiye", min_value=0.0, step=0.01, format="%.2f")
                para_birimi = st.selectbox("Para Birimi", ["TL", "USD", "EUR"])
                if st.form_submit_button("➕ Ekle", type="primary"):
                    if hesap_adi:
                        banka_ekle(hesap_adi, bakiye, para_birimi)
                        st.success("✅ Hesap eklendi.")
                        st.rerun()
    
        with col2:
            if bankalar:
                st.markdown("**✏️ Hesap Düzenle / Sil**")
                secim = st.selectbox("Hesap seçin", [f"{b['hesap_adi']} ({b['para_birimi']})" for b in bankalar])
                sec_idx = [f"{b['hesap_adi']} ({b['para_birimi']})" for b in bankalar].index(secim)
                sec_banka = bankalar[sec_idx]
    
                with st.form("banka_duzenle"):
                    yeni_ad = st.text_input("Hesap Adı", value=sec_banka["hesap_adi"])
                    yeni_bakiye = st.number_input("Bakiye", value=float(sec_banka["bakiye"]), step=0.01, format="%.2f")
                    yeni_pb = st.selectbox("Para Birimi", ["TL", "USD", "EUR"],
                                           index=["TL", "USD", "EUR"].index(sec_banka["para_birimi"]))
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.form_submit_button("💾 Kaydet", type="primary"):
                            banka_guncelle(sec_banka["id"], yeni_ad, yeni_bakiye, yeni_pb)
                            st.success("✅ Güncellendi.")
                            st.rerun()
                    with col_b:
                        if st.form_submit_button("🗑 Sil"):
                            banka_sil(sec_banka["id"])
                            st.success("Silindi.")
                            st.rerun()
    
    
    # ════════════════════════════════════════════════════════════════════
    # 4) NAKİT AKIŞ
    # ════════════════════════════════════════════════════════════════════
        st.markdown("---")
        if st.button("🔁 Bankalar Arası Virman", key="btn_acc_virman", use_container_width=True):
            _dlg_virman()
    elif sayfa == "💸 Nakit Akış":
        st.markdown('<div class="baslik"><span class="baslik-ikon">💸</span>Nakit Akış Analizi</div>', unsafe_allow_html=True)
        st.markdown('<div class="alt-baslik">Bekleyen ödemeler baz alınmıştır</div>', unsafe_allow_html=True)
    
        kur = get_kur()
        odemeler, hafta = get_aktif_odemeler()
        bankalar = get_bankalar()
    
        if not odemeler:
            st.info("Veri yok.")
            st.stop()
    
        banka_tl = sum(b["bakiye"] for b in bankalar if b["para_birimi"] == "TL")
        banka_usd = sum(b["bakiye"] for b in bankalar if b["para_birimi"] == "USD")
    
        from collections import defaultdict
        by_day = defaultdict(list)
        for o in odemeler:
            if o["durum"] == "bekliyor":
                day = (o.get("vade") or "")[:10] or "?"
                by_day[day].append(o)
    
        kum_tl = 0
        kum_usd = 0
        tablo_rows = []
    
        for day in sorted(by_day.keys()):
            gun_tl = sum(o.get("tutar_tl") or 0 for o in by_day[day])
            gun_usd = sum(o.get("tutar_usd") or 0 for o in by_day[day])
            kum_tl += gun_tl
            kum_usd += gun_usd
            kalan = banka_tl - kum_tl - (kum_usd * kur)
    
            tablo_rows.append({
                "Tarih": day,
                "Günlük TL (₺)": gun_tl or None,
                "Günlük USD ($)": gun_usd or None,
                "Kümülatif TL (₺)": kum_tl,
                "Kümülatif USD ($)": kum_usd,
                "TL Bakiye Kalan (₺)": kalan,
                "_kalan": kalan,
            })
    
        net_tl = banka_tl - kum_tl - (kum_usd * kur)
        tablo_rows.append({
            "Tarih": "TOPLAM",
            "Günlük TL (₺)": kum_tl,
            "Günlük USD ($)": kum_usd,
            "Kümülatif TL (₺)": kum_tl,
            "Kümülatif USD ($)": kum_usd,
            "TL Bakiye Kalan (₺)": net_tl,
            "_kalan": net_tl,
        })
    
        df_nakit = pd.DataFrame(tablo_rows)
    
        def nakit_rengi(row):
            k = row.get("_kalan", 0)
            if row["Tarih"] == "TOPLAM":
                return ["background-color:#0A2D15;color:#86EFAC;font-weight:700" if k >= 0
                        else "background-color:#2D0A0A;color:#FCA5A5;font-weight:700"] * len(row)
            return ["background-color:#FEF2F2;color:#FCA5A5" if k < 0 else ""] * len(row)
    
        # --- Nakit Akis HTML Tablosu ---
        def fmt_tl(v):
            if v is None or (isinstance(v, float) and v == 0.0): return "-"
            return f"₺ {v:,.0f}"
        def fmt_usd(v):
            if v is None or (isinstance(v, float) and v == 0.0): return "-"
            return f"$ {v:,.0f}"
        nakit_rows_html = ""
        for idx_r, row in enumerate(tablo_rows):
            is_toplam = row["Tarih"] == "TOPLAM"
            kalan_v = row.get("_kalan") or 0
            if is_toplam:
                row_bg = "background:#1E293B;"
                tarih_style = "font-weight:700;color:#E2E8F0;font-size:13px;"
            elif idx_r % 2 == 0:
                row_bg = "background:#131C35;"
                tarih_style = "color:#CBD5E1;font-size:13px;"
            else:
                row_bg = "background:#151F38;"
                tarih_style = "color:#CBD5E1;font-size:13px;"
            kalan_color = "#10B981" if kalan_v >= 0 else "#EF4444"
            gun_tl_v = row.get("Günlük TL (₺)") or 0
            gun_usd_v = row.get("Günlük USD ($)") or 0
            kum_tl_v = row.get("Kümülatif TL (₺)") or 0
            kum_usd_v = row.get("Kümülatif USD ($)") or 0
            num_style = "font-family:monospace;font-size:13px;text-align:right;"
            num_style_top = "font-family:monospace;font-size:13px;text-align:right;font-weight:700;color:#94A3B8;"
            if is_toplam:
                nakit_rows_html += (
                    f'<tr style="{row_bg}border-top:2px solid #94A3B8;">'
                    f'<td style="padding:8px 16px;{tarih_style}border-bottom:1px solid #94A3B8;">Σ TOPLAM</td>'
                    f'<td style="padding:8px 16px;{num_style_top}border-bottom:1px solid #94A3B8;">{fmt_tl(gun_tl_v)}</td>'
                    f'<td style="padding:8px 16px;{num_style_top}border-bottom:1px solid #94A3B8;">{fmt_usd(gun_usd_v)}</td>'
                    f'<td style="padding:8px 16px;{num_style_top}border-bottom:1px solid #94A3B8;">{fmt_tl(kum_tl_v)}</td>'
                    f'<td style="padding:8px 16px;{num_style_top}border-bottom:1px solid #94A3B8;">{fmt_usd(kum_usd_v)}</td>'
                    f'<td style="padding:8px 16px;font-family:monospace;font-size:13px;text-align:right;font-weight:700;color:{kalan_color};border-bottom:1px solid #94A3B8;">{fmt_tl(kalan_v)}</td>'
                    '</tr>'
                )
            else:
                nakit_rows_html += (
                    f'<tr style="{row_bg}" onmouseover="this.style.background=''#0E1A3A''" onmouseout="this.style.background=''{"#131C35" if idx_r%2 else "#151F38"}''">'
                    f'<td style="padding:8px 16px;{tarih_style}border-bottom:1px solid rgba(255,255,255,0.1);">{row["Tarih"]}</td>'
                    f'<td style="padding:8px 16px;{num_style}color:#10B981;border-bottom:1px solid rgba(255,255,255,0.1);">{fmt_tl(gun_tl_v)}</td>'
                    f'<td style="padding:8px 16px;{num_style}color:#3B82F6;border-bottom:1px solid rgba(255,255,255,0.1);">{fmt_usd(gun_usd_v)}</td>'
                    f'<td style="padding:8px 16px;{num_style}color:#059669;border-bottom:1px solid rgba(255,255,255,0.1);">{fmt_tl(kum_tl_v)}</td>'
                    f'<td style="padding:8px 16px;{num_style}color:#2563EB;border-bottom:1px solid rgba(255,255,255,0.1);">{fmt_usd(kum_usd_v)}</td>'
                    f'<td style="padding:8px 16px;font-family:monospace;font-size:13px;text-align:right;font-weight:600;color:{kalan_color};border-bottom:1px solid rgba(255,255,255,0.1);">{fmt_tl(kalan_v)}</td>'
                    '</tr>'
                )
        nakit_tablo_html = (
            '<div style="border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);margin-top:8px;">'
            '<div style="overflow-x:auto;">'
            '<table style="width:100%;border-collapse:collapse;background:transparent;">'
            '<thead><tr style="background:linear-gradient(135deg,#1E293B 0%,#0F172A 100%);">'
            '<th style="padding:12px 16px;text-align:left;color:#94A3B8;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Tarih</th>'
            '<th style="padding:12px 16px;text-align:right;color:#34D399;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Günlük TL</th>'
            '<th style="padding:12px 16px;text-align:right;color:#60A5FA;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Günlük USD</th>'
            '<th style="padding:12px 16px;text-align:right;color:#6EE7B7;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Küm. TL</th>'
            '<th style="padding:12px 16px;text-align:right;color:#93C5FD;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Küm. USD</th>'
            '<th style="padding:12px 16px;text-align:right;color:#F59E0B;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">TL Bakiye</th>'
            '</tr></thead><tbody>'
            + nakit_rows_html +
            '</tbody></table></div></div>'
        )
        st.markdown(nakit_tablo_html, unsafe_allow_html=True)
    
        # Grafik
        df_grafik = pd.DataFrame([r for r in tablo_rows if r["Tarih"] != "TOPLAM"])
        if len(df_grafik) > 1:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_grafik["Tarih"],
                y=df_grafik["Günlük TL (₺)"].fillna(0),
                name="Günlük TL Ödemesi",
                marker_color="rgba(99,102,241,0.85)",
                marker_line=dict(color="rgba(0,0,0,0)", width=0),
                hovertemplate="<b>%{x}</b><br>Günlük: ₺%{y:,.0f}<extra></extra>",
            ))
            fig.add_trace(go.Scatter(
                x=df_grafik["Tarih"],
                y=df_grafik["TL Bakiye Kalan (₺)"],
                name="Kalan Bakiye",
                mode="lines+markers",
                line=dict(color="#34D399", width=2.5, shape="spline", smoothing=0.6),
                marker=dict(size=7, color="#34D399", line=dict(color="#080C20", width=2)),
                yaxis="y2",
                hovertemplate="<b>%{x}</b><br>Kalan: ₺%{y:,.0f}<extra></extra>",
            ))
            fig.update_layout(
                title=dict(
                    text="<b>Günlük Ödeme ve Kalan Bakiye</b>",
                    font=dict(family="Inter, sans-serif", size=15, color="#E2E8F0"),
                    x=0.01, xanchor="left",
                ),
                xaxis=dict(
                    title=dict(text="Tarih", font=dict(family="Inter, sans-serif", size=12, color="#475569")),
                    tickfont=dict(family="Inter, sans-serif", size=11, color="#94A3B8"),
                    gridcolor="rgba(148,163,184,0.10)",
                    linecolor="rgba(148,163,184,0.18)",
                    showline=True,
                ),
                yaxis=dict(
                    title=dict(text="Ödeme TL (₺)", font=dict(family="Inter, sans-serif", size=12, color="#818CF8")),
                    tickfont=dict(family="Inter, sans-serif", size=11, color="#94A3B8"),
                    gridcolor="rgba(148,163,184,0.10)",
                    linecolor="rgba(148,163,184,0.18)",
                    showline=True,
                    zeroline=True,
                    zerolinecolor="rgba(148,163,184,0.22)",
                ),
                yaxis2=dict(
                    title=dict(text="Kalan Bakiye (₺)", font=dict(family="Inter, sans-serif", size=12, color="#34D399")),
                    tickfont=dict(family="Inter, sans-serif", size=11, color="#94A3B8"),
                    overlaying="y",
                    side="right",
                    showgrid=False,
                    linecolor="rgba(148,163,184,0.18)",
                    showline=True,
                ),
                height=420,
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                hovermode="x unified",
                hoverlabel=dict(bgcolor="#131C35", bordercolor="rgba(129,140,248,0.4)",
                                font=dict(family="Inter, sans-serif", color="#F1F5F9")),
                bargap=0.45, barcornerradius=6,
                font=dict(family="Inter, sans-serif", color="#E2E8F0"),
                legend=dict(
                    font=dict(family="Inter, sans-serif", size=12, color="#E2E8F0"),
                    orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    bgcolor="rgba(255,255,255,0)",
                ),
                margin=dict(t=60, b=60, l=70, r=70),
            )
            st.plotly_chart(fig, use_container_width=True)
    
    
    # ════════════════════════════════════════════════════════════════════
    # 5) FİRMA ÇEKLERİ
    # ════════════════════════════════════════════════════════════════════
    elif sayfa == "📋 Firma Çekleri":
        st.markdown('<div class="baslik"><span class="baslik-ikon">📋</span>Firma Çekleri</div>', unsafe_allow_html=True)
        st.markdown('<div class="alt-baslik">TL ve USD bazında çek takibi</div>', unsafe_allow_html=True)
    
        def cek_ozet_kart(cekler, cur):
            if not cekler:
                return
            sym = "$" if cur == "USD" else "₺"
    
            def _f(v):
                try: return float(v) if v else 0.0
                except (TypeError, ValueError): return 0.0
    
            # Türkçe karakter normalize ederek karşılaştır (Python upper(İ→I sorununu önlemek için)
            def _tr_norm(s):
                if not s: return ""
                s = str(s)
                for tr, en in [("İ","i"),("I","i"),("Ş","s"),("ş","s"),("Ç","c"),("ç","c"),
                               ("Ğ","g"),("ğ","g"),("Ü","u"),("ü","u"),("Ö","o"),("ö","o"),("ı","i")]:
                    s = s.replace(tr, en)
                return s.lower().strip()
    
            ODENDI_DURUMLAR = {"odendi", "tahsil edildi", "tahsil", "iptal", "portfoyden cikti"}
    
            def _odendi_mi(c):
                return _tr_norm(c.get("durum", "")) in ODENDI_DURUMLAR
    
            toplam_meblagh = 0.0
            toplam_odenen = 0.0
            toplam_kalan = 0.0
            odendi_cnt = 0
            bekleyen_cnt = 0
    
            for c in cekler:
                meblag = _f(c.get("meblagh"))
                odenen_kolon = _f(c.get("odenen"))
                kalan_kolon = _f(c.get("kalan"))
                is_odendi = _odendi_mi(c)
    
                toplam_meblagh += meblag
    
                if is_odendi:
                    # Durum "Ödendi" ise: tamamı ödenmiş sayılır
                    # odenen kolonu 0 olsa bile meblağ kadar ödenmiş sayalım
                    toplam_odenen += max(odenen_kolon, meblag)
                    # kalan 0
                    odendi_cnt += 1
                else:
                    # Bekleyen/Ciro: gerçek kalanı hesapla
                    toplam_odenen += odenen_kolon
                    # Gerçek kalan: önce kalan kolonunu dene, mantıklı değilse meblag-odenen
                    gercek_kalan = meblag - odenen_kolon
                    # Eğer kalan kolonu dolu ve mantıklıysa kullan
                    if kalan_kolon > 0 and abs(kalan_kolon - gercek_kalan) < max(1, meblag * 0.01):
                        toplam_kalan += kalan_kolon
                    else:
                        toplam_kalan += max(0, gercek_kalan)
                    bekleyen_cnt += 1
    
            metrik_satiri([
                {"label": "Toplam Meblağ", "value": f"{sym}{fmt(toplam_meblagh)}", "renk": "#60A5FA", "alt": f"{len(cekler)} çek (tümü)"},
                {"label": "Toplam Ödenen", "value": f"{sym}{fmt(toplam_odenen)}", "renk": "#34D399", "alt": f"{odendi_cnt} adet ödendi"},
                {"label": "Toplam Kalan", "value": f"{sym}{fmt(toplam_kalan)}", "renk": "#FBBF24", "alt": f"{bekleyen_cnt} bekleyen/ciro"},
            ])
    
        def cek_tablo(cekler, cur):
            if not cekler:
                st.info(f"{cur} çeki bulunamadı.")
                return
            sym = "$" if cur == "USD" else "₺"
    
            cek_ozet_kart(cekler, cur)
    
            rows = []
            for c in cekler:
                vd = vade_durumu(c.get("vade"))
                rows.append({
                    "Ref No":       c.get("ref_no") or c.get("ref", ""),
                    "Çek No":       c.get("cek_no", ""),
                    "Tarih":        fmt_tarih(c.get("tarih")),
                    "Vade Tarihi":  fmt_tarih(c.get("vade")),
                    f"Meblağ ({sym})": c.get("meblagh", 0),
                    f"Ödenen ({sym})": c.get("odenen", 0),
                    f"Kalan ({sym})":  c.get("kalan", 0),
                    "Son Pozisyon": c.get("durum", "Bekliyor"),
                    "C/H Kodu":     c.get("ch_kodu", ""),
                    "C/H İsmi":     c.get("ch_ismi", ""),
                    "Banka":        c.get("banka", ""),
                    "Şube":         c.get("sube", ""),
                    "Hesap No":     c.get("hesap_no", ""),
                    "_vd": vd,
                })
            df = pd.DataFrame(rows)
    
            def renk(row):
                vd = row.get("_vd", "")
                durum = str(row.get("Son Pozisyon", "")).lower()
                if vd == "gecmis" and "odendi" not in durum:
                    return ["background-color:#2D0A0A;color:#FCA5A5"] * len(row)
                if vd == "bugun" and "odendi" not in durum:
                    return ["background-color:#2D200A;color:#FDE68A"] * len(row)
                if "odendi" in durum:
                    return ["background-color:#0A2D15;color:#86EFAC"] * len(row)
                if "ciro" in durum:
                    return ["background-color:#0E1A3A;color:#93C5FD"] * len(row)
                return [""] * len(row)
    
            # --- Firma Cekleri HTML Tablosu ---
            is_usd = (cur == "USD")
            sym_prefix = "$" if is_usd else "₺"
            def fmt_para(v):
                if v is None or v == 0: return "-"
                return f"{sym_prefix} {v:,.0f}"
            cek_rows_html = ""
            for ri, row in enumerate(rows):
                vd_raw = row.get("_vd", "")
                pozisyon = str(row.get("Son Pozisyon", "")).lower()
                kalan_v = row.get(f"Kalan ({sym})", 0) or 0
                if "gecmis" in pozisyon or ("odendi" not in pozisyon and kalan_v > 0 and vd_raw and vd_raw < str(__import__("datetime").date.today())):
                    row_bg = "background:rgba(248,113,113,0.08);"
                    ref_color = "#DC2626"
                elif "odendi" in pozisyon:
                    row_bg = "background:#0A2D15;" if ri % 2 == 0 else "background:rgba(16,185,129,0.08);"
                    ref_color = "#059669"
                elif ri % 2 == 0:
                    row_bg = "background:#131C35;"
                    ref_color = "#CBD5E1"
                else:
                    row_bg = "background:#151F38;"
                    ref_color = "#CBD5E1"
                meblag_v = row.get(f"Meblağ ({sym})", 0) or 0
                odenen_v = row.get(f"Ödenen ({sym})", 0) or 0
                kalan_color = "#10B981" if kalan_v <= 0 else "#EF4444"
                pos_badge = ""
                if "odendi" in pozisyon:
                    pos_badge = '<span style="background:#D1FAE5;color:#6EE7B7;font-size:11px;font-weight:600;padding:0px 8px;border-radius:10px;">✓ ÖDENDİ</span>'
                elif "bekliyor" in pozisyon:
                    pos_badge = '<span style="background:#2D200A;color:#FDE68A;font-size:11px;font-weight:600;padding:0px 8px;border-radius:10px;">⏳ BEKLİYOR</span>'
                elif "gecmis" in pozisyon:
                    pos_badge = '<span style="background:#2D0A0A;color:#FCA5A5;font-size:11px;font-weight:600;padding:0px 8px;border-radius:10px;">⚠ GECİKMİŞ</span>'
                else:
                    pos_badge = f'<span style="background:rgba(255,255,255,0.08);color:#94A3B8;font-size:11px;padding:0px 8px;border-radius:10px;">{row.get("Son Pozisyon","")}</span>'
                num_s = "font-family:monospace;font-size:13px;text-align:right;"
                cek_rows_html += (
                    f'<tr style="{row_bg}">'
                    f'<td style="padding:8px 12px;font-size:11px;font-weight:600;color:{ref_color};border-bottom:1px solid rgba(255,255,255,0.1);white-space:nowrap;">{row.get("Ref No","")}</td>'
                    f'<td style="padding:8px 12px;{num_s}color:#64748B;border-bottom:1px solid rgba(255,255,255,0.1);">{row.get("Cek No","") or row.get("Çek No","")}</td>'
                    f'<td style="padding:8px 12px;font-size:13px;color:#64748B;border-bottom:1px solid rgba(255,255,255,0.1);white-space:nowrap;">{row.get("Tarih","")}</td>'
                    f'<td style="padding:8px 12px;font-size:13px;color:#64748B;border-bottom:1px solid rgba(255,255,255,0.1);white-space:nowrap;">{row.get("Vade Tarihi","")}</td>'
                    f'<td style="padding:8px 12px;{num_s}color:#CBD5E1;font-weight:600;border-bottom:1px solid rgba(255,255,255,0.1);">{fmt_para(meblag_v)}</td>'
                    f'<td style="padding:8px 12px;{num_s}color:#059669;border-bottom:1px solid rgba(255,255,255,0.1);">{fmt_para(odenen_v)}</td>'
                    f'<td style="padding:8px 12px;{num_s}color:{kalan_color};font-weight:600;border-bottom:1px solid rgba(255,255,255,0.1);">{fmt_para(kalan_v)}</td>'
                    f'<td style="padding:8px 12px;text-align:center;border-bottom:1px solid rgba(255,255,255,0.1);">{pos_badge}</td>'
                    '</tr>'
                )
            cur_label = "USD ($)" if is_usd else "TL (₺)"
            cek_html = (
                '<div style="border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);margin-top:8px;">'
                '<div style="overflow-x:auto;">'
                '<table style="width:100%;border-collapse:collapse;">'
                '<thead><tr style="background:linear-gradient(135deg,#1E293B 0%,#0F172A 100%);">'
                '<th style="padding:12px 12px;text-align:left;color:#94A3B8;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Ref No</th>'
                '<th style="padding:12px 12px;text-align:right;color:#94A3B8;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Çek No</th>'
                '<th style="padding:12px 12px;text-align:left;color:#94A3B8;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Tarih</th>'
                '<th style="padding:12px 12px;text-align:left;color:#94A3B8;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Vade</th>'
                f'<th style="padding:12px 12px;text-align:right;color:#60A5FA;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Meblağ {cur_label}</th>'
                f'<th style="padding:12px 12px;text-align:right;color:#34D399;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Ödenen {cur_label}</th>'
                f'<th style="padding:12px 12px;text-align:right;color:#F59E0B;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Kalan {cur_label}</th>'
                '<th style="padding:12px 12px;text-align:center;color:#94A3B8;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Durum</th>'
                '</tr></thead><tbody>'
                + cek_rows_html +
                '</tbody></table></div></div>'
            )
            st.markdown(cek_html, unsafe_allow_html=True)
    
        tab1, tab2 = st.tabs(["💴 TL Çekleri", "💵 USD Çekleri"])
        with tab1:
            cek_tablo(get_cekler("TL"), "TL")
        with tab2:
            cek_tablo(get_cekler("USD"), "USD")
    
    
    # ════════════════════════════════════════════════════════════════════
    # 6) ÖDENENLEr
    # ════════════════════════════════════════════════════════════════════
    elif sayfa == "🕐 Ödenenler & Geçmiş":
        st.markdown('<div class="baslik"><span class="baslik-ikon">🕐</span>Ödenenler & Geçmiş</div>', unsafe_allow_html=True)
        st.markdown('<div class="alt-baslik">Bu haftanın ödenenleri · geçmiş haftalar · çek arşivi</div>', unsafe_allow_html=True)
        _tab_odenen, gecmis_tab1, gecmis_tab2 = st.tabs(["✅ Ödenen Ödemeler", "📅 Geçmiş Haftalar", "📋 Firma Çekleri Arşivi"])
        with _tab_odenen:
    
            odemeler, hafta = get_aktif_odemeler()
            odenenler = [o for o in odemeler if o["durum"] == "odendi"]
    
            if not odenenler:
                st.info("Bu haftada henüz ödendi olarak işaretlenmiş ödeme yok.")
                st.stop()
    
            tl_top = sum(o.get("tutar_tl") or 0 for o in odenenler)
            usd_top = sum(o.get("tutar_usd") or 0 for o in odenenler)
    
            metrik_satiri([
                {"label": "Ödenen TL", "value": f"₺{fmt(tl_top)}", "renk": "#34D399"},
                {"label": "Ödenen USD", "value": f"${fmt(usd_top)}", "renk": "#60A5FA"},
                {"label": "Ödeme Adedi", "value": f"{len(odenenler):,}", "renk": "#818CF8", "alt": "tamamlanan ödeme"},
            ])
    
            # Banka bilgilerini al (banka_id -> hesap_adi eşleştirmesi için)
            bankalar = get_bankalar()
            banka_map = {b["id"]: f"{b['hesap_adi']} ({b['para_birimi']})" for b in bankalar}
    
            rows = []
            for o in sorted(odenenler, key=lambda x: x.get("vade") or ""):
                kat = KATEGORILER.get(o.get("kategori") or "diger", KATEGORILER["diger"])
                banka_adi = "—"
                b_id = o.get("banka_id")
                if b_id:
                    banka_adi = banka_map.get(b_id, f"ID: {b_id} (silinmiş?)")
                rows.append({
                    "Firma": o["firma"],
                    "Açıklama": o.get("aciklama") or "",
                    "Kategori": kat["label"],
                    "Vade": fmt_tarih(o.get("vade")),
                    "Tutar TL (₺)": o.get("tutar_tl"),
                    "Tutar USD ($)": o.get("tutar_usd"),
                    "Ödendiği Banka": banka_adi,
                    "Ödendi Tarihi": o.get("odendi_tarih") or "",
                    "ID": o["id"],
                })
    
            # === ODENENLER HTML TABLO ===
            def fmt_para_od(val):
                if val is None or val == "" or (val != val):
                    return "-"
                try:
                    v = float(val)
                    if v == 0:
                        return "-"
                    return f"{v:,.0f}".replace(",", ".")
                except:
                    return str(val) if val else "-"

            od_rows_html = ""
            for idx2, row2 in enumerate(rows):
                bg = "#FFFFFF" if idx2 % 2 == 0 else "#F8FAFC"
                firma_v = str(row2.get("Firma") or "-")
                aciklama_v = str(row2.get("Açıklama") or "")
                kategori_v = str(row2.get("Kategori") or "-")
                vade_v = str(row2.get("Vade") or "-")
                tutar_tl_r = fmt_para_od(row2.get("Tutar TL (₺)"))
                tutar_usd_r = fmt_para_od(row2.get("Tutar USD ($)"))
                tl_str = f"₺ {tutar_tl_r}" if tutar_tl_r != "-" else "-"
                usd_str = f"$ {tutar_usd_r}" if tutar_usd_r != "-" else "-"
                banka_v = str(row2.get("Ödendiği Banka") or "-")
                tarih_v = str(row2.get("Ödendi Tarihi") or "-")
                od_rows_html += (
                    f'<tr style="background:{bg};border-bottom:1px solid rgba(255,255,255,0.1);">' +
                    f'<td style="padding:8px 16px;color:#CBD5E1;font-size:13px;font-weight:600;">{firma_v}</td>' +
                    f'<td style="padding:8px 8px;color:#64748B;font-size:13px;">{aciklama_v}</td>' +
                    f'<td style="padding:8px 8px;text-align:center;"><span style="background:rgba(99,102,241,0.15);color:#A5B4FC;padding:4px 8px;border-radius:12px;font-size:11px;font-weight:600;">{kategori_v}</span></td>' +
                    f'<td style="padding:8px 8px;text-align:center;color:#64748B;font-size:13px;">{vade_v}</td>' +
                    f'<td style="padding:8px 8px;text-align:right;color:#16A34A;font-size:13px;font-weight:700;font-family:monospace;">{tl_str}</td>' +
                    f'<td style="padding:8px 8px;text-align:right;color:#2563EB;font-size:13px;font-weight:700;font-family:monospace;">{usd_str}</td>' +
                    f'<td style="padding:8px 8px;color:#64748B;font-size:13px;">{banka_v}</td>' +
                    f'<td style="padding:8px 8px;text-align:center;color:#64748B;font-size:13px;">{tarih_v}</td>' +
                    '</tr>' + "\n"
                )

            od_header = (
                '<div style="border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);margin-top:8px;">' +
                '<table style="width:100%;border-collapse:collapse;font-family:Inter,sans-serif;font-size:13px;">' +
                '<thead><tr style="background:linear-gradient(135deg,#1E293B 0%,#0F172A 100%);">' +
                '<th style="padding:12px 16px;text-align:left;color:#94A3B8;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Firma</th>' +
                '<th style="padding:12px 8px;text-align:left;color:#94A3B8;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Açıklama</th>' +
                '<th style="padding:12px 8px;text-align:center;color:#94A3B8;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Kategori</th>' +
                '<th style="padding:12px 8px;text-align:center;color:#94A3B8;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Vade</th>' +
                '<th style="padding:12px 8px;text-align:right;color:#86EFAC;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Tutar TL (₺)</th>' +
                '<th style="padding:12px 8px;text-align:right;color:#93C5FD;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Tutar USD ($)</th>' +
                '<th style="padding:12px 8px;text-align:left;color:#94A3B8;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Ödendiği Banka</th>' +
                '<th style="padding:12px 8px;text-align:center;color:#94A3B8;font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;white-space:nowrap;">Ödendi Tarihi</th>' +
                '</tr></thead><tbody>' + "\n"
            )
            od_footer = '</tbody></table></div>' + "\n"
            od_tablo_html = od_header + od_rows_html + od_footer
            st.markdown(od_tablo_html, unsafe_allow_html=True)
    
            st.markdown("---")
            st.markdown("**Geri almak istediğin ödeme:**")
            geri_sec = st.selectbox("Ödeme seç", [f"{o['firma']} — {fmt_tarih(o.get('vade'))}" for o in odenenler])
            if st.button("↩ Geri Al", type="secondary"):
                idx = [f"{o['firma']} — {fmt_tarih(o.get('vade'))}" for o in odenenler].index(geri_sec)
                kur_now = get_kur()
                odeme_durum_guncelle(odenenler[idx]["id"], "bekliyor", kur=kur_now)
                st.success("Geri alındı.")
                st.rerun()
    
    
        # ════════════════════════════════════════════════════════════════════
        # 7) GEÇMİŞ
        # ════════════════════════════════════════════════════════════════════
    
    
        # ── TAB 1: Geçmiş Haftalar ────────────────────────────────
        with gecmis_tab1:
            haftalar = get_tum_haftalar()
    
            if not haftalar:
                st.info("Henüz geçmiş hafta yok.")
            else:
                aktif = get_aktif_hafta()
                aktif_id = aktif["id"] if aktif else None
    
                for h in haftalar:
                    ozet = get_hafta_ozet(h["id"])
                    is_aktif = h["id"] == aktif_id
    
                    renk = "#0E1A3A" if is_aktif else "rgba(255,255,255,0.03)"
                    border = "2px solid #2563EB" if is_aktif else "1px solid rgba(255,255,255,0.06)"
    
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        aktif_badge = '<span style="background:#2563EB;color:white;font-size:11px;padding:0px 8px;border-radius:4px;margin-left:8px;font-weight:700">AKTİF</span>' if is_aktif else ''
                        gecmis_html = (
                            f'<div style="background:{renk};border:{border};border-radius:10px;padding:16px 16px;margin-bottom:8px">'
                            f'<div style="font-size:15px;font-weight:700;color:#E2E8F0">{h["hafta_adi"]}{aktif_badge}</div>'
                            f'<div style="font-size:13px;color:#64748B;margin-top:4px">{ozet["toplam"]} ödeme · {ozet["odendi"]}/{ozet["toplam"]} ödendi · Yüklendi: {h["yuklendi_tarih"]}</div>'
                            f'<div style="margin-top:8px"><span class="tag-yesil">₺{fmt(ozet["tl_toplam"])}</span>&nbsp;<span class="tag-mavi">${fmt(ozet["usd_toplam"])}</span></div>'
                            '</div>'
                        )
                        st.markdown(gecmis_html, unsafe_allow_html=True)
    
                    with col2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if not is_aktif:
                            if st.button("📂 Aç", key=f"ac_{h['id']}"):
                                hafta_aktif_yap(h["id"])
                                st.success(f"'{h['hafta_adi']}' aktif yapıldı.")
                                st.rerun()
                        if st.button("🗑 Sil", key=f"sil_{h['id']}"):
                            hafta_sil(h["id"])
                            st.success("Silindi.")
                            st.rerun()
    
        # ── TAB 2: Firma Çekleri Arşivi ───────────────────────────
        with gecmis_tab2:
            st.markdown('<div style="font-size:13px;color:#64748B;margin-bottom:16px;">Firma çeklerinin tamamını burada görüntüleyebilir ve silebilirsiniz.</div>', unsafe_allow_html=True)
    
            cek_tab1, cek_tab2 = st.tabs(["💴 TL Çekleri", "💵 USD Çekleri"])
    
            def cek_arsiv_goster(para_birimi):
                cekler = get_cekler(para_birimi)
                sym = "$" if para_birimi == "USD" else "₺"
    
                if not cekler:
                    st.info(f"Kayıtlı {para_birimi} çeki yok.")
                    return
    
                # Toplu silme butonu
                col_sil1, col_sil2, col_sil3 = st.columns([2, 2, 2])
                with col_sil1:
                    st.markdown(
                        f'<div style="background:#151F38;border:1px solid rgba(255,255,255,0.12);border-radius:10px;'
                        f'padding:8px 16px;"><span style="font-size:11px;font-weight:600;color:#64748B;'
                        f'letter-spacing:.5px;text-transform:uppercase;">Toplam</span><br>'
                        f'<span style="font-size:19px;font-weight:700;color:#E2E8F0;font-family:monospace;">{len(cekler)} çek</span></div>',
                        unsafe_allow_html=True
                    )
                with col_sil2:
                    toplam_meblagh = sum(c.get("meblagh") or 0 for c in cekler)
                    st.markdown(
                        f'<div style="background:rgba(96,165,250,0.1);border:1px solid rgba(96,165,250,0.25);border-radius:10px;'
                        f'padding:8px 16px;"><span style="font-size:11px;font-weight:600;color:#93C5FD;'
                        f'letter-spacing:.5px;text-transform:uppercase;">Toplam Meblağ</span><br>'
                        f'<span style="font-size:19px;font-weight:700;color:#BFDBFE;font-family:monospace;">{sym}{fmt(toplam_meblagh)}</span></div>',
                        unsafe_allow_html=True
                    )
                with col_sil3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    # Onay checkbox'lı toplu silme
                    onay_key = f"toplu_sil_onay_{para_birimi}"
                    if st.session_state.get(onay_key, False):
                        if st.button(f"⚠️ EVET, TÜM {para_birimi} ÇEKLERİNİ SİL", key=f"toplu_sil_exec_{para_birimi}", type="primary", use_container_width=True):
                            cek_sil_hepsi(para_birimi)
                            st.session_state[onay_key] = False
                            st.success(f"Tüm {para_birimi} çekleri silindi.")
                            st.rerun()
                        if st.button("Vazgeç", key=f"toplu_sil_iptal_{para_birimi}", use_container_width=True):
                            st.session_state[onay_key] = False
                            st.rerun()
                    else:
                        if st.button(f"🗑 Tüm {para_birimi} Çeklerini Sil", key=f"toplu_sil_btn_{para_birimi}", use_container_width=True):
                            st.session_state[onay_key] = True
                            st.rerun()
    
                st.markdown("<br>", unsafe_allow_html=True)
    
                # Arama
                arama = st.text_input("🔍 Ara (firma, çek no, ref no)", key=f"cek_ara_{para_birimi}", placeholder="Aramak istediğiniz kelimeyi yazın...")
    
                # Filtrele
                filtre_cekler = cekler
                if arama:
                    a = arama.lower()
                    filtre_cekler = [c for c in cekler if
                                     a in str(c.get("ch_ismi", "")).lower() or
                                     a in str(c.get("cek_no", "")).lower() or
                                     a in str(c.get("ref_no", "")).lower() or
                                     a in str(c.get("banka", "")).lower()]
                    st.caption(f"{len(filtre_cekler)} / {len(cekler)} çek gösteriliyor")
    
                # Çek listesi (her biri silinebilir)
                for c in filtre_cekler:
                    durum_str = str(c.get("durum", "")).lower()
                    vd = vade_durumu(c.get("vade"))
    
                    if "odendi" in durum_str:
                        kart_bg = "#0A2D15"; kart_border = "#86EFAC"; durum_renk = "#86EFAC"
                    elif "ciro" in durum_str:
                        kart_bg = "#0E1A3A"; kart_border = "#93C5FD"; durum_renk = "#93C5FD"
                    elif vd == "gecmis":
                        kart_bg = "#2D0A0A"; kart_border = "#FCA5A5"; durum_renk = "#FCA5A5"
                    elif vd == "bugun":
                        kart_bg = "#2D200A"; kart_border = "#FCD34D"; durum_renk = "#FDE68A"
                    else:
                        kart_bg = "#F8FAFC"; kart_border = "#E2E8F0"; durum_renk = "#94A3B8"
    
                    col_a, col_b = st.columns([9, 1])
                    with col_a:
                        st.markdown(f"""
                        <div style="background:{kart_bg};border:1px solid {kart_border};border-radius:10px;padding:12px 16px;margin-bottom:8px">
                            <div style="display:grid;grid-template-columns:1.5fr 1.5fr 1fr 1.5fr 1fr;gap:12px;align-items:center">
                                <div>
                                    <div style="font-size:13px;color:#64748B;font-weight:600">ÇEK NO</div>
                                    <div style="font-size:13px;font-weight:700;color:#E2E8F0;font-family:monospace">{c.get('cek_no') or '-'}</div>
                                    <div style="font-size:11px;color:#64748B;margin-top:0px">Ref: {c.get('ref_no') or '-'}</div>
                                </div>
                                <div>
                                    <div style="font-size:13px;color:#64748B;font-weight:600">CARİ/FİRMA</div>
                                    <div style="font-size:13px;font-weight:600;color:#E2E8F0">{c.get('ch_ismi') or '-'}</div>
                                    <div style="font-size:11px;color:#64748B;margin-top:0px">{c.get('ch_kodu') or ''}</div>
                                </div>
                                <div>
                                    <div style="font-size:13px;color:#64748B;font-weight:600">VADE</div>
                                    <div style="font-size:13px;font-weight:600;color:#E2E8F0">{fmt_tarih(c.get('vade')) or '-'}</div>
                                </div>
                                <div>
                                    <div style="font-size:13px;color:#64748B;font-weight:600">MEBLAĞ / KALAN</div>
                                    <div style="font-size:15px;font-weight:700;color:#E2E8F0;font-family:monospace">{sym}{fmt(c.get('meblagh') or 0)}</div>
                                    <div style="font-size:11px;color:#64748B;margin-top:0px">Kalan: {sym}{fmt(c.get('kalan') or 0)}</div>
                                </div>
                                <div>
                                    <div style="font-size:13px;color:#64748B;font-weight:600">DURUM</div>
                                    <div style="font-size:13px;font-weight:700;color:{durum_renk};text-transform:uppercase;letter-spacing:.3px">{c.get('durum') or 'Bekliyor'}</div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    with col_b:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("🗑", key=f"cek_sil_{c.get('id')}", help="Bu çeki sil"):
                            cek_sil(c.get("id"))
                            st.success("Silindi.")
                            st.rerun()
    
            with cek_tab1:
                cek_arsiv_goster("TL")
            with cek_tab2:
                cek_arsiv_goster("USD")
    
    
    # ════════════════════════════════════════════════════════════════════
    # 7b) GELENLER GEÇMİŞİ — para girişleri (tahsilatlar)
    # ════════════════════════════════════════════════════════════════════
    elif sayfa == "💵 Gelenler Geçmişi":
        st.markdown('<div class="baslik"><span class="baslik-ikon">💵</span>Gelenler Geçmişi</div>', unsafe_allow_html=True)
        st.markdown('<div class="alt-baslik">Kimden · ne kadar · hangi bankaya · ne zaman gelmiş — tüm para girişleri</div>', unsafe_allow_html=True)

        _tahsilatlar = get_tahsilatlar(limit=2000)
        if not _tahsilatlar:
            st.info("Henüz tahsilat (para girişi) kaydı yok. Banka Bakiyeleri sayfasından "
                    "**💰 Tahsilat Ekle** ile giriş yapabilirsin.")
            st.stop()

        import pandas as _pd
        _gdf = _pd.DataFrame([{
            "Tarih": str(t.get("tarih", ""))[:10],
            "Kaynak (Kimden)": (t.get("kaynak") or "—").strip() or "—",
            "Banka": t.get("hesap_adi", "—"),
            "Döviz": t.get("para_birimi", ""),
            "Tutar": float(t.get("tutar", 0) or 0),
            "Açıklama": (t.get("aciklama") or "").strip(),
        } for t in _tahsilatlar])

        # ── Filtreler ──
        f1, f2, f3 = st.columns([1.3, 1.3, 1])
        _kaynaklar = ["Tümü"] + sorted([k for k in _gdf["Kaynak (Kimden)"].unique() if k and k != "—"])
        _bankalar_f = ["Tümü"] + sorted(_gdf["Banka"].unique().tolist())
        _sec_kaynak = f1.selectbox("Kaynak (kimden)", _kaynaklar, key="gg_kaynak")
        _sec_banka = f2.selectbox("Banka", _bankalar_f, key="gg_banka")
        _sec_doviz = f3.selectbox("Döviz", ["Tümü"] + sorted([d for d in _gdf["Döviz"].unique() if d]), key="gg_doviz")

        _f = _gdf.copy()
        if _sec_kaynak != "Tümü":
            _f = _f[_f["Kaynak (Kimden)"] == _sec_kaynak]
        if _sec_banka != "Tümü":
            _f = _f[_f["Banka"] == _sec_banka]
        if _sec_doviz != "Tümü":
            _f = _f[_f["Döviz"] == _sec_doviz]

        # ── Özet metrikler (döviz bazında toplam) ──
        _tl = _f[_f["Döviz"] == "TL"]["Tutar"].sum()
        _usd = _f[_f["Döviz"] == "USD"]["Tutar"].sum()
        _eur = _f[_f["Döviz"] == "EUR"]["Tutar"].sum()
        metrik_satiri([
            {"label": "Gelen TL", "value": f"₺{fmt(_tl)}", "renk": "#34D399"},
            {"label": "Gelen USD", "value": f"${fmt(_usd)}", "renk": "#60A5FA"},
            {"label": "Gelen EUR", "value": f"€{fmt(_eur)}", "renk": "#FBBF24"},
            {"label": "Kayıt Adedi", "value": f"{len(_f):,}", "renk": "#818CF8", "alt": "para girişi"},
        ])

        # ── Kimden ne kadar gelmiş (kaynak bazında özet) ──
        with st.expander("👥 Kimden ne kadar gelmiş (kaynak bazında toplam)", expanded=False):
            _ozet = (_f.groupby(["Kaynak (Kimden)", "Döviz"])["Tutar"]
                     .sum().reset_index().sort_values("Tutar", ascending=False))
            _ozet["Tutar"] = _ozet["Tutar"].map(lambda x: f"{x:,.2f}")
            st.dataframe(_ozet, hide_index=True, use_container_width=True,
                         height=min(60 + len(_ozet) * 35, 420))

        # ── Detay tablo ──
        _goster = _f.copy()
        _goster["Tutar"] = _goster.apply(
            lambda r: f"{r['Tutar']:,.2f} {r['Döviz']}", axis=1)
        _goster = _goster.drop(columns=["Döviz"])
        st.dataframe(_goster, hide_index=True, use_container_width=True,
                     height=min(60 + len(_goster) * 35, 560))
        st.caption(f"Toplam {len(_f)} para girişi kaydı. Yeni tahsilat için: "
                   "**Banka Bakiyeleri → 💰 Tahsilat Ekle**.")


    # ════════════════════════════════════════════════════════════════════
    # 8) VERİ YÜKLEME
    # ════════════════════════════════════════════════════════════════════
    elif sayfa == "📂 Veri Yükleme":
        st.markdown('<div class="baslik"><span class="baslik-ikon">📂</span>Veri Yükleme</div>', unsafe_allow_html=True)
    
        # Son yüklenenler (Recents)
        haftalar = get_tum_haftalar()
        if haftalar:
            st.markdown("### 🕐 Son Yüklenenler")
            aktif = get_aktif_hafta()
            aktif_id = aktif["id"] if aktif else None
    
            cols = st.columns(min(len(haftalar), 4))
            for i, h in enumerate(haftalar[:8]):
                ozet = get_hafta_ozet(h["id"])
                is_aktif = h["id"] == aktif_id
                with cols[i % 4]:
                    renk = "#0E1A3A" if is_aktif else "rgba(255,255,255,0.03)"
                    border = "2px solid #2563EB" if is_aktif else "1px solid rgba(255,255,255,0.06)"
                    aktif_badge = '<br><span style="background:#2563EB;color:white;font-size:11px;padding:0px 8px;border-radius:3px">AKTİF</span>' if is_aktif else ''
                    recent_html = (
                        f'<div style="background:{renk};border:{border};border-radius:10px;padding:12px 16px;margin-bottom:8px;min-height:100px">'
                        f'<div style="font-size:13px;font-weight:700;color:#E2E8F0;line-height:1.3">{h["hafta_adi"]}{aktif_badge}</div>'
                        f'<div style="font-size:11px;color:#9CA3AF;margin:4px 0">{ozet["odendi"]}/{ozet["toplam"]} ödendi</div>'
                        f'<div style="font-size:11px"><span style="color:#6EE7B7">₺{fmt(ozet["tl_toplam"])}</span></div>'
                        f'<div style="font-size:11px;color:#9CA3AF">{h["yuklendi_tarih"]}</div>'
                        '</div>'
                    )
                    st.markdown(recent_html, unsafe_allow_html=True)
                    if not is_aktif:
                        if st.button("Aç", key=f"recent_ac_{h['id']}", use_container_width=True):
                            hafta_aktif_yap(h["id"])
                            st.success(f"'{h['hafta_adi']}' aktif yapıldı.")
                            st.rerun()
    
            st.markdown("---")
    
        st.markdown("### 📤 Yeni Hafta Yükle")
        st.markdown(
            '<div style="background:#2D200A;border:1px solid #FDE68A;border-radius:8px;padding:12px 16px;margin-bottom:16px;font-size:13px;color:#FCD34D">'
            '<b>Excel sutun sirasi:</b> A=HAFTA | B=FIRMA | C=ACIKLAMA | D=(bos) | E=VADE | F=TUTAR TL | G=TUTAR USD | <b>H=KATEGORI (opsiyonel)</b>'
            '</div>',
            unsafe_allow_html=True
        )
    
        col1, col2 = st.columns(2)
    
        with col1:
            st.markdown("**1. Haftalık Ödeme Listesi (XLSX)**")
            odeme_file = st.file_uploader("Ödeme Listesi Excel", type=["xlsx", "xls"], key="odeme_upload", label_visibility="collapsed")
            if odeme_file:
                st.success(f"✅ {odeme_file.name} seçildi")
    
        with col2:
            st.markdown("**2. Firma Çekleri Dökümü (XLSX) — Opsiyonel**")
            cek_file = st.file_uploader("Çek Dökümü Excel", type=["xlsx", "xls"], key="cek_upload", label_visibility="collapsed")
            if cek_file:
                st.success(f"✅ {cek_file.name} seçildi")
    
        col_a, col_b = st.columns(2)
        with col_a:
            yukle_btn = st.button("✅ Verileri İşle ve Yükle", type="primary", use_container_width=True)
        with col_b:
            ornek = create_sample_excel()
            st.download_button(
                "📥 Örnek Excel İndir",
                data=ornek,
                file_name="ornek_odeme_listesi.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    
        if yukle_btn:
            if not odeme_file and not cek_file:
                st.error("Lütfen en az bir dosya seçin.")
            else:
                mesajlar = []
    
                if odeme_file:
                    try:
                        file_bytes = odeme_file.read()
                        hafta_adi, odemeler, hatalar = excel_yukle_odeme_listesi(file_bytes)
    
                        if hatalar:
                            for h in hatalar:
                                st.warning(h)
    
                        if odemeler:
                            hafta_id = hafta_ekle(hafta_adi or f"Hafta {len(get_tum_haftalar()) + 1}")
                            hafta_aktif_yap(hafta_id)
                            odeme_ekle_bulk(hafta_id, odemeler)
                            mesajlar.append(f"✅ {len(odemeler)} ödeme yüklendi — '{hafta_adi}'")
                        else:
                            mesajlar.append("⚠️ Ödeme listesinde işlenebilir veri bulunamadı.")
                    except Exception as e:
                        st.error(f"❌ Ödeme yükleme hatası: {e}")
    
                if cek_file:
                    try:
                        file_bytes = cek_file.read()
                        tl_cekler, usd_cekler, hatalar = excel_yukle_cek_listesi(file_bytes)
    
                        if hatalar:
                            for h in hatalar:
                                st.warning(h)
    
                        if tl_cekler or usd_cekler:
                            if tl_cekler:
                                cek_ekle_bulk(tl_cekler, "TL")
                            if usd_cekler:
                                cek_ekle_bulk(usd_cekler, "USD")
                            mesajlar.append(f"✅ Çekler yüklendi: TL {len(tl_cekler)} · USD {len(usd_cekler)}")
                        else:
                            mesajlar.append("⚠️ Çek dosyasında veri bulunamadı.")
                    except Exception as e:
                        st.error(f"❌ Çek yükleme hatası: {e}")
    
                for m in mesajlar:
                    st.success(m) if m.startswith("✅") else st.warning(m)
    
                if any(m.startswith("✅") for m in mesajlar):
                    st.balloons()
                    st.rerun()
    
    
    # ════════════════════════════════════════════════════════════════════
    # 9) RAPORLAR
    # ════════════════════════════════════════════════════════════════════
    elif sayfa == "📄 Raporlar & Bildirim":
        _tab_rapor, _tab_bildirim = st.tabs(["📄 Raporlar", "🔔 Bildirim Ayarları"])
        with _tab_rapor:
            st.markdown('<div class="baslik"><span class="baslik-ikon">📄</span>Raporlar</div>', unsafe_allow_html=True)
            st.markdown('<div class="alt-baslik">Excel ve PDF formatında haftalık raporlar</div>', unsafe_allow_html=True)
    
            kur      = get_kur()
            odemeler, hafta = get_aktif_odemeler()
            bankalar = get_bankalar()
    
            if not odemeler:
                st.info("Rapor oluşturmak için önce veri yükleyin.")
                st.stop()
    
            hafta_adi = hafta["hafta_adi"] if hafta else "Haftalık Rapor"
    
            st.markdown(f"**Aktif hafta:** `{hafta_adi}` — {len(odemeler)} ödeme")
            st.markdown("---")
    
            # ── TAB: Excel / HTML ──
            tab1, tab2, tab3 = st.tabs(["📊 Tam Excel Raporu", "🖨️ PDF / Yazdır", "💸 Nakit Akış Excel"])
    
            with tab1:
                st.markdown("**Özet + Günlük Detay + Kategori Analizi** üç sayfalı Excel dosyası.")
                st.markdown("")
    
                tl_top = sum(o.get("tutar_tl")  or 0 for o in odemeler)
                usd_top = sum(o.get("tutar_usd") or 0 for o in odemeler)
                odendi = sum(1 for o in odemeler if o.get("durum") == "odendi")
                metrik_satiri([
                    {"label": "Toplam TL", "value": f"₺{fmt(tl_top)}", "renk": "#818CF8"},
                    {"label": "Toplam USD", "value": f"${fmt(usd_top)}", "renk": "#34D399"},
                    {"label": "Ödendi", "value": f"{odendi}/{len(odemeler)}", "renk": "#FBBF24"},
                ])
    
                st.markdown("")
                try:
                    excel_buf = haftalik_excel_raporu(odemeler, hafta_adi, bankalar, kur)
                    st.download_button(
                        label="📥 Excel Raporu İndir",
                        data=excel_buf,
                        file_name=f"MuhasebeFin_{hafta_adi.replace(' ','_')}_{tr_today()}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"Excel oluşturulamadı: {e}")
    
            with tab2:
                st.markdown("Tarayıcınızda açılır — **Ctrl+P / Cmd+P** ile yazdırabilir ya da PDF olarak kaydedebilirsiniz.")
                st.markdown("")
    
                try:
                    html_bytes = haftalik_html_raporu(odemeler, hafta_adi, bankalar, kur)
                    st.download_button(
                        label="🖨️ HTML Rapor İndir (Yazdır/PDF)",
                        data=html_bytes,
                        file_name=f"MuhasebeFin_{hafta_adi.replace(' ','_')}_{tr_today()}.html",
                        mime="text/html",
                        type="primary",
                        use_container_width=True,
                    )
                    st.markdown("")
                    st.markdown(
                        '<div class="info-box">💡 <b>Nasıl PDF yapılır?</b><br>HTML dosyasını indirip tarayıcıda açın - Ctrl+P (veya Cmd+P) - "Hedef" olarak <b>PDF Olarak Kaydet</b> secin - Kaydet.</div>',
                        unsafe_allow_html=True
                    )
                except Exception as e:
                    st.error(f"HTML rapor oluşturulamadı: {e}")
    
                # Önizleme
                @st.dialog("👁️ Rapor Önizleme", width="large")
                def _dlg_rapor_onizleme():
                    try:
                        preview = haftalik_html_raporu(odemeler, hafta_adi, bankalar, kur)
                        st.components.v1.html(preview.decode("utf-8"), height=500, scrolling=True)
                    except Exception as e:
                        st.warning(f"Önizleme yüklenemedi: {e}")
                if st.button("👁️ Rapor Önizleme", key="btn_acc_rapor_on", use_container_width=True):
                    _dlg_rapor_onizleme()
    
            with tab3:
                st.markdown("Nakit akış tablosunu Excel dosyası olarak indirin.")
                st.markdown("")
                try:
                    nakit_buf = nakit_akis_excel(odemeler, bankalar, hafta_adi, kur)
                    st.download_button(
                        label="📥 Nakit Akış Excel İndir",
                        data=nakit_buf,
                        file_name=f"MuhasebeFin_NakitAkis_{tr_today()}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"Nakit akış raporu oluşturulamadı: {e}")
    
    
        # ════════════════════════════════════════════════════════════════════
        # 10) BİLDİRİM AYARLARI
        # ════════════════════════════════════════════════════════════════════
        with _tab_bildirim:
            st.markdown('<div class="baslik"><span class="baslik-ikon">🔔</span>Bildirim Ayarları</div>', unsafe_allow_html=True)
            st.markdown('<div class="alt-baslik">Vade yaklaşan ödemeler için email bildirimleri</div>', unsafe_allow_html=True)
    
            ayarlar  = get_bildirim_ayarlari()
            odemeler, hafta = get_aktif_odemeler()
            bankalar = get_bankalar()
    
            # Secrets konfigürasyonu
            @st.dialog("⚙️ SMTP Ayarları (Streamlit Secrets)", width="large")
            def _dlg_smtp_ayar():
                st.markdown(
                    "Email bildirimleri icin Streamlit Cloud > Settings > Secrets bolumune ekleyin:\n\n"
                    "```toml\n[bildirim]\nsmtp_host = \"smtp.gmail.com\"\nsmtp_port = 587\n"
                    "smtp_user = \"sizin@gmail.com\"\nsmtp_pass = \"uygulama-sifresi\"\n"
                    "alici_email = \"alici@firma.com\"\naktif = true\n```"
                )
                st.markdown(
                    '<div class="info-box">Gmail Uygulama Sifresi: Google Hesabim > Guvenlik > 2 Adimli Dogrulama > Uygulama Sifreleri > Yeni olustur > Posta secin > Kopyalayin.</div>',
                    unsafe_allow_html=True
                )
            if st.button("⚙️ SMTP Ayarları (Streamlit Secrets)", key="btn_acc_smtp", use_container_width=True):
                _dlg_smtp_ayar()
    
            # Mevcut ayar durumu
            st.markdown("---")
    
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Mevcut Konfigürasyon**")
                if ayarlar.get("smtp_user"):
                    st.markdown(f'<div class="ok-box">✅ SMTP: {ayarlar["smtp_host"]}:{ayarlar["smtp_port"]}<br>👤 Kullanıcı: {mask_email(ayarlar["smtp_user"])}<br>📧 Alıcı: {mask_email(ayarlar["alici_email"])}</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="uyari-box">⚠️ SMTP ayarları henüz yapılandırılmamış.<br>Secrets bölümünden ekleyin.</div>', unsafe_allow_html=True)
    
            with col2:
                st.markdown("**Bağlantı Testi**")
                if ayarlar.get("smtp_user"):
                    if st.button("🔌 Bağlantıyı Test Et", use_container_width=True):
                        with st.spinner("Test ediliyor..."):
                            basarili, mesaj = baglanti_test(ayarlar)
                        if basarili:
                            st.success(mesaj)
                        else:
                            st.error(mesaj)
                else:
                    st.info("Önce SMTP ayarlarını yapılandırın.")
    
            st.markdown("---")
            st.markdown("### 📨 Manuel Bildirim Gönder")
    
            if not ayarlar.get("smtp_user"):
                st.warning("Email göndermek için önce SMTP ayarlarını yapılandırın.")
            elif not odemeler:
                st.info("Göndermek için önce veri yükleyin.")
            else:
                hafta_adi = hafta["hafta_adi"] if hafta else "Bu Hafta"
    
                tab1, tab2 = st.tabs(["⚠️ Vade Uyarısı", "📊 Haftalık Özet"])
    
                with tab1:
                    konu, html_icerik = vade_bildirimi_olustur(odemeler, hafta_adi)
                    if not konu:
                        st.markdown('<div class="ok-box">✅ Bugün ve yarın vadeli bekleyen ödeme yok. Bildirim gönderilecek bir durum yok.</div>', unsafe_allow_html=True)
                    else:
                        bugun_cnt  = sum(1 for o in odemeler if o.get("durum") != "odendi" and (o.get("vade") or "")[:10] == tr_today_iso())
                        yarin_cnt  = sum(1 for o in odemeler if o.get("durum") != "odendi" and (o.get("vade") or "")[:10] == (tr_today() + timedelta(days=1)).isoformat())
                        gecmis_cnt = sum(1 for o in odemeler if o.get("durum") != "odendi" and (o.get("vade") or "")[:10] < tr_today_iso() and (o.get("vade") or "")[:10])
    
                        if gecmis_cnt:
                            st.markdown(f'<div class="alarm-box">🚨 {gecmis_cnt} gecikmiş ödeme!</div>', unsafe_allow_html=True)
                        if bugun_cnt:
                            st.markdown(f'<div class="uyari-box">⚠️ Bugün vadeli: {bugun_cnt} ödeme</div>', unsafe_allow_html=True)
                        if yarin_cnt:
                            st.markdown(f'<div class="info-box">📅 Yarın vadeli: {yarin_cnt} ödeme</div>', unsafe_allow_html=True)
    
                        st.markdown(f"**Konu:** `{konu}`")
                        st.markdown(f"**Alıcı:** `{mask_email(ayarlar['alici_email'])}`")
    
                        @st.dialog("👁️ Email Önizleme", width="large")
                        def _dlg_email_on_vade():
                            st.components.v1.html(html_icerik, height=400, scrolling=True)
                        if st.button("👁️ Email Önizleme", key="btn_acc_eml_vade", use_container_width=True):
                            _dlg_email_on_vade()
    
                        if st.button("📨 Vade Uyarısı Gönder", type="primary", use_container_width=True):
                            with st.spinner("Gönderiliyor..."):
                                basarili, mesaj = email_gonder(konu, html_icerik, ayarlar)
                            if basarili:
                                st.success(mesaj)
                            else:
                                st.error(mesaj)
    
                with tab2:
                    konu_ozet, html_ozet = ozet_bildirimi_olustur(odemeler, bankalar, hafta_adi)
                    st.markdown(f"**Konu:** `{konu_ozet}`")
                    st.markdown(f"**Alıcı:** `{mask_email(ayarlar['alici_email'])}`")
    
                    @st.dialog("👁️ Email Önizleme", width="large")
                    def _dlg_email_on_hafta():
                        st.components.v1.html(html_ozet, height=400, scrolling=True)
                    if st.button("👁️ Email Önizleme", key="btn_acc_eml_hft", use_container_width=True):
                        _dlg_email_on_hafta()
    
                    if st.button("📨 Haftalık Özet Gönder", type="primary", use_container_width=True):
                        with st.spinner("Gönderiliyor..."):
                            basarili, mesaj = email_gonder(konu_ozet, html_ozet, ayarlar)
                        if basarili:
                            st.success(mesaj)
                        else:
                            st.error(mesaj)
    
    
        # ════════════════════════════════════════════════════════════════════
        # 11) BANKALAR ARASI VİRMAN
        # ════════════════════════════════════════════════════════════════════
    elif sayfa == "⏳ Ertelenen Ödemeler":
        st.markdown('<div class="baslik"><span class="baslik-ikon">⏳</span>Ertelenen Ödemeler</div>', unsafe_allow_html=True)
        st.markdown('<div class="alt-baslik">Bu oturumda vadesi değiştirilmiş ödemeler</div>', unsafe_allow_html=True)
    
        # ─── Session state'ten ertelemeleri al ───
        ertelemeler_dict = st.session_state.get("ertelemeler", {})
    
        # Mevcut ödemelerle eşleştir (silinmiş veya ödenmiş olabilir)
        odemeler_aktif, _ = get_aktif_odemeler()
        odeme_lookup = {o["id"]: o for o in odemeler_aktif}
    
        # Ertelenenler listesini oluştur — güncel ödeme verisi ile birleştir
        ertelenenler = []
        for odeme_id, kayit in ertelemeler_dict.items():
            guncel = odeme_lookup.get(odeme_id)
            if guncel:
                # Mevcut ödeme bulundu — durum bilgisini al
                ertelenenler.append({
                    "id": odeme_id,
                    "firma": guncel.get("firma") or kayit.get("firma", ""),
                    "aciklama": guncel.get("aciklama") or kayit.get("aciklama", ""),
                    "kategori": guncel.get("kategori") or kayit.get("kategori") or "diger",
                    "tutar_tl": guncel.get("tutar_tl"),
                    "tutar_usd": guncel.get("tutar_usd"),
                    "vade": guncel.get("vade"),
                    "durum": guncel.get("durum", "bekliyor"),
                    "orijinal_vade": kayit.get("orijinal_vade"),
                    "ertelendi_sayisi": kayit.get("sayi", 1),
                    "son_erteleme_tarih": kayit.get("son_tarih"),
                })
    
        # Üstte temizleme butonu
        col_baslik, col_temizle = st.columns([5, 1])
        with col_temizle:
            if ertelenenler:
                if st.button("🗑️ Geçmişi Temizle", help="Erteleme kayıtlarını sıfırla", use_container_width=True):
                    st.session_state.ertelemeler = {}
                    st.success("Erteleme geçmişi temizlendi.")
                    st.rerun()
    
        # Bilgi notu
        st.markdown("""
        <div style="background:rgba(96,165,250,0.1);border:1px solid rgba(96,165,250,0.25);border-radius:8px;padding:8px 16px;margin:8px 0;font-size:11px;color:#BFDBFE">
            ℹ️ Erteleme kayıtları bu oturumda tutulur. Tarayıcıyı kapatınca veya çıkış yapınca geçmiş silinir.
            Kalıcı kayıt için Supabase'e 3 kolon eklenmesi gerekir (opsiyonel).
        </div>
        """, unsafe_allow_html=True)
    
        if not ertelenenler:
            st.info("📭 Henüz ertelenmiş ödeme yok.")
            st.markdown("""
            <div style="background:rgba(96,165,250,0.1);border:1px solid rgba(96,165,250,0.25);border-radius:10px;padding:16px 16px;margin-top:12px">
                <div style="font-size:13px;color:#93C5FD;font-weight:600;margin-bottom:8px">💡 Nasıl ertelerim?</div>
                <div style="font-size:13px;color:#BFDBFE;line-height:1.5">
                    <b>"Bu Hafta"</b> sayfasında bir ödemenin altındaki <b>"📅 Vadeyi Ötele"</b> kutucuğunu işaretle, yeni tarih seç, <b>💾 Ötele</b>'ye bas. Ya da hızlı butonlardan <b>+1, +3, +7, +30 gün</b> kullan. Sonra bu sayfaya geri dön.
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Özet metrikler — float dönüşümü güvenli
            def _f(v):
                try:
                    return float(v) if v else 0.0
                except (TypeError, ValueError):
                    return 0.0
            toplam_tl = sum(_f(o.get("tutar_tl")) for o in ertelenenler)
            toplam_usd = sum(_f(o.get("tutar_usd")) for o in ertelenenler)
            toplam_erteleme = sum(int(o.get("ertelendi_sayisi") or 0) for o in ertelenenler)
            bekleyen_cnt = sum(1 for o in ertelenenler if o["durum"] == "bekliyor")
    
            metrik_satiri([
                {"label": "Ertelenen Adet", "value": f"{len(ertelenenler):,}", "renk": "#FBBF24", "alt": f"{bekleyen_cnt} bekliyor"},
                {"label": "Toplam Erteleme", "value": f"{toplam_erteleme:,}", "renk": "#F87171", "alt": "kez ötelendi"},
                {"label": "Toplam TL", "value": f"₺{fmt(toplam_tl)}", "renk": "#60A5FA"},
                {"label": "Toplam USD", "value": f"${fmt(toplam_usd)}", "renk": "#A78BFA"},
            ])
    
            # Filtre
            col_f1, col_f2 = st.columns([3, 1])
            with col_f1:
                arama = st.text_input("🔍 Firma adı veya açıklama ara", key="ertelenen_arama")
            with col_f2:
                durum_filt = st.selectbox("Durum", ["Tümü", "Bekleyen", "Ödenen"], key="ertelenen_durum")
    
            filtrelenmis = ertelenenler
            if arama:
                a = arama.lower()
                filtrelenmis = [o for o in filtrelenmis if a in str(o.get("firma","")).lower() or a in str(o.get("aciklama","")).lower()]
            if durum_filt == "Bekleyen":
                filtrelenmis = [o for o in filtrelenmis if o["durum"] == "bekliyor"]
            elif durum_filt == "Ödenen":
                filtrelenmis = [o for o in filtrelenmis if o["durum"] == "odendi"]
    
            st.markdown(f"**{len(filtrelenmis)}** ödeme gösteriliyor")
            st.markdown("")
    
            # En çok ertelenenlere göre sırala
            filtrelenmis = sorted(filtrelenmis, key=lambda o: -(o.get("ertelendi_sayisi") or 0))
    
            for o in filtrelenmis:
                kat = o.get("kategori") or "diger"
                kat_info = KATEGORILER.get(kat, KATEGORILER["diger"])
                is_odendi = o["durum"] == "odendi"
    
                # Vade farkı hesapla
                try:
                    orjinal = pd.to_datetime(o.get("orijinal_vade")).date()
                    yeni = pd.to_datetime(o.get("vade")).date()
                    fark_gun = (yeni - orjinal).days
                    fark_str = f"+{fark_gun} gün ileri" if fark_gun > 0 else f"{fark_gun} gün"
                    orjinal_str = orjinal.strftime("%d.%m.%Y")
                    yeni_str = yeni.strftime("%d.%m.%Y")
                except Exception:
                    fark_str = "?"
                    orjinal_str = "?"
                    yeni_str = fmt_tarih(o.get("vade"))
    
                erteleme_sayisi = o.get("ertelendi_sayisi") or 1
                son_erteleme = o.get("son_erteleme_tarih") or ""
    
                tutar_str = ""
                if o.get("tutar_tl"):
                    tutar_str = f"<span style='color:#6EE7B7;font-weight:700;font-family:monospace'>₺{fmt(o['tutar_tl'])}</span>"
                elif o.get("tutar_usd"):
                    tutar_str = f"<span style='color:#93C5FD;font-weight:700;font-family:monospace'>${fmt(o['tutar_usd'])}</span>"
    
                durum_badge = (
                    '<span style="background:#0A2D15;color:#86EFAC;padding:0px 8px;border-radius:12px;font-size:11px;font-weight:700">✅ Ödendi</span>'
                    if is_odendi else
                    '<span style="background:#2D200A;color:#FDE68A;padding:0px 8px;border-radius:12px;font-size:11px;font-weight:700">⏳ Bekliyor</span>'
                )
    
                opacity = "0.5" if is_odendi else "1"
    
                st.markdown(f"""
                <div style="background:#131C35;border-left:4px solid {kat_info['renk']};border:1px solid rgba(255,255,255,0.12);border-radius:10px;padding:16px 16px;margin-bottom:8px;opacity:{opacity}">
                    <div style="display:grid;grid-template-columns:2.5fr 1.5fr 1.5fr 1fr 1fr;gap:16px;align-items:center">
                        <div>
                            <div style="font-size:15px;font-weight:700;color:#E2E8F0">{o['firma']}</div>
                            <div style="font-size:11px;color:#64748B;margin-top:0px">{o.get('aciklama') or ''}</div>
                            <span style="background:{kat_info['renk']};color:white;font-size:11px;padding:0px 8px;border-radius:8px;font-weight:600;margin-top:8px;display:inline-block">{kat_info['label']}</span>
                        </div>
                        <div>
                            <div style="font-size:11px;color:#94A3B8;font-weight:600;letter-spacing:.3px">ORİJİNAL VADE</div>
                            <div style="font-size:13px;color:#64748B;font-weight:600;text-decoration:line-through;font-family:monospace">{orjinal_str}</div>
                        </div>
                        <div>
                            <div style="font-size:11px;color:#94A3B8;font-weight:600;letter-spacing:.3px">YENİ VADE</div>
                            <div style="font-size:13px;color:#E2E8F0;font-weight:700;font-family:monospace">{yeni_str}</div>
                            <div style="font-size:11px;color:#DC2626;font-weight:600">{fark_str}</div>
                        </div>
                        <div style="text-align:center">
                            <div style="background:#2D0A0A;color:#FCA5A5;border-radius:8px;padding:8px 8px;font-size:19px;font-weight:700;font-family:monospace">{erteleme_sayisi}x</div>
                            <div style="font-size:11px;color:#94A3B8;margin-top:0px">erteleme</div>
                        </div>
                        <div style="text-align:right">
                            <div>{tutar_str}</div>
                            <div style="margin-top:8px">{durum_badge}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    
            # Kalıcı kayıt için bilgilendirme
            with st.expander("💡 Erteleme geçmişini kalıcı yapmak ister misiniz? (opsiyonel)"):
                st.markdown("""
                Bu sayfa şu an **oturum bazlı** çalışıyor — tarayıcıyı kapatınca erteleme geçmişi kaybolur.
    
                Kalıcı kayıt için Supabase SQL Editor'de bu komutları çalıştırın:
                """)
                st.code("""ALTER TABLE odemeler ADD COLUMN IF NOT EXISTS orijinal_vade DATE;
    ALTER TABLE odemeler ADD COLUMN IF NOT EXISTS ertelendi_sayisi INTEGER DEFAULT 0;
    ALTER TABLE odemeler ADD COLUMN IF NOT EXISTS son_erteleme_tarih DATE;""", language="sql")
                st.caption("Bu opsiyoneldir, mevcut özellik onsuz da çalışır.")
    
    
    # ════════════════════════════════════════════════════════════════════
    # 13) TOPLAM AKTİFLER
    # ════════════════════════════════════════════════════════════════════
    elif sayfa == "🧾 Cari Ekstre":
        from kayranacc.cari_ekstre import render as _cari_ekstre_render
        _cari_ekstre_render()

    elif sayfa == "💰 Toplam Aktifler":
        # ─── Yetki kontrolü: Sadece yetkili kullanıcılar erişebilir ───
        aktif_kul = st.session_state.get("aktif_kullanici", "").lower().strip()
        YETKILI_TOPLAM_AKTIFLER = {"ibrahim", "cem", "yilmaz", "derman", "pamuk"}
        if aktif_kul not in YETKILI_TOPLAM_AKTIFLER:
            st.error("🔒 Bu sayfaya erişim yetkiniz yok.")
            st.stop()
    
        st.markdown('<div class="baslik"><span class="baslik-ikon">💰</span>Toplam Aktifler</div>', unsafe_allow_html=True)
        st.markdown('<div class="alt-baslik">Stok + Yoldaki Mal + Banka + Alacaklar − Borçlar − Çekler (USD)</div>', unsafe_allow_html=True)
    
        kur = get_kur()
    
        # ─── Yardımcı: Excel parse fonksiyonları ───
        def parse_stok_excel(file_bytes):
            """
            Stok Excel'inden değerleri çıkar.
            ÖNEMLİ: Excel'in son satırlarında zaten toplam satırı var. Onu kullan.
            Yoksa elle topla ama "TOPLAM" satırlarını atla.
            """
            import pandas as pd
            from io import BytesIO
            df = pd.read_excel(BytesIO(file_bytes), header=None)
    
            # ─── Sütun 4 = USD SON DURUM STOK DEĞERİ ───
            # Önce alt taraftaki TOPLAM satırını bul (genelde son ~3 satırda)
            usd_stok = 0.0
            toplam_bulundu = False
            for i in range(len(df) - 1, max(2, len(df) - 10), -1):
                v = df.iloc[i, 4]
                if pd.notna(v):
                    try:
                        val = float(v)
                        # Toplam satırı genelde stok kodu boş ama büyük tutar var
                        stok_kodu = df.iloc[i, 0]
                        if pd.isna(stok_kodu) or str(stok_kodu).strip() == "" or "TOPLAM" in str(stok_kodu).upper():
                            usd_stok = val
                            toplam_bulundu = True
                            break
                    except (ValueError, TypeError):
                        continue
    
            # Toplam yoksa elle topla (header'ları atla, son toplam satırlarını da atla)
            if not toplam_bulundu:
                for i in range(2, len(df)):
                    stok_kodu = df.iloc[i, 0]
                    if pd.isna(stok_kodu) or str(stok_kodu).strip() == "":
                        continue  # boş satır = muhtemel toplam
                    if "TOPLAM" in str(stok_kodu).upper():
                        continue
                    v = df.iloc[i, 4]
                    if pd.notna(v):
                        try:
                            usd_stok += float(v)
                        except (ValueError, TypeError):
                            pass
    
            # ─── Pazaryeri firmaları: "TOPLAM TUTAR" sütunlarını bul ───
            # ÖNEMLİ: Excel'de her pazaryerinin altında bir ALT TOPLAM satırı var
            # (firma kodu boş, ama toplam değer dolu). Bunları atlamak için
            # firma kodu sütununu (col_idx - 3) kontrol ediyoruz.
            pazaryerleri = {}
            try:
                for col_idx in range(df.shape[1]):
                    header = df.iloc[1, col_idx]
                    if pd.notna(header) and isinstance(header, str) and "TOPLAM TUTAR" in header.upper():
                        # Firma adı için geriye doğru tara
                        firma_adi = "Bilinmeyen"
                        blacklist = ["STOK", "SATIŞ", "FIYAT", "FİYAT", "MIKT", "MİKT", "ADET", "İADE", "TOPLAM"]
                        firma_kod_col = None  # firma kodu sütunu (header'da firma adı olan)
                        for back in range(1, 5):
                            check_col = col_idx - back
                            if check_col < 0:
                                break
                            candidate = df.iloc[1, check_col]
                            if pd.notna(candidate) and isinstance(candidate, str):
                                cand_str = candidate.strip()
                                cand_upper = cand_str.upper()
                                if cand_str and not any(bl in cand_upper for bl in blacklist):
                                    firma_adi = cand_str
                                    firma_kod_col = check_col  # ← bu sütun firma stok kodu içerir
                                    break
    
                        # Toplama yaparken firma kodu sütunu BOŞ olan satırları atla (alt toplam = duplicate)
                        toplam = 0.0
                        for i in range(2, len(df)):
                            v = df.iloc[i, col_idx]
                            if pd.notna(v):
                                # Firma kodu sütunu kontrolü
                                if firma_kod_col is not None:
                                    kod = df.iloc[i, firma_kod_col]
                                    if pd.isna(kod) or str(kod).strip() == "":
                                        continue  # alt toplam satırı, atla
                                try:
                                    toplam += float(v)
                                except (ValueError, TypeError):
                                    pass
                        if firma_adi and firma_adi != "Bilinmeyen":
                            pazaryerleri[firma_adi] = toplam
            except Exception:
                pass
    
            return usd_stok, pazaryerleri
    
        def parse_ithalat_excel(file_bytes):
            """
            İthalat Excel'inden 'Ödenen / USD' toplamını al.
            Sütun yapısı:
            0=Durum, 1=Üretici, 2=PI No, 3=Ürünler, 4=Tahmini Varış, 5=Invoice/USD,
            6=ÖDENEN/USD ← BU, 7=Kalan/USD, 8=Vergi/TL, 9=Vergi/USD, ...
            """
            import pandas as pd
            from io import BytesIO
            df = pd.read_excel(BytesIO(file_bytes), header=None)
    
            # TOPLAM satırını bul (sütun 0'da "TOPLAM" yazar)
            for i in range(len(df)):
                ilk = df.iloc[i, 0]
                if pd.notna(ilk) and "TOPLAM" in str(ilk).upper():
                    v = df.iloc[i, 6]  # ÖDENEN sütunu = 6
                    if pd.notna(v):
                        try:
                            return float(v)
                        except (ValueError, TypeError):
                            pass
    
            # TOPLAM yoksa elle topla (header satırları 0,1,2'yi atla)
            odenen = 0.0
            for i in range(3, len(df)):
                v = df.iloc[i, 6]
                if pd.notna(v):
                    try:
                        odenen += float(v)
                    except (ValueError, TypeError):
                        pass
            return odenen
    
        def _cari_isimleri_cikar(file_bytes):
            """Cari Excel'inden Hesap adı (sütun 2) listesini çıkarır — Satış kanalları için."""
            import pandas as pd
            from io import BytesIO
            try:
                df = pd.read_excel(BytesIO(file_bytes), header=None)
            except Exception:
                return []
            isimler = []
            for i in range(1, len(df)):
                ad = df.iloc[i, 2] if df.shape[1] > 2 else None
                if pd.notna(ad):
                    s = str(ad).strip()
                    if s and s.lower() != "nan" and s not in isimler:
                        isimler.append(s)
            return isimler

        def parse_cari_excel(file_bytes):
            """
            Cari Excel'inden BORÇ ve ALACAK kalemlerini çıkarır.
            Sütun yapısı: 0=Tip, 1=Kod, 2=Hesap adı, 3=Döviz, 4=Borç, 5=Alacak, 6=Bakiye
            - Negatif bakiye = SEN borçlusun (BORÇ)
            - Pozitif bakiye = SANA borçlu (ALACAK)
            Returns: dict{'borc': {usd, tl, eur}, 'alacak': {usd, tl, eur}}
            """
            import pandas as pd
            from io import BytesIO
            df = pd.read_excel(BytesIO(file_bytes), header=None)
    
            sonuc = {
                "borc": {"usd": 0.0, "tl": 0.0, "eur": 0.0},
                "alacak": {"usd": 0.0, "tl": 0.0, "eur": 0.0},
            }
            for i in range(1, len(df)):
                tip = df.iloc[i, 0]
                doviz = df.iloc[i, 3]
                bakiye = df.iloc[i, 6]
                if pd.notna(tip) and pd.notna(bakiye) and pd.notna(doviz):
                    try:
                        bakiye_val = float(bakiye)
                        if bakiye_val == 0:
                            continue
                        yon = "borc" if bakiye_val < 0 else "alacak"
                        d = str(doviz).strip().upper()
                        if d == "USD":
                            sonuc[yon]["usd"] += abs(bakiye_val)
                        elif d == "TL":
                            sonuc[yon]["tl"] += abs(bakiye_val)
                        elif d == "EUR":
                            sonuc[yon]["eur"] += abs(bakiye_val)
                    except (ValueError, TypeError):
                        pass
            return sonuc
    
        # ─── Session state init + Supabase'den önceki kayıtları yükle ───
        # NOT: Toplam Aktifler verileri paylaşımlıdır — yetki verilen tüm kullanıcılar (ibrahim, cem) aynı veriyi görür.
        # Bu yüzden kayıtlar sabit "ortak" anahtarıyla saklanır.
        gercek_kullanici = (st.session_state.get("aktif_kullanici") or "ibrahim").lower().strip()
        aktif_kul = "ortak"  # Paylaşımlı veri anahtarı
    
        # Paylaşımlı veri HER render'da DB'den okunur — böylece başka bir kullanıcı
        # (pamuk vb.) yüklediğinde diğer oturumlar da anında en güncel veriyi görür.
        # (Tek seferlik session cache KULLANILMAZ; aksi halde başkasının yüklemesi yansımaz.)
        if True:
            # İlk açılış — Supabase'den önceki kayıtları çek (tablo yoksa None döner, sorun değil)
            # MIGRATION: "ortak" boşsa "ibrahim"den oku ve "ortak"a kopyala (eski veriler için)
            try:
                stok_v = aktif_excel_oku(aktif_kul, "stok")
                if stok_v is None:
                    # Eski "ibrahim" kayıtlarını ara
                    eski = aktif_excel_oku("ibrahim", "stok")
                    if eski is not None:
                        aktif_excel_kaydet(aktif_kul, "stok", eski)
                        stok_v = eski
                st.session_state.aktif_stok_data = stok_v
            except Exception:
                st.session_state.aktif_stok_data = None
            try:
                ith_v = aktif_excel_oku(aktif_kul, "ithalat")
                if ith_v is None:
                    eski = aktif_excel_oku("ibrahim", "ithalat")
                    if eski is not None:
                        aktif_excel_kaydet(aktif_kul, "ithalat", eski)
                        ith_v = eski
                st.session_state.aktif_ithalat_data = ith_v
            except Exception:
                st.session_state.aktif_ithalat_data = None
            try:
                cari_v = aktif_excel_oku(aktif_kul, "cari")
                if cari_v is None:
                    eski = aktif_excel_oku("ibrahim", "cari")
                    if eski is not None:
                        aktif_excel_kaydet(aktif_kul, "cari", eski)
                        cari_v = eski
                st.session_state.aktif_cari_data = cari_v
            except Exception:
                st.session_state.aktif_cari_data = None
    
            # JSON list olarak gelirse tuple'a çevir (parser tuple bekler)
            try:
                if isinstance(st.session_state.aktif_stok_data, list) and len(st.session_state.aktif_stok_data) == 2:
                    usd_stok_v, pazar_dict = st.session_state.aktif_stok_data
                    if not isinstance(pazar_dict, dict):
                        pazar_dict = {}
                    st.session_state.aktif_stok_data = (float(usd_stok_v or 0), pazar_dict)
            except Exception:
                st.session_state.aktif_stok_data = None
            try:
                if isinstance(st.session_state.aktif_cari_data, list) and len(st.session_state.aktif_cari_data) == 3:
                    st.session_state.aktif_cari_data = tuple(float(x or 0) for x in st.session_state.aktif_cari_data)
            except Exception:
                st.session_state.aktif_cari_data = None
            st.session_state.aktif_excel_yuklendi = True
    
        # ─── Excel yükleme bölümü — kompakt: durum kartları + pencereden yükleme ───
    
        st.markdown(
            '<style>'
            '[data-testid="stFileUploaderDropzone"]{padding:10px 16px !important;min-height:0 !important;}'
            '[data-testid="stFileUploaderDropzone"] button{padding:5px 16px !important;}'
            '[data-testid="stFileUploaderDropzoneInstructions"] span{font-size:11px !important;}'
            '[data-testid="stFileUploaderDropzoneInstructions"] small{font-size:11px !important;}'
            '</style>',
            unsafe_allow_html=True
        )

        col1, col2, col3 = st.columns(3)
    
        # Meta bilgileri al
        stok_meta = None
        ithalat_meta = None
        cari_meta = None
        try:
            stok_meta = aktif_excel_meta_oku("stok")
            ithalat_meta = aktif_excel_meta_oku("ithalat")
            cari_meta = aktif_excel_meta_oku("cari")
        except Exception:
            pass
    
        def _meta_str(meta):
            """Meta bilgiyi kısa string'e çevir."""
            if not meta:
                return ""
            kim = (meta.get("son_yukleyen") or "?").capitalize()
            zaman = (meta.get("yukleme_zamani") or "")[:16]
            return f"👤 {kim} · 🕐 {zaman}"
    
        with col1:
            st.markdown("**1️⃣ Stok Değeri Raporu**")
            if st.session_state.aktif_stok_data:
                try:
                    usd_v, pzr = st.session_state.aktif_stok_data
                    metrik_satiri([{"label": "✅ Yüklendi", "value": f"${float(usd_v):,.0f}",
                                    "renk": "#34D399", "alt": _meta_str(stok_meta)}])
                except Exception:
                    st.session_state.aktif_stok_data = None
    
        with col2:
            st.markdown("**2️⃣ İthalat Ödeme Takip**")
            if st.session_state.aktif_ithalat_data:
                try:
                    metrik_satiri([{"label": "✅ Yüklendi", "value": f"${float(st.session_state.aktif_ithalat_data):,.0f}",
                                    "renk": "#34D399", "alt": _meta_str(ithalat_meta)}])
                except Exception:
                    st.session_state.aktif_ithalat_data = None
    
        with col3:
            st.markdown("**3️⃣ Cari Alacaklar Listesi**")
            if st.session_state.aktif_cari_data:
                try:
                    cari = st.session_state.aktif_cari_data
                    if isinstance(cari, dict) and "borc" in cari:
                        _b = cari.get("borc", {}) or {}
                        _a = cari.get("alacak", {}) or {}

                        def _usd_kar(d):
                            return (float(d.get("usd") or 0)
                                    + (float(d.get("tl") or 0) / kur if kur > 0 else 0)
                                    + float(d.get("eur") or 0) * 1.10)
                        b_tot = _usd_kar(_b)
                        a_tot = _usd_kar(_a)
                        metrik_satiri([
                            {"label": "Borç", "value": f"${b_tot:,.0f}", "renk": "#F87171",
                             "alt": f"USD {float(_b.get('usd') or 0):,.0f} · TL {float(_b.get('tl') or 0):,.0f} · EUR {float(_b.get('eur') or 0):,.0f}"},
                            {"label": "Alacak", "value": f"${a_tot:,.0f}", "renk": "#34D399",
                             "alt": f"USD {float(_a.get('usd') or 0):,.0f} · TL {float(_a.get('tl') or 0):,.0f} · EUR {float(_a.get('eur') or 0):,.0f}"},
                        ])
                    elif isinstance(cari, (tuple, list)) and len(cari) == 3:
                        metrik_satiri([{"label": "✅ Yüklendi (eski format)", "value": f"${float(cari[0]):,.0f}",
                                        "renk": "#34D399", "alt": "USD borç"}])
                    else:
                        st.session_state.aktif_cari_data = None
                    if cari_meta:
                        st.caption(_meta_str(cari_meta))
                except Exception:
                    st.session_state.aktif_cari_data = None
    

        @st.dialog("📤 Excel Dosyalarını Yükle", width="large")
        def _dlg_aktif_excel():
            st.caption("Stok Değeri · İthalat Ödeme Takip · Cari Alacaklar — yükleme bitince pencere kapanır, kartlar güncellenir.")
            st.markdown("**1️⃣ Stok Değeri Raporu**")
            stok_file = st.file_uploader("Stok Excel", type=["xls", "xlsx"], key="aktif_stok_upload", label_visibility="collapsed")
            if stok_file is not None:
                _fid = f"{stok_file.name}:{getattr(stok_file, 'size', 0)}"
                if st.session_state.get("_stok_islenen_fid") != _fid:
                    st.session_state["_stok_islenen_fid"] = _fid
                    try:
                        with st.spinner("📦 Stok Excel'i işleniyor…"):
                            parsed = parse_stok_excel(stok_file.read())
                        st.session_state.aktif_stok_data = parsed
                        # Supabase'e kaydet (tablo yoksa hata vermeden geç)
                        try:
                            usd_stok_v, pazar_dict = parsed
                            aktif_excel_kaydet(aktif_kul, "stok", [float(usd_stok_v), pazar_dict])
                        except Exception:
                            pass
                        st.success(f"✅ {stok_file.name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Hata: {type(e).__name__}: {e}")
            st.markdown("**2️⃣ İthalat Ödeme Takip**")
            ithalat_file = st.file_uploader("İthalat Excel", type=["xls", "xlsx"], key="aktif_ithalat_upload", label_visibility="collapsed")
            if ithalat_file is not None:
                _fid = f"{ithalat_file.name}:{getattr(ithalat_file, 'size', 0)}"
                if st.session_state.get("_ithalat_islenen_fid") != _fid:
                    st.session_state["_ithalat_islenen_fid"] = _fid
                    try:
                        with st.spinner("🚢 İthalat Excel'i işleniyor…"):
                            parsed = parse_ithalat_excel(ithalat_file.read())
                        st.session_state.aktif_ithalat_data = parsed
                        try:
                            aktif_excel_kaydet(aktif_kul, "ithalat", float(parsed))
                        except Exception:
                            pass
                        st.success(f"✅ {ithalat_file.name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Hata: {type(e).__name__}: {e}")
            st.markdown("**3️⃣ Cari Alacaklar Listesi**")
            cari_file = st.file_uploader("Cari Excel", type=["xls", "xlsx"], key="aktif_cari_upload", label_visibility="collapsed")
            if cari_file is not None:
                _fid = f"{cari_file.name}:{getattr(cari_file, 'size', 0)}"
                if st.session_state.get("_cari_islenen_fid") != _fid:
                    st.session_state["_cari_islenen_fid"] = _fid
                    try:
                        with st.spinner("🧾 Cari Excel'i işleniyor…"):
                            _cari_bytes = cari_file.read()
                            parsed = parse_cari_excel(_cari_bytes)
                        st.session_state.aktif_cari_data = parsed
                        try:
                            aktif_excel_kaydet(aktif_kul, "cari", parsed)
                            _isimler = _cari_isimleri_cikar(_cari_bytes)
                            if _isimler:
                                aktif_excel_kaydet(aktif_kul, "cari_isimler", _isimler)
                        except Exception:
                            pass
                        st.success(f"✅ {cari_file.name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Hata: {type(e).__name__}: {e}")
        if st.button("📤 Excel Dosyalarını Yükle / Güncelle", key="btn_aktif_excel", use_container_width=True):
            _dlg_aktif_excel()

        st.markdown("---")
    
        # ─── Hesaplama ───
        bankalar = get_bankalar()
        banka_tl = sum(float(b["bakiye"]) for b in bankalar if b["para_birimi"] == "TL")
        banka_usd = sum(float(b["bakiye"]) for b in bankalar if b["para_birimi"] == "USD")
        banka_usd_eqv = banka_usd + (banka_tl / kur if kur > 0 else 0)
    
        # Stok kalemleri
        usd_stok, pazaryerleri = 0.0, {}
        try:
            if st.session_state.aktif_stok_data:
                data = st.session_state.aktif_stok_data
                if isinstance(data, (tuple, list)) and len(data) == 2:
                    usd_stok = float(data[0] or 0)
                    pazaryerleri = data[1] if isinstance(data[1], dict) else {}
        except Exception:
            usd_stok, pazaryerleri = 0.0, {}
    
        # %20 KDV dahil stok (formül: değer × 1.20)
        stok_marjli = usd_stok * 1.20 if usd_stok else 0
    
        # İthalat
        try:
            odenen_ithalat = float(st.session_state.aktif_ithalat_data or 0)
        except (TypeError, ValueError):
            odenen_ithalat = 0.0
    
        # Cari Borçlar ve Alacaklar
        usd_borc = tl_borc = eur_borc = 0.0
        usd_alacak = tl_alacak = eur_alacak = 0.0
        try:
            if st.session_state.aktif_cari_data:
                cari = st.session_state.aktif_cari_data
                # Yeni format: dict{'borc': {...}, 'alacak': {...}}
                if isinstance(cari, dict) and "borc" in cari:
                    b = cari.get("borc") or {}
                    a = cari.get("alacak") or {}
                    usd_borc = float(b.get("usd") or 0)
                    tl_borc = float(b.get("tl") or 0)
                    eur_borc = float(b.get("eur") or 0)
                    usd_alacak = float(a.get("usd") or 0)
                    tl_alacak = float(a.get("tl") or 0)
                    eur_alacak = float(a.get("eur") or 0)
                # Eski format: tuple/list (sadece borçlar) - geriye dönük uyumluluk
                elif isinstance(cari, (tuple, list)) and len(cari) == 3:
                    usd_borc = float(cari[0] or 0)
                    tl_borc = float(cari[1] or 0)
                    eur_borc = float(cari[2] or 0)
        except Exception:
            usd_borc = tl_borc = eur_borc = 0.0
            usd_alacak = tl_alacak = eur_alacak = 0.0
    
        tl_borc_usd = tl_borc / kur if kur > 0 else 0
        eur_borc_usd = eur_borc * 1.10 if eur_borc > 0 else 0
        tl_alacak_usd = tl_alacak / kur if kur > 0 else 0
        eur_alacak_usd = eur_alacak * 1.10 if eur_alacak > 0 else 0
        toplam_alacak_usd = usd_alacak + tl_alacak_usd + eur_alacak_usd
    
        # ─── Çekler (Sistemden) ───
        cek_tl, cek_usd, cek_adet_tl, cek_adet_usd = get_cek_toplamlari()
        cek_tl_usd_eqv = cek_tl / kur if kur > 0 else 0
        cek_toplam_usd = cek_tl_usd_eqv + cek_usd
    
        # ─── Manuel Kalemler (Supabase + session_state fallback) ───
        # Önce Supabase'den dene, başarısızsa session_state kullan
        if "manuel_kalemler_local" not in st.session_state:
            st.session_state.manuel_kalemler_local = []
    
        manuel_kalemler_db = []
        try:
            manuel_kalemler_db = aktif_manuel_listele(aktif_kul) or []
            # MIGRATION: "ortak"ta yoksa "ibrahim"den çek ve kopyala
            if not manuel_kalemler_db:
                eski_kalemler = aktif_manuel_listele("ibrahim") or []
                for kalem in eski_kalemler:
                    try:
                        aktif_manuel_ekle(
                            aktif_kul,
                            kalem.get("aciklama", ""),
                            float(kalem.get("tutar") or 0),
                            kalem.get("para_birimi") or "USD",
                            kalem.get("tip") or "ekle"
                        )
                    except Exception:
                        pass
                # Migration sonrası tekrar oku
                if eski_kalemler:
                    manuel_kalemler_db = aktif_manuel_listele(aktif_kul) or []
        except Exception:
            manuel_kalemler_db = []
    
        # Eğer Supabase'den veri geldiyse onu kullan, yoksa session'dan
        if manuel_kalemler_db:
            manuel_kalemler = manuel_kalemler_db
        else:
            manuel_kalemler = st.session_state.manuel_kalemler_local
    
        manuel_ekle_toplam = 0.0
        manuel_cikar_toplam = 0.0
        for k in manuel_kalemler:
            try:
                tutar = float(k.get("tutar") or 0)
                pb = (k.get("para_birimi") or "USD").upper()
                tutar_usd = tutar if pb == "USD" else (tutar / kur if kur > 0 else 0)
                if k.get("tip") == "ekle":
                    manuel_ekle_toplam += tutar_usd
                else:
                    manuel_cikar_toplam += tutar_usd
            except (TypeError, ValueError):
                pass
    
        # ─── EERA HAVUZ BÜTÇE (Ürün Yönetimi → Ref No Takibi) ───
        try:
            from kayranpm.ref_no import (get_firmalar as _rf_firmalar,
                                         get_butce as _rf_butce, _f as _rf_f)
            havuz_butce_usd = 0.0
            for _hf in (_rf_firmalar() or []):
                _hk = _rf_butce(_hf["id"]) or []
                _hg = sum(_rf_f(x.get("tutar")) for x in _hk if x.get("yon") == "giris")
                _hh = sum(_rf_f(x.get("tutar")) for x in _hk if x.get("yon") != "giris")
                havuz_butce_usd += (_hg - _hh)
        except Exception:
            havuz_butce_usd = 0.0

        # TOPLAM AKTİFLER
        toplam_aktif = (
            stok_marjli
            + odenen_ithalat
            + banka_usd_eqv
            + toplam_alacak_usd
            + manuel_ekle_toplam
            + havuz_butce_usd
            - usd_borc
            - tl_borc_usd
            - eur_borc_usd
            - cek_toplam_usd
            - manuel_cikar_toplam
        )
    
        # ─── Sonuç kaydı (gösterim Yönetim panosunda) ───
        # NOT: Toplam aktif sonucu burada GÖSTERİLMEZ; sadece kaydedilir ve
        # yalnızca Yönetim Panosu (P&L) navigasyonunda görüntülenir.
        _snap_ok = False
        _snap_hata = ""
        try:
            import datetime as _dt_acc
            _snap_ok = set_ayar("toplam_aktif_snapshot", {
                "toplam": round(toplam_aktif, 2),
                "kur": kur,
                "tarih": str(_dt_acc.date.today()),
                "stok": round(stok_marjli, 2),
                "ithalat": round(odenen_ithalat, 2),
                "banka": round(banka_usd_eqv, 2),
                "alacak": round(toplam_alacak_usd, 2),
                "borc": round(usd_borc + tl_borc_usd + eur_borc_usd, 2),
                "cek": round(cek_toplam_usd, 2),
                "manuel_ekle": round(manuel_ekle_toplam, 2),
                "manuel_cikar": round(manuel_cikar_toplam, 2),
                "havuz": round(havuz_butce_usd, 2),
            })
        except Exception as _e:
            _snap_ok = False
            _snap_hata = str(_e)[:200]
        if _snap_ok:
            st.success("✅ Veriler işlendi ve kaydedildi. Yönetim Panosu'na da yansıdı.")
            # ── 💎 Genel toplam BURADA da göster (Yönetim Panosu'na gitmeye gerek yok) ──
            st.markdown(
                f'<div style="background:linear-gradient(135deg,#93C5FD,#3730A3,#7C3AED);border-radius:16px;'
                f'padding:24px 24px;text-align:center;margin:8px 0 8px;box-shadow:0 10px 28px rgba(30,64,175,0.28)">'
                f'<div style="font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#C7D2FE;margin-bottom:8px">💎 TOPLAM AKTİFLER (GENEL TOPLAM)</div>'
                f'<div style="font-size:23px;font-weight:800;color:#FFFFFF;font-family:JetBrains Mono,monospace;letter-spacing:-1px;line-height:1.1">${toplam_aktif:,.0f}</div>'
                f'<div style="font-size:13px;color:#A5B4FC;margin-top:8px;font-family:JetBrains Mono,monospace">≈ ₺{(toplam_aktif*kur):,.0f} (kur: {kur:g})</div>'
                f'</div>', unsafe_allow_html=True)
            # Kısa hesap dökümü
            _dk = [
                ("📦 Stok (×1.20)", stok_marjli, "+"), ("🚢 İthalat (ödenen)", odenen_ithalat, "+"),
                ("🏦 Banka (USD)", banka_usd_eqv, "+"), ("📥 Cari alacak", toplam_alacak_usd, "+"),
                ("💰 Havuz bütçe", havuz_butce_usd, "+"), ("➕ Manuel ekleme", manuel_ekle_toplam, "+"),
                ("📤 Cari borç", usd_borc + tl_borc_usd + eur_borc_usd, "−"),
                ("🧾 Çekler", cek_toplam_usd, "−"), ("➖ Manuel çıkarma", manuel_cikar_toplam, "−"),
            ]
            _chips = "".join(
                f'<span style="display:inline-flex;gap:4px;align-items:center;background:rgba(255,255,255,0.04);'
                f'border:1px solid rgba(148,163,184,0.18);border-radius:8px;padding:4px 8px;font-size:13px;margin:4px 4px 4px 0">'
                f'<span style="color:{"#34D399" if y=="+" else "#F87171"}">{y}</span>'
                f'<span style="color:#94A3B8">{k}</span>'
                f'<b style="color:#E2E8F0;font-family:monospace">${float(v or 0):,.0f}</b></span>'
                for k, v, y in _dk if float(v or 0))
            st.markdown(f'<div style="display:flex;flex-wrap:wrap;margin-bottom:8px">{_chips}</div>',
                        unsafe_allow_html=True)
        else:
            _h = st.session_state.get("_son_ayar_hata", "") or _snap_hata
            st.error("⚠️ Veriler işlendi ama sonuç **kaydedilemedi** — bu yüzden Yönetim Panosu'na yansımıyor. "
                     "Genellikle `sistem_ayarlari` tablosu eksik/yanlış olduğunda olur.")
            if _h:
                st.code(_h, language="text")
                st.caption("☝️ Bu hata mesajını yöneticine ilet — kesin çözüm için bu lazım.")

        # ─── Manuel Ekleme/Çıkarma ───
        st.markdown("---")
        st.markdown("### ✏️ Manuel Ekleme / Çıkarma")
        st.caption("Excel'lerde olmayan ek kalemler için manuel giriş yap. Kayıtlar kalıcıdır.")
    
        @st.dialog("➕ Yeni Kalem Ekle", width="large")
        def _dlg_yeni_kalem():
            col_t, col_a, col_tu, col_pb, col_b = st.columns([1, 3, 1.5, 1, 1])
            with col_t:
                yeni_tip = st.selectbox("Tip", ["ekle", "cikar"],
                                         format_func=lambda x: "➕ Ekle" if x == "ekle" else "➖ Çıkar",
                                         key="manuel_tip")
            with col_a:
                yeni_aciklama = st.text_input("Açıklama", key="manuel_aciklama",
                                               placeholder="Örn: Kasa nakit, Yatırım fonu, Henüz fatura kesilmemiş alacak")
            with col_tu:
                yeni_tutar = st.number_input("Tutar", min_value=0.0, step=0.01, format="%.2f", key="manuel_tutar")
            with col_pb:
                yeni_pb = st.selectbox("PB", ["USD", "TL"], key="manuel_pb")
            with col_b:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("💾 Ekle", type="primary", use_container_width=True, key="manuel_kaydet"):
                    if not yeni_aciklama.strip():
                        st.error("Açıklama boş olamaz")
                    elif yeni_tutar <= 0:
                        st.error("Tutar 0'dan büyük olmalı")
                    else:
                        # Önce Supabase'e kaydetmeyi dene
                        supabase_basarili = False
                        try:
                            supabase_basarili = aktif_manuel_ekle(aktif_kul, yeni_aciklama.strip(), yeni_tutar, yeni_pb, yeni_tip)
                        except Exception:
                            supabase_basarili = False
    
                        # Supabase başarısızsa session_state'e ekle (fallback)
                        if not supabase_basarili:
                            import time as _time
                            st.session_state.manuel_kalemler_local.append({
                                "id": f"local_{int(_time.time() * 1000)}",
                                "kullanici": aktif_kul,
                                "aciklama": yeni_aciklama.strip(),
                                "tutar": float(yeni_tutar),
                                "para_birimi": yeni_pb,
                                "tip": yeni_tip,
                                "olusturuldu": str(tr_today()),
                            })
                            st.warning("⚠️ Supabase'e kaydedilemedi (tablo yok), oturum belleğine kaydedildi.")
                        else:
                            st.success("✅ Kalem eklendi (kalıcı)")
                        st.rerun()
        if st.button("➕ Yeni Kalem Ekle", key="btn_acc_kalem", use_container_width=True):
            _dlg_yeni_kalem()
    
        # Mevcut kalemleri listele
        if manuel_kalemler:
            st.markdown(f"**📋 Kayıtlı Kalemler ({len(manuel_kalemler)})**")
            for k in manuel_kalemler:
                tip = k.get("tip", "ekle")
                renk = "#16A34A" if tip == "ekle" else "#DC2626"
                isaret = "+" if tip == "ekle" else "-"
                sembol = "$" if (k.get("para_birimi") or "USD").upper() == "USD" else "₺"
                tutar_v = float(k.get("tutar") or 0)
                col_a, col_b = st.columns([10, 1])
                with col_a:
                    st.markdown(
                        f'<div style="background:#131C35;border:1px solid rgba(255,255,255,0.12);border-left:3px solid {renk};border-radius:8px;padding:8px 16px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center">'
                        f'<div><b style="color:#E2E8F0;font-size:13px">{k.get("aciklama","")}</b><div style="font-size:11px;color:#94A3B8">📅 {(k.get("olusturuldu") or "")[:10]}</div></div>'
                        f'<div style="color:{renk};font-weight:700;font-family:monospace;font-size:15px">{isaret}{sembol}{tutar_v:,.2f}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                with col_b:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🗑️", key=f"manuel_sil_{k['id']}", help="Sil"):
                        kalem_id = k['id']
                        # Local kalem ise (id "local_" ile başlar) session'dan sil
                        if isinstance(kalem_id, str) and kalem_id.startswith("local_"):
                            st.session_state.manuel_kalemler_local = [
                                kk for kk in st.session_state.manuel_kalemler_local
                                if kk.get("id") != kalem_id
                            ]
                        else:
                            try:
                                aktif_manuel_sil(kalem_id)
                            except Exception:
                                pass
                        st.rerun()
    
        # ─── Eksik dosya uyarıları ───
        st.markdown("---")
        eksikler = []
        if not st.session_state.aktif_stok_data:
            eksikler.append("📦 Stok Değeri Raporu yüklenmedi")
        if not st.session_state.aktif_ithalat_data:
            eksikler.append("🚢 İthalat Ödeme Takip yüklenmedi")
        if not st.session_state.aktif_cari_data:
            eksikler.append("⚠️ Cari Alacaklar Listesi yüklenmedi")
        if eksikler:
            st.warning("📭 Eksik dosyalar (sıfır olarak hesaplandı):\n\n" + "\n".join(f"- {e}" for e in eksikler))
    
        # ─── Temizleme ───
        @st.dialog("🗑️ Yüklenen verileri temizle", width="large")
        def _dlg_veri_temizle():
            st.warning("⚠️ Bu işlem **kalıcı kayıtları da siler**. Yeniden Excel yüklemeniz gerekir.")
            if st.button("Tüm Excel verilerini sıfırla", type="secondary"):
                st.session_state.aktif_stok_data = None
                st.session_state.aktif_ithalat_data = None
                st.session_state.aktif_cari_data = None
                aktif_excel_sil(aktif_kul)  # Supabase'ten de sil
                st.success("Temizlendi.")
                st.rerun()
        if st.button("🗑️ Yüklenen verileri temizle", key="btn_acc_temizle", use_container_width=True):
            _dlg_veri_temizle()
    
        # ─── Formül açıklaması ───
        with st.popover("📐 Hesaplama Formülü"):
            st.markdown(f"""
            **Toplam Aktifler (USD) =**
    
            - **G5F Stok Değeri × 1.20** — Stok Excel'inden USD STOK DEĞERİ toplamı (%20 KDV dahil)
            - **+ İthalat Ödenmiş Tutar** — İthalat Excel "Ödenen / USD" toplamı
            - **+ Banka Hesapları USD eşdeğeri** — Uygulamadaki TL hesapları kur ile USD'ye çevrilir
            - **+ Cari Alacaklar** — Cari Excel'inden POZİTİF bakiyeler (size borçlular)
            - **+ Manuel Eklemeler** — Kullanıcının elle eklediği kalemler
            - **− Cari Borçlar** — Cari Excel'inden NEGATİF bakiyeler (sizin borçlu olduklarınız)
            - **− Sistemdeki Çekler** — Uygulamadaki bekleyen + ciro çek kalanları
            - **− Manuel Çıkarmalar** — Kullanıcının elle çıkardığı kalemler
    
            Kullanılan kur: **{kur} TL/USD** (sidebar'daki güncel kur — sidebar'da değiştirirsen burası da değişir)
            """)
