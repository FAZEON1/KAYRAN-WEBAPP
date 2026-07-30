"""Pratik tarih aralığı seçici — tek satır, tek tık, kaydırmalı.

Kullanım (değişmedi):
    from shared.tarih import hizli_tarih_araligi
    bas, bit = hizli_tarih_araligi("p", varsayilan="Bu ay")
    satislar = get_satislar(bas, bit)

TASARIM NOTU
------------
Eski sürüm st.radio'yu CSS ile hapa dönüştürüyordu:
    [role="radiogroup"] label>div:first-child{display:none}
Streamlit iç yapısını değiştirdiğinde bu seçici tutmaz oldu ve radyo
daireleri görünmeye başladı — bileşen tasarlandığı gibi bile çizilmiyordu.

Artık CSS numarası yok. Streamlit 1.40+ ile gelen YERLEŞİK st.pills
kullanılıyor; sürüm yükseltmelerinde kırılmaz.

Yerleşim (tek satır, ~36 px — eskisi iki sıra ve ~100 px idi):
    [Bugün|Bu ay|Geçen ay|Son 30 g|Bu yıl]  [Diğer ▾]  [‹ ›]  01.01–29.07 · 210 gün

• Sık kullanılan 5 önayar hap olarak — tek tık.
• Kalanlar açılır listede — sıra taşması yok.
• ‹ › okları seçili dönem TÜRÜNDE bir önceki/sonraki döneme atlar.
  "Bu ay" + ‹ → geçen ay, tekrar ‹ → ondan öncesi. Eskiden geçen aydan
  öncesine gitmek için Özel takvim açmak gerekiyordu.
• Çözülmüş aralık her zaman yazılı — "Bu yıl"ın hangi tarihleri kapsadığı
  eskiden hiç görünmüyordu.
"""
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

# Hap olarak gösterilenler — tek sıraya sığacak kadar
HIZLI = ["Bugün", "Bu ay", "Geçen ay", "Son 30 gün", "Bu yıl"]

# Kaydırma adımı: (birim, miktar). None → o önayar kaydırılamaz.
_KAYDIRMA = {
    "Bugün": ("gun", 1), "Dün": ("gun", 1),
    "Bu hafta": ("hafta", 1), "Geçen hafta": ("hafta", 1),
    "Bu ay": ("ay", 1), "Geçen ay": ("ay", 1),
    "Son 30 gün": ("gun", 30), "Son 90 gün": ("gun", 90),
    "Bu yıl": ("yil", 1), "Geçen yıl": ("yil", 1),
}

_KISA = {"Son 30 gün": "Son 30 g", "Son 90 gün": "Son 90 g"}


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


def hizli_tarih_araligi(key, varsayilan="Bu ay", min_tarih=None, etiket=None, secenekler=None):
    """Tek satır dönem seçici. Döner: (bas_date, bit_date) — her zaman geçerli.

    secenekler: None ise tüm ONAYARLAR; liste verilirse yalnız onlar.
    """
    bugun = _bugun()
    _liste = [o for o in (secenekler or ONAYARLAR) if o in ONAYARLAR]
    if "Özel…" not in _liste:
        _liste = _liste + ["Özel…"]
    if varsayilan not in _liste:
        varsayilan = _liste[0]

    _sk = f"{key}_secim"       # geçerli önayar
    _kk = f"{key}_kaydir"      # dönem kaydırma sayacı
    if _sk not in st.session_state:
        st.session_state[_sk] = varsayilan
    if _kk not in st.session_state:
        st.session_state[_kk] = 0

    _haplar = [o for o in HIZLI if o in _liste]
    _digerler = [o for o in _liste if o not in _haplar]

    def _hap_degisti():
        v = st.session_state.get(f"{key}_hap")
        if v:
            st.session_state[_sk] = v
            st.session_state[_kk] = 0
            st.session_state[f"{key}_dig"] = None

    def _dig_degisti():
        v = st.session_state.get(f"{key}_dig")
        if v:
            st.session_state[_sk] = v
            st.session_state[_kk] = 0
            st.session_state[f"{key}_hap"] = None

    if etiket:
        st.caption(etiket)

    _secim = st.session_state[_sk]
    _kaydirilabilir = _secim in _KAYDIRMA

    c_hap, c_dig, c_geri, c_ileri, c_bilgi = st.columns(
        [len(_haplar) * 0.62 or 1, 1.05, 0.20, 0.20, 1.6],
        vertical_alignment="center")

    with c_hap:
        st.pills("Dönem", _haplar, selection_mode="single",
                 default=(_secim if _secim in _haplar else None),
                 format_func=lambda x: _KISA.get(x, x),
                 key=f"{key}_hap", on_change=_hap_degisti,
                 label_visibility="collapsed")
    with c_dig:
        st.selectbox("Diğer", _digerler,
                     index=(_digerler.index(_secim) if _secim in _digerler else None),
                     placeholder="Diğer…", key=f"{key}_dig",
                     on_change=_dig_degisti, label_visibility="collapsed")
    with c_geri:
        if st.button("‹", key=f"{key}_geri", use_container_width=True,
                     disabled=not _kaydirilabilir,
                     help="Bir önceki döneme"):
            st.session_state[_kk] -= 1
            st.rerun()
    with c_ileri:
        if st.button("›", key=f"{key}_ileri", use_container_width=True,
                     disabled=not _kaydirilabilir,
                     help="Bir sonraki döneme"):
            st.session_state[_kk] += 1
            st.rerun()

    _hesap = _aralik(_secim, bugun, min_tarih)

    if _hesap is None:                      # Özel… → takvim
        with c_bilgi:
            st.caption("takvimden seç →")
        _sec = st.date_input("Özel aralık", value=(bugun.replace(day=1), bugun),
                             key=f"{key}_ozel", label_visibility="collapsed",
                             format="DD.MM.YYYY")
        if isinstance(_sec, (tuple, list)):
            if len(_sec) == 2:
                return _sec[0], _sec[1]
            if len(_sec) == 1:
                return _sec[0], _sec[0]
            return bugun, bugun
        return _sec, _sec

    bas, bit = _kaydir(_hesap[0], _hesap[1], _secim, st.session_state[_kk])
    if min_tarih and bas < min_tarih:
        bas = min_tarih
    if bit < bas:
        bas, bit = bit, bas

    with c_bilgi:
        _gun = (bit - bas).days + 1
        _ofs = st.session_state[_kk]
        _ek = f" · {_ofs:+d} dönem" if _ofs else ""
        st.markdown(
            f'<div style="font-size:12px;font-family:JetBrains Mono,monospace;'
            f'color:#94A3B8;white-space:nowrap;padding-top:2px">'
            f'{_tr(bas)} – {_tr(bit)}<br>'
            f'<span style="color:#7B8AA0">{_gun:,} gün{_ek}</span></div>',
            unsafe_allow_html=True)

    return bas, bit
