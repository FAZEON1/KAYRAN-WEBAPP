# -*- coding: utf-8 -*-
"""Mikro'dan ürün kartları ve satış fiyat listeleri — ilk onay kutusu (Ekim 2026). Hesap: kayranpm/mikro_urun.py.

Ürün Yönetimi › Tüm Ürünler'in üstünde: eşitleme kapalıyken bir kez "şimdi ↔ Mikro" karşılaştırması (açılacak
kartlar, dolacak boş alanlar, değişecek müşteri fiyatları, liste ↔ müşteri eşleşmesi) ve onay; açıkken kaynağı
söyleyen kısa not. Yalnız kârı görebilenler görür.
"""
import pandas as pd
import streamlit as st

from shared.tasarim import tr_sayi

from . import mikro_urun as M

_ALAN_AD = {"urun_adi": "Ad", "kategori": "Kategori", "marka": "Marka", "barkod": "Barkod"}


def _fiyat(v):
    return "—" if v is None else "$" + tr_sayi(v, 2)


def ilk_onay_kutusu():
    from shared.kar_gizle import kar_gorunur
    if M.acik_mi():
        # Açıkken (varsayılan, 22.10.2026) yalnız kaynak notu; aşağıdaki onay dalı yedek ({"acik": false})
        st.caption("Ürün kartları Mikro'dan gelir: Mikro'da açılan yeni ürün buraya da açılır, boş ad / kategori / "
                   "marka / barkod dolar; dolu alanlar değişmez.")
        return
    if not kar_gorunur():
        return
    try:
        if not M.son_aktarim():
            return
    except Exception:  # noqa: BLE001
        return
    with st.expander("Ürün kartları ve fiyat listeleri Mikro'dan gelsin (bir kez onay)", expanded=False,
                     icon=":material/sync:"):
        st.caption("Onaydan sonra Mikro'da açılan yeni ürün kartı buraya da gelir ('Fazeon ' öneki atılır, kod "
                   "aynen kalır). Mevcut kartta yalnız BOŞ ad, kategori, marka ve barkod doldurulur; dolu alanlar "
                   "değişmez. Mikro'da müşteriye bağlanan dolar fiyat listeleri o müşterinin fiyatı olur; diğer "
                   "müşterilerin fiyatına dokunulmaz. Pasif Mikro kartı uygulamada silinmez. Bu kutu bir daha "
                   "çıkmaz.")
        if not st.toggle("Karşılaştırmayı göster", key="mu_goster"):
            return
        with st.spinner("Mikro ürün kartları okunuyor…"):
            try:
                plan = M.plan_hazirla()
            except Exception as e:  # noqa: BLE001
                st.error(f"Mikro verisi okunamadı: {type(e).__name__}: {str(e)[:160]}")
                return
        if plan["bos"]:
            st.warning("Mikro ürün kartı verisi boş geldi; onay verilemez.")
            return
        fz = plan["fazeon"]
        st.markdown(f"**Mikro'da {tr_sayi(plan['mikro_kart'])} kart** · 'Fazeon ' önekli {tr_sayi(len(fz))} kod, "
                    f"{tr_sayi(sum(1 for x in fz if x[2]))} tanesi uygulamadaki karta bağlanıyor")
        st.markdown(f"**Açılacak kartlar** · {tr_sayi(len(plan['yeni']))}")
        if plan["yeni"]:
            st.dataframe(pd.DataFrame([{"SKU": y["sku"], "Mikro kodu": y["mikro_kod"], "Ad": y["urun_adi"],
                                        "Kategori": y["kategori"], "Marka": y["marka"], "Barkod": y["barkod"]}
                                       for y in plan["yeni"]]), hide_index=True, use_container_width=True)
        if plan["pasif_atlanan"]:
            st.caption(f"Mikro'da pasif, uygulamada olmayan {tr_sayi(len(plan['pasif_atlanan']))} kart açılmaz.")
        st.markdown(f"**Boş alanı dolacak kartlar** · {tr_sayi(len(plan['doldur']))}")
        if plan["doldur"]:
            st.dataframe(pd.DataFrame([{"SKU": s, **{_ALAN_AD[a]: v for a, v in al.items()}}
                                       for s, al in plan["doldur"]]), hide_index=True, use_container_width=True)
        st.markdown("**Fiyat listeleri ↔ müşteri**")
        if plan["liste"]:
            st.dataframe(pd.DataFrame([{"Mikro listesi": e["ad"], "Müşteri": e["musteri"] or "eşleşmedi, aktarılmaz",
                                        "KDV": "dahil (aktarılmaz)" if e["kdv_dahil"] else "hariç"}
                                       for e in plan["liste"]]), hide_index=True, use_container_width=True)
        else:
            st.caption("Mikro'da satış fiyat listesi yok.")
        st.markdown(f"**Değişecek müşteri fiyatları** · {tr_sayi(len(plan['fiyat']))}")
        if plan["fiyat"]:
            st.dataframe(pd.DataFrame([{"SKU": s, "Müşteri": m, "Şimdi": _fiyat(e), "Mikro": _fiyat(y)}
                                       for s, m, e, y in plan["fiyat"]]), hide_index=True, use_container_width=True)
        if plan["fiyat_atlanan"]:
            st.caption("Aktarılmayan fiyat satırları: " + " · ".join(
                f"{n} {tr_sayi(a)}" for n, a in plan["fiyat_atlanan"].items()))
        onay = st.checkbox("Karşılaştırmayı gördüm; ürün kartları ve fiyat listeleri bundan sonra Mikro'dan gelsin",
                           key="mu_onay")
        if st.button("Onayla ve otomatik eşitlemeyi aç", type="primary", disabled=not onay,
                     icon=":material/sync:", key="mu_ac"):
            sonuc = M.uygula(plan)
            if isinstance(sonuc, str):
                st.error(sonuc)
                return
            M.ac(st.session_state.get("aktif_kullanici", ""))
            st.success(f"Açıldı. {tr_sayi(sonuc)} kart Mikro'dan güncellendi. Bundan sonra otomatik.")
