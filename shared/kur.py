# -*- coding: utf-8 -*-
"""KUR — tek kaynak (Ekim 2026).

EUR→USD eskiden ekrandan ekrana sabitti: bankalar 1,08, Toplam Aktifler cari kuralı 1,10, Ref No ise
canlı kur. Artık hepsi eur_usd()'den gelir: güncel kur (open.er-api.com, saatlik önbellek); alınamazsa
YEDEK (1,08) — ekran yine açılır. USD/TL kaydı kayranacc.database.get_kur'da (kur_gunluk) kalır.

Testlerde ağa çıkılmasın diye KAYRAN_KUR_CEVRIMDISI=1 ortam değişkeni yedeği döndürür."""
import os

import streamlit as st

YEDEK_EUR_USD = 1.08


def _cevrimdisi():
    return str(os.environ.get("KAYRAN_KUR_CEVRIMDISI") or "").strip() not in ("", "0")


@st.cache_data(ttl=3600, show_spinner=False)
def _eur_usd_canli():
    import requests
    d = requests.get("https://open.er-api.com/v6/latest/EUR", timeout=6).json()
    return float(d["rates"]["USD"])


def eur_usd():
    """1 EUR kaç USD. Güncel kur; alınamazsa ya da akla yatkın değilse (0,5–2,5 dışı) YEDEK_EUR_USD."""
    if _cevrimdisi():
        return YEDEK_EUR_USD
    try:
        v = float(_eur_usd_canli())
        return v if 0.5 < v < 2.5 else YEDEK_EUR_USD
    except Exception as _e:
        try:
            from shared.kayit import sessiz
            sessiz("shared.kur.eur_usd", _e, "debug")
        except Exception:
            pass
        return YEDEK_EUR_USD


def usd_try(tarih=None):
    """USD/TL — kur_gunluk'taki kayıt (tarih verilirse o günün, yoksa en son). Bulunamazsa None."""
    try:
        from kayranacc.database import get_kur
        k = get_kur(tarih)
        return float(k) if k and float(k) > 0 else None
    except Exception:
        return None


def banka_karsiligi(pb, tutar_tl=0.0, tutar_usd=0.0, kur=None, eur=None):
    """Bir ödemenin (TL + USD kısmı) banka hesabının para biriminde karşılığı.

    kur: USD/TL. Gerekip de yoksa (TL bankadan USD ödeme, USD bankadan TL ödeme, EUR bankadan TL ödeme)
    None döner — eskiden kur yoksa 1,0 kabul ediliyor, 100 USD TL bankadan ₺100 düşülüyordu.
    eur: 1 EUR kaç USD (verilmezse eur_usd()). EUR bankadan ödeme eskiden yalnız TL kısmını düşüyordu
    (USD ödemede bakiye değişmiyordu); artık TL+USD toplamının EUR karşılığı."""
    tl = float(tutar_tl or 0)
    usd = float(tutar_usd or 0)
    k = float(kur) if kur and float(kur) > 0 else None
    pb = str(pb or "").upper().strip()
    if pb == "TL":
        if usd and not k:
            return None
        return tl + (usd * k if usd else 0.0)
    if pb == "USD":
        if tl and not k:
            return None
        return usd + (tl / k if tl else 0.0)
    if pb == "EUR":
        if tl and not k:
            return None
        e = float(eur) if eur and float(eur) > 0 else eur_usd()
        return (usd + (tl / k if tl else 0.0)) / e
    return tl                      # bilinmeyen para birimi: eski davranış
