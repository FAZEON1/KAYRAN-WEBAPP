# -*- coding: utf-8 -*-
"""
KAYRAN — TASARIM ÇEKİRDEĞİ (v2)
===============================
Programın TEK görsel kaynağı. Buradaki değerleri değiştir → her yer değişir.

Neden yeni dosya:
  Eski `shared/ui.py` doğru fikirdi ama yarım kaldı — token'ları tanımlayıp
  kullanmıyordu. Bu dosya token'ları CSS SINIFI olarak yayınlar; modüller
  artık inline hex yazmak yerine sınıf adı yazar.

Kullanım (app.py'de BİR KEZ):
    from shared.tasarim import cekirdek_css
    st.markdown(cekirdek_css(), unsafe_allow_html=True)

Sonra her modülde:
    from shared.tasarim import baslik, kpi_serit, kart, kart_grid, rozet, satir, sayi
    st.markdown(baslik("Satış", "Kâr / P&L", "01.01 – 28.07.2026"), unsafe_allow_html=True)
    st.markdown(kpi_serit([
        {"etiket": "CİRO",    "deger": sayi(1_170_000, "$")},
        {"etiket": "NET KÂR", "deger": sayi(181_000, "$"), "renk": "yesil"},
        {"etiket": "MARJ",    "deger": "%25,9",            "renk": "cyan"},
    ]), unsafe_allow_html=True)

GERİYE UYUMLULUK: `RENK` sözlüğünün anahtarları eski `shared/ui.py` ile
birebir aynı. Eski kod bozulmadan çalışmaya devam eder.
"""

# ═══════════════════════════════════════════════════════════════════
# 1. PALET — tek rampa. Zemin #0B1120 (slate) ailesine kilitli.
#    .streamlit/config.toml bu değerlerle AYNI olmalı, yoksa dikiş görünür.
# ═══════════════════════════════════════════════════════════════════
RENK = {
    # ── Yüzeyler: en dipten en öne (tek aile, tek hue) ──
    "yuzey0":  "#0B1120",   # sayfa zemini      → config.toml backgroundColor
    "yuzey1":  "#0F172A",   # kart zemini       → config.toml secondaryBackgroundColor
    "yuzey2":  "#152036",   # öne çıkan / hover
    "yuzey3":  "#1C2A44",   # en öndeki eleman (dialog, popover)
    "kenar":   "rgba(148,163,184,0.10)",
    "kenar2":  "rgba(148,163,184,0.18)",

    # ── Metin: 3 kademe, fazlası gürültü ──
    # Kontrast (kart zemini #0F172A üzerinde, WCAG AA eşiği 4.5):
    "metin":   "#E2E8F0",   # 15.3  ✓
    "soluk":   "#94A3B8",   #  7.0  ✓
    "silik":   "#7B8AA0",   #  5.1  ✓  (eski #64748B = 3.75 → eşiğin altındaydı)

    # ── Anlam renkleri: her biri TEK ton + TEK açık ton ──
    "mor":      "#818CF8",  "mor2":      "#A5B4FC",   # marka / nötr metrik
    "yesil":    "#34D399",  "yesil2":    "#6EE7B7",   # pozitif
    "kirmizi":  "#F87171",  "kirmizi2":  "#FCA5A5",   # negatif / acil
    "amber":    "#FBBF24",  "amber2":    "#FCD34D",   # uyarı / beklemede
    "cyan":     "#22D3EE",  "cyan2":     "#67E8F9",   # bilgi / oran

    # ── Modül kimlikleri (sidebar çipi + kart sol şeridi) ──
    "mavi":     "#7DD3FC",   # ithalat
    "pembe":    "#F9A8D4",   # ürün yönetimi
}

# ── KALDIRILAN RENKLER ──────────────────────────────────────────────
# #A78BFA, #F472B6, #FB923C  → KART_PALET'ten geliyordu, RENK'te karşılığı yoktu
# #10B981, #EF4444, #F59E0B  → mevcut tonların hafif varyantlarıydı
# #60A5FA, #93C5FD, #CBD5E1  → mavi/metin tonlarıyla çakışıyordu
# Toplam 205 farklı hex → 22. Eşleme tablosu için ESKI_RENK_ESLEME'ye bak.
ESKI_RENK_ESLEME = {
    "#A78BFA": "mor",   "#F472B6": "pembe",  "#FB923C": "amber",
    "#10B981": "yesil", "#EF4444": "kirmizi", "#F59E0B": "amber",
    "#60A5FA": "mavi",  "#93C5FD": "mavi",   "#CBD5E1": "metin",
    "#6EE7B7": "yesil2", "#FCD34D": "amber2", "#F1F5F9": "metin",
    "#7C8AA0": "soluk", "#8B97A8": "soluk",  "#475569": "silik",
    "#131C35": "yuzey2", "#0F1730": "yuzey1", "#080C20": "yuzey0",
    "#5B6B84": "silik",  "#8B98B8": "soluk",  "#B6C2D6": "metin",
    "#FFFFFF": "metin",  "#FDA4AF": "kirmizi2", "#F9A8D4": "pembe",
}

# ── Renk verilmeyen kartlar için döngü (eski KART_PALET'in karşılığı) ──
KART_TOKEN = ["mor", "yesil", "amber", "mor2", "cyan", "pembe", "mavi"]

# ── Modül → kimlik rengi (tek yerden) ──
MODUL_RENK = {
    "kayranacc":     "mor2",
    "kayranpm":      "pembe",
    "ithalat":       "mavi",
    "satis":         "yesil",
    "depo":          "yesil2",
    "teknikservis":  "kirmizi2",
    "yonetim":       "cyan",
    "hesap_makinesi": "amber2",
}


# ═══════════════════════════════════════════════════════════════════
# 2. YOĞUNLUK — kompaktlığın kaynağı.
#    "sik" veri ekranlarının varsayılanı; "genis" sadece giriş formları için.
# ═══════════════════════════════════════════════════════════════════
YOGUNLUK = {
    "sik": {
        "kart_pad":   "9px 13px",
        "kart_r":     "10px",
        "grid_gap":   "8px",
        "serit_alt":  "10px",
        "satir_pad":  "3px 10px",
        "kart_min":   "132px",
    },
    "genis": {
        "kart_pad":   "13px 17px",
        "kart_r":     "12px",
        "grid_gap":   "12px",
        "serit_alt":  "16px",
        "satir_pad":  "5px 12px",
        "kart_min":   "160px",
    },
}
VARSAYILAN_YOGUNLUK = "sik"

# ═══════════════════════════════════════════════════════════════════
# 3. TİPOGRAFİ — 6 boyut. Değere göre küçülme YOK.
#    Uzun sayı kartı taşırmasın diye sayi() kısaltır, font sabit kalır.
# ═══════════════════════════════════════════════════════════════════
FONT = {
    "etiket":  "10px",   # KPI etiketi (uppercase, tracking .6)
    "kucuk":   "11px",   # rozet · caption · zaman damgası
    "govde":   "13px",   # liste satırı · tablo · gövde
    "orta":    "14px",   # alt başlık · vurgulu satır
    "baslik":  "16px",   # sayfa başlığı
    "deger":   "19px",   # metrik değeri (mono, tabular)
    "hero":    "23px",   # SADECE tek başına duran büyük rakam (Toplam Aktifler)
}
MONO = "'JetBrains Mono', ui-monospace, monospace"
SANS = "Inter, -apple-system, sans-serif"

# ── AĞIRLIK: 3 kademe. Programda 8 farklı ağırlık vardı (450/750/900 dahil)
#    ve 931 kalın kullanıma karşılık sadece 10 normal — her şey aynı anda
#    bağırıyordu. Gövde artık 400; kalın istisna. ──
AGIRLIK = {
    "govde":  "400",   # varsayılan. Liste satırı, tablo, açıklama, caption.
    "vurgu":  "600",   # etiket, aktif sekme, öne çıkan satır.
    "baslik": "700",   # sayfa başlığı, KPI değeri, kart başlığı. Fazlası yok.
}

# ── TRACKING: 3 değer. 38 farklı letter-spacing vardı. ──
TRACKING = {
    "baslik":  "-0.2px",  # 16px+ başlıklar
    "govde":   "0",       # her şey
    "etiket":  "0.6px",   # SADECE uppercase KPI etiketleri
}


def _y(anahtar, yogunluk=None):
    return YOGUNLUK.get(yogunluk or VARSAYILAN_YOGUNLUK, YOGUNLUK["sik"])[anahtar]


# ═══════════════════════════════════════════════════════════════════
# 4. SAYI BİÇİMLENDİRME
#    Kart daralınca fontu küçültmek yerine sayıyı kısaltırız; tam değer
#    title="" içinde durur, üstüne gelince görünür.
# ═══════════════════════════════════════════════════════════════════
def sayi(deger, birim="", kisa=True, basamak=0):
    """1170000 → '$1,17M' (title'da tam değer). Font sabit 19px kalır."""
    try:
        d = float(deger)
    except (TypeError, ValueError):
        return str(deger)
    isaret = "-" if d < 0 else ""
    m = abs(d)
    if kisa and m >= 1_000_000_000:
        govde = _tr(f"{m/1_000_000_000:,.2f}") + "B"
    elif kisa and m >= 1_000_000:
        govde = _tr(f"{m/1_000_000:,.2f}") + "M"
    elif kisa and m >= 100_000:
        govde = _tr(f"{m/1_000:,.0f}") + "K"
    else:
        govde = _tr(f"{m:,.{basamak}f}")
    return f"{isaret}{birim}{govde}"


def _tr(s):
    """Türkçe sayı biçimi: binlik nokta, ondalık virgül. 1,234.50 → 1.234,50"""
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _tam(deger, birim=""):
    try:
        return f"{birim}{float(deger):,.2f}"
    except (TypeError, ValueError):
        return str(deger)


# ═══════════════════════════════════════════════════════════════════
# 5. ÇEKİRDEK CSS — app.py'de bir kez. Tüm sınıflar burada tanımlı.
# ═══════════════════════════════════════════════════════════════════
def css_tek_satir(metin: str) -> str:
    """CSS'i markdown'ın karışamayacağı tek hatta indirir.

    NEDEN: st.markdown(..., unsafe_allow_html=True) ile basılan bir <style>
    bloğunda BOŞ SATIR varsa, markdown HTML bloğunu orada kapatıyor ve
    kalan CSS ekrana DÜZ METİN olarak basılıyor. Satır başındaki 4+ boşluk
    da ayrı bir sorun (girintili kod bloğu sayılıyor).

    Bu fonksiyon boş satırları atar, girintileri kırpar, hepsini tek hatta
    birleştirir. CSS için satır sonu anlamsızdır — davranış değişmez.

    CSS üreten HER fonksiyon çıkışını buradan geçirmeli.
    """
    tek = "".join(l.strip() for l in str(metin).split("\n") if l.strip())
    # Bitişik bloklar birleştirilir: '</style><style>' dizisinde ikinci
    # <style> satır başında olmadığı için markdown onu HTML bloğu saymaz.
    while "</style><style>" in tek:
        tek = tek.replace("</style><style>", "")
    return tek


def _streamlit_normalize():
    """Streamlit'in KENDİ ilkellerini tasarım sistemine sokar.

    NEDEN AYRI: Şimdiye kadar stil bileşen bazlıydı ve opt-in'di — modül
    çağırmayı unutunca Streamlit'in ham hali çıkıyordu. (metric_css()
    hiçbir modülden çağrılmıyordu; bu yüzden her st.metric 64px değerle,
    kartsız çiziliyordu.) Burası app.py'de bir kez basılır ve hiçbir
    modülün kaçamayacağı taban katmanıdır.

    Kapsam: başlıklar (### → h3) · st.metric · st.info/warning/success/error
    (745 çağrı) · st.expander (67) · caption · ayraç · sekme · buton.
    """
    R, F, A, T = RENK, FONT, AGIRLIK, TRACKING
    y = YOGUNLUK["sik"]
    # DİKKAT: <style> sarmalı YOK. cekirdek_css() her şeyi TEK bloğa koyar.
    # (İki bloğu uç uca eklemek '</style><style>' üretiyordu; satır başında
    #  olmayan <style> etiketi markdown tarafından HTML bloğu sayılmadığı
    #  için ikinci bloğun içeriği ekrana düz metin olarak basılıyordu.)
    return f"""
/* ── BAŞLIKLAR: markdown ### ve st.header hep aynı ölçekte ── */
.stApp h1{{font-size:20px !important;}}
.stApp h2{{font-size:18px !important;}}
.stApp h3{{font-size:{F['baslik']} !important;}}
.stApp h4,.stApp h5,.stApp h6{{font-size:{F['orta']} !important;}}
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp h5,.stApp h6{{
  font-weight:{A['baslik']} !important;letter-spacing:{T['baslik']} !important;
  color:{R['metin']} !important;line-height:1.3 !important;
  padding:0 !important;margin:14px 0 6px !important;}}

/* ── st.metric: ortak kart diline sokulur ── */
div[data-testid="stMetric"]{{
  background:{R['yuzey1']} !important;border:1px solid {R['kenar']} !important;
  border-left:2px solid {R['mor']} !important;border-radius:{y['kart_r']} !important;
  padding:{y['kart_pad']} !important;}}
div[data-testid="stMetricLabel"],div[data-testid="stMetricLabel"] p,
div[data-testid="stMetricLabel"] div{{
  font-size:{F['etiket']} !important;color:{R['soluk']} !important;
  font-weight:{A['vurgu']} !important;letter-spacing:{T['etiket']} !important;
  text-transform:uppercase !important;line-height:1.3 !important;
  white-space:normal !important;overflow:visible !important;}}
div[data-testid="stMetricValue"],div[data-testid="stMetricValue"] div{{
  font-size:{F['deger']} !important;color:{R['metin']} !important;
  font-weight:{A['baslik']} !important;font-family:{MONO} !important;
  font-variant-numeric:tabular-nums !important;letter-spacing:{T['baslik']} !important;
  line-height:1.3 !important;}}
div[data-testid="stMetricDelta"]{{font-size:{F['kucuk']} !important;
  font-family:{MONO} !important;}}

/* ── Uyarı kutuları: 745 çağrı, hepsi tek dilde ── */
div[data-testid="stAlert"],div[data-testid="stNotification"]{{
  border-radius:{y['kart_r']} !important;padding:8px 13px !important;
  border:1px solid {R['kenar2']} !important;border-left-width:2px !important;
  margin:6px 0 !important;}}
div[data-testid="stAlert"] p,div[data-testid="stNotification"] p{{
  font-size:{F['govde']} !important;font-weight:{A['govde']} !important;
  line-height:1.55 !important;margin:0 !important;}}
div[data-testid="stAlert"] svg,div[data-testid="stNotification"] svg{{
  width:15px !important;height:15px !important;}}

/* ── Expander: 67 çağrı ── */
details[data-testid="stExpander"],div[data-testid="stExpander"] details{{
  border:1px solid {R['kenar']} !important;border-radius:{y['kart_r']} !important;
  background:{R['yuzey1']} !important;}}
div[data-testid="stExpander"] summary{{
  padding:7px 13px !important;font-size:{F['govde']} !important;
  font-weight:{A['vurgu']} !important;color:{R['soluk']} !important;}}
div[data-testid="stExpander"] summary:hover{{color:{R['metin']} !important;}}
div[data-testid="stExpander"] summary p{{
  font-size:{F['govde']} !important;font-weight:{A['vurgu']} !important;}}

/* ── Caption · ayraç · sekme ── */
div[data-testid="stCaptionContainer"] p,.stApp small{{
  font-size:{F['kucuk']} !important;color:{R['silik']} !important;
  font-weight:{A['govde']} !important;line-height:1.5 !important;}}
.stApp hr,div[data-testid="stDivider"] hr{{
  border-color:{R['kenar']} !important;margin:12px 0 !important;}}
button[data-baseweb="tab"]{{font-size:{F['govde']} !important;
  font-weight:{A['vurgu']} !important;border-radius:9px 9px 0 0 !important;}}
button[data-baseweb="tab"][aria-selected="true"]{{
  background:rgba(129,140,248,0.10) !important;color:{R['metin']} !important;}}

/* ── Gövde metni: varsayılan 400. Program 931 kalın / 10 normal idi. ── */
.stApp [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stMarkdownContainer"] li{{
  font-size:{F['govde']} !important;font-weight:{A['govde']} !important;
  line-height:1.6 !important;}}
.stApp [data-testid="stMarkdownContainer"] strong{{
  font-weight:{A['vurgu']} !important;color:{R['metin']} !important;}}
"""


def cekirdek_css(yogunluk=None):
    R, F = RENK, FONT
    kp, kr, gg, sa, sp, kmin = (_y("kart_pad", yogunluk), _y("kart_r", yogunluk),
                                _y("grid_gap", yogunluk), _y("serit_alt", yogunluk),
                                _y("satir_pad", yogunluk), _y("kart_min", yogunluk))
    degiskenler = "".join(f"--k-{k}:{v};" for k, v in R.items())
    return "<style>" + css_tek_satir(f"""
:root{{{degiskenler}--k-r:{kr};--k-gap:{gg};--k-pad:{kp};--k-mono:{MONO};}}

.k-grid{{display:flex;gap:var(--k-gap);flex-wrap:wrap;align-items:stretch;margin:0 0 {sa};}}

.k-kart{{flex:1;min-width:{kmin};background:{R['yuzey1']};
  border:1px solid {R['kenar']};border-radius:var(--k-r);padding:var(--k-pad);
  display:flex;flex-direction:column;
  transition:background .12s ease,border-color .12s ease;}}
.k-kart:hover{{background:{R['yuzey2']};border-color:{R['kenar2']};}}
.k-kart[data-akscent]{{border-left-width:2px;border-radius:var(--k-r);}}

.k-etiket{{font-size:{F['etiket']};color:{R['soluk']};
  font-weight:{AGIRLIK['vurgu']};letter-spacing:{TRACKING['etiket']};text-transform:uppercase;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;line-height:1.2;}}
.k-deger{{font-size:{F['deger']};color:{R['metin']};font-weight:{AGIRLIK['baslik']};
  font-family:var(--k-mono);font-variant-numeric:tabular-nums;
  letter-spacing:{TRACKING['baslik']};margin-top:2px;line-height:1.25;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.k-alt{{font-size:{F['kucuk']};color:{R['silik']};margin-top:2px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}

.k-baslik{{display:flex;align-items:center;gap:8px;
  padding:0 0 7px;margin:0 0 11px;
  border-bottom:1px solid {R['kenar']};}}
.k-baslik-ikon{{width:22px;height:22px;border-radius:6px;flex-shrink:0;
  background:{R['yuzey2']};border:1px solid {R['kenar2']};
  display:flex;align-items:center;justify-content:center;font-size:12px;}}
.k-baslik-mod{{font-size:{F['orta']};color:{R['soluk']};font-weight:{AGIRLIK['vurgu']};}}
.k-baslik-ayrac{{color:{R['silik']};font-size:{F['orta']};}}
.k-baslik-ad{{font-size:{F['baslik']};color:{R['metin']};
  font-weight:{AGIRLIK['baslik']};letter-spacing:{TRACKING['baslik']};}}
.k-baslik-alt{{margin-left:auto;font-size:{F['kucuk']};color:{R['silik']};
  font-family:var(--k-mono);white-space:nowrap;}}

.k-rozet{{display:inline-block;padding:2px 7px;border-radius:999px;
  font-size:{F['kucuk']};font-weight:{AGIRLIK['vurgu']};line-height:1.4;white-space:nowrap;}}

.k-pencere-basi{{display:flex;align-items:center;gap:8px;margin-bottom:6px;
  flex-shrink:0;font-size:{F['govde']};font-weight:{AGIRLIK['baslik']};}}
.k-pencere-ic{{overflow-y:auto;padding-right:6px;}}
.k-pencere-ic::-webkit-scrollbar{{width:5px;}}
.k-pencere-ic::-webkit-scrollbar-track{{background:transparent;}}
.k-pencere-ic::-webkit-scrollbar-thumb{{background:{R['kenar2']};border-radius:3px;}}

.k-satir{{display:flex;justify-content:space-between;align-items:center;
  padding:{sp};margin:2px 0;border-radius:6px;font-size:{F['govde']};
  font-weight:{AGIRLIK['govde']};background:rgba(255,255,255,0.025);}}
.k-satir:hover{{background:rgba(255,255,255,0.05);}}
.k-satir-sag{{display:flex;gap:10px;flex-shrink:0;margin-left:8px;
  align-items:center;font-variant-numeric:tabular-nums;}}

.k-bos{{color:{R['silik']};font-size:{F['govde']};padding:10px 4px;}}

[data-testid="stDataFrame"]{{border-radius:var(--k-r) !important;
  overflow:hidden !important;border:1px solid {R['kenar']} !important;}}
div[data-testid="stDialog"] > div:first-child{{
  border:1px solid {R['kenar2']} !important;border-radius:14px !important;}}
div[data-testid="stDialog"] [data-testid="stHeading"]{{
  font-size:{F['baslik']} !important;font-weight:700 !important;
  letter-spacing:-.2px !important;color:{R['metin']} !important;}}
div[data-testid="stCaptionContainer"] p{{color:{R['soluk']} !important;}}

@media (max-width:640px){{
  .k-kart{{min-width:110px;}}
  .k-baslik-alt{{display:none;}}
}}
""" + _streamlit_normalize()) + "</style>"


def islem_gosterge_css():
    """Sadece üstte ince akan çubuk. Nabız atan 'İşleniyor' kapsülü KALDIRILDI —
    her checkbox tıklamasında ekranın ortasında uyarı belirmesi, uygulamayı
    olduğundan yavaş hissettiriyordu."""
    return "<style>" + css_tek_satir(f"""
@keyframes k-akan{{0%{{background-position:0 0}}100%{{background-position:200% 0}}}}
div[data-testid="stApp"][data-test-script-state="running"]::before{{
  content:"";position:fixed;top:0;left:0;right:0;height:2px;z-index:999999;
  background:linear-gradient(90deg,{RENK['mor']},{RENK['cyan']},{RENK['mor']});
  background-size:200% 100%;animation:k-akan 1.1s linear infinite;}}
div[data-testid="stStatusWidget"]{{display:none !important;}}
div[data-stale="true"]{{opacity:.5 !important;transition:opacity .2s ease;}}
""") + "</style>"


# ═══════════════════════════════════════════════════════════════════
# 6. BİLEŞENLER — programda "etiketli kutu" artık SADECE burada.
# ═══════════════════════════════════════════════════════════════════
def baslik(modul, sayfa, alt="", ipucu=""):
    """Tek satır kompakt başlık: 34px. Eskisi 85px'ti.

    Modül adı zaten sidebar çipinde ve aktif nav pill'inde yazıyor — bu,
    nerede olduğunun üçüncü kez söylenmesiydi. Kırıntı biçimine indirildi.

    modul  : "🧾 Satış" gibi (baştaki emoji ikon karosuna alınır)
    sayfa  : "Kâr / P&L"
    alt    : sağda mono ile — kısa olmalı ("01.01–28.07.2026")
    ipucu  : uzun açıklama. Piksel harcamaz, üstüne gelince görünür.
    """
    ikon = ""
    if modul and not modul[0].isalnum():
        ikon = f'<div class="k-baslik-ikon">{modul[0]}</div>'
        modul = modul[1:].strip()
    alt_html = f'<div class="k-baslik-alt">{alt}</div>' if alt else ""
    ttl = f' title="{ipucu}"' if ipucu else ""
    return (f'<div class="k-baslik"{ttl}>{ikon}'
            f'<span class="k-baslik-mod">{modul}</span>'
            f'<span class="k-baslik-ayrac">›</span>'
            f'<span class="k-baslik-ad">{sayfa}</span>{alt_html}</div>')


def kpi_serit(kalemler, yogunluk=None):
    """KPI kartı şeridi — programdaki TEK metrik bileşeni.

    kalemler = [{"etiket","deger","renk"?,"alt"?,"ipucu"?,"tam"?}]
    `renk` RENK anahtarıdır ("yesil"), hex DEĞİL.
    """
    hucreler = ""
    for k in kalemler:
        c = RENK.get(k.get("renk", "mor"), RENK["mor"])
        ipucu = k.get("ipucu") or k.get("tam") or ""
        ttl = f' title="{ipucu}"' if ipucu else ""
        alt = f'<div class="k-alt">{k["alt"]}</div>' if k.get("alt") else ""
        hucreler += (
            f'<div class="k-kart" data-akscent style="border-left-color:{c}"{ttl}>'
            f'<div class="k-etiket">{k["etiket"]}</div>'
            f'<div class="k-deger" style="color:{c}">{k["deger"]}</div>'
            f'{alt}</div>')
    return f'<div class="k-grid">{hucreler}</div>'


def kart(baslik_metni, renk, icerik_html, rozet_metni="", yukseklik=170):
    """İç kaydırmalı pencere kartı. `renk` RENK anahtarı."""
    c = RENK.get(renk, RENK["mor"])
    roz = rozet(rozet_metni, renk) if rozet_metni else ""
    return (f'<div class="k-kart" data-akscent style="border-left-color:{c}">'
            f'<div class="k-pencere-basi" style="color:{c}">'
            f'<span>{baslik_metni}</span>{roz}</div>'
            f'<div class="k-pencere-ic" style="max-height:{yukseklik}px">'
            f'{icerik_html}</div></div>')


def kart_grid(*kartlar):
    return f'<div class="k-grid">{"".join(kartlar)}</div>'


def rozet(metin, renk="mor"):
    c = RENK.get(renk, RENK["mor"])
    return f'<span class="k-rozet" style="background:{c}22;color:{c}">{metin}</span>'


def satir(sol_html, sag_html=""):
    sag = f'<div class="k-satir-sag">{sag_html}</div>' if sag_html else ""
    return f'<div class="k-satir">{sol_html}{sag}</div>'


def bos(mesaj):
    return f'<div class="k-bos">{mesaj}</div>'


def tablo_h(n_satir, maks=320):
    """st.dataframe yüksekliği: içerik kadar, en fazla `maks`."""
    try:
        n = max(1, int(n_satir))
    except (TypeError, ValueError):
        n = 1
    return int(min(maks, 38 + 35 * n))


# ═══════════════════════════════════════════════════════════════════
# 7. TABLO KOLONLARI
#    Sorun: para değerleri DataFrame'e METİN olarak giriyordu ("$1.170.000").
#    Sonuç: sola yaslanıyor VE başlığa tıklayınca alfabetik sıralanıyor —
#    "$689" ile "$1.170.000" karşılaştırıldığında ikincisi küçük çıkıyor.
#    Çözüm: değerler sayısal kalır, biçimi burası verir.
#
#    KÂR GİZLEME UYUMU: df_maskele() maskelediği kolonu "•••" metnine
#    çevirir → dtype sayısal olmaktan çıkar → bu fonksiyon o kolona
#    dokunmaz, metin olarak geçer. Maskeleme bozulmaz.
# ═══════════════════════════════════════════════════════════════════
_ORAN_K = ("marj", "kârlılık", "karlilik", "oran", "yüzde", "%")
_ADET_K = ("adet", "kalem", "satır", "satir", "fatura", "stok", "sayı", "sayi")
_PARA_K = ("ciro", "tutar", "maliyet", "kâr", "kar ", "kar)", "destek", "fiyat",
           "bakiye", "gider", "masraf", "satış", "satis", "cogs", "b.satış",
           "b.maliyet", "iskonto")


def _kolon_tipi(ad):
    a = str(ad).strip().lower()
    if any(k in a for k in _ORAN_K):
        return "oran"
    if any(k in a for k in _ADET_K):      # "Satış adedi" → adet, para değil
        return "adet"
    if a in ("kâr", "kar") or any(k in a for k in _PARA_K):
        return "para"
    return None


def tablo_kolonlari(df, para="dollar", ekstra=None):
    """DataFrame'e bakıp column_config üretir. Sadece SAYISAL kolonlara dokunur.

        st.dataframe(df, column_config=tablo_kolonlari(df), ...)

    para : "dollar" | "euro" | "accounting" | "localized"
    ekstra : elle ezmek istediğin kolonlar → {"Kolon": st.column_config...}
    """
    try:
        import pandas as pd
        import streamlit as st
    except ImportError:
        return ekstra or {}
    cfg = {}
    for c in df.columns:
        try:
            s = df[c]
            if pd.api.types.is_datetime64_any_dtype(s):
                cfg[c] = st.column_config.DateColumn(format="DD.MM.YYYY")
                continue
            if not pd.api.types.is_numeric_dtype(s):
                continue          # metin ya da maskelenmiş → olduğu gibi bırak
            t = _kolon_tipi(c)
            if t == "para":
                cfg[c] = st.column_config.NumberColumn(format=para, alignment="right")
            elif t == "adet":
                cfg[c] = st.column_config.NumberColumn(format="localized", alignment="right")
            elif t == "oran":
                cfg[c] = st.column_config.NumberColumn(format="%.1f%%", alignment="right")
        except Exception:
            continue              # tek kolon patlasa tablo yine çizilsin
    if ekstra:
        cfg.update(ekstra)
    return cfg


# ═══════════════════════════════════════════════════════════════════
# 8. OTOMATİK TABLO BİÇİMİ
#    st.dataframe app.py'de sarmalanır; bu fonksiyon her tabloya
#    kolon adına göre biçim verir. Böylece 74 tablo tek yerden düzelir.
#
#    Ham hali: 596699.4595 · 36.9231 · 21813
#    Biçimli : $596,699.46 · %36,9    · 21,813   (sağa yaslı, sıralanabilir)
# ═══════════════════════════════════════════════════════════════════

# Sıra ÖNEMLİ: yüzde → adet → para. "Net adet" hem 'net' hem 'adet' içerir;
# adet kazanmalı. "İade oranı" hem 'iade' hem 'oran' içerir; oran kazanmalı.
_ORAN_AD = ("marj", "oran", "kârlılık", "karlilik", "yüzde", "yuzde", "%")
_ADET_AD = ("adet", "kalem", "satır", "satir", "sayı", "sayi", "fatura",
            "stok", "miktar", "çeşit", "cesit", "gün", "gun", "adedi")
# TÜRKÇE ÜNSÜZ YUMUŞAMASI: "destek" → "desteği" (k→ğ), "alacak" → "alacağı".
# Alt dizge araması bu yüzden yumuşamış hâlleri de içermeli, yoksa
# "Ref No desteği" kolonu para sayılmaz ve biçimlenmez.
_PARA_AD = ("ciro", "tutar", "kâr", "kar", "maliyet", "destek", "desteğ",
            "alacağ", "fiyat",
            "bakiye", "gider", "masraf", "fob", "satış", "satis", "alış",
            "alis", "net", "brüt", "brut", "cogs", "ödeme", "odeme",
            "borç", "borc", "alacak", "çek", "cek", "bedel", "prim")


# ADET anlamına gelen kolonlar, içinde para kelimesi geçse bile adet kalmalı.
# "Toplam Satış" adet taşıyabilir (sell-out raporu) — para sanıp $ koymak
# rakamı yanlış gösteriyordu.
_ADET_ONCELIK = ("toplam satış", "toplam satis", "toplam stok", "satış adet",
                 "satis adet", "satılan", "satilan", "sellout", "sell-out",
                 "iade adet", "toplam adet", "stok adet")


def _tablo_kolon_tipi(ad):
    """Kolon adından biçim tipini çıkarır. None → dokunulmaz."""
    a = str(ad or "").strip().lower()
    if not a:
        return None
    if any(k in a for k in _ADET_ONCELIK):
        return "adet"
    if any(k in a for k in _ORAN_AD):
        return "oran"
    if any(k in a for k in _ADET_AD):
        return "adet"
    if any(k in a for k in _PARA_AD):
        return "para"
    return None


def otomatik_kolonlar(df, mevcut=None):
    """DataFrame'e bakıp column_config üretir.

    • Yalnız SAYISAL ve TARİH kolonlarına dokunur. Metin kolonları
      (kâr gizleme maskesi '•••' dahil) olduğu gibi kalır.
    • `mevcut` (elle yazılmış column_config) her zaman kazanır — bu fonksiyon
      yalnız eksikleri tamamlar, mevcut ayarı EZMEZ.
    • Hata durumunda boş döner; tablo asla kırılmaz.
    """
    try:
        import pandas as pd
        import streamlit as _st
    except ImportError:
        return dict(mevcut or {})
    cfg = {}
    # DİKKAT: `df.columns or []` YAZILAMAZ — pandas Index üzerinde `or`,
    # "truth value of a Index is ambiguous" hatası verir; except onu yutar ve
    # fonksiyon sessizce BOŞ config döndürür (hiçbir tablo biçimlenmez).
    try:
        _k = getattr(df, "columns", None)
        kolonlar = list(_k) if _k is not None else []
    except Exception:
        return dict(mevcut or {})
    for c in kolonlar:
        if mevcut and c in mevcut:
            continue                      # elle yazılan ayara dokunma
        try:
            seri = df[c]
            if pd.api.types.is_datetime64_any_dtype(seri):
                cfg[c] = _st.column_config.DateColumn(format="DD.MM.YYYY")
                continue
            if pd.api.types.is_bool_dtype(seri):
                continue                  # onay kutusu varsayılanı yeterli
            if not pd.api.types.is_numeric_dtype(seri):
                continue                  # metin / maskelenmiş → dokunma
            t = _tablo_kolon_tipi(c)
            if t == "para":
                cfg[c] = _st.column_config.NumberColumn(
                    format="dollar", alignment="right")
            elif t == "adet":
                cfg[c] = _st.column_config.NumberColumn(
                    format="localized", alignment="right")
            elif t == "oran":
                cfg[c] = _st.column_config.NumberColumn(
                    format="%%%.1f", alignment="right")
        except Exception:
            continue
    if mevcut:
        cfg.update(mevcut)
    return cfg


# ═══════════════════════════════════════════════════════════════════
# 9. HTML ÖZET TABLOSU
#    st.dataframe canvas'a çizildiği için görünümü değiştirilemiyor —
#    satır yüksekliği, hücre boşluğu, zebra, hover, hizalama, negatifi
#    kırmızıya boyamak, Türkçe sayı biçimi: hiçbiri mümkün değil.
#    Bu fonksiyon KISA, SALT-OKUR özet tabloları için HTML üretir.
#
#    KAYIP: başlığa tıklayıp sıralama · kolon genişliği · CSV indirme ·
#           satır seçimi. Uzun listelerde st.dataframe kalmalı.
# ═══════════════════════════════════════════════════════════════════

def _tr_para(v, birim="$", basamak=2):
    """1616061.27 → '$1.616.061,27' (TR ayraç). st.dataframe bunu yapamıyordu."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return ""
    s = f"{abs(f):,.{basamak}f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return ("-" if f < 0 else "") + birim + s


def _tr_adet(v):
    try:
        return f"{int(round(float(v))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return ""


def _tr_oran(v, basamak=2):
    try:
        return "%" + f"{float(v):,.{basamak}f}".replace(".", ",")
    except (TypeError, ValueError):
        return ""


def tablo_ciz(satirlar, birim="$", yukseklik=None, toplam_isaret="Σ",
              stil="zebra"):
    """Salt-okur özet tablosu (HTML). satirlar: [{kolon: değer}].

    stil:
      "zebra"   — çerçeveli, dolgulu başlık, dönüşümlü satır zemini.
                  Yoğun/uzun özetlerde göz kaymasını engeller.
      "havadar" — kutu ve zebra yok, yalnız saç teli çizgi + ferah aralık.
                  En modern duran; ama yer kapladığı için kısa tablolara.
      "rozet"   — havadar düzen + oran kolonları renkli rozette. Maliyeti
                  girilmemiş satırların %100 marjı böyle gözden kaçmıyor.

    Kolon tipi ADINDAN çıkarılır (_tablo_kolon_tipi): para · adet · oran.
    Negatifler kırmızı; ilk hücresi `toplam_isaret` ile başlayan satır
    toplam sayılıp vurgulanır. yukseklik verilirse başlık yapışkan olur.
    """
    if not satirlar:
        return bos(" Gösterilecek veri yok.")
    R, F, A = RENK, FONT, AGIRLIK
    kolonlar = list(satirlar[0].keys())
    tipler = {k: _tablo_kolon_tipi(k) for k in kolonlar}
    _acik = stil in ("havadar", "rozet")      # kutusuz düzen
    _rozet = (stil == "rozet")
    _pad = "10px 12px" if _acik else "6px 11px"
    _ilk_genislik = 130                      # sabit kolonun asgari genişliği
    _ilk_zemin = R["yuzey0"] if _acik else R["yuzey2"]

    # ── Başlık ──
    if _acik:
        _bas_stil = (f'font-size:{F["kucuk"]};font-weight:{A["vurgu"]};'
                     f'color:{R["silik"]};letter-spacing:.6px;text-transform:uppercase;'
                     f'padding:0 12px 8px;border-bottom:1px solid {R["kenar2"]};'
                     f'background:transparent')
    else:
        _bas_stil = (f'font-size:{F["kucuk"]};font-weight:{A["vurgu"]};'
                     f'color:{R["soluk"]};letter-spacing:.3px;padding:8px 11px;'
                     f'background:{R["yuzey2"]};border-bottom:1px solid {R["kenar2"]}')
    _bas = "".join(
        f'<th style="text-align:{"right" if tipler[k] else "left"};{_bas_stil};'
        f'position:sticky;top:0;white-space:nowrap'
        # İlk kolon YATAY kaydırmada da sabit kalır (left:0). Başlık hücresi
        # hem üstte hem solda durduğu için z-index en yüksek olmalı, yoksa
        # kayan sayı hücreleri üstüne biner.
        + (f';left:0;z-index:3;min-width:{_ilk_genislik}px;'
           f'background:{_ilk_zemin}' if _i == 0 else ';z-index:2')
        + f'">{k}</th>'
        for _i, k in enumerate(kolonlar))

    # ── Gövde ──
    _govde = []
    for i, r in enumerate(satirlar):
        _toplam = str(r.get(kolonlar[0], "") or "").strip().startswith(toplam_isaret)
        if _toplam:
            _satir_stil = (f'border-top:1px solid {R["kenar2"]}'
                           if _acik else
                           f'background:{R["yuzey2"]};border-top:1px solid {R["kenar2"]}')
        elif _acik:
            _satir_stil = "background:transparent"
        else:
            _satir_stil = f'background:{R["yuzey2"] if i % 2 else "transparent"}'

        # Sabit ilk kolonun zemini satırınkiyle AYNI olmalı (zebra dahil),
        # yoksa kaydırırken şerit gibi görünür.
        _satir_zemin = (R["yuzey2"] if (_toplam or (not _acik and i % 2))
                        else R["yuzey1"])
        _hucre = []
        for k in kolonlar:
            v, t = r.get(k), tipler[k]
            if t == "para":
                metin, sayi_mi = _tr_para(v, birim), True
            elif t == "adet":
                metin, sayi_mi = _tr_adet(v), True
            elif t == "oran":
                metin, sayi_mi = _tr_oran(v), True
            else:
                metin, sayi_mi = ("" if v is None else str(v)), False
            try:
                _neg = sayi_mi and float(v) < 0
            except (TypeError, ValueError):
                _neg = False
            _cizgi = f';border-bottom:1px solid {R["kenar"]}' if (_acik and not _toplam) else ""

            # Rozet: yalnız oran kolonlarında
            if _rozet and t == "oran" and metin:
                _rc = R["mor"] if _toplam else (R["kirmizi"] if _neg else R["yesil"])
                _ic = (f'<span style="display:inline-block;padding:2px 8px;'
                       f'border-radius:{YOGUNLUK["sik"]["kart_r"]};'
                       f'background:{_rc}22;color:{_rc};font-size:{F["kucuk"]};'
                       f'font-family:{MONO};font-variant-numeric:tabular-nums;'
                       f'font-weight:{A["vurgu"]}">{metin}</span>')
                _hucre.append(f'<td style="text-align:right;padding:{_pad}{_cizgi}">'
                              f'{_ic}</td>')
                continue

            _renk = R["kirmizi"] if _neg else R["metin"]
            # nowrap YALNIZ sayılarda. Metin kolonlarında da olunca marka/kategori
            # adları satırı genişletiyor ve yan yana iki tablo sığmıyordu.
            _ilk_mi = (k == kolonlar[0])
            _hucre.append(
                f'<td style="text-align:{"right" if sayi_mi else "left"};'
                f'padding:{_pad};font-size:{F["govde"]};'
                f'font-weight:{A["baslik"] if _toplam else A["govde"]};'
                f'color:{_renk};'
                + ("white-space:nowrap" if sayi_mi
                   # KELİME ORTASINDAN kırma (word-break:break-word) "FAZEO/N"
                   # gibi çirkin sonuç veriyordu. overflow-wrap yalnız SIĞMAYAN
                   # tek kelimeyi kırar; normal metin kelime aralarından sarar.
                   else "overflow-wrap:anywhere;word-break:normal")
                # Sağa kaydırınca ilk kolon (marka/kategori adı) yerinde kalır.
                # Zemin ŞART: saydam kalırsa altından kayan sayılar görünür.
                + (f';position:sticky;left:0;z-index:1;'
                   f'min-width:{_ilk_genislik}px;background:{_satir_zemin}'
                   if _ilk_mi else '')
                + f'{_cizgi}'
                + (f';font-family:{MONO};font-variant-numeric:tabular-nums'
                   if sayi_mi else "")
                + f'">{metin}</td>')
        _govde.append(f'<tr style="{_satir_stil}">' + "".join(_hucre) + "</tr>")

    # ── Sarmal ──
    # SARMALAYICI HER ZAMAN taşmayı kontrol etmeli. Hücrelerde nowrap var;
    # havadar/rozet stilinde çerçeve boş bırakıldığı için overflow kuralı da
    # yoktu ve geniş tablo st.columns kolonunu taşırıp YANINDAKİ TABLONUN
    # ÜSTÜNE biniyordu. max-width + overflow-x ile kendi kolonunda kaydırır.
    _cerceve = ("max-width:100%;overflow-x:auto" if _acik else
                f'max-width:100%;overflow-x:auto;border:1px solid {R["kenar"]};'
                f'border-radius:{YOGUNLUK["sik"]["kart_r"]}')
    _kaydir = f'max-height:{yukseklik}px;overflow-y:auto;' if yukseklik else ""
    return (f'<div style="{_kaydir}{_cerceve}">'
            f'<table style="width:100%;border-collapse:collapse;'
            + (f'background:{R["yuzey1"]}' if not _acik else "")
            + f'">'
            + f"<thead><tr>{_bas}</tr></thead><tbody>"
            + "".join(_govde) + "</tbody></table></div>")


# ═══════════════════════════════════════════════════════════════════
# 10. SIRALANABİLİR TABLO (components.html)
#     st.markdown JS çalıştırmıyor (Streamlit sanitize eder), o yüzden
#     başlığa tıklayıp sıralama için iframe şart.
#
#     BEDELİ: yükseklik sabit (satır sayısından hesaplanır) · CSV indirme
#     düğmesi yok · her satır DOM'a çizilir, bu yüzden UZUN listeler için
#     UYGUN DEĞİL — orada st.dataframe sanallaştırma yapıyor.
#     Bu fonksiyon KISA özet tabloları içindir (varsayılan sınır 150 satır).
# ═══════════════════════════════════════════════════════════════════

# CSS sınıflarına geçtikten sonra 3000 satır 903 KB / 36 ms — kabul edilebilir.
# Üstünde st.dataframe kalır: orada satırlar sanallaştırıldığı için DOM şişmez.
SIRALANABILIR_SINIR = 3000

# Her tabloya benzersiz kimlik: st.html iframe DEĞİL, sayfaya doğrudan yazıyor.
# Sabit id kullanılsa aynı sayfadaki tablolar birbirinin CSS'ini ve scriptini
# ezerdi. Bu sayaç her çizimde artar.
import itertools as _it
_TABLO_SAYAC = _it.count(1)


def tablo_sirali(satirlar, birim="$", stil="zebra", toplam_isaret="Σ",
                 satir_yuksekligi=None, maks_yukseklik=520, kap=None):
    """Başlığa tıklayınca sıralanan tablo (components.html · iframe).

    Sıralama tamamen tarayıcıda olur — Streamlit'e gidip gelmez, anlıktır.
    Toplam satırı (Σ) tfoot'ta durduğu için sıralamaya katılmaz.
    Sayısal kolonlar data-s'teki HAM değere göre sıralanır.

    BOYUT: stiller satır içi değil CSS SINIFI olarak yazılır. Satır içi
    yazıldığında 600 satır 704 KB oluyordu ve bu her çizimde tarayıcıya
    gidiyordu; sınıflarla ~10 kat küçülür, böylece uzun tablolar da mümkün.
    """
    import streamlit as _st
    _k = kap if kap is not None else _st
    if not satirlar:
        _k.markdown(bos(" Gösterilecek veri yok."), unsafe_allow_html=True)
        return
    R, F, A = RENK, FONT, AGIRLIK
    kolonlar = list(satirlar[0].keys())
    tipler = {k: _tablo_kolon_tipi(k) for k in kolonlar}
    _acik = stil in ("havadar", "rozet")
    _rozet = (stil == "rozet")
    _pad = "10px 12px" if _acik else "6px 11px"
    _sy = satir_yuksekligi or (38 if _acik else 30)

    _id = f"kt{next(_TABLO_SAYAC)}"
    _css = f"""<style>
#{_id}{{{'' if _acik else f'border:1px solid {R["kenar"]};border-radius:10px;'}max-width:100%;overflow:auto}}
#{_id} table{{width:100%;border-collapse:collapse{'' if _acik else f';background:{R["yuzey1"]}'}}}
#{_id} th{{font-size:{F["kucuk"]};font-weight:{A["vurgu"]};white-space:nowrap;
   position:sticky;top:0;z-index:1;cursor:pointer;user-select:none;
   {f'color:{R["silik"]};letter-spacing:.6px;text-transform:uppercase;padding:0 12px 8px;background:{R["yuzey0"]};border-bottom:1px solid {R["kenar2"]}'
     if _acik else
     f'color:{R["soluk"]};letter-spacing:.3px;padding:8px 11px;background:{R["yuzey2"]};border-bottom:1px solid {R["kenar2"]}'}}}
#{_id} th:hover{{color:{R["metin"]}}}
#{_id} td{{padding:{_pad};font-size:{F["govde"]};font-weight:{A["govde"]};
   color:{R["metin"]};overflow-wrap:anywhere;word-break:normal{f';border-bottom:1px solid {R["kenar"]}' if _acik else ''}}}
#{_id} td.n{{text-align:right;white-space:nowrap;font-family:{MONO};font-variant-numeric:tabular-nums}}
/* İlk kolon yatay kaydırmada sabit. Zemin ŞART — saydam kalırsa altından
   kayan sayılar görünür. Zebra/toplam satırları kendi zeminini ezer. */
#{_id} th:first-child{{position:sticky;left:0;z-index:3;min-width:130px;
   background:{R["yuzey2"] if not _acik else R["yuzey0"]}}}
#{_id} td:first-child{{position:sticky;left:0;z-index:1;min-width:130px;
   background:{R["yuzey1"] if not _acik else R["yuzey0"]}}}
{'' if _acik else f'#{_id} tbody tr:nth-child(even) td:first-child{{background:{R["yuzey2"]}}}'}
#{_id} tbody tr:hover td:first-child{{background:{R["yuzey3"]}}}
#{_id} tfoot td:first-child{{background:{R["yuzey2"] if not _acik else R["yuzey0"]}}}
#{_id} td.neg{{color:{R["kirmizi"]}}}
{'' if _acik else f'#{_id} tbody tr:nth-child(even){{background:{R["yuzey2"]}}}'}
#{_id} tbody tr:hover{{background:{R["yuzey3"]}}}
#{_id} tfoot td{{font-weight:{A["baslik"]};border-top:1px solid {R["kenar2"]}
   {'' if _acik else f';background:{R["yuzey2"]}'}}}
#{_id} .rz{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:{F["kucuk"]};
   font-family:{MONO};font-variant-numeric:tabular-nums;font-weight:{A["vurgu"]}}}
#{_id} .rp{{background:{R["yesil"]}22;color:{R["yesil"]}}}
#{_id} .rn{{background:{R["kirmizi"]}22;color:{R["kirmizi"]}}}
#{_id} .rt{{background:{R["mor"]}22;color:{R["mor"]}}}
#{_id} .ok{{opacity:.35;margin-left:5px}}
</style>"""

    def _hucre(v, t, toplam):
        if t == "para":
            metin, sayi = _tr_para(v, birim), True
        elif t == "adet":
            metin, sayi = _tr_adet(v), True
        elif t == "oran":
            metin, sayi = _tr_oran(v), True
        else:
            metin, sayi = ("" if v is None else str(v)), False
        try:
            ham = float(v) if sayi else None
        except (TypeError, ValueError):
            ham = None
        neg = bool(ham is not None and ham < 0)
        ds = f' data-s="{ham if ham is not None else metin}"'
        if _rozet and t == "oran" and metin:
            rc = "rt" if toplam else ("rn" if neg else "rp")
            return f'<td class="n"{ds}><span class="rz {rc}">{metin}</span></td>'
        sinif = ("n neg" if (sayi and neg) else ("n" if sayi else ""))
        return f'<td{f" class=\"{sinif}\"" if sinif else ""}{ds}>{metin}</td>'

    bas_html = "".join(
        f'<th data-k="{i}" style="text-align:{"right" if tipler[k] else "left"}'
        + (';min-width:110px' if i == 0 else '')
        + f'">{k}<span class="ok">↕</span></th>' for i, k in enumerate(kolonlar))

    govde, toplam_tr = [], ""
    for r in satirlar:
        toplam = str(r.get(kolonlar[0], "") or "").strip().startswith(toplam_isaret)
        tr = "<tr>" + "".join(_hucre(r.get(k), tipler[k], toplam) for k in kolonlar) + "</tr>"
        if toplam:
            toplam_tr = tr
        else:
            govde.append(tr)

    _yuk = min(maks_yukseklik, 46 + _sy * (len(satirlar) + 1) + 14)
    html = (_css
            + f'<div id="{_id}" style="max-height:{_yuk}px">'
            + f'<table><thead><tr>{bas_html}</tr></thead><tbody>'
            + "".join(govde)
            + f'</tbody>{"<tfoot>" + toplam_tr + "</tfoot>" if toplam_tr else ""}'
            + '</table></div>'
            '<script>(function(){'
            f'const t=document.querySelector("#{_id} table");if(!t)return;let y={{}};'
            't.querySelectorAll("th").forEach(h=>h.addEventListener("click",()=>{'
            ' const k=+h.dataset.k;y[k]=!y[k];const b=t.tBodies[0];'
            ' const r=[...b.rows];r.sort((p,q)=>{'
            '  const x=p.cells[k].dataset.s,z=q.cells[k].dataset.s;'
            '  const a=parseFloat(x),c=parseFloat(z);'
            '  const s=(!isNaN(a)&&!isNaN(c))?a-c:String(x).localeCompare(String(z),"tr");'
            '  return y[k]?s:-s;});'
            ' const f=document.createDocumentFragment();r.forEach(x=>f.appendChild(x));'
            ' b.appendChild(f);'
            ' t.querySelectorAll("th .ok").forEach(o=>{o.textContent="↕";o.style.opacity=".35"});'
            ' const o=h.querySelector(".ok");o.textContent=y[k]?"↑":"↓";o.style.opacity="1";'
            '}));'
            '})();</script>')
    # st.html: iframe DEĞİL, sayfaya doğrudan yazar → sabit yükseklik gerekmez,
    # iç içe kaydırma çubuğu olmaz. components.v1.html(height=...) ile KARIŞTIRMA:
    # st.html'in height parametresi YOKTUR, verilirse TypeError atar ve
    # çağıran taraftaki except onu yutup tabloyu sessizce native çizer.
    _k.html(html, unsafe_allow_javascript=True)
