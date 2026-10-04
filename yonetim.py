"""
KAYRAN — Yönetim Panosu (P&L)
Dönemsel kâr/zarar: Ciro − COGS − Destekler = Net Kâr.
 • Gelir/maliyet → Satış modülünden (ciro, paçal COGS).
 • Destekler → Ref no harcamalarından, türlere göre kırılımlı.
Tüm tutarlar USD. TL cinsi destekler güncel kurla yaklaşık çevrilir.
"""
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
    _kal = [("Stok değeri (×1.20)", snap.get("stok", 0), "+"),
            ("İthalat (ödenen)", snap.get("ithalat", 0), "+"),
            ("Banka (USD eşd.)", snap.get("banka", 0), "+"),
            ("Cari alacak", snap.get("alacak", 0), "+"),
            ("Manuel ekleme", snap.get("manuel_ekle", 0), "+"),
            ("Cari borç", snap.get("borc", 0), "−"),
            ("Çekler", snap.get("cek", 0), "−"),
            ("Manuel çıkarma", snap.get("manuel_cikar", 0), "−")]
    fs = "13px" if buyuk else "11px"
    satirlar = "".join(
        f'<div style="display:flex;justify-content:space-between;padding:{"5px" if buyuk else "4px"} 12px;margin:2px 0;'
        f'border-radius:6px;background:color-mix(in srgb,var(--k-metin) 3%,transparent)">'
        f'<span style="color:{RENK["metin"]};font-size:{fs}">{a}</span>'
        f'<span style="color:{(RENK["yesil"] if y == "+" else RENK["kirmizi"])};font-size:{fs};'
        f'font-weight:700;font-variant-numeric:tabular-nums">{y} &#36;{tr_sayi(float(v or 0))}</span></div>'
        for a, v, y in _kal if float(v or 0))
    return (f'<div style="text-align:center;padding:{"10px 0 14px" if buyuk else "8px 0 12px"};margin-bottom:8px;'
            f'border-bottom:1px solid color-mix(in srgb,var(--k-metin) 8%,transparent)">'
            f'<div style="font-size:23px;font-weight:700;color:var(--k-metin);'
            f'font-variant-numeric:tabular-nums;letter-spacing:-1px">&#36;{tr_sayi(_t)}</div>'
            f'<div style="font-size:{fs};color:{RENK["mor2"]};font-variant-numeric:tabular-nums;'
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
    # Biçim içerikten (pandas): .xls adlı .xlsx içerik de okunur (eskiden ada bakılıyordu)
    eng = None
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


def _oturum_kuru():
    try:
        return float(st.session_state.get("kur") or 0)
    except Exception:  # noqa: BLE001
        return 0.0


@st.cache_data(ttl=600, show_spinner=False)
def _pnl_onbellekli(yil, donem, bas, bit, aylar, kur):
    """Kıyas dönemleri (önceki dönem, geçen yıl): pano ile AYNI hesap ve kaynak."""
    return pnl_topla(yil, donem, bas, bit, _PnlKaynak(kur), bugun=_bugun(), aylar=tuple(aylar))


@st.cache_data(ttl=900, show_spinner=False)
def _ay_ozeti(yil, ay_idx, kur):
    """12 aylık trend için bir ayın özeti (yalnız toplamlar)."""
    bas, bit = ay_tarihleri(yil, ay_idx)
    r = pnl_topla(yil, GIDER_AYLAR[ay_idx], bas, bit, _PnlKaynak(kur), bugun=_bugun())
    return {k: float(r.get(k, 0) or 0) for k in ("ciro", "cogs", "brut", "destek", "gider", "alinan",
                                                  "net_kar", "marj")}


def _on_isit(yil, donem, bugun, kur, ozet=True):
    """Hızlandırma (Ekim 2026): dönem hesabından ÖNCE ortak okumalar (satış, iade, kur) aynı anda
    ısıtılır; Özet'te kıyas dönemleri ve 12 aylık trend de arka planda hesaplanmaya başlar, ana dönem
    bu arada hesaplanır. Hepsi önbellekli fonksiyonlar: sayfa aynı çağrıları yaptığında sonuç hazır.
    Eskiden ana dönem, iki kıyas ve trend sırayla, her biri 5-6 sıralı istekle hesaplanıyordu.
    Ortak okumalar önce: 12 iş parçacığı aynı anda boş önbelleğe çarpıp tabloyu 12 kez indirmesin.
    Döner: bekle() — kıyas/trend işlerinin bitmesini bekler."""
    from shared.paralel import hepsi, basla
    from satis.database import _tum_satislar_yalin, _tum_iadeler, get_pacal_map
    from kayranacc.database import _tum_kurlar
    hepsi([_tum_satislar_yalin, _tum_iadeler, _tum_kurlar, get_pacal_map])
    if not ozet:
        return lambda: None
    from yonetim_pano import kiyas_donemleri, trend_aylari
    isler = [(_pnl_onbellekli, ky, kd, kb, kt, tuple(ka), kur)
             for _a, _e, ky, kd, kb, kt, ka in kiyas_donemleri(yil, donem, bugun)]
    isler += [(_ay_ozeti, y, i, kur) for y, i in trend_aylari(yil, donem, bugun)]
    return basla(isler)


def _trend(aylar, kur):
    """[(yıl, ay_idx, özet)] — 12 ay paralel hesaplanır (her ay ayrı önbellekte; geçmiş aylar
    sonraki açılışlarda veritabanına gitmez)."""
    import threading
    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
    ctx, sonuc = get_script_run_ctx(), {}

    def _calis(y, i):
        try:
            sonuc[(y, i)] = _ay_ozeti(y, i, kur)
        except Exception:  # noqa: BLE001
            sonuc[(y, i)] = None
    isler = [threading.Thread(target=_calis, args=(y, i)) for y, i in aylar]
    for t in isler:
        add_script_run_ctx(t, ctx)
        t.start()
    for t in isler:
        t.join()
    return [(y, i, sonuc.get((y, i))) for y, i in aylar]


def _cip(d, bos=""):
    """▲▼ yüzde çipi (iyi = yeşil, kötü = kırmızı)."""
    if not d:
        return bos
    renk = "yesil" if d["iyi"] else "kirmizi"
    ok = "▲" if d["oran"] >= 0 else "▼"
    return (f'<span style="display:inline-block;border-radius:999px;padding:0 7px;font-size:11px;font-weight:700;'
            f'font-variant-numeric:tabular-nums;color:var(--k-{renk});'
            f'background:color-mix(in srgb,var(--k-{renk}) 14%,transparent)">{ok} %{tr_sayi(abs(d["oran"]), 1)}</span>')


def _hucre(etiket, deger, alt, renk="metin", vurgulu=False):
    """P&L şeridi hücresi — ortak metrik kartıyla aynı dil: solda etiket, altında rakam
    (görünüm birliği #20, Ekim 2026; eskiden ortalanmış ve daktilo yazılıydı)."""
    _st = (f"background:color-mix(in srgb,var(--k-{renk}) 8%,var(--k-yuzey1));"
           f"border-color:color-mix(in srgb,var(--k-{renk}) 45%,transparent);" if vurgulu else "")
    return (f'<div style="flex:1;min-width:112px;padding:9px 12px;border-radius:10px;'
            f'border:1px solid var(--k-kenar);background:var(--k-yuzey1);{_st}">'
            f'<div style="font-size:12px;color:var(--k-soluk);white-space:nowrap">{etiket}</div>'
            f'<div style="color:var(--k-{renk if vurgulu else "metin"});font-size:19px;font-weight:600;'
            f'font-variant-numeric:tabular-nums;line-height:1.3;margin-top:2px;white-space:nowrap">{deger}</div>'
            f'<div style="font-size:11px;color:var(--k-silik);margin-top:3px;min-height:16px">{alt}</div></div>')


def _op(s):
    return (f'<div style="display:flex;align-items:center;color:var(--k-silik);font-size:18px;'
            f'font-weight:700;padding:0 1px">{s}</div>')


def _serit(r, k1):
    """P&L akışı: her kalemin altında önceki döneme göre değişim (k1: önceki dönem sonucu)."""
    from yonetim_pano import degisim as _dg

    def d(a, tersi=False):
        return _cip(_dg(r[a], k1.get(a) if k1 else None, tersi))
    _ciro_alt = d("ciro") or (f"iade −{_usd(r['iade_tutar'])}" if r.get("iade_tutar") else "net satış")
    h = (_hucre("Ciro", _usd(r["ciro"]), _ciro_alt)
         + _op("−") + _hucre("COGS", _usd(r["cogs"]), d("cogs", True) or "ürün maliyeti")
         + _op("=") + _hucre("Brüt kâr", _usd(r["brut"]), f"marj {_pct(r['brut_marj'])} {d('brut')}")
         + _op("−") + _hucre("Destekler", _usd(r["destek"]), d("destek", True) or "ref no destekleri")
         + _op("−") + _hucre("Giderler", _usd(r["gider"]), d("gider", True) or "işletme (TL→USD)"))
    if r.get("alinan"):
        h += _op("+") + _hucre("Alınan destek", _usd(r["alinan"]), d("alinan") or "sellout / mkt / rebate")
    renk = "yesil" if r["net_kar"] >= 0 else "kirmizi"
    h += _op("=") + _hucre("Net kâr", _usd(r["net_kar"]), f"marj {_pct(r['marj'])} {d('net_kar')}", renk, vurgulu=True)
    return f'<div style="display:flex;align-items:stretch;gap:5px;flex-wrap:wrap;margin:4px 0">{h}</div>'


def _kucuk_kartlar(trend):
    """Dört küçük trend kartı: ciro, brüt kâr, net kâr, net marj (son 12 ay)."""
    from yonetim_pano import kucuk_trend_svg, ay_etiketi
    dolu = [(y, i, o) for y, i, o in trend if o is not None]
    if len(dolu) < 2:
        return ""
    et = [ay_etiketi(y, i) for y, i, _o in dolu]
    kartlar = [("Ciro · aylık", "ciro", "mor", _usd), ("Brüt kâr · aylık", "brut", "cyan", _usd),
               ("Net kâr · aylık", "net_kar", "yesil", _usd), ("Net marj · aylık", "marj", "yesil", _pct)]
    html = ""
    for ad, k, renk, bicim in kartlar:
        v = [o[k] for _y, _i, o in dolu]
        rk = renk if not (k in ("net_kar", "marj") and v[-1] < 0) else "kirmizi"
        html += (f'<div style="flex:1;min-width:200px;background:var(--k-yuzey1);border:1px solid var(--k-kenar);'
                 f'border-radius:12px;padding:10px 12px">'
                 f'<div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px">'
                 f'<span style="font-size:12px;color:var(--k-soluk)">{ad}</span>'
                 f'<b style="font-weight:700;font-size:15px;font-variant-numeric:tabular-nums;color:var(--k-metin)">{bicim(v[-1])}</b></div>'
                 f'<div style="margin:6px 0 2px">{kucuk_trend_svg(v, et, rk, bicim)}</div>'
                 f'<div style="font-size:11px;color:var(--k-silik)">{et[0]} – {et[-1]}</div></div>')
    return f'<div style="display:flex;gap:10px;flex-wrap:wrap;margin:10px 0 4px">{html}</div>'


def _kanal_cubuklari(kanal):
    """Kanal katkısı: net kâr çubukları, ilk 7 kanal + kalanlar 'Diğer'."""
    from yonetim_pano import kanal_satirlari
    rows = kanal_satirlari(kanal)
    if not rows:
        return ""
    rows.sort(key=lambda x: -x["Net kâr ($)"])
    if len(rows) > 8:
        diger = rows[7:]
        rows = rows[:7] + [{"Kanal": f"Diğer ({len(diger)})", "Net kâr ($)": sum(x["Net kâr ($)"] for x in diger),
                            "Kâr payı (%)": sum(x["Kâr payı (%)"] for x in diger)}]
    mx = max(abs(x["Net kâr ($)"]) for x in rows) or 1
    h = ""
    for x in rows:
        nk = x["Net kâr ($)"]
        renk = "mor" if nk >= 0 else "kirmizi"
        h += (f'<div style="display:grid;grid-template-columns:minmax(90px,30%) 1fr;gap:10px;align-items:center;margin:5px 0" '
              f'title="{x["Kanal"]}: {_usd(nk)} · kâr payı %{tr_sayi(x["Kâr payı (%)"], 1)}">'
              f'<span style="font-size:13px;color:var(--k-metin);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'
              f'{x["Kanal"]}</span><div style="display:flex;align-items:center;gap:8px;min-width:0">'
              f'<div style="height:16px;border-radius:4px;width:{max(2, abs(nk) / mx * 70):.1f}%;'
              f'background:color-mix(in srgb,var(--k-{renk}) 75%,transparent)"></div>'
              f'<span style="font-weight:700;font-size:12px;font-variant-numeric:tabular-nums;color:var(--k-metin);white-space:nowrap">{_usd(nk)}'
              f'<span style="color:var(--k-silik);font-weight:500"> · %{tr_sayi(x["Kâr payı (%)"], 0)}</span></span>'
              f'</div></div>')
    return h


def _toplam_aktif_penceresi(RENK, pencere, pencere_bos, buyuk=False):
    try:
        from kayranacc.database import get_ayar
        snap = get_ayar("toplam_aktif_snapshot")
    except Exception:  # noqa: BLE001
        snap = None
    if not snap:
        return pencere("Toplam aktifler", RENK["mor"], pencere_bos("Muhasebe → Toplam Aktifler işlenince burada görünür"),
                       yukseklik=60)
    return pencere("Toplam aktifler", RENK["mor"], _toplam_aktif_html(snap, RENK, buyuk=buyuk),
                   rozet=_tr_tarih(snap.get("tarih"), saat=True), yukseklik=320 if buyuk else 300)


def _ozet(r, yil, donem, bugun, kur, RENK, pencere, pencere_grid, pencere_bos):
    from yonetim_pano import kiyas_donemleri, devam_ediyor, trend_aylari, degisim as _dg
    kiyas = []
    for anahtar, etiket, ky, kd, kb, kt, ka in kiyas_donemleri(yil, donem, bugun):
        try:
            kiyas.append((anahtar, etiket, _pnl_onbellekli(ky, kd, kb, kt, tuple(ka), kur)))
        except Exception:  # noqa: BLE001
            kiyas.append((anahtar, etiket, None))
    k1 = kiyas[0][2] if kiyas else None
    st.markdown(_serit(r, k1), unsafe_allow_html=True)
    # Tek bilgi satırı: dönem · kıyas · geçen yıl · veri durumu (eskiden üç ayrı satırdı)
    parca = [f"{_tr_tarih(r['bas'])} – {_tr_tarih(r['bit'])}"]
    if kiyas:
        parca.append(f"değişim: {kiyas[0][1]} ile")
    if devam_ediyor(yil, donem, bugun) and donem in GIDER_AYLAR + ["Q1", "Q2", "Q3", "Q4"]:
        parca.append("dönem sürüyor, kıyas tam dönemle")
    gecen = next((x for x in kiyas if x[0] == "gecen"), None)
    if gecen and gecen[2] and len(kiyas) > 1:
        g = gecen[2]
        parca.append(f'geçen yıl ({gecen[1]}): ciro <b style="color:var(--k-metin)">{_usd(g["ciro"])}</b> '
                     f'{_cip(_dg(r["ciro"], g["ciro"]))}, net kâr <b style="color:var(--k-metin)">'
                     f'{_usd(g["net_kar"])}</b> {_cip(_dg(r["net_kar"], g["net_kar"]))}')
    if r.get("tl_cevrildi"):
        parca.append("TL tutarlar o günün kuruyla çevrildi")
    if not r["eksikler"]:
        parca.append('<span style="color:var(--k-yesil)">tüm bileşenler okundu</span>')
    st.markdown(f'<div style="font-size:12px;color:var(--k-silik);margin:2px 2px 8px;line-height:1.7">'
                f'{" · ".join(parca)}</div>', unsafe_allow_html=True)
    if r["eksikler"]:
        _veri_durumu(r["eksikler"])
    try:
        from shared.islem import bekle
        with bekle("Son 12 ay hesaplanıyor…"):
            trend = _trend(trend_aylari(yil, donem, bugun), kur)
        st.markdown(_kucuk_kartlar(trend), unsafe_allow_html=True)
    except Exception as e:  # noqa: BLE001
        st.caption(f"12 aylık seyir hesaplanamadı: {type(e).__name__}")
    _k = _kanal_cubuklari(r["kanal"])
    _p_kanal = pencere("Kanal katkısı · net kâr", RENK["mor"], _k or pencere_bos("Bu dönemde satış kaydı yok"),
                       rozet=f"{len(r['kanal'])} kanal", yukseklik=300)
    st.markdown(pencere_grid(_p_kanal, _toplam_aktif_penceresi(RENK, pencere, pencere_bos)), unsafe_allow_html=True)


@st.cache_data(ttl=600, show_spinner=False)
def _kanal_urunleri(bas, bit, kanal):
    """Bir kanalın ürün kırılımı — P&L ile aynı satış kaynağı (görünüm, yoksa satışlar)."""
    from satis.database import get_satis_pnl_view, ozet_from_view, get_satislar_yalin, ozet_hesapla
    v = get_satis_pnl_view(bas, bit)
    if v is not None:
        return ozet_from_view([x for x in v if (x.get("kanal") or "—") == kanal])[2]
    return ozet_hesapla([x for x in (get_satislar_yalin(bas, bit) or []) if (x.get("kanal") or "—") == kanal])[2]


def _kanal_urun(r):
    from shared.tablo import tablo
    from yonetim_pano import kanal_satirlari, urun_satirlari
    from kayranpm.stok_yasi import excel_bytes
    krows = kanal_satirlari(r["kanal"])
    urows = urun_satirlari(r["urun"])
    st.caption("Kanal kırılımı satışlardan; iadeler toplamda düşülür, kanala dağıtılmaz. "
               "Bir kanala tıkla: o kanalın ürünleri altta açılır.")
    if not krows:
        st.info("Bu dönemde satış kaydı yok.")
        return
    sec = tablo(krows, key="yon_kanal", kalici=True, arama=True, dosya_adi="yonetim_kanallar")
    if sec is not None and sec < len(krows):
        kn = krows[sec]["_id"]
        try:
            _ku = urun_satirlari(_kanal_urunleri(r["bas"], r["bit"], kn))
        except Exception as e:  # noqa: BLE001
            _ku = []
            st.caption(f"Kanalın ürünleri okunamadı: {type(e).__name__}")
        with st.container(border=True):
            st.markdown(f"**{kn}** · {tr_sayi(len(_ku))} ürün")
            tablo(_ku, key=f"yon_kanal_urun_{kn}", arama=True, dosya_adi="yonetim_kanal_urunleri")
    st.markdown("**Ürünler** · net kâra göre")
    tablo(urows, key="yon_urunler", arama=True, dosya_adi="yonetim_urunler")
    st.download_button("Excel: kanallar ve ürünler", excel_bytes({"Kanallar": krows, "Ürünler": urows}),
                       file_name=f"yonetim_kanal_urun_{r['bas']}_{r['bit']}.xlsx", icon=":material/download:",
                       key="yon_xl_kanal")


def _destek_gider(r, yil, donem):
    from shared.tablo import tablo
    from yonetim_pano import destek_satirlari, gider_satirlari
    from kayranpm.stok_yasi import excel_bytes
    drows = destek_satirlari(r["tur_usd"])
    st.markdown(f"**Destekler** · {_usd(r['destek'])} · ref no harcamaları, türlerine göre")
    if drows:
        tablo(drows, key="yon_destek", arama=True, dosya_adi="yonetim_destekler")
    else:
        st.caption("Bu dönemde destek / harcama kaydı yok.")
    _gider_anahtar = f"gider_tablosu_{yil}"
    try:
        from kayranacc.database import get_ayar as _ga
    except Exception:  # noqa: BLE001
        _ga = None
    _gider = _ga(_gider_anahtar) if _ga else None
    st.markdown(f"**İşletme giderleri** · {yil} · TL"
                + (f" · dönemde ≈ {_usd(r['gider'])} · yüklenme {_tr_tarih(_gider.get('tarih'))}" if _gider else ""))
    if not _gider:
        st.info(f"{yil} gider tablosu yüklenmedi. Doldurulmuş tabloyu üst menüdeki **Dosya** düğmesinden "
                "yükleyebilirsin.")
        return
    grows, gtop = gider_satirlari(_gider.get("kat") or {})
    try:
        import plotly.graph_objects as go
        from shared.grafik import goster, rol
        fg = go.Figure()
        for ad, rk in (("Sabit", "mavi"), ("Değişken", "amber"), ("Yarı Değişken", "mor")):
            satir = next(x for x in grows if x["_id"] == ad)
            _yv = [satir[a] for a in GIDER_AYLAR]
            fg.add_bar(x=[a[:3] for a in GIDER_AYLAR], y=_yv, name=ad, marker_color=rol(rk), marker_line_width=0,
                       customdata=[f"₺{tr_sayi(v)}" for v in _yv],
                       hovertemplate=f"{ad}<br>%{{x}}: %{{customdata}}<extra></extra>")
        goster(fg, key="yon_gider_grafik", yukseklik=260, barmode="stack", bargap=0.35,
               yaxis=dict(tickprefix="₺", separatethousands=True))
    except Exception:  # noqa: BLE001
        pass
    tablo(grows, key="yon_gider", birim="₺", dosya_adi="yonetim_giderler")
    st.download_button("Excel: destekler ve giderler", excel_bytes({"Destekler ($)": drows, "Giderler (TL)": grows,
                                                                    "Gider kalemleri (TL)": [
                                                                        dict({"Kategori": k, "Kalem": b},
                                                                             **{a: v for a, v in zip(GIDER_AYLAR, ay)})
                                                                        for k, b, ay in (_gider.get("detay") or [])]}),
                       file_name=f"yonetim_destek_gider_{yil}.xlsx", icon=":material/download:", key="yon_xl_gider")


def kapi_gider(dosya, kapi):
    """Dosya kapısı (Ekim 2026): aylık gider tablosu. Eskiden Destekler ve giderler sayfasındaki
    'Gider yükle' penceresiydi; yıl o sayfanın yıl seçiminden gelirdi, artık burada seçilir."""
    from shared.yukleme_takvimi import serit as _yt_serit
    _yt_serit("gider_tablosu")
    st.markdown("Muhasebenin doldurduğu tablo: **sabit / değişken / yarı değişken** kalemler, 12 ay. "
                "Aynı yılı tekrar yüklersen o yılın tablosu güncellenir.")
    _bu = _bugun().year
    _yillar = [_bu - 1, _bu, _bu + 1]
    # Yıl dosyadan (ad / başlık) gelir; bulunamazsa boş başlar ve seçilmeden kayıt yapılmaz — "bu yıl"
    # varsayılanı Ocak'ta geçen yılın tablosunu yeni yıla yazardı.
    from yonetim_hesap import gider_yili_bul
    _dy = gider_yili_bul(dosya.name, dosya.getvalue(), _bugun())
    yil = st.selectbox("Hangi yılın gider tablosu?", _yillar, index=_yillar.index(_dy) if _dy in _yillar else None,
                       key=kapi.anahtar("gider_yil"), placeholder="Yıl seç",
                       help="Dosyanın adından ya da başlığından okunur; bulunamazsa sen seç.")
    if yil is None:
        st.info("Dosyada yıl bulunamadı; tablonun hangi yıla ait olduğunu seç.")
        return
    _gider_anahtar = f"gider_tablosu_{yil}"
    try:
        with st.spinner("Gider tablosu işleniyor…"):
            _katp, _detayp = gider_tablosu_parse(dosya)
    except Exception as e:  # noqa: BLE001
        st.error(f"Dosya işlenemedi: {e}")
        return
    _yillik_top = sum(sum(v) for v in _katp.values())
    if not _detayp or _yillik_top <= 0:
        st.warning("Dosya açıldı ama **hiç gider değeri okunamadı**, kayıt yapılmaz. "
                   "Kontrol et: (1) tutarlar ay kolonlarına (Ocak…Aralık) girilmiş mi, "
                   "(2) hücreler sayı mı (formül sonucu da olur), "
                   "(3) veriler dosyanın ilk sayfasında, aynı düzende mi.")
        return
    st.success(f"{len(_detayp)} kalem · yıllık ₺{tr_sayi(_yillik_top)} okundu · "
               + " · ".join(f"{k} ₺{tr_sayi(sum(v))}" for k, v in _katp.items()))
    try:
        from kayranacc.database import get_ayar as _ga, set_ayar as _sa3
    except Exception:  # noqa: BLE001
        st.error("Ayar tablosuna erişilemiyor; kayıt yapılamaz.")
        return
    _onay = True
    if _ga(_gider_anahtar):
        _onay = st.checkbox(f"{yil} için kayıtlı bir tablo var; yerine bu dosyayı yaz",
                            key=kapi.anahtar("gider_uzerine"))
    if st.button("Kaydet", key=kapi.anahtar("gider_kaydet"), type="primary", use_container_width=True,
                 icon=":material/save:", disabled=not _onay):
        _sa3(_gider_anahtar, {"kat": _katp, "detay": _detayp, "tarih": _bugun().isoformat()})
        from shared.yukleme_gecmisi import kaydet as _yg_kaydet
        _yg_kaydet("gider_tablosu", len(_detayp), dosya.name)
        from shared.yukleme_takvimi import _temizle as _yt_tazele
        _yt_tazele()                      # geri sayım yeni ayı görsün
        _pnl_onbellekli.clear()
        _ay_ozeti.clear()
        kapi.bitti(f"{yil} gider tablosu kaydedildi: {len(_detayp)} kalem · yıllık ₺{tr_sayi(_yillik_top)}.")


def _ay_kapanis():
    from shared.tablo import tablo
    from shared.utils import metrik_satiri
    from yonetim_pano import degisim as _dg, pnl_satirlari
    from kayranpm.stok_yasi import excel_bytes
    _bgr = _bugun()
    _vy, _vay = onceki_ay(_bgr)          # Ocak'ta önceki yılın Aralık'ı
    _c1, _c2 = st.columns(2)
    _yillar = list(range(_bgr.year, _bgr.year - 4, -1))
    _ryil = _c1.selectbox("Yıl", _yillar, index=_yillar.index(_vy), key="ayrap_yil")
    _ray = _c2.selectbox("Ay", GIDER_AYLAR, index=_vay, key="ayrap_ay")
    _ai = GIDER_AYLAR.index(_ray)
    # Panoyla AYNI kaynak (aynı kur yedeği) — yoksa TL kalemler farklı çevrilirdi
    _okur = _oturum_kuru()
    _kyn = _PnlKaynak(_okur)
    with st.spinner(f"{_ray} {_ryil} kapanışı hesaplanıyor…"):
        _r = ay_pnl_hesapla(_ryil, _ai, kaynak=_kyn)
        _pyil, _pai = (_ryil - 1, 11) if _ai == 0 else (_ryil, _ai - 1)
        _rp = ay_pnl_hesapla(_pyil, _pai, kaynak=_kyn)

    def _alt(a, tersi=False):
        d = _dg(_r[a], _rp[a], tersi)
        return "" if not d else f"{'▲' if d['oran'] >= 0 else '▼'} %{tr_sayi(abs(d['oran']), 1)} · {_rp['ay']}"
    st.markdown(f"**{_r['ay']} {_r['yil']} kapanışı** · {_tr_tarih(_r['bas'])} – {_tr_tarih(_r['bit'])} · "
                f"önceki ay ({_rp['ay']}) ile kıyaslı · tüm tutarlar USD")
    metrik_satiri([
        {"label": "Ciro", "value": _usd(_r["ciro"]), "alt": _alt("ciro")},
        {"label": "Ürün maliyeti", "value": _usd(_r["cogs"]), "alt": _alt("cogs", True)},
        {"label": "Net kâr", "value": _usd(_r["net_kar"]), "alt": _alt("net_kar"),
         "renk": "yesil" if _r["net_kar"] >= 0 else "kirmizi"},
        {"label": "Net marj", "value": _pct(_r["marj"])},
    ])
    gelir = pnl_satirlari(_r, [(f"{_rp['ay']} {_rp['yil']}", _rp)])
    tablo(gelir, key="ayrap_gelir", dosya_adi="kapanis_gelir_tablosu")
    _veri_durumu(_r["eksikler"])
    kanal = [{"_id": k["kanal"], "Kanal": k["kanal"], "Adet": k["adet"], "Ciro ($)": round(k["ciro"], 2),
              "Net kâr ($)": round(k["net_kar"], 2), "Marj (%)": round(k["marj"], 1)} for k in _r["kanal"]]
    top = [{"_id": u["sku"], "Ürün": u["urun"], "Adet": u["adet"], "Net kâr ($)": round(u["net_kar"], 2)}
           for u in _r["urun_top"]]
    zarar = [{"_id": u["sku"], "Ürün": u["urun"], "Adet": u["adet"], "Net kâr ($)": round(u["net_kar"], 2)}
             for u in _r["urun_zarar"]]
    if kanal:
        st.markdown("**Kanal kırılımı**")
        tablo(kanal, key="ayrap_kanal", dosya_adi="kapanis_kanallar")
    st.markdown("**En kârlı ürünler**")
    if top:
        tablo(top, key="ayrap_top", dosya_adi="kapanis_karli")
    else:
        st.caption("Kayıt yok.")
    st.markdown("**Zarardaki ürünler**")
    if zarar:
        tablo(zarar, key="ayrap_zarar", dosya_adi="kapanis_zarar")
    else:
        st.caption("Zararda ürün yok.")
    st.download_button("Excel: kapanış raporu",
                       excel_bytes({"Gelir tablosu": gelir, "Kanallar": kanal, "En kârlı": top, "Zararda": zarar,
                                    "Eksikler": [{"Not": e} for e in _r["eksikler"]]}),
                       file_name=f"kapanis_{_r['yil']}_{_ai + 1:02d}.xlsx", icon=":material/download:",
                       key="ayrap_dl", use_container_width=True)


def _sistem():
    st.markdown("**Değişiklik günlüğü** · kim, ne zaman, hangi kaydı değiştirdi")
    _audit_render()
    st.divider()
    st.markdown("**Yedekleme**")
    _yedek_render()


def run():
    with st.sidebar:
        from shared.utils import sidebar_ust
        sidebar_ust("", "Yönetim", "yonetim")
        from shared.gezinme import secenekler, sayfa_menusu
        from shared.tasarim import menu_etiketi as _me
        _bolum = sayfa_menusu("Bölüm", secenekler("yonetim"), modul="yonetim", key="yon_sayfa", format_func=_me)

    # ── Sayfa gövdesi: KENDİ İÇİNDE YENİLENEN PARÇA (st.fragment) ───────────
    # HIZ: Sayfadaki filtre, seçim kutusu, sekme ya da onay kutusu değişince
    # yalnız bu gövde yeniden çizilir; üst menü, sol menü, oturum kontrolü ve
    # ortak CSS yeniden çalışmaz. Kayıt sonrası st.rerun() çağrıları ESKİSİ
    # GİBİ tüm sayfayı yeniler (Streamlit 1.64'te parça içi st.rerun() tam
    # yenilemedir). Blok ile dış kapsamın paylaştığı değişkenler nonlocal ile
    # aynen korunur (otomatik hesaplandı; tests/test_parca.py denetler).
    @st.fragment
    def _sayfa_parcasi():
        from shared.tasarim import RENK, pencere_css, pencere, pencere_grid, pencere_bos
        from shared.tasarim import baslik
        # KÂR GİZLEME: Kâr/zarar analizleri (ciro−COGS−destek−gider) girilmemiş
        # destek ve masraflar nedeniyle henüz doğru sonuç vermiyor → yalnız yetkiliye.
        # ANCAK Toplam Aktifler kâr hesabı DEĞİL; yüklenen stok/banka/cari verisinden
        # gelir ve doğrudur → herkese gösterilir.
        from shared.kar_gizle import kar_gorunur, uyari_ciz
        st.markdown(pencere_css(), unsafe_allow_html=True)
        if _bolum == "Para haritası":
            # Kâr verisi değil (varlık / borç): Yönetim yetkisi olan herkes görür — kâr gizlemeden önce
            from yonetim_para import sayfa as _para_haritasi
            _para_haritasi()
            return
        if not kar_gorunur():
            st.markdown(baslik(":material/monitoring: Yönetim", "Yönetim panosu", aciklama="Toplam aktifler özeti"),
                        unsafe_allow_html=True)
            uyari_ciz()
            st.markdown(_toplam_aktif_penceresi(RENK, pencere, pencere_bos, buyuk=True), unsafe_allow_html=True)
            return
        st.markdown(baslik(":material/monitoring: Yönetim", "Yönetim panosu",
                           aciklama="Ciro − COGS − destekler − giderler = net kâr · tüm tutarlar USD"),
                    unsafe_allow_html=True)
        if _bolum == "Ay kapanışı":
            _ay_kapanis()
            return
        if _bolum == "Sistem":
            _sistem()
            return

        # ── Dönem seçimi — tek kompakt satır ──
        _bg = _bugun()
        c1, c2, c3, _c4 = st.columns([0.8, 1.6, 1.3, 2.3])
        with c1:
            _yil = st.selectbox("Yıl", list(range(_bg.year + 1, _bg.year - 4, -1)), index=1, key="yon_yil")
        with c2:
            _gor = secim_serit("Görünüm", ["Aylık", "Çeyreklik", "Yıllık"], index=2, key="yon_gorunum")
        with c3:
            if _gor == "Aylık":
                _donem = st.selectbox("Ay", GIDER_AYLAR, index=min(_bg.month - 1, 11), key="yon_ay")
            elif _gor == "Çeyreklik":
                _donem = secim_serit("Çeyrek", ["Q1", "Q2", "Q3", "Q4"], index=(_bg.month - 1) // 3, key="yon_ceyrek")
            else:
                _donem = "Tüm Yıl"
        baslangic, bitis = _donem_tarih(_yil, _donem)

        # ── P&L — TEK HESAP (yonetim_hesap.pnl_topla; Ay Kapanış Raporu da bunu kullanır) ──
        _oturum_kur = _oturum_kuru()
        _kiyas_bekle = _on_isit(_yil, _donem, _bg, _oturum_kur, ozet=(_bolum not in ("Kanal ve ürün",
                                                                                  "Destekler ve giderler")))
        _r = pnl_topla(_yil, _donem, baslangic, bitis, _PnlKaynak(_oturum_kur), bugun=_bg)
        _kiyas_bekle()
        if _bolum == "Kanal ve ürün":
            _kanal_urun(_r)
        elif _bolum == "Destekler ve giderler":
            _destek_gider(_r, _yil, _donem)
        else:
            _ozet(_r, _yil, _donem, _bg, _oturum_kur, RENK, pencere, pencere_grid, pencere_bos)

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
    "veri_surumu",         # önbellek tazelik sayacı (tetikleyiciyle dolar), veri değil
    "yuklemeler",          # yükleme geçmişi + geri alma kopyaları; asıl tablolar zaten yedekte
    "soru_kayitlari",      # soru kutusuna sorulan sorular (kalıp geliştirme için), iş verisi değil
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
        ozet.append(("Okunamadı: " + ", ".join(hatali), 0))
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
        st.success(f"Yedek hazır — {len(_ozet)} tablo, {tr_sayi(_toplam)} kayıt.")
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
