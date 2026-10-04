# -*- coding: utf-8 -*-
"""Ürün karnesi — hangi ürün kalsın, hangisi gitsin? (Ekim 2026)

Her ürüne yedi ölçüden A–F not ve öneri (Büyüt / Koru / İzle / Bırak). Stok kartı › Analiz'in
en üstünde görünür. YALNIZ OKUR; rakamlar mevcut hesaplardan gelir:
  kârlılık    → satis.database.satir_kar (P&L satır kuralı) − iade kârı (iade_net − adet × paçal)
  sermaye     → yıllık net kâr ÷ (bizim stok × paçal, satis.database.get_pacal_map)
  satış hızı  → stok ÷ son 90 günün günlük satışı
  stok yaşı   → kayranpm.stok_yasi (FIFO, Stok yaşı sayfasıyla aynı): 180 günü geçen stoğun payı
  arıza       → Teknik servis › Arıza oranı ile aynı hesap (alt sınır)
  iade oranı  → iade adedi ÷ satış adedi
  kampanya    → kampanya takibindeki satılan adet ÷ satış adedi (satış satırında destek alanı boş)
Pencere: son 12 ay (satış, iade, kampanya, servis). Ağırlık ve eşikler kullanıcı onaylı (Ekim 2026).

Saf fonksiyonlar (test edilir): puan, karne, olculer, portfoy_hesapla, baglam.
"""
from datetime import date, timedelta

# (anahtar, ad, ağırlık %, eşik noktaları [(değer, puan)], düşük mü iyi)
OLCULER = [
    ("marj", "Kârlılık", 25, [(-5, 0), (0, 20), (10, 60), (20, 100)]),
    ("gmroi", "Sermaye verimi", 20, [(0, 0), (0.5, 20), (1, 55), (3, 100)]),
    ("devir", "Satış hızı", 20, [(45, 100), (90, 70), (180, 25), (365, 0)]),
    ("yasli", "Stok yaşı", 15, [(0, 100), (50, 0)]),
    ("ariza", "Arıza oranı", 10, [(1, 100), (3, 60), (8, 0)]),
    ("iade", "İade oranı", 5, [(1, 100), (10, 0)]),
    ("kampanya", "Kampanya bağımlılığı", 5, [(30, 100), (80, 20), (100, 10)]),
]
OLCU_AD = {a: ad for a, ad, *_ in OLCULER}
NOTLAR = [(85, "A"), (70, "B"), (55, "C"), (40, "D"), (0, "F")]
GUN = 365            # pencere
HIZ_GUN = 90         # satış hızı penceresi
YAS_ESIK = 180       # yaşlı stok eşiği (gün)


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def puan(anahtar, deger):
    """Ölçü değeri → 0..100 (eşik noktaları arasında doğrusal). Değer yoksa None."""
    if deger is None:
        return None
    noktalar = next(n for a, _ad, _w, n in OLCULER if a == anahtar)
    if deger == float("inf"):
        return float(noktalar[-1][1])
    if deger <= noktalar[0][0]:
        return float(noktalar[0][1])
    for (x0, y0), (x1, y1) in zip(noktalar, noktalar[1:]):
        if deger <= x1:
            return y0 + (y1 - y0) * (deger - x0) / (x1 - x0)
    return float(noktalar[-1][1])


def karne(o):
    """o: {ölçü: değer | None} → {puanlar, toplam, not, oneri, dusurenler, eksik}.
    Verisi olmayan ölçünün ağırlığı diğerlerine dağıtılır. Hiç ölçü yoksa not None."""
    puanlar = {a: puan(a, o.get(a)) for a, *_ in OLCULER}
    dolu = [(a, w) for a, _ad, w, _n in OLCULER if puanlar[a] is not None]
    eksik = [a for a, *_ in OLCULER if puanlar[a] is None]
    if not dolu:
        return {"puanlar": puanlar, "toplam": None, "not": None, "oneri": None, "dusurenler": [], "eksik": eksik}
    tw = sum(w for _a, w in dolu)
    toplam = sum(puanlar[a] * w for a, w in dolu) / tw
    nt = next(h for esik, h in NOTLAR if toplam >= esik)
    # Notu en çok düşüren iki ölçü: ağırlık × eksik puan (yalnız 70'in altındakiler)
    kayip = sorted(((w * (100 - puanlar[a]), a) for a, w in dolu if puanlar[a] < 70), reverse=True)
    return {"puanlar": puanlar, "toplam": toplam, "not": nt, "oneri": oneri(nt, o),
            "dusurenler": [a for _k, a in kayip[:2]], "eksik": eksik}


def oneri(nt, o):
    """Not ve ölçülerden öneri."""
    devir, gmroi = o.get("devir"), o.get("gmroi")
    if nt == "F" or (devir is not None and devir > 180 and gmroi is not None and gmroi < 1):
        return "Bırak"
    if nt in ("A", "B"):
        if devir is None:
            # Stok yok: son 90 günde sattıysa talep var (bitti); satmadıysa talep ölçülemez
            return "Büyüt" if _f(o.get("_son90")) > 0 else "Koru"
        return "Büyüt" if devir <= 60 else "Koru"
    return "İzle"


ONERI_METNI = {"Büyüt": "Büyüt — talep güçlü, stok hızlı dönüyor",
               "Koru": "Koru — iyi ürün, mevcut düzen sürsün",
               "İzle": "İzle — zayıf yanları var, yeni siparişte dikkat",
               "Bırak": "Bırak — yeniden sipariş verme, eldekini erit"}


def olculer(s):
    """Tek ürünün ham toplamlarından ölçüler. s: {s_adet, ciro, destek, kar, i_adet, i_tutar, i_kar,
    son90, stok, pacal, yasli_adet, yas_stok, ariza, kampanya_adet}."""
    s_adet = _f(s.get("s_adet"))
    stok = _f(s.get("stok"))
    net_satis = _f(s.get("ciro")) - _f(s.get("destek")) - _f(s.get("i_tutar"))
    net_kar = _f(s.get("kar")) - _f(s.get("i_kar"))
    stok_degeri = stok * _f(s.get("pacal"))
    hiz = _f(s.get("son90")) / HIZ_GUN
    yas_stok = _f(s.get("yas_stok"))
    return {
        "marj": (net_kar / net_satis * 100) if net_satis > 0 else None,
        "gmroi": (net_kar / stok_degeri) if stok_degeri > 0 else None,
        "devir": (stok / hiz if hiz > 0 else float("inf")) if stok > 0 else None,
        "yasli": (_f(s.get("yasli_adet")) / yas_stok * 100) if yas_stok > 0 else None,
        "ariza": s.get("ariza"),
        "iade": (_f(s.get("i_adet")) / s_adet * 100) if s_adet > 0 else None,
        "kampanya": min(_f(s.get("kampanya_adet")) / s_adet * 100, 100.0) if s_adet > 0 else None,
        "_net_kar": net_kar, "_stok_degeri": stok_degeri, "_son90": _f(s.get("son90")),
    }


def portfoy_hesapla(satislar, iadeler, kartlar, pacal, yasli, ariza, kampanya, bugun, satir_kar, anahtar):
    """Bütün ürünler: {sku_anahtar: {ham…, olc: ölçüler, karne: karne(…)}}.
    satislar / iadeler: son 12 ayın satırları · kartlar: {anahtar: kart} · pacal: {anahtar: $}
    yasli: {anahtar: (180+ adet, stok)} · ariza: {anahtar: oran %} · kampanya: {anahtar: adet}."""
    b90 = str(bugun - timedelta(days=HIZ_GUN))
    ham = {}

    def _e(k):
        return ham.setdefault(k, {"s_adet": 0.0, "ciro": 0.0, "destek": 0.0, "kar": 0.0, "son90": 0.0,
                                  "i_adet": 0.0, "i_tutar": 0.0, "i_kar": 0.0})
    for r in satislar or []:
        k = anahtar(r.get("sku"))
        if not k:
            continue
        x = satir_kar(r)
        e = _e(k)
        e["s_adet"] += _f(x.get("adet"))
        e["ciro"] += _f(x.get("ciro"))
        e["destek"] += _f(x.get("destek"))
        e["kar"] += _f(x.get("net_kar"))
        if str(r.get("tarih") or "")[:10] >= b90:
            e["son90"] += _f(x.get("adet"))
    for r in iadeler or []:
        k = anahtar(r.get("sku"))
        if not k:
            continue
        e = _e(k)
        a, net = _f(r.get("iade_adet")), _f(r.get("iade_net"))
        e["i_adet"] += a
        e["i_tutar"] += net
        e["i_kar"] += net - a * _f(pacal.get(k))
    for k, u in (kartlar or {}).items():
        if _f(u.get("bizim_stok")) > 0:
            _e(k)
    out = {}
    for k, e in ham.items():
        u = (kartlar or {}).get(k) or {}
        ya = (yasli or {}).get(k)
        e.update({"stok": max(_f(u.get("bizim_stok")), 0.0), "pacal": _f(pacal.get(k)),
                  "yasli_adet": ya[0] if ya else 0.0, "yas_stok": ya[1] if ya else 0.0,
                  "ariza": (ariza or {}).get(k), "kampanya_adet": _f((kampanya or {}).get(k))})
        o = olculer(e)
        out[k] = {"ham": e, "olc": o, "karne": karne(o)}
    return out


def baglam(portfoy, k):
    """Ürünün portföydeki yeri: sermaye payı, kâr payı, kaç ürünün önünde (puana göre)."""
    p = portfoy.get(k)
    if not p:
        return None
    top_sermaye = sum(max(x["olc"]["_stok_degeri"], 0) for x in portfoy.values())
    top_kar = sum(max(x["olc"]["_net_kar"], 0) for x in portfoy.values())
    notlu = [x["karne"]["toplam"] for x in portfoy.values() if x["karne"]["toplam"] is not None]
    t = p["karne"]["toplam"]
    return {
        "sermaye_pay": (p["olc"]["_stok_degeri"] / top_sermaye * 100) if top_sermaye > 0 else None,
        "kar_pay": (max(p["olc"]["_net_kar"], 0) / top_kar * 100) if top_kar > 0 else None,
        "onunde": (sum(1 for v in notlu if v < t) / len(notlu) * 100) if (t is not None and len(notlu) > 1) else None,
        "urun_sayisi": len(notlu),
    }


# ── Veri (önbellekli, bütün ürünler bir kez) ────────────────────────
def _onbellek(ttl):
    try:
        import streamlit as st
        return st.cache_data(ttl=ttl, show_spinner=False)
    except Exception:  # noqa: BLE001
        return lambda fn: fn


@_onbellek(600)
def portfoy(bugun_iso):
    """Bütün ürünlerin karnesi (10 dk önbellek; ilk açılan stok kartı hesaplar, diğerleri hazır alır)."""
    from satis.database import get_satislar_yalin, get_iadeler, get_pacal_map, satir_kar
    from kayranpm.database import urunler_skuya_gore, get_tum_kampanya_urunler, get_kampanyalar
    from shared.utils import sku_anahtar
    bugun = date.fromisoformat(bugun_iso)
    bas = str(bugun - timedelta(days=GUN))
    kartlar = {}
    for u in urunler_skuya_gore() or []:
        k = sku_anahtar(u.get("sku"))
        if k:
            kartlar.setdefault(k, u)
    pacal = get_pacal_map() or {}
    yasli = {}
    try:
        from kayranpm.stok_yasi import hesapla, yasli_satirlar
        h = hesapla()
        for k, (oz, _kal, _u) in (h.get("bizim") or {}).items():
            yasli[k] = (0.0, _f(oz.get("stok")))
        for r in yasli_satirlar(h.get("bizim") or {}, pacal, h.get("bugun") or bugun, YAS_ESIK):
            yasli[r["_id"]] = (_f(r.get(f"{YAS_ESIK}+ gün adet")), _f(r.get("Toplam stok")))
    except Exception:  # noqa: BLE001
        pass
    ariza = {}
    try:
        from teknikservis.ariza_ekran import _veri
        for r in (_veri(date.fromisoformat(bas), bugun) or {}).get("satirlar") or []:
            if _f(r.get("Son kullanıcıya ulaşan")) > 0 and r.get("Arıza oranı (%)") is not None:
                ariza[sku_anahtar(r.get("SKU"))] = _f(r.get("Arıza oranı (%)"))
    except Exception:  # noqa: BLE001
        pass
    kampanya = {}
    try:
        donemde = {kp.get("id") for kp in get_kampanyalar() or []
                   if str(kp.get("bitis_tarihi") or "9999")[:10] >= bas}
        for r in get_tum_kampanya_urunler() or []:
            if r.get("kampanya_id") in donemde:
                k = sku_anahtar(r.get("sku"))
                kampanya[k] = kampanya.get(k, 0.0) + _f(r.get("satilan_adet"))
    except Exception:  # noqa: BLE001
        pass
    return portfoy_hesapla(get_satislar_yalin(bas, bugun_iso) or [], get_iadeler(bas, bugun_iso) or [],
                           kartlar, pacal, yasli, ariza, kampanya, bugun, satir_kar, sku_anahtar)


# ── Ekran ───────────────────────────────────────────────────────────
NOT_RENK = {"A": "yesil", "B": "yesil", "C": "amber", "D": "kirmizi2", "F": "kirmizi"}
ONERI_RENK = {"Büyüt": "yesil", "Koru": "mavi", "İzle": "amber", "Bırak": "kirmizi"}


def _deger_metni(a, v, kar_acik):
    from shared.tasarim import tr_sayi
    if v is None:
        return "veri yok"
    if a in ("marj", "gmroi") and not kar_acik:
        return "gizli"
    if a == "marj":
        return f"%{tr_sayi(v, 1)} net marj"
    if a == "gmroi":
        return f"1 $ stok → {tr_sayi(v, 2)} $ kâr/yıl"
    if a == "devir":
        return "satış yok" if v == float("inf") else f"{tr_sayi(v)} günde biter"
    if a == "yasli":
        return f"%{tr_sayi(v)} stok {YAS_ESIK}+ gün"
    return f"%{tr_sayi(v, 1)}"


def _gerekce(a, v):
    from shared.tasarim import tr_sayi
    if a == "devir":
        return "son 90 günde satış yok" if v == float("inf") else f"stok {tr_sayi(v)} günde biter"
    return {"marj": f"net marj %{tr_sayi(v or 0, 1)}", "gmroi": f"1 $ stok yılda {tr_sayi(v or 0, 2)} $ kâr",
            "yasli": f"stoğun %{tr_sayi(v or 0)}'i {YAS_ESIK} günü geçmiş", "ariza": f"arıza oranı %{tr_sayi(v or 0, 1)}",
            "iade": f"iade oranı %{tr_sayi(v or 0, 1)}", "kampanya": f"satışın %{tr_sayi(v or 0)}'i kampanyada"}[a]


def kart_html(p, b, kar_acik=True):
    """Karne kartı (HTML). p: portfoy()[anahtar] · b: baglam(...)."""
    import html as _h
    from shared.tasarim import tr_sayi
    kr, o = p["karne"], p["olc"]
    if kr["not"] is None:
        return ('<div class="uk"><div class="uk-bos">Karne için yeterli veri yok: son 12 ayda satış ve '
                'stokta ürün yok.</div></div>')
    nr, orr = NOT_RENK[kr["not"]], ONERI_RENK[kr["oneri"]]
    satirlar = ""
    for a, ad, w, _n in OLCULER:
        pu = kr["puanlar"][a]
        dolu = 0 if pu is None else max(2, round(pu))
        rk = "silik" if pu is None else ("yesil" if pu >= 70 else "amber" if pu >= 40 else "kirmizi")
        satirlar += (f'<div class="uk-s"><span class="uk-ad">{ad}<i>%{w}</i></span>'
                     f'<span class="uk-cb"><b style="width:{dolu}%;background:var(--k-{rk})"></b></span>'
                     f'<span class="uk-d">{_h.escape(_deger_metni(a, o.get(a), kar_acik))}</span></div>')
    dus = [_gerekce(a, o.get(a)) for a in kr["dusurenler"] if not (a in ("marj", "gmroi") and not kar_acik)]
    ozet = ("Notu düşüren: " + " · ".join(dus) + ".") if dus else "Bütün ölçüler iyi durumda."
    bg = ""
    if b:
        p1 = []
        if b.get("sermaye_pay") is not None:
            p1.append(f"sermayenin %{tr_sayi(b['sermaye_pay'], 1)}'ini bağlıyor")
        if kar_acik and b.get("kar_pay") is not None:
            p1.append(f"kârın %{tr_sayi(b['kar_pay'], 1)}'ini getiriyor")
        if b.get("onunde") is not None:
            if b["onunde"] <= 0:
                p1.append(f"{b['urun_sayisi']} ürün arasında puanı en düşük olanlardan")
            elif b["onunde"] >= 99.5:
                p1.append(f"{b['urun_sayisi']} ürün arasında puanı en yüksek olanlardan")
            else:
                p1.append(f"{b['urun_sayisi']} ürünün %{tr_sayi(b['onunde'])}'inden iyi")
        if p1:
            bg = f'<div class="uk-bg">Bu ürün {", ".join(p1)}.</div>'
    eksik = (f'<div class="uk-ek">Veri yok: {", ".join(OLCU_AD[a].lower() for a in kr["eksik"])} — ağırlığı '
             f'diğer ölçülere dağıtıldı.</div>') if kr["eksik"] else ""
    return (f'<div class="uk"><div class="uk-ust">'
            f'<div class="uk-not" style="color:var(--k-{nr});border-color:var(--k-{nr})">{kr["not"]}</div>'
            f'<div class="uk-ozet"><div class="uk-oneri" style="color:var(--k-{orr})">'
            f'{_h.escape(ONERI_METNI[kr["oneri"]])}</div>'
            f'<div class="uk-pu">Ürün karnesi · {tr_sayi(kr["toplam"])}/100 · son 12 ay</div>'
            f'<div class="uk-gr">{_h.escape(ozet)}</div>{bg}</div></div>'
            f'<div class="uk-liste">{satirlar}</div>{eksik}</div>')


CSS = """<style>
.uk{border:1px solid var(--k-kenar2);border-radius:14px;background:var(--k-yuzey1);padding:16px 18px;margin:2px 0 14px}
.uk-ust{display:flex;gap:16px;align-items:flex-start}
.uk-not{flex:0 0 auto;width:64px;height:64px;border:2px solid;border-radius:14px;display:flex;align-items:center;
  justify-content:center;font-size:36px;font-weight:700;line-height:1}
.uk-ozet{min-width:0}
.uk-oneri{font-size:16px;font-weight:600}
.uk-pu{font-size:12px;color:var(--k-silik);margin-top:2px}
.uk-gr{font-size:13px;color:var(--k-metin);margin-top:6px}
.uk-bg{font-size:12.5px;color:var(--k-soluk);margin-top:4px}
.uk-liste{margin-top:14px;display:grid;gap:7px}
.uk-s{display:grid;grid-template-columns:minmax(150px,1.1fr) 2fr minmax(150px,1.2fr);gap:12px;align-items:center;font-size:12.5px}
.uk-ad{color:var(--k-soluk)}.uk-ad i{font-style:normal;color:var(--k-silik);font-size:11px;margin-left:6px}
.uk-cb{height:6px;border-radius:99px;background:var(--k-ortu2);overflow:hidden}.uk-cb b{display:block;height:100%;border-radius:99px}
.uk-d{color:var(--k-metin);font-variant-numeric:tabular-nums}
.uk-ek,.uk-bos{font-size:12px;color:var(--k-silik);margin-top:10px}
@media (max-width:640px){.uk-s{grid-template-columns:1fr 1fr}.uk-cb{grid-column:1/3;order:3}}
</style>"""


def ciz(sku):
    """Stok kartı › Analiz'in üstündeki karne. Hata olursa kısa not, sekme çalışmaya devam eder."""
    import streamlit as st
    from shared.utils import sku_anahtar
    try:
        from shared.kar_gizle import kar_gorunur
        kar_acik = kar_gorunur()
    except Exception:  # noqa: BLE001
        kar_acik = False
    try:
        from shared.islem import bekle
        with bekle("Ürün karnesi hesaplanıyor"):
            pf = portfoy(date.today().isoformat())
        k = sku_anahtar(sku)
        p = pf.get(k)
        st.markdown(CSS, unsafe_allow_html=True)
        if not p:
            st.markdown('<div class="uk"><div class="uk-bos">Karne için yeterli veri yok: son 12 ayda satış '
                        've stokta ürün yok.</div></div>', unsafe_allow_html=True)
            return
        st.markdown(kart_html(p, baglam(pf, k), kar_acik), unsafe_allow_html=True)
    except Exception as e:  # noqa: BLE001
        from shared.hata_log import kaydet
        kaydet("urun_karnesi", e)
        st.caption("Ürün karnesi şu an hesaplanamadı.")
