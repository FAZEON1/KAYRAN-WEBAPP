"""Pratik tarih aralığı seçici — tek tık önayar + gerektiğinde özel takvim.

Kullanım:
    from shared.tarih import hizli_tarih_araligi
    bas, bit = hizli_tarih_araligi("p", varsayilan="Bu ay")
    satislar = get_satislar(bas, bit)
"""
import datetime as _dt
import streamlit as st


def _bugun():
    try:
        from shared.utils import tr_today
        return tr_today()
    except Exception:
        return _dt.date.today()


# Sık kullanılan dönemler — tek tıkla
ONAYARLAR = [
    "Bugün", "Dün", "Bu hafta", "Bu ay", "Geçen ay",
    "Son 30 gün", "Son 90 gün", "Bu yıl", "Geçen yıl", "Tümü", "Özel…",
]


def _aralik(secim, bugun, min_tarih):
    if secim == "Bugün":
        return bugun, bugun
    if secim == "Dün":
        d = bugun - _dt.timedelta(days=1)
        return d, d
    if secim == "Bu hafta":
        return bugun - _dt.timedelta(days=bugun.weekday()), bugun
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


def hizli_tarih_araligi(key, varsayilan="Bu ay", min_tarih=None, etiket=None):
    """Tek satır önayar (tek tık) + sadece 'Özel…' seçilince takvim.
    Döner: (bas_date, bit_date). Her zaman geçerli bir aralık döndürür."""
    bugun = _bugun()
    try:
        idx = ONAYARLAR.index(varsayilan)
    except ValueError:
        idx = ONAYARLAR.index("Bu ay")

    if etiket:
        st.caption(etiket)
    secim = st.radio("Dönem", ONAYARLAR, horizontal=True, index=idx,
                     key=f"{key}_onayar", label_visibility="collapsed")

    hesap = _aralik(secim, bugun, min_tarih)
    if hesap is not None:
        return hesap

    # Özel aralık — tek takvimde başlangıç + bitiş
    secilen = st.date_input("Özel aralık", value=(bugun.replace(day=1), bugun),
                            key=f"{key}_ozel", label_visibility="collapsed",
                            format="DD.MM.YYYY")
    if isinstance(secilen, (tuple, list)):
        if len(secilen) == 2:
            return secilen[0], secilen[1]
        if len(secilen) == 1:  # kullanıcı henüz bitişi seçmedi
            return secilen[0], secilen[0]
        return bugun, bugun
    return secilen, secilen
