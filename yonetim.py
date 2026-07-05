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
    _aylar = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
              "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    if donem in _aylar:
        ay = _aylar.index(donem) + 1
        import calendar
        son = calendar.monthrange(yil, ay)[1]
        return f"{yil}-{ay:02d}-01", f"{yil}-{ay:02d}-{son:02d}"
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
    """Sayıya çevir; nan/boş ise None. '1.234,56' · '₺12.500' · '12 500' gibi
    Türkçe biçimli METİN sayıları da çevirir."""
    try:
        f = float(x)
        if f != f:  # nan
            return None
        return f
    except Exception:
        pass
    try:
        s = str(x).strip().replace("₺", "").replace("TL", "").replace("\u00a0", " ").replace(" ", "")
        if not s or s.lower() == "nan":
            return None
        if "," in s and "." in s:      # 1.234,56 → 1234.56
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:                 # 1234,56 → 1234.56
            s = s.replace(",", ".")
        elif s.count(".") > 1:         # 1.234.567 → 1234567
            s = s.replace(".", "")
        elif "." in s:                 # tek nokta: 12.500 (TR binlik) → 12500; 12.5 → 12.5
            _tam, _kus = s.rsplit(".", 1)
            if len(_kus) == 3 and _kus.isdigit() and _tam.replace("-", "").isdigit():
                s = s.replace(".", "")
        f = float(s)
        return None if f != f else f
    except Exception:
        return None


def _read_excel_any(file):
    import pandas as pd
    name = (getattr(file, "name", "") or "").lower()
    eng = "xlrd" if name.endswith(".xls") else "openpyxl"
    return pd.read_excel(file, engine=eng, header=None)


GIDER_AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
               "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

# ═════════════════════════════════════════════════════════════════════
# AY KAPANIŞ RAPORU — tek fonksiyonda dönem P&L + kanal + ürün + kıyas
# ═════════════════════════════════════════════════════════════════════
def ay_pnl_hesapla(yil, ay_idx):
    """Bir ayın tam P&L'ini hesaplar (Yönetim Panosu ile aynı mantık, saf veri).
    ay_idx: 0-11. Döner: dict (ciro, cogs, brut, destek, gider, net_kar, marj,
    kanal[], urun[], iade_tutar). Hata olan blok 0 kalır, asla patlamaz."""
    import calendar as _cal
    _son = _cal.monthrange(yil, ay_idx + 1)[1]
    bas = f"{yil}-{ay_idx+1:02d}-01"
    bit = f"{yil}-{ay_idx+1:02d}-{_son:02d}"

    r = {"yil": yil, "ay": GIDER_AYLAR[ay_idx], "bas": bas, "bit": bit,
         "ciro": 0.0, "cogs": 0.0, "brut": 0.0, "destek": 0.0, "gider": 0.0,
         "net_kar": 0.0, "marj": 0.0, "iade_tutar": 0.0,
         "kanal": [], "urun_top": [], "urun_zarar": []}

    # Satış P&L — TEK KAYNAK: v_satis_pnl (yoksa Python)
    kanal = {}
    urun = {}
    try:
        from satis.database import (get_satislar, ozet_hesapla, iade_satis_net_ozet,
                                    get_satis_pnl_view, ozet_from_view)
        _vr_s = get_satis_pnl_view(bas, bit)
        if _vr_s is not None:
            _top, kanal, urun = ozet_from_view(_vr_s)
        else:
            _sat = get_satislar(bas, bit)
            _top, kanal, urun = ozet_hesapla(_sat)
        r["ciro"] = float(_top.get("ciro", 0) or 0)
        r["cogs"] = float(_top.get("maliyet", 0) or 0)
        try:
            _isat, _itop = iade_satis_net_ozet(bas, bit)
            r["iade_tutar"] = float(_itop.get("i_tutar", 0) or 0)
            _iade_maliyet = r["iade_tutar"] - float(_itop.get("i_kar", 0) or 0)
            r["ciro"] -= r["iade_tutar"]
            r["cogs"] -= _iade_maliyet
        except Exception:
            pass
    except Exception:
        pass
    r["brut"] = r["ciro"] - r["cogs"]

    # Kur
    _usdtry = 0.0
    try:
        from gunluk import get_doviz
        _usdtry = float(get_doviz().get("USD") or 0)
    except Exception:
        pass
    _kur_map = {}
    try:
        from kayranacc.database import get_kur_araligi
        _kur_map = get_kur_araligi(bas, bit)
    except Exception:
        pass
    def _kur_of(t):
        return _kur_map.get(str(t)[:10]) if t else None

    # Destekler — TEK KAYNAK: v_destek_donem (yoksa Python yedeği)
    destek = 0.0
    _vr = None
    try:
        from kayranpm.ref_no import get_destek_donem
        _vr = get_destek_donem(bas, bit)
    except Exception:
        _vr = None
    if _vr is not None:
        for h in _vr:
            _t = float(h.get("tutar") or 0)
            if (h.get("doviz") or "USD").strip().upper() in ("TL", "TRY", "₺", "TRL"):
                _k = _kur_of(h.get("donem")) or _usdtry
                _t = (_t / _k) if _k else 0
            destek += _t
    else:
        try:
            from kayranpm.ref_no import get_tum_butce_harcamalari, get_tum_ref_tutarlari
            for h in (get_tum_butce_harcamalari(bas, bit) or []):
                _t = float(h.get("tutar") or 0)
                if (h.get("doviz") or "USD").strip().upper() in ("TL", "TRY", "₺", "TRL"):
                    _k = _kur_of(h.get("fatura_tarih")) or _usdtry
                    _t = (_t / _k) if _k else 0
                destek += _t
            for rf in (get_tum_ref_tutarlari(bas, bit) or []):
                _t = float(rf.get("tutar") or 0)
                if (rf.get("doviz") or "USD").strip().upper() in ("TL", "TRY", "₺", "TRL"):
                    _k = _kur_of(rf.get("tarih")) or _usdtry
                    _t = (_t / _k) if _k else 0
                destek += _t
        except Exception:
            pass
    r["destek"] = destek

    # İşletme gideri (aylık gider tablosu → USD)
    gider = 0.0
    try:
        from kayranacc.database import get_ayar
        _gd = get_ayar(f"gider_tablosu_{yil}")
        if _gd and _gd.get("kat"):
            _kk = _gd["kat"]
            _ay_tl = sum(float(((_kk.get(_k) or [0.0]*12 + [0.0]*12)[ay_idx]) or 0)
                         for _k in ("Sabit", "Değişken", "Yarı Değişken"))
            _ay_kur = _kur_of(f"{yil}-{ay_idx+1:02d}-15") or _usdtry
            if _ay_kur:
                gider = _ay_tl / _ay_kur
    except Exception:
        pass
    r["gider"] = gider

    r["net_kar"] = r["brut"] - r["destek"] - r["gider"]
    r["marj"] = (r["net_kar"] / r["ciro"] * 100) if r["ciro"] else 0.0

    # Kanal kırılımı (ciro azalan)
    r["kanal"] = sorted(
        [{"kanal": kn, "ciro": v.get("ciro", 0), "adet": int(v.get("adet", 0)),
          "net_kar": v.get("net_kar", 0),
          "marj": (v.get("net_kar", 0) / v.get("ciro", 1) * 100) if v.get("ciro") else 0}
         for kn, v in kanal.items()],
        key=lambda x: -x["ciro"])[:12]

    # En kârlı / en zararlı ürünler
    _ur = [{"sku": su, "urun": (v.get("urun_adi") or su)[:34], "adet": int(v.get("adet", 0)),
            "ciro": v.get("ciro", 0), "net_kar": v.get("net_kar", 0)}
           for su, v in urun.items()]
    r["urun_top"] = sorted(_ur, key=lambda x: -x["net_kar"])[:8]
    r["urun_zarar"] = [u for u in sorted(_ur, key=lambda x: x["net_kar"])[:8] if u["net_kar"] < 0]
    return r



def gider_tablosu_parse(file):
    """Doldurulmuş aylık gider taslağı → (kategori_aylik, kalem_detay).
    Ay kolonları BAŞLIK SATIRINDAN dinamik bulunur (kolon eklenmiş/kaymışsa da çalışır);
    başlık bulunamazsa eski sabit düzen (C..N) kullanılır. Veri içeren İLK sayfa işlenir."""
    import pandas as pd
    name = (getattr(file, "name", "") or "").lower()
    eng = "xlrd" if name.endswith(".xls") else "openpyxl"
    try:
        _sheets = pd.read_excel(file, engine=eng, header=None, sheet_name=None)
    except Exception:
        try:
            file.seek(0)
        except Exception:
            pass
        _sheets = {"0": pd.read_excel(file, engine=eng, header=None)}

    def _tr_up(s):
        return str(s).strip().replace("i", "İ").replace("ı", "I").upper()

    _AY_NORM = {_tr_up(a): a for a in GIDER_AYLAR}

    def _parse_df(df):
        kat = {"Sabit": [0.0] * 12, "Değişken": [0.0] * 12, "Yarı Değişken": [0.0] * 12}
        detay = []
        # 1) Başlık satırını bul: en az 3 ay adı içeren satır → {ay: kolon} haritası
        ay_kolon, kat_kolon, kalem_kolon, hdr_idx = {}, 0, 1, None
        for ridx in range(min(len(df), 15)):
            _hits = {}
            for cidx in range(len(df.columns)):
                _v = _tr_up(df.iat[ridx, cidx])
                if _v in _AY_NORM:
                    _hits[_AY_NORM[_v]] = cidx
            if len(_hits) >= 3:
                ay_kolon, hdr_idx = _hits, ridx
                for cidx in range(len(df.columns)):
                    _v = _tr_up(df.iat[ridx, cidx])
                    if "KATEGORİ" in _v or "KATEGORI" in _v:
                        kat_kolon = cidx
                    elif "KALEM" in _v:
                        kalem_kolon = cidx
                break
        if not ay_kolon:  # eski sabit düzen: C..N = Ocak..Aralık
            ay_kolon = {a: 2 + i for i, a in enumerate(GIDER_AYLAR)}

        kategori = None
        for ridx in range(((hdr_idx + 1) if hdr_idx is not None else 0), len(df)):
            row = df.iloc[ridx]
            a = str(row.iloc[kat_kolon]).strip() if len(row) > kat_kolon else ""
            b = str(row.iloc[kalem_kolon]).strip() if len(row) > kalem_kolon else ""
            aU = _tr_up(a)
            if aU and aU != "NAN" and "GİDER" in aU:
                if "SABİT" in aU or "SABIT" in aU:
                    kategori = "Sabit"
                elif "YARI" in aU:
                    kategori = "Yarı Değişken"
                elif "DEĞİŞKEN" in aU or "DEGISKEN" in aU:
                    kategori = "Değişken"
                continue
            if not b or b.lower() == "nan" or "TOPLAM" in _tr_up(b) or not kategori:
                continue
            aylik = []
            for _ay in GIDER_AYLAR:
                _c = ay_kolon.get(_ay)
                _v = _num(row.iloc[_c]) if (_c is not None and _c < len(row)) else None
                aylik.append(_v or 0.0)
            if any(aylik):
                detay.append((kategori, b, aylik))
                for i in range(12):
                    kat[kategori][i] += aylik[i]
        return kat, detay

    _en_iyi = None
    for _sn, _df in _sheets.items():
        try:
            kat, detay = _parse_df(_df)
        except Exception:
            continue
        if detay:
            return kat, detay
        if _en_iyi is None:
            _en_iyi = (kat, detay)
    return _en_iyi or ({"Sabit": [0.0] * 12, "Değişken": [0.0] * 12, "Yarı Değişken": [0.0] * 12}, [])


def run():
    from shared.ui import RENK, pencere_css, pencere, pencere_grid, bos_durum, sayfa_baslik, tablo_h
    st.markdown(pencere_css(), unsafe_allow_html=True)
    st.markdown(sayfa_baslik("📊", "Yönetim Panosu", "Ciro − COGS − Destekler − Giderler = Net Kâr · tüm tutarlar USD"),
                unsafe_allow_html=True)

    # ── Dönem seçimi — tek kompakt satır ──
    _bugun = dt.date.today()
    c1, c2, c3 = st.columns([0.8, 1.6, 1.6])
    with c1:
        _yil = st.selectbox("Yıl", list(range(_bugun.year + 1, _bugun.year - 4, -1)), index=1)
    with c2:
        _gor = st.radio("Görünüm", ["Aylık", "Çeyreklik", "Yıllık"], horizontal=True, index=2)
    with c3:
        if _gor == "Aylık":
            _donem = st.selectbox("Ay", GIDER_AYLAR, index=min(_bugun.month - 1, 11))
        elif _gor == "Çeyreklik":
            _donem = st.radio("Çeyrek", ["Q1", "Q2", "Q3", "Q4"], horizontal=True, index=0)
        else:
            _donem = "Tüm Yıl"
            st.markdown('<div style="color:#64748B;font-size:12px;margin-top:34px">Tüm yıl görünümü</div>',
                        unsafe_allow_html=True)
    baslangic, bitis = _donem_tarih(_yil, _donem)

    # ── Gelir / maliyet (satış) — TEK KAYNAK: v_satis_pnl (yoksa Python) ──
    ciro = cogs = 0.0
    kanal = {}
    try:
        from satis.database import (get_satislar, ozet_hesapla,
                                    get_satis_pnl_view, ozet_from_view)
        _vrows_s = get_satis_pnl_view(baslangic, bitis)
        if _vrows_s is not None:
            top, kanal, _urun = ozet_from_view(_vrows_s)
        else:
            _satislar = get_satislar(baslangic, bitis)
            top, kanal, _urun = ozet_hesapla(_satislar)
        ciro = float(top.get("ciro", 0.0) or 0.0)
        cogs = float(top.get("maliyet", 0.0) or 0.0)
    except Exception as e:
        st.warning(f"Satış verisi okunamadı: {e}")

    # ── İadeler (net kâra dahil) ──
    iade_tutar = iade_maliyet = 0.0
    try:
        from satis.database import iade_satis_net_ozet
        _isat, _itop = iade_satis_net_ozet(baslangic, bitis)
        iade_tutar = float(_itop.get("i_tutar", 0.0) or 0.0)
        iade_maliyet = iade_tutar - float(_itop.get("i_kar", 0.0) or 0.0)
    except Exception:
        pass

    ciro_brut, cogs_brut = ciro, cogs
    ciro = ciro_brut - iade_tutar
    cogs = cogs_brut - iade_maliyet
    brut = ciro - cogs
    brut_marj = (brut / ciro * 100) if ciro else 0.0

    # ── Destekler — TEK KAYNAK: v_destek_donem view (yoksa Python hesabına düşer) ──
    _vrows = None
    try:
        from kayranpm.ref_no import get_destek_donem
        _vrows = get_destek_donem(baslangic, bitis)
    except Exception:
        _vrows = None

    _harcama = []
    if _vrows is None:
        try:
            from kayranpm.ref_no import get_tum_butce_harcamalari
            _harcama = get_tum_butce_harcamalari(baslangic, bitis)
        except Exception:
            _harcama = []
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

    _kur_map = {}
    try:
        from kayranacc.database import get_kur_araligi
        _kur_map = get_kur_araligi(baslangic, bitis)
    except Exception:
        _kur_map = {}

    def _kur_of(tarih):
        k = _kur_map.get(str(tarih)[:10]) if tarih else None
        return k or _usdtry

    _tur_usd = {}
    _tl_uyari = False
    _kur_eksik = False
    toplam_destek = 0.0

    if _vrows is not None:
        # ✅ TEK KAYNAK dalı: v_destek_donem — ref + havuz tek döngüde
        for h in _vrows:
            t = (h.get("tur") or "Diğer").strip() or "Diğer"
            tutar = float(h.get("tutar") or 0)
            dv = (h.get("doviz") or "USD").strip().upper()
            if dv in ("TL", "TRY", "₺", "TRL"):
                _k = _kur_of(h.get("donem"))
                if _k:
                    tutar = tutar / _k
                    _tl_uyari = True
                else:
                    _kur_eksik = True
                    continue
            _tur_usd[t] = _tur_usd.get(t, 0.0) + tutar
            toplam_destek += tutar
    else:
        # 🔁 Yedek dal: view kurulmamışsa eski Python hesabı (davranış birebir)
        for h in _harcama:
            t = (h.get("tur") or "Diğer").strip() or "Diğer"
            tutar = float(h.get("tutar") or 0)
            dv = (h.get("doviz") or "USD").strip().upper()
            if dv in ("TL", "TRY", "₺", "TRL"):
                _k = _kur_of(h.get("fatura_tarih"))
                if _k:
                    tutar = tutar / _k
                    _tl_uyari = True
                else:
                    _kur_eksik = True
                    continue
            _tur_usd[t] = _tur_usd.get(t, 0.0) + tutar
            toplam_destek += tutar

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
                _k = _kur_of(r.get("tarih"))
                if _k:
                    tutar = tutar / _k
                    _tl_uyari = True
                else:
                    _kur_eksik = True
                    continue
            _ref_usd += tutar
        if _ref_usd:
            _tur_usd["Ref No"] = _tur_usd.get("Ref No", 0.0) + _ref_usd
            toplam_destek += _ref_usd

    # ── İşletme giderleri (Aylık Gider Tablosu) → USD ──
    gider_usd = 0.0
    try:
        from kayranacc.database import get_ayar as _gax
        _gd = _gax(f"gider_tablosu_{_yil}")
        if _gd and _gd.get("kat"):
            _kk = _gd["kat"]

            def _gv(k, i):
                v = (_kk.get(k) or [0.0] * 12)
                return float(((v + [0.0] * 12)[i]) or 0)

            if _donem in GIDER_AYLAR:
                _gi0 = GIDER_AYLAR.index(_donem)
                _gi1 = _gi0 + 1
            else:
                _gi0, _gi1 = {"Q1": (0, 3), "Q2": (3, 6), "Q3": (6, 9),
                              "Q4": (9, 12)}.get(_donem, (0, 12))
            for _mi in range(_gi0, _gi1):
                _ay_tl = _gv("Sabit", _mi) + _gv("Değişken", _mi) + _gv("Yarı Değişken", _mi)
                if not _ay_tl:
                    continue
                _ay_kur = _kur_of(f"{_yil}-{_mi + 1:02d}-15") or _usdtry
                if _ay_kur:
                    gider_usd += _ay_tl / _ay_kur
    except Exception:
        pass

    net_kar = brut - toplam_destek - gider_usd
    net_marj = (net_kar / ciro * 100) if ciro else 0.0
    _nrenk = RENK["yesil"] if net_kar >= 0 else RENK["kirmizi"]

    # ═════════ P&L DENKLEM ŞERİDİ — kartlar + formül tek bantta ═════════
    def _hucre(etiket, deger, alt, renk, vurgulu=False):
        _st = ("background:" + renk + "14;border:1px solid " + renk + "45;border-radius:12px;"
               if vurgulu else "")
        _vf = "22px" if vurgulu else "18px"
        _vr = renk if vurgulu else RENK["metin"]
        return (f'<div style="flex:1;min-width:116px;text-align:center;padding:10px 8px;{_st}">'
                f'<div style="font-size:10px;color:{RENK["soluk"]};letter-spacing:1.2px;'
                f'text-transform:uppercase;font-weight:700;margin-bottom:5px">{etiket}</div>'
                f'<div style="color:{_vr};font-size:{_vf};font-weight:800;'
                f'font-family:JetBrains Mono,monospace;line-height:1.1">{deger}</div>'
                f'<div style="color:{renk};font-size:10.5px;font-weight:600;margin-top:4px">{alt}</div></div>')

    def _op(s):
        return (f'<div style="display:flex;align-items:center;color:#475569;font-size:19px;'
                f'font-weight:700;padding:0 2px">{s}</div>')

    _ciro_alt = (f"brüt {_usd(ciro_brut)} − iade {_usd(iade_tutar)}" if iade_tutar > 0 else "net satış")
    st.markdown(
        f'<div style="display:flex;align-items:stretch;gap:4px;flex-wrap:wrap;'
        f'background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.07);'
        f'border-radius:16px;padding:12px 10px;margin:6px 0 4px">'
        + _hucre("Ciro", _usd(ciro), _ciro_alt, RENK["mor2"])
        + _op("−") + _hucre("COGS", _usd(cogs), "ürün maliyeti", RENK["amber"])
        + _op("=") + _hucre("Brüt Kâr", _usd(brut), f"marj {_pct(brut_marj)}", RENK["cyan"])
        + _op("−") + _hucre("Destekler", _usd(toplam_destek), "havuz + ref no", RENK["pembe"])
        + _op("−") + _hucre("Giderler", _usd(gider_usd), "işletme (TL→USD)", RENK["amber2"])
        + _op("=") + _hucre("NET KÂR", _usd(net_kar), f"net marj {_pct(net_marj)}", _nrenk, vurgulu=True)
        + '</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="color:#475569;font-size:11px;margin:0 2px 10px">📅 {baslangic} → {bitis}'
                + (f' · ℹ️ TL destekler fatura günü kuruyla çevrildi (eksik günlerde ~{_usdtry:.2f}₺)' if _tl_uyari else '')
                + '</div>', unsafe_allow_html=True)
    if _kur_eksik:
        st.warning("⚠️ Güncel kur alınamadığı için TL cinsi destekler hesaba katılamadı.")

    # ═════════ ORTA GRID — 4 scroll'lu pencere ═════════
    def _bar_satir(ad, tutar_str, oran, renk, sag_ek=""):
        _w = max(2, min(100, oran))
        return (f'<div style="padding:5px 10px;margin:3px 0;border-radius:6px;background:rgba(255,255,255,0.03)">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">'
                f'<span style="color:{RENK["metin"]};font-size:12px;font-weight:600">{ad}</span>'
                f'<span style="color:{RENK["metin"]};font-size:12px;font-weight:700;'
                f'font-family:JetBrains Mono,monospace">{tutar_str}'
                f'<span style="color:{RENK["silik"]};font-weight:500"> {sag_ek}</span></span></div>'
                f'<div style="height:4px;border-radius:2px;background:rgba(255,255,255,0.05)">'
                f'<div style="height:4px;border-radius:2px;width:{_w:.1f}%;background:{renk}"></div></div></div>')

    # Pencere 1 — Destek kırılımı
    if _tur_usd:
        _dmax = max(_tur_usd.values()) or 1
        _d_html = "".join(
            _bar_satir(t, f"${v:,.0f}", v / _dmax * 100, RENK["pembe"],
                       sag_ek=(f"· %{(v / toplam_destek * 100):.0f}" if toplam_destek else ""))
            for t, v in sorted(_tur_usd.items(), key=lambda x: -x[1]))
    else:
        _d_html = bos_durum("Bu dönemde destek/harcama kaydı yok")
    _p_destek = pencere("🎯 DESTEK KIRILIMI", RENK["pembe"], _d_html,
                        rozet=_usd(toplam_destek), yukseklik=230)

    # Pencere 2 — Kanal bazında satış
    if kanal:
        _kmax = max((v.get("ciro", 0) for v in kanal.values()), default=1) or 1
        _k_html = "".join(
            _bar_satir(kn, _usd(v.get("ciro", 0)), v.get("ciro", 0) / _kmax * 100, RENK["mor"],
                       sag_ek=f"· {int(v.get('adet', 0)):,} ad · NK {_usd(v.get('net_kar', 0))}")
            for kn, v in sorted(kanal.items(), key=lambda x: -x[1].get("ciro", 0)))
    else:
        _k_html = bos_durum("Bu dönemde satış kaydı yok")
    _p_kanal = pencere("🛒 KANAL BAZINDA SATIŞ", RENK["mor"], _k_html,
                       rozet=f"{len(kanal)} kanal", yukseklik=230)

    st.markdown(pencere_grid(_p_destek, _p_kanal), unsafe_allow_html=True)

    # Gider verisi (pencere 3 için)
    _gider_anahtar = f"gider_tablosu_{_yil}"
    try:
        from kayranacc.database import get_ayar as _ga3, set_ayar as _sa3
    except Exception:
        _ga3 = _sa3 = None
    _gider = _ga3(_gider_anahtar) if _ga3 else None

    if _gider:
        _kat = _gider.get("kat", {}) or {}

        def _g12(k):
            v = _kat.get(k, [0.0] * 12) or [0.0] * 12
            return [float(x or 0) for x in (v + [0.0] * 12)[:12]]

        if _donem in GIDER_AYLAR:
            _gdx = GIDER_AYLAR.index(_donem)
            _i0, _i1 = _gdx, _gdx + 1
        else:
            _i0, _i1 = {"Q1": (0, 3), "Q2": (3, 6), "Q3": (6, 9), "Q4": (9, 12)}.get(_donem, (0, 12))
        _sabit = sum(_g12("Sabit")[_i0:_i1])
        _degisken = sum(_g12("Değişken")[_i0:_i1])
        _yari = sum(_g12("Yarı Değişken")[_i0:_i1])
        _topgider = _sabit + _degisken + _yari
        _gmax = max(_sabit, _degisken, _yari, 1)
        _g_html = (
            _bar_satir("Sabit", f"₺{_sabit:,.0f}", _sabit / _gmax * 100, "#60A5FA",
                       sag_ek=(f"· %{(_sabit / _topgider * 100):.0f}" if _topgider else ""))
            + _bar_satir("Değişken", f"₺{_degisken:,.0f}", _degisken / _gmax * 100, "#FB923C",
                         sag_ek=(f"· %{(_degisken / _topgider * 100):.0f}" if _topgider else ""))
            + _bar_satir("Yarı Değişken", f"₺{_yari:,.0f}", _yari / _gmax * 100, "#A78BFA",
                         sag_ek=(f"· %{(_yari / _topgider * 100):.0f}" if _topgider else ""))
            + f'<div style="display:flex;justify-content:space-between;padding:7px 10px;margin-top:5px;'
              f'border-top:1px solid rgba(255,255,255,0.08)">'
              f'<span style="color:{RENK["soluk"]};font-size:11px;font-weight:700;letter-spacing:.5px">TOPLAM ({_donem})</span>'
              f'<span style="color:{RENK["kirmizi"]};font-size:13px;font-weight:800;'
              f'font-family:JetBrains Mono,monospace">₺{_topgider:,.0f}</span></div>'
            + f'<div style="color:{RENK["silik"]};font-size:10.5px;padding:2px 10px">'
              f'≈ {_usd(gider_usd)} · yüklenme: {_gider.get("tarih", "")}</div>')
    else:
        _g_html = bos_durum(f"{_yil} gider tablosu yüklenmedi — aşağıdan yükleyebilirsin")
    _p_gider = pencere("🧾 İŞLETME GİDERLERİ", RENK["kirmizi"], _g_html,
                       rozet=str(_yil), yukseklik=230)

    # Pencere 4 — Toplam Aktifler
    try:
        from kayranacc.database import get_ayar
        _snap = get_ayar("toplam_aktif_snapshot")
    except Exception:
        _snap = None
    if not _snap:
        _a_html = bos_durum("Muhasebe → Toplam Aktifler işlenince burada görünür")
        _a_rozet = ""
    else:
        _ta = float(_snap.get("toplam", 0) or 0)
        _kur_s = float(_snap.get("kur", 0) or 0)
        _a_rozet = str(_snap.get("tarih", ""))[:16]
        _kalemler = [
            ("📦 Stok değeri (×1.20)", _snap.get("stok", 0), "+"),
            ("🚢 İthalat (ödenen)", _snap.get("ithalat", 0), "+"),
            ("🏦 Banka (USD eşd.)", _snap.get("banka", 0), "+"),
            ("📥 Cari alacak", _snap.get("alacak", 0), "+"),
            ("💰 Havuz bütçe (net)", _snap.get("havuz", 0), "+"),
            ("➕ Manuel ekleme", _snap.get("manuel_ekle", 0), "+"),
            ("📤 Cari borç", _snap.get("borc", 0), "−"),
            ("🧾 Çekler", _snap.get("cek", 0), "−"),
            ("➖ Manuel çıkarma", _snap.get("manuel_cikar", 0), "−"),
        ]
        _kalem_html = "".join(
            f'<div style="display:flex;justify-content:space-between;padding:4px 10px;margin:2px 0;'
            f'border-radius:6px;background:rgba(255,255,255,0.03)">'
            f'<span style="color:{RENK["metin"]};font-size:11.5px">{k}</span>'
            f'<span style="color:{(RENK["yesil"] if y == "+" else RENK["kirmizi"])};font-size:11.5px;'
            f'font-weight:700;font-family:JetBrains Mono,monospace">{y} ${float(v or 0):,.0f}</span></div>'
            for k, v, y in _kalemler if float(v or 0))
        _a_html = (
            f'<div style="text-align:center;padding:8px 0 10px;margin-bottom:6px;'
            f'border-bottom:1px solid rgba(255,255,255,0.08)">'
            f'<div style="font-size:27px;font-weight:800;color:#FFFFFF;'
            f'font-family:JetBrains Mono,monospace;letter-spacing:-1px">${_ta:,.0f}</div>'
            f'<div style="font-size:11.5px;color:{RENK["mor2"]};'
            f'font-family:JetBrains Mono,monospace;margin-top:3px">≈ ₺{(_ta * _kur_s):,.0f} · kur {_kur_s:g}</div></div>'
            + _kalem_html)
    _p_aktif = pencere("💎 TOPLAM AKTİFLER", RENK["mor"], _a_html, rozet=_a_rozet, yukseklik=230)

    st.markdown(pencere_grid(_p_gider, _p_aktif), unsafe_allow_html=True)

    # ═════════ ARAÇLAR — 4 pencere butonu ═════════
    @st.dialog(f"📤 {_yil} Gider Tablosu Yükle", width="large")
    def _dlg_gider_yukle():
        st.markdown("Boş taslağı muhasebene gönder; **sabit / değişken / yarı değişken** kalemleri "
                    "12 ay için doldurulup buraya `.xlsx` olarak yüklenir. Aynı yılı tekrar yüklersen güncellenir.")
        _gf = st.file_uploader("Doldurulmuş Gider Tablosu (.xlsx / .xls)", type=["xlsx", "xls"],
                               key=f"gf_{_gider_anahtar}")
        if st.button("İşle ve kaydet", key=f"gider_kaydet_{_gider_anahtar}", type="primary"):
            if not _gf:
                st.error("Önce doldurulmuş tabloyu yükle.")
            else:
                try:
                    with st.spinner("🧾 Gider tablosu işleniyor…"):
                        _katp, _detayp = gider_tablosu_parse(_gf)
                    _yillik_top = sum(sum(v) for v in _katp.values())
                    if not _detayp or _yillik_top <= 0:
                        st.warning("⚠️ Dosya açıldı ama **hiç gider değeri okunamadı** — kayıt YAPILMADI. "
                                   "Kontrol et: (1) tutarlar ay kolonlarına (Ocak…Aralık) girilmiş mi, "
                                   "(2) hücreler sayı mı (formül sonucu da olur), "
                                   "(3) veriler dosyanın İLK sayfasında/aynı düzende mi.")
                    else:
                        _kayit = {"kat": _katp, "detay": _detayp, "tarih": str(dt.date.today())}
                        if _sa3:
                            _sa3(_gider_anahtar, _kayit)
                        st.success(f"✅ {len(_detayp)} kalem · yıllık ₺{_yillik_top:,.0f} kaydedildi.")
                        st.rerun()
                except Exception as e:
                    st.error(f"Dosya işlenemedi: {e}")

    @st.dialog("📅 Aylık Gider Dağılımı (₺)", width="large")
    def _dlg_gider_aylik():
        if not _gider:
            st.info("Bu yıl için gider tablosu yüklenmedi.")
            return
        import pandas as _pd_g
        _satirlar = []
        for _knm in ["Sabit", "Değişken", "Yarı Değişken"]:
            _vv = _g12(_knm)
            _row = {"Kategori": _knm}
            for _idx, _a in enumerate(GIDER_AYLAR):
                _row[_a] = f"{_vv[_idx]:,.0f}"
            _row["Yıllık"] = f"{sum(_vv):,.0f}"
            _satirlar.append(_row)
        _trow = {"Kategori": "TOPLAM"}
        for _idx, _a in enumerate(GIDER_AYLAR):
            _trow[_a] = f"{(_g12('Sabit')[_idx] + _g12('Değişken')[_idx] + _g12('Yarı Değişken')[_idx]):,.0f}"
        _trow["Yıllık"] = f"{(sum(_g12('Sabit')) + sum(_g12('Değişken')) + sum(_g12('Yarı Değişken'))):,.0f}"
        _satirlar.append(_trow)
        st.dataframe(_pd_g.DataFrame(_satirlar), hide_index=True, use_container_width=True,
                     height=tablo_h(len(_satirlar)))
        st.caption(f"📅 Yüklenme: {_gider.get('tarih', '')} · Tutarlar TL · yatay kaydırılabilir.")

    @st.dialog("🗂️ Değişiklik Günlüğü (Audit Log)", width="large")
    def _dlg_audit():
        _audit_render()

    @st.dialog("💾 Veri Yedekleme", width="large")
    def _dlg_yedek():
        _yedek_render()

    @st.dialog("📄 Ay Kapanış Raporu", width="large")
    def _dlg_ay_rapor():
        from shared.ui import RENK
        _bugun = dt.date.today()
        _c1, _c2 = st.columns(2)
        _ryil = _c1.selectbox("Yıl", list(range(_bugun.year, _bugun.year - 4, -1)), key="ayrap_yil")
        _ray = _c2.selectbox("Ay", GIDER_AYLAR,
                             index=max(0, _bugun.month - 2), key="ayrap_ay")
        _ai = GIDER_AYLAR.index(_ray)
        with st.spinner(f"{_ray} {_ryil} kapanışı hesaplanıyor…"):
            _r = ay_pnl_hesapla(_ryil, _ai)
            # Önceki ay kıyas
            _pai = _ai - 1
            _pyil = _ryil
            if _pai < 0:
                _pai = 11
                _pyil = _ryil - 1
            _rp = ay_pnl_hesapla(_pyil, _pai)

        def _delta(now, prev, tersi=False):
            if not prev:
                return ""
            _d = (now - prev) / abs(prev) * 100
            _ok = "▲" if _d >= 0 else "▼"
            _iyi = (_d >= 0) if not tersi else (_d < 0)
            _c = RENK["yesil"] if _iyi else RENK["kirmizi"]
            return f'<span style="color:{_c};font-size:11px;font-weight:700"> {_ok}%{abs(_d):.0f}</span>'

        _nr = RENK["yesil"] if _r["net_kar"] >= 0 else RENK["kirmizi"]
        # Başlık + 4 büyük metrik (önceki aya kıyaslı)
        st.markdown(
            f'<div style="font-size:16px;font-weight:800;color:{RENK["metin"]};margin-bottom:2px">'
            f'{_r["ay"]} {_r["yil"]} — Kapanış</div>'
            f'<div style="color:{RENK["silik"]};font-size:11.5px;margin-bottom:10px">'
            f'{_r["bas"]} → {_r["bit"]} · önceki ay ({_rp["ay"]}) ile kıyaslı · tüm tutarlar USD</div>'
            f'<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px">'
            + "".join(
                f'<div style="flex:1;min-width:130px;text-align:center;padding:12px 8px;'
                f'background:rgba(255,255,255,0.02);border:1px solid {c}30;border-radius:12px">'
                f'<div style="font-size:9.5px;color:{RENK["soluk"]};letter-spacing:1px;'
                f'text-transform:uppercase;font-weight:700;margin-bottom:5px">{lbl}</div>'
                f'<div style="color:{c};font-size:20px;font-weight:800;'
                f'font-family:JetBrains Mono,monospace">{val}{dl}</div></div>'
                for lbl, val, c, dl in [
                    ("Ciro", _usd(_r["ciro"]), RENK["mor2"], _delta(_r["ciro"], _rp["ciro"])),
                    ("COGS", _usd(_r["cogs"]), RENK["amber"], _delta(_r["cogs"], _rp["cogs"], tersi=True)),
                    ("Net Kâr", _usd(_r["net_kar"]), _nr, _delta(_r["net_kar"], _rp["net_kar"])),
                    ("Marj", f'%{_r["marj"]:.1f}', _nr, ""),
                ])
            + '</div>', unsafe_allow_html=True)

        # P&L akış satırı
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.07);'
            f'border-radius:10px;padding:10px 14px;margin-bottom:14px;font-family:JetBrains Mono,monospace;'
            f'font-size:12.5px;color:#CBD5E1">'
            f'{_usd(_r["ciro"])} <span style="color:#64748B">ciro</span> − '
            f'{_usd(_r["cogs"])} <span style="color:#64748B">cogs</span> − '
            f'{_usd(_r["destek"])} <span style="color:#64748B">destek</span> − '
            f'{_usd(_r["gider"])} <span style="color:#64748B">gider</span> = '
            f'<b style="color:{_nr}">{_usd(_r["net_kar"])} net kâr</b></div>',
            unsafe_allow_html=True)

        import pandas as _pd
        if _r["kanal"]:
            st.markdown("**🛒 Kanal Kırılımı**")
            st.dataframe(_pd.DataFrame([{
                "Kanal": k["kanal"], "Adet": k["adet"], "Ciro": _usd(k["ciro"]),
                "Net Kâr": _usd(k["net_kar"]), "Marj": f'%{k["marj"]:.1f}',
            } for k in _r["kanal"]]), hide_index=True, use_container_width=True,
                height=min(300, 40 + 35 * len(_r["kanal"])))

        _cc1, _cc2 = st.columns(2)
        if _r["urun_top"]:
            with _cc1:
                st.markdown("**🏆 En Kârlı Ürünler**")
                st.dataframe(_pd.DataFrame([{
                    "Ürün": u["urun"], "Adet": u["adet"], "Net Kâr": _usd(u["net_kar"]),
                } for u in _r["urun_top"]]), hide_index=True, use_container_width=True,
                    height=min(260, 40 + 35 * len(_r["urun_top"])))
        if _r["urun_zarar"]:
            with _cc2:
                st.markdown("**📉 Zarardaki Ürünler**")
                st.dataframe(_pd.DataFrame([{
                    "Ürün": u["urun"], "Adet": u["adet"], "Net Kâr": _usd(u["net_kar"]),
                } for u in _r["urun_zarar"]]), hide_index=True, use_container_width=True,
                    height=min(260, 40 + 35 * len(_r["urun_zarar"])))

        # İndirilebilir özet (metin)
        _txt = (f"{_r['ay']} {_r['yil']} KAPANIŞ ÖZETİ\n"
                f"{'='*40}\n"
                f"Dönem: {_r['bas']} → {_r['bit']}\n\n"
                f"Ciro       : {_usd(_r['ciro'])}\n"
                f"COGS       : {_usd(_r['cogs'])}\n"
                f"Brüt Kâr   : {_usd(_r['brut'])}\n"
                f"Destekler  : {_usd(_r['destek'])}\n"
                f"Giderler   : {_usd(_r['gider'])}\n"
                f"NET KÂR    : {_usd(_r['net_kar'])}  (marj %{_r['marj']:.1f})\n\n"
                f"KANAL KIRILIMI\n" +
                "\n".join(f"  {k['kanal'][:30]:30s} {_usd(k['ciro']):>12s}  "
                          f"NK {_usd(k['net_kar']):>10s}  %{k['marj']:.1f}"
                          for k in _r["kanal"]))
        st.download_button("⬇️ Özeti indir (.txt)", _txt.encode("utf-8"),
                           f"kapanis_{_r['yil']}_{_ai+1:02d}.txt", "text/plain",
                           use_container_width=True, key="ayrap_dl")

    _bt = st.columns(5)
    if _bt[0].button(f"📤 Gider Yükle ({_yil})", key="btn_yon_gider", use_container_width=True):
        _dlg_gider_yukle()
    if _bt[1].button("📅 Aylık Gider", key="btn_yon_aylik", use_container_width=True):
        _dlg_gider_aylik()
    if _bt[2].button("📄 Ay Kapanış Raporu", key="btn_yon_ayrapor", use_container_width=True):
        _dlg_ay_rapor()
    if _bt[3].button("🗂️ Değişiklik Günlüğü", key="btn_yon_audit", use_container_width=True):
        _dlg_audit()
    if _bt[4].button("💾 Yedekleme", key="btn_yon_yedek", use_container_width=True):
        _dlg_yedek()


def _audit_render():
    """Değişiklik günlüğü (audit log) görüntüleme — Yönetim Panosu içinde."""
    import pandas as pd
    from shared.audit import get_loglar
    c1, c2, c3 = st.columns(3)
    _modul_f = c1.selectbox("Modül", ["(tümü)", "Muhasebe", "Ürün Yönetimi",
                                       "İthalat", "Satış", "Teknik Servis"], key="audit_modul")
    _islem_f = c2.selectbox("İşlem", ["(tümü)", "ekle", "güncelle", "sil", "ekle/güncelle"],
                            key="audit_islem")
    _limit = c3.selectbox("Kayıt sayısı", [100, 250, 500, 1000], index=2, key="audit_limit")
    loglar = get_loglar(
        limit=_limit,
        modul=None if _modul_f == "(tümü)" else _modul_f,
        islem=None if _islem_f == "(tümü)" else _islem_f,
    )
    if not loglar:
        st.info("Henüz kayıt yok ya da audit_log tablosu oluşturulmadı (SQL'i çalıştırın).")
        return
    _kullanicilar = ["(tümü)"] + sorted({l.get("kullanici", "") for l in loglar if l.get("kullanici")})
    _kul = st.selectbox("Kullanıcı", _kullanicilar, key="audit_kul")
    if _kul != "(tümü)":
        loglar = [l for l in loglar if l.get("kullanici") == _kul]
    df = pd.DataFrame([{
        "Zaman": l.get("zaman", ""),
        "Kullanıcı": l.get("kullanici", ""),
        "Modül": l.get("modul", ""),
        "İşlem": l.get("islem", ""),
        "Tablo": l.get("tablo", ""),
        "Kayıt No": l.get("kayit_id", ""),
        "Detay": l.get("detay", ""),
    } for l in loglar])
    st.dataframe(df, hide_index=True, use_container_width=True)
    st.caption(f"{len(loglar)} kayıt gösteriliyor (yeni→eski).")


# ── Veri Yedekleme ──────────────────────────────────────────────────
# İş verisi yedeklenir. ŞİFRE ve oturum/geçici tablolar GÜVENLİK için hariç.
YEDEK_TABLOLAR = [
    "urunler", "firma_stok", "stok_yas", "yoldaki_urunler",
    "kampanyalar", "kampanya_urunler",
    "ref_kayitlari", "ref_butce", "ref_firmalar",
    "ithalat_dosyalari", "ithalat_kalemleri",
    "satislar",
    "odemeler", "bankalar", "cekler", "virmanlar", "haftalar",
    "ts_kayitlar", "ts_gecmis",
    "siparis_onerileri", "talepler", "gorevler", "bildirimler",
    "kur_gunluk", "sistem_ayarlari", "pm_ayarlar",
    "gunluk_giris", "aktif_manuel_kalemler",
]
# Bilerek HARİÇ: kullanici_sifreler (şifre!), kullanici_durum (oturum),
#                aktif_excel_verileri (geçici cache), audit_log (denetim logu)


def _yedek_olustur():
    """Tüm iş verisini tek çok-sayfalı Excel (BytesIO bytes) olarak döndürür.
    Her tablo ayrı sayfa. Hata olan tablo boş sayfa olarak geçer."""
    import io
    import pandas as pd
    from shared.audit import _raw_client
    sb = _raw_client()
    ozet = []
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for tablo in YEDEK_TABLOLAR:
            try:
                rows = sb.table(tablo).select("*").execute().data or []
            except Exception:
                rows = []
            df = pd.DataFrame(rows) if rows else pd.DataFrame()
            # Excel sayfa adı en fazla 31 karakter
            df.to_excel(w, sheet_name=tablo[:31], index=False)
            ozet.append((tablo, len(rows)))
    buf.seek(0)
    return buf.getvalue(), ozet


def _yedek_render():
    from datetime import datetime, timedelta
    st.caption("Tüm iş verisini tek bir Excel dosyasına indirir (her tablo ayrı sayfa). "
               "Şifreler ve geçici/oturum verileri güvenlik gereği yedeğe DAHİL EDİLMEZ.")
    if st.button("📦 Yedeği Hazırla", key="yedek_hazirla"):
        with st.spinner("Tablolar toplanıyor…"):
            try:
                veri, ozet = _yedek_olustur()
                _ts = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d_%H-%M")
                st.session_state["_yedek_data"] = veri
                st.session_state["_yedek_ad"] = f"kayran_yedek_{_ts}.xlsx"
                st.session_state["_yedek_ozet"] = ozet
            except Exception as e:
                st.error(f"Yedek hazırlanamadı: {e}")
    if st.session_state.get("_yedek_data"):
        _ozet = st.session_state.get("_yedek_ozet", [])
        _toplam = sum(n for _, n in _ozet)
        st.success(f"✅ Yedek hazır — {len(_ozet)} tablo, {_toplam:,} kayıt.")
        st.download_button(
            "💾 Excel'i İndir",
            data=st.session_state["_yedek_data"],
            file_name=st.session_state["_yedek_ad"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="yedek_indir",
        )
        with st.expander("Tablo özeti", expanded=False):
            import pandas as pd
            st.dataframe(pd.DataFrame(_ozet, columns=["Tablo", "Kayıt"]),
                         hide_index=True, use_container_width=True)
