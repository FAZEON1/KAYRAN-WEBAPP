# -*- coding: utf-8 -*-
"""Paçal maliyet — SAF hesap (Ekim 2026, ana veri entegrasyonu Faz 2a).

Bugün aynı ürünün paçalı üç yoldan hesaplanıyor:
  Tüm Ürünler  get_sku_maliyet_ozet()[ham SKU]   yoldaki parti HARİÇ, SKU ham, yurt içi YOK
  Stok kartı   get_sku_alim_detay(ham SKU) ort.  yoldaki parti DAHİL, SKU ham, yurt içi YOK
  P&L / TS     get_pacal_map()[sku_anahtar]      yoldaki HARİÇ, SKU normalize ama yazımlardan
                                                 yalnız İLKİ, yurt içi alış VAR
Hedef (yeni, tek tanım):
  yoldaki parti HARİÇ · aynı ürünün TÜM SKU yazımlarındaki partiler BİRLEŞİK adet-ağırlıklı
  ortalama · ithalatı olmayan / paçalı 0 olan üründe yurt içi alış fiyatı.

Girdi 'satirlar': ithalat.database.get_parti_satirlari() — her ithalat kalemi için
{sku, dosya_id, yolda, adet, fob, final, tarih}. Bu modül veritabanına gitmez.
"""


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _ort(satirlar):
    adet = sum(_f(s["adet"]) for s in satirlar)
    return (sum(_f(s["final"]) * _f(s["adet"]) for s in satirlar) / adet) if adet > 0 else 0.0


def _grupla(satirlar, anahtar_fn, yolda_dahil):
    g = {}
    for s in satirlar or []:
        if _f(s.get("adet")) <= 0 or (s.get("yolda") and not yolda_dahil):
            continue
        k = anahtar_fn(s.get("sku"))
        if k:
            g.setdefault(k, []).append(s)
    return g


def _ham(sku):
    return str(sku or "").strip()


# ── Bugünkü üç hesap (karşılaştırma için birebir taklit) ─────────────
def eski_tum_urunler(satirlar):
    """{ham SKU: paçal} — get_sku_maliyet_ozet ile aynı kural."""
    return {k: _ort(v) for k, v in _grupla(satirlar, _ham, yolda_dahil=False).items()}


def eski_stok_karti(satirlar):
    """{ham SKU: paçal} — stok kartının get_sku_alim_detay ortalaması (yoldakiler DAHİL)."""
    return {k: _ort(v) for k, v in _grupla(satirlar, _ham, yolda_dahil=True).items()}


def eski_pnl(satirlar, kart_alis, sku_fn):
    """{sku_anahtar: paçal} — get_pacal_map ile aynı kural: özet sırasında İLK yazım kazanır,
    paçalı olmayan / 0 olana yurt içi alış."""
    out = {}
    for ham, p in eski_tum_urunler(satirlar).items():
        k = sku_fn(ham)
        if k and k not in out:
            out[k] = p
    for sku, alis in (kart_alis or {}).items():
        k = sku_fn(sku)
        if k and _f(alis) > 0 and out.get(k, 0) <= 0:
            out[k] = _f(alis)
    return out


# ── Yeni tek tanım ───────────────────────────────────────────────────
def yeni_pacal(satirlar, kart_alis, sku_fn):
    """{sku_anahtar: paçal} — yoldaki hariç, tüm yazımlar birleşik, yurt içi yedek."""
    out = {k: _ort(v) for k, v in _grupla(satirlar, sku_fn, yolda_dahil=False).items()}
    for sku, alis in (kart_alis or {}).items():
        k = sku_fn(sku)
        if k and _f(alis) > 0 and out.get(k, 0) <= 0:
            out[k] = _f(alis)
    return out


# ── Karşılaştırma tablosu ────────────────────────────────────────────
SEBEP_YOLDA = "Stok kartı yoldaki partiyi de sayıyor"
SEBEP_YAZIM = "Aynı ürün birden çok SKU yazımıyla ithal edilmiş"
SEBEP_KART = "Kart SKU'su ithalattakinden farklı yazılmış"
SEBEP_YURTICI = "Yurt içi alış — Tüm Ürünler ve stok kartı göstermiyor"
SEBEP_DIGER = "Diğer"

def karsilastir(satirlar, kartlar, sku_fn, esik_yuzde=0.5):
    """Her ürün için dört değer + farkın sebebi. Yalnız en az bir ekranın yeni değerden
    esik_yuzde'den fazla saptığı (ya da biri boşken diğeri dolu olduğu) ürünler döner.

    kartlar: [{sku, urun_adi, alis_fiyati}] (urunler tablosu).
    Döner: (satirlar, ozet) — ozet = {"urun": n, "farkli": n, "sebep": {sebep: n}}."""
    kart_alis = {_ham(k.get("sku")): k.get("alis_fiyati") for k in kartlar or []}
    A, B = eski_tum_urunler(satirlar), eski_stok_karti(satirlar)
    C, Y = eski_pnl(satirlar, kart_alis, sku_fn), yeni_pacal(satirlar, kart_alis, sku_fn)

    yazimlar, yoldaki = {}, {}
    for s in satirlar or []:
        if _f(s.get("adet")) <= 0:
            continue
        k = sku_fn(s.get("sku"))
        yazimlar.setdefault(k, set()).add(_ham(s.get("sku")))
        if s.get("yolda"):
            yoldaki[_ham(s.get("sku"))] = yoldaki.get(_ham(s.get("sku")), 0) + _f(s.get("adet"))

    kart_by_k = {}
    for k in kartlar or []:
        kart_by_k.setdefault(sku_fn(k.get("sku")), k)
    anahtarlar = set(kart_by_k) | set(Y) | set(yazimlar)

    def _sapma(eski, yeni):
        if not eski and not yeni:
            return 0.0
        if not eski or not yeni:
            return 100.0
        return abs(eski - yeni) / yeni * 100

    out, sebep_say, n_urun = [], {}, 0
    for k in sorted(a for a in anahtarlar if a):
        kart = kart_by_k.get(k) or {}
        ham_kart = _ham(kart.get("sku")) if kart else ""
        a = A.get(ham_kart) if kart else None          # Tüm Ürünler yalnız kartı olanı gösterir
        b = B.get(ham_kart) if kart else None
        c, y = C.get(k), Y.get(k)
        if not any((a, b, c, y)):
            continue
        n_urun += 1
        sapma = max(_sapma(v or 0.0, y or 0.0) for v in ((a, b) if kart else ()) + (c,))
        if sapma <= esik_yuzde:
            continue
        sebepler = []                                   # (sabit etiket, ayrıntı)
        if ham_kart and yoldaki.get(ham_kart) and b and a is not None and abs((b or 0) - (a or 0)) > 1e-9:
            sebepler.append((SEBEP_YOLDA, f"{int(yoldaki[ham_kart])} adet"))
        yz = sorted(yazimlar.get(k, ()))
        if len(yz) > 1:
            sebepler.append((SEBEP_YAZIM, " · ".join(yz)))
        if ham_kart and yz and ham_kart not in yz:
            sebepler.append((SEBEP_KART, " · ".join(yz)))
        if not yz and _f(kart.get("alis_fiyati")) > 0:
            sebepler.append((SEBEP_YURTICI, ""))
        if not sebepler:
            sebepler.append((SEBEP_DIGER, ""))
        for etk, _ in sebepler:
            sebep_say[etk] = sebep_say.get(etk, 0) + 1
        out.append({"SKU": ham_kart or (yz[0] if yz else k), "Ürün": kart.get("urun_adi") or "",
                    "Tüm Ürünler maliyeti": a, "Ürün kartı maliyeti": b, "P&L maliyeti": c, "Yeni maliyet": y,
                    "En büyük sapma %": round(sapma, 1),
                    "Sebep": " · ".join(f"{e} ({d})" if d else e for e, d in sebepler)})
    out.sort(key=lambda r: -r["En büyük sapma %"])
    return out, {"urun": n_urun, "farkli": len(out), "sebep": sebep_say}
