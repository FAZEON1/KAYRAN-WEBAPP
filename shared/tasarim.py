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
}

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
def cekirdek_css(yogunluk=None):
    R, F = RENK, FONT
    kp, kr, gg, sa, sp, kmin = (_y("kart_pad", yogunluk), _y("kart_r", yogunluk),
                                _y("grid_gap", yogunluk), _y("serit_alt", yogunluk),
                                _y("satir_pad", yogunluk), _y("kart_min", yogunluk))
    degiskenler = "".join(f"--k-{k}:{v};" for k, v in R.items())
    return f"""<style>
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
</style>"""


def islem_gosterge_css():
    """Sadece üstte ince akan çubuk. Nabız atan 'İşleniyor' kapsülü KALDIRILDI —
    her checkbox tıklamasında ekranın ortasında uyarı belirmesi, uygulamayı
    olduğundan yavaş hissettiriyordu."""
    return f"""<style>
@keyframes k-akan{{0%{{background-position:0 0}}100%{{background-position:200% 0}}}}
div[data-testid="stApp"][data-test-script-state="running"]::before{{
  content:"";position:fixed;top:0;left:0;right:0;height:2px;z-index:999999;
  background:linear-gradient(90deg,{RENK['mor']},{RENK['cyan']},{RENK['mor']});
  background-size:200% 100%;animation:k-akan 1.1s linear infinite;}}
div[data-testid="stStatusWidget"]{{display:none !important;}}
div[data-stale="true"]{{opacity:.5 !important;transition:opacity .2s ease;}}
</style>"""


# ═══════════════════════════════════════════════════════════════════
# 6. BİLEŞENLER — programda "etiketli kutu" artık SADECE burada.
# ═══════════════════════════════════════════════════════════════════
def baslik(modul, sayfa, alt=""):
    """Tek satır kompakt başlık: 34px. Eskisi 85px'ti.

    Modül adı zaten sidebar çipinde ve aktif nav pill'inde yazıyor — bu,
    nerede olduğunun üçüncü kez söylenmesiydi. Kırıntı biçimine indirildi.
    """
    ikon = ""
    if modul and modul[0] not in "ABCÇDEFGHIİJKLMNOÖPRSŞTUÜVYZabcçdefg":
        ikon = f'<div class="k-baslik-ikon">{modul[0]}</div>'
        modul = modul[1:].strip()
    alt_html = f'<div class="k-baslik-alt">{alt}</div>' if alt else ""
    return (f'<div class="k-baslik">{ikon}'
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
