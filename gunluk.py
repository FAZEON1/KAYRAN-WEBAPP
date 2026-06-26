"""
KAYRAN — Günlük pratik bilgiler
Döviz kuru · gram altın · hava durumu · günün sözü.

Tüm fonksiyonlar internet/API hatalarına karşı GÜVENLİDİR:
herhangi bir hata olursa None / {} döner, uygulama ASLA çökmez.
Canlı veriler için uygulamanın sunucusunda internet erişimi gerekir
(Streamlit Cloud'da sorun olmaz). Veriler 30 dk önbelleğe alınır.
"""
import datetime as _dt
import streamlit as st

try:
    import requests
except Exception:
    requests = None

# Varsayılan konum (İstanbul) — istenirse değiştirilebilir
VARSAYILAN_LAT, VARSAYILAN_LON, VARSAYILAN_SEHIR = 41.0082, 28.9784, "İstanbul"

_TIMEOUT = 6


@st.cache_data(ttl=1800, show_spinner=False)
def get_doviz():
    """1 USD ve 1 EUR kaç TL? → {'USD': float, 'EUR': float}. Hata → {}."""
    if not requests:
        return {}
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=_TIMEOUT)
        rates = (r.json() or {}).get("rates", {}) or {}
        usd_try = float(rates.get("TRY")) if rates.get("TRY") else None
        eur_usd = float(rates.get("EUR")) if rates.get("EUR") else None
        out = {}
        if usd_try:
            out["USD"] = usd_try
            if eur_usd:
                out["EUR"] = usd_try / eur_usd
        return out
    except Exception:
        return {}


@st.cache_data(ttl=1800, show_spinner=False)
def get_gram_altin():
    """Gram altın fiyatı (TL). Hata → None."""
    if not requests:
        return None
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=_TIMEOUT)
        ons_usd = float((r.json() or {}).get("price"))
        usd_try = get_doviz().get("USD")
        if ons_usd and usd_try:
            return ons_usd / 31.1034768 * usd_try  # ons → gram
        return None
    except Exception:
        return None


# open-meteo weather_code → (emoji, Türkçe açıklama)
_WC = {
    0: ("☀️", "Açık"), 1: ("🌤️", "Az bulutlu"), 2: ("⛅", "Parçalı bulutlu"), 3: ("☁️", "Kapalı"),
    45: ("🌫️", "Sisli"), 48: ("🌫️", "Sisli"),
    51: ("🌦️", "Hafif çiseleme"), 53: ("🌦️", "Çiseleme"), 55: ("🌦️", "Yoğun çiseleme"),
    61: ("🌧️", "Hafif yağmur"), 63: ("🌧️", "Yağmurlu"), 65: ("🌧️", "Kuvvetli yağmur"),
    66: ("🌧️", "Dondurucu yağmur"), 67: ("🌧️", "Dondurucu yağmur"),
    71: ("🌨️", "Hafif kar"), 73: ("🌨️", "Karlı"), 75: ("❄️", "Yoğun kar"), 77: ("🌨️", "Kar taneli"),
    80: ("🌦️", "Sağanak"), 81: ("🌦️", "Sağanak"), 82: ("⛈️", "Kuvvetli sağanak"),
    85: ("🌨️", "Kar sağanağı"), 86: ("❄️", "Kar sağanağı"),
    95: ("⛈️", "Gök gürültülü"), 96: ("⛈️", "Dolulu fırtına"), 99: ("⛈️", "Dolulu fırtına"),
}


@st.cache_data(ttl=1800, show_spinner=False)
def get_hava(lat=VARSAYILAN_LAT, lon=VARSAYILAN_LON, sehir=VARSAYILAN_SEHIR):
    """{'sicaklik': int, 'durum': str, 'ikon': str, 'sehir': str}. Hata → None."""
    if not requests:
        return None
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current": "temperature_2m,weather_code"},
            timeout=_TIMEOUT,
        )
        c = (r.json() or {}).get("current", {}) or {}
        t = c.get("temperature_2m")
        wc = int(c.get("weather_code", 0))
        ikon, durum = _WC.get(wc, ("🌡️", "—"))
        return {
            "sicaklik": round(float(t)) if t is not None else None,
            "durum": durum, "ikon": ikon, "sehir": sehir,
        }
    except Exception:
        return None


# Orijinal, kısa Türkçe motivasyon cümleleri (gün bazlı döner, internet gerektirmez)
_SOZLER = [
    "Küçük adımlar da seni ileri taşır.",
    "Bugünün işini yarına bırakma; yarınki hâlin teşekkür eder.",
    "Zor günler güçlü insanlar yetiştirir.",
    "Başlamak için en iyi zaman şu an.",
    "Düzen, özgürlüğün sessiz hâlidir.",
    "Bir işi iyi yapmak, çok iş yapmaktan değerlidir.",
    "Acele etme, ama durma da.",
    "Net hedef, yarı yarıya tamamlanmış iştir.",
    "Bugün ektiğin, yarın topladığındır.",
    "Sabır, çabanın olgunlaşmış hâlidir.",
    "Dünkü rekorun, bugünkü başlangıç çizgindir.",
    "Planlı gün, kazanılmış gündür.",
    "İyi bir başlangıç, işin yarısıdır.",
    "Önce halledilmesi gereken işi hallet, gerisi rahatlar.",
    "Kararlılık, yeteneğin önüne geçer.",
    "Bir şeyi basitleştirmek, onu anlamaktır.",
    "Bugün biraz daha iyisini dene, yeter.",
    "Yorgunluk geçer, yapılan iş kalır.",
    "Dürüst emek, en sağlam yatırımdır.",
    "Hata, ilerleyenin ayak izidir.",
    "Erteleme, küçük işleri büyütür.",
    "Bir adım at; yol kendini gösterir.",
    "Detaya özen, güvenin temelidir.",
    "Bugünü iyi yönet, gelecek kendini yönetir.",
    "Vazgeçmek dışında her şey çözülebilir.",
    "Sakin kafa, hızlı çözüm bulur.",
    "Bildiğini paylaş, ekibinle büyürsün.",
    "Önce ölç, sonra kes; iki kez çalışma.",
    "Bugünün küçük disiplini, yarının büyük rahatı.",
    "İşini sev, iş de seni kollar.",
]


def get_gunun_sozu():
    """Güne göre değişen kısa motivasyon cümlesi."""
    return _SOZLER[_dt.date.today().toordinal() % len(_SOZLER)]


# Türkiye resmi tatilleri — 1. günleri (dini bayram tarihleri 2026-2028 için doğrulandı)
_TATILLER = [
    ("2026-07-15", "Demokrasi ve Millî Birlik Günü"),
    ("2026-08-30", "Zafer Bayramı"),
    ("2026-10-29", "Cumhuriyet Bayramı"),
    ("2027-01-01", "Yılbaşı"),
    ("2027-03-09", "Ramazan Bayramı"),
    ("2027-04-23", "Ulusal Egemenlik ve Çocuk Bayramı"),
    ("2027-05-01", "Emek ve Dayanışma Günü"),
    ("2027-05-16", "Kurban Bayramı"),
    ("2027-05-19", "Gençlik ve Spor Bayramı"),
    ("2027-07-15", "Demokrasi ve Millî Birlik Günü"),
    ("2027-08-30", "Zafer Bayramı"),
    ("2027-10-29", "Cumhuriyet Bayramı"),
    ("2028-01-01", "Yılbaşı"),
    ("2028-02-27", "Ramazan Bayramı"),
    ("2028-04-23", "Ulusal Egemenlik ve Çocuk Bayramı"),
    ("2028-05-01", "Emek ve Dayanışma Günü"),
    ("2028-05-05", "Kurban Bayramı"),
    ("2028-05-19", "Gençlik ve Spor Bayramı"),
    ("2028-07-15", "Demokrasi ve Millî Birlik Günü"),
    ("2028-08-30", "Zafer Bayramı"),
    ("2028-10-29", "Cumhuriyet Bayramı"),
]


def get_yaklasan_tatil():
    """Bugün veya sonrasındaki ilk resmi tatil.
    → {'ad': str, 'tarih': date, 'kalan_gun': int, 'bugun': bool} | None."""
    bugun = _dt.date.today()
    for ts, ad in _TATILLER:
        try:
            d = _dt.date.fromisoformat(ts)
        except Exception:
            continue
        if d >= bugun:
            return {"ad": ad, "tarih": d, "kalan_gun": (d - bugun).days, "bugun": d == bugun}
    return None


def get_mola_ipucu():
    """Saate göre kısa mola / su / wellness hatırlatması."""
    h = _dt.datetime.now().hour
    if h < 6:
        return "Geç oldu, dinlenmeyi unutma 🌙"
    if h < 10:
        return "Güne bir bardak su ile başla 💧"
    if h < 12:
        return "Kısa bir ara ver, biraz su iç 💧"
    if h < 14:
        return "Öğle molası — biraz hareket et 🚶"
    if h < 16:
        return "Gözlerini dinlendir: 20 saniye uzağa bak 👀"
    if h < 18:
        return "Bir bardak su daha, dinç kal 💧"
    if h < 22:
        return "Gününü topla, derin bir nefes al 🌿"
    return "Geç oldu, dinlenmeyi unutma 🌙"
