"""
KAYRAN PORTAL — Çatı Uygulama
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


def kullanici_yetkileri(kullanici):
    """
    Verilen kullanıcının hangi uygulamalara erişimi var?
    Returns: dict {'kayranacc': True/False, 'kayranpm': True/False}
    """
    k = (kullanici or "").lower().strip()
    return {
        "kayranacc": k in KAYRANACC_KULLANICILAR,
        "kayranpm":  k in KAYRANPM_KULLANICILAR,
    }


# ─────────────────────────────────────────────────────────────────────
# Sayfa ayarları (yalnızca bir kere, portal'da)
# ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="KAYRAN | Portal",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ─────────────────────────────────────────────────────────────────────
# Session state defaults
# ─────────────────────────────────────────────────────────────────────
if "giris_yapildi" not in st.session_state:
    st.session_state.giris_yapildi = False
if "aktif_kullanici" not in st.session_state:
    st.session_state.aktif_kullanici = ""
if "aktif_uygulama" not in st.session_state:
    st.session_state.aktif_uygulama = None  # None / "kayranacc" / "kayranpm"


# ─────────────────────────────────────────────────────────────────────
# 1) GİRİŞ EKRANI
# ─────────────────────────────────────────────────────────────────────
def giris_ekrani():
    """Portal giriş ekranı — tek seferlik login."""
    st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #0B1437 0%, #162050 100%) !important; }
    [data-testid="stHeader"] { background: transparent; }
    section[data-testid="stSidebar"] { display: none; }
    .main .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 480px; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="text-align:center; padding: 40px 0 20px;">
        <div style="font-size:64px; margin-bottom:12px;">🏢</div>
        <div style="font-size:38px; font-weight:900; color:#FFFFFF; letter-spacing:4px;">KAYRAN</div>
        <div style="font-size:13px; color:#90A4AE; letter-spacing:3px; text-transform:uppercase; margin-top:8px;">
            Şirket Yönetim Portalı
        </div>
        <div style="width:80px; height:3px; background:linear-gradient(90deg,#1565C0,#42A5F5);
                    margin:20px auto 0; border-radius:2px;"></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.10);
                border-radius:16px; padding:32px 28px; margin-top:8px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.3);">
        <div style="color:#90CAF9; font-size:13px; font-weight:600; letter-spacing:1px;
                    text-transform:uppercase; margin-bottom:20px; text-align:center;">
            🔐 Güvenli Giriş
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("giris_form"):
        kullanici = st.text_input("Kullanıcı Adı", placeholder="kullanici_adi")
        sifre = st.text_input("Şifre", type="password", placeholder="••••••••")
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
    <div style="text-align:center; margin-top:24px;">
        <span style="color:#546E7A; font-size:11px;">
            🔒 Verileriniz şifreli ve güvende
        </span>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# 2) UYGULAMA SEÇİCİ
# ─────────────────────────────────────────────────────────────────────
def uygulama_secici():
    """Uygulama seçici — hangi uygulama açılsın?"""
    aktif_kullanici = st.session_state.get("aktif_kullanici", "")

    st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #F8FAFC 0%, #EFF6FF 100%); }
    section[data-testid="stSidebar"] { display: none; }
    [data-testid="stHeader"] { background: transparent; }
    .main .block-container { padding-top: 1.5rem; max-width: 1000px; }
    </style>
    """, unsafe_allow_html=True)

    # Üst bar — kullanıcı bilgisi + çıkış
    col_logo, col_user = st.columns([3, 1])
    with col_logo:
        st.markdown(f"""
        <div style="padding: 8px 0;">
            <div style="font-size:32px; font-weight:900; color:#0B1437; letter-spacing:3px;">🏢 KAYRAN</div>
            <div style="font-size:12px; color:#64748B; letter-spacing:1px; text-transform:uppercase;">Portal</div>
        </div>
        """, unsafe_allow_html=True)
    with col_user:
        st.markdown(f"""
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px;
                    padding:10px 14px; margin-top:8px; text-align:right;">
            <div style="color:#64748B; font-size:10px; font-weight:600; letter-spacing:0.5px; margin-bottom:2px;">OTURUM AÇIK</div>
            <div style="color:#0F172A; font-weight:700; font-size:13px;">👤 {aktif_kullanici.capitalize()}</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Çıkış Yap", use_container_width=True, type="secondary"):
            st.session_state.giris_yapildi = False
            st.session_state.aktif_kullanici = ""
            st.session_state.aktif_uygulama = None
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Hoş geldin mesajı
    st.markdown(f"""
    <div style="text-align:center; margin: 20px 0 32px;">
        <div style="font-size:24px; font-weight:700; color:#0B1437;">
            Hoş geldin, {aktif_kullanici.capitalize()} 👋
        </div>
        <div style="font-size:14px; color:#64748B; margin-top:6px;">
            Açmak istediğin uygulamayı seç
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Kullanıcı yetkilerini hesapla
    yetkiler = kullanici_yetkileri(aktif_kullanici)
    erisilebilir_uygulamalar = []
    if yetkiler["kayranacc"]:
        erisilebilir_uygulamalar.append("kayranacc")
    if yetkiler["kayranpm"]:
        erisilebilir_uygulamalar.append("kayranpm")

    # Hiçbir uygulamaya erişimi yoksa uyarı göster
    if not erisilebilir_uygulamalar:
        st.markdown("""
        <div style="background:#FEF2F2; border:1px solid #FCA5A5; border-left:4px solid #DC2626;
                    border-radius:12px; padding:24px; margin:40px auto; max-width:600px; text-align:center;">
            <div style="font-size:32px; margin-bottom:12px;">🔒</div>
            <div style="font-size:16px; font-weight:700; color:#991B1B; margin-bottom:8px;">
                Erişim Yetkiniz Yok
            </div>
            <div style="font-size:13px; color:#7F1D1D;">
                Sistem yöneticisi sizin için henüz herhangi bir uygulamaya erişim tanımlamamış.<br>
                Lütfen yöneticinizle iletişime geçin.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # Uygulama kartları - sadece yetkili olanlar gösterilir
    # 1 yetki varsa tam genişlik, 2 yetki varsa yan yana
    if len(erisilebilir_uygulamalar) == 2:
        col1, col2 = st.columns(2)
        kayranacc_col = col1
        kayranpm_col = col2
    elif len(erisilebilir_uygulamalar) == 1:
        # Tek uygulama varsa ortada büyük kart
        col_left, col_main, col_right = st.columns([1, 2, 1])
        kayranacc_col = col_main if "kayranacc" in erisilebilir_uygulamalar else None
        kayranpm_col = col_main if "kayranpm" in erisilebilir_uygulamalar else None

    if yetkiler["kayranacc"] and kayranacc_col:
        with kayranacc_col:
            st.markdown("""
            <div style="background:linear-gradient(135deg, #1E40AF 0%, #3730A3 100%);
                        border-radius:20px; padding:32px 28px; color:white;
                        box-shadow: 0 12px 32px rgba(30, 64, 175, 0.25);
                        min-height:220px;">
                <div style="font-size:48px; margin-bottom:12px;">💳</div>
                <div style="font-size:22px; font-weight:800; letter-spacing:1px; margin-bottom:8px;">KAYRANACC</div>
                <div style="font-size:12px; color:#C7D2FE; letter-spacing:0.5px; text-transform:uppercase; margin-bottom:14px;">Ödeme Takip Sistemi</div>
                <div style="font-size:13px; line-height:1.6; color:#E0E7FF; opacity:0.95;">
                    Haftalık ödemeler · Banka bakiyeleri · Çek takibi · Nakit akış · Toplam aktifler
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("→ KAYRANACC'yi Aç", key="acc_aç", type="primary", use_container_width=True):
                st.session_state.aktif_uygulama = "kayranacc"
                st.rerun()

    if yetkiler["kayranpm"] and kayranpm_col:
        with kayranpm_col:
            st.markdown("""
            <div style="background:linear-gradient(135deg, #1565C0 0%, #0D47A1 100%);
                        border-radius:20px; padding:32px 28px; color:white;
                        box-shadow: 0 12px 32px rgba(21, 101, 192, 0.25);
                        min-height:220px;">
                <div style="font-size:48px; margin-bottom:12px;">📦</div>
                <div style="font-size:22px; font-weight:800; letter-spacing:1px; margin-bottom:8px;">KAYRANPM</div>
                <div style="font-size:12px; color:#BBDEFB; letter-spacing:0.5px; text-transform:uppercase; margin-bottom:14px;">Ürün & Stok Yönetimi</div>
                <div style="font-size:13px; line-height:1.6; color:#E1F5FE; opacity:0.95;">
                    Ürün dashboard · Stok takibi · Sipariş önerisi · Kampanya · Satın alma geçmişi
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("→ KAYRANPM'yi Aç", key="pm_aç", type="primary", use_container_width=True):
                st.session_state.aktif_uygulama = "kayranpm"
                st.rerun()

    # Footer
    st.markdown("""
    <div style="text-align:center; margin-top:60px; padding:20px 0; border-top:1px solid #E2E8F0;">
        <span style="color:#94A3B8; font-size:11px;">
            KAYRAN PORTAL · v1.0
        </span>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# 3) PORTAL'A DÖNÜŞ BUTONU (alt uygulamaların sidebar'larına eklenir)
# ─────────────────────────────────────────────────────────────────────
def portal_dön_butonu():
    """Alt uygulamaların sidebar'ında 'Portal'a Dön' butonu."""
    with st.sidebar:
        st.markdown('<div style="margin-bottom:10px"></div>', unsafe_allow_html=True)
        if st.button("🏠 Portal'a Dön", key="portal_don_btn", use_container_width=True):
            st.session_state.aktif_uygulama = None
            st.rerun()
        st.markdown('<hr style="margin:8px 0; border-color:rgba(255,255,255,0.1)">', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# 4) ANA ROUTING
# ─────────────────────────────────────────────────────────────────────
def main():
    # Giriş yapmamışsa giriş ekranı
    if not st.session_state.giris_yapildi:
        giris_ekrani()
        return

    # Aktif uygulama seçilmemişse seçici ekranı
    if not st.session_state.aktif_uygulama:
        uygulama_secici()
        return

    # Aktif uygulamayı çalıştır
    aktif = st.session_state.aktif_uygulama

    # ─── GÜVENLİK: Yetki kontrolü (URL hile için) ───
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

    # Portal'a Dön butonunu sidebar'ın en üstüne ekle
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
    # Streamlit Cloud import edip run etmek yerine direkt çağırır
    main()
