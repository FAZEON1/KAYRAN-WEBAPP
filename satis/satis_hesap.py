# -*- coding: utf-8 -*-
"""Satış — hesap katmanı (SAF: veritabanına ve ekrana dokunmaz).

Satışlar ekranı ve Satış Girişi'ndeki "son siparişler" listesi buradan beslenir.
Satış satırları (kalem) SİPARİŞE göre gruplanır: kullanıcı bir siparişi tek
satırda görür (firma · kalem · adet · ciro · kâr), tıklayınca kalemlerine iner.

Kâr hesabı satis.database.satir_kar ile AYNIDIR (parametre olarak verilir):
destekler satış fiyatından düşülür → net satış; marj = net kâr / net satış.
"""
from datetime import date

AY = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
      "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
GUN = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def _anahtar_kucuk(s):
    """Arama anahtarı: i/ı/İ/I aynı sayılır (ürün adları noktasız I'lı büyütülüyor)."""
    return str(s or "").replace("İ", "i").replace("I", "i").lower().replace("ı", "i")


def siparis_grupla(satislar, satir_kar):
    """Kalemleri siparişlere toplar. Sipariş no'su boş kalemler tek başına bir sipariş sayılır.
    Döner: [{siparis_no, tarih, kanal, kalemler[], kalem, adet, ciro, maliyet, destek,
             net_kar, marj, maliyetsiz}] — en yeni tarih ve sipariş üstte."""
    g = {}
    for s in satislar or []:
        sno = str(s.get("siparis_no") or "").strip()
        anahtar = sno or f"#kalem-{s.get('id')}"
        o = g.setdefault(anahtar, {"siparis_no": sno, "tarih": str(s.get("tarih") or "")[:10],
                                   "kanal": str(s.get("kanal") or "").strip(), "kalemler": [],
                                   "adet": 0, "ciro": 0.0, "maliyet": 0.0, "destek": 0.0,
                                   "net_kar": 0.0, "maliyetsiz": 0})
        k = satir_kar(s)
        o["kalemler"].append(s)
        o["adet"] += int(k["adet"] or 0)
        for f in ("ciro", "maliyet", "destek", "net_kar"):
            o[f] += float(k[f] or 0)
        if float(s.get("birim_maliyet") or 0) <= 0 and float(s.get("birim_satis") or 0) > 0:
            o["maliyetsiz"] += 1
        t = str(s.get("tarih") or "")[:10]
        if t > o["tarih"]:
            o["tarih"] = t
    out = []
    for o in g.values():
        ns = o["ciro"] - o["destek"]
        o["marj"] = (o["net_kar"] / ns * 100) if ns > 0 else None
        o["kalem"] = len(o["kalemler"])
        out.append(o)
    out.sort(key=lambda o: (o["tarih"], o["siparis_no"]), reverse=True)
    return out


def ara(siparisler, metin="", kanal="Tümü"):
    """Sipariş no · firma · SKU · ürün adında arar; firma filtresi uygular."""
    a = _anahtar_kucuk(metin).strip()
    out = []
    for o in siparisler:
        if kanal != "Tümü" and o["kanal"] != kanal:
            continue
        if a:
            havuz = _anahtar_kucuk(" ".join([o["siparis_no"], o["kanal"]] + [
                f"{k.get('sku', '')} {k.get('urun_adi', '')}" for k in o["kalemler"]]))
            if a not in havuz:
                continue
        out.append(o)
    return out


def gun_adi(iso, bugun=None):
    """'2026-10-01' → 'Bugün' / 'Dün' / '29 Eylül, Salı' (yıl farklıysa yıl da)."""
    try:
        d = date.fromisoformat(str(iso)[:10])
    except ValueError:
        return "Tarihsiz"
    bugun = bugun or date.today()
    if d == bugun:
        return "Bugün"
    if (bugun - d).days == 1:
        return "Dün"
    yil = f" {d.year}" if d.year != bugun.year else ""
    return f"{d.day} {AY[d.month]}{yil}, {GUN[d.weekday()]}"


def gunlere_bol(siparisler):
    """[(tarih 'YYYY-AA-GG', [sipariş…])] — sırayı korur."""
    out, son = [], None
    for o in siparisler:
        if o["tarih"] != son:
            out.append((o["tarih"], []))
            son = o["tarih"]
        out[-1][1].append(o)
    return out


def toplam(siparisler):
    t = {"siparis": len(siparisler), "adet": 0, "ciro": 0.0, "maliyet": 0.0, "destek": 0.0, "net_kar": 0.0}
    for o in siparisler:
        for f in ("adet", "ciro", "maliyet", "destek", "net_kar"):
            t[f] += o[f]
    ns = t["ciro"] - t["destek"]
    t["marj"] = (t["net_kar"] / ns * 100) if ns > 0 else None
    return t
