# -*- coding: utf-8 -*-
"""Satış › Mikro eşitleme ekranı (Ekim 2026). Hesap: satis/mikro_esitle.py.

Kapalıyken: salt okunur "şimdi ↔ Mikro'dan sonra" karşılaştırması + onay düğmesi (rakam değiştiren
değişiklik, kullanıcı onayı şart). Açıkken: son otomatik eşitlemenin özeti + "Şimdi eşitle".
"""
import pandas as pd
import streamlit as st

from shared.tasarim import kpi_serit, para, tr_sayi

from . import mikro_esitle as M


def _ay_tablosu(ozet):
    satir = []
    for o in ozet:
        satir.append({
            "Ay": o["ay"],
            "Adet (şimdi)": tr_sayi(o["adet_once"]), "Adet (Mikro)": tr_sayi(o["adet_sonra"]),
            "Ciro $ (şimdi)": para(o["ciro_once"]), "Ciro $ (Mikro)": para(o["ciro_sonra"]),
            "Kâr $ (şimdi)": para(o["kar_once"]), "Kâr $ (Mikro)": para(o["kar_sonra"]),
            "İade $ (şimdi)": para(o["iade_once"]), "İade $ (Mikro)": para(o["iade_sonra"]),
        })
    return pd.DataFrame(satir)


def _plan_goster(plan):
    oz = plan["ozet"]
    t = {k: sum(o[k] for o in oz) for k in ("adet_once", "adet_sonra", "ciro_once", "ciro_sonra",
                                             "kar_once", "kar_sonra", "iade_once", "iade_sonra")}
    st.markdown(kpi_serit([
        {"etiket": "Ciro (şimdi → Mikro)", "deger": f"{para(t['ciro_once'])} → {para(t['ciro_sonra'])}", "renk": "mavi"},
        {"etiket": "Kâr (şimdi → Mikro)", "deger": f"{para(t['kar_once'])} → {para(t['kar_sonra'])}", "renk": "yesil"},
        {"etiket": "Adet", "deger": f"{tr_sayi(t['adet_once'])} → {tr_sayi(t['adet_sonra'])}", "renk": "mor"},
        {"etiket": "İade", "deger": f"{para(t['iade_once'])} → {para(t['iade_sonra'])}", "renk": "amber"},
    ]), unsafe_allow_html=True)
    if oz:
        st.dataframe(_ay_tablosu(oz), hide_index=True, use_container_width=True)
    y = plan["yuk"]
    st.caption(f"Eklenecek: {tr_sayi(len(y['ekle_satis']))} satış satırı ({tr_sayi(plan['yeni_fatura'])} fatura), "
               f"{tr_sayi(len(y['ekle_iade']))} iade satırı. Değiştirilecek: {tr_sayi(len(y['sil_satis_id']))} "
               f"Mikro dışı satış satırı, {tr_sayi(len(y['fatura_nolar']))} değişen fatura, "
               f"{tr_sayi(len(y['sil_iade_id']))} Excel iade satırı. Stok değişmez.")
    if plan["sil_satis_kanal"]:
        with st.expander("Değiştirilecek Mikro dışı satış satırları (firma)"):
            st.dataframe(pd.DataFrame(plan["sil_satis_kanal"], columns=["Firma", "Satır", "Adet"]),
                         hide_index=True, use_container_width=True)
    if plan["hizmet_faturalari"]:
        with st.expander(f"Ürün satırı olmayan {len(plan['hizmet_faturalari'])} satış faturası "
                         "(hizmet / masraf / fark — satışa yazılmaz)"):
            st.dataframe(pd.DataFrame([{"Tarih": b["tarih"], "Fatura": b["fatura_no"], "Firma": b["kanal"],
                                        "Tutar (KDV dahil)": f"{tr_sayi(b['tutar'], 2)} {b['doviz']}"}
                                       for b in plan["hizmet_faturalari"]]),
                         hide_index=True, use_container_width=True)
    at = plan.get("atlanan") or {}
    if at:
        ad = {"bedelsiz": "bedelsiz (teknik servis yazıyor)", "kursuz": "kuru bilinmeyen", "adetsiz": "adetsiz"}
        st.caption("Alınmayan satırlar: " + " · ".join(f"{ad.get(k, k)} {tr_sayi(v)}" for k, v in at.items()))


def _aktarici_dugmesi(guncel):
    """Sunucudaki aktarıcı dosyası: sunucuda bu sayfayı açıp indirmek, dosyayı taşımaktan kolay (Ekim 2026)."""
    from pathlib import Path
    yol = Path(__file__).resolve().parent.parent / "araclar" / "mikro_aktarici" / "mikro_kayran.py"
    if not yol.exists():
        return
    if not guncel:
        st.warning("Sunucudaki aktarıcı eski: fatura satırlarını henüz getirmiyor. Sunucuda (10.0.1.11) bu sayfayı "
                   "açıp aşağıdaki düğmeyle mikro_kayran.py dosyasını indir, C:\\MikroKayran klasöründeki eskisinin "
                   "üzerine kaydet. Sonraki 15 dakikalık turda satırlar gelir.")
    st.download_button("Aktarıcıyı indir (mikro_kayran.py)", yol.read_bytes(), file_name="mikro_kayran.py",
                       mime="text/x-python", icon=":material/download:", key="me_aktarici")


def sayfa():
    st.markdown("### Mikro eşitleme")
    d = M.durum()
    if d is None:
        st.warning("Mikro eşitleme tabloları henüz kurulmamış (veritabani/37_mikro_satis.sql).")
        return
    try:
        guncel = bool(M._son_aktarim())
    except Exception:  # noqa: BLE001
        guncel = False
    _aktarici_dugmesi(guncel)
    if not guncel:
        return
    bas = str(d.get("baslangic") or M.BASLANGIC)[:10]
    st.caption(f"{bas[8:10]}.{bas[5:7]}.{bas[:4]} sonrasındaki satışlar ve iadeler Mikro faturalarından gelir: "
               "fatura tarihi, cari, ürün, adet, $ net fiyat (KDV ve iskonto hariç). Aktarıcı 15 dakikada bir "
               "yeni faturaları getirir.")
    if d.get("acik"):
        so = d.get("son_ozet") or {}
        st.success(f"Otomatik eşitleme açık. Son çalışma: {str(d.get('son_calisma') or '—')[:16].replace('T', ' ')}"
                   f" · eklenen satış {tr_sayi(so.get('eklenen_satis', 0))}, iade {tr_sayi(so.get('eklenen_iade', 0))}"
                   f" · değiştirilen satış {tr_sayi(so.get('silinen_satis', 0))}, iade {tr_sayi(so.get('silinen_iade', 0))}")
        if st.button("Şimdi eşitle", icon=":material/sync:", key="me_simdi"):
            with st.spinner("Mikro faturaları okunuyor…"):
                plan = M.plan_hazirla(bas)
                ok, mesaj, _s = M.uygula(plan)
            (st.success if ok else st.error)(mesaj)
        return
    with st.spinner("Mikro faturaları okunuyor…"):
        try:
            plan = M.plan_hazirla(bas)
        except Exception as e:  # noqa: BLE001
            st.error(f"Mikro verisi okunamadı: {type(e).__name__}: {str(e)[:160]}")
            return
    st.info("Henüz açılmadı. Aşağıdaki karşılaştırma salt okunur: onaylayana kadar hiçbir şey yazılmaz.")
    _plan_goster(plan)
    onay = st.checkbox("Karşılaştırmayı gördüm; bu tarihten sonra satışların ve iadelerin kaynağı Mikro olsun",
                       key="me_onay")
    if st.button("Onayla ve otomatik eşitlemeyi aç", type="primary", disabled=not onay,
                 icon=":material/sync:", key="me_ac"):
        ok, mesaj, sonuc = M.uygula(plan)
        if ok:
            M.ac(st.session_state.get("aktif_kullanici", ""))
            st.success(f"{mesaj} Eklenen satış {tr_sayi(sonuc.get('eklenen_satis', 0))}, "
                       f"iade {tr_sayi(sonuc.get('eklenen_iade', 0))}. Eski satırlar arşivde.")
        else:
            st.error(mesaj)
