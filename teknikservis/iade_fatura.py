# -*- coding: utf-8 -*-
"""Fatura ile iade (Ekim 2026, kullanıcı kararı): Yeni Mal Kabül penceresinde iade faturası satış
girişi gibi kalem kalem girilir. Bir faturada 10 farklı model olabilir, her birinin birim fiyatı
ayrıdır; tek ürünlük mal kabuldeki tek fiyat alanı bu yüzden kalktı.

Her ADET için bir servis kaydı açılır (seri "NO SERIAL NUMBER"), stok seçilen depoya +1 girer ve
Satış › İade'ye manuel iade satırı (birim fiyat USD) yazılır. Bu modül yalnız saf hesapları taşır;
ekran teknikservis/main.py, yazma teknikservis.stok ve teknikservis.database'tedir.
"""

SERISIZ = "NO SERIAL NUMBER"
VARSAYILAN_ACIKLAMA = "Fatura ile iade"
SON_GUN = 365          # fiyat önerisi için geriye bakılan satış günü


def firma_koku(ad):
    """Firma karşılaştırma kökü: Türkçe harfler indirilmiş, büyük harf, ilk kelime.
    'VATAN BİLGİSAYAR SAN. A.Ş.' ve 'Vatan' aynı köke iner."""
    from shared.utils import normalize_tr
    p = normalize_tr(ad).replace(".", " ").replace(",", " ").split()
    return p[0] if p else ""


def _tr_tarih(t):
    """'2026-03-12' → '12.03.2026'; tanınmazsa olduğu gibi."""
    p = str(t or "")[:10].split("-")
    return ".".join(reversed(p)) if len(p) == 3 else str(t or "")


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def son_fiyat_haritasi(satislar, firma):
    """{sku_anahtar: {"fiyat", "tarih", "firma_mi"}} — her SKU'nun son satış birim fiyatı (USD).
    Bu firmaya yapılmış satış varsa o kazanır (firma_mi=True); yoksa herhangi bir firmaya son satış.
    Fiyatı 0 olan satırlar (bedelsiz) sayılmaz."""
    from shared.utils import sku_anahtar
    kok = firma_koku(firma)
    firma_son, genel_son = {}, {}
    for s in satislar or []:
        fiyat = _f(s.get("birim_satis"))
        k = sku_anahtar(s.get("sku"))
        if fiyat <= 0 or not k:
            continue
        sira = (str(s.get("tarih") or "")[:10], _f(s.get("id")))
        aday = {"fiyat": round(fiyat, 4), "tarih": sira[0], "_sira": sira}
        if sira > genel_son.get(k, {}).get("_sira", ("", -1.0)):
            genel_son[k] = aday
        if kok and firma_koku(s.get("kanal")) == kok and sira > firma_son.get(k, {}).get("_sira", ("", -1.0)):
            firma_son[k] = aday
    out = {}
    for k, v in genel_son.items():
        secilen, firma_mi = (firma_son[k], True) if k in firma_son else (v, False)
        out[k] = {"fiyat": secilen["fiyat"], "tarih": secilen["tarih"], "firma_mi": firma_mi}
    return out


def fiyat_onerisi(sku, firma, harita, urun=None):
    """Kalem için önerilen birim fiyat (USD) ve kaynağı: (fiyat, açıklama).
    Sıra: bu firmaya son satış > başka firmaya son satış > ürün kartında firmanın fiyatı > kartın
    satış fiyatı. Hiçbiri yoksa (0.0, 'fiyat önerisi yok')."""
    from shared.utils import sku_anahtar
    h = (harita or {}).get(sku_anahtar(sku))
    if h and h.get("fiyat"):
        ne = "bu firmaya son satış" if h.get("firma_mi") else "son satış (başka firma)"
        return float(h["fiyat"]), f"{ne} {_tr_tarih(h.get('tarih'))}".strip()
    u = urun or {}
    liste = u.get("satis_fiyat_listesi") or {}
    if isinstance(liste, dict) and firma:
        kok = firma_koku(firma)
        for ad, fiyat in liste.items():
            if _f(fiyat) > 0 and firma_koku(ad) == kok:
                return round(_f(fiyat), 4), "ürün kartında bu firmanın fiyatı"
    if _f(u.get("satis_fiyati")) > 0:
        return round(_f(u.get("satis_fiyati")), 4), "ürün kartı satış fiyatı"
    return 0.0, "fiyat önerisi yok"


def para_cevir(usd, para_birimi, kur):
    """USD öneriyi seçili para birimine çevirir: TL ise × kur (kur yoksa 0), USD ise aynen."""
    if str(para_birimi or "USD").upper() in ("TL", "TRY", "₺"):
        k = _f(kur)
        return round(_f(usd) * k, 2) if k > 1 else 0.0
    return round(_f(usd), 4)


def kalem_ekle(kalemler, sku, ad, adet, fiyat):
    """Sepete kalem ekler; aynı SKU ve aynı fiyat varsa adedini artırır. Yeni liste döner."""
    from shared.utils import sku_anahtar
    adet, fiyat = int(adet or 0), round(_f(fiyat), 4)
    out = [dict(k) for k in (kalemler or [])]
    if adet <= 0 or not str(sku or "").strip():
        return out
    for k in out:
        if sku_anahtar(k["sku"]) == sku_anahtar(sku) and abs(_f(k["fiyat"]) - fiyat) < 0.00005:
            k["adet"] = int(k["adet"]) + adet
            return out
    out.append({"sku": str(sku).strip(), "ad": str(ad or "").strip(), "adet": adet, "fiyat": fiyat})
    return out


def sepet_toplam(kalemler, para_birimi="USD", kur=None):
    """Sepetin özeti: {"adet", "toplam" (seçili para birimi), "usd" (USD karşılığı; TL'de kur yoksa None)}."""
    from teknikservis.stok import iade_usd
    adet = sum(int(k.get("adet") or 0) for k in kalemler or [])
    toplam = round(sum(int(k.get("adet") or 0) * _f(k.get("fiyat")) for k in kalemler or []), 2)
    return {"adet": adet, "toplam": toplam, "usd": iade_usd(toplam, para_birimi, kur)}


def fatura_daha_once(kayitlar, fatura_no, firma):
    """Aynı firma ve fatura numarasıyla açılmış servis kaydı sayısı (aynı fatura iki kez girilmesin)."""
    no = str(fatura_no or "").strip().upper()
    if not no:
        return 0
    kok = firma_koku(firma)
    return sum(1 for k in kayitlar or []
               if str(k.get("fatura_no") or "").strip().upper() == no
               and firma_koku(k.get("firma_bilgisi")) == kok)


def birim_kayitlari(kalemler, baslik, kur=None, gruplar=None):
    """Sepet → her ADET için bir servis kaydı verisi (ekle_kayit'e gider).

    baslik: {"firma", "fatura_no", "irsaliye_no", "giris_depo", "para_birimi", "aciklama"}.
    gruplar: {sku: ürün grubu} (ürün kartından). TL'de kur yoksa ValueError — yanlış (0) tutarla iade
    yazılmasın."""
    from teknikservis.stok import iade_usd
    pb = str(baslik.get("para_birimi") or "USD").upper()
    out = []
    for k in kalemler or []:
        fiyat = round(_f(k.get("fiyat")), 4)
        usd = iade_usd(fiyat, pb, kur)
        if usd is None:
            raise ValueError("TL fiyat için USD kuru bulunamadı")
        fno = str(baslik.get("fatura_no") or "").strip()
        tek = {
            "arayuz": "iade", "stok_kodu": str(k["sku"]).strip(), "stok_adi": str(k.get("ad") or "").strip(),
            "urun_grubu": str((gruplar or {}).get(k["sku"]) or "").strip(),
            "seri_no": SERISIZ, "ariza": str(baslik.get("aciklama") or "").strip() or VARSAYILAN_ACIKLAMA,
            "firma_bilgisi": str(baslik.get("firma") or "").strip(),
            "musteri_adi": str(baslik.get("firma") or "").strip(),
            "sevk_kargo_bilgisi": "", "fatura_no": fno, "fatura_mevcut": bool(fno),
            "irsaliye_no": str(baslik.get("irsaliye_no") or "").strip(),
            "giris_depo": baslik.get("giris_depo"),
            "iade_fiyat": fiyat, "iade_pb": pb, "iade_kur": (kur if pb == "TL" else None), "iade_net": usd,
        }
        for _ in range(int(k.get("adet") or 0)):
            out.append(dict(tek))
    return out
