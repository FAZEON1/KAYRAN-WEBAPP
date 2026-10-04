# -*- coding: utf-8 -*-
"""SKU Stok Kartı — ortada açılan modal pencere.
Sekmeler: 📊 Özet · 📥 Alımlar · 📤 Satışlar · 🎯 Kampanya · 📈 Analiz
Veriyi ürün/stok (kayranpm), ithalat ve satış modüllerinden birleştirir.
Performans: satışlar SKU bazlı çekilir, paçal alım partilerinden hesaplanır."""
from shared.tasarim import renk as trenk  # aktif temanın rengi (hex)
from shared.tasarim import tr_sayi  # TR sayı biçimi (1.234,56)
import streamlit as st
import pandas as pd
from datetime import timedelta
from shared.ana_veri import kategori_ad as _kat_ad, marka_ad as _marka_ad   # tek yazım (Eki 2026)
from shared.utils import firma_kanonik   # eski 'KANAL' → DİĞER (Eki 2026)

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
    return f"${tr_sayi(_f(v), 2)}"



def _cari_ad(kod):
    try:
        from shared.utils import firma_gorunen_ad
        return firma_gorunen_ad(kod, kisa=False) if kod else ""
    except Exception:  # noqa: BLE001
        return str(kod or "")

def _kart(baslik, deger, alt="", renk="#A5B4FC", anlam=None):
    from shared.tasarim import KART_YENI, kart_hucresi
    if KART_YENI:       # ortak kart (başlık eskiden CSS ile BÜYÜK HARF yapılıyordu)
        return kart_hucresi({"etiket": baslik, "deger": deger, "alt": alt, "renk": renk, "anlam": anlam})
    return (
        f'<div style="flex:1;min-width:150px;background:linear-gradient(180deg,var(--k-yuzey2),var(--k-yuzey1));'
        f'border:1px solid color-mix(in srgb,var(--k-metin) 8%,transparent);border-left:3px solid {renk};'
        f'border-radius:10px;padding:12px 16px">'
        f'<div style="color:var(--k-soluk);font-size:11px;text-transform:uppercase;letter-spacing:.4px">{baslik}</div>'
        f'<div style="color:{renk};font-size:19px;font-weight:700;margin-top:0px">{deger}</div>'
        f'<div style="color:var(--k-silik);font-size:11px;margin-top:0px">{alt}</div></div>'
    )


def _kart_satiri(kartlar):
    st.markdown('<div class="k-grid" style="margin:6px 0 14px">'
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


def _detay_satir(etiket, deger, renk="#E2E8F0"):
    """Tek bir etiket:değer satırı (hizalı, profesyonel)."""
    return (f'<div style="display:flex;justify-content:space-between;align-items:baseline;'
            f'padding:6px 0;border-bottom:1px solid color-mix(in srgb,var(--k-soluk) 8%,transparent)">'
            f'<span style="color:var(--k-soluk);font-size:11px;font-weight:600">{etiket}</span>'
            f'<span style="color:{renk};font-size:13px;font-weight:700;'
            f'font-family:JetBrains Mono,monospace">{deger}</span></div>')


def _alim_detay(a):
    _ind = _f(a.get("indirim_orani")) * 100
    _fob = _usd(a.get("birim_fob"))
    _final = _usd(a.get("final_birim"))
    _mas_yuzde = _f(a.get("maliyet_yuzde"))
    _adet = _f(a.get("adet"))

    # ── Başlık şeridi ──
    st.markdown(
        f'<div style="background:linear-gradient(180deg,var(--k-yuzey2),var(--k-yuzey1));'
        f'border:1px solid color-mix(in srgb,var(--k-mor) 20%,transparent);border-left:3px solid var(--k-mor);'
        f'border-radius:16px 16px 0 0;padding:14px 18px 12px;margin-top:16px">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">'
        f'<span style="font-size:14px;font-weight:700;color:var(--k-metin)">Alım Detayı</span>'
        f'<span style="font-size:13px;font-weight:700;color:var(--k-mor2);'
        f'font-family:JetBrains Mono,monospace">{a.get("belge_no") or "—"}</span></div>'
        f'</div>', unsafe_allow_html=True)

    # ── Bilgi + hesap iki sütun ──
    _sol = (
        _detay_satir("Sipariş Tarihi", gun_ay_yil(a.get("siparis_tarih")) or "—")
        + _detay_satir("Teslim Tarihi", gun_ay_yil(a.get("teslim_tarih")) or "—")
        + _detay_satir("Tedarikçi",
                       f'<span style="font-family:Inter">{(a.get("tedarikci") or "—")[:26]}</span>')
        + _detay_satir("Takip No", a.get("takip_no") or "—")
        + _detay_satir("Döviz / Kur", f'{a.get("doviz")} · {_f(a.get("kur")):.2f}')
        + _detay_satir("Durum",
                       f'<span style="color:var(--k-yesil);font-family:Inter">{a.get("durum") or "—"}</span>'))

    _indirim_str = f' · indirim %{tr_sayi(_ind, 1)}' if _ind else ''
    _sag = (
        _detay_satir("Adet", f"{tr_sayi(_adet)}", trenk("mavi"))
        + _detay_satir("Birim FOB", _fob, trenk("mavi"))
        + _detay_satir("Masraf Payı", f"%{tr_sayi(_mas_yuzde, 1)}{_indirim_str}", trenk("amber"))
        + f'<div style="margin-top:10px;padding:12px 14px;background:color-mix(in srgb,var(--k-yesil) 8%,transparent);'
          f'border:1px solid color-mix(in srgb,var(--k-yesil) 28%,transparent);border-radius:12px;text-align:center">'
          f'<div style="font-size:10px;color:var(--k-soluk);text-transform:uppercase;'
          f'letter-spacing:1px;font-weight:700;margin-bottom:2px">Final Birim Maliyet</div>'
          f'<div style="font-size:23px;font-weight:700;color:var(--k-yesil);'
          f'font-family:JetBrains Mono,monospace;letter-spacing:-0.5px">{_final}</div></div>')

    st.markdown(
        f'<div style="background:linear-gradient(180deg,var(--k-yuzey2),var(--k-yuzey1));'
        f'border:1px solid color-mix(in srgb,var(--k-mor) 20%,transparent);border-top:none;'
        f'border-radius:0 0 16px 16px;padding:14px 18px 16px;margin-bottom:12px;'
        f'display:flex;gap:24px;flex-wrap:wrap">'
        f'<div style="flex:1;min-width:220px">{_sol}</div>'
        f'<div style="flex:1;min-width:200px">{_sag}</div>'
        f'</div>', unsafe_allow_html=True)

    # ── Masraf dökümü ──
    try:
        from ithalat.database import masraf_dokumu
        _md = masraf_dokumu(a.get("_dosya") or {})
        if _md:
            st.markdown('<div style="font-size:13px;font-weight:700;color:var(--k-soluk);'
                        'margin:4px 0 6px">Dosya Masraf Dökümü</div>', unsafe_allow_html=True)
            st.dataframe(pd.DataFrame([{"Masraf": ad, "Tutar": _usd(t)} for ad, t in _md]),
                         hide_index=True, use_container_width=True,
                         height=min(320, 40 + 35 * len(_md)))
    except Exception:
        pass


def _satis_detay(s, satir_kar):
    k = satir_kar(s) if satir_kar else {}
    _destek = _f(s.get("birim_firma_destek")) + _f(s.get("birim_ek_destek"))
    _marj = _f(k.get("marj"))
    _nk = _f(k.get("net_kar"))
    _nk_renk = trenk("yesil") if _nk >= 0 else trenk("kirmizi")

    st.markdown(
        f'<div style="background:linear-gradient(180deg,var(--k-yuzey2),var(--k-yuzey1));'
        f'border:1px solid color-mix(in srgb,var(--k-mor) 20%,transparent);border-left:3px solid var(--k-mor);'
        f'border-radius:16px 16px 0 0;padding:14px 18px 12px;margin-top:16px">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">'
        f'<span style="font-size:14px;font-weight:700;color:var(--k-metin)">Satış Detayı</span>'
        f'<span style="font-size:13px;font-weight:700;color:var(--k-mor2);font-family:Inter">'
        f'{gun_ay_yil(s.get("tarih"))} · {s.get("kanal") or "—"}</span></div></div>',
        unsafe_allow_html=True)

    _sol = (
        _detay_satir("Sipariş No", s.get("siparis_no") or "—")
        + _detay_satir("Adet", f"{tr_sayi(_f(k.get('adet') or s.get('adet')))}", trenk("mavi"))
        + _detay_satir("Birim Satış", _usd(s.get("birim_satis")), trenk("mavi"))
        + _detay_satir("Birim Maliyet", _usd(s.get("birim_maliyet")), trenk("amber")))
    _sag = (
        _detay_satir("Birim Destek", _usd(_destek), trenk("mor"))
        + _detay_satir("Ciro", _usd(k.get("ciro")), trenk("mavi"))
        + f'<div style="margin-top:10px;padding:12px 14px;background:color-mix(in srgb,var(--k-yesil) 6%,transparent);'
          f'border:1px solid {_nk_renk}44;border-radius:12px;text-align:center">'
          f'<div style="font-size:10px;color:var(--k-soluk);text-transform:uppercase;'
          f'letter-spacing:1px;font-weight:700;margin-bottom:2px">Net Kâr · Marj %{tr_sayi(_marj, 1)}</div>'
          f'<div style="font-size:23px;font-weight:700;color:{_nk_renk};'
          f'font-family:JetBrains Mono,monospace;letter-spacing:-0.5px">{_usd(_nk)}</div></div>')

    st.markdown(
        f'<div style="background:linear-gradient(180deg,var(--k-yuzey2),var(--k-yuzey1));'
        f'border:1px solid color-mix(in srgb,var(--k-mor) 20%,transparent);border-top:none;'
        f'border-radius:0 0 16px 16px;padding:14px 18px 16px;margin-bottom:12px;'
        f'display:flex;gap:24px;flex-wrap:wrap">'
        f'<div style="flex:1;min-width:220px">{_sol}</div>'
        f'<div style="flex:1;min-width:200px">{_sag}</div>'
        f'</div>', unsafe_allow_html=True)

    if s.get("kampanya_id"):
        st.caption(f"Kampanya ID: {s.get('kampanya_id')}")
    if s.get("notlar"):
        st.caption(f"Not: {s.get('notlar')}")


@st.dialog("📦 Stok Kartı", width="large")
def goster(sku):
    from shared.tasarim import yan_panel; yan_panel("genis")   # sağ panel (okuma)
    sku = str(sku or "").strip()
    if not sku:
        st.warning("SKU seçilmedi.")
        return

    from kayranpm.database import (get_client, get_urun_detay, get_uretim_suresi, canli_stok,
                                   firma_son_tarihleri, firma_stok_satirlari, sku_satirlari)
    from kayranpm.stok_hesap import kanal_stoklari
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

    firma_stok = firma_stok_satirlari(sku)          # SKU yazımından bağımsız ('MIO …' = 'Mio …')
    yas_rows = _sel("stok_yas")
    yolda_rows = _sel("yoldaki_urunler")
    # Satış / iade satırları SKU yazımından bağımsız (sku_satirlari: ilike + sku_anahtar doğrulaması).
    # Eskiden esnek arama yalnız birebir eşleşme HİÇ yoksa yapılıyordu: 'Mio MiVue J30' kartında
    # 'MIO MIVUE J30' yazılı satışlar görünmüyordu (27 satışın 22'si listede) (Ekim 2026).
    satislar = sku_satirlari("satislar", sku, order="tarih", desc=True)
    kampanya_urun = _sel("kampanya_urunler")

    # İadeler — SKU yazımından bağımsız ('Fazeon X24F200' iadeleri 'X24F200' kartında)
    iadeler = sku_satirlari("iadeler", sku, order="tarih", desc=True)

    # Alımlar (ithalat) — paçal buradan hesaplanır (ayrı maliyet sorgusu yok = hızlı)
    alimlar = []
    try:
        from ithalat.database import get_sku_alim_detay
        alimlar = get_sku_alim_detay(sku) or []
    except Exception:
        pass
    _adet_t = sum(_f(a["adet"]) for a in alimlar)
    # Paçal TEK KAPIDAN (satis.get_pacal_map — Faz 2b, kullanıcı onaylı). Eskiden burada
    # alımların kendi ortalaması alınıyordu: YOLDAKİ partiler de giriyordu (13.08'de İthalat
    # özetinde düzeltilen hata buraya ulaşmamıştı), yurt içi alış yoktu. Artık Tüm Ürünler,
    # P&L ve Teknik Servis ile aynı rakam.
    try:
        from satis.database import get_pacal_map as _gpm
        from shared.utils import sku_anahtar as _skn_p
        pacal_final = float((_gpm() or {}).get(_skn_p(sku), 0) or 0)
    except Exception:  # noqa: BLE001
        pacal_final = 0.0
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
    # depo_dagilimi: aynı deponun farklı yazımları tek satır, sıfır depolar yok (Tüm Ürünler ile aynı kaynak)
    from .database import depo_dagilimi as _depo_dagilimi
    _depo_satir, _g5f_toplam = _depo_dagilimi(urun.get("depo_kirilim"))
    _g5f_satilabilir = _f(urun.get("bizim_stok"))
    # Kanal (müşteri) stoğu: her kanalın GENEL son raporu (stok_hesap — liste ve
    # panoyla aynı kural). Bu ürünün son görüldüğü satır DEĞİL: kanalın son
    # raporunda olmayan ürün satılıp bitmiştir, o kanalda 0'dır.
    try:
        _son_tarih = firma_son_tarihleri()
    except Exception:
        _son_tarih = None                 # okunamazsa satırların kendi son tarihi
    _kanal_stok = kanal_stoklari(firma_stok, son_tarih=_son_tarih)
    firma_stok_son = [r for r in firma_stok
                      if str(r.get("yukleme_tarihi") or "")[:10] == (_son_tarih or {}).get(firma_kanonik(r.get("firma")))] \
        if _son_tarih is not None else firma_stok
    # Üst rozet + stok değeri: TOPLAM STOK = bizim satılabilir depolar (Merkez +
    # Happy Life), Tüm Ürünler ve Genel Bakış'la aynı tanım (stok_hesap). Kanaldaki
    # mal satılmıştır, stok değerine girmez; iade / ikinci el depo da girmez.
    # NOT: Eskiden burada canlı hesap (_cs["canli"]) gösteriliyordu; müşteri stok
    # dosyası henüz yüklenmemişken satış girilince eksiye düşüyor ve rozette
    # '-700 adet' gibi kafa karıştıran değerler çıkıyordu (kullanıcı talebi:
    # eksiler yazmasın). Canlı hesap Analiz tarafında yaşamaya devam eder;
    # rozet ve stok değeri artık elle tutulur fiziki stoğu gösterir.
    toplam_stok = _g5f_satilabilir
    if toplam_stok <= 0 and _cs.get("var"):
        toplam_stok = max(_f(_cs.get("canli")), 0)
    yolda_adet = sum(_f(r.get("yoldaki_miktar")) for r in yolda_rows)
    liste_fiyat = _f(urun.get("satis_fiyati"))
    stok_degeri = toplam_stok * pacal_final
    ilk_gorulen = (yas_rows[0].get("ilk_gorulen_tarih") if yas_rows else "") or ""

    # Gerçek satış hızı (son 90 gün)
    _90 = (tr_today() - timedelta(days=90)).isoformat()
    _son90 = sum(_f(s.get("adet")) for s in satislar if str(s.get("tarih", ""))[:10] >= _90)
    gunluk_hiz = _son90 / 90.0
    haftalik_gercek = gunluk_hiz * 7

    # ── Ürün başlık şeridi (profesyonel) ──
    _canli_renk = trenk("yesil") if toplam_stok > 0 else trenk("kirmizi")
    st.markdown(
        f'<div style="background:linear-gradient(135deg,color-mix(in srgb,var(--k-mor) 12%,transparent),color-mix(in srgb,var(--k-cyan) 4%,transparent) 60%,transparent);'
        f'border:1px solid color-mix(in srgb,var(--k-mor) 25%,transparent);border-left:3px solid var(--k-mor);'
        f'border-radius:16px;padding:14px 18px;margin-bottom:12px">'
        f'<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">'
        f'<span style="font-size:19px;font-weight:700;color:var(--k-metin);'
        f'font-family:JetBrains Mono,monospace;letter-spacing:-0.3px">{sku}</span>'
        f'<span style="font-size:13px;color:var(--k-soluk);flex:1;min-width:180px">'
        f'{(urun.get("urun_adi") or "—")}</span>'
        f'<span style="font-size:11px;font-weight:700;color:{_canli_renk};'
        f'background:{_canli_renk}1A;padding:4px 12px;border-radius:999px;white-space:nowrap">'
        f'📦 {tr_sayi(toplam_stok)} adet</span></div>'
        f'<div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:8px;'
        f'font-size:11px;color:var(--k-silik)">'
        f'<span>Marka: <b style="color:var(--k-soluk)">{_marka_ad(urun.get("marka")) or "—"}</b></span>'
        f'<span>Kategori: <b style="color:var(--k-soluk)">{_kat_ad(urun.get("kategori")) or "—"}</b></span>'
        f'<span>Barkod: <b style="color:var(--k-soluk)">{urun.get("barkod") or "—"}</b></span>'
        f'</div></div>', unsafe_allow_html=True)

    # ── Başka bir SKU / modele geç (modal içi arama — yazdıkça filtreler,
    #    Enter gerektirmez; SKU *veya* ürün adına göre eşleşir) ──
    _gec_map = {}
    try:
        from kayranpm.database import get_tum_sku_listesi
        for _r in (get_tum_sku_listesi() or []):
            _s = str(_r.get("sku") or "")
            if not _s or _s == sku:
                continue
            _ad = (_r.get("urun_adi") or "")[:55]
            _gec_map[f"{_s}  ·  {_ad}" if _ad else _s] = _s
    except Exception:
        _gec_map = {}
    if _gec_map:
        _gec_sec = st.selectbox(
            "Başka SKU aç", sorted(_gec_map),
            index=None, key=f"stok_gec_{sku}",
            placeholder="🔍 Başka bir SKU / model yaz → listeden seç, kart açılır",
            label_visibility="collapsed")
        if _gec_sec:
            st.session_state["_stok_gec_sku"] = _gec_map[_gec_sec]
            st.rerun()

    t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs(["📊 Özet", "📥 Alımlar", "📤 Satışlar", "🎯 Kampanya", "📈 Analiz", "↩️ İade",
                                              "📜 Stok Hareketleri", "Stok yaşı"])

    # ═══ ÖZET ═══
    with t1:
        from shared.ui import RENK, pencere_css, pencere, pencere_grid, bos_durum
        st.markdown(pencere_css(), unsafe_allow_html=True)
        _yeter = (f"~{toplam_stok / haftalik_gercek:.0f} hafta yeter"
                  if haftalik_gercek > 0 else "satış verisi yok")

        # Panel verileri
        _dagilim_dolu = dict(_depo_satir)                 # zaten kanonik, sıfırsız, adede göre sıralı
        _firma_son = {}
        for r in firma_stok_son:
            _fa = firma_gorunen_ad(r.get("firma", "")) or "—"
            _ft = str(r.get("yukleme_tarihi") or "")[:10]
            if (_fa not in _firma_son) or (_ft > _firma_son[_fa][0]):
                _firma_son[_fa] = (_ft, _f(r.get("stok_miktari")), _f(r.get("haftalik_satis")))
        _musteri_toplam = sum(sum(_f(v) for v in d.values()) for d in _kanal_stok.values())

        _kart1 = (_kart("Toplam Stok", f"{tr_sayi(toplam_stok)}",
                        (f"satılabilir · tüm depolar {tr_sayi(_g5f_toplam)}"
                         if _g5f_toplam != toplam_stok else "satılabilir"), trenk("yesil"))
                  if _g5f_toplam > 0 else
                  _kart("Canlı Stok", f"{tr_sayi(toplam_stok)}", _yeter, trenk("yesil")))
        _kart_satiri([
            _kart1,
            _kart("Stok Değeri", _usd(stok_degeri), "paçal × satılabilir stok", trenk("mavi")),
            _kart("Paçal Maliyet", _usd(pacal_final), "adet-ağırlıklı", trenk("kirmizi"), anlam="notr"),
            _kart("Liste Satış", _usd(liste_fiyat), "güncel", trenk("mor2")),
        ])

        # ── İKİZ STOK PANELİ — solda bizim depolar, sağda müşteriler ──
        def _srow(ad, adet, maks, renk, alt=""):
            _w = max(2.0, min(100.0, (adet / maks * 100) if maks else 0))
            _alt = (f'<div style="color:{RENK["silik"]};font-size:11px;margin-top:0px">{alt}</div>'
                    if alt else "")
            return (f'<div style="padding:4px 12px;margin:3px 0;border-radius:6px;'
                    f'background:linear-gradient(180deg,var(--k-yuzey2),var(--k-yuzey1))">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">'
                    f'<span style="color:{RENK["metin"]};font-size:13px;font-weight:600">{ad}</span>'
                    f'<span style="color:{RENK["metin"]};font-size:13px;font-weight:700;'
                    f'font-family:JetBrains Mono,monospace">{tr_sayi(adet)}</span></div>'
                    f'<div style="height:4px;border-radius:2px;background:color-mix(in srgb,var(--k-metin) 5%,transparent)">'
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
            # Kayıtlı bizim_stok (Toplam Stok kartı) kırılımla tutmuyorsa fark yazılır (değer değiştirilmez)
            from .database import satilabilir_kontrol as _sat_kontrol
            _sk = _sat_kontrol(urun.get("depo_kirilim"), urun.get("bizim_stok"))
            if _sk["fark"]:
                _depo_html += (f'<div style="color:{RENK["amber"]};font-size:11px;margin-top:6px">'
                               f'Satılabilir kayıtlı {tr_sayi(_sk["kayitli"])}, kırılıma göre {tr_sayi(_sk["hesap"])} '
                               f'(fark {"+" if _sk["fark"] > 0 else "−"}{tr_sayi(abs(_sk["fark"]))}) — G5F sayımını yeniden yükle</div>')
        else:
            _depo_html = bos_durum("G5F depo sayımı yüklenmemiş — Ürün Yönetimi → Veri Yükleme")
        _p_depo = pencere("🏬 BİZİM DEPOLAR", RENK["yesil"], _depo_html,
                          rozet=(f"{tr_sayi(_g5f_toplam)} adet" if _g5f_toplam else ""), yukseklik=200)

        if _firma_son:
            _mmax = max(v[1] for v in _firma_son.values()) or 1
            _mus_html = "".join(
                _srow(fa, v[1], _mmax, RENK["mor"],
                      alt=f"haftalık satış {tr_sayi(v[2])} · {gun_ay_yil(v[0]) or v[0] or '—'}")
                for fa, v in sorted(_firma_son.items(), key=lambda x: -x[1][1]))
        else:
            _mus_html = bos_durum("Müşterilerde stok kaydı yok")
        _p_mus = pencere("🛍️ MÜŞTERİ STOĞU", RENK["mor"], _mus_html,
                         rozet=(f"{tr_sayi(_musteri_toplam)} adet" if _musteri_toplam else ""), yukseklik=200)

        st.markdown(pencere_grid(_p_depo, _p_mus, alt_bosluk=2), unsafe_allow_html=True)

        # Genel toplam şeridi
        _genel = toplam_stok + _musteri_toplam
        _serit = (f'<span style="color:{RENK["metin"]};font-weight:700">Kanal dahil '
                  f'<span style="font-family:JetBrains Mono,monospace">{tr_sayi(_genel)}</span></span>'
                  f'<span style="color:{RENK["silik"]}"> = satılabilir {tr_sayi(toplam_stok)} + kanallarda {tr_sayi(_musteri_toplam)}</span>')
        # NOT: 'canlı hesap' ibaresi kullanıcı talebiyle şeritten kaldırıldı
        # (müşteri stok dosyası beklenirken eksi görünüp kafa karıştırıyordu).
        if haftalik_gercek > 0:
            _serit += f'<span style="color:{RENK["silik"]}"> · {_yeter}</span>'
        if yolda_adet > 0:
            _serit += (f'<span style="color:{RENK["mavi"]}"> · 🚚 yolda '
                       f'<b style="font-family:JetBrains Mono,monospace">{tr_sayi(yolda_adet)}</b></span>')
        st.markdown(
            f'<div style="background:linear-gradient(180deg,var(--k-yuzey2),var(--k-yuzey1));border:1px solid color-mix(in srgb,var(--k-metin) 7%,transparent);'
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
                _yd.append(f"{tr_sayi(_m)} adet — {r.get('yoldaki_tedarikci') or '—'} "
                           f"(varış {gun_ay_yil(r.get('tahmini_varis_tarihi')) or '—'})")
            st.info("🚚 **Yolda:** " + " · ".join(_yd))
        st.caption(f"İlk görülme: {gun_ay_yil(ilk_gorulen) or '—'}  ·  "
                   f"Son alım: {gun_ay_yil(son_tarih) or '—'}")

    # ═══ ALIMLAR ═══
    with t2:
        if alimlar:
            _kart_satiri([
                _kart("Toplam Alınan", f"{tr_sayi(_adet_t)}", f"{len(alimlar)} parti", trenk("yesil")),
                _kart("Son Alım FOB", _usd(son_fob), gun_ay_yil(son_tarih), trenk("amber")),
                _kart("Paçal (Final)", _usd(pacal_final), "teslim alınan partiler", trenk("kirmizi"), anlam="notr"),
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
            from shared.tablo import tablo as _ortak_tablo
            _ai = _ortak_tablo([{
                "Tarih": gun_ay_yil(a["tarih"]), "Belge": a["belge_no"],
                "Tür": {"yurtici": "Yurt içi", "yerli": "Yerli üretim"}.get(a.get("alim_turu"), "İthalat"),
                "Tedarikçi": a["tedarikci"], "Ülke": a["ulke"], "Döviz": a["doviz"],
                "Adet": _f(a["adet"]), "Birim FOB": round(_f(a["birim_fob"]), 2),
                "% Maliyet": round(_f(a["maliyet_yuzde"]), 1),
                "Final Birim": round(_f(a["final_birim"]), 2),
            } for a in alimlar], key="alim_tablo", kalici=True, dosya_adi=f"alimlar_{sku}")
            st.caption("Detayını görmek için bir satıra tıkla (tekrar tıkla: kapat).")
            if _ai is not None:
                _alim_detay(alimlar[_ai])
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
                    "Marj": f"%{tr_sayi(_f(k.get('marj')), 1)}",
                })
            _om = (_tk / _tc * 100) if _tc else 0.0
            _kart_satiri([
                _kart("Toplam Satılan", f"{tr_sayi(_ta)}", f"{len(satislar)} kalem", trenk("yesil")),
                _kart("Toplam Ciro", _usd(_tc), "", trenk("mor2")),
                _kart("Toplam Kâr", _usd(_tk), f"ort. marj %{tr_sayi(_om, 1)}",
                      trenk("yesil") if _tk >= 0 else trenk("kirmizi")),
            ])
            st.markdown("**Kanal / Firma Kırılımı**")
            st.dataframe(pd.DataFrame([{
                "Kanal/Firma": kn, "Adet": v["adet"],
                "Ort. Birim": _usd(v["ciro"] / v["adet"]) if v["adet"] else _usd(0),
                "Ciro": _usd(v["ciro"]), "Kâr": _usd(v["kar"]),
                "Marj": f"%{tr_sayi((v['kar'] / v['ciro'] * 100) if v['ciro'] else 0, 1)}",
            } for kn, v in sorted(_kanal.items(), key=lambda x: -x[1]["ciro"])]),
                hide_index=True, use_container_width=True)
            st.markdown("**Satış Hareketleri**")
            from shared.tablo import tablo as _ortak_tablo
            _si = _ortak_tablo(_rows, key="satis_tablo", kalici=True, dosya_adi=f"satislar_{sku}")
            st.caption("Detayını görmek için bir satıra tıkla (tekrar tıkla: kapat).")
            if _si is not None:
                _satis_detay(satislar[_si], satir_kar)
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

            # Kampanyanın devam edip etmediğini bitiş tarihinden hesapla
            def _kamp_durum(_k):
                _bit = str(_k.get("bitis_tarihi") or "")[:10]
                _dur = (_k.get("durum") or "").lower()
                if _dur in ("kapali", "kapalı", "pasif", "iptal"):
                    return "kapali"
                try:
                    _bugun = tr_today().strftime("%Y-%m-%d")
                    if _bit and _bit < _bugun:
                        return "kapali"
                except Exception:
                    pass
                return "devam"

            _rows, _detay = [], []   # _detay: satırla aynı sırada (ku, _k) tut
            for ku in kampanya_urun:
                _k = _kamp_map.get(ku.get("kampanya_id"), {})
                _durum = _kamp_durum(_k)
                _rows.append({
                    "Durum": "🟢 Devam" if _durum == "devam" else "🔴 Bitti",
                    "Kampanya": _k.get("kampanya_adi", "") or f"#{ku.get('kampanya_id')}",
                    "Firma": _cari_ad(_k.get("firma", "")) or "—",   # cari kartındaki tam ad
                    "Tür": _k.get("kampanya_turu", "") or "—",
                    "Başlangıç": gun_ay_yil(_k.get("baslangic_tarihi")),
                    "Bitiş": gun_ay_yil(_k.get("bitis_tarihi")),
                    "Firma Destek": _usd(ku.get("birim_firma_destek")),
                    "Ek Destek": _usd(ku.get("birim_ek_destek")),
                })
                _detay.append((ku, _k))

            st.caption("Detay için bir kampanya satırına tıkla ↓")
            from shared.tablo import tablo as _ortak_tablo
            _ki = _ortak_tablo(_rows, key=f"kamp_tbl_{sku}", kalici=True, dosya_adi=f"kampanyalar_{sku}")
            st.caption(f"Bu SKU {len(kampanya_urun)} kampanyada yer almış.")

            # ── Seçilen kampanyanın detay paneli (tablonun altında açılır) ──
            if _ki is not None:
                _ku, _k = _detay[_ki]
                _durum = _kamp_durum(_k)
                _renk = trenk("yesil") if _durum == "devam" else trenk("kirmizi")
                _durum_txt = "🟢 Devam ediyor" if _durum == "devam" else "🔴 Kapanmış"
                _ad = _k.get("kampanya_adi", "") or f"#{_ku.get('kampanya_id')}"

                st.markdown(
                    f'<div style="background:linear-gradient(135deg,color-mix(in srgb,var(--k-mor) 14%,transparent),'
                    f'color-mix(in srgb,var(--k-cyan) 5%,transparent) 70%,transparent);border:1px solid color-mix(in srgb,var(--k-mor) 30%,transparent);'
                    f'border-left:3px solid {_renk};border-radius:14px;padding:16px 18px;margin-top:12px">'
                    f'<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:10px">'
                    f'<span style="font-size:16px;font-weight:700;color:var(--k-metin)">{_ad}</span>'
                    f'<span style="font-size:11px;font-weight:700;color:{_renk};'
                    f'background:{_renk}1A;padding:4px 12px;border-radius:999px">{_durum_txt}</span></div>'
                    f'<div style="display:flex;gap:20px;flex-wrap:wrap;font-size:13px;color:var(--k-soluk)">'
                    f'<span>Firma: <b style="color:var(--k-mavi)">{firma_gorunen_ad(_k.get("firma")) or "—"}</b></span>'
                    f'<span>Tür: <b style="color:var(--k-mavi)">{_k.get("kampanya_turu") or "—"}</b></span>'
                    f'<span>Kategori: <b style="color:var(--k-mavi)">{_kat_ad(_k.get("kategori")) or "—"}</b></span>'
                    f'<span>Tarih: <b style="color:var(--k-mavi)">{gun_ay_yil(_k.get("baslangic_tarihi"))} → '
                    f'{gun_ay_yil(_k.get("bitis_tarihi"))}</b></span></div></div>',
                    unsafe_allow_html=True)

                _c1, _c2, _c3, _c4 = st.columns(4)
                _c1.metric("Firma Destek", _usd(_ku.get("birim_firma_destek")))
                _c2.metric("Ek Destek", _usd(_ku.get("birim_ek_destek")))
                _c3.metric("Satış Fiyatı", _usd(_ku.get("satis_fiyati")))
                _c4.metric("Satılan Adet", f"{tr_sayi(_f(_ku.get('satilan_adet')))}")

                _sp_tl = _f(_k.get("spiff_tl"))
                _sp_kur = _f(_k.get("spiff_kur"))
                if _sp_tl:
                    _sp_usd = (f" (≈ ${tr_sayi(_sp_tl / _sp_kur, 2)})" if _sp_kur else "")
                    st.caption(f"Spiff: ₺{tr_sayi(_sp_tl, 2)}{_sp_usd}"
                               + ("  · faturalı" if _k.get("spiff_fatura") else ""))
                if _k.get("notlar"):
                    st.markdown(f"**Not:** {_k.get('notlar')}")
                if _ku.get("notlar"):
                    st.caption(f"Ürün notu: {_ku.get('notlar')}")
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
                st.warning(f"⚠️ **Düşük marj:** Teorik marj sadece %{tr_sayi(_marj, 1)}.")
            else:
                st.success(f"✅ **Sağlıklı marj:** Teorik marj %{tr_sayi(_marj, 1)}.")

        # Gerçek satış hızı + reorder + DIO
        if gunluk_hiz > 0:
            _tukenme = toplam_stok / gunluk_hiz
            _reorder = gunluk_hiz * uretim_suresi
            _kart_satiri([
                _kart("Günlük Hız", f"{gunluk_hiz:.1f}", "son 90 gün", trenk("mor2")),
                _kart("Tükenme", f"~{_tukenme:.0f} gün", "mevcut hızda", trenk("amber")),
                _kart("Stok Devir (DIO)", f"{_tukenme:.0f} gün", "elde kalma", trenk("mavi")),
            ])
            st.markdown(
                f"**Yeniden sipariş noktası:** Üretim/tedarik süresi {uretim_suresi} gün. "
                f"Stok **{tr_sayi(_reorder)} adet**'e inince sipariş ver "
                f"(şu an {tr_sayi(toplam_stok)}, yolda {tr_sayi(yolda_adet)})."
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
            _renk = {"A": trenk("yesil"), "B": trenk("amber"), "C": trenk("soluk")}[_abc]
            st.markdown(
                f"<div style='margin:8px 0'>️ <b style='color:{_renk}'>ABC Sınıfı: {_abc}</b> — "
                f"Toplam cironun %{tr_sayi(_cp, 1)}'i, toplam kârın %{tr_sayi(_kp, 1)}'i bu üründen.</div>",
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
                _kart("Toplam İade", f"{tr_sayi(_ia)}", f"{len(iadeler)} kalem · stoğa döndü", trenk("amber")),
                _kart("İade Tutarı", _usd(_it), "müşteriye iade", trenk("amber")),
                _kart("Tekrar Satılabilir", f"{tr_sayi(_ia)} adet", "stoğa eklendi", trenk("yesil")),
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
            st.caption("İade edilen mal stoğa döner ve tekrar satılabilir; kâr/marj brüt satıştan "
                       "hesaplanır, iade kârdan düşülmez.")

    # ── 📜 Stok hareket defteri ──
    with t7:
        _hareket_sekmesi(sku)

    # ═══ STOK YAŞI (FIFO, depoya girişten — kayranpm/stok_yasi.py) ═══
    with t8:
        from .stok_yasi_ekran import kart_bolumu
        kart_bolumu(sku)

    st.divider()
    if st.button("Kapat", use_container_width=True):
        st.rerun()


_TUR_ADI = {"cikis": "📤 Çıkış", "giris": "📥 Giriş", "sevk": "🔁 Sevk",
            "aktarim": "📋 Excel aktarımı", "sifirlama": "🧹 Sıfırlama", "hata": "⚠️ BAŞARISIZ"}


def _hareket_sekmesi(sku):
    """Bu SKU'nun stok hareket defteri — 'stok neden değişti?' sorusunun cevabı."""
    try:
        from shared.stok_defteri import gecmis
        rows = gecmis(sku=sku, limit=300)
    except Exception:
        rows = []
    if not rows:
        st.info("Bu ürün için kayıtlı stok hareketi yok. Defter, kurulumdan sonraki "
                "hareketleri tutar; daha eski değişimler burada görünmez.")
        return
    _hatali = [r for r in rows if not r.get("basarili", True)]
    if _hatali:
        st.error(f"⚠️ {len(_hatali)} başarısız stok işlemi var — stok bu işlemlerde "
                 f"DEĞİŞMEDİ. Nedenleri aşağıda 'Hata' sütununda.")
    _giris = sum(_f(r.get("degisim")) for r in rows if r.get("basarili", True) and _f(r.get("degisim")) > 0)
    _cikis = sum(_f(r.get("degisim")) for r in rows if r.get("basarili", True) and _f(r.get("degisim")) < 0)
    _kart_satiri([
        _kart("Kayıt", f"{tr_sayi(len(rows))}", "son 300 hareket"),
        _kart("Toplam Giriş", f"+{tr_sayi(_giris)}", "adet", trenk("yesil")),
        _kart("Toplam Çıkış", f"{tr_sayi(_cikis)}", "adet", trenk("kirmizi"), anlam="notr"),
        _kart("Başarısız", f"{tr_sayi(len(_hatali))}", "işlem", trenk("amber") if _hatali else trenk("silik")),
    ])
    _depolar = sorted({r.get("depo") or "" for r in rows} - {""})
    _sec = st.selectbox("Depo", ["Tümü"] + _depolar, key=f"sh_depo_{sku}")
    _goster = [r for r in rows if _sec == "Tümü" or r.get("depo") == _sec]
    st.dataframe(pd.DataFrame([{
        "Zaman": str(r.get("zaman") or "")[:16].replace("T", " "),
        "Tür": _TUR_ADI.get(r.get("tur"), r.get("tur") or ""),
        "Depo": r.get("depo") or "",
        "Önce": _f(r.get("onceki")), "Sonra": _f(r.get("sonraki")),
        "Değişim": _f(r.get("degisim")),
        "Açıklama": r.get("aciklama") or "",
        "Kaynak": r.get("kaynak") or "",
        "Kullanıcı": r.get("kullanici") or "",
        "Hata": r.get("hata") or "",
    } for r in _goster]), hide_index=True, use_container_width=True,
        column_config={"Değişim": st.column_config.NumberColumn(format="%+.0f")})
    st.caption("Kaynak: stok işlemini başlatan kod (ör. satis/database.py:_stok_uygula_depolu). "
               "Başarısız satırlarda Önce/Sonra 0 görünür — stok o işlemde hiç değişmemiştir.")
