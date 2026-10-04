# -*- coding: utf-8 -*-
"""Soru kutusu — çözülmüş soruya cevap (Ekim 2026). YALNIZ OKUR; hiçbir kaydı değiştirmez.

Rakam burada YENİDEN HESAPLANMAZ; ilgili ekranın kullandığı fonksiyon çağrılır:
  satış toplamı → satis.pnl_hesap.satis_pnl (P&L kartıyla aynı "Net kâr")
  ürün / firma / kategori / marka kırılımı → aynı fonksiyonun ürün ve firma kırılımı, iade düşülmüş
  aylık seyir → satis.satis_hesap.aylik_seyir · yaşlı stok → kayranpm.stok_yasi.yasli_satirlar
  arıza → teknikservis (Arıza oranı sayfasının okuyucusu) · kampanya → kayranpm.kampanya_hesap
  ödeme → kayranacc.odeme_hesap · çek → kayranacc.database.cek_tutarlari

cevapla(niyet, izin, veri) → {baslik, kartlar, satirlar, grafik, kaynak, hedef, uyarilar, bos, yetki}
`veri` testte sahte bir nesneyle değiştirilir (Veri ile aynı yöntemler).
"""
from datetime import date

from shared.soru import OLCU_AD, KIRILIM_AD, KAPSAM_AD, KAMPANYA_AD, AY_AD, sade

# Konu → gereken modül yetkisi
YETKI = {"satis": "satis", "seyir": "satis", "iade": "satis", "stok": "kayranpm", "yasli_stok": "kayranpm",
         "ariza": "teknikservis", "kampanya": "kayranpm", "odeme": "kayranacc", "cek": "kayranacc",
         "urun": "kayranpm"}
MODUL_AD = {"satis": "Satış", "kayranpm": "Ürün yönetimi", "teknikservis": "Teknik servis",
            "kayranacc": "Muhasebe"}


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _gun(v):
    try:
        return date.fromisoformat(str(v or "")[:10])
    except ValueError:
        return None


# ── Veri kaynağı (gerçek) ───────────────────────────────────────────
class Veri:
    """Mevcut okuma fonksiyonlarına ince bir kapı. Testte aynı yöntemlerle sahtesi verilir."""

    def pnl(self, bas, bit, kanal, kat):
        from satis.pnl_hesap import satis_pnl, Kaynak
        return satis_pnl(bas, bit, kanal or "Tümü", kat or "Tümü", Kaynak())

    def satislar(self, bas, bit):
        from satis.database import get_satislar_yalin
        return get_satislar_yalin(bas, bit) or []

    def iadeler(self, bas, bit):
        from satis.database import get_iadeler
        return get_iadeler(bas, bit) or []

    def pacal(self):
        from satis.database import get_pacal_map
        return get_pacal_map() or {}

    def kartlar(self):
        """{sku_anahtar: kart} — urunler tablosu (sayfalı)."""
        from kayranpm.database import urunler_skuya_gore
        from shared.utils import sku_anahtar
        out = {}
        for u in urunler_skuya_gore() or []:
            k = sku_anahtar(u.get("sku"))
            if k:
                out.setdefault(k, u)
        return out

    def stok_yasi(self):
        from kayranpm.stok_yasi import hesapla
        return hesapla()

    def ariza(self, bas, bit):
        from teknikservis.ariza_ekran import _veri
        return _veri(bas, bit)

    def kampanyalar(self):
        from kayranpm.kampanya import _veri
        kamps, ku_map, pacal, _ = _veri()
        return kamps, ku_map, pacal

    def odemeler(self, kapsam):
        if kapsam == "hafta":
            from kayranacc.database import get_aktif_odemeler
            return get_aktif_odemeler()[0] or []
        from kayranacc.database import get_tum_odemeler
        return get_tum_odemeler() or []

    def cekler(self):
        from kayranacc.database import get_cekler
        return [dict(c, _pb="TL") for c in get_cekler("TL") or []] + \
               [dict(c, _pb="USD") for c in get_cekler("USD") or []]


# ── Sözlük: soru çözümleyicinin tanıyacağı adlar (veriden) ──────────
def sozluk_kur():
    """{firmalar: {görünen ad: [kanal…]}, kategoriler, markalar, skular: {ANAHTAR: sku}}."""
    from shared.utils import firma_kisa_ad, sku_anahtar
    s = {"firmalar": {}, "kategoriler": [], "markalar": [], "skular": {}}
    try:
        from satis.database import get_kanallar
        for k in get_kanallar() or []:
            ad = firma_kisa_ad(k).split(" · ")[0]
            s["firmalar"].setdefault(ad, []).append(k)
    except Exception:  # noqa: BLE001
        pass
    try:
        from shared.ana_veri import get_kategori_havuzu, get_marka_havuzu
        s["kategoriler"] = [x for x in get_kategori_havuzu() or [] if x]
        s["markalar"] = [x for x in get_marka_havuzu() or [] if x]
    except Exception:  # noqa: BLE001
        pass
    try:
        from kayranpm.database import get_tum_sku_listesi
        for r in get_tum_sku_listesi() or []:
            sku = str((r.get("sku") if isinstance(r, dict) else r) or "").strip()
            if sku:
                s["skular"].setdefault(sku_anahtar(sku).replace("-", "").replace(" ", ""), sku)
    except Exception:  # noqa: BLE001
        pass
    return s


# ── Yardımcılar ─────────────────────────────────────────────────────
def _kart(etiket, deger, alt=""):
    return {"etiket": etiket, "deger": deger, "alt": alt}


def _para(v, birim="$"):
    from shared.tasarim import para
    return para(v, birim)


def _sayi(v, b=0):
    from shared.tasarim import tr_sayi
    return tr_sayi(v, b)


def _bos(baslik, metin, n):
    return {"baslik": baslik, "kartlar": [], "satirlar": [], "grafik": None, "kaynak": "",
            "hedef": None, "uyarilar": [], "bos": metin, "yetki": None}


def _kart_bilgi(kartlar, anahtar):
    return kartlar.get(anahtar) or {}


def _ad_haritasi(kartlar):
    """shared.ana_veri.urun_ad için harita: kartın adı (BÜYÜK harf), kartlar zaten okunmuşken."""
    from shared.utils import tr_buyuk
    return {k: tr_buyuk(u.get("urun_adi")) for k, u in (kartlar or {}).items() if u.get("urun_adi")}


def _kat_uyar(k, kategori):
    from shared.ana_veri import kategori_anahtar
    return not kategori or kategori_anahtar(k) == kategori_anahtar(kategori)


def _marka_uyar(m, marka):
    from shared.ana_veri import marka_anahtar
    return not marka or marka_anahtar(m) == marka_anahtar(marka)


def _sirala(satirlar, alan, sira, limit):
    satirlar = sorted(satirlar, key=lambda r: (r.get(alan) is None, -(r.get(alan) or 0)))
    if sira == "artan":
        satirlar = list(reversed([r for r in satirlar if r.get(alan) is not None])) + \
                   [r for r in satirlar if r.get(alan) is None]
    return satirlar[:limit] if limit else satirlar


# ── Satış ───────────────────────────────────────────────────────────
def _iade_kirilim(iadeler, kanallar, kat_f, marka, kartlar, pacal):
    """{(kanal, sku_anahtar): {i_adet, i_tutar, i_kar}} — P&L'in süzgeçli iade kuralıyla aynı:
    iade kârı = iade_net − adet × paçal."""
    from shared.utils import sku_anahtar
    out = {}
    for ir in iadeler or []:
        kn = (ir.get("kanal") or "").strip()
        if kanallar and kn not in kanallar:
            continue
        k = sku_anahtar(ir.get("sku"))
        kb = _kart_bilgi(kartlar, k)
        if not _kat_uyar(kb.get("kategori"), kat_f) or not _marka_uyar(kb.get("marka"), marka):
            continue
        net, adet = _f(ir.get("iade_net")), int(_f(ir.get("iade_adet")))
        e = out.setdefault((kn, k), {"i_adet": 0, "i_tutar": 0.0, "i_kar": 0.0})
        e["i_adet"] += adet
        e["i_tutar"] += net
        e["i_kar"] += net - adet * _f(pacal.get(k))
    return out


def _satis(n, izin, v):
    from shared.ana_veri import urun_ad
    from shared.utils import sku_anahtar
    d = n["donem"]
    bas, bit = d["bas"], d["bit"]
    kanallar = list(n.get("kanallar") or [])
    kat, marka = n.get("kategori"), n.get("marka")
    kar_acik = izin.get("kar", False)
    olcu = n.get("olcu") or "net_kar"
    uyari = []
    if olcu in ("net_kar", "marj") and not kar_acik:
        olcu = "ciro"
        uyari.append("Kâr ve marj yalnız yetkili kullanıcıya görünür; ciro gösteriliyor.")

    # P&L: firma başına bir kez (aynı firmanın TL/USD carisi ayrı kanal adıdır)
    sonuclar = [v.pnl(bas, bit, k, kat) for k in (kanallar or [None])]
    sonuclar = [p for p in sonuclar if p and not p.get("bos")]
    for p in sonuclar:
        uyari += [e for e in p.get("eksikler") or [] if e not in uyari]
    baslik = _baslik(n, olcu)
    if not sonuclar:
        return _bos(baslik, "Bu dönemde ve süzgeçte satış kaydı yok.", n)

    kartlar = v.kartlar()
    pacal = v.pacal()
    iade = _iade_kirilim(v.iadeler(bas, bit), set(kanallar), kat, marka, kartlar, pacal)

    # Ürün satırları (iade düşülmüş, net): satış SKU'su kanonik anahtarla birleşir
    urun = {}
    for p in sonuclar:
        for sk, u in (p.get("urun") or {}).items():
            k = sku_anahtar(sk)
            kb = _kart_bilgi(kartlar, k)
            if not _marka_uyar(kb.get("marka"), marka):
                continue
            e = urun.setdefault(k, {"sku": kb.get("sku") or sk, "ad": u.get("urun_adi") or "",
                                    "kategori": kb.get("kategori") or "", "marka": kb.get("marka") or "",
                                    "ciro": 0.0, "destek": 0.0, "kar": 0.0, "adet": 0})
            e["ciro"] += _f(u.get("ciro"))
            e["destek"] += _f(u.get("destek"))
            e["kar"] += _f(u.get("net_kar"))
            e["adet"] += int(_f(u.get("adet")))
    # Firma satırları: P&L'in kanal kırılımı
    firma = {}
    for p in sonuclar:
        for kn, u in (p.get("kanal") or {}).items():
            e = firma.setdefault(kn, {"ciro": 0.0, "destek": 0.0, "kar": 0.0, "adet": 0})
            e["ciro"] += _f(u.get("ciro"))
            e["destek"] += _f(u.get("destek"))
            e["kar"] += _f(u.get("net_kar"))
            e["adet"] += int(_f(u.get("adet")))
    for (kn, k), ii in iade.items():
        if k in urun:
            urun[k]["ciro"] -= ii["i_tutar"]
            urun[k]["kar"] -= ii["i_kar"]
            urun[k]["adet"] -= ii["i_adet"]
        if kn in firma and not marka:
            firma[kn]["ciro"] -= ii["i_tutar"]
            firma[kn]["kar"] -= ii["i_kar"]
            firma[kn]["adet"] -= ii["i_adet"]

    def _marj(e):
        ns = e["ciro"] - e["destek"]
        return (e["kar"] / ns * 100) if ns > 0 else None

    # ── Toplam kartları ──
    if marka:
        # Marka süzgeci P&L'de yok: ürün satırlarının toplamı (Ref No / destek ürüne dağıtılmaz)
        t = {"ciro": sum(e["ciro"] for e in urun.values()), "destek": sum(e["destek"] for e in urun.values()),
             "kar": sum(e["kar"] for e in urun.values()), "adet": sum(e["adet"] for e in urun.values())}
        net_kar, net_ciro, adet, marj = t["kar"], t["ciro"], t["adet"], _marj(t)
        kar_alt = "satış kârı − iade (marka süzgeci)"
        kaynak = "Kâr / P&L ile aynı satır ve iade hesabı; marka süzgeci P&L'de olmadığı için ürünlerin toplamı."
    else:
        net_kar = sum(_f(p.get("nihai")) for p in sonuclar)
        net_ciro = sum(_f(p.get("net_ciro")) for p in sonuclar)
        net_satis = sum(_f(p.get("net_satis")) for p in sonuclar)
        adet = sum(int(_f((p.get("top") or {}).get("adet"))) - int(_f((p.get("itop") or {}).get("i_adet")))
                   for p in sonuclar)
        marj = (net_kar / net_satis * 100) if net_satis > 0 else None
        kar_alt = "P&L kartıyla aynı"
        kaynak = "Satış › Kâr / P&L ile aynı hesap (satis_pnl): iade, Ref No ve destekler dahil."
    k = [_kart("Net ciro", _para(net_ciro), f"{_sayi(adet)} adet")]
    if kar_acik:
        k.append(_kart("Net kâr", _para(net_kar), kar_alt))
        k.append(_kart("Net marj", "—" if marj is None else f"%{_sayi(marj, 1)}"))
    k.append(_kart("Dönem", d["ad"], f"{bas:%d.%m.%Y} – {bit:%d.%m.%Y}"))

    # ── Kırılım ──
    kir = n.get("kirilim")
    satirlar, grafik = [], None
    alan = {"net_kar": "Net kâr ($)", "ciro": "Net ciro ($)", "adet": "Adet", "marj": "Marj (%)"}[olcu]
    if kir in ("urun", "kategori", "marka"):
        if kir == "urun":
            har = _ad_haritasi(kartlar)
            kaynak_s = [{"_k": k2, "SKU": e["sku"], "Ürün": urun_ad(e["sku"], e["ad"], har), **_degerler(e, _marj)}
                        for k2, e in urun.items()]
        else:
            g = {}
            for e in urun.values():
                ad = (e["kategori"] if kir == "kategori" else e["marka"]) or "Diğer"
                x = g.setdefault(ad, {"ciro": 0.0, "destek": 0.0, "kar": 0.0, "adet": 0})
                for f in x:
                    x[f] += e[f]
            kaynak_s = [{KIRILIM_AD[kir]: ad, **_degerler(e, _marj)} for ad, e in g.items()]
        satirlar = _sirala(kaynak_s, alan, n.get("sira"), n.get("limit"))
        kaynak += " Kırılım: ürün başına satış kârı − iade (Ref No ve alınan destek ürüne dağıtılmaz)."
    elif kir == "firma":
        from shared.utils import firma_kisa_ad
        kaynak_s = [{"Firma": firma_kisa_ad(kn), **_degerler(e, _marj)} for kn, e in firma.items()]
        satirlar = _sirala(kaynak_s, alan, n.get("sira"), n.get("limit"))
        kaynak += " Kırılım: P&L'in firma kırılımı, firmanın iadesi düşülmüş."
    if not kar_acik:
        satirlar = [{a: b for a, b in r.items() if a not in ("Net kâr ($)", "Marj (%)")} for r in satirlar]
    if satirlar:
        ad_alan = next(a for a in satirlar[0] if not a.startswith("_") and a not in ("SKU",))
        grafik = {"x": [str(r.get(ad_alan) or r.get("SKU") or "")[:28] for r in satirlar][:15],
                  "y": [r.get(alan) or 0 for r in satirlar][:15], "etiket": alan}
    return {"baslik": baslik, "kartlar": k, "satirlar": satirlar, "grafik": grafik, "kaynak": kaynak,
            "hedef": "satis/pnl", "uyarilar": uyari, "bos": None, "yetki": None}


def _degerler(e, marj_f):
    m = marj_f(e)
    return {"Adet": e["adet"], "Net ciro ($)": round(e["ciro"], 2), "Net kâr ($)": round(e["kar"], 2),
            "Marj (%)": None if m is None else round(m, 1)}


def _baslik(n, olcu=None):
    p = []
    if n.get("firma"):
        p.append(n["firma"])
    if n.get("marka"):
        p.append(n["marka"])
    if n.get("kategori"):
        p.append(n["kategori"])
    ad = {"satis": OLCU_AD.get(olcu or n.get("olcu"), "Satış"), "seyir": "Aylık " + OLCU_AD.get(n.get("olcu"), "ciro").lower(),
          "iade": "İadeler", "stok": "Stok", "yasli_stok": f"{n.get('esik') or 90} günden eski stok",
          "ariza": "Arıza oranı", "kampanya": "Kampanyalar", "odeme": "Ödemeler", "cek": "Bekleyen çekler",
          "urun": "Ürün özeti"}[n["tip"]]
    if n.get("kirilim") and n["tip"] not in ("seyir",) and n.get("kirilim") != "ay":
        ad += f" · {KIRILIM_AD[n['kirilim']].lower()} bazında"
    if n["tip"] == "odeme" and n.get("kapsam"):
        ad = f"{KAPSAM_AD[n['kapsam']]} ödemeler"
    if n["tip"] == "kampanya" and n.get("kampanya_durum"):
        ad = f"{KAMPANYA_AD[n['kampanya_durum']]} kampanyalar"
    d = f" · {n['donem']['ad']}" if n.get("donem") and n["tip"] in ("satis", "seyir", "iade", "ariza") else ""
    return " · ".join(p + [ad]) + d if p else ad + d


# ── Aylık seyir ─────────────────────────────────────────────────────
def _seyir(n, izin, v):
    from satis.database import satir_kar
    from satis.satis_hesap import aylik_seyir
    from shared.utils import sku_anahtar
    d = n["donem"]
    kanallar = set(n.get("kanallar") or [])
    kartlar = v.kartlar() if (n.get("kategori") or n.get("marka")) else {}
    rows = []
    for s in v.satislar(d["bas"], d["bit"]):
        if kanallar and (s.get("kanal") or "").strip() not in kanallar:
            continue
        kb = _kart_bilgi(kartlar, sku_anahtar(s.get("sku")))
        if n.get("kategori") and not _kat_uyar(kb.get("kategori"), n["kategori"]):
            continue
        if n.get("marka") and not _marka_uyar(kb.get("marka"), n["marka"]):
            continue
        rows.append(s)
    olcu = n.get("olcu") or "ciro"
    uyari = []
    if olcu == "net_kar" and not izin.get("kar"):
        olcu, uyari = "ciro", ["Kâr yalnız yetkili kullanıcıya görünür; ciro gösteriliyor."]
    sey = aylik_seyir(rows, satir_kar)
    if not sey:
        return _bos(_baslik(n), "Bu dönemde satış kaydı yok.", n)
    satirlar = []
    for ay, ciro, kar, adet in sey:
        y, m = ay.split("-")
        r = {"Ay": f"{AY_AD[int(m) - 1]} {y}", "Adet": adet, "Ciro ($)": round(ciro, 2)}
        if izin.get("kar"):
            r["Satış kârı ($)"] = round(kar, 2)
        satirlar.append(r)
    alan = {"ciro": "Ciro ($)", "net_kar": "Satış kârı ($)", "adet": "Adet"}.get(olcu, "Ciro ($)")
    toplam = sum(r.get(alan) or 0 for r in satirlar)
    k = [_kart("Toplam " + alan.replace(" ($)", "").lower(), _para(toplam) if alan != "Adet" else _sayi(toplam),
               f"{len(satirlar)} ay"),
         _kart("Aylık ortalama", (_para(toplam / len(satirlar)) if alan != "Adet" else _sayi(toplam / len(satirlar))))]
    return {"baslik": _baslik(n), "kartlar": k, "satirlar": satirlar,
            "grafik": {"x": [r["Ay"] for r in satirlar], "y": [r.get(alan) or 0 for r in satirlar],
                       "etiket": alan, "cizgi": True},
            "kaynak": "Kâr / P&L'deki aylık seyirle aynı hesap (satır kârı; iade, Ref No ve alınan destek ay ay "
                      "dağıtılmaz).", "hedef": "satis/pnl", "uyarilar": uyari, "bos": None, "yetki": None}


# ── İade ────────────────────────────────────────────────────────────
def _iade(n, izin, v):
    from shared.ana_veri import urun_ad
    from shared.utils import sku_anahtar
    d = n["donem"]
    kanallar = set(n.get("kanallar") or [])
    kartlar = v.kartlar()
    har = _ad_haritasi(kartlar)
    g, sat = {}, {}
    for s in v.satislar(d["bas"], d["bit"]):
        if kanallar and (s.get("kanal") or "").strip() not in kanallar:
            continue
        k = sku_anahtar(s.get("sku"))
        sat[k] = sat.get(k, 0) + int(_f(s.get("adet")))
    for ir in v.iadeler(d["bas"], d["bit"]):
        if kanallar and (ir.get("kanal") or "").strip() not in kanallar:
            continue
        k = sku_anahtar(ir.get("sku"))
        kb = _kart_bilgi(kartlar, k)
        if not _kat_uyar(kb.get("kategori"), n.get("kategori")) or not _marka_uyar(kb.get("marka"), n.get("marka")):
            continue
        kir = n.get("kirilim") or "urun"
        if kir == "urun":
            anah = k
            bas_ = {"SKU": kb.get("sku") or ir.get("sku"),
                    "Ürün": urun_ad(ir.get("sku"), ir.get("urun_adi") or "", har)}
        else:
            anah = (kb.get("kategori") if kir == "kategori" else kb.get("marka")) or "Diğer"
            bas_ = {KIRILIM_AD[kir]: anah}
        e = g.setdefault(anah, {**bas_, "_k": set(), "İade adet": 0, "İade tutarı ($)": 0.0})
        e["_k"].add(k)
        e["İade adet"] += int(_f(ir.get("iade_adet")))
        e["İade tutarı ($)"] += _f(ir.get("iade_net"))
    if not g:
        return _bos(_baslik(n), "Bu dönemde ve süzgeçte iade kaydı yok.", n)
    satirlar = []
    for e in g.values():
        s_adet = sum(sat.get(k, 0) for k in e.pop("_k"))
        e["Satış adet"] = s_adet
        e["İade oranı (%)"] = round(e["İade adet"] / s_adet * 100, 1) if s_adet > 0 else None
        e["İade tutarı ($)"] = round(e["İade tutarı ($)"], 2)
        satirlar.append(e)
    top_adet = sum(r["İade adet"] for r in satirlar)
    top_tutar = sum(r["İade tutarı ($)"] for r in satirlar)
    satirlar = _sirala(satirlar, "İade adet", n.get("sira"), n.get("limit"))
    k = [_kart("İade adet", _sayi(top_adet), f"{len(g)} {KIRILIM_AD[n.get('kirilim') or 'urun'].lower()}"),
         _kart("İade tutarı", _para(top_tutar), "iade net"),
         _kart("Dönem", n["donem"]["ad"])]
    ad = next(a for a in satirlar[0] if a not in ("SKU",))
    return {"baslik": _baslik(n), "kartlar": k, "satirlar": satirlar,
            "grafik": {"x": [str(r[ad])[:28] for r in satirlar][:15], "y": [r["İade adet"] for r in satirlar][:15],
                       "etiket": "İade adet"},
            "kaynak": "Satış › İade kayıtları (iade net tutarı); satış adedi aynı dönemin satış kayıtlarından.",
            "hedef": "satis/iade", "uyarilar": [], "bos": None, "yetki": None}


# ── Stok ────────────────────────────────────────────────────────────
def _stok(n, izin, v):
    from shared.utils import sku_anahtar
    kartlar = v.kartlar()
    pacal = v.pacal()
    secili = []
    for k, u in kartlar.items():
        if n.get("sku") and k != sku_anahtar(n["sku"]):
            continue
        if not _kat_uyar(u.get("kategori"), n.get("kategori")) or not _marka_uyar(u.get("marka"), n.get("marka")):
            continue
        st_ = _f(u.get("bizim_stok"))
        if st_ <= 0:
            continue
        secili.append({"SKU": u.get("sku") or k, "Ürün": u.get("urun_adi") or "", "Kategori": u.get("kategori") or "",
                       "Marka": u.get("marka") or "", "Stok": int(st_),
                       "Birim maliyet ($)": round(_f(pacal.get(k)), 2),
                       "Maliyet ($)": round(st_ * _f(pacal.get(k)), 2)})
    if not secili:
        return _bos(_baslik(n), "Bu süzgeçte stoğu olan ürün yok.", n)
    adet = sum(r["Stok"] for r in secili)
    deger = sum(r["Maliyet ($)"] for r in secili)
    paçalsiz = sum(1 for r in secili if not r["Birim maliyet ($)"])
    kir = n.get("kirilim")
    if kir in ("kategori", "marka"):
        g = {}
        for r in secili:
            a = r[KIRILIM_AD[kir]] or "Diğer"
            x = g.setdefault(a, {KIRILIM_AD[kir]: a, "Ürün sayısı": 0, "Stok": 0, "Maliyet ($)": 0.0})
            x["Ürün sayısı"] += 1
            x["Stok"] += r["Stok"]
            x["Maliyet ($)"] = round(x["Maliyet ($)"] + r["Maliyet ($)"], 2)
        satirlar = _sirala(list(g.values()), "Maliyet ($)", n.get("sira"), n.get("limit"))
    else:
        satirlar = _sirala(secili, "Stok", n.get("sira"), n.get("limit") or 50)
    k = [_kart("Stok", _sayi(adet), f"{len(secili)} ürün"), _kart("Stok değeri", _para(deger), "paçal ile")]
    uy = [f"{paçalsiz} ürünün paçalı yok; değere katılmadı."] if paçalsiz else []
    ad = next(a for a in satirlar[0] if a not in ("SKU",))
    return {"baslik": _baslik(n), "kartlar": k, "satirlar": satirlar,
            "grafik": None if n.get("sku") else {"x": [str(r[ad])[:28] for r in satirlar][:15],
                                                 "y": [r.get("Maliyet ($)") or 0 for r in satirlar][:15],
                                                 "etiket": "Maliyet ($)"},
            "kaynak": "Ürün kartlarındaki bizim stok × paçal (satis.database.get_pacal_map).",
            "hedef": "kayranpm/tum_urunler", "uyarilar": uy, "bos": None, "yetki": None}


def _yasli(n, izin, v):
    from kayranpm.stok_yasi import yasli_satirlar
    h = v.stok_yasi()
    esik = int(n.get("esik") or 90)
    rows = yasli_satirlar(h.get("bizim") or {}, v.pacal(), h.get("bugun") or date.today(), esik)
    kartlar = v.kartlar() if n.get("marka") else {}
    from shared.utils import sku_anahtar
    rows = [r for r in rows if _kat_uyar(r.get("Kategori"), n.get("kategori"))
            and (not n.get("marka") or _marka_uyar(_kart_bilgi(kartlar, sku_anahtar(r.get("SKU"))).get("marka"),
                                                   n["marka"]))]
    if not rows:
        return _bos(_baslik(n), f"{esik} günden eski stok yok.", n)
    ad_alan = f"{esik}+ gün adet"
    adet = sum(_f(r.get(ad_alan)) for r in rows)
    deger = sum(_f(r.get("Yaşlı değer ($)")) for r in rows)
    satirlar = [{a: b for a, b in r.items() if not a.startswith("_")} for r in rows]
    if n.get("sira") == "artan":
        satirlar = list(reversed(satirlar))
    k = [_kart("Yaşlı adet", _sayi(adet), f"{len(rows)} ürün"), _kart("Yaşlı değer", _para(deger), "paçal ile"),
         _kart("Eşik", f"{esik} gün", "depoya girişten, FIFO")]
    return {"baslik": _baslik(n), "kartlar": k, "satirlar": satirlar[:n.get("limit") or 200],
            "grafik": {"x": [str(r.get("SKU"))[:28] for r in satirlar][:15],
                       "y": [r.get("Yaşlı değer ($)") or 0 for r in satirlar][:15], "etiket": "Yaşlı değer ($)"},
            "kaynak": "Ürün yönetimi › Stok yaşı ile aynı hesap (FIFO, satılabilir depolar).",
            "hedef": "kayranpm/stok_yasi", "uyarilar": [], "bos": None, "yetki": None}


# ── Arıza ───────────────────────────────────────────────────────────
def _ariza(n, izin, v):
    from teknikservis.ariza_orani import grup_ozeti
    from shared.utils import sku_anahtar
    d = n["donem"]
    rows = list((v.ariza(d["bas"], d["bit"]) or {}).get("satirlar") or [])
    rows = [r for r in rows if _kat_uyar(r.get("Kategori"), n.get("kategori"))
            and _marka_uyar(r.get("Marka"), n.get("marka"))
            and (not n.get("sku") or sku_anahtar(r.get("SKU")) == sku_anahtar(n["sku"]))]
    rows = [r for r in rows if _f(r.get("Servise gelen")) > 0 or _f(r.get("Arızalı")) > 0]
    if not rows:
        return _bos(_baslik(n), "Bu dönemde ve süzgeçte servise gelen ürün yok.", n)
    ariz = sum(_f(r.get("Arızalı")) for r in rows)
    ulas = sum(_f(r.get("Son kullanıcıya ulaşan")) for r in rows)
    kir = n.get("kirilim") or "urun"
    if kir in ("kategori", "marka"):
        satirlar = grup_ozeti(rows, KIRILIM_AD[kir])
    else:
        satirlar = [{a: b for a, b in r.items() if not a.startswith("_")} for r in rows]
    satirlar = _sirala(satirlar, "Arıza oranı (%)", n.get("sira"), n.get("limit"))
    k = [_kart("Arızalı", _sayi(ariz), f"{len(rows)} üründe"),
         _kart("Arıza oranı", f"%{_sayi(ariz / ulas * 100, 2)}" if ulas > 0 else "—", "alt sınır"),
         _kart("Dönem", d["ad"], "servis kayıtları")]
    ad = "SKU" if kir == "urun" else KIRILIM_AD[kir]
    return {"baslik": _baslik(n), "kartlar": k, "satirlar": satirlar,
            "grafik": {"x": [str(r.get(ad))[:28] for r in satirlar][:15],
                       "y": [r.get("Arıza oranı (%)") or 0 for r in satirlar][:15], "etiket": "Arıza oranı (%)"},
            "kaynak": "Teknik servis › Arıza oranı ile aynı hesap. Payda bitiş tarihine kadarki bütün satışlardır; "
                      "oran bir alt sınırdır.", "hedef": "teknikservis/ariza_orani", "uyarilar": [], "bos": None,
            "yetki": None}


# ── Kampanya ────────────────────────────────────────────────────────
def _kampanya(n, izin, v):
    from kayranpm.kampanya_hesap import kampanya_ozet
    from shared.utils import firma_gorunen_ad
    bugun = date.today()
    kamps, ku_map, pacal = v.kampanyalar()
    satirlar = []
    firma_s = sade(n.get("firma") or "").split(" ")[0]
    for kp in kamps or []:
        o = kampanya_ozet(kp, ku_map.get(kp.get("id")) or [], pacal, bugun)
        if n.get("kampanya_durum") and o.get("durum") != n["kampanya_durum"]:
            continue
        fad = firma_gorunen_ad(kp.get("firma")) or str(kp.get("firma") or "")
        if firma_s and not sade(fad).startswith(firma_s):
            continue
        if n.get("kategori") and not _kat_uyar(kp.get("kategori"), n["kategori"]):
            continue
        r = {"Kampanya": kp.get("kampanya_adi") or "", "Firma": fad,
             "Başlangıç": _tr_tarih(kp.get("baslangic_tarihi")), "Bitiş": _tr_tarih(kp.get("bitis_tarihi")),
             "Durum": KAMPANYA_AD.get(o.get("durum"), ""), "Adet": o.get("adet") or 0,
             "Ciro ($)": round(_f(o.get("ciro")), 2), "Destek ($)": round(_f(o.get("destek")), 2)}
        if izin.get("kar"):
            r["Net ($)"] = round(_f(o.get("net")), 2)
            r["Marj (%)"] = None if o.get("marj") is None else round(o["marj"], 1)
        satirlar.append(r)
    if not satirlar:
        return _bos(_baslik(n), "Bu süzgeçte kampanya yok.", n)
    alan = "Net ($)" if (izin.get("kar") and n.get("olcu") in ("net_kar", "marj")) else "Ciro ($)"
    satirlar = _sirala(satirlar, alan, n.get("sira"), n.get("limit"))
    k = [_kart("Kampanya", _sayi(len(satirlar))), _kart("Ciro", _para(sum(r["Ciro ($)"] for r in satirlar))),
         _kart("Destek", _para(sum(r["Destek ($)"] for r in satirlar)))]
    if izin.get("kar"):
        k.append(_kart("Net", _para(sum(r["Net ($)"] for r in satirlar)), "spiff sonrası"))
    return {"baslik": _baslik(n), "kartlar": k, "satirlar": satirlar, "grafik": None,
            "kaynak": "Ürün yönetimi › Kampanya takip ile aynı hesap (kampanya_ozet).",
            "hedef": "kayranpm/kampanya", "uyarilar": [], "bos": None, "yetki": None}


def _tr_tarih(v):
    g = _gun(v)
    return g.strftime("%d.%m.%Y") if g else "—"


# ── Ödeme / çek ─────────────────────────────────────────────────────
def _odeme(n, izin, v):
    from kayranacc.odeme_hesap import vade_durumu, odendi_mi
    bugun = date.today()
    kapsam = n.get("kapsam") or "bekleyen"
    rows = []
    for o in v.odemeler(kapsam):
        if odendi_mi(o):
            continue
        dur = vade_durumu(o, bugun)
        if kapsam == "gecikmis" and dur != "gecikmis":
            continue
        if kapsam == "bugun" and dur != "bugun":
            continue
        if kapsam == "yarin" and dur != "yarin":
            continue
        if n.get("firma") and not sade(o.get("firma")).startswith(sade(n["firma"]).split(" ")[0]):
            continue
        rows.append({"Vade": _tr_tarih(o.get("vade")), "_v": str(o.get("vade") or ""), "Firma": o.get("firma") or "",
                     "Açıklama": o.get("aciklama") or "", "Kategori": o.get("kategori") or "",
                     "Tutar": round(_f(o.get("tutar_tl")) or _f(o.get("tutar_usd")), 2),
                     "_birim": "₺" if _f(o.get("tutar_tl")) else "$",
                     "_tl": _f(o.get("tutar_tl")), "_usd": _f(o.get("tutar_usd")),
                     "Durum": {"gecikmis": "Gecikmiş", "bugun": "Bugün", "yarin": "Yarın"}.get(dur, "")})
    if not rows:
        return _bos(_baslik(n), "Bu kapsamda bekleyen ödeme yok.", n)
    rows.sort(key=lambda r: (r["_v"] == "", r["_v"]))
    for r in rows:
        r.pop("_v")
    k = [_kart("Ödeme", _sayi(len(rows)), KAPSAM_AD[kapsam].lower()),
         _kart("Toplam TL", _para(sum(r["_tl"] for r in rows), "₺")),
         _kart("Toplam USD", _para(sum(r["_usd"] for r in rows)))]
    return {"baslik": _baslik(n), "kartlar": k, "satirlar": rows, "grafik": None,
            "kaynak": "Muhasebe ödeme kayıtları; vade durumu Bu hafta sayfasındaki kuralla (odeme_hesap).",
            "hedef": "kayranacc/bu_hafta",
            "uyarilar": [], "bos": None, "yetki": None}


def _cek(n, izin, v):
    from kayranacc.database import cek_tutarlari
    rows = []
    for c in v.cekler():
        t = cek_tutarlari(c)
        if t.get("odendi") or _f(t.get("kalan")) <= 0:
            continue
        if n.get("firma") and not sade(c.get("ch_ismi") or "").startswith(sade(n["firma"]).split(" ")[0]):
            continue
        rows.append({"Vade": _tr_tarih(c.get("vade")), "_v": str(c.get("vade") or ""),
                     "Firma": c.get("ch_ismi") or "",
                     "Çek no": c.get("cek_no") or "", "Durum": c.get("durum") or "",
                     "Banka": c.get("banka") or "", "_pb": c.get("_pb"), "_birim": "₺" if c.get("_pb") == "TL" else "$",
                     "Kalan": round(_f(t.get("kalan")), 2)})
    if not rows:
        return _bos(_baslik(n), "Bekleyen çek yok.", n)
    rows.sort(key=lambda r: (r["_v"] == "", r["_v"]))
    for r in rows:
        r.pop("_v")
    tl = sum(r["Kalan"] for r in rows if r["_pb"] == "TL")
    usd = sum(r["Kalan"] for r in rows if r["_pb"] == "USD")
    k = [_kart("Çek", _sayi(len(rows)), "tahsil edilmemiş"), _kart("Kalan TL", _para(tl, "₺")),
         _kart("Kalan USD", _para(usd))]
    return {"baslik": _baslik(n), "kartlar": k, "satirlar": rows, "grafik": None,
            "kaynak": "Muhasebe › Firma çekleri; kalan tutar ekrandaki kuralla (cek_tutarlari).",
            "hedef": "kayranacc/cekler", "uyarilar": [], "bos": None, "yetki": None}


# ── Ürün özeti (SKU) ────────────────────────────────────────────────
def _urun(n, izin, v):
    from shared.utils import sku_anahtar
    k = sku_anahtar(n["sku"])
    kb = v.kartlar().get(k) or {}
    pacal = _f(v.pacal().get(k))
    bugun = date.today()
    bas = date(bugun.year, 1, 1)
    sat = [s for s in v.satislar(bas, bugun) if sku_anahtar(s.get("sku")) == k]
    from satis.database import satir_kar
    ciro = kar = 0.0
    adet = 0
    for s in sat:
        x = satir_kar(s)
        ciro += x["ciro"]
        kar += x["net_kar"]
        adet += x["adet"]
    kartlar = [_kart("Stok", _sayi(_f(kb.get("bizim_stok"))), kb.get("kategori") or ""),
               _kart("Paçal", _para(pacal, "$") if pacal else "—"),
               _kart("Bu yıl satış", _sayi(adet) + " adet", _para(ciro) + " ciro")]
    if izin.get("kar"):
        kartlar.append(_kart("Bu yıl satış kârı", _para(kar), "iade düşülmeden"))
    return {"baslik": f"{kb.get('sku') or n['sku']} · {kb.get('urun_adi') or ''}".strip(" ·"), "kartlar": kartlar,
            "satirlar": [], "grafik": None, "kaynak": "Ürün kartı, paçal ve bu yılın satış kayıtları.",
            "hedef": "urun:" + str(kb.get("sku") or n["sku"]), "uyarilar": [], "bos": None, "yetki": None}


_IS = {"satis": _satis, "seyir": _seyir, "iade": _iade, "stok": _stok, "yasli_stok": _yasli, "ariza": _ariza,
       "kampanya": _kampanya, "odeme": _odeme, "cek": _cek, "urun": _urun}


def cevapla(n, izin, veri=None):
    """izin: {modül: bool, 'kar': bool}. Yetki yoksa cevap yerine 'yetki' metni döner."""
    if not n or not n.get("tip"):
        return None
    mod = YETKI[n["tip"]]
    if not izin.get(mod):
        r = _bos(TIP_BASLIK.get(n["tip"], ""), "", n)
        r["yetki"] = f"Bu soru {MODUL_AD[mod]} verisini kullanıyor; bu modüle yetkiniz yok."
        return r
    return _IS[n["tip"]](n, izin, veri or Veri())


TIP_BASLIK = {"satis": "Satış", "seyir": "Aylık seyir", "iade": "İadeler", "stok": "Stok", "yasli_stok": "Yaşlı stok",
              "ariza": "Arıza oranı", "kampanya": "Kampanyalar", "odeme": "Ödemeler", "cek": "Çekler",
              "urun": "Ürün özeti"}
