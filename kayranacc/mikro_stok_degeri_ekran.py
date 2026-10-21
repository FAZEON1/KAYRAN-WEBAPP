# -*- coding: utf-8 -*-
"""Toplam Aktifler · stok değeri uygulama verisinden — ilk onay kutusu (Ekim 2026). Hesap: kayranacc/mikro_stok_degeri.py.

Muhasebe › Toplam Aktifler'in üstünde: kapalıyken bir kez salt okunur "şimdi (Excel) ↔ uygulama" karşılaştırması
(depo depo değer, paçalı olmayanlar, müşterideki stok) ve onay; açıkken kaynağı söyleyen kısa not. Rakam
değiştiren değişiklik: kullanıcı onayı şart. Yalnız kârı görebilenler görür.
"""
import pandas as pd
import streamlit as st

from shared.tasarim import tr_sayi

from . import mikro_stok_degeri as M


def _usd(v):
    return "" if v is None else f"${tr_sayi(v, 2)}"


def _plan_goster(plan):
    once, yeni = plan["once"], plan["kayit"][0]
    st.markdown("**Toplam Aktifler'e giren stok (KDV dahil, × 1,20)**")
    st.dataframe(pd.DataFrame([
        {"Kalem": "Stok değeri (ham)", "Şimdi": _usd(once), "Uygulama": _usd(yeni),
         "Fark": _usd(round(yeni - once, 2)) if once is not None else ""},
        {"Kalem": "Aktiflere giren (× 1,20)", "Şimdi": _usd(once * M.KDV if once is not None else None),
         "Uygulama": _usd(yeni * M.KDV),
         "Fark": _usd(round((yeni - once) * M.KDV, 2)) if once is not None else ""},
    ]), hide_index=True, use_container_width=True)
    st.markdown("**Depo depo** (stok × paçal; bütün depolar, Excel'deki gibi)")
    d = plan["depo"]
    st.dataframe(pd.DataFrame([{"Depo": dp, "Adet": tr_sayi(d["adet"].get(dp, 0)), "Değer": _usd(v)}
                               for dp, v in d["deger"].items()]), hide_index=True, use_container_width=True)
    if d["pacalsiz"]:
        st.caption("Paçalı olmayan (değeri 0 sayılır): " + " · ".join(
            f"{s} ({dp}) {tr_sayi(a)} adet" for s, dp, a in d["pacalsiz"]))
    from shared.utils import firma_gorunen_ad
    st.markdown("**Müşterideki stok** (bilgi; Toplam Aktifler'e girmez)")
    st.dataframe(pd.DataFrame([{"Firma": firma_gorunen_ad(k), "Şimdi": _usd(a), "Uygulama (paçalla)": _usd(b)}
                               for k, a, b in M.kanal_karsilastir(plan["once_kanal"], plan["kanal"])]),
                 hide_index=True, use_container_width=True)
    st.caption("Excel müşteri bloklarında paçal yerine başka bir birim fiyat kullanıyordu; buradaki rakamlar "
               "her kanalın son stok raporu × paçal.")


def ilk_onay_kutusu():
    """Toplam Aktifler sayfasının üstü: kapalıysa bir kerelik onay; açıksa kaynağı söyleyen kısa not."""
    from shared.kar_gizle import kar_gorunur
    d = M.durum()
    if d.get("acik"):
        st.caption("Stok değeri uygulamadan otomatik gelir: bütün depolardaki stok (Mikro'dan) × paçal, "
                   "15 dakikada bir. Stok değeri raporu Excel'i gerekmez.")
        return
    if not kar_gorunur():
        return
    with st.expander("Stok değeri Excel yerine uygulamadan gelsin (bir kez onay)", expanded=False,
                     icon=":material/sync:"):
        st.caption("Onaydan sonra Toplam Aktifler'in stok kalemi Stok değeri raporu Excel'inden değil, bütün "
                   "depolardaki stok (Mikro'dan gelen depo kırılımı) × paçal maliyetten hesaplanır ve kendiliğinden "
                   "güncellenir; bu Excel yüklemesi kalkar. Bu kutu bir daha çıkmaz.")
        if not st.toggle("Karşılaştırmayı göster", key="msd_goster"):
            return
        with st.spinner("Depo stoğu ve paçal okunuyor…"):
            try:
                plan = M.plan_hazirla()
            except Exception as e:  # noqa: BLE001
                st.error(f"Veri okunamadı: {type(e).__name__}: {str(e)[:160]}")
                return
        if plan["bos"]:
            st.warning("Paçal ya da depo stoğu okunamadı (değer 0 çıktı); onay verilemez.")
            return
        _plan_goster(plan)
        onay = st.checkbox("Karşılaştırmayı gördüm; stok değerinin kaynağı bundan sonra uygulama olsun",
                           key="msd_onay")
        if st.button("Onayla ve otomatik hesabı aç", type="primary", disabled=not onay,
                     icon=":material/sync:", key="msd_ac"):
            sonuc = M.uygula(plan)
            if isinstance(sonuc, str):
                st.error(sonuc)
                return
            M.ac(st.session_state.get("aktif_kullanici", ""))
            st.success("Açıldı. Stok değeri uygulamadan yazıldı; bundan sonra otomatik.")
