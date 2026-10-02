# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Genel Bakış — saf hesaplar (Ekim 2026). Test edilir.

Girdi: analitik.dashboard_hesapla() satırları (firma/kategori filtresi uygulanmış)
ve haftalık müşteri verisi (get_musteri_haftalik_satis). Veritabanına gitmez.

  kpi               sayı kartları
  yapilacaklar      öncelikli eylem grupları (boş grup dönmez)
  kapsama_dagilimi  stok kaç güne yetiyor — dağılım
  kategori_ozeti    kategori bazında tablo satırları
  kanal_ozeti       kanal (firma) bazında stok + haftalık satış
  haftalik_seri     son n haftanın toplam sell-out'u
  trend_listeleri   en çok yükselen / düşen ürünler
  yaklasan_varislar yoldaki ürünlerin yakın varışları
"""
from datetime import date, timedelta

from shared.tasarim import tr_sayi


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _tarih(v):
    try:
        return date.fromisoformat(str(v or "")[:10])
    except ValueError:
        return None


def _acil(r):
    return r.get("siparis_durum") == "acil" and not r.get("eol")


def _kucuk(s):
    return str(s or "").strip().replace("I", "ı").replace("İ", "i").lower()


def _tr_bas(s):
    s = str(s or "").strip()
    if not s:
        return "Kategorisiz"
    ilk = {"i": "İ", "ı": "I"}.get(s[0], s[0].upper())
    return ilk + s[1:].replace("I", "ı").replace("İ", "i").lower()


# ── Sayı kartları ───────────────────────────────────────────────────
def kpi(rows, seri, bugun):
    stok = sum(int(_f(r.get("toplam_stok"))) for r in rows)
    son = seri[-1][1] if seri else None
    onceki = seri[-2][1] if len(seri) >= 2 else None
    degisim = (round((son - onceki) / onceki * 100, 1) if (son is not None and onceki) else None)
    varislar = [d for d in (_tarih(r.get("yol_varis")) for r in rows if _f(r.get("yol_miktar")) > 0)
                if d and d >= bugun]
    return {
        "stok": stok,
        "hafta_satis": son,
        "onceki_satis": onceki,
        "degisim": degisim,
        "kapsama_hafta": round(stok / son, 1) if son else None,
        "stok_degeri": round(sum(_f(r.get("bizim_stok")) * _f(r.get("ithalat_final")) for r in rows), 2),
        "yolda": int(sum(_f(r.get("yol_miktar")) for r in rows)),
        "en_yakin_varis": min(varislar) if varislar else None,
        "acil": sum(1 for r in rows if _acil(r)),
        "olu": sum(1 for r in rows if r.get("olu_stok_durum") == "olu"),
    }


# ── Yapılacaklar ────────────────────────────────────────────────────
def _mesaj_temiz(m):
    """'🪦 ÖLÜSTOK: 6 haftadır satış yok, …' → '6 haftadır satış yok, …'"""
    m = str(m or "").strip()
    return m.split(":", 1)[1].strip() if ":" in m else m


def yapilacaklar(rows):
    """Öncelik sırasıyla eylem grupları. Her grup:
    {anahtar, baslik, renk, hedef (sayfa), aciklama, urunler: [(satır, detay)]}."""
    g = []

    acil = sorted([r for r in rows if _acil(r)], key=lambda r: _f(r.get("stok_bitis_gun")))
    g.append(dict(anahtar="stok_bitiyor", baslik="Stok bitiyor", renk="kirmizi", hedef="📦  Sipariş Önerisi",
                  aciklama="Sipariş eşiğinin altına düştü",
                  urunler=[(r, (f"{int(_f(r.get('stok_bitis_gun')))} günde biter"
                               if _f(r.get("stok_bitis_gun")) > 0 else "stok tükendi")
                              + (f" · öneri {tr_sayi(int(_f(r.get('oneri_miktar'))))} adet"
                                 if _f(r.get("oneri_miktar")) else "")) for r in acil]))

    yol = [r for r in rows if r.get("yol_renk") == "sari" and _f(r.get("yol_miktar")) > 0]
    g.append(dict(anahtar="yol_risk", baslik="Yoldaki ürün yetişmeyebilir", renk="amber", hedef=None,
                  aciklama="Varış gecikirse stok tükenir",
                  urunler=[(r, f"{tr_sayi(int(_f(r.get('yol_miktar'))))} adet yolda · "
                              + str(r.get("yol_mesaj") or "").strip()) for r in yol]))

    olu = sorted([r for r in rows if r.get("olu_stok_durum") in ("olu", "yavas") and _f(r.get("bizim_stok")) > 0],
                 key=lambda r: -_f(r.get("bizim_stok")))
    g.append(dict(anahtar="olu_yavas", baslik="Ölü / yavaş stok", renk="amber", hedef="🎯  Kampanya Takip",
                  aciklama="Kampanya ya da fiyat aksiyonu düşün",
                  urunler=[(r, ("ölü stok · " if r.get("olu_stok_durum") == "olu" else "yavaş · ")
                              + _mesaj_temiz(r.get("olu_stok_mesaj"))) for r in olu]))

    zarar = sorted([r for r in rows if r.get("kar_durum") == "zarar"], key=lambda r: _f(r.get("kar_marji")))
    g.append(dict(anahtar="zarar", baslik="Zararına satılıyor", renk="kirmizi", hedef="📋  Tüm Ürünler",
                  aciklama="Satış fiyatı paçal maliyetin altında",
                  urunler=[(r, f"zarar %{tr_sayi(abs(_f(r.get('kar_marji'))), 1)}") for r in zarar]))

    eksik = [r for r in rows if r.get("kar_durum") in ("fiyat_yok", "alis_yok") and _f(r.get("toplam_stok")) > 0]
    g.append(dict(anahtar="eksik_veri", baslik="Fiyat / maliyet eksik", renk="silik", hedef="📂  Veri Yükleme",
                  aciklama="Kâr ve marj hesaplanamıyor",
                  urunler=[(r, "satış fiyatı yok" if r.get("kar_durum") == "fiyat_yok"
                               else "paçal maliyet yok (ithalat ya da maliyet girişi)") for r in eksik]))
    return [x for x in g if x["urunler"]]


# ── Dağılımlar ──────────────────────────────────────────────────────
KAPSAMA_DILIM = [("0–30 gün", 0, 30, "kirmizi"), ("31–60 gün", 31, 60, "amber"),
                 ("61–135 gün", 61, 135, "yesil"), ("135+ gün", 136, 10 ** 9, "mavi")]


def kapsama_dagilimi(rows):
    """[(etiket, ürün sayısı, toplam stok)] — stok_bitis_gun'e göre; satışı olmayanlar ayrı."""
    out = []
    for et, a, b, _r in KAPSAMA_DILIM:
        ks = [r for r in rows if r.get("stok_bitis_gun") is not None and a <= _f(r["stok_bitis_gun"]) <= b]
        out.append((et, len(ks), int(sum(_f(r.get("toplam_stok")) for r in ks))))
    yok = [r for r in rows if r.get("stok_bitis_gun") is None]
    out.append(("Satış yok", len(yok), int(sum(_f(r.get("toplam_stok")) for r in yok))))
    return out


def kategori_ozeti(rows):
    gr = {}
    for r in rows:
        gr.setdefault(_kucuk(r.get("kategori")), []).append(r)
    out = []
    for k, rs in gr.items():
        satis = sum(_f(r.get("toplam_haftalik_satis")) for r in rs)
        stok = sum(_f(r.get("toplam_stok")) for r in rs)
        out.append({"Kategori": _tr_bas(k), "Ürün": len(rs), "Stok": int(stok), "Adet / hafta": int(satis),   # "Haftalık satış" para sayılırdı
                    "Kapsama (hft)": round(stok / satis, 1) if satis else None,
                    "Acil": sum(1 for r in rs if _acil(r)),
                    "Ölü / yavaş": sum(1 for r in rs if r.get("olu_stok_durum") in ("olu", "yavas"))})
    return sorted(out, key=lambda x: -x["Stok"])


def kanal_ozeti(rows):
    k = {"G5F depo": {"kanal": "G5F depo", "stok": 0, "satis": 0}}
    for r in rows:
        k["G5F depo"]["stok"] += int(_f(r.get("bizim_stok")))
        for fd in r.get("firma_detay") or []:
            ad = str(fd.get("firma") or "").strip() or "?"
            x = k.setdefault(ad, {"kanal": ad, "stok": 0, "satis": 0})
            x["stok"] += int(_f(fd.get("stok")))
            x["satis"] += int(_f(fd.get("satis")))
    return sorted(k.values(), key=lambda x: -(x["stok"] + x["satis"]))


def haftalik_seri(firma_rows, skular, bugun, n=8):
    """[(hafta başı, toplam satış)] son n hafta (içinde bulunulan dahil), eski → yeni.
    skular: filtre uygulanmış ürünlerin SKU kümesi (None = hepsi)."""
    bu = bugun - timedelta(days=bugun.weekday())
    haftalar = [bu - timedelta(days=7 * i) for i in range(n - 1, -1, -1)]
    top = {h: 0 for h in haftalar}
    for r in firma_rows or []:
        if skular is not None and r.get("sku") not in skular:
            continue
        d = _tarih(r.get("yukleme_tarihi"))
        if not d:
            continue
        h = d - timedelta(days=d.weekday())
        if h in top:
            top[h] += int(_f(r.get("haftalik_satis")) + _f(r.get("satis_magaza")))
    return [(h, top[h]) for h in haftalar]


def trend_listeleri(rows, n=5, en_az=1.0):
    """(yükselenler, düşenler) — çok az satan ürünlerin gürültüsü elenir."""
    aday = [r for r in rows if _f(r.get("ortalama_haftalik_satis")) >= en_az]
    yuk = sorted([r for r in aday if r.get("trend_yon") == "yukseliyor"], key=lambda r: -_f(r.get("trend_yuzdesi")))
    dus = sorted([r for r in aday if r.get("trend_yon") == "dusuyor"], key=lambda r: _f(r.get("trend_yuzdesi")))
    return yuk[:n], dus[:n]


def yaklasan_varislar(rows, bugun, n=6):
    v = [(r, _tarih(r.get("yol_varis"))) for r in rows if _f(r.get("yol_miktar")) > 0]
    v = [(r, d) for r, d in v if d and d >= bugun]
    return [r for r, _ in sorted(v, key=lambda x: x[1])[:n]]
