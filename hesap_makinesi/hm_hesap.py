# -*- coding: utf-8 -*-
"""Hesap Makinesi — saf hesaplar (Ekim 2026). Formüller eski ekran kodundakiyle
BİREBİR aynı; yalnız tek yerde toplandı ve test edildi (tests/test_hesap_makinesi.py).
"""


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


# ── Ürün kârlılık ───────────────────────────────────────────────────
def karlilik(alis, masraf_tipi, masraf, satis, indirim=0.0):
    """Marj satış fiyatı üzerinden. İndirimli fiyat 0 ya da altıysa hesaplanmaz."""
    alis, masraf, satis, indirim = _f(alis), _f(masraf), _f(satis), _f(indirim)
    maliyet = alis * (1 + masraf / 100) if masraf_tipi == "%" else alis + masraf
    kar = satis - maliyet
    marj = (kar / satis * 100) if satis > 0 else 0.0
    r = {"maliyet": maliyet, "kar": kar, "marj": marj, "ind_satis": None, "ind_kar": None, "ind_marj": None}
    if indirim > 0 and satis - indirim > 0:
        r["ind_satis"] = satis - indirim
        r["ind_kar"] = r["ind_satis"] - maliyet
        r["ind_marj"] = r["ind_kar"] / r["ind_satis"] * 100
    return r


# ── Kırılma noktası ─────────────────────────────────────────────────
PERIYOT_GUN = {"Günlük": 1, "Haftalık": 7, "Aylık": 30, "Yıllık": 365}


def kirilma(gider, marj, mevcut, ort_fiyat, periyot):
    """Hedef ciro = sabit gider ÷ marj. Günlük: kalan ciro, dönem boyunca gün başına."""
    gider, marj, mevcut, ort_fiyat = _f(gider), _f(marj), _f(mevcut), _f(ort_fiyat)
    hedef = gider / (marj / 100) if marj > 0 else 0.0
    kalan = max(0.0, hedef - mevcut)
    return {
        "hedef": hedef, "kalan": kalan, "asildi": hedef > 0 and mevcut >= hedef,
        "fazla": max(0.0, mevcut - hedef),
        "ilerleme": (min(1.0, mevcut / hedef) * 100) if hedef > 0 else 0.0,
        "hedef_adet": (hedef / ort_fiyat) if ort_fiyat > 0 else None,
        "kalan_adet": (kalan / ort_fiyat) if ort_fiyat > 0 else None,
        "gunluk": kalan / PERIYOT_GUN.get(periyot, 30),
    }


# ── Prim: Gökhan Yavuz ──────────────────────────────────────────────
def gokhan_prim(aylik_maas, baz_kat, kasa_hedef, kasa_gercek, kasa_ciro, sog_hedef, sog_gercek, sog_ciro, kur):
    """Prim = baz hakediş (maaş × katsayı) + ciro ağırlıklı bonus.
    Çarpan = gerçekleşen ÷ hedef; ağırlık = ciro payı (ciro yoksa yarı yarıya);
    bonus = max(0, ağırlıklı çarpan − 1) × baz."""
    kasa_c = (_f(kasa_gercek) / _f(kasa_hedef)) if _f(kasa_hedef) > 0 else 0.0
    sog_c = (_f(sog_gercek) / _f(sog_hedef)) if _f(sog_hedef) > 0 else 0.0
    top_ciro = _f(kasa_ciro) + _f(sog_ciro)
    kp = (_f(kasa_ciro) / top_ciro) if top_ciro > 0 else 0.5
    sp = (_f(sog_ciro) / top_ciro) if top_ciro > 0 else 0.5
    baz = _f(baz_kat) * _f(aylik_maas)
    agirlikli = kasa_c * kp + sog_c * sp
    bonus = max(0.0, agirlikli - 1.0) * baz
    return {"baz": baz, "kasa_carpan": kasa_c, "sog_carpan": sog_c, "kasa_pay": kp, "sog_pay": sp,
            "agirlikli": agirlikli, "bonus": bonus, "toplam": baz + bonus,
            "toplam_ciro": top_ciro, "toplam_ciro_tl": top_ciro * _f(kur),
            "kasa_ciro_tl": _f(kasa_ciro) * _f(kur), "sog_ciro_tl": _f(sog_ciro) * _f(kur)}


# ── Prim: Ayhan Eroğlu ──────────────────────────────────────────────
def ayhan_prim(mon_oran, kasa_oran, ek_usd, ssd_oran, kur, mon_ciro, kasa_ciro, ssd_ciro, ek_adet):
    """Monitör / kasa / SSD&RAM: ciro × oran %; ekran kartı: adet × birim USD; toplam × kur."""
    mon = _f(mon_ciro) * _f(mon_oran) / 100
    kasa = _f(kasa_ciro) * _f(kasa_oran) / 100
    ek = _f(ek_adet) * _f(ek_usd)
    ssd = _f(ssd_ciro) * _f(ssd_oran) / 100
    top = mon + kasa + ek + ssd
    return {"mon": mon, "kasa": kasa, "ek": ek, "ssd": ssd, "toplam_usd": top, "toplam_tl": top * _f(kur)}


# ── Ödeme geçmişi ───────────────────────────────────────────────────
def _norm(s):
    return " ".join(str(s or "").split()).casefold()


def donem_var_mi(gecmis, donem):
    """Aynı dönem için kayıt var mı (büyük/küçük harf ve boşluk farkı yok sayılır)."""
    n = _norm(donem)
    return bool(n) and any(_norm(r.get("donem")) == n for r in gecmis or [])
