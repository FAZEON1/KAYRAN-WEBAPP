# -*- coding: utf-8 -*-
"""İthalat › Tedarikçi siparişleri — Mikro'dan (Ekim 2026).

Kullanıcı: "Tüm siparişler Mikro'dan çekilsin; Mikro'ya sipariş girildiğinde programa da yansısın."
Tedarikçiye verilen siparişler (Mikro SIPARISLER, sip_tip 1) aktarıcıyla 15 dakikada bir mikro_siparis
tablosuna gelir; bu sayfa onları salt okunur gösterir: ne, kimden, kaç adet sipariş edildi, kaçı geldi,
kaçı bekliyor. Rakam yazmaz, paçala dokunmaz. Müşteri siparişleri satışa bekleyen satış olarak girer
(satis/mikro_esitle.siparis_kayitlari).
"""
from collections import defaultdict

import pandas as pd
import streamlit as st

from shared.tasarim import kpi_serit, para, tr_sayi

DOVIZ = {0: "TL", 1: "USD", 2: "EUR"}


def _f(v):
    try:
        x = float(v)
        return x if x == x else 0.0
    except (TypeError, ValueError):
        return 0.0


def tedarikci_siparisleri(satirlar, unvanlar=None, ad_harita=None):
    """mikro_siparis satırları → tedarikçi sipariş listesi (sip_tip 1). Açık olanlar önce, sonra yeniden eskiye.
    Döner: [{tarih, siparis_no, tedarikci, sku, urun, siparis, gelen, kalan, birim, doviz, kalan_tutar, acik}]."""
    from satis.mikro_esitle import fatura_no
    from shared.utils import sku_anahtar
    unvanlar, ad_harita = unvanlar or {}, ad_harita or {}
    out = []
    for r in satirlar or []:
        try:
            if int(r.get("sip_tip")) != 1:
                continue
        except (TypeError, ValueError):
            continue
        miktar, gelen = _f(r.get("sip_miktar")), _f(r.get("sip_teslim_miktar"))
        kalan = max(miktar - gelen, 0.0)
        kapali = r.get("sip_kapat_fl") in (True, 1, "1", "true")
        kod = str(r.get("sip_musteri_kod") or "").strip()
        sku = sku_anahtar(r.get("sip_stok_kod"))
        birim = _f(r.get("sip_b_fiyat"))
        out.append({
            "tarih": str(r.get("sip_tarih") or "")[:10],
            "siparis_no": fatura_no(r.get("sip_evrakno_seri"), r.get("sip_evrakno_sira")),
            "tedarikci": " ".join(str(unvanlar.get(kod) or kod).split()), "sku": sku,
            "urun": ad_harita.get(sku, ""), "siparis": miktar, "gelen": gelen, "kalan": 0.0 if kapali else kalan,
            "birim": birim, "doviz": DOVIZ.get(int(_f(r.get("sip_doviz_cinsi"))), "?"),
            "kalan_tutar": 0.0 if kapali else round(kalan * birim, 2), "acik": (not kapali) and kalan > 0,
        })
    acik = [x for x in out if x["acik"]]
    diger = sorted((x for x in out if not x["acik"]), key=lambda x: (x["tarih"], x["siparis_no"]), reverse=True)
    acik.sort(key=lambda x: (x["tarih"], x["siparis_no"]), reverse=True)
    return acik + diger


def ozet(liste):
    """{acik_siparis, acik_adet, acik_tutar: {döviz: tutar}, tedarikci}."""
    tutar = defaultdict(float)
    for x in liste:
        if x["acik"]:
            tutar[x["doviz"]] += x["kalan_tutar"]
    return {"acik_siparis": len({x["siparis_no"] for x in liste if x["acik"]}),
            "acik_adet": sum(x["kalan"] for x in liste if x["acik"]),
            "acik_tutar": dict(tutar), "tedarikci": len({x["tedarikci"] for x in liste})}


def _oku():
    from satis.mikro_esitle import _cli, kopyasiz
    cli = _cli()
    sat = kopyasiz(cli.table("mikro_siparis").select("*").eq("sip_tip", 1).order("sip_guid").execute().data or [],
                   "sip_guid")
    unvan = {str(c.get("cari_kod") or ""): c.get("cari_unvan1") or ""
             for c in (cli.table("mikro_cari_bakiye").select("cari_kod,cari_unvan1").execute().data or [])}
    return sat, unvan


def sayfa():
    st.caption("Tedarikçilere verilen siparişler Mikro'dan otomatik gelir (15 dakikada bir). Mikro'ya sipariş "
               "girildiğinde burada görünür; mal geldikçe kalan adet düşer.")
    try:
        sat, unvan = _oku()
    except Exception as e:  # noqa: BLE001
        st.warning(f"Mikro siparişleri okunamadı: {type(e).__name__}: {str(e)[:160]}")
        return
    try:
        from shared.ana_veri import get_urun_ad_haritasi
        ad = get_urun_ad_haritasi()
    except Exception:  # noqa: BLE001
        ad = {}
    liste = tedarikci_siparisleri(sat, unvan, ad)
    if not liste:
        st.info("Mikro'da tedarikçi siparişi yok.")
        return
    oz = ozet(liste)
    st.markdown(kpi_serit([
        {"etiket": "Açık sipariş", "deger": tr_sayi(oz["acik_siparis"]), "renk": "mavi"},
        {"etiket": "Bekleyen adet", "deger": tr_sayi(oz["acik_adet"]), "renk": "mor"},
        {"etiket": "Bekleyen tutar", "deger": " · ".join(
            para(v, {"USD": "$", "EUR": "€", "TL": "₺"}.get(k, ""), 0) for k, v in sorted(oz["acik_tutar"].items()))
            or "—", "renk": "amber"},
        {"etiket": "Tedarikçi", "deger": tr_sayi(oz["tedarikci"]), "renk": "yesil"},
    ]), unsafe_allow_html=True)
    tedarikciler = sorted({x["tedarikci"] for x in liste})
    c1, c2 = st.columns([1, 2])
    yalniz_acik = c1.toggle("Yalnız bekleyenler", value=False, key="ith_msip_acik")
    secili = c2.multiselect("Tedarikçi", tedarikciler, key="ith_msip_ted", placeholder="Hepsi")
    gor = [x for x in liste if (not yalniz_acik or x["acik"]) and (not secili or x["tedarikci"] in secili)]
    st.dataframe(pd.DataFrame([{
        "Tarih": x["tarih"], "Sipariş no": x["siparis_no"], "Tedarikçi": x["tedarikci"], "SKU": x["sku"],
        "Ürün": x["urun"], "Sipariş": tr_sayi(x["siparis"]), "Gelen": tr_sayi(x["gelen"]),
        "Bekleyen": tr_sayi(x["kalan"]), "Birim fiyat": f"{tr_sayi(x['birim'], 2)} {x['doviz']}",
        "Durum": "Bekliyor" if x["acik"] else "Tamamlandı"} for x in gor]),
        hide_index=True, use_container_width=True)
