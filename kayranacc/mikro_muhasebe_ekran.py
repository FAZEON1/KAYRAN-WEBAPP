# -*- coding: utf-8 -*-
"""Mikro'dan otomatik muhasebe — ilk onay kutusu (Ekim 2026). Hesap: kayranacc/mikro_muhasebe.py.

Satıştaki gibi ayrı sayfa yok: eşitleme kapalıyken Muhasebe › Banka Bakiyeleri'nin üstünde bir kez salt okunur
"şimdi ↔ Mikro" karşılaştırması (banka, çek, cari, ithalat ödenen) ve onay düğmesi çıkar (rakam değiştiren
değişiklik, kullanıcı onayı şart). Onaylanınca kutu bir daha çıkmaz; eşitleme otomatik sürer.
Yalnız kârı görebilen kullanıcılar görür.
"""
import pandas as pd
import streamlit as st

from shared.tasarim import tr_sayi

from . import mikro_muhasebe as M

_ISARET = {"TL": "₺", "TRY": "₺", "USD": "$", "EUR": "€"}


def _tutar(v, pb):
    return "" if v is None else f"{_ISARET.get(pb, '')}{tr_sayi(v, 2)}"


def _banka_tablosu(plan):
    satir = []
    for b in plan["banka"]:
        pb = b["para_birimi"]
        fark = None if b["sonra"] is None else round(b["sonra"] - b["once"], 2)
        satir.append({"Hesap": b["hesap"], "Şimdi": _tutar(b["once"], pb),
                      "Mikro": _tutar(b["sonra"], pb) if b["sonra"] is not None else "eşleşmedi",
                      "Fark": _tutar(fark, pb) if fark else "", "Mikro hesabı": b["mikro_ad"]})
    return pd.DataFrame(satir)


def _cari_tablosu(plan):
    once, sonra = plan["cari_once"] or {}, plan["cari"]
    satir = []
    for yon, ad in (("alacak", "Alacak (bize borçlu)"), ("borc", "Borç (avans dahil)")):
        for pb, k in (("USD", "usd"), ("TL", "tl"), ("EUR", "eur")):
            a, b = M._f((once.get(yon) or {}).get(k)), sonra[yon][k]
            if a or b:
                satir.append({"Kalem": f"{ad} {pb}", "Şimdi": _tutar(a, pb), "Mikro": _tutar(b, pb),
                              "Fark": _tutar(round(b - a, 2), pb) if abs(b - a) >= M.KURUS else ""})
    satir.append({"Kalem": "İthalat ödenen (verilen avans) USD", "Şimdi": _tutar(M._f(plan["ithalat_once"]), "USD"),
                  "Mikro": _tutar(plan["ithalat"], "USD"),
                  "Fark": _tutar(round(plan["ithalat"] - M._f(plan["ithalat_once"]), 2), "USD")
                  if plan["ithalat_degisir"] else ""})
    return pd.DataFrame(satir)


def _cek_metni(oz):
    return " · ".join(f"{pb}: {n} çek, kalan {_tutar(t, pb)}" for pb, (n, t) in sorted(oz.items())) or "kalan çek yok"


def _plan_goster(plan):
    st.markdown("**Banka bakiyeleri**")
    st.dataframe(_banka_tablosu(plan), hide_index=True, use_container_width=True)
    if plan["banka_disarida"]:
        st.caption("Mikro'da olup uygulamada hesabı olmayanlar (eklenmez): " + " · ".join(
            f"{d['mikro_ad']} {tr_sayi(d['bakiye'], 2)}" for d in plan["banka_disarida"]))
    st.markdown("**Toplam Aktifler: cari ve ithalat ödenen**")
    st.dataframe(_cari_tablosu(plan), hide_index=True, use_container_width=True)
    st.markdown("**Firma çekleri**")
    st.caption(f"Şimdi: {_cek_metni(plan['cek_once'])}  \nMikro: {_cek_metni(plan['cek_sonra'])} "
               f"({len(plan['cek'])} çek, ödenenler dahil)")
    with st.expander("Mikro'daki çek listesi"):
        st.dataframe(pd.DataFrame([{"Çek no": c["cek_no"], "Vade": c["vade"], "Tutar": _tutar(c["meblagh"], c["para_birimi"]),
                                    "Kalan": _tutar(c["kalan"], c["para_birimi"]), "Durum": c["durum"],
                                    "Verildiği": c["ch_ismi"]} for c in plan["cek"]]),
                     hide_index=True, use_container_width=True)


def ilk_onay_kutusu():
    """Banka Bakiyeleri sayfasının üstü: eşitleme kapalıysa ve Mikro verisi geldiyse bir kerelik onay;
    açıksa kaynağı söyleyen kısa not."""
    from shared.kar_gizle import kar_gorunur
    d = M.durum()
    if d.get("acik"):
        st.caption("Banka bakiyeleri, firma çekleri ve Toplam Aktifler'deki cari / ithalat ödenen Mikro'dan "
                   "otomatik gelir (15 dakikada bir).")
        return
    if not kar_gorunur():
        return
    try:
        if not M.son_aktarim():
            return                        # aktarıcı muhasebe verisini henüz getirmedi
    except Exception:  # noqa: BLE001
        return
    with st.expander("Banka, çek, cari ve ithalat ödenen Mikro'dan otomatik gelsin (bir kez onay)",
                     expanded=False, icon=":material/sync:"):
        st.caption("Onaydan sonra banka bakiyeleri, firma çekleri ve Toplam Aktifler'deki cari borç / alacak ile "
                   "ithalat ödenen Mikro'dan kendiliğinden güncellenir; bu üç Excel yüklemesi kalkar. Uygulamada "
                   "girilen ödeme, tahsilat ve virman kayıtları durur, ama bakiye Mikro'daki hesaptan gelir. "
                   "Stok değeri ve gider tablosu kendi sayfalarında ayrı onayla gelir. Bu kutu bir daha çıkmaz.")
        if not st.toggle("Karşılaştırmayı göster", key="mm_goster"):
            return
        with st.spinner("Mikro hareketleri okunuyor…"):
            try:
                plan = M.plan_hazirla()
            except Exception as e:  # noqa: BLE001
                st.error(f"Mikro verisi okunamadı: {type(e).__name__}: {str(e)[:160]}")
                return
        _plan_goster(plan)
        onay = st.checkbox("Karşılaştırmayı gördüm; bu rakamların kaynağı bundan sonra Mikro olsun", key="mm_onay")
        if st.button("Onayla ve otomatik eşitlemeyi aç", type="primary", disabled=not onay,
                     icon=":material/sync:", key="mm_ac"):
            sonuc = M.uygula(plan, ilk=True)
            M.ac(st.session_state.get("aktif_kullanici", ""))
            st.success(f"Açıldı. {tr_sayi(sonuc['banka'])} banka bakiyesi güncellendi"
                       + (", çek listesi Mikro'dan yazıldı (eskiler çöp kutusunda)" if sonuc["cek"] else "")
                       + ". Bundan sonra otomatik.")
