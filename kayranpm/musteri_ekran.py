# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Müşteri Satışları — ekran (Ekim 2026). Hesap: musteri_hesap.py (saf, testli).

Üstte aralık + görünüm (Müşteri · Marka · Ürün · Kategori) + Excel. Haftalık dosya üst menüdeki Dosya kapısından yüklenir.
Kartlar: satış (önceki eşit döneme göre ▲/▼), kanal stoğu (son raporlar), haftalık
ortalama, kapsama. Altta yan yana: solda seçilen kırılımın listesi, sağda seçili satırın
haftalık eğilimi ve alt kırılımı (müşteri → ürünler, ürün → müşteriler, marka/kategori →
ürünler). Ürün satırına tıklayınca stok kartı açılır. Müşteri adları cari kartındaki tam ad.
"""
from datetime import date, timedelta
from functools import partial

import pandas as pd
import streamlit as st

from shared.tasarim import tr_sayi
from shared.ana_veri import urun_ad   # ürün adı = kart adı, tek kaynak (Eki 2026)
from . import musteri_hesap as H

# "Ürün" görünümü kaldırıldı (Eki 2026): ürünler marka/kategori seçilince sağdaki detayda listeleniyor.
GORUNUM = {"Müşteri": "musteri", "Marka": "marka", "Kategori": "kategori"}


def _cari(kod):
    from shared.utils import firma_gorunen_ad
    return firma_gorunen_ad(kod, kisa=False) if kod else ""


def _hf(v):
    return None if v is None else round(v, 1)


def _satirlar(gruplar, kirilim, ust_ad, mod="tam"):
    """Ortak tablo satırları. _id = grup anahtarı (seçim kimliği).
    mod: "liste" (sol, dar: ad · satış · son stok) · "detay" (sağ: + kapsama) · "tam" (Excel: hepsi).
    Dar modlarda ürün tek sütunda "SKU · ad" (iki metin sütunu dar alanda eziliyordu)."""
    out = []
    for g in gruplar:
        if kirilim == "urun":
            _ad = urun_ad(g["anahtar"], g["urun_adi"])          # kartın adı (shared.ana_veri)
            r = ({"SKU": g["anahtar"], "Ürün": _ad or "—"} if mod == "tam"
                 else {"Ürün": f'{g["anahtar"]} · {_ad}' if _ad else g["anahtar"]})
        else:
            r = {ust_ad: g["ad"]}
        r.update({"Satış adedi": g["satis"], "Son stok": g["stok"]})
        if mod == "tam":
            r["Haftalık ort."] = round(g["haftalik_ort"], 1)
        if mod in ("tam", "detay"):
            r["Kapsama (hafta)"] = _hf(g["kapsama"])
        r["_id"] = g["anahtar"]
        out.append(r)
    return out


def _onceki(bas, bit):
    try:
        b, e = date.fromisoformat(str(bas)[:10]), date.fromisoformat(str(bit)[:10])
    except (TypeError, ValueError):
        return None, None
    gun = (e - b).days + 1
    return b - timedelta(days=gun), b - timedelta(days=1)


def _excel(ozet_df, detay_df, ozet_ad):
    import io
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        ozet_df.to_excel(w, index=False, sheet_name=ozet_ad[:31])
        detay_df.to_excel(w, index=False, sheet_name="Ham Detay")
        for sn, d in ((ozet_ad[:31], ozet_df), ("Ham Detay", detay_df)):
            ws = w.sheets[sn]
            for i, kol in enumerate(d.columns, start=1):
                uzun = max([len(str(kol))] + [len(str(v)) for v in d[kol].head(200)])
                ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = min(max(uzun + 2, 10), 48)
            ws.freeze_panes = "A2"
    return buf.getvalue()


def _egilim(seri, haftalar, key):
    if len(seri) < 2:
        return
    import plotly.graph_objects as go
    from shared.grafik import goster, rol
    x = [f"{h[8:10]}.{h[5:7]}" for h in haftalar]
    fg = go.Figure()
    fg.add_bar(x=x, y=seri, marker_color=rol("ana"), marker_line=dict(width=0),
               customdata=[f"{tr_sayi(v)} adet" for v in seri], hovertemplate="%{x} · %{customdata}<extra></extra>")
    goster(fg, key=key, yukseklik=150, aciklama=False, bargap=0.3,
           xaxis=dict(type="category"), yaxis=dict(tickformat=",d"))


_KART_KAYNAK = {"sku": "SKU birebir", "tablo": "Onaylı eşleme", "kural": "Ürün adı / model kodu",
                "belirsiz": "Belirsiz, onay bekliyor"}


def _eslesme_bolumu(rows, meta, kartlar, eslesme_satir):
    """Kart eşleşmesi bekleyen rapor kodları: belirsiz (birden çok aday) ve hiç bulunamayanlar.
    Kullanıcı kartı seçip onaylar → sku_eslesme. Koruma musteri_hesap.eslesme_dogrula'da:
    kendisi kart SKU'su olan kod (F11PA650BWM) başka bir karta (F11PA650BBM) bağlanamaz."""
    from .database import SKU_ESLESME_SQL, sku_eslesme_kaydet, sku_eslesme_sil
    bekleyen = sorted((k for k, m in meta.items() if m.get("kart_kaynak") in ("belirsiz", "")),
                      key=lambda k: (meta[k].get("kart_kaynak") != "belirsiz", k))
    n_bel = sum(1 for k in bekleyen if meta[k].get("kart_kaynak") == "belirsiz")
    with st.expander(f"Kart eşleşmesi bekleyen kodlar ({len(bekleyen)})", icon=":material/link:"):
        st.caption("Rapordaki kod hiçbir stok kartına bağlanamadı ya da birden çok karta uyuyor "
                   f"({n_bel} belirsiz). Belirsizde program seçim yapmaz; doğru kartı sen onaylarsın. "
                   "Kendi stok kartı olan bir kod başka bir karta bağlanamaz.")
        if eslesme_satir is None:
            st.info("Onaylı eşlemeler için 'sku_eslesme' tablosu henüz yok. Supabase → SQL Editor'de "
                    "bir kez çalıştırın (veritabani/10_sku_eslesme.sql):")
            st.code(SKU_ESLESME_SQL, language="sql")
            return
        adlar = {}
        for r in rows:
            adlar.setdefault(str(r.get("sku") or "").strip(), str(r.get("urun_adi") or "").strip())

        def _kart_etiket(ks):
            ad = (kartlar.get(ks) or {}).get("urun_adi") or ""
            return f"{ks} · {ad}" if ad else ks

        if bekleyen:
            c1, c2, c3 = st.columns([1.2, 1.2, 0.6], vertical_alignment="bottom")
            dis = c1.selectbox(
                "Rapordaki kod", bekleyen, key="mhs_es_dis",
                format_func=lambda k: f"{k} · {adlar.get(k) or '—'}" + (
                    f" · {len(meta[k]['adaylar'])} aday" if meta[k].get("adaylar") else ""))
            aday = list(meta[dis].get("adaylar") or [])
            secenek = aday + sorted(k for k in kartlar if k not in aday)
            kart = c2.selectbox("Stok kartı", secenek, index=None, key=f"mhs_es_kart_{dis}",
                                placeholder="Aday kartlar başta", format_func=_kart_etiket)
            if c3.button("Eşlemeyi kaydet", key="mhs_es_kaydet", icon=":material/link:",
                         disabled=not kart, use_container_width=True):
                ok, msg = sku_eslesme_kaydet(dis, kart, st.session_state.get("aktif_kullanici", ""))
                if ok:
                    st.toast(msg)
                    st.rerun()
                st.error(msg)
        else:
            st.caption("Bu aralıkta bekleyen kod yok.")
        if eslesme_satir:
            st.markdown("**Onaylı eşlemeler**")
            st.dataframe(pd.DataFrame([{"Rapordaki kod": r.get("dis_kod"), "Stok kartı": _kart_etiket(r.get("kart_sku")),
                                        "Onaylayan": r.get("onaylayan") or "—",
                                        "Tarih": str(r.get("created_at") or "")[:10]} for r in eslesme_satir]),
                         hide_index=True, use_container_width=True)
            k1, k2 = st.columns([2.4, 0.6], vertical_alignment="bottom")
            sil = k1.selectbox("Kaldırılacak eşleme", [r.get("dis_kod") for r in eslesme_satir], index=None,
                               key="mhs_es_sil", placeholder="Seç")
            if k2.button("Kaldır", key="mhs_es_sil_btn", icon=":material/link_off:", disabled=not sil,
                         use_container_width=True):
                ok, msg = sku_eslesme_sil(sil)
                if ok:
                    st.toast(msg)
                    st.rerun()
                st.error(msg)


def render():
    from shared.tarih import hizli_tarih_araligi
    from shared.utils import metrik_satiri
    from shared.tablo import tablo
    from .database import get_musteri_haftalik_satis, get_urun_marka_kategori

    bas, bit = hizli_tarih_araligi(
        "mhs", varsayilan="Geçen hafta",
        secenekler=["Geçen hafta", "Bu ay", "Geçen ay", "Son 30 gün", "Son 90 gün", "Bu yıl", "Geçen yıl",
                    "Tümü", "Özel…"])
    c1, c3 = st.columns([4.2, 1], vertical_alignment="bottom")
    if st.session_state.get("mhs_gorunum") not in GORUNUM:       # eski oturumda "Ürün" seçiliyse
        st.session_state.pop("mhs_gorunum", None)
    gor = c1.segmented_control("Görünüm", list(GORUNUM), default="Müşteri", key="mhs_gorunum",
                               label_visibility="collapsed") or "Müşteri"
    kir = GORUNUM[gor]

    rows = get_musteri_haftalik_satis(bas, bit) or []
    if not rows:
        st.info("Bu aralıkta haftalık satış raporu yok. Aralığı genişlet ya da haftalık dosyayı üst menüdeki Dosya düğmesinden yükle.")
        return
    # Kart eşleştirme + kategori çözümü (musteri_hesap.meta_hazirla): ham SKU tutmasa da
    # normalize SKU / SKU parçası / ürün adıyla kart bulunur; kartta kategori boşsa addan tahmin.
    from shared.utils import sku_anahtar
    from .database import kategori_oner, marka_oner, KATEGORI_LISTE, MARKA_KURALLAR, get_sku_eslesme
    kartlar = get_urun_marka_kategori() or {}
    eslesme_satir = get_sku_eslesme()               # None: tablo kurulmamış (kurallar yine çalışır)
    meta = H.meta_hazirla(rows, kartlar, sku_fn=sku_anahtar,
                          oner=kategori_oner, kategori_liste=KATEGORI_LISTE,
                          marka_oner=marka_oner, marka_liste=[m for m, _ in MARKA_KURALLAR],
                          eslesme={r.get("dis_kod"): r.get("kart_sku") for r in (eslesme_satir or [])})
    oz = H.ozet(rows)

    # Önceki eşit dönem (satış karşılaştırması). Okunamazsa rozet çıkmaz, sayfa çalışır.
    ob, oe = _onceki(bas, bit)
    try:
        onceki = H.ozet(get_musteri_haftalik_satis(str(ob), str(oe)) or [])["satis"] if ob else None
    except Exception:  # noqa: BLE001
        onceki = None

    metrik_satiri([
        {"label": "Satış (aralık)", "value": f"{tr_sayi(oz['satis'])} adet", "vurgu": True,
         "simdi": oz["satis"], "onceki": onceki or None, "seri": oz["seri"],
         "alt": f"{oz['hafta']} haftalık rapor" + (" · önceki eşit döneme göre" if onceki else "")},
        {"label": "Kanal stoğu", "value": f"{tr_sayi(oz['stok'])} adet", "alt": "her müşterinin son raporu"},
        {"label": "Haftalık ortalama", "value": f"{tr_sayi(oz['haftalik_ort'], 0)} adet", "alt": "adet / hafta"},
        {"label": "Kapsama", "value": (f"{tr_sayi(oz['kapsama'], 1)} hafta" if oz["kapsama"] is not None else "—"),
         "alt": "kanal stoğu ÷ haftalık ortalama"},
    ])

    gruplar = H.grupla(rows, kir, meta, ad_fn=_cari)
    ust_ad = gor
    satirlar = _satirlar(gruplar, kir, ust_ad, mod="liste")

    # Excel: bu görünümün özeti + ham satırlar (yalnız tıklanınca üretilir)
    ham = pd.DataFrame([{"Rapor": str(r.get("yukleme_tarihi") or "")[:10], "Müşteri": _cari(r.get("firma")),
                         "SKU": r.get("sku", ""), "Ürün": urun_ad(r.get("sku"), r.get("urun_adi")),
                         "Marka": (meta.get(str(r.get("sku") or "").strip()) or {}).get("marka", ""),
                         "Marka kaynağı": {"kart": "Stok kartı", "tahmin": "Ürün adından tahmin"}.get(
                             (meta.get(str(r.get("sku") or "").strip()) or {}).get("marka_kaynak"), "—"),
                         "Kategori": (meta.get(str(r.get("sku") or "").strip()) or {}).get("kategori", ""),
                         "Kategori kaynağı": {"kart": "Stok kartı", "tahmin": "Ürün adından tahmin"}.get(
                             (meta.get(str(r.get("sku") or "").strip()) or {}).get("kategori_kaynak"), "—"),
                         "Stok kartı": (meta.get(str(r.get("sku") or "").strip()) or {}).get("kart_sku", ""),
                         "Kart eşleşmesi": _KART_KAYNAK.get(
                             (meta.get(str(r.get("sku") or "").strip()) or {}).get("kart_kaynak"), "—"),
                         "Satış adedi": H.satis(r), "Stok": H.stok(r)} for r in rows])
    ozet_df = pd.DataFrame([{k: v for k, v in s.items() if not k.startswith("_")}
                            for s in _satirlar(gruplar, kir, ust_ad, mod="tam")])          # Excel: tüm sütunlar
    c3.download_button("Excel", partial(_excel, ozet_df, ham, f"{gor} özeti"),
                       f"musteri_satislari_{kir}_{bas}_{bit}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       key="mhs_xlsx", icon=":material/download:", use_container_width=True)

    sol, sag = st.columns([1, 1.25], gap="medium")
    with sol:
        sec = tablo(satirlar, key=f"mhs_liste_{kir}", kalici=True, pay="Satış adedi", kompakt=True,
                    dosya_adi=f"musteri_satislari_{kir}")
        if kir in ("kategori", "marka"):
            _alan = _ad = kir
            _tah = sorted(k for k, m in meta.items() if m.get(f"{_alan}_kaynak") == "tahmin")
            _yok = sorted(k for k, m in meta.items() if not m.get(_alan))
            if _tah or _yok:
                st.caption(
                    (f"{len(_tah)} ürünün {_ad} bilgisi stok kartında yok; ürün adından tahmin edildi. " if _tah else "")
                    + (f"{len(_yok)} ürün hâlâ {'kategorisiz' if kir == 'kategori' else 'markasız'}. " if _yok else "")
                    + "Kalıcı yapmak için: Ürün Yönetimi → Toplu Kategori & Marka.",
                    help=("Tahmin: " + ", ".join(_tah[:30]) + (" …" if len(_tah) > 30 else "") if _tah else "")
                    + (("\n\nEşleşmeyen: " + ", ".join(_yok[:30]) + (" …" if len(_yok) > 30 else "")) if _yok else ""))
        _eslesme_bolumu(rows, meta, kartlar, eslesme_satir)
    secili = gruplar[sec] if sec is not None else (gruplar[0] if gruplar else None)
    with sag:
        if not secili:
            return
        baslik = secili["ad"] if kir != "urun" else f"{secili['anahtar']} · {urun_ad(secili['anahtar'], secili['urun_adi'])}"
        st.markdown(f'<div style="font-weight:600;font-size:14.5px;margin:2px 0 0">{baslik}</div>'
                    f'<div style="font-size:12px;color:var(--k-silik);margin-bottom:4px">'
                    f'{tr_sayi(secili["satis"])} adet satış · son stok {tr_sayi(secili["stok"])} · '
                    f'pay %{tr_sayi(secili["pay"], 1)}'
                    + ("" if sec is not None else " · en çok satan (listeden seç)") + '</div>',
                    unsafe_allow_html=True)
        _egilim(secili["seri"], oz["haftalar"], key=f"mhs_egilim_{kir}")
        alt_kir = H.ALT[kir]
        alt = H.detay(rows, kir, secili["anahtar"], meta, ad_fn=_cari)
        alt_ad = {"urun": "Ürün", "musteri": "Müşteri"}[alt_kir]
        tik = tablo(_satirlar(alt, alt_kir, alt_ad, mod="detay"), key=f"mhs_detay_{kir}", secilebilir=(alt_kir == "urun"),
                    pay="Satış adedi", kompakt=True, dosya_adi=f"detay_{kir}")
        if alt_kir == "urun":
            st.caption("Ürüne tıkla: stok kartı açılır.")
            if tik is not None and 0 <= int(tik) < len(alt):
                from .stok_karti import goster as _stok_karti
                _sk = alt[int(tik)]["anahtar"]
                _stok_karti((meta.get(_sk) or {}).get("kart_sku") or _sk)   # rapor SKU'su ≠ kart SKU'su olabilir
