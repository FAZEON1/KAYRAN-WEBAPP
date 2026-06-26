# -*- coding: utf-8 -*-
"""Satış & Kârlılık modülü — arayüz (USD bazlı, tek tek işlem girişi)."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from shared.utils import sidebar_stil, sidebar_baslik, sidebar_kullanici
from .database import (
    KANALLAR, get_pacal_map, get_urunler, kampanya_destek_bul,
    ekle_satis, get_satislar, sil_satis, guncelle_satis,
    satir_kar, ozet_hesapla,
)


def _usd(x):
    try:
        return f"${float(x):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _kart(satirlar):
    return "".join(
        f'<div style="flex:1;min-width:120px;background:rgba(255,255,255,0.04);'
        f'border:1px solid rgba(148,163,184,0.2);border-radius:12px;padding:11px 15px">'
        f'<div style="font-size:10px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">{l}</div>'
        f'<div style="font-size:17px;font-weight:800;color:{c};font-family:monospace">{v}</div></div>'
        for l, v, c in satirlar)


def run():
    aktif_kullanici = st.session_state.get("aktif_kullanici", "")

    st.markdown("<style>.main .block-container{max-width:1200px !important;}</style>",
                unsafe_allow_html=True)

    with st.sidebar:
        st.markdown(sidebar_stil(), unsafe_allow_html=True)
        st.markdown(sidebar_baslik("💰", "Satış", "Satış & Kârlılık"), unsafe_allow_html=True)
        if aktif_kullanici:
            st.markdown(sidebar_kullanici(aktif_kullanici), unsafe_allow_html=True)
            if st.button("Çıkış Yap", use_container_width=True, key="satis_cikis"):
                st.session_state.giris_yapildi = False
                st.session_state.aktif_kullanici = ""
                st.session_state.aktif_uygulama = "anasayfa"
                st.rerun()

    st.markdown("## 💰 Satış & Kârlılık")
    st.caption("Her şey **USD**. Maliyet = güncel paçal (ağırlıklı ortalama landed), kayıt anında sabitlenir.")

    sekme1, sekme2, sekme3 = st.tabs(["🧾 Satış Girişi", "📋 Satışlar", "📊 Kâr / P&L"])

    # ───────────────────────── SATIŞ GİRİŞİ ─────────────────────────
    with sekme1:
        pacal = get_pacal_map()
        urunler = get_urunler()
        urun_map = {u["sku"]: u for u in urunler if u.get("sku")}
        # SKU seçenekleri: katalog + paçalı olanlar
        tum_sku = sorted(set(urun_map.keys()) | set(pacal.keys()))
        if not tum_sku:
            st.info("Henüz ürün/maliyet verisi yok. Önce İthalat/Ürün Yönetimi'nden ürün ve maliyet girilmeli.")
        else:
            with st.container(border=True):
                c1, c2, c3 = st.columns(3)
                g_tarih = c1.date_input("Tarih", value=date.today(), key="s_tarih")
                g_kanal = c2.selectbox("Kanal", KANALLAR, key="s_kanal")
                _sku_opts = [f"{s} — {urun_map.get(s, {}).get('urun_adi', '') or ''}".strip(" —") for s in tum_sku]
                _sec = c3.selectbox("Ürün (SKU)", _sku_opts, key="s_sku_sec")
                g_sku = tum_sku[_sku_opts.index(_sec)] if _sec in _sku_opts else (tum_sku[0] if tum_sku else "")
                g_urun = urun_map.get(g_sku, {})
                g_urun_adi = g_urun.get("urun_adi", "") or ""

                # Önerilen değerler
                _pacal = float(pacal.get(g_sku, 0) or 0)
                _liste = g_urun.get("satis_fiyat_listesi") or {}
                if isinstance(_liste, dict):
                    _oneri_satis = float(_liste.get(g_kanal) or _liste.get(g_kanal.upper()) or
                                         g_urun.get("satis_fiyati") or 0)
                else:
                    _oneri_satis = float(g_urun.get("satis_fiyati") or 0)
                _kfd, _ked, _kid = kampanya_destek_bul(g_sku, g_kanal, str(g_tarih))

                d1, d2, d3 = st.columns(3)
                g_adet = d1.number_input("Adet", min_value=0, step=1, value=1, key="s_adet")
                g_satis = d2.number_input("Birim Satış ($)", min_value=0.0, step=0.01, format="%.2f",
                                          value=round(_oneri_satis, 2) if _oneri_satis > 0 else None,
                                          placeholder="0.00", key="s_satis")
                g_maliyet = d3.number_input("Birim Maliyet ($) · paçal", min_value=0.0, step=0.01, format="%.2f",
                                            value=round(_pacal, 2) if _pacal > 0 else None,
                                            placeholder="0.00", key="s_maliyet",
                                            help="Güncel paçal otomatik gelir; gerekirse düzenleyebilirsin. Kayıtta sabitlenir.")
                if _pacal <= 0:
                    d3.caption("⚠️ Bu SKU için İthalat paçal maliyeti yok — elle gir.")

                e1, e2 = st.columns(2)
                g_fdestek = e1.number_input("Birim Firma Desteği ($)", min_value=0.0, step=0.01, format="%.2f",
                                            value=round(_kfd, 2) if _kfd > 0 else None, placeholder="0.00",
                                            key="s_fdestek")
                g_edestek = e2.number_input("Birim Ek Destek ($)", min_value=0.0, step=0.01, format="%.2f",
                                            value=round(_ked, 2) if _ked > 0 else None, placeholder="0.00",
                                            key="s_edestek")
                if _kid:
                    st.caption(f"🎯 Bu kanal+tarih için aktif kampanya bulundu — destekler otomatik dolduruldu (düzenleyebilirsin).")
                g_not = st.text_input("Not (opsiyonel)", key="s_not")

                # Canlı kâr önizleme
                _sat = {"adet": g_adet, "birim_satis": g_satis or 0, "birim_maliyet": g_maliyet or 0,
                        "birim_firma_destek": g_fdestek or 0, "birim_ek_destek": g_edestek or 0}
                k = satir_kar(_sat)
                _renk = "#34D399" if k["net_kar"] > 0 else ("#F87171" if k["net_kar"] < 0 else "#94A3B8")
                st.markdown(
                    '<div style="display:flex;gap:10px;flex-wrap:wrap;margin:12px 0 4px">' + _kart([
                        ("Ciro", _usd(k["ciro"]), "#CBD5E1"),
                        ("Maliyet", _usd(k["maliyet"]), "#FB923C"),
                        ("Destek", _usd(k["destek"]), "#A78BFA"),
                        ("Net Kâr", _usd(k["net_kar"]), _renk),
                        ("Marj", f"%{k['marj']:.1f}", _renk),
                    ]) + '</div>', unsafe_allow_html=True)

                if st.button("💾 Satışı Kaydet", type="primary", use_container_width=True, key="s_kaydet"):
                    if not g_sku:
                        st.warning("Ürün seç.")
                    elif g_adet <= 0:
                        st.warning("Adet 0'dan büyük olmalı.")
                    elif not g_satis or g_satis <= 0:
                        st.warning("Birim satış fiyatı gir.")
                    else:
                        ok, msg = ekle_satis(g_tarih, g_kanal, g_sku, g_urun_adi, g_adet,
                                             g_satis, g_maliyet or 0, g_fdestek or 0, g_edestek or 0,
                                             kampanya_id=_kid, notlar=g_not)
                        if ok:
                            st.success(msg + f" · Net kâr: {_usd(k['net_kar'])}")
                            for _k in ("s_adet", "s_satis", "s_maliyet", "s_fdestek", "s_edestek", "s_not"):
                                st.session_state.pop(_k, None)
                            st.rerun()
                        else:
                            st.error(msg)

    # ───────────────────────── SATIŞLAR ─────────────────────────
    with sekme2:
        f1, f2, f3 = st.columns([1, 1, 1.3])
        _bas = f1.date_input("Başlangıç", value=date.today() - timedelta(days=30), key="l_bas")
        _bit = f2.date_input("Bitiş", value=date.today(), key="l_bit")
        _kanal_f = f3.selectbox("Kanal", ["Tümü"] + KANALLAR, key="l_kanal")

        satislar = get_satislar(_bas, _bit)
        if _kanal_f != "Tümü":
            satislar = [s for s in satislar if (s.get("kanal") or "") == _kanal_f]

        if not satislar:
            st.info("Bu aralıkta satış kaydı yok.")
        else:
            _rows_disp = []
            for s in satislar:
                k = satir_kar(s)
                _rows_disp.append({
                    "id": s.get("id"), "Tarih": str(s.get("tarih", ""))[:10], "Kanal": s.get("kanal", ""),
                    "SKU": s.get("sku", ""), "Ürün": (s.get("urun_adi", "") or "")[:34],
                    "Adet": k["adet"], "B.Satış": _usd(s.get("birim_satis")),
                    "B.Maliyet": _usd(s.get("birim_maliyet")),
                    "Destek": _usd(s.get("birim_firma_destek", 0)) if (s.get("birim_firma_destek") or s.get("birim_ek_destek")) else "—",
                    "Ciro": _usd(k["ciro"]), "Net Kâr": _usd(k["net_kar"]), "Marj": f"%{k['marj']:.1f}",
                })
            st.dataframe(pd.DataFrame(_rows_disp), hide_index=True, use_container_width=True, height=380,
                         column_config={"id": None})
            with st.expander("🗑️ Satış sil"):
                _sec_sil = st.selectbox(
                    "Silinecek kayıt", satislar,
                    format_func=lambda s: f"#{s.get('id')} · {str(s.get('tarih',''))[:10]} · {s.get('kanal','')} · {s.get('sku','')} · {s.get('adet')} adet",
                    key="l_sil_sec")
                if st.button("🗑️ Seçili Satışı Sil", key="l_sil_btn"):
                    if sil_satis(_sec_sil["id"]):
                        st.success("✅ Silindi.")
                        st.rerun()
                    else:
                        st.error("Silinemedi.")

    # ───────────────────────── KÂR / P&L ─────────────────────────
    with sekme3:
        p1, p2, p3 = st.columns([1, 1, 1.4])
        _pbas = p1.date_input("Başlangıç", value=date.today() - timedelta(days=30), key="p_bas")
        _pbit = p2.date_input("Bitiş", value=date.today(), key="p_bit")
        _hizli = p3.selectbox("Hızlı", ["—", "Bugün", "Son 7 gün", "Bu ay"], key="p_hizli")
        if _hizli == "Bugün":
            _pbas = _pbit = date.today()
        elif _hizli == "Son 7 gün":
            _pbas, _pbit = date.today() - timedelta(days=6), date.today()
        elif _hizli == "Bu ay":
            _pbas, _pbit = date.today().replace(day=1), date.today()

        satislar = get_satislar(_pbas, _pbit)
        if not satislar:
            st.info("Bu aralıkta satış yok.")
        else:
            top, kanal, urun = ozet_hesapla(satislar)
            _renk = "#34D399" if top["net_kar"] > 0 else "#F87171"
            st.markdown(
                '<div style="display:flex;gap:10px;flex-wrap:wrap;margin:8px 0 14px">' + _kart([
                    ("Ciro", _usd(top["ciro"]), "#CBD5E1"),
                    ("Maliyet (COGS)", _usd(top["maliyet"]), "#FB923C"),
                    ("Destek", _usd(top["destek"]), "#A78BFA"),
                    ("Net Kâr", _usd(top["net_kar"]), _renk),
                    ("Marj", f"%{top['marj']:.1f}", _renk),
                    ("Adet", f"{int(top['adet']):,}", "#93C5FD"),
                ]) + '</div>', unsafe_allow_html=True)

            st.markdown("#### Kanal Kırılımı")
            _kr = sorted(kanal.items(), key=lambda x: -x[1]["net_kar"])
            st.dataframe(pd.DataFrame([{
                "Kanal": kn, "Adet": int(v["adet"]), "Ciro": _usd(v["ciro"]),
                "Net Kâr": _usd(v["net_kar"]),
                "Marj": f"%{(v['net_kar']/v['ciro']*100) if v['ciro']>0 else 0:.1f}",
            } for kn, v in _kr]), hide_index=True, use_container_width=True)

            st.markdown("#### Ürün Kırılımı (net kâra göre)")
            _ur = sorted(urun.items(), key=lambda x: -x[1]["net_kar"])
            st.dataframe(pd.DataFrame([{
                "SKU": su, "Ürün": (v["urun_adi"] or "")[:36], "Adet": int(v["adet"]),
                "Ciro": _usd(v["ciro"]), "Net Kâr": _usd(v["net_kar"]),
                "Marj": f"%{(v['net_kar']/v['ciro']*100) if v['ciro']>0 else 0:.1f}",
            } for su, v in _ur]), hide_index=True, use_container_width=True, height=320)
