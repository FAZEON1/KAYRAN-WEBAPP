# -*- coding: utf-8 -*-
"""Yeni uygulamanın sol menüsü (Faz 0): kim hangi modülü ve sayfayı görür.

Görünürlük kuralı YENİDEN YAZILMAZ: eski uygulamanın komut paleti (shared.gezinme.palet_ogeleri)
neyi gösteriyorsa menü de onu gösterir. Burada yalnız o düz listeyi modül → grup → sayfa ağacına
dizeriz. Henüz yeni uygulamaya taşınmamış sayfa eski uygulamada açılır (`eski` bağlantısı:
?s=modül&p=sayfa — app.py ve shared.gezinme.adres_oku bunu anlar).
"""
from urllib.parse import urlencode

# Yeni uygulamada hazır olan sayfalar (faz faz büyür). Anahtar: "modül/sayfa" ya da tek sayfalı modülde "modül".
YENI_SAYFALAR = {"anasayfa"}


def _eski(eski_url, mod, kod=None):
    if not eski_url:
        return None
    q = {"s": mod}
    if kod:
        q["p"] = kod
    return f"{eski_url.rstrip('/')}/?{urlencode(q)}"


def menu_agaci(yetkiler, ozel, kullanici, eski_url="", kosul=None):
    """[{kod, ad, ikon, yeni, eski, sayfalar: [{kod, ad, grup, yeni, eski}]}] — yetkiye göre süzülmüş.

    yetkiler: {modül: bool} · ozel: kullanıcının özel yetkileri (küme) · kosul(ad, kullanici) → bool
    (Kâr / P&L, Toplam aktifler gibi koşullu sayfalar; verilmezse özel yetki adıyla aynı sayılır)."""
    from shared.gezinme import MODULLER, palet_ogeleri
    ozel = set(ozel or ())
    kosul = kosul or (lambda ad, _k: ad in ozel)
    gorunen = {o["id"] for o in palet_ogeleri(yetkiler or {}, ozel, kullanici, kosul) if o["tur"] == "sayfa"}
    out = []
    for m in MODULLER:
        k = m["kod"]
        gruplar = {kod: ad for _gk, ad, kodlar in (m.get("gruplar") or []) for kod in kodlar}
        # Grubu tanımlı modülde sayfalar grup sırasıyla (eski uygulamanın iki katlı menüsü gibi);
        # gruba girmeyen sayfa sona.
        sira = {kod: i for i, kod in enumerate(kod for _gk, _ad, kodlar in (m.get("gruplar") or []) for kod in kodlar)}
        sayfalar = [{"kod": kod, "ad": ad, "grup": gruplar.get(kod),
                     "yeni": f"{k}/{kod}" in YENI_SAYFALAR, "eski": _eski(eski_url, k, kod)}
                    for _sec, kod, ad, _ks in (m.get("sayfalar") or []) if f"{k}/{kod}" in gorunen]
        sayfalar.sort(key=lambda p: sira.get(p["kod"], len(sira)))
        tek = not m.get("sayfalar")
        if (tek and k not in gorunen and k != "anasayfa") or (not tek and not sayfalar):
            continue
        out.append({"kod": k, "ad": m["ad"], "ikon": m.get("ikon") or "apps",
                    "yeni": k in YENI_SAYFALAR, "eski": _eski(eski_url, k), "sayfalar": sayfalar})
    return out
