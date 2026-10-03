"""
KAYRAN — Yönetim Panosu (P&L)
Dönemsel kâr/zarar: Ciro − COGS − Destekler = Net Kâr.
 • Gelir/maliyet → Satış modülünden (ciro, paçal COGS).
 • Destekler → Ref no harcamalarından, türlere göre kırılımlı.
Tüm tutarlar USD. TL cinsi destekler güncel kurla yaklaşık çevrilir.
"""
from shared.tasarim import renk as trenk  # aktif temanın rengi (hex)
from shared.tasarim import tr_sayi  # TR sayı biçimi (1.234,56)
import streamlit as st
from shared.utils import secim_serit
import datetime as dt
from yonetim_hesap import pnl_topla, Kaynak as _PnlKaynak, onceki_ay, ay_tarihleri


def _usd(x):
    try:
        return f"${tr_sayi(float(x))}"
    except Exception:
        return "$0"


def _pct(x):
    try:
        return f"%{tr_sayi(float(x), 1)}"
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


GIDER_AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
               "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

# ═════════════════════════════════════════════════════════════════════
# AY KAPANIŞ RAPORU — tek fonksiyonda dönem P&L + kanal + ürün + kıyas
# ═════════════════════════════════════════════════════════════════════
def ay_pnl_hesapla(yil, ay_idx, kaynak=None, bugun=None):
    """Bir ayın P&L'i — Yönetim Panosu ile AYNI hesap (yonetim_hesap.pnl_topla).
    Eskiden ayrı kodla hesaplanıyordu: alınan desteği eklemiyor, kur kuralı
    farklıydı; aynı ay için pano ile rapor farklı net kâr verebiliyordu."""
    bas, bit = ay_tarihleri(yil, ay_idx)
    r = pnl_topla(yil, GIDER_AYLAR[ay_idx], bas, bit, kaynak or _PnlKaynak(), bugun=bugun or _bugun())
    r["ay"] = GIDER_AYLAR[ay_idx]
    r["kanal"] = sorted(
        [{"kanal": kn, "ciro": float(v.get("ciro", 0) or 0), "adet": int(v.get("adet", 0) or 0),
          "net_kar": float(v.get("net_kar", 0) or 0),
          "marj": (v.get("net_kar", 0) / v.get("ciro", 1) * 100) if v.get("ciro") else 0}
         for kn, v in (r["kanal"] or {}).items()],
        key=lambda x: -x["ciro"])[:12]
    _ur = [{"sku": su, "urun": (v.get("urun_adi") or su)[:34], "adet": int(v.get("adet", 0) or 0),
            "ciro": float(v.get("ciro", 0) or 0), "net_kar": float(v.get("net_kar", 0) or 0)}
           for su, v in (r["urun"] or {}).items()]
    r["urun_top"] = sorted(_ur, key=lambda x: -x["net_kar"])[:8]
    r["urun_zarar"] = [u for u in sorted(_ur, key=lambda x: x["net_kar"])[:8] if u["net_kar"] < 0]
    return r


def _bugun():
    """İstanbul günü (sunucu UTC: ayın ilk gecesi 00–03 arası önceki ayı açıyordu)."""
    try:
        from shared.utils import tr_today
        return tr_today()
    except Exception:  # noqa: BLE001
        return dt.date.today()


def _tr_tarih(v, saat=False):
    from kayranpm.urun_hesap import tarih_tr
    return tarih_tr(v, saat=saat)


def _toplam_aktif_html(snap, RENK, buyuk=False):
    """Toplam aktifler kalemleri — kâr görünürlüğü olmayan özet ile panodaki
    pencere AYNI fonksiyonu kullanır (eskiden iki kopya vardı)."""
    _t = float(snap.get("toplam", 0) or 0)
    _k = float(snap.get("kur", 0) or 0)
    _kal = [("📦 Stok değeri (×1.20)", snap.get("stok", 0), "+"),
            ("🚢 İthalat (ödenen)", snap.get("ithalat", 0), "+"),
            ("🏦 Banka (USD eşd.)", snap.get("banka", 0), "+"),
            ("📥 Cari alacak", snap.get("alacak", 0), "+"),
            ("➕ Manuel ekleme", snap.get("manuel_ekle", 0), "+"),
            ("📤 Cari borç", snap.get("borc", 0), "−"),
            ("🧾 Çekler", snap.get("cek", 0), "−"),
            ("➖ Manuel çıkarma", snap.get("manuel_cikar", 0), "−")]
    fs = "13px" if buyuk else "11px"
    satirlar = "".join(
        f'<div style="display:flex;justify-content:space-between;padding:{"5px" if buyuk else "4px"} 12px;margin:2px 0;'
        f'border-radius:6px;background:color-mix(in srgb,var(--k-metin) 3%,transparent)">'
        f'<span style="color:{RENK["metin"]};font-size:{fs}">{a}</span>'
        f'<span style="color:{(RENK["yesil"] if y == "+" else RENK["kirmizi"])};font-size:{fs};'
        f'font-weight:700;font-family:JetBrains Mono,monospace">{y} &#36;{tr_sayi(float(v or 0))}</span></div>'
        for a, v, y in _kal if float(v or 0))
    return (f'<div style="text-align:center;padding:{"10px 0 14px" if buyuk else "8px 0 12px"};margin-bottom:8px;'
            f'border-bottom:1px solid color-mix(in srgb,var(--k-metin) 8%,transparent)">'
            f'<div style="font-size:23px;font-weight:700;color:var(--k-metin);'
            f'font-family:JetBrains Mono,monospace;letter-spacing:-1px">&#36;{tr_sayi(_t)}</div>'
            f'<div style="font-size:{fs};color:{RENK["mor2"]};font-family:JetBrains Mono,monospace;'
            f'margin-top:4px">≈ ₺{tr_sayi(_t * _k)} · kur {_k:g}</div></div>' + satirlar)


def _veri_durumu(eksikler):
    """P&L şeridinin altı: hangi bileşen eksik? Eskiden okunamayan bileşen sessizce
    0 sayılıyor, net kâr olduğundan yüksek görünüyordu."""
    if not eksikler:
        st.markdown('<div style="color:var(--k-yesil);font-size:12px;margin:0 2px 10px">'
                    '✓ Tüm bileşenler okundu · gider tablosu dönem için tam</div>', unsafe_allow_html=True)
        return
    st.warning("**Net kâr eksik veriyle hesaplandı — olduğundan farklı olabilir:**\n\n"
               + "\n".join(f"- {e}" for e in eksikler))


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
    # ── Sayfa gövdesi: KENDİ İÇİNDE YENİLENEN PARÇA (st.fragment) ───────────
    # HIZ: Sayfadaki filtre, seçim kutusu, sekme ya da onay kutusu değişince
    # yalnız bu gövde yeniden çizilir; üst menü, sol menü, oturum kontrolü ve
    # ortak CSS yeniden çalışmaz. Kayıt sonrası st.rerun() çağrıları ESKİSİ
    # GİBİ tüm sayfayı yeniler (Streamlit 1.64'te parça içi st.rerun() tam
    # yenilemedir). Blok ile dış kapsamın paylaştığı değişkenler nonlocal ile
    # aynen korunur (otomatik hesaplandı; tests/test_parca.py denetler).
    @st.fragment
    def _sayfa_parcasi():
        from shared.ui import RENK, pencere_css, pencere, pencere_grid, bos_durum, sayfa_baslik, tablo_h
        # KÂR GİZLEME: Kâr/zarar analizleri (ciro−COGS−destek−gider) girilmemiş
        # destek ve masraflar nedeniyle henüz doğru sonuç vermiyor → yalnız yetkiliye.
        # ANCAK Toplam Aktifler kâr hesabı DEĞİL; yüklenen stok/banka/cari verisinden
        # gelir ve doğrudur → herkese gösterilir.
        from shared.kar_gizle import kar_gorunur, uyari_ciz
        st.markdown(pencere_css(), unsafe_allow_html=True)
        if not kar_gorunur():
            st.markdown(sayfa_baslik("📊", "Yönetim Panosu", "Toplam Aktifler özeti"),
                        unsafe_allow_html=True)
            uyari_ciz()
            try:
                from kayranacc.database import get_ayar
                _s = get_ayar("toplam_aktif_snapshot")
            except Exception:
                _s = None
            if not _s:
                st.markdown(pencere("💎 Toplam aktifler", RENK["mor"],
                                    bos_durum("Muhasebe → Toplam Aktifler işlenince burada görünür")),
                            unsafe_allow_html=True)
                return
            st.markdown(pencere("💎 Toplam aktifler", RENK["mor"], _toplam_aktif_html(_s, RENK, buyuk=True),
                                rozet=_tr_tarih(_s.get("tarih"), saat=True), yukseklik=320),
                        unsafe_allow_html=True)
            return
        st.markdown(sayfa_baslik("📊", "Yönetim Panosu", "Ciro − COGS − Destekler − Giderler = Net Kâr · tüm tutarlar USD"),
                    unsafe_allow_html=True)

        # ── Dönem seçimi — tek kompakt satır ──
        _bg = _bugun()
        c1, c2, c3 = st.columns([0.8, 1.6, 1.6])
        with c1:
            _yil = st.selectbox("Yıl", list(range(_bg.year + 1, _bg.year - 4, -1)), index=1)
        with c2:
            _gor = secim_serit("Görünüm", ["Aylık", "Çeyreklik", "Yıllık"], index=2)
        with c3:
            if _gor == "Aylık":
                _donem = st.selectbox("Ay", GIDER_AYLAR, index=min(_bg.month - 1, 11))
            elif _gor == "Çeyreklik":
                _donem = secim_serit("Çeyrek", ["Q1", "Q2", "Q3", "Q4"], index=0)
            else:
                _donem = "Tüm Yıl"
                st.markdown('<div style="color:var(--k-silik);font-size:13px;margin-top:32px">Tüm yıl görünümü</div>',
                            unsafe_allow_html=True)
        baslangic, bitis = _donem_tarih(_yil, _donem)

        # ── P&L — TEK HESAP (yonetim_hesap.pnl_topla; Ay Kapanış Raporu da bunu kullanır) ──
        try:
            _oturum_kur = float(st.session_state.get("kur") or 0)
        except Exception:
            _oturum_kur = 0.0
        _r = pnl_topla(_yil, _donem, baslangic, bitis, _PnlKaynak(_oturum_kur), bugun=_bg)
        ciro, cogs, brut, brut_marj = _r["ciro"], _r["cogs"], _r["brut"], _r["brut_marj"]
        ciro_brut, iade_tutar, kanal = _r["ciro_brut"], _r["iade_tutar"], _r["kanal"]
        toplam_destek, _tur_usd, gider_usd = _r["destek"], _r["tur_usd"], _r["gider"]
        alinan_destek_usd, net_kar, net_marj = _r["alinan"], _r["net_kar"], _r["marj"]
        _tl_uyari = _r["tl_cevrildi"]
        _nrenk = RENK["yesil"] if net_kar >= 0 else RENK["kirmizi"]

        # ═════════ P&L DENKLEM ŞERİDİ — kartlar + formül tek bantta ═════════
        def _hucre(etiket, deger, alt, renk, vurgulu=False):
            _st = ("background:" + renk + "14;border:1px solid " + renk + "45;border-radius:12px;"
                   if vurgulu else "")
            _vf = "22px" if vurgulu else "18px"
            _vr = renk if vurgulu else RENK["metin"]
            return (f'<div style="flex:1;min-width:116px;text-align:center;padding:12px 8px;{_st}">'
                    f'<div style="font-size:12px;color:{RENK["soluk"]};'
                    f'font-weight:500;margin-bottom:4px">{etiket}</div>'
                    f'<div style="color:{_vr};font-size:{_vf};font-weight:700;'
                    f'font-family:JetBrains Mono,monospace;line-height:1.1">{deger}</div>'
                    f'<div style="color:{renk};font-size:11px;font-weight:600;margin-top:4px">{alt}</div></div>')

        def _op(s):
            return (f'<div style="display:flex;align-items:center;color:var(--k-silik);font-size:19px;'
                    f'font-weight:700;padding:0 2px">{s}</div>')

        _ciro_alt = (f"brüt {_usd(ciro_brut)} − iade {_usd(iade_tutar)}" if iade_tutar > 0 else "net satış")
        st.markdown(
            f'<div style="display:flex;align-items:stretch;gap:4px;flex-wrap:wrap;'
            f'background:linear-gradient(180deg,var(--k-yuzey2),var(--k-yuzey1));border:1px solid color-mix(in srgb,var(--k-soluk) 14%,transparent);'
            f'border-radius:16px;padding:12px 12px;margin:6px 0 4px">'
            + _hucre("Ciro", _usd(ciro), _ciro_alt, RENK["mor2"])
            + _op("−") + _hucre("COGS", _usd(cogs), "ürün maliyeti", RENK["amber"])
            + _op("=") + _hucre("Brüt Kâr", _usd(brut), f"marj {_pct(brut_marj)}", RENK["cyan"])
            + _op("−") + _hucre("Destekler", _usd(toplam_destek), "ref no destekleri", RENK["pembe"])
            + _op("−") + _hucre("Giderler", _usd(gider_usd), "işletme (TL→USD)", RENK["amber2"])
            + (_op("+") + _hucre("Alınan destek", _usd(alinan_destek_usd), "sellout/mkt/rebate", trenk("yesil"))
               if alinan_destek_usd else "")
            + _op("=") + _hucre("Net kâr", _usd(net_kar), f"net marj {_pct(net_marj)}", _nrenk, vurgulu=True)
            + '</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="color:var(--k-silik);font-size:11px;margin:0 2px 4px">📅 '
                    f'{_tr_tarih(baslangic)} – {_tr_tarih(bitis)}'
                    + (' · ℹ️ TL tutarlar o günün kuruyla çevrildi (kur yoksa güncel kur)' if _tl_uyari else '')
                    + '</div>', unsafe_allow_html=True)
        _veri_durumu(_r["eksikler"])

        # ═════════ ORTA GRID — 4 scroll'lu pencere ═════════
        def _bar_satir(ad, tutar_str, oran, renk, sag_ek=""):
            _w = max(2, min(100, oran))
            return (f'<div style="padding:4px 12px;margin:3px 0;border-radius:6px;background:color-mix(in srgb,var(--k-metin) 3%,transparent)">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">'
                    f'<span style="color:{RENK["metin"]};font-size:13px;font-weight:600">{ad}</span>'
                    f'<span style="color:{RENK["metin"]};font-size:13px;font-weight:700;'
                    f'font-family:JetBrains Mono,monospace">{tutar_str}'
                    f'<span style="color:{RENK["silik"]};font-weight:400"> {sag_ek}</span></span></div>'
                    f'<div style="height:4px;border-radius:2px;background:color-mix(in srgb,var(--k-metin) 5%,transparent)">'
                    f'<div style="height:4px;border-radius:2px;width:{_w:.1f}%;background:{renk}"></div></div></div>')

        # Pencere 1 — Destek kırılımı
        if _tur_usd:
            _dmax = max(_tur_usd.values()) or 1
            _d_html = "".join(
                _bar_satir(t, f"${tr_sayi(v)}", v / _dmax * 100, RENK["pembe"],
                           sag_ek=(f"· %{tr_sayi((v / toplam_destek * 100))}" if toplam_destek else ""))
                for t, v in sorted(_tur_usd.items(), key=lambda x: -x[1]))
        else:
            _d_html = bos_durum("Bu dönemde destek/harcama kaydı yok")
        _p_destek = pencere("🎯 Destek kırılımı", RENK["pembe"], _d_html,
                            rozet=_usd(toplam_destek), yukseklik=230)

        # Pencere 2 — Kanal bazında satış
        if kanal:
            _kmax = max((v.get("ciro", 0) for v in kanal.values()), default=1) or 1
            _k_html = "".join(
                _bar_satir(kn, _usd(v.get("ciro", 0)), v.get("ciro", 0) / _kmax * 100, RENK["mor"],
                           sag_ek=f"· {tr_sayi(int(v.get('adet', 0)))} ad · NK {_usd(v.get('net_kar', 0))}")
                for kn, v in sorted(kanal.items(), key=lambda x: -x[1].get("ciro", 0)))
        else:
            _k_html = bos_durum("Bu dönemde satış kaydı yok")
        _p_kanal = pencere("🛒 Kanal bazında satış", RENK["mor"], _k_html,
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
                _bar_satir("Sabit", f"₺{tr_sayi(_sabit)}", _sabit / _gmax * 100, trenk("mavi"),
                           sag_ek=(f"· %{tr_sayi((_sabit / _topgider * 100))}" if _topgider else ""))
                + _bar_satir("Değişken", f"₺{tr_sayi(_degisken)}", _degisken / _gmax * 100, trenk("amber"),
                             sag_ek=(f"· %{tr_sayi((_degisken / _topgider * 100))}" if _topgider else ""))
                + _bar_satir("Yarı Değişken", f"₺{tr_sayi(_yari)}", _yari / _gmax * 100, trenk("mor"),
                             sag_ek=(f"· %{tr_sayi((_yari / _topgider * 100))}" if _topgider else ""))
                + f'<div style="display:flex;justify-content:space-between;padding:8px 12px;margin-top:4px;'
                  f'border-top:1px solid color-mix(in srgb,var(--k-metin) 8%,transparent)">'
                  f'<span style="color:{RENK["soluk"]};font-size:12px;font-weight:700">Toplam ({_donem})</span>'
                  f'<span style="color:{RENK["kirmizi"]};font-size:13px;font-weight:700;'
                  f'font-family:JetBrains Mono,monospace">₺{tr_sayi(_topgider)}</span></div>'
                + f'<div style="color:{RENK["silik"]};font-size:11px;padding:4px 12px">'
                  f'≈ {_usd(gider_usd)} · yüklenme: {_tr_tarih(_gider.get("tarih"))}</div>')
        else:
            _g_html = bos_durum(f"{_yil} gider tablosu yüklenmedi — aşağıdan yükleyebilirsin")
        _p_gider = pencere("🧾 İşletme giderleri", RENK["kirmizi"], _g_html,
                           rozet=str(_yil), yukseklik=300)

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
            _a_html = _toplam_aktif_html(_snap, RENK)
            _a_rozet = _tr_tarih(_snap.get("tarih"), saat=True)
        # 8 kalem + başlık bloğu kaydırmasız sığsın diye 300px; komşu gider
        # penceresiyle AYNI değer — pencere_grid stretch ile boyları eşitliyor.
        _p_aktif = pencere("💎 Toplam aktifler", RENK["mor"], _a_html, rozet=_a_rozet, yukseklik=300)

        st.markdown(pencere_grid(_p_gider, _p_aktif), unsafe_allow_html=True)

        # ═════════ ARAÇLAR — 4 pencere butonu ═════════
        @st.dialog(f"📤 {_yil} Gider Tablosu Yükle", width="large")
        def _dlg_gider_yukle():
            from shared.yukleme_takvimi import serit as _yt_serit
            _yt_serit("gider_tablosu")
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
                            _kayit = {"kat": _katp, "detay": _detayp, "tarih": _bugun().isoformat()}
                            if _sa3:
                                _sa3(_gider_anahtar, _kayit)
                                from shared.yukleme_takvimi import _temizle as _yt_tazele
                                _yt_tazele()                      # geri sayım yeni ayı görsün
                            # toast: rerun'dan önce basılan st.success görünmeden kayboluyordu
                            st.toast(f"✅ {len(_detayp)} kalem · yıllık ₺{tr_sayi(_yillik_top)} kaydedildi")
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
            # Ham sayı (metin verilince sıralama bozuluyordu); "Σ" satırı alt bilgide sabit
            for _knm in ["Sabit", "Değişken", "Yarı Değişken"]:
                _vv = _g12(_knm)
                _row = {"Kategori": _knm}
                for _idx, _a in enumerate(GIDER_AYLAR):
                    _row[_a] = round(_vv[_idx], 2)
                _row["Yıllık"] = round(sum(_vv), 2)
                _satirlar.append(_row)
            _trow = {"Kategori": "Σ Toplam"}
            for _idx, _a in enumerate(GIDER_AYLAR):
                _trow[_a] = round(_g12('Sabit')[_idx] + _g12('Değişken')[_idx] + _g12('Yarı Değişken')[_idx], 2)
            _trow["Yıllık"] = round(sum(_g12('Sabit')) + sum(_g12('Değişken')) + sum(_g12('Yarı Değişken')), 2)
            _satirlar.append(_trow)
            st.dataframe(_pd_g.DataFrame(_satirlar), hide_index=True, use_container_width=True,
                         height=tablo_h(len(_satirlar)))
            st.caption(f"Yüklenme: {_tr_tarih(_gider.get('tarih'))} · Tutarlar TL · yatay kaydırılabilir.")

        @st.dialog("🗂️ Değişiklik Günlüğü (Audit Log)", width="large")
        def _dlg_audit():
            _audit_render()

        @st.dialog("💾 Veri Yedekleme", width="large")
        def _dlg_yedek():
            _yedek_render()

        @st.dialog("📄 Ay Kapanış Raporu", width="large")
        def _dlg_ay_rapor():
            from shared.ui import RENK
            _bgr = _bugun()
            _vy, _vay = onceki_ay(_bgr)          # Ocak'ta önceki yılın Aralık'ı
            _c1, _c2 = st.columns(2)
            _yillar = list(range(_bgr.year, _bgr.year - 4, -1))
            _ryil = _c1.selectbox("Yıl", _yillar, index=_yillar.index(_vy), key="ayrap_yil")
            _ray = _c2.selectbox("Ay", GIDER_AYLAR, index=_vay, key="ayrap_ay")
            _ai = GIDER_AYLAR.index(_ray)
            # Panoyla AYNI kaynak (aynı kur yedeği) — yoksa TL kalemler farklı çevrilirdi
            try:
                _okur = float(st.session_state.get("kur") or 0)
            except Exception:
                _okur = 0.0
            _kyn = _PnlKaynak(_okur)
            with st.spinner(f"{_ray} {_ryil} kapanışı hesaplanıyor…"):
                _r = ay_pnl_hesapla(_ryil, _ai, kaynak=_kyn)
                # Önceki ay kıyas
                _pai = _ai - 1
                _pyil = _ryil
                if _pai < 0:
                    _pai = 11
                    _pyil = _ryil - 1
                _rp = ay_pnl_hesapla(_pyil, _pai, kaynak=_kyn)

            def _delta(now, prev, tersi=False):
                if not prev:
                    return ""
                _d = (now - prev) / abs(prev) * 100
                _ok = "▲" if _d >= 0 else "▼"
                _iyi = (_d >= 0) if not tersi else (_d < 0)
                _c = RENK["yesil"] if _iyi else RENK["kirmizi"]
                return f'<span style="color:{_c};font-size:11px;font-weight:700"> {_ok}%{tr_sayi(abs(_d))}</span>'

            _nr = RENK["yesil"] if _r["net_kar"] >= 0 else RENK["kirmizi"]
            # Başlık + 4 büyük metrik (önceki aya kıyaslı)
            st.markdown(
                f'<div style="font-size:14px;font-weight:700;color:{RENK["metin"]};margin-bottom:0px">'
                f'{_r["ay"]} {_r["yil"]} — Kapanış</div>'
                f'<div style="color:{RENK["silik"]};font-size:11px;margin-bottom:8px">'
                f'{_tr_tarih(_r["bas"])} – {_tr_tarih(_r["bit"])} · önceki ay ({_rp["ay"]}) ile kıyaslı · tüm tutarlar USD</div>'
                f'<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px">'
                + "".join(
                    f'<div style="flex:1;min-width:130px;text-align:center;padding:12px 8px;'
                    f'background:linear-gradient(180deg,var(--k-yuzey2),var(--k-yuzey1));border:1px solid {c}2E;border-radius:12px;box-shadow:0 1px 2px rgba(0,0,0,0.30)">'
                    f'<div style="font-size:12px;color:{RENK["soluk"]};'
                    f'font-weight:500;margin-bottom:4px">{lbl}</div>'
                    f'<div style="color:{c};font-size:19px;font-weight:700;'
                    f'font-family:JetBrains Mono,monospace">{val}{dl}</div></div>'
                    for lbl, val, c, dl in [
                        ("Ciro", _usd(_r["ciro"]), RENK["mor2"], _delta(_r["ciro"], _rp["ciro"])),
                        ("COGS", _usd(_r["cogs"]), RENK["amber"], _delta(_r["cogs"], _rp["cogs"], tersi=True)),
                        ("Net Kâr", _usd(_r["net_kar"]), _nr, _delta(_r["net_kar"], _rp["net_kar"])),
                        ("Marj", f'%{tr_sayi(_r["marj"], 1)}', _nr, ""),
                    ])
                + '</div>', unsafe_allow_html=True)

            # P&L akış satırı
            st.markdown(
                f'<div style="background:color-mix(in srgb,var(--k-metin) 2%,transparent);border:1px solid color-mix(in srgb,var(--k-metin) 7%,transparent);'
                f'border-radius:10px;padding:12px 16px;margin-bottom:16px;font-family:JetBrains Mono,monospace;'
                f'font-size:13px;color:var(--k-mavi)">'
                f'{_usd(_r["ciro"])} <span style="color:var(--k-silik)">ciro</span> − '
                f'{_usd(_r["cogs"])} <span style="color:var(--k-silik)">cogs</span> − '
                f'{_usd(_r["destek"])} <span style="color:var(--k-silik)">destek</span> − '
                f'{_usd(_r["gider"])} <span style="color:var(--k-silik)">gider</span> '
                + (f'+ {_usd(_r["alinan"])} <span style="color:var(--k-silik)">alınan destek</span> ' if _r["alinan"] else '')
                + f'= '
                f'<b style="color:{_nr}">{_usd(_r["net_kar"])} net kâr</b></div>',
                unsafe_allow_html=True)

            _veri_durumu(_r["eksikler"])
            import pandas as _pd
            if _r["kanal"]:
                st.markdown("**Kanal Kırılımı**")
                st.dataframe(_pd.DataFrame([{
                    "Kanal": k["kanal"], "Adet": k["adet"], "Ciro": round(k["ciro"], 2),
                    "Net Kâr": round(k["net_kar"], 2), "Marj (%)": round(k["marj"], 1),
                } for k in _r["kanal"]]), hide_index=True, use_container_width=True,
                    height=min(300, 40 + 35 * len(_r["kanal"])))

            _cc1, _cc2 = st.columns(2)
            if _r["urun_top"]:
                with _cc1:
                    st.markdown("**En Kârlı Ürünler**")
                    st.dataframe(_pd.DataFrame([{
                        "Ürün": u["urun"], "Adet": u["adet"], "Net Kâr": round(u["net_kar"], 2),
                    } for u in _r["urun_top"]]), hide_index=True, use_container_width=True,
                        height=min(260, 40 + 35 * len(_r["urun_top"])))
            if _r["urun_zarar"]:
                with _cc2:
                    st.markdown("**Zarardaki Ürünler**")
                    st.dataframe(_pd.DataFrame([{
                        "Ürün": u["urun"], "Adet": u["adet"], "Net Kâr": round(u["net_kar"], 2),
                    } for u in _r["urun_zarar"]]), hide_index=True, use_container_width=True,
                        height=min(260, 40 + 35 * len(_r["urun_zarar"])))

            # İndirilebilir özet (metin)
            _txt = (f"{_r['ay']} {_r['yil']} KAPANIŞ ÖZETİ\n"
                    f"{'='*40}\n"
                    f"Dönem: {_tr_tarih(_r['bas'])} – {_tr_tarih(_r['bit'])}\n\n"
                    f"Ciro       : {_usd(_r['ciro'])}\n"
                    f"COGS       : {_usd(_r['cogs'])}\n"
                    f"Brüt Kâr   : {_usd(_r['brut'])}\n"
                    f"Destekler  : {_usd(_r['destek'])}\n"
                    f"Giderler   : {_usd(_r['gider'])}\n"
                    f"Alınan dst.: {_usd(_r['alinan'])}\n"
                    f"NET KÂR    : {_usd(_r['net_kar'])}  (marj %{tr_sayi(_r['marj'], 1)})\n\n"
                    f"KANAL KIRILIMI\n" +
                    "\n".join(f"  {k['kanal'][:30]:30s} {_usd(k['ciro']):>12s}  "
                              f"NK {_usd(k['net_kar']):>10s}  %{tr_sayi(k['marj'], 1)}"
                              for k in _r["kanal"]))
            st.download_button("Özeti indir (.txt)", _txt.encode("utf-8"),
                               f"kapanis_{_r['yil']}_{_ai+1:02d}.txt", "text/plain",
                               use_container_width=True, key="ayrap_dl", icon=":material/download:")

        _bt = st.columns(5)
        if _bt[0].button(f"Gider Yükle ({_yil})", key="btn_yon_gider", use_container_width=True, icon=":material/upload:"):
            _dlg_gider_yukle()
        if _bt[1].button("Aylık Gider", key="btn_yon_aylik", use_container_width=True, icon=":material/calendar_month:"):
            _dlg_gider_aylik()
        if _bt[2].button("Ay Kapanış Raporu", key="btn_yon_ayrapor", use_container_width=True, icon=":material/description:"):
            _dlg_ay_rapor()
        if _bt[3].button("Değişiklik Günlüğü", key="btn_yon_audit", use_container_width=True, icon=":material/folder_open:"):
            _dlg_audit()
        if _bt[4].button("Yedekleme", key="btn_yon_yedek", use_container_width=True, icon=":material/save:"):
            _dlg_yedek()

    _sayfa_parcasi()


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
        "Zaman": _tr_tarih(l.get("zaman"), saat=True),
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
# İş verisi yedeklenir. ŞİFRE ve oturum/geçici/log tabloları GÜVENLİK için hariç.
# tests/test_yonetim_yeni.py kodda kullanılan HER tablonun bu iki listeden birinde
# olmasını denetler (Ekim 2026: iadeler, tahsilatlar, e-Defter… hiç yedeklenmiyordu).
YEDEK_TABLOLAR = [
    # Ürün / stok
    "urunler", "firma_stok", "stok_yas", "yoldaki_urunler", "stok_hareketleri",
    "depo_manuel_takip", "depo_sevk_log", "happylife_stok", "sku_eslesme",
    # Kampanya / ref / destek
    "kampanyalar", "kampanya_urunler", "ref_kayitlari", "ref_butce", "ref_firmalar", "ref_no",
    "alinan_destekler",
    # İthalat
    "ithalat_dosyalari", "ithalat_kalemleri",
    # Satış
    "satislar", "iadeler",
    # Muhasebe
    "odemeler", "bankalar", "cekler", "virmanlar", "haftalar", "tahsilatlar", "kur_gunluk",
    "aktif_manuel_kalemler",
    # e-Defter
    "edefter_ayarlar", "edefter_donem_kilit", "edefter_fisler", "edefter_fis_satirlari", "edefter_hesap_plani",
    # Teknik servis
    "ts_kayitlar", "ts_gecmis",
    # Hesap Makinesi (prim ödeme geçmişi — tek tırnakla yazıldığı için denetimden kaçıyordu)
    "prim_gecmis",
    # Ortak
    "siparis_onerileri", "talepler", "gorevler", "bildirimler",
    "sistem_ayarlari", "pm_ayarlar", "kullanici_yetkileri", "kullanici_tercih", "gunluk_giris",
]
# Bilerek HARİÇ: şifre, oturum, geçici önbellek, loglar; v_ / mv_ ile başlayanlar
# veritabanı GÖRÜNÜMÜ (veri değil, tablolardan hesaplanır).
YEDEK_HARIC = [
    "kullanici_sifreler", "kullanici_durum", "giris_denemeleri",
    "aktif_excel_verileri", "audit_log", "hata_kayitlari",
    "cop_kutusu",          # silinenlerin 30 günlük kopyası; gece yedeği asıl tabloları zaten alıyor
    "v_destek_donem", "v_satis_pnl", "mv_gunluk_pnl", "mv_kanal_ay_pnl",
]


def _tum_satirlar(sb, tablo, sayfa=1000):
    """Bir tablonun TÜM satırları. Supabase tek sorguda en fazla 1000 satır döndürür;
    yedek sayfalamayı yapan sarmalayıcıyı atlayan ham bağlantıyla okuduğu için
    1000'i aşan tablolar sessizce kesiliyordu."""
    out, bas = [], 0
    while True:
        parca = sb.table(tablo).select("*").range(bas, bas + sayfa - 1).execute().data or []
        out.extend(parca)
        if len(parca) < sayfa:
            return out
        bas += sayfa


def _yedek_olustur():
    """Tüm iş verisini tek çok-sayfalı Excel (BytesIO bytes) olarak döndürür.
    Her tablo ayrı sayfa. Hata olan tablo boş sayfa olarak geçer."""
    import io
    import pandas as pd
    from shared.audit import _raw_client
    sb = _raw_client()
    ozet, hatali = [], []
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for tablo in YEDEK_TABLOLAR:
            try:
                rows = _tum_satirlar(sb, tablo)
            except Exception:
                rows = []
                hatali.append(tablo)
            df = pd.DataFrame(rows) if rows else pd.DataFrame()
            # Excel sayfa adı en fazla 31 karakter
            df.to_excel(w, sheet_name=tablo[:31], index=False)
            ozet.append((tablo, len(rows)))
    buf.seek(0)
    if hatali:
        ozet.append(("⚠️ okunamadı: " + ", ".join(hatali), 0))
    return buf.getvalue(), ozet


def _yedek_render():
    from datetime import datetime, timedelta
    st.caption("Tüm iş verisini tek bir Excel dosyasına indirir (her tablo ayrı sayfa). "
               "Şifreler ve geçici/oturum verileri güvenlik gereği yedeğe DAHİL EDİLMEZ.")
    if st.button("Yedeği Hazırla", key="yedek_hazirla", icon=":material/inventory_2:"):
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
        st.success(f"✅ Yedek hazır — {len(_ozet)} tablo, {tr_sayi(_toplam)} kayıt.")
        st.download_button(
            "Excel'i İndir",
            data=st.session_state["_yedek_data"],
            file_name=st.session_state["_yedek_ad"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="yedek_indir", icon=":material/save:"
        )
        with st.expander("Tablo özeti", expanded=False):
            import pandas as pd
            st.dataframe(pd.DataFrame(_ozet, columns=["Tablo", "Kayıt"]),
                         hide_index=True, use_container_width=True)
