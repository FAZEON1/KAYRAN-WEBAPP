# -*- coding: utf-8 -*-
"""Paçal: önceki ↔ şimdiki — ana veri entegrasyonu Faz 2a/2b (Ekim 2026). SALT OKUNUR.

Üç ekranın bugün gösterdiği paçalı (Tüm Ürünler · stok kartı · P&L) önerilen tek
tanımla yan yana koyar; farklı olan ürünleri sebebiyle listeler. Hiçbir hesabı
değiştirmez, hiçbir şey yazmaz. Kullanıcı bu listeyi onaylayınca Faz 2b'de üç ekran
yeni tanıma bağlanır. Hesap: ithalat/pacal_hesap.py.
"""
import streamlit as st

from shared.tasarim import tr_sayi


def goster():
    st.caption(
        "Faz 2b ile **Tüm Ürünler, ürün (stok) kartı, P&L ve Teknik Servis aynı paçalı gösteriyor**: "
        "yoldaki partiler hariç, aynı ürünün bütün SKU yazımları birleşik, ithalatı yoksa yurt içi alış. "
        "Bu tablo, bu değişiklikle rakamı değişen ürünleri gösterir — 'Önceki' sütunları ekranların "
        "değişiklikten önce gösterdiği değer, 'Şimdiki' artık her yerde görünen değer. Hiçbir şey yazmaz.")
    if not st.button("Karşılaştır", key="pacal_kars_btn", icon=":material/compare_arrows:"):
        return
    from ithalat.database import get_parti_satirlari
    from ithalat.pacal_hesap import karsilastir
    from shared.utils import sku_anahtar
    from shared.tablo import tablo
    from .database import _hepsi
    try:
        kartlar = _hepsi("urunler", "sku, urun_adi, alis_fiyati", "sku") or []
    except Exception as e:  # noqa: BLE001
        st.error(f"Ürün kartları okunamadı: {type(e).__name__}: {e}")
        return
    satirlar = get_parti_satirlari()
    if not satirlar:
        st.warning("İthalat kalemleri okunamadı ya da hiç yok; karşılaştırma yapılamadı.")
        return
    rows, oz = karsilastir(satirlar, kartlar, sku_anahtar)
    st.markdown(f"**{tr_sayi(oz['urun'])}** ürünün **{tr_sayi(oz['farkli'])}** tanesinde en az bir ekran "
                f"şimdiki değerden %0,5'ten fazla farklıydı.")
    if oz["sebep"]:
        st.markdown("  \n".join(f"• {s}: **{tr_sayi(n)}** ürün"
                                for s, n in sorted(oz["sebep"].items(), key=lambda x: -x[1])))
    if rows:
        tablo(rows, key="pacal_kars_tablo", dosya_adi="pacal_karsilastirma", birim="$")
        st.caption("Boş hücre: o ekran bu ürün için paçal göstermiyor. Tabloyu sağ üstteki düğmeyle "
                   "indirip inceleyebilirsin.")
