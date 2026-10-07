"""Pratik tarih aralığı seçici — tek düğme, kaydırmalı.

Kullanım (değişmedi):
    from shared.tarih import hizli_tarih_araligi
    bas, bit = hizli_tarih_araligi("p", varsayilan="Bu ay")
    satislar = get_satislar(bas, bit)

TASARIM (Ekim 2026, "tek araç çubuğu" — kullanıcı seçimi A):
    [‹] [takvim  Bu ay · 1–7 Eki  ▾] [›]

• Ortadaki düğme bir pencere açar: solda hazır dönemler, sağda takvim (özel aralık).
  Eskiden 5 hap + "Diğer…" açılır listesi + ayrı tarih yazısı iki satıra yayılıyordu.
• Düğmenin yazısı dönemi ve çözülmüş aralığı birlikte söyler ("Bu yıl · 1 Oca – 7 Eki").
• ‹ › okları seçili dönem TÜRÜNDE bir önceki/sonraki döneme atlar:
  "Bu ay" + ‹ → "Eylül 2026", tekrar ‹ → "Ağustos 2026".
• Bulunduğu kabın içine çizilir; Satışlar'da arama ve filtreyle aynı çubuğun parçasıdır.
  Görünüm CSS'i: shared/tasarim.py (st-key-k_donem_*).
"""
from shared.tasarim import tr_sayi  # TR sayı biçimi (1.234,56)
import datetime as _dt
import streamlit as st


def _bugun():
    try:
        from shared.utils import tr_today
        return tr_today()
    except Exception:
        return _dt.date.today()


# Sık kullanılan dönemler
ONAYARLAR = [
    "Bugün", "Dün", "Bu hafta", "Geçen hafta", "Bu ay", "Geçen ay",
    "Son 30 gün", "Son 90 gün", "Bu yıl", "Geçen yıl", "Tümü", "Özel…",
]

# Kaydırma adımı: (birim, miktar). None → o önayar kaydırılamaz.
_KAYDIRMA = {
    "Bugün": ("gun", 1), "Dün": ("gun", 1),
    "Bu hafta": ("hafta", 1), "Geçen hafta": ("hafta", 1),
    "Bu ay": ("ay", 1), "Geçen ay": ("ay", 1),
    "Son 30 gün": ("gun", 30), "Son 90 gün": ("gun", 90),
    "Bu yıl": ("yil", 1), "Geçen yıl": ("yil", 1),
}

def _aralik(secim, bugun, min_tarih):
    if secim == "Bugün":
        return bugun, bugun
    if secim == "Dün":
        d = bugun - _dt.timedelta(days=1)
        return d, d
    if secim == "Bu hafta":
        return bugun - _dt.timedelta(days=bugun.weekday()), bugun
    if secim == "Geçen hafta":
        _bu_pzt = bugun - _dt.timedelta(days=bugun.weekday())
        return _bu_pzt - _dt.timedelta(days=7), _bu_pzt - _dt.timedelta(days=1)
    if secim == "Bu ay":
        return bugun.replace(day=1), bugun
    if secim == "Geçen ay":
        gecen_son = bugun.replace(day=1) - _dt.timedelta(days=1)
        return gecen_son.replace(day=1), gecen_son
    if secim == "Son 30 gün":
        return bugun - _dt.timedelta(days=29), bugun
    if secim == "Son 90 gün":
        return bugun - _dt.timedelta(days=89), bugun
    if secim == "Bu yıl":
        return bugun.replace(month=1, day=1), bugun
    if secim == "Geçen yıl":
        return _dt.date(bugun.year - 1, 1, 1), _dt.date(bugun.year - 1, 12, 31)
    if secim == "Tümü":
        return (min_tarih or _dt.date(2020, 1, 1)), bugun
    return None  # "Özel…" → takvim


def _ay_kaydir(d, n):
    """Tarihi n ay kaydırır. Ayın son gününü taşırmaz (31 Ocak −1 ay = 28/29 Şubat)."""
    y, m = d.year, d.month + n
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    _son = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return _dt.date(y, m, min(d.day, _son))


def _kaydir(bas, bit, secim, adim):
    """Aralığı, önayarın türüne göre `adim` dönem ileri/geri taşır."""
    if not adim:
        return bas, bit
    birim_miktar = _KAYDIRMA.get(secim)
    if not birim_miktar:
        return bas, bit
    birim, miktar = birim_miktar
    if birim == "gun":
        d = _dt.timedelta(days=miktar * adim)
        return bas + d, bit + d
    if birim == "hafta":
        # Geçmiş/gelecek haftaya gidince TAM hafta (Pzt–Paz) döner; "Bu hafta"
        # kısmi olduğu için gün kaydırması yapılsa 3 günlük aralık kalırdı.
        _pzt = bas - _dt.timedelta(days=bas.weekday()) + _dt.timedelta(weeks=miktar * adim)
        return _pzt, _pzt + _dt.timedelta(days=6)
    if birim == "ay":
        _yb = _ay_kaydir(bas.replace(day=1), miktar * adim)
        _sonraki = _ay_kaydir(_yb, 1)
        return _yb, _sonraki - _dt.timedelta(days=1)
    if birim == "yil":
        y = bas.year + miktar * adim
        return _dt.date(y, 1, 1), _dt.date(y, 12, 31)
    return bas, bit


def _tr(d):
    return d.strftime("%d.%m.%Y") if d else "—"


AY_KISA = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
AY_UZUN = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim",
           "Kasım", "Aralık"]


def kisa_aralik(bas, bit, bugun=None):
    """'1–7 Eki' · '8 Eyl – 7 Eki' · '7 Eki' · başka yıl: '1 Oca 2025 – 7 Eki 2026'."""
    bugun = bugun or _bugun()
    if bas.year != bit.year:
        return f"{bas.day} {AY_KISA[bas.month - 1]} {bas.year} – {bit.day} {AY_KISA[bit.month - 1]} {bit.year}"
    yil = "" if bit.year == bugun.year else f" {bit.year}"
    if bas == bit:
        return f"{bit.day} {AY_KISA[bit.month - 1]}{yil}"
    if bas.month == bit.month:
        return f"{bas.day}–{bit.day} {AY_KISA[bit.month - 1]}{yil}"
    return f"{bas.day} {AY_KISA[bas.month - 1]} – {bit.day} {AY_KISA[bit.month - 1]}{yil}"


def donem_coz(secim, kaydir, bugun, min_tarih=None, ozel=None):
    """Seçim + kaydırma (+ özel aralık) → (bas, bit). Her zaman geçerli aralık döner."""
    if secim == "Özel…":
        if isinstance(ozel, (tuple, list)) and ozel:
            bas, bit = ozel[0], ozel[-1]
        else:
            bas, bit = bugun.replace(day=1), bugun
    else:
        bas, bit = _kaydir(*_aralik(secim, bugun, min_tarih), secim, kaydir)
    if min_tarih and bas < min_tarih:
        bas = min_tarih
    if bit < bas:
        bas, bit = bit, bas
    return bas, bit


def donem_etiketi(secim, bas, bit, kaydir=0, bugun=None):
    """Dönem düğmesinin yazısı: 'Bu ay · 1–7 Eki', kaydırılmış ay 'Eylül 2026', yıl '2025'."""
    bugun = bugun or _bugun()
    birim = (_KAYDIRMA.get(secim) or ("", 0))[0]
    if secim == "Tümü":
        return "Tümü"
    if secim == "Özel…":
        return kisa_aralik(bas, bit, bugun)
    if kaydir:
        if birim == "ay":
            return f"{AY_UZUN[bas.month - 1]} {bas.year}"
        if birim == "yil":
            return str(bas.year)
        return kisa_aralik(bas, bit, bugun)
    return f"{secim} · {kisa_aralik(bas, bit, bugun)}"


def hizli_tarih_araligi(key, varsayilan="Bu ay", min_tarih=None, etiket=None, secenekler=None):
    """Dönem seçici (Ekim 2026, "tek araç çubuğu" tasarımı). Döner: (bas_date, bit_date) — her zaman geçerli.

        [‹] [takvim  Bu ay · 1–7 Eki  ▾] [›]

    Ortadaki düğme bir pencere açar: solda hazır dönemler, sağda takvim (özel aralık). Oklar seçili
    dönem TÜRÜNDE bir önceki/sonraki döneme atlar ("Bu ay" ‹ → "Eylül 2026"). Bulunduğu kabın içine
    çizilir: Satışlar'daki araç çubuğu gibi yatay bir kabın içinde çağrılırsa o çubuğun parçası olur.

    secenekler: None ise tüm ONAYARLAR; liste verilirse yalnız onlar (+ takvimden özel aralık).
    """
    bugun = _bugun()
    _liste = [o for o in (secenekler or ONAYARLAR) if o in ONAYARLAR]
    if "Özel…" not in _liste:
        _liste = _liste + ["Özel…"]
    if varsayilan not in _liste:
        varsayilan = _liste[0]

    _sk = f"{key}_secim"       # geçerli önayar
    _kk = f"{key}_kaydir"      # dönem kaydırma sayacı
    _ok = f"{key}_ozel"        # takvim (özel aralık) değeri
    if _sk not in st.session_state:
        st.session_state[_sk] = varsayilan
    if _kk not in st.session_state:
        st.session_state[_kk] = 0

    def _guncel():
        return donem_coz(st.session_state[_sk], st.session_state[_kk], bugun, min_tarih,
                         st.session_state.get(_ok))

    if _ok not in st.session_state:
        st.session_state[_ok] = _guncel()

    # Geri çağrılar betikten ÖNCE çalışır: takvim de seçilen döneme eşitlenir (tek çalışma).
    def _sec(o):
        st.session_state[_sk] = o
        st.session_state[_kk] = 0
        st.session_state[_ok] = _guncel()

    def _kaydir_tik(adim):
        st.session_state[_kk] = st.session_state.get(_kk, 0) + adim
        st.session_state[_ok] = _guncel()

    def _ozel_degisti():
        v = st.session_state.get(_ok)
        if isinstance(v, (tuple, list)) and len(v) == 2:
            st.session_state[_sk] = "Özel…"
            st.session_state[_kk] = 0

    secim = st.session_state[_sk]
    bas, bit = _guncel()
    if etiket:
        st.caption(etiket)
    kaydirilabilir = secim in _KAYDIRMA
    with st.container(key=f"k_donem_{key}", horizontal=True, gap=None, width="content",
                      vertical_alignment="center"):
        st.button("", key=f"{key}_geri", icon=":material/chevron_left:", help="Bir önceki dönem",
                  disabled=not kaydirilabilir, on_click=_kaydir_tik, args=(-1,))
        with st.popover(donem_etiketi(secim, bas, bit, st.session_state[_kk], bugun),
                        icon=":material/calendar_month:", key=f"{key}_pencere"):
            sol, sag = st.columns([1, 1.45], gap="medium")
            with sol.container(key=f"k_donem_liste_{key}", gap=None):
                for i, o in enumerate(o for o in _liste if o != "Özel…"):
                    st.button(o, key=f"{key}_o{i}", width="stretch",
                              type="primary" if o == secim else "tertiary", on_click=_sec, args=(o,))
            with sag:
                st.date_input("Özel aralık", key=_ok, format="DD.MM.YYYY", on_change=_ozel_degisti,
                              min_value=min_tarih)
                st.caption(f"{_tr(bas)} – {_tr(bit)} · {tr_sayi((bit - bas).days + 1)} gün")
        st.button("", key=f"{key}_ileri", icon=":material/chevron_right:", help="Bir sonraki dönem",
                  disabled=not kaydirilabilir, on_click=_kaydir_tik, args=(1,))
    return bas, bit
