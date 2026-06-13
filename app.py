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


# ─────────────────────────────────────────────────────────────────────
# YETKİ TANIMLARI
# ─────────────────────────────────────────────────────────────────────
KAYRANACC_KULLANICILAR = {"ibrahim", "derman", "cem", "pamuk", "serkan", "yilmaz", "korkut"}
KAYRANPM_KULLANICILAR  = {"ibrahim", "gokhan", "derya"}

DUYURU_AKTIF = True
DUYURU_METNI = "✨ Yeni: Sidebar navigasyon ve ana sayfa eklendi"


def kullanici_yetkileri(kullanici):
    k = (kullanici or "").lower().strip()
    return {
        "kayranacc": k in KAYRANACC_KULLANICILAR,
        "kayranpm":  k in KAYRANPM_KULLANICILAR,
    }


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
KAYRAN_LOGO_SVG = '<svg width="40" height="40" viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="logoGrad" x1="0" y1="0" x2="56" y2="56" gradientUnits="userSpaceOnUse"><stop offset="0%" stop-color="#60A5FA"/><stop offset="50%" stop-color="#A78BFA"/><stop offset="100%" stop-color="#F472B6"/></linearGradient></defs><rect width="56" height="56" rx="14" fill="url(#logoGrad)"/><path d="M16 12 L16 44" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/><path d="M16 28 L38 12" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/><path d="M16 28 L38 44" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/><circle cx="42" cy="14" r="3" fill="#FFFFFF" opacity="0.9"/></svg>'

KAYRAN_LOGO_BIG = '<svg width="64" height="64" viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="logoGradB" x1="0" y1="0" x2="56" y2="56" gradientUnits="userSpaceOnUse"><stop offset="0%" stop-color="#60A5FA"/><stop offset="50%" stop-color="#A78BFA"/><stop offset="100%" stop-color="#F472B6"/></linearGradient></defs><rect width="56" height="56" rx="14" fill="url(#logoGradB)"/><path d="M16 12 L16 44" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/><path d="M16 28 L38 12" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/><path d="M16 28 L38 44" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/><circle cx="42" cy="14" r="3" fill="#FFFFFF" opacity="0.9"/></svg>'


# ─────────────────────────────────────────────────────────────────────
# CSS — Login + Portal
# ─────────────────────────────────────────────────────────────────────
def login_css():
    return """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    .stApp {
        background: #0a0e27 !important;
        font-family: 'Manrope', -apple-system, sans-serif !important;
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
        background: #0a0e27; overflow: hidden;
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
        background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%) !important;
        color: white !important;
        font-family: 'Manrope', sans-serif !important;
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
        font-family: 'Manrope', sans-serif !important;
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
    </style>

    <div class="kayran-bg"></div>
    """


def portal_css():
    """Ana sayfa + sidebar CSS (alt uygulamalar yüklenmedikçe geçerli)"""
    return """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    .stApp {
        background: #0a0e27 !important;
        font-family: 'Manrope', -apple-system, sans-serif !important;
    }
    [data-testid="stHeader"] { background: transparent !important; }
    .stDeployButton { display: none !important; }
    footer { display: none !important; }
    #MainMenu { display: none !important; }

    /* ── STREAMLIT SIDEBAR — Custom KAYRAN Stil ── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1230 0%, #0a0e27 100%) !important;
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
        font-family: 'Manrope', sans-serif !important;
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
        background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%) !important;
        color: white !important;
        font-family: 'Manrope', sans-serif !important;
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
    if DUYURU_AKTIF:
        st.markdown(f'<div class="duyuru-band">{DUYURU_METNI}</div>', unsafe_allow_html=True)

    st.markdown('<div style="height:60px"></div>', unsafe_allow_html=True)

    col_l, col_main, col_r = st.columns([1, 2, 1])

    with col_main:
        st.markdown(
            '<div style="text-align:center;padding:20px 0 28px;animation:fadeUp 0.6s ease-out">'
            '<div style="display:flex;justify-content:center;margin-bottom:24px">'
            f'{KAYRAN_LOGO_BIG}'
            '</div>'
            '<div style="font-family:Manrope,sans-serif;font-size:42px;font-weight:800;color:#FFFFFF;letter-spacing:6px;line-height:1">KAYRAN</div>'
            '<div style="font-size:11px;color:#64748B;letter-spacing:4px;text-transform:uppercase;margin-top:10px;font-weight:600">Şirket Yönetim Sistemi</div>'
            '<div style="width:60px;height:2px;margin:18px auto 0;background:linear-gradient(90deg,#6366F1,#A78BFA,#EC4899);border-radius:2px"></div>'
            '</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            '<div style="background:rgba(255,255,255,0.03);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.08);border-radius:20px;padding:32px 32px 8px;margin-top:8px;box-shadow:0 20px 60px rgba(0,0,0,0.4)">'
            '<div style="display:flex;align-items:center;gap:10px;margin-bottom:24px">'
            '<div style="width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,rgba(99,102,241,0.2),rgba(139,92,246,0.2));display:flex;align-items:center;justify-content:center;border:1px solid rgba(139,92,246,0.3)">'
            '<span style="font-size:14px">🔐</span>'
            '</div>'
            '<div>'
            '<div style="color:#CBD5E1;font-size:14px;font-weight:600">Güvenli Giriş</div>'
            '<div style="color:#64748B;font-size:11px">Lütfen kimlik bilgilerinizi girin</div>'
            '</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True
        )

        with st.form("giris_form", clear_on_submit=False):
            kullanici = st.text_input("Kullanıcı Adı", placeholder="ornek_kullanici", key="login_user")
            sifre = st.text_input("Şifre", type="password", placeholder="••••••••", key="login_pass")
            st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
            giris_btn = st.form_submit_button("Giriş Yap →", type="primary", use_container_width=True)

        if giris_btn:
            try:
                kullanicilar = st.secrets.get("kullanicilar", {})
                if not kullanicilar:
                    st.warning("⚠️ Kullanıcı ayarları yapılandırılmamış. Streamlit Secrets bölümünden ekleyin.")
                    return
                if kullanici in kullanicilar and kullanicilar[kullanici] == sifre:
                    st.session_state.giris_yapildi = True
                    st.session_state.aktif_kullanici = kullanici
                    st.session_state.aktif_uygulama = "anasayfa"
                    st.rerun()
                else:
                    st.error("❌ Kullanıcı adı veya şifre hatalı.")
            except Exception as e:
                st.error(f"Giriş sistemi hatası: {e}")


# ─────────────────────────────────────────────────────────────────────
# 2) SIDEBAR NAVIGATION (Portal)
# ─────────────────────────────────────────────────────────────────────
def portal_sidebar(kompakt=False):
    """Streamlit'in resmi sidebar'ına KAYRAN'ın navigasyonunu çizer.

    Args:
        kompakt: True ise alt uygulama içindeyken sadece üst bar (Ana Sayfa + uygulamalar)
                 False ise tam navigasyon (hesap kartı + çıkış dahil)
    """
    aktif_kullanici = st.session_state.get("aktif_kullanici", "")
    aktif_sayfa = st.session_state.get("aktif_uygulama", "anasayfa")
    yetkiler = kullanici_yetkileri(aktif_kullanici)
    ilk_harf = aktif_kullanici[0].upper() if aktif_kullanici else "U"

    with st.sidebar:
        # Logo + KAYRAN başlığı (her zaman)
        st.markdown(
            '<div style="display:flex;align-items:center;gap:12px;padding:4px 0 16px;border-bottom:1px solid rgba(255,255,255,0.06);margin-bottom:14px">'
            f'{KAYRAN_LOGO_SVG}'
            '<div>'
            '<div style="font-family:Manrope,sans-serif;font-size:18px;font-weight:800;color:#FFFFFF;letter-spacing:2px;line-height:1">KAYRAN</div>'
            '<div style="font-size:9px;color:#64748B;letter-spacing:1.5px;text-transform:uppercase;margin-top:3px;font-weight:600">Workspace</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True
        )

        # NAVIGASYON grubu — daima görünür
        st.markdown(
            '<div style="font-size:10px;color:#64748B;letter-spacing:2px;font-weight:700;text-transform:uppercase;margin:4px 0 8px;padding-left:6px">NAVİGASYON</div>',
            unsafe_allow_html=True
        )

        if st.button(
            "🏠  Ana Sayfa",
            key="nav_anasayfa",
            type="primary" if aktif_sayfa == "anasayfa" else "secondary",
            use_container_width=True
        ):
            st.session_state.aktif_uygulama = "anasayfa"
            st.rerun()

        # KAYRANACC
        if yetkiler["kayranacc"]:
            if st.button(
                "💳  KAYRANACC",
                key="nav_kayranacc",
                type="primary" if aktif_sayfa == "kayranacc" else "secondary",
                use_container_width=True
            ):
                st.session_state.aktif_uygulama = "kayranacc"
                st.rerun()
        else:
            st.button(
                "🔒  KAYRANACC",
                key="nav_kayranacc_disabled",
                disabled=True,
                use_container_width=True,
                help="Bu uygulamaya erişim yetkiniz yok"
            )

        # KAYRANPM
        if yetkiler["kayranpm"]:
            if st.button(
                "📦  KAYRANPM",
                key="nav_kayranpm",
                type="primary" if aktif_sayfa == "kayranpm" else "secondary",
                use_container_width=True
            ):
                st.session_state.aktif_uygulama = "kayranpm"
                st.rerun()
        else:
            st.button(
                "🔒  KAYRANPM",
                key="nav_kayranpm_disabled",
                disabled=True,
                use_container_width=True,
                help="Bu uygulamaya erişim yetkiniz yok"
            )

        # Ayırıcı çizgi
        st.markdown(
            '<div style="height:1px;background:rgba(255,255,255,0.06);margin:14px 0 14px"></div>',
            unsafe_allow_html=True
        )

        # Alt uygulama açıksa: o uygulamanın sidebar içeriği BURADAN sonra yüklenir
        # Ana sayfadaysak: HESAP bölümü
        if aktif_sayfa == "anasayfa":
            # Kullanıcı + Çıkış (sadece ana sayfada)
            st.markdown(
                '<div style="font-size:10px;color:#64748B;letter-spacing:2px;font-weight:700;text-transform:uppercase;margin:4px 0 10px;padding-left:6px">HESAP</div>',
                unsafe_allow_html=True
            )
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;padding:10px 12px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:10px;margin-bottom:8px">'
                f'<div style="width:30px;height:30px;border-radius:8px;background:linear-gradient(135deg,#6366F1,#8B5CF6);display:flex;align-items:center;justify-content:center;font-weight:700;color:white;font-size:13px">{ilk_harf}</div>'
                f'<div style="overflow:hidden">'
                f'<div style="color:#94A3B8;font-size:9px;font-weight:600;letter-spacing:0.5px;text-transform:uppercase;line-height:1">Oturum</div>'
                f'<div style="color:#FFFFFF;font-weight:600;font-size:12px;margin-top:2px;line-height:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{aktif_kullanici.capitalize()}</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True
            )

            if st.button("🚪  Çıkış Yap", key="nav_cikis", use_container_width=True):
                st.session_state.giris_yapildi = False
                st.session_state.aktif_kullanici = ""
                st.session_state.aktif_uygulama = "anasayfa"
                st.rerun()
        else:
            # Alt uygulama içindeyken: küçük "Sayfalar" başlığı
            # (KAYRANACC/PM kendi st.radio'larıyla buraya ekleyecek)
            uyg_adi = "KAYRANACC" if aktif_sayfa == "kayranacc" else "KAYRANPM"
            uyg_renk = "#A5B4FC" if aktif_sayfa == "kayranacc" else "#F9A8D4"
            st.markdown(
                f'<div style="font-size:10px;color:{uyg_renk};letter-spacing:2px;font-weight:700;text-transform:uppercase;margin:4px 0 8px;padding-left:6px">📂 {uyg_adi} SAYFALARI</div>',
                unsafe_allow_html=True
            )


# ─────────────────────────────────────────────────────────────────────
# 3) ANA SAYFA (Welcome Dashboard)
# ─────────────────────────────────────────────────────────────────────
def anasayfa():
    aktif_kullanici = st.session_state.get("aktif_kullanici", "")
    yetkiler = kullanici_yetkileri(aktif_kullanici)

    st.markdown(portal_css(), unsafe_allow_html=True)

    if DUYURU_AKTIF:
        st.markdown(
            f'<div style="background:linear-gradient(90deg,rgba(59,130,246,0.12),rgba(139,92,246,0.12),rgba(236,72,153,0.12));border:1px solid rgba(99,102,241,0.2);border-radius:12px;padding:10px 16px;text-align:center;color:#A5B4FC;font-size:12px;font-weight:500;margin-bottom:24px;animation:fadeUp 0.5s ease-out">{DUYURU_METNI}</div>',
            unsafe_allow_html=True
        )

    # Hoşgeldin başlığı
    saat = datetime.now().hour
    if saat < 12: selamlama = "Günaydın"
    elif saat < 18: selamlama = "İyi günler"
    else: selamlama = "İyi akşamlar"

    st.markdown(
        '<div style="margin-bottom:36px;animation:fadeUp 0.6s ease-out">'
        '<div style="display:inline-block;padding:6px 14px;background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.25);border-radius:20px;margin-bottom:18px">'
        '<span style="color:#A5B4FC;font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase">🏠 Ana Sayfa</span>'
        '</div>'
        f'<h1 style="font-family:Manrope,sans-serif;font-size:38px;font-weight:800;color:#FFFFFF;letter-spacing:-0.5px;line-height:1.1;margin:0">'
        f'{selamlama}, '
        f'<span style="background:linear-gradient(90deg,#60A5FA,#A78BFA,#F472B6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">{aktif_kullanici.capitalize()}</span>'
        '</h1>'
        '<p style="color:#94A3B8;font-size:15px;margin-top:8px;font-weight:400">'
        'KAYRAN Workspace\'e hoş geldin. Sol menüden uygulamana erişebilirsin.'
        '</p>'
        '</div>',
        unsafe_allow_html=True
    )

    # Yetki istatistikleri
    erisilebilir = sum(1 for v in yetkiler.values() if v)
    toplam_uygulama = len(yetkiler)

    st.markdown(
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:36px;animation:fadeUp 0.7s ease-out">'
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
        '<span style="color:#FFFFFF;font-size:24px;font-weight:700;font-family:JetBrains Mono,monospace">v1.1</span>'
        '<span style="color:#64748B;font-size:12px">.0</span>'
        '</div>'
        '<div style="color:#F9A8D4;font-size:11px;font-weight:500;margin-top:6px">🎨 Sidebar nav</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # Uygulama erişim kartları
    st.markdown(
        '<div style="margin:40px 0 16px;animation:fadeUp 0.8s ease-out">'
        '<div style="font-size:11px;color:#64748B;letter-spacing:2px;text-transform:uppercase;font-weight:700;margin-bottom:14px">Uygulamalar</div>'
        '</div>',
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2, gap="medium")

    # KAYRANACC
    with col1:
        if yetkiler["kayranacc"]:
            st.markdown(
                '<div style="position:relative;background:linear-gradient(135deg,rgba(99,102,241,0.12),rgba(59,130,246,0.06));border:1px solid rgba(99,102,241,0.25);border-radius:20px;padding:28px 26px 20px;overflow:hidden;min-height:200px;animation:fadeUp 0.9s ease-out">'
                '<div style="position:absolute;top:-40px;right:-40px;width:180px;height:180px;background:radial-gradient(circle,rgba(99,102,241,0.4),transparent 70%);border-radius:50%;pointer-events:none"></div>'
                '<div style="display:inline-flex;align-items:center;gap:6px;padding:4px 10px;background:rgba(99,102,241,0.2);border:1px solid rgba(99,102,241,0.35);border-radius:12px;margin-bottom:16px;position:relative;z-index:2">'
                '<div style="width:5px;height:5px;border-radius:50%;background:#A5B4FC"></div>'
                '<span style="color:#C7D2FE;font-size:9px;font-weight:600;letter-spacing:1px;text-transform:uppercase">Finans</span>'
                '</div>'
                '<div style="display:flex;align-items:center;gap:14px;margin-bottom:14px;position:relative;z-index:2">'
                '<div style="width:52px;height:52px;border-radius:14px;background:linear-gradient(135deg,#6366F1,#8B5CF6);display:flex;align-items:center;justify-content:center;box-shadow:0 8px 24px rgba(99,102,241,0.4)">'
                '<span style="font-size:26px">💳</span>'
                '</div>'
                '<div>'
                '<div style="font-family:Manrope,sans-serif;font-size:20px;font-weight:800;color:#FFFFFF;letter-spacing:0.3px;line-height:1.1">KAYRANACC</div>'
                '<div style="font-size:11px;color:#A5B4FC;letter-spacing:0.5px;font-weight:600;text-transform:uppercase;margin-top:3px">Ödeme Takip Sistemi</div>'
                '</div>'
                '</div>'
                '<div style="font-size:12px;line-height:1.6;color:#CBD5E1;position:relative;z-index:2">'
                'Haftalık ödemeler · Banka bakiyeleri · Çek takibi · Nakit akış · Toplam aktifler'
                '</div>'
                '</div>',
                unsafe_allow_html=True
            )
            if st.button("→ KAYRANACC'yi Aç", key="acc_aç_home", use_container_width=True):
                st.session_state.aktif_uygulama = "kayranacc"
                st.rerun()
        else:
            st.markdown(
                '<div style="position:relative;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:20px;padding:28px 26px 20px;min-height:200px;opacity:0.6;animation:fadeUp 0.9s ease-out">'
                '<div style="display:inline-flex;align-items:center;gap:6px;padding:4px 10px;background:rgba(100,116,139,0.15);border:1px solid rgba(100,116,139,0.2);border-radius:12px;margin-bottom:16px">'
                '<span style="color:#94A3B8;font-size:9px;font-weight:600;letter-spacing:1px;text-transform:uppercase">🔒 Kilitli</span>'
                '</div>'
                '<div style="display:flex;align-items:center;gap:14px;margin-bottom:14px">'
                '<div style="width:52px;height:52px;border-radius:14px;background:rgba(100,116,139,0.15);border:1px solid rgba(100,116,139,0.2);display:flex;align-items:center;justify-content:center">'
                '<span style="font-size:26px;filter:grayscale(1)">💳</span>'
                '</div>'
                '<div>'
                '<div style="font-family:Manrope,sans-serif;font-size:20px;font-weight:800;color:#64748B;letter-spacing:0.3px;line-height:1.1">KAYRANACC</div>'
                '<div style="font-size:11px;color:#475569;letter-spacing:0.5px;font-weight:600;text-transform:uppercase;margin-top:3px">Ödeme Takip Sistemi</div>'
                '</div>'
                '</div>'
                '<div style="font-size:12px;line-height:1.6;color:#475569">'
                'Bu uygulamaya erişim yetkiniz yok. Yetki için yöneticinizle iletişime geçin.'
                '</div>'
                '</div>',
                unsafe_allow_html=True
            )

    # KAYRANPM
    with col2:
        if yetkiler["kayranpm"]:
            st.markdown(
                '<div style="position:relative;background:linear-gradient(135deg,rgba(236,72,153,0.12),rgba(244,114,182,0.06));border:1px solid rgba(236,72,153,0.25);border-radius:20px;padding:28px 26px 20px;overflow:hidden;min-height:200px;animation:fadeUp 1s ease-out">'
                '<div style="position:absolute;top:-40px;right:-40px;width:180px;height:180px;background:radial-gradient(circle,rgba(236,72,153,0.4),transparent 70%);border-radius:50%;pointer-events:none"></div>'
                '<div style="display:inline-flex;align-items:center;gap:6px;padding:4px 10px;background:rgba(236,72,153,0.2);border:1px solid rgba(236,72,153,0.35);border-radius:12px;margin-bottom:16px;position:relative;z-index:2">'
                '<div style="width:5px;height:5px;border-radius:50%;background:#F9A8D4"></div>'
                '<span style="color:#FBCFE8;font-size:9px;font-weight:600;letter-spacing:1px;text-transform:uppercase">Operasyon</span>'
                '</div>'
                '<div style="display:flex;align-items:center;gap:14px;margin-bottom:14px;position:relative;z-index:2">'
                '<div style="width:52px;height:52px;border-radius:14px;background:linear-gradient(135deg,#EC4899,#F472B6);display:flex;align-items:center;justify-content:center;box-shadow:0 8px 24px rgba(236,72,153,0.4)">'
                '<span style="font-size:26px">📦</span>'
                '</div>'
                '<div>'
                '<div style="font-family:Manrope,sans-serif;font-size:20px;font-weight:800;color:#FFFFFF;letter-spacing:0.3px;line-height:1.1">KAYRANPM</div>'
                '<div style="font-size:11px;color:#F9A8D4;letter-spacing:0.5px;font-weight:600;text-transform:uppercase;margin-top:3px">Ürün & Stok Yönetimi</div>'
                '</div>'
                '</div>'
                '<div style="font-size:12px;line-height:1.6;color:#CBD5E1;position:relative;z-index:2">'
                'Ürün dashboard · Stok takibi · Sipariş önerisi · Kampanya · Satın alma'
                '</div>'
                '</div>',
                unsafe_allow_html=True
            )
            if st.button("→ KAYRANPM'yi Aç", key="pm_aç_home", use_container_width=True):
                st.session_state.aktif_uygulama = "kayranpm"
                st.rerun()
        else:
            st.markdown(
                '<div style="position:relative;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:20px;padding:28px 26px 20px;min-height:200px;opacity:0.6;animation:fadeUp 1s ease-out">'
                '<div style="display:inline-flex;align-items:center;gap:6px;padding:4px 10px;background:rgba(100,116,139,0.15);border:1px solid rgba(100,116,139,0.2);border-radius:12px;margin-bottom:16px">'
                '<span style="color:#94A3B8;font-size:9px;font-weight:600;letter-spacing:1px;text-transform:uppercase">🔒 Kilitli</span>'
                '</div>'
                '<div style="display:flex;align-items:center;gap:14px;margin-bottom:14px">'
                '<div style="width:52px;height:52px;border-radius:14px;background:rgba(100,116,139,0.15);border:1px solid rgba(100,116,139,0.2);display:flex;align-items:center;justify-content:center">'
                '<span style="font-size:26px;filter:grayscale(1)">📦</span>'
                '</div>'
                '<div>'
                '<div style="font-family:Manrope,sans-serif;font-size:20px;font-weight:800;color:#64748B;letter-spacing:0.3px;line-height:1.1">KAYRANPM</div>'
                '<div style="font-size:11px;color:#475569;letter-spacing:0.5px;font-weight:600;text-transform:uppercase;margin-top:3px">Ürün & Stok Yönetimi</div>'
                '</div>'
                '</div>'
                '<div style="font-size:12px;line-height:1.6;color:#475569">'
                'Bu uygulamaya erişim yetkiniz yok. Yetki için yöneticinizle iletişime geçin.'
                '</div>'
                '</div>',
                unsafe_allow_html=True
            )

    # İpuçları paneli
    st.markdown(
        '<div style="margin:50px 0 16px;animation:fadeUp 1.1s ease-out">'
        '<div style="font-size:11px;color:#64748B;letter-spacing:2px;text-transform:uppercase;font-weight:700;margin-bottom:14px">İpuçları</div>'
        '</div>'
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;animation:fadeUp 1.2s ease-out;margin-bottom:40px">'
        '<div style="background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:16px 18px">'
        '<div style="font-size:18px;margin-bottom:6px">⌨️</div>'
        '<div style="color:#E2E8F0;font-size:13px;font-weight:600;margin-bottom:4px">Hızlı Geçiş</div>'
        '<div style="color:#94A3B8;font-size:11px;line-height:1.5">Sol menüden istediğin uygulamaya direkt geçebilirsin</div>'
        '</div>'
        '<div style="background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:16px 18px">'
        '<div style="font-size:18px;margin-bottom:6px">🔒</div>'
        '<div style="color:#E2E8F0;font-size:13px;font-weight:600;margin-bottom:4px">Güvenli Ortam</div>'
        '<div style="color:#94A3B8;font-size:11px;line-height:1.5">Verilerin şifreli — sadece yetkili kullanıcılar görür</div>'
        '</div>'
        '<div style="background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:16px 18px">'
        '<div style="font-size:18px;margin-bottom:6px">☁️</div>'
        '<div style="color:#E2E8F0;font-size:13px;font-weight:600;margin-bottom:4px">Bulut Senkronu</div>'
        '<div style="color:#94A3B8;font-size:11px;line-height:1.5">Verilerin gerçek zamanlı senkronize edilir</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )


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

    aktif = st.session_state.aktif_uygulama
    yetkiler = kullanici_yetkileri(st.session_state.aktif_kullanici)

    # Yetki kontrolü
    if aktif == "kayranacc" and not yetkiler["kayranacc"]:
        st.error("🔒 KAYRANACC uygulamasına erişim yetkiniz yok.")
        st.session_state.aktif_uygulama = "anasayfa"
        return
    if aktif == "kayranpm" and not yetkiler["kayranpm"]:
        st.error("🔒 KAYRANPM uygulamasına erişim yetkiniz yok.")
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
        else:
            st.error(f"Bilinmeyen sayfa: {aktif}")
            st.session_state.aktif_uygulama = "anasayfa"
            if st.button("← Ana Sayfaya Dön"):
                st.rerun()
    except Exception as hata:
        ad = "KAYRANACC" if aktif == "kayranacc" else ("KAYRANPM" if aktif == "kayranpm" else aktif)
        _global_hata_kart(ad, hata)


if __name__ == "__main__":
    main()
else:
    main()
