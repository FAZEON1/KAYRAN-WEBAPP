"""
KAYRAN WORKSPACE — Çatı Uygulama
Sol sidebar navigation ile çoklu uygulama portalı.
Modüller: kayranacc, kayranpm

Mimari:
  Login → Welcome Dashboard (ana sayfa)
  Sidebar: GÖRÜNÜM (Ana Sayfa) · UYGULAMALAR (ACC/PM) · AYARLAR (Çıkış)
  Yetkisiz uygulamalar gri + 🔒 görünür, tıklanamaz
  Hamburger ile sidebar açılır-kapanır
"""
import streamlit as st
from datetime import datetime
import traceback
import smtplib
import ssl
from email.mime.text import MIMEText
from email.utils import formataddr
from urllib.parse import quote
from shared.auth import kullanici_dogrula, kullanici_dogrula_v2, sifre_dogrula, sifre_hash_uret, supabase_sifre_kaydet, _get_supabase


# ─────────────────────────────────────────────────────────────────────
# YETKİ TANIMLARI
# ─────────────────────────────────────────────────────────────────────
KAYRANACC_KULLANICILAR = {"ibrahim", "derman", "cem", "pamuk", "serkan", "yilmaz", "korkut"}
KAYRANPM_KULLANICILAR  = {"ibrahim", "gokhan", "derya"}
HESAP_MAKINESI_KULLANICILAR = {"ibrahim"}

DUYURU_AKTIF = False
DUYURU_METNI = ""


def kullanici_yetkileri(kullanici):
    k = (kullanici or "").lower().strip()
    return {
        "kayranacc": k in KAYRANACC_KULLANICILAR,
        "kayranpm":  k in KAYRANPM_KULLANICILAR,
        "hesap_makinesi": k in HESAP_MAKINESI_KULLANICILAR,
    }


# ─────────────────────────────────────────────────────────────────────
# TALEP / GERİ BİLDİRİM — Mail gönderimi
# ─────────────────────────────────────────────────────────────────────
TALEP_ALICI = "ibrahim.kayran@g5fteknoloji.com"

# ─────────────────────────────────────────────────────────────────────
# ONLINE KULLANICI TAKİP
# ─────────────────────────────────────────────────────────────────────
def online_durum_guncelle(kullanici_adi: str):
    """Kullanıcının son aktivite zamanını Supabase'e kaydeder."""
    try:
        import datetime as _dt
        sb = _get_supabase()
        if not sb:
            return
        sb.table("kullanici_durum").upsert({
            "kullanici_adi": kullanici_adi,
            "son_aktivite": _dt.datetime.utcnow().isoformat(),
        }, on_conflict="kullanici_adi").execute()
    except Exception:
        pass

def get_online_kullanicilar():
    """Son 5 dakika içinde aktif olan kullanıcıların listesini döner."""
    try:
        import datetime as _dt
        sb = _get_supabase()
        if not sb:
            return []
        bitis = _dt.datetime.utcnow()
        baslangic = bitis - _dt.timedelta(minutes=5)
        res = sb.table("kullanici_durum").select("kullanici_adi, son_aktivite").gte("son_aktivite", baslangic.isoformat()).execute()
        return res.data if res.data else []
    except Exception:
        return []

# ─────────────────────────────────────────────────────────────────────
# DUYURU YÖNETİMİ — Supabase'den oku / yaz
# ─────────────────────────────────────────────────────────────────────
def get_duyuru():
    """sistem_ayarlari tablosundan duyuru aktif/metin bilgisini döner."""
    try:
        sb = _get_supabase()
        if not sb:
            return False, ""
        res = sb.table("sistem_ayarlari").select("anahtar, deger").in_("anahtar", ["duyuru_aktif", "duyuru_metni"]).execute()
        d = {r["anahtar"]: r["deger"] for r in (res.data or [])}
        aktif = d.get("duyuru_aktif", "false") == "true"
        metni = d.get("duyuru_metni", "")
        return aktif, metni
    except Exception:
        return False, ""

def set_duyuru(aktif: bool, metni: str):
    """sistem_ayarlari tablosuna duyuru durumu yazar."""
    try:
        import datetime as _dt
        sb = _get_supabase()
        if not sb:
            return False
        now = _dt.datetime.utcnow().isoformat()
        sb.table("sistem_ayarlari").upsert({"anahtar": "duyuru_aktif", "deger": "true" if aktif else "false", "guncelleme_tarihi": now}, on_conflict="anahtar").execute()
        sb.table("sistem_ayarlari").upsert({"anahtar": "duyuru_metni", "deger": metni, "guncelleme_tarihi": now}, on_conflict="anahtar").execute()
        return True
    except Exception:
        return False

# ─────────────────────────────────────────────────────────────────────
# BİLDİRİM SİSTEMİ — Gönder / Oku / Okundu işaretle
# ─────────────────────────────────────────────────────────────────────
def bildirim_gonder(alici: str, mesaj: str):
    """Ibrahim'den belirtilen alıcıya bildirim gönderir."""
    try:
        sb = _get_supabase()
        if not sb:
            return False
        sb.table("bildirimler").insert({"gonderen": "ibrahim", "alici": alici, "mesaj": mesaj, "okundu": False}).execute()
        return True
    except Exception:
        return False

def bildirim_gonder_herkese(mesaj: str, kullanici_listesi: list):
    """Tüm kullanıcılara aynı mesajı gönderir (ibrahim hariç)."""
    try:
        sb = _get_supabase()
        if not sb:
            return False
        rows = [{"gonderen": "ibrahim", "alici": k, "mesaj": mesaj, "okundu": False} for k in kullanici_listesi if k.lower() != "ibrahim"]
        if rows:
            sb.table("bildirimler").insert(rows).execute()
        return True
    except Exception:
        return False

def get_okunmamis_bildirimler(kullanici_adi: str):
    """Kullanıcının okunmamış bildirimlerini döner."""
    try:
        sb = _get_supabase()
        if not sb:
            return []
        res = sb.table("bildirimler").select("*").eq("alici", kullanici_adi).eq("okundu", False).order("olusturma_tarihi", desc=True).execute()
        return res.data if res.data else []
    except Exception:
        return []

def bildirim_okundu_isaretle(bildirim_id: int):
    """Bildirimi okundu olarak işaretle."""
    try:
        sb = _get_supabase()
        if not sb:
            return
        sb.table("bildirimler").update({"okundu": True}).eq("id", bildirim_id).execute()
    except Exception:
        pass

def tumunu_okundu_isaretle(kullanici_adi: str):
    """Kullanıcının tüm bildirimlerini okundu yap."""
    try:
        sb = _get_supabase()
        if not sb:
            return
        sb.table("bildirimler").update({"okundu": True}).eq("alici", kullanici_adi).eq("okundu", False).execute()
    except Exception:
        pass

def get_tum_bildirimler_ibrahim():
    """Ibrahim'in gönderdiği tüm bildirimleri döner."""
    try:
        sb = _get_supabase()
        if not sb:
            return []
        res = sb.table("bildirimler").select("*").order("olusturma_tarihi", desc=True).limit(100).execute()
        return res.data if res.data else []
    except Exception:
        return []






def talep_gonder(gonderen_ad, konu, mesaj):
    """Talebi SMTP ile sabit alıcıya (TALEP_ALICI) gönderir.
    SMTP bilgileri: st.secrets['bildirim'] (smtp_host/port/user/pass).
    Döner: (basarili: bool, kod: str). 'smtp_yok' = SMTP yapılandırılmamış."""
    try:
        b = st.secrets.get("bildirim", {})
    except Exception:
        b = {}
    smtp_host = b.get("smtp_host", "smtp.gmail.com")
    smtp_port = int(b.get("smtp_port", 587))
    smtp_user = b.get("smtp_user", "")
    smtp_pass = b.get("smtp_pass", "")

    if not smtp_user or not smtp_pass:
        return False, "smtp_yok"

    html = (
        "<div style='font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#0f172a;line-height:1.6'>"
        "<h2 style='color:#4338CA;margin:0 0 12px'>📨 KAYRAN Workspace — Yeni Talep / Geri Bildirim</h2>"
        f"<p style='margin:4px 0'><b>Gönderen:</b> {gonderen_ad}</p>"
        f"<p style='margin:4px 0'><b>Konu:</b> {konu}</p>"
        "<hr style='border:none;border-top:1px solid #e2e8f0;margin:12px 0'>"
        f"<div style='white-space:pre-wrap'>{mesaj}</div>"
        "<hr style='border:none;border-top:1px solid #e2e8f0;margin:12px 0'>"
        "<p style='color:#64748b;font-size:12px'>Bu mesaj KAYRAN Workspace ana sayfasındaki talep formundan gönderildi.</p>"
        "</div>"
    )
    try:
        msg = MIMEText(html, "html", "utf-8")
        msg["Subject"] = f"[KAYRAN Talep] {konu}"
        msg["From"] = formataddr(("KAYRAN Workspace", smtp_user))
        msg["To"] = TALEP_ALICI
        msg["Reply-To"] = smtp_user
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port, timeout=12) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [TALEP_ALICI], msg.as_string())
        return True, "ok"
    except smtplib.SMTPAuthenticationError:
        return False, "❌ SMTP kimlik doğrulama hatası (kullanıcı adı/şifre)."
    except Exception as e:
        return False, f"❌ Gönderim hatası: {type(e).__name__}: {str(e)[:200]}"


# ─────────────────────────────────────────────────────────────────────
# Sayfa ayarları
# ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="KAYRAN | Workspace",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Session state defaults
if "giris_yapildi" not in st.session_state:
    st.session_state.giris_yapildi = False
if "aktif_kullanici" not in st.session_state:
    st.session_state.aktif_kullanici = ""
if "aktif_uygulama" not in st.session_state:
    st.session_state.aktif_uygulama = "anasayfa"  # default: ana sayfa


# ─────────────────────────────────────────────────────────────────────
# KURUMSAL KIMLIK
# ─────────────────────────────────────────────────────────────────────
KAYRAN_LOGO_SVG = '<svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="kgS" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse"><stop offset="0%" stop-color="#5B5EF4"/><stop offset="50%" stop-color="#7C3AED"/><stop offset="100%" stop-color="#2563EB"/></linearGradient></defs><rect width="40" height="40" rx="10" fill="url(#kgS)"/><polygon points="9,8 15,8 15,19 24,8 32,8 21,21 32,32 24,32 15,21 15,32 9,32" fill="white"/></svg>'

KAYRAN_LOGO_BIG = '<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="kgB" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse"><stop offset="0%" stop-color="#5B5EF4"/><stop offset="50%" stop-color="#7C3AED"/><stop offset="100%" stop-color="#2563EB"/></linearGradient></defs><rect width="64" height="64" rx="16" fill="url(#kgB)"/><polygon points="14,13 24,13 24,30 38,13 51,13 34,34 51,51 38,51 24,34 24,51 14,51" fill="white"/></svg>'


# ─────────────────────────────────────────────────────────────────────
# CSS — Login + Portal
# ─────────────────────────────────────────────────────────────────────
def login_css():
    return """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

    .stApp {
        background: #080C20 !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
    }
    [data-testid="stHeader"] { background: transparent !important; height: 0 !important; }
    section[data-testid="stSidebar"] { display: none !important; }
    .main .block-container { padding-top: 0 !important; max-width: 100% !important; }
    .stDeployButton { display: none !important; }
    footer { display: none !important; }
    #MainMenu { display: none !important; }

    .kayran-bg {
        position: fixed; top: 0; left: 0;
        width: 100vw; height: 100vh; z-index: -1;
        background: #080C20; overflow: hidden;
    }
    .kayran-bg::before, .kayran-bg::after {
        content: ''; position: absolute;
        width: 800px; height: 800px;
        border-radius: 50%; filter: blur(120px);
        opacity: 0.45;
        animation: blobMove 20s ease-in-out infinite;
    }
    .kayran-bg::before {
        background: radial-gradient(circle, #3b82f6, transparent 70%);
        top: -200px; left: -150px;
    }
    .kayran-bg::after {
        background: radial-gradient(circle, #ec4899, transparent 70%);
        bottom: -200px; right: -150px;
        animation-delay: -10s;
    }
    @keyframes blobMove {
        0%, 100% { transform: translate(0,0) scale(1); }
        33% { transform: translate(100px, 80px) scale(1.1); }
        66% { transform: translate(-80px, 60px) scale(0.95); }
    }
    @keyframes fadeUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .duyuru-band {
        position: fixed; top: 0; left: 0; right: 0;
        background: linear-gradient(90deg, rgba(59,130,246,0.15), rgba(139,92,246,0.15), rgba(236,72,153,0.15));
        backdrop-filter: blur(10px);
        border-bottom: 1px solid rgba(255,255,255,0.08);
        padding: 10px 24px; text-align: center;
        color: #E0E7FF; font-size: 12px; font-weight: 500;
        z-index: 100;
    }

    .stButton > button, .stFormSubmitButton > button,
    button[kind="primaryFormSubmit"] {
        background: linear-gradient(135deg, #6366F1 0%, #7C3AED 100%) !important;
        color: white !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 12px 24px !important;
        box-shadow: 0 4px 20px rgba(99,102,241,0.35) !important;
        transition: all 0.3s !important;
    }
    .stButton > button:hover, .stFormSubmitButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 28px rgba(139,92,246,0.5) !important;
    }

    .stTextInput > div > div > input {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 12px !important;
        color: white !important;
        font-family: 'Inter', sans-serif !important;
        padding: 12px 16px !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #8B5CF6 !important;
        box-shadow: 0 0 0 3px rgba(139,92,246,0.15) !important;
    }
    .stTextInput label {
        color: #CBD5E1 !important;
        font-size: 12px !important;
        font-weight: 500 !important;
        letter-spacing: 0.5px !important;
        text-transform: uppercase !important;
    }

    /* ── STREAMLIT TOOLBAR FIX (sağ üstteki Deploy, menü vb. butonlar) ── */
    /* Default rengi koyu gri (#313143) — koyu zeminde okunmaz, beyaza çeviriyoruz */
    header[data-testid="stHeader"] *,
    .stAppToolbar *,
    .stAppDeployButton *,
    .stMainMenu *,
    [data-testid="stToolbar"] * {
        color: rgba(255,255,255,0.65) !important;
    }
    header[data-testid="stHeader"] button:hover,
    .stAppToolbar button:hover,
    .stAppDeployButton button:hover {
        color: #FFFFFF !important;
        background: rgba(255,255,255,0.06) !important;
    }
    header[data-testid="stHeader"] svg,
    .stAppToolbar svg,
    .stMainMenu svg {
        fill: rgba(255,255,255,0.65) !important;
    }
    /* Material Icons ligature fix */
    button[data-testid="stBaseButton-headerNoPadding"] span:not(.material-symbols-rounded):not(.material-symbols-outlined),
    [data-testid="stSidebarCollapsedControl"] span:not(.material-symbols-rounded):not(.material-symbols-outlined) {
        font-size: 0 !important;
    }
    button[data-testid="stBaseButton-headerNoPadding"] svg,
    [data-testid="stSidebarCollapsedControl"] svg {
        width: 18px !important;
        height: 18px !important;
    }

    /* ── SCROLLBAR — koyu tema ── */
    ::-webkit-scrollbar { width: 10px; height: 10px; }
    ::-webkit-scrollbar-track { background: rgba(255,255,255,0.02); }
    ::-webkit-scrollbar-thumb {
        background: rgba(255,255,255,0.15);
        border-radius: 6px;
        border: 2px solid transparent;
        background-clip: padding-box;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(255,255,255,0.25);
        background-clip: padding-box;
    }
    
    </style>
    <div class="kayran-bg"></div>
    """


def portal_css():
    """Ana sayfa + sidebar CSS (alt uygulamalar yüklenmedikçe geçerli)"""
    return """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

    .stApp {
        background: #080C20 !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
    }
    [data-testid="stHeader"] { background: transparent !important; }
    .stDeployButton { display: none !important; }
    footer { display: none !important; }
    #MainMenu { display: none !important; }

    /* ── STREAMLIT SIDEBAR — Custom KAYRAN Stil ── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0D1235 0%, #080C20 100%) !important;
        border-right: 1px solid rgba(255,255,255,0.06) !important;
        padding-top: 0 !important;
    }
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 0 !important;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 1.5rem !important;
        padding-left: 1.25rem !important;
        padding-right: 1.25rem !important;
    }

    /* Sidebar içindeki butonlar */
    section[data-testid="stSidebar"] .stButton > button {
        background: transparent !important;
        color: #CBD5E1 !important;
        border: 1px solid transparent !important;
        border-radius: 10px !important;
        padding: 10px 14px !important;
        text-align: left !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        font-family: 'Inter', sans-serif !important;
        box-shadow: none !important;
        transition: all 0.2s !important;
        margin-bottom: 4px !important;
        justify-content: flex-start !important;
        width: 100% !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(99,102,241,0.1) !important;
        color: #FFFFFF !important;
        transform: none !important;
        box-shadow: none !important;
        border-color: rgba(99,102,241,0.2) !important;
    }
    /* Aktif buton */
    section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, rgba(99,102,241,0.25), rgba(139,92,246,0.15)) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(99,102,241,0.4) !important;
        box-shadow: 0 0 0 1px rgba(99,102,241,0.1) inset !important;
    }
    /* Disabled (yetkisiz) butonlar */
    section[data-testid="stSidebar"] .stButton > button:disabled {
        background: transparent !important;
        color: #475569 !important;
        cursor: not-allowed !important;
        border-color: transparent !important;
    }
    section[data-testid="stSidebar"] .stButton > button:disabled:hover {
        background: transparent !important;
    }

    /* Sidebar markdown stilleri */
    section[data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.06) !important;
        margin: 12px 0 !important;
    }

    /* ── STREAMLIT TOOLBAR (sağ üstteki Deploy, Share, kebab menü) ── */
    header[data-testid="stHeader"] *,
    .stAppToolbar *,
    .stAppDeployButton *,
    .stMainMenu *,
    [data-testid="stToolbar"] * {
        color: rgba(255,255,255,0.65) !important;
    }
    header[data-testid="stHeader"] button:hover,
    .stAppToolbar button:hover,
    .stAppDeployButton button:hover {
        color: #FFFFFF !important;
        background: rgba(255,255,255,0.06) !important;
    }
    header[data-testid="stHeader"] svg,
    .stAppToolbar svg,
    .stMainMenu svg {
        fill: rgba(255,255,255,0.65) !important;
    }
    /* Sidebar collapse butonu (hamburger) — beyaz arka planda beyazdı, koyu yapıyoruz */
    [data-testid="stSidebarCollapsedControl"],
    button[aria-label*="Close"],
    button[aria-label*="Open"],
    [data-testid="stBaseButton-headerNoPadding"] {
        background: rgba(255,255,255,0.05) !important;
        color: rgba(255,255,255,0.8) !important;
    }
    [data-testid="stSidebarCollapsedControl"] svg,
    [data-testid="stSidebarCollapsedControl"] span {
        color: rgba(255,255,255,0.8) !important;
        fill: rgba(255,255,255,0.8) !important;
    }
    [data-testid="stSidebarCollapsedControl"]:hover,
    [data-testid="stBaseButton-headerNoPadding"]:hover {
        background: rgba(255,255,255,0.1) !important;
    }
    /* Material Icons ligature fix - text gözükmesin */
    button[data-testid="stBaseButton-headerNoPadding"] span:not(.material-symbols-rounded):not(.material-symbols-outlined),
    [data-testid="stSidebarCollapsedControl"] span:not(.material-symbols-rounded):not(.material-symbols-outlined) {
        font-size: 0 !important;
    }
    button[data-testid="stBaseButton-headerNoPadding"] svg,
    [data-testid="stSidebarCollapsedControl"] svg {
        width: 18px !important;
        height: 18px !important;
    }

    /* ── SCROLLBAR koyu tema ── */
    ::-webkit-scrollbar { width: 10px; height: 10px; }
    ::-webkit-scrollbar-track { background: rgba(255,255,255,0.02); }
    ::-webkit-scrollbar-thumb {
        background: rgba(255,255,255,0.15);
        border-radius: 6px;
        border: 2px solid transparent;
        background-clip: padding-box;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(255,255,255,0.25);
        background-clip: padding-box;
    }

    /* ── TOOLTIP & POPOVER ── */
    [role="tooltip"], .stTooltipIcon, [data-baseweb="tooltip"] {
        background: #1B2436 !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
    }

    /* Ana içerik alanı */
    .main .block-container {
        padding-top: 2.5rem !important;
        max-width: 1200px !important;
    }

    /* Animasyonlu arka plan blob'ları (sadece ana sayfada) */
    .anasayfa-bg-blob1, .anasayfa-bg-blob2 {
        position: fixed;
        border-radius: 50%;
        filter: blur(120px);
        opacity: 0.3;
        z-index: -1;
        pointer-events: none;
    }
    .anasayfa-bg-blob1 {
        background: radial-gradient(circle, #3b82f6, transparent 70%);
        top: -100px; right: -100px;
        width: 500px; height: 500px;
        animation: blobMove 25s ease-in-out infinite;
    }
    .anasayfa-bg-blob2 {
        background: radial-gradient(circle, #ec4899, transparent 70%);
        bottom: -100px; left: 300px;
        width: 500px; height: 500px;
        animation: blobMove 25s ease-in-out infinite -12s;
    }
    @keyframes blobMove {
        0%, 100% { transform: translate(0,0) scale(1); }
        33% { transform: translate(80px, 60px) scale(1.1); }
        66% { transform: translate(-60px, 40px) scale(0.95); }
    }
    @keyframes fadeUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* ── Genel buton stili (ana içerik alanı) ── */
    .main .stButton > button {
        background: linear-gradient(135deg, #6366F1 0%, #7C3AED 100%) !important;
        color: white !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 12px 24px !important;
        box-shadow: 0 4px 20px rgba(99,102,241,0.35) !important;
        transition: all 0.3s !important;
    }
    .main .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 28px rgba(139,92,246,0.5) !important;
    }
    
    </style>
    <div class="anasayfa-bg-blob1"></div>
    <div class="anasayfa-bg-blob2"></div>
    """


# ─────────────────────────────────────────────────────────────────────
# 1) LOGIN EKRANI
# ─────────────────────────────────────────────────────────────────────
def giris_ekrani():
    st.markdown(login_css(), unsafe_allow_html=True)
    # ─── Login mobil: sol panel gizle ───
    st.markdown(
        """<style>
@media (max-width: 768px) {
    .main .block-container { padding-top: 1rem !important; }
}
@media (max-width: 640px) {
    [data-testid="column"]:first-child { display: none !important; }
    [data-testid="column"]:last-child { flex: 1 1 100% !important; max-width: 100% !important; }
    input { font-size: 16px !important; }
}
</style>""",
        unsafe_allow_html=True
    )
    _duyuru_aktif2, _duyuru_metni2 = get_duyuru()
    if _duyuru_aktif2 and _duyuru_metni2:
        st.markdown(f'<div class="duyuru-band">{_duyuru_metni2}</div>', unsafe_allow_html=True)

    st.markdown('<div style="height:60px"></div>', unsafe_allow_html=True)

    col_l, col_r = st.columns([1.1, 0.9], gap="large")

    # ── SOL PANEL: Marka + Özellikler ──
    with col_l:
        st.markdown(
            '<div style="padding:20px 24px 20px 8px;animation:fadeUp 0.6s ease-out">'
            # Logo + başlık
            '<div style="display:flex;align-items:center;gap:16px;margin-bottom:36px">'
            f'{KAYRAN_LOGO_BIG}'
            '<div>'
            '<div style="font-family:Inter,sans-serif;font-size:42px;font-weight:900;color:#FFFFFF;letter-spacing:5px;line-height:1">KAYRAN</div>'
            '<div style="font-size:11px;color:#94A3B8;letter-spacing:3px;text-transform:uppercase;font-weight:600;margin-top:4px">Workspace</div>'
            '</div>'
            '</div>'
            # Tagline
            '<div style="margin-bottom:32px">'
            '<h2 style="font-family:Inter,sans-serif;font-size:28px;font-weight:700;color:#FFFFFF;line-height:1.3;margin:0 0 12px">'
            'Şirket Operasyonlarını<br>'
            '<span style="background:linear-gradient(90deg,#60A5FA,#A78BFA,#F472B6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">Tek Çatı Altında</span>'
            '</h2>'
            '<p style="color:#94A3B8;font-size:14px;line-height:1.7;margin:0">'
            'Muhasebe, finans, ithalat ve ürün yönetimini entegre bir platformda yönetin.'
            '</p>'
            '</div>'
            # Özellik listesi
            '<div style="display:flex;flex-direction:column;gap:14px;margin-bottom:36px">'
            '<div style="display:flex;align-items:center;gap:14px">'
            '<div style="width:38px;height:38px;border-radius:10px;background:rgba(99,102,241,0.15);border:1px solid rgba(99,102,241,0.25);display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:16px">💳</div>'
            '<div><div style="color:#E2E8F0;font-size:13px;font-weight:600">Muhasebe & Finans</div>'
            '<div style="color:#64748B;font-size:11px;margin-top:2px">Haftalık ödeme takibi, banka bakiyeleri, nakit akış</div></div>'
            '</div>'
            '<div style="display:flex;align-items:center;gap:14px">'
            '<div style="width:38px;height:38px;border-radius:10px;background:rgba(236,72,153,0.1);border:1px solid rgba(236,72,153,0.2);display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:16px">📦</div>'
            '<div><div style="color:#E2E8F0;font-size:13px;font-weight:600">İthalat & Ürün Yönetimi</div>'
            '<div style="color:#64748B;font-size:11px;margin-top:2px">Stok takibi, sipariş yönetimi, tedarik zinciri</div></div>'
            '</div>'
            '<div style="display:flex;align-items:center;gap:14px">'
            '<div style="width:38px;height:38px;border-radius:10px;background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.2);display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:16px">🔐</div>'
            '<div><div style="color:#E2E8F0;font-size:13px;font-weight:600">Yetki Bazlı Erişim</div>'
            '<div style="color:#64748B;font-size:11px;margin-top:2px">Kullanıcıya özel panel, güvenli oturum yönetimi</div></div>'
            '</div>'
            '</div>'
'<div style="display:flex;align-items:center;gap:14px">'
'<div style="width:38px;height:38px;border-radius:10px;background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.2);display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:16px">🧮</div>'
'<div><div style="color:#E2E8F0;font-size:13px;font-weight:600">Hesap Makinesi</div>'
'<div style="color:#64748B;font-size:11px;margin-top:2px">Urun karlilik analizi, kirilma noktasi hesaplama</div></div>'
'</div>'
'<div style="display:flex;align-items:center;gap:14px">'
'<div style="width:38px;height:38px;border-radius:10px;background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.2);display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:16px">🚧</div>'
'<div><div style="color:#E2E8F0;font-size:13px;font-weight:600">Depo &amp; Teknik Servis</div>'
'<div style="color:#64748B;font-size:11px;margin-top:2px">Stok yonetimi, teknik servis takibi - yakinda</div></div>'
'</div>'
            # Alt bilgi
            '<div style="display:flex;align-items:center;gap:10px;padding-top:20px;border-top:1px solid rgba(255,255,255,0.06)">'
            '<div style="width:6px;height:6px;border-radius:50%;background:#10B981;box-shadow:0 0 8px #10B981"></div>'
            '<span style="color:#64748B;font-size:11px;font-weight:500">Bir <b style="color:#94A3B8">G5F Teknoloji</b> &amp; <b style="color:#94A3B8">Fazeon</b> projesi</span>'
            '</div>'
            '</div>'
'<div style="display:flex;align-items:center;gap:10px;padding-top:10px;margin-top:6px">'
'<div style="width:6px;height:6px;border-radius:50%;background:#6366F1;box-shadow:0 0 8px #6366F1"></div>'
'<span style="color:#64748B;font-size:11px;font-weight:500">Ibrahim Kayran tarafindan gelistirildi</span>'
'</div>',
            unsafe_allow_html=True
        )

    # ── SAĞ PANEL: Login Kartı ──
    with col_r:
        st.markdown(
            '<div style="animation:fadeUp 0.7s ease-out">'
            # Login kartı
            '<div style="background:rgba(255,255,255,0.03);backdrop-filter:blur(24px);'
            'border:1px solid rgba(255,255,255,0.09);border-radius:24px;'
            'padding:36px 32px;box-shadow:0 32px 80px rgba(0,0,0,0.5),0 0 0 1px rgba(255,255,255,0.03) inset">'
            # Kart başlık
            '<div style="text-align:center;margin-bottom:30px">'
            '<div style="width:48px;height:48px;border-radius:14px;'
            'background:linear-gradient(135deg,rgba(99,102,241,0.25),rgba(139,92,246,0.2));'
            'border:1px solid rgba(139,92,246,0.3);display:flex;align-items:center;'
            'justify-content:center;font-size:20px;margin:0 auto 16px">🔐</div>'
            '<div style="color:#FFFFFF;font-size:20px;font-weight:700;margin-bottom:6px">Hesabınıza Giriş Yapın</div>'
            '<div style="color:#64748B;font-size:12px">Yetkili personel için özel erişim</div>'
            '</div>'
            '</div></div>',
            unsafe_allow_html=True
        )
        with st.form("giris_form", clear_on_submit=False):
            kullanici = st.text_input("Kullanıcı Adı", placeholder="kullanici_adi", key="login_user")
            sifre = st.text_input("Şifre", type="password", placeholder="••••••••••••", key="login_pass")
            st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
            giris_btn = st.form_submit_button("Giriş Yap  →", type="primary", use_container_width=True)

        st.markdown(
            '<div style="margin-top:16px;text-align:center">'
            '<div style="display:flex;align-items:center;justify-content:center;gap:8px">'
            '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
            '<path d="M12 2L2 7v10c0 5.25 3.75 10.15 10 11.25C18.25 27.15 22 22.25 22 17V7L12 2z" fill="rgba(16,185,129,0.8)"/>'
            '</svg>'
            '<span style="color:#64748B;font-size:11px">256-bit SSL şifrelemeli güvenli bağlantı</span>'
            '</div>'
            '</div>',
            unsafe_allow_html=True
        )

        if giris_btn:
            try:
                kullanicilar = st.secrets.get("kullanicilar", {})
                if not kullanicilar:
                    st.warning("⚠️ Kullanıcı ayarları yapılandırılmamış.")
                    return
                if kullanici_dogrula_v2(kullanici, sifre, kullanicilar):
                    st.session_state.giris_yapildi = True
                    st.session_state.aktif_kullanici = kullanici
                    st.session_state.aktif_uygulama = "anasayfa"
                    st.rerun()
                else:
                    st.error("❌ Kullanıcı adı veya şifre hatalı.")
            except Exception as e:
                st.error(f"Giriş sistemi hatası: {e}")


def portal_sidebar(kompakt=False):
    """Streamlit'in resmi sidebar'ina KAYRAN'in navigasyonunu cizer."""
    aktif_kullanici = st.session_state.get("aktif_kullanici", "")
    aktif_sayfa = st.session_state.get("aktif_uygulama", "anasayfa")
    yetkiler = kullanici_yetkileri(aktif_kullanici)
    ilk_harf = aktif_kullanici[0].upper() if aktif_kullanici else "U"

    st.markdown(
        """<style>
@media (max-width: 768px) {
section[data-testid="stSidebar"] { width: 85vw !important; min-width: 0 !important; }
.main .block-container { padding-top: 1rem !important; padding-left: 1rem !important; padding-right: 1rem !important; }
}
@media (max-width: 480px) {
input, textarea, select { font-size: 16px !important; }
}
</style>""",
        unsafe_allow_html=True
    )
    st.markdown(
        '<style>'
        'section[data-testid="stSidebar"]{'
        'background:linear-gradient(180deg,#0D1235 0%,#080C20 100%) !important;'
        'border-right:1px solid rgba(255,255,255,0.06) !important;'
        '}'
        'section[data-testid="stSidebar"] *{'
        'color:#CBD5E1 !important;'
        '}'
        'section[data-testid="stSidebar"] h1,'
        'section[data-testid="stSidebar"] h2,'
        'section[data-testid="stSidebar"] h3,'
        'section[data-testid="stSidebar"] strong{'
        'color:#FFFFFF !important;'
        '}'
        'section[data-testid="stSidebar"] .stButton > button{'
        'background:transparent !important;'
        'color:#CBD5E1 !important;'
        'border:1px solid transparent !important;'
        'border-radius:10px !important;'
        'padding:10px 14px !important;'
        'font-size:13px !important;'
        'font-weight:500 !important;'
        'font-family:\'Inter\',sans-serif !important;'
        'line-height:1.2 !important;'
        'letter-spacing:0 !important;'
        'text-transform:none !important;'
        'box-shadow:none !important;'
        'transition:background 0.2s,border-color 0.2s,color 0.2s !important;'
        'margin-bottom:4px !important;'
        'min-height:40px !important;'
        'width:100% !important;'
        '}'
        'section[data-testid="stSidebar"] .stButton > button > div,'
        'section[data-testid="stSidebar"] .stButton > button [class*="e12tamyi22"]{'
        'justify-content:flex-start !important;'
        'align-items:center !important;'
        'width:100% !important;'
        '}'
        'section[data-testid="stSidebar"] .stButton > button span,'
        'section[data-testid="stSidebar"] .stButton > button p,'
        'section[data-testid="stSidebar"] .stButton > button div{'
        'text-align:left !important;'
        'justify-content:flex-start !important;'
        'font-size:13px !important;'
        'font-weight:500 !important;'
        'font-family:\'Inter\',sans-serif !important;'
        'color:inherit !important;'
        'line-height:1.2 !important;'
        '}'
        'section[data-testid="stSidebar"] .stButton > button:hover{'
        'background:rgba(99,102,241,0.1) !important;'
        'color:#FFFFFF !important;'
        'border-color:rgba(99,102,241,0.2) !important;'
        'transform:none !important;'
        'box-shadow:none !important;'
        '}'
        'section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]{'
        'background:linear-gradient(135deg,rgba(99,102,241,0.25),rgba(139,92,246,0.15)) !important;'
        'color:#FFFFFF !important;'
        'border:1px solid rgba(99,102,241,0.4) !important;'
        'font-size:13px !important;'
        'font-weight:500 !important;'
        'font-family:\'Inter\',sans-serif !important;'
        'padding:10px 14px !important;'
        '}'
        'section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] > div{'
        'justify-content:flex-start !important;'
        '}'
        'section[data-testid="stSidebar"] .stButton > button:disabled{'
        'background:transparent !important;'
        'color:#475569 !important;'
        'cursor:not-allowed !important;'
        'border-color:transparent !important;'
        '}'
        'section[data-testid="stSidebar"] .stButton > button:disabled:hover{'
        'background:transparent !important;'
        'transform:none !important;'
        'box-shadow:none !important;'
        '}'
        'section[data-testid="stSidebar"] .stButton [data-testid="stMarkdownContainer"],'
        'section[data-testid="stSidebar"] .stButton [data-testid="stMarkdownContainer"] *{'
        'text-align:left !important;'
        'justify-content:flex-start !important;'
        '}'
        'section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"],'
        'section[data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"]{'
        'background:linear-gradient(135deg,rgba(99,102,241,0.25),rgba(139,92,246,0.15)) !important;'
        'color:#FFFFFF !important;'
        'border:1px solid rgba(99,102,241,0.4) !important;'
        'font-size:13px !important;'
        'font-weight:500 !important;'
        '}'
        'section[data-testid="stSidebar"] .stButton > button:disabled,'
        'section[data-testid="stSidebar"] .stButton > button:disabled:hover{'
        'background:transparent !important;'
        'color:#475569 !important;'
        'cursor:not-allowed !important;'
        'border-color:transparent !important;'
        'transform:none !important;'
        'box-shadow:none !important;'
        '}'
        'section[data-testid="stSidebar"] [data-testid="stRadio"] label,'
        'section[data-testid="stSidebar"] [data-testid="stRadio"] p{'
        'color:#CBD5E1 !important;'
        '}'
        'button[data-testid="stBaseButton-headerNoPadding"],'
        '[data-testid="stSidebarCollapsedControl"]{'
        'background:rgba(255,255,255,0.05) !important;'
        '}'
        'button[data-testid="stBaseButton-headerNoPadding"] *,'
        '[data-testid="stSidebarCollapsedControl"] *{'
        'color:rgba(255,255,255,0.7) !important;'
        'fill:rgba(255,255,255,0.7) !important;'
        '}'
        'button[data-testid="stBaseButton-headerNoPadding"] span:not(.material-symbols-rounded):not(.material-symbols-outlined),'
        '[data-testid="stSidebarCollapsedControl"] span:not(.material-symbols-rounded):not(.material-symbols-outlined){'
        'font-size:0 !important;'
        '}'
        'button[data-testid="stBaseButton-headerNoPadding"] svg,'
        '[data-testid="stSidebarCollapsedControl"] svg{'
        'font-size:initial !important;'
        'width:18px !important;'
        'height:18px !important;'
        '}'
        'header[data-testid="stHeader"] *,'
        '.stAppToolbar *,'
        '.stAppDeployButton *{'
        'color:rgba(255,255,255,0.65) !important;'
        '}'
        'header[data-testid="stHeader"] svg,'
        '.stAppToolbar svg{'
        'fill:rgba(255,255,255,0.65) !important;'
        '}'
        '::-webkit-scrollbar{width:10px;height:10px;}'
        '::-webkit-scrollbar-track{background:rgba(255,255,255,0.02);}'
        '::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.15);border-radius:6px;}'
        '::-webkit-scrollbar-thumb:hover{background:rgba(255,255,255,0.25);}'
        '</style>',
        unsafe_allow_html=True
    )

    with st.sidebar:
        # Logo + KAYRAN basligi
        st.markdown(
            '<div style="display:flex;align-items:center;gap:12px;padding:4px 0 16px;border-bottom:1px solid rgba(255,255,255,0.06);margin-bottom:14px">'
            + KAYRAN_LOGO_SVG +
            '<div>'
            '<div style="font-family:Inter,sans-serif;font-size:20px;font-weight:800;color:#FFFFFF;letter-spacing:2px;line-height:1">KAYRAN</div>'
            '<div style="font-size:10px;color:#94A3B8;letter-spacing:1.5px;text-transform:uppercase;margin-top:3px;font-weight:600">Workspace</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True
        )

        # NAVIGASYON grubu
        st.markdown(
            '<div style="font-size:10px;color:#64748B;letter-spacing:2px;font-weight:700;text-transform:uppercase;margin:4px 0 8px;padding-left:6px">NAViGASYON</div>',
            unsafe_allow_html=True
        )

        if st.button(
            "🏠 Ana Sayfa",
            key="nav_anasayfa",
            type="primary" if aktif_sayfa == "anasayfa" else "secondary",
            use_container_width=True
        ):
            st.session_state.aktif_uygulama = "anasayfa"
            st.rerun()

        if yetkiler["kayranacc"]:
            if st.button(
                "💳 Muhasebe & Finans",
                key="nav_kayranacc",
                type="primary" if aktif_sayfa == "kayranacc" else "secondary",
                use_container_width=True
            ):
                st.session_state.aktif_uygulama = "kayranacc"
                st.rerun()
        else:
            st.button(
                "🔒 Muhasebe & Finans",
                key="nav_kayranacc_disabled",
                disabled=True,
                use_container_width=True,
                help="Bu uygulamaya erisim yetkiniz yok"
            )

        if yetkiler["kayranpm"]:
            if st.button(
                "📦 Ithalat & Urun Yonetimi",
                key="nav_kayranpm",
                type="primary" if aktif_sayfa == "kayranpm" else "secondary",
                use_container_width=True
            ):
                st.session_state.aktif_uygulama = "kayranpm"
                st.rerun()
        else:
            st.button(
                "🔒 Ithalat & Urun Yonetimi",
                key="nav_kayranpm_disabled",
                disabled=True,
                use_container_width=True,
                help="Bu uygulamaya erisim yetkiniz yok"
            )

        if yetkiler["hesap_makinesi"]:
            if st.button(
                "🧮 Hesap Makinesi",
                key="nav_hesap_makinesi",
                type="primary" if aktif_sayfa == "hesap_makinesi" else "secondary",
                use_container_width=True
            ):
                st.session_state.aktif_uygulama = "hesap_makinesi"
                st.rerun()

        if st.button(
            "🚧 Depo & Teknik Servis",
            key="nav_kayrantsw",
            type="primary" if aktif_sayfa == "kayrantsw" else "secondary",
            use_container_width=True,
            help="Cok yakinda sizlerle"
        ):
            st.session_state.aktif_uygulama = "kayrantsw"
            st.rerun()

        st.markdown(
            '<div style="height:1px;background:rgba(255,255,255,0.06);margin:14px 0 14px"></div>',
            unsafe_allow_html=True
        )

        if aktif_sayfa in ("anasayfa", "kayrantsw", "sifre_degistir", "hesap_makinesi"):
            st.markdown(
                '<div style="font-size:10px;color:#64748B;letter-spacing:2px;font-weight:700;text-transform:uppercase;margin:4px 0 10px;padding-left:6px">HESAP</div>',
                unsafe_allow_html=True
            )
            st.markdown(
                '<div style="display:flex;align-items:center;gap:10px;padding:10px 12px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:10px;margin-bottom:8px">'
                '<div style="width:30px;height:30px;border-radius:8px;background:linear-gradient(135deg,#6366F1,#8B5CF6);display:flex;align-items:center;justify-content:center;font-weight:700;color:white;font-size:13px">' + ilk_harf + '</div>'
                '<div style="overflow:hidden">'
                '<div style="color:#94A3B8;font-size:9px;font-weight:600;letter-spacing:0.5px;text-transform:uppercase;line-height:1">Oturum</div>'
                '<div style="color:#FFFFFF;font-weight:600;font-size:12px;margin-top:2px;line-height:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + aktif_kullanici.capitalize() + '</div>'
                '</div>'
                '</div>',
                unsafe_allow_html=True
            )

            if st.button(
                "🔑 Sifremi Degistir",
                key="nav_sifre_degistir",
                type="primary" if aktif_sayfa == "sifre_degistir" else "secondary",
                use_container_width=True
            ):
                st.session_state.aktif_uygulama = "sifre_degistir"
                st.rerun()

            if st.button("🚪 Cikis Yap", key="nav_cikis", use_container_width=True):
                st.session_state.giris_yapildi = False
                st.session_state.aktif_kullanici = ""
                st.session_state.aktif_uygulama = "anasayfa"
                st.rerun()
        else:
            uyg_adi_map = {"kayranacc": "Muhasebe & Finans", "kayranpm": "Ithalat & Urun Yonetimi", "hesap_makinesi": "Hesap Makinesi"}
            uyg_adi = uyg_adi_map.get(aktif_sayfa, aktif_sayfa.capitalize())
            uyg_renk_map = {"kayranacc": "#A5B4FC", "kayranpm": "#F9A8D4", "hesap_makinesi": "#FCD34D"}
            uyg_renk = uyg_renk_map.get(aktif_sayfa, "#A5B4FC")
            st.markdown(
                '<div style="font-size:10px;color:' + uyg_renk + ';letter-spacing:2px;font-weight:700;text-transform:uppercase;margin:4px 0 8px;padding-left:6px"> ' + uyg_adi + ' SAYFALARI</div>',
                unsafe_allow_html=True
            )


def anasayfa():
    G5F_LOGO_SVG = '<svg width="100" height="44" viewBox="0 0 220 90" fill="none" xmlns="http://www.w3.org/2000/svg" style="display:inline-block"><text x="10" y="72" font-family="Inter, sans-serif" font-size="80" font-weight="900" fill="#FFFFFF">G</text><text x="78" y="72" font-family="Inter, sans-serif" font-size="80" font-weight="900" fill="#E88420">5</text><text x="142" y="72" font-family="Inter, sans-serif" font-size="80" font-weight="900" fill="#FFFFFF">F</text></svg>'
    FAZEON_LOGO_SVG = '<svg width="170" height="32" viewBox="0 0 360 60" fill="none" xmlns="http://www.w3.org/2000/svg" style="display:inline-block"><text x="0" y="44" font-family="Inter, sans-serif" font-size="44" font-weight="300" fill="#FFFFFF" letter-spacing="6">FAZEON</text></svg>'
    aktif_kullanici = st.session_state.get("aktif_kullanici", "")
    yetkiler = kullanici_yetkileri(aktif_kullanici)

    st.markdown(portal_css(), unsafe_allow_html=True)

    # Duyuruyu Supabase'den dinamik oku
    _duyuru_aktif, _duyuru_metni = get_duyuru()
    if _duyuru_aktif and _duyuru_metni:
        st.markdown(
            f'<div style="background:linear-gradient(90deg,rgba(59,130,246,0.12),rgba(139,92,246,0.12),rgba(236,72,153,0.12));border:1px solid rgba(99,102,241,0.2);border-radius:12px;padding:10px 16px;text-align:center;color:#A5B4FC;font-size:12px;font-weight:500;margin-bottom:24px;animation:fadeUp 0.5s ease-out">{_duyuru_metni}</div>',
            unsafe_allow_html=True
        )

    # Saate göre selamlama
    saat = datetime.now().hour
    if saat < 12: selamlama = "Günaydın"
    elif saat < 18: selamlama = "İyi günler"
    else: selamlama = "İyi akşamlar"

    # ─────────────────────────────────────────────────────────────────────
    # KULLANICIYA BİLDİRİM — EN ÜSTTE (ibrahim dışı herkes)
    # ─────────────────────────────────────────────────────────────────────
    if aktif_kullanici.lower() != "ibrahim":
        _bildirimler = get_okunmamis_bildirimler(aktif_kullanici)
        if _bildirimler:
            _bil_html = (
                '<div style="background:linear-gradient(135deg,rgba(99,102,241,0.12),rgba(139,92,246,0.08));'
                'border:1px solid rgba(99,102,241,0.3);border-radius:16px;'
                'padding:16px 20px;margin-bottom:24px;animation:fadeUp 0.4s ease-out">'
                f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">'
                f'<div style="width:28px;height:28px;border-radius:8px;background:rgba(99,102,241,0.25);'
                f'display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0">🔔</div>'
                f'<span style="color:#A5B4FC;font-size:13px;font-weight:700">'
                f'{len(_bildirimler)} yeni bildirim</span>'
                f'</div>'
            )
            for _b in _bildirimler:
                _bil_html += (
                    f'<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);'
                    f'border-radius:10px;padding:12px 16px;margin-bottom:8px">'
                    f'<div style="color:#E2E8F0;font-size:13px;line-height:1.6">{_b.get("mesaj","")}</div>'
                    f'<div style="color:#64748B;font-size:10px;margin-top:6px;display:flex;align-items:center;gap:6px">'
                    f'<span style="width:5px;height:5px;border-radius:50%;background:#6366F1;display:inline-block"></span>'
                    f'Ibrahim · {str(_b.get("olusturma_tarihi",""))[:16].replace("T"," ")}'
                    f'</div>'
                    f'</div>'
                )
            _bil_html += '</div>'
            st.markdown(_bil_html, unsafe_allow_html=True)
            if st.button("✓ Tümünü Okundu İşaretle", key="okundu_btn", use_container_width=False):
                tumunu_okundu_isaretle(aktif_kullanici)
                st.rerun()

    # ─── HERO BÖLÜMÜ ───
    st.markdown(
        '<div style="margin-bottom:32px;animation:fadeUp 0.6s ease-out">'
        '<div style="display:inline-block;padding:6px 14px;background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.25);border-radius:20px;margin-bottom:18px">'
        '<span style="color:#A5B4FC;font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase">🏠 Ana Sayfa</span>'
        '</div>'
        f'<h1 style="font-family:Inter,sans-serif;font-size:clamp(26px,5vw,44px);font-weight:800;color:#FFFFFF;letter-spacing:-0.5px;line-height:1.1;margin:0">'
        f'{selamlama}, '
        f'<span style="background:linear-gradient(90deg,#60A5FA,#A78BFA,#F472B6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">{aktif_kullanici.capitalize()}</span>'
        '</h1>'
        '<p style="color:#94A3B8;font-size:15px;margin-top:8px;font-weight:400">'
        'KAYRAN Workspace\'e hoş geldin. Sol menüden uygulamana erişebilirsin.'
        '</p>'
        '</div>',
        unsafe_allow_html=True
    )

    # ─── ÜST İSTATİSTİK KARTLARI ───
    erisilebilir = sum(1 for v in yetkiler.values() if v)
    toplam_uygulama = len(yetkiler)

    st.markdown(
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;margin-bottom:48px;animation:fadeUp 0.7s ease-out">'
        f'<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(99,102,241,0.15);border-radius:14px;padding:20px 22px;backdrop-filter:blur(10px)">'
        '<div style="font-size:10px;color:#64748B;letter-spacing:1.5px;text-transform:uppercase;font-weight:700;margin-bottom:8px">Erişim</div>'
        f'<div style="display:flex;align-items:baseline;gap:6px">'
        f'<span style="color:#FFFFFF;font-size:32px;font-weight:800;font-family:JetBrains Mono,monospace">{erisilebilir}</span>'
        f'<span style="color:#64748B;font-size:14px;font-weight:500">/ {toplam_uygulama} uygulama</span>'
        '</div>'
        '<div style="color:#A5B4FC;font-size:11px;font-weight:500;margin-top:6px">⚡ Yetkili olduğun uygulamalar</div>'
        '</div>'
        '<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(16,185,129,0.2);border-radius:14px;padding:20px 22px;backdrop-filter:blur(10px)">'
        '<div style="font-size:10px;color:#64748B;letter-spacing:1.5px;text-transform:uppercase;font-weight:700;margin-bottom:8px">Sistem</div>'
        '<div style="display:flex;align-items:center;gap:8px;margin-top:2px">'
        '<div style="width:8px;height:8px;border-radius:50%;background:#10B981;box-shadow:0 0 12px #10B981"></div>'
        '<span style="color:#FFFFFF;font-size:18px;font-weight:700">Çevrimiçi</span>'
        '</div>'
        '<div style="color:#6EE7B7;font-size:11px;font-weight:500;margin-top:6px">✓ Tüm servisler aktif</div>'
        '</div>'
        f'<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(236,72,153,0.15);border-radius:14px;padding:20px 22px;backdrop-filter:blur(10px)">'
        '<div style="font-size:10px;color:#64748B;letter-spacing:1.5px;text-transform:uppercase;font-weight:700;margin-bottom:8px">Versiyon</div>'
        '<div style="display:flex;align-items:baseline;gap:6px">'
        '<span style="color:#FFFFFF;font-size:24px;font-weight:700;font-family:JetBrains Mono,monospace">v2.0</span>'
        '<span style="color:#64748B;font-size:12px">.0</span>'
        '</div>'
        '<div style="color:#F9A8D4;font-size:11px;font-weight:500;margin-top:6px">🏢 Kurumsal sürüm</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )
    # ─── KURUMSAL BÖLÜMÜ BAŞLIĞI ───
    st.markdown(
        '<div style="margin:8px 0 24px;animation:fadeUp 0.8s ease-out">'
        '<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px">'
        '<div style="height:1px;flex:1;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.1))"></div>'
        '<div style="font-size:11px;color:#64748B;letter-spacing:3px;text-transform:uppercase;font-weight:700">Kurumsal</div>'
        '<div style="height:1px;flex:1;background:linear-gradient(90deg,rgba(255,255,255,0.1),transparent)"></div>'
        '</div>'
        '<h2 style="font-family:Inter,sans-serif;font-size:28px;font-weight:700;color:#FFFFFF;text-align:center;letter-spacing:-0.3px;margin:0">'
        'Bir <span style="background:linear-gradient(90deg,#E88420,#F59E0B);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;font-weight:800">G5F Teknoloji</span> projesi'
        '</h2>'
        '<p style="color:#94A3B8;font-size:13px;text-align:center;margin-top:8px;font-weight:400">'
        'Teknoloji ve operasyon çözümlerini bir araya getiriyoruz'
        '</p>'
        '</div>',
        unsafe_allow_html=True
    )

    # ─── 2 BRAND KARTI: G5F + FAZEON ───
    col1, col2 = st.columns(2, gap="medium")

    # G5F Kartı — Kurumsal koyu lacivert + turuncu
    with col1:
        st.markdown(
            '<div style="position:relative;background:linear-gradient(135deg,#1B2436 0%,#0F172A 100%);'
            'border:1px solid rgba(232,132,32,0.2);border-radius:20px;padding:32px 28px 24px;overflow:hidden;'
            'min-height:280px;animation:fadeUp 0.9s ease-out;box-shadow:0 10px 40px rgba(0,0,0,0.3)">'
            # Turuncu accent çizgi
            '<div style="position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#E88420,#F59E0B,#E88420)"></div>'
            # Decorative glow
            '<div style="position:absolute;top:-60px;right:-60px;width:220px;height:220px;background:radial-gradient(circle,rgba(232,132,32,0.15),transparent 70%);border-radius:50%;pointer-events:none"></div>'
            # Header
            '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;position:relative;z-index:2">'
            f'{G5F_LOGO_SVG}'
            '</div>'
            # Başlık
            '<div style="margin-bottom:16px;position:relative;z-index:2">'
            '<div style="font-family:Inter,sans-serif;font-size:22px;font-weight:800;color:#FFFFFF;letter-spacing:-0.2px;line-height:1.2;margin-bottom:6px">G5F Teknoloji</div>'
            '<div style="font-size:11px;color:#FED7AA;letter-spacing:1px;font-weight:600;text-transform:uppercase">Distribütör · Teknoloji Çözümleri</div>'
            '</div>'
            # Açıklama
            '<div style="font-size:13px;line-height:1.7;color:#CBD5E1;margin-bottom:20px;position:relative;z-index:2">'
            'Yılların deneyimi ve uzmanlığıyla yüksek kaliteli teknoloji ürünlerini, hızlı tedarik ve güvenilir hizmet anlayışıyla sunan distribütör.'
            '</div>'
            # Mini istatistikler
            '<div style="display:flex;gap:20px;margin-bottom:20px;position:relative;z-index:2">'
            '<div>'
            '<div style="font-family:JetBrains Mono,monospace;font-size:18px;font-weight:700;color:#FED7AA">4+</div>'
            '<div style="font-size:10px;color:#94A3B8;letter-spacing:0.5px;text-transform:uppercase;font-weight:600">Marka</div>'
            '</div>'
            '<div>'
            '<div style="font-family:JetBrains Mono,monospace;font-size:18px;font-weight:700;color:#FED7AA">100%</div>'
            '<div style="font-size:10px;color:#94A3B8;letter-spacing:0.5px;text-transform:uppercase;font-weight:600">Memnuniyet</div>'
            '</div>'
            '<div>'
            '<div style="font-family:JetBrains Mono,monospace;font-size:18px;font-weight:700;color:#FED7AA">7/24</div>'
            '<div style="font-size:10px;color:#94A3B8;letter-spacing:0.5px;text-transform:uppercase;font-weight:600">Destek</div>'
            '</div>'
            '</div>'
            # Web sitesi link — koyu zemin + açık turuncu yazı, kontrast yüksek
            '<a href="https://g5fteknoloji.com" target="_blank" rel="noopener noreferrer" '
            'style="display:inline-flex;align-items:center;gap:8px;padding:10px 18px;background:rgba(0,0,0,0.4);'
            'border:1px solid rgba(232,132,32,0.5);border-radius:10px;color:#FFEDD5;text-decoration:none;'
            'font-size:12px;font-weight:600;letter-spacing:0.3px;transition:all 0.25s;position:relative;z-index:2">'
            '<span>🌐 g5fteknoloji.com</span>'
            '<span style="font-size:14px">→</span>'
            '</a>'
            '</div>',
            unsafe_allow_html=True
        )

    # FAZEON Kartı — Siyah + Beyaz minimalist, Gaming
    with col2:
        st.markdown(
            '<div style="position:relative;background:linear-gradient(135deg,#0F0A1E 0%,#1A0F3C 50%,#0D0D2B 100%);'
            'border:1px solid rgba(139,92,246,0.25);border-radius:20px;padding:32px 28px 24px;overflow:hidden;'
            'min-height:280px;animation:fadeUp 1s ease-out;box-shadow:0 10px 50px rgba(99,102,241,0.2),0 2px 0 rgba(139,92,246,0.3) inset">'
            # White accent çizgi
            '<div style="position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,transparent,#FFFFFF,transparent)"></div>'
            # Decorative tech grid
            '<div style="position:absolute;top:0;right:0;width:200px;height:200px;background-image:linear-gradient(45deg,transparent 49%,rgba(255,255,255,0.04) 50%,transparent 51%),linear-gradient(-45deg,transparent 49%,rgba(255,255,255,0.04) 50%,transparent 51%);background-size:20px 20px;opacity:0.6;pointer-events:none"></div>'
            # Header
            '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;position:relative;z-index:2">'
            f'{FAZEON_LOGO_SVG}'
            '</div>'
            # Slogan
            '<div style="margin-bottom:16px;position:relative;z-index:2">'
            '<div style="font-family:Inter,sans-serif;font-size:22px;font-weight:800;color:#FFFFFF;letter-spacing:-0.2px;line-height:1.2;margin-bottom:6px">Are You Ready to <span style="font-style:italic;font-weight:300">Faze</span> the World?</div>'
            '<div style="font-size:11px;color:#A78BFA;letter-spacing:1px;font-weight:600;text-transform:uppercase">Gaming · Monitors · Cases · Coolers</div>'
            '</div>'
            # Açıklama
            '<div style="font-size:13px;line-height:1.7;color:#CBD5E1;margin-bottom:20px;position:relative;z-index:2">'
            'Yüksek performanslı oyuncu monitörleri, özelleştirilebilir PC kasaları ve verimli soğutma sistemleriyle teknolojinin yeni yüzü.'
            '</div>'
            # Ürün kategorileri
            '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:20px;position:relative;z-index:2">'
            '<span style="font-size:10px;color:#C4B5FD;background:rgba(139,92,246,0.12);padding:4px 10px;border-radius:6px;border:1px solid rgba(139,92,246,0.25);font-weight:600;letter-spacing:0.3px">📺 Monitors</span>'
            '<span style="font-size:10px;color:#C4B5FD;background:rgba(139,92,246,0.12);padding:4px 10px;border-radius:6px;border:1px solid rgba(139,92,246,0.25);font-weight:600;letter-spacing:0.3px">📦 Cases</span>'
            '<span style="font-size:10px;color:#BAE6FD;background:rgba(56,189,248,0.1);padding:4px 10px;border-radius:6px;border:1px solid rgba(56,189,248,0.2);font-weight:600;letter-spacing:0.3px">❄️ Coolers</span>'
            '<span style="font-size:10px;color:#C4B5FD;background:rgba(139,92,246,0.12);padding:4px 10px;border-radius:6px;border:1px solid rgba(139,92,246,0.25);font-weight:600;letter-spacing:0.3px">🖱️ Mouse Pads</span>'
            '</div>'
            # Web sitesi link
            '<a href="https://fazeon.com" target="_blank" rel="noopener noreferrer" '
            'style="display:inline-flex;align-items:center;gap:8px;padding:10px 20px;'
            'background:linear-gradient(135deg,rgba(99,102,241,0.2),rgba(139,92,246,0.15));'
            'border:1px solid rgba(139,92,246,0.4);border-radius:10px;color:#C4B5FD;text-decoration:none;'
            'font-size:12px;font-weight:600;letter-spacing:0.3px;transition:all 0.25s;position:relative;z-index:2;'
            'box-shadow:0 4px 15px rgba(99,102,241,0.15)">'
            '<span>🌐 fazeon.com</span>'
            '<span style="font-size:14px">→</span>'
            '</a>'
            '</div>',
            unsafe_allow_html=True
        )

    # ─── TALEP / GERİ BİLDİRİM PLATFORMU ───
    st.markdown(
        '<div style="margin:52px 0 18px;animation:fadeUp 1.05s ease-out">'
        '<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px">'
        '<div style="height:1px;flex:1;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.1))"></div>'
        '<div style="font-size:11px;color:#64748B;letter-spacing:3px;text-transform:uppercase;font-weight:700">Destek</div>'
        '<div style="height:1px;flex:1;background:linear-gradient(90deg,rgba(255,255,255,0.1),transparent)"></div>'
        '</div>'
        '<h2 style="font-family:Inter,sans-serif;font-size:28px;font-weight:700;color:#FFFFFF;text-align:center;letter-spacing:-0.3px;margin:0">'
        '💬 Talep &amp; Geri Bildirim</h2>'
        '<p style="color:#94A3B8;font-size:13px;text-align:center;margin-top:8px;font-weight:400">'
        'Uygulamalarla ilgili geliştirme, optimizasyon veya yeni özellik taleplerinizi doğrudan ekibimize iletin'
        '</p>'
        '</div>',
        unsafe_allow_html=True
    )

    # Form alanları için koyu temaya uygun stil
    st.markdown(
        '<style>'
        '[data-testid="stTextInput"] label,[data-testid="stTextArea"] label{'
        'color:#CBD5E1 !important;font-weight:600 !important;font-size:12px !important;'
        'letter-spacing:.5px !important;text-transform:uppercase !important;}'
        '[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea{'
        'background:rgba(255,255,255,0.04) !important;border:1px solid rgba(255,255,255,0.12) !important;'
        'color:#FFFFFF !important;border-radius:12px !important;}'
        '[data-testid="stTextInput"] input::placeholder,[data-testid="stTextArea"] textarea::placeholder{'
        'color:#64748B !important;}'
        '[data-testid="stTextInput"] input:focus,[data-testid="stTextArea"] textarea:focus{'
        'border-color:#8B5CF6 !important;box-shadow:0 0 0 3px rgba(139,92,246,0.15) !important;}'
        '.stFormSubmitButton > button,[data-testid="stFormSubmitButton"] button{'
        'background:linear-gradient(135deg,#6366F1,#8B5CF6) !important;color:#fff !important;'
        'border:none !important;border-radius:12px !important;font-weight:600 !important;'
        'box-shadow:0 4px 20px rgba(99,102,241,0.35) !important;}'
        '</style>',
        unsafe_allow_html=True
    )

    col_tl, col_tc, col_tr = st.columns([1, 2, 1])
    with col_tc:
        with st.form("talep_form", clear_on_submit=True):
            konu = st.text_input("Konu", placeholder="Örn. KAYRAN'a toplu Excel dışa aktarma")
            mesaj = st.text_area(
                "Mesajınız",
                placeholder="Talebinizi, önerinizi veya karşılaştığınız sorunu detaylıca yazın...",
                height=150
            )
            gonder = st.form_submit_button("📨  Talebi Gönder", type="primary", use_container_width=True)

        if gonder:
            if not mesaj or not mesaj.strip():
                st.warning("⚠️ Lütfen mesaj alanını doldurun.")
            else:
                konu_son = (konu or "").strip() or "Konusuz Talep"
                with st.spinner("Talebiniz kaydediliyor..."):
                    from kayranpm.database import ekle_talep, get_talepler
                    ok = ekle_talep(aktif_kullanici.capitalize(), konu_son, mesaj.strip())
                if ok:
                    st.cache_data.clear()
                    st.success("✅ Talebiniz kaydedildi. Teşekkürler!")
                else:
                    st.error("❌ Talep kaydedilemedi. Lütfen tekrar deneyin.")
    # ─── ALT BİLGİ ŞERİDİ ───
    st.markdown(
        '<div style="margin:48px 0 0;padding:24px 0;border-top:1px solid rgba(255,255,255,0.06);animation:fadeUp 1.1s ease-out">'
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;text-align:center">'
        # Hızlı erişim
        '<div>'
        '<div style="font-size:24px;margin-bottom:8px">⚡</div>'
        '<div style="color:#E2E8F0;font-size:13px;font-weight:600;margin-bottom:4px">Hızlı Erişim</div>'
        '<div style="color:#94A3B8;font-size:11px;line-height:1.5">Sol menüden tek tıkla uygulamalarınıza ulaşın</div>'
        '</div>'
        # Güvenli
        '<div>'
        '<div style="font-size:24px;margin-bottom:8px">🔐</div>'
        '<div style="color:#E2E8F0;font-size:13px;font-weight:600;margin-bottom:4px">Kurumsal Güvenlik</div>'
        '<div style="color:#94A3B8;font-size:11px;line-height:1.5">Şifreli bağlantı, yetki bazlı erişim kontrolü</div>'
        '</div>'
        # Bulut
        '<div>'
        '<div style="font-size:24px;margin-bottom:8px">☁️</div>'
        '<div style="color:#E2E8F0;font-size:13px;font-weight:600;margin-bottom:4px">Bulut Senkronizasyon</div>'
        '<div style="color:#94A3B8;font-size:11px;line-height:1.5">Tüm verileriniz gerçek zamanlı korunur</div>'
        '</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # ─── COPYRIGHT ───
    yil = datetime.now().year
    st.markdown(
        f'<div style="margin:32px 0 20px;text-align:center;animation:fadeUp 1.2s ease-out">'
        '<div style="display:inline-flex;align-items:center;gap:14px;padding:8px 18px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.04);border-radius:30px">'
        '<div style="display:flex;align-items:center;gap:6px">'
        '<div style="width:6px;height:6px;border-radius:50%;background:#10B981;box-shadow:0 0 8px #10B981"></div>'
        '<span style="color:#10B981;font-size:10px;font-weight:600;letter-spacing:1px;text-transform:uppercase">Sistem Aktif</span>'
        '</div>'
        '<span style="color:#475569;font-size:10px">•</span>'
        f'<span style="color:#64748B;font-size:11px;font-family:JetBrains Mono,monospace">KAYRAN v2.0.0</span>'
        '<span style="color:#475569;font-size:10px">•</span>'
        f'<span style="color:#64748B;font-size:11px;font-weight:500">© {yil} G5F Teknoloji</span>'
        '</div>'
        '</div>'
        '<div style="margin-top:8px;text-align:center">'
        '<span style="color:#475569;font-size:10px">Ibrahim Kayran tarafindan gelistirildi</span>'
        '</div>',
        unsafe_allow_html=True
    )

    # ─────────────────────────────────────────────────────────────────────
    # ONLİNE KULLANICILAR (sadece ibrahim görür)
    # ─────────────────────────────────────────────────────────────────────
    if aktif_kullanici.lower() == "ibrahim":
        st.markdown("---")
        st.markdown(
            '<div style="margin:0 0 20px;animation:fadeUp 0.95s ease-out">'
            '<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px">'
            '<div style="height:1px;flex:1;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.1))"></div>'
            '<div style="font-size:11px;color:#64748B;letter-spacing:3px;text-transform:uppercase;font-weight:700">Aktif Kullanıcılar</div>'
            '<div style="height:1px;flex:1;background:linear-gradient(90deg,rgba(255,255,255,0.1),transparent)"></div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True
        )
        # Son giriş zamanı da ek olarak göster (tüm kullanıcılar, son 24 saat)
        online_listesi = get_online_kullanicilar()
        # Son giriş bilgisi için tüm kullanıcıları al (son 24 saat)
        try:
            import datetime as _dt2
            sb2 = _get_supabase()
            _son_giris_map = {}
            if sb2:
                _sg_res = sb2.table("kullanici_durum").select("kullanici_adi, son_aktivite").execute()
                _son_giris_map = {r["kullanici_adi"]: r["son_aktivite"] for r in (_sg_res.data or [])}
        except Exception:
            _son_giris_map = {}
        if not online_listesi:
            st.markdown(
                '<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:20px 24px;text-align:center">'
                '<span style="color:#64748B;font-size:13px">Şu an aktif kullanıcı yok.</span>'
                '</div>',
                unsafe_allow_html=True
            )
        else:
            import datetime as _dt
            simdi = _dt.datetime.utcnow()
            cards_html = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-bottom:8px">'
            for u in online_listesi:
                k_adi = u.get("kullanici_adi", "?")
                son_akt = u.get("son_aktivite", "")
                try:
                    son_dt = _dt.datetime.fromisoformat(son_akt.replace("Z",""))
                    fark_sn = int((simdi - son_dt).total_seconds())
                    if fark_sn < 60:
                        zaman_str = f"{fark_sn}sn önce"
                    else:
                        zaman_str = f"{fark_sn // 60}dk önce"
                except Exception:
                    zaman_str = "az önce"
                ilk = k_adi[0].upper() if k_adi else "?"
                cards_html += (
                    f'<div style="background:rgba(16,185,129,0.06);border:1px solid rgba(16,185,129,0.2);border-radius:14px;padding:16px 18px;display:flex;align-items:center;gap:12px">'
                    f'<div style="position:relative;flex-shrink:0">'
                    f'<div style="width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#10B981,#059669);display:flex;align-items:center;justify-content:center;font-weight:700;color:white;font-size:15px">{ilk}</div>'
                    f'<div style="position:absolute;bottom:-2px;right:-2px;width:10px;height:10px;border-radius:50%;background:#10B981;border:2px solid #080C20;box-shadow:0 0 6px #10B981"></div>'
                    f'</div>'
                    f'<div style="overflow:hidden">'
                    f'<div style="color:#FFFFFF;font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{k_adi.capitalize()}</div>'
                    f'<div style="color:#6EE7B7;font-size:10px;font-weight:500;margin-top:2px">● {zaman_str}</div>'
                    f'</div>'
                    f'</div>'
                )
            cards_html += '</div>'
            st.markdown(
                f'<div style="margin-bottom:8px"><span style="color:#6EE7B7;font-size:12px;font-weight:600">{len(online_listesi)} kullanıcı aktif (son 5 dk)</span></div>'
                + cards_html,
                unsafe_allow_html=True
            )
        # Son giriş tablosu — tüm kullanıcılar
        if _son_giris_map:
            import datetime as _dt3
            _simdi3 = _dt3.datetime.utcnow()
            sg_html = '<div style="margin-top:16px"><div style="font-size:10px;color:#64748B;letter-spacing:2px;font-weight:700;text-transform:uppercase;margin-bottom:10px;padding-left:2px">Son Giriş Zamanları</div>'
            sg_html += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px">'
            for _kg, _sa in sorted(_son_giris_map.items()):
                try:
                    _sdt = _dt3.datetime.fromisoformat(_sa.replace("Z",""))
                    _fark = int((_simdi3 - _sdt).total_seconds())
                    if _fark < 60: _zs = f"{_fark}sn önce"
                    elif _fark < 3600: _zs = f"{_fark//60}dk önce"
                    elif _fark < 86400: _zs = f"{_fark//3600}sa önce"
                    else: _zs = f"{_fark//86400}g önce"
                except Exception:
                    _zs = "bilinmiyor"
                _online_su = any(u.get("kullanici_adi") == _kg for u in online_listesi)
                _renk = "#10B981" if _online_su else "#64748B"
                _bg = "rgba(16,185,129,0.06)" if _online_su else "rgba(255,255,255,0.02)"
                _border = "rgba(16,185,129,0.15)" if _online_su else "rgba(255,255,255,0.06)"
                sg_html += (
                    f'<div style="background:{_bg};border:1px solid {_border};border-radius:10px;padding:10px 14px;display:flex;align-items:center;justify-content:space-between">'
                    f'<span style="color:#E2E8F0;font-size:12px;font-weight:600">{_kg.capitalize()}</span>'
                    f'<span style="color:{_renk};font-size:10px;font-weight:500">{_zs}</span>'
                    f'</div>'
                )
            sg_html += '</div></div>'
            st.markdown(sg_html, unsafe_allow_html=True)

    # ─────────────────────────────────────────────────────────────────────
    # GELEN TALEPLER (sadece ibrahim görür)
    # ─────────────────────────────────────────────────────────────────────
    if aktif_kullanici.lower() == "ibrahim":
        st.markdown("---")
        st.markdown("### 📬 Gelen Talepler")
        try:
            from kayranpm.database import get_talepler
            talepler = get_talepler()
        except Exception:
            talepler = []
        if not talepler:
            st.info("Henüz talep yok.")
        else:
            for t in talepler:
                durum_renk = {"bekliyor": "🟡", "inceleniyor": "🔵", "tamamlandi": "🟢"}.get(t.get("durum",""), "⚪")
                with st.expander(f"{durum_renk} {t.get('konu','—')} · {t.get('gonderen','?')} · {str(t.get('olusturma_tarihi',''))[:16]}"):
                    st.write(t.get("mesaj",""))
                    st.caption(f"Durum: **{t.get('durum','bekliyor')}**")

    # ─────────────────────────────────────────────────────────────────────
    # DUYURU YÖNETİMİ PANELİ (sadece ibrahim görür)
    # ─────────────────────────────────────────────────────────────────────
    if aktif_kullanici.lower() == "ibrahim":
        st.markdown("---")
        st.markdown(
            '<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">'
            '<div style="height:1px;flex:1;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.1))"></div>'
            '<div style="font-size:11px;color:#64748B;letter-spacing:3px;text-transform:uppercase;font-weight:700">Sistem Duyurusu</div>'
            '<div style="height:1px;flex:1;background:linear-gradient(90deg,rgba(255,255,255,0.1),transparent)"></div>'
            '</div>',
            unsafe_allow_html=True
        )
        _mevcut_aktif, _mevcut_metni = get_duyuru()
        _durum_etiketi = "🟢 Aktif" if _mevcut_aktif else "🔴 Kapalı"
        st.markdown(
            f'<div style="color:#94A3B8;font-size:12px;margin-bottom:12px">'
            f'Mevcut durum: <b style="color:#E2E8F0">{_durum_etiketi}</b>'
            f'{(" — " + _mevcut_metni[:60] + ("..." if len(_mevcut_metni)>60 else "")) if _mevcut_metni else ""}'
            f'</div>',
            unsafe_allow_html=True
        )
        with st.form("duyuru_form", clear_on_submit=False):
            _yeni_aktif = st.checkbox("Duyuruyu Aktifleştir", value=bool(_mevcut_aktif))
            _yeni_metni = st.text_input("Duyuru Metni", value=_mevcut_metni, placeholder="Örn: Sistem bugün 18:00-19:00 arası bakımda olacak.")
            _duyuru_kaydet = st.form_submit_button("💾 Duyuruyu Kaydet", type="primary", use_container_width=False)
            if _duyuru_kaydet:
                if set_duyuru(_yeni_aktif, _yeni_metni or ""):
                    st.success("✅ Duyuru kaydedildi! Sayfa yenileniyor...")
                    st.rerun()
                else:
                    st.error("❌ Kayıt başarısız.")

    # ─────────────────────────────────────────────────────────────────────
    # BİLDİRİM GÖNDERME PANELİ (sadece ibrahim görür)
    # ─────────────────────────────────────────────────────────────────────
    if aktif_kullanici.lower() == "ibrahim":
        st.markdown("---")
        st.markdown(
            '<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">'
            '<div style="height:1px;flex:1;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.1))"></div>'
            '<div style="font-size:11px;color:#64748B;letter-spacing:3px;text-transform:uppercase;font-weight:700">Bildirim Gönder</div>'
            '<div style="height:1px;flex:1;background:linear-gradient(90deg,rgba(255,255,255,0.1),transparent)"></div>'
            '</div>',
            unsafe_allow_html=True
        )
        _tum_kullanicilar = sorted((KAYRANACC_KULLANICILAR | KAYRANPM_KULLANICILAR) - {"ibrahim"})
        with st.form("bildirim_form", clear_on_submit=True):
            _alici_sec = st.selectbox("Alıcı", ["Herkese Gönder"] + [k.capitalize() for k in _tum_kullanicilar])
            _bildirim_mesaj = st.text_area("Mesaj", placeholder="Kullanıcılara göndermek istediğin mesajı yaz...", height=100)
            _bildirim_gonder_btn = st.form_submit_button("📢 Bildirimi Gönder", type="primary", use_container_width=False)
            if _bildirim_gonder_btn:
                if not _bildirim_mesaj or not _bildirim_mesaj.strip():
                    st.warning("⚠️ Mesaj boş olamaz.")
                else:
                    if _alici_sec == "Herkese Gönder":
                        _ok2 = bildirim_gonder_herkese(_bildirim_mesaj.strip(), list(_tum_kullanicilar))
                        _alici_str = "herkese"
                    else:
                        _ok2 = bildirim_gonder(_alici_sec.lower(), _bildirim_mesaj.strip())
                        _alici_str = _alici_sec + " kişisine"
                    if _ok2:
                        st.success(f"✅ Bildirim {_alici_str} gönderildi!")
                    else:
                        st.error("❌ Bildirim gönderilemedi.")


# ─────────────────────────────────────────────────────────────────────
# 3.5) KAYRANTS&W — YAKINDA SİZLERLE
# ─────────────────────────────────────────────────────────────────────
def sifre_degistir():
    """Kullanıcının kendi şifresini değiştirebileceği sayfa."""
    aktif_kullanici = st.session_state.get("aktif_kullanici", "")
    ilk_harf = aktif_kullanici[0].upper() if aktif_kullanici else "U"

    st.markdown(portal_css(), unsafe_allow_html=True)

    # ─── BAŞLIK ───────────────────────────────────────────────────────────────
    st.markdown(
        '<div style="margin-bottom:32px;animation:fadeUp 0.6s ease-out">'
        '<div style="display:inline-block;padding:6px 14px;background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.25);border-radius:20px;margin-bottom:18px">'
        '<span style="color:#A5B4FC;font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase">🔑 Güvenlik</span>'
        '</div>'
        '<h1 style="font-family:Inter,sans-serif;font-size:clamp(24px,5vw,36px);font-weight:800;color:#FFFFFF;margin:0">Şifremi Değiştir</h1>'
        '<p style="color:#94A3B8;font-size:14px;margin-top:8px">Yeni şifren Supabase&#39;de güvenli şekilde saklanır &mdash; Streamlit Secrets&#39;tan bağımsızdır.</p>'
        '</div>',
        unsafe_allow_html=True
    )

    # ─── FORM CSS ─────────────────────────────────────────────────────────────
    st.markdown(
        '<style>'
        '[data-testid="stTextInput"] label{color:#CBD5E1 !important;font-weight:600 !important;'
        'font-size:12px !important;letter-spacing:.5px !important;text-transform:uppercase !important;}'
        '[data-testid="stTextInput"] input{background:rgba(255,255,255,0.04) !important;'
        'border:1px solid rgba(255,255,255,0.12) !important;color:#FFFFFF !important;border-radius:12px !important;}'
        '[data-testid="stTextInput"] input:focus{border-color:#8B5CF6 !important;'
        'box-shadow:0 0 0 3px rgba(139,92,246,0.15) !important;}'
        '.stFormSubmitButton>button{background:linear-gradient(135deg,#6366F1,#8B5CF6) !important;'
        'color:#fff !important;border:none !important;border-radius:12px !important;'
        'font-weight:600 !important;box-shadow:0 4px 20px rgba(99,102,241,0.35) !important;}'
        '</style>',
        unsafe_allow_html=True
    )

    # ─── FORM ─────────────────────────────────────────────────────────────────
    col_l, col_c, col_r = st.columns([1, 1.4, 1])
    with col_c:
        st.markdown(
            '<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);'
            'border-radius:20px;padding:32px 28px;">'
            f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:24px;'
            f'padding-bottom:16px;border-bottom:1px solid rgba(255,255,255,0.06)">'
            f'<div style="width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#6366F1,#8B5CF6);'
            f'display:flex;align-items:center;justify-content:center;font-weight:700;color:white;font-size:14px">{ilk_harf}</div>'
            f'<div><div style="color:#FFFFFF;font-weight:600;font-size:14px">{aktif_kullanici.capitalize()}</div>'
            f'<div style="color:#64748B;font-size:11px">Şifre değiştirme</div></div>'
            f'</div>'
            '</div>',
            unsafe_allow_html=True
        )

        with st.form("sifre_degistir_form", clear_on_submit=True):
            mevcut = st.text_input("Mevcut Şifre", type="password", placeholder="Mevcut şifrenizi girin")
            yeni   = st.text_input("Yeni Şifre",   type="password", placeholder="En az 6 karakter")
            tekrar = st.text_input("Yeni Şifre (Tekrar)", type="password", placeholder="Yeni şifreyi tekrar girin")
            kaydet = st.form_submit_button("🔑 Şifreyi Güncelle", type="primary", use_container_width=True)

        if kaydet:
            # Validasyonlar
            if not mevcut or not yeni or not tekrar:
                st.error("❌ Tüm alanları doldurun.")
            elif len(yeni) < 6:
                st.error("❌ Yeni şifre en az 6 karakter olmalı.")
            elif yeni != tekrar:
                st.error("❌ Yeni şifreler eşleşmiyor.")
            else:
                # Mevcut şifreyi doğrula (Supabase öncelikli)
                try:
                    kullanicilar = st.secrets.get("kullanicilar", {})
                    from shared.auth import kullanici_dogrula_v2, sifre_hash_uret, supabase_sifre_kaydet
                    if not kullanici_dogrula_v2(aktif_kullanici, mevcut, kullanicilar):
                        st.error("❌ Mevcut şifreniz hatalı.")
                    else:
                        yeni_hash = sifre_hash_uret(yeni)
                        if supabase_sifre_kaydet(aktif_kullanici, yeni_hash):
                            st.success("✅ Şifreniz başarıyla güncellendi! Bir sonraki girişte yeni şifreniz geçerli olacak.")
                            st.balloons()
                        else:
                            st.error("❌ Şifre kaydedilemedi. Lütfen tekrar deneyin veya yöneticiye bildirin.")
                except Exception as e:
                    st.error(f"❌ Bir hata oluştu: {e}")

        st.markdown(
            '<div style="margin-top:16px;padding:12px 16px;background:rgba(99,102,241,0.08);'
            'border:1px solid rgba(99,102,241,0.2);border-radius:10px">'
            '<div style="color:#A5B4FC;font-size:11px;font-weight:600;margin-bottom:4px">💡 Bilgi</div>'
            '<div style="color:#94A3B8;font-size:11px;line-height:1.6">'
            'Yeni şifren Supabase&#39;de güvenli hash olarak saklanır. '
            'Sadece sen değiştirebilirsin &mdash; yönetici dahil kimse eski şifreni göremez.'
            '</div>'
            '</div>',
            unsafe_allow_html=True
        )

def kayrantsw_yakinda():
    """KAYRANTS&W modülü için 'Yakında Sizlerle' bilgilendirme sayfası."""
    st.markdown(portal_css(), unsafe_allow_html=True)

    st.markdown(
        '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;'
        'text-align:center;padding:48px 20px 24px;animation:fadeUp 0.6s ease-out">'
        # İkon rozeti
        '<div style="width:96px;height:96px;border-radius:24px;'
        'background:linear-gradient(135deg,rgba(99,102,241,0.25),rgba(236,72,153,0.2));'
        'border:1px solid rgba(139,92,246,0.35);display:flex;align-items:center;justify-content:center;'
        'font-size:46px;margin-bottom:28px;box-shadow:0 10px 40px rgba(99,102,241,0.25)">🚧</div>'
        # Uygulama adı rozeti
        '<div style="display:inline-block;padding:6px 16px;background:rgba(99,102,241,0.12);'
        'border:1px solid rgba(99,102,241,0.25);border-radius:20px;margin-bottom:20px">'
        '<span style="color:#A5B4FC;font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase">KAYRANTS&amp;W</span>'
        '</div>'
        # Başlık
        '<h1 style="font-family:Inter,sans-serif;font-size:clamp(26px,5vw,44px);font-weight:800;color:#FFFFFF;'
        'letter-spacing:1px;margin:0;line-height:1.1">'
        '<span style="background:linear-gradient(90deg,#60A5FA,#A78BFA,#F472B6);'
        '-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">YAKINDA SİZLERLE</span>'
        '</h1>'
        # Alt açıklama
        '<p style="color:#94A3B8;font-size:15px;margin-top:18px;max-width:480px;line-height:1.7;font-weight:400">'
        'Depo & Teknik Servis üzerinde çalışıyoruz. Çok yakında bu modül de KAYRAN Workspace ailesine katılacak. '
        'Gelişmelerden haberdar olmak için takipte kalın.'
        '</p>'
        # Dekoratif çizgi
        '<div style="width:80px;height:3px;margin:28px auto 0;'
        'background:linear-gradient(90deg,#6366F1,#A78BFA,#EC4899);border-radius:2px"></div>'
        '</div>',
        unsafe_allow_html=True
    )

    # Ana sayfaya dön butonu (ortalı)
    col_l, col_c, col_r = st.columns([1, 1.2, 1])
    with col_c:
        if st.button("🏠  Ana Sayfaya Dön", key="tsw_ana_don", use_container_width=True):
            st.session_state.aktif_uygulama = "anasayfa"
            st.rerun()


# ─────────────────────────────────────────────────────────────────────
# 4) GLOBAL HATA KARTI
# ─────────────────────────────────────────────────────────────────────
def _global_hata_kart(uygulama_adi, hata):
    st.markdown(
        '<div style="background:#FEE2E2;border:1px solid #FCA5A5;border-left:4px solid #DC2626;border-radius:12px;padding:24px 28px;margin:30px auto;max-width:700px">'
        '<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px">'
        '<span style="font-size:32px">⚠️</span>'
        f'<b style="color:#991B1B;font-size:18px">{uygulama_adi} Uygulamasında Bir Sorun Oluştu</b>'
        '</div>'
        '<div style="color:#7F1D1D;font-size:14px;line-height:1.6;margin-bottom:14px">'
        'Üzgünüz, beklenmedik bir hata oluştu. Verileriniz güvende — sadece bu işlem tamamlanamadı.'
        '</div>'
        '<div style="background:#FFFFFF;border:1px solid #FCA5A5;border-radius:8px;padding:12px 16px;font-family:monospace;font-size:12px;color:#991B1B;margin-bottom:14px;overflow-x:auto">'
        f'<b>Hata:</b> {type(hata).__name__}: {str(hata)[:300]}'
        '</div>'
        '<div style="font-size:12px;color:#991B1B">'
        '💡 <b>Ne yapabilirim?</b> Tarayıcı önbelleğini temizle (Ctrl+F5) · Ana sayfaya dön · Sorun devam ederse yöneticiye bildir'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    with st.expander("🔧 Teknik Detay"):
        st.code(traceback.format_exc(), language="python")

    if st.button("🏠 Ana Sayfaya Dön", key="hata_ana_don", type="primary"):
        st.session_state.aktif_uygulama = "anasayfa"
        st.rerun()


# ─────────────────────────────────────────────────────────────────────
# 5) ANA ROUTING
# ─────────────────────────────────────────────────────────────────────
def main():
    # Login yapılmamışsa giriş ekranı
    if not st.session_state.giris_yapildi:
        giris_ekrani()
        return

    # Sidebar her zaman görünür (login sonrası)
    portal_sidebar()

    # Aktif kullanıcının online durumunu güncelle
    online_durum_guncelle(st.session_state.aktif_kullanici)

    aktif = st.session_state.aktif_uygulama
    yetkiler = kullanici_yetkileri(st.session_state.aktif_kullanici)

    # Yetki kontrolü
    if aktif == "kayranacc" and not yetkiler["kayranacc"]:
        st.error("🔒 Muhasebe & Finans uygulamasına erişim yetkiniz yok.")
        st.session_state.aktif_uygulama = "anasayfa"
        return
    if aktif == "kayranpm" and not yetkiler["kayranpm"]:
        st.error("🔒 İthalat & Ürün Yönetimi uygulamasına erişim yetkiniz yok.")
        st.session_state.aktif_uygulama = "anasayfa"
        return

    # Sayfa dispatch
    try:
        if aktif == "anasayfa":
            anasayfa()
        elif aktif == "kayranacc":
            from kayranacc.main import run as kayranacc_run
            kayranacc_run()
        elif aktif == "kayranpm":
            from kayranpm.main import run as kayranpm_run
            kayranpm_run()
        elif aktif == "hesap_makinesi":
            from hesap_makinesi.main import run as hesap_makinesi_run
            hesap_makinesi_run()
        elif aktif == "kayrantsw":
            kayrantsw_yakinda()
        elif aktif == "sifre_degistir":
            sifre_degistir()
        else:
            st.error(f"Bilinmeyen sayfa: {aktif}")
            st.session_state.aktif_uygulama = "anasayfa"
            if st.button("← Ana Sayfaya Dön"):
                st.rerun()
    except Exception as hata:
        ad = "KAYRAN" if aktif == "kayranacc" else ("KAYRAN" if aktif == "kayranpm" else aktif)
        _global_hata_kart(ad, hata)


if __name__ == "__main__":
    main()
else:
    main()
