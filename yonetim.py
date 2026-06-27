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


def _num(x):
    """Sayıya çevir; nan/boş ise None."""
    try:
        f = float(x)
        if f != f:  # nan
            return None
        return f
    except Exception:
        return None


def _read_excel_any(file):
    import pandas as pd
    name = (getattr(file, "name", "") or "").lower()
    eng = "xlrd" if name.endswith(".xls") else "openpyxl"
    return pd.read_excel(file, engine=eng, header=None)


GIDER_AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
               "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def gider_tablosu_parse(file):
    """Doldurulmuş aylık gider taslağı → (kategori_aylik, kalem_detay).
    kategori_aylik: {"Sabit":[12], "Değişken":[12], "Yarı Değişken":[12]}
    kalem_detay: [(kategori, kalem_adı, [12 aylık]), ...]"""
    df = _read_excel_any(file)
    kat = {"Sabit": [0.0] * 12, "Değişken": [0.0] * 12, "Yarı Değişken": [0.0] * 12}
    detay = []
    kategori = None
    for _, row in df.iterrows():
        a = str(row.iloc[0]).strip() if len(row) > 0 else ""
        b = str(row.iloc[1]).strip() if len(row) > 1 else ""
        aU = a.upper()
        if aU and "GİDER" in aU:
            if "SABİT" in aU or "SABIT" in aU:
                kategori = "Sabit"
            elif "YARI" in aU:
                kategori = "Yarı Değişken"
            elif "DEĞİŞKEN" in aU or "DEGISKEN" in aU:
                kategori = "Değişken"
            continue
        if not b or b == "nan" or "TOPLAM" in b.upper() or not kategori:
            continue
        aylik = [(_num(row.iloc[c]) or 0.0) if c < len(row) else 0.0 for c in range(2, 14)]
        if any(aylik):
            detay.append((kategori, b, aylik))
            for i in range(12):
                kat[kategori][i] += aylik[i]
    return kat, detay


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
    # Tek kur kaynağı: önce muhasebenin kullandığı kur (manuel override dahil),
    # muhasebe sayfası bu oturumda hiç açılmadıysa gunluk'tan güncel kur.
    _usdtry = 0.0
    try:
        _usdtry = float(st.session_state.get("kur") or 0)
    except Exception:
        _usdtry = 0.0
    if not _usdtry or _usdtry <= 1:
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

    # Ref no tutarları — havuz bütçeden AYRI destek kalemi (toplama dahil)
    try:
        from kayranpm.ref_no import get_tum_ref_tutarlari
        _ref_tutar = get_tum_ref_tutarlari(baslangic, bitis)
    except Exception:
        _ref_tutar = []
    _ref_usd = 0.0
    for r in _ref_tutar:
        tutar = float(r.get("tutar") or 0)
        dv = (r.get("doviz") or "USD").strip().upper()
        if dv in ("TL", "TRY", "₺", "TRL"):
            if _usdtry:
                tutar = tutar / _usdtry
                _tl_uyari = True
            else:
                _kur_eksik = True
                continue
        _ref_usd += tutar
    if _ref_usd:
        _tur_usd["Ref No"] = _tur_usd.get("Ref No", 0.0) + _ref_usd
        toplam_destek += _ref_usd

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

    # ── Aylık Gider Tablosu (Sabit / Değişken / Yarı Değişken) ──
    st.markdown("---")
    st.markdown("### 🧾 Aylık Gider Tablosu")
    st.caption("Sabit / Değişken / Yarı Değişken giderler · taslağı muhasebeye doldurtup yükle")
    _gider_anahtar = f"gider_tablosu_{_yil}"
    try:
        from kayranacc.database import get_ayar as _ga3, set_ayar as _sa3
    except Exception:
        _ga3 = _sa3 = None
    _gider = _ga3(_gider_anahtar) if _ga3 else None

    with st.expander(f"📤 {_yil} yılı gider tablosunu yükle (doldurulmuş taslak)", expanded=(not _gider)):
        st.markdown("Boş taslağı muhasebene gönder; **sabit / değişken / yarı değişken** kalemleri "
                    "12 ay için doldurulup buraya `.xlsx` olarak yüklenir. Aynı yılı tekrar yüklersen güncellenir.")
        _gf = st.file_uploader("Doldurulmuş Gider Tablosu (.xlsx / .xls)", type=["xlsx", "xls"],
                               key=f"gf_{_gider_anahtar}")
        if st.button("İşle ve kaydet", key=f"gider_kaydet_{_gider_anahtar}", type="primary"):
            if not _gf:
                st.error("Önce doldurulmuş tabloyu yükle.")
            else:
                try:
                    _katp, _detayp = gider_tablosu_parse(_gf)
                    _kayit = {"kat": _katp, "detay": _detayp, "tarih": str(dt.date.today())}
                    if _sa3:
                        _sa3(_gider_anahtar, _kayit)
                    _gider = _kayit
                    st.success("✅ Gider tablosu işlendi ve kaydedildi.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Dosya işlenemedi: {e}")

    if not _gider:
        st.info("Bu yıl için gider tablosu yüklenmedi. Taslağı doldurup yükleyince aylık masraflar burada görünür.")
    else:
        _kat = _gider.get("kat", {}) or {}
        AYLAR = GIDER_AYLAR

        def _g12(k):
            v = _kat.get(k, [0.0] * 12) or [0.0] * 12
            return [float(x or 0) for x in (v + [0.0] * 12)[:12]]

        _ay_aralik = {"Q1": (0, 3), "Q2": (3, 6), "Q3": (6, 9), "Q4": (9, 12)}.get(_donem, (0, 12))
        _i0, _i1 = _ay_aralik
        _sabit = sum(_g12("Sabit")[_i0:_i1])
        _degisken = sum(_g12("Değişken")[_i0:_i1])
        _yari = sum(_g12("Yarı Değişken")[_i0:_i1])
        _topgider = _sabit + _degisken + _yari

        def _tl(x):
            return f"₺{x:,.0f}"

        def _pay(x):
            return f"%{(x / _topgider * 100):.1f} pay" if _topgider else "—"

        st.markdown(f"**Seçili dönem ({_donem}) gider özeti**")
        st.markdown(
            '<div style="display:flex;gap:12px;flex-wrap:wrap;margin:8px 0 14px">'
            + _kart("Sabit Giderler", _tl(_sabit), _pay(_sabit), "#60A5FA")
            + _kart("Değişken Giderler", _tl(_degisken), _pay(_degisken), "#FB923C")
            + _kart("Yarı Değişken", _tl(_yari), _pay(_yari), "#A78BFA")
            + _kart("TOPLAM GİDER", _tl(_topgider), f"{_donem} dönemi", "#F87171")
            + '</div>', unsafe_allow_html=True)

        import pandas as _pd_g
        _satirlar = []
        for _knm in ["Sabit", "Değişken", "Yarı Değişken"]:
            _vv = _g12(_knm)
            _row = {"Kategori": _knm}
            for _idx, _a in enumerate(AYLAR):
                _row[_a] = f"{_vv[_idx]:,.0f}"
            _row["Yıllık"] = f"{sum(_vv):,.0f}"
            _satirlar.append(_row)
        _trow = {"Kategori": "TOPLAM"}
        for _idx, _a in enumerate(AYLAR):
            _trow[_a] = f"{(_g12('Sabit')[_idx] + _g12('Değişken')[_idx] + _g12('Yarı Değişken')[_idx]):,.0f}"
        _trow["Yıllık"] = f"{(sum(_g12('Sabit')) + sum(_g12('Değişken')) + sum(_g12('Yarı Değişken'))):,.0f}"
        _satirlar.append(_trow)
        st.markdown("**Aylık gider dağılımı (₺)** — yatay kaydırılabilir")
        st.dataframe(_pd_g.DataFrame(_satirlar), hide_index=True, use_container_width=True)
        st.caption(f"📅 Yüklenme: {_gider.get('tarih','')} · Tutarlar TL.")

    # ── Toplam Aktifler (Muhasebe → snapshot, anlık) ──
    st.markdown("---")
    st.markdown("### 💎 Toplam Aktifler")
    try:
        from kayranacc.database import get_ayar
        _snap = get_ayar("toplam_aktif_snapshot")
    except Exception:
        _snap = None
    if not _snap:
        st.info("Henüz toplam aktif verisi yok. Muhasebe & Finans → 'Toplam Aktifler' sayfasında "
                "veriler işlendiğinde burada görünür.")
    else:
        _ta = float(_snap.get("toplam", 0) or 0)
        _kur = float(_snap.get("kur", 0) or 0)
        _tarih = _snap.get("tarih", "")
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#93C5FD,#3730A3,#7C3AED);border-radius:18px;'
            f'padding:26px 24px;text-align:center;margin:8px 0 12px;box-shadow:0 12px 32px rgba(30,64,175,0.25)">'
            f'<div style="font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#C7D2FE;margin-bottom:8px">💎 TOPLAM AKTİFLERİNİZ</div>'
            f'<div style="font-size:38px;font-weight:800;color:#FFFFFF;font-family:JetBrains Mono,monospace;letter-spacing:-1px;line-height:1.1">${_ta:,.0f}</div>'
            f'<div style="font-size:13px;color:#A5B4FC;margin-top:8px;font-family:JetBrains Mono,monospace">≈ ₺{(_ta*_kur):,.0f} (kur: {_kur:g})</div>'
            f'</div>', unsafe_allow_html=True)
        st.caption(f"📅 Son güncelleme: {_tarih} · Muhasebe → 'Toplam Aktifler' sayfası her işlendiğinde otomatik yenilenir.")
        import pandas as _pd_ta
        _kalemler = [
            ("📦 Stok değeri (×1.20)", _snap.get("stok", 0), "➕"),
            ("🚢 İthalat (ödenen)", _snap.get("ithalat", 0), "➕"),
            ("🏦 Banka (USD eşdeğeri)", _snap.get("banka", 0), "➕"),
            ("📥 Cari alacak", _snap.get("alacak", 0), "➕"),
            ("💰 Havuz bütçe (net)", _snap.get("havuz", 0), "➕"),
            ("➕ Manuel ekleme", _snap.get("manuel_ekle", 0), "➕"),
            ("📤 Cari borç", _snap.get("borc", 0), "➖"),
            ("🧾 Çekler", _snap.get("cek", 0), "➖"),
            ("➖ Manuel çıkarma", _snap.get("manuel_cikar", 0), "➖"),
        ]
        _rows_b = [{"Kalem": k, "Yön": y, "Tutar (USD)": f"${float(v or 0):,.0f}"}
                   for k, v, y in _kalemler if float(v or 0)]
        if _rows_b:
            st.markdown("**Hesaplama detayı**")
            st.dataframe(_pd_ta.DataFrame(_rows_b), hide_index=True, use_container_width=True)
