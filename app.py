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
from datetime import datetime, timedelta
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
KAYRANACC_KULLANICILAR = {"ibrahim", "derman", "cem", "pamuk", "serkan", "yilmaz", "korkut", "caglar"}
KAYRANPM_KULLANICILAR  = {"ibrahim", "gokhan", "derya", "serkan", "korkut", "caglar"}
HESAP_MAKINESI_KULLANICILAR = {"ibrahim"}
ITHALAT_KULLANICILAR = {"ibrahim", "kemal", "serkan", "derya", "gokhan", "korkut", "caglar", "cem", "pamuk"}
TEKNIKSERVIS_KULLANICILAR = {"ibrahim", "berkay", "gokhan", "cem", "pamuk", "derya"}
SATIS_KULLANICILAR = {"ibrahim", "gokhan", "derya", "serkan", "korkut", "caglar"}

DUYURU_AKTIF = False
DUYURU_METNI = ""


def kullanici_yetkileri(kullanici):
    k = (kullanici or "").lower().strip()
    return {
        "kayranacc": k in KAYRANACC_KULLANICILAR,
        "kayranpm":  k in KAYRANPM_KULLANICILAR,
        "hesap_makinesi": k in HESAP_MAKINESI_KULLANICILAR,
        "ithalat": k in ITHALAT_KULLANICILAR,
        "teknikservis": k in TEKNIKSERVIS_KULLANICILAR,
        "satis": k in SATIS_KULLANICILAR,
    }


# ─────────────────────────────────────────────────────────────────────
# TALEP / GERİ BİLDİRİM — Mail gönderimi
# ─────────────────────────────────────────────────────────────────────
TALEP_ALICI = "ibrahim.kayran@g5fteknoloji.com"

# ─────────────────────────────────────────────────────────────────────
# ONLINE KULLANICI TAKİP
# ─────────────────────────────────────────────────────────────────────
def online_durum_guncelle(kullanici_adi: str):
    """Kullanıcının son aktivite zamanını Supabase'e kaydeder (en fazla 60 sn'de bir)."""
    try:
        import time as _t
        if _t.time() - st.session_state.get("_son_online_upsert", 0) < 60:
            return
        import datetime as _dt
        sb = _get_supabase()
        if not sb:
            return
        sb.table("kullanici_durum").upsert({
            "kullanici_adi": kullanici_adi,
            "son_aktivite": _dt.datetime.utcnow().isoformat(),
        }, on_conflict="kullanici_adi").execute()
        st.session_state["_son_online_upsert"] = _t.time()
    except Exception:
        pass

def get_online_kullanicilar():
    """Son 180 dakika (3 saat) içinde aktif olan kullanıcıların listesini döner."""
    try:
        import datetime as _dt
        sb = _get_supabase()
        if not sb:
            return []
        bitis = _dt.datetime.utcnow()
        baslangic = bitis - _dt.timedelta(minutes=180)
        res = sb.table("kullanici_durum").select("kullanici_adi, son_aktivite").gte("son_aktivite", baslangic.isoformat()).execute()
        return res.data if res.data else []
    except Exception:
        return []

# ─────────────────────────────────────────────────────────────────────
# GÜNLÜK GİRİŞ / SERİ / LİDERLİK
# ─────────────────────────────────────────────────────────────────────
def _gunluk_giris_seri(tarih_set):
    """Bugün veya dün ile biten ardışık gün serisi."""
    import datetime as _dt
    if not tarih_set:
        return 0
    bugun = _dt.date.today()
    if bugun in tarih_set:
        cur = bugun
    elif (bugun - _dt.timedelta(days=1)) in tarih_set:
        cur = bugun - _dt.timedelta(days=1)
    else:
        return 0
    seri = 0
    while cur in tarih_set:
        seri += 1
        cur = cur - _dt.timedelta(days=1)
    return seri

def gunluk_giris_yap(kullanici_adi):
    """Bugün için giriş kaydı ekler (zaten varsa False)."""
    try:
        import datetime as _dt
        sb = _get_supabase()
        if not sb or not kullanici_adi:
            return False
        bugun = _dt.date.today().isoformat()
        mevcut = sb.table("gunluk_giris").select("id").eq("kullanici_adi", kullanici_adi).eq("tarih", bugun).limit(1).execute()
        if mevcut.data:
            return False
        sb.table("gunluk_giris").insert({"kullanici_adi": kullanici_adi, "tarih": bugun}).execute()
        return True
    except Exception:
        return False

def get_giris_durum(kullanici_adi):
    """{bugun, seri, toplam} döner."""
    try:
        import datetime as _dt
        sb = _get_supabase()
        if not sb or not kullanici_adi:
            return {"bugun": False, "seri": 0, "toplam": 0}
        res = sb.table("gunluk_giris").select("tarih").eq("kullanici_adi", kullanici_adi).execute()
        tset = set()
        for r in (res.data or []):
            try:
                tset.add(_dt.date.fromisoformat(str(r["tarih"])[:10]))
            except Exception:
                pass
        return {"bugun": _dt.date.today() in tset, "seri": _gunluk_giris_seri(tset), "toplam": len(tset)}
    except Exception:
        return {"bugun": False, "seri": 0, "toplam": 0}

def get_giris_liderlik(limit=8):
    """Tüm kullanıcılar: seri + toplam, seriye göre azalan."""
    try:
        import datetime as _dt
        sb = _get_supabase()
        if not sb:
            return []
        res = sb.table("gunluk_giris").select("kullanici_adi, tarih").execute()
        per = {}
        for r in (res.data or []):
            k = r.get("kullanici_adi")
            if not k:
                continue
            try:
                d = _dt.date.fromisoformat(str(r["tarih"])[:10])
            except Exception:
                continue
            per.setdefault(k, set()).add(d)
        lider = [{"kullanici": k, "seri": _gunluk_giris_seri(v), "toplam": len(v)} for k, v in per.items()]
        lider.sort(key=lambda x: (x["seri"], x["toplam"]), reverse=True)
        return lider[:limit]
    except Exception:
        return []

# ─────────────────────────────────────────────────────────────────────
# DUYURU YÖNETİMİ — Supabase'den oku / yaz
# ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
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
        try:
            get_duyuru.clear()
        except Exception:
            pass
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

@st.cache_data(ttl=20, show_spinner=False)
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
    try:
        get_okunmamis_bildirimler.clear()
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
    try:
        get_okunmamis_bildirimler.clear()
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







# ─────────────────────────────────────────────────────────────────────
# GÖREV ATAMA VE TAKİP SİSTEMİ
# ─────────────────────────────────────────────────────────────────────
def gorev_ata(atanan: str, baslik: str, aciklama: str, oncelik: str, bitis_tarihi):
    """Ibrahim tarafindan kullaniciya gorev atar."""
    try:
        sb = _get_supabase()
        if not sb:
            return False
        row = {
            "atayan": "ibrahim",
            "atanan": atanan,
            "baslik": baslik,
            "aciklama": aciklama or "",
            "oncelik": oncelik,
            "durum": "bekliyor",
        }
        if bitis_tarihi:
            row["bitis_tarihi"] = str(bitis_tarihi)
        sb.table("gorevler").insert(row).execute()
        return True
    except Exception:
        return False

def get_kullanici_gorevleri(kullanici_adi: str):
    """Kullanicinin aktif (tamamlanmamis) gorevlerini getirir."""
    try:
        sb = _get_supabase()
        if not sb:
            return []
        res = sb.table("gorevler").select("*").eq("atanan", kullanici_adi).neq("durum", "tamamlandi").order("olusturma_tarihi", desc=True).execute()
        return res.data if res.data else []
    except Exception:
        return []

def get_tum_gorevler_ibrahim():
    """Ibrahim icin tum gorevleri getirir."""
    try:
        sb = _get_supabase()
        if not sb:
            return []
        res = sb.table("gorevler").select("*").order("olusturma_tarihi", desc=True).limit(200).execute()
        return res.data if res.data else []
    except Exception:
        return []

def gorev_durum_guncelle(gorev_id: int, yeni_durum: str):
    """Kullanicinin gorev durumunu gunceller."""
    try:
        import datetime as _dt
        sb = _get_supabase()
        if not sb:
            return False
        row = {"durum": yeni_durum, "guncelleme_tarihi": _dt.datetime.utcnow().isoformat()}
        if yeni_durum == "tamamlandi":
            row["tamamlanma_tarihi"] = _dt.datetime.utcnow().isoformat()
        sb.table("gorevler").update(row).eq("id", gorev_id).execute()
        return True
    except Exception:
        return False

def gorev_sil(gorev_id: int):
    """Ibrahim gorev siler."""
    try:
        sb = _get_supabase()
        if not sb:
            return False
        sb.table("gorevler").delete().eq("id", gorev_id).execute()
        return True
    except Exception:
        return False

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

# ── Global mobil / dar ekran uyumu (yalnız <=640px; masaüstü etkilenmez) ──
st.markdown(
    """<style>
@media (max-width: 640px) {
  .main .block-container, .block-container {
    padding-left: 0.6rem !important;
    padding-right: 0.6rem !important;
  }
  [data-testid="stMetricValue"] { font-size: 1.05rem !important; }
  [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p { font-size: 0.68rem !important; }
  h1 { font-size: 1.35rem !important; }
  h2 { font-size: 1.15rem !important; }
  h3 { font-size: 1.02rem !important; }
  h4 { font-size: 0.95rem !important; }
  [data-testid="stDataFrame"] { font-size: 0.72rem !important; }
  .stButton button, .stDownloadButton button { font-size: 0.85rem !important; }
  [data-testid="stTabs"] button p { font-size: 0.8rem !important; }
  /* Kart/kolon şeritleri taşarsa yatay kaydırma */
  [data-testid="stHorizontalBlock"] { overflow-x: auto; }
}
</style>""",
    unsafe_allow_html=True,
)


# Session state defaults
def _oturum_secret():
    try:
        return str(st.secrets["supabase"]["key"])
    except Exception:
        return "kayran-oturum-varsayilan-anahtar"


def _oturum_token(kullanici):
    import hmac, hashlib
    return hmac.new(_oturum_secret().encode(),
                    (kullanici or "").lower().strip().encode(),
                    hashlib.sha256).hexdigest()[:32]


def _oturum_dogrula(kullanici, token):
    import hmac
    if not kullanici or not token:
        return False
    try:
        return hmac.compare_digest(_oturum_token(kullanici), str(token))
    except Exception:
        return False


if "giris_yapildi" not in st.session_state:
    st.session_state.giris_yapildi = False
if "aktif_kullanici" not in st.session_state:
    st.session_state.aktif_kullanici = ""

# Tarayıcı yenilendiğinde (yeni oturum) girişi URL'deki güvenli token'dan geri yükle
# → otomatik çıkışı önler. Token = HMAC(kullanıcı, sunucu_secret); başkası için taklit edilemez.
if not st.session_state.giris_yapildi:
    try:
        _qu = st.query_params.get("u", "")
        _qt = st.query_params.get("t", "")
        if _qu and _oturum_dogrula(_qu, _qt):
            st.session_state.giris_yapildi = True
            st.session_state.aktif_kullanici = _qu
    except Exception:
        pass
if "aktif_uygulama" not in st.session_state:
    # Sayfa yenilenince son sayfada kal (URL'deki 's' parametresinden geri yükle)
    try:
        st.session_state.aktif_uygulama = st.query_params.get("s") or "anasayfa"
    except Exception:
        st.session_state.aktif_uygulama = "anasayfa"


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
            '<div style="display:flex;align-items:center;gap:16px;margin-bottom:30px">'
            f'{KAYRAN_LOGO_BIG}'
            '<div>'
            '<div style="font-family:Inter,sans-serif;font-size:42px;font-weight:900;color:#FFFFFF;letter-spacing:5px;line-height:1">KAYRAN</div>'
            '<div style="font-size:11px;color:#94A3B8;letter-spacing:3px;text-transform:uppercase;font-weight:600;margin-top:4px">Workspace</div>'
            '</div>'
            '</div>'
            '<div style="margin-bottom:28px">'
            '<h2 style="font-family:Inter,sans-serif;font-size:26px;font-weight:700;color:#FFFFFF;line-height:1.3;margin:0 0 10px">'
            'Şirket Operasyonları '
            '<span style="background:linear-gradient(90deg,#60A5FA,#A78BFA);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">Tek Çatı Altında</span>'
            '</h2>'
            '<p style="color:#94A3B8;font-size:14px;line-height:1.6;margin:0">'
            'Muhasebe, finans, ithalat ve ürün yönetimini tek platformda yönetin.'
            '</p>'
            '</div>'
            '<div style="display:flex;flex-direction:column;gap:12px;margin-bottom:26px">'
            + "".join(
                '<div style="display:flex;align-items:center;gap:14px">'
                f'<div style="width:38px;height:38px;border-radius:10px;background:{_bg};border:1px solid {_bd};display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:16px">{_ik}</div>'
                f'<div><div style="color:#E2E8F0;font-size:13px;font-weight:600">{_ad}</div>'
                f'<div style="color:#64748B;font-size:11px;margin-top:2px">{_alt}</div></div>'
                '</div>'
                for _ik, _bg, _bd, _ad, _alt in [
                    ("💳", "rgba(99,102,241,0.15)", "rgba(99,102,241,0.25)", "Muhasebe & Finans", "Haftalık ödeme takibi, banka bakiyeleri, nakit akış"),
                    ("📦", "rgba(236,72,153,0.12)", "rgba(236,72,153,0.22)", "İthalat & Ürün Yönetimi", "Stok takibi, sipariş yönetimi, tedarik zinciri"),
                    ("🧮", "rgba(16,185,129,0.12)", "rgba(16,185,129,0.22)", "Hesap Makinesi", "Ürün kârlılık analizi, kırılma noktası hesaplama"),
                    ("🔐", "rgba(245,158,11,0.12)", "rgba(245,158,11,0.22)", "Yetki Bazlı Erişim", "Kullanıcıya özel panel, güvenli oturum yönetimi"),
                ]
            )
            + '</div>'
            '<div style="display:flex;align-items:center;gap:10px;padding-top:18px;border-top:1px solid rgba(255,255,255,0.06)">'
            '<div style="width:6px;height:6px;border-radius:50%;background:#10B981;box-shadow:0 0 8px #10B981"></div>'
            '<span style="color:#64748B;font-size:11px;font-weight:500">Bir <b style="color:#94A3B8">G5F Teknoloji</b> &amp; <b style="color:#94A3B8">Fazeon</b> projesi · İbrahim Kayran tarafından geliştirildi</span>'
            '</div>'
            '</div>',
            unsafe_allow_html=True
        )

    # ── SAĞ PANEL: Login Kartı ──
    with col_r:
        with st.container(border=True):
            st.markdown(
                '<div style="text-align:center;margin-bottom:18px">'
                '<div style="width:48px;height:48px;border-radius:14px;'
                'background:linear-gradient(135deg,rgba(99,102,241,0.25),rgba(139,92,246,0.2));'
                'border:1px solid rgba(139,92,246,0.3);display:flex;align-items:center;'
                'justify-content:center;font-size:20px;margin:0 auto 14px">🔐</div>'
                '<div style="color:#FFFFFF;font-size:20px;font-weight:700;margin-bottom:6px">Hesabınıza Giriş Yapın</div>'
                '<div style="color:#64748B;font-size:12px">Yetkili personel için özel erişim</div>'
                '</div>',
                unsafe_allow_html=True
            )
            with st.form("giris_form", clear_on_submit=False):
                kullanici = st.text_input("Kullanıcı Adı", placeholder="kullanici_adi", key="login_user")
                sifre = st.text_input("Şifre", type="password", placeholder="••••••••••••", key="login_pass")
                st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
                giris_btn = st.form_submit_button("Giriş Yap  →", type="primary", use_container_width=True)
            st.markdown(
                '<div style="margin-top:14px;text-align:center">'
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
                from shared.auth import giris_kontrol, giris_basarisiz, giris_basarili
                _izin, _kalan = giris_kontrol(kullanici)
                if not _izin:
                    st.error(f"🔒 Çok fazla hatalı deneme. Lütfen {_kalan // 60} dk {_kalan % 60} sn sonra tekrar deneyin.")
                elif kullanici_dogrula_v2(kullanici, sifre, kullanicilar):
                    giris_basarili(kullanici)
                    st.session_state.giris_yapildi = True
                    st.session_state.aktif_kullanici = kullanici
                    st.session_state.aktif_uygulama = "anasayfa"
                    try:
                        st.query_params["u"] = kullanici
                        st.query_params["t"] = _oturum_token(kullanici)
                    except Exception:
                        pass
                    st.rerun()
                else:
                    _sayi, _kilit = giris_basarisiz(kullanici)
                    _kalan_hak = max(0, 5 - _sayi)
                    if _kilit > 0:
                        st.error(f"🔒 Çok fazla hatalı deneme. Hesap {_kilit // 60} dakika kilitlendi.")
                    elif _sayi >= 3:
                        st.error(f"❌ Kullanıcı adı veya şifre hatalı. {_kalan_hak} deneme hakkınız kaldı.")
                    else:
                        st.error("❌ Kullanıcı adı veya şifre hatalı.")
            except Exception as e:
                st.error(f"Giriş sistemi hatası: {e}")


def portal_sidebar(kompakt=False):
    """Streamlit'in resmi sidebar'ina KAYRAN'in navigasyonunu cizer."""
    aktif_kullanici = st.session_state.get("aktif_kullanici", "")
    aktif_sayfa = st.session_state.get("aktif_uygulama", "anasayfa")
    # Aktif sayfayı URL'ye yaz → tarayıcı yenilense de aynı sayfada kal
    try:
        if st.query_params.get("s") != aktif_sayfa:
            st.query_params["s"] = aktif_sayfa
    except Exception:
        pass
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
        'background:rgba(255,255,255,0.022) !important;'
        'color:#D5DBE5 !important;'
        'border:1px solid rgba(255,255,255,0.06) !important;'
        'border-left:3px solid #818CF8 !important;'
        'border-radius:13px !important;'
        'padding:10px 14px !important;'
        'font-size:14px !important;'
        'font-weight:600 !important;'
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
        'font-size:14px !important;'
        'font-weight:600 !important;'
        'letter-spacing:0.2px !important;'
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
        'background:linear-gradient(135deg,rgba(99,102,241,0.30),rgba(139,92,246,0.18)) !important;'
        'color:#FFFFFF !important;'
        'border:1px solid rgba(139,92,246,0.55) !important;'
        'border-left:3px solid #A78BFA !important;'
        'border-radius:13px !important;'
        'box-shadow:0 2px 14px rgba(99,102,241,0.25) !important;'
        'font-size:14px !important;'
        'font-weight:700 !important;'
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

        if st.button(
            "🔍 Arama",
            key="nav_arama",
            type="primary" if aktif_sayfa == "arama" else "secondary",
            use_container_width=True
        ):
            st.session_state.aktif_uygulama = "arama"
            st.rerun()

        # Yönetim Panosu (P&L) — finansal özet, sadece İbrahim
        if aktif_kullanici.strip().lower() == "ibrahim":
            if st.button(
                "📊 Yönetim P&L",
                key="nav_yonetim",
                type="primary" if aktif_sayfa == "yonetim" else "secondary",
                use_container_width=True
            ):
                st.session_state.aktif_uygulama = "yonetim"
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
            if st.button(
                "💳 Muhasebe & Finans",
                key="nav_kayranacc_dn",
                type="secondary",
                use_container_width=True
            ):
                st.toast("⛔ Muhasebe & Finans için erişim yetkiniz yok.", icon="🔒")

        # Ithalat — herkese gorunur, sadece yetkili (ibrahim) girebilir
        if yetkiler["ithalat"]:
            if st.button(
                "🚢 Ithalat",
                key="nav_ithalat",
                type="primary" if aktif_sayfa == "ithalat" else "secondary",
                use_container_width=True
            ):
                st.session_state.aktif_uygulama = "ithalat"
                st.rerun()
        else:
            if st.button(
                "🚢 Ithalat",
                key="nav_ithalat_dn",
                type="secondary",
                use_container_width=True
            ):
                st.toast("⛔ İthalat için erişim yetkiniz yok.", icon="🔒")

        if yetkiler["kayranpm"]:
            if st.button(
                "📦 Urun Yonetimi",
                key="nav_kayranpm",
                type="primary" if aktif_sayfa == "kayranpm" else "secondary",
                use_container_width=True
            ):
                st.session_state.aktif_uygulama = "kayranpm"
                st.rerun()
        else:
            if st.button(
                "📦 Urun Yonetimi",
                key="nav_kayranpm_dn",
                type="secondary",
                use_container_width=True
            ):
                st.toast("⛔ Ürün Yönetimi için erişim yetkiniz yok.", icon="🔒")

        if yetkiler["satis"]:
            if st.button(
                "💰 Satış",
                key="nav_satis",
                type="primary" if aktif_sayfa == "satis" else "secondary",
                use_container_width=True
            ):
                st.session_state.aktif_uygulama = "satis"
                st.rerun()
        else:
            if st.button(
                "💰 Satış",
                key="nav_satis_dn",
                type="secondary",
                use_container_width=True
            ):
                st.toast("⛔ Satış için erişim yetkiniz yok.", icon="🔒")

        # Teknik Servis
        if yetkiler["teknikservis"]:
            if st.button(
                "🛠️ Teknik Servis",
                key="nav_teknikservis",
                type="primary" if aktif_sayfa == "teknikservis" else "secondary",
                use_container_width=True
            ):
                st.session_state.aktif_uygulama = "teknikservis"
                st.rerun()
        else:
            if st.button(
                "🛠️ Teknik Servis",
                key="nav_teknikservis_dn",
                type="secondary",
                use_container_width=True
            ):
                st.toast("⛔ Teknik Servis için erişim yetkiniz yok.", icon="🔒")

        if yetkiler["hesap_makinesi"]:
            if st.button(
                "🧮 Hesap Makinesi",
                key="nav_hesap_makinesi",
                type="primary" if aktif_sayfa == "hesap_makinesi" else "secondary",
                use_container_width=True
            ):
                st.session_state.aktif_uygulama = "hesap_makinesi"
                st.rerun()

        st.markdown(
            '<div style="height:1px;background:rgba(255,255,255,0.06);margin:14px 0 14px"></div>',
            unsafe_allow_html=True
        )

        # ── Yeni sekmede aç: her modülü ayrı sekmede, oturum korunarak ──
        with st.expander("↗ Yeni Sekmede Aç", expanded=False):
            _u = aktif_kullanici
            _t = _oturum_token(_u)
            _yeni_sekme = [("🏠 Anasayfa", "anasayfa"), ("🔍 Arama", "arama")]
            if _u.strip().lower() == "ibrahim":
                _yeni_sekme.append(("📊 Yönetim P&L", "yonetim"))
            if yetkiler.get("kayranacc"):
                _yeni_sekme.append(("💰 Muhasebe", "kayranacc"))
            if yetkiler.get("kayranpm"):
                _yeni_sekme.append(("📦 Ürün Yönetimi", "kayranpm"))
            if yetkiler.get("ithalat"):
                _yeni_sekme.append(("🚢 İthalat", "ithalat"))
            if yetkiler.get("satis"):
                _yeni_sekme.append(("🛒 Satış", "satis"))
            if yetkiler.get("teknikservis"):
                _yeni_sekme.append(("🔧 Teknik Servis", "teknikservis"))
            _lh = '<div style="display:flex;flex-direction:column;gap:6px">'
            for _ad, _mod in _yeni_sekme:
                _lh += (f'<a href="?u={_u}&t={_t}&s={_mod}" target="_blank" '
                        f'style="display:block;padding:8px 12px;background:rgba(255,255,255,0.03);'
                        f'border:1px solid rgba(255,255,255,0.07);border-radius:8px;color:#A5B4FC;'
                        f'text-decoration:none;font-size:13px;font-weight:500">{_ad} ↗</a>')
            _lh += '</div>'
            st.markdown(_lh, unsafe_allow_html=True)
            st.caption("Her modül ayrı sekmede açılır; oturumun korunur. Böylece örn. Satış ve İthalat'ı aynı anda kullanabilirsin.")

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
                try:
                    st.query_params.clear()
                except Exception:
                    pass
                st.rerun()
        else:
            uyg_adi_map = {"kayranacc": "Muhasebe & Finans", "kayranpm": "Urun Yonetimi", "ithalat": "Ithalat", "teknikservis": "Teknik Servis", "satis": "Satis", "hesap_makinesi": "Hesap Makinesi"}
            uyg_adi = uyg_adi_map.get(aktif_sayfa, aktif_sayfa.capitalize())
            uyg_renk_map = {"kayranacc": "#A5B4FC", "kayranpm": "#F9A8D4", "ithalat": "#7DD3FC", "teknikservis": "#FDA4AF", "hesap_makinesi": "#FCD34D"}
            uyg_renk = uyg_renk_map.get(aktif_sayfa, "#A5B4FC")
            st.markdown(
                '<div style="font-size:10px;color:' + uyg_renk + ';letter-spacing:2px;font-weight:700;text-transform:uppercase;margin:4px 0 8px;padding-left:6px"> ' + uyg_adi + ' SAYFALARI</div>',
                unsafe_allow_html=True
            )
            # Modüle tıklayınca soldaki menünün kayacağı hedef
            st.markdown('<div id="kayran-submenu-anchor"></div>', unsafe_allow_html=True)


def _arama_kutusu(yer="anasayfa"):
    """Global arama kutusu + gruplu sonuçlar (özet + git/stok kartı)."""
    terim = st.text_input(
        "🔍 Ara",
        key=f"global_arama_{yer}",
        placeholder="SKU, ürün, firma, sipariş no, seri no, tedarikçi…",
        label_visibility="collapsed",
    )
    if not terim or len(terim.strip()) < 2:
        if yer == "sayfa":
            st.caption("En az 2 karakter yazın. Ürün (SKU/ad/barkod), cari, sipariş no, "
                       "seri no, servis no ve tedarikçi aranır.")
        return
    from shared.arama import ara
    sonuclar = ara(terim)
    if not sonuclar:
        st.info("Sonuç bulunamadı.")
        return
    _toplam = sum(len(v) for v in sonuclar.values())
    st.caption(f"{_toplam} sonuç")

    def _git(modul):
        st.session_state.aktif_uygulama = modul
        st.rerun()

    # 📦 Ürünler — özet + Stok Kartı (modal)
    if sonuclar.get("urunler"):
        st.markdown(f"**📦 Ürünler ({len(sonuclar['urunler'])})**")
        for u in sonuclar["urunler"]:
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"`{u.get('sku','')}` — {u.get('urun_adi','') or '—'}  ·  "
                        f"{u.get('marka','') or ''} · ₺{u.get('satis_fiyati') or 0}")
            if c2.button("Stok Kartı", key=f"ara_u_{yer}_{u.get('sku')}", use_container_width=True):
                try:
                    from kayranpm.stok_karti import goster
                    goster(u.get("sku"))
                except Exception:
                    _git("kayranpm")

    # 🏢 Cariler → Muhasebe
    if sonuclar.get("cariler"):
        st.markdown(f"**🏢 Cariler ({len(sonuclar['cariler'])})**")
        for f in sonuclar["cariler"]:
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"{f.get('firma_adi','') or '—'}  ·  kod: {f.get('firma_kodu','') or '—'}")
            if c2.button("→ Muhasebe", key=f"ara_c_{yer}_{f.get('id', f.get('firma_kodu'))}",
                         use_container_width=True):
                _git("kayranacc")

    # 🧾 Satışlar → Satış
    if sonuclar.get("satislar"):
        st.markdown(f"**🧾 Satışlar ({len(sonuclar['satislar'])})**")
        for s in sonuclar["satislar"]:
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"{str(s.get('tarih',''))[:10]} · {s.get('kanal','') or '—'} · "
                        f"`{s.get('sku','')}` · sipariş: {s.get('siparis_no','') or '—'} · "
                        f"{s.get('adet',0)} ad")
            if c2.button("→ Satış", key=f"ara_s_{yer}_{s.get('id')}", use_container_width=True):
                _git("satis")

    # 🚢 İthalat → İthalat
    if sonuclar.get("ithalat"):
        st.markdown(f"**🚢 İthalat ({len(sonuclar['ithalat'])})**")
        for d in sonuclar["ithalat"]:
            c1, c2 = st.columns([5, 1])
            _belge = d.get("pi_no") or d.get("dosya_no") or d.get("ithalat_takip_no") or "—"
            c1.markdown(f"{str(d.get('tarih',''))[:10]} · belge: {_belge} · "
                        f"{d.get('tedarikci','') or '—'} · {d.get('mense_ulke','') or ''}")
            if c2.button("→ İthalat", key=f"ara_i_{yer}_{d.get('id', _belge)}", use_container_width=True):
                _git("ithalat")

    # 🔧 Servis → Teknik Servis
    if sonuclar.get("servis"):
        st.markdown(f"**🔧 Teknik Servis ({len(sonuclar['servis'])})**")
        for t in sonuclar["servis"]:
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"servis: {t.get('servis_form_no','') or '—'} · seri: {t.get('seri_no','') or '—'} · "
                        f"{t.get('stok_adi','') or t.get('sku','') or ''} · {t.get('musteri','') or ''}")
            if c2.button("→ Servis", key=f"ara_t_{yer}_{t.get('kayit_id', t.get('servis_form_no'))}",
                         use_container_width=True):
                _git("teknikservis")


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

    # Global arama kutusu
    _arama_kutusu("anasayfa")

    # Saate göre selamlama — İstanbul saat dilimi (UTC+3)
    _ist_now = datetime.utcnow() + timedelta(hours=3)
    saat = _ist_now.hour
    if saat < 12: selamlama = "Günaydın"
    elif saat < 18: selamlama = "İyi günler"
    else: selamlama = "İyi akşamlar"

    # ─────────────────────────────────────────────────────────────────────
    # KULLANICIYA BİLDİRİM — zorunlu popup + üst şerit (herkes, ibrahim dahil)
    # ─────────────────────────────────────────────────────────────────────
    _bildirimler = get_okunmamis_bildirimler(aktif_kullanici)
    _dlg = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)
    if _bildirimler and _dlg:
        @_dlg("🔔 Yeni Bildirimler")
        def _zorunlu_bildirim_modal():
            st.markdown(f"**{len(_bildirimler)} okunmamış bildirimin var — lütfen oku:**")
            for _bm in _bildirimler:
                _gnd = str(_bm.get("gonderen") or "Sistem").capitalize()
                st.markdown(
                    '<div style="background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);border-radius:10px;padding:12px 14px;margin:8px 0">'
                    f'<div style="color:#E2E8F0;font-size:13px;line-height:1.6">{_bm.get("mesaj","")}</div>'
                    f'<div style="color:#64748B;font-size:10px;margin-top:6px">{_gnd} · {str(_bm.get("olusturma_tarihi",""))[:16].replace("T"," ")}</div>'
                    '</div>', unsafe_allow_html=True)
            if st.button("✓ Okudum, kapat", type="primary", use_container_width=True, key="_modal_okundu_btn"):
                tumunu_okundu_isaretle(aktif_kullanici)
                st.rerun()
        _zorunlu_bildirim_modal()
    _frag = getattr(st, "fragment", None)
    if _frag:
        @_frag(run_every="15s")
        def _bildirim_izleyici():
            try:
                _yeni_say = len(get_okunmamis_bildirimler(aktif_kullanici))
            except Exception:
                return
            _eski = st.session_state.get("_bildirim_say_izle")
            st.session_state["_bildirim_say_izle"] = _yeni_say
            if _eski is not None and _yeni_say > _eski:
                try:
                    st.cache_data.clear()
                except Exception:
                    pass
                try:
                    st.rerun(scope="app")
                except TypeError:
                    st.rerun()
        _bildirim_izleyici()

    # (📬 Gelen Talepler — aşağıya, istatistik kartlarının altına taşındı ve kapalı panel yapıldı)

    # ─────────────────────────────────────────────────────────────────────
    # ─── HERO BÖLÜMÜ ───
    _gunler_tr = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    _aylar_tr = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
                 "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    _now_h = _ist_now
    _tarih_str = f"{_now_h.day} {_aylar_tr[_now_h.month-1]} {_now_h.year} · {_gunler_tr[_now_h.weekday()]}"
    st.markdown(
        '<div style="margin-bottom:26px;animation:fadeUp 0.6s ease-out">'
        '<div style="font-size:10px;color:#475569;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:10px">⚡ İbrahim Kayran tarafından geliştirildi</div>'
        '<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px">'
        '<div style="display:inline-block;padding:6px 14px;background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.25);border-radius:20px">'
        '<span style="color:#A5B4FC;font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase">🏠 Ana Sayfa</span>'
        '</div>'
        f'<span style="color:#64748B;font-size:12px;font-weight:500">{_tarih_str}</span>'
        '</div>'
        f'<h1 style="font-family:Inter,sans-serif;font-size:clamp(26px,5vw,40px);font-weight:800;color:#FFFFFF;letter-spacing:-0.5px;line-height:1.1;margin:0">'
        f'{selamlama}, '
        f'<span style="background:linear-gradient(90deg,#60A5FA,#A78BFA,#F472B6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">{aktif_kullanici.capitalize()}</span>'
        '</h1>'
        '<p style="color:#94A3B8;font-size:14px;margin-top:6px;font-weight:400">'
        'İşletmenin güncel durumu aşağıda. Bir modüle geçmek için kartına tıkla.'
        '</p>'
        '</div>',
        unsafe_allow_html=True
    )

    # ─── GÜNLÜK BİLGİ ŞERİDİ (döviz · altın · hava · günün sözü) ───
    try:
        from gunluk import (get_doviz, get_gram_altin, get_hava, get_gunun_sozu,
                            get_yaklasan_tatil, get_mola_ipucu)
        _dv = get_doviz()
        # Tarihsel kur için: o günün USD/TL kurunu kaydet (idempotent, günde 1)
        try:
            if _dv.get("USD"):
                from kayranacc.database import kur_kaydet
                from shared.utils import tr_today
                kur_kaydet(tr_today(), _dv["USD"])
        except Exception:
            pass
        _altin = get_gram_altin()
        _hava = get_hava()
        _soz = get_gunun_sozu()
        _tatil = get_yaklasan_tatil()
        _mola = get_mola_ipucu()
    except Exception:
        _dv, _altin, _hava, _soz, _tatil, _mola = {}, None, None, "", None, ""

    def _g_card(ust, buyuk, alt, accent, ikon):
        return (f'<div style="background:rgba(255,255,255,0.04);border:1px solid {accent}2e;border-radius:16px;'
                f'padding:18px 20px;flex:1;min-width:150px">'
                f'<div style="font-size:10px;color:#94A3B8;letter-spacing:1.5px;text-transform:uppercase;font-weight:700;margin-bottom:8px">{ikon} {ust}</div>'
                f'<div style="color:#FFFFFF;font-size:26px;font-weight:800;line-height:1;font-family:JetBrains Mono,monospace">{buyuk}</div>'
                f'<div style="color:{accent};font-size:12px;font-weight:600;margin-top:6px">{alt}</div></div>')

    _saat_str = _ist_now.strftime("%H:%M")
    _gunluk_kartlar = [_g_card("Bugün", _saat_str, _tarih_str, "#A5B4FC", "📅")]
    if _dv.get("USD"):
        _usd_s = f"₺{_dv['USD']:.2f}".replace(".", ",")
        _eur_alt = (f"EUR ₺{_dv['EUR']:.2f}".replace(".", ",")) if _dv.get("EUR") else "USD/TRY"
        _gunluk_kartlar.append(_g_card("Dolar", _usd_s, _eur_alt, "#34D399", "💱"))
    if _altin:
        _gunluk_kartlar.append(_g_card("Gram Altın", f"₺{_altin:,.0f}".replace(",", "."), "Anlık fiyat", "#FBBF24", "🥇"))
    if _hava and _hava.get("sicaklik") is not None:
        _gunluk_kartlar.append(_g_card("Hava", f"{_hava['sicaklik']}°",
                                       f"{_hava['ikon']} {_hava['durum']} · {_hava['sehir']}", "#38BDF8", "🌤️"))
    if _tatil:
        _td = _tatil["tarih"]
        _ttar = f"{_td.day} {_aylar_tr[_td.month-1][:3]}"
        if _tatil["bugun"]:
            _gunluk_kartlar.append(_g_card("Bugün Tatil", "🎉", _tatil["ad"], "#FB7185", "🗓️"))
        else:
            _gunluk_kartlar.append(_g_card("Yaklaşan Tatil", f"{_tatil['kalan_gun']} gün",
                                           f"{_tatil['ad']} · {_ttar}", "#FB7185", "🗓️"))
    st.markdown(
        '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px;animation:fadeUp 0.6s ease-out">'
        + "".join(_gunluk_kartlar) + '</div>', unsafe_allow_html=True)
    if _soz:
        st.markdown(
            '<div style="background:linear-gradient(135deg,rgba(99,102,241,0.10),rgba(168,85,247,0.06));'
            'border:1px solid rgba(139,92,246,0.22);border-radius:14px;padding:13px 20px;margin-bottom:10px;'
            'display:flex;align-items:center;gap:12px;animation:fadeUp 0.7s ease-out">'
            '<span style="font-size:20px">💬</span>'
            f'<span style="color:#CBD5E1;font-size:14px;font-style:italic;font-weight:500">{_soz}</span></div>',
            unsafe_allow_html=True)
    if _mola:
        st.markdown(
            '<div style="background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.22);'
            'border-radius:14px;padding:13px 20px;margin-bottom:28px;display:flex;align-items:center;gap:12px;'
            'animation:fadeUp 0.75s ease-out">'
            '<span style="font-size:20px">💧</span>'
            f'<span style="color:#A7F3D0;font-size:14px;font-weight:600">{_mola}</span></div>',
            unsafe_allow_html=True)

    # ─────────────────────────────────────────────────────────────────────
    # ─── İŞ KPI KARTLARI (gerçek veriden, yetkiye göre, güvenli) ───
    erisilebilir = sum(1 for v in yetkiler.values() if v)
    toplam_uygulama = len(yetkiler)

    def _kpi_card(label, value, sub, accent):
        return (f'<div style="background:rgba(255,255,255,0.03);border:1px solid {accent}33;border-radius:12px;'
                f'padding:12px 15px;backdrop-filter:blur(10px)">'
                f'<div style="font-size:9px;color:#64748B;letter-spacing:1.2px;text-transform:uppercase;font-weight:700;margin-bottom:6px">{label}</div>'
                f'<div style="color:#FFFFFF;font-size:19px;font-weight:800;font-family:JetBrains Mono,monospace;line-height:1">{value}</div>'
                f'<div style="color:{accent};font-size:10px;font-weight:500;margin-top:5px">{sub}</div></div>')

    import datetime as _kdt
    _ay_ilk = _kdt.date.today().replace(day=1).isoformat()
    _bugun_iso = _kdt.date.today().isoformat()
    # Finansal rakamları (net kâr, ciro, marj) yalnızca yetkili görür — diğer personele gösterilmez
    _finans_gor = (aktif_kullanici or "").lower() == "ibrahim"
    _rozet = {}
    kpi_html = [_kpi_card("Erişim", f"{erisilebilir}/{toplam_uygulama}", "⚡ Yetkili uygulama", "#A5B4FC")]

    if _finans_gor:
        try:
            from satis.database import get_satislar, ozet_hesapla
            _top, _, _ = ozet_hesapla(get_satislar(_ay_ilk, _bugun_iso))
            _r = "#34D399" if _top["net_kar"] >= 0 else "#F87171"
            kpi_html.append(_kpi_card("Satış · Bu Ay Net Kâr", f"${_top['net_kar']:,.0f}",
                                      f"Ciro ${_top['ciro']:,.0f} · %{_top['marj']:.1f}", _r))
        except Exception:
            pass
    if yetkiler.get("ithalat"):
        try:
            from ithalat.database import get_dosyalar, IN_TRANSIT_DURUMLAR
            _yol = sum(1 for d in get_dosyalar() if str(d.get("durum", "")).strip() in IN_TRANSIT_DURUMLAR)
            kpi_html.append(_kpi_card("İthalat", f"{_yol}", "🚢 Yolda dosya", "#38BDF8"))
            if _yol:
                _rozet["ithalat"] = f"{_yol} yolda"
        except Exception:
            pass
    if yetkiler.get("teknikservis"):
        try:
            from teknikservis.database import get_kayitlar
            _ts_n = len(get_kayitlar())
            kpi_html.append(_kpi_card("Teknik Servis", f"{_ts_n}", "🛠️ Açık kayıt", "#A78BFA"))
            if _ts_n:
                _rozet["teknikservis"] = f"{_ts_n} açık"
        except Exception:
            pass
    if yetkiler.get("kayranpm"):
        try:
            from kayranpm.database import get_kampanyalar
            _kmp_n = len(get_kampanyalar(durum='aktif'))
            kpi_html.append(_kpi_card("Kampanya", f"{_kmp_n}", "🎯 Aktif kampanya", "#F472B6"))
            if _kmp_n:
                _rozet["kayranpm"] = f"{_kmp_n} kampanya"
        except Exception:
            pass

    st.markdown(
        '<div style="font-size:11px;color:#64748B;letter-spacing:2px;text-transform:uppercase;font-weight:700;margin:0 0 10px">📊 İş özeti</div>'
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));gap:10px;margin-bottom:28px;animation:fadeUp 0.75s ease-out">'
        + "".join(kpi_html) + '</div>',
        unsafe_allow_html=True
    )

    if _bildirimler:
        if True:
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
                    f'{str(_b.get("gonderen") or "Sistem").capitalize()} · {str(_b.get("olusturma_tarihi",""))[:16].replace("T"," ")}'
                    f'</div>'
                    f'</div>'
                )
            _bil_html += '</div>'
            st.markdown(_bil_html, unsafe_allow_html=True)
            if st.button("✓ Tümünü Okundu İşaretle", key="okundu_btn", use_container_width=False):
                tumunu_okundu_isaretle(aktif_kullanici)
                st.rerun()

    # ── Otomatik bildirim izleyici: yeni talep/bildirim gelince sayfa kendiliğinden yenilenir ──
    # ─── HIZLI ERİŞİM — tıklanabilir modül kartları ───
    _mod_meta = [
        ("kayranpm", "📦", "Ürün Yönetimi", "Stok · sipariş önerisi · kampanya · rapor"),
        ("ithalat", "🚢", "İthalat", "Dosya · masraf · paçal maliyet · teslim"),
        ("satis", "💰", "Satış", "Sipariş · kâr / P&L · kârlılık"),
        ("kayranacc", "💵", "Muhasebe & Finans", "Ödeme · çek · banka · cari · aktifler"),
        ("teknikservis", "🛠️", "Teknik Servis", "Servis · iade · değişim · depo"),
        ("hesap_makinesi", "🧮", "Hesap Makinesi", "Hızlı hesaplama araçları"),
    ]
    _acik_mod = [m for m in _mod_meta if yetkiler.get(m[0])]
    if _acik_mod:
        st.markdown('<div style="color:#94A3B8;font-size:12px;font-weight:700;letter-spacing:1.5px;'
                    'text-transform:uppercase;margin:2px 0 14px">⚡ Hızlı Erişim</div>', unsafe_allow_html=True)
        for _ri in range(0, len(_acik_mod), 3):
            _satir_mod = _acik_mod[_ri:_ri + 3]
            _cols = st.columns(3)
            for _ci, (_mk, _ic, _ad, _ds) in enumerate(_satir_mod):
                with _cols[_ci]:
                    with st.container(border=True):
                        _rz = _rozet.get(_mk)
                        _rz_html = (f'<span style="background:rgba(56,189,248,0.15);color:#7DD3FC;font-size:10px;'
                                    f'font-weight:700;padding:3px 9px;border-radius:8px;white-space:nowrap">{_rz}</span>'
                                    ) if _rz else ''
                        st.markdown(
                            f'<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px">'
                            f'<div style="font-size:26px;line-height:1">{_ic}</div>{_rz_html}</div>'
                            f'<div style="color:#F1F5F9;font-size:15px;font-weight:700;margin-top:6px">{_ad}</div>'
                            f'<div style="color:#64748B;font-size:11px;margin:4px 0 10px;min-height:30px;line-height:1.4">{_ds}</div>',
                            unsafe_allow_html=True)
                        if st.button("Aç →", key=f"home_open_{_mk}", use_container_width=True):
                            st.session_state.aktif_uygulama = _mk
                            st.rerun()
        st.markdown(
            '<div style="display:flex;align-items:center;gap:8px;margin:18px 0 40px;color:#475569;font-size:11px">'
            '<span style="width:7px;height:7px;border-radius:50%;background:#10B981;box-shadow:0 0 10px #10B981"></span>'
            'Tüm servisler aktif · KAYRAN Workspace v2.0 Kurumsal sürüm'
            '</div>', unsafe_allow_html=True)
    # GÜNLÜK GİRİŞ & SERİ & LİDERLİK — tek kapalı panel
    # ─────────────────────────────────────────────────────────────────────
    # Giriş kaydı + kutlama panelin DIŞINDA; panel kapalı olsa da her açılışta çalışır
    import datetime as _dtg
    _bugun_str = _dtg.date.today().isoformat()
    if st.session_state.get("_giris_kayit_gun") != _bugun_str:
        if gunluk_giris_yap(aktif_kullanici):
            st.session_state["_giris_kutla"] = True
        st.session_state["_giris_kayit_gun"] = _bugun_str
    if st.session_state.pop("_giris_kutla", False):
        st.balloons()
        st.toast("🔥 Seri devam ediyor! Bugünkü girişin kaydedildi.")

    _gd = get_giris_durum(aktif_kullanici)
    _bugun_g, _seri, _toplam = _gd["bugun"], _gd["seri"], _gd["toplam"]
    _alev = "🔥" if _seri > 0 else "🧊"
    _seri_renk = "#FB923C" if _seri > 0 else "#64748B"
    with st.expander(f"{_alev} Giriş serin: {_seri} gün · toplam {_toplam} gün · {'bugün tamam ✓' if _bugun_g else 'bugün henüz yok'}", expanded=False):
        st.markdown(
            '<div style="background:linear-gradient(135deg,rgba(251,146,60,0.10),rgba(239,68,68,0.05));border:1px solid rgba(251,146,60,0.22);border-radius:14px;padding:16px 20px;margin-bottom:12px">'
            '<div style="display:flex;align-items:center;gap:18px">'
            f'<div style="font-size:36px;line-height:1">{_alev}</div>'
            '<div>'
            f'<div style="color:{_seri_renk};font-size:26px;font-weight:800;line-height:1">{_seri}<span style="font-size:13px;color:#94A3B8;font-weight:600;margin-left:6px">günlük seri</span></div>'
            f'<div style="color:#94A3B8;font-size:12px;margin-top:5px">Toplam {_toplam} gün giriş · {"Bugün tamam ✓" if _bugun_g else "Bugün henüz giriş yok"} · girişin otomatik kaydedilir</div>'
            '</div></div></div>',
            unsafe_allow_html=True
        )
        _lider = get_giris_liderlik(8)
        if _lider:
            _madalya = {0: "🥇", 1: "🥈", 2: "🥉"}
            _satir = ""
            for _i, _u in enumerate(_lider):
                _benmi = (_u["kullanici"] or "").lower() == (aktif_kullanici or "").lower()
                _ikon = _madalya.get(_i, f'<span style="color:#64748B;font-size:12px;font-weight:700">{_i+1}</span>')
                _bg = "rgba(99,102,241,0.12)" if _benmi else "transparent"
                _ad_renk = "#A5B4FC" if _benmi else "#E2E8F0"
                _ad = (_u["kullanici"] or "").capitalize() + (" (sen)" if _benmi else "")
                _kalin = "700" if _benmi else "500"
                _satir += (
                    f'<div style="display:flex;align-items:center;gap:12px;padding:7px 14px;border-radius:9px;background:{_bg}">'
                    f'<div style="width:22px;text-align:center">{_ikon}</div>'
                    f'<div style="flex:1;color:{_ad_renk};font-size:13px;font-weight:{_kalin}">{_ad}</div>'
                    f'<div style="color:#FB923C;font-size:13px;font-weight:700">🔥 {_u["seri"]}</div>'
                    f'<div style="color:#64748B;font-size:11px;width:62px;text-align:right">{_u["toplam"]} gün</div>'
                    f'</div>'
                )
            st.markdown(
                '<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:14px;padding:12px 6px 8px">'
                '<div style="color:#94A3B8;font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;padding:0 14px 8px">🏆 Giriş Liderliği</div>'
                + _satir +
                '</div>',
                unsafe_allow_html=True
            )

    # ── 📬 Gelen Talepler (admin) — kapalı panel, sade liste ──
    if aktif_kullanici.lower() == "ibrahim":
        try:
            from kayranpm.database import get_talepler
            talepler = get_talepler()
        except Exception:
            talepler = []
        _acik = sum(1 for t in talepler if t.get("durum") != "tamamlandi")
        with st.expander(f"📬 Gelen Talepler — {len(talepler)} kayıt · {_acik} açık", expanded=False):
            if not talepler:
                st.info("Henüz talep yok.")
            else:
                _durum_secenekler = ["bekliyor", "inceleniyor", "tamamlandi"]
                for _i_t, t in enumerate(talepler):
                    durum_renk = {"bekliyor": "🟡", "inceleniyor": "🔵", "tamamlandi": "🟢"}.get(t.get("durum", ""), "⚪")
                    if _i_t:
                        st.markdown('<div style="height:1px;background:rgba(255,255,255,0.07);margin:12px 0"></div>', unsafe_allow_html=True)
                    st.markdown(
                        f'<div style="color:#E2E8F0;font-size:13px;font-weight:700">{durum_renk} {t.get("konu","—")}</div>'
                        f'<div style="color:#64748B;font-size:11px;margin:2px 0 6px">{t.get("gonderen","?")} · {str(t.get("olusturma_tarihi",""))[:16].replace("T"," ")}</div>'
                        f'<div style="color:#CBD5E1;font-size:12px;line-height:1.5;margin-bottom:8px">{t.get("mesaj","")}</div>',
                        unsafe_allow_html=True)
                    talep_id = t.get("id")
                    _ct1, _ct2 = st.columns([3, 1])
                    with _ct1:
                        yeni_cevap = st.text_area("Cevap", value=(t.get("cevap") or ""), key=f"cevap_{talep_id}", height=70,
                                                  label_visibility="collapsed", placeholder="Cevabınızı yazın...")
                    with _ct2:
                        _mevcut_durum = t.get("durum", "bekliyor")
                        _durum_idx = _durum_secenekler.index(_mevcut_durum) if _mevcut_durum in _durum_secenekler else 0
                        durum_sec = st.selectbox("Durum", _durum_secenekler, index=_durum_idx,
                                                 key=f"durum_{talep_id}", label_visibility="collapsed")
                        _kaydet = st.button("💾 Kaydet", key=f"kaydet_{talep_id}", use_container_width=True)
                    if _kaydet:
                        try:
                            from kayranpm.database import guncelle_talep_cevap
                            _cevap = (yeni_cevap or "").strip()
                            guncelle_talep_cevap(talep_id, _cevap, durum_sec)
                            _gonderen = (t.get("gonderen") or "").strip()
                            if _gonderen and _cevap:
                                try:
                                    bildirim_gonder(_gonderen.lower(),
                                                    f"📬 '{t.get('konu','talebiniz')}' talebinize yanıt verildi: {_cevap}")
                                except Exception:
                                    pass
                            st.success("✅ Cevap kaydedildi ve gönderene iletildi.")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as _e:
                            st.error(f"Kaydedilemedi: {_e}")

    # ─── KURUMSAL — G5F & FAZEON (kapalı panel, kompakt) ───
    with st.expander("🏢 Kurumsal · G5F Teknoloji & Fazeon", expanded=False):
        _bk1, _bk2 = st.columns(2, gap="medium")
        with _bk1:
            st.markdown(
                '<div style="background:linear-gradient(135deg,#1B2436 0%,#0F172A 100%);'
                'border:1px solid rgba(232,132,32,0.2);border-left:3px solid #E88420;border-radius:14px;padding:18px 20px;display:flex;flex-direction:column;min-height:200px">'
                f'<div style="height:46px;display:flex;align-items:center;margin-bottom:6px">{G5F_LOGO_SVG}</div>'
                '<div style="font-size:16px;font-weight:800;color:#FFFFFF;margin-bottom:2px">G5F Teknoloji</div>'
                '<div style="font-size:10px;color:#FED7AA;letter-spacing:1px;font-weight:600;text-transform:uppercase;margin-bottom:8px">Distribütör · Teknoloji Çözümleri</div>'
                '<div style="font-size:12px;line-height:1.6;color:#CBD5E1;margin-bottom:14px">Yüksek kaliteli teknoloji ürünlerini hızlı tedarik ve güvenilir hizmetle sunan distribütör.</div>'
                '<a href="https://g5fteknoloji.com" target="_blank" rel="noopener noreferrer" style="margin-top:auto;align-self:flex-start;display:inline-flex;align-items:center;gap:6px;padding:7px 14px;background:rgba(0,0,0,0.4);border:1px solid rgba(232,132,32,0.5);border-radius:9px;color:#FFEDD5;text-decoration:none;font-size:11px;font-weight:600">🌐 g5fteknoloji.com →</a>'
                '</div>',
                unsafe_allow_html=True
            )
        with _bk2:
            st.markdown(
                '<div style="background:linear-gradient(135deg,#0F0A1E 0%,#1A0F3C 50%,#0D0D2B 100%);'
                'border:1px solid rgba(139,92,246,0.25);border-left:3px solid #A78BFA;border-radius:14px;padding:18px 20px;display:flex;flex-direction:column;min-height:200px">'
                f'<div style="height:46px;display:flex;align-items:center;margin-bottom:6px">{FAZEON_LOGO_SVG}</div>'
                '<div style="font-size:16px;font-weight:800;color:#FFFFFF;margin-bottom:2px">Fazeon</div>'
                '<div style="font-size:10px;color:#A78BFA;letter-spacing:1px;font-weight:600;text-transform:uppercase;margin-bottom:8px">Gaming · Monitors · Cases · Coolers</div>'
                '<div style="font-size:12px;line-height:1.6;color:#CBD5E1;margin-bottom:14px">Yüksek performanslı oyuncu monitörleri, PC kasaları ve verimli soğutma sistemleri.</div>'
                '<a href="https://fazeon.com" target="_blank" rel="noopener noreferrer" style="margin-top:auto;align-self:flex-start;display:inline-flex;align-items:center;gap:6px;padding:7px 14px;background:linear-gradient(135deg,rgba(99,102,241,0.2),rgba(139,92,246,0.15));border:1px solid rgba(139,92,246,0.4);border-radius:9px;color:#C4B5FD;text-decoration:none;font-size:11px;font-weight:600">🌐 fazeon.com →</a>'
                '</div>',
                unsafe_allow_html=True
            )

    # ─── DESTEK · TALEP / GERİ BİLDİRİM (kompakt, kapalı panel) ───
    st.markdown(
        '<style>'
        '[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea{'
        'background:rgba(255,255,255,0.04) !important;border:1px solid rgba(255,255,255,0.12) !important;'
        'color:#FFFFFF !important;border-radius:10px !important;}'
        '[data-testid="stTextInput"] input::placeholder,[data-testid="stTextArea"] textarea::placeholder{color:#64748B !important;}'
        '[data-testid="stTextInput"] input:focus,[data-testid="stTextArea"] textarea:focus{'
        'border-color:#8B5CF6 !important;box-shadow:0 0 0 3px rgba(139,92,246,0.15) !important;}'
        '</style>',
        unsafe_allow_html=True
    )
    with st.expander("💬 Destek · Talep / geri bildirim gönder", expanded=False):
        st.caption("Geliştirme, optimizasyon veya yeni özellik taleplerini doğrudan ekibe ilet.")
        with st.form("talep_form", clear_on_submit=True):
            konu = st.text_input("Konu", placeholder="Örn. toplu Excel dışa aktarma")
            mesaj = st.text_area("Mesajınız", placeholder="Talebinizi, önerinizi veya sorunu detaylıca yazın...", height=110)
            gonder = st.form_submit_button("📨 Talebi Gönder", type="primary", use_container_width=True)
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
                    if aktif_kullanici.lower() != "ibrahim":
                        try:
                            bildirim_gonder("ibrahim", f"📨 Yeni talep — {konu_son} · {aktif_kullanici.capitalize()}")
                        except Exception:
                            pass
                    st.success("✅ Talebiniz kaydedildi. Teşekkürler!")
                else:
                    st.error("❌ Talep kaydedilemedi. Lütfen tekrar deneyin.")

    # ─── ALT BİLGİ ŞERİDİ (sade tek satır) ───
    st.markdown(
        '<div style="margin:40px 0 0;padding:16px 0;border-top:1px solid rgba(255,255,255,0.06);text-align:center;color:#64748B;font-size:11px;line-height:1.9;animation:fadeUp 1.1s ease-out">'
        '⚡ Sol menüden tek tıkla erişim &nbsp;·&nbsp; 🔐 Yetki bazlı güvenli oturum &nbsp;·&nbsp; ☁️ Gerçek zamanlı bulut senkronizasyonu'
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
        '</div>',
        unsafe_allow_html=True
    )

    # ─── YÖNETİM (sadece ibrahim) — kompakt kapalı paneller ───
    if aktif_kullanici.lower() == "ibrahim":
        st.markdown("---")
        st.markdown(
            '<div style="display:flex;align-items:center;gap:10px;margin:6px 0 12px">'
            '<span style="font-size:12px;color:#64748B;letter-spacing:2px;text-transform:uppercase;font-weight:700">⚙️ Yönetim</span>'
            '<div style="height:1px;flex:1;background:linear-gradient(90deg,rgba(255,255,255,0.1),transparent)"></div>'
            '</div>',
            unsafe_allow_html=True
        )

        # 1) Aktif kullanıcılar & son giriş zamanları
        with st.expander("👥 Aktif kullanıcılar & son giriş zamanları", expanded=False):
            online_listesi = get_online_kullanicilar()
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
                st.caption("Şu an aktif kullanıcı yok.")
            else:
                import datetime as _dt
                simdi = _dt.datetime.utcnow()
                cards_html = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:8px;margin-bottom:4px">'
                for u in online_listesi:
                    k_adi = u.get("kullanici_adi", "?")
                    son_akt = u.get("son_aktivite", "")
                    try:
                        son_dt = _dt.datetime.fromisoformat(son_akt.replace("Z", ""))
                        fark_sn = int((simdi - son_dt).total_seconds())
                        zaman_str = f"{fark_sn}sn önce" if fark_sn < 60 else f"{fark_sn // 60}dk önce"
                    except Exception:
                        zaman_str = "az önce"
                    ilk = k_adi[0].upper() if k_adi else "?"
                    cards_html += (
                        f'<div style="background:rgba(16,185,129,0.06);border:1px solid rgba(16,185,129,0.2);border-radius:10px;padding:9px 12px;display:flex;align-items:center;gap:9px">'
                        f'<div style="width:28px;height:28px;border-radius:8px;background:linear-gradient(135deg,#10B981,#059669);display:flex;align-items:center;justify-content:center;font-weight:700;color:white;font-size:13px;flex-shrink:0">{ilk}</div>'
                        f'<div style="overflow:hidden"><div style="color:#FFFFFF;font-weight:600;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{k_adi.capitalize()}</div>'
                        f'<div style="color:#6EE7B7;font-size:10px;font-weight:500">● {zaman_str}</div></div></div>'
                    )
                cards_html += '</div>'
                st.markdown(
                    f'<div style="margin-bottom:6px"><span style="color:#6EE7B7;font-size:12px;font-weight:600">{len(online_listesi)} kullanıcı aktif (son 5 dk)</span></div>'
                    + cards_html, unsafe_allow_html=True)
            if _son_giris_map:
                import datetime as _dt3
                sg_html = '<div style="margin-top:12px"><div style="font-size:10px;color:#64748B;letter-spacing:1px;font-weight:700;text-transform:uppercase;margin-bottom:8px">Son giriş zamanları</div>'
                sg_html += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:6px">'
                for _kg, _sa in sorted(_son_giris_map.items()):
                    _zs = "—"
                    try:
                        _raw = str(_sa).replace("Z", "+00:00")
                        _sdt = _dt3.datetime.fromisoformat(_raw)
                        if _sdt.tzinfo is not None:
                            _sdt = _sdt.astimezone(_dt3.timezone.utc).replace(tzinfo=None)
                        _ist = _sdt + _dt3.timedelta(hours=3)
                        _zs = _ist.strftime("%d.%m.%Y %H:%M")
                    except Exception:
                        _zs = "—"
                    _online_su = any(u.get("kullanici_adi") == _kg for u in online_listesi)
                    _renk = "#10B981" if _online_su else "#64748B"
                    _bg = "rgba(16,185,129,0.06)" if _online_su else "rgba(255,255,255,0.02)"
                    _border = "rgba(16,185,129,0.15)" if _online_su else "rgba(255,255,255,0.06)"
                    sg_html += (
                        f'<div style="background:{_bg};border:1px solid {_border};border-radius:8px;padding:8px 12px;display:flex;align-items:center;justify-content:space-between">'
                        f'<span style="color:#E2E8F0;font-size:12px;font-weight:600">{_kg.capitalize()}</span>'
                        f'<span style="color:{_renk};font-size:11px;font-weight:600;font-family:JetBrains Mono,monospace;white-space:nowrap">{_zs}</span></div>'
                    )
                sg_html += '</div></div>'
                st.markdown(sg_html, unsafe_allow_html=True)

        # 2) Sistem duyurusu
        with st.expander("📢 Sistem duyurusu", expanded=False):
            _mevcut_aktif, _mevcut_metni = get_duyuru()
            _durum_etiketi = "🟢 Aktif" if _mevcut_aktif else "🔴 Kapalı"
            st.caption(f"Durum: {_durum_etiketi}" + ((" — " + _mevcut_metni[:60] + ("..." if len(_mevcut_metni) > 60 else "")) if _mevcut_metni else ""))
            with st.form("duyuru_form", clear_on_submit=False):
                _yeni_aktif = st.checkbox("Duyuruyu aktifleştir", value=bool(_mevcut_aktif))
                _yeni_metni = st.text_input("Duyuru metni", value=_mevcut_metni, placeholder="Örn: Sistem bugün 18:00-19:00 arası bakımda.")
                _duyuru_kaydet = st.form_submit_button("💾 Kaydet", type="primary")
                if _duyuru_kaydet:
                    if set_duyuru(_yeni_aktif, _yeni_metni or ""):
                        st.success("✅ Duyuru kaydedildi.")
                        st.rerun()
                    else:
                        st.error("❌ Kayıt başarısız.")

        # 3) Bildirim gönder
        with st.expander("🔔 Bildirim gönder", expanded=False):
            _tum_kullanicilar = sorted((KAYRANACC_KULLANICILAR | KAYRANPM_KULLANICILAR) - {"ibrahim"})
            with st.form("bildirim_form", clear_on_submit=True):
                _alici_sec = st.selectbox("Alıcı", ["Herkese Gönder"] + [k.capitalize() for k in _tum_kullanicilar])
                _bildirim_mesaj = st.text_area("Mesaj", placeholder="Kullanıcılara göndermek istediğin mesajı yaz...", height=90)
                _bildirim_gonder_btn = st.form_submit_button("📢 Gönder", type="primary")
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

    # Modül değişince soldaki menüyü ilgili alt menüye (SAYFALARI) kaydır
    if st.session_state.get("_nav_onceki") != aktif:
        if aktif in ("kayranacc", "kayranpm", "ithalat", "teknikservis", "hesap_makinesi"):
            st.session_state["_sidebar_kaydir"] = True
        st.session_state["_nav_onceki"] = aktif

    # Yetki kontrolü
    if aktif == "kayranacc" and not yetkiler["kayranacc"]:
        st.error("🔒 Muhasebe & Finans uygulamasına erişim yetkiniz yok.")
        st.session_state.aktif_uygulama = "anasayfa"
        return
    if aktif == "kayranpm" and not yetkiler["kayranpm"]:
        st.error("🔒 Ürün Yönetimi uygulamasına erişim yetkiniz yok.")
        st.session_state.aktif_uygulama = "anasayfa"
        return
    if aktif == "ithalat" and not yetkiler["ithalat"]:
        st.error("🔒 İthalat uygulamasına erişim yetkiniz yok.")
        st.session_state.aktif_uygulama = "anasayfa"
        return
    if aktif == "teknikservis" and not yetkiler["teknikservis"]:
        st.error("🔒 Teknik Servis uygulamasına erişim yetkiniz yok.")
        st.session_state.aktif_uygulama = "anasayfa"
        return
    if aktif == "satis" and not yetkiler["satis"]:
        st.error("🔒 Satış uygulamasına erişim yetkiniz yok.")
        st.session_state.aktif_uygulama = "anasayfa"
        return

    # Global modern form-alanı stili (tüm modüllere uygulanır): +/- gizli, modern kutular
    try:
        from shared.utils import modern_input_stil
        st.markdown(modern_input_stil(), unsafe_allow_html=True)
    except Exception:
        pass

    # Sayfa dispatch
    try:
        if aktif == "anasayfa":
            anasayfa()
        elif aktif == "arama":
            st.markdown("## 🔍 Arama")
            _arama_kutusu("sayfa")
        elif aktif == "kayranacc":
            from kayranacc.main import run as kayranacc_run
            kayranacc_run()
        elif aktif == "kayranpm":
            from kayranpm.main import run as kayranpm_run
            kayranpm_run()
        elif aktif == "ithalat":
            from ithalat.main import run as ithalat_run
            ithalat_run()
        elif aktif == "teknikservis":
            from teknikservis.main import run as teknikservis_run
            teknikservis_run()
        elif aktif == "satis":
            from satis.main import run as satis_run
            satis_run()
        elif aktif == "yonetim":
            from yonetim import run as yonetim_run
            yonetim_run()
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

    # Modül değiştiyse soldaki menüyü ilgili "SAYFALARI" alt menüsüne kaydır
    if st.session_state.pop("_sidebar_kaydir", False):
        import streamlit.components.v1 as _components
        _components.html(
            "<script>"
            "(function(){function go(n){try{"
            "var d=window.parent.document;"
            "var a=d.querySelector('#kayran-submenu-anchor');"
            "if(a){a.scrollIntoView({behavior:'smooth',block:'start'});}"
            "else if(n>0){setTimeout(function(){go(n-1);},120);}"
            "}catch(e){}}go(20);})();"
            "</script>",
            height=0,
        )


if __name__ == "__main__":
    main()
else:
    main()
