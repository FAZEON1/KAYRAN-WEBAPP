# -*- coding: utf-8 -*-
"""Sipariş yüklemede eksik stoğu başka depodan tamamlama (Ekim 2026).

Sipariş Excel'i yüklenirken bir ürün, düşeceği depoda (Excel'deki ÇIKIŞ DEPOSU ya da ekrandaki
varsayılan) yetmiyorsa eskiden yalnız "Yetersiz stok" uyarısı çıkıyor, kalan o depoyu eksiye
düşürüyordu. Şimdi stoğu olan diğer depolar adetleriyle gösterilir; kullanıcı kalanı hangi
depolardan tamamlayacağını tek tek seçer.

Satış kayıtlarına dokunulmaz (satislar tablosunda depo yok); yalnız STOK DÜŞÜMÜ planı değişir:
    plan = {(hedef_depo, sku): [(kaynak_depo, adet), ...]}
ice_aktar_satislar(tamamla=plan) bu adetleri hedef depodan alıp kaynak depolardan düşer.
"""


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def eksikler(ihtiyac, dagilim_fn, sinir=60):
    """ihtiyac: {hedef_depo: {sku: adet}}; dagilim_fn(sku) → {depo: mevcut}.
    Döner: [{hedef, sku, gerek, mevcut, eksik, secenekler: [(depo, mevcut)]}] — yalnız eksik olanlar.
    secenekler: hedef dışında stoğu olan depolar, çoktan aza."""
    out = []
    for hedef, skular in (ihtiyac or {}).items():
        for sku, gerek in list((skular or {}).items())[:sinir]:
            dag = dagilim_fn(sku) or {}
            mevcut = max(_f(dag.get(hedef)), 0)
            gerek = _f(gerek)
            if gerek <= mevcut:
                continue
            sec = sorted(((d, _f(m)) for d, m in dag.items() if d != hedef and _f(m) > 0),
                         key=lambda x: (-x[1], x[0]))
            out.append({"hedef": hedef, "sku": sku, "gerek": gerek, "mevcut": mevcut,
                        "eksik": gerek - mevcut, "secenekler": sec})
    return out


def dagit(eksik, secilen, secenekler):
    """Eksiği, kullanıcının SEÇTİĞİ SIRAYLA depolardan, her depodaki mevcut kadar alır.
    Döner: ([(depo, adet)], karsilanamayan). Karşılanamayan kısım hedef depoda kalır (eksiye düşer)."""
    mevcut = dict(secenekler or [])
    kalan = _f(eksik)
    plan = []
    for d in secilen or []:
        if kalan <= 0:
            break
        al = min(kalan, max(_f(mevcut.get(d)), 0))
        if al > 0:
            plan.append((d, al))
            kalan -= al
    return plan, max(kalan, 0)


def uygula(depo_gruplu, plan, sku_norm=lambda s: s):
    """Stok düşümü haritasına planı uygular: {depo: {sku: adet}} → yeni harita.
    Taşınan adet, hedef depoda o SKU için GERÇEKTEN düşülecek adetle sınırlıdır (zaten kayıtlı
    olduğu için atlanan satırlar düşülmez; onların planı da uygulanmaz)."""
    yeni = {d: dict(h) for d, h in (depo_gruplu or {}).items()}
    for (hedef, sku), kaynaklar in (plan or {}).items():
        h = yeni.get(hedef) or {}
        anahtar = next((k for k in h if sku_norm(k) == sku_norm(sku)), None)
        if anahtar is None:
            continue
        for kaynak, adet in kaynaklar or []:
            tasi = min(_f(adet), _f(h.get(anahtar)))
            if tasi <= 0 or kaynak == hedef:
                continue
            h[anahtar] = _f(h[anahtar]) - tasi
            k = yeni.setdefault(kaynak, {})
            k[anahtar] = _f(k.get(anahtar)) + tasi
        if _f(h.get(anahtar)) <= 0:
            h.pop(anahtar, None)
    return {d: h for d, h in yeni.items() if h}
