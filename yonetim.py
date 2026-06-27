"""
KAYRAN — Yönetim Panosu (P&L)
Dönemsel kâr/zarar: Ciro − COGS − Destekler = Net Kâr.
 • Gelir/maliyet → Satış modülünden (ciro, paçal COGS).
 • Destekler → Havuz bütçe / ref no harcamalarından, türlere göre kırılımlı.
Tüm tutarlar USD. TL cinsi destekler güncel kurla yaklaşık çevrilir.
"""
import streamlit as st
import datetime as dt


def _usd(x):
    try:
        return f"${float(x):,.0f}"
    except Exception:
        return "$0"


def _pct(x):
    try:
        return f"%{float(x):.1f}"
    except Exception:
        return "%0.0"


def _donem_tarih(yil, donem):
    if donem == "Q1":
        return f"{yil}-01-01", f"{yil}-03-31"
    if donem == "Q2":
        return f"{yil}-04-01", f"{yil}-06-30"
    if donem == "Q3":
        return f"{yil}-07-01", f"{yil}-09-30"
    if donem == "Q4":
        return f"{yil}-10-01", f"{yil}-12-31"
    return f"{yil}-01-01", f"{yil}-12-31"


def _kart(baslik, deger, alt, renk):
    return (f'<div style="background:rgba(255,255,255,0.03);border:1px solid {renk}33;border-radius:14px;'
            f'padding:16px 18px;flex:1;min-width:148px">'
            f'<div style="font-size:11px;color:#94A3B8;letter-spacing:1px;text-transform:uppercase;font-weight:700;margin-bottom:8px">{baslik}</div>'
            f'<div style="color:#FFFFFF;font-size:23px;font-weight:800;font-family:JetBrains Mono,monospace;line-height:1">{deger}</div>'
            f'<div style="color:{renk};font-size:12px;font-weight:600;margin-top:6px">{alt}</div></div>')


def run():
    st.markdown("## 📊 Yönetim Panosu — Kâr / Zarar")
    st.caption("Ciro − COGS − Destekler = Net Kâr · destekler havuz/ref no harcamalarından (türlere göre)")

    _bugun = dt.date.today()
    c1, c2 = st.columns([1, 3])
    with c1:
        _yil = st.selectbox("Yıl", list(range(_bugun.year + 1, _bugun.year - 4, -1)), index=1)
    with c2:
        _donem = st.radio("Dönem", ["Q1", "Q2", "Q3", "Q4", "Tüm Yıl"], horizontal=True, index=4)
    baslangic, bitis = _donem_tarih(_yil, _donem)
    st.caption(f"📅 Seçili dönem: **{baslangic} → {bitis}**")

    # ── Gelir / maliyet (satış) ──
    ciro = cogs = 0.0
    kanal = {}
    try:
        from satis.database import get_satislar, ozet_hesapla
        _satislar = get_satislar(baslangic, bitis)
        top, kanal, _urun = ozet_hesapla(_satislar)
        ciro = float(top.get("ciro", 0.0) or 0.0)
        cogs = float(top.get("maliyet", 0.0) or 0.0)
    except Exception as e:
        st.warning(f"Satış verisi okunamadı: {e}")
    brut = ciro - cogs
    brut_marj = (brut / ciro * 100) if ciro else 0.0

    # ── Destekler (havuz/ref no harcamaları) ──
    _harcama = []
    try:
        from kayranpm.ref_no import get_tum_butce_harcamalari
        _harcama = get_tum_butce_harcamalari(baslangic, bitis)
    except Exception:
        _harcama = []
    _usdtry = 0.0
    try:
        from gunluk import get_doviz
        _usdtry = float(get_doviz().get("USD") or 0)
    except Exception:
        _usdtry = 0.0

    _tur_usd = {}
    _tl_uyari = False
    _kur_eksik = False
    toplam_destek = 0.0
    for h in _harcama:
        t = (h.get("tur") or "Diğer").strip() or "Diğer"
        tutar = float(h.get("tutar") or 0)
        dv = (h.get("doviz") or "USD").strip().upper()
        if dv in ("TL", "TRY", "₺", "TRL"):
            if _usdtry:
                tutar = tutar / _usdtry
                _tl_uyari = True
            else:
                _kur_eksik = True
                continue
        _tur_usd[t] = _tur_usd.get(t, 0.0) + tutar
        toplam_destek += tutar

    net_kar = brut - toplam_destek
    net_marj = (net_kar / ciro * 100) if ciro else 0.0

    # ── P&L kartları ──
    _nrenk = "#34D399" if net_kar >= 0 else "#F87171"
    st.markdown(
        '<div style="display:flex;gap:12px;flex-wrap:wrap;margin:10px 0 18px">'
        + _kart("Ciro", _usd(ciro), "Toplam satış", "#A5B4FC")
        + _kart("COGS", _usd(cogs), "Ürün maliyeti", "#FBBF24")
        + _kart("Brüt Kâr", _usd(brut), f"Brüt marj {_pct(brut_marj)}", "#38BDF8")
        + _kart("Destekler", _usd(toplam_destek), "Toplam destek/harcama", "#FB7185")
        + _kart("Net Kâr", _usd(net_kar), f"Net marj {_pct(net_marj)}", _nrenk)
        + '</div>', unsafe_allow_html=True)
    if _tl_uyari and _usdtry:
        st.caption(f"ℹ️ TL cinsi destekler güncel kurla (1$={_usdtry:.2f}₺) USD'ye çevrildi (yaklaşık).")
    if _kur_eksik:
        st.warning("⚠️ Güncel kur alınamadığı için TL cinsi destekler hesaba katılamadı.")

    # ── Net kâr açıklama satırı (P&L akışı) ──
    st.markdown(
        f'<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.08);'
        f'border-radius:12px;padding:12px 16px;margin-bottom:20px;font-family:JetBrains Mono,monospace;font-size:13px;color:#CBD5E1">'
        f'{_usd(ciro)} <span style="color:#64748B">ciro</span> &nbsp;−&nbsp; {_usd(cogs)} <span style="color:#64748B">cogs</span> '
        f'&nbsp;−&nbsp; {_usd(toplam_destek)} <span style="color:#64748B">destek</span> &nbsp;=&nbsp; '
        f'<b style="color:{_nrenk}">{_usd(net_kar)} net kâr</b> &nbsp;·&nbsp; <span style="color:{_nrenk}">{_pct(net_marj)} marj</span>'
        f'</div>', unsafe_allow_html=True)

    # ── Destek / harcama kırılımı (tür bazlı) ──
    st.markdown("#### 🎯 Destek / harcama kırılımı (tür bazlı)")
    if not _tur_usd:
        st.info("Bu dönemde havuz/ref no harcaması (destek) kaydı bulunamadı.")
    else:
        import pandas as pd
        _rows_t = []
        for t, v in sorted(_tur_usd.items(), key=lambda x: -x[1]):
            _rows_t.append({
                "Kategori": t,
                "Tutar (USD)": f"${v:,.0f}",
                "Ciroya oran": (f"%{(v / ciro * 100):.1f}" if ciro else "—"),
                "Toplam destekte pay": (f"%{(v / toplam_destek * 100):.1f}" if toplam_destek else "—"),
            })
        _rows_t.append({
            "Kategori": "▸ TOPLAM",
            "Tutar (USD)": f"${toplam_destek:,.0f}",
            "Ciroya oran": (f"%{(toplam_destek / ciro * 100):.1f}" if ciro else "—"),
            "Toplam destekte pay": "%100",
        })
        st.dataframe(pd.DataFrame(_rows_t), hide_index=True, use_container_width=True)

    # ── Kanal bazında satış ──
    if kanal:
        st.markdown("#### 🛒 Kanal bazında satış")
        import pandas as pd
        _rk = []
        for kn, v in sorted(kanal.items(), key=lambda x: -x[1].get("ciro", 0)):
            _rk.append({
                "Kanal": kn,
                "Ciro": _usd(v.get("ciro", 0)),
                "Adet": int(v.get("adet", 0)),
                "Satış Net Kâr": _usd(v.get("net_kar", 0)),
            })
        st.dataframe(pd.DataFrame(_rk), hide_index=True, use_container_width=True)
        st.caption("Not: 'Satış Net Kâr' satış-içi birim destekleri yansıtır (operasyonel); "
                   "resmi dönem net kârı için üstteki havuz/ref no destekleri esastır.")
