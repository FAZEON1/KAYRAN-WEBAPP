# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Stok yaşı sayfası ve stok kartındaki "Stok yaşı" sekmesi (Ekim 2026).

Hesap kayranpm/stok_yasi.py'de (FIFO, depoya giriş tarihinden). Değer = adet × paçal maliyet
(satis.get_pacal_map — Tüm Ürünler ve P&L ile aynı rakam). Salt okunur.
"""
import streamlit as st

from shared.tasarim import tr_sayi

from . import stok_yasi as Y


def _pacal():
    try:
        from satis.database import get_pacal_map
        return get_pacal_map() or {}
    except Exception:  # noqa: BLE001
        return {}


def _gun(v):
    return "—" if v is None else tr_sayi(v, 0)


def _firma_ad(kod):
    try:
        from shared.utils import firma_gorunen_ad
        return firma_gorunen_ad(kod) or kod
    except Exception:  # noqa: BLE001
        return kod


def _grup_tablosu(oz, pacal_birim=None, key="sy_grup"):
    from shared.tablo import tablo
    stok = oz.get("stok") or 0
    sira = [g for g, _a, _u in Y.GRUPLAR] + [Y.KAYITSIZ]
    satir = []
    for g in sira:
        a = (oz.get("gruplar") or {}).get(g, 0)
        if g == Y.KAYITSIZ and not a:
            continue
        r = {"Yaş": g, "Adet": a, "Pay (%)": round(a / stok * 100, 1) if stok else 0.0}
        if pacal_birim is not None:
            r["Değer ($)"] = round(a * pacal_birim.get(g, 0.0), 2)
        satir.append(r)
    tablo(satir, key=key, dosya_adi="stok_yasi_gruplar", arama=True)


def _parti_tablosu(kalanlar, bugun, key, musteri=False):
    from shared.tablo import tablo
    from shared.utils import gun_ay_yil
    if not kalanlar:
        st.caption("Elde kalan stoğu karşılayan giriş kaydı yok.")
        return
    tur = {"ithalat": "İthalat", "yurtici": "Yurt içi", "yerli": "Yerli üretim"}
    rows = []
    for k in reversed(kalanlar):
        g = Y._gun(k.get("tarih"), bugun)
        r = {("Fatura tarihi" if musteri else "Depoya giriş"): gun_ay_yil(k.get("tarih")),
             "Belge": k.get("belge") or "", "Kalan adet": k.get("kalan"), "Yaş (gün)": g,
             "Grup": Y.grup_adi(g or 0)}
        if not musteri:
            r["Tür"] = tur.get(k.get("tur"), "")
        rows.append(r)
    tablo(rows, key=key, dosya_adi="stok_yasi_partiler", arama=True)


def kart_bolumu(sku):
    """Stok kartı › Stok yaşı sekmesi: bizim stok + her müşterideki stok."""
    from shared.utils import sku_anahtar, metrik_satiri
    try:
        from shared.islem import bekle
        with bekle("Stok yaşı hesaplanıyor…"):
            v = Y.hesapla()
    except Exception as e:  # noqa: BLE001
        st.error(f"Stok yaşı hesaplanamadı: {type(e).__name__}: {str(e)[:120]}")
        return
    k, bugun = sku_anahtar(sku), v["bugun"]
    st.markdown("**Bizim stok** · satılabilir depolar (Merkez + Happy Life) · yaş depoya girişten, FIFO")
    b = v["bizim"].get(k)
    if not b:
        st.caption("Satılabilir depoda stok yok.")
    else:
        oz, kal, _u = b
        metrik_satiri([
            {"label": "Stok", "value": tr_sayi(oz["stok"])},
            {"label": "Ağırlıklı ort. yaş", "value": f"{_gun(oz['ort_gun'])} gün"},
            {"label": "En eski parti", "value": f"{_gun(oz['en_eski_gun'])} gün"},
            {"label": Y.KAYITSIZ, "value": tr_sayi(oz["kapsanmayan"])},
        ])
        if oz["kapsanmayan"] > 0:
            st.warning(f"{tr_sayi(oz['kapsanmayan'])} adedin giriş kaydı yok; yaşı hesaplanmadı. Yurt içinden "
                       "alındıysa Ürün Yönetimi › Yurt içi alış sayfasından alımı gir.")
        _grup_tablosu(oz, key=f"sy_k_grup_{k}")
        _parti_tablosu(kal, bugun, key=f"sy_k_parti_{k}")
    st.markdown("**Müşterilerdeki stok** · son rapor · yaş bizim fatura tarihimizden, FIFO")
    var = False
    for firma in sorted(v["musteri"]):
        m = v["musteri"][firma].get(k)
        if not m:
            continue
        var = True
        oz, kal = m
        with st.expander(f"{_firma_ad(firma)} · {tr_sayi(oz['stok'])} adet · ort. {_gun(oz['ort_gun'])} gün"
                         f" · en eski {_gun(oz['en_eski_gun'])} gün", expanded=False):
            if oz["kapsanmayan"] > 0:
                st.caption(f"{tr_sayi(oz['kapsanmayan'])} adet bizim satış kayıtlarımızdan eski ya da kaydı yok.")
            _grup_tablosu(oz, key=f"sy_m_grup_{firma}_{k}")
            _parti_tablosu(kal, bugun, key=f"sy_m_parti_{firma}_{k}", musteri=True)
    if not var:
        st.caption("Müşterilerin son raporlarında bu ürün yok.")


def _grup_degerleri(bizim, pacal):
    """{grup: değer $} — her ürünün grup adedi × paçal."""
    out = {}
    for k, (oz, _kal, _u) in bizim.items():
        p = float(pacal.get(k, 0) or 0)
        for g, a in oz["gruplar"].items():
            out[g] = out.get(g, 0.0) + a * p
    return out


def goster():
    from shared.tasarim import baslik as _sb
    from shared.tablo import tablo
    from shared.utils import metrik_satiri
    st.markdown(_sb("Ürün Yönetimi", "Stok yaşı",
                    aciklama="FIFO · yaş depoya giriş tarihinden · satılabilir depolar ve müşterilerdeki stok"),
                unsafe_allow_html=True)
    c1, c2 = st.columns([5, 1], vertical_alignment="center")
    c1.caption("Elde kalan stok en yeni partilerden oluşur (en eski önce satılır). İade, teknik, ikinci el ve "
               "outlet depoları sayılmaz. Değer paçal maliyetle.")
    if c2.button("Yenile", icon=":material/refresh:", key="sy_yenile", use_container_width=True):
        if hasattr(Y.hesapla, "clear"):
            Y.hesapla.clear()
        st.rerun()
    try:
        from shared.islem import bekle
        with bekle("Stok yaşı hesaplanıyor…"):
            v = Y.hesapla()
    except Exception as e:  # noqa: BLE001
        st.error(f"Stok yaşı hesaplanamadı: {type(e).__name__}: {str(e)[:120]}")
        return
    pacal, bugun = _pacal(), v["bugun"]
    t1, t2 = st.tabs(["Bizim stok", "Müşterilerdeki stok"])
    with t1:
        rows = Y.urun_satirlari(v["bizim"], pacal)
        if not rows:
            st.info("Satılabilir depolarda stok yok.")
        else:
            top = Y.toplam_ozet([oz for oz, _k, _u in v["bizim"].values()])
            gd = _grup_degerleri(v["bizim"], pacal)
            yasli = sum(top["gruplar"].get(g, 0) for g in ("91–180 gün", "180+ gün"))
            metrik_satiri([
                {"label": "Satılabilir stok", "value": tr_sayi(top["stok"])},
                {"label": "Ağırlıklı ort. yaş", "value": f"{_gun(top['ort_gun'])} gün"},
                {"label": "90 günden yaşlı", "value": tr_sayi(yasli),
                 "alt": f"$ {tr_sayi(gd.get('91–180 gün', 0) + gd.get('180+ gün', 0), 0)}"},
                {"label": Y.KAYITSIZ, "value": tr_sayi(top["kapsanmayan"])},
            ])
            sira = [g for g in [g for g, _a, _u in Y.GRUPLAR] + [Y.KAYITSIZ] if top["gruplar"].get(g, 0)]
            ozet = [{"_id": g, "Yaş": g, "Adet": top["gruplar"].get(g, 0),
                     "Pay (%)": round(top["gruplar"].get(g, 0) / top["stok"] * 100, 1) if top["stok"] else 0.0,
                     "Değer ($)": round(gd.get(g, 0.0))} for g in sira]
            gsec = tablo(ozet, key="sy_toplam_grup", kalici=True, arama=True, dosya_adi="stok_yasi_ozet")
            grup = ozet[gsec]["_id"] if gsec is not None and gsec < len(ozet) else None
            tum = {"Özet": ozet, "Ürünler": rows, "Partiler": Y.parti_satirlari(v["bizim"], bugun),
                   "Müşteriler": Y.musteri_satirlari(v["musteri"], _firma_ad)}
            e1, e2 = st.columns(2)
            e2.download_button("Excel: tümü", Y.excel_bytes(tum), file_name=f"stok_yasi_{bugun}.xlsx",
                               icon=":material/download:", key="sy_xl_tum", use_container_width=True,
                               help="Özet, ürünler, elde kalan partiler ve müşteri stokları ayrı sayfalarda.")
            if grup is None:
                e1.caption("Bir yaş grubuna tıkla: o gruptaki ürünler altta listelenir ve ayrıca indirilebilir.")
            else:
                g_rows = Y.urun_satirlari(v["bizim"], pacal, grup=grup)
                g_part = Y.parti_satirlari(v["bizim"], bugun, grup=grup) if grup != Y.KAYITSIZ else []
                e1.download_button(f"Excel: {grup}", Y.excel_bytes({"Ürünler": g_rows, "Partiler": g_part}),
                                   file_name=f"stok_yasi_{grup.replace(' ', '_').replace('–', '-')}_{bugun}.xlsx",
                                   icon=":material/download:", key="sy_xl_grup", use_container_width=True)
                with st.container(border=True):
                    st.markdown(f"**{grup}** · {tr_sayi(len(g_rows))} ürün · "
                                f"{tr_sayi(sum(r['Bu yaştaki adet'] for r in g_rows))} adet · "
                                f"$ {tr_sayi(sum(r['Bu yaştaki değer ($)'] for r in g_rows), 0)}")
                    tablo(g_rows, key=f"sy_grup_urun_{grup}", arama=True, dosya_adi="stok_yasi_grup")
            if top["kapsanmayan"] > 0:
                st.caption(f"{tr_sayi(top['kapsanmayan'])} adedin giriş kaydı yok (yurt içinden alınmış olabilir); "
                           "Yurt içi alış sayfasından alımı girince yaşı hesaplanır.")
            st.markdown("**Tüm ürünler**")
            sec = tablo(rows, key="sy_urunler", kalici=True, arama=True, dosya_adi="stok_yasi_urunler")
            if sec is not None:
                k = rows[sec]["_id"]
                oz, kal, u = v["bizim"][k]
                with st.container(border=True):
                    st.markdown(f"**{u.get('sku')}** · {u.get('urun_adi') or ''} · elde kalan partiler")
                    _parti_tablosu(kal, bugun, key=f"sy_secili_{k}")
            else:
                st.caption("Partilerini görmek için bir ürüne tıkla.")
    with t2:
        mus = v["musteri"]
        if not mus:
            st.info("Müşteri stok raporu yok.")
            return
        ozet_satir = []
        for firma, skular in mus.items():
            top = Y.toplam_ozet([oz for oz, _k in skular.values()])
            ozet_satir.append({"Müşteri": _firma_ad(firma), "Stok": top["stok"],
                               "Ort. yaş (gün)": None if top["ort_gun"] is None else round(top["ort_gun"]),
                               "90 günden yaşlı": sum(top["gruplar"].get(g, 0) for g in ("91–180 gün", "180+ gün")),
                               "Kaydı yok": top["kapsanmayan"]})
        ozet_satir.sort(key=lambda r: -r["Stok"])
        tablo(ozet_satir, key="sy_musteri_ozet", dosya_adi="stok_yasi_musteriler", arama=True)
        st.download_button("Excel: tüm müşteriler", Y.excel_bytes({"Müşteri özeti": ozet_satir,
                                                                    "Müşteri × ürün": Y.musteri_satirlari(mus, _firma_ad)}),
                           file_name=f"stok_yasi_musteriler_{bugun}.xlsx", icon=":material/download:",
                           key="sy_xl_musteri")
        firmalar = sorted(mus, key=lambda f: -sum(oz["stok"] for oz, _k in mus[f].values()))
        firma = st.selectbox("Müşteri", firmalar, format_func=_firma_ad, key="sy_firma")
        satir = []
        for sku, (oz, _kal) in mus[firma].items():
            r = {"_id": sku, "SKU": sku, "Stok": oz["stok"],
                 "Ort. yaş (gün)": None if oz["ort_gun"] is None else round(oz["ort_gun"]),
                 "En eski (gün)": oz["en_eski_gun"]}
            for g, _a, _u in Y.GRUPLAR:
                r[g] = oz["gruplar"].get(g, 0)
            r["Kaydı yok"] = oz["kapsanmayan"]
            satir.append(r)
        satir.sort(key=lambda r: (-(r["Ort. yaş (gün)"] or -1), r["SKU"]))
        sec = tablo(satir, key=f"sy_m_{firma}", kalici=True, arama=True, dosya_adi=f"stok_yasi_{firma}")
        st.caption("'Kaydı yok': müşterinin stoğu, bizim kayıtlı satışlarımızdan fazla (eski dönem ya da başka "
                   "kanaldan gelen mal).")
        if sec is not None:
            sku = satir[sec]["_id"]
            oz, kal = mus[firma][sku]
            _parti_tablosu(kal, bugun, key=f"sy_m_sec_{firma}_{sku}", musteri=True)
