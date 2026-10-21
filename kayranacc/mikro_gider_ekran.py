# -*- coding: utf-8 -*-
"""Mikro'dan otomatik gider tablosu — ilk onay kutusu (Ekim 2026). Hesap: kayranacc/mikro_gider.py.

Yönetim › Destekler ve giderler'in gider bölümünün üstünde: eşitleme kapalıyken bir kez "Excel ↔ Mikro"
karşılaştırması (kategori × ay, en çok değişen kalemler) ve onay; açıkken kaynağı söyleyen kısa not.
"""
import pandas as pd
import streamlit as st

from shared.tasarim import tr_sayi

from . import mikro_gider as G

_AY = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def _kat_tablosu(k, son_ay):
    satir = []
    for kat, eski, yeni in k["kat"]:
        for ad, dizi in (("Excel", eski), ("Mikro", yeni)):
            satir.append(dict({"Kategori": kat, "Kaynak": ad},
                              **{_AY[i]: tr_sayi(dizi[i]) for i in range(max(son_ay, 1))}))
    return pd.DataFrame(satir)


def ilk_onay_kutusu():
    from shared.kar_gizle import kar_gorunur
    d = G.durum()
    if d.get("acik"):
        st.caption("Gider tablosu Mikro'nun muhasebe hesaplarından otomatik gelir (biten aylar, 15 dakikada bir).")
        return
    if not kar_gorunur():
        return
    try:
        if not G.son_aktarim():
            return
    except Exception:  # noqa: BLE001
        return
    with st.expander("Gider tablosu Mikro'dan otomatik gelsin (bir kez onay)", expanded=False, icon=":material/sync:"):
        st.caption("Onaydan sonra gider tablosu her ay elle yüklenmez: kalemler Mikro'daki gider hesaplarından "
                   "(760, 770, 780, 689) hesaplanır, kalem adları ve kategoriler aynı kalır. Satış destek "
                   f"bedelleri alınmaz. {G.ILK_YIL} ve sonrası; içinde bulunulan ay bitince girer. Bu kutu bir "
                   "daha çıkmaz.")
        if not st.toggle("Karşılaştırmayı göster", key="mg_goster"):
            return
        with st.spinner("Mikro muhasebe hesapları okunuyor…"):
            try:
                plan = G.plan_hazirla()
            except Exception as e:  # noqa: BLE001
                st.error(f"Mikro verisi okunamadı: {type(e).__name__}: {str(e)[:160]}")
                return
        bugun = G._bugun()
        for y, p in plan.items():
            k = G.karsilastir(p["eski"], p["yeni"])
            son = G.ay_siniri(y, bugun)
            et, yt = (sum(sum(x[1][:son]) for x in k["kat"]), sum(sum(x[2][:son]) for x in k["kat"]))
            st.markdown(f"**{y}** · Ocak–{_AY[max(son, 1) - 1]} toplamı: Excel ₺{tr_sayi(et)} → Mikro ₺{tr_sayi(yt)}")
            st.dataframe(_kat_tablosu(k, son), hide_index=True, use_container_width=True)
            if k["kalem"]:
                with st.expander(f"{y}: farkı olan kalemler (yıllık, büyükten küçüğe)"):
                    st.dataframe(pd.DataFrame([{"Kategori": a, "Kalem": b, "Excel": tr_sayi(e), "Mikro": tr_sayi(m),
                                                "Fark": tr_sayi(m - e)} for a, b, e, m in k["kalem"]]),
                                 hide_index=True, use_container_width=True)
        onay = st.checkbox("Karşılaştırmayı gördüm; gider tablosunun kaynağı bundan sonra Mikro olsun", key="mg_onay")
        if st.button("Onayla ve otomatik eşitlemeyi aç", type="primary", disabled=not onay,
                     icon=":material/sync:", key="mg_ac"):
            yazilan = G.uygula(plan)
            G.ac(st.session_state.get("aktif_kullanici", ""), ilk_yil=min(plan) if plan else None)
            st.success("Açıldı. " + (f"{', '.join(map(str, yazilan))} gider tablosu Mikro'dan yazıldı. " if yazilan else "")
                       + "Bundan sonra otomatik.")
