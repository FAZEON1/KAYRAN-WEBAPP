# -*- coding: utf-8 -*-
"""SKU Stok Kartı — ortada açılan modal pencere.
Sekmeler: 📊 Özet · 📥 Alımlar · 📤 Satışlar · 🎯 Kampanya · 📈 Analiz
Veriyi ürün/stok (kayranpm), ithalat ve satış modüllerinden birleştirir.
Performans: satışlar SKU bazlı çekilir, paçal alım partilerinden hesaplanır."""
import streamlit as st
import pandas as pd
from datetime import timedelta

try:
    from shared.utils import gun_ay_yil, tr_today, firma_gorunen_ad
except Exception:
    def firma_gorunen_ad(k):
        return str(k or "")
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
        f'<div style="flex:1;min-width:150px;background:linear-gradient(180deg,#152036,#0F172A);'
        f'border:1px solid rgba(255,255,255,0.08);border-left:3px solid {renk};'
        f'border-radius:10px;padding:12px 16px">'
        f'<div style="color:#94A3B8;font-size:11px;text-transform:uppercase;letter-spacing:.4px">{baslik}</div>'
        f'<div style="color:{renk};font-size:19px;font-weight:700;margin-top:0px">{deger}</div>'
        f'<div style="color:#64748B;font-size:11px;margin-top:0px">{alt}</div></div>'
    )


def _kart_satiri(kartlar):
    st.markdown('<div style="display:flex;gap:12px;flex-wrap:wrap;margin:6px 0 14px">'
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

    from kayranpm.database import get_client, get_urun_detay, get_uretim_suresi, canli_stok
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
    if not satislar:
        # Satış kaydı SKU'su farklı yazımda olabilir (büyük/küçük harf ya da 'Fazeon ' öneki).
        # → esnek ara, normalize ile kesin doğrula (yanlış eşleşmeyi eler).
        try:
            from kayranpm.excel_islemler import normalize_sku as _nsku
            _skn = _nsku(sku)
            _cand = (sb.table("satislar").select("*").ilike("sku", f"%{sku}")
                     .order("tarih", desc=True).execute().data or [])
            satislar = [r for r in _cand if _nsku(r.get("sku", "")) == _skn]
        except Exception:
            pass
    kampanya_urun = _sel("kampanya_urunler")

    # İadeler — SKU bazlı (satışlardaki esnek eşleşme kalıbıyla)
    iadeler = _sel("iadeler", order="tarih", desc=True)
    if not iadeler:
        try:
            from kayranpm.excel_islemler import normalize_sku as _nsku2
            _skn2 = _nsku2(sku)
            _cand2 = (sb.table("iadeler").select("*").ilike("sku", f"%{sku}")
                      .order("tarih", desc=True).execute().data or [])
            iadeler = [r for r in _cand2 if _nsku2(r.get("sku", "")) == _skn2]
        except Exception:
            pass

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
    # Canlı (perpetual) stok: başlangıç snapshot + teslim alınan ithalat − satışlar
    _cs = canli_stok(sku)
    # G5F bizim depo (kullanıcının yüklediği fiziksel depo sayımı) — depo kırılımı
    _depo_kirilim = urun.get("depo_kirilim") if isinstance(urun.get("depo_kirilim"), dict) else {}
    _g5f_toplam = sum(_f(v) for v in _depo_kirilim.values())
    _g5f_satilabilir = _f(urun.get("bizim_stok"))
    _firma_toplam = sum(_f(r.get("stok_miktari")) for r in firma_stok)
    if _cs.get("var"):
        toplam_stok = _cs["canli"]
    elif _g5f_toplam > 0:
        toplam_stok = _g5f_toplam
    else:
        toplam_stok = _firma_toplam
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

    # ── Başka bir SKU / modele geç (modal içi arama — hep görünür) ──
    _q = st.text_input("Ara", key=f"stok_ara_{sku}",
                       placeholder="🔍 Başka bir SKU / model ara ve aç…",
                       label_visibility="collapsed")
    if _q and len(_q.strip()) >= 2:
        try:
            from kayranpm.database import get_tum_sku_listesi
            from shared.utils import normalize_tr
            _qn = normalize_tr(_q)
            _tum = get_tum_sku_listesi() or []
            _bulunan = [r for r in _tum
                        if str(r.get("sku") or "") != sku and (
                            _qn in normalize_tr(r.get("sku") or "") or
                            _qn in normalize_tr(r.get("urun_adi") or ""))][:8]
        except Exception:
            _bulunan = []
        if _bulunan:
            for r in _bulunan:
                _ad = (r.get("urun_adi") or "")[:55]
                _lbl = f"{r['sku']} — {_ad}" if _ad else r["sku"]
                if st.button(_lbl, key=f"gec_{r['sku']}", use_container_width=True):
                    st.session_state["_stok_gec_sku"] = r["sku"]
                    st.rerun()
        else:
            st.caption("Eşleşen ürün bulunamadı.")

    t1, t2, t3, t4, t5, t6 = st.tabs(["📊 Özet", "📥 Alımlar", "📤 Satışlar", "🎯 Kampanya", "📈 Analiz", "↩️ İade"])

    # ═══ ÖZET ═══
    with t1:
        from shared.ui import RENK, pencere_css, pencere, pencere_grid, bos_durum
        st.markdown(pencere_css(), unsafe_allow_html=True)
        _yeter = (f"~{toplam_stok / haftalik_gercek:.0f} hafta yeter"
                  if haftalik_gercek > 0 else "satış verisi yok")

        # Panel verileri
        _dagilim_dolu = {d: _f(m) for d, m in (_depo_kirilim or {}).items() if _f(m) != 0}
        _firma_son = {}
        for r in firma_stok:
            _fa = firma_gorunen_ad(r.get("firma", "")) or "—"
            _ft = str(r.get("yukleme_tarihi") or "")[:10]
            if (_fa not in _firma_son) or (_ft > _firma_son[_fa][0]):
                _firma_son[_fa] = (_ft, _f(r.get("stok_miktari")), _f(r.get("haftalik_satis")))
        _musteri_toplam = sum(v[1] for v in _firma_son.values())

        _kart1 = (_kart("Bizim Stok", f"{_g5f_toplam:,.0f}",
                        f"{_g5f_satilabilir:,.0f} satılabilir", "#34D399")
                  if _g5f_toplam > 0 else
                  _kart("Canlı Stok", f"{toplam_stok:,.0f}", _yeter, "#34D399"))
        _kart_satiri([
            _kart1,
            _kart("Stok Değeri", _usd(stok_degeri), "paçal × canlı stok", "#38BDF8"),
            _kart("Paçal Maliyet", _usd(pacal_final), "adet-ağırlıklı", "#F87171"),
            _kart("Liste Satış", _usd(liste_fiyat), "güncel", "#A5B4FC"),
        ])

        # ── İKİZ STOK PANELİ — solda bizim depolar, sağda müşteriler ──
        def _srow(ad, adet, maks, renk, alt=""):
            _w = max(2.0, min(100.0, (adet / maks * 100) if maks else 0))
            _alt = (f'<div style="color:{RENK["silik"]};font-size:11px;margin-top:0px">{alt}</div>'
                    if alt else "")
            return (f'<div style="padding:4px 12px;margin:3px 0;border-radius:6px;'
                    f'background:linear-gradient(180deg,#152036,#0F172A)">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">'
                    f'<span style="color:{RENK["metin"]};font-size:13px;font-weight:600">{ad}</span>'
                    f'<span style="color:{RENK["metin"]};font-size:13px;font-weight:700;'
                    f'font-family:JetBrains Mono,monospace">{adet:,.0f}</span></div>'
                    f'<div style="height:4px;border-radius:2px;background:rgba(255,255,255,0.05)">'
                    f'<div style="height:4px;border-radius:2px;width:{_w:.1f}%;background:{renk}"></div></div>'
                    f'{_alt}</div>')

        def _satilabilir_mi(depo):
            _du = str(depo).upper().replace("İ", "I")
            return ("MERKEZ" in _du) or ("HAPPY" in _du)

        if _dagilim_dolu:
            _dmax = max(_dagilim_dolu.values())
            _depo_html = "".join(
                _srow(str(d).upper(), m, _dmax,
                      RENK["yesil"] if _satilabilir_mi(d) else RENK["soluk"],
                      alt=("satılabilir" if _satilabilir_mi(d) else "fiziksel takip"))
                for d, m in sorted(_dagilim_dolu.items(), key=lambda x: -x[1]))
        else:
            _depo_html = bos_durum("G5F depo sayımı yüklenmemiş — Ürün Yönetimi → Veri Yükleme")
        _p_depo = pencere("🏬 BİZİM DEPOLAR", RENK["yesil"], _depo_html,
                          rozet=(f"{_g5f_toplam:,.0f} adet" if _g5f_toplam else ""), yukseklik=200)

        if _firma_son:
            _mmax = max(v[1] for v in _firma_son.values()) or 1
            _mus_html = "".join(
                _srow(fa, v[1], _mmax, RENK["mor"],
                      alt=f"haftalık satış {v[2]:,.0f} · {gun_ay_yil(v[0]) or v[0] or '—'}")
                for fa, v in sorted(_firma_son.items(), key=lambda x: -x[1][1]))
        else:
            _mus_html = bos_durum("Müşterilerde stok kaydı yok")
        _p_mus = pencere("🛍️ MÜŞTERİ STOĞU", RENK["mor"], _mus_html,
                         rozet=(f"{_musteri_toplam:,.0f} adet" if _musteri_toplam else ""), yukseklik=200)

        st.markdown(pencere_grid(_p_depo, _p_mus, alt_bosluk=2), unsafe_allow_html=True)

        # Genel toplam şeridi
        _genel = _g5f_toplam + _musteri_toplam
        _serit = (f'<span style="color:{RENK["metin"]};font-weight:800">GENEL TOPLAM '
                  f'<span style="font-family:JetBrains Mono,monospace">{_genel:,.0f}</span></span>'
                  f'<span style="color:{RENK["silik"]}"> = bizim {_g5f_toplam:,.0f} + müşteri {_musteri_toplam:,.0f}</span>')
        if _cs.get("var"):
            _serit += (f'<span style="color:{RENK["silik"]}"> · canlı hesap </span>'
                       f'<span style="color:{RENK["yesil"]};font-family:JetBrains Mono,monospace;'
                       f'font-weight:700">{_cs["canli"]:,.0f}</span>')
        if haftalik_gercek > 0:
            _serit += f'<span style="color:{RENK["silik"]}"> · {_yeter}</span>'
        if yolda_adet > 0:
            _serit += (f'<span style="color:{RENK["mavi"]}"> · 🚚 yolda '
                       f'<b style="font-family:JetBrains Mono,monospace">{yolda_adet:,.0f}</b></span>')
        st.markdown(
            f'<div style="background:linear-gradient(180deg,#152036,#0F172A);border:1px solid rgba(255,255,255,0.07);'
            f'border-radius:10px;padding:8px 16px;margin:0 0 10px;font-size:13px">{_serit}</div>',
            unsafe_allow_html=True)
        if not _dagilim_dolu and not _cs.get("var") and _g5f_toplam <= 0:
            st.warning("⚠️ Başlangıç stoğu (Excel) yüklenmemiş — canlı stok için bir kez mevcut stoğu yükle. "
                       "Şimdilik gösterilen değer ham snapshot.")
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
                "Kanal/Firma": kn, "Adet": v["adet"],
                "Ort. Birim": _usd(v["ciro"] / v["adet"]) if v["adet"] else _usd(0),
                "Ciro": _usd(v["ciro"]), "Kâr": _usd(v["kar"]),
                "Marj": f"%{(v['kar'] / v['ciro'] * 100) if v['ciro'] else 0:.1f}",
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

    with t6:
        if not iadeler:
            st.info("Bu ürün için iade kaydı yok.")
        else:
            _ia = sum(_f(r.get("iade_adet")) for r in iadeler)
            _it = sum(_f(r.get("iade_net")) for r in iadeler)
            _kart_satiri([
                _kart("Toplam İade", f"{_ia:,.0f}", f"{len(iadeler)} kalem · stoğa döndü", "#FBBF24"),
                _kart("İade Tutarı", _usd(_it), "müşteriye iade", "#FB923C"),
                _kart("Tekrar Satılabilir", f"{_ia:,.0f} adet", "stoğa eklendi", "#34D399"),
            ])
            _fk = {}
            for r in iadeler:
                f = (r.get("kanal") or "").strip() or "(cari belirsiz)"
                o = _fk.setdefault(f, {"adet": 0.0, "tutar": 0.0})
                o["adet"] += _f(r.get("iade_adet")); o["tutar"] += _f(r.get("iade_net"))
            if len(_fk) > 1:
                st.markdown("**Cari / Firma Kırılımı**")
                st.dataframe(pd.DataFrame([{
                    "Cari / Firma": (f or "")[:40], "İade Adet": v["adet"], "İade Tutarı": _usd(v["tutar"]),
                } for f, v in sorted(_fk.items(), key=lambda x: -x[1]["adet"])]),
                    hide_index=True, use_container_width=True)
            st.markdown("**İade Detayı**")
            st.dataframe(pd.DataFrame([{
                "Tarih": gun_ay_yil(r.get("tarih")), "Cari / Firma": (r.get("kanal") or "—")[:40],
                "Adet": _f(r.get("iade_adet")), "İade Tutarı": _usd(_f(r.get("iade_net"))),
            } for r in iadeler]), hide_index=True, use_container_width=True)
            st.caption("↩️ İade edilen mal stoğa döner ve tekrar satılabilir; kâr/marj brüt satıştan "
                       "hesaplanır, iade kârdan düşülmez.")

    st.divider()
    if st.button("Kapat", use_container_width=True):
        st.rerun()
