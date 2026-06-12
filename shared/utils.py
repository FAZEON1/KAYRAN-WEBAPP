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
