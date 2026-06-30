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


# ─────────────────────────────────────────────────────────────────────
# METİN — Türkçe karakter normalizasyonu (string eşleştirme için)
# ─────────────────────────────────────────────────────────────────────
def normalize_tr(s) -> str:
    """Türkçe karakterleri Latin karşılığına indirger ve BÜYÜK harfe çevirir.
    İ/ı/I, Ş, Ğ, Ü, Ö, Ç kaynaklı eşleşme uyuşmazlıklarını önler:
    normalize_tr('İTOPYA') == 'ITOPYA'. Firma/cari/sekme eşleştirmesinde kullanılır."""
    s = str(s or "")
    for a, b in (("İ", "I"), ("ı", "I"), ("Ş", "S"), ("ş", "S"),
                 ("Ğ", "G"), ("ğ", "G"), ("Ü", "U"), ("ü", "U"),
                 ("Ö", "O"), ("ö", "O"), ("Ç", "C"), ("ç", "C")):
        s = s.replace(a, b)
    return s.upper()


# Firma stok kodu → gerçek/görünen ad. Veri/sorgu KODU korur (ITOPYA), bu yalnız GÖSTERİM içindir.
# Kaynak: kayranpm/ref_no.py FIRMA_ESLESME ile aynı eşleme.
FIRMA_GORUNEN_AD = {
    "ITOPYA": "EERA",
    "HB": "D-MARKET",
    "VATAN": "VATAN",
}


def firma_gorunen_ad(kod) -> str:
    """Firma stok kodunu (ITOPYA, HB...) muhasebedeki TAM cari adına çevirir.
    Önce ref_no.firma_tam_cari_adi ile cari listesinden tam adı bulur; ulaşılamazsa
    kısa öneke (EERA / D-MARKET...) düşer; o da yoksa kodu olduğu gibi gösterir.
    Sadece ekranda gösterim için — veri/sorguda firma kodu kullanılır."""
    if not kod:
        return ""
    try:
        from kayranpm.ref_no import firma_tam_cari_adi
        ad = firma_tam_cari_adi(kod)
        if ad:
            return ad
    except Exception:
        pass
    k = normalize_tr(kod).strip()
    return FIRMA_GORUNEN_AD.get(k, str(kod).strip())


def tr_kucuk(s) -> str:
    """Türkçe-doğru küçük harf çevrimi. İ→i, I→ı yapıp küçültür; Türkçe karakter KORUNUR.
    Serbest metinleri (kategori vb.) tek biçime indirger:
    'MONİTÖR'→'monitör', 'KASA'→'kasa', 'SOĞUTUCU'→'soğutucu', 'MicroSD Card'→'microsd card'."""
    s = str(s or "").replace("İ", "i").replace("I", "ı")
    return s.lower().strip()


def gun_ay_yil(d) -> str:
    """Tarihi ekranda DD-MM-YYYY biçiminde gösterir. ISO string ('2026-06-28'),
    date/datetime veya boş değer kabul eder. DB'ye yazarken KULLANILMAZ —
    veritabanı her zaman ISO (YYYY-MM-DD) saklar; bu yalnızca görünüm içindir."""
    if not d:
        return ""
    try:
        if isinstance(d, (datetime, date)):
            return d.strftime("%d-%m-%Y")
        return date.fromisoformat(str(d)[:10]).strftime("%d-%m-%Y")
    except Exception:
        return str(d or "")


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
    """st.radio sidebar navigasyonunu, metric kartlarıyla BİREBİR aynı görünüme çevirir.
    Renkli sol şerit + renkli kalın yazı + koyu kart + yuvarlak köşe. Tüm modüllerde ortak."""
    SB = 'section[data-testid="stSidebar"] div[role="radiogroup"]'
    # Metric kartlarındaki palet (7'li, döngüsel)
    _palet = ["#818CF8", "#34D399", "#FB923C", "#A78BFA", "#22D3EE", "#FBBF24", "#F472B6"]
    _renk_kurallari = ""
    for i, renk in enumerate(_palet, start=1):
        _renk_kurallari += (
            f'{SB} > label:nth-of-type(7n+{i}){{border-left-color:{renk} !important;}}'
            f'{SB} > label:nth-of-type(7n+{i}) p{{color:{renk} !important;}}'
            f'{SB} > label:nth-of-type(7n+{i}):has(input:checked){{'
            f'background:linear-gradient(135deg,{renk}2E,{renk}14) !important;'
            f'border-color:{renk}99 !important;box-shadow:0 2px 14px {renk}33 !important;}}'
        )
    return f"""
    <style>
    {SB}{{ display:flex; flex-direction:column; gap:8px; }}
    {SB} > label{{
        background:rgba(255,255,255,0.022) !important;
        border:1px solid rgba(255,255,255,0.06) !important;
        border-left:3px solid #818CF8 !important;
        border-radius:13px !important;
        padding:10px 14px !important;
        margin:0 !important;
        width:100% !important;
        box-sizing:border-box !important;
        display:flex !important;
        align-items:center !important;
        cursor:pointer;
        transition:background .15s ease, border-color .15s ease, transform .1s ease;
    }}
    {SB} > label:hover{{ background:rgba(255,255,255,0.05) !important; transform:translateX(1px); }}
    {SB} > label > div:first-child{{ display:none !important; }}
    {SB} label p{{
        font-family:Inter,sans-serif !important;
        font-size:15px !important;
        font-weight:800 !important;
        letter-spacing:-0.2px !important;
        font-variant-numeric:tabular-nums;
    }}
    {_renk_kurallari}
    section[data-testid="stSidebar"] [data-testid="stButton"] button{{
        border-radius:13px !important; font-weight:700 !important;
    }}
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


# ════════════════════════════════════════════════════════════════════
# ORTAK METRİK KARTLARI (tüm programda tek tip — renkli sol şeritli kart)
# ════════════════════════════════════════════════════════════════════
KART_PALET = ["#818CF8", "#34D399", "#FB923C", "#A78BFA", "#22D3EE", "#FBBF24", "#F472B6"]


def metrik_satiri(cards):
    """Renkli, sol şeritli metric kart satırı (sidebar/İthalat temasıyla birebir).
    cards = [{'label','value','renk'?,'alt'?,'help'?}]. renk verilmezse paletten döner."""
    cells = ""
    for i, c in enumerate(cards):
        renk = c.get("renk") or KART_PALET[i % len(KART_PALET)]
        ttl = f' title="{c["help"]}"' if c.get("help") else ""
        ipucu = ' <span style="color:#64748B;font-size:11px">ⓘ</span>' if c.get("help") else ""
        alt = c.get("alt", "")
        alt_html = (f'<div style="color:#7C8AA0;font-size:10px;margin-top:3px;'
                    f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{alt}</div>') if alt else ""
        cells += (
            f'<div{ttl} style="flex:1;min-width:128px;background:rgba(255,255,255,0.022);'
            f'border:1px solid rgba(255,255,255,0.06);border-left:3px solid {renk};'
            f'border-radius:13px;padding:11px 15px">'
            f'<div style="color:#8B97A8;font-size:9.5px;font-weight:700;letter-spacing:.6px;'
            f'text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{c["label"]}{ipucu}</div>'
            f'<div style="color:{renk};font-size:20px;font-weight:800;margin-top:2px;'
            f'font-variant-numeric:tabular-nums;letter-spacing:-0.3px;white-space:nowrap;'
            f'overflow:hidden;text-overflow:ellipsis">{c["value"]}</div>'
            f'{alt_html}</div>'
        )
    st.markdown(f'<div style="display:flex;gap:10px;flex-wrap:wrap;margin:2px 0 14px">{cells}</div>',
                unsafe_allow_html=True)


def metrik_karti(label, value, renk="#818CF8", alt="", help=""):
    """Tek bir kartı satır olarak çizer (metrik_satiri kısayolu)."""
    metrik_satiri([{"label": label, "value": value, "renk": renk, "alt": alt, "help": help}])


def metric_css(renk="#818CF8") -> str:
    """Geriye kalan st.metric öğelerini de aynı koyu kart görünümüne sokan global CSS."""
    return f"""
    <style>
    div[data-testid="stMetric"]{{
        background:rgba(255,255,255,0.022) !important;
        border:1px solid rgba(255,255,255,0.06) !important;
        border-left:3px solid {renk} !important;
        border-radius:13px !important;
        padding:11px 15px !important;
    }}
    div[data-testid="stMetricLabel"] p, div[data-testid="stMetricLabel"]{{
        color:#8B97A8 !important; font-size:9.5px !important; font-weight:700 !important;
        letter-spacing:.6px !important; text-transform:uppercase !important;
    }}
    div[data-testid="stMetricValue"]{{
        color:#F1F5F9 !important; font-size:20px !important; font-weight:800 !important;
        font-variant-numeric:tabular-nums; line-height:1.2 !important;
    }}
    </style>
    """


def modern_input_stil() -> str:
    """Tüm modüllerde ortak modern form alanları:
      • number_input'taki +/- adım düğmelerini gizler,
      • text/number/textarea/date input ve selectbox'lara modern görünüm verir
        (yuvarlak köşe, yumuşak kenar, odakta parlama, rahat iç boşluk).
    app.py'de modül dağıtımından hemen önce bir kez enjekte edilir → her sayfaya uygulanır.
    """
    return """
    <style>
    /* number_input +/- adım düğmelerini kaldır */
    [data-testid="stNumberInputStepUp"],
    [data-testid="stNumberInputStepDown"] { display:none !important; }
    [data-testid="stNumberInput"] button { display:none !important; }

    /* Görünür kutu = baseweb input/select sarmalayıcısı */
    div[data-baseweb="input"],
    div[data-baseweb="base-input"],
    div[data-baseweb="select"] > div,
    [data-testid="stTextArea"] textarea {
        background: rgba(255,255,255,0.045) !important;
        border: 1px solid rgba(148,163,184,0.22) !important;
        border-radius: 11px !important;
        transition: border-color .15s ease, box-shadow .15s ease, background .15s ease !important;
        box-shadow: none !important;
    }
    div[data-baseweb="select"] > div { min-height: 44px !important; }

    /* İç input — şeffaf, rahat boşluk, okunaklı */
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stDateInput"] input,
    [data-testid="stTextArea"] textarea {
        background: transparent !important;
        color: #E8EDF4 !important;
        font-size: 13.5px !important;
        padding: 11px 14px !important;
        border: none !important;
        font-variant-numeric: tabular-nums;
    }
    [data-testid="stTextArea"] textarea { padding: 12px 14px !important; }

    /* Placeholder daha yumuşak */
    [data-testid="stTextInput"] input::placeholder,
    [data-testid="stNumberInput"] input::placeholder,
    [data-testid="stTextArea"] textarea::placeholder { color: rgba(148,163,184,0.65) !important; }

    /* Hover */
    div[data-baseweb="input"]:hover,
    div[data-baseweb="base-input"]:hover,
    div[data-baseweb="select"] > div:hover,
    [data-testid="stTextArea"] textarea:hover {
        border-color: rgba(148,163,184,0.40) !important;
        background: rgba(255,255,255,0.06) !important;
    }
    /* Odak — accent parlaması */
    div[data-baseweb="input"]:focus-within,
    div[data-baseweb="base-input"]:focus-within,
    div[data-baseweb="select"]:focus-within > div,
    [data-testid="stTextArea"] textarea:focus {
        border-color: #6366F1 !important;
        box-shadow: 0 0 0 3px rgba(99,102,241,0.20) !important;
        background: rgba(99,102,241,0.06) !important;
    }

    /* BaseWeb'in kendi iç kenarlığını sıfırla (çift kenar olmasın) */
    div[data-baseweb="input"] > div,
    div[data-baseweb="base-input"] > div { border: none !important; background: transparent !important; }

    /* Etiketler biraz daha okunur */
    [data-testid="stWidgetLabel"] p { font-size: 12px !important; color: #AEB9C9 !important; font-weight: 600 !important; }
    </style>
    """


# ─────────────────────────── PDF Türkçe Font ───────────────────────────
_PDF_FONT_KAYITLI = {"normal": None, "bold": None}


def pdf_turkce_font():
    """reportlab için Türkçe (ş, ğ, İ, ı, ç, ö, ü) destekli font kaydeder.
    Döner: (normal_font_adi, bold_font_adi). Kayıt başarısızsa Helvetica'ya düşer.
    Bir kez kaydeder, sonraki çağrılarda hazır adları döndürür."""
    if _PDF_FONT_KAYITLI["normal"]:
        return _PDF_FONT_KAYITLI["normal"], _PDF_FONT_KAYITLI["bold"]
    import os
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.pdfmetrics import registerFontFamily

    burada = os.path.dirname(os.path.abspath(__file__))
    adaylar_normal = [
        os.path.join(burada, "fonts", "DejaVuSans.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    adaylar_bold = [
        os.path.join(burada, "fonts", "DejaVuSans-Bold.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    yol_n = next((p for p in adaylar_normal if os.path.exists(p)), None)
    yol_b = next((p for p in adaylar_bold if os.path.exists(p)), None)
    try:
        if yol_n:
            pdfmetrics.registerFont(TTFont("DejaVuSans", yol_n))
            if yol_b:
                pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", yol_b))
            else:
                pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", yol_n))
            registerFontFamily("DejaVuSans", normal="DejaVuSans", bold="DejaVuSans-Bold",
                               italic="DejaVuSans", boldItalic="DejaVuSans-Bold")
            _PDF_FONT_KAYITLI["normal"] = "DejaVuSans"
            _PDF_FONT_KAYITLI["bold"] = "DejaVuSans-Bold"
            return "DejaVuSans", "DejaVuSans-Bold"
    except Exception:
        pass
    _PDF_FONT_KAYITLI["normal"] = "Helvetica"
    _PDF_FONT_KAYITLI["bold"] = "Helvetica-Bold"
    return "Helvetica", "Helvetica-Bold"


def pdf_stilleri_turkcele(styles, normal=None, bold=None):
    """getSampleStyleSheet() ile gelen tüm stillerin fontunu Türkçe fonta çevirir."""
    if normal is None:
        normal, bold = pdf_turkce_font()
    for ad in list(styles.byName.keys()):
        try:
            st_obj = styles[ad]
            st_obj.fontName = bold if ("Bold" in (st_obj.fontName or "") or "Heading" in ad or "Title" in ad) else normal
        except Exception:
            pass
    return styles
