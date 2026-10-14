# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Tüm Ürünler — LİSTE MASASI (Ekim 2026, ortak masa: shared/masa.py).

Liste ortak masada: özet bandı, kategori / marka seçimi, "Zararına" anahtarı, arama, sütun başlığıyla
sıralama. Satıra tıklayınca bugünkü sayfa içi ayrıntı açılır (B.sec("pm_urun", sku) — ayrıntı kodu
kayranpm/main.py'de, DEĞİŞMEDİ). Dışa aktarma: masada ürünleri seç (başlıktaki kutu süzülmüş listenin
hepsini seçer) → "Excel / PDF hazırla" → altta indirme düğmeleri; seçim yoksa tüm ürünler.

Rakamlar eski listeyle aynı fonksiyonlardan: urun_hesap.urun_satiri (paçal, net kâr, marj, maliyet %),
özet bandı main.py'deki eski kartlarla aynı toplamlar. Kâr/marj eski listede de herkese görünüyordu
(shared.kar_gizle bu sayfada kullanılmıyor) — aynı kaldı.

Geri almak için: kayranpm/urunler_ekran.py → URUNLER_MASASI_YENI = False.
"""
from shared.tasarim import tr_sayi

from .masa_ortak import ac_islemi, kisa, usd
from .urun_hesap import urun_filtrele_sirala, urun_satiri

ON_EK = "pm_urun"
AKTAR_KEY = "pm_ul_aktar"
VARSAYILAN_SIRA = ("Stok yaşı · en eski önce", "_stok_yas", True)    # eski listenin ilk sıralaması
_YAS_RENK = {"yesil": "yesil", "sari": "amber", "turuncu": "amber", "kirmizi": "kirmizi"}


def ozet_kartlari(urun_data):
    """Eski sayfanın dört kartı (main.py metrik_satiri) — aynı toplamlar; büyük rakamda kuruş yok."""
    toplam_stok_degeri = sum(u.get("stok_degeri_fcp", 0) for u in urun_data)
    toplam_satis_degeri = sum(u.get("stok_degeri_satis", 0) for u in urun_data)
    toplam_genel_stok = sum(u.get("toplam_stok", u.get("bizim_stok", 0)) for u in urun_data)
    toplam_kanal_stok = sum(u.get("kanal_stok", 0) or 0 for u in urun_data)
    return [
        {"k": "urun", "et": "Toplam ürün", "dg": tr_sayi(len(urun_data)), "renk": "mor", "nokta": False},
        {"k": "stok", "et": "Toplam stok", "dg": f"{tr_sayi(toplam_genel_stok)} adet", "renk": "cyan", "nokta": False,
         "al": (f"Merkez + Happy Life · kanallarda {tr_sayi(toplam_kanal_stok)}" if toplam_kanal_stok
                else "Merkez + Happy Life")},
        {"k": "maliyet", "et": "Depo stok değeri (maliyet)", "dg": kisa(f"${tr_sayi(toplam_stok_degeri)}"),
         "renk": "amber", "nokta": False},
        {"k": "satis", "et": "Depo stok değeri (satış)", "dg": kisa(f"${tr_sayi(toplam_satis_degeri)}"),
         "renk": "yesil", "nokta": False},
    ]


def sirali_satirlar(urun_data):
    """urun_satiri satırları, eski listenin varsayılan sırasıyla (stok yaşı, en eski önce)."""
    tum = [urun_satiri(u) for u in urun_data or []]
    return urun_filtrele_sirala(tum, sira=VARSAYILAN_SIRA[1], azalan=VARSAYILAN_SIRA[2])


def _fiyat_metni(fcp, satis):
    if fcp and satis:
        return f"{usd(fcp)} → {usd(satis)}"
    if satis:
        return f"satış {usd(satis)}"
    if fcp:
        return f"paçal {usd(fcp)}"
    return "fiyat yok"


def _satir(r, firma_ad):
    sku = r["SKU"]
    nk, marj, fcp, satis = r.get("Net Kar ($)"), r.get("Net Marj (%)"), r.get("Final Cost ($)"), r.get("Satış ($)")
    yas_renk = _YAS_RENK.get(r.get("_stok_renk"))
    kanallar = [f"{firma_ad(k)} {tr_sayi(a)}" for k, a in r.get("_kanal_stok", []) if a]
    kat, mar = str(r.get("Kategori") or "").strip(), str(r.get("Marka") or "").strip()
    alt = " · ".join(x for x in (*kanallar, kat, mar, "EOL" if r.get("_eol") else "") if x)
    g5f, zincir = int(r.get("G5F Depo") or 0), int(r.get("Kanal dahil") or 0)
    mal = r.get("Maliyet %")
    return {
        "id": sku, "sku": sku, "ad": str(r.get("Ürün Adı") or "").strip() or sku, "alt": alt,
        "alt_dar": " · ".join(x for x in (sku, kat) if x),
        "kat": kat, "mar": mar,
        # müşteri süzgeci: ürünün stoğu olan müşteriler (satırın alt yazısındaki firmalarla aynı; _kanal_stok her
        # firmayı 0 adetle de taşır) — liste alanı, masa "içerir" ile eşler
        "mus": sorted({firma_ad(k) for k, a in r.get("_kanal_stok", []) if a and firma_ad(k)}),
        "stok_m": tr_sayi(g5f), "stok_m__s": g5f,
        "stok_alt": f"kanal dahil {tr_sayi(zincir)}" if zincir and zincir != g5f else "",
        "fiyat_m": _fiyat_metni(fcp, satis), "fiyat_m__s": float(satis or 0),
        "mal_m": f"%{tr_sayi(mal, 1)}" if mal is not None else "", "mal_m__s": mal,
        "kar_m": usd(nk) if nk is not None else "", "kar_m__s": nk,
        "marj_m": f"%{tr_sayi(abs(marj or 0), 1)}" if nk is not None else "", "marj_m__s": marj,
        "marj_alt": ("zarar" if nk < 0 else "marj") if nk is not None else "",
        "marj_renk": ("kirmizi" if nk < 0 else "yesil") if nk is not None else "",
        "risk": tr_sayi(r.get("_risk") or 0), "risk__s": float(r.get("_risk") or 0),
        "yas": f"{r['_stok_yas']} gün", "yas__s": int(r.get("_stok_yas") or 0),
        "_durum": {"ad": f"{r['_stok_yas']} gün", "renk": yas_renk} if yas_renk else {},
        "zarar": bool(nk is not None and nk < 0), "eol": bool(r.get("_eol")), "_soluk": bool(r.get("_eol")),
        "_baslik": str(r.get("Ürün Adı") or "").strip() or sku, "_alt": sku,
    }


def masa_verisi(urun_data, dar=False, firma_ad=None):
    """Masanın tanımı. dar=True: ayrıntının yanındaki sütun (az sütun, özet ve dışa aktarma yok).
    firma_ad: kanal kodu → görünen ad (varsayılan shared.utils.firma_gorunen_ad)."""
    if firma_ad is None:
        from shared.utils import firma_gorunen_ad as firma_ad
    rows = sirali_satirlar(urun_data)
    satirlar = [_satir(r, firma_ad) for r in rows]
    kategoriler = sorted({s["kat"] for s in satirlar if s["kat"]}, key=str.lower)
    markalar = sorted({s["mar"] for s in satirlar if s["mar"]}, key=str.lower)
    musteriler = sorted({m for s in satirlar for m in s["mus"]}, key=str.lower)
    zarar_say = sum(1 for s in satirlar if s["zarar"])
    if dar:
        sutunlar = [
            {"alan": "ad", "ad": "Ürün", "tip": "ana", "alt": "alt_dar"},
            {"alan": "stok_m", "ad": "Stok", "sag": True, "gen": "72px", "dar": "sag"},
            {"alan": "marj_m", "ad": "Marj", "sag": True, "gen": "82px", "alt": "marj_alt", "alt_renk": "marj_renk",
             "dar": "alt"},
        ]
    else:
        sutunlar = [
            {"alan": "sku", "ad": "SKU", "tip": "metin", "gen": "150px", "dar": "alt"},
            {"alan": "ad", "ad": "Ürün", "tip": "ana", "alt": "alt"},
            {"alan": "stok_m", "ad": "G5F stok", "sag": True, "gen": "96px", "alt": "stok_alt", "dar": "sag"},
            {"alan": "fiyat_m", "ad": "Paçal → satış", "sag": True, "gen": "170px"},
            {"alan": "mal_m", "ad": "Maliyet %", "sag": True, "gen": "92px", "genis": True},
            {"alan": "kar_m", "ad": "Net kâr", "sag": True, "gen": "100px", "genis": True},
            {"alan": "marj_m", "ad": "Net marj", "sag": True, "gen": "92px", "alt": "marj_alt", "alt_renk": "marj_renk"},
            {"alan": "risk", "ad": "Risk", "sag": True, "gen": "64px", "genis": True},
            {"alan": "yas", "ad": "Stok yaşı", "tip": "durum", "gen": "104px"},
        ]
    islemler = [ac_islemi("Ürünü aç")]
    if not dar:
        islemler.append({"k": "aktar", "ad": "Dışa aktar", "okuma": True, "yalniz_toplu": True,
                         "toplu": {"ad": "Excel / PDF hazırla", "alanlar": []}})
    return {
        "ozet": [] if dar else ozet_kartlari(urun_data or []),
        "secimler": [{"alan": "kat", "ad": "Tüm kategoriler", "secenekler": [{"k": k, "ad": k} for k in kategoriler]},
                     {"alan": "mar", "ad": "Tüm markalar", "secenekler": [{"k": m, "ad": m} for m in markalar]},
                     {"alan": "mus", "ad": "Tüm müşteriler", "secenekler": [{"k": m, "ad": m} for m in musteriler]}],
        "anahtarlar": [{"k": "zarar", "ad": f"Zararına ({zarar_say})" if dar else f"Yalnız zararına satılanlar ({zarar_say})",
                        "f": [["zarar", "eq", True]]}],
        "ara": {"alanlar": ["sku", "ad"], "ipucu": "SKU ya da ürün adı"},
        "sutunlar": sutunlar,
        "satirlar": satirlar,
        "islemler": islemler,
        "tik": "ac",
        "bos": {"liste": "Henüz ürün yok.", "suzgec": "Filtreyle eşleşen ürün yok."},
        "baslik_ipucu": "Ürünler",
    }


def aktarilacak(urun_data, skular=None):
    """Excel / PDF'e gidecek urun_satiri satırları: varsayılan sırada; skular verilirse yalnız onlar."""
    rows = sirali_satirlar(urun_data)
    if skular is None:
        return rows
    s = set(skular)
    return [r for r in rows if r["SKU"] in s]


def yurutucu(state=None):
    """shared.masa.calistir için. ac: bugünkü sayfa içi ayrıntı (B.sec) — sayfa yeniden çalışır, önbellek
    boşalmaz. aktar: seçilen SKU'lar dışa aktarma için oturuma yazılır (altta indirme düğmeleri)."""
    def yurut(temiz):
        ids = temiz["ids"]
        if temiz["islem"] == "ac":
            from shared import bilesen as B
            B.sec(ON_EK, ids[0])
            return {"ok": True, "sessiz": True, "onbellek": False}
        if temiz["islem"] == "aktar":
            ss = state
            if ss is None:
                import streamlit as st
                ss = st.session_state
            ss[AKTAR_KEY] = list(ids)
            return {"ok": True, "onbellek": False,
                    "mesaj": f"{tr_sayi(len(ids))} ürün dışa aktarmaya hazır; listenin altındaki Excel ya da PDF."}
        return {"ok": False, "mesaj": "Bilinmeyen işlem."}
    return yurut
