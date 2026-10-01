# -*- coding: utf-8 -*-
"""Muhasebe › Banka Bakiyeleri — kartlar, toplam ve hesap pencereleri (Ekim 2026).

  banka_toplam()        Toplam TL · Toplam USD · (EUR) · USD karşılığı
  banka_kartlari()      Her hesap tıklanır kart: bakiye KESİLMEDEN (eskiden
                        "₺1.845.230…"), para birimi, hafta sonu tahmini
  banka_yeni_dialog()   Yeni hesap (eskiden sayfada sürekli açık form)
  banka_detay_kontrol() Karta tıklanınca: düzenle · son tahsilatlar · ONAYLI sil
                        (eskiden "Sil" düğmesi hesabı onaysız siliyordu)

Hafta sonu tahmini TOPLAM üzerinden gösterilir (Genel Bakış / Bu Hafta ile aynı):
  TL bankalar toplamı − bekleyen TL − bekleyen USD × kur
Eskiden her TL hesabın kartında "bakiye − haftanın TÜM bekleyenleri" yazıyordu:
ödemeler tek hesaptan çıkacakmış gibi; küçük hesaplar (Kasa TL) sahte açık
gösteriyordu. Hesap kartı artık yalnız gerçek bakiyeyi gösterir.
"""
import html as _h

import streamlit as st

from shared import bilesen as B
from shared.tasarim import kpi_serit, tr_sayi, mesaj
from .database import banka_ekle, banka_guncelle, banka_sil, get_bankalar, get_tahsilatlar

SEMBOL = {"TL": "₺", "TRY": "₺", "USD": "$", "EUR": "€"}
EUR_USD = 1.08     # eski ekranla aynı sabit (toplam USD değerinde)


def _para(v, pb):
    return f"{'-' if float(v or 0) < 0 else ''}{SEMBOL.get(pb, '')}{tr_sayi(abs(float(v or 0)), 2)}"


def banka_toplam(bankalar, kur, bekleyen_tl=0.0, bekleyen_usd=0.0):
    t = {pb: sum(float(b.get("bakiye") or 0) for b in bankalar if b.get("para_birimi") == pb)
         for pb in ("TL", "USD", "EUR")}
    usd_deger = t["USD"] + (t["TL"] / kur if kur else 0) + t["EUR"] * EUR_USD
    kal = [{"etiket": "Toplam TL", "deger": _para(t["TL"], "TL"), "renk": "mor",
            "alt": f"{sum(1 for b in bankalar if b.get('para_birimi') == 'TL')} hesap"},
           {"etiket": "Toplam USD", "deger": _para(t["USD"], "USD"), "renk": "cyan",
            "alt": f"{sum(1 for b in bankalar if b.get('para_birimi') == 'USD')} hesap"}]
    if t["EUR"]:
        kal.append({"etiket": "Toplam EUR", "deger": _para(t["EUR"], "EUR"), "renk": "mavi"})
    kal.append({"etiket": "Hepsi (USD karşılığı)", "deger": _para(usd_deger, "USD"), "renk": "mavi",
                "alt": f"kur ₺{tr_sayi(kur, 4)}" if kur else ""})
    hs = t["TL"] - bekleyen_tl - bekleyen_usd * float(kur or 0)
    kal.append({"etiket": "Hafta sonu tahmini", "deger": _para(hs, "TL"), "renk": "yesil" if hs >= 0 else "kirmizi",
                "alt": "TL bankalar − bu haftanın bekleyenleri"})
    st.markdown(kpi_serit(kal), unsafe_allow_html=True)


def _kart_html(b, hs):
    pb = b.get("para_birimi") or ""
    alt = ""
    if hs is not None:
        renk = "var(--k-yesil)" if hs >= 0 else "var(--k-kirmizi)"
        alt = (f'<div style="font-size:12px;color:var(--k-silik);margin-top:4px">Hafta sonu '
               f'<b style="color:{renk};font-family:var(--k-mono);font-weight:600">{_para(hs, pb)}</b></div>')
    return (f'<div style="display:flex;align-items:center;gap:8px;min-width:0">'
            f'<span style="flex:1;min-width:0;font-size:13.5px;font-weight:650;color:var(--k-metin);'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{_h.escape(str(b.get("hesap_adi") or ""))}</span>'
            f'{B.cip(pb, "cyan" if pb == "USD" else ("mavi" if pb == "EUR" else "mor"))}</div>'
            f'<div style="font-family:var(--k-mono);font-variant-numeric:tabular-nums;font-size:20px;font-weight:600;'
            f'color:var(--k-metin);margin-top:8px;white-space:nowrap">{_para(b.get("bakiye"), pb)}</div>{alt}')


def _ac(bid):
    B.detay_ac("bnk", bid)


def banka_kartlari(bankalar, kur, bekleyen_tl, bekleyen_usd):
    st.markdown(B.grup_basligi("Hesaplar", "karta tıkla: düzenle, son girişler, sil"), unsafe_allow_html=True)
    sirali = sorted(bankalar, key=lambda b: ({"TL": 0, "USD": 1, "EUR": 2}.get(b.get("para_birimi"), 3),
                                             -float(b.get("bakiye") or 0)))
    for i in range(0, len(sirali), 3):
        for col, b in zip(st.columns(3, gap="small"), sirali[i:i + 3]):
            with col:
                renk = "cyan" if b.get("para_birimi") == "USD" else ("mavi" if b.get("para_birimi") == "EUR" else "mor")
                B.tiklanir(f"bnk{b['id']}", _kart_html(b, None), _ac, (b["id"],), tur="kart", renk=renk,
                           etiket=f"{b.get('hesap_adi')} hesabını aç")


@st.dialog("Yeni banka hesabı", width="medium")
def banka_yeni_dialog():
    with st.form("bnk_yeni_form", border=False):
        ad = st.text_input("Hesap adı", placeholder="örn. YAPI KREDİ - TL")
        c1, c2 = st.columns([1.6, 1])
        bak = c1.number_input("Açılış bakiyesi", min_value=0.0, step=1000.0, format="%.2f")
        pb = c2.selectbox("Para birimi", ["TL", "USD", "EUR"])
        st.caption("Aynı bankanın hesaplarını 'BANKA ADI - TL', 'BANKA ADI - USD' diye adlandırırsan "
                   "Arbitraj penceresi onları otomatik eşleştirir.")
        if st.form_submit_button("Hesabı ekle", type="primary", icon=":material/add:"):
            if not ad.strip():
                st.error("Hesap adı gerekli.")
            else:
                banka_ekle(ad.strip(), bak, pb)
                B.yenile(f"{ad.strip()} eklendi")


def banka_detay_kontrol(kur):
    bid = B.detay_istendi("bnk")
    if bid:
        b = next((x for x in (get_bankalar() or []) if x.get("id") == bid), None)
        if b:
            _banka_dialog(b, kur)


@st.dialog("Banka hesabı", width="large")
def _banka_dialog(b, kur):
    pb = b.get("para_birimi") or "TL"
    st.markdown(f'<div style="font-size:19px;font-weight:650">{_h.escape(str(b.get("hesap_adi") or ""))}</div>'
                f'<div style="font-family:var(--k-mono);font-size:24px;font-weight:600;margin:4px 0 14px">'
                f'{_para(b.get("bakiye"), pb)}</div>', unsafe_allow_html=True)
    t1, t2, t3 = st.tabs(["Son girişler", "Düzenle", "Sil"])
    with t1:
        son = [t for t in (get_tahsilatlar(limit=200) or []) if t.get("banka_id") == b["id"]][:12]
        if not son:
            st.caption("Bu hesaba kayıtlı tahsilat yok.")
        for t in son:
            st.markdown(f'<div style="display:flex;gap:12px;padding:6px 0;border-bottom:1px solid var(--k-kenar);font-size:13px">'
                        f'<span style="width:90px;color:var(--k-silik)">{str(t.get("tarih") or "")[:10]}</span>'
                        f'<span style="flex:1;min-width:0">{_h.escape(str(t.get("kaynak") or "—"))}'
                        f'<span style="color:var(--k-silik)"> · {_h.escape(str(t.get("aciklama") or ""))}</span></span>'
                        f'<b style="font-family:var(--k-mono)">{_para(t.get("tutar"), t.get("para_birimi") or pb)}</b></div>',
                        unsafe_allow_html=True)
    with t2:
        with st.form(f"bnk_duz_{b['id']}", border=False):
            ad = st.text_input("Hesap adı", value=b.get("hesap_adi") or "")
            c1, c2 = st.columns([1.6, 1])
            bak = c1.number_input("Bakiye", value=float(b.get("bakiye") or 0), step=100.0, format="%.2f",
                                  help="Bankadaki gerçek bakiyeyle eşitlemek için. Normal akışta ödeme, "
                                       "tahsilat ve virman bakiyeyi kendisi günceller.")
            pbs = ["TL", "USD", "EUR"]
            ypb = c2.selectbox("Para birimi", pbs, index=pbs.index(pb) if pb in pbs else 0)
            if st.form_submit_button("Kaydet", type="primary", icon=":material/save:"):
                banka_guncelle(b["id"], ad.strip() or b.get("hesap_adi"), bak, ypb)
                B.yenile("Hesap güncellendi", ac=("bnk", b["id"]))
    with t3:
        st.markdown(mesaj("uyari", "Hesap silinir. Bu hesaptan yapılmış ödeme, tahsilat ve virman kayıtları "
                                   "durur ama artık bu hesaba bağlanamaz."), unsafe_allow_html=True)
        if B.onayli_sil(f"Evet, {b.get('hesap_adi')} hesabını sil", key=f"bnk_{b['id']}", dugme="Hesabı sil"):
            banka_sil(b["id"])
            B.yenile(f"{b.get('hesap_adi')} silindi")
