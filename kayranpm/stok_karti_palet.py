# -*- coding: utf-8 -*-
"""Stok kartı arama penceresi (Ctrl+K, shared/palet.py) için ürün özetleri (Ekim 2026).

Pencere ürünleri tarayıcıda, yazarken anında süzer; her satırda stok ve "kaç gün yeter" görünür. Kural stok
kartınınkiyle aynı (kayranpm/stok_karti.py, stok_karti_yeni.durum_uyarilari):
  günlük hız   son 90 günün satış adedi / 90 (SKU yazımından bağımsız, shared.utils.sku_anahtar)
  kaç gün      satılabilir stok / günlük hız
  durum        siparis  → stok + yolda ≤ günlük hız × tedarik süresi (kartta "Sipariş zamanı")
               yeter    → satışı var, sipariş noktasının üstünde
               satissiz → stok var, son 90 günde satış yok (kartta "Hareketsiz stok")
               yok      → stok da satış da yok
"""
from datetime import timedelta

import streamlit as st

HIZ_GUN = 90


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def ozet_satirlari(urunler, satislar, yolda, bugun, uretim_suresi, anahtar):
    """[{sku, ad, stok, gun, durum}] — urunler: kartlar (sku, urun_adi, bizim_stok); satislar: (sku, adet,
    tarih); yolda: {sku: adet}. Sıra kartların sırası."""
    bas = (bugun - timedelta(days=HIZ_GUN)).isoformat()
    satis = {}
    for s in satislar or []:
        if str(s.get("tarih") or "")[:10] >= bas:
            k = anahtar(s.get("sku"))
            satis[k] = satis.get(k, 0.0) + _f(s.get("adet"))
    yol = {}
    for sku, adet in (yolda or {}).items():
        yol[anahtar(sku)] = yol.get(anahtar(sku), 0.0) + _f(adet)
    out = []
    for u in urunler or []:
        sku = str(u.get("sku") or "").strip()
        if not sku:
            continue
        k = anahtar(sku)
        stok = max(_f(u.get("bizim_stok")), 0.0)
        hiz = satis.get(k, 0.0) / HIZ_GUN
        gun = round(stok / hiz) if hiz > 0 else None
        if hiz > 0:
            durum = "siparis" if stok + yol.get(k, 0.0) <= hiz * uretim_suresi else "yeter"
        else:
            durum = "satissiz" if stok > 0 else "yok"
        out.append({"sku": sku, "ad": str(u.get("urun_adi") or "").strip(), "stok": int(round(stok)),
                    "gun": gun, "durum": durum})
    return out


@st.cache_data(ttl=300, show_spinner=False)
def _oku():
    from kayranpm.database import urunler_skuya_gore, get_yoldaki_urunler, get_uretim_suresi
    from satis.database import get_satislar_yalin
    from shared.utils import sku_anahtar, tr_today
    bugun = tr_today()
    try:
        uretim = int(get_uretim_suresi() or 135)
    except Exception:  # noqa: BLE001
        uretim = 135
    yolda = {s: _f(r.get("yoldaki_miktar")) for s, r in (get_yoldaki_urunler() or {}).items()}
    satis = get_satislar_yalin((bugun - timedelta(days=HIZ_GUN)).isoformat()) or []
    return ozet_satirlari(urunler_skuya_gore() or [], satis, yolda, bugun, uretim, sku_anahtar)


def palet_urunleri():
    """Canlı veriden ürün özetleri (5 dk önbellek). Okunamazsa []: pencere sunucu aramasına döner."""
    try:
        return _oku()
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("kayranpm.stok_karti_palet.palet_urunleri", e)
        return []
