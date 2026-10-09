# -*- coding: utf-8 -*-
"""KAYRAN — Yönetim Panosu yardımcıları (Ekim 2026, görünüm B: P&L akışı önde).

SAF: veritabanına gitmez, test edilir (tests/test_yonetim_pano.py). Hesap yine TEK kaynaktan
(yonetim_hesap.pnl_topla); burada yalnız dönem kıyası, 12 aylık trend ayları, tablo satırları,
küçük trend grafiği (SVG) ve Excel sayfaları üretilir. Rakam değiştirmez.

  kiyas_donemleri(yil, donem, bugun) → önceki dönem ve geçen yılın aynı dönemi (bas, bit, aylar)
  trend_aylari(yil, donem, bugun)    → kıyas grafiği için son 12 ay [(yıl, ay_idx)]
  degisim(simdi, once, tersi)        → ▲▼ yüzde, iyi mi
  kucuk_trend_svg(...)               → kart içindeki 12 aylık çizgi (tema renkleri, nokta başına ipucu)
"""
import calendar


AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
AY_KISA = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
CEYREK = {"Q1": (0, 3), "Q2": (3, 6), "Q3": (6, 9), "Q4": (9, 12)}


def _son_gun(yil, ay):
    return calendar.monthrange(yil, ay)[1]


def donem_araligi(yil, donem, bugun=None):
    """(bas, bit, aylar) — aylar: gider ay aralığı [i0, i1). İçinde bulunulan yılın 'Tüm Yıl'ı
    yılbaşından BUGÜNE kadardır (gelecek aylar boş; kıyas aynı aylarla yapılsın diye)."""
    if donem in AYLAR:
        i = AYLAR.index(donem)
        return f"{yil}-{i + 1:02d}-01", f"{yil}-{i + 1:02d}-{_son_gun(yil, i + 1):02d}", (i, i + 1)
    if donem in CEYREK:
        i0, i1 = CEYREK[donem]
        return f"{yil}-{i0 + 1:02d}-01", f"{yil}-{i1:02d}-{_son_gun(yil, i1):02d}", (i0, i1)
    if bugun is not None and yil == bugun.year:
        return f"{yil}-01-01", bugun.isoformat(), (0, bugun.month)
    return f"{yil}-01-01", f"{yil}-12-31", (0, 12)


def _gecen_yil_ayni(yil, donem, bugun):
    """Geçen yılın aynı dönemi. İçinde bulunulan yılın 'Tüm Yıl'ı → geçen yıl aynı güne kadar."""
    if donem not in AYLAR and donem not in CEYREK and bugun is not None and yil == bugun.year:
        gun = min(bugun.day, _son_gun(yil - 1, bugun.month))
        return f"{yil - 1}-01-01", f"{yil - 1}-{bugun.month:02d}-{gun:02d}", (0, bugun.month)
    return donem_araligi(yil - 1, donem)


def kiyas_donemleri(yil, donem, bugun):
    """[(anahtar, etiket, yil, donem, bas, bit, aylar)] — önceki dönem (ay / çeyrek) ve geçen yılın
    aynı dönemi. Yıllık görünümde önceki dönem zaten geçen yıl olduğu için tek kıyas döner."""
    out = []
    if donem in AYLAR:
        i = AYLAR.index(donem)
        py, pi = (yil - 1, 11) if i == 0 else (yil, i - 1)
        b, t, a = donem_araligi(py, AYLAR[pi])
        out.append(("onceki", f"{AYLAR[pi]} {py}", py, AYLAR[pi], b, t, a))
    elif donem in CEYREK:
        q = int(donem[1])
        py, pq = (yil - 1, 4) if q == 1 else (yil, q - 1)
        b, t, a = donem_araligi(py, f"Q{pq}")
        out.append(("onceki", f"{py} Q{pq}", py, f"Q{pq}", b, t, a))
    b, t, a = _gecen_yil_ayni(yil, donem, bugun)
    etiket = (f"{donem} {yil - 1}" if donem in AYLAR else f"{yil - 1} {donem}" if donem in CEYREK
              else f"{yil - 1} aynı dönem")
    out.append(("gecen", etiket, yil - 1, donem, b, t, a))
    return out


def devam_ediyor(yil, donem, bugun):
    """Seçili dönem henüz bitmedi mi (kıyas tam dönemle yapılırken uyarı için)."""
    _b, bit, _a = donem_araligi(yil, donem, bugun)
    return bugun.isoformat() < bit or (donem not in AYLAR and donem not in CEYREK and yil == bugun.year)


def trend_aylari(yil, donem, bugun, n=12):
    """Son n ay [(yıl, ay_idx)] — dönemin son ayında (içinde bulunulan aydan ileri değil) biter."""
    if donem in AYLAR:
        y, i = yil, AYLAR.index(donem)
    elif donem in CEYREK:
        y, i = yil, CEYREK[donem][1] - 1
    else:
        y, i = yil, 11
    if (y, i) > (bugun.year, bugun.month - 1):
        y, i = bugun.year, bugun.month - 1
    out = []
    for _ in range(n):
        out.append((y, i))
        y, i = (y - 1, 11) if i == 0 else (y, i - 1)
    return list(reversed(out))


def degisim(simdi, once, tersi=False):
    """{'oran': %, 'iyi': bool} — önceki 0 ise None (yüzde anlamsız). tersi: azalış iyidir (COGS)."""
    try:
        simdi, once = float(simdi or 0), float(once or 0)
    except (TypeError, ValueError):
        return None
    if not once:
        return None
    o = (simdi - once) / abs(once) * 100.0
    return {"oran": o, "iyi": (o <= 0) if tersi else (o >= 0)}


def kanal_satirlari(kanal):
    top = sum(float(v.get("net_kar", 0) or 0) for v in (kanal or {}).values())
    rows = []
    for kn, v in (kanal or {}).items():
        ciro, nk = float(v.get("ciro", 0) or 0), float(v.get("net_kar", 0) or 0)
        rows.append({"_id": kn, "Kanal": kn, "Adet": int(v.get("adet", 0) or 0), "Ciro ($)": round(ciro, 2),
                     "Net kâr ($)": round(nk, 2), "Marj (%)": round(nk / ciro * 100, 1) if ciro else 0.0,
                     "Kâr payı (%)": round(nk / top * 100, 1) if top else 0.0})
    rows.sort(key=lambda r: -r["Ciro ($)"])
    return rows


def urun_satirlari(urun, adlar=None):
    rows = []
    for su, v in (urun or {}).items():
        ciro, nk = float(v.get("ciro", 0) or 0), float(v.get("net_kar", 0) or 0)
        ad = (adlar or {}).get(su) or v.get("urun_adi") or ""
        rows.append({"_id": su, "SKU": su, "Ürün": ad, "Adet": int(v.get("adet", 0) or 0),
                     "Ciro ($)": round(ciro, 2), "Net kâr ($)": round(nk, 2),
                     "Marj (%)": round(nk / ciro * 100, 1) if ciro else 0.0})
    rows.sort(key=lambda r: -r["Net kâr ($)"])
    return rows


def destek_satirlari(tur_usd):
    top = sum(float(v or 0) for v in (tur_usd or {}).values())
    rows = [{"_id": t, "Tür": t, "Tutar ($)": round(float(v or 0), 2),
             "Pay (%)": round(float(v or 0) / top * 100, 1) if top else 0.0}
            for t, v in (tur_usd or {}).items()]
    rows.sort(key=lambda r: -r["Tutar ($)"])
    return rows


def gider_satirlari(kat):
    """Aylık gider tablosu (TL): kategori satırları + Σ."""
    rows, top = [], [0.0] * 12
    for k in ("Sabit", "Değişken", "Yarı Değişken"):
        v = [float(x or 0) for x in (list((kat or {}).get(k) or []) + [0.0] * 12)[:12]]
        top = [a + b for a, b in zip(top, v)]
        r = {"_id": k, "Kategori": k}
        r.update({a: round(x, 2) for a, x in zip(AYLAR, v)})
        r["Yıllık"] = round(sum(v), 2)
        rows.append(r)
    r = {"_id": "Σ", "Kategori": "Toplam"}
    r.update({a: round(x, 2) for a, x in zip(AYLAR, top)})
    r["Yıllık"] = round(sum(top), 2)
    rows.append(r)
    return rows, top


def ay_kurlari(yil, kmap, yedek):
    """Gider tablosunun aylık kuru (₺/$): P&L ile AYNI kural (yonetim_hesap.pnl_topla → tl_usd):
    ayın 15'indeki kur, yoksa güncel (yedek) kur, o da yoksa None. 12 elemanlı liste."""
    out = []
    for mi in range(12):
        k = (kmap or {}).get(f"{yil}-{mi + 1:02d}-15") or (yedek if (yedek or 0) > 1 else None)
        out.append(float(k) if k else None)
    return out


def gider_usd_satirlari(kat, kurlar):
    """Aylık gider tablosu USD: her ayın TL tutarı o ayın kuruna (ay_kurlari) bölünür; böylece
    tablo P&L'deki 'dönemde ≈ $' rakamıyla aynı kuru kullanır. Kuru olmayan ay 0 yazılır ve
    eksik listesine düşer. Dönüş: (satırlar, 12 aylık toplam, kuru eksik aylar)."""
    kur = (list(kurlar or []) + [None] * 12)[:12]
    rows, top = [], [0.0] * 12
    eksik = []
    for k in ("Sabit", "Değişken", "Yarı Değişken"):
        v = [float(x or 0) for x in (list((kat or {}).get(k) or []) + [0.0] * 12)[:12]]
        u = [(t / c) if (c and t) else 0.0 for t, c in zip(v, kur)]
        eksik += [a for a, t, c in zip(AYLAR, v, kur) if t and not c]
        top = [a + b for a, b in zip(top, u)]
        r = {"_id": k, "Kategori": k}
        r.update({a: round(x, 2) for a, x in zip(AYLAR, u)})
        r["Yıllık"] = round(sum(u), 2)
        rows.append(r)
    r = {"_id": "Σ", "Kategori": "Toplam"}
    r.update({a: round(x, 2) for a, x in zip(AYLAR, top)})
    r["Yıllık"] = round(sum(top), 2)
    rows.append(r)
    return rows, top, sorted(set(eksik), key=AYLAR.index)


def pnl_satirlari(r, kiyaslar=()):
    """Excel / tablo için gelir tablosu: kalem × (dönem, kıyaslar)."""
    kalemler = [("Ciro", "ciro"), ("COGS", "cogs"), ("Brüt kâr", "brut"), ("Destekler", "destek"),
                ("İşletme giderleri", "gider"), ("Alınan destek", "alinan"), ("Net kâr", "net_kar")]
    rows = []
    for ad, k in kalemler:
        # Sütun adları shared.tablo biçim kuralına göre: "Kalem" adet sayılırdı, "tutar" para
        row = {"Hesap": ad, "Tutar ($)": round(float(r.get(k, 0) or 0), 2)}
        for etiket, rk in kiyaslar:
            row[f"{etiket} tutarı ($)"] = round(float(rk.get(k, 0) or 0), 2)
        rows.append(row)
    return rows


def _x(i, n, gen, pay):
    return pay + i * (gen - 2 * pay) / max(1, n - 1)


def kucuk_trend_svg(degerler, etiketler, renk="mor", bicim=lambda v: str(v), gen=220, yuk=56):
    """Kart içi 12 aylık çizgi. Renk tema değişkeninden (var(--k-renk)); her noktada ipucu
    (<title>: ay ve değer). Değer yoksa boş döner."""
    d = [float(v or 0) for v in (degerler or [])]
    if len(d) < 2:
        return ""
    mn, mx = min(d), max(d)
    if mx == mn:
        mx, mn = mx + 1, mn - 1
    pay = 5

    def y(v):
        return yuk - 6 - (v - mn) / (mx - mn) * (yuk - 14)
    pts = [(_x(i, len(d), gen, pay), y(v)) for i, v in enumerate(d)]
    yol = "".join(f"{'L' if i else 'M'}{x:.1f},{yy:.1f}" for i, (x, yy) in enumerate(pts))
    c = f"var(--k-{renk})"
    alan = f'{yol}L{pts[-1][0]:.1f},{yuk - 2}L{pts[0][0]:.1f},{yuk - 2}Z'
    noktalar = "".join(
        f'<circle cx="{x:.1f}" cy="{yy:.1f}" r="{3.5 if i == len(pts) - 1 else 7}" '
        f'fill="{c if i == len(pts) - 1 else "transparent"}">'
        f'<title>{etiketler[i] if i < len(etiketler) else ""}: {bicim(d[i])}</title></circle>'
        for i, (x, yy) in enumerate(pts))
    return (f'<svg viewBox="0 0 {gen} {yuk}" width="100%" height="{yuk}" preserveAspectRatio="none" '
            f'role="img" aria-label="12 aylık seyir" style="display:block;overflow:visible">'
            f'<path d="{alan}" fill="{c}" fill-opacity="0.12"/>'
            f'<path d="{yol}" fill="none" stroke="{c}" stroke-width="2" stroke-linejoin="round" '
            f'vector-effect="non-scaling-stroke"/>{noktalar}</svg>')


def ay_etiketi(yil, ay_idx):
    return f"{AY_KISA[ay_idx]} {yil}"


