# -*- coding: utf-8 -*-
"""Satış & Kârlılık modülü — arayüz (USD bazlı, tek tek işlem girişi)."""
from datetime import date, timedelta, datetime

import pandas as pd
import streamlit as st

from shared.utils import sidebar_stil, sidebar_baslik, sidebar_kullanici
from .database import (
    KANALLAR, get_kanallar, get_pacal_map, get_urunler, kampanya_destek_bul,
    ekle_satis, ekle_siparis, get_satislar, sil_satis, sil_siparis, guncelle_satis,
    satir_kar, ozet_hesapla, TR_TZ,
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
    _kanallar = get_kanallar()

    # ───────────────────────── SATIŞ GİRİŞİ ─────────────────────────
    with sekme1:
        pacal = get_pacal_map()
        urunler = get_urunler()
        urun_map = {u["sku"]: u for u in urunler if u.get("sku")}
        tum_sku = sorted(set(urun_map.keys()) | set(pacal.keys()))
        st.session_state.setdefault("satis_kalemler", [])
        kalemler = st.session_state.satis_kalemler

        if not tum_sku:
            st.info("Henüz ürün/maliyet verisi yok. Önce İthalat/Ürün Yönetimi'nden ürün ve maliyet girilmeli.")
        else:
            # ── Sipariş başlığı ──
            with st.container(border=True):
                st.markdown("##### 🧾 Sipariş Bilgileri")
                h1, h2, h3 = st.columns([1, 1.4, 1])
                g_tarih = h1.date_input("Tarih", value=date.today(), key="s_tarih")
                g_kanal = h2.selectbox("Kanal / Cari", _kanallar, key="s_kanal",
                                       help="Muhasebe'ye yüklediğin cari listesinden gelir (yoksa varsayılan).")
                g_sipno = h3.text_input("Sipariş No (ops.)", key="s_sipno", placeholder="boşsa otomatik")
                g_not = st.text_input("Sipariş notu (ops.)", key="s_not")

            # ── Kalem ekle ──
            with st.container(border=True):
                st.markdown("##### ➕ Ürün Kalemi Ekle")
                _sku_opts = [f"{s} — {urun_map.get(s, {}).get('urun_adi', '') or ''}".strip(" —") for s in tum_sku]
                a1, a2, a3, a4 = st.columns([2.6, 0.9, 1.1, 1.1])
                _sec = a1.selectbox("Ürün (SKU ara)", _sku_opts, key="s_sku_sec", label_visibility="collapsed",
                                    placeholder="SKU / ürün ara")
                _sku = tum_sku[_sku_opts.index(_sec)] if _sec in _sku_opts else (tum_sku[0] if tum_sku else "")
                _urun = urun_map.get(_sku, {})
                _pacal = float(pacal.get(_sku, 0) or 0)
                _liste = _urun.get("satis_fiyat_listesi") or {}
                if isinstance(_liste, dict):
                    _oneri = float(_liste.get(g_kanal) or _liste.get(str(g_kanal).upper()) or _urun.get("satis_fiyati") or 0)
                else:
                    _oneri = float(_urun.get("satis_fiyati") or 0)
                _adet = a2.number_input("Adet", min_value=1, step=1, value=1, key="s_adet", label_visibility="collapsed")
                _bsat = a3.number_input("Birim Satış $", min_value=0.0, step=0.01, format="%.2f",
                                        value=round(_oneri, 2) if _oneri > 0 else None, placeholder="Satış $",
                                        key="s_bsat", label_visibility="collapsed")
                if a4.button("➕ Ekle", use_container_width=True, key="s_ekle"):
                    if not _bsat or _bsat <= 0:
                        st.warning("Birim satış fiyatı gir.")
                    else:
                        _kfd, _ked, _kid = kampanya_destek_bul(_sku, g_kanal, str(g_tarih))
                        kalemler.append({
                            "sku": _sku, "urun_adi": _urun.get("urun_adi", "") or "",
                            "adet": int(_adet), "birim_satis": float(_bsat),
                            "birim_maliyet": round(_pacal, 4), "birim_firma_destek": round(_kfd, 4),
                            "birim_ek_destek": round(_ked, 4), "kampanya_id": _kid,
                        })
                        st.session_state.satis_kalemler = kalemler
                        st.rerun()
                _ipucu = []
                _ipucu.append(f"Maliyet (paçal): {_usd(_pacal)}" if _pacal > 0 else "⚠️ Paçal maliyet yok — kalemde elle düzelt")
                a3.caption(_ipucu[0])

            # ── Sepet (kalemler) ──
            if not kalemler:
                st.info("Henüz kalem eklenmedi. Yukarıdan ürün ekleyerek siparişi oluştur.")
            else:
                st.markdown("##### 🛒 Sipariş Kalemleri — düzenle / sil")
                _df = pd.DataFrame([{
                    "Sil": False, "SKU": k["sku"], "Ürün": (k["urun_adi"] or "")[:30],
                    "Adet": int(k["adet"]), "B.Satış$": float(k["birim_satis"]),
                    "Maliyet$": float(k["birim_maliyet"]), "Firma Destek$": float(k["birim_firma_destek"]),
                    "Ek Destek$": float(k["birim_ek_destek"]),
                } for k in kalemler])
                _ed = st.data_editor(
                    _df, hide_index=True, use_container_width=True, num_rows="fixed",
                    key=f"satis_cart_{len(kalemler)}",
                    column_config={
                        "Sil": st.column_config.CheckboxColumn("🗑", width="small"),
                        "SKU": st.column_config.TextColumn("SKU", disabled=True),
                        "Ürün": st.column_config.TextColumn("Ürün", disabled=True),
                        "Adet": st.column_config.NumberColumn("Adet", min_value=0, step=1),
                        "B.Satış$": st.column_config.NumberColumn("B.Satış $", min_value=0.0, format="%.2f"),
                        "Maliyet$": st.column_config.NumberColumn("Maliyet $", min_value=0.0, format="%.2f"),
                        "Firma Destek$": st.column_config.NumberColumn("Firma Destek $", min_value=0.0, format="%.2f"),
                        "Ek Destek$": st.column_config.NumberColumn("Ek Destek $", min_value=0.0, format="%.2f"),
                    },
                )
                # Düzenlemeleri session'a yansıt + Sil işaretlileri çıkar
                _yeni = []
                for i, row in _ed.iterrows():
                    if bool(row.get("Sil")):
                        continue
                    k = dict(kalemler[i])
                    k["adet"] = int(row["Adet"] or 0)
                    k["birim_satis"] = float(row["B.Satış$"] or 0)
                    k["birim_maliyet"] = float(row["Maliyet$"] or 0)
                    k["birim_firma_destek"] = float(row["Firma Destek$"] or 0)
                    k["birim_ek_destek"] = float(row["Ek Destek$"] or 0)
                    _yeni.append(k)
                if _yeni != kalemler:
                    st.session_state.satis_kalemler = _yeni
                    st.rerun()
                kalemler = _yeni

                # ── Sipariş özeti (canlı) ──
                top, _, _ = ozet_hesapla(kalemler)
                _renk = "#34D399" if top["net_kar"] > 0 else ("#F87171" if top["net_kar"] < 0 else "#94A3B8")
                st.markdown(
                    '<div style="display:flex;gap:10px;flex-wrap:wrap;margin:12px 0 6px">' + _kart([
                        ("Kalem / Adet", f"{len(kalemler)} / {int(top['adet']):,}", "#93C5FD"),
                        ("Ciro", _usd(top["ciro"]), "#CBD5E1"),
                        ("Maliyet", _usd(top["maliyet"]), "#FB923C"),
                        ("Destek", _usd(top["destek"]), "#A78BFA"),
                        ("Net Kâr", _usd(top["net_kar"]), _renk),
                        ("Net Kârlılık", f"%{top['marj']:.1f}", _renk),
                    ]) + '</div>', unsafe_allow_html=True)

                b1, b2 = st.columns([3, 1])
                if b1.button("💾 Siparişi Kaydet", type="primary", use_container_width=True, key="s_kaydet"):
                    gecerli = [k for k in kalemler if k.get("sku") and int(k.get("adet", 0)) > 0
                               and float(k.get("birim_satis", 0)) > 0]
                    if not gecerli:
                        st.warning("Kaydedilecek geçerli kalem yok (adet ve satış > 0 olmalı).")
                    else:
                        sipno = (g_sipno or "").strip() or f"S{datetime.now(TR_TZ).strftime('%y%m%d-%H%M%S')}"
                        ok, msg, n = ekle_siparis(g_tarih, g_kanal, sipno, g_not, gecerli)
                        if ok:
                            st.success(f"{msg} · Sipariş No: {sipno} · Net kâr: {_usd(top['net_kar'])}")
                            st.session_state.satis_kalemler = []
                            for _k in ("s_sipno", "s_not", "s_adet", "s_bsat"):
                                st.session_state.pop(_k, None)
                            st.rerun()
                        else:
                            st.error(msg)
                if b2.button("🧹 Temizle", use_container_width=True, key="s_temizle"):
                    st.session_state.satis_kalemler = []
                    st.rerun()

    # ───────────────────────── SATIŞLAR ─────────────────────────
    with sekme2:
        f1, f2, f3 = st.columns([1, 1, 1.3])
        _bas = f1.date_input("Başlangıç", value=date.today() - timedelta(days=30), key="l_bas")
        _bit = f2.date_input("Bitiş", value=date.today(), key="l_bit")
        _kanal_f = f3.selectbox("Kanal", ["Tümü"] + _kanallar, key="l_kanal")

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
                    "id": s.get("id"), "Tarih": str(s.get("tarih", ""))[:10],
                    "Sipariş No": s.get("siparis_no", "") or "—", "Kanal": s.get("kanal", ""),
                    "SKU": s.get("sku", ""), "Ürün": (s.get("urun_adi", "") or "")[:30],
                    "Adet": k["adet"], "B.Satış": _usd(s.get("birim_satis")),
                    "B.Maliyet": _usd(s.get("birim_maliyet")),
                    "Destek": _usd((s.get("birim_firma_destek") or 0) + (s.get("birim_ek_destek") or 0)) if (s.get("birim_firma_destek") or s.get("birim_ek_destek")) else "—",
                    "Ciro": _usd(k["ciro"]), "Net Kâr": _usd(k["net_kar"]), "Marj": f"%{k['marj']:.1f}",
                })
            st.dataframe(pd.DataFrame(_rows_disp), hide_index=True, use_container_width=True, height=380,
                         column_config={"id": None})
            with st.expander("🗑️ Sil — kalem veya sipariş"):
                _ds1, _ds2 = st.columns(2)
                with _ds1:
                    _sec_sil = st.selectbox(
                        "Tek kalem sil", satislar,
                        format_func=lambda s: f"#{s.get('id')} · {str(s.get('tarih',''))[:10]} · {s.get('kanal','')} · {s.get('sku','')} · {s.get('adet')} ad.",
                        key="l_sil_sec")
                    if st.button("🗑️ Kalemi Sil", key="l_sil_btn"):
                        if sil_satis(_sec_sil["id"]):
                            st.success("✅ Silindi.")
                            st.rerun()
                        else:
                            st.error("Silinemedi.")
                with _ds2:
                    _sipnolar = sorted({(s.get("siparis_no") or "").strip() for s in satislar if (s.get("siparis_no") or "").strip()})
                    if _sipnolar:
                        _sec_sip = st.selectbox("Tüm siparişi sil", _sipnolar, key="l_sil_sip")
                        if st.button("🗑️ Siparişi Sil", key="l_sil_sip_btn"):
                            if sil_siparis(_sec_sip):
                                st.success(f"✅ '{_sec_sip}' siparişi silindi.")
                                st.rerun()
                            else:
                                st.error("Silinemedi.")
                    else:
                        st.caption("Sipariş no'lu kayıt yok.")

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
