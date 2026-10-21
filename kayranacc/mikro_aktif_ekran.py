# -*- coding: utf-8 -*-
"""Toplam Aktifler · Mikro defter kalemleri ve satış maliyeti — onay kutusu ve döküm (Ekim 2026).
Hesap: kayranacc/mikro_aktif.py.

Kapalıyken bir kez "şimdi ↔ Mikro defteriyle" karşılaştırması ve onay (rakam değiştiren değişiklik: kullanıcı onayı
şart); açıkken kalem kalem döküm (hangi Mikro hesabından), satış maliyeti oranının kaynağı ve Mikro'dan geldiği
için sayılmayan manuel kalemler. Yalnız Toplam Aktifler'i görebilenler görür.
"""
import pandas as pd
import streamlit as st

from shared.tasarim import tr_sayi

from . import mikro_aktif as M


def _usd(v):
    return f"${tr_sayi(v, 2)}"


def _yuzde(v):
    return f"%{tr_sayi(v * 100, 2)}"


def kalem_satirlari(ozet):
    return [{"Kalem": k["ad"], "Tutar": ("+ " if k["usd"] > 0 else "− ") + _usd(abs(k["usd"])),
             "Mikro hesapları": ", ".join(list((k.get("hesaplar") or {}))[:8])
             + (" …" if len(k.get("hesaplar") or {}) > 8 else "")} for k in ozet["kalemler"]]


def oran_satirlari(kayit, kur):
    sm = (kayit or {}).get("satis_maliyeti") or {}
    return [{"Mikro hesabı": f"{x['kod']} {x['ad']}", "12 ay": _usd(x["tl"] / kur if kur > 0 else 0)}
            for x in sm.get("kalemler") or []]


def _cakisan_adlar(manuel_kalemler, cakisan):
    return [f"{m.get('aciklama')} ({cakisan[m.get('id', i)]})" for i, m in enumerate(manuel_kalemler or [])
            if m.get("id", i) in cakisan]


def _dokum(kayit, ozet, kur, cakisan_adlar):
    sm = (kayit or {}).get("satis_maliyeti") or {}
    st.markdown("**Mikro defterinden gelen kalemler** (bakiye, bugünkü kurla)")
    st.dataframe(pd.DataFrame(kalem_satirlari(ozet)), hide_index=True, use_container_width=True)
    st.markdown(f"**Satış maliyeti** {_yuzde(ozet['oran'])} × stok = {_usd(ozet['satis_maliyeti_usd'])} "
                f"(dönem {sm.get('donem') or '—'}: masraf {_usd(M._f(sm.get('masraf_tl')) / kur if kur > 0 else 0)} "
                f"÷ net satış {_usd(M._f(sm.get('satis_tl')) / kur if kur > 0 else 0)}; satış destek bedelleri hariç)")
    st.dataframe(pd.DataFrame(oran_satirlari(kayit, kur)), hide_index=True, use_container_width=True)
    st.caption("Banka, çek, cari, ithalat avansı ve stok hesapları (102, 103, 120, 340, 159, 320.50, 153) zaten "
               "Toplam Aktifler'in kendi kalemlerinde olduğu için burada yok: iki kez sayılmaz.")
    if cakisan_adlar:
        st.warning("Mikro'dan da geldiği için toplama girmeyen manuel kalemler: " + "; ".join(cakisan_adlar)
                   + ". İstersen aşağıdaki manuel listeden silebilirsin.")


def bolum(kur, stok_ham, toplam_once, manuel_kalemler):
    """Toplam Aktifler'in toplamından önce. Açıksa döküm (kapalı bölüm), kapalıysa bir kerelik onay.
    stok_ham: stok değeri (maliyet, çarpansız); toplam_once: sayfanın şu anki toplamı."""
    stok_yeni = stok_ham * M.stok_carpani(True)
    if M.acik_mi():
        kayit = M.kayitli()
        cakisan_adlar = _cakisan_adlar(manuel_kalemler, M.manuel_cakisan(manuel_kalemler, kayit))
        if not kayit:
            st.caption("Mikro defter kalemleri ilk eşitleme turunda hesaplanacak.")
            return
        ozet = M.usd_ozeti(kayit, kur, stok_yeni)
        with st.expander(f"Mikro defter kalemleri: + {_usd(ozet['arti'])} · − {_usd(ozet['eksi'])} · satış maliyeti "
                         f"− {_usd(ozet['satis_maliyeti_usd'])}", expanded=False, icon=":material/sync:"):
            _dokum(kayit, ozet, kur, cakisan_adlar)
        return
    with st.expander("Kasa, avans, KDV, vergi, SGK, tahakkuk ve satış maliyeti Mikro'dan düşülsün (bir kez onay)",
                     expanded=False, icon=":material/sync:"):
        st.caption("Onaydan sonra Toplam Aktifler'e Mikro'nun muhasebe bakiyelerinden, bugün hesapta olmayan kalemler "
                   "eklenir ve stoktan satış maliyeti (kargo, lojistik, depolama, kredi kartı komisyonu, teknik servis; "
                   "son 12 ayın oranı) düşülür; her aktarımda kendiliğinden güncellenir. Stok bilanço mantığıyla "
                   "maliyetten (× 1,00) sayılır: gümrükte peşin ödenen KDV Mikro'da indirilecek KDV'dedir ve KDV "
                   "kaleminde satış KDV'sinden mahsup edilerek görünür; × 1,20 ile birlikte KDV iki kez sayılırdı. "
                   "Bu kutu bir daha çıkmaz.")
        if not st.toggle("Karşılaştırmayı göster", key="mak_goster"):
            return
        with st.spinner("Mikro muhasebe bakiyeleri okunuyor…"):
            try:
                plan = M.plan_hazirla()
            except Exception as e:  # noqa: BLE001
                st.error(f"Veri okunamadı: {type(e).__name__}: {str(e)[:160]}")
                return
        if plan["bos"]:
            st.warning("Mikro muhasebe bakiyeleri okunamadı; onay verilemez.")
            return
        ozet = M.usd_ozeti(plan["kayit"], kur, stok_yeni)
        cakisan = M.manuel_cakisan(manuel_kalemler, plan["kayit"])
        cakisan_adlar = _cakisan_adlar(manuel_kalemler, cakisan)
        kdv_payi = stok_ham * (M.stok_carpani(False) - M.stok_carpani(True))
        fark = (ozet["arti"] - ozet["eksi"] - ozet["satis_maliyeti_usd"] - kdv_payi
                - M.cakisan_etki(manuel_kalemler, cakisan, kur))
        st.dataframe(pd.DataFrame([
            {"": "Toplam aktifler (şimdi)", "Tutar": _usd(toplam_once)},
            {"": "Mikro defter kalemleri (+)", "Tutar": "+ " + _usd(ozet["arti"])},
            {"": "Mikro defter kalemleri (−)", "Tutar": "− " + _usd(ozet["eksi"])},
            {"": "Satış maliyeti (−)", "Tutar": "− " + _usd(ozet["satis_maliyeti_usd"])},
            {"": "Stoktaki KDV payı (× 1,20 → maliyet; KDV defterde ayrı kalem) (−)", "Tutar": "− " + _usd(kdv_payi)},
            {"": "Mikro'dan da gelen manuel kalemler (sayılmaz)",
             "Tutar": _usd(-M.cakisan_etki(manuel_kalemler, cakisan, kur))},
            {"": "Toplam aktifler (onaydan sonra)", "Tutar": _usd(toplam_once + fark)},
        ]), hide_index=True, use_container_width=True)
        _dokum(plan["kayit"], ozet, kur, cakisan_adlar)
        onay = st.checkbox("Karşılaştırmayı gördüm; bu kalemler Toplam Aktifler'e girsin", key="mak_onay")
        if st.button("Onayla ve otomatik hesabı aç", type="primary", disabled=not onay, icon=":material/sync:",
                     key="mak_ac"):
            sonuc = M.uygula(plan)
            if isinstance(sonuc, str):
                st.error(sonuc)
                return
            M.ac(st.session_state.get("aktif_kullanici", ""))
            st.success("Açıldı. Toplam Aktifler bundan sonra bu kalemlerle hesaplanır.")
            st.rerun()
