# -*- coding: utf-8 -*-
"""Müşteri Satışları — SAF hesap (Ekim 2026). Ekran: kayranpm/musteri_ekran.py.

Girdi: firma_stok haftalık satırları (get_musteri_haftalik_satis; haftada yalnız en
güncel yükleme). Dört kırılım: müşteri · marka · ürün · kategori.

Kurallar:
  satış   = aralıktaki haftaların toplamı (haftalik_satis + satis_magaza)
  stok    = her (müşteri, SKU) için aralıktaki SON rapor (stok_miktari + stok_magaza) —
            TOPLANMAZ. Eskiden aralıktaki bütün raporların stoğu üst üste ekleniyordu.
  haftalık ortalama = satış / aralıktaki rapor haftası sayısı
  kapsama = stok / haftalık ortalama (hafta)
"""

KIRILIM = {"musteri": "Müşteri", "marka": "Marka", "urun": "Ürün", "kategori": "Kategori"}
ALT = {"musteri": "urun", "urun": "musteri", "marka": "urun", "kategori": "urun"}


def _i(v):
    try:
        return int(float(v or 0))
    except (TypeError, ValueError):
        return 0


def satis(r):
    return _i(r.get("haftalik_satis")) + _i(r.get("satis_magaza"))


def stok(r):
    return _i(r.get("stok_miktari")) + _i(r.get("stok_magaza"))


def _hafta(r):
    return str(r.get("yukleme_tarihi") or "")[:10]


def _sku(r):
    return str(r.get("sku") or "").strip()


def _firma(r):
    return str(r.get("firma") or "").strip()


def haftalar(rows):
    return sorted({_hafta(r) for r in rows if _hafta(r)})


def _anahtar(r, kirilim, meta):
    sku = _sku(r)
    if kirilim == "musteri":
        return _firma(r)
    if kirilim == "urun":
        return sku
    m = (meta or {}).get(sku) or {}
    if kirilim == "marka":
        return (m.get("marka") or "").strip() or "Markasız"
    return (m.get("kategori") or "").strip() or "Kategorisiz"


def _son_raporlar(rows):
    """(müşteri, SKU) → aralıktaki son rapor satırı."""
    son = {}
    for r in rows:
        k = (_firma(r), _sku(r))
        if k not in son or _hafta(r) >= _hafta(son[k]):
            son[k] = r
    return son


def grupla(rows, kirilim, meta=None, ad_fn=None, hafta_sayisi=None):
    """Kırılıma göre gruplar, satışa göre azalan. hafta_sayisi verilmezse rows'tan."""
    hs = haftalar(rows)
    n = hafta_sayisi or len(hs) or 1
    toplam = sum(satis(r) for r in rows) or 0
    g = {}
    for r in rows:
        a = _anahtar(r, kirilim, meta)
        x = g.setdefault(a, {"anahtar": a, "satis": 0, "stok": 0, "_seri": {}, "urun_adi": ""})
        x["satis"] += satis(r)
        x["_seri"][_hafta(r)] = x["_seri"].get(_hafta(r), 0) + satis(r)
        if kirilim == "urun" and not x["urun_adi"]:
            x["urun_adi"] = str(r.get("urun_adi") or "").strip()
    for r in _son_raporlar(rows).values():
        g[_anahtar(r, kirilim, meta)]["stok"] += stok(r)
    out = []
    for a, x in g.items():
        ort = x["satis"] / n
        ad = a
        if kirilim == "musteri" and ad_fn:
            try:
                ad = ad_fn(a) or a
            except Exception:  # noqa: BLE001
                ad = a
        out.append({"anahtar": a, "ad": ad, "urun_adi": x["urun_adi"], "satis": x["satis"], "stok": x["stok"],
                    "haftalik_ort": ort, "kapsama": (x["stok"] / ort) if ort > 0 else None,
                    "pay": (x["satis"] / toplam * 100) if toplam else 0.0,
                    "seri": [x["_seri"].get(h, 0) for h in hs]})
    out.sort(key=lambda x: (-x["satis"], str(x["ad"])))
    return out


def detay(rows, kirilim, anahtar, meta=None, ad_fn=None):
    """Seçili grubun alt kırılımı (müşteri → ürünler, ürün → müşteriler, marka/kategori → ürünler).
    Haftalık ortalama aralığın TÜM haftalarına bölünür (grubun sattığı haftalara değil)."""
    alt = [r for r in rows if _anahtar(r, kirilim, meta) == anahtar]
    return grupla(alt, ALT[kirilim], meta, ad_fn=ad_fn, hafta_sayisi=len(haftalar(rows)) or 1)


def ozet(rows):
    hs = haftalar(rows)
    s = sum(satis(r) for r in rows)
    st = sum(stok(r) for r in _son_raporlar(rows).values())
    ort = (s / len(hs)) if hs else 0.0
    return {"satis": s, "stok": st, "hafta": len(hs), "haftalik_ort": ort,
            "kapsama": (st / ort) if ort > 0 else None, "seri": [sum(satis(r) for r in rows if _hafta(r) == h)
                                                                  for h in hs], "haftalar": hs}
