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

_TIMEOUT = 4


# ─────────────────────────────────────────────────────────────────────
# PARALEL ÇEKİM (performans)
#
# SORUN : Döviz → Altın → Hava SIRAYLA çekiliyordu (altın, dövizi bekliyordu).
#         Her biri 6 sn timeout → cache boşken ana sayfa en kötü 18 sn kilitli.
# ÇÖZÜM : Üçü de AYNI ANDA çekilir (3 iş parçacığı) ve tek cache'te tutulur.
#         En kötü senaryo 18 sn → 4 sn. Ağ hatasında davranış aynı: boş/None.
#
# NOT   : Aşağıdaki _ham_* fonksiyonları önbelleksizdir — iş parçacığı içinde
#         Streamlit cache'i çağırmak güvenli olmadığı için kasıtlı böyle.
#         Önbellek, ana iş parçacığındaki get_gunluk_veri() üzerindedir.
# ─────────────────────────────────────────────────────────────────────
def _ham_doviz():
    """Ham USD/EUR çekimi (önbelleksiz, iş parçacığı güvenli)."""
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


def _ham_ons_altin():
    """Ham ons altın fiyatı (USD). TL çevrimi sonradan yapılır."""
    if not requests:
        return None
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=_TIMEOUT)
        return float((r.json() or {}).get("price"))
    except Exception:
        return None


def _ham_hava(lat, lon, sehir):
    """Ham hava durumu çekimi (önbelleksiz, iş parçacığı güvenli)."""
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


@st.cache_data(ttl=1800, show_spinner=False)
def get_gunluk_veri(lat=None, lon=None, sehir=None):
    """Döviz + altın + hava — ÜÇÜ BİRDEN, PARALEL. Tek ağ turu, tek önbellek."""
    lat = VARSAYILAN_LAT if lat is None else lat
    lon = VARSAYILAN_LON if lon is None else lon
    sehir = VARSAYILAN_SEHIR if sehir is None else sehir

    doviz, ons, hava = {}, None, None
    try:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=3) as havuz:
            f_doviz = havuz.submit(_ham_doviz)
            f_ons = havuz.submit(_ham_ons_altin)
            f_hava = havuz.submit(_ham_hava, lat, lon, sehir)
            doviz, ons, hava = f_doviz.result(), f_ons.result(), f_hava.result()
    except Exception:
        # İş parçacığı kurulamazsa (çok nadir) sıralı çekime düş — çalışmaya devam
        doviz, ons, hava = _ham_doviz(), _ham_ons_altin(), _ham_hava(lat, lon, sehir)

    # Gram altın = (ons USD / 31.1034768) × USD-TL  — çevrim burada, çekim sonrası
    usd_try = doviz.get("USD")
    gram_altin = (ons / 31.1034768 * usd_try) if (ons and usd_try) else None

    return {"doviz": doviz, "gram_altin": gram_altin, "hava": hava}


# ── Eski arayüz korunur: çağıranların hiçbiri değişmez ───────────────
# Üçü de tek önbellekli paralel çekimden okur → toplam 1 ağ turu.

def get_doviz():
    """1 USD ve 1 EUR kaç TL? → {'USD': float, 'EUR': float}. Hata → {}."""
    return get_gunluk_veri(None, None, None).get("doviz", {})


def get_gram_altin():
    """Gram altın fiyatı (TL). Hata → None."""
    return get_gunluk_veri(None, None, None).get("gram_altin")


def get_hava(lat=None, lon=None, sehir=None):
    """{'sicaklik': int, 'durum': str, 'ikon': str, 'sehir': str}. Hata → None.

    NOT: Üç sarmalayıcı da get_gunluk_veri'yi BİREBİR aynı imzayla çağırır
    (None, None, None) — Streamlit önbelleği argümanlara göre anahtarladığı
    için, ancak böyle tek bir çekim paylaşılır. Açıkça lat/lon geçilirse o
    konum için ayrı çekim yapılır (eski davranış korunur).
    """
    return get_gunluk_veri(lat, lon, sehir).get("hava")


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
