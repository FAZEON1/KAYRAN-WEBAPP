# -*- coding: utf-8 -*-
"""Ref No Takibi — hesap katmanı (SAF: veritabanına ve ekrana dokunmaz).

Eski ekranın "Toplam Tutar" kutusu farklı para birimlerini yan yana yazıyor,
en büyük SAYIYI öne çıkarıyordu (₺1.543.786 büyük, $177.368 küçük) — gerçek
toplam hiçbir yerde görünmüyordu. Burada her ref USD karşılığına çevrilir
(TL: kayıtlı günlük kur, EUR: güncel EUR/USD); kur yoksa o tutar toplama
katılmaz ve bu açıkça raporlanır (sessizce yanlış toplam yok).

Liste firma adına göre değil DÖNEME göre gruplanır (en yeni ay üstte):
ref'ler ayların hakedişi olduğu için iş akışı aylıktır.
"""
import json

DURUMLAR = ["beklemede", "paylasildi", "iptal"]
DURUM_AD = {"beklemede": "Beklemede", "paylasildi": "Paylaşıldı", "iptal": "İptal"}
DURUM_RENK = {"beklemede": "amber", "paylasildi": "yesil", "iptal": "silik"}
AY_AD = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
         "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
SEMBOL = {"USD": "$", "TL": "₺", "TRY": "₺", "EUR": "€"}


def _f(v):
    try:
        return float(str(v).replace(",", "").strip()) if v not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def doviz(r):
    d = str(r.get("doviz") or "USD").strip().upper()
    return "TL" if d in ("TRY", "₺") else ("EUR" if d in ("EURO", "€") else d)


def usd(tutar, dvz, eur_usd=None, usd_try=None):
    """Tutarın USD karşılığı; çevrilemiyorsa None."""
    t = _f(tutar)
    if dvz == "USD":
        return t
    if dvz == "EUR":
        return t * eur_usd if eur_usd else None
    if dvz == "TL":
        return t / usd_try if usd_try else None
    return None


def aylik(r):
    a = r.get("aylik") or {}
    if isinstance(a, str):
        try:
            a = json.loads(a) if a.strip() else {}
        except ValueError:
            a = {}
    return a if isinstance(a, dict) else {}


def donem(r):
    """Ref'in dönemi 'YYYY-AA' (aylık kırılımın İLK ayı; yoksa kayıt tarihi)."""
    a = sorted(k for k in aylik(r) if len(str(k)) >= 7)
    if a:
        return str(a[0])[:7]
    t = str(r.get("tarih") or "")[:7]
    return t if len(t) == 7 and t[4] == "-" else ""


def donem_adi(d):
    try:
        y, m = d.split("-")
        return f"{AY_AD[int(m)]} {y}"
    except (ValueError, IndexError, AttributeError):
        return "Dönemsiz"


def donem_metni(r):
    """'Eylül 2026' ya da çok aylıysa 'Ağustos – Ekim 2026'."""
    a = sorted(k for k in aylik(r) if len(str(k)) >= 7)
    if len(a) > 1:
        b, e = donem_adi(a[0][:7]), donem_adi(a[-1][:7])
        if b.split()[-1] == e.split()[-1]:
            b = b.rsplit(" ", 1)[0]
        return f"{b} – {e}"
    return donem_adi(donem(r)) if donem(r) else "Dönemsiz"


def kategoriler(r):
    return [x.strip() for x in str(r.get("kategori") or "").split("·") if x.strip()]


def toplam(refler, eur_usd=None, usd_try=None):
    """{'usd': çevrilebilenlerin USD toplamı, 'ham': {döviz: tutar}, 'cevrilmeyen': {döviz: tutar}}"""
    ham, cevrilmeyen, u = {}, {}, 0.0
    for r in refler:
        d, t = doviz(r), _f(r.get("tutar"))
        ham[d] = ham.get(d, 0.0) + t
        v = usd(t, d, eur_usd, usd_try)
        if v is None:
            cevrilmeyen[d] = cevrilmeyen.get(d, 0.0) + t
        else:
            u += v
    return {"usd": u, "ham": ham, "cevrilmeyen": cevrilmeyen}


def filtrele(refler, durum="tumu", kategori="Tümü", yil="Tümü", ara=""):
    from shared.utils import tr_kucuk
    a = tr_kucuk(ara)
    out = []
    for r in refler:
        if durum != "tumu" and (r.get("durum") or "beklemede") != durum:
            continue
        if kategori != "Tümü" and kategori not in kategoriler(r):
            continue
        if yil != "Tümü" and not donem(r).startswith(str(yil)):
            continue
        if a and a not in tr_kucuk(f"{r.get('ref_no','')} {r.get('aciklama','')} {r.get('kategori','')} "
                                   f"{r.get('_firma','')} {r.get('tutar','')} {r.get('doviz','')}"):
            continue
        out.append(r)
    return out


def grupla(refler):
    """[(dönem 'YYYY-AA' | '', [ref…])] — en yeni dönem üstte, grup içinde ref no büyükten küçüğe."""
    g = {}
    for r in refler:
        g.setdefault(donem(r), []).append(r)
    sira = sorted([d for d in g if d], reverse=True) + ([""] if "" in g else [])
    return [(d, sorted(g[d], key=lambda r: (str(r.get("ref_no") or "")), reverse=True)) for d in sira]


def firma_ozet(refler):
    """{firma_id: {'adet','beklemede'}}"""
    o = {}
    for r in refler:
        x = o.setdefault(r.get("_fid"), {"adet": 0, "beklemede": 0})
        x["adet"] += 1
        x["beklemede"] += 1 if (r.get("durum") or "beklemede") == "beklemede" else 0
    return o
