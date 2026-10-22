# -*- coding: utf-8 -*-
"""Mikro'dan otomatik depo stoğu — ilk onay kutusu (Ekim 2026). Hesap: kayranpm/mikro_stok.py.

Ürün Yönetimi › Tüm Ürünler'in üstünde: eşitleme kapalıyken bir kez "şimdi ↔ Mikro" karşılaştırması (depo
toplamları, değişecek ürünler) ve onay; açıkken kaynağı söyleyen kısa not. Yalnız kârı görebilenler görür.
"""
import pandas as pd
import streamlit as st

from shared.tasarim import tr_sayi

from . import mikro_stok as M


def _kirilim_metni(dd):
    return " · ".join(f"{d} {tr_sayi(m)}" for d, m in sorted(dd.items())) or "—"


def ilk_onay_kutusu():
    from shared.kar_gizle import kar_gorunur
    d = M.durum()
    if d.get("acik"):
        # Açıkken yalnız kaynak notu; aşağıdaki onay dalı yedek (eşitleme kapanırsa geri gelir)
        st.caption("Depo stoğu Mikro'dan gelir (15 dakikada bir).")
        return
    if not kar_gorunur():
        return
    try:
        if not M.son_aktarim():
            return
    except Exception:  # noqa: BLE001
        return
    with st.expander("Depo stoğu Mikro'dan otomatik gelsin (bir kez onay)", expanded=False, icon=":material/sync:"):
        st.caption("Onaydan sonra her ürünün depo depo stoğu Mikro'dan güncellenir; G5F sayım Excel'i kalkar. "
                   "Yazım sayımla aynı yoldan (stok defterine fark olarak işlenir); 'bizim stok' = Merkez + Happy "
                   "Life. Uygulamadaki mal kabul ve sevk kayıtları durur, miktar Mikro'dan gelir. Bu kutu bir "
                   "daha çıkmaz.")
        if not st.toggle("Karşılaştırmayı göster", key="ms_goster"):
            return
        with st.spinner("Mikro stokları okunuyor…"):
            try:
                plan = M.plan_hazirla()
            except Exception as e:  # noqa: BLE001
                st.error(f"Mikro verisi okunamadı: {type(e).__name__}: {str(e)[:160]}")
                return
        if plan["bos"]:
            st.warning("Mikro stok verisi boş geldi; onay verilemez.")
            return
        depolar = sorted(set(plan["once"]) | set(plan["sonra"]))
        st.markdown("**Depo toplamları**")
        st.dataframe(pd.DataFrame([{"Depo": dp, "Şimdi": tr_sayi(plan["once"].get(dp, 0)),
                                    "Mikro": tr_sayi(plan["sonra"].get(dp, 0)),
                                    "Fark": tr_sayi(plan["sonra"].get(dp, 0) - plan["once"].get(dp, 0))}
                                   for dp in depolar]), hide_index=True, use_container_width=True)
        st.markdown(f"**Değişecek ürünler** · {tr_sayi(len(plan['fark']))}")
        if plan["fark"]:
            st.dataframe(pd.DataFrame([{"SKU": s, "Şimdi": _kirilim_metni(e), "Mikro": _kirilim_metni(y)}
                                       for s, e, y in plan["fark"]]), hide_index=True, use_container_width=True)
        onay = st.checkbox("Karşılaştırmayı gördüm; depo stoğunun kaynağı bundan sonra Mikro olsun", key="ms_onay")
        if st.button("Onayla ve otomatik eşitlemeyi aç", type="primary", disabled=not onay,
                     icon=":material/sync:", key="ms_ac"):
            from shared.yukleme_gecmisi import Kayit
            k = Kayit("g5f_sayim", "Mikro")
            k.anahtar("g5f")
            sonuc = M.uygula(plan, kayit=k)
            if isinstance(sonuc, str):
                st.error(sonuc)
                return
            if sonuc:
                k.kaydet(sonuc)
            M.ac(st.session_state.get("aktif_kullanici", ""))
            st.success(f"Açıldı. {tr_sayi(sonuc)} ürünün stoğu Mikro'dan yazıldı (Yükleme geçmişinden geri "
                       "alınabilir). Bundan sonra otomatik.")
