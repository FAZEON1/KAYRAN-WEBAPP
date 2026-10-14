# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Sipariş Önerisi — LİSTE MASALARI (Ekim 2026, ortak masa: shared/masa.py).

İki masa:
  öneriler   : stoğu eşikten önce bitecek ürünler (analitik.siparis_onerisi_listesi); yan panelde
               "Siparişe ekle" — miktar öneriyle gelir → database.ekle_siparis_onerisi("G5F", sku, ad, miktar)
               (eski satırdaki miktar kutusu + düğmeyle aynı çağrı).
  kayıtlar   : onay bekleyen ve sonuçlanan öneriler; Onayla / Reddet (tek ya da seçilenlere toplu) →
               database.onayla_siparis / reddet_siparis (eski satır düğmeleriyle aynı fonksiyonlar).
Eşik ayarı (uretim_suresi_*) sayfada eskisi gibi.

Geri almak için: kayranpm/siparis_ekran.py → SIPARIS_MASASI_YENI = False.
"""
from shared.tasarim import tr_sayi

from .urun_hesap import siparis_durum_adi, tarih_tr

DURUM_RENK = {"acil": "kirmizi", "yaklasıyor": "amber", "planlama": "amber"}
DURUM_AD = {"acil": "Acil", "yaklasıyor": "30 gün içinde", "planlama": "60 gün içinde"}
_DURUM_SIRA = {"acil": 0, "yaklasıyor": 1, "planlama": 2}
GECMIS_RENK = {"bekliyor": "amber", "onaylandi": "yesil", "reddedildi": "kirmizi"}


def _mesaj_kisa(m):
    """'ACİL — 74g'de biter' → '74g'de biter' (siparis_ekran ile aynı)."""
    m = str(m or "").strip()
    return m.split(" — ", 1)[1] if " — " in m else m


def oneri_verisi(liste, urun_dict, bekleyen, firma_ad=str):
    """Öneriler masası. liste: siparis_onerisi_listesi(); urun_dict: {sku: tum_urunler_listesi satırı};
    bekleyen: urun_hesap.bekleyen_haritasi(kayıtlar)."""
    say = {d: sum(1 for u in liste if u.get("siparis_durum") == d) for d in DURUM_AD}
    satirlar = []
    for u in liste or []:
        sku = u["sku"]
        d = u.get("siparis_durum", "")
        ud = urun_dict.get(sku, {})
        fcp, satis = ud.get("final_cost_price") or 0, ud.get("satis_fiyati") or 0
        kanal = " · ".join(f'{firma_ad(fd["firma"])} {fd["stok"]}' for fd in u.get("firma_detay", [])
                           if fd.get("stok", 0) > 0)
        oneri = int(u.get("oneri_miktar", 0) or 0)
        bek = bekleyen.get(sku)
        mesaj = _mesaj_kisa(u.get("siparis_mesaj", ""))
        hafta = f'haftalık {tr_sayi(u.get("ortalama_haftalik_satis", 0) or 0, 1)}'
        fiyat = f"paçal ${tr_sayi(fcp, 2)} → satış ${tr_sayi(satis, 2)}" if fcp else ""
        satirlar.append({
            "id": sku, "sku": sku, "ad": str(u.get("urun_adi") or "").strip() or sku, "durum": d,
            "durum__s": _DURUM_SIRA.get(d, 9), "_durum": {"ad": DURUM_AD.get(d, d or "—"), "renk": DURUM_RENK.get(d, "silik")},
            "mesaj": mesaj, "hafta": hafta,
            "stok_m": tr_sayi(u.get("bizim_stok", 0)), "stok_m__s": float(u.get("bizim_stok", 0) or 0), "kanal": kanal,
            "fiyat": fiyat,
            "oneri_m": f"{tr_sayi(oneri)} adet", "oneri_m__s": oneri, "oneri_v": max(oneri, 1),
            "bek_m": f"bekliyor · {tr_sayi(bek)} adet" if bek else "", "bek_renk": "amber" if bek else "",
            "_baslik": str(u.get("urun_adi") or "").strip() or sku, "_alt": sku,
            "_buyuk": f"{tr_sayi(oneri)} adet", "_buyuk_alt": "öneri",
            "_detay": [x for x in (["Stok bitişi", mesaj], ["G5F stok", tr_sayi(u.get("bizim_stok", 0))],
                                   ["Satış", hafta], ["Kanallarda", kanal], ["Fiyat", fiyat],
                                   ["Onay bekleyen", f"{tr_sayi(bek)} adet" if bek else ""]) if x[1]],
            "_not": str(u.get("oneri_mesaj") or "").strip(),
        })
    return {
        "ozet": [{"k": "acil", "et": "Acil", "dg": tr_sayi(say["acil"]), "renk": "kirmizi", "suz": "acil"},
                 {"k": "yaklasıyor", "et": "30 gün içinde", "dg": tr_sayi(say["yaklasıyor"]), "renk": "amber",
                  "suz": "yaklasıyor"},
                 {"k": "planlama", "et": "60 gün içinde", "dg": tr_sayi(say["planlama"]), "renk": "amber",
                  "suz": "planlama"}],
        "gorunumler": [{"k": "tumu", "ad": "Tümü", "f": []}]
                      + [{"k": d, "ad": a, "f": [["durum", "eq", d]]} for d, a in DURUM_AD.items()],
        "ara": {"alanlar": ["sku", "ad", "kanal"], "ipucu": "SKU ya da ürün adı"},
        "sutunlar": [
            {"alan": "ad", "ad": "Ürün", "tip": "ana", "alt": "sku"},
            {"alan": "mesaj", "ad": "Stok bitişi", "alt": "hafta", "gen": "150px", "dar": "alt"},
            {"alan": "stok_m", "ad": "G5F stok", "sag": True, "alt": "kanal", "gen": "150px", "genis": True},
            {"alan": "oneri_m", "ad": "Öneri", "sag": True, "alt": "bek_m", "alt_renk": "bek_renk", "gen": "150px",
             "dar": "sag"},
            {"alan": "durum", "ad": "Durum", "tip": "durum", "gen": "132px"},
        ],
        "satirlar": satirlar,
        "islemler": [{"k": "ekle", "ad": "Siparişe ekle", "dugme": "Sipariş önerisi oluştur", "birincil": True,
                      "ipucu": "Öneri 'onay bekleyen' listesine eklenir; onay ya da red orada.",
                      "alanlar": [{"ad": "miktar", "et": "Miktar (adet)", "tip": "sayi", "varsayilan_alan": "oneri_v",
                                   "ondalik": 0, "zorunlu": True, "en_az": 1, "tam": True}]}],
        "bos": {"liste": "Sipariş gereken ürün yok.", "suzgec": "Bu süzgece uyan ürün yok."},
        "baslik_ipucu": "Sipariş önerileri",
    }


def kayit_verisi(kayitlar):
    """Onay bekleyen + sonuçlanan öneriler masası (get_siparis_onerileri sırasıyla: en yeni üstte)."""
    satirlar = []
    for sp in kayitlar or []:
        d = sp.get("durum", "")
        satirlar.append({
            "id": sp.get("id"), "sku": str(sp.get("sku") or ""), "ad": str(sp.get("urun_adi") or "").strip() or "—",
            "durum": d, "_durum": {"ad": siparis_durum_adi(d), "renk": GECMIS_RENK.get(d, "silik")},
            "miktar_m": f"{tr_sayi(sp.get('oneri_miktari') or 0)} adet", "miktar_m__s": float(sp.get("oneri_miktari") or 0),
            "olusturma": tarih_tr(sp.get("olusturma_tarihi"), saat=True),
            "olusturma__s": str(sp.get("olusturma_tarihi") or ""),
            "sonuc": tarih_tr(sp.get("onay_tarihi"), saat=True) if sp.get("onay_tarihi") else "",
            "sonuc__s": str(sp.get("onay_tarihi") or ""),
            "_baslik": str(sp.get("urun_adi") or "").strip() or "—", "_alt": str(sp.get("sku") or ""),
            "_buyuk": f"{tr_sayi(sp.get('oneri_miktari') or 0)} adet",
            "_detay": [x for x in (["Oluşturma", tarih_tr(sp.get("olusturma_tarihi"), saat=True)],
                                   ["Sonuç", tarih_tr(sp.get("onay_tarihi"), saat=True) if sp.get("onay_tarihi") else ""],
                                   ["Firma", str(sp.get("firma") or "")]) if x[1]],
            "_soluk": d == "reddedildi",
        })
    bekl = [["durum", "eq", "bekliyor"]]
    gorunum = [{"k": "bekleyen", "ad": "Onay bekleyen", "f": bekl},
               {"k": "sonuclanan", "ad": "Sonuçlanan", "f": [["durum", "ne", "bekliyor"]]},
               {"k": "tumu", "ad": "Tümü", "f": []}]
    if not any(s["durum"] == "bekliyor" for s in satirlar):
        gorunum = [gorunum[1], gorunum[0], gorunum[2]]
    return {
        "gorunumler": gorunum,
        "ara": {"alanlar": ["sku", "ad"], "ipucu": "SKU ya da ürün adı"},
        "sutunlar": [
            {"alan": "ad", "ad": "Ürün", "tip": "ana", "alt": "sku"},
            {"alan": "miktar_m", "ad": "Miktar", "sag": True, "gen": "110px", "dar": "sag"},
            {"alan": "olusturma", "ad": "Oluşturma", "gen": "140px", "dar": "alt"},
            {"alan": "sonuc", "ad": "Sonuç", "gen": "140px", "genis": True},
            {"alan": "durum", "ad": "Durum", "tip": "durum", "gen": "120px"},
        ],
        "satirlar": satirlar,
        "islemler": [
            {"k": "onayla", "ad": "Onayla", "f": bekl, "birincil": True,
             "toplu": {"ad": "Seçilenleri onayla", "alanlar": []}},
            {"k": "reddet", "ad": "Reddet", "f": bekl, "toplu": {"ad": "Seçilenleri reddet", "alanlar": []}},
        ],
        "bos": {"liste": "Henüz öneri kaydı yok.",
                "suzgec": "Bu görünümde öneri yok. Sonuçlananları görmek için 'Sonuçlanan' ya da 'Tümü'."},
        "baslik_ipucu": "Sipariş önerisi kayıtları",
    }


def oneri_yurutucu():
    """Siparişe ekle → database.ekle_siparis_onerisi("G5F", sku, ürün adı, miktar) — eski düğmeyle aynı."""
    def yurut(temiz):
        if temiz["islem"] != "ekle":
            return {"ok": False, "mesaj": "Bilinmeyen işlem."}
        s = temiz["satirlar"][0]
        m = temiz["degerler"].get("miktar")
        if m is None or m != int(m) or m < 1:
            return {"ok": False, "mesaj": "Miktar 1 ya da daha büyük bir tam sayı olmalı."}
        from .database import ekle_siparis_onerisi
        ekle_siparis_onerisi("G5F", s["sku"], s["ad"], int(m))
        return {"ok": True, "mesaj": f"{s['ad']} için {tr_sayi(int(m))} adet sipariş önerisi oluşturuldu"}
    return yurut


def kayit_yurutucu():
    """Onayla / Reddet → database.onayla_siparis / reddet_siparis (her kayıt için, eski düğmeyle aynı)."""
    def yurut(temiz):
        from . import database as D
        ids, islem = temiz["ids"], temiz["islem"]
        if islem not in ("onayla", "reddet"):
            return {"ok": False, "mesaj": "Bilinmeyen işlem."}
        fn = D.onayla_siparis if islem == "onayla" else D.reddet_siparis
        for i in ids:
            fn(int(i))
        ad = temiz["satirlar"][0]["ad"] if len(ids) == 1 else f"{len(ids)} öneri"
        return {"ok": True, "mesaj": f"{ad} {'onaylandı' if islem == 'onayla' else 'reddedildi'}"}
    return yurut
