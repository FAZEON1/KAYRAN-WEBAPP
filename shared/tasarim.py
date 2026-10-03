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
class TemaRenk(dict):
    """Tema duyarlı renk sözlüğü.

    RENK["metin"] → AKTİF temanın metin rengi (koyu: #E2E8F0, açık: #0F172A).
    Programda 150+ yerde RENK["x"] HTML'e ve Plotly'ye gömülüyor; sözlüğün
    kendisi temaya göre cevap verince hiçbirine dokunmak gerekmedi.
    .items()/.values() ise her zaman KOYU paleti verir (tema_degiskenleri
    ve testler ham paleti bekler)."""

    def __getitem__(self, k):
        if aktif_tema() == "acik" and k in RENK_ACIK:
            return RENK_ACIK[k]
        return dict.__getitem__(self, k)

    def get(self, k, varsayilan=None):
        return self[k] if k in self else varsayilan


def aktif_tema():
    """'koyu' | 'acik' — kullanıcının seçimi (session). Streamlit yoksa koyu."""
    try:
        import streamlit as st
        t = st.session_state.get("tema")
        return "acik" if t == "acik" else "koyu"
    except Exception:  # noqa: BLE001 — test ortamı / import zamanı
        return "koyu"


def renk(anahtar, varsayilan="mor"):
    """Aktif temanın rengi (hex). Python değeri gereken yerde — Plotly,
    {"renk": renk("yesil")} gibi. HTML içinde ise var(--k-anahtar) kullan."""
    k = anahtar if anahtar in RENK else varsayilan
    return RENK[k]


def karisim(anahtar, yuzde):
    """HTML/CSS için yarı saydam ton: 'color-mix(in srgb,var(--k-x) 15%,transparent)'."""
    return f"color-mix(in srgb,var(--k-{anahtar}) {int(yuzde)}%,transparent)"


RENK = TemaRenk({
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
})

# ═══════════════════════════════════════════════════════════════════
# 1b. TEMALAR — aynı anahtarlar, iki palet.
#     RENK = koyu tema (varsayılan, geriye uyumlu). Bileşenler renk kodunu
#     DEĞİL `var(--k-anahtar)` değişkenini kullanır; tema değişince yalnız
#     değişkenlerin değeri değişir, hiçbir bileşene dokunulmaz.
#     Açık paletteki her metin rengi beyaz kart üstünde WCAG AA (4.5) eşiğini,
#     anlam renkleri 3.0 eşiğini geçer — tests/test_tasarim_tema.py ölçer.
# ═══════════════════════════════════════════════════════════════════
RENK_ACIK = {
    "yuzey0":  "#F4F6FA",   # sayfa zemini (saf beyaz değil: göz yormasın)
    "yuzey1":  "#FFFFFF",   # kart
    "yuzey2":  "#F1F4F9",   # öne çıkan / hover
    "yuzey3":  "#E7ECF3",   # dialog, popover
    "kenar":   "rgba(15,23,42,0.09)",
    "kenar2":  "rgba(15,23,42,0.16)",
    "metin":   "#0F172A",
    "soluk":   "#475569",
    "silik":   "#5B6778",
    "mor":     "#4F46E5",  "mor2":     "#4338CA",
    "yesil":   "#047857",  "yesil2":   "#065F46",
    "kirmizi": "#DC2626",  "kirmizi2": "#B91C1C",
    "amber":   "#B45309",  "amber2":   "#92400E",
    "cyan":    "#0E7490",  "cyan2":    "#155E75",
    "mavi":    "#0369A1",
    "pembe":   "#BE185D",
}
# Yarı saydam katmanlar (satır zemini, vurgu dolgusu, gölge) tema başına
ORTU = {
    "koyu": {"ortu": "rgba(255,255,255,0.025)", "ortu2": "rgba(255,255,255,0.05)",
             "vurgu": "rgba(129,140,248,0.10)", "golge": "0 1px 2px rgba(0,0,0,.3)",
             "dolgu": "#6366F1", "dolgu-metin": "#FFFFFF"},
    "acik": {"ortu": "rgba(15,23,42,0.025)", "ortu2": "rgba(15,23,42,0.05)",
             "vurgu": "rgba(79,70,229,0.08)", "golge": "0 1px 3px rgba(15,23,42,.08)",
             "dolgu": "#4F46E5", "dolgu-metin": "#FFFFFF"},
}
TEMALAR = {"koyu": RENK, "acik": RENK_ACIK}


def rv(anahtar, varsayilan="mor"):
    """RENK anahtarı → 'var(--k-anahtar)'. Bileşenler hex yerine bunu kullanır,
    böylece iki temada da doğru renk çıkar. Bilinmeyen anahtar → varsayılan."""
    return f"var(--k-{anahtar if anahtar in RENK else varsayilan})"


def tema_degiskenleri(tema="koyu"):
    """'--k-metin:#E2E8F0;...' — :root ya da bir önizleme kapsayıcısına basılır."""
    palet = TEMALAR.get(tema, RENK)
    ek = ORTU.get(tema, ORTU["koyu"])
    return ("".join(f"--k-{k}:{v};" for k, v in palet.items())
            + "".join(f"--k-{k}:{v};" for k, v in ek.items()))


def _parlaklik(hex_renk):
    h = hex_renk.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def _f(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * _f(r) + 0.7152 * _f(g) + 0.0722 * _f(b)


def kontrast(on, arka):
    """WCAG kontrast oranı (1–21). 4.5 = normal metin eşiği, 3.0 = büyük metin/ikon."""
    a, b = sorted((_parlaklik(on), _parlaklik(arka)), reverse=True)
    return (a + 0.05) / (b + 0.05)


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

# ── Kategorik grafik paleti (pasta/halka/çubuk dilimleri) ──────────────
# Koyu zeminde birbirinden AYIRT EDİLEBİLİR 13 ton. Eskiden Muhasebe'de
# Çek=Kredi aynı kırmızı, SGK (#0891b2) ile İthalat (#0e7490) neredeyse aynı
# camgöbeğiydi; #1e40af / #92400e gibi koyu tonlar zeminde kayboluyordu.
GRAFIK_PALET = [
    "#818CF8",  # çivit
    "#34D399",  # yeşil
    "#FBBF24",  # amber
    "#F87171",  # kırmızı
    "#22D3EE",  # camgöbeği
    "#F472B6",  # pembe
    "#60A5FA",  # mavi
    "#FB923C",  # turuncu
    "#A3E635",  # limon
    "#C084FC",  # mor
    "#2DD4BF",  # turkuaz
    "#FDA4AF",  # gül
    "#94A3B8",  # gri (her zaman "Diğer" için)
]
# Grafik dilimi üstündeki yazı: açık dilimlerde koyu metin okunur.
GRAFIK_DILIM_METIN = "#0B1120"


# ── Menü ikon dili ──────────────────────────────────────────────────
# Sidebar menülerinde emoji yerine TEK ikon ailesi (Material Symbols).
# Menü DEĞERLERİ (emoji'li metin) aynen kalır; bu yalnız GÖRÜNÜMÜ çevirir,
# böylece `if sayfa == "📊 Dashboard"` gibi karşılaştırmalar bozulmaz.
EMOJI_IKON = {
    "📊": "dashboard", "📋": "list_alt", "📈": "trending_up", "🎯": "campaign",
    "📦": "inventory_2", "💵": "payments", "🔖": "tag", "📂": "upload_file",
    "💳": "credit_card", "🏦": "account_balance", "💰": "savings",
    "💸": "account_balance_wallet", "🕐": "history", "⏳": "hourglass_top",
    "🧾": "receipt_long", "📄": "description", "📚": "menu_book",
    "🏬": "warehouse", "🚚": "local_shipping", "🔎": "manage_search",
    "🔍": "search", "🏭": "factory", "📥": "move_to_inbox", "↩️": "undo",
    "↩": "undo", "➕": "add_circle", "🔧": "build", "🔑": "key",
    "👥": "group", "🏠": "home", "🚢": "directions_boat", "🛒": "shopping_cart",
    # Pencere / bölüm başlıklarında geçenler (ui.pencere, tasarim.kart, baslik)
    "🚨": "notification_important", "⚠": "warning", "💎": "diamond", "🛍": "shopping_bag",
    "🔔": "notifications", "🚀": "rocket_launch", "📉": "trending_down", "🧩": "extension",
    "🎨": "palette", "📤": "outbox", "🗓": "calendar_month", "📅": "calendar_month",
    "✅": "check_circle", "🔒": "lock", "🔗": "link", "🛠": "construction", "🧮": "calculate",
    "📢": "campaign", "📌": "push_pin", "💱": "currency_exchange", "🏢": "domain",
    "🔄": "sync", "📝": "edit_note", "🗂": "folder_open", "⏱": "timer", "🏷": "sell",
    # Mesaj, düğme, sekme ve pencere başlıklarında sık geçenler (shared/ikon.py, Ekim 2026)
    "❌": "cancel", "⛔": "block", "🚫": "block", "🗑": "delete", "✏": "edit", "💾": "save",
    "🔁": "repeat", "📜": "history_edu", "🧯": "bug_report", "ℹ": "info", "✔": "check",
    "🖨": "print", "📧": "mail", "📨": "mail", "👤": "person", "🆕": "fiber_new", "⬇": "download",
    "⬆": "upload", "💡": "lightbulb", "📍": "place", "🧹": "cleaning_services", "🧪": "science",
    "⚙": "settings", "🌐": "language", "📁": "folder", "📞": "call", "🎁": "redeem",
    "🔥": "local_fire_department", "⏭": "skip_next", "📆": "calendar_month", "💼": "work",
    "🏪": "store", "📱": "smartphone", "💻": "computer", "🖥": "desktop_windows", "🔐": "lock",
    "🔓": "lock_open", "📣": "campaign", "🛡": "shield", "🔙": "arrow_back", "💬": "chat",
    "⌛": "hourglass_bottom", "🔢": "pin", "🧭": "explore", "🎉": "celebration", "👁": "visibility",
}


# Menüde görünen İngilizce ad → Türkçe. DEĞER aynı kalır (kod "📊 Dashboard"
# ile karşılaştırmaya devam eder); yalnız ekranda Türkçe yazılır.
MENU_CEVIRI = {"Dashboard": "Genel Bakış"}


def emoji_ayir(metin):
    """'⚠️ YAKLAŞAN' → ('warning', 'YAKLAŞAN'). Baştaki emoji (değişken seçici
    U+FE0F ve birleştirici dahil) atılır; tanınırsa Material ikon adı döner,
    tanınmazsa None. Emoji yoksa (None, metin)."""
    s = str(metin or "").strip()
    i = 0
    while i < len(s) and not s[i].isalnum() and s[i] not in "(%$₺€#\"'«":
        i += 1
    if i == 0:
        return None, s
    bas = s[:i].replace("\ufe0f", "").replace("\u200d", "").strip()
    return EMOJI_IKON.get(bas) or EMOJI_IKON.get(bas[:1]), s[i:].strip()


# Büyük harfle yazılmış başlık/etiketlerde KORUNAN kısaltmalar
KISALTMA = {"SKU", "KDV", "USD", "EUR", "TL", "TRY", "P&L", "FOB", "CIF", "DIO", "PI",
            "SLA", "SGK", "KPI", "ID", "AB", "ABD", "PDF", "API", "B2B", "B2C", "E-DEFTER",
            "IBAN", "ÖTV", "GTİP", "ETA", "ETD", "CRM", "ERP", "ÜTS", "ÜY"}


def cumle_duzeni(metin):
    """TAMAMI BÜYÜK yazılmış etiketi Türkçe cümle düzenine çevirir:
    'BU AY NET KÂR' → 'Bu ay net kâr', 'TOPLAM AKTİF (USD)' → 'Toplam aktif (USD)',
    '30 GÜN İÇİNDE SİPARİŞ' → '30 gün içinde sipariş', "SKU'LAR" → "SKU'lar".
    Karışık yazılmış metne (zaten bilinçli yazılmış) dokunmaz. Kısaltmalar korunur.
    NEDEN: 10px, aralıklı BÜYÜK HARF etiketler her kartta bağırıyordu ve
    Türkçe'de I/İ sorunu çıkarıyordu; programın yeni dili cümle düzeni."""
    s = str(metin or "")
    harf = [c for c in s if c.isalpha()]
    if not harf or any(c.islower() for c in harf):
        return s

    def _kucuk(w):
        return w.replace("İ", "i").replace("I", "ı").lower()

    parcalar = []
    for w in s.split(" "):
        cekirdek = w.strip("()[]:,.·—-/")
        kok, ek = (cekirdek.split("'", 1) + [""])[:2] if "'" in cekirdek else (cekirdek, None)
        if kok.upper() in KISALTMA or (len(kok) <= 3 and any(ch.isdigit() for ch in kok)):
            if ek is None:
                parcalar.append(w)
            else:                                   # SKU'LAR → SKU'lar
                i = w.index("'")
                parcalar.append(w[:i + 1] + _kucuk(w[i + 1:]))
            continue
        parcalar.append(_kucuk(w))
    out = " ".join(parcalar)
    # İlk harf yalnız metin HARFLE başlıyorsa büyür ('30 gün…' rakamla başlar,
    # '(USD) …' parantezle — onlara dokunulmaz). Baştaki boşluk/tırnak atlanır.
    for j, c in enumerate(out):
        if c in " \"'«“":
            continue
        if c.isalpha():
            out = out[:j] + _tr_ust(c) + out[j + 1:]
        break
    return out


def _kart_etiket(k):
    """Kart etiketi: varsayılan cümle düzeni (kpi_etiketi). ozel_ad=True → OLDUĞU GİBİ:
    cari adı / marka gibi özel adlar ('D-MARKET' → 'D-market' olmasın). (Ekim 2026, Faz 4)"""
    e = k.get("etiket", "") if isinstance(k, dict) else k
    return str(e or "") if (isinstance(k, dict) and k.get("ozel_ad")) else kpi_etiketi(e)


def kpi_etiketi(metin):
    """KPI kartı etiketi: baştaki emoji atılır ('🔴 Acil Sipariş' → 'Acil Sipariş';
    kartın renkli sol çizgisi durumu zaten söylüyor), BÜYÜK HARF cümle düzenine iner."""
    _, govde = emoji_ayir(metin)
    return cumle_duzeni(govde)


def menu_etiketi(metin):
    """'📊  Dashboard' → ':material/dashboard: Genel Bakış'.
    st.radio(..., format_func=menu_etiketi) ile kullanılır. Tanınmayan emoji
    atılır (menüde yarı emoji yarı ikon karışımı olmasın)."""
    s = str(metin or "").strip()
    for emo in sorted(EMOJI_IKON, key=len, reverse=True):
        if s.startswith(emo):
            ad = s[len(emo):].strip()
            return f":material/{EMOJI_IKON[emo]}: {MENU_CEVIRI.get(ad, ad)}"
    # Tanınmayan emoji / sembol → at (harf ya da rakamla başlayana kadar)
    i = 0
    while i < len(s) and not (s[i].isalnum()):
        i += 1
    return s[i:] if i < len(s) else s


# ── Ürün etiketi: SKU her zaman görünür, ad CSS ile kısalır ─────────
def urun_etiketi(ad, sku="", renk=None, kalin=False):
    """Liste satırı için ürün etiketi (HTML).

    SKU sabit genişlikte başta durur ve ASLA kesilmez; ad kalan yere sığdığı
    kadar görünür, taşarsa '…' ile biter, tam adı fareyle üstüne gelince
    görünür. Eskiden ad Python'da 46 karakterde kesiliyordu: 'FAZEON F14 PLUS…'
    ile başlayan iki farklı ürün ekranda AYNI görünüyordu.

    Kapsayıcı satır `display:flex` olmalı; bu span `min-width:0` ile daralır."""
    import html as _h
    ad = str(ad or "").strip()
    sku = str(sku or "").strip()
    ad_e, sku_e = _h.escape(ad), _h.escape(sku)
    baslik = _h.escape(f"{sku} · {ad}" if sku else ad, quote=True)
    renk = renk or "var(--k-metin)"
    agirlik = AGIRLIK["vurgu"] if kalin else AGIRLIK["govde"]
    sku_html = (f'<span style="flex-shrink:0;font-family:{MONO};font-size:11px;'
                f'color:var(--k-mor2);background:var(--k-vurgu);'
                f'border:1px solid color-mix(in srgb,var(--k-mor) 30%,transparent);border-radius:5px;'
                f'padding:1px 6px;letter-spacing:0">{sku_e}</span>') if sku else ""
    return (f'<span title="{baslik}" style="display:flex;align-items:center;gap:8px;'
            f'min-width:0;flex:1 1 auto">{sku_html}'
            f'<span class="k-urun-ad" style="min-width:0;overflow:hidden;text-overflow:ellipsis;'
            f'white-space:nowrap;color:{renk};font-size:13px;font-weight:{agirlik}">'
            f'{ad_e}</span></span>')


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
  color:var(--k-metin) !important;line-height:1.3 !important;
  padding:0 !important;margin:14px 0 6px !important;}}

/* ── st.metric: ortak kart diline sokulur ── */
div[data-testid="stMetric"]{{
  background:var(--k-yuzey1) !important;border:1px solid var(--k-kenar) !important;
  border-left:2px solid var(--k-mor) !important;border-radius:{y['kart_r']} !important;
  padding:{y['kart_pad']} !important;}}
div[data-testid="stMetricLabel"],div[data-testid="stMetricLabel"] p,
div[data-testid="stMetricLabel"] div{{
  font-size:12px !important;color:var(--k-soluk) !important;
  font-weight:500 !important;letter-spacing:0 !important;
  text-transform:none !important;line-height:1.3 !important;
  white-space:normal !important;overflow:visible !important;}}
div[data-testid="stMetricValue"],div[data-testid="stMetricValue"] div{{
  font-size:{F['deger']} !important;color:var(--k-metin) !important;
  font-weight:{A['baslik']} !important;font-family:{MONO} !important;
  font-variant-numeric:tabular-nums !important;letter-spacing:{T['baslik']} !important;
  line-height:1.3 !important;}}
div[data-testid="stMetricDelta"]{{font-size:{F['kucuk']} !important;
  font-family:{MONO} !important;}}

/* ── Uyarı kutuları: 745 çağrı, hepsi tek dilde ── */
/* Çerçeve + zemin TEK katmanda: stAlertContainer (Streamlit zemini orada).
   Dış stAlert'e çerçeve verilirse "kutu içinde kutu" oluşur. */
div[data-testid="stAlert"]{{margin:6px 0 !important;padding:0 !important;
  border:0 !important;background:transparent !important;}}
div[data-testid="stAlertContainer"],div[data-testid="stNotification"]{{
  border-radius:{y['kart_r']} !important;padding:8px 13px !important;
  border:1px solid var(--k-kenar2) !important;border-left-width:2px !important;}}
/* Streamlit metnin altına -1rem koyar (paragraf boşluğunu telafi için);
   paragraf boşluğunu sıfırladığımızdan kutu 5px'e iniyor, metin taşıyordu. */
div[data-testid="stAlert"] [data-testid="stMarkdownContainer"]{{margin-bottom:0 !important;}}
div[data-testid="stAlert"] p,div[data-testid="stNotification"] p{{
  font-size:{F['govde']} !important;font-weight:{A['govde']} !important;
  line-height:1.55 !important;margin:0 !important;}}
div[data-testid="stAlert"] svg,div[data-testid="stNotification"] svg{{
  width:15px !important;height:15px !important;}}

/* ── Expander: 67 çağrı ── */
details[data-testid="stExpander"],div[data-testid="stExpander"] details{{
  border:1px solid var(--k-kenar) !important;border-radius:{y['kart_r']} !important;
  background:var(--k-yuzey1) !important;}}
div[data-testid="stExpander"] summary{{
  padding:7px 13px !important;font-size:{F['govde']} !important;
  font-weight:{A['vurgu']} !important;color:var(--k-soluk) !important;}}
div[data-testid="stExpander"] summary:hover{{color:var(--k-metin) !important;}}
div[data-testid="stExpander"] summary p{{
  font-size:{F['govde']} !important;font-weight:{A['vurgu']} !important;}}

/* ── Caption · ayraç · sekme ── */
div[data-testid="stCaptionContainer"] p,.stApp small{{
  font-size:{F['kucuk']} !important;color:var(--k-silik) !important;
  font-weight:{A['govde']} !important;line-height:1.5 !important;}}
.stApp hr,div[data-testid="stDivider"] hr{{
  border-color:var(--k-kenar) !important;margin:12px 0 !important;}}
button[data-baseweb="tab"]{{font-size:{F['govde']} !important;
  font-weight:{A['vurgu']} !important;border-radius:9px 9px 0 0 !important;}}
button[data-baseweb="tab"][aria-selected="true"]{{
  background:var(--k-vurgu) !important;color:var(--k-metin) !important;}}

/* ── Gövde metni: varsayılan 400. Program 931 kalın / 10 normal idi. ── */
.stApp [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stMarkdownContainer"] li{{
  font-size:{F['govde']} !important;font-weight:{A['govde']} !important;
  line-height:1.6 !important;}}
.stApp [data-testid="stMarkdownContainer"] strong{{
  font-weight:{A['vurgu']} !important;color:var(--k-metin) !important;}}
"""


# ═══════════════════════════════════════════════════════════════════
# 5. DÜĞME HİYERARŞİSİ — sayfa başına tek ANA düğme, gerisi sakin.
#    Eskiden sayfa içindeki her düğme aynı parlak mor dolguyla çiziliyordu;
#    "Kaydet" ile "Listeyi yenile" aynı ağırlıktaydı, göz nereye basacağını
#    bulamıyordu. Artık Streamlit'in kendi `type=` parametresi belirler:
#
#      type="primary"    → dolu renk      (sayfanın ASIL eylemi: Kaydet, Gönder)
#      type="secondary"  → kenarlı, sade  (varsayılan: Filtrele, Yenile, İndir)
#      type="tertiary"   → yalnız yazı    (Vazgeç, Temizle, küçük bağlantılar)
#      anahtarında "_sil" geçen düğme → KIRMIZI (silme / geri alınamaz işlem)
#
#    Seçiciler bilinçli olarak çok özgül: modüllerdeki eski düğme kuralları
#    (Ürün Yön. mavi degrade, ana sayfa mor degrade…) bunu ezemez.
#    Üst menü (.st-key-ustnav), sağ alttaki ✉️ talep düğmesi (.st-key-fab_talep)
#    ve sidebar kendi stilinde kalır.
# ═══════════════════════════════════════════════════════════════════
# NOT (Ekim 2026): '> button' yerine 'button[data-testid^="stBaseButton"]'.
# help= verilen düğmeyi Streamlit bir ipucu kabına (stTooltipIcon) sarar;
# '> button' ona ulaşmıyordu → ipuçlu düğmeler ortak stili ALMIYORDU (birincil
# düğme dolgusuz/soluk görünüyordu). Bu seçici bir kademe daha özgül; ona
# bağlı özel kurallar (tıklanır kart düğmesi, tarih okları) bundan SONRA ve en
# az bu özgüllükte yazılır (test_bilesen denetler).
_D = ('html body :is([data-testid="stMain"],[data-testid="stDialog"]) '
      ':is(.stButton,.stDownloadButton,.stFormSubmitButton):not(.st-key-ustnav *):not(.st-key-fab_talep *) '
      'button[data-testid^="stBaseButton"]')
_SIL = ('html body :is([data-testid="stMain"],[data-testid="stDialog"]) '
        '[class*="st-key-"][class*="_sil"]:not([class*="iptal"]):not([class*="vazgec"]) '
        ':is(.stButton,.stFormSubmitButton) button[data-testid^="stBaseButton"]')
DUGME_CSS = f"""
{_D}{{min-height:38px !important;height:auto !important;padding:0 16px !important;
  border-radius:9px !important;font-size:13px !important;font-weight:600 !important;
  letter-spacing:0 !important;box-shadow:none !important;transform:none !important;
  transition:background .15s ease,border-color .15s ease,color .15s ease,filter .15s ease !important;}}
{_D} p{{font-size:13px !important;font-weight:600 !important;color:inherit !important;}}
{_D}:is([data-testid="stBaseButton-secondary"],[data-testid="stBaseButton-secondaryFormSubmit"]){{
  background:transparent !important;border:1px solid var(--k-kenar2) !important;color:var(--k-metin) !important;}}
{_D}:is([data-testid="stBaseButton-secondary"],[data-testid="stBaseButton-secondaryFormSubmit"]):hover{{
  background:var(--k-vurgu) !important;border-color:var(--k-mor) !important;}}
{_D}:is([data-testid="stBaseButton-primary"],[data-testid="stBaseButton-primaryFormSubmit"]){{
  background:var(--k-dolgu) !important;border:1px solid var(--k-dolgu) !important;
  color:var(--k-dolgu-metin) !important;}}
{_D}:is([data-testid="stBaseButton-primary"],[data-testid="stBaseButton-primaryFormSubmit"]):hover{{
  filter:brightness(1.1) !important;}}
{_D}[data-testid="stBaseButton-tertiary"]{{background:transparent !important;border:1px solid transparent !important;
  color:var(--k-soluk) !important;padding:0 8px !important;}}
{_D}[data-testid="stBaseButton-tertiary"]:hover{{color:var(--k-metin) !important;background:var(--k-ortu2) !important;}}
{_D}:disabled{{opacity:.45 !important;filter:none !important;cursor:not-allowed !important;}}
{_SIL}:is([data-testid="stBaseButton-secondary"],[data-testid="stBaseButton-secondaryFormSubmit"],[data-testid="stBaseButton-tertiary"]){{
  color:var(--k-kirmizi) !important;border-color:color-mix(in srgb,var(--k-kirmizi) 45%,transparent) !important;}}
{_SIL}:is([data-testid="stBaseButton-secondary"],[data-testid="stBaseButton-secondaryFormSubmit"]):hover{{
  background:color-mix(in srgb,var(--k-kirmizi) 10%,transparent) !important;border-color:var(--k-kirmizi) !important;}}
{_SIL}:is([data-testid="stBaseButton-primary"],[data-testid="stBaseButton-primaryFormSubmit"]){{
  background:var(--k-kirmizi) !important;border-color:var(--k-kirmizi) !important;color:#FFFFFF !important;}}
/* Telefonda parmakla rahat basılsın: en az 44px (Apple/Google dokunma hedefi) */
@media (max-width:640px){{ {_D}{{min-height:44px !important;}} }}
"""

# ═══════════════════════════════════════════════════════════════════
# 6. ORTAK BİLEŞENLER (değişkenlerle — iki temada da çalışır)
# ═══════════════════════════════════════════════════════════════════
BILESEN_CSS = """
.k-bosd{display:flex;flex-direction:column;align-items:center;justify-content:center;
  text-align:center;gap:6px;padding:28px 16px;border:1px dashed var(--k-kenar2);
  border-radius:var(--k-r);background:var(--k-ortu);}
.k-bosd-ikon{font-family:"Material Symbols Rounded";font-size:28px;line-height:1;
  color:var(--k-silik);font-weight:normal;letter-spacing:normal;text-transform:none;}
.k-bosd-baslik{color:var(--k-metin);font-size:14px;font-weight:600;}
.k-bosd-aciklama{color:var(--k-soluk);font-size:12.5px;max-width:420px;line-height:1.5;}
.k-mesaj{display:flex;gap:10px;align-items:flex-start;padding:10px 14px;border-radius:10px;
  font-size:13px;line-height:1.5;color:var(--k-metin);
  background:color-mix(in srgb,var(--m) 9%,transparent);
  border:1px solid color-mix(in srgb,var(--m) 30%,transparent);border-left:3px solid var(--m);}
.k-mesaj-ikon{font-family:"Material Symbols Rounded";font-size:18px;line-height:1.2;color:var(--m);
  font-weight:normal;letter-spacing:normal;text-transform:none;flex-shrink:0;}
.k-tbw{max-width:100%;overflow:auto;border:1px solid var(--k-kenar);border-radius:var(--k-r);
  background:var(--k-yuzey1);}
.k-tb{width:100%;border-collapse:separate;border-spacing:0;font-size:13px;color:var(--k-metin);}
.k-tb thead th{position:sticky;top:0;z-index:2;background:var(--k-yuzey2);color:var(--k-soluk);
  font-size:12px;font-weight:600;letter-spacing:0;white-space:nowrap;
  padding:9px 12px;border-bottom:1px solid var(--k-kenar2);text-align:left;}
.k-tb tbody td{padding:7px 12px;border-bottom:1px solid var(--k-kenar);vertical-align:middle;
  line-height:1.4;word-break:normal;}
.k-tb tbody tr:nth-child(even) td{background:var(--k-ortu);}
.k-tb tbody tr:hover td{background:var(--k-ortu2);}
.k-tb tbody tr[data-vurgu] td{background:color-mix(in srgb,var(--v) 10%,transparent);}
.k-tb tbody tr[data-vurgu]:hover td{background:color-mix(in srgb,var(--v) 16%,transparent);}
.k-tb tbody tr:last-child td{border-bottom:0;}
.k-tb .sag{text-align:right;} .k-tb .orta{text-align:center;}
.k-tb .sayi{font-family:var(--k-mono);font-variant-numeric:tabular-nums;white-space:nowrap;}
.k-tb .neg{color:var(--k-kirmizi);} .k-tb .silik{color:var(--k-silik);}
.k-tb td.kisa{max-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.k-tb.sik thead th{padding:6px 8px;font-size:11.5px;}
.k-tb.sik tbody td{padding:5px 8px;font-size:11.5px;}
.k-tb.sik td.kisa{max-width:170px;}
.k-tb tfoot td{padding:8px 12px;font-weight:700;background:var(--k-yuzey2);
  border-top:2px solid var(--k-kenar2);position:sticky;bottom:0;}
.k-tb .k-rz{display:inline-block;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:700;
  letter-spacing:.2px;white-space:nowrap;background:color-mix(in srgb,var(--r) 12%,transparent);
  color:var(--r);border:1px solid color-mix(in srgb,var(--r) 30%,transparent);}
"""


def bos_durum(baslik, aciklama="", ikon="inbox"):
    """Boş liste / sonuç yok durumu. Kullanıcıya NE olduğunu ve varsa ne
    yapacağını söyler — tek başına 'Veri yok' yazmaz.
      st.markdown(bos_durum("Bekleyen sevk yok", "Yeni sevk 'Depolar Arası Sevk'ten açılır."), unsafe_allow_html=True)"""
    import html as _h
    ac = f'<div class="k-bosd-aciklama">{_h.escape(aciklama)}</div>' if aciklama else ""
    return (f'<div class="k-bosd"><span class="k-bosd-ikon" aria-hidden="true">{_h.escape(ikon)}</span>'
            f'<div class="k-bosd-baslik">{_h.escape(baslik)}</div>{ac}</div>')


_MESAJ = {"bilgi": ("cyan", "info"), "basari": ("yesil", "check_circle"),
          "uyari": ("amber", "warning"), "hata": ("kirmizi", "error")}


def mesaj(tur, metin):
    """Satır içi bilgi / başarı / uyarı / hata kutusu (HTML). tur: bilgi|basari|uyari|hata"""
    import html as _h
    renk, ikon = _MESAJ.get(tur, _MESAJ["bilgi"])
    return (f'<div class="k-mesaj" style="--m:var(--k-{renk})">'
            f'<span class="k-mesaj-ikon" aria-hidden="true">{ikon}</span>'
            f'<div>{_h.escape(metin)}</div></div>')


# ═══════════════════════════════════════════════════════════════════
# 7. MOBİL KATMAN — telefonda (≤640px) HER sayfa buna uyar.
#    Ekran ekran uğraşmak yerine ortak kurallar: dokunma hedefleri, iOS
#    yakınlaştırma sorunu, taşan tablolar, sıkışan ızgaralar, tam ekran
#    pencereler. Modüllerin kendi kodu değişmeden telefonda düzgün görünür.
# ═══════════════════════════════════════════════════════════════════
_MD = '[data-testid="stMarkdownContainer"]'
MOBIL_CSS = f"""
@media (max-width:640px){{
  /* Kenar boşluğu: ekranın her pikseli değerli. Altta ✉️ düğmesi için yer. */
  .stApp [data-testid="stMainBlockContainer"], .stApp .block-container{{
    padding-left:10px !important;padding-right:10px !important;padding-bottom:96px !important;}}

  /* iOS, 16px'ten küçük yazılı kutuya dokununca sayfayı YAKINLAŞTIRIR ve
     geri uzaklaştırmaz. Bütün giriş kutuları 16px. */
  input, textarea, select, [data-baseweb="select"] *{{font-size:16px !important;}}

  /* Dokunma hedefleri: en az 44px (parmak ucu ~ 1cm) */
  [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
  [data-testid="stDateInput"] input, [data-testid="stTimeInput"] input{{min-height:44px !important;}}
  [data-baseweb="select"] > div{{min-height:44px !important;}}
  [data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"]{{
    min-width:44px !important;min-height:44px !important;}}
  [data-testid="stCheckbox"] label, [data-testid="stToggle"] label,
  [data-testid="stMain"] :is([role="radiogroup"] > label,[data-testid="stRadioOption"]){{min-height:40px !important;align-items:center !important;}}
  [data-testid="stExpander"] summary{{min-height:48px !important;align-items:center !important;}}
  html body section[data-testid="stSidebar"] :is([role="radiogroup"] > label,[data-testid="stRadioOption"]){{min-height:42px !important;align-items:center !important;}}

  /* Sekmeler: sığmazsa yana kaysın, sekme yüksekliği parmağa uygun */
  [data-baseweb="tab-list"]{{overflow-x:auto !important;scrollbar-width:none;flex-wrap:nowrap !important;}}
  [data-baseweb="tab-list"]::-webkit-scrollbar{{display:none;}}
  button[data-baseweb="tab"]{{min-height:44px !important;padding:0 12px !important;flex-shrink:0 !important;}}

  /* Düğmeler telefonda tam genişlik: sütunlar alt alta dizildiğinde "Kaydet"
     küçük bir ada gibi kalmasın, başparmakla her yerden basılabilsin.
     (Üst menü, ✉️ ve Bugün paneli kendi düzeninde kalır.) */
  /* Form düğmesinde kapsayıcı ile düğme arasında bir ara katman daha var
     (stElementContainer > div > .stFormSubmitButton) — ikisi de genişlemeli. */
  :is([data-testid="stMain"],[data-testid="stDialog"]) [data-testid="stElementContainer"]:has(> :is(.stButton,.stDownloadButton,.stFormSubmitButton), > div > .stFormSubmitButton):not(.st-key-ustnav *):not(.st-key-fab_talep):not(.st-key-bugun_panel *),
  :is([data-testid="stMain"],[data-testid="stDialog"]) [data-testid="stElementContainer"]:has(> div > .stFormSubmitButton) > div{{
    width:100% !important;}}
  :is([data-testid="stMain"],[data-testid="stDialog"]) :is(.stButton,.stDownloadButton,.stFormSubmitButton):not(.st-key-ustnav *):not(.st-key-fab_talep *):not(.st-key-bugun_panel *){{
    width:100% !important;}}
  :is([data-testid="stMain"],[data-testid="stDialog"]) :is(.stButton,.stDownloadButton,.stFormSubmitButton):not(.st-key-ustnav *):not(.st-key-fab_talep *):not(.st-key-bugun_panel *) button[data-testid^="stBaseButton"]{{
    width:100% !important;}}

  /* Elle yazılmış HTML tablolar: ekranı taşırmasın, kendi içinde yana kaysın.
     Hücre bölünmesin (3 satıra kırılan "FAZEON / F14 / PLUS" yerine tek satır),
     aralık daralsın: telefonda bir satır = bir kayıt, yana kaydırarak okunur. */
  {_MD} table{{display:block !important;max-width:100% !important;overflow-x:auto !important;
    -webkit-overflow-scrolling:touch;}}
  {_MD} table :is(td,th){{white-space:nowrap !important;padding:6px 10px !important;font-size:12.5px !important;}}
  {_MD} :is(img,svg,video,pre){{max-width:100% !important;height:auto;}}

  /* Sabit 3-6 sütunlu ızgaralar telefonda 2 sütuna iner (rakamlar okunur kalır) */
  {_MD} :is([style*="grid-template-columns:repeat(3"],[style*="grid-template-columns:repeat(4"],
    [style*="grid-template-columns:repeat(5"],[style*="grid-template-columns:repeat(6"],
    [style*="grid-template-columns: repeat(3"],[style*="grid-template-columns: repeat(4"]){{
    grid-template-columns:repeat(2,minmax(0,1fr)) !important;}}

  /* Kısalan metin telefonda "üstüne gel" ile açılamaz (fare yok): ürün adı ve
     Bugün satırı ayrıntısı kesilmek yerine en fazla 2 satıra sarar. */
  .k-urun-ad, .bgn-detay{{white-space:normal !important;display:-webkit-box !important;
    -webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden !important;}}

  [data-testid="stMetricValue"]{{font-size:1.05rem !important;}}
  [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p{{font-size:.72rem !important;}}
  .stApp h1{{font-size:1.3rem !important;}} .stApp h2{{font-size:1.12rem !important;}}
  .stApp h3{{font-size:1rem !important;}}
}}
"""


# ═══════════════════════════════════════════════════════════════════
# 7b. KİŞİ ADI — Türkçe büyük harf. 'ibrahim'.capitalize() → 'Ibrahim'
#     (noktasız I) çıkıyordu; selamlamada ve sol menüde her gün görünüyordu.
#     YALNIZ GÖSTERİM içindir: veri anahtarı olarak kullanılan yerlerde
#     (talep sorgusu, bildirim alıcısı) eski biçim korunur.
# ═══════════════════════════════════════════════════════════════════
def _tr_ust(c):
    return {"i": "İ", "ı": "I"}.get(c, c.upper())


def kisi_adi(kullanici):
    """'ibrahim' → 'İbrahim', 'ayşe nur' → 'Ayşe Nur', 'IŞIL' → 'Işıl'."""
    s = str(kullanici or "").strip()
    if not s:
        return ""
    kucuk = s.replace("İ", "i").replace("I", "ı").lower()
    return " ".join((_tr_ust(w[0]) + w[1:]) if w else w for w in kucuk.split(" "))


def bas_harf(kullanici):
    """Avatar harfi: 'ibrahim' → 'İ' (eskiden 'I')."""
    s = str(kullanici or "").strip()
    return _tr_ust(s[0].replace("İ", "i").replace("I", "ı").lower()) if s else "?"


# ── Modül → menü ikonu (Material Symbols). Üst menü, sol menü çipi ve ana
#    sayfa kartları AYNI ikonu kullanır; emoji yalnız eski verilerde kalır. ──
MODUL_IKON = {
    "anasayfa": "home", "arama": "search", "yonetim": "monitoring",
    "kayranacc": "account_balance_wallet", "ithalat": "directions_boat",
    "kayranpm": "inventory_2", "depo": "warehouse", "satis": "point_of_sale",
    "teknikservis": "construction", "hesap_makinesi": "calculate",
}


def ikon(ad, boyut=18, renk=None):
    """Satır içi Material Symbols ikonu (HTML). Streamlit bu yazı tipini zaten
    yüklüyor (:material/..: ikonları için); ek indirme yok."""
    import html as _h
    stil = f"font-size:{int(boyut)}px;" + (f"color:{renk};" if renk else "")
    return (f'<span class="k-ikon" aria-hidden="true" style="{stil}">'
            f'{_h.escape(str(ad))}</span>')


ikon_html = ikon   # başlık/kart içinde 'ikon' adlı yerel değişkenle çakışmasın


# ═══════════════════════════════════════════════════════════════════
# 7c. SOL MENÜ KABUĞU + MENÜ SEÇENEKLERİ (tek kaynak)
#
#   NEDEN BURADA: Streamlit 1.64 radyo düğmesinin iç yapısını değiştirdi
#   (her seçenek artık bir kabın içinde: radiogroup > div > label). Eski
#   kurallar 'radiogroup > label' aradığı için HİÇBİRİ tutmuyordu: sol
#   menülerde form gibi yuvarlak seçim düğmeleri çıkıyor, seçili sayfa öne
#   çıkmıyordu. Seçiciler artık İKİ yapıyı da tanır (eski: > label, yeni:
#   [data-testid=stRadioOption]); test_radyo_secici bunu denetler.
#
#   Ayrıca her modül sol menüye kendi rengini basıyordu (Satış'ta her yazı
#   mavi, Muhasebe'de beyaz; çıkış düğmesi üç ayrı biçimde). Buradaki
#   kurallar 'html body' ile güçlendirildi: modül kuralları bunları ezemez,
#   böylece her modülde sol menü AYNI görünür.
# ═══════════════════════════════════════════════════════════════════
_SB = 'html body section[data-testid="stSidebar"]'
# Radyo seçeneği: eski yapı (> label) + 1.64 yapısı (stRadioOption)
_OPT = ':is([data-testid="stRadio"] [role="radiogroup"] > label,[data-testid="stRadioOption"])'
# Seçenek önündeki yuvarlak: eskide label'ın ilk div'i, 1.64'te iç kabın ilk div'i
_DAIRE = (':is([data-testid="stRadio"] [role="radiogroup"] > label > div:first-child,'
          '[data-testid="stRadioOption"] > div > div:first-child:not([data-testid]))')

SIDEBAR_CSS = f"""
{_SB}{{background:var(--k-yuzey1) !important;border-right:1px solid var(--k-kenar) !important;}}
{_SB} hr{{border-color:var(--k-kenar) !important;margin:12px 0 !important;}}
.k-ikon,{_SB} .k-ikon{{font-family:"Material Symbols Rounded" !important;font-weight:normal;font-style:normal;line-height:1;
  letter-spacing:normal;text-transform:none;display:inline-block;white-space:nowrap;
  font-feature-settings:"liga";-webkit-font-smoothing:antialiased;vertical-align:middle;}}

/* ── Marka ── */
{_SB} .k-sb-marka{{display:flex;align-items:center;gap:10px;padding:2px 2px 14px;}}
{_SB} .k-sb-marka svg{{width:28px;height:28px;flex-shrink:0;}}
{_SB} .k-sb-marka b{{font-size:15px;font-weight:700;letter-spacing:1.4px;color:var(--k-metin) !important;line-height:1;}}
{_SB} .k-sb-marka span{{font-size:11px;font-weight:500;color:var(--k-silik) !important;line-height:1;}}

/* ── Modül çipi: renkli ikon karosu + ad ── */
{_SB} .k-sb-modul{{display:flex;align-items:center;gap:10px;padding:0 2px 12px;margin-bottom:10px;
  border-bottom:1px solid var(--k-kenar);}}
{_SB} .k-sb-modul i{{width:30px;height:30px;border-radius:8px;flex-shrink:0;display:flex;align-items:center;
  justify-content:center;font-style:normal;background:color-mix(in srgb,var(--c) 16%,transparent);
  box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--c) 28%,transparent);font-size:14px;}}
{_SB} .k-sb-modul i .k-ikon{{color:var(--c) !important;font-size:18px;}}
{_SB} .k-sb-modul b{{font-size:14px;font-weight:650;letter-spacing:-.1px;color:var(--k-metin) !important;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}

/* ── Kişi satırı: avatar + ad (çıkış düğmesi yanında) ── */
{_SB} .k-sb-kisi{{display:flex;align-items:center;gap:9px;min-width:0;}}
{_SB} .k-sb-kisi i{{width:28px;height:28px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;
  justify-content:center;font-style:normal;font-size:13px;font-weight:700;
  background:color-mix(in srgb,var(--k-mor) 20%,var(--k-yuzey1));color:var(--k-mor2) !important;
  box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--k-mor) 35%,transparent);}}
{_SB} .k-sb-kisi b{{font-size:13px;font-weight:600;color:var(--k-metin) !important;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;}}
{_SB} .k-sb-kisi small{{display:block;font-size:11px;color:var(--k-silik) !important;font-weight:400;line-height:1.3;}}
{_SB} .k-sb-baslik{{font-size:11px;font-weight:600;color:var(--k-silik) !important;margin:14px 2px 6px;}}

/* ── Sol menüdeki sıradan düğmeler: sakin, kenarlı (Güncel Kur, Yenile…) ── */
{_SB} :is(.stButton,.stDownloadButton) > button{{min-height:34px !important;border-radius:8px !important;
  background:transparent !important;border:1px solid var(--k-kenar2) !important;color:var(--k-metin) !important;
  font-size:13px !important;font-weight:500 !important;box-shadow:none !important;transform:none !important;
  padding:0 12px !important;transition:background .12s ease,border-color .12s ease !important;}}
{_SB} :is(.stButton,.stDownloadButton) > button:hover{{background:var(--k-ortu2) !important;border-color:var(--k-mor) !important;}}
{_SB} :is(.stButton,.stDownloadButton) > button p{{font-size:13px !important;font-weight:500 !important;color:inherit !important;}}

/* ── Gezinme düğmeleri (ana sayfa sol menüsü: Şifremi Değiştir, Kullanıcı
      Yönetimi…) radyo menüsüyle AYNI görünür ── */
{_SB} [class*="st-key-nav_"]:not(.st-key-nav_cikis) .stButton > button{{
  border:0 !important;justify-content:flex-start !important;color:var(--k-soluk) !important;
  padding:0 10px !important;font-weight:500 !important;}}
{_SB} [class*="st-key-nav_"]:not(.st-key-nav_cikis) .stButton > button > div{{justify-content:flex-start !important;}}
{_SB} [class*="st-key-nav_"]:not(.st-key-nav_cikis) .stButton > button [data-testid="stIconMaterial"]{{
  color:var(--k-silik) !important;font-size:18px !important;}}
{_SB} [class*="st-key-nav_"] .stButton > button:hover{{background:var(--k-ortu2) !important;color:var(--k-metin) !important;}}
{_SB} [class*="st-key-nav_"] .stButton > button[data-testid="stBaseButton-primary"]{{
  background:color-mix(in srgb,var(--k-mor) 13%,transparent) !important;color:var(--k-metin) !important;font-weight:600 !important;}}
{_SB} [class*="st-key-nav_"] .stButton > button[data-testid="stBaseButton-primary"] [data-testid="stIconMaterial"]{{color:var(--k-mor) !important;}}

/* ── Çıkış: kişi satırının yanında küçük, sessiz düğme ── */
{_SB} :is([class*="st-key-cikis_"],.st-key-nav_cikis) .stButton > button{{border-color:transparent !important;
  color:var(--k-silik) !important;padding:0 8px !important;min-height:30px !important;}}
{_SB} :is([class*="st-key-cikis_"],.st-key-nav_cikis) .stButton > button:hover{{
  color:var(--k-kirmizi) !important;border-color:color-mix(in srgb,var(--k-kirmizi) 35%,transparent) !important;
  background:color-mix(in srgb,var(--k-kirmizi) 8%,transparent) !important;}}
{_SB} [data-testid="stHorizontalBlock"]:has(.k-sb-kisi){{align-items:center !important;gap:6px !important;
  flex-direction:row !important;flex-wrap:nowrap !important;}}
{_SB} [data-testid="stHorizontalBlock"]:has(.k-sb-kisi) [data-testid="stMarkdownContainer"]{{margin-bottom:0 !important;}}
{_SB} [data-testid="stHorizontalBlock"]:has(.k-sb-kisi) > [data-testid="stColumn"]:first-child{{
  flex:1 1 auto !important;width:auto !important;min-width:0 !important;}}
{_SB} [data-testid="stHorizontalBlock"]:has(.k-sb-kisi) > [data-testid="stColumn"]:last-child{{
  flex:0 0 auto !important;width:auto !important;min-width:0 !important;}}

/* ── Sol menü sayfa listesi (radyo) → gezinme menüsü ── */
{_SB} [data-testid="stElementContainer"]:has(> [data-testid="stRadio"]),
{_SB} [data-testid="stRadio"],{_SB} [data-testid="stRadio"] [role="radiogroup"]{{width:100% !important;}}
{_SB} [data-testid="stRadio"] [role="radiogroup"]{{display:flex !important;flex-direction:column !important;gap:1px !important;}}
{_SB} [data-testid="stRadio"] [role="radiogroup"] > div{{width:100% !important;}}
{_SB} {_OPT}{{position:relative;display:flex !important;align-items:center !important;width:100% !important;
  box-sizing:border-box !important;min-height:34px;margin:0 !important;padding:6px 10px 6px 12px !important;
  border-radius:8px !important;background:transparent !important;border:0 !important;cursor:pointer;
  transition:background .12s ease;}}
{_SB} {_DAIRE}{{display:none !important;}}
{_SB} {_OPT} p{{display:flex !important;align-items:center;gap:10px;margin:0 !important;font-size:13px !important;
  font-weight:500 !important;letter-spacing:0 !important;line-height:1.3 !important;color:var(--k-soluk) !important;}}
{_SB} {_OPT} p [role="img"]{{font-size:18px !important;color:var(--k-silik) !important;width:18px;flex-shrink:0;}}
{_SB} {_OPT}:hover{{background:var(--k-ortu2) !important;}}
{_SB} {_OPT}:hover p{{color:var(--k-metin) !important;}}
{_SB} {_OPT}:has(input:checked){{background:color-mix(in srgb,var(--k-mor) 13%,transparent) !important;}}
{_SB} {_OPT}:has(input:checked)::before{{content:"";position:absolute;left:0;top:8px;bottom:8px;width:3px;
  border-radius:0 3px 3px 0;background:var(--k-mor);}}
{_SB} {_OPT}:has(input:checked) p{{color:var(--k-metin) !important;font-weight:600 !important;}}
{_SB} {_OPT}:has(input:checked) p [role="img"]{{color:var(--k-mor) !important;}}
{_SB} {_OPT}:has(input:focus-visible){{outline:2px solid var(--k-mor);outline-offset:-2px;}}

/* ── Sayfa içi radyolar (Dönem, Filtre…) → hap düğmeler ── */
section[data-testid="stMain"] [data-testid="stRadio"] [role="radiogroup"]{{gap:6px !important;align-items:center;flex-wrap:wrap;}}
section[data-testid="stMain"] {_OPT}{{display:flex !important;align-items:center !important;margin:0 !important;
  min-height:32px;padding:4px 14px !important;border-radius:8px !important;cursor:pointer;
  background:transparent !important;border:1px solid var(--k-kenar2) !important;
  transition:background .12s ease,border-color .12s ease;}}
section[data-testid="stMain"] {_DAIRE}{{display:none !important;}}
section[data-testid="stMain"] {_OPT} p{{margin:0 !important;font-size:13px !important;font-weight:500 !important;
  color:var(--k-soluk) !important;}}
section[data-testid="stMain"] {_OPT}:hover{{background:var(--k-ortu2) !important;border-color:var(--k-mor) !important;}}
section[data-testid="stMain"] {_OPT}:has(input:checked){{background:var(--k-vurgu) !important;
  border-color:color-mix(in srgb,var(--k-mor) 60%,transparent) !important;}}
section[data-testid="stMain"] {_OPT}:has(input:checked) p{{color:var(--k-metin) !important;font-weight:600 !important;}}
section[data-testid="stMain"] {_OPT}:has(input:focus-visible){{outline:2px solid var(--k-mor);outline-offset:1px;}}
"""


# ═══════════════════════════════════════════════════════════════════
# 7d. ORTAK BİLEŞEN STİLLERİ — shared/bilesen.py ile birlikte çalışır
#     tiklanir() kapları (kart · satir · ray), k-grup, k-cip, k-meta.
#     Kampanya Takip ve Ref No'da ayrı ayrı yazılmıştı; tek kaynak burası.
# ═══════════════════════════════════════════════════════════════════
_TK = '[class*="st-key-tk_"]'
_TKA = ':is([data-testid="stMain"],[data-testid="stDialog"])'
ORTAK_BILESEN_CSS = f"""
{_TK}{{position:relative;gap:0 !important;}}
{_TK} [data-testid="stMarkdownContainer"]{{margin-bottom:0 !important;}}
{_TK} > [data-testid="stElementContainer"]:has(.stButton){{position:absolute !important;inset:0 !important;
  margin:0 !important;z-index:3;width:auto !important;height:auto !important;}}
html body {_TK} .stButton{{width:100% !important;height:100% !important;}}
html body {_TKA} {_TK} [data-testid="stButton"].stButton > button[data-testid]{{width:100% !important;
  height:100% !important;min-height:100% !important;opacity:0 !important;border:0 !important;padding:0 !important;}}
{_TK}:has(button:focus-visible){{outline:2px solid var(--k-mor);outline-offset:2px;}}
[class*="st-key-tk_kart_"]{{padding:14px 16px 13px !important;border-radius:12px !important;
  background:var(--k-yuzey1) !important;border:1px solid var(--k-kenar) !important;
  border-left:3px solid var(--d,var(--k-kenar2)) !important;transition:border-color .15s ease,background-color .15s ease;}}
[class*="st-key-tk_kart_"]:hover{{background:color-mix(in srgb,var(--d,var(--k-mor)) 4%,var(--k-yuzey1)) !important;
  border-color:color-mix(in srgb,var(--d,var(--k-mor)) 45%,transparent) !important;border-left-color:var(--d,var(--k-mor)) !important;}}
[class*="st-key-tk_satir_"]{{padding:9px 14px !important;border-radius:10px;background:var(--k-yuzey1);
  border:1px solid var(--k-kenar);border-left:3px solid var(--d,var(--k-kenar2));margin-bottom:-6px;
  transition:background .12s ease,border-color .12s ease;}}
[class*="st-key-tk_satir_"]:hover{{background:color-mix(in srgb,var(--d,var(--k-mor)) 5%,var(--k-yuzey1));
  border-color:color-mix(in srgb,var(--d,var(--k-mor)) 40%,transparent);border-left-color:var(--d,var(--k-mor));}}
[class*="st-key-tk_ray_"]{{border-radius:9px;padding:8px 10px !important;transition:background .12s ease;}}
[class*="st-key-tk_ray_"]:hover{{background:var(--k-ortu2);}}
[class*="st-key-tk_ray_"][class*="__sec"]{{background:color-mix(in srgb,var(--k-mor) 13%,transparent) !important;}}
[class*="st-key-tk_ray_"][class*="__sec"]::before{{content:"";position:absolute;left:0;top:9px;bottom:9px;width:3px;
  border-radius:0 3px 3px 0;background:var(--k-mor);}}
.k-grup{{display:flex;align-items:baseline;gap:10px;margin:18px 2px 6px;}}
.k-grup b{{font-size:14px;font-weight:650;color:var(--k-metin);}}
.k-grup span{{font-size:12px;color:var(--k-silik);}}
.k-grup i{{flex:1;height:1px;background:var(--k-kenar);font-style:normal;align-self:center;}}
.k-cip{{display:inline-block;flex-shrink:0;font-size:11px;font-weight:600;line-height:1;padding:4px 8px;
  border-radius:999px;white-space:nowrap;color:var(--d);background:color-mix(in srgb,var(--d) 13%,transparent);}}
.k-meta{{display:flex;gap:6px;flex-wrap:wrap;align-items:center;font-size:12px;color:var(--k-silik);}}
.k-meta > span:not(.k-cip) + span:not(.k-cip)::before{{content:"·";margin-right:6px;}}
"""


def sidebar_modul_html(ikon_adi, ad, renk="mor2"):
    """Sol menü üstündeki modül çipi. ikon_adi Material adı ('point_of_sale')
    ya da eski çağrılardan gelen emoji olabilir."""
    import html as _h
    ic = str(ikon_adi or "")
    ic_html = ikon(ic) if ic.replace("_", "").isalnum() and ic.isascii() else _h.escape(ic)
    return (f'<div class="k-sb-modul" style="--c:{rv(renk)}"><i>{ic_html}</i>'
            f'<b>{_h.escape(str(ad))}</b></div>')


def sidebar_kisi_html(kullanici, alt=""):
    """Avatar + Türkçe doğru büyük harfli ad."""
    import html as _h
    a = f"<small>{_h.escape(alt)}</small>" if alt else ""
    return (f'<div class="k-sb-kisi"><i>{_h.escape(bas_harf(kullanici))}</i>'
            f'<div style="min-width:0"><b>{_h.escape(kisi_adi(kullanici))}</b>{a}</div></div>')


def cekirdek_css(yogunluk=None):
    R, F = RENK, FONT
    kp, kr, gg, sa, sp, kmin = (_y("kart_pad", yogunluk), _y("kart_r", yogunluk),
                                _y("grid_gap", yogunluk), _y("serit_alt", yogunluk),
                                _y("satir_pad", yogunluk), _y("kart_min", yogunluk))
    degiskenler = tema_degiskenleri(aktif_tema())
    acik = tema_degiskenleri('acik')
    return "<style>" + css_tek_satir(f"""
:root{{{degiskenler}--k-r:{kr};--k-gap:{gg};--k-pad:{kp};--k-mono:{MONO};}}
/* Bu sınıfı taşıyan kapsayıcı AÇIK paleti kullanır (Tasarım Rehberi önizlemesi;
   ileride kullanıcı tema seçimi de aynı değişkenlerle çalışır). */
.k-tema-acik{{{acik}color:var(--k-metin);}}
""" + DUGME_CSS + BILESEN_CSS + SIDEBAR_CSS + ORTAK_BILESEN_CSS + MOBIL_CSS + f"""

.k-grid{{display:flex;gap:var(--k-gap);flex-wrap:wrap;align-items:stretch;margin:0 0 {sa};}}

.k-kart{{flex:1;min-width:{kmin};background:var(--k-yuzey1);
  border:1px solid var(--k-kenar);border-radius:var(--k-r);padding:var(--k-pad);
  display:flex;flex-direction:column;
  transition:background .12s ease,border-color .12s ease;}}
.k-kart:hover{{background:var(--k-yuzey2);border-color:var(--k-kenar2);}}
.k-kart[data-akscent]{{border-left-width:2px;border-radius:var(--k-r);}}

.k-etiket{{font-size:12px;color:var(--k-soluk);
  font-weight:500;letter-spacing:0;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;line-height:1.2;}}
.k-deger{{font-size:{F['deger']};color:var(--k-metin);font-weight:{AGIRLIK['baslik']};
  font-family:var(--k-mono);font-variant-numeric:tabular-nums;
  letter-spacing:{TRACKING['baslik']};margin-top:2px;line-height:1.25;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.k-alt{{font-size:{F['kucuk']};color:var(--k-silik);margin-top:2px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}

/* ── Yan panel: yan_panel() işaretli pencere sağdan tam boy (liste arkada görünür) ── */
[data-testid="stDialog"]:has(.k-panel) [role="dialog"]{{position:fixed !important;top:0 !important;right:0 !important;
  left:auto !important;bottom:0 !important;margin:0 !important;height:100vh !important;height:100dvh !important;
  max-height:100dvh !important;width:min(680px,100vw) !important;max-width:100vw !important;border-radius:0 !important;
  overflow:auto !important;border-left:1px solid var(--k-kenar2) !important;background:var(--k-yuzey1) !important;
  box-shadow:-16px 0 40px rgba(0,0,0,.35) !important;animation:k-panel-gir .18s ease-out;}}
[data-testid="stDialog"]:has(.k-panel-orta) [role="dialog"]{{width:min(680px,100vw) !important;}}
[data-testid="stDialog"]:has(.k-panel-dar) [role="dialog"]{{width:min(520px,100vw) !important;}}
[data-testid="stDialog"]:has(.k-panel-genis) [role="dialog"]{{width:min(860px,100vw) !important;}}
@keyframes k-panel-gir{{from{{transform:translateX(28px);opacity:.5}}to{{transform:none;opacity:1}}}}

/* ── Yeni kartlar (KART_YENI): nötr değer, renk yalnız anlam ── */
.k-kart.k-yeni{{border-left-width:1px;}}
.k-yeni .k-deger-satir{{display:flex;align-items:baseline;gap:8px;min-width:0;margin-top:2px;}}
.k-yeni .k-deger{{font-family:inherit;color:var(--k-metin);font-weight:600;margin-top:0;min-width:0;}}
.k-yeni.k-kotu .k-deger{{color:var(--k-kirmizi);}}
.k-yeni.k-iyi .k-deger{{color:var(--k-yesil);}}
.k-yeni.k-dikkat .k-deger{{color:var(--k-amber);}}
.k-yeni .k-alt{{white-space:normal;overflow:visible;line-height:1.35;}}
.k-kart.k-vurgu{{flex:1.7;}}
.k-vurgu .k-deger{{font-size:28px;letter-spacing:-0.5px;line-height:1.15;}}
.k-rozet{{flex:0 0 auto;font-size:11.5px;font-weight:600;padding:1px 7px;border-radius:999px;white-space:nowrap;
  background:var(--k-ortu2);color:var(--k-soluk);font-variant-numeric:tabular-nums;}}
.k-rozet.k-iyi{{background:color-mix(in srgb,var(--k-yesil) 15%,transparent);color:var(--k-yesil);}}
.k-rozet.k-kotu{{background:color-mix(in srgb,var(--k-kirmizi) 15%,transparent);color:var(--k-kirmizi);}}
.k-spark{{display:block;width:100% !important;height:28px !important;margin-top:6px;}}
.k-yeni .k-deger-satir{{flex-wrap:wrap;row-gap:2px;}}
@media (max-width:640px){{ .k-kart.k-vurgu{{flex-basis:100%;}} }}

/* ── GÖRÜNMEZ ELEMAN BOŞLUĞU ────────────────────────────────────────
   Sayfaya eklenen yalnız-<style> blokları ve yüksekliği 0 olan script
   iframe'leri görünmez, ama Streamlit her birinin arasına 16px boşluk koyar.
   Sayfa başında ~10 tane olduğu için içerik ~200px aşağıda başlıyordu.
   Bunları akıştan çıkarıyoruz (position:absolute → flex boşluğu almaz).
   display:none DEĞİL — script'ler çalışmaya devam etsin. Seçiciler canlı
   sayfada doğrulandı: görünür hiçbir elemanı yakalamıyor. */
[data-testid="stElementContainer"]:has([data-testid="stMarkdownContainer"] > style:only-child),
[data-testid="stElementContainer"][height="0px"]{{
  position:absolute !important;width:0 !important;height:0 !important;
  margin:0 !important;padding:0 !important;overflow:hidden !important;pointer-events:none;}}
.k-baslik{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;
  padding:0 0 7px;margin:0 0 11px;
  border-bottom:1px solid var(--k-kenar);}}
.k-baslik-ikon{{width:26px;height:26px;border-radius:7px;flex-shrink:0;
  background:color-mix(in srgb,var(--c,var(--k-mor2)) 15%,transparent);
  box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--c,var(--k-mor2)) 28%,transparent);
  display:flex;align-items:center;justify-content:center;font-size:12px;}}
.k-baslik-ikon .k-ikon{{color:var(--c,var(--k-mor2));}}
.k-baslik-mod{{font-size:{F['orta']};color:var(--k-soluk);font-weight:{AGIRLIK['vurgu']};}}
.k-baslik-ayrac{{color:var(--k-silik);font-size:{F['orta']};}}
.k-baslik-ad{{font-size:{F['baslik']};color:var(--k-metin);
  font-weight:{AGIRLIK['baslik']};letter-spacing:{TRACKING['baslik']};}}
.k-baslik-aciklama{{flex-basis:100%;order:9;margin:3px 0 0 34px;
  font-size:12.5px;color:var(--k-soluk);line-height:1.45;}}
.k-baslik-alt{{margin-left:auto;font-size:{F['kucuk']};color:var(--k-silik);
  font-family:var(--k-mono);white-space:nowrap;}}

.k-rozet{{display:inline-block;padding:2px 7px;border-radius:999px;
  font-size:{F['kucuk']};font-weight:{AGIRLIK['vurgu']};line-height:1.4;white-space:nowrap;}}

.k-pencere-basi{{display:flex;align-items:center;gap:8px;margin-bottom:8px;
  flex-shrink:0;font-size:{F['orta']};font-weight:650;color:var(--k-metin);}}
.k-pencere-ic{{overflow-y:auto;padding-right:6px;}}
.k-pencere-ic::-webkit-scrollbar{{width:5px;}}
.k-pencere-ic::-webkit-scrollbar-track{{background:transparent;}}
.k-pencere-ic::-webkit-scrollbar-thumb{{background:var(--k-kenar2);border-radius:3px;}}

.k-satir{{display:flex;justify-content:space-between;align-items:center;
  padding:{sp};margin:2px 0;border-radius:6px;font-size:{F['govde']};
  font-weight:{AGIRLIK['govde']};background:var(--k-ortu);}}
.k-satir:hover{{background:var(--k-ortu2);}}
.k-satir-sag{{display:flex;gap:10px;flex-shrink:0;margin-left:8px;
  align-items:center;font-variant-numeric:tabular-nums;}}

.k-bos{{color:var(--k-silik);font-size:{F['govde']};padding:10px 4px;}}

[data-testid="stDataFrame"]{{border-radius:var(--k-r) !important;
  overflow:hidden !important;border:1px solid var(--k-kenar) !important;}}
div[data-testid="stDialog"] > div:first-child{{
  border:1px solid var(--k-kenar2) !important;border-radius:14px !important;}}
div[data-testid="stDialog"] [data-testid="stHeading"]{{
  font-size:{F['baslik']} !important;font-weight:700 !important;
  letter-spacing:-.2px !important;color:var(--k-metin) !important;}}
div[data-testid="stCaptionContainer"] p{{color:var(--k-soluk) !important;}}

@media (max-width:640px){{
  .k-kart{{min-width:110px;}}
  .k-baslik-alt{{display:none;}}
}}
""" + _streamlit_normalize() + (TABLO_YENI_CSS if TABLO_YENI else "")
        + (PENCERE_GENIS_CSS if PENCERE_GENIS else "")) + "</style>"


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
def baslik(modul, sayfa, alt="", ipucu="", aciklama=""):
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
        # Baştaki emoji → aynı sayfanın sol menüdeki ikonu (Material), modülün
        # kimlik renginde karo. Eskiden emoji olduğu gibi basılıyordu; sol
        # menü ve üst menü çizgi ikonken başlıkta renkli emoji kalıyordu.
        _ik, modul = emoji_ayir(modul)
        _renk = "mor2"
        try:
            import streamlit as _st
            _renk = MODUL_RENK.get(_st.session_state.get("aktif_uygulama", ""), "mor2")
        except Exception:  # noqa: BLE001 — test ortamı: streamlit yok
            pass
        if _ik:
            ikon = f'<div class="k-baslik-ikon" style="--c:{rv(_renk)}">{ikon_html(_ik, 15)}</div>'
    alt_html = f'<div class="k-baslik-alt">{alt}</div>' if alt else ""
    ack_html = f'<div class="k-baslik-aciklama">{aciklama}</div>' if aciklama else ""
    ttl = f' title="{ipucu}"' if ipucu else ""
    mod_html = (f'<span class="k-baslik-mod">{modul}</span>'
                f'<span class="k-baslik-ayrac">›</span>') if modul else ""
    return (f'<div class="k-baslik"{ttl}>{ikon}{mod_html}'
            f'<span class="k-baslik-ad">{sayfa}</span>{alt_html}{ack_html}</div>')


# ── Emoji → çizgi ikon (Ekim 2026) ──────────────────────────────────
# True : mesaj kutusu, pencere başlığı, sekme, açılır bölüm ve düğme etiketlerinin
#        başındaki emoji Material ikona çevrilir (shared/ikon.py, app.py'de kurulur).
# False: emojiler eskisi gibi. Geri almak için YALNIZ bu satırı değiştir.
IKON_YENI = True

# ── Tablo çekirdeği görünümü (Ekim 2026) ────────────────────────────
# True : tablo_html / df_tablo_html (Muhasebe, İthalat, Veri yükleme tabloları) ortak
#        tablo bileşeniyle (shared/tablo.py) aynı görünümde: zebra yok, sayılar normal yazı
#        tipinde, hap rozet. Satır vurgusu aynen.
# False: eski görünüm. Geri almak için YALNIZ bu satırı değiştir.
TABLO_YENI = True

# ── Streamlit ızgarası (Ekim 2026) ──────────────────────────────────
# True : düzenlenebilir tablolar ve uzun / seçimli st.dataframe ortak ayarla (shared/izgara.py):
#        ferah satır, "$149,00" (4 ondalık "$149,0000" değil), Türkçe sayı, geniş ürün sütunu,
#        çok sütunlu tabloda SKU solda sabit. Kayıt hassasiyeti değişmez.
# False: eski görünüm. Geri almak için YALNIZ bu satırı değiştir.
IZGARA_YENI = True

# ── Sade tablo (Ekim 2026, kullanıcının seçtiği "I" tasarımı, renklendirmesiz) ─────
# True : ortak tablo (shared/tablo.py) ve düzenlenebilir tablolar (shared/duzenle.py) aynı
#        sade görünümde: ürün adının altında SKU, başlık bandı yok, ferah satır, kâr/marj/ciro
#        renksiz, birim maliyet soluk. Düzenlenebilir tablolar hücre içinde düzeltilir.
# False: eski görünüm ve Streamlit'in düzenleme tablosu. Geri almak için YALNIZ bu satırı değiştir.
TABLO_SADE = True

TABLO_YENI_CSS = """
/* ── Tablo çekirdeği (tablo_html) ortak görünümde (TABLO_YENI) ── */
.k-tbw{border-radius:12px !important;}
.k-tb thead th{font-weight:500;padding:9px 12px;}
.k-tb tbody td{padding:9px 12px;}
.k-tb tbody tr:nth-child(even) td{background:transparent;}
.k-tb tbody tr[data-vurgu] td{background:color-mix(in srgb,var(--v) 10%,transparent);}
.k-tb .sayi{font-family:inherit;font-variant-numeric:tabular-nums;}
.k-tb tfoot td{font-weight:600;border-top:1px solid var(--k-kenar2);}
.k-tb.sik thead th{padding:6px 8px;} .k-tb.sik tbody td{padding:6px 8px;}
.k-tb .k-rz{border:0;border-radius:999px;font-size:12px;font-weight:500;padding:1px 8px;letter-spacing:0;}
"""


# ── Yan panel (Ekim 2026) ───────────────────────────────────────────
# True : yan_panel() çağıran okuma pencereleri (detaylar) sağdan tam boy panel açılır.
# False: bütün pencereler eskisi gibi ortada. Geri almak için YALNIZ bu satırı değiştir.
YAN_PANEL = True

# True : sayfa içi detaylarda (Tüm Ürünler) geniş ekranda liste solda, detay sağda.
# False: eskisi gibi yalnız detay + "Listeye dön". Geri almak için YALNIZ bu satırı değiştir.
YAN_YANA = True


def panel_isareti(genislik="orta"):
    """Pencereye basılan görünmez işaret; CSS :has(.k-panel) bu pencereyi sağa alır.
    <style> öğesi: ortak CSS, yalnız-stil öğelerini akıştan çıkardığı için boşluk bırakmaz."""
    return f'<style class="k-panel k-panel-{genislik}"></style>'


def yan_panel(genislik="orta"):
    """Pencere fonksiyonunun ilk satırı: bu pencere sağ panel olsun (dar / orta / genis).
    Yalnız okumaya dönük detaylar için; formlar ortada kalır."""
    if not YAN_PANEL:
        return
    import streamlit as _st
    _st.markdown(panel_isareti(genislik), unsafe_allow_html=True)


# ── Geniş pencere (Ekim 2026, kullanıcının seçtiği "A") ──────────────
# True : tablolu pencereler (yan_panel "orta" / "genis": sipariş, firma sipariş geçmişi, Ref,
#        kampanya, stok kartı) ortada, ekranın neredeyse tamamı (en çok 1.280 px) açılır; tablo
#        yana kaydırmadan sığar. Kısa bilgi pencereleri ("dar": iade, ödeme, çek) sağda kalır.
#        Telefonda tam ekran.
# False: hepsi sağdan panel (680 / 860 px). Geri almak için YALNIZ bu satırı değiştir.
PENCERE_GENIS = True

PENCERE_GENIS_CSS = """
[data-testid="stDialog"]:has(.k-panel-orta) [role="dialog"],
[data-testid="stDialog"]:has(.k-panel-genis) [role="dialog"]{position:fixed !important;top:3vh !important;bottom:3vh !important;
  left:0 !important;right:0 !important;margin:0 auto !important;width:min(1280px,96vw) !important;max-width:96vw !important;
  height:auto !important;max-height:94vh !important;max-height:94dvh !important;border-radius:18px !important;
  border:1px solid var(--k-kenar2) !important;box-shadow:0 24px 70px rgba(0,0,0,.5) !important;animation:k-genis-gir .16s ease-out;}
@keyframes k-genis-gir{from{transform:scale(.985);opacity:.4}to{transform:none;opacity:1}}
@media (max-width:640px){
  [data-testid="stDialog"]:has(.k-panel-orta) [role="dialog"],
  [data-testid="stDialog"]:has(.k-panel-genis) [role="dialog"]{top:0 !important;bottom:0 !important;width:100vw !important;
    max-width:100vw !important;max-height:100dvh !important;border-radius:0 !important;border:none !important;}
}
"""


# ── Sayı kartları (Ekim 2026) ───────────────────────────────────────
# True : tek görünüm, renk yalnız anlam taşıdığında (kırmızı = sorun); ana kart,
#        değişim rozeti ve eğilim çizgisi isteğe bağlı.
# False: eski renkli şeritli kartlar. Geri almak için YALNIZ bu satırı değiştir.
KART_YENI = True

_KOTU_ANAHTAR = ("kirmizi", "kirmizi2")


def kart_anlami(renk):
    """Eski 'renk' alanı → anlam. Yalnız kırmızı 'kötü'dür; mor/cyan/mavi/amber/yeşil
    çoğunlukla süs olarak kullanılmıştı (sayım: 80 süs, 11 kırmızı) → nötr."""
    if not renk:
        return None
    r = str(renk).strip()
    if r in _KOTU_ANAHTAR or any(f"--k-{k})" in r for k in _KOTU_ANAHTAR):
        return "kotu"
    u = r.upper()
    if ESKI_RENK_ESLEME.get(u) in _KOTU_ANAHTAR:
        return "kotu"
    for palet in TEMALAR.values():
        if any(str(palet.get(k, "")).upper() == u for k in _KOTU_ANAHTAR):
            return "kotu"
    return None


def degisim_rozeti(simdi, onceki, artis_iyi=True):
    """(metin, anlam) — '▼ %40,0', 'kotu'. Önceki yoksa / sıfırsa None."""
    try:
        s, o = float(simdi), float(onceki)
    except (TypeError, ValueError):
        return None
    if not o:
        return None
    d = (s - o) / abs(o) * 100
    if abs(d) < 0.05:
        return (f"■ %{tr_sayi(0, 1)}", None)
    yukari = d > 0
    anlam = "iyi" if (yukari == bool(artis_iyi)) else "kotu"
    return (f"{'▲' if yukari else '▼'} %{tr_sayi(abs(d), 1)}", anlam)


def spark_svg(seri, anlam=None):
    """Küçük eğilim çizgisi (son nokta anlam rengiyle). 2'den az noktada boş."""
    try:
        v = [float(x) for x in (seri or []) if x is not None]
    except (TypeError, ValueError):
        return ""
    if len(v) < 2:
        return ""
    lo, hi = min(v), max(v)
    ara = (hi - lo) or 1.0
    n = len(v) - 1
    pts = [(i / n * 100, 24 - (x - lo) / ara * 20) for i, x in enumerate(v)]
    nok = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    # Çizgi enine esnetildiği için uç noktası elipse dönüşüyordu → nokta yok; yönü rozet söyler.
    return (f'<svg class="k-spark" viewBox="0 0 100 28" preserveAspectRatio="none" aria-hidden="true">'
            f'<polyline fill="none" style="stroke:var(--k-soluk)" stroke-width="1.5" '
            f'vector-effect="non-scaling-stroke" points="{nok}"/></svg>')


def kart_hucresi(k):
    """Tek kart HTML'i. k: etiket, deger (HTML olabilir), alt?, ipucu?, renk? (eski;
    yalnız kırmızı anlam taşır), anlam? (iyi/kotu/dikkat — renkten önce gelir),
    vurgu? (ana kart), simdi?+onceki? (değişim rozeti), artis_iyi? (varsayılan True),
    seri? (eğilim çizgisi), bilgi? (ⓘ)."""
    anlam = k.get("anlam") or kart_anlami(k.get("renk"))
    if anlam == "notr":             # renk süs olarak kırmızı verilmiş (ör. paçal, borç)
        anlam = None
    roz = k.get("rozet") or (degisim_rozeti(k.get("simdi"), k.get("onceki"), k.get("artis_iyi", True))
                             if k.get("onceki") is not None else None)
    sinif = "k-kart k-yeni" + (" k-vurgu" if k.get("vurgu") else "") + (f" k-{anlam}" if anlam else "")
    ip = k.get("ipucu") or ""
    ttl = f' title="{_html.escape(str(ip), quote=True)}"' if ip else ""
    im = ' <span style="opacity:.6">ⓘ</span>' if k.get("bilgi") else ""
    rz = (f'<span class="k-rozet{" k-" + roz[1] if roz[1] else ""}">{roz[0]}</span>' if roz else "")
    alt = f'<div class="k-alt">{k["alt"]}</div>' if k.get("alt") else ""
    sp = spark_svg(k.get("seri"), roz[1] if roz else anlam) if k.get("seri") else ""
    return (f'<div class="{sinif}"{ttl}>'
            f'<div class="k-etiket">{_kart_etiket(k)}{im}</div>'
            f'<div class="k-deger-satir"><span class="k-deger">{k.get("deger", "")}</span>{rz}</div>'
            f'{alt}{sp}</div>')


def kpi_serit(kalemler, yogunluk=None):
    """KPI kartı şeridi — programdaki TEK metrik bileşeni.

    kalemler = [{"etiket","deger","renk"?,"alt"?,"ipucu"?,"tam"?}]
    `renk` RENK anahtarıdır ("yesil"), hex DEĞİL.
    """
    if KART_YENI:
        return '<div class="k-grid">' + "".join(
            kart_hucresi(dict(k, ipucu=k.get("ipucu") or k.get("tam") or "")) for k in kalemler) + '</div>'
    hucreler = ""
    for k in kalemler:
        if k.get("onceki") is not None:          # eski görünümde rozet yok → bilgiyi alt satıra yaz
            _rz = degisim_rozeti(k.get("simdi"), k.get("onceki"), k.get("artis_iyi", True))
            if _rz:
                k = dict(k, alt=f'{_rz[0]} · {k.get("alt") or ""}'.rstrip(" ·"))
        c = rv(k.get("renk", "mor"))
        ipucu = k.get("ipucu") or k.get("tam") or ""
        ttl = f' title="{ipucu}"' if ipucu else ""
        alt = f'<div class="k-alt">{k["alt"]}</div>' if k.get("alt") else ""
        hucreler += (
            f'<div class="k-kart" data-akscent style="border-left-color:{c}"{ttl}>'
            f'<div class="k-etiket">{_kart_etiket(k)}</div>'
            f'<div class="k-deger" style="color:{c}">{k["deger"]}</div>'
            f'{alt}</div>')
    return f'<div class="k-grid">{hucreler}</div>'


def kart(baslik_metni, renk, icerik_html, rozet_metni="", yukseklik=170):
    """İç kaydırmalı pencere kartı. `renk` RENK anahtarı."""
    c = rv(renk)
    roz = rozet(rozet_metni, renk) if rozet_metni else ""
    _ik, _bas = emoji_ayir(baslik_metni)
    _ik_html = ikon_html(_ik, 16, c) if _ik else ""
    return (f'<div class="k-kart" data-akscent style="border-left-color:{c}">'
            f'<div class="k-pencere-basi">{_ik_html}'
            f'<span>{cumle_duzeni(_bas)}</span>{roz}</div>'
            f'<div class="k-pencere-ic" style="max-height:{yukseklik}px">'
            f'{icerik_html}</div></div>')


def kart_grid(*kartlar):
    return f'<div class="k-grid">{"".join(kartlar)}</div>'


def rozet(metin, renk="mor"):
    c = rv(renk)
    return (f'<span class="k-rozet" style="background:color-mix(in srgb,{c} 14%,transparent);'
            f'color:{c}">{metin}</span>')


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
                # format="dollar" sabit 2 hane verir; birim fiyatlardaki
                # kuruş altı basamak (7,2938) kaybolurdu. Kolonun DEĞERLERİNE
                # bakıp gereken hassasiyeti seçiyoruz.
                try:
                    _ond = 2
                    for _v in seri.dropna().head(400):
                        _f2 = float(_v)
                        if _f2 != round(_f2, 2):
                            _ond = 4
                            break
                except Exception:
                    _ond = 2
                cfg[c] = _st.column_config.NumberColumn(
                    format=("dollar" if _ond == 2 else "$%.4f"),
                    alignment="right")
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

def _tr_para(v, birim="$", basamak=None):
    """1616061.27 → '$1.616.061,27' (TR ayraç).

    basamak=None (varsayılan): AKILLI — en az 2, en fazla 4 hane. Gereksiz
    sondaki sıfırlar atılır. Böylece birim fiyatlardaki kuruş altı basamak
    (7,2938) korunur, toplamlarda gürültü olmaz (1.616.061,27).
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return ""
    if basamak is None:
        s = f"{abs(f):,.4f}"
        tam, _, ond = s.partition(".")
        ond = ond.rstrip("0")
        ond = (ond + "00")[:2] if len(ond) < 2 else ond
        s = f"{tam}.{ond}"
    else:
        s = f"{abs(f):,.{basamak}f}"
    s = s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return ("-" if f < 0 else "") + birim + s


def _tr_adet(v):
    try:
        return f"{int(round(float(v))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return ""


def _tr_oran(v, basamak=2):
    # Eskiden yalnız "." → "," yapılıyordu: 1234.5 → "%1,234,50" (binlik
    # virgül kalıyordu). Artık tam TR biçimi: "%1.234,50".
    try:
        return "%" + _tr(f"{float(v):,.{basamak}f}")
    except (TypeError, ValueError):
        return ""


# ═══════════════════════════════════════════════════════════════════
# SAYI · TARİH STANDARDI — programın TEK biçimi (Türkçe)
#   para(678033)            → "$678.033"      para(1240500.5, "₺", 2) → "₺1.240.500,50"
#   adet(12500)             → "12.500"
#   oran(30.94)             → "%30,9"
#   tarih("2026-09-30")     → "30.09.2026"
#   tr_sayi(1234.5, 2)      → "1.234,50"       (f-string içinde: {tr_sayi(x, 2)})
# Eskiden aynı ekranda "$678,033" (İngilizce) ile "₺226.500" (Türkçe) yan
# yana duruyordu. f"{x:,.2f}" YAZMA — bunları kullan.
# ═══════════════════════════════════════════════════════════════════
def tr_sayi(v, basamak=0):
    """Sayı → TR biçimli metin (binlik nokta, ondalık virgül). Sayı değilse olduğu gibi."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "" if v is None else str(v)
    if basamak == 0:
        f = round(f)
    return _tr(f"{f:,.{basamak}f}")


def para(v, birim="$", basamak=0):
    """Para: işaret birimden önce → '-$1.234'. Sayı değilse '—'."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    return ("-" if f < 0 else "") + birim + tr_sayi(abs(f), basamak)


def adet(v):
    try:
        return tr_sayi(int(round(float(v))))
    except (TypeError, ValueError):
        return "—"


def oran(v, basamak=1):
    try:
        return "%" + tr_sayi(float(v), basamak)
    except (TypeError, ValueError):
        return "—"


def tarih(v, saat=False):
    """'2026-09-30' / date / datetime → '30.09.2026' (saat=True → '30.09.2026 14:05')."""
    import datetime as _dt
    if v in (None, ""):
        return "—"
    try:
        if isinstance(v, str):
            t = v.strip().replace("T", " ")
            d = _dt.datetime.fromisoformat(t[:19]) if len(t) > 10 else _dt.datetime.fromisoformat(t[:10])
        elif isinstance(v, _dt.datetime):
            d = v
        elif isinstance(v, _dt.date):
            d = _dt.datetime(v.year, v.month, v.day)
        else:
            return str(v)
    except ValueError:
        return str(v)
    return d.strftime("%d.%m.%Y %H:%M" if saat else "%d.%m.%Y")


class Ham(str):
    """tablo_html hücresi için HAZIR HTML — kaçış uygulanmadan basılır.
    Metin/sayı hücreleri kaçırılır (DB'den gelen '<' patlatmaz); rozet, link ya da
    renkli parça gerekiyorsa Ham("...") ver ya da rozet_html()/renkli() kullan."""


def rozet_html(metin, renk="mor"):
    """Tablo/kart içinde küçük durum rozeti: rozet_html("ÖDENDİ", "yesil")."""
    import html as _h
    return Ham(f'<span class="k-rz" style="--r:var(--k-{renk if renk in RENK else "mor"})">{_h.escape(str(metin))}</span>')


def renkli(metin, renk="metin", kalin=False, title=None, tek=True):
    """Tek renkli hücre parçası (Ham). tek=True → kelime ortasından kırılmaz
    (gün adı, kod gibi kısa metinler). title verilirse üstüne gelince görünür."""
    import html as _h
    t = f' title="{_h.escape(str(title), quote=True)}"' if title else ""
    k = ("font-weight:700;" if kalin else "") + ("white-space:nowrap;" if tek else "")
    return Ham(f'<span style="{k}color:var(--k-{renk if renk in RENK else "metin"})"{t}>{_h.escape(str(metin))}</span>')


class Kisa(Ham):
    """kisalt() çıktısı — hücre tek satırda kalır, sığmayan kısım '…' ile kesilir."""


def kisalt(metin, n=42):
    """Uzun metni '…' ile kısaltıp tamamını title'a koyar (üstüne gelince görünür).
    Hücre tek satır kalır, en fazla 200px genişler; komşu sütunları ezmez."""
    import html as _h
    m = str(metin or "")
    if len(m) <= n:
        return Kisa(_h.escape(m))
    return Kisa(f'<span title="{_h.escape(m, quote=True)}">{_h.escape(m[:n - 1])}…</span>')



_TB_HIZA = {"para": "sag", "adet": "sag", "oran": "sag", "tam": "sag", "sayi": "sag", "mono": "sol"}


def _tr_tam(v, max_ond=6):
    """YUVARLAMADAN, sondaki sıfırları atarak TR biçimi: 1234 → '1.234', 1234.5678 → '1.234,5678'.
    İthalat mal bedeli/masraf gibi tutarlar yukarı-aşağı yuvarlanmadan görünür."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return ""
    neg = x < 0
    sayi = f"{abs(x):.{max_ond}f}".rstrip("0").rstrip(".")
    tam, _, ond = sayi.partition(".")
    tam = f"{int(tam):,}".replace(",", ".")
    return ("-" if neg else "") + tam + ("," + ond if ond else "")


def tablo_html(kolonlar, satirlar, toplam=None, vurgu=None, yukseklik=None, bos_mesaj="Gösterilecek veri yok.",
               sik=False):
    """ORTAK salt-okur tablo (HTML). Modüllerin kendi <table> yazması yerine bu.

    kolonlar: ["Firma", ("Tutar", "para", "₺"), {"ad": "Adet", "tip": "adet"}]
        tip: metin (varsayılan) · para · adet · oran · sayi (en çok 2 hane) · tam (yuvarlamasız) · mono
        birim: para için ₺ / $ (tip para ise 3. eleman ya da "birim" anahtarı)
        hiza: sol / sag / orta (varsayılan: sayı → sağ, diğer → sol)
    satirlar: [{kolon_adi: değer}]  değer: sayı, metin, None ("—") ya da Ham (hazır HTML)
    toplam:   {kolon_adi: değer} — kalın alt satır (tfoot)
    vurgu:    satır → renk anahtarı ("kirmizi"/"amber"/"yesil"/…) ya da None
    yukseklik: px verilirse kaydırmalı olur, başlık yapışkan kalır.
    sik:      çok sütunlu tablolar için dar boşluk + küçük yazı (15 sütun ekrana sığsın).

    Kaçış: Ham olmayan her hücre html.escape'ten geçer.
    Kullanım: st.html(tablo_html(...))  (st.markdown da olur)
    """
    import html as _h
    if not satirlar:
        return bos(_h.escape(bos_mesaj))
    kol = []
    for k in kolonlar:
        if isinstance(k, dict):
            kol.append({"ad": k["ad"], "tip": k.get("tip", "metin"), "birim": k.get("birim", "$"),
                        "hiza": k.get("hiza")})
        elif isinstance(k, (tuple, list)):
            kol.append({"ad": k[0], "tip": k[1] if len(k) > 1 else "metin",
                        "birim": k[2] if len(k) > 2 else "$", "hiza": k[3] if len(k) > 3 else None})
        else:
            kol.append({"ad": str(k), "tip": "metin", "birim": "$", "hiza": None})
    for k in kol:
        k["hiza"] = k["hiza"] or _TB_HIZA.get(k["tip"], "sol")

    def hucre(k, v, tag="td"):
        sinif = [k["hiza"]] if k["hiza"] != "sol" else []
        if isinstance(v, Kisa):
            metin = str(v); sinif.append("kisa")
        elif isinstance(v, Ham):
            metin = str(v)
        elif v is None or v == "":
            metin, sinif = "—", sinif + ["silik"]
        elif k["tip"] == "para":
            metin = _tr_para(v, k["birim"]); sinif.append("sayi")
        elif k["tip"] == "adet":
            metin = _tr_adet(v); sinif.append("sayi")
        elif k["tip"] == "oran":
            metin = _tr_oran(v); sinif.append("sayi")
        elif k["tip"] == "tam":
            metin = _tr_tam(v); sinif.append("sayi")
        elif k["tip"] == "sayi":                      # 12 → '12', 12,5 → '12,5', 12,345 → '12,35'
            metin = _tr_tam(v, 2); sinif.append("sayi")
        elif k["tip"] == "mono":
            metin = _h.escape(str(v)); sinif.append("sayi")
        else:
            metin = _h.escape(str(v))
        if k["tip"] in ("para", "adet", "oran", "tam", "sayi") and not isinstance(v, Ham):
            try:
                if float(v) < 0:
                    sinif.append("neg")
            except (TypeError, ValueError):
                pass
        c = f' class="{" ".join(sinif)}"' if sinif else ""
        return f"<{tag}{c}>{metin}</{tag}>"

    bas = "".join(f'<th class="{k["hiza"]}">{_h.escape(k["ad"])}</th>' if k["hiza"] != "sol"
                  else f'<th>{_h.escape(k["ad"])}</th>' for k in kol)
    govde = []
    for r in satirlar:
        vr = vurgu(r) if vurgu else None
        attr = f' data-vurgu="{vr}" style="--v:var(--k-{vr})"' if vr in RENK else ""
        govde.append(f"<tr{attr}>" + "".join(hucre(k, r.get(k["ad"])) for k in kol) + "</tr>")
    alt = ""
    if toplam:
        alt = "<tfoot><tr>" + "".join(hucre(k, toplam.get(k["ad"])) for k in kol) + "</tr></tfoot>"
    sarmal = f' style="max-height:{int(yukseklik)}px"' if yukseklik else ""
    return (f'<div class="k-tbw"{sarmal}><table class="k-tb{" sik" if sik else ""}"><thead><tr>{bas}</tr></thead>'
            f'<tbody>{"".join(govde)}</tbody>{alt}</table></div>')


def df_tablo_html(df, para=None, yuzde=None, kar=None, sol=None, kisa=None, gizle=None,
                  satir_vurgu=None, birim="$", tam=False, bos_mesaj="Gösterilecek veri yok.", sik=False):
    """DataFrame → tablo_html. Modüllerin kendi 'render_renkli_tablo' / '_tablo'
    yardımcılarının ORTAK karşılığı (Aşama 4b).

    para/yuzde: kolon adları (para: birim ile, yuzde: %x,x) · kar: + yeşil / − kırmızı
    sol: sayısal olsa da sola yaslanacak kolonlar · kisa: {kolon: en çok karakter}
    gizle: gösterilmeyecek kolonlar · satir_vurgu: (kolon, {değer: renk}) → satır rengi
    tam=True: para ve sayılar yuvarlanmadan (İthalat tutarları)
    """
    try:
        import pandas as _pd
    except ImportError:            # pandas yoksa düz metin
        _pd = None
    para = set(para or []); yuzde = set(yuzde or []); kar = set(kar or [])
    sol = set(sol or []); kisa = kisa or {}; gizle = set(gizle or [])
    if df is None or len(df) == 0:
        return bos(bos_mesaj)
    kolonlar = [c for c in df.columns if c not in gizle]

    def _sayisal(c):
        try:
            return bool(_pd and _pd.api.types.is_numeric_dtype(df[c]))
        except Exception:
            return False

    kol = []
    for c in kolonlar:
        if c in sol and c not in para and c not in yuzde:
            kol.append((c, "metin")); continue
        if c in para:
            kol.append((c, "tam" if tam else "para", birim, "sol" if c in sol else "sag"))
        elif c in yuzde:
            kol.append((c, "oran", "$", "sol" if c in sol else "sag"))
        elif _sayisal(c):
            kol.append((c, "tam" if tam else "sayi", "$", "sol" if c in sol else "sag"))
        else:
            kol.append((c, "metin"))
    vk, vharita = (satir_vurgu or (None, {}))

    satirlar = []
    for _, r in df.iterrows():
        kayit = {}
        for c in kolonlar:
            v = r[c]
            if _pd is not None and v is not None and not isinstance(v, str):
                try:
                    if _pd.isna(v):
                        v = None
                except (TypeError, ValueError):
                    pass
            if c in kar and v is not None:
                try:
                    f = float(v)
                    v = renkli(_tr_para(f, birim), "yesil2" if f > 0 else ("kirmizi" if f < 0 else "metin"), kalin=f != 0)
                except (TypeError, ValueError):
                    pass
            elif c in kisa and v is not None:
                v = kisalt(v, kisa[c])
            kayit[c] = v
        satirlar.append(kayit)
    vurgu = (lambda r: vharita.get(str(r.get(vk, "")))) if vk else None
    return tablo_html(kol, satirlar, vurgu=vurgu, bos_mesaj=bos_mesaj, sik=sik)


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
import html as _html
import itertools as _it
_TABLO_SAYAC = _it.count(1)


def tablo_sirali(satirlar, birim="$", stil="zebra", toplam_isaret="Σ",
                 satir_yuksekligi=None, maks_yukseklik=520, kap=None,
                 maks_hucre=280):
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
    # Ekim 2026: tek görünüm shared/tablo.py'de (arama, Σ alt bilgi, mobil kart,
    # indirme). components v2 yoksa (eski Streamlit) aşağıdaki eski çizim kalır.
    try:
        from shared.tablo import tablo
        tablo(satirlar, birim=birim, toplam_isaret=toplam_isaret,
              maks_yukseklik=maks_yukseklik, kap=kap)
        return
    except Exception:          # bileşen yok ya da çizilemedi → tablo kaybolmasın
        pass
    R, F, A = RENK, FONT, AGIRLIK
    kolonlar = list(satirlar[0].keys())
    tipler = {k: _tablo_kolon_tipi(k) for k in kolonlar}
    _acik = stil in ("havadar", "rozet")
    _rozet = (stil == "rozet")
    _pad = "10px 12px" if _acik else "6px 11px"
    _sy = satir_yuksekligi or (38 if _acik else 30)
    try:
        _maks_hucre = max(90, int(maks_hucre))
    except (TypeError, ValueError):
        _maks_hucre = 280

    _id = f"kt{next(_TABLO_SAYAC)}"
    _css = f"""<style>
#{_id}{{{'' if _acik else f'border:1px solid {R["kenar"]};border-radius:10px;'}max-width:100%;overflow:auto}}
#{_id} table{{width:100%;border-collapse:collapse{'' if _acik else f';background:{R["yuzey1"]}'}}}
#{_id} th{{font-size:{F["kucuk"]};font-weight:{A["vurgu"]};white-space:nowrap;
   position:sticky;top:0;z-index:1;cursor:pointer;user-select:none;
   {f'color:{R["silik"]};letter-spacing:0;padding:0 12px 8px;background:{R["yuzey0"]};border-bottom:1px solid {R["kenar2"]}'
     if _acik else
     f'color:{R["soluk"]};letter-spacing:.3px;padding:8px 11px;background:{R["yuzey2"]};border-bottom:1px solid {R["kenar2"]}'}}}
#{_id} th:hover{{color:{R["metin"]}}}
#{_id} td{{padding:{_pad};font-size:{F["govde"]};font-weight:{A["govde"]};
   color:{R["metin"]};
   /* TEK SATIR. Eskiden `overflow-wrap:anywhere` vardı ve uzun ürün adları
      satırı aşağı doğru büyütüyor, hatta kelime ortasından kırıp
      "FAZEO / N" gibi okunmaz sonuçlar veriyordu. Artık her hücre tek
      satır; sığmayan metin "…" ile kısalır ve tamamı fareyle üzerine
      gelince ipucu (title) olarak görünür. */
   white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
   max-width:{_maks_hucre}px{f';border-bottom:1px solid {R["kenar"]}' if _acik else ''}}}
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
            # Sayı olarak SINIFLANDIRILMAYAN kolonlarda (ör. "id") pandas
            # değeri float tuttuğu için str() "49669.0" üretiyordu. Tam
            # sayıya eşit float'lar ondalıksız yazılır. Gerçek ondalıklı
            # değerler (12.5) olduğu gibi kalır.
            if isinstance(v, float) and v == v and float(v).is_integer():
                metin, sayi = str(int(v)), False
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
        # Hücre tek satıra sığmayınca "…" ile kısalıyor; tam metin KAYBOLMASIN
        # diye title olarak eklenir (fareyle üzerine gelince görünür).
        # Sayılar kısa olduğu için onlara ipucu konmaz.
        _ip = ""
        if not sayi and len(metin) > 24:
            _kacis = (metin.replace("&", "&amp;").replace('"', "&quot;")
                      .replace("<", "&lt;").replace(">", "&gt;"))
            _ip = f' title="{_kacis}"'
        _cls = f' class="{sinif}"' if sinif else ""      # Python 3.11: f-string içinde ters bölü yok
        return f'<td{_cls}{ds}{_ip}>{metin}</td>'

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
