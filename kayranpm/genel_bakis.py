# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Genel Bakış — yeniden tasarım (Ekim 2026).

Tek soru: "Ürünlerim ne durumda, bugün ne yapmalıyım?"

  ┌ filtre (firma · kategori) · veri tazeliği ─────────────────────────┐
  │ sayı kartları: stok · haftalık satış · stok değeri · yolda · risk   │
  ├ Yapılacaklar (öncelikli gruplar) ─┬ Satış eğilimi (8 hafta) ────────┤
  ├ Stok sağlığı (kapsama dağılımı) ──┴ Kategori özeti ─────────────────┤
  └ Kanal dağılımı ───────────────────┴ Yolda · aktif kampanyalar ──────┘

Eskiden yalnız "acil" ve "30 gün içinde" listeleri vardı; dashboard_hesapla()'nın
ürettiği eğilim, ölü stok, yoldaki ürün, kâr durumu, kanal stokları kullanılmıyordu.
Hesaplar genel_hesap.py'de (testli). Filtre HER bölüme uygulanır. Ürün satırına
tıklayınca Stok Kartı açılır; grup başlığından ilgili sayfaya gidilir.
"""
import hashlib
import html as _h
from datetime import timedelta

import streamlit as st

from shared import bilesen as B
from shared.tasarim import tr_sayi, urun_etiketi
from shared.tasarim import renk as trenk
from shared.utils import metrik_satiri, firma_gorunen_ad

from .genel_hesap import (kpi, yapilacaklar, kapsama_dagilimi, kategori_ozeti, kanal_ozeti,
                          haftalik_seri, trend_listeleri, yaklasan_varislar, KAPSAMA_DILIM)
from .urun_hesap import dashboard_filtrele, tarih_tr

from shared.utils import FIRMA_KODLARI as _FK   # tek liste (Faz 4); DİĞER bu ekranın seçenek yazımı
FIRMALAR = ["Tüm Firmalar", *_FK, "DIGER"]            # yedek liste; ekranda veriden üretilir
HAFTA = 8
GRUP_ILK = 5


@st.cache_data(ttl=600, show_spinner=False)
def _haftalik_ham(bas_iso, firma):
    from .database import get_musteri_haftalik_satis
    return get_musteri_haftalik_satis(bas_iso, None, None if firma == "Tüm Firmalar" else firma)


def _e(v):
    return _h.escape(str(v or "").strip())


def _usd(v):
    return f"&#36;{tr_sayi(float(v or 0))}"            # düz "$" iki kez geçerse LaTeX sanılır


def _bolum(baslik, alt=""):
    st.markdown(B.grup_basligi(baslik, alt), unsafe_allow_html=True)


def _sk_ac(sku):
    st.session_state["_gb_stok_karti"] = sku


def _sayfaya(hedef):
    st.session_state["pm_sayfa"] = hedef


# ── Sayı kartları ───────────────────────────────────────────────────
def _kartlar(k):
    # Ana kart: haftalık satış — önceki haftaya göre rozet + son 8 haftanın eğilimi
    if k["hafta_satis"] is None:
        satis, satis_alt = "—", "haftalık veri yok"
    else:
        satis = tr_sayi(k['hafta_satis'])
        satis_alt = ("adet · önceki haftaya göre" if k.get("onceki_satis") else "adet · son hafta")
        if len(k.get("seri") or []) >= 2:
            satis_alt += f" · son {len(k['seri'])} hafta"
    metrik_satiri([
        {"label": "Haftalık satış", "value": satis, "alt": satis_alt, "vurgu": True,
         "simdi": k["hafta_satis"], "onceki": k.get("onceki_satis"), "seri": k.get("seri")},
        {"label": "Toplam stok", "value": tr_sayi(k['stok']), "renk": trenk("mor"),
         "alt": (f"adet · kanal dahil ~{tr_sayi(k['kapsama_hafta'], 1)} hafta" if k["kapsama_hafta"]
                 else "adet · bizim depolar")},
        {"label": "Stok değeri", "value": f"${tr_sayi(k['stok_degeri'])}", "renk": trenk("amber"),
         "alt": "G5F stok × paçal"},
        {"label": "Yolda", "value": tr_sayi(k['yolda']), "renk": trenk("mavi"),
         "alt": (f"adet · en yakın varış {tarih_tr(k['en_yakin_varis'].isoformat())}" if k["en_yakin_varis"]
                 else "adet · yaklaşan varış yok")},
        {"label": "Risk", "value": f"{k['acil']} acil", "renk": trenk("kirmizi") if k["acil"] else trenk("yesil"),
         "alt": f"{k['olu']} ölü stok"},
    ])


# ── Yapılacaklar ────────────────────────────────────────────────────
# Satır: yer varsa ad ile ayrıntı yan yana; yoksa ayrıntı alt satıra geçer
# (telefonda aynı satırda çekişip adı harf harf eziyordu).
SATIR_CSS = ("<style>.gb-sr{display:flex;flex-wrap:wrap;align-items:center;gap:2px 12px;min-width:0}"
             ".gb-ad{display:flex;min-width:0;flex:1 1 220px}"
             ".gb-dt{font-size:12px;color:var(--k-soluk);white-space:nowrap}"
             "@media(max-width:640px){.gb-dt{white-space:normal}}</style>")


def _yapilacaklar(gruplar):
    st.markdown(SATIR_CSS, unsafe_allow_html=True)
    _bolum("Yapılacaklar", f"{sum(len(g['urunler']) for g in gruplar)} ürün" if gruplar else "")
    if not gruplar:
        st.markdown('<div style="color:var(--k-yesil);font-size:13px;padding:6px 2px">✓ Bugün dikkat gerektiren '
                    'ürün yok — stok, yoldaki ürünler, kâr ve veri tamam.</div>', unsafe_allow_html=True)
        return
    for g in gruplar:
        n = len(g["urunler"])
        c1, c2 = st.columns([3, 1.5], vertical_alignment="center")
        # Başlık + sayı tek satırda (kırılmaz); açıklama altta küçük satır
        c1.markdown(
            f'<div style="margin-top:6px"><div style="display:flex;align-items:center;gap:8px;white-space:nowrap">'
            f'<span style="width:8px;height:8px;border-radius:50%;flex:0 0 auto;background:var(--k-{g["renk"]})"></span>'
            f'<b style="font-size:14px">{_e(g["baslik"])}</b>'
            f'<span style="font-family:var(--k-mono);font-size:12px;color:var(--k-{g["renk"]})">{n}</span></div>'
            f'<div style="font-size:12px;color:var(--k-silik);margin-left:16px">{_e(g["aciklama"])}</div></div>',
            unsafe_allow_html=True)
        if g["hedef"]:
            if c2.button(g["hedef"].split("  ", 1)[-1], key=f"gb_git_{g['anahtar']}", type="tertiary",
                         icon=":material/arrow_forward:", use_container_width=True,
                         on_click=_sayfaya, args=(g["hedef"],)):
                st.rerun()                         # kenar çubuğundaki sayfa seçici de güncellensin
        for r, detay in g["urunler"][:GRUP_ILK]:
            B.tiklanir(
                f"gb_{g['anahtar']}_{hashlib.md5(str(r['sku']).encode('utf-8')).hexdigest()[:12]}",
                f'<div class="gb-sr"><div class="gb-ad">{urun_etiketi(r.get("urun_adi"), r.get("sku"))}</div>'
                f'<div class="gb-dt">{_e(detay)}</div></div>',
                _sk_ac, (r["sku"],), tur="satir", renk=g["renk"], etiket="Stok kartını aç")
        if n > GRUP_ILK:
            st.caption(f"+{n - GRUP_ILK} ürün daha" + (f" — tamamı {g['hedef'].split('  ', 1)[-1]} sayfasında"
                                                      if g["hedef"] else ""))


# ── Satış eğilimi ───────────────────────────────────────────────────
def _egilim(seri, yuk, dus):
    toplam = sum(v for _, v in seri)
    _bolum("Satış eğilimi", f"son {len(seri)} hafta · müşteri sell-out")
    if not toplam:
        st.caption("Bu filtre için son haftalarda müşteri satış verisi yok.")
    else:
        import plotly.graph_objects as go
        x = [h.strftime("%d.%m") for h, _ in seri]          # Türkçe etiket (tarih ekseni İngilizce çıkar)
        from shared.grafik import goster as _goster, rol as _rol, saydam as _saydam
        fg = go.Figure()
        fg.add_scatter(x=x, y=[v for _, v in seri], mode="lines+markers", line=dict(color=_rol("ana"), width=2.2),
                       marker=dict(size=5), fill="tozeroy",
                       fillcolor=_saydam(_rol("ana"), 0.10),
                       customdata=[f"{h:%d.%m}–{(h + timedelta(days=6)):%d.%m} · {tr_sayi(v)} adet" for h, v in seri],
                       hovertemplate="%{customdata}<extra></extra>")
        _goster(fg, key="gb_egilim", yukseklik=220, aciklama=False,
                yaxis=dict(tickformat=",d"), xaxis=dict(type="category"))

    def _liste(baslik, rs, renk, isaret):
        st.markdown(f'<div style="font-size:12.5px;font-weight:650;margin:4px 0 2px">{baslik}</div>',
                    unsafe_allow_html=True)
        if not rs:
            st.markdown('<div style="font-size:12px;color:var(--k-silik)">—</div>', unsafe_allow_html=True)
            return
        st.markdown("".join(
            f'<div style="display:flex;align-items:center;gap:8px;padding:3px 0;min-width:0">'
            f'<div style="display:flex;min-width:0;flex:1">{urun_etiketi(r.get("urun_adi"), r.get("sku"))}</div>'
            f'<span style="font-family:var(--k-mono);font-size:12px;color:var(--k-{renk});white-space:nowrap">'
            f'{isaret} %{tr_sayi(abs(float(r.get("trend_yuzdesi") or 0)), 0)}</span></div>' for r in rs),
            unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        _liste("En çok yükselen", yuk, "yesil", "▲")
    with c2:
        _liste("En çok düşen", dus, "kirmizi", "▼")


# ── Stok sağlığı ────────────────────────────────────────────────────
def _stok_sagligi(dag):
    _bolum("Stok sağlığı", "stok kaç güne yetiyor")
    toplam = sum(n for _, n, _s in dag) or 1
    renk = {et: r for et, _a, _b, r in KAPSAMA_DILIM}
    renk["Satış yok"] = "silik"
    serit = "".join(
        f'<div title="{et}: {n} ürün" style="flex:{n};background:var(--k-{renk[et]});min-width:{4 if n else 0}px"></div>'
        for et, n, _s in dag if n)
    st.markdown(
        f'<div style="display:flex;height:12px;border-radius:6px;overflow:hidden;gap:2px;margin:4px 0 10px">{serit}</div>'
        + "".join(
            f'<div style="display:flex;justify-content:space-between;align-items:center;font-size:13px;padding:3px 0">'
            f'<span><span style="display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:8px;'
            f'background:var(--k-{renk[et]})"></span>{et}</span>'
            f'<span style="font-family:var(--k-mono);color:var(--k-soluk)">{n} ürün · %{tr_sayi(n / toplam * 100, 0)}'
            f' · {tr_sayi(s)} adet</span></div>' for et, n, s in dag),
        unsafe_allow_html=True)


# ── Kanal · yolda · kampanya ────────────────────────────────────────
def _kanallar(kn):
    _bolum("Kanal dağılımı", "stok ve son haftalık satış")
    mx = max([x["stok"] for x in kn] + [1])
    st.markdown("".join(
        f'<div style="padding:4px 0"><div style="display:flex;justify-content:space-between;font-size:13px">'
        f'<span>{_e(firma_gorunen_ad(x["kanal"]) if x["kanal"] != "G5F depo" else "G5F depo")}</span>'
        f'<span style="font-family:var(--k-mono);color:var(--k-soluk)">{tr_sayi(x["stok"])} stok · '
        f'{tr_sayi(x["satis"])} satış/hafta</span></div>'
        f'<div style="height:5px;border-radius:3px;background:var(--k-kenar2);margin-top:4px;overflow:hidden">'
        f'<div style="height:100%;width:{x["stok"] / mx * 100:.0f}%;background:var(--k-mor)"></div></div></div>'
        for x in kn if x["stok"] or x["satis"]), unsafe_allow_html=True)


def _yolda_kampanya(varis, bugun):
    _bolum("Yolda", f"{len(varis)} yaklaşan varış" if varis else "")
    if not varis:
        st.caption("Yaklaşan ithalat varışı yok.")
    for r in varis:
        from datetime import date as _d
        g = (_d.fromisoformat(str(r["yol_varis"])[:10]) - bugun).days
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;padding:3px 0;min-width:0">'
            f'<div style="display:flex;min-width:0;flex:1">{urun_etiketi(r.get("urun_adi"), r.get("sku"))}</div>'
            f'<span style="font-family:var(--k-mono);font-size:12px;color:var(--k-soluk);white-space:nowrap">'
            f'{tr_sayi(int(r.get("yol_miktar") or 0))} adet · {tarih_tr(r["yol_varis"])} · {g} gün</span></div>',
            unsafe_allow_html=True)
    try:
        from .database import get_kampanyalar
        kmp = get_kampanyalar(durum="aktif") or []
    except Exception:
        kmp = []
    _bolum("Aktif kampanyalar", f"{len(kmp)} kampanya" if kmp else "")
    if not kmp:
        st.caption("Şu an aktif kampanya yok.")
    for k in sorted(kmp, key=lambda k: str(k.get("bitis_tarihi") or "9999"))[:6]:
        bit = str(k.get("bitis_tarihi") or "")[:10]
        try:
            from datetime import date as _d
            kalan = (_d.fromisoformat(bit) - bugun).days
            ne = "bugün bitiyor" if kalan == 0 else (f"{kalan} gün kaldı" if kalan > 0 else "süresi doldu")
        except ValueError:
            kalan, ne = None, "bitiş yok"
        renk = "kirmizi" if (kalan is not None and kalan <= 3) else ("amber" if (kalan is not None and kalan <= 7)
                                                                    else "soluk")
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;gap:8px;font-size:13px;padding:3px 0">'
            f'<span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'
            f'{_e(k.get("kampanya_adi"))} <span style="color:var(--k-silik)">· {_e(k.get("firma"))}</span></span>'
            f'<span style="color:var(--k-{renk});white-space:nowrap;font-size:12px">{ne}</span></div>',
            unsafe_allow_html=True)


# ── Sayfa ───────────────────────────────────────────────────────────
def render(_sb):
    from .analitik import dashboard_hesapla
    from shared.utils import tr_today
    st.markdown(_sb("📊 Ürün Yönetimi", "Genel Bakış",
                    aciklama="Ürünlerin durumu · bugün yapılacaklar · satış eğilimi"), unsafe_allow_html=True)
    try:
        from shared.islem import bekle
        with bekle("Genel bakış hazırlanıyor…"):
            veri = dashboard_hesapla()
    except Exception as e:  # noqa: BLE001
        st.error(f"Veri yüklenemedi: {e}")
        return
    bugun = tr_today()

    from shared.ana_veri import kategori_ad as _kat_ad
    # Yalnız verideki kategoriler, tabloyla AYNI tek yazımla (shared.ana_veri)
    kat = sorted({_kat_ad(u.get("kategori")) for u in veri} - {""}, key=lambda x: x.lower())
    f1, f2, f3 = st.columns([1.6, 1.6, 0.8], vertical_alignment="bottom")
    # Firma seçenekleri VERİDEN (KANAL yok; her firma kendi adıyla — Ekim 2026)
    from shared.utils import firma_sirala
    _firmalar = ["Tüm Firmalar"] + firma_sirala(
        list(FIRMALAR[1:]) + [fd.get("firma") for u in veri for fd in (u.get("firma_detay") or [])])
    firma = f1.selectbox("Firma", _firmalar,
                         format_func=lambda f: f if f == "Tüm Firmalar" else firma_gorunen_ad(f), key="gb_firma")
    kategori = f2.selectbox("Kategori", ["Tüm Kategoriler"] + kat, key="dash_kat")
    if f3.button("Yenile", use_container_width=True, icon=":material/refresh:", key="gb_yenile"):
        st.cache_data.clear()
        st.rerun()
    from shared.yukleme_takvimi import serit as _yt_serit
    _yt_serit("musteri_haftalik")                 # eğilim haftalık müşteri verisine bağlı: tazelik

    d = dashboard_filtrele(veri, firma, kategori)   # filtre HER bölüme uygulanır
    if len(d) != len(veri):
        st.caption(f"{tr_sayi(len(d))} / {tr_sayi(len(veri))} ürün · filtre uygulandı"
                   + (" (firma: o firmada stoğu olan ürünler)" if firma != "Tüm Firmalar" else ""))
    if not d:
        st.info("Bu filtreye uyan ürün yok.")
        return
    skular = {r["sku"] for r in d}
    bas = bugun - timedelta(days=bugun.weekday() + 7 * (HAFTA - 1))
    try:
        ham = _haftalik_ham(bas.isoformat(), firma)
    except Exception:  # noqa: BLE001
        ham = []
    seri = haftalik_seri(ham, skular, bugun, n=HAFTA)
    # Henüz yüklenmemiş içinde bulunulan hafta grafiği sıfıra düşürmesin
    if seri and seri[-1][1] == 0 and any(v for _, v in seri[:-1]):
        seri = seri[:-1]

    _kartlar(kpi(d, seri, bugun))

    sol, sag = st.columns([1.05, 1], gap="large")
    with sol:
        _yapilacaklar(yapilacaklar(d))
    with sag:
        _egilim(seri, *trend_listeleri(d))

    sol, sag = st.columns([1.05, 1], gap="large")
    with sol:
        _stok_sagligi(kapsama_dagilimi(d))
    with sag:
        _bolum("Kategori özeti", f"{len(kategori_ozeti(d))} kategori")
        import pandas as pd
        st.dataframe(pd.DataFrame(kategori_ozeti(d)), hide_index=True, use_container_width=True)

    sol, sag = st.columns([1.05, 1], gap="large")
    with sol:
        _kanallar(kanal_ozeti(d))
    with sag:
        _yolda_kampanya(yaklasan_varislar(d, bugun), bugun)

    sku = st.session_state.pop("_gb_stok_karti", None)
    if sku:
        from .stok_karti import goster
        goster(sku)
