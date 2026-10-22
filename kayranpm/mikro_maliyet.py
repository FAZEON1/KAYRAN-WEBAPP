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

SEVKİYAT PAÇALI (aynı gün, kullanıcı: "Ürünleri 20 konteyner ithal edip antrepoya çektik, parça parça çekerken her
çekimden sonra masrafları Mikro'ya işledik; son ithalatlarda masrafların tamamı işlenmemiş olabilir"). Bulgu: her
çekimin masrafı o çekimdeki konteynerlere bölünmüş; geç çekilen konteyner o güne kadar biriken bekleme masrafını
(demuraj, liman / antrepo ardiyesi) tek başına taşıyor (P251031 ve P251126'da FOB'un %62,8'i), antrepodaki
konteynerler hiç taşımıyor. Karar: antrepoda konteyneri kalan (açık) sevkiyatta çekilen kalemin masrafı yeniden
dağıtılır:
    normal masraf  = FOB × (çekilenlerin normal masrafı ÷ çekilenlerin FOB'u)      (navlun, gümrük … — her konteynerde olur)
    bekleme        = FOB × (çekilenlerin bekleme masrafı ÷ sevkiyatın TÜM FOB'u)    (antrepodakiler de payını alır)
SKU paçalı = (Mikro toplam USD + Σ (yeni − işlenmiş masraf)) ÷ Mikro adet. Sevkiyat tamamen çekilince düzeltme biter,
Mikro paçalı aynen kullanılır. Sevkiyat: PI no'nun ilk '-' öncesi (P251017-22-ST → P251017, 2511S07-4 → 2511S07).
Kâr ekranı bekleme payını ayrı satırda gösterir (bekleme_payi).
"""
from __future__ import annotations

import json

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


BEKLEME_KALEMLERI = ("demuraj", "liman_ardiye", "antrepo_ardiye")
ANTREPODA = "Antrepoda"


def sevkiyat_anahtari(d):
    return str((d.get("pi_no") or d.get("dosya_no") or "")).strip().split("-")[0].upper()


def _masraflar(d):
    m = d.get("masraflar")
    if isinstance(m, str):
        try:
            m = json.loads(m or "{}")
        except ValueError:
            m = {}
    m = m if isinstance(m, dict) else {}
    toplam = sum(_f(v) for v in m.values())
    bekleme = sum(_f(m.get(k)) for k in BEKLEME_KALEMLERI)
    return toplam, bekleme


def sevkiyat_duzeltmesi(dosyalar, kalemler):
    """İthalat dosyaları + kalemleri → {sku_anahtar: {"fark": Σ (yeni − işlenmiş masraf) USD,
    "bekleme": Σ yeni bekleme masrafı USD}}. Yalnız USD dosyalar; yurt içi / yerli alım sayılmaz.
    fark yalnız açık sevkiyatta sıfırdan farklıdır; bekleme bütün çekilmiş ithalatlar için hesaplanır."""
    from shared.utils import sku_anahtar
    kal = {}
    for k in kalemler or []:
        kal.setdefault(k.get("dosya_id"), []).append(k)
    gruplar = {}
    for d in dosyalar or []:
        if str(d.get("alim_turu") or "ithalat").strip().lower() in ("yurtici", "yerli"):
            continue
        if str(d.get("doviz") or "USD").strip().upper() not in ("USD", ""):
            continue
        gruplar.setdefault(sevkiyat_anahtari(d), []).append(d)
    out = {}
    for _, ds in gruplar.items():
        bilgi = []
        for d in ds:
            ks = kal.get(d.get("id")) or []
            fob = sum(_f(k.get("adet")) * _f(k.get("birim_fob")) for k in ks)
            toplam, bekleme = _masraflar(d)
            bilgi.append((d, ks, fob, toplam, bekleme, str(d.get("durum") or "").strip() == ANTREPODA))
        cek = [b for b in bilgi if not b[5]]
        acik = len(cek) < len(bilgi) and bool(cek)
        fob_cek = sum(b[2] for b in cek)
        fob_tum = sum(b[2] for b in bilgi)
        normal_oran = (sum(b[3] - b[4] for b in cek) / fob_cek) if fob_cek > 0 else 0.0
        bekleme_oran = (sum(b[4] for b in cek) / fob_tum) if fob_tum > 0 else 0.0
        for d, ks, fob, toplam, bekleme, antrepoda in cek:
            if fob <= 0:
                continue
            for k in ks:
                kfob = _f(k.get("adet")) * _f(k.get("birim_fob"))
                sku = sku_anahtar(k.get("sku"))
                if not sku or kfob <= 0:
                    continue
                pay = kfob / fob
                e = out.setdefault(sku, {"fark": 0.0, "bekleme": 0.0})
                if acik:
                    e["fark"] += kfob * (normal_oran + bekleme_oran) - toplam * pay
                    e["bekleme"] += kfob * bekleme_oran
                else:
                    e["bekleme"] += bekleme * pay
    return out


def pacal_hesapla_sevkiyatli(satirlar, duzeltme):
    """Mikro giriş paçalı, açık sevkiyatların masrafı yeniden dağıtılmış. Döner: ({sku: birim USD}, {sku: bekleme
    payı USD/adet})."""
    from shared.utils import sku_anahtar
    adet, usd = {}, {}
    for r in satirlar or []:
        try:
            if int(r.get("hareket_cins")) == TRANSFER:
                continue
        except (TypeError, ValueError):
            continue
        k = sku_anahtar(r.get("stok_kod"))
        if k:
            adet[k] = adet.get(k, 0.0) + _f(r.get("giris"))
            usd[k] = usd.get(k, 0.0) + _f(r.get("alt_giris"))
    pacal, bekleme = {}, {}
    for k, a in adet.items():
        if a <= 0:
            continue
        dz = (duzeltme or {}).get(k) or {}
        toplam = usd.get(k, 0.0) + _f(dz.get("fark"))
        if toplam > 0:
            pacal[k] = round(toplam / a, 4)
        if _f(dz.get("bekleme")) > 0:
            bekleme[k] = round(_f(dz.get("bekleme")) / a, 4)
    return pacal, bekleme


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


def _ithalat():
    from ithalat.database import get_dosyalar, get_tum_kalemler
    return get_dosyalar() or [], get_tum_kalemler() or []


def haritalar():
    """({sku: paçal USD}, {sku: bekleme payı USD/adet}) — sevkiyat paçalı. Kapalı / okunamazsa ({}, {})."""
    try:
        if not acik_mi():
            return {}, {}
        satir = _oku()
        try:
            dz = sevkiyat_duzeltmesi(*_ithalat())
        except Exception as e:  # noqa: BLE001 — ithalat okunamazsa düz Mikro paçalı
            from shared.kayit import sessiz
            sessiz("kayranpm.mikro_maliyet.sevkiyat", e)
            dz = {}
        return pacal_hesapla_sevkiyatli(satir, dz)
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("kayranpm.mikro_maliyet.haritalar", e)
        return {}, {}


def pacal_haritasi():
    """{sku_anahtar: birim USD} — sevkiyat paçalı; kapalıysa, tablo yoksa ya da okunamazsa boş (eski hesap)."""
    try:
        if not acik_mi():
            return {}
        return haritalar()[0]
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("kayranpm.mikro_maliyet.pacal_haritasi", e)
        return {}
