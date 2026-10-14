# -*- coding: utf-8 -*-
"""Muhasebe › Firma Çekleri — ORTAK LİSTE MASASINDA (Ekim 2026, salt okunur).

Başlık main.py'de (eskisi gibi). Para birimi seçici (TL / USD) → masa: özet (toplam meblağ · ödenen · kalan),
görünüm çipleri (bekleyen/ciro · gecikmiş · ödendi), banka seçimi, arama, sıralama; satıra tıkla → sağda
bütün alanlar. Rakamlar cek_tutarlari'ndan (eski tabloyla aynı kural); tanım muhasebe_masalari'nda.
Geri almak için: FIRMA_CEKLERI_MASASI_YENI = False → main.py'deki eski sekmeli tablo aynen.
"""
import streamlit as st

from shared.utils import tr_today
from .database import get_cekler

FIRMA_CEKLERI_MASASI_YENI = True


def render_firma_cekleri():
    from shared.masa import calistir
    from . import muhasebe_masalari as MM
    pb = st.segmented_control("Para birimi", ["TL", "USD"], default="TL", key="fcek_pb",
                              format_func=lambda p: f"{p} çekleri", label_visibility="collapsed") or "TL"
    cekler = get_cekler(pb) or []
    if not cekler:
        st.info(f"{pb} çeki bulunamadı.")
        return
    calistir(MM.firma_cekleri_verisi(cekler, pb, tr_today()), f"firma_cek_masasi_{pb}", MM.salt_okunur_yurutucu())
