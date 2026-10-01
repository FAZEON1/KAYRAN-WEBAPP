# -*- coding: utf-8 -*-
"""Stok kartı araması (Ürün Yön. sol menü). Bağımlılıksız saf fonksiyon — testte
streamlit/plotly olmadan içe aktarılabilsin diye main.py'den ayrı."""
_SK_HARF = str.maketrans("İIıŞşÇçĞğÜüÖö", "iiissccgguuoo")


def _sk_norm(m):
    return " ".join(str(m or "").translate(_SK_HARF).lower().split())


def stok_karti_ara(liste, sorgu):
    """Stok kartı araması. Her kelime SKU'da ya da adda geçmeli (sıra fark etmez):
    "x24 ips" → X24F100 … IPS. Türkçe harf duyarsız (ı/i, ş/s…).
    Sıralama: tam SKU → SKU ile başlayan → SKU'da geçen → yalnız adda geçen."""
    kel = _sk_norm(sorgu).split()
    if not kel:
        return []
    q = "".join(kel)
    sonuc = []
    for r in liste:
        sku = _sk_norm(r.get("sku"))
        metin = sku + " " + _sk_norm(r.get("urun_adi")) + " " + _sk_norm(r.get("marka"))
        if not all(k in metin for k in kel):
            continue
        sku_b = sku.replace(" ", "")
        derece = 0 if sku_b == q else 1 if sku_b.startswith(q) else 2 if q in sku_b else 3
        sonuc.append((derece, sku, r))
    sonuc.sort(key=lambda t: (t[0], t[1]))
    return [r for _, _, r in sonuc]

