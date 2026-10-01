"""
KAYRAN — Ürün & Stok Yönetim Sistemi
Modüler olarak KAYRAN portal içinden çağrılır.

Kullanım:
    from kayranpm.main import run
    run()
"""
from shared.tasarim import renk as trenk  # aktif temanın rengi (hex)
from shared.tasarim import df_tablo_html, tablo_html, Ham, rozet_html, renkli, kisalt as _kisalt
from kayranpm.stok_ara import stok_karti_ara
from shared.tasarim import tr_sayi  # TR sayı biçimi (1.234,56)
import streamlit as st
import logging
_log = logging.getLogger(__name__)
# Türkiye saat dilimi için ortak yardımcılar
from shared.utils import secim_serit, tr_today, tr_now, tr_now_str, tr_tomorrow, tr_yesterday as _tr_today_iso_dummy
from shared.utils import tr_kucuk
from shared.utils import firma_gorunen_ad
from shared.utils import sidebar_stil, sidebar_baslik, sidebar_kullanici
from shared.utils import metrik_satiri, metric_css
from shared.ui import tablo_h
from shared.tasarim import baslik as _sb
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
                      ekle_kampanya, get_kampanyalar, get_kampanya,
                      guncelle_kampanya, kapat_kampanya, sil_kampanya,
                      ekle_kampanya_urun, get_kampanya_urunler, get_tum_kampanya_urunler,
                      guncelle_kampanya_urun, sil_kampanya_urun,
                      get_tum_sku_listesi, get_client,
                      get_gecmis_satis_tum_firmalar,
                      get_kampanya_destek_ortalamalari,
                      get_firma_listesi, get_musteri_haftalik_satis,
                      sku_fazeon_temizle_onizle, sku_fazeon_temizle_uygula)
from .analitik import dashboard_hesapla, tum_urunler_listesi, siparis_onerisi_listesi
from .excel_islemler import (excel_yukle_ana_stok, excel_yukle_firma_stoklari,
                            excel_yukle_yoldaki_urunler, create_sample_excel_bytes,
                            excel_yukle_firma_birlesik, excel_yukle_g5f_depolar,
                            excel_yukle_haftalik_stok_satis, excel_yukle_stok_kartlari)


_RK_RENK = {"rk-grn": "yesil", "rk-red": "kirmizi", "rk-yel": "amber", "rk-org": "amber", "rk-dim": None}


def render_renkli_tablo(df, para=None, yuzde=None, kar=None, sol=None,
                        kisalt=None, gizle=None, satir_durum=None):
    """DataFrame'i ORTAK tabloda çizer (Aşama 4b — shared.tasarim.df_tablo_html).
    satir_durum: (kolon, {değer: "rk-grn"/"rk-red"/"rk-yel"}) eski adlar da kabul edilir
    → satır zemini yeşil/kırmızı/sarı vurgulanır."""
    vurgu = None
    if satir_durum:
        kol, harita = satir_durum
        vurgu = (kol, {k: _RK_RENK.get(v, v) for k, v in harita.items()})
    st.html(df_tablo_html(df, para=para, yuzde=yuzde, kar=kar, sol=sol, kisa=kisalt,
                          gizle=gizle, satir_vurgu=vurgu))


def run():
    """KAYRAN ana çalıştırıcı. Portal tarafından çağrılır."""
    initialize_db()

    # İthalat'taki tüm modeller Ürün Yönetimi'ne otomatik yansısın (oturumda bir kez · ekleme-only, silme yok)
    if not st.session_state.get("_ith_autosync"):
        try:
            from .database import ithalat_eksikleri_ekle
            _yeni = ithalat_eksikleri_ekle()
            if _yeni:
                st.toast(f"🚢 İthalat'tan {_yeni} model ürünlere eklendi")
        except Exception:
            pass
        st.session_state["_ith_autosync"] = True

    st.markdown("""
    <style>
    /* ── GLOBAL ─────────────────────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    html, body, .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        background: var(--k-yuzey0) !important;
    }

    /* ── METRIC KARTLARI (modern · sade · profesyonel) ───────────────── */
    div[data-testid="stMetric"] {
        background: linear-gradient(180deg, color-mix(in srgb,var(--k-metin) 4%,transparent), color-mix(in srgb,var(--k-metin) 2%,transparent));
        border: 1px solid color-mix(in srgb,var(--k-metin) 7%,transparent);
        border-radius: 16px;
        padding: 16px 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.22);
        transition: border-color .15s ease;
    }
    div[data-testid="stMetric"]:hover {
        border-color: color-mix(in srgb,var(--k-mor) 32%,transparent);
    }
    div[data-testid="stMetricLabel"],
    div[data-testid="stMetricLabel"] p,
    div[data-testid="stMetricLabel"] div {
        color: var(--k-soluk) !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        letter-spacing: .5px !important;
        text-transform: uppercase !important;
    }
    div[data-testid="stMetricValue"] {
        color: var(--k-mavi) !important;
        font-size:23px !important;
        font-weight: 700 !important;
        font-variant-numeric: tabular-nums;
        line-height: 1.22 !important;
        margin-top: 3px;
        white-space: normal !important;
        word-break: break-word;
    }
    div[data-testid="stMetricDelta"] { font-size:13px !important; }

    /* ── ALERT BOX'LARI (warning/error/info/success) ─────────────────── */
    /* Streamlit'in default renkleri dark tema'da okunmuyor. Manuel override. */
    div[data-testid="stAlert"] {
        border-radius: 10px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 13px !important;
        font-weight:400 !important;
        padding: 0 !important;
        border: 1px solid transparent !important;
        box-shadow: none !important;
    }
    div[data-testid^="stAlertContent"] {
        background: transparent !important;
        border: none !important;
        padding: 11px 15px !important;
        color: var(--k-metin) !important;
    }
    div.stAlert:has([data-testid="stAlertContentWarning"]) {
        background: color-mix(in srgb,var(--k-amber) 7%,transparent) !important;
        border: 1px solid color-mix(in srgb,var(--k-amber) 20%,transparent) !important;
        border-left: 3px solid color-mix(in srgb,var(--k-amber) 60%,transparent) !important;
    }
    div.stAlert:has([data-testid="stAlertContentError"]) {
        background: color-mix(in srgb,var(--k-kirmizi) 7%,transparent) !important;
        border: 1px solid color-mix(in srgb,var(--k-kirmizi) 20%,transparent) !important;
        border-left: 3px solid color-mix(in srgb,var(--k-kirmizi) 60%,transparent) !important;
    }
    div.stAlert:has([data-testid="stAlertContentInfo"]) {
        background: color-mix(in srgb,var(--k-mavi) 6%,transparent) !important;
        border: 1px solid color-mix(in srgb,var(--k-mavi) 20%,transparent) !important;
        border-left: 3px solid color-mix(in srgb,var(--k-mavi) 55%,transparent) !important;
    }
    div.stAlert:has([data-testid="stAlertContentSuccess"]) {
        background: color-mix(in srgb,var(--k-yesil) 6%,transparent) !important;
        border: 1px solid color-mix(in srgb,var(--k-yesil) 20%,transparent) !important;
        border-left: 3px solid color-mix(in srgb,var(--k-yesil) 50%,transparent) !important;
    }
    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] span,
    div[data-testid="stAlert"] strong,
    div[data-testid="stAlert"] div {
        color: var(--k-metin) !important;
    }
    div[data-testid="stAlert"] strong,
    div[data-testid="stAlert"] b {
        font-weight: 700 !important;
    }
    
    /* ── METRIC KARTLARI (özet barlar) ── eski 'metric-container' + yeni 'stMetric' */
    [data-testid="metric-container"],
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, color-mix(in srgb,var(--k-metin) 7%,transparent) 0%, color-mix(in srgb,var(--k-metin) 3%,transparent) 100%);
        border-radius: 14px;
        padding: 16px 16px;
        border: 1px solid color-mix(in srgb,var(--k-metin) 10%,transparent);
        transition: border-color 0.2s;
        min-width: 0;
        overflow: hidden;
    }
    [data-testid="metric-container"]:hover,
    [data-testid="stMetric"]:hover { border-color: rgba(66,165,245,0.4); }
    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] * {
        color: var(--k-silik) !important; font-size:11px !important; font-weight:700 !important;
        letter-spacing:0.5px; text-transform:uppercase;
        white-space:nowrap !important; overflow:hidden !important; text-overflow:ellipsis !important;
    }
    [data-testid="stMetricValue"],
    [data-testid="stMetricValue"] * {
        color: var(--k-metin) !important; font-weight:700 !important; font-size:23px !important;
        white-space:nowrap !important; overflow:hidden !important; text-overflow:ellipsis !important;
        line-height:1.15 !important;
    }
    [data-testid="stMetricDelta"] { font-size:13px !important; }
    
    /* ── BAŞLIK STİLLERİ ─────────────────────────────────────────────────── */
    .baslik {
        display: flex !important; align-items: center !important; gap: 11px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 19px !important;
        font-weight:700 !important;
        color: var(--k-mavi) !important;
        letter-spacing: -0.3px !important;
        margin: 2px 0 0 !important;
        line-height: 1.25 !important;
    }
    .baslik-ikon {
        width: 30px; height: 30px; border-radius: 9px; flex-shrink: 0;
        background: linear-gradient(135deg, color-mix(in srgb,var(--k-mor) 28%,transparent), color-mix(in srgb,var(--k-mor) 16%,transparent));
        border: 1px solid color-mix(in srgb,var(--k-mor) 28%,transparent);
        display: flex; align-items: center; justify-content: center;
        font-size: 14px; letter-spacing: 0;
    }
    .alt-baslik {
        font-size:13px !important;
        color: var(--k-soluk) !important;
        font-weight:400 !important;
        letter-spacing: .1px !important;
        margin: 7px 0 18px !important;
        padding: 0 0 12px 41px !important;
        border-bottom: 1px solid color-mix(in srgb,var(--k-soluk) 10%,transparent) !important;
        position: relative !important;
    }
    .alt-baslik::before {
        content: ""; position: absolute; left: 41px; bottom: -1px;
        width: 40px; height: 2px; border-radius: 2px;
        background: linear-gradient(90deg, var(--k-mor), var(--k-mor));
    }
    .sayfa-baslik-cizgi {
        height: 3px;
        background: linear-gradient(90deg, var(--k-mavi), var(--k-mavi), transparent);
        border-radius: 2px;
        margin-bottom: 24px;
    }
    
    /* ── ETİKET KUTUCUKLARI ──────────────────────────────────────────────── */
    .tag-kirmizi { background:color-mix(in srgb,var(--k-kirmizi) 25%,transparent); color:var(--k-kirmizi); padding:4px 8px; border-radius:20px; font-size:11px; font-weight:700; }
    .tag-turuncu { background:color-mix(in srgb,var(--k-amber) 30%,transparent); color:var(--k-amber); padding:4px 8px; border-radius:20px; font-size:11px; font-weight:700; }
    .tag-sari    { background:var(--k-amber); color:var(--k-amber2); padding:4px 8px; border-radius:20px; font-size:11px; font-weight:700; }
    .tag-yesil   { background:color-mix(in srgb,var(--k-yesil) 25%,transparent); color:var(--k-yesil2); padding:4px 8px; border-radius:20px; font-size:11px; font-weight:700; }
    .tag-mavi    { background:color-mix(in srgb,var(--k-mavi) 30%,transparent); color:var(--k-mavi); padding:4px 8px; border-radius:20px; font-size:11px; font-weight:700; }
    .tag-gri     { background:color-mix(in srgb,var(--k-soluk) 20%,transparent); color:var(--k-soluk); padding:4px 8px; border-radius:20px; font-size:11px; }
    
    /* ── BİLGİ KUTULARI ─────────────────────────────────────────────────── */
    .uyari-box {
        background: color-mix(in srgb,var(--k-amber) 10%,var(--k-yuzey1));
        border-left: 3px solid var(--k-amber);
        color: var(--k-amber);
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
        font-size: 13px;
        font-weight:400;
    }
    .info-box {
        background: color-mix(in srgb,var(--k-mavi) 10%,var(--k-yuzey1));
        border-left: 3px solid var(--k-mavi);
        color: var(--k-mavi);
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
        font-size: 13px;
        font-weight:400;
    }
    .basari-box {
        background: color-mix(in srgb,var(--k-yesil) 10%,var(--k-yuzey1));
        border-left: 3px solid var(--k-yesil2);
        color: var(--k-yesil2);
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
        font-size: 13px;
        font-weight:400;
    }
    
    /* ── SIDEBAR ─────────────────────────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--k-yuzey0) 0%, var(--k-yuzey1) 100%) !important;
        border-right: 1px solid color-mix(in srgb,var(--k-metin) 6%,transparent) !important;
    }
    section[data-testid="stSidebar"] * { color: var(--k-metin) !important; }
    /* ── Stok Kartı kutusu (sol menü) — tek kap: başlık + arama + sonuçlar ──
       'html body section…' ile güçlendirildi: üstteki sidebar '*' ve düğme
       kuralları bu kutuyu ezmesin. */
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu {
        background: var(--k-yuzey1) !important; border: 1px solid var(--k-kenar2) !important;
        border-radius: 12px !important; padding: 12px 10px 10px !important; gap: 2px !important;
        margin: 6px 0 4px !important;
    }
    /* Streamlit metnin altına -1rem koyar (paragraf boşluğunu telafi için); genel
       kural paragraf boşluğunu sıfırladığından başlık 16px "kısalıyor", arama kutusu
       başlığın ÜSTÜNE biniyordu. Bu kutudaki yazı blokları için sıfırla. */
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu [data-testid="stMarkdown"] [data-testid="stMarkdownContainer"] {
        margin-bottom: 0 !important;
    }
    /* Sonuç satırındaki ipucu (tam ürün adı) kabı: genel kural ona zemin+çerçeve
       veriyordu → her satır ayrı kutu gibi görünüyordu. Şeffaf, tam genişlik. */
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu [data-testid="stTooltipIcon"],
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu [data-testid="stTooltipHoverTarget"] {
        background: transparent !important; border: 0 !important; padding: 0 !important;
        border-radius: 0 !important; box-shadow: none !important; display: block !important; width: 100% !important;
    }
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu .sk-bas {
        display: flex; align-items: baseline; justify-content: space-between; padding: 0 2px 8px;
        line-height: 1.3 !important;
    }
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu .sk-bas-ad {
        font-size: 13px !important; font-weight: 650 !important; color: var(--k-metin) !important;
    }
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu .sk-bas-say,
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu .sk-alt {
        font-size: 11px !important; color: var(--k-silik) !important; font-weight: 500 !important;
    }
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu .sk-alt {
        padding: 10px 2px 4px; text-transform: uppercase; letter-spacing: .5px; font-size: 10.5px !important;
        font-weight: 600 !important; line-height: 1.2 !important;
    }
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu .sk-not {
        font-size: 11.5px !important; line-height: 1.5 !important; color: var(--k-silik) !important; padding: 8px 2px 0;
    }
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu .sk-not b { color: var(--k-soluk) !important; }
    /* Arama kutusu */
    /* Çerçeve DIŞ katmanda (ikon + yazı aynı kutuda); iç alan şeffaf */
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu [data-testid="stTextInputRootElement"] {
        background: var(--k-yuzey0) !important; border: 1px solid var(--k-kenar2) !important;
        border-radius: 9px !important; min-height: 38px !important; padding-left: 10px !important;
        align-items: center !important; gap: 6px !important;
    }
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu [data-testid="stTextInputRootElement"]:focus-within {
        border-color: var(--k-mor) !important; box-shadow: 0 0 0 3px color-mix(in srgb,var(--k-mor) 18%,transparent) !important;
    }
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu input {
        font-size: 13px !important; background: transparent !important; border: 0 !important;
        box-shadow: none !important; padding-left: 0 !important;
    }
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu [data-testid="stTextInputIcon"] [data-testid="stIconMaterial"] {
        color: var(--k-silik) !important; font-size: 18px !important;
    }
    /* Sonuç satırları: liste görünümü (düğme değil) — SKU mono+mor, ad tek satır '…' */
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu .stButton { margin: 0 !important; }
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu [data-testid="stElementContainer"]:has([data-testid="stTextInput"]) {
        margin-bottom: 4px !important;
    }
    /* İki satırlı liste: üstte SKU (mono, mor), altta ürün adı (tek satır '…') */
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu .stButton button {
        justify-content: flex-start !important; text-align: left !important; min-height: 0 !important;
        height: auto !important; padding: 5px 8px !important; border: 0 !important; border-radius: 7px !important;
        background: transparent !important; box-shadow: none !important; gap: 6px !important;
    }
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu .stButton button:hover {
        background: var(--k-ortu2) !important;
    }
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu .stButton button > div,
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu .stButton button [data-testid="stMarkdownContainer"] {
        min-width: 0 !important; overflow: hidden !important; width: 100% !important; justify-content: flex-start !important;
    }
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu .stButton button p {
        font-size: 12px !important; font-weight: 400 !important; color: var(--k-soluk) !important;
        white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important;
        text-align: left !important; margin: 0 !important;
    }
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu .stButton button code {
        display: block !important; font-family: var(--k-mono) !important; font-size: 12px !important;
        font-weight: 600 !important; line-height: 1.35 !important; color: var(--k-mor) !important;
        background: transparent !important; padding: 0 !important; border: 0 !important;
    }
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu .stButton button p { line-height: 1.4 !important; }
    html body section[data-testid="stSidebar"] .st-key-stok_karti_kutu .stButton button [data-testid="stIconMaterial"] {
        color: var(--k-silik) !important; font-size: 15px !important;
    }

    /* Sidebar nav stili shared/utils.py → sidebar_stil() tarafından yönetilir */
    section[data-testid="stSidebar"] .stButton button {
        background: var(--k-yuzey2) !important;
        color: var(--k-metin) !important;
        border: 1px solid var(--k-kenar2) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }
    section[data-testid="stSidebar"] hr {
        border-color: color-mix(in srgb,var(--k-metin) 8%,transparent) !important;
        margin: 12px 0 !important;
    }

    /* Sol menü aç/kapat düğmesi: app.py'deki ortak düğme (tema renkli, sade).
       Burada eskiden parlak mavi kare + gölge veriliyordu; yalnız bu modülde
       sol üstte mavi bir kutu çıkıyordu. */

    /* ── BUTONLAR ────────────────────────────────────────────────────────── */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        transition: all 0.2s !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg,var(--k-mavi),var(--k-mavi)) !important;
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
        background: color-mix(in srgb,var(--k-metin) 5%,transparent) !important;
        border: 1px solid color-mix(in srgb,var(--k-metin) 12%,transparent) !important;
        border-radius: 8px !important;
        color: var(--k-metin) !important;
        font-size: 13px !important;
    }
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {
        border-color: var(--k-mavi) !important;
        box-shadow: 0 0 0 2px rgba(66,165,245,0.15) !important;
    }
    label[data-testid="stWidgetLabel"] p {
        color: var(--k-silik) !important;
        font-size:13px !important;
        font-weight: 600 !important;
        letter-spacing: 0.3px !important;
    }
    
    /* ── EXPANDER ────────────────────────────────────────────────────────── */
    .streamlit-expanderHeader {
        background: color-mix(in srgb,var(--k-metin) 4%,transparent) !important;
        border-radius: 10px !important;
        border: 1px solid color-mix(in srgb,var(--k-metin) 8%,transparent) !important;
        color: var(--k-mavi) !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }
    .streamlit-expanderContent {
        background: color-mix(in srgb,var(--k-metin) 2%,transparent) !important;
        border: 1px solid color-mix(in srgb,var(--k-metin) 6%,transparent) !important;
        border-top: none !important;
        border-radius: 0 0 10px 10px !important;
    }
    
    /* ── TABS ────────────────────────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        background: color-mix(in srgb,var(--k-metin) 3%,transparent) !important;
        border-radius: 10px !important;
        padding: 4px !important;
        gap: 2px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        color: var(--k-silik) !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        padding: 6px 16px !important;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(21,101,192,0.4) !important;
        color: var(--k-mavi) !important;
    }
    
    /* ── DATAFRAME ───────────────────────────────────────────────────────── */
    .stDataFrame { border-radius: 10px !important; overflow: hidden !important; }
    .stDataFrame [data-testid="stDataFrameResizable"] {
        border: 1px solid color-mix(in srgb,var(--k-metin) 8%,transparent) !important;
        border-radius: 10px !important;
    }
    
    /* ── DIVIDER ─────────────────────────────────────────────────────────── */
    hr { border-color: color-mix(in srgb,var(--k-metin) 6%,transparent) !important; margin: 20px 0 !important; }
    
    /* ── TABLO HÜCRE RENKLERİ ────────────────────────────────────────────── */
    .hucre-acil    { background:color-mix(in srgb,var(--k-kirmizi) 25%,transparent) !important; color:var(--k-kirmizi) !important; font-weight:700; }
    .hucre-turuncu { background:color-mix(in srgb,var(--k-amber) 30%,transparent) !important; color:var(--k-amber) !important; font-weight:600; }
    .hucre-sari    { background:color-mix(in srgb,var(--k-amber) 35%,transparent) !important; color:var(--k-amber) !important; font-weight:600; }
    .hucre-yesil   { background:color-mix(in srgb,var(--k-yesil) 25%,transparent) !important; color:var(--k-yesil2) !important; font-weight:600; }
    .hucre-gri     { background:color-mix(in srgb,var(--k-soluk) 20%,transparent) !important; color:var(--k-metin) !important; }
    .fcp-vurgu { color:var(--k-amber2); font-weight:700; font-size:14px; }
    
    /* ── SCROLLBAR ───────────────────────────────────────────────────────── */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: color-mix(in srgb,var(--k-metin) 2%,transparent); }
    ::-webkit-scrollbar-thumb { background: color-mix(in srgb,var(--k-metin) 15%,transparent); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: color-mix(in srgb,var(--k-metin) 25%,transparent); }
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
        from shared.utils import sidebar_ust
        sidebar_ust("📦", "Ürün Yönetimi", "kayranpm")
        from shared.tasarim import menu_etiketi as _me
        sayfa = st.radio("Sayfa", [
            "📊  Dashboard",
            "📋  Tüm Ürünler",
            "📈  Müşteri Satışları",
            "🎯  Kampanya Takip",
            "📦  Sipariş Önerisi",
            "💵  Maliyet Girişi",
            "🔖  Ref No Takibi",
            "📂  Veri Yükleme",
        ], label_visibility="collapsed",
           format_func=_me)

        # ── STOK KARTI — hızlı erişim (Ürün Yön.'nin en sık kullanılan eylemi) ──
        # Eskiden başlık ayrı bir HTML kutusuydu; arama kutusu ve sonuçlar onun
        # DIŞINDA kalıyordu (kopuk görünüm). Şimdi hepsi tek kap (st.container).
        #
        # Korunan dersler (önceki iki hata — yeniden yaşanmasın):
        # 1) Selectbox YOK: kendi anahtarına yazınca ilk karakter siliniyordu.
        # 2) Bayrak dansı YOK: sonuca basmak kartı HER ZAMAN açar.
        # Yeni: Enter'da tek/tam eşleşme varsa kart doğrudan açılır — ama yalnız
        # arama METNİ DEĞİŞTİYSE (_sk_acilan): yoksa sonraki her yenilemede açılırdı.
        _skl = get_tum_sku_listesi() or []
        _hedef = st.session_state.pop("_stok_gec_sku", None)   # modal içi geçiş
        with st.container(key="stok_karti_kutu"):
            st.markdown('<div class="sk-bas"><span class="sk-bas-ad">Stok Kartı</span>'
                        f'<span class="sk-bas-say">{tr_sayi(len(_skl))} ürün</span></div>',
                        unsafe_allow_html=True)
            _ara = st.text_input(
                "Stok kartı ara", key="stok_karti_ara", icon=":material/search:",
                placeholder="SKU, model ya da ürün adı",
                label_visibility="collapsed")
            _q = (_ara or "").strip()
            if not _hedef and _q:
                _bul = stok_karti_ara(_skl, _q)
                if not _bul:
                    st.markdown('<div class="sk-not">Eşleşen ürün yok. SKU\'nun bir kısmını '
                                'ya da modeli yazmayı dene.</div>', unsafe_allow_html=True)
                else:
                    _tam = [r for r in _bul if str(r.get("sku") or "").strip().upper() == _q.upper()]
                    _tek = _tam[0] if _tam else (_bul[0] if len(_bul) == 1 else None)
                    if _tek and st.session_state.get("_sk_acilan") != _q:
                        st.session_state["_sk_acilan"] = _q           # aynı aramada bir kez
                        _hedef = _tek["sku"]
                    for _r in _bul[:6]:
                        _ad = (_r.get("urun_adi") or "").strip()
                        if st.button(f"`{_r['sku']}` {_ad}" if _ad else f"`{_r['sku']}`",
                                     key=f"stok_ac_{_r['sku']}", use_container_width=True,
                                     help=_ad or None):
                            _hedef = _r["sku"]
                    if len(_bul) > 6:
                        st.markdown(f'<div class="sk-not">+{tr_sayi(len(_bul) - 6)} sonuç daha — '
                                    f'aramayı daralt.</div>', unsafe_allow_html=True)
            elif not _hedef:
                _son = st.session_state.get("_sk_son", [])
                if _son:
                    st.markdown('<div class="sk-alt">Son açılanlar</div>', unsafe_allow_html=True)
                    for _s in _son:
                        if st.button(f"`{_s}`", key=f"stok_son_{_s}", use_container_width=True,
                                     icon=":material/history:"):
                            _hedef = _s
                else:
                    st.markdown('<div class="sk-not">Yaz ve <b>Enter</b>\'a bas — tam SKU '
                                'yazarsan kart doğrudan açılır.</div>', unsafe_allow_html=True)

        if _hedef:
            _son = [x for x in st.session_state.get("_sk_son", []) if x != _hedef]
            st.session_state["_sk_son"] = ([_hedef] + _son)[:4]
            from kayranpm.stok_karti import goster as _stok_goster
            _stok_goster(_hedef)


        st.markdown(f"""
        <div style="text-align:center; margin-top:20px; padding-bottom:8px;">
            <div style="color:var(--k-silik); font-size:11px;">🕐 {tr_now().strftime('%d.%m.%Y  %H:%M')}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # ════════════════════════════════════════════════════════════════════
    # 1) DASHBOARD
    # ════════════════════════════════════════════════════════════════════
    # ── Sayfa gövdesi: KENDİ İÇİNDE YENİLENEN PARÇA (st.fragment) ───────────
    # HIZ: Sayfadaki filtre, seçim kutusu, sekme ya da onay kutusu değişince
    # yalnız bu gövde yeniden çizilir; üst menü, sol menü, oturum kontrolü ve
    # ortak CSS yeniden çalışmaz. Kayıt sonrası st.rerun() çağrıları ESKİSİ
    # GİBİ tüm sayfayı yeniler (Streamlit 1.64'te parça içi st.rerun() tam
    # yenilemedir). Blok ile dış kapsamın paylaştığı değişkenler nonlocal ile
    # aynen korunur (otomatik hesaplandı; tests/test_parca.py denetler).
    @st.fragment
    def _sayfa_parcasi():
        nonlocal _yeni
        if sayfa == "📊  Dashboard":
            st.markdown(_sb("📊 Ürün Yönetimi", "Genel Bakış", aciklama="Stok durumu · Satış performansı · Uyarılar"), unsafe_allow_html=True)
            st.markdown('<div class="sayfa-baslik-cizgi"></div>', unsafe_allow_html=True)
    
            # Veri yükle (seçici için SKU listesi gerekli)
            try:
                veri = dashboard_hesapla()
            except Exception as e:
                _log.error("Dashboard veri hatası: %s", e)
                st.error(f"Veri yüklenemedi: {e}")
                st.stop()

            # Filtreler
            _kat_list_d = sorted({tr_kucuk(u.get("kategori")) for u in veri if tr_kucuk(u.get("kategori"))})
            col_f1, col_f2, col_f3 = st.columns([1.6, 1.6, 0.9])
            with col_f1:
                filtre_firma = st.selectbox("Firma Filtresi", ["Tüm Firmalar", "ITOPYA", "HB", "VATAN", "MONDAY", "KANAL", "DİĞER"], format_func=firma_gorunen_ad)
            with col_f2:
                filtre_kat = st.selectbox("Kategori", ["Tüm Kategoriler"] + _kat_list_d, key="dash_kat")
            with col_f3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Yenile", use_container_width=True, icon=":material/refresh:"):
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
    
                # Kategori filtresi
                if filtre_kat != "Tüm Kategoriler" and tr_kucuk(urun.get("kategori")) != filtre_kat:
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
    
            metrik_satiri([
                {"label": "📦 Toplam Ürün", "value": f"{tr_sayi(toplam_sku)}", "renk": trenk("mor")},
                {"label": "🔴 Acil Sipariş", "value": f"{tr_sayi(len(acil_urunler))}", "renk": trenk("kirmizi")},
                {"label": "🟠 Yaklaşıyor", "value": f"{tr_sayi(len(yaklasan_urunler))}", "renk": trenk("amber")},
                {"label": "🟡 Planlama", "value": f"{tr_sayi(len(planlama_urunler))}", "renk": trenk("amber")},
            ])
    
            # ── UYARI PENCERELERİ — shared/ui.py standardı: yan yana kart + iç scroll ──
            from shared.ui import RENK, pencere_css, pencere, pencere_grid, bos_durum
            from shared.tasarim import urun_etiketi
            st.markdown(pencere_css(), unsafe_allow_html=True)

            acil_items_list = []
            for u in acil_urunler:
                gun = u.get('stok_bitis_gun', '?')
                toplam = u.get('toplam_stok', u.get('bizim_stok', 0))
                acil_items_list.append(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;'
                    f'padding:4px 8px;margin:4px 0;border-radius:6px;background:linear-gradient(180deg,var(--k-yuzey2),var(--k-yuzey1));">'
                    f'{urun_etiketi(u.get("urun_adi"), u.get("sku"), kalin=True)}'
                    f'<div style="display:flex;gap:12px;flex-shrink:0;margin-left:8px;">'
                    f'<span style="color:var(--k-soluk);font-size:11px;">📦 {tr_sayi(toplam)}</span>'
                    f'<span style="color:var(--k-kirmizi);font-size:11px;font-weight:700;">{gun}g</span>'
                    f'</div></div>'
                )
            acil_html = "".join(acil_items_list) or bos_durum("Acil sipariş gerektiren ürün yok")

            yak_items_list = []
            for u in yaklasan_urunler:
                gun = u.get('siparis_son_gun', u.get('stok_bitis_gun', '?'))
                yak_items_list.append(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;'
                    f'padding:4px 8px;margin:4px 0;border-radius:6px;background:linear-gradient(180deg,var(--k-yuzey2),var(--k-yuzey1));">'
                    f'{urun_etiketi(u.get("urun_adi"), u.get("sku"))}'
                    f'<span style="color:var(--k-amber);font-size:11px;font-weight:600;flex-shrink:0;margin-left:8px;">'
                    f'{gun}g içinde</span></div>'
                )
            yak_html = "".join(yak_items_list) or bos_durum("30 gün içinde sipariş gereken ürün yok")

            st.markdown(pencere_grid(
                pencere("🚨 ACİL SİPARİŞ", RENK["kirmizi"], acil_html,
                        rozet=f"{len(acil_urunler)} ürün"),
                pencere("⚠️ 30 GÜN İÇİNDE SİPARİŞ", RENK["amber"], yak_html,
                        rozet=f"{len(yaklasan_urunler)} ürün"),
            ), unsafe_allow_html=True)
    
    
            st.markdown("---")
    
            # ── GÜNCEL KAMPANYA ÖZETİ (kapalı panel + tablo) ──
            try:
                from .database import get_kampanyalar as _get_kmp
                _kmps = _get_kmp(durum="aktif") or []
            except Exception:
                _kmps = []
            import datetime as _kdt2

            def _bts(k):
                try:
                    return _kdt2.date.fromisoformat(str(k.get("bitis_tarihi"))[:10])
                except Exception:
                    return _kdt2.date.max

            _bg = _kdt2.date.today()
            @st.dialog(f"🎯 Güncel Kampanyalar ({len(_kmps)} aktif)", width="large")
            def _dlg_dash_kampanyalar():
                if not _kmps:
                    st.info("Şu an aktif kampanya yok. Kampanya eklemek için **Kampanya Takip** sayfasını kullan.")
                else:
                    _tur_say = {}
                    for k in _kmps:
                        _t = (k.get("kampanya_turu") or "").strip() or "Belirsiz"
                        _tur_say[_t] = _tur_say.get(_t, 0) + 1
                    _dagilim = " · ".join(f"{v} {t}" for t, v in sorted(_tur_say.items(), key=lambda x: -x[1]))
                    _yakin = sum(1 for k in _kmps if _bts(k) != _kdt2.date.max and 0 <= (_bts(k) - _bg).days <= 7)
                    _ozet = f'<b style="color:var(--k-mor2)">{len(_kmps)} aktif kampanya</b>'
                    if _dagilim:
                        _ozet += f' · <span style="color:var(--k-soluk)">{_dagilim}</span>'
                    if _yakin:
                        _ozet += f' · <span style="color:var(--k-amber)">⏳ {_yakin} tanesi 7 gün içinde bitiyor</span>'
                    st.markdown(f'<div style="font-size:13px;margin-bottom:8px">{_ozet}</div>', unsafe_allow_html=True)

                    _rows_k = []
                    for k in sorted(_kmps, key=_bts):
                        _bt = _bts(k)
                        if _bt == _kdt2.date.max:
                            _kalan = ""
                            _durum_k = "—"
                        else:
                            _kg = (_bt - _bg).days
                            _kalan = _kg
                            _durum_k = ("Süresi doldu" if _kg < 0 else
                                        "Bugün bitiyor" if _kg == 0 else
                                        "Yakında bitiyor" if _kg <= 7 else "Aktif")
                        try:
                            _sp = float(k.get("spiff_tl") or 0)
                        except Exception:
                            _sp = 0.0
                        _rows_k.append({
                            "Kampanya": k.get("kampanya_adi", "—"),
                            "Tür": (k.get("kampanya_turu") or "—"),
                            "Firma": k.get("firma", "") or "",
                            "Kategori": k.get("kategori", "") or "",
                            "Başlangıç": str(k.get("baslangic_tarihi", "") or "")[:10],
                            "Bitiş": str(k.get("bitis_tarihi", "") or "")[:10],
                            "Kalan (gün)": _kalan,
                            "Durum": _durum_k,
                            "Spiff ₺": (f"{tr_sayi(_sp)}" if _sp else ""),
                        })
                    st.dataframe(pd.DataFrame(_rows_k), hide_index=True, use_container_width=True, height=tablo_h(len(_rows_k)))
            if st.button(f"Güncel Kampanyalar ({len(_kmps)} aktif)", key="btn_dash_kmp", use_container_width=True, icon=":material/track_changes:"):
                _dlg_dash_kampanyalar()

        elif sayfa == "📋  Tüm Ürünler":
            st.markdown(_sb("📋 Ürün Yönetimi", "Tüm Ürünler", aciklama="FOB Price · Cost · Cost Price · Final Cost Price (Paçal) · Stok Dağılımı"), unsafe_allow_html=True)
            st.markdown('<div class="sayfa-baslik-cizgi"></div>', unsafe_allow_html=True)
    
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
    
            metrik_satiri([
                {"label": "📦 Toplam Ürün", "value": f"{tr_sayi(len(urun_data))}", "renk": trenk("mor")},
                {"label": "🏭 Toplam Stok (Tüm Kanallar)", "value": f"{tr_sayi(toplam_genel_stok)} adet", "renk": trenk("cyan")},
                {"label": "💰 Depo Stok Değeri (Maliyet)", "value": f"${tr_sayi(toplam_stok_degeri)}", "renk": trenk("amber")},
                {"label": "💵 Depo Stok Değeri (Satış)", "value": f"${tr_sayi(toplam_satis_degeri)}", "renk": trenk("yesil")},
            ])

            # 🩺 Veri sağlığı (tek satır · eksik alanlar)
            _eksik_kat = sum(1 for u in urun_data if not (u.get("kategori") or "").strip())
            _eksik_mar = sum(1 for u in urun_data if not (u.get("marka") or "").strip())
            _eksik_fiy = sum(1 for u in urun_data if not (u.get("satis_fiyati") or 0))
            _eksik_mal = sum(1 for u in urun_data if not (u.get("final_cost_price") or 0))
            _sg = []
            if _eksik_kat: _sg.append(f'<span style="color:var(--k-amber)">⚠ {_eksik_kat} kategorisiz</span>')
            if _eksik_mar: _sg.append(f'<span style="color:var(--k-amber)">⚠ {_eksik_mar} markasız</span>')
            if _eksik_fiy: _sg.append(f'<span style="color:var(--k-kirmizi)">⚠ {_eksik_fiy} satış fiyatsız</span>')
            if _eksik_mal: _sg.append(f'<span style="color:var(--k-soluk)">{_eksik_mal} İthalat maliyeti yok</span>')
            if _sg:
                st.markdown('<div style="font-size:13px;color:var(--k-soluk);margin:8px 0 0px">🩺 <b>Veri sağlığı:</b> '
                            + '  ·  '.join(_sg)
                            + ' <span style="color:var(--k-silik)">— Veri Yükleme’deki 🏷️/💲 toplu araçlardan doldurabilirsin</span></div>',
                            unsafe_allow_html=True)
            else:
                st.markdown('<div style="font-size:13px;color:var(--k-yesil);margin:8px 0 0px">🩺 <b>Veri sağlığı:</b> ✓ tüm alanlar dolu</div>',
                            unsafe_allow_html=True)

            st.markdown("---")
    
            # SKU arama + ürün seçimi
            st.markdown('<div style="font-size:11px;font-weight:700;color:var(--k-soluk);letter-spacing:1px;text-transform:uppercase;margin:0px 0 8px;text-align:center;">🔎 Ürün Ara / Seç</div>', unsafe_allow_html=True)
            _sl_tu, col_sec, _sr_tu = st.columns([1.6, 2.0, 1.6])
            with col_sec:
                sku_secenekler = {u['sku']: u['sku'] for u in urun_data}
                secim = st.selectbox("Ürün Seç", list(sku_secenekler.keys()),
                                     label_visibility="collapsed", key="tu_sku")
    
            secilen_sku = sku_secenekler[secim]
            secilen = next(u for u in urun_data if u["sku"] == secilen_sku)
            firma_st = secilen.get("firma_stoklari", {})
    
            # ── Ürün Başlığı (modern kart) ──
            st.markdown(f"""<div style="display:flex;align-items:center;gap:16px;padding:16px 16px;margin:4px 0 16px;background:linear-gradient(135deg,color-mix(in srgb,var(--k-mor) 10%,transparent),color-mix(in srgb,var(--k-mavi) 4%,transparent));border:1px solid color-mix(in srgb,var(--k-mor) 18%,transparent);border-radius:16px;">
     <div style="width:48px;height:48px;border-radius:13px;flex-shrink:0;background:linear-gradient(135deg,var(--k-mor),var(--k-mor));display:flex;align-items:center;justify-content:center;font-size:23px;box-shadow:0 6px 18px color-mix(in srgb,var(--k-mor) 35%,transparent);">📦</div>
     <div style="min-width:0;">
     <div style="font-family:'Manrope','Inter',sans-serif;font-size:19px;font-weight:700;color:var(--k-mavi);line-height:1.3;letter-spacing:-0.3px;">{secilen["urun_adi"]}</div>
     <div style="margin-top:8px;"><span style="display:inline-block;padding:4px 12px;border-radius:7px;background:color-mix(in srgb,var(--k-mor) 15%,transparent);border:1px solid color-mix(in srgb,var(--k-mor) 25%,transparent);color:var(--k-mor2);font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;letter-spacing:0.5px;">{secilen["sku"]}</span></div>
     </div></div>""", unsafe_allow_html=True)
    
            bizim_stok = secilen.get("bizim_stok", 0)
            toplam_firma = secilen.get("toplam_firma_stok", 0)
            toplam = secilen.get("toplam_stok", bizim_stok + toplam_firma)
    
            # Stok kartları — ortak tema (renkli sol şeritli kart)
            _stok_cards = [{"label": "G5F DEPO", "value": f"{tr_sayi(bizim_stok)}", "alt": "adet", "renk": trenk("mavi")}]
            for firma, adet in firma_st.items():
                if adet > 0:
                    _stok_cards.append({"label": firma, "value": f"{tr_sayi(adet)}", "alt": "adet"})
            st.markdown(
                f'<div style="display:flex; justify-content:space-between; align-items:center; margin:8px 0 8px;">'
                f'<span style="color:var(--k-soluk); font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:1.5px;">STOK DAĞILIMI</span>'
                f'<span style="color:var(--k-amber); font-size:19px; font-weight:700;">{tr_sayi(toplam)} adet</span>'
                f'</div>',
                unsafe_allow_html=True)
            metrik_satiri(_stok_cards)

            # G5F depo kırılımı (tüm depolar) — bizim deponun depo bazlı dağılımı + genel toplam
            _dk = secilen.get("depo_kirilim") or {}
            if isinstance(_dk, dict) and _dk:
                _dk_toplam = sum(int(v or 0) for v in _dk.values())
                _chips = "".join(
                    f'<span style="display:inline-flex;gap:8px;align-items:center;background:color-mix(in srgb,var(--k-metin) 4%,transparent);'
                    f'border:1px solid color-mix(in srgb,var(--k-soluk) 20%,transparent);border-radius:8px;padding:4px 12px;font-size:13px;color:var(--k-mavi)">'
                    f'{_d} <b style="color:var(--k-mavi);font-family:monospace">{tr_sayi(int(_v or 0))}</b></span>'
                    for _d, _v in sorted(_dk.items(), key=lambda x: -int(x[1] or 0)))
                st.markdown(
                    f'<div style="margin:0px 0 12px">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
                    f'<span style="color:var(--k-soluk);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px">🏬 G5F DEPO KIRILIMI</span>'
                    f'<span style="color:var(--k-yesil);font-size:14px;font-weight:700;font-family:monospace">Tüm depolar: {tr_sayi(_dk_toplam)} adet</span></div>'
                    f'<div style="display:flex;flex-wrap:wrap;gap:8px">{_chips}</div>'
                    f'<div style="color:var(--k-silik);font-size:11px;margin-top:8px">Sipariş önerisinde kullanılan stok '
                    f'(Merkez + Happy Life): <b style="color:var(--k-mavi)">{tr_sayi(bizim_stok)}</b></div>'
                    f'</div>', unsafe_allow_html=True)
    
            # Fiyat ve karlılık kartı
            fob = secilen.get("fob_price") or 0
            cost = secilen.get("cost") or 0
            cost_price = secilen.get("cost_price") or 0
            fcp = secilen.get("final_cost_price") or 0
            son_fob = secilen.get("son_fob") or 0
            son_fcp = secilen.get("son_final") or 0
            son_tarih = secilen.get("son_tarih") or ""
            ithalat_dosya = secilen.get("ithalat_dosya_sayisi", 0) or 0
            satis = secilen.get("satis_fiyati") or 0
            mal_y = secilen.get("mal_yuzde") or secilen.get("son_mal_yuzde") or 0
    
            if fob > 0 or fcp > 0:
                _son_alt = f"En yeni dosya · {son_tarih}" if son_tarih else "En yeni ithalat dosyası"
                _fiyat_cards = [
                    {"label": "PAÇAL FOB", "value": f"${tr_sayi(fob, 2)}", "renk": trenk("mavi"),
                     "alt": "Adet-ağırlıklı ortalama"},
                    {"label": "SON FOB", "value": f"${tr_sayi(son_fob, 2)}" if son_fob else "—", "renk": trenk("mavi"),
                     "alt": _son_alt},
                    {"label": f"MALİYET (%{tr_sayi(mal_y, 1)})", "value": f"${tr_sayi(cost, 2)}", "renk": trenk("amber")},
                    {"label": "⭐ PAÇAL MALİYET", "value": f"${tr_sayi(fcp, 2)}", "renk": trenk("amber"),
                     "alt": "Landed · İthalat"},
                    {"label": "SON MALİYET", "value": f"${tr_sayi(son_fcp, 2)}" if son_fcp else "—", "renk": trenk("amber2"),
                     "alt": _son_alt},
                ]
                if satis > 0:
                    _fiyat_cards.append({"label": "SATIŞ FİYATI", "value": f"${tr_sayi(satis, 2)}", "renk": trenk("cyan")})
                    if fcp > 0:
                        _kar = satis - fcp
                        _marj = (_kar / satis * 100) if satis else 0
                        if _kar >= 0:
                            _fiyat_cards.append({"label": "KÂR", "value": f"${tr_sayi(_kar, 2)}",
                                                 "renk": trenk("yesil"), "alt": f"Marj %{tr_sayi(_marj, 1)} · paçala göre"})
                        else:
                            _fiyat_cards.append({"label": "⚠️ ZARAR", "value": f"${tr_sayi(_kar, 2)}",
                                                 "renk": trenk("kirmizi"), "alt": "Satış, paçal maliyetin altında"})
                st.markdown(
                    f'<div style="display:flex;align-items:center;justify-content:space-between;margin:8px 0 8px">'
                    f'<div style="color:var(--k-mavi);font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px">FİYAT ANALİZİ</div>'
                    f'<div style="color:var(--k-yesil2);font-size:11px;font-weight:600;background:color-mix(in srgb,var(--k-yesil) 12%,transparent);border:1px solid color-mix(in srgb,var(--k-yesil) 25%,transparent);border-radius:6px;padding:4px 8px">🚢 İthalat · {ithalat_dosya} parti</div></div>',
                    unsafe_allow_html=True)
                metrik_satiri(_fiyat_cards)
            else:
                st.markdown('<div style="background:color-mix(in srgb,var(--k-soluk) 6%,transparent);border:1px dashed color-mix(in srgb,var(--k-soluk) 25%,transparent);border-radius:12px;padding:16px;text-align:center;color:var(--k-soluk);font-size:13px;margin-bottom:16px">🚢 Bu ürün için İthalat maliyet verisi yok — İthalat modülünden bu SKU ile dosya girilince maliyet/paçal otomatik gelecek.</div>', unsafe_allow_html=True)

            # EOL rozeti
            if secilen.get("eol"):
                st.markdown(
                    '<div style="background:color-mix(in srgb,var(--k-kirmizi) 10%,transparent);border:1px solid color-mix(in srgb,var(--k-kirmizi) 35%,transparent);'
                    'border-radius:10px;padding:8px 16px;margin:4px 0 8px;color:var(--k-kirmizi);font-size:13px;font-weight:700">'
                    '⛔ EOL — Bu ürün üretimi/satışı sonlandı olarak işaretli; sipariş önerisine girmez.</div>',
                    unsafe_allow_html=True)

            # Müşteri bazlı satış fiyat listesi
            _fl = secilen.get("satis_fiyat_listesi") or {}
            if _fl:
                st.markdown('<div style="color:var(--k-mavi);font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:8px 0 8px">🏷️ Müşteri Bazlı Satış Fiyatları</div>', unsafe_allow_html=True)
                metrik_satiri([{"label": _m, "value": f"${tr_sayi(_v, 2)}", "renk": trenk("cyan")}
                               for _m, _v in _fl.items()])

            st.markdown("---")

            # Detayli Gorunum (satis trendi - siparis - yoldaki)
            try:
                _veri_detay = dashboard_hesapla()
                urun = next((u for u in _veri_detay if u["sku"] == secilen_sku), secilen)
            except Exception:
                urun = secilen
            # Üst bilgi kartları
            c1, c2, c3, c4, c5 = st.columns(5)
            toplam_stok_ud = urun.get("toplam_stok", urun.get("bizim_stok", 0))
            stok_bitis = urun.get('stok_bitis_gun')
            stok_bitis_str = f"{stok_bitis} gün" if stok_bitis is not None and stok_bitis != 0 else "Veri yok"
            _risk = urun.get('risk_skor', 0) or 0
            _risk_renk = trenk("kirmizi") if _risk >= 70 else (trenk("amber") if _risk >= 40 else trenk("yesil"))
            metrik_satiri([
                {"label": "📦 Toplam Stok", "value": f"{tr_sayi(toplam_stok_ud)}", "renk": trenk("mor")},
                {"label": "📊 Ort. Hft. Satış", "value": f"{tr_sayi(round(urun.get('ortalama_haftalik_satis', 0)))}", "renk": trenk("cyan")},
                {"label": "⚡ Risk Skoru", "value": f"{_risk}/100", "renk": _risk_renk},
                {"label": "📅 Stok Biter", "value": stok_bitis_str, "renk": trenk("mor")},
                {"label": "📦 Sipariş Önerisi", "value": f"{urun.get('oneri_miktar',0)} adet", "renk": trenk("amber")},
            ])
    
            # Sipariş durumu banner (yumuşak, tek katman)
            siparis_durum = urun.get("siparis_durum", "veri_yok")
            siparis_mesaj = urun.get("siparis_mesaj", "")
            _oneri_mesaj = urun.get("oneri_mesaj", "")
            _durum_stil = {
                "acil":       ("rgba(239,68,68,0.07)", "rgba(239,68,68,0.55)", "🚨", trenk("kirmizi")),
                "yaklasıyor": ("rgba(245,158,11,0.07)", "rgba(245,158,11,0.5)", "⚠️", trenk("amber")),
                "planlama":   ("rgba(59,130,246,0.07)", "rgba(59,130,246,0.5)", "📋", trenk("mavi")),
                "veri_yok":   ("rgba(34,197,94,0.06)", "rgba(34,197,94,0.45)", "✅", trenk("yesil2")),
            }
            _bg, _brd, _ik, _tc = _durum_stil.get(siparis_durum, _durum_stil["veri_yok"])
            _detay = f' <span style="color:var(--k-soluk);font-weight:400;">· {_oneri_mesaj}</span>' if _oneri_mesaj else ""
            st.markdown(
                f'<div style="background:{_bg};border-left:3px solid {_brd};border-radius:8px;padding:12px 16px;margin:8px 0;font-size:13px;">'
                f'<span style="color:{_tc};font-weight:700;">{_ik} {siparis_mesaj}</span>{_detay}</div>',
                unsafe_allow_html=True
            )
    
            st.markdown("---")
    
            # Tüm ürünler özet tablosu
            @st.dialog("📊 Tüm Ürünler Özet — filtrele, sırala, incele", width="large")
            def _dlg_urunler_ozet():
                _kat_oz = sorted({tr_kucuk(u.get("kategori")) for u in urun_data if tr_kucuk(u.get("kategori"))})
                _mar_oz = sorted({(u.get("marka") or "").strip() for u in urun_data if (u.get("marka") or "").strip()})
                _ozf0, _ozf1, _ozf2, _ozf3, _ozf4 = st.columns([1.6, 1.2, 1.2, 1.5, 1.0])
                _sku_ad_map_oz = {}
                for _uu in urun_data:
                    _ss = str(_uu.get("sku", "") or "").strip()
                    if _ss and _ss not in _sku_ad_map_oz:
                        _sku_ad_map_oz[_ss] = _uu.get("urun_adi", "") or ""
                _sku_secenek_oz = ["Tümü"] + [f"{s} — {a}" if a else s for s, a in sorted(_sku_ad_map_oz.items())]
                with _ozf0:
                    f_ara_oz = st.selectbox(f"🔍 SKU / Ürün ({len(_sku_ad_map_oz)} model · yazarak ara)",
                                            _sku_secenek_oz, key="oz_ara")
                with _ozf1:
                    f_kat_oz = st.selectbox("Kategori", ["Tümü"] + _kat_oz, key="oz_kat")
                with _ozf2:
                    f_mar_oz = st.selectbox("Marka", ["Tümü"] + _mar_oz, key="oz_mar")
                with _ozf3:
                    f_sira_oz = st.selectbox("Sırala", ["Stok Yaşı (gün)", "Net Kâr ($)", "Net Marj (%)", "Maliyet %", "Toplam Stok", "Satış ($)", "FOB ($)", "Risk Skoru", "SKU (A-Z)"], key="oz_sira")
                with _ozf4:
                    f_yon_oz = st.selectbox("Yön", ["Azalan", "Artan"], key="oz_yon")
                _sadece_zarar = st.checkbox("⚠️ Sadece zararına satılanlar (satış < paçal maliyet)", value=False, key="oz_zarar")
                _sira_map_oz = {"Stok Yaşı (gün)": "_stok_yas", "Net Kâr ($)": "Net Kar ($)", "Net Marj (%)": "Net Marj (%)", "Maliyet %": "Maliyet %", "Toplam Stok": "Toplam", "Satış ($)": "Satış ($)", "FOB ($)": "FOB ($)", "Risk Skoru": "_risk", "SKU (A-Z)": "SKU"}
                rows_oz = []
                for u in urun_data:
                    fs = u.get("firma_stoklari", {})
                    satis = u.get('satis_fiyati') or 0
                    ith_var = (u.get("ithalat_dosya_sayisi", 0) or 0) > 0
                    fcp = (u.get('final_cost_price') or 0) if ith_var else 0
                    fob = (u.get('fob_price') or 0) if ith_var else 0
                    son_fob = (u.get('son_fob') or 0) if ith_var else 0
                    son_fcp = (u.get('son_final') or 0) if ith_var else 0
                    maliyet_yuzde = ((fcp / fob - 1) * 100) if (fob > 0 and fcp > 0) else None
                    net_kar = (satis - fcp) if (satis > 0 and fcp > 0) else None
                    net_marj = ((net_kar / satis) * 100) if (net_kar is not None and satis > 0) else None
                    rows_oz.append({
                        "SKU": u["sku"],
                        "Ürün Adı": u.get("urun_adi", ""),
                        "Kategori": u.get("kategori", ""),
                        "Marka": u.get("marka", ""),
                        "_stok_yas": int(u.get("stok_gun", 0) or 0),
                        "_stok_renk": u.get("stok_renk", "yok"),
                        "_risk": float(u.get("risk_skor", 0) or 0),
                        "G5F Depo": int(u.get("bizim_stok", 0) or 0),
                        "ITOPYA": int(fs.get("ITOPYA", 0) or 0),
                        "HB": int(fs.get("HB", 0) or 0),
                        "VATAN": int(fs.get("VATAN", 0) or 0),
                        "MONDAY": int(fs.get("MONDAY", 0) or 0),
                        "KANAL": int(fs.get("KANAL", 0) or 0),
                        "Toplam": int(u.get("toplam_stok", u.get("bizim_stok", 0)) or 0),
                        "FOB ($)": (float(fob) if ith_var else None),
                        "Son FOB ($)": (float(son_fob) if (ith_var and son_fob) else None),
                        "Maliyet %": float(maliyet_yuzde) if maliyet_yuzde is not None else None,
                        "Final Cost ($)": (float(fcp) if ith_var else None),
                        "Son Maliyet ($)": (float(son_fcp) if (ith_var and son_fcp) else None),
                        "Satış ($)": float(satis or 0),
                        "Net Marj (%)": float(net_marj) if net_marj is not None else None,
                        "Net Kar ($)": float(net_kar) if net_kar is not None else None,
                    })
                _toplam_oz = len(rows_oz)
                _zarar_say = sum(1 for r in rows_oz
                                 if r.get("Net Kar ($)") is not None and r.get("Net Kar ($)") < 0)
                # Filtre + sıralama uygula
                if f_ara_oz and f_ara_oz != "Tümü":
                    _sel_sku = f_ara_oz.split(" — ")[0].strip()
                    rows_oz = [r for r in rows_oz if str(r.get("SKU") or "").strip() == _sel_sku]
                if f_kat_oz != "Tümü":
                    rows_oz = [r for r in rows_oz if tr_kucuk(r.get("Kategori")) == f_kat_oz]
                if f_mar_oz != "Tümü":
                    rows_oz = [r for r in rows_oz if (r.get("Marka") or "").strip() == f_mar_oz]
                if _sadece_zarar:
                    rows_oz = [r for r in rows_oz
                               if r.get("Net Kar ($)") is not None and r.get("Net Kar ($)") < 0]
                _sk_oz = _sira_map_oz.get(f_sira_oz, "_stok_yas")
                _rev_oz = (f_yon_oz == "Azalan")
                if _sk_oz == "SKU":
                    rows_oz.sort(key=lambda r: str(r.get("SKU") or "").lower(), reverse=_rev_oz)
                else:
                    _dolu = [r for r in rows_oz if r.get(_sk_oz) not in (None, "")]
                    _bos = [r for r in rows_oz if r.get(_sk_oz) in (None, "")]
                    _dolu.sort(key=lambda r: float(r.get(_sk_oz) or 0), reverse=_rev_oz)
                    rows_oz = _dolu + _bos

                st.caption(f"📦 {len(rows_oz)} / {_toplam_oz} ürün gösteriliyor"
                           + (f"  ·  ⚠️ {_zarar_say} ürün zararına satılıyor (satış < paçal)" if _zarar_say else ""))
                df_oz = pd.DataFrame(rows_oz)
                if df_oz.empty:
                    st.info("Henüz ürün yok.")
                else:
                    # ── Ürün tablosu: ortak tablo_html (Aşama 4b — elle yazılmış HTML kaldırıldı) ──
                    _YAS_RENK = {"yesil": "yesil2", "sari": "amber", "turuncu": "amber", "kirmizi": "kirmizi"}

                    def _para_h(v, renk="metin", kalin=False):
                        """0/boş → '—' (silik); doluysa $ TR biçimi."""
                        try:
                            f = float(v)
                        except (TypeError, ValueError):
                            return None
                        return renkli(f"${tr_sayi(f, 2)}", renk, kalin=kalin) if f else None

                    def _isaret_h(v, bicim):
                        """+ yeşil · − kırmızı · 0 düz · None '—'."""
                        if v is None:
                            return None
                        renk = "yesil2" if v > 0 else ("kirmizi" if v < 0 else "mavi")
                        return renkli(bicim(v), renk, kalin=v != 0)

                    satirlar = []
                    for r in rows_oz:
                        nk = r.get("Net Kar ($)")
                        _kanallar = [f"{_kl}:{int(r.get(_kn) or 0)}"
                                     for _kn, _kl in (("ITOPYA", "IT"), ("HB", "HB"), ("VATAN", "VT"), ("MONDAY", "MN"), ("KANAL", "KN"))
                                     if r.get(_kn)]
                        _yas_renk = r.get("_stok_renk", "yok")
                        satirlar.append({
                            "SKU": renkli(r.get("SKU", ""), "metin", kalin=True),
                            "Ürün Adı": _kisalt(r.get("Ürün Adı", ""), 46),
                            "Kategori": r.get("Kategori", "") or None,
                            "Stok Yaşı": renkli(f"{int(r.get('_stok_yas') or 0)}g", _YAS_RENK[_yas_renk], kalin=True)
                                         if _yas_renk in _YAS_RENK else None,
                            "G5F": int(r.get("G5F Depo") or 0) or None,
                            "Kanal Stok": _kisalt(" · ".join(_kanallar), 28) if _kanallar else None,
                            "Toplam": renkli(tr_sayi(int(r.get("Toplam") or 0)), "mavi", kalin=True) if r.get("Toplam") else None,
                            "Paçal FOB": _para_h(r.get("FOB ($)"), "mavi"),
                            "Son FOB": _para_h(r.get("Son FOB ($)"), "mavi"),
                            "Maliyet %": renkli(f"%{tr_sayi(float(r['Maliyet %']), 1)}", "mor") if r.get("Maliyet %") is not None else None,
                            "⭐ Paçal Maliyet": _para_h(r.get("Final Cost ($)"), "amber", kalin=True),
                            "Son Maliyet": _para_h(r.get("Son Maliyet ($)"), "amber", kalin=True),
                            "Satış": _para_h(r.get("Satış ($)"), "metin", kalin=True),
                            "📊 Net Marj %": _isaret_h(r.get("Net Marj (%)"), lambda v: f"%{tr_sayi(v, 1)}"),
                            "💰 Net Kâr $": _isaret_h(nk, lambda v: f"${tr_sayi(v, 2)}"),
                            "_zarar": nk is not None and nk < 0,
                        })
                    st.html(tablo_html(
                        ["SKU", "Ürün Adı", "Kategori", ("Stok Yaşı", "metin", "$", "sag"), ("G5F", "adet"),
                         ("Kanal Stok", "mono"), ("Toplam", "metin", "$", "sag"), ("Paçal FOB", "metin", "$", "sag"),
                         ("Son FOB", "metin", "$", "sag"), ("Maliyet %", "metin", "$", "sag"),
                         ("⭐ Paçal Maliyet", "metin", "$", "sag"), ("Son Maliyet", "metin", "$", "sag"),
                         ("Satış", "metin", "$", "sag"), ("📊 Net Marj %", "metin", "$", "sag"), ("💰 Net Kâr $", "metin", "$", "sag")],
                        satirlar, sik=True,
                        vurgu=lambda r: "kirmizi" if r["_zarar"] else None))
                st.caption("💡 FOB/Maliyet iki türlü: Paçal = adet-ağırlıklı ortalama (kâr/marj buna göre) · Son = en yeni ithalat dosyası · Net Kâr $ = Satış − Paçal Maliyet")

                # ── 📤 Rapor Al — Excel / PDF (ekrandaki filtreye göre) ──
                if rows_oz:
                    _rapor_meta = (f"Kategori: {f_kat_oz} · Marka: {f_mar_oz} · "
                                   f"Sıra: {f_sira_oz} ({f_yon_oz})"
                                   + (" · Sadece zararına" if _sadece_zarar else ""))
                    with st.expander(f"📤 Rapor Al — Excel / PDF  ·  {len(rows_oz)} ürün (filtreye göre)", expanded=False):
                        st.caption(f"Aktif filtre → {_rapor_meta}")
                        _rr1, _rr2 = st.columns(2)
                        with _rr1:
                            if st.button("Excel Oluştur", use_container_width=True, type="primary", key="oz_rapor_excel", icon=":material/table_view:"):
                                from .rapor import tum_urunler_excel
                                import tempfile
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as _tmp:
                                    _tp = _tmp.name
                                _ok, _msg = tum_urunler_excel(rows_oz, _tp, _rapor_meta)
                                if _ok:
                                    with open(_tp, "rb") as _f:
                                        st.download_button("Excel İndir", _f.read(),
                                            f"Tum_Urunler_{tr_now().strftime('%Y%m%d_%H%M')}.xlsx",
                                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                            use_container_width=True, key="oz_rapor_excel_dl", icon=":material/download:")
                                    os.unlink(_tp)
                                else:
                                    st.error(_msg)
                        with _rr2:
                            if st.button("PDF Oluştur", use_container_width=True, key="oz_rapor_pdf", icon=":material/picture_as_pdf:"):
                                from .rapor import tum_urunler_pdf
                                import tempfile
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as _tmp:
                                    _tp = _tmp.name
                                _ok, _msg = tum_urunler_pdf(rows_oz, _tp, _rapor_meta)
                                if _ok:
                                    with open(_tp, "rb") as _f:
                                        st.download_button("PDF İndir", _f.read(),
                                            f"Tum_Urunler_{tr_now().strftime('%Y%m%d_%H%M')}.pdf",
                                            mime="application/pdf",
                                            use_container_width=True, key="oz_rapor_pdf_dl", icon=":material/download:")
                                    os.unlink(_tp)
                                else:
                                    st.error(_msg)
            if st.button("Tüm Ürünler Özet — filtrele, sırala, incele", key="btn_urun_ozet", use_container_width=True, icon=":material/table_view:"):
                _dlg_urunler_ozet()

            # KALICI PANEL — @st.dialog DEĞİL.
            # Dialog, st.rerun() çağrıldığında kapanıyordu; her kayıttan sonra
            # düğmeye basıp yeniden açmak gerekiyordu. Normal panel açık kalır,
            # kaydettikten sonra listeden başka ürün seçip devam edebilirsin.
            def _dlg_urun_duzenle():
                st.caption("Açılır listeden ürünü seç, alanları düzenle, **Kaydet**'e bas. "
                           "Panel açık kalır — arka arkaya birden çok ürün düzenleyebilirsin.")
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
                            d_satis = st.number_input("Genel Satış ($)", value=float(_u.get("satis_fiyati", 0) or 0), min_value=0.0, step=1.0, format="%.4f",
                                                      help="Genel/liste fiyatı — kâr marjı ve dashboard bundan hesaplanır.")
                        with fc4:
                            d_stok = st.number_input("G5F Depo", value=int(_u.get("bizim_stok", 0) or 0), min_value=0, step=1)

                        # ── YURT İÇİ ALIM MALİYETİ ──
                        # Kaspersky, mouse pad gibi ithalatı olmayan ürünlerin
                        # maliyeti hiçbir yerden gelmiyordu; raporlarda marj %100
                        # çıkıyordu. Burası tüm raporları besleyen tek giriş noktası.
                        from shared.utils import sku_anahtar as _skn_kart
                        _ith_pacal = 0.0
                        try:
                            from ithalat.database import get_sku_maliyet_ozet as _gsmo
                            for _s2, _v2 in (_gsmo() or {}).items():
                                if _skn_kart(_s2) == _skn_kart(_sec_sku):
                                    _ith_pacal = float(_v2.get("pacal_final") or 0)
                                    break
                        except Exception:
                            _ith_pacal = 0.0

                        _alis_mevcut = float(_u.get("alis_fiyati", 0) or 0)
                        st.markdown("**\U0001F4B5 Birim Maliyet ($)**")
                        if _ith_pacal > 0:
                            st.info(
                                "Bu ürünün **ithalat paçalı** var: "
                                "**${}**. Raporlarda o kullanılır — aşağıdaki alan "
                                "yalnız yurt içinden alınan, ithalatı olmayan ürünler "
                                "içindir.".format(tr_sayi(_ith_pacal, 4)))
                            d_alis = st.number_input(
                                "Yurt içi alış maliyeti ($) — bu üründe kullanılmıyor",
                                value=_alis_mevcut, min_value=0.0, step=0.01,
                                format="%.4f", key="urun_alis_f")
                        else:
                            d_alis = st.number_input(
                                "Yurt içi alış maliyeti ($) — birim başına, nakliye dahil",
                                value=_alis_mevcut, min_value=0.0, step=0.01,
                                format="%.4f", key="urun_alis_f",
                                help="Bu ürünün ithalat dosyası yok. Buraya girdiğin maliyet "
                                     "Kâr/P&L, marka/kategori kırılımı ve tüm satış "
                                     "raporlarında kullanılır. 0 bırakırsan marj %100 "
                                     "görünmeye devam eder.")
                            if _alis_mevcut <= 0:
                                st.warning(
                                    "\u26a0\ufe0f Maliyet girilmemiş — bu ürünün satışları "
                                    "raporlarda **%100 marj** gösterir.")

                        # Müşteri bazlı satış fiyat listesi (ana müşteriler hazır + satır ekleyerek yeni müşteri)
                        from .database import ANA_MUSTERILER as _ANA_MUST
                        _mevcut_liste = _u.get("satis_fiyat_listesi") or {}
                        _musteriler = list(_ANA_MUST) + [m for m in _mevcut_liste if m not in _ANA_MUST]
                        _liste_df = pd.DataFrame(
                            [{"Müşteri": m, "Fiyat ($)": float(_mevcut_liste.get(m, 0) or 0)} for m in _musteriler]
                        )
                        st.markdown("**🏷️ Satış Fiyat Listesi (müşteri bazlı)** — ana müşteriler hazır gelir; "
                                    "müşteriye özel fiyat gir. **Satır ekleyip** yeni müşteri de yazabilirsin (0 bıraktığın satır kaydedilmez).")
                        _liste_edit = st.data_editor(
                            _liste_df, num_rows="dynamic", use_container_width=True, key="urun_fiyat_liste",
                            column_config={
                                "Müşteri": st.column_config.TextColumn("Müşteri", required=False),
                                "Fiyat ($)": st.column_config.NumberColumn("Fiyat ($)", min_value=0.0, step=1.0, format="%.4f"),
                            },
                        )
                        d_eol = st.checkbox(
                            "⛔ EOL — üretimi/satışı sonlandı (bu ürüne sipariş ÖNERİLMESİN)",
                            value=bool(_u.get("eol")))

                        if st.form_submit_button("Kaydet", type="primary", use_container_width=True, icon=":material/save:"):
                            from .database import upsert_urun as _upsert_urun
                            # Fiyat listesini editörden topla
                            _yeni_liste = {}
                            try:
                                for _, _r in _liste_edit.iterrows():
                                    _m = str(_r.get("Müşteri", "") or "").strip()
                                    _fy = float(_r.get("Fiyat ($)", 0) or 0)
                                    if _m and _fy != 0:
                                        _yeni_liste[_m] = _fy
                            except Exception:
                                _yeni_liste = {}
                            try:
                                _upsert_urun(
                                    _sec_sku, d_ad.strip(), d_kat.strip(),
                                    _u.get("marka", "") or "", float(d_satis or 0),
                                    float(d_alis or 0), float(_u.get("hedef_kar_marji", 0) or 0),
                                    _u.get("ozellikler", "") or "", int(d_stok or 0),
                                    int(_u.get("trendyol_stok", 0) or 0),
                                    satis_fiyat_listesi=_yeni_liste, eol=d_eol,
                                )
                                st.cache_data.clear()
                                # Panel AÇIK kalsın: bayrağı koru, seçili ürünü
                                # hatırla. rerun listeyi tazeler ama panel kapanmaz.
                                st.session_state["urun_duz_acik"] = True
                                st.session_state["_urun_duz_son"] = _sec_sku
                                st.toast(f"✅ {_sec_sku} güncellendi", icon="✅")
                                st.rerun()
                            except Exception as _e:
                                st.error(f"Kaydedilemedi: {_e}")

                    # ── Yanlış girilen stok kartını sil ──
                    st.markdown("<div style='height:1px;background:color-mix(in srgb,var(--k-metin) 6%,transparent);margin:12px 0 8px'></div>",
                                unsafe_allow_html=True)
                    _sil_onay = st.checkbox(f"⚠️ '{_sec_sku}' stok kartını kalıcı olarak sil", key="urun_sil_onay")
                    if st.button("Stok Kartını Sil", key="urun_sil_btn",
                                 disabled=not _sil_onay, use_container_width=True, icon=":material/delete:"):
                        from .database import sil_urun as _sil_urun
                        try:
                            _sil_urun(_sec_sku)
                            st.cache_data.clear()
                            st.session_state["urun_duz_acik"] = True
                            st.session_state.pop("_urun_duz_son", None)   # silinen ürünü unutma
                            st.session_state.pop("urun_duzen_sec", None)
                            st.toast(f"🗑️ {_sec_sku} silindi", icon="🗑️")
                            st.rerun()
                        except Exception as _e:
                            st.error(f"Silinemedi: {_e}")
            # Panel durumu session_state'te tutulur → rerun'da kaybolmaz.
            _duz_acik = st.session_state.get("urun_duz_acik", False)
            if st.button(("✖️ Ürün Düzenle — kapat" if _duz_acik else "✏️ Ürün Düzenle"),
                         key="btn_urun_duz", use_container_width=True,
                         type=("secondary" if _duz_acik else "primary")):
                st.session_state["urun_duz_acik"] = not _duz_acik
                st.rerun()
            if st.session_state.get("urun_duz_acik"):
                with st.container(border=True):
                    _dlg_urun_duzenle()
    
    
    
            st.markdown("---")
            st.markdown('<div style="font-size:13px;font-weight:700;color:var(--k-soluk);letter-spacing:1px;text-transform:uppercase;margin:8px 0 8px;display:flex;align-items:center;gap:8px"><span style="width:4px;height:14px;border-radius:3px;background:linear-gradient(180deg,var(--k-mavi),var(--k-mavi));display:inline-block"></span>🚢 Yoldaki Ürün Durumu</div>', unsafe_allow_html=True)
            _yr = urun.get("yol_renk", "yok")
            _ymik = urun.get("yol_miktar", 0)
            _ymsg = urun.get("yol_mesaj", "")
            _yol_map = {"yesil": ("rgba(34,197,94,0.10)", trenk("yesil2"), "🟢", f"{_ymik} adet yolda · {_ymsg}"), "sari": ("rgba(245,158,11,0.10)", trenk("amber"), "🟡", f"{_ymik} adet yolda · {_ymsg}"), "kirmizi": ("rgba(239,68,68,0.10)", trenk("kirmizi"), "🔴", _ymsg)}
            _yb, _yc, _yi, _yt = _yol_map.get(_yr, ("rgba(148,163,184,0.08)", trenk("soluk"), "⚪", "Yolda ürün kaydı bulunmuyor."))
            st.markdown(f'<div style="background:{_yb};border-left:3px solid {_yc};border-radius:7px;padding:8px 12px;font-size:13px;color:{_yc};font-weight:600;display:inline-block">{_yi} {_yt}</div>', unsafe_allow_html=True)


        elif sayfa == "💵  Maliyet Girişi":
            st.markdown(_sb("💵 Ürün Yönetimi", "Maliyet Girişi"), unsafe_allow_html=True)
            st.markdown(
                '<div class="alt-baslik">Yurt içinden alınan ürünlerin birim maliyeti. '
                'İthal ettiğin ürünler burada <b>yok</b> — onların maliyeti ithalat '
                'paçalından otomatik gelir. Girdiğin maliyet Kâr/P&L, kırılımlar ve '
                'tüm satış raporlarına yansır.</div>',
                unsafe_allow_html=True)

            from shared.utils import sku_anahtar as _skn_m
            from .database import (get_yurtici_kategoriler as _gyk,
                                   set_yurtici_kategoriler as _syk)
            # ÖLÇÜT: KATEGORİ. "İthalatta geçiyor mu" ölçütü tek başına yetmedi
            # çünkü bazı ürünlerin SKU yazımı iki tarafta farklı (F11PA650BWM ↔
            # F11PA650BBM) ve o ürünler yanlışlıkla listeye düşüyordu.
            _yurtici_kat = _gyk()

            # get_urunler() bu modülde YOK (satis modülünde). Ham urunler
            # tablosunu doğrudan çekiyoruz — upsert için alis_fiyati, bizim_stok,
            # satis_fiyat_listesi gibi TÜM alanlar gerekiyor.
            try:
                from .database import get_client as _gc_m
                _tum_u = (_gc_m().table("urunler").select("*")
                          .order("urun_adi").execute().data) or []
            except Exception as _e_m:
                _tum_u = []
                st.error("Ürün listesi alınamadı: {}".format(str(_e_m)[:120]))
            _satirlar = []
            _kat_norm = {str(k).strip().lower() for k in _yurtici_kat}
            for _u3 in _tum_u:
                _sk = _u3.get("sku", "")
                if str(_u3.get("kategori", "") or "").strip().lower() not in _kat_norm:
                    continue                       # yurt içi kategorisinde değil
                _satirlar.append({
                    "SKU": _sk,
                    "Ürün": _u3.get("urun_adi", "") or "",
                    "Kategori": _u3.get("kategori", "") or "",
                    "Maliyet ($)": float(_u3.get("alis_fiyati", 0) or 0),
                })
            _satirlar.sort(key=lambda r: (r["Maliyet ($)"] > 0, r["Kategori"], r["SKU"]))

            with st.expander("⚙️ Hangi kategoriler yurt içi? ({} seçili)".format(len(_yurtici_kat))):
                st.caption("Yeni bir yurt içi ürün grubu aldığında buraya ekle — "
                           "kodu değiştirmeye gerek yok.")
                _tum_kat = sorted({str(u.get("kategori", "") or "").strip()
                                   for u in _tum_u if str(u.get("kategori", "") or "").strip()})
                _sec_kat = st.multiselect("Yurt içi kategoriler", _tum_kat,
                                          default=[k for k in _yurtici_kat if k in _tum_kat],
                                          key="mal_kat_sec")
                if st.button("Kategori seçimini kaydet", key="mal_kat_kaydet", icon=":material/save:"):
                    if _syk(_sec_kat):
                        st.cache_data.clear()
                        st.success("✅ Kaydedildi.")
                        st.rerun()
                    else:
                        st.error("Kaydedilemedi (pm_ayarlar tablosu yok olabilir).")

            _eksik = [r for r in _satirlar if r["Maliyet ($)"] <= 0]
            metrik_satiri([
                {"label": "📋 Yurt içi ürün", "value": f"{tr_sayi(len(_satirlar))}", "renk": trenk("mor")},
                {"label": "⚠️ Maliyeti girilmemiş", "value": f"{tr_sayi(len(_eksik))}", "renk": trenk("kirmizi")},
                {"label": "✅ Maliyeti girilmiş",
                 "value": f"{tr_sayi(len(_satirlar) - len(_eksik))}", "renk": trenk("yesil")},
            ])

            if not _satirlar:
                st.info("Tüm ürünlerin ithalat maliyeti var — bu ekranda düzenlenecek ürün yok.")
            else:
                if _eksik:
                    st.warning(
                        "⚠️ **{} ürünün maliyeti girilmemiş.** Bu ürünlerin satışları "
                        "raporlarda **%100 marj** gösterir. Aşağıdaki tabloda "
                        "**Maliyet ($)** kolonunu doldurup kaydet.".format(tr_sayi(len(_eksik))))

                _sadece_eksik = st.checkbox("Yalnız maliyeti girilmemiş ürünleri göster",
                                            value=bool(_eksik), key="mal_sadece_eksik")
                _goster = _eksik if _sadece_eksik else _satirlar
                _ara_m = st.text_input("🔍 Ara (SKU / ürün / kategori)", key="mal_ara").strip().lower()
                if _ara_m:
                    _goster = [r for r in _goster
                               if _ara_m in (r["SKU"] + " " + r["Ürün"] + " " + r["Kategori"]).lower()]

                st.caption("{} ürün gösteriliyor".format(tr_sayi(len(_goster))))
                _duz = st.data_editor(
                    pd.DataFrame(_goster), use_container_width=True, hide_index=True,
                    key="mal_editor", num_rows="fixed",
                    column_config={
                        "SKU": st.column_config.TextColumn("SKU", disabled=True),
                        "Ürün": st.column_config.TextColumn("Ürün", disabled=True),
                        "Kategori": st.column_config.TextColumn("Kategori", disabled=True),
                        "Maliyet ($)": st.column_config.NumberColumn(
                            "Maliyet ($)", min_value=0.0, step=0.0001, format="localized",
                            help="Birim başına, nakliye dahil"),
                    })

                if st.button("Maliyetleri Kaydet", type="primary",
                             use_container_width=True, key="mal_kaydet", icon=":material/save:"):
                    from .database import upsert_urun as _upsert_m
                    _eski_map = {r["SKU"]: r["Maliyet ($)"] for r in _goster}
                    _u_map = {u.get("sku"): u for u in _tum_u}
                    _n, _hata = 0, []
                    for _, _r4 in _duz.iterrows():
                        _sk4 = str(_r4.get("SKU", "") or "").strip()
                        _yeni = float(_r4.get("Maliyet ($)", 0) or 0)
                        if not _sk4 or abs(_yeni - float(_eski_map.get(_sk4, 0))) < 0.00005:
                            continue               # değişmeyen satıra dokunma
                        _uu = _u_map.get(_sk4) or {}
                        try:
                            _upsert_m(
                                _sk4, _uu.get("urun_adi", "") or "", _uu.get("kategori", "") or "",
                                _uu.get("marka", "") or "", float(_uu.get("satis_fiyati", 0) or 0),
                                _yeni, float(_uu.get("hedef_kar_marji", 0) or 0),
                                _uu.get("ozellikler", "") or "", int(_uu.get("bizim_stok", 0) or 0),
                                int(_uu.get("trendyol_stok", 0) or 0),
                                satis_fiyat_listesi=_uu.get("satis_fiyat_listesi") or {},
                                eol=bool(_uu.get("eol")))
                            _n += 1
                        except Exception as _e4:
                            _hata.append("{}: {}".format(_sk4, str(_e4)[:60]))
                    st.cache_data.clear()
                    if _n:
                        st.success("✅ {} ürünün maliyeti güncellendi. "
                                   "Raporlar yeni maliyete göre hesaplanacak.".format(tr_sayi(_n)))
                    if _hata:
                        st.error("Yazılamayan {} kayıt:\n\n".format(len(_hata))
                                 + "\n".join("- " + h for h in _hata[:10]))
                    if not _n and not _hata:
                        st.info("Değişiklik yok.")
                    if _n:
                        st.rerun()

        elif sayfa == "📈  Müşteri Satışları":
            from shared.tarih import hizli_tarih_araligi
            st.markdown(_sb("📈 Ürün Yönetimi", "Müşteri Haftalık Satışları", aciklama="Müşteri (firma) bazında haftalık satış geçmişi · aynı haftada yalnız en güncel yükleme sayılır · geniş aralık seçersen toplam, aralıktaki HAFTALARIN toplamıdır"), unsafe_allow_html=True)
            st.markdown('<div class="sayfa-baslik-cizgi"></div>', unsafe_allow_html=True)
            _bas, _bit = hizli_tarih_araligi(
                "mhs", varsayilan="Geçen hafta",
                secenekler=["Geçen hafta", "Bu ay", "Geçen ay", "Son 30 gün",
                            "Son 90 gün", "Bu yıl", "Geçen yıl", "Tümü", "Özel…"])
            _mc1, _mc2 = st.columns([1, 1.4])
            _firmalar = ["Tümü"] + get_firma_listesi()
            _f = _mc1.selectbox("Müşteri", _firmalar, key="mhs_firma", format_func=firma_gorunen_ad)
            _sku_ara = _mc2.text_input("Ürün / SKU ara", key="mhs_sku",
                                       placeholder="SKU veya ürün adı ile filtrele…")
            _rows = get_musteri_haftalik_satis(_bas, _bit, _f, _sku_ara)
            if not _rows:
                st.info("Bu filtrelerle haftalık satış kaydı bulunamadı.")
            else:
                _df = pd.DataFrame([{
                    "Tarih": str(r.get("yukleme_tarihi", ""))[:10],
                    "Müşteri": firma_gorunen_ad(r.get("firma", "")),
                    "SKU": r.get("sku", ""),
                    "Ürün": (r.get("urun_adi", "") or "")[:45],
                    "Satış": int(r.get("haftalik_satis", 0) or 0) + int(r.get("satis_magaza", 0) or 0),
                    "Stok": int(r.get("stok_miktari", 0) or 0) + int(r.get("stok_magaza", 0) or 0),
                } for r in _rows])
                metrik_satiri([
                    {"label": "📈 Toplam Satış (seçili aralık)", "value": f"{tr_sayi(int(_df['Satış'].sum()))}", "renk": trenk("mor")},
                    {"label": "📦 Toplam Stok", "value": f"{tr_sayi(int(_df['Stok'].sum()))}", "renk": trenk("cyan")},
                    {"label": "👥 Müşteri Sayısı", "value": f"{tr_sayi(int(_df['Müşteri'].nunique()))}", "renk": trenk("yesil")},
                ])

                # ── MÜŞTERİ BAZINDA ÖZET (her müşteri = 1 satır: toplam satış + stok) ──
                st.markdown('<div class="alt-baslik">👥 Müşteri Bazında Özet — her müşteri tek satır (toplam satış + stok)</div>', unsafe_allow_html=True)
                _ozet = (_df.groupby("Müşteri")
                         .agg(**{"Toplam Satış": ("Satış", "sum"),
                                 "Toplam Stok": ("Stok", "sum"),
                                 "SKU Çeşidi": ("SKU", "nunique")})
                         .reset_index()
                         .sort_values("Toplam Satış", ascending=False))
                st.dataframe(_ozet, hide_index=True, use_container_width=True,
                             height=min(60 + len(_ozet) * 36, 420),
                             column_config={
                                 "Toplam Satış": st.column_config.NumberColumn("Toplam Satış", format="localized", step=1),
                                 "Toplam Stok": st.column_config.NumberColumn("Toplam Stok", format="localized", step=1),
                                 "SKU Çeşidi": st.column_config.NumberColumn("SKU Çeşidi", format="localized", step=1),
                             })
                _ind1, _ind2 = st.columns(2)
                _ind1.download_button("Özet CSV indir",
                                      _ozet.to_csv(index=False).encode("utf-8-sig"),
                                      "musteri_ozet.csv", "text/csv", key="mhs_ozet_csv",
                                      use_container_width=True, icon=":material/download:")

                # ── EXCEL (tek dosya, iki sayfa: Özet + Ham Detay) ──
                def _mhs_excel(ozet_df, detay_df):
                    import io as _io
                    _buf = _io.BytesIO()
                    with pd.ExcelWriter(_buf, engine="openpyxl") as _w:
                        ozet_df.to_excel(_w, index=False, sheet_name="Müşteri Özet")
                        detay_df.to_excel(_w, index=False, sheet_name="Ham Detay")
                        # sütun genişliklerini içeriğe göre ayarla (okunabilirlik)
                        for _sn, _d in (("Müşteri Özet", ozet_df), ("Ham Detay", detay_df)):
                            _ws = _w.sheets[_sn]
                            for _i, _kol in enumerate(_d.columns, start=1):
                                _uzun = max([len(str(_kol))] +
                                            [len(str(_v)) for _v in _d[_kol].head(200)])
                                _ws.column_dimensions[
                                    _ws.cell(row=1, column=_i).column_letter
                                ].width = min(max(_uzun + 2, 10), 48)
                            _ws.freeze_panes = "A2"       # başlık satırı sabit
                    return _buf.getvalue()

                _ind2.download_button(
                    "Excel indir (Özet + Detay)",
                    _mhs_excel(_ozet, _df),
                    f"musteri_satislari_{_bas}_{_bit}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="mhs_xlsx", type="primary", use_container_width=True, icon=":material/download:")

                # ── HAM DETAY (isteyen SKU kırılımını görsün) ──
                with st.expander(f"🔎 Ham detay — SKU bazında tüm satırlar ({tr_sayi(len(_df))} kayıt)", expanded=False):
                    st.dataframe(_df, hide_index=True, use_container_width=True, height=460)
                    st.download_button("Detay CSV indir",
                                       _df.to_csv(index=False).encode("utf-8-sig"),
                                       "musteri_haftalik_satis.csv", "text/csv", key="mhs_csv", icon=":material/download:")

            st.markdown("---")
            @st.dialog("📤 Müşteri Satış / Stok Verisi Yükle", width="large")
            def _dlg_musteri_yukle():
                st.markdown("**📅 Haftalık STOK + SATIŞ · Firma Başına 2 Sekme (portal formatları)**")
                st.caption("Sekmeler: `ITOPYA STOK` · `ITOPYA SATIŞ` · `VATAN STOK` · `VATAN SATIŞ` · "
                           "`HEPSİBURADA STOK/SATIŞ` · `MONDAY STOK/SATIŞ`. Her firmanın **kendi portal başlıkları** "
                           "olduğu gibi kalır (STOKKODU/Kod/Sku/Malzeme/Ürün Kodu…). Satışlar SKU ile stokun yanına "
                           "bağlanıp tek özet oluşturulur. **Kategori dosyada gerekmez** — bizim ürün kartından eşlenir; "
                           "boş bırakılan kategori kolonları hata vermez.")
                _dosya_hss = st.file_uploader("Haftalık STOK+SATIŞ Excel'i Seç", type=["xlsx", "xls"], key="mhs_hss_dosya")
                _hss_bas = st.button("Haftalık STOK+SATIŞ Yükle", type="primary",
                                     use_container_width=True, key="mhs_hss_btn",
                                     disabled=not _dosya_hss, icon=":material/upload:")
                if _hss_bas:
                    if not _dosya_hss:
                        st.error("Önce dosya seçin.")
                        st.stop()
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as _tb2:
                        _tb2.write(_dosya_hss.read())
                        _tbp2 = _tb2.name
                    try:
                        with st.spinner("⏳ İçe aktarılıyor…"):
                            _ok2, _msg2 = excel_yukle_haftalik_stok_satis(_tbp2)
                    except Exception as _he:
                        import traceback
                        _ok2 = False
                        _msg2 = f"❌ Beklenmedik hata: {type(_he).__name__}: {str(_he)[:200]}"
                        st.code(traceback.format_exc()[-1500:])
                    finally:
                        try:
                            os.unlink(_tbp2)
                        except Exception:
                            pass
                    st.cache_data.clear()
                    (st.success if _ok2 else st.error)(_msg2)
            if st.button("Müşteri Satış / Stok Verisi Yükle", key="btn_mus_yuk", use_container_width=True, icon=":material/upload:"):
                _dlg_musteri_yukle()

        elif sayfa == "🎯  Kampanya Takip":
            # Yeni ekran: kayranpm/kampanya.py (hesaplar kampanya_hesap.py'de, testli)
            from .kampanya import render as _kampanya_ekrani
            _kampanya_ekrani()

        elif sayfa == "📦  Sipariş Önerisi":
            from .database import get_uretim_suresi, set_uretim_suresi
            _esik = get_uretim_suresi()
            st.markdown(_sb("📦 Ürün Yönetimi", "Sipariş Önerisi", aciklama=f"{_esik} günden az stok kalan ürünler · Otomatik öneri"), unsafe_allow_html=True)
            st.markdown('<div class="sayfa-baslik-cizgi"></div>', unsafe_allow_html=True)

            with st.popover(f"⚙️ Sipariş eşiği (üretim/tedarik süresi) — şu an {_esik} gün", use_container_width=False):
                st.caption("Stok bu kadar günde biteceği zaman 'sipariş ver' uyarısı çıkar. "
                           "Üretim/tedarik sürenize göre ayarlayın (varsayılan 135 gün).")
                _e1, _e2 = st.columns([2, 1])
                _yeni_esik = _e1.number_input("Eşik (gün)", min_value=1, max_value=730, value=int(_esik),
                                              step=5, key="uretim_suresi_input")
                _e2.markdown("<br>", unsafe_allow_html=True)
                if _e2.button("Kaydet", use_container_width=True, key="uretim_suresi_kaydet", icon=":material/save:"):
                    if set_uretim_suresi(int(_yeni_esik)):
                        st.cache_data.clear()
                        st.toast(f"✅ Sipariş eşiği {int(_yeni_esik)} güne ayarlandı", icon="✅")
                        st.rerun()
                    else:
                        st.error("Kaydedilemedi. 'pm_ayarlar' tablosu eksik olabilir — Supabase'de şu SQL'i çalıştırın:")
                        st.code("create table if not exists pm_ayarlar (anahtar text primary key, deger text);\n"
                                "alter table pm_ayarlar disable row level security;", language="sql")

            try:
                siparis_listesi = siparis_onerisi_listesi()
                urun_data = tum_urunler_listesi()
                urun_dict = {u["sku"]: u for u in urun_data}
            except Exception as e:
                _log.error("Hata: %s", e)
                st.error(f"Veri yüklenemedi: {e}")
                st.stop()
    
            if not siparis_listesi:
                st.success(f"✅ Tüm ürünlerde {_esik} günden fazla stok var, sipariş gerekmiyor!")
                st.stop()
    
            # Özet
            acil = [u for u in siparis_listesi if u.get("siparis_durum") == "acil"]
            yaklasan = [u for u in siparis_listesi if u.get("siparis_durum") == "yaklasıyor"]
            planlama = [u for u in siparis_listesi if u.get("siparis_durum") == "planlama"]
    
            metrik_satiri([
                {"label": "🔴 ACİL", "value": f"{tr_sayi(len(acil))}", "renk": trenk("kirmizi")},
                {"label": "🟠 Yaklaşıyor (30 gün)", "value": f"{tr_sayi(len(yaklasan))}", "renk": trenk("amber")},
                {"label": "🟡 Planlama (60 gün)", "value": f"{tr_sayi(len(planlama))}", "renk": trenk("amber")},
            ])

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
                    alt.append(f'💵 ${tr_sayi(fcp)}→${tr_sayi(satis)}')
                alt_str = "  ·  ".join(alt)

                c1, c2, c3 = st.columns([6, 1.2, 1.7])
                with c1:
                    st.markdown(
                        f'<div style="background:{dt};border-left:3px solid {brd};border-radius:8px;padding:8px 12px;">'
                        f'<div style="font-size:13px;font-weight:600;color:var(--k-metin);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                        f'{ik} {urun["urun_adi"]} <span style="color:var(--k-soluk);font-size:11px;font-family:monospace;">{sku}</span></div>'
                        f'<div style="font-size:11px;color:var(--k-soluk);margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                        f'{alt_str}  ·  <span style="color:var(--k-amber);font-weight:600;">💡 {oneri} adet</span></div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                with c2:
                    miktar = st.number_input("Miktar", min_value=1, value=max(oneri, 1),
                                             key=f"sp_miktar_{sku}", label_visibility="collapsed")
                with c3:
                    if st.button("Sipariş Ekle", key=f"sp_btn_{sku}", use_container_width=True, icon=":material/inventory_2:"):
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
                    if d == "onaylandi":   return ["background-color:color-mix(in srgb,var(--k-yesil) 25%,transparent); color:var(--k-yesil2)"]*len(row)
                    if d == "reddedildi":  return ["background-color:color-mix(in srgb,var(--k-kirmizi) 25%,transparent); color:var(--k-kirmizi)"]*len(row)
                    return ["background-color:color-mix(in srgb,var(--k-amber) 35%,transparent); color:var(--k-amber2)"]*len(row)
    
                render_renkli_tablo(
                    df_sp,
                    kisalt={"Ürün": 42},
                    satir_durum=("Durum", {"onaylandi": "rk-grn", "reddedildi": "rk-red", "bekliyor": "rk-yel"}),
                    gizle=["ID"],
                )
    
                col_o1, col_o2 = st.columns(2)
                with col_o1:
                    onayla_id = st.number_input("Onaylanacak ID", min_value=1, step=1, key="onayla_id")
                    if st.button("Onayla", key="onayla_btn", use_container_width=True, icon=":material/check_circle:"):
                        from .database import onayla_siparis
                        onayla_siparis(int(onayla_id))
                        st.toast("Onaylandı!")
                        st.rerun()
                with col_o2:
                    reddet_id = st.number_input("Reddedilecek ID", min_value=1, step=1, key="reddet_id")
                    if st.button("Reddet", key="reddet_btn", use_container_width=True, icon=":material/close:"):
                        from .database import reddet_siparis
                        reddet_siparis(int(reddet_id))
                        st.warning("Reddedildi.")
                        st.rerun()

    
    
        elif sayfa == "🔖  Ref No Takibi":
            from .ref_no import render as _ref_render
            _ref_render()

        elif sayfa == "📂  Veri Yükleme":
            st.markdown(_sb("📂 Ürün Yönetimi", "Veri Yükleme", aciklama="Excel yükle · Geçmiş yüklemeleri gör · Veriyi yönet"), unsafe_allow_html=True)
            st.markdown('<div class="sayfa-baslik-cizgi"></div>', unsafe_allow_html=True)

            # 💲 Toplu Satış Fiyatı & Marj
            @st.dialog("💲 Toplu Satış Fiyatı & Marj — paçal maliyetten fiyat öner", width="large")
            def _dlg_toplu_fiyat():
                from .database import toplu_satis_kaydet as _satis_kaydet, _hepsi as _hepsi_s
                try:
                    from ithalat.database import get_sku_maliyet_ozet as _ith_maliyet
                    _pacal_map = _ith_maliyet() or {}
                except Exception:
                    _pacal_map = {}
                try:
                    _ur_s = _hepsi_s("urunler", "sku, urun_adi, satis_fiyati, hedef_kar_marji",
                                     "urun_adi") or []
                except Exception as _e_s:
                    _ur_s = []
                    st.warning(f"Ürünler okunamadı: {_e_s}")
                if not _ur_s:
                    st.info("Henüz ürün yok.")
                else:
                    _fiyatsiz = sum(1 for u in _ur_s if not (u.get("satis_fiyati") or 0))
                    st.caption(f"Toplam {len(_ur_s)} ürün · satış fiyatı girilmemiş {_fiyatsiz}. "
                               "Hedef marjı gir → 🪄 Öner ile paçaldan satış fiyatı hesapla → düzelt → 💾 Kaydet.")
                    _sc1, _sc2, _sc3 = st.columns([1, 1, 1])
                    _hedef_marj = _sc1.number_input("Hedef marj (%)", min_value=0.0, max_value=500.0,
                                                    value=25.0, step=5.0, key="satis_marj")
                    _sadece_fiyatsiz = _sc2.checkbox("Sadece fiyatsız ürünler", value=False, key="satis_sadece")
                    if _sc3.button("Marj'dan Satış Öner", use_container_width=True, key="satis_oner", icon=":material/auto_fix_high:"):
                        _on = {}
                        for u in _ur_s:
                            _p = (_pacal_map.get(u["sku"], {}) or {}).get("pacal_final", 0) or 0
                            if _p > 0:
                                _on[u["sku"]] = round(_p * (1 + _hedef_marj / 100.0), 2)
                        st.session_state["_satis_oneri"] = _on
                        st.session_state["_satis_oneri_v"] = st.session_state.get("_satis_oneri_v", 0) + 1
                        st.toast(f"🪄 {len(_on)} ürün için satış fiyatı önerildi (marj %{tr_sayi(_hedef_marj)})", icon="🪄")
                        st.rerun()
                    _son = st.session_state.get("_satis_oneri", {})
                    st.caption("💡 Satış ($) hücresini elle de değiştirebilirsin. Paçal = İthalat maliyeti · "
                               "Marj % satışı değiştirince kaydederken yeniden hesaplanır.")
                    _liste_s = [u for u in _ur_s if not (u.get("satis_fiyati") or 0)] if _sadece_fiyatsiz else _ur_s
                    _rows_s = []
                    for u in _liste_s:
                        _p = (_pacal_map.get(u["sku"], {}) or {}).get("pacal_final", 0) or 0
                        _ps = (_pacal_map.get(u["sku"], {}) or {}).get("son_final", 0) or 0
                        _satis = _son.get(u["sku"]) if u["sku"] in _son else (u.get("satis_fiyati") or 0)
                        _marj = ((_satis / _p - 1) * 100) if (_p > 0 and _satis) else 0.0
                        _rows_s.append({
                            "SKU": u["sku"], "Ürün Adı": u.get("urun_adi", ""),
                            "Paçal ($)": round(_p, 2), "Son ($)": round(_ps, 2),
                            "Satış ($)": round(float(_satis or 0), 2),
                            "Marj %": round(_marj, 1),
                        })
                    _df_s = pd.DataFrame(_rows_s)
                    _ed_s_key = f"satis_editor_{int(_sadece_fiyatsiz)}_{st.session_state.get('_satis_oneri_v', 0)}"
                    _edited_s = st.data_editor(
                        _df_s, use_container_width=True, height=420, hide_index=True, key=_ed_s_key,
                        column_config={
                            "SKU": st.column_config.TextColumn("SKU", disabled=True, width="small"),
                            "Ürün Adı": st.column_config.TextColumn("Ürün Adı", disabled=True, width="large"),
                            "Paçal ($)": st.column_config.NumberColumn("Paçal ($)", disabled=True, format="dollar"),
                            "Son ($)": st.column_config.NumberColumn("Son ($)", disabled=True, format="dollar", help="En yeni ithalat dosyasındaki maliyet (referans · öneri paçala göre)"),
                            "Satış ($)": st.column_config.NumberColumn("Satış ($)", min_value=0.0, step=1.0, format="$%.2f"),
                            "Marj %": st.column_config.NumberColumn("Marj %", disabled=True, format="%.1f%%"),
                        },
                    )
                    if st.button("Satış Fiyatlarını Kaydet", type="primary", key="satis_kaydet_btn", icon=":material/save:"):
                        _map_s = {}
                        for _, r in _edited_s.iterrows():
                            _satis_v = float(r.get("Satış ($)") or 0)
                            _p = float(r.get("Paçal ($)") or 0)
                            _marj_v = ((_satis_v / _p - 1) * 100) if (_p > 0 and _satis_v) else 0.0
                            _map_s[str(r["SKU"])] = {"satis_fiyati": _satis_v, "hedef_kar_marji": round(_marj_v, 1)}
                        with st.spinner("Kaydediliyor..."):
                            _oks, _hts = _satis_kaydet(_map_s)
                        st.session_state.pop("_satis_oneri", None)
                        st.toast(f"✅ {_oks} ürün fiyatı kaydedildi" + (f" · {_hts} hata" if _hts else ""), icon="✅")
                        st.rerun()
            if st.button("Toplu Satış Fiyatı & Marj — paçal maliyetten fiyat öner", key="btn_top_fiy", use_container_width=True, icon=":material/attach_money:"):
                _dlg_toplu_fiyat()

            # 🏷️ Toplu Kategori & Marka — markası/kategorisi boş ürünleri tek tabloda etiketle
            @st.dialog("🏷️ Toplu Kategori & Marka — ürünleri tek tabloda etiketle", width="large")
            def _dlg_toplu_kat_marka():
                from .database import (kategori_oner as _kat_oner,
                                       marka_oner as _marka_oner,
                                       toplu_kategori_marka_kaydet as _km_kaydet,
                                       kategori_standartlastir as _kat_std,
                                       _hepsi as _hepsi_kat)
                try:
                    # _hepsi → sayfalamalı; 1000'den fazla üründe liste kesilmesin
                    _ur_kat = _hepsi_kat("urunler", "sku, urun_adi, kategori, marka", "urun_adi") or []
                except Exception as _e_kat:
                    _ur_kat = []
                    st.warning(f"Ürünler okunamadı: {type(_e_kat).__name__}: {_e_kat}")
                if not _ur_kat:
                    st.info("Henüz ürün yok.")
                    return
                _kbos = sum(1 for u in _ur_kat if not (u.get("kategori") or "").strip())
                _mbos = sum(1 for u in _ur_kat if not (u.get("marka") or "").strip())
                st.caption(f"Toplam {len(_ur_kat)} ürün · kategorisiz **{_kbos}** · markasız **{_mbos}**. "
                           "Önce 🪄 Otomatik Öner'e bas, kalanları elle yaz, 💾 Kaydet. "
                           "Markası boş ürünler Satış → P&L'de **DİĞER** grubuna düşer.")
                _kc1, _kc2, _kc3 = st.columns([1, 1, 1])
                _sadece_bos = _kc1.checkbox("Sadece eksik olanlar", value=True, key="kat_sadece_bos",
                                            help="Kategorisi veya markası boş olan ürünleri gösterir.")
                if _kc2.button("Otomatik Öner (kategori + marka)", use_container_width=True, key="kat_oto", icon=":material/auto_fix_high:"):
                    _onk = {u["sku"]: _kat_oner(u.get("urun_adi", "")) for u in _ur_kat
                            if _kat_oner(u.get("urun_adi", ""))}
                    _onm = {u["sku"]: _marka_oner(u.get("urun_adi", "")) for u in _ur_kat
                            if _marka_oner(u.get("urun_adi", ""))}
                    st.session_state["_kat_oneri"] = _onk
                    st.session_state["_marka_oneri"] = _onm
                    st.session_state["_kat_oneri_v"] = st.session_state.get("_kat_oneri_v", 0) + 1
                    st.toast(f"🪄 {len(_onk)} kategori · {len(_onm)} marka önerildi", icon="🪄")
                    st.rerun()
                if _kc3.button("Kategori Standartlaştır", use_container_width=True, key="kat_std_btn",
                               help="Aynı kategorinin farklı yazımlarını tek biçime indirger (MONİTÖR / Monitör → monitör).", icon=":material/shuffle:"):
                    with st.spinner("Birleştiriliyor..."):
                        _ds, _hrt = _kat_std()
                    if _ds:
                        st.session_state["_kat_std_ozet"] = " · ".join(f"{e}→{y}" for e, y in list(_hrt.items())[:6])
                        st.toast(f"🔀 {_ds} ürün standart yazıma çevrildi", icon="🔀")
                    else:
                        st.session_state["_kat_std_ozet"] = "Zaten standart — birleştirilecek bir şey yok."
                    st.rerun()
                if st.session_state.get("_kat_std_ozet"):
                    st.caption("🔀 " + st.session_state.pop("_kat_std_ozet"))
                _onk = st.session_state.get("_kat_oneri", {})
                _onm = st.session_state.get("_marka_oneri", {})
                st.caption("💡 **Kategori ve Marka hücrelerine tıklayıp serbestçe yazabilirsin.** "
                           "🪄 Otomatik Öner bilinenleri doldurur; üzerine kendi değerini yazabilirsin.")
                if _sadece_bos:
                    _liste = [u for u in _ur_kat
                              if not (u.get("kategori") or "").strip() or not (u.get("marka") or "").strip()]
                else:
                    _liste = _ur_kat
                if not _liste:
                    st.success("✅ Tüm ürünlerin kategorisi ve markası dolu.")
                    return
                _df_kat = pd.DataFrame([{
                    "SKU": u["sku"],
                    "Ürün Adı": u.get("urun_adi", ""),
                    "Kategori": (_onk.get(u["sku"]) or (u.get("kategori") or "")),
                    "Marka": (_onm.get(u["sku"]) or (u.get("marka") or "")),
                } for u in _liste])
                _ed_key = f"kat_editor_{int(_sadece_bos)}_{st.session_state.get('_kat_oneri_v', 0)}"
                _edited_kat = st.data_editor(
                    _df_kat, use_container_width=True, height=430, hide_index=True, key=_ed_key,
                    column_config={
                        "SKU": st.column_config.TextColumn("SKU", disabled=True, width="small"),
                        "Ürün Adı": st.column_config.TextColumn("Ürün Adı", disabled=True, width="large"),
                        "Kategori": st.column_config.TextColumn(
                            "Kategori", help="Serbest yaz (kasa, monitör, ekran kartı...)"),
                        "Marka": st.column_config.TextColumn(
                            "Marka", help="Serbest yaz (FAZEON, INNO3D, NZXT, MIO, AGI...)"),
                    },
                )
                if st.button("Kategori & Marka Kaydet", type="primary", key="kat_kaydet_btn", icon=":material/save:"):
                    _map = {str(r["SKU"]): {"kategori": str(r.get("Kategori", "") or "").strip(),
                                            "marka": str(r.get("Marka", "") or "").strip()}
                            for _, r in _edited_kat.iterrows()}
                    with st.spinner("Kaydediliyor..."):
                        _okk, _htk = _km_kaydet(_map)
                    st.session_state.pop("_kat_oneri", None)
                    st.session_state.pop("_marka_oneri", None)
                    st.toast(f"✅ {_okk} ürün kaydedildi" + (f" · {_htk} hata" if _htk else ""), icon="✅")
                    st.rerun()

            if st.button("Toplu Kategori & Marka — markasız ürünleri etiketle",
                         key="btn_top_kat_marka", use_container_width=True, icon=":material/sell:"):
                _dlg_toplu_kat_marka()

            # 🧹 'Fazeon ' önekli SKU temizliği — satislar'daki "Fazeon X24F165S" ile
            # urunler'deki "X24F165S" aynı ürün; önek yüzünden eşleşmeyip P&L'de
            # DİĞER'e düşüyor. Arka uç fonksiyonları hazırdı, arayüzü buradan bağlandı.
            @st.dialog("🧹 'Fazeon' Önekli SKU Temizliği", width="large")
            def _dlg_fazeon_sku():
                st.caption("Satış/stok kayıtlarında **'Fazeon ' önekiyle** yazılmış SKU'ları bulur ve "
                           "öneksiz gerçek koduna taşır (örn. `Fazeon X24F165S` → `X24F165S`). "
                           "8 tabloda birden çalışır: ürünler, satışlar, firma stok, kampanyalar, "
                           "yoldaki ürünler, stok yaşı, ithalat kalemleri, sipariş önerileri.")
                with st.spinner("Taranıyor — hiçbir şey yazılmıyor..."):
                    try:
                        _onz = sku_fazeon_temizle_onizle() or []
                    except Exception as _e_fz:
                        st.error(f"Önizleme alınamadı: {type(_e_fz).__name__}: {_e_fz}")
                        return
                if not _onz:
                    st.success("✅ Temizlenecek 'Fazeon' önekli SKU yok — sistem zaten temiz.")
                    return
                _top_kayit = sum(int(i.get("toplam_kayit") or 0) for i in _onz)
                _catisan = sum(1 for i in _onz if i.get("catisma"))
                st.markdown(f"**{len(_onz)} SKU** bulundu · toplam **{tr_sayi(_top_kayit)} kayıt** etkilenecek · "
                            f"**{_catisan}** tanesinin öneksiz hedefi zaten kayıtlı (birleştirilecek).")
                st.dataframe(pd.DataFrame([{
                    "Eski SKU": i["eski"], "Yeni SKU": i["yeni"],
                    "Durum": "🔗 Mevcutla birleşir" if i.get("catisma") else "✏️ Yeniden adlanır",
                    "Kayıt": int(i.get("toplam_kayit") or 0),
                    "Tablolar": ", ".join(f"{t}:{n}" for t, n in (i.get("tablolar") or {}).items()),
                } for i in _onz]), hide_index=True, use_container_width=True, height=300)
                st.warning("⚠️ Bu işlem **geri alınamaz** — 8 tabloda SKU'ları kalıcı olarak değiştirir. "
                           "Uygulamadan önce GitHub → Actions → **Gece Yedeği** iş akışını elle çalıştırıp "
                           "güncel bir yedek indirmen önerilir.")
                _onay = st.checkbox(f"Önizlemeyi inceledim; {len(_onz)} SKU'nun ({tr_sayi(_top_kayit)} kayıt) "
                                    "kalıcı olarak taşınacağını anladım.", key="fz_sku_onay")
                if st.button("Temizliği Uygula", type="primary", disabled=not _onay,
                             use_container_width=True, key="fz_sku_uygula", icon=":material/cleaning_services:"):
                    with st.spinner("Uygulanıyor — tablo tablo taşınıyor..."):
                        _ok_fz, _msg_fz = sku_fazeon_temizle_uygula()
                    st.cache_data.clear()
                    if _ok_fz:
                        st.success(_msg_fz)
                        st.caption("Satış → P&L sayfasını yenilediğinde bu satırlar FAZEON altında görünecek.")
                    else:
                        st.error(_msg_fz)

            if st.button("'Fazeon' Önekli SKU Temizliği — mükerrer SKU'ları birleştir",
                         key="btn_fz_sku", use_container_width=True, icon=":material/cleaning_services:"):
                _dlg_fazeon_sku()

            with st.expander("📋 Excel Şablonunu İndir (ilk kez kullanıyorsanız buradan başlayın)", expanded=False):
                st.markdown('<div style="color:var(--k-soluk);font-size:13px;line-height:1.6;margin-bottom:8px">Aşağıdaki butona tıklayıp örnek şablonu indir, doldur ve yükle.</div>', unsafe_allow_html=True)
                sablon_bytes = create_sample_excel_bytes()
                st.download_button("Şablonu İndir", sablon_bytes, "SABLON_STOK_TAKIP.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/move_to_inbox:")
    
            st.markdown("---")
    
            # Disa Aktar (eski Raporlar)
            @st.dialog("📤 Dışa Aktar — Excel / PDF Rapor", width="large")
            def _dlg_disa_aktar():
                _de1, _de2 = st.columns(2)
                with _de1:
                    st.markdown('<div style="color:var(--k-mavi);font-size:13px;font-weight:700;letter-spacing:.5px;margin-bottom:4px">📊 EXCEL RAPORU</div>', unsafe_allow_html=True)
                    st.markdown('<div style="color:var(--k-soluk);font-size:11px;line-height:1.6;margin-bottom:8px">Dashboard, Stok Yayılımı ve Sipariş Önerileri — 3 sekme, renkli.</div>', unsafe_allow_html=True)
                    if st.button("Excel Raporu Oluştur", use_container_width=True, type="primary", key="vy_excel_rapor", icon=":material/table_view:"):
                        from .rapor import excel_rapor_olustur
                        import tempfile
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as _tmp:
                            _tmp_path = _tmp.name
                        _ok, _msg = excel_rapor_olustur(_tmp_path)
                        if _ok:
                            with open(_tmp_path, "rb") as _f:
                                st.download_button("Excel İndir", _f.read(), f"Stok_Raporu_{tr_now().strftime('%Y%m%d_%H%M')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, key="vy_excel_dl", icon=":material/download:")
                            os.unlink(_tmp_path)
                        else:
                            st.error(_msg)
                with _de2:
                    st.markdown('<div style="color:var(--k-pembe);font-size:13px;font-weight:700;letter-spacing:.5px;margin-bottom:4px">📑 PDF RAPORU</div>', unsafe_allow_html=True)
                    st.markdown('<div style="color:var(--k-soluk);font-size:11px;line-height:1.6;margin-bottom:8px">A4 yatay, yazdırmaya hazır özet rapor.</div>', unsafe_allow_html=True)
                    if st.button("PDF Raporu Oluştur", use_container_width=True, key="vy_pdf_rapor", icon=":material/picture_as_pdf:"):
                        from .rapor import pdf_rapor_olustur
                        import tempfile
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as _tmp:
                            _tmp_path = _tmp.name
                        _ok, _msg = pdf_rapor_olustur(_tmp_path)
                        if _ok:
                            with open(_tmp_path, "rb") as _f:
                                st.download_button("PDF İndir", _f.read(), f"Stok_Raporu_{tr_now().strftime('%Y%m%d_%H%M')}.pdf", mime="application/pdf", use_container_width=True, key="vy_pdf_dl", icon=":material/download:")
                            os.unlink(_tmp_path)
                        else:
                            st.error(_msg)
            if st.button("Dışa Aktar — Excel / PDF Rapor", key="btn_disa_akt", use_container_width=True, icon=":material/upload:"):
                _dlg_disa_aktar()

            st.markdown("---")
            st.markdown("---")
            st.markdown('<div style="font-size:13px;font-weight:700;color:var(--k-mor2);letter-spacing:1px;text-transform:uppercase;margin:8px 0 8px;display:flex;align-items:center;gap:8px"><span style="width:5px;height:16px;border-radius:3px;background:linear-gradient(180deg,var(--k-mavi),var(--k-mor));display:inline-block"></span>🏬 G5F Stok · Depo Kırılımlı (Bizim Depo)</div>', unsafe_allow_html=True)
            st.markdown('<div style="color:var(--k-soluk);font-size:13px;line-height:1.6;margin-bottom:12px">Bizim depo stoğu — <b style="color:var(--k-mavi)">tek sayfa</b>, her satır bir depo-ürün. Sütunlar: <b style="color:var(--k-mavi)">DEPO ADI · STOK KODU · STOK İSMİ · MİKTAR</b>. Bir SKU birden çok depoda olabilir; <b>genel toplam</b> ve <b>depo kırılımı</b> tüm depolardan; sipariş önerisindeki <b>"bizim stok"</b> = Merkez depo + Happy Life. (Ürünün fiyat/kategori/marka bilgisine dokunmaz.)</div>', unsafe_allow_html=True)

            dosya_g = st.file_uploader("G5F Stok Excel'ini Seç", type=["xlsx", "xls"], key="g5f_depo_dosya")
            st.warning("📌 **Hareket bazlı stok (Model B) aktif:** İthalat teslimi, satış ve iadeler depo stoğunu "
                       "otomatik günceller. Bu G5F yüklemesi artık **SAYIM / DÜZELTMEDİR** — canlı takip edilen stoğu "
                       "Excel'deki değerlere **eşitler** (üzerine yazar). Yalnızca fiziksel sayım sonrası ya da "
                       "düzeltme amacıyla yükle.")
            if dosya_g:
                if st.button("G5F Stok Yükle (Depo Kırılımlı)", type="primary", use_container_width=True, key="g5f_depo_btn", icon=":material/upload:"):
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmpg:
                        tmpg.write(dosya_g.read())
                        tmpg_path = tmpg.name
                    with st.spinner("🏬 G5F depo kırılımlı stok işleniyor — ürünler senkronlanıyor…"):
                        basari_g, mesaj_g = excel_yukle_g5f_depolar(tmpg_path)
                    os.unlink(tmpg_path)
                    st.cache_data.clear()
                    if basari_g:
                        st.success(mesaj_g)
                    else:
                        st.error(mesaj_g)

            st.markdown("---")
            st.markdown('<div style="font-size:13px;font-weight:700;color:var(--k-mor2);letter-spacing:1px;text-transform:uppercase;margin:8px 0 8px;display:flex;align-items:center;gap:8px"><span style="width:5px;height:16px;border-radius:3px;background:linear-gradient(180deg,var(--k-mor),var(--k-mor));display:inline-block"></span>📅 Geçmiş Yüklemeler</div>', unsafe_allow_html=True)
            st.markdown('<div style="color:var(--k-soluk);font-size:13px;line-height:1.6;margin-bottom:8px">Hangi tarihlerde veri yüklendiğini gör, gerekirse sil.</div>', unsafe_allow_html=True)
    
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
                    @st.dialog("🗑️ Belirli Bir Tarihin Firma Stok Verisini Sil", width="large")
                    def _dlg_tarih_sil():
                        st.caption("⚠️ Seçilen tarihe ait firma stok verileri silinir. Ürün listesi ve satın alma geçmişi etkilenmez.")
                        sil_tarih = st.selectbox("Silinecek Tarih", sorted(tarih_firma.keys(), reverse=True), key="vy_sil_tarih")
                        if st.button("Bu Tarihin Verisini Sil", type="secondary", key="vy_sil_btn", icon=":material/delete:"):
                            sb_vy.table("firma_stok").delete().eq("yukleme_tarihi", sil_tarih).execute()
                            st.toast(f"✅ {sil_tarih} tarihli firma stok verisi silindi.")
                            st.rerun()
                    if st.button("Belirli Bir Tarihin Firma Stok Verisini Sil", key="btn_tarih_sil", use_container_width=True, icon=":material/delete:"):
                        _dlg_tarih_sil()
    
            except Exception as e:
                _log.warning("Hata: %s", e)
                st.warning(f"Geçmiş yüklemeler yüklenemedi: {e}")

    _sayfa_parcasi()
