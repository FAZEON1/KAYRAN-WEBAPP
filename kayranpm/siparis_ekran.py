# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Sipariş Önerisi (Ekim 2026).

Düzeltilenler:
  • Onay / red için ID yazılıyordu ama ID sütunu tabloda GİZLİYDİ; kutu 1'den
    başladığından yanlışlıkla 1 numaralı öneri onaylanabiliyordu → her bekleyen
    önerinin kendi satırında Onayla / Reddet.
  • Öneri listesi boşsa sayfa duruyor (stop), bekleyen önerilerin onay
    bölümüne ulaşılamıyordu → geçmiş her durumda çizilir.
  • Bekleyen önerisi olan ürüne art arda öneri eklenebiliyordu ve bu görünmüyordu
    → satırda "bekliyor · N adet" çipi.
"""
import html as _h

import streamlit as st

from shared import bilesen as B
from shared.tasarim import tr_sayi
from shared.tasarim import renk as trenk  # aktif temanın rengi (hex)
from shared.utils import metrik_satiri

from .urun_hesap import bekleyen_haritasi, siparis_durum_adi, tarih_tr

_DURUM_RENK = {"acil": "kirmizi", "yaklasıyor": "amber", "planlama": "amber2"}
_DURUM_AD = {"acil": "Acil", "yaklasıyor": "30 gün içinde", "planlama": "60 gün içinde"}
_GECMIS_RENK = {"bekliyor": "amber", "onaylandi": "yesil", "reddedildi": "kirmizi"}


def _e(v):
    return _h.escape(str(v or "").strip())


def _esik_ayari(esik):
    from .database import set_uretim_suresi
    with st.popover(f"Sipariş eşiği: {esik} gün", icon=":material/tune:"):
        st.caption("Stok bu kadar günde biteceği zaman 'sipariş ver' uyarısı çıkar. "
                   "Üretim/tedarik sürenize göre ayarlayın (varsayılan 135 gün).")
        yeni = st.number_input("Eşik (gün)", min_value=1, max_value=730, value=int(esik),
                               step=5, key="uretim_suresi_input")
        if st.button("Kaydet", use_container_width=True, key="uretim_suresi_kaydet", icon=":material/save:"):
            if set_uretim_suresi(int(yeni)):
                st.cache_data.clear()
                st.toast(f"✅ Sipariş eşiği {int(yeni)} güne ayarlandı", icon="✅")
                st.rerun()
            else:
                st.error("Kaydedilemedi. 'pm_ayarlar' tablosu eksik olabilir — Supabase'de şu SQL'i çalıştırın:")
                st.code("create table if not exists pm_ayarlar (anahtar text primary key, deger text);\n"
                        "alter table pm_ayarlar disable row level security;", language="sql")


def _mesaj_kisa(m):
    """'ACİL — 74g'de biter' → '74g'de biter' (durum zaten çipte yazıyor)."""
    m = str(m or "").strip()
    return m.split(" — ", 1)[1] if " — " in m else m


def _oneriler(esik, bekleyen):
    from .analitik import siparis_onerisi_listesi, tum_urunler_listesi
    try:
        liste = siparis_onerisi_listesi()
        urun_dict = {u["sku"]: u for u in tum_urunler_listesi()}
    except Exception as e:
        st.error(f"Veri yüklenemedi: {e}")
        return
    if not liste:
        st.success(f"✅ Tüm ürünlerde {esik} günden fazla stok var, sipariş gerekmiyor.")
        return
    say = {d: sum(1 for u in liste if u.get("siparis_durum") == d) for d in _DURUM_AD}
    metrik_satiri([
        {"label": "🔴 Acil", "value": tr_sayi(say["acil"]), "renk": trenk("kirmizi")},
        {"label": "🟠 30 gün içinde", "value": tr_sayi(say["yaklasıyor"]), "renk": trenk("amber")},
        {"label": "🟡 60 gün içinde", "value": tr_sayi(say["planlama"]), "renk": trenk("amber")},
    ])
    st.markdown(B.grup_basligi("Önerilen siparişler", f"{len(liste)} ürün"), unsafe_allow_html=True)
    limit = int(st.session_state.get("sp_oneri_limit", 25))
    for u in liste[:limit]:
        sku = u["sku"]
        d = u.get("siparis_durum", "")
        ud = urun_dict.get(sku, {})
        fcp, satis = ud.get("final_cost_price") or 0, ud.get("satis_fiyati") or 0
        firma_kisa = " · ".join(f'{fd["firma"]} {fd["stok"]}' for fd in u.get("firma_detay", [])
                                if fd.get("stok", 0) > 0)
        meta = B.meta(
            B.cip(_DURUM_AD.get(d, d or "—"), _DURUM_RENK.get(d, "silik")),
            _mesaj_kisa(u.get("siparis_mesaj", "")),
            f'G5F {tr_sayi(u.get("bizim_stok", 0))}',
            f'haftalık {tr_sayi(u.get("ortalama_haftalik_satis", 0) or 0, 1)}',
            firma_kisa,
            # "&#36;": düz "$" iki kez geçerse st.markdown LaTeX sanır (tuzak 2)
            (f"<span>paçal &#36;{tr_sayi(fcp, 2)} → satış &#36;{tr_sayi(satis, 2)}</span>" if fcp else ""),
            (B.cip(f"bekliyor · {tr_sayi(bekleyen[sku])} adet", "amber",
                   title="Bu ürün için onay bekleyen öneri var") if bekleyen.get(sku) else ""))
        oneri = int(u.get("oneri_miktar", 0) or 0)
        with st.container(border=True):
            c1, c2, c3 = st.columns([6, 1.2, 1.6], vertical_alignment="center")
            c1.markdown(
                f'<div style="font-size:13.5px;font-weight:600;white-space:nowrap;overflow:hidden;'
                f'text-overflow:ellipsis">{_e(u.get("urun_adi"))} <span style="font-family:var(--k-mono);'
                f'font-size:12px;color:var(--k-mor2)">{_e(sku)}</span></div>{meta}'
                f'<div style="font-size:12px;color:var(--k-amber);margin-top:2px">💡 '
                + (_e(u.get("oneri_mesaj")) if u.get("oneri_mesaj") else f"öneri {tr_sayi(oneri)} adet") + "</div>",
                unsafe_allow_html=True)
            miktar = c2.number_input("Miktar", min_value=1, value=max(oneri, 1),
                                     key=f"sp_miktar_{sku}", label_visibility="collapsed")
            if c3.button("Sipariş ekle", key=f"sp_btn_{sku}", use_container_width=True,
                         icon=":material/inventory_2:"):
                from .database import ekle_siparis_onerisi
                ekle_siparis_onerisi("G5F", sku, u["urun_adi"], miktar)
                st.cache_data.clear()
                st.toast(f"✅ {u['urun_adi']} için {miktar} adet sipariş önerisi oluşturuldu")
                st.rerun()
    if len(liste) > limit:
        st.button(f"Daha fazla göster ({len(liste) - limit} ürün daha)", key="sp_oneri_daha", type="tertiary",
                  use_container_width=True,
                  on_click=lambda: st.session_state.__setitem__("sp_oneri_limit", limit + 25))


def _onayla(sid):
    from .database import onayla_siparis
    onayla_siparis(int(sid))
    st.cache_data.clear()
    st.toast("✅ Öneri onaylandı")


def _reddet(sid):
    from .database import reddet_siparis
    reddet_siparis(int(sid))
    st.cache_data.clear()
    st.toast("Öneri reddedildi")


def _satir(sp):
    d = sp.get("durum", "")
    tarih = tarih_tr(sp.get("olusturma_tarihi"), saat=True)
    onay = tarih_tr(sp.get("onay_tarihi"), saat=True) if sp.get("onay_tarihi") else ""
    html = (f'<div style="font-size:13.5px;font-weight:600;white-space:nowrap;overflow:hidden;'
            f'text-overflow:ellipsis">{_e(sp.get("urun_adi"))} <span style="font-family:var(--k-mono);'
            f'font-size:12px;color:var(--k-mor2)">{_e(sp.get("sku"))}</span></div>'
            + B.meta(B.cip(siparis_durum_adi(d), _GECMIS_RENK.get(d, "silik")),
                     f'{tr_sayi(sp.get("oneri_miktari") or 0)} adet', f"oluşturma {tarih}",
                     f"sonuç {onay}" if onay else ""))
    if d == "bekliyor":
        c1, c2, c3 = st.columns([6, 1.2, 1.2], vertical_alignment="center")
        c1.markdown(html, unsafe_allow_html=True)
        c2.button("Onayla", key=f"sp_onay_{sp['id']}", icon=":material/check_circle:", type="primary",
                  use_container_width=True, on_click=_onayla, args=(sp["id"],))
        c3.button("Reddet", key=f"sp_red_{sp['id']}", icon=":material/close:",
                  use_container_width=True, on_click=_reddet, args=(sp["id"],))
    else:
        st.markdown(html, unsafe_allow_html=True)
    st.markdown('<div style="height:1px;background:var(--k-kenar);margin:4px 0 6px"></div>',
                unsafe_allow_html=True)


def _bekleyenler(onceki):
    """Onay bekleyenler önerilerin ÜSTÜNDE: yapılacak iş bunlar."""
    bekl = [sp for sp in onceki if sp.get("durum") == "bekliyor"]
    if not bekl:
        return
    st.markdown(B.grup_basligi("Onay bekleyen öneriler", f"{len(bekl)} öneri"), unsafe_allow_html=True)
    for sp in bekl:
        _satir(sp)


def _gecmis(onceki):
    diger = [sp for sp in onceki if sp.get("durum") != "bekliyor"]
    st.markdown(B.grup_basligi("Sonuçlanan öneriler", f"{len(diger)} kayıt"), unsafe_allow_html=True)
    if not diger:
        st.caption("Henüz onaylanan ya da reddedilen öneri yok.")
        return
    limit = int(st.session_state.get("sp_gecmis_limit", 20))
    for sp in diger[:limit]:
        _satir(sp)
    if len(diger) > limit:
        st.button(f"Daha fazla göster ({len(diger) - limit} kayıt daha)", key="sp_gecmis_daha",
                  type="tertiary", use_container_width=True,
                  on_click=lambda: st.session_state.__setitem__("sp_gecmis_limit", limit + 20))


def render(_sb):
    from .database import get_uretim_suresi, get_siparis_onerileri
    esik = get_uretim_suresi()
    st.markdown(_sb("📦 Ürün Yönetimi", "Sipariş Önerisi",
                    aciklama=f"{esik} günden az stok kalan ürünler · otomatik öneri"), unsafe_allow_html=True)
    st.markdown('<div class="sayfa-baslik-cizgi"></div>', unsafe_allow_html=True)
    _esik_ayari(esik)
    try:
        onceki = get_siparis_onerileri() or []
    except Exception:
        onceki = []
    _bekleyenler(onceki)
    _oneriler(esik, bekleyen_haritasi(onceki))
    _gecmis(onceki)
