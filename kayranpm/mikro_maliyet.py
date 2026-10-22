# -*- coding: utf-8 -*-
"""Paçal maliyet Mikro'dan (Ekim 2026). Kullanılan yer: satis.database.get_pacal_map (bütün maliyetlerin tek kapısı).

Kullanıcı (22.10.2026): "Mikro'da ürünlerin maliyeti paçalı vs neyse ona göre programda da revize olsun; Mikro'daki
veriler baz alınsın." Karar (aynı gün, iki rakam yan yana gösterildikten sonra): "A ile yap" — GİRİŞ PAÇALI.

Kaynak: aktarıcının mikro_stok_maliyet tablosu (STOK_HAREKETLERI_OZET; stok × mali yıl × hareket cinsi; veritabani/54).
Birim maliyet (USD) = Σ alternatif döviz giriş maliyeti ÷ Σ giren adet, bütün yıllar ve hareket cinsleri:
ithalat girişi, yurt içi alış, sonradan işlenen ithalat masrafı (adetsiz tutar) ve değer farkı faturaları dahil.
Depolar arası transfer (hareket cinsi 6) sayılmaz: aynı ürün bir depodan çıkıp ötekine girer, paçalı değiştirmez.
Müşteri iadeleri (giris_iade) sayılmaz. Mikro'nun satışa yazdığı maliyet (B) kullanılmaz: sonradan gelen masraflar
ona yansımadığı için düşük kalıyordu (ör. F1M650BBM giriş paçalı 39,53 $, satış maliyeti 28,37 $).

Mikro'da maliyeti olmayan SKU'da eski hesap (İthalat paçalı, sonra kart alış fiyatı) yedek olarak kalır.
Kapatmak için sistem_ayarlari 'mikro_maliyet_durum' = {"acik": false}.
"""
from __future__ import annotations

TABLO = "mikro_stok_maliyet"
DURUM_ANAHTAR = "mikro_maliyet_durum"
TRANSFER = 6                    # depolar arası sevk: paçala girmez


def _f(v):
    try:
        x = float(v)
        return x if x == x else 0.0
    except (TypeError, ValueError):
        return 0.0


def pacal_hesapla(satirlar):
    """mikro_stok_maliyet satırları → {sku_anahtar: birim USD}. Adedi ya da tutarı olmayan SKU yer almaz."""
    from shared.utils import sku_anahtar
    adet, usd = {}, {}
    for r in satirlar or []:
        try:
            if int(r.get("hareket_cins")) == TRANSFER:
                continue
        except (TypeError, ValueError):
            continue
        k = sku_anahtar(r.get("stok_kod"))
        if not k:
            continue
        adet[k] = adet.get(k, 0.0) + _f(r.get("giris"))
        usd[k] = usd.get(k, 0.0) + _f(r.get("alt_giris"))
    return {k: round(usd[k] / a, 4) for k, a in adet.items() if a > 0 and usd.get(k, 0) > 0}


def durum():
    try:
        from kayranacc.database import get_ayar
        return get_ayar(DURUM_ANAHTAR, {}) or {}
    except Exception:  # noqa: BLE001
        return {}


def acik_mi():
    """Varsayılan AÇIK (kullanıcı kararı); {"acik": false} kapatır."""
    return durum().get("acik", True) is not False


def _oku():
    from satis.database import _get_client
    cli = _get_client()
    out, bas = [], 0
    while True:
        parca = (cli.table(TABLO).select("stok_kod,yil,hareket_cins,giris,alt_giris")
                 .order("stok_kod").order("yil").order("hareket_cins").range(bas, bas + 999).execute().data or [])
        out += parca
        if len(parca) < 1000:
            return out
        bas += 1000


def pacal_haritasi():
    """{sku_anahtar: birim USD} — kapalıysa, tablo yoksa ya da okunamazsa boş (eski hesap kullanılır)."""
    try:
        if not acik_mi():
            return {}
        return pacal_hesapla(_oku())
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("kayranpm.mikro_maliyet.pacal_haritasi", e)
        return {}
