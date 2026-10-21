# -*- coding: utf-8 -*-
"""Geçmiş İthalatlar › Mikro eşitlemesi bölümü (Ekim 2026). Hesap: ithalat/mikro_ithalat.py.

Ayrı sayfa yok (kullanıcı): Geçmiş İthalatlar'ın üstünde kısa bir not ve kapalı bir bölüm. Bölümde son
eşitlemenin değiştirdiği dosyalar (masraf önce → sonra, % maliyet, durum), eklenen dosyalar, paçalı değişen
ürünler ve Mikro'yla eşleşmeyen dosyalar. Salt okunur.
"""
import pandas as pd
import streamlit as st

from shared.tasarim import tr_sayi

from . import mikro_ithalat as M


def _usd(v):
    return f"${tr_sayi(v, 2)}"


def _yuzde(v):
    return f"%{tr_sayi(v, 1)}"


def degisen_satirlari(rapor):
    return [{"Dosya": r.get("dosya_no"), "Mikro dosyası": r.get("kod"), "FOB": _usd(r.get("fob", 0)),
             "Masraf (önce)": _usd(r.get("masraf_once", 0)), "Masraf (Mikro)": _usd(r.get("masraf_sonra", 0)),
             "% maliyet": f"{_yuzde(r.get('yuzde_once', 0))} → {_yuzde(r.get('yuzde_sonra', 0))}",
             "Durum": r.get("durum_sonra") if r.get("durum_once") == r.get("durum_sonra")
             else f"{r.get('durum_once') or '—'} → {r.get('durum_sonra')}"}
            for r in rapor.get("degisen") or []]


def pacal_satirlari(rapor):
    return [{"Ürün": p["sku"], "Paçal (önce)": _usd(p["once"]), "Paçal (sonra)": _usd(p["sonra"]),
             "Fark": _usd(p["sonra"] - p["once"])} for p in rapor.get("pacal") or []]


def bolum():
    """Geçmiş İthalatlar'ın üstü. Eşitleme kapalıysa ya da hiç çalışmadıysa yalnız kısa not."""
    try:
        acik = M.acik_mi()
    except Exception:  # noqa: BLE001
        return
    if not acik:
        return
    from kayranacc.database import get_ayar
    rapor = (get_ayar(M.RAPOR_ANAHTAR, {}) or {})
    son = rapor.get("son") or {}
    st.caption("Masraflar, teslim tarihi / deposu, durum ve beyanname no Mikro'dan otomatik gelir; Mikro'da açılan yeni "
               "ithalat dosyası buraya kendiliğinden eklenir. Değişmeden önce her dosyanın eski hâli arşivlenir.")
    if not son:
        return
    gecmis = rapor.get("gecmis") or []
    son_degisiklik = gecmis[0] if gecmis else son
    oz = son.get("ozet") or {}
    baslik = (f"Mikro eşitlemesi · {oz.get('bagli_mikro', 0)} Mikro dosyası bağlı"
              + (f" · {len(son.get('eslesmeyen') or [])} eşleşmeyen" if son.get("eslesmeyen") else ""))
    with st.expander(baslik, expanded=False, icon=":material/sync:"):
        zaman = str(son_degisiklik.get("zaman") or "")[:16].replace("T", " ")
        st.caption(f"Son değişiklik: {zaman} UTC")
        if son_degisiklik.get("degisen"):
            st.markdown("**Değişen dosyalar**")
            st.dataframe(pd.DataFrame(degisen_satirlari(son_degisiklik)), hide_index=True, use_container_width=True)
        if son_degisiklik.get("yeni"):
            st.markdown("**Mikro'dan eklenen dosyalar:** " + ", ".join(son_degisiklik["yeni"]))
        if son_degisiklik.get("pacal"):
            st.markdown("**Paçalı değişen ürünler**")
            st.dataframe(pd.DataFrame(pacal_satirlari(son_degisiklik)), hide_index=True, use_container_width=True)
        if son.get("eslesmeyen"):
            st.markdown("**Mikro'da olup uygulamadaki dosyalarla eşleşmeyenler** (çift kayıt olmasın diye eklenmedi)")
            st.dataframe(pd.DataFrame([{"Mikro dosyası": e["kod"], "Tedarikçi": e["tedarikci"], "Giriş": e["giris"],
                                        "Adet": tr_sayi(e["adet"]), "Sebep": e["sebep"]}
                                       for e in son["eslesmeyen"]]), hide_index=True, use_container_width=True)
        hata = (son_degisiklik.get("sonuc") or {}).get("hata") or []
        if hata:
            st.warning("Yazılamayanlar: " + "; ".join(hata))
