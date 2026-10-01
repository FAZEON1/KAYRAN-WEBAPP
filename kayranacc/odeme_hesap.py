# -*- coding: utf-8 -*-
"""Muhasebe — ödeme hesap katmanı (SAF: veritabanına ve ekrana dokunmaz).

Bu Hafta ve Genel Bakış'taki özet rakamlar buradan gelir.
Hafta sonu tahmini (Genel Bakış ile AYNI formül):
    TL banka bakiyesi − bekleyen TL − bekleyen USD × kur
"""
from datetime import date, timedelta

GUN = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
# Ödeme kategorisi anahtarı → ekranda görünen ad (main.KATEGORILER ile aynı).
# Cari Ekstre gibi ekranlar ham anahtarı ("kart") gösteriyordu.
KATEGORI_AD = {"cek": "Çek", "kredi": "Kredi", "kart": "K.Kartı", "vergi": "Vergi", "sgk": "SGK",
               "kira": "Kira", "sabit": "Sabit Gider", "cari": "Cari Hesap", "ithalat": "İthalat",
               "ihracat": "İhracat", "masraf": "Masraf", "maas": "Maaş", "diger": "Diğer"}
# Kısaltma: ilk 3 harf DEĞİL (Pazartesi ve Pazar ikisi de "Paz" olurdu)
GUN_KISA = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
AY = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
      "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _tarih(v):
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def odendi_mi(o):
    return str(o.get("durum") or "") == "odendi"


def vade_durumu(o, bugun):
    """'odendi' | 'gecikmis' | 'bugun' | 'yarin' | 'ileri' | 'tarihsiz'"""
    if odendi_mi(o):
        return "odendi"
    v = _tarih(o.get("vade"))
    if v is None:
        return "tarihsiz"
    if v < bugun:
        return "gecikmis"
    if v == bugun:
        return "bugun"
    if v == bugun + timedelta(days=1):
        return "yarin"
    return "ileri"


def gun_basligi(iso, bugun):
    """'2026-09-28' → 'Pazartesi, 28 Eylül' (+ 'Bugün'/'Yarın'/'Dün' öneki). Ay adı TÜRKÇE
    (eskiden strftime('%B') İngilizce yazıyordu: '28 September 2026')."""
    d = _tarih(iso)
    if d is None:
        return "Vadesiz"
    yil = f" {d.year}" if d.year != bugun.year else ""
    t = f"{GUN[d.weekday()]}, {d.day} {AY[d.month]}{yil}"
    on = {0: "Bugün · ", 1: "Yarın · ", -1: "Dün · "}.get((d - bugun).days, "")
    return on + t


def ozet(odemeler, bankalar, kur, bugun):
    tl = sum(_f(o.get("tutar_tl")) for o in odemeler)
    usd = sum(_f(o.get("tutar_usd")) for o in odemeler)
    od_tl = sum(_f(o.get("tutar_tl")) for o in odemeler if odendi_mi(o))
    od_usd = sum(_f(o.get("tutar_usd")) for o in odemeler if odendi_mi(o))
    bek = [o for o in odemeler if not odendi_mi(o)]
    gec = [o for o in bek if vade_durumu(o, bugun) == "gecikmis"]
    bug = [o for o in bek if vade_durumu(o, bugun) == "bugun"]
    banka_tl = sum(_f(b.get("bakiye")) for b in bankalar if b.get("para_birimi") == "TL")
    bek_tl, bek_usd = tl - od_tl, usd - od_usd
    return {
        "adet": len(odemeler), "odendi_adet": len(odemeler) - len(bek),
        "tl": tl, "usd": usd, "odendi_tl": od_tl, "odendi_usd": od_usd,
        "bekleyen_tl": bek_tl, "bekleyen_usd": bek_usd,
        "gecikmis": gec, "bugun": bug,
        "gecikmis_tl": sum(_f(o.get("tutar_tl")) for o in gec),
        "gecikmis_usd": sum(_f(o.get("tutar_usd")) for o in gec),
        "bugun_tl": sum(_f(o.get("tutar_tl")) for o in bug),
        "bugun_usd": sum(_f(o.get("tutar_usd")) for o in bug),
        "banka_tl": banka_tl,
        "hafta_sonu_tl": banka_tl - bek_tl - bek_usd * _f(kur),
    }


def gunlere_bol(odemeler, oncelik=None):
    """[(vade 'YYYY-AA-GG', [ödeme…])] — vade sırasıyla; gün içinde önce bekleyenler,
    sonra kategori önceliği (oncelik: {kategori: sıra})."""
    oncelik = oncelik or {}
    g = {}
    for o in odemeler:
        g.setdefault(str(o.get("vade") or "")[:10], []).append(o)
    out = []
    for gun in sorted(g, key=lambda d: (d == "", d)):
        liste = sorted(g[gun], key=lambda o: (odendi_mi(o), oncelik.get(o.get("kategori") or "diger", 99),
                                              -(_f(o.get("tutar_tl")) + _f(o.get("tutar_usd")) * 40)))
        out.append((gun, liste))
    return out


def gun_toplam(liste):
    bek = [o for o in liste if not odendi_mi(o)]
    return {"tl": sum(_f(o.get("tutar_tl")) for o in liste), "usd": sum(_f(o.get("tutar_usd")) for o in liste),
            "bekleyen": len(bek), "bek_tl": sum(_f(o.get("tutar_tl")) for o in bek),
            "bek_usd": sum(_f(o.get("tutar_usd")) for o in bek)}
