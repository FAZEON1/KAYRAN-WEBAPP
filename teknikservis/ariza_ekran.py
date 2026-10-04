# -*- coding: utf-8 -*-
"""Teknik Servis › Arıza oranı sayfası (Ekim 2026). Hesap: teknikservis/ariza_orani.py. Salt okunur."""
from datetime import date

import streamlit as st

from shared.tasarim import tr_sayi

from . import ariza_orani as A


@st.cache_data(ttl=300, show_spinner=False)
def _veri(bas, bit):
    """Dönemin bütün girdileri — servis kayıtları, satışlar, müşteri stoğu, alımlar, kartlar."""
    from kayranpm.database import _hepsi
    from kayranpm.stok_hesap import kanal_stoklari
    from kayranpm.stok_yasi import _bizim_partiler_oku
    from satis.database import get_satislar_yalin
    from shared.utils import sku_anahtar
    from .database import get_kayitlar
    kayitlar = get_kayitlar() or []
    kartlar = {}
    for u in _hepsi("urunler", "sku, urun_adi, kategori, marka"):
        k = sku_anahtar(u.get("sku"))
        if k:
            kartlar.setdefault(k, u)
    servis = A.servis_ozeti(kayitlar, sku_anahtar, bas, bit)
    # Payda bütün satış geçmişi (bitişe kadar); dönem yalnız servis kayıtlarına uygulanır.
    satis = A.satis_toplami(get_satislar_yalin(None, bit) or [], sku_anahtar, None, bit)
    mstok = A.musteri_stogu(kanal_stoklari(_hepsi("firma_stok", "firma, sku, stok_miktari, yukleme_tarihi")))
    alim = A.alim_toplami(_bizim_partiler_oku())
    rows = A.satirlar(kartlar, alim, satis, mstok, servis)
    kayit_rows = []
    for k in kayitlar:
        g = A._gun(k.get("mal_kabul_tarihi") or k.get("olusturma_tarihi"))
        if g and (g < str(bas) or g > str(bit)):
            continue
        s, t = A.sonuc(k)
        kayit_rows.append({"_id": k.get("id"), "Form no": k.get("servis_form_no") or "",
                           "Tarih": g, "Giriş": {"teknik": "Teknik", "iade": "İade"}.get(k.get("arayuz"), "Evraksız"),
                           "SKU": k.get("stok_kodu") or "", "Seri no": k.get("seri_no") or "",
                           "Arıza sonucu": s, "Kaynak": "Tahmin" if t else "Teknisyen",
                           "Arıza beyanı": (k.get("ariza") or "")[:120],
                           "Yapılan işlem": (k.get("yapilan_islem") or "")[:120]})
    return {"satirlar": rows, "kayitlar": kayit_rows}


@st.cache_data(ttl=600, show_spinner=False)
def _ilk_kayit_tarihi():
    from .database import get_kayitlar
    g = [A._gun(k.get("mal_kabul_tarihi") or k.get("olusturma_tarihi")) for k in get_kayitlar() or []]
    g = [x for x in g if x]
    return min(g) if g else ""


def goster():
    from shared.tasarim import baslik as _sb
    from shared.tablo import tablo
    from shared.utils import metrik_satiri, tr_now
    st.markdown(_sb(":material/troubleshoot: Teknik Servis", "Arıza oranı",
                    aciklama="SKU bazında: son kullanıcıya ulaşan ürünlerin kaçı arızalı olarak servise geldi"),
                unsafe_allow_html=True)
    bugun = tr_now().date()
    ilk = _ilk_kayit_tarihi()
    try:
        varsayilan = date.fromisoformat(ilk) if ilk else date(bugun.year, 1, 1)
    except ValueError:
        varsayilan = date(bugun.year, 1, 1)
    c1, c2, c3 = st.columns([1, 1, 1], vertical_alignment="bottom")
    bas = c1.date_input("Başlangıç", value=varsayilan, key="ao_bas", format="DD.MM.YYYY")
    bit = c2.date_input("Bitiş", value=bugun, key="ao_bit", format="DD.MM.YYYY")
    if c3.button("Yenile", icon=":material/refresh:", key="ao_yenile", use_container_width=True):
        _veri.clear()
        _ilk_kayit_tarihi.clear()
        st.rerun()
    _ilk_tr = ('%s.%s.%s' % (ilk[8:10], ilk[5:7], ilk[:4])) if ilk else '—'
    st.caption(f"Arıza oranı = arızalı ÷ son kullanıcıya ulaşan · servis kayıtları {_ilk_tr}'den beri, "
               "oran şimdilik alt sınır",
               help="Son kullanıcıya ulaşan = bitiş tarihine kadar müşterilere net satılan (bütün satış geçmişi) − "
                    "müşterinin son stok raporundaki stok (raporu olmayan müşteriye satılanın tamamı ulaşmış sayılır). "
                    "Arızalı = dönemde servise gelip arıza sonucu \"Arıza doğrulandı\" olan, aynı seri numarası bir kez. "
                    "Arıza sonucu girilmemiş eski kayıtlarda sonuç metinden tahmin edilir.")
    try:
        from shared.islem import bekle
        with bekle("Arıza oranı hesaplanıyor…"):
            v = _veri(bas, bit)
    except Exception as e:  # noqa: BLE001
        st.error(f"Arıza oranı hesaplanamadı: {type(e).__name__}: {str(e)[:120]}")
        return
    rows = v["satirlar"]
    kats = sorted({r["Kategori"] for r in rows if r["Kategori"]})
    f1, f2 = st.columns([3, 1], vertical_alignment="bottom")
    secili = f1.multiselect("Kategori", kats, key="ao_kat", placeholder="Tüm kategoriler")
    yalniz = f2.toggle("Yalnız servise gelenler", value=True, key="ao_yalniz")
    if secili:
        rows = [r for r in rows if r["Kategori"] in secili]
    if yalniz:
        rows = [r for r in rows if r["Servise gelen"]]
    ulasan = sum(r["Son kullanıcıya ulaşan"] for r in rows)
    arizali = sum(r["Arızalı"] for r in rows)
    tahmini = sum(r["Arızalının tahmini"] for r in rows)
    genel = A.oran(arizali, ulasan)
    metrik_satiri([
        {"label": "Son kullanıcıya ulaşan", "value": tr_sayi(ulasan)},
        {"label": "Servise gelen", "value": tr_sayi(sum(r["Servise gelen"] for r in rows))},
        {"label": "Arızalı", "value": tr_sayi(arizali), "alt": f"{tr_sayi(tahmini)} tanesi tahmin"},
        {"label": "Arıza oranı", "value": "—" if genel is None else f"%{tr_sayi(genel, 2)}"},
    ])
    kat_rows = A.grup_ozeti(rows, "Kategori")
    marka_rows = A.grup_ozeti(rows, "Marka")
    kayit_rows = v["kayitlar"]
    if secili or yalniz:
        skular = {r["SKU"] for r in rows}
        from shared.utils import sku_anahtar
        anahtarlar = {sku_anahtar(s) for s in skular}
        kayit_rows = [k for k in kayit_rows if sku_anahtar(k["SKU"]) in anahtarlar]
    from kayranpm.stok_yasi import excel_bytes
    st.download_button("Excel: tümü", excel_bytes({"Ürünler": rows, "Kategori": kat_rows, "Marka": marka_rows,
                                                   "Servis kayıtları": kayit_rows}),
                       file_name=f"ariza_orani_{bas}_{bit}.xlsx", icon=":material/download:", key="ao_xl")
    t1, t2, t3, t4 = st.tabs(["Ürünler", "Kategori", "Marka", "Servis kayıtları"])
    with t1:
        tablo(rows, key="ao_urun", arama=True, dosya_adi="ariza_orani_urunler")
    with t2:
        tablo(kat_rows, key="ao_kat_tbl", arama=True, dosya_adi="ariza_orani_kategori")
    with t3:
        tablo(marka_rows, key="ao_marka_tbl", arama=True, dosya_adi="ariza_orani_marka")
    with t4:
        dag = {}
        for k in kayit_rows:
            d = dag.setdefault(k["Arıza sonucu"], {"Arıza sonucu": k["Arıza sonucu"], "Kayıt": 0, "Tahmin": 0})
            d["Kayıt"] += 1
            d["Tahmin"] += 1 if k["Kaynak"] == "Tahmin" else 0
        tablo(sorted(dag.values(), key=lambda d: -d["Kayıt"]), key="ao_dagilim", dosya_adi="ariza_sonuc_dagilimi")
        st.caption("Tahmin edilen sonucu düzeltmek için kaydı Teknik Servis ya da İade listesinden açıp "
                   "Durum Güncelle ekranında \"Arıza sonucu\"nu seç.")
        tablo(kayit_rows, key="ao_kayit", arama=True, dosya_adi="ariza_servis_kayitlari")
