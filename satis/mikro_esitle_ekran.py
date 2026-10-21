# -*- coding: utf-8 -*-
"""Mikro'dan otomatik satış — ilk onay kutusu (Ekim 2026). Hesap: satis/mikro_esitle.py.

Kullanıcı: "Mikro eşitleme sidebarı olmasın, sürekli manuel işlem yapmayayım; ilk seferinde bir şey
gerekirse yapayım, sonra her şey tam otomatik." Bu yüzden ayrı sayfa yok: eşitleme kapalıyken Satış ›
Satışlar'ın üstünde bir kez salt okunur "şimdi ↔ Mikro" karşılaştırması ve onay düğmesi çıkar (rakam
değiştiren değişiklik, kullanıcı onayı şart). Onaylanınca kutu bir daha çıkmaz; eşitleme otomatik sürer.
Yalnız kârı görebilen kullanıcılar görür. Aktarıcı kendini günceller (dosya indirme yok).
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
               f"{tr_sayi(len(y['sil_iade_id']))} Excel iade satırı. Mikro'da açık "
               f"{tr_sayi(plan.get('acik_siparis', 0))} sipariş ({tr_sayi(plan.get('acik_siparis_adet', 0))} adet) "
               "faturası kesilene kadar bekleyen satış olarak görünür. Stok değişmez.")
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
        ad = {"bedelsiz": "bedelsiz (teknik servis yazıyor)", "kursuz": "kuru bilinmeyen", "adetsiz": "adetsiz",
              "siparis_fiyatsiz": "fiyatsız sipariş", "siparis_kursuz": "kuru bilinmeyen sipariş"}
        st.caption("Alınmayan satırlar: " + " · ".join(f"{ad.get(k, k)} {tr_sayi(v)}" for k, v in at.items()))


def _aktarici_dugmesi():
    """SON KEZ elle güncelleme: bu sürümden sonra aktarıcı kendini günceller (mikro_aktarici_surum)."""
    from pathlib import Path
    yol = Path(__file__).resolve().parent.parent / "araclar" / "mikro_aktarici" / "mikro_kayran.py"
    if yol.exists():
        st.caption("Sunucudaki aktarıcı bir kez daha elle güncellenmeli; bundan sonra kendini kendisi günceller. "
                   "Sunucuda (10.0.1.11) bu düğmeyle indir, C:\\MikroKayran klasöründekinin üzerine kaydet.")
        st.download_button("Aktarıcıyı indir (mikro_kayran.py)", yol.read_bytes(), file_name="mikro_kayran.py",
                           mime="text/x-python", icon=":material/download:", key="me_aktarici")


def ilk_onay_kutusu():
    """Satışlar sayfasının üstü: eşitleme kapalıysa ve Mikro satırları geldiyse bir kerelik onay."""
    from shared.kar_gizle import kar_gorunur
    if not kar_gorunur():
        return
    d = M.durum()
    if not d or d.get("acik"):
        return
    try:
        if not M._son_aktarim():
            return                        # aktarıcı henüz satırları getirmedi
    except Exception:  # noqa: BLE001
        return
    bas = str(d.get("baslangic") or M.BASLANGIC)[:10]
    with st.expander(f"Satışlar ve iadeler Mikro'dan otomatik gelsin — {bas[8:10]}.{bas[5:7]}.{bas[:4]} sonrası "
                     "(bir kez onay)", expanded=False, icon=":material/sync:"):
        st.caption("Onaydan sonra satışlar ve iadeler Mikro faturalarından kendiliğinden güncellenir: fatura tarihi, "
                   "cari, ürün, adet, $ net fiyat (KDV ve iskonto hariç). Bu kutu bir daha çıkmaz.")
        _aktarici_dugmesi()
        if not st.toggle("Karşılaştırmayı göster", key="me_goster"):
            return
        with st.spinner("Mikro faturaları okunuyor…"):
            try:
                plan = M.plan_hazirla(bas)
            except Exception as e:  # noqa: BLE001
                st.error(f"Mikro verisi okunamadı: {type(e).__name__}: {str(e)[:160]}")
                return
        _plan_goster(plan)
        onay = st.checkbox("Karşılaştırmayı gördüm; bu tarihten sonra satışların ve iadelerin kaynağı Mikro olsun",
                           key="me_onay")
        if st.button("Onayla ve otomatik eşitlemeyi aç", type="primary", disabled=not onay,
                     icon=":material/sync:", key="me_ac"):
            ok, mesaj, sonuc = M.uygula(plan)
            if ok:
                M.ac(st.session_state.get("aktif_kullanici", ""))
                st.success(f"{mesaj} Eklenen satış {tr_sayi(sonuc.get('eklenen_satis', 0))}, "
                           f"iade {tr_sayi(sonuc.get('eklenen_iade', 0))}. Eski satırlar arşivde. "
                           "Bundan sonra otomatik.")
            else:
                st.error(mesaj)
