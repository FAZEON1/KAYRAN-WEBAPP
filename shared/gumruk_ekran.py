# -*- coding: utf-8 -*-
"""İthalat › Gümrük danışmanı (Ekim 2026).

Kullanıcı ürünü, menşei ve fiyatı yazar; claude.ai'deki gümrük görevi (otonom/gumruk_gorevi.md) GTİP
önerisini, vergi oranlarını, ek vergileri ve gereken belgeleri araştırıp yazar. Vergi tutarlarını
program hesaplar (shared.asistan_hesap.vergi_hesabi). Sonuç her zaman ÖNERİDİR: kesin GTİP gümrük
müşavirine teyit ettirilir. Hiçbir ithalat dosyasına / maliyete yazılmaz.
"""
import html as _h
from datetime import datetime, timedelta, timezone

import streamlit as st

from shared import asistan as A
from shared import bilesen as B
from shared.asistan_hesap import DURUM_AD, ORAN_ALANLARI, vergi_hesabi
from shared.tasarim import bos_durum, mesaj, tr_sayi

MENSELER = ["Çin", "Tayvan", "Güney Kore", "Vietnam", "Malezya", "Tayland", "Hindistan", "Japonya", "ABD",
            "Almanya", "AB (diğer)", "Diğer"]
PARALAR = ["USD", "EUR", "CNY", "TRY"]
DURUM_RENK = {"bekliyor": "amber", "calisiyor": "mavi", "tamam": "yesil", "hata": "kirmizi"}
GUVEN_AD = {"yüksek": "Güven yüksek", "orta": "Güven orta", "düşük": "Güven düşük"}


def _tr_zaman(iso):
    try:
        z = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if z.tzinfo is None:
            z = z.replace(tzinfo=timezone.utc)
        return z.astimezone(timezone(timedelta(hours=3))).strftime("%d.%m.%Y %H:%M")
    except (TypeError, ValueError):
        return str(iso or "")[:16]


def _gtip(g):
    g = "".join(ch for ch in str(g or "") if ch.isdigit())
    return ".".join([g[:4], g[4:6], g[6:8], g[8:10], g[10:12]][:max(1, (len(g) - 4) // 2 + 1)]) if g else "—"


def sayfa(baslik=True):
    """baslik=False: Ekip'in sekmesi içinde."""
    if baslik:
        B.baslik_eylem("İthalat", "Gümrük danışmanı · Hakan",
                       aciklama="Ürünü yaz; Hakan GTİP önerisini, vergi oranlarını, ek vergileri ve gereken "
                                "belgeleri araştırsın. Sonuç öneridir, gümrük müşavirine teyit ettir.")
    sorgular = A.gumruk_sorgulari()
    if sorgular is None:
        st.markdown(bos_durum("Gümrük danışmanı kurulmamış",
                              "veritabani/25_asistanlar.sql Supabase'de bir kez çalıştırılmalı.", "gavel"),
                    unsafe_allow_html=True)
        return
    _form()
    st.markdown(B.grup_basligi("Sorgular", f"{tr_sayi(len(sorgular))} kayıt"), unsafe_allow_html=True)
    if not sorgular:
        st.caption("Henüz sorgu yok.")
        return
    if any(s.get("durum") in ("bekliyor", "calisiyor") for s in sorgular):
        if st.button("Yenile", key="gm_yenile", icon=":material/refresh:"):
            A.gumruk_sorgulari.clear()
            st.rerun()
    for s in sorgular:
        _kart(s)


def _form():
    with st.form("gm_form", clear_on_submit=True):
        urun = st.text_area("Ürün", height=70, placeholder="ör. 27 inç IPS LED monitör, 165 Hz, HDMI + DP, model X27Q")
        c1, c2, c3, c4 = st.columns([1.4, 1.1, 0.8, 1.0])
        mense = c1.selectbox("Menşe ülke", MENSELER)
        fiyat = c2.number_input("Birim fiyat (FOB)", min_value=0.0, step=1.0, format="%.2f")
        para = c3.selectbox("Para", PARALAR)
        adet = c4.number_input("Adet", min_value=0, step=10)
        c5, c6 = st.columns(2)
        navlun = c5.number_input("Toplam navlun (varsa)", min_value=0.0, step=10.0, format="%.2f")
        sigorta = c6.number_input("Toplam sigorta (varsa)", min_value=0.0, step=1.0, format="%.2f")
        notu = st.text_input("Not (isteğe bağlı)", placeholder="ör. kablosuz özelliği var, AB menşe şahadetnamesi var")
        if st.form_submit_button("Hakan'a sor", type="primary", icon=":material/send:"):
            if len(urun.strip()) < 4:
                st.error("Ürünü birkaç kelimeyle tarif et (tür, özellik, model).")
                return
            ok, m = A.gumruk_ekle({"urun": urun.strip()[:500], "mense": mense, "birim_fiyat": fiyat or None,
                                   "para": para, "adet": adet or None, "navlun": navlun or None,
                                   "sigorta": sigorta or None, "notu": notu.strip()[:300]},
                                  st.session_state.get("aktif_kullanici", ""))
            (st.success(m) if ok else st.error(m))


def _kart(s):
    durum = s.get("durum") or "bekliyor"
    with st.container(border=True):
        k1, k2 = st.columns([4, 1.2], vertical_alignment="center")
        alt = " · ".join(x for x in (s.get("mense"), f"{tr_sayi(s.get('adet'))} adet" if s.get("adet") else "",
                                     f"{tr_sayi(s.get('birim_fiyat'), 2)} {s.get('para') or ''}"
                                     if s.get("birim_fiyat") else "", _tr_zaman(s.get("zaman"))) if x)
        k1.markdown(f"**{_h.escape(s.get('urun') or '')}**  \n<span style='color:var(--k-silik)'>{_h.escape(alt)}</span>",
                    unsafe_allow_html=True)
        k2.markdown(B.cip(DURUM_AD.get(durum, durum), DURUM_RENK.get(durum, "silik")), unsafe_allow_html=True)
        if durum in ("bekliyor", "calisiyor"):
            st.caption("Hakan araştırıyor; birkaç dakika sonra Yenile'ye bas.")
            return
        if durum == "hata":
            st.markdown(mesaj("hata", s.get("ozet") or "Hakan bu ürünü tamamlayamadı."), unsafe_allow_html=True)
            if st.button("Yeniden dene", key=f"gm_tekrar_{s['id']}", icon=":material/replay:"):
                ok, h = A.gumruk_yeniden(s["id"])
                (st.rerun() if ok else st.error(h))
            return
        _sonuc(s)


def _sonuc(s):
    r = s.get("sonuc") or {}
    o = r.get("oranlar") or {}
    st.markdown(f"**GTİP önerisi:** `{_gtip(r.get('gtip'))}` · {_h.escape(r.get('gtip_aciklama') or '')}  \n"
                + " · ".join(f"{ad} %{tr_sayi(o.get(k), 1)}" for k, ad in ORAN_ALANLARI if o.get(k) is not None)
                + f"  \n{GUVEN_AD.get(r.get('guven'), '')}")
    if s.get("ozet"):
        st.markdown(_h.escape(s["ozet"]))
    v = vergi_hesabi(s, o)
    if v:
        p = s.get("para") or ""
        st.dataframe([{"Kalem": a, "Tutar": f"{tr_sayi(v[k], 2)} {p}"} for a, k in (
            ("CIF (matrah)", "cif"), ("Gümrük vergisi", "gumruk_vergisi"),
            ("İlave gümrük vergisi", "ilave_gumruk_vergisi"), ("KDV (indirilebilir)", "kdv"),
            ("Maliyet, KDV hariç", "maliyet_kdv_haric"), ("Birim maliyet, KDV hariç", "birim_maliyet_kdv_haric"))],
            hide_index=True, use_container_width=True)
        st.caption("Ek vergiler (damping vb.) ve gümrük masrafları bu tabloya dahil değil.")
    for baslik, alan in (("Ek vergiler", "ek_vergiler"), ("Gereken belgeler", "belgeler"),
                         ("Dikkat", "uyarilar")):
        if r.get(alan):
            st.markdown(f"**{baslik}:**\n" + "\n".join(f"- {_h.escape(x)}" for x in r[alan]))
    if r.get("kaynaklar"):
        with st.expander("Kaynaklar"):
            st.markdown("\n".join(f"- {_h.escape(x)}" for x in r["kaynaklar"]))
    st.caption("Öneridir; kesin GTİP ve oranları gümrük müşavirine teyit ettir.")
