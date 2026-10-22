# -*- coding: utf-8 -*-
"""Muhasebe › Tahsilat (Ekim 2026). Hesap: kayranacc/mikro_tahsilat.py — Mikro'daki müşteri alacakları, canlı.

Üstte döviz bazında özet (açık alacak, vadesi geçen, bu hafta, satışa bağlı), altında müşteri × döviz satırları
(en büyük üstte) ve son 7 günde Mikro'ya düşen tahsilatlar. Yalnız okur; veritabanına hiçbir şey yazmaz.
"""
from datetime import timedelta

import streamlit as st

from shared import bilesen as B
from shared.tasarim import tr_sayi
from shared.utils import tr_today

from . import mikro_tahsilat as T
from .mikro_odeme import hafta_araligi

PB = {0: "TL", 1: "USD", 2: "EUR"}
SEMBOL = {0: "₺", 1: "$", 2: "€"}


def _para(v, dc):
    return f"{SEMBOL.get(dc, '')}{tr_sayi(float(v or 0), 0)}"


@st.cache_data(ttl=300, show_spinner=False)
def _hesap(bugun_iso):
    from datetime import date
    return T.hesapla(T.veri_oku(), date.fromisoformat(bugun_iso))


def render():
    from shared.masa_liste import ciz, kolon
    from shared.utils import metrik_satiri
    bugun = tr_today()
    ey = B.baslik_eylem(":material/call_received: Muhasebe", "Tahsilat",
                        aciklama="Mikro'daki müşteri alacakları · vadesine göre · 15 dakikada bir güncellenir",
                        eylemler=[{"etiket": "Yenile", "key": "th_yenile", "icon": ":material/refresh:"}])
    if ey.get("th_yenile"):
        _hesap.clear()
    try:
        with st.spinner("Mikro cari hareketleri okunuyor…"):
            r = _hesap(bugun.isoformat())
    except Exception as e:  # noqa: BLE001
        st.error(f"Mikro verisi okunamadı: {type(e).__name__}: {str(e)[:160]}")
        return
    if not r["satirlar"]:
        st.info("Mikro'da açık müşteri alacağı yok.")
    for dc in sorted(r["toplam"]):
        t = r["toplam"][dc]
        metrik_satiri([
            {"label": f"Açık alacak ({PB.get(dc, dc)})", "value": _para(t["toplam"], dc)},
            {"label": "Vadesi geçen", "value": _para(t["gecikmis"], dc)},
            {"label": "Bu hafta", "value": _para(t["bu_hafta"], dc)},
            {"label": f"Sonraki {T.UFUK_HAFTA} hafta", "value": _para(t["sonraki_toplam"], dc)},
            {"label": "Satışa bağlı", "value": _para(t["satisa_bagli"], dc)},
        ])
    if r["satirlar"]:
        st.caption("Vade Mikro'daki ödeme planından (gün planın adında: '30 GÜN VADE'), taksitten ya da vade "
                   "tarihinden; yoksa fatura günü. 'Satış şartlı' plandaki faturaların sabit vadesi yok: ödeme "
                   "satışa bağlı olduğu için vadesi geçmiş sayılmaz, ayrı sütunda durur. Tahsilat en eski vadeli "
                   "faturadan başlayarak düşülür.")
        bas, _son = hafta_araligi(bugun)
        sutun = [f"{(bas + timedelta(days=7 * (i + 1))):%d.%m} haftası" for i in range(T.UFUK_HAFTA)]
        satir = []
        for x in r["satirlar"]:
            d = {"Müşteri": x["unvan"], "Hesap": x["cari_kod"], "Döviz": PB.get(x["doviz"], x["doviz"]),
                 "Açık": x["toplam"], "Vadesi geçen": x["gecikmis"],
                 "Gecikme (gün)": x["gecikme_gun"] or None, "Bu hafta": x["bu_hafta"]}
            for ad, v in zip(sutun, x["sonraki"]):
                d[ad] = v
            d.update({"Daha ileri": x["ileri"], "Satışa bağlı": x["satisa_bagli"]})
            satir.append(d)
        ciz(satir, [kolon("Müşteri", ana=True, alt="Hesap"), kolon("Hesap", gizli=True),
                    kolon("Döviz", secim=True, gen="70px"), kolon("Açık", "sayi", gen="110px", basamak=0),
                    kolon("Vadesi geçen", "sayi", gen="110px", basamak=0),
                    kolon("Gecikme (gün)", "adet", gen="90px", genis=True),
                    kolon("Bu hafta", "sayi", gen="100px", basamak=0)]
            + [kolon(a, "sayi", gen="100px", basamak=0, genis=True) for a in sutun]
            + [kolon("Daha ileri", "sayi", gen="100px", basamak=0, genis=True),
               kolon("Satışa bağlı", "sayi", gen="110px", basamak=0)],
            "tahsilat_masa", excel="tahsilat_listesi")
    st.markdown(f"**Son {T.SON_GUN} günde tahsil edilen** · Mikro'daki banka havalesi ve POS tahsilatları")
    if not r["son"]:
        st.caption("Son 7 günde Mikro'ya düşen tahsilat yok.")
        return
    ciz([{"Tarih": x["tarih"], "Müşteri": x["unvan"], "Döviz": PB.get(x["doviz"], x["doviz"]), "Tutar": x["tutar"],
          "Açıklama": x["aciklama"]} for x in r["son"]],
        [kolon("Tarih", "tarih", gen="100px"), kolon("Müşteri", ana=True), kolon("Döviz", secim=True, gen="70px"),
         kolon("Tutar", "sayi", gen="110px", basamak=0), kolon("Açıklama", genis=True)],
        "tahsilat_son", excel="son_tahsilatlar")
