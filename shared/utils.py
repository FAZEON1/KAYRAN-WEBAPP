"""
KAYRAN - Ortak Yardımcı Fonksiyonlar
Tüm uygulamaların kullandığı timezone, error handling, vb.
"""
from datetime import datetime, date, timedelta
import zoneinfo
import streamlit as st
import traceback


# ─────────────────────────────────────────────────────────────────────
# TIMEZONE — Türkiye Saatine Göre Tarih/Saat
# ─────────────────────────────────────────────────────────────────────
# Streamlit Cloud sunucuları UTC saatinde çalışır. Türkiye UTC+3.
# Bu yüzden tüm uygulamada Türkiye saatini garantilemek için bu fonksiyonları kullanırız.

TURKIYE_TZ = zoneinfo.ZoneInfo("Europe/Istanbul")


def tr_now() -> datetime:
    """Türkiye saatine göre şu anki datetime."""
    return datetime.now(TURKIYE_TZ)


def tr_today() -> date:
    """Türkiye saatine göre bugünün tarihi.
    UTC sunucularda saat 21:00-00:00 arası 'date.today()' kullanılırsa
    yanlış (bir gün geride) tarih döner. Bu fonksiyon her zaman doğru gün döner."""
    return tr_now().date()


def tr_tomorrow() -> date:
    """Türkiye saatine göre yarının tarihi."""
    return tr_today() + timedelta(days=1)


def tr_yesterday() -> date:
    """Türkiye saatine göre dünün tarihi."""
    return tr_today() - timedelta(days=1)


def tr_today_iso() -> str:
    """Türkiye saatine göre bugün - ISO formatında (YYYY-MM-DD)."""
    return tr_today().isoformat()


def tr_now_str(fmt: str = "%d.%m.%Y %H:%M") -> str:
    """Türkiye saatine göre formatlanmış zaman.
    Varsayılan format: 27.04.2026 14:35
    """
    return tr_now().strftime(fmt)


# ─────────────────────────────────────────────────────────────────────
# ERROR HANDLING — Sayfa Bazlı Hata Yakalama
# ─────────────────────────────────────────────────────────────────────

def sayfa_error_handler(sayfa_adi: str, hata: Exception) -> None:
    """
    Sayfada hata oluştuğunda kullanıcıya gösterilecek standart hata kartı.
    Tüm app çökmesi yerine sadece o sayfa hata gösterir.

    Kullanım:
        try:
            # sayfa içeriği
        except Exception as e:
            sayfa_error_handler("Bu Hafta", e)
    """
    st.markdown(
        '<div style="background:#FEE2E2;border:1px solid #FCA5A5;border-left:4px solid #DC2626;'
        'border-radius:12px;padding:20px 24px;margin:20px 0">'
        '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">'
        '<span style="font-size:24px">⚠️</span>'
        f'<b style="color:#991B1B;font-size:16px">{sayfa_adi} Sayfasında Bir Sorun Oluştu</b>'
        '</div>'
        '<div style="color:#7F1D1D;font-size:13px;line-height:1.6;margin-bottom:14px">'
        'Üzgünüz, beklenmedik bir hata oluştu. Sayfayı yenileyebilir veya birkaç dakika sonra tekrar deneyebilirsiniz.'
        '</div>'
        '<div style="background:#FFFFFF;border:1px solid #FCA5A5;border-radius:8px;padding:10px 14px;'
        'font-family:monospace;font-size:11px;color:#991B1B;margin-bottom:10px;overflow-x:auto">'
        f'<b>Hata Detayı:</b> {type(hata).__name__}: {str(hata)[:300]}'
        '</div>'
        '<div style="font-size:11px;color:#991B1B">'
        '💡 <b>Ne yapabilirim?</b> Sayfayı yenileyin (Ctrl+F5) · Çıkış yapıp tekrar girin · Sorun devam ederse yöneticiye bildirin'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # Geliştirici detayı (sadece debug modunda gösterilir)
    with st.expander("🔧 Teknik Detay (Geliştirici için)"):
        st.code(traceback.format_exc(), language="python")


def safe_run(fn, sayfa_adi: str = "Bu sayfa", *args, **kwargs):
    """
    Bir fonksiyonu güvenli şekilde çalıştırır.
    Hata olursa kullanıcıya gösterir, app çökmez.

    Kullanım:
        safe_run(sayfayi_goster, "Dashboard")
    """
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        sayfa_error_handler(sayfa_adi, e)
        return None


# ─────────────────────────────────────────────────────────────────────
# YARDIMCI - Vade Durumu (timezone-aware)
# ─────────────────────────────────────────────────────────────────────

def vade_durumu(vade_str: str) -> str:
    """
    Bir vade tarihini bugüne göre değerlendirir.
    Returns: 'gecmis' | 'bugun' | 'yarin' | 'normal' | 'bilinmiyor'
    """
    if not vade_str:
        return "bilinmiyor"
    try:
        # ISO formatta gelirse direkt parse, değilse pandas ile
        try:
            v = date.fromisoformat(str(vade_str)[:10])
        except ValueError:
            import pandas as pd
            v = pd.to_datetime(vade_str).date()

        bugun = tr_today()
        if v < bugun:
            return "gecmis"
        elif v == bugun:
            return "bugun"
        elif v == bugun + timedelta(days=1):
            return "yarin"
        return "normal"
    except Exception:
        return "bilinmiyor"


# ════════════════════════════════════════════════════════════════════
# ORTAK SIDEBAR (tüm modüllerde aynı modern navigasyon)
# ════════════════════════════════════════════════════════════════════
def sidebar_stil() -> str:
    """st.radio tabanlı sidebar navigasyonunu modern 'nav pill'lere çevirir. Tüm modüllerde ortak."""
    return """
    <style>
    section[data-testid="stSidebar"] div[role="radiogroup"]{
        display:flex; flex-direction:column; gap:6px;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label{
        background:rgba(255,255,255,0.025);
        border:1px solid rgba(255,255,255,0.06);
        border-radius:12px;
        padding:11px 14px !important;
        margin:0 !important;
        cursor:pointer;
        transition:background .15s ease, border-color .15s ease;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover{
        background:rgba(99,102,241,0.10);
        border-color:rgba(99,102,241,0.35);
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child{
        display:none !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked){
        background:linear-gradient(135deg, rgba(99,102,241,0.28), rgba(167,139,250,0.16));
        border-color:rgba(139,92,246,0.6);
        box-shadow:0 2px 14px rgba(99,102,241,0.22);
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label p{
        font-size:14px !important; font-weight:600 !important; color:#CBD5E1 !important; letter-spacing:.2px;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p{
        color:#FFFFFF !important;
    }
    section[data-testid="stSidebar"] [data-testid="stButton"] button{
        border-radius:11px !important; font-weight:600 !important;
    }
    </style>
    """


def sidebar_baslik(ikon: str, ad: str, alt: str = "") -> str:
    """Modern sidebar başlığı: gradyan rozet + gradyan başlık. Tüm modüllerde ortak."""
    alt_html = (
        f'<div style="font-size:10px;color:#64748B;font-weight:600;letter-spacing:1px;'
        f'text-transform:uppercase;margin-top:3px">{alt}</div>'
    ) if alt else ""
    return (
        '<div style="text-align:center;padding:4px 4px 6px">'
        '<div style="width:52px;height:52px;border-radius:15px;margin:0 auto 8px;'
        'background:linear-gradient(135deg,#6366F1,#A78BFA);display:flex;align-items:center;'
        f'justify-content:center;font-size:26px;box-shadow:0 8px 22px rgba(99,102,241,0.4)">{ikon}</div>'
        '<div style="font-family:Inter,sans-serif;font-size:18px;font-weight:800;letter-spacing:-0.4px;'
        'background:linear-gradient(90deg,#C7D2FE,#A78BFA,#67E8F9);-webkit-background-clip:text;'
        f'background-clip:text;-webkit-text-fill-color:transparent;display:inline-block">{ad}</div>'
        f'{alt_html}'
        '<div style="height:1px;background:linear-gradient(90deg,transparent,rgba(99,102,241,0.5),transparent);margin-top:12px"></div>'
        '</div>'
    )


def sidebar_kullanici(kullanici: str) -> str:
    """Modern 'oturum açık' kartı (HTML). Çıkış butonu modülde st.button ile eklenir."""
    if not kullanici:
        return ""
    bas = kullanici[0].upper()
    return (
        '<div style="display:flex;align-items:center;gap:10px;background:rgba(255,255,255,0.04);'
        'border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:9px 12px;margin-bottom:10px">'
        '<div style="width:32px;height:32px;border-radius:50%;flex-shrink:0;'
        'background:linear-gradient(135deg,#6366F1,#A78BFA);display:flex;align-items:center;'
        f'justify-content:center;font-size:14px;font-weight:700;color:#fff">{bas}</div>'
        '<div><div style="font-size:10px;color:#64748B;font-weight:600;letter-spacing:.5px">OTURUM AÇIK</div>'
        f'<div style="font-size:13px;color:#F1F5F9;font-weight:700">{kullanici.capitalize()}</div></div>'
        '</div>'
    )
