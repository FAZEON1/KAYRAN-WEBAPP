# -*- coding: utf-8 -*-
"""SKU Stok Kartı — ortada açılan modal pencere.
Sekmeler: 📊 Özet · 📥 Alımlar · 📤 Satışlar · 📈 Analiz
Veriyi ürün/stok (kayranpm), ithalat ve satış modüllerinden birleştirir."""
import streamlit as st
import pandas as pd

try:
    from shared.utils import gun_ay_yil
except Exception:
    def gun_ay_yil(d):
        return str(d or "")[:10]


def _f(v, d=0.0):
    try:
        if v in (None, ""):
            return d
        return float(str(v).replace(",", "").replace(" ", ""))
    except Exception:
        return d


def _usd(v):
    return f"${_f(v):,.2f}"


def _kart(baslik, deger, alt="", renk="#A5B4FC"):
    return (
        f'<div style="flex:1;min-width:150px;background:rgba(255,255,255,0.03);'
        f'border:1px solid rgba(255,255,255,0.08);border-left:3px solid {renk};'
        f'border-radius:10px;padding:11px 14px">'
        f'<div style="color:#94A3B8;font-size:11px;text-transform:uppercase;letter-spacing:.4px">{baslik}</div>'
        f'<div style="color:{renk};font-size:20px;font-weight:700;margin-top:2px">{deger}</div>'
        f'<div style="color:#64748B;font-size:11px;margin-top:1px">{alt}</div></div>'
    )


def _kart_satiri(kartlar):
    st.markdown('<div style="display:flex;gap:10px;flex-wrap:wrap;margin:6px 0 14px">'
                + "".join(kartlar) + '</div>', unsafe_allow_html=True)


@st.dialog("📦 Stok Kartı", width="large")
def goster(sku):
    sku = str(sku or "").strip()
    if not sku:
        st.warning("SKU seçilmedi.")
        return

    from kayranpm.database import get_client, get_urun_detay
    sb = get_client()
    urun = get_urun_detay(sku) or {}

    # ── SKU bazlı veri çek ──
    def _sel(tablo):
        try:
            return sb.table(tablo).select("*").eq("sku", sku).execute().data or []
        except Exception:
            return []

    firma_stok = _sel("firma_stok")
    yas_rows = _sel("stok_yas")
    yolda_rows = _sel("yoldaki_urunler")

    maliyet, alimlar = {}, []
    try:
        from ithalat.database import get_sku_maliyet_ozet, get_sku_alim_detay
        maliyet = get_sku_maliyet_ozet().get(sku, {}) or {}
        alimlar = get_sku_alim_detay(sku) or []
    except Exception:
        pass

    satislar, satir_kar = [], None
    try:
        from satis.database import get_satislar, satir_kar as _sk
        satir_kar = _sk
        satislar = [s for s in (get_satislar() or []) if str(s.get("sku", "")).strip() == sku]
    except Exception:
        pass

    # ── Ortak hesaplar ──
    toplam_stok = sum(_f(r.get("stok_miktari")) for r in firma_stok)
    yolda_adet = sum(_f(r.get("yoldaki_miktar")) for r in yolda_rows)
    haftalik = sum(_f(r.get("haftalik_satis")) for r in firma_stok)
    liste_fiyat = _f(urun.get("satis_fiyati"))
    pacal_final = _f(maliyet.get("pacal_final"))
    son_final = _f(maliyet.get("son_final"))
    son_tarih = maliyet.get("son_tarih") or ""
    ilk_gorulen = (yas_rows[0].get("ilk_gorulen_tarih") if yas_rows else "") or ""

    # Başlık
    st.markdown(f"#### {sku} — {urun.get('urun_adi') or '—'}")
    st.caption(f"Marka: **{urun.get('marka') or '—'}**  ·  Kategori: **{urun.get('kategori') or '—'}**  "
               f"·  Barkod: **{urun.get('barkod') or '—'}**")

    t1, t2, t3, t4 = st.tabs(["📊 Özet", "📥 Alımlar", "📤 Satışlar", "📈 Analiz"])

    # ═══ ÖZET ═══
    with t1:
        _hafta_yeter = (toplam_stok / haftalik) if haftalik > 0 else None
        _yeter_txt = (f"~{_hafta_yeter:.0f} hafta yeter" if _hafta_yeter is not None else "satış verisi yok")
        _kart_satiri([
            _kart("Toplam Stok", f"{toplam_stok:,.0f}", _yeter_txt, "#34D399"),
            _kart("Yolda (İthalat)", f"{yolda_adet:,.0f}", "gelen sipariş", "#FBBF24"),
            _kart("Paçal Maliyet", _usd(pacal_final), "adet-ağırlıklı", "#F87171"),
            _kart("Liste Satış", _usd(liste_fiyat), "güncel", "#A5B4FC"),
        ])
        if firma_stok:
            st.markdown("**Firma / Depo Stok Kırılımı**")
            _df = pd.DataFrame([{
                "Firma/Depo": r.get("firma", ""),
                "Stok": _f(r.get("stok_miktari")),
                "Haftalık Satış": _f(r.get("haftalik_satis")),
                "Güncellenme": gun_ay_yil(r.get("yukleme_tarihi")),
            } for r in firma_stok])
            st.dataframe(_df, hide_index=True, use_container_width=True)
        else:
            st.info("Bu SKU için firma/depo stok kaydı yok.")
        st.caption(f"İlk görülme: {gun_ay_yil(ilk_gorulen) or '—'}  ·  "
                   f"Son alım: {gun_ay_yil(son_tarih) or '—'}")

    # ═══ ALIMLAR ═══
    with t2:
        if alimlar:
            _toplam_alinan = sum(_f(a["adet"]) for a in alimlar)
            _kart_satiri([
                _kart("Toplam Alınan", f"{_toplam_alinan:,.0f}", f"{len(alimlar)} parti", "#34D399"),
                _kart("Son Alım Birim", _usd(son_final), gun_ay_yil(son_tarih), "#FBBF24"),
                _kart("Paçal (Final)", _usd(pacal_final), "tüm partiler", "#F87171"),
            ])
            _df = pd.DataFrame([{
                "Tarih": gun_ay_yil(a["tarih"]),
                "Belge": a["belge_no"],
                "Tedarikçi": a["tedarikci"],
                "Ülke": a["ulke"],
                "Döviz": a["doviz"],
                "Adet": _f(a["adet"]),
                "Birim FOB": round(_f(a["birim_fob"]), 2),
                "% Maliyet": round(_f(a["maliyet_yuzde"]), 1),
                "Final Birim": round(_f(a["final_birim"]), 2),
            } for a in alimlar])
            st.dataframe(_df, hide_index=True, use_container_width=True)
        else:
            st.info("Bu SKU için ithalat alım kaydı bulunamadı.")

    # ═══ SATIŞLAR ═══
    with t3:
        if satislar and satir_kar:
            _topl_adet = _topl_ciro = _topl_kar = 0.0
            _kanal = {}
            _rows = []
            for s in satislar:
                k = satir_kar(s)
                _topl_adet += _f(k.get("adet"))
                _topl_ciro += _f(k.get("ciro"))
                _topl_kar += _f(k.get("net_kar"))
                kn = s.get("kanal", "") or "—"
                kc = _kanal.setdefault(kn, {"adet": 0.0, "ciro": 0.0, "kar": 0.0})
                kc["adet"] += _f(k.get("adet"))
                kc["ciro"] += _f(k.get("ciro"))
                kc["kar"] += _f(k.get("net_kar"))
                _rows.append({
                    "Tarih": gun_ay_yil(s.get("tarih")),
                    "Kanal/Firma": kn,
                    "Sipariş No": s.get("siparis_no", "") or "—",
                    "Adet": _f(k.get("adet")),
                    "B.Satış": round(_f(s.get("birim_satis")), 2),
                    "Net Kâr": round(_f(k.get("net_kar")), 2),
                    "Marj": f"%{_f(k.get('marj')):.1f}",
                })
            _ort_marj = (_topl_kar / _topl_ciro * 100) if _topl_ciro else 0.0
            _kart_satiri([
                _kart("Toplam Satılan", f"{_topl_adet:,.0f}", f"{len(satislar)} kalem", "#34D399"),
                _kart("Toplam Ciro", _usd(_topl_ciro), "", "#A5B4FC"),
                _kart("Toplam Kâr", _usd(_topl_kar), f"ort. marj %{_ort_marj:.1f}",
                      "#34D399" if _topl_kar >= 0 else "#F87171"),
            ])
            st.markdown("**Kanal / Firma Kırılımı**")
            _kdf = pd.DataFrame([{
                "Kanal/Firma": kn, "Adet": v["adet"],
                "Ciro": _usd(v["ciro"]), "Kâr": _usd(v["kar"]),
            } for kn, v in sorted(_kanal.items(), key=lambda x: -x[1]["ciro"])])
            st.dataframe(_kdf, hide_index=True, use_container_width=True)
            st.markdown("**Satış Hareketleri**")
            st.dataframe(pd.DataFrame(_rows), hide_index=True, use_container_width=True)
        else:
            st.info("Bu SKU için satış kaydı bulunamadı.")

    # ═══ ANALİZ ═══
    with t4:
        # Marj sağlığı
        if pacal_final > 0 and liste_fiyat > 0:
            _marj = (liste_fiyat - pacal_final) / liste_fiyat * 100
            if liste_fiyat <= pacal_final:
                st.error(f"⚠️ **Zarar riski:** Liste satış ({_usd(liste_fiyat)}) ≤ paçal maliyet ({_usd(pacal_final)}).")
            elif _marj < 10:
                st.warning(f"⚠️ **Düşük marj:** Liste fiyatına göre teorik marj sadece %{_marj:.1f}.")
            else:
                st.success(f"✅ **Sağlıklı marj:** Liste fiyatına göre teorik marj %{_marj:.1f}.")
        # Tükenme tahmini
        if haftalik > 0:
            _kalan_hafta = toplam_stok / haftalik
            if _kalan_hafta < 4:
                st.warning(f"📉 **Stok azalıyor:** Mevcut hızda (~{haftalik:.0f}/hafta) stok ~{_kalan_hafta:.0f} hafta yeter. "
                           f"Yolda {yolda_adet:,.0f} adet var.")
            else:
                st.info(f"📦 Mevcut hızda (~{haftalik:.0f}/hafta) stok ~{_kalan_hafta:.0f} hafta yeter.")
        elif toplam_stok > 0:
            st.info("ℹ️ Haftalık satış verisi yok — tükenme tahmini yapılamıyor.")
        # Ölü stok uyarısı
        if toplam_stok > 0 and haftalik <= 0 and not satislar:
            st.warning("🪦 **Hareketsiz stok:** Stok var ama satış geçmişi yok. Ölü stok olabilir.")
        # En kârlı kanal
        if satislar and satir_kar:
            _kanal2 = {}
            for s in satislar:
                k = satir_kar(s)
                _kanal2.setdefault(s.get("kanal", "") or "—", [0.0])[0] += _f(k.get("net_kar"))
            if _kanal2:
                _en = max(_kanal2.items(), key=lambda x: x[1][0])
                st.info(f"🏆 **En kârlı kanal:** {_en[0]} ({_usd(_en[1][0])} toplam kâr).")
        # Tedarikçi karşılaştırması
        if alimlar:
            _ted = {}
            for a in alimlar:
                t = a["tedarikci"] or "—"
                tt = _ted.setdefault(t, {"fob_x": 0.0, "adet": 0.0})
                tt["fob_x"] += _f(a["birim_fob"]) * _f(a["adet"])
                tt["adet"] += _f(a["adet"])
            if len(_ted) > 1:
                st.markdown("**Tedarikçi Karşılaştırması (ort. birim FOB)**")
                _tdf = pd.DataFrame([{
                    "Tedarikçi": t,
                    "Toplam Adet": v["adet"],
                    "Ort. Birim FOB": round(v["fob_x"] / v["adet"], 2) if v["adet"] else 0,
                } for t, v in sorted(_ted.items(), key=lambda x: x[1]["fob_x"] / x[1]["adet"] if x[1]["adet"] else 0)])
                st.dataframe(_tdf, hide_index=True, use_container_width=True)

    st.divider()
    if st.button("Kapat", use_container_width=True):
        st.rerun()
