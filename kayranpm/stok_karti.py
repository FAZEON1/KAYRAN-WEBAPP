# -*- coding: utf-8 -*-
"""SKU Stok Kartı — ortada açılan modal pencere.
Sekmeler: 📊 Özet · 📥 Alımlar · 📤 Satışlar · 🎯 Kampanya · 📈 Analiz
Veriyi ürün/stok (kayranpm), ithalat ve satış modüllerinden birleştirir.
Performans: satışlar SKU bazlı çekilir, paçal alım partilerinden hesaplanır."""
import streamlit as st
import pandas as pd
from datetime import timedelta

try:
    from shared.utils import gun_ay_yil, tr_today
except Exception:
    def gun_ay_yil(d):
        return str(d or "")[:10]
    from datetime import date as _d
    def tr_today():
        return _d.today()


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


@st.cache_data(ttl=300, show_spinner=False)
def _tum_satis_ozeti():
    """ABC / kâr katkısı için: tüm satışlardan SKU bazlı kâr+ciro toplamı.
    Dönen: {toplam_kar, toplam_ciro, sku_kar:{}, sku_ciro:{}}"""
    try:
        from satis.database import get_satislar, satir_kar
        sku_kar, sku_ciro = {}, {}
        tk = tc = 0.0
        for s in (get_satislar() or []):
            k = satir_kar(s)
            sku = str(s.get("sku", "")).strip()
            sku_kar[sku] = sku_kar.get(sku, 0.0) + _f(k.get("net_kar"))
            sku_ciro[sku] = sku_ciro.get(sku, 0.0) + _f(k.get("ciro"))
            tk += _f(k.get("net_kar"))
            tc += _f(k.get("ciro"))
        return {"toplam_kar": tk, "toplam_ciro": tc, "sku_kar": sku_kar, "sku_ciro": sku_ciro}
    except Exception:
        return {"toplam_kar": 0.0, "toplam_ciro": 0.0, "sku_kar": {}, "sku_ciro": {}}


def _alim_detay(a):
    st.divider()
    st.markdown(f"##### 📄 Alım Detayı — {a.get('belge_no') or '—'}")
    st.markdown(
        f"- **Sipariş Tarihi:** {gun_ay_yil(a.get('siparis_tarih')) or '—'}  ·  "
        f"**Teslim:** {gun_ay_yil(a.get('teslim_tarih')) or '—'}\n"
        f"- **Tedarikçi:** {a.get('tedarikci') or '—'} ({a.get('ulke') or '—'})  ·  "
        f"**Takip No:** {a.get('takip_no') or '—'}\n"
        f"- **Döviz / Kur:** {a.get('doviz')} / {_f(a.get('kur')):.2f}  ·  "
        f"**Durum:** {a.get('durum') or '—'}"
    )
    _ind = _f(a.get("indirim_orani")) * 100
    st.markdown(
        f"**Bu kalem:** {_f(a.get('adet')):,.0f} adet × birim FOB {_usd(a.get('birim_fob'))}"
        + (f" (indirim %{_ind:.1f})" if _ind else "")
        + f"  →  final birim **{_usd(a.get('final_birim'))}** "
        f"(masraf %{_f(a.get('maliyet_yuzde')):.1f})"
    )
    try:
        from ithalat.database import masraf_dokumu
        _md = masraf_dokumu(a.get("_dosya") or {})
        if _md:
            st.markdown("**Dosya Masraf Dökümü**")
            st.dataframe(pd.DataFrame([{"Masraf": ad, "Tutar": _usd(t)} for ad, t in _md]),
                         hide_index=True, use_container_width=True)
    except Exception:
        pass


def _satis_detay(s, satir_kar):
    st.divider()
    k = satir_kar(s) if satir_kar else {}
    st.markdown(f"##### 📄 Satış Detayı — {gun_ay_yil(s.get('tarih'))} · {s.get('kanal') or '—'}")
    _destek = _f(s.get("birim_firma_destek")) + _f(s.get("birim_ek_destek"))
    st.markdown(
        f"- **Sipariş No:** {s.get('siparis_no') or '—'}\n"
        f"- **Adet:** {_f(k.get('adet') or s.get('adet')):,.0f}  ·  "
        f"**Birim Satış:** {_usd(s.get('birim_satis'))}  ·  "
        f"**Birim Maliyet:** {_usd(s.get('birim_maliyet'))}\n"
        f"- **Birim Destek:** {_usd(_destek)}  ·  "
        f"**Ciro:** {_usd(k.get('ciro'))}  ·  "
        f"**Net Kâr:** {_usd(k.get('net_kar'))} (marj %{_f(k.get('marj')):.1f})"
    )
    if s.get("kampanya_id"):
        st.caption(f"🎯 Kampanya ID: {s.get('kampanya_id')}")
    if s.get("notlar"):
        st.caption(f"📝 Not: {s.get('notlar')}")


@st.dialog("📦 Stok Kartı", width="large")
def goster(sku):
    sku = str(sku or "").strip()
    if not sku:
        st.warning("SKU seçilmedi.")
        return

    from kayranpm.database import get_client, get_urun_detay, get_uretim_suresi
    sb = get_client()
    urun = get_urun_detay(sku) or {}

    def _sel(tablo, order=None, desc=False):
        try:
            q = sb.table(tablo).select("*").eq("sku", sku)
            if order:
                q = q.order(order, desc=desc)
            return q.execute().data or []
        except Exception:
            return []

    firma_stok = _sel("firma_stok")
    yas_rows = _sel("stok_yas")
    yolda_rows = _sel("yoldaki_urunler")
    satislar = _sel("satislar", order="tarih", desc=True)
    kampanya_urun = _sel("kampanya_urunler")

    # Alımlar (ithalat) — paçal buradan hesaplanır (ayrı maliyet sorgusu yok = hızlı)
    alimlar = []
    try:
        from ithalat.database import get_sku_alim_detay
        alimlar = get_sku_alim_detay(sku) or []
    except Exception:
        pass
    _adet_t = sum(_f(a["adet"]) for a in alimlar)
    pacal_final = (sum(_f(a["final_birim"]) * _f(a["adet"]) for a in alimlar) / _adet_t) if _adet_t else 0.0
    son = next((a for a in alimlar if _f(a.get("birim_fob")) > 0), (alimlar[0] if alimlar else {}))
    son_fob = _f(son.get("birim_fob"))
    son_final = _f(son.get("final_birim"))
    son_tarih = son.get("tarih", "") or ""

    satir_kar = None
    try:
        from satis.database import satir_kar as _sk
        satir_kar = _sk
    except Exception:
        pass

    try:
        uretim_suresi = get_uretim_suresi()
    except Exception:
        uretim_suresi = 135

    # ── Ortak hesaplar ──
    toplam_stok = sum(_f(r.get("stok_miktari")) for r in firma_stok)
    yolda_adet = sum(_f(r.get("yoldaki_miktar")) for r in yolda_rows)
    haftalik_statik = sum(_f(r.get("haftalik_satis")) for r in firma_stok)
    liste_fiyat = _f(urun.get("satis_fiyati"))
    stok_degeri = toplam_stok * pacal_final
    ilk_gorulen = (yas_rows[0].get("ilk_gorulen_tarih") if yas_rows else "") or ""

    # Gerçek satış hızı (son 90 gün)
    _90 = (tr_today() - timedelta(days=90)).isoformat()
    _son90 = sum(_f(s.get("adet")) for s in satislar if str(s.get("tarih", ""))[:10] >= _90)
    gunluk_hiz = _son90 / 90.0
    haftalik_gercek = gunluk_hiz * 7

    # Başlık
    st.markdown(f"#### {sku} — {urun.get('urun_adi') or '—'}")
    st.caption(f"Marka: **{urun.get('marka') or '—'}**  ·  Kategori: **{urun.get('kategori') or '—'}**  "
               f"·  Barkod: **{urun.get('barkod') or '—'}**")

    t1, t2, t3, t4, t5 = st.tabs(["📊 Özet", "📥 Alımlar", "📤 Satışlar", "🎯 Kampanya", "📈 Analiz"])

    # ═══ ÖZET ═══
    with t1:
        _yeter = (f"~{toplam_stok / haftalik_gercek:.0f} hafta yeter"
                  if haftalik_gercek > 0 else "satış verisi yok")
        _kart_satiri([
            _kart("Toplam Stok", f"{toplam_stok:,.0f}", _yeter, "#34D399"),
            _kart("Stok Değeri", _usd(stok_degeri), "paçal × stok", "#38BDF8"),
            _kart("Paçal Maliyet", _usd(pacal_final), "adet-ağırlıklı", "#F87171"),
            _kart("Liste Satış", _usd(liste_fiyat), "güncel", "#A5B4FC"),
        ])
        # Yolda detay
        if yolda_adet > 0:
            _yd = []
            for r in yolda_rows:
                _m = _f(r.get("yoldaki_miktar"))
                if _m <= 0:
                    continue
                _yd.append(f"{_m:,.0f} adet — {r.get('yoldaki_tedarikci') or '—'} "
                           f"(varış {gun_ay_yil(r.get('tahmini_varis_tarihi')) or '—'})")
            st.info("🚚 **Yolda:** " + " · ".join(_yd))
        if firma_stok:
            st.markdown("**Firma / Depo Stok Kırılımı**")
            st.dataframe(pd.DataFrame([{
                "Firma/Depo": r.get("firma", ""),
                "Stok": _f(r.get("stok_miktari")),
                "Haftalık Satış": _f(r.get("haftalik_satis")),
                "Güncellenme": gun_ay_yil(r.get("yukleme_tarihi")),
            } for r in firma_stok]), hide_index=True, use_container_width=True)
        else:
            st.info("Bu SKU için firma/depo stok kaydı yok.")
        st.caption(f"İlk görülme: {gun_ay_yil(ilk_gorulen) or '—'}  ·  "
                   f"Son alım: {gun_ay_yil(son_tarih) or '—'}")

    # ═══ ALIMLAR ═══
    with t2:
        if alimlar:
            _kart_satiri([
                _kart("Toplam Alınan", f"{_adet_t:,.0f}", f"{len(alimlar)} parti", "#34D399"),
                _kart("Son Alım FOB", _usd(son_fob), gun_ay_yil(son_tarih), "#FBBF24"),
                _kart("Paçal (Final)", _usd(pacal_final), "tüm partiler", "#F87171"),
            ])
            # Maliyet trendi
            if len(alimlar) >= 2:
                _onceki = [_f(a["final_birim"]) for a in alimlar[1:] if _f(a["final_birim"]) > 0]
                _oort = (sum(_onceki) / len(_onceki)) if _onceki else 0.0
                if _oort > 0 and son_final > 0:
                    if son_final > _oort * 1.02:
                        st.warning(f"📈 Maliyet **artıyor**: son alım {_usd(son_final)} vs önceki ort. {_usd(_oort)}")
                    elif son_final < _oort * 0.98:
                        st.success(f"📉 Maliyet **düşüyor**: son alım {_usd(son_final)} vs önceki ort. {_usd(_oort)}")
            _df = pd.DataFrame([{
                "Tarih": gun_ay_yil(a["tarih"]), "Belge": a["belge_no"],
                "Tedarikçi": a["tedarikci"], "Ülke": a["ulke"], "Döviz": a["doviz"],
                "Adet": _f(a["adet"]), "Birim FOB": round(_f(a["birim_fob"]), 2),
                "% Maliyet": round(_f(a["maliyet_yuzde"]), 1),
                "Final Birim": round(_f(a["final_birim"]), 2),
            } for a in alimlar])
            _ev = st.dataframe(_df, hide_index=True, use_container_width=True,
                               on_select="rerun", selection_mode="single-row", key="alim_tablo")
            st.caption("👆 Detayını görmek için bir satıra tıkla.")
            if _ev.selection.rows:
                _alim_detay(alimlar[_ev.selection.rows[0]])
        else:
            st.info("Bu SKU için ithalat alım kaydı bulunamadı.")

    # ═══ SATIŞLAR ═══
    with t3:
        if satislar and satir_kar:
            _ta = _tc = _tk = 0.0
            _kanal, _rows = {}, []
            for s in satislar:
                k = satir_kar(s)
                _ta += _f(k.get("adet")); _tc += _f(k.get("ciro")); _tk += _f(k.get("net_kar"))
                kn = s.get("kanal", "") or "—"
                kc = _kanal.setdefault(kn, {"adet": 0.0, "ciro": 0.0, "kar": 0.0})
                kc["adet"] += _f(k.get("adet")); kc["ciro"] += _f(k.get("ciro")); kc["kar"] += _f(k.get("net_kar"))
                _rows.append({
                    "Tarih": gun_ay_yil(s.get("tarih")), "Kanal/Firma": kn,
                    "Sipariş No": s.get("siparis_no", "") or "—", "Adet": _f(k.get("adet")),
                    "B.Satış": round(_f(s.get("birim_satis")), 2),
                    "Net Kâr": round(_f(k.get("net_kar")), 2),
                    "Marj": f"%{_f(k.get('marj')):.1f}",
                })
            _om = (_tk / _tc * 100) if _tc else 0.0
            _kart_satiri([
                _kart("Toplam Satılan", f"{_ta:,.0f}", f"{len(satislar)} kalem", "#34D399"),
                _kart("Toplam Ciro", _usd(_tc), "", "#A5B4FC"),
                _kart("Toplam Kâr", _usd(_tk), f"ort. marj %{_om:.1f}",
                      "#34D399" if _tk >= 0 else "#F87171"),
            ])
            st.markdown("**Kanal / Firma Kırılımı**")
            st.dataframe(pd.DataFrame([{
                "Kanal/Firma": kn, "Adet": v["adet"], "Ciro": _usd(v["ciro"]), "Kâr": _usd(v["kar"]),
            } for kn, v in sorted(_kanal.items(), key=lambda x: -x[1]["ciro"])]),
                hide_index=True, use_container_width=True)
            st.markdown("**Satış Hareketleri**")
            _sev = st.dataframe(pd.DataFrame(_rows), hide_index=True, use_container_width=True,
                                on_select="rerun", selection_mode="single-row", key="satis_tablo")
            st.caption("👆 Detayını görmek için bir satıra tıkla.")
            if _sev.selection.rows:
                _satis_detay(satislar[_sev.selection.rows[0]], satir_kar)
        else:
            st.info("Bu SKU için satış kaydı bulunamadı.")

    # ═══ KAMPANYA ═══
    with t4:
        if kampanya_urun:
            _kids = [k.get("kampanya_id") for k in kampanya_urun if k.get("kampanya_id")]
            _kamp_map = {}
            try:
                if _kids:
                    _kr = sb.table("kampanyalar").select("*").in_("id", _kids).execute().data or []
                    _kamp_map = {k["id"]: k for k in _kr}
            except Exception:
                pass
            _rows = []
            for ku in kampanya_urun:
                _k = _kamp_map.get(ku.get("kampanya_id"), {})
                _rows.append({
                    "Kampanya": _k.get("kampanya_adi", "") or f"#{ku.get('kampanya_id')}",
                    "Firma": _k.get("firma", "") or "—",
                    "Tür": _k.get("kampanya_turu", "") or "—",
                    "Başlangıç": gun_ay_yil(_k.get("baslangic_tarihi")),
                    "Bitiş": gun_ay_yil(_k.get("bitis_tarihi")),
                    "Firma Destek": _usd(ku.get("birim_firma_destek")),
                    "Ek Destek": _usd(ku.get("birim_ek_destek")),
                })
            st.dataframe(pd.DataFrame(_rows), hide_index=True, use_container_width=True)
            st.caption(f"Bu SKU {len(kampanya_urun)} kampanyada yer almış.")
        else:
            st.info("Bu SKU hiç kampanyada yer almamış.")

    # ═══ ANALİZ ═══
    with t5:
        # Marj sağlığı
        if pacal_final > 0 and liste_fiyat > 0:
            _marj = (liste_fiyat - pacal_final) / liste_fiyat * 100
            if liste_fiyat <= pacal_final:
                st.error(f"⚠️ **Zarar riski:** Liste satış ({_usd(liste_fiyat)}) ≤ paçal maliyet ({_usd(pacal_final)}).")
            elif _marj < 10:
                st.warning(f"⚠️ **Düşük marj:** Teorik marj sadece %{_marj:.1f}.")
            else:
                st.success(f"✅ **Sağlıklı marj:** Teorik marj %{_marj:.1f}.")

        # Gerçek satış hızı + reorder + DIO
        if gunluk_hiz > 0:
            _tukenme = toplam_stok / gunluk_hiz
            _reorder = gunluk_hiz * uretim_suresi
            _kart_satiri([
                _kart("Günlük Hız", f"{gunluk_hiz:.1f}", "son 90 gün", "#A5B4FC"),
                _kart("Tükenme", f"~{_tukenme:.0f} gün", "mevcut hızda", "#FBBF24"),
                _kart("Stok Devir (DIO)", f"{_tukenme:.0f} gün", "elde kalma", "#38BDF8"),
            ])
            st.markdown(
                f"📦 **Yeniden sipariş noktası:** Üretim/tedarik süresi {uretim_suresi} gün. "
                f"Stok **{_reorder:,.0f} adet**'e inince sipariş ver "
                f"(şu an {toplam_stok:,.0f}, yolda {yolda_adet:,.0f})."
            )
            if toplam_stok + yolda_adet <= _reorder:
                st.warning("🔴 **Sipariş zamanı:** Stok + yoldaki, yeniden sipariş noktasının altında.")
        elif toplam_stok > 0:
            st.info("ℹ️ Son 90 günde satış yok — hız/tükenme hesaplanamıyor.")
            if not satislar:
                st.warning("🪦 **Hareketsiz stok:** Stok var ama satış geçmişi yok. Ölü stok olabilir.")

        # Kâr katkısı / ABC
        _oz = _tum_satis_ozeti()
        _bk = _oz["sku_kar"].get(sku, 0.0)
        _bc = _oz["sku_ciro"].get(sku, 0.0)
        if _oz["toplam_ciro"]:
            _cp = _bc / _oz["toplam_ciro"] * 100
            _kp = (_bk / _oz["toplam_kar"] * 100) if _oz["toplam_kar"] else 0.0
            _abc = "A" if _cp >= 5 else ("B" if _cp >= 1 else "C")
            _renk = {"A": "#34D399", "B": "#FBBF24", "C": "#94A3B8"}[_abc]
            st.markdown(
                f"<div style='margin:8px 0'>🏷️ <b style='color:{_renk}'>ABC Sınıfı: {_abc}</b> — "
                f"Toplam cironun %{_cp:.1f}'i, toplam kârın %{_kp:.1f}'i bu üründen.</div>",
                unsafe_allow_html=True)

        # En kârlı kanal
        if satislar and satir_kar:
            _k2 = {}
            for s in satislar:
                _k2.setdefault(s.get("kanal", "") or "—", [0.0])[0] += _f(satir_kar(s).get("net_kar"))
            if _k2:
                _en = max(_k2.items(), key=lambda x: x[1][0])
                st.info(f"🏆 **En kârlı kanal:** {_en[0]} ({_usd(_en[1][0])} toplam kâr).")

        # Tedarikçi karşılaştırması
        if len(alimlar) > 1:
            _ted = {}
            for a in alimlar:
                t = a["tedarikci"] or "—"
                tt = _ted.setdefault(t, {"fob_x": 0.0, "adet": 0.0})
                tt["fob_x"] += _f(a["birim_fob"]) * _f(a["adet"]); tt["adet"] += _f(a["adet"])
            if len(_ted) > 1:
                st.markdown("**Tedarikçi Karşılaştırması (ort. birim FOB)**")
                st.dataframe(pd.DataFrame([{
                    "Tedarikçi": t, "Toplam Adet": v["adet"],
                    "Ort. Birim FOB": round(v["fob_x"] / v["adet"], 2) if v["adet"] else 0,
                } for t, v in sorted(_ted.items(), key=lambda x: (x[1]["fob_x"] / x[1]["adet"]) if x[1]["adet"] else 0)]),
                    hide_index=True, use_container_width=True)

    st.divider()
    if st.button("Kapat", use_container_width=True):
        st.rerun()
