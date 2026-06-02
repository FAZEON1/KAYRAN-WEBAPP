"""
KAYRAN PORTAL — Çatı Uygulama (Premium SaaS Edition)
Modüller: kayranacc, kayranpm
"""
import streamlit as st
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────
# YETKİ TANIMLARI — Hangi kullanıcı hangi uygulamaya erişebilir
# Yeni kullanıcı eklemek/çıkarmak için bu set'leri düzenle
# ─────────────────────────────────────────────────────────────────────
KAYRANACC_KULLANICILAR = {"ibrahim", "derman", "cem", "pamuk", "serkan", "yilmaz", "korkut"}
KAYRANPM_KULLANICILAR  = {"ibrahim", "gokhan", "derya"}

# Duyuru bandı — istemediğinde DUYURU_AKTIF = False yap
DUYURU_AKTIF = True
DUYURU_METNI = "✨ Yeni: KAYRAN portal artık çoklu uygulama desteğiyle yayında!"


def kullanici_yetkileri(kullanici):
    """Verilen kullanıcının hangi uygulamalara erişimi var?"""
    k = (kullanici or "").lower().strip()
    return {
        "kayranacc": k in KAYRANACC_KULLANICILAR,
        "kayranpm":  k in KAYRANPM_KULLANICILAR,
    }


# ─────────────────────────────────────────────────────────────────────
# Sayfa ayarları
# ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="KAYRAN | Portal",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# Session state defaults
if "giris_yapildi" not in st.session_state:
    st.session_state.giris_yapildi = False
if "aktif_kullanici" not in st.session_state:
    st.session_state.aktif_kullanici = ""
if "aktif_uygulama" not in st.session_state:
    st.session_state.aktif_uygulama = None


# ─────────────────────────────────────────────────────────────────────
# KURUMSAL KIMLIK — SVG Logo
# ─────────────────────────────────────────────────────────────────────
KAYRAN_LOGO_SVG = '<svg width="56" height="56" viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="logoGrad" x1="0" y1="0" x2="56" y2="56" gradientUnits="userSpaceOnUse"><stop offset="0%" stop-color="#60A5FA"/><stop offset="50%" stop-color="#A78BFA"/><stop offset="100%" stop-color="#F472B6"/></linearGradient><linearGradient id="logoGradInner" x1="0" y1="0" x2="0" y2="56" gradientUnits="userSpaceOnUse"><stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.15"/><stop offset="100%" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient></defs><rect width="56" height="56" rx="14" fill="url(#logoGrad)"/><rect width="56" height="56" rx="14" fill="url(#logoGradInner)"/><path d="M16 12 L16 44" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/><path d="M16 28 L38 12" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/><path d="M16 28 L38 44" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/><circle cx="42" cy="14" r="3" fill="#FFFFFF" opacity="0.9"/></svg>'

KAYRAN_LOGO_SMALL_SVG = '<svg width="36" height="36" viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="logoGradS" x1="0" y1="0" x2="56" y2="56" gradientUnits="userSpaceOnUse"><stop offset="0%" stop-color="#60A5FA"/><stop offset="50%" stop-color="#A78BFA"/><stop offset="100%" stop-color="#F472B6"/></linearGradient></defs><rect width="56" height="56" rx="14" fill="url(#logoGradS)"/><path d="M16 12 L16 44" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/><path d="M16 28 L38 12" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/><path d="M16 28 L38 44" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/><circle cx="42" cy="14" r="3" fill="#FFFFFF" opacity="0.9"/></svg>'


# ─────────────────────────────────────────────────────────────────────
# GLOBAL CSS — Premium SaaS tasarım
# ─────────────────────────────────────────────────────────────────────
def premium_css():
    return """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500&display=swap');

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
    .kayran-blob3 {
        position: fixed; top: 40%; left: 50%;
        width: 600px; height: 600px;
        background: radial-gradient(circle, #8b5cf6, transparent 70%);
        border-radius: 50%; filter: blur(120px);
        opacity: 0.35; z-index: -1;
        animation: blobMove2 25s ease-in-out infinite;
        transform: translate(-50%, -50%);
    }
    @keyframes blobMove {
        0%, 100% { transform: translate(0,0) scale(1); }
        33% { transform: translate(100px, 80px) scale(1.1); }
        66% { transform: translate(-80px, 60px) scale(0.95); }
    }
    @keyframes blobMove2 {
        0%, 100% { transform: translate(-50%, -50%) scale(1); }
        50% { transform: translate(-40%, -55%) scale(1.15); }
    }
    .kayran-grid {
        position: fixed; top: 0; left: 0;
        width: 100vw; height: 100vh; z-index: -1;
        background-image:
            linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
        background-size: 50px 50px; opacity: 0.6;
        pointer-events: none;
    }

    .duyuru-band {
        position: fixed; top: 0; left: 0; right: 0;
        background: linear-gradient(90deg, rgba(59,130,246,0.15), rgba(139,92,246,0.15), rgba(236,72,153,0.15));
        backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
        border-bottom: 1px solid rgba(255,255,255,0.08);
        padding: 10px 24px; text-align: center;
        color: #E0E7FF; font-size: 12px; font-weight: 500;
        letter-spacing: 0.3px; z-index: 100;
        animation: bandSlide 0.6s ease-out;
    }
    @keyframes bandSlide {
        from { transform: translateY(-100%); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
    }

    @keyframes fadeUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .stButton > button {
        background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%) !important;
        color: white !important;
        font-family: 'Manrope', sans-serif !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        letter-spacing: 0.3px !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 12px 24px !important;
        box-shadow: 0 4px 20px rgba(99,102,241,0.35) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    /* Form submit button (Giriş Yap) için aynı stil */
    .stFormSubmitButton > button,
    button[kind="primaryFormSubmit"],
    button[data-testid="stFormSubmitButton"] {
        background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%) !important;
        color: white !important;
        font-family: 'Manrope', sans-serif !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        letter-spacing: 0.3px !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 12px 24px !important;
        box-shadow: 0 4px 20px rgba(99,102,241,0.35) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    .stButton > button:hover,
    .stFormSubmitButton > button:hover,
    button[kind="primaryFormSubmit"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 28px rgba(139,92,246,0.5) !important;
        background: linear-gradient(135deg, #818CF8 0%, #A78BFA 100%) !important;
    }
    .stButton > button[kind="secondary"] {
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        box-shadow: none !important;
        color: #94A3B8 !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background: rgba(255,255,255,0.1) !important;
        border-color: rgba(255,255,255,0.3) !important;
        color: white !important;
    }

    .stTextInput > div > div > input {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 12px !important;
        color: white !important;
        font-family: 'Manrope', sans-serif !important;
        font-size: 14px !important;
        padding: 12px 16px !important;
        transition: all 0.25s ease !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #8B5CF6 !important;
        box-shadow: 0 0 0 3px rgba(139,92,246,0.15) !important;
        background: rgba(255,255,255,0.07) !important;
    }
    .stTextInput label {
        color: #CBD5E1 !important;
        font-family: 'Manrope', sans-serif !important;
        font-size: 12px !important;
        font-weight: 500 !important;
        letter-spacing: 0.5px !important;
        text-transform: uppercase !important;
    }
    </style>

    <div class="kayran-bg"></div>
    <div class="kayran-blob3"></div>
    <div class="kayran-grid"></div>
    """


def duyuru_bandi_render():
    if DUYURU_AKTIF:
        st.markdown(f'<div class="duyuru-band">{DUYURU_METNI}</div>', unsafe_allow_html=True)


def footer_render():
    yil = datetime.now().year
    st.markdown(f"""
    <div style="margin-top:80px; padding:32px 0 24px; border-top:1px solid rgba(255,255,255,0.06);
                text-align:center; font-family:'Manrope', sans-serif;">
        <div style="display:flex; justify-content:center; align-items:center; gap:10px; margin-bottom:14px;">
            <div style="display:flex; align-items:center; gap:8px;">
                <div style="width:6px; height:6px; border-radius:50%; background:#10B981; box-shadow:0 0 12px #10B981;"></div>
                <span style="color:#10B981; font-size:11px; font-weight:600; letter-spacing:1px; text-transform:uppercase;">Sistem Aktif</span>
            </div>
            <span style="color:#475569; font-size:11px;">•</span>
            <span style="color:#94A3B8; font-size:11px; font-family:'JetBrains Mono', monospace;">v1.0.0</span>
        </div>
        <div style="color:#64748B; font-size:11px; font-weight:500; letter-spacing:0.5px;">
            © {yil} KAYRAN · Şirket Yönetim Sistemi
        </div>
        <div style="color:#475569; font-size:10px; margin-top:6px;">
            🔒 Tüm veriler şifreli — Güvenli bağlantı (HTTPS)
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# 1) GİRİŞ EKRANI
# ─────────────────────────────────────────────────────────────────────
def giris_ekrani():
    st.markdown(premium_css(), unsafe_allow_html=True)
    duyuru_bandi_render()
    st.markdown('<div style="height:60px"></div>', unsafe_allow_html=True)

    col_l, col_main, col_r = st.columns([1, 2, 1])

    with col_main:
        st.markdown(
            '<div style="text-align:center;padding:20px 0 28px;animation:fadeUp 0.6s ease-out">'
            '<div style="display:flex;justify-content:center;margin-bottom:24px">'
            f'{KAYRAN_LOGO_SVG}'
            '</div>'
            '<div style="font-family:Manrope,sans-serif;font-size:42px;font-weight:800;color:#FFFFFF;letter-spacing:6px;line-height:1">KAYRAN</div>'
            '<div style="font-size:11px;color:#64748B;letter-spacing:4px;text-transform:uppercase;margin-top:10px;font-weight:600">Şirket Yönetim Sistemi</div>'
            '<div style="width:60px;height:2px;margin:18px auto 0;background:linear-gradient(90deg,#6366F1,#A78BFA,#EC4899);border-radius:2px"></div>'
            '</div>',
            unsafe_allow_html=True
        )

        st.markdown("""
        <div style="background:rgba(255,255,255,0.03); backdrop-filter:blur(20px);
                    -webkit-backdrop-filter:blur(20px); border:1px solid rgba(255,255,255,0.08);
                    border-radius:20px; padding:32px 32px 8px; margin-top:8px;
                    animation: fadeUp 0.8s ease-out 0.1s both;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.4);">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:24px;">
                <div style="width:32px; height:32px; border-radius:8px;
                            background:linear-gradient(135deg, rgba(99,102,241,0.2), rgba(139,92,246,0.2));
                            display:flex; align-items:center; justify-content:center;
                            border:1px solid rgba(139,92,246,0.3);">
                    <span style="font-size:14px;">🔐</span>
                </div>
                <div>
                    <div style="color:#CBD5E1; font-size:14px; font-weight:600;">Güvenli Giriş</div>
                    <div style="color:#64748B; font-size:11px;">Lütfen kimlik bilgilerinizi girin</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

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
                    st.rerun()
                else:
                    st.error("❌ Kullanıcı adı veya şifre hatalı.")
            except Exception as e:
                st.error(f"Giriş sistemi hatası: {e}")

        st.markdown("""
        <div style="text-align:center; margin-top:24px; animation: fadeUp 1s ease-out 0.3s both;">
            <div style="display:inline-flex; align-items:center; gap:6px;
                        background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.2);
                        border-radius:20px; padding:6px 14px;">
                <div style="width:6px; height:6px; border-radius:50%; background:#10B981;
                            box-shadow:0 0 8px #10B981;"></div>
                <span style="color:#6EE7B7; font-size:10px; font-weight:600; letter-spacing:1px;
                            text-transform:uppercase;">Şifreli Bağlantı</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    footer_render()


# ─────────────────────────────────────────────────────────────────────
# 2) UYGULAMA SEÇİCİ
# ─────────────────────────────────────────────────────────────────────
def uygulama_secici():
    aktif_kullanici = st.session_state.get("aktif_kullanici", "")

    st.markdown(premium_css(), unsafe_allow_html=True)
    duyuru_bandi_render()
    st.markdown('<div style="height:60px"></div>', unsafe_allow_html=True)

    col_logo, col_spacer, col_user, col_logout = st.columns([3, 4, 2, 1.2])

    with col_logo:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:14px;padding:8px 0;animation:fadeUp 0.5s ease-out">'
            f'{KAYRAN_LOGO_SMALL_SVG}'
            f'<div>'
            f'<div style="font-family:Manrope,sans-serif;font-size:22px;font-weight:800;color:#FFFFFF;letter-spacing:3px;line-height:1">KAYRAN</div>'
            f'<div style="font-size:9px;color:#64748B;letter-spacing:2px;text-transform:uppercase;margin-top:3px;font-weight:600">Portal</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    with col_user:
        ilk_harf = aktif_kullanici[0].upper() if aktif_kullanici else "U"
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:10px; padding:8px 14px;
                    background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08);
                    border-radius:12px; backdrop-filter:blur(10px);
                    animation: fadeUp 0.6s ease-out;">
            <div style="width:32px; height:32px; border-radius:10px;
                        background:linear-gradient(135deg, #6366F1, #8B5CF6);
                        display:flex; align-items:center; justify-content:center;
                        font-weight:700; color:white; font-size:14px;">{ilk_harf}</div>
            <div>
                <div style="color:#94A3B8; font-size:9px; font-weight:600; letter-spacing:0.5px;
                            text-transform:uppercase; line-height:1;">Oturum Açık</div>
                <div style="color:#FFFFFF; font-weight:600; font-size:13px; margin-top:3px;
                            line-height:1;">{aktif_kullanici.capitalize()}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_logout:
        st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
        if st.button("Çıkış", use_container_width=True, type="secondary", key="logout_btn"):
            st.session_state.giris_yapildi = False
            st.session_state.aktif_kullanici = ""
            st.session_state.aktif_uygulama = None
            st.rerun()

    # Hoş geldin
    saat = datetime.now().hour
    if saat < 12: selamlama = "Günaydın"
    elif saat < 18: selamlama = "İyi günler"
    else: selamlama = "İyi akşamlar"

    st.markdown(f"""
    <div style="text-align:center; margin:60px 0 48px; animation: fadeUp 0.7s ease-out 0.1s both;">
        <div style="display:inline-block; padding:6px 14px;
                    background:rgba(99,102,241,0.12); border:1px solid rgba(99,102,241,0.25);
                    border-radius:20px; margin-bottom:18px;">
            <span style="color:#A5B4FC; font-size:11px; font-weight:600; letter-spacing:1px;
                        text-transform:uppercase;">✨ Çalışma Alanı</span>
        </div>
        <h1 style="font-family:'Manrope', sans-serif; font-size:42px; font-weight:800;
                color:#FFFFFF; letter-spacing:-1px; line-height:1.1; margin:0;">
            {selamlama}, <span style="background:linear-gradient(90deg, #60A5FA, #A78BFA, #F472B6);
                                    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                                    background-clip:text;">{aktif_kullanici.capitalize()}</span>
        </h1>
        <p style="color:#94A3B8; font-size:15px; margin-top:10px; font-weight:400;">
            Açmak istediğiniz uygulamayı seçin
        </p>
    </div>
    """, unsafe_allow_html=True)

    yetkiler = kullanici_yetkileri(aktif_kullanici)
    erisilebilir = []
    if yetkiler["kayranacc"]: erisilebilir.append("kayranacc")
    if yetkiler["kayranpm"]: erisilebilir.append("kayranpm")

    if not erisilebilir:
        st.markdown("""
        <div style="max-width:520px; margin:40px auto; padding:36px;
                    background:rgba(239,68,68,0.08); border:1px solid rgba(239,68,68,0.25);
                    border-radius:20px; text-align:center; backdrop-filter:blur(10px);
                    animation: fadeUp 0.8s ease-out 0.2s both;">
            <div style="font-size:42px; margin-bottom:14px;">🔒</div>
            <div style="font-size:18px; font-weight:700; color:#FCA5A5; margin-bottom:8px;">
                Erişim Yetkiniz Yok
            </div>
            <div style="font-size:13px; color:#FECACA; line-height:1.6;">
                Sistem yöneticisi sizin için henüz herhangi bir uygulamaya erişim tanımlamamış.<br>
                Lütfen yöneticinizle iletişime geçin.
            </div>
        </div>
        """, unsafe_allow_html=True)
        footer_render()
        return

    if len(erisilebilir) == 2:
        col1, col2 = st.columns(2, gap="medium")
        kayranacc_col = col1
        kayranpm_col = col2
    else:
        col_l, col_main, col_r = st.columns([1, 2, 1])
        kayranacc_col = col_main if "kayranacc" in erisilebilir else None
        kayranpm_col = col_main if "kayranpm" in erisilebilir else None

    if yetkiler["kayranacc"] and kayranacc_col:
        with kayranacc_col:
            st.markdown("""
            <div style="position:relative; background:linear-gradient(135deg, rgba(99,102,241,0.12), rgba(59,130,246,0.08));
                        border:1px solid rgba(99,102,241,0.25); border-radius:24px;
                        padding:36px 32px 28px; backdrop-filter:blur(20px);
                        animation: fadeUp 0.8s ease-out 0.2s both;
                        overflow:hidden; min-height:280px;">
                <div style="position:absolute; top:-40px; right:-40px; width:200px; height:200px;
                            background:radial-gradient(circle, rgba(99,102,241,0.4), transparent 70%);
                            border-radius:50%; pointer-events:none;"></div>
                <div style="display:inline-flex; align-items:center; gap:6px; padding:5px 12px;
                            background:rgba(99,102,241,0.2); border:1px solid rgba(99,102,241,0.35);
                            border-radius:14px; margin-bottom:20px; position:relative; z-index:2;">
                    <div style="width:6px; height:6px; border-radius:50%; background:#A5B4FC;"></div>
                    <span style="color:#C7D2FE; font-size:10px; font-weight:600; letter-spacing:1px;
                                text-transform:uppercase;">Finans</span>
                </div>
                <div style="width:64px; height:64px; border-radius:18px;
                            background:linear-gradient(135deg, #6366F1, #8B5CF6);
                            display:flex; align-items:center; justify-content:center;
                            box-shadow:0 12px 32px rgba(99,102,241,0.35); margin-bottom:20px;
                            position:relative; z-index:2;">
                    <span style="font-size:32px;">💳</span>
                </div>
                <div style="font-family:'Manrope', sans-serif; font-size:24px; font-weight:800;
                            color:#FFFFFF; letter-spacing:0.5px; margin-bottom:8px; position:relative; z-index:2;">
                    KAYRANACC
                </div>
                <div style="font-size:13px; color:#A5B4FC; letter-spacing:0.5px; font-weight:600;
                            text-transform:uppercase; margin-bottom:18px; position:relative; z-index:2;">
                    Ödeme Takip Sistemi
                </div>
                <div style="font-size:13px; line-height:1.7; color:#CBD5E1; margin-bottom:24px;
                            position:relative; z-index:2;">
                    Haftalık ödemeler · Banka bakiyeleri · Çek takibi · Nakit akış · Toplam aktifler
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("→ KAYRANACC'yi Aç", key="acc_aç", use_container_width=True):
                st.session_state.aktif_uygulama = "kayranacc"
                st.rerun()

    if yetkiler["kayranpm"] and kayranpm_col:
        with kayranpm_col:
            st.markdown("""
            <div style="position:relative; background:linear-gradient(135deg, rgba(236,72,153,0.12), rgba(244,114,182,0.08));
                        border:1px solid rgba(236,72,153,0.25); border-radius:24px;
                        padding:36px 32px 28px; backdrop-filter:blur(20px);
                        animation: fadeUp 0.8s ease-out 0.3s both;
                        overflow:hidden; min-height:280px;">
                <div style="position:absolute; top:-40px; right:-40px; width:200px; height:200px;
                            background:radial-gradient(circle, rgba(236,72,153,0.4), transparent 70%);
                            border-radius:50%; pointer-events:none;"></div>
                <div style="display:inline-flex; align-items:center; gap:6px; padding:5px 12px;
                            background:rgba(236,72,153,0.2); border:1px solid rgba(236,72,153,0.35);
                            border-radius:14px; margin-bottom:20px; position:relative; z-index:2;">
                    <div style="width:6px; height:6px; border-radius:50%; background:#F9A8D4;"></div>
                    <span style="color:#FBCFE8; font-size:10px; font-weight:600; letter-spacing:1px;
                                text-transform:uppercase;">Operasyon</span>
                </div>
                <div style="width:64px; height:64px; border-radius:18px;
                            background:linear-gradient(135deg, #EC4899, #F472B6);
                            display:flex; align-items:center; justify-content:center;
                            box-shadow:0 12px 32px rgba(236,72,153,0.35); margin-bottom:20px;
                            position:relative; z-index:2;">
                    <span style="font-size:32px;">📦</span>
                </div>
                <div style="font-family:'Manrope', sans-serif; font-size:24px; font-weight:800;
                            color:#FFFFFF; letter-spacing:0.5px; margin-bottom:8px; position:relative; z-index:2;">
                    KAYRANPM
                </div>
                <div style="font-size:13px; color:#F9A8D4; letter-spacing:0.5px; font-weight:600;
                            text-transform:uppercase; margin-bottom:18px; position:relative; z-index:2;">
                    Ürün & Stok Yönetimi
                </div>
                <div style="font-size:13px; line-height:1.7; color:#CBD5E1; margin-bottom:24px;
                            position:relative; z-index:2;">
                    Ürün dashboard · Stok takibi · Sipariş önerisi · Kampanya · Satın alma geçmişi
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("→ KAYRANPM'yi Aç", key="pm_aç", use_container_width=True):
                st.session_state.aktif_uygulama = "kayranpm"
                st.rerun()

    # Hızlı bilgi şeridi
    st.markdown("""
    <div style="margin-top:60px; display:grid; grid-template-columns:repeat(3,1fr); gap:16px;
                animation: fadeUp 1s ease-out 0.5s both;">
        <div style="padding:18px 22px; background:rgba(255,255,255,0.025);
                    border:1px solid rgba(255,255,255,0.06); border-radius:14px;
                    backdrop-filter:blur(10px);">
            <div style="font-size:11px; color:#64748B; letter-spacing:1px; text-transform:uppercase;
                        font-weight:600; margin-bottom:6px;">⚡ Hız</div>
            <div style="color:#E2E8F0; font-size:14px; font-weight:500;">Anlık veri senkronizasyonu</div>
        </div>
        <div style="padding:18px 22px; background:rgba(255,255,255,0.025);
                    border:1px solid rgba(255,255,255,0.06); border-radius:14px;
                    backdrop-filter:blur(10px);">
            <div style="font-size:11px; color:#64748B; letter-spacing:1px; text-transform:uppercase;
                        font-weight:600; margin-bottom:6px;">🔒 Güvenlik</div>
            <div style="color:#E2E8F0; font-size:14px; font-weight:500;">Şifreli bağlantı (HTTPS)</div>
        </div>
        <div style="padding:18px 22px; background:rgba(255,255,255,0.025);
                    border:1px solid rgba(255,255,255,0.06); border-radius:14px;
                    backdrop-filter:blur(10px);">
            <div style="font-size:11px; color:#64748B; letter-spacing:1px; text-transform:uppercase;
                        font-weight:600; margin-bottom:6px;">☁️ Bulut</div>
            <div style="color:#E2E8F0; font-size:14px; font-weight:500;">Her yerden erişim</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    footer_render()


def portal_dön_butonu():
    """Alt uygulamaların sidebar'ında 'Portal'a Dön' butonu."""
    with st.sidebar:
        st.markdown('<div style="margin-bottom:10px"></div>', unsafe_allow_html=True)
        if st.button("🏠 Portal'a Dön", key="portal_don_btn", use_container_width=True):
            st.session_state.aktif_uygulama = None
            st.rerun()
        st.markdown('<hr style="margin:8px 0; border-color:rgba(255,255,255,0.1)">', unsafe_allow_html=True)


def main():
    if not st.session_state.giris_yapildi:
        giris_ekrani()
        return

    if not st.session_state.aktif_uygulama:
        uygulama_secici()
        return

    aktif = st.session_state.aktif_uygulama

    yetkiler = kullanici_yetkileri(st.session_state.aktif_kullanici)
    if aktif == "kayranacc" and not yetkiler["kayranacc"]:
        st.error("🔒 KAYRANACC uygulamasına erişim yetkiniz yok.")
        st.session_state.aktif_uygulama = None
        if st.button("← Portal'a Dön"):
            st.rerun()
        return
    if aktif == "kayranpm" and not yetkiler["kayranpm"]:
        st.error("🔒 KAYRANPM uygulamasına erişim yetkiniz yok.")
        st.session_state.aktif_uygulama = None
        if st.button("← Portal'a Dön"):
            st.rerun()
        return

    portal_dön_butonu()

    if aktif == "kayranacc":
        from kayranacc.main import run as kayranacc_run
        kayranacc_run()
    elif aktif == "kayranpm":
        from kayranpm.main import run as kayranpm_run
        kayranpm_run()
    else:
        st.error(f"Bilinmeyen uygulama: {aktif}")
        if st.button("← Portal'a Dön"):
            st.session_state.aktif_uygulama = None
            st.rerun()


if __name__ == "__main__":
    main()
else:
    main()
