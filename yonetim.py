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


def gelir_tablosu_parse(file):
    """Resmi gelir tablosu (.xls/.xlsx) → kalem sözlüğü (cari dönem değerleri)."""
    df = _read_excel_any(file)
    sonuc = {}
    HARITA = {
        "net_satis":       ["C. NET SATIŞLAR", "NET SATIŞLAR"],
        "cogs":            ["SATIŞLARIN MALİYETİ"],
        "brut_kar":        ["BRÜT SATIŞ KARI"],
        "faaliyet_gideri": ["E. FAALİYET GİDERLERİ", "FAALİYET GİDERLERİ"],
        "pazarlama":       ["PAZARLAMA SAT"],
        "genel_yonetim":   ["GENEL YÖNETİM GİD"],
        "faaliyet_kari":   ["FAALİYET KARI"],
        "finansman":       ["FİNANSMAN GİDER"],
        "net_kar":         ["DÖNEM NET KARI"],
    }
    for _, row in df.iterrows():
        ad = str(row.iloc[0]).strip()
        cari = None
        for c in range(len(row) - 1, 0, -1):
            v = _num(row.iloc[c])
            if v is not None:
                cari = v
                break
        if cari is None:
            continue
        adU = ad.upper()
        for key, kaliplar in HARITA.items():
            if key in sonuc:
                continue
            if any(k in adU for k in kaliplar):
                sonuc[key] = cari
                break
    return sonuc


def mizan_amortisman_parse(file):
    """Mizandan dönem amortisman & itfa gideri (760.06 + 770.06 ana grup bakiyeleri)."""
    df = _read_excel_any(file)
    amort = 0.0
    for _, row in df.iterrows():
        kod = str(row.iloc[0]).strip()
        if kod in ("760.06", "770.06"):
            # TL borç bakiye sütununu sağdan en yakın pozitif sayı olarak bul
            v = None
            for c in (4, 3, 5, 2):
                if c < len(row):
                    vv = _num(row.iloc[c])
                    if vv:
                        v = vv
                        break
            if v:
                amort += abs(v)
    return amort


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

    # ── FAVÖK (EBITDA) & Mali Sonuçlar (Gelir Tablosu + Mizan) ──
    st.markdown("---")
    st.markdown("### 📈 FAVÖK (EBITDA) & Mali Sonuçlar")
    st.caption("Resmi gelir tablosu + mizan bazlı (çeyreklik) · FAVÖK = Faaliyet Kârı + Amortisman")
    _mali_anahtar = f"mali_sonuc_{_yil}_{_donem}"
    try:
        from kayranacc.database import get_ayar as _get_ayar2, set_ayar as _set_ayar2
    except Exception:
        _get_ayar2 = _set_ayar2 = None
    _mali = _get_ayar2(_mali_anahtar) if _get_ayar2 else None

    with st.expander(f"📤 {_yil} {_donem} için Gelir Tablosu + Mizan yükle", expanded=(not _mali)):
        _gt = st.file_uploader("Gelir Tablosu (.xls / .xlsx)", type=["xls", "xlsx"], key=f"gt_{_mali_anahtar}")
        _mz = st.file_uploader("Mizan (.xls / .xlsx) — amortisman için", type=["xls", "xlsx"], key=f"mz_{_mali_anahtar}")
        _kur_d = st.number_input("Dönem USD/TL kuru (USD karşılığı için)", min_value=0.0,
                                 value=float(_usdtry or 0), step=0.1, format="%.2f",
                                 key=f"kur_{_mali_anahtar}")
        if st.button("İşle ve kaydet", key=f"mali_kaydet_{_mali_anahtar}", type="primary"):
            if not _gt:
                st.error("En azından Gelir Tablosu yükle.")
            else:
                try:
                    _gtd = gelir_tablosu_parse(_gt)
                    _amort = mizan_amortisman_parse(_mz) if _mz else 0.0
                    _kayit = dict(_gtd)
                    _kayit["amortisman"] = _amort
                    _kayit["kur"] = _kur_d
                    _kayit["tarih"] = str(dt.date.today())
                    if _set_ayar2:
                        _set_ayar2(_mali_anahtar, _kayit)
                    _mali = _kayit
                    st.success("✅ Mali sonuçlar işlendi ve kaydedildi.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Dosya işlenemedi: {e}")

    if not _mali:
        st.info("Bu dönem için gelir tablosu/mizan yüklenmedi. Yukarıdaki kutudan yükleyince "
                "FAVÖK (EBITDA) marjı ve net kazanç burada görünür.")
    else:
        _ns = abs(float(_mali.get("net_satis") or 0))
        _ebit = float(_mali.get("faaliyet_kari") or 0)
        _amort = float(_mali.get("amortisman") or 0)
        _ebitda = _ebit + _amort
        _nk = float(_mali.get("net_kar") or 0)
        _kur_m = float(_mali.get("kur") or 0) or _usdtry or 0
        _ebitda_marj = (_ebitda / _ns * 100) if _ns else 0.0
        _net_marj = (_nk / _ns * 100) if _ns else 0.0

        def _ikili(tl):
            _u = (tl / _kur_m) if _kur_m else 0
            return f"₺{tl:,.0f} · ${_u:,.0f}"

        _nkrenk = "#34D399" if _nk >= 0 else "#F87171"
        st.markdown(
            '<div style="display:flex;gap:12px;flex-wrap:wrap;margin:10px 0 8px">'
            + _kart("Net Satış", _ikili(_ns), "Gelir tablosu", "#A5B4FC")
            + _kart("Faaliyet Kârı (EBIT)", _ikili(_ebit), f"EBIT marj {_pct(_ebit/_ns*100 if _ns else 0)}", "#38BDF8")
            + _kart("Amortisman", _ikili(_amort), "Mizan 760.06+770.06", "#FBBF24")
            + _kart("FAVÖK (EBITDA)", _ikili(_ebitda), f"FAVÖK marj {_pct(_ebitda_marj)}", "#34D399")
            + _kart("Dönem Net Kârı", _ikili(_nk), f"Net marj {_pct(_net_marj)}", _nkrenk)
            + '</div>', unsafe_allow_html=True)
        st.caption(f"📅 Yüklenme: {_mali.get('tarih','')} · USD karşılıkları 1$={_kur_m:g}₺ kuruyla. "
                   "FAVÖK = Faaliyet Kârı + Amortisman & İtfa.")

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
