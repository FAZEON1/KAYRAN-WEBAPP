# -*- coding: utf-8 -*-
"""Mikro depo hareketleri — bir kerelik onay kutusu ve Happy Life'ın Mikro görünümü (Ekim 2026).
Hesap: kayranpm/mikro_depo.py.

Onay kutusu Depo › Happy Life ve Ürün Yönetimi › Stok yaşı sayfalarının üstünde, kaynak kapalıyken ve aktarıcı
mikro_depo_hareket'i en az bir kez çektiyse görünür (göç 43 uygulanmadan / veri gelmeden hiç çıkmaz). Yalnız
kârı görebilenler (yönetim) görür. Karşılaştırma: Happy Life son Excel ↔ Mikro, stok yaşı şimdi ↔ Mikro,
satılamayan stok depo bazında şimdi ↔ Mikro.
"""
import pandas as pd
import streamlit as st

from shared.tasarim import tr_sayi

from . import mikro_depo as M


def _gun(v):
    return "—" if v is None else tr_sayi(v, 0)


def _tarih(iso):
    s = str(iso or "")[:10]
    return f"{s[8:10]}.{s[5:7]}.{s[:4]}" if len(s) == 10 else "—"


def _yas_tablosu(y):
    o, s = y["once"], y["sonra"]
    satir = [("Satılabilir stok", o["stok"], s["stok"]), ("Ağırlıklı ort. yaş (gün)", o["ort_gun"], s["ort_gun"]),
             ("Giriş kaydı yok (adet)", o["kapsanmayan"], s["kapsanmayan"])]
    from .stok_yasi import GRUPLAR
    satir += [(g, o["gruplar"].get(g, 0), s["gruplar"].get(g, 0)) for g, _a, _u in GRUPLAR]
    return pd.DataFrame([{"": ad, "Şimdi": _gun(a), "Mikro": _gun(b)} for ad, a, b in satir])


def ilk_onay_kutusu(yer="hl"):
    """yer: anahtar öneki (aynı kutu iki sayfada)."""
    from shared.kar_gizle import kar_gorunur
    if M.acik_mi():
        # Açıkken yalnız kaynak notu; aşağıdaki onay dalı yedek (eşitleme kapanırsa geri gelir)
        st.caption("Depo stoğu, depoya giriş tarihleri ve stok yaşı Mikro'nun stok hareketlerinden gelir.")
        return
    if not kar_gorunur() or not M.son_aktarim():
        return
    with st.expander("Happy Life ve stok yaşı Mikro'dan gelsin (bir kez onay)", expanded=False,
                     icon=":material/sync:"):
        st.caption("Onaydan sonra Happy Life sayfası (stok, giriş tarihi, yaş), stok yaşı ve satılamayan stoktaki "
                   "bekleme süresi Mikro'daki stok hareketlerinden hesaplanır: ithalat ya da yurt içi alışla depoya "
                   "giriş ve depolar arası sevk. Happy Life Excel'i gerekmez; yalnız palet etiketi Mikro'da yok, "
                   "palet listesi için Excel isteğe bağlı yüklenebilir. Veri kopyalanmaz, hiçbir kayıt "
                   "değişmez. Bu kutu bir daha çıkmaz.")
        if not st.toggle("Karşılaştırmayı göster", key=f"md_goster_{yer}"):
            return
        with st.spinner("Mikro hareketleri okunuyor…"):
            try:
                plan = M.plan_hazirla()
            except Exception as e:  # noqa: BLE001
                st.error(f"Mikro verisi okunamadı: {type(e).__name__}: {str(e)[:160]}")
                return
        if plan["bos"]:
            st.warning("Mikro depo hareketleri henüz boş; onay verilemez.")
            return
        ht = plan["hl_toplam"]
        st.markdown(f"**Happy Life** · Mikro: {tr_sayi(ht['cesit'])} ürün · {tr_sayi(ht['stok'])} adet · en eski "
                    f"{_gun(ht['en_eski_gun'])} gün · giriş kaydı yok {tr_sayi(ht['kayitsiz'])}")
        if plan["excel"]:
            st.caption(f"Son Excel {_tarih(plan['excel_rapor'])} tarihli; Mikro bugünkü stok. Adet farkı o günden "
                       "beri çıkışlardır, en eski giriş farkı FIFO'dur (Mikro elde kalan partiye bakar).")
            st.dataframe(pd.DataFrame([{
                "SKU": r["sku"], "Ürün": r["ad"], "Excel adet": tr_sayi(r["excel_adet"]),
                "Mikro adet": tr_sayi(r["mikro_adet"]), "Excel en eski giriş": _tarih(r["excel_en_eski"]),
                "Mikro en eski giriş": _tarih(r["mikro_en_eski"]), "Mikro en eski (gün)": _gun(r["mikro_yas"])}
                for r in plan["excel"]]), hide_index=True, use_container_width=True)
        st.markdown("**Stok yaşı** · satılabilir stok (Merkez + Happy Life)")
        st.dataframe(_yas_tablosu(plan["yas"]), hide_index=True, use_container_width=True)
        if plan["yas"]["urunler"]:
            st.markdown(f"Yaşı değişen ürünler · {tr_sayi(len(plan['yas']['urunler']))}")
            st.dataframe(pd.DataFrame([{
                "SKU": r["sku"], "Stok": tr_sayi(r["stok"]), "Ort. yaş şimdi": _gun(r["ort_once"]),
                "Ort. yaş Mikro": _gun(r["ort_sonra"]), "Kayıtsız şimdi": tr_sayi(r["kayitsiz_once"]),
                "Kayıtsız Mikro": tr_sayi(r["kayitsiz_sonra"])} for r in plan["yas"]["urunler"]]),
                hide_index=True, use_container_width=True)
        so, ss = ({o["depo"]: o for o in plan["satilamayan"][k]} for k in ("once", "sonra"))
        if so or ss:
            st.markdown("**Satılamayan stok** · depo bazında")
            from depo.satilamayan import YASLI_GUN
            st.dataframe(pd.DataFrame([{
                "Depo": d, "Adet": tr_sayi((ss.get(d) or so.get(d))["adet"]),
                f"{YASLI_GUN}+ gün şimdi": tr_sayi((so.get(d) or {}).get("yasli_adet", 0)),
                f"{YASLI_GUN}+ gün Mikro": tr_sayi((ss.get(d) or {}).get("yasli_adet", 0)),
                "Kayıtsız şimdi": tr_sayi((so.get(d) or {}).get("kayitsiz", 0)),
                "Kayıtsız Mikro": tr_sayi((ss.get(d) or {}).get("kayitsiz", 0))}
                for d in sorted(set(so) | set(ss))]), hide_index=True, use_container_width=True)
        onay = st.checkbox("Karşılaştırmayı gördüm; depoya giriş tarihlerinin kaynağı bundan sonra Mikro olsun",
                           key=f"md_onay_{yer}")
        if st.button("Onayla ve Mikro'ya geç", type="primary", disabled=not onay, icon=":material/sync:",
                     key=f"md_ac_{yer}"):
            if M.uygula(plan, st.session_state.get("aktif_kullanici", "")):
                try:
                    from shared.yukleme_takvimi import _temizle
                    _temizle()
                except Exception:  # noqa: BLE001
                    pass
                st.success("Açıldı. Happy Life, stok yaşı ve satılamayan stok bundan sonra Mikro'dan.")
            else:
                st.error("Mikro verisi boş; açılmadı.")


def hl_sayfasi():
    """Depo › Happy Life, Mikro kaynağı açıkken: model, adet ve stok yaşı Mikro'dan (FIFO, elde kalan parti).
    Döner: çizildi mi (Mikro verisi yoksa False; sayfa Excel görünümüne düşer)."""
    from shared.masa_liste import ciz, kolon
    from shared.utils import metrik_satiri
    try:
        v = M.hesapla()
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("kayranpm.mikro_depo_ekran.hl_sayfasi", e)
        st.error("Mikro verisi okunamadı; biraz sonra yeniden deneyin.")
        return False
    if v["bos"]:
        return False
    oz = M.depo_ozet_satirlari(v["depo"], M.HAPPY_LIFE, v["adlar"])
    t = M.toplam(oz)
    kartlar = [
        {"label": "Stok", "value": tr_sayi(t["stok"]), "alt": f"{tr_sayi(t['cesit'])} model"},
        {"label": "En yaşlı stok", "value": f"{_gun(t['en_eski_gun'])} gün"},
        {"label": "Ağırlıklı ort. yaş", "value": f"{_gun(t['ort_gun'])} gün"},
    ]
    if t["kayitsiz"]:
        kartlar.append({"label": "Giriş kaydı yok", "value": tr_sayi(t["kayitsiz"])})
    metrik_satiri(kartlar)
    if not oz:
        st.info("Mikro'ya göre Happy Life'ta stok yok.")
        return True
    # Kullanıcı (22.10.2026): "palet listesine ihtiyacım yok; sadece adet, model ve stok yaşı yeterli"
    st.caption("Yaş, malın Happy Life'a girdiği günden (ithalat girişi ya da depolar arası sevk) FIFO ile: en eski "
               "önce çıkar, elde kalan stok en yeni girişlerdendir. Her gün kendiliğinden güncellenir.")
    ciz([{"Model": r["ad"] or r["sku"], "SKU": r["sku"], "Adet": r["stok"],
          "En eski giriş": r["en_eski_tarih"] or None, "Stok yaşı (gün)": r["en_eski_gun"],
          "Ort. yaş (gün)": r["ort_gun"]} for r in oz],
        [kolon("Model", ana=True, alt="SKU"), kolon("SKU", gizli=True), kolon("Adet", "adet", gen="90px"),
         kolon("En eski giriş", "tarih", gen="110px", genis=True), kolon("Stok yaşı (gün)", "adet", gen="110px"),
         kolon("Ort. yaş (gün)", "adet", gen="100px", dar="alt")],
        "hl_mikro_ozet", excel="happylife_mikro_ozet")
    return True
