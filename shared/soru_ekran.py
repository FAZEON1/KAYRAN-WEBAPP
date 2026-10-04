# -*- coding: utf-8 -*-
"""Soru sor sayfası (Ekim 2026). Türkçe soru → mevcut hesaplardan cevap. YALNIZ OKUR.

Çözümleme: shared/soru.py · cevap: shared/soru_cevap.py. Anlaşılan parçalar etiket olarak
görünür; "Düzelt" ile her parça elle değiştirilebilir. Sorular (anlaşılmayanlar dahil)
soru_kayitlari tablosuna yazılır (veritabani/21) — tablo yoksa sessizce geçilir.
"""
import html as _h
from datetime import date

import streamlit as st

from shared.soru import (coz, parcalar, donem_bul, sade, ORNEKLER, OLCU_AD, KIRILIM_AD, TIP_AD)

BEKLEYEN = "_soru_bekleyen"          # paletten / ana sayfadan gelen soru


def sor(metin):
    """Başka yerden (palet, ana sayfa) soru sorup bu sayfaya git."""
    st.session_state[BEKLEYEN] = str(metin or "").strip()
    st.session_state.aktif_uygulama = "soru"


@st.cache_data(ttl=600, show_spinner=False)
def _sozluk():
    from shared.soru_cevap import sozluk_kur
    return sozluk_kur()


def anlasilir_mi(metin):
    """Palet ve ana sayfa araması için: metin bir SORU olarak anlaşılıyor mu (sözlük önbellekte).
    Tek kelime ("stok") ya da yalnız SKU sayılmaz — onlar sayfa / stok kartı aramasıdır."""
    if len(str(metin or "").split()) < 2:
        return False
    try:
        return coz(metin, _sozluk()).get("tip") not in (None, "urun")
    except Exception:  # noqa: BLE001
        return False


def _kaydet(kullanici, metin, n):
    anahtar = "_soru_kayitli"
    gorulen = st.session_state.setdefault(anahtar, set())
    if metin in gorulen:
        return
    gorulen.add(metin)
    try:
        from kayranpm.database import get_client
        get_client().table("soru_kayitlari").insert({
            "kullanici": kullanici, "metin": metin[:500], "anlasildi": bool(n.get("tip")),
            "konu": n.get("tip")}).execute()
    except Exception:  # noqa: BLE001 — tablo kurulmamışsa kayıt tutulmaz, soru yine cevaplanır
        pass


def _css():
    return """<style>
.sq-parca{display:flex;flex-wrap:wrap;gap:6px;margin:2px 0 14px}
.sq-p{display:inline-flex;align-items:baseline;gap:6px;padding:3px 10px;border-radius:999px;font-size:12.5px;
  background:color-mix(in srgb,var(--k-mor) 10%,transparent);border:1px solid color-mix(in srgb,var(--k-mor) 28%,transparent);
  color:var(--k-metin)}
.sq-p i{font-style:normal;color:var(--k-silik);font-size:11.5px}
.sq-baslik{font-size:17px;font-weight:600;color:var(--k-metin);margin:6px 0 10px}
.sq-kaynak{font-size:12px;color:var(--k-silik);margin-top:6px}
</style>"""


def _parca_html(p):
    return '<div class="sq-parca">' + "".join(
        f'<span class="sq-p"><i>{_h.escape(t)}</i>{_h.escape(e)}</span>' for t, e in p) + "</div>"


def _duzelt(n, sozluk):
    """Anlaşılan parçaları elle değiştirme. Değişen alan niyete yazılır."""
    bugun = date.today()
    with st.expander("Düzelt", icon=":material/tune:"):
        c1, c2, c3 = st.columns(3)
        konular = list(TIP_AD)
        tip = c1.selectbox("Konu", konular, index=konular.index(n["tip"]) if n.get("tip") in konular else 0,
                           format_func=lambda x: TIP_AD[x], key="sq_d_tip")
        donemler = ["Bugün", "Dün", "Bu hafta", "Geçen hafta", "Bu ay", "Geçen ay", "Bu çeyrek", "Geçen çeyrek",
                    "Son 30 gün", "Son 90 gün", "Bu yıl", "Geçen yıl", "Tüm zamanlar"]
        mevcut = (n.get("donem") or {}).get("ad")
        sec = [mevcut] + [x for x in donemler if x != mevcut] if mevcut else donemler
        dad = c2.selectbox("Dönem", sec, key="sq_d_donem")
        firmalar = ["Tümü"] + sorted(sozluk.get("firmalar") or {})
        fsec = c3.selectbox("Firma", firmalar, index=firmalar.index(n["firma"]) if n.get("firma") in firmalar else 0,
                            key="sq_d_firma")
        c4, c5, c6 = st.columns(3)
        kats = ["Tümü"] + list(sozluk.get("kategoriler") or [])
        ksec = c4.selectbox("Kategori", kats, index=kats.index(n["kategori"]) if n.get("kategori") in kats else 0,
                            key="sq_d_kat")
        mars = ["Tümü"] + list(sozluk.get("markalar") or [])
        msec = c5.selectbox("Marka", mars, index=mars.index(n["marka"]) if n.get("marka") in mars else 0,
                            key="sq_d_marka")
        kirs = ["Toplam"] + list(KIRILIM_AD)
        kir = c6.selectbox("Kırılım", kirs, index=kirs.index(n["kirilim"]) if n.get("kirilim") in kirs else 0,
                           format_func=lambda x: KIRILIM_AD.get(x, x), key="sq_d_kir")
        olculer = list(OLCU_AD)
        olcu = st.radio("Ölçü", olculer, horizontal=True, format_func=lambda x: OLCU_AD[x], key="sq_d_olcu",
                        index=olculer.index(n["olcu"]) if n.get("olcu") in olculer else 0)
    m = dict(n)
    m["tip"] = tip
    if dad != mevcut:
        d = donem_bul(sade(dad), bugun)
        if d:
            m["donem"], m["donem_varsayilan"] = d, False
    if fsec != (n.get("firma") or "Tümü"):
        m["firma"] = None if fsec == "Tümü" else fsec
        m["kanallar"] = [] if fsec == "Tümü" else list((sozluk.get("firmalar") or {}).get(fsec) or [])
    m["kategori"] = None if ksec == "Tümü" else ksec
    m["marka"] = None if msec == "Tümü" else msec
    m["kirilim"] = None if kir == "Toplam" else kir
    if m["kirilim"] and not m.get("sira"):
        m["sira"] = "azalan"
    if m["kirilim"] == "urun" and not m.get("limit"):
        m["limit"] = 10
    m["olcu"] = olcu
    if m["tip"] in ("satis", "seyir", "iade", "ariza") and not m.get("donem"):
        m["donem"] = {"bas": date(bugun.year, 1, 1), "bit": bugun, "ad": "Bu yıl"}
    if m["tip"] == "seyir":
        m["kirilim"] = "ay"
    return m


def _grafik(g):
    import plotly.graph_objects as go
    from shared.grafik import goster, rol, isaretli
    from shared.tasarim import tr_sayi
    fg = go.Figure()
    para = "$" in g["etiket"]
    yuzde = "%" in g["etiket"]
    metin = [(f"%{tr_sayi(v, 1)}" if yuzde else ("$" if para else "") + tr_sayi(v, 0)) for v in g["y"]]
    if g.get("cizgi"):
        fg.add_scatter(x=g["x"], y=g["y"], mode="lines+markers", name=g["etiket"], customdata=metin,
                       hovertemplate="%{x}: %{customdata}<extra></extra>",
                       line=dict(color=rol("ana"), width=2), marker=dict(size=8))
    else:
        fg.add_bar(x=g["x"], y=g["y"], name=g["etiket"], marker_color=isaretli(g["y"]), customdata=metin,
                   hovertemplate="%{x}: %{customdata}<extra></extra>")
    goster(fg, key="sq_grafik", yukseklik=260, aciklama=False,
           yaxis=dict(tickprefix="$" if para else "", tickformat=",.0f"), xaxis=dict(tickangle=-30))


def _cevap_ciz(c):
    from shared.utils import metrik_satiri
    from shared.tablo import tablo
    st.markdown(f'<div class="sq-baslik">{_h.escape(c["baslik"])}</div>', unsafe_allow_html=True)
    if c.get("yetki"):
        st.info(c["yetki"], icon=":material/lock:")
        return
    for u in c.get("uyarilar") or []:
        st.caption(u)
    if c.get("bos"):
        st.info(c["bos"], icon=":material/info:")
        return
    if c.get("kartlar"):
        metrik_satiri([{"label": k["etiket"], "value": k["deger"], "alt": k.get("alt") or ""} for k in c["kartlar"]])
    if c.get("grafik") and len(c["grafik"]["x"]) > 1:
        _grafik(c["grafik"])
    if c.get("satirlar"):
        tablo(c["satirlar"], key="sq_tablo", dosya_adi="soru_cevabi")
    alt1, alt2 = st.columns([5, 1.4], vertical_alignment="center")
    alt1.markdown(f'<div class="sq-kaynak">Kaynak: {_h.escape(c.get("kaynak") or "")}</div>',
                  unsafe_allow_html=True)
    if c.get("hedef"):
        if alt2.button("Sayfaya git", icon=":material/arrow_forward:", key="sq_git", use_container_width=True):
            from shared.palet import git
            git(c["hedef"])


def sayfa(kullanici, yetkiler, kar_acik):
    """yetkiler: {modül: bool}; kar_acik: kâr / marj görünür mü (shared.kar_gizle)."""
    from shared.tasarim import baslik
    from shared.soru_cevap import cevapla
    st.markdown(_css(), unsafe_allow_html=True)
    st.markdown(baslik(":material/forum: Soru sor", "Programa sor",
                       aciklama="Türkçe yazın; cevap programın kendi hesaplarından gelir, hiçbir kayıt değişmez."),
                unsafe_allow_html=True)

    bekleyen = st.session_state.pop(BEKLEYEN, None)
    if bekleyen:
        st.session_state["sq_metin"] = bekleyen
        for k in [k for k in st.session_state if str(k).startswith("sq_d_")]:
            del st.session_state[k]                      # yeni soru: eski düzeltmeler sıfırlanır

    def _yeni_soru():
        for k in [k for k in st.session_state if str(k).startswith("sq_d_")]:
            del st.session_state[k]

    metin = st.text_input("Soru", key="sq_metin", label_visibility="collapsed", on_change=_yeni_soru,
                          placeholder="Örn. geçen ay D-MARKET'te en çok kâr bıraktıran 5 monitör",
                          icon=":material/search:")
    ornek = st.pills("Örnek sorular", ORNEKLER, key="sq_ornek", label_visibility="collapsed")
    if ornek and ornek != st.session_state.get("_sq_son_ornek"):
        st.session_state["_sq_son_ornek"] = ornek
        st.session_state[BEKLEYEN] = ornek
        st.rerun()
    if not (metin or "").strip():
        st.caption("Satış, kâr, iade, stok, yaşlı stok, arıza oranı, kampanya, ödeme ve çek sorularını anlar. "
                   "Dönem (geçen ay, bu çeyrek, eylül, 2025), firma, kategori, marka ve \"en çok 5\" gibi "
                   "sıralamalar yazılabilir.")
        return

    sozluk = _sozluk()
    n = coz(metin, sozluk)
    _kaydet(kullanici, metin.strip(), n)
    if not n.get("tip"):
        st.warning("Bu soruyu anlayamadım. Konuyu (satış, kâr, stok, iade, arıza, kampanya, ödeme, çek) ve "
                   "isterseniz dönemi yazın ya da yukarıdaki örneklerden birini seçin.",
                   icon=":material/help:")
        return
    st.markdown(_parca_html(parcalar(n)), unsafe_allow_html=True)
    n = _duzelt(n, sozluk)

    izin = dict(yetkiler or {})
    izin["kar"] = bool(kar_acik)
    from shared.islem import bekle
    try:
        with bekle("Cevap hazırlanıyor"):
            c = cevapla(n, izin)
    except Exception as e:  # noqa: BLE001
        from shared.hata_log import kaydet
        kaydet("soru.cevap", e)
        st.error("Cevap hazırlanırken bir sorun oldu; ilgili sayfadan bakabilirsiniz.")
        return
    if c:
        _cevap_ciz(c)
