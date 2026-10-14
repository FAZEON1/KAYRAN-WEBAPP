# -*- coding: utf-8 -*-
"""SALT-OKUR LİSTE MASASI (Ekim 2026, kalan eski tablolar yeni görünüme).

Eski `st.dataframe` listeleri (Cari ekstre, Son sevkler, Değişiklik günlüğü, Sistem kayıtları, e-Defter…)
ortak masaya (shared/masa.py) bu yardımcıyla geçer: sayfa satırlarını HAM değerlerle verir, sütun türünü
söyler; biçim (1.234,56 · ₺ · $ · %31,1 · 14.10.2026), sıralama anahtarı, arama, açılır süzgeç, satıra
tıklayınca ayrıntı paneli ve telefon kartı burada kurulur. Rakam hesaplamaz: gelen değer aynen gösterilir.

    from shared.masa_liste import kolon, ciz
    ciz(satirlar, [kolon("Tarih", "tarih"), kolon("Firma", ana=True, secim=True), kolon("Adet", "adet")],
        "dpo_son_sevk", toplam=["Adet"], excel="son_sevkler")

Değer yerine (gösterim, sıralama) ikilisi verilebilir (ör. önceden biçimlenmiş zaman). Eski tablonun
"TOPLAM" satırı özet bandına döner (toplam=[sütun adları]); süzgeçten bağımsız, tüm liste."""

TURLER = ("metin", "tarih", "zaman", "adet", "sayi", "tl", "usd", "yuzde", "durum")
SAYISAL = ("adet", "sayi", "tl", "usd", "yuzde")
_SECIM_EN_COK = 80


def kolon(ad, tur="metin", *, ana=False, alt=None, gen=None, secim=False, ara=None, dar=None, genis=False,
          basamak=None, gizli=False):
    """Sütun tanımı. ana: kalın ana sütun (yoksa ilk metin sütunu); alt: ana sütunun altına yazılan sütun adı;
    secim: değerlerinden açılır süzgeç; ara: aramaya girsin mi (varsayılan metin sütunları); dar: telefon
    kartındaki yeri (ana/sag/alt/durum/gizle — verilmezse kendiliğinden); genis: dar ekranda gizlenir;
    gizli: tabloda sütun olarak çizilmez (ör. ana sütunun altında zaten yazan SKU) ama aranır, ayrıntıda ve
    Excel'de görünür."""
    if tur not in TURLER:
        raise ValueError(f"Bilinmeyen sütun türü: {tur}")
    return {"ad": ad, "tur": tur, "ana": ana, "alt": alt, "gen": gen, "secim": secim,
            "ara": (tur in ("metin",)) if ara is None else ara, "dar": dar, "genis": genis, "basamak": basamak,
            "gizli": gizli}


def _sayi(v):
    if v is None or isinstance(v, bool) or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def bicim(tur, v, basamak=None):
    """(gösterim, sıralama anahtarı). Boş değer → ("", None): masa "—" yazar, sıralamada sona düşer."""
    from shared import tasarim as T
    if isinstance(v, tuple) and len(v) == 2:
        return ("" if v[0] is None else str(v[0])), v[1]
    if tur == "durum":
        ad = v[0] if isinstance(v, (list, tuple)) else v
        return ("" if ad in (None, "") else str(ad)), (None if ad in (None, "") else str(ad))
    if tur in SAYISAL:
        f = _sayi(v)
        if f is None:
            return ("" if v in (None, "") else str(v)), None
        if tur == "adet":
            return T.adet(f), f
        if tur == "tl":
            return T.para(f, "₺", 2 if basamak is None else basamak), f
        if tur == "usd":
            return T.para(f, "$", 2 if basamak is None else basamak), f
        if tur == "yuzde":
            return T.oran(f, 1 if basamak is None else basamak), f
        return T.tr_sayi(f, 2 if basamak is None else basamak), f
    if v in (None, ""):
        return "", None
    if tur == "tarih":
        g = T.tarih(v)
        return ("" if g == "—" else g), str(v)[:10]
    if tur == "zaman":
        from shared.cop_kutusu import yerel_zaman
        try:
            g = yerel_zaman(v)
        except Exception:  # noqa: BLE001 — okunamayan zaman olduğu gibi
            g = str(v)
        return (g or str(v)), str(v)
    return str(v), None


def _durum_renk(v):
    if isinstance(v, (list, tuple)) and len(v) > 1:
        return v[1]
    return "soluk"


def veri(satirlar, kolonlar, *, ozet=None, toplam=(), bos="Kayıt yok.", baslik_ipucu="", ara_ipucu=None):
    """Masa tanımı (saf). satirlar: [{sütun adı: ham değer}]."""
    kolonlar = list(kolonlar)
    alan = {k["ad"]: f"k{i}" for i, k in enumerate(kolonlar)}
    ana = next((k for k in kolonlar if k["ana"]), None) or next((k for k in kolonlar if k["tur"] == "metin"),
                                                                kolonlar[0])
    ilk_sayi = next((k["ad"] for k in kolonlar if k["tur"] in SAYISAL and not k.get("gizli")), None)
    ilk_tarih = next((k["ad"] for k in kolonlar if k["tur"] in ("tarih", "zaman") and not k.get("gizli")), None)

    rows = []
    for n, s in enumerate(satirlar or []):
        r = {"id": n + 1}
        detay = []
        for k in kolonlar:
            g, sira = bicim(k["tur"], s.get(k["ad"]), k["basamak"])
            a = alan[k["ad"]]
            r[a] = g
            if sira is not None or k["tur"] in SAYISAL + ("tarih", "zaman"):
                r[a + "__s"] = sira
            if k["tur"] == "durum" and g:
                r["_durum"] = {"ad": g, "renk": _durum_renk(s.get(k["ad"]))}
            if g:
                detay.append([k["ad"], g])
        r["_baslik"] = r[alan[ana["ad"]]] or "—"
        if ana["alt"]:
            r["_alt"] = r[alan[ana["alt"]]]
        r["_detay"] = detay
        rows.append(r)

    sutunlar = []
    for k in kolonlar:
        if k.get("gizli"):
            continue
        c = {"alan": alan[k["ad"]], "ad": k["ad"], "tip": "metin"}
        if k is ana:
            c["tip"] = "ana"
            if k["alt"]:
                c["alt"] = alan[k["alt"]]
        elif k["tur"] == "durum":
            c["tip"] = "durum"
        if k["tur"] in SAYISAL:
            c["sag"] = True
        if k["gen"]:
            c["gen"] = k["gen"]
        if k["genis"]:
            c["genis"] = True
        dar = k["dar"] or ("ana" if k is ana else "sag" if k["ad"] == ilk_sayi else
                           "durum" if k["tur"] == "durum" else "alt" if k["ad"] == ilk_tarih else None)
        if dar and dar != "gizle":
            c["dar"] = dar
        sutunlar.append(c)

    secimler = []
    for k in kolonlar:
        if not k["secim"]:
            continue
        degerler = sorted({r[alan[k["ad"]]] for r in rows if r[alan[k["ad"]]]}, key=lambda x: x.casefold())
        if 1 < len(degerler) <= _SECIM_EN_COK:
            secimler.append({"alan": alan[k["ad"]], "ad": f"Tüm {k['ad'].lower()}",
                             "secenekler": [{"k": d, "ad": d} for d in degerler]})

    ara_k = [k for k in kolonlar if k["ara"]]
    kartlar = list(ozet or [])
    if toplam:       # tek kart sayfa boyu uzamasın: kayıt sayısı + toplamlar
        kartlar.append({"k": "kayit", "et": "Kayıt", "dg": bicim("adet", len(rows))[0]})
    for ad in toplam or ():
        k = next(x for x in kolonlar if x["ad"] == ad)
        top = sum(_sayi(s.get(ad)) or 0 for s in satirlar or [])
        kartlar.append({"k": f"top_{alan[ad]}", "et": f"Toplam {ad.lower()}",
                        "dg": bicim(k["tur"], top, k["basamak"])[0], "renk": "mor" if len(kartlar) < 2 else "yesil",
                        "al": "tüm kayıtlar"})
    sonuc = {
        "gorunumler": [{"k": "tum", "ad": "Tümü", "f": []}],
        "secimler": secimler,
        "sutunlar": sutunlar,
        "satirlar": rows,
        "islemler": [],
        "bos": {"liste": bos, "suzgec": "Süzgece ya da aramaya uyan kayıt yok."},
        "baslik_ipucu": baslik_ipucu or ana["ad"],
    }
    if ara_k:
        sonuc["ara"] = {"alanlar": [alan[k["ad"]] for k in ara_k],
                        "ipucu": ara_ipucu or ", ".join(k["ad"] for k in ara_k[:3])}
    if kartlar:
        sonuc["ozet"] = kartlar
    return sonuc


def excel_bayt(satirlar, kolonlar, sayfa="Liste"):
    """Görünen sütunlar, ham değerlerle (sayılar sayı olarak) Excel'e."""
    from io import BytesIO
    import pandas as pd
    adlar = [k["ad"] for k in kolonlar]
    tablo = []
    for s in satirlar or []:
        sat = {}
        for k in kolonlar:
            v = s.get(k["ad"])
            if isinstance(v, tuple):
                v = v[0]
            elif k["tur"] == "durum" and isinstance(v, (list, tuple)):
                v = v[0]
            elif k["tur"] in ("tarih", "zaman") and v not in (None, ""):
                v = bicim(k["tur"], v)[0]
            sat[k["ad"]] = v
        tablo.append(sat)
    buf = BytesIO()
    pd.DataFrame(tablo, columns=adlar).to_excel(buf, index=False, sheet_name=sayfa[:31])
    return buf.getvalue()


def ciz(satirlar, kolonlar, key, *, excel=None, **kw):
    """Masayı çizer (salt-okur). excel: dosya adı verilirse altına "Excel'e aktar" düğmesi."""
    import streamlit as st
    from shared.masa import masa
    kolonlar = list(kolonlar)
    masa(veri(satirlar, kolonlar, **kw), key)
    if excel and satirlar:
        from datetime import date
        from functools import partial
        st.download_button("Excel'e aktar", data=partial(excel_bayt, satirlar, kolonlar),
                           file_name=f"{excel}_{date.today()}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key=f"{key}_excel", icon=":material/download:")
