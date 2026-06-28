# -*- coding: utf-8 -*-
"""Global arama — tek terimle tüm modüllerde arama.
SKU / ürün adı / barkod, cari, sipariş no, seri no, servis no, tedarikçi...
ara(terim) → {"urunler":[...], "cariler":[...], "satislar":[...],
              "ithalat":[...], "servis":[...]}  (yalnız dolu gruplar döner)"""


def _temiz(t):
    # or_ filtre string'ini bozabilecek karakterleri ayıkla
    return (t or "").strip().replace(",", " ").replace("*", "").replace("%", "").replace("(", " ").replace(")", " ")


def _or_filtre(terim, kolonlar):
    return ",".join(f"{k}.ilike.*{terim}*" for k in kolonlar)


def ara(terim, limit=8):
    terim = _temiz(terim)
    if len(terim) < 2:
        return {}
    try:
        from shared.audit import _raw_client
        sb = _raw_client()
    except Exception:
        return {}

    out = {}

    def _q(tablo, kolonlar, secim="*", order=None):
        try:
            q = sb.table(tablo).select(secim).or_(_or_filtre(terim, kolonlar))
            if order:
                q = q.order(order, desc=True)
            return q.limit(limit).execute().data or []
        except Exception:
            return []

    r = _q("urunler", ["sku", "urun_adi", "barkod"],
           "sku,urun_adi,marka,kategori,barkod,satis_fiyati")
    if r:
        out["urunler"] = r

    r = _q("ref_firmalar", ["firma_adi", "firma_kodu"])
    if r:
        out["cariler"] = r

    r = _q("satislar", ["siparis_no", "sku", "kanal"],
           "id,tarih,kanal,sku,siparis_no,adet,birim_satis", order="tarih")
    if r:
        out["satislar"] = r

    r = _q("ithalat_dosyalari", ["pi_no", "dosya_no", "ithalat_takip_no", "tedarikci"],
           order="tarih")
    if r:
        out["ithalat"] = r

    r = _q("ts_kayitlar",
           ["servis_form_no", "seri_no", "sku", "musteri", "irsaliye", "ean", "stok_adi"],
           order="tarih")
    if r:
        out["servis"] = r

    return out
