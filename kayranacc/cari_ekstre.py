# -*- coding: utf-8 -*-
"""Cari Ekstre & Vade Yaşlandırma — ödenecekler (tedarikçi/gider) tarafı.
'odemeler' tablosundan beslenir. Müşteri alacağı (satış tahsilatı) AYRI bir konudur,
o veri henüz tutulmadığı için burada yer almaz."""
import streamlit as st
import pandas as pd
from datetime import datetime

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
        return float(v)
    except Exception:
        return d


def _parse(d):
    s = str(d or "")[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _tl(v):
    return f"₺{_f(v):,.0f}"


def _usd(v):
    return f"${_f(v):,.2f}"


KOVALAR = ["Vadesi gelmemiş", "0-30 gün", "31-60 gün", "61-90 gün", "90+ gün"]


def render():
    st.markdown("## 🧾 Cari Ekstre & Vade Yaşlandırma")
    st.caption("Ödenecekler (tedarikçi/gider) tarafı — ödeme kayıtlarından üretilir. "
               "Müşteri alacağı için satışlara tahsilat takibi gerekir (henüz yok).")

    from kayranacc.database import get_tum_odemeler
    odemeler = get_tum_odemeler()
    if not odemeler:
        st.info("Henüz ödeme kaydı yok.")
        return

    bugun = tr_today()
    t1, t2 = st.tabs(["📋 Cari Ekstre", "⏳ Vade Yaşlandırma"])

    # ═══ CARİ EKSTRE ═══
    with t1:
        firmalar = sorted({(o.get("firma") or "—") for o in odemeler}, key=lambda s: s.lower())
        secili = st.selectbox("Cari (firma) seç", firmalar, key="ekstre_firma")
        kayitlar = [o for o in odemeler if (o.get("firma") or "—") == secili]
        kayitlar.sort(key=lambda o: str(o.get("vade") or ""))

        acik_tl = sum(_f(o.get("tutar_tl")) for o in kayitlar if o.get("durum") != "odendi")
        acik_usd = sum(_f(o.get("tutar_usd")) for o in kayitlar if o.get("durum") != "odendi")
        odenen_tl = sum(_f(o.get("tutar_tl")) for o in kayitlar if o.get("durum") == "odendi")
        odenen_usd = sum(_f(o.get("tutar_usd")) for o in kayitlar if o.get("durum") == "odendi")

        c1, c2, c3 = st.columns(3)
        c1.metric("Açık Borç (TL)", _tl(acik_tl))
        c2.metric("Açık Borç (USD)", _usd(acik_usd))
        c3.metric("Ödenmiş (TL)", _tl(odenen_tl), help=f"USD: {_usd(odenen_usd)}")

        # Gecikmiş açık kalem var mı?
        _gecikmis = [o for o in kayitlar if o.get("durum") != "odendi"
                     and _parse(o.get("vade")) and (bugun - _parse(o.get("vade"))).days > 0]
        if _gecikmis:
            _gt = sum(_f(o.get("tutar_tl")) for o in _gecikmis)
            st.warning(f"🔴 {len(_gecikmis)} kalemin vadesi geçmiş — toplam {_tl(_gt)} "
                       f"(+ USD kalemler varsa ayrı).")

        df = pd.DataFrame([{
            "Vade": gun_ay_yil(o.get("vade")),
            "Açıklama": o.get("aciklama", "") or "—",
            "Kategori": o.get("kategori", "") or "—",
            "Tutar (TL)": round(_f(o.get("tutar_tl")), 2),
            "Tutar (USD)": round(_f(o.get("tutar_usd")), 2),
            "Durum": "✅ Ödendi" if o.get("durum") == "odendi" else "⏳ Bekliyor",
        } for o in kayitlar])
        st.dataframe(df, hide_index=True, use_container_width=True)
        st.caption(f"{len(kayitlar)} kayıt · {secili}")

    # ═══ VADE YAŞLANDIRMA ═══
    with t2:
        pb = st.radio("Para birimi", ["TL", "USD"], horizontal=True, key="yas_pb")
        alan = "tutar_tl" if pb == "TL" else "tutar_usd"
        _fmt = _tl if pb == "TL" else _usd

        acik = [o for o in odemeler if o.get("durum") != "odendi"]
        if not acik:
            st.success("✅ Açık (bekleyen) ödeme yok.")
            return

        def _kova(vade):
            d = _parse(vade)
            if not d:
                return "Vadesi gelmemiş"
            g = (bugun - d).days
            if g < 0:
                return "Vadesi gelmemiş"
            if g <= 30:
                return "0-30 gün"
            if g <= 60:
                return "31-60 gün"
            if g <= 90:
                return "61-90 gün"
            return "90+ gün"

        firma_kova = {}
        for o in acik:
            tutar = _f(o.get(alan))
            if tutar == 0:
                continue
            f = o.get("firma") or "—"
            k = _kova(o.get("vade"))
            firma_kova.setdefault(f, {kk: 0.0 for kk in KOVALAR})
            firma_kova[f][k] += tutar

        if not firma_kova:
            st.info(f"{pb} cinsinden açık ödeme yok.")
            return

        # Üst kartlar: kova toplamları
        kova_top = {kk: sum(kv[kk] for kv in firma_kova.values()) for kk in KOVALAR}
        cols = st.columns(len(KOVALAR))
        for col, kk in zip(cols, KOVALAR):
            col.metric(kk, _fmt(kova_top[kk]))

        _gecikmis_top = sum(kova_top[kk] for kk in ["0-30 gün", "31-60 gün", "61-90 gün", "90+ gün"])
        if _gecikmis_top > 0:
            st.warning(f"🔴 Vadesi geçmiş toplam açık borç: {_fmt(_gecikmis_top)}")

        # Firma bazlı tablo
        rows = []
        for f, kv in sorted(firma_kova.items(), key=lambda x: -sum(x[1].values())):
            r = {"Cari": f}
            for kk in KOVALAR:
                r[kk] = round(kv[kk], 2)
            r["Toplam"] = round(sum(kv.values()), 2)
            rows.append(r)
        # Toplam satırı
        _tsat = {"Cari": "TOPLAM"}
        for kk in KOVALAR:
            _tsat[kk] = round(kova_top[kk], 2)
        _tsat["Toplam"] = round(sum(kova_top.values()), 2)
        rows.append(_tsat)

        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.caption(f"Bugün ({gun_ay_yil(bugun.isoformat())}) itibarıyla, {pb} cinsinden açık ödemeler. "
                   "Gün sayıları vade tarihine göre gecikmedir.")
