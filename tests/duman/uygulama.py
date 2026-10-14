# -*- coding: utf-8 -*-
"""Sayfa testinin çalıştırdığı betik: sahte veritabanını kurar, hata kaydını dinler, app.py'yi çalıştırır.
(streamlit.testing AppTest bu dosyayı her çalıştırmada baştan yürütür.)"""
import os
import runpy
import sys

_BURASI = os.path.dirname(os.path.abspath(__file__))
_KOK = os.path.dirname(os.path.dirname(_BURASI))
for _y in (_KOK, _BURASI):
    if _y not in sys.path:
        sys.path.insert(0, _y)

import sahte_db  # noqa: E402

sahte_db.kur()

import streamlit as st  # noqa: E402
import shared.hata_log as _hl  # noqa: E402


def _kaydet(yer, hata=None, *a, **k):
    """Uygulamanın yakaladığı hatalar (sayfa çökmesi vb.) testte görünsün."""
    st.session_state.setdefault("_duman_hatalar", []).append(
        f"{yer}: {type(hata).__name__}: {str(hata)[:300]}" if isinstance(hata, BaseException) else f"{yer}: {hata}")
    return True


_hl.kaydet = _kaydet

# Örnek veriyle çalışan testler (test_stok_yasi_veri) önceki sayfaların BOŞ veriyle doldurduğu
# önbelleği temizletir; temizlik AppTest çalışma zamanının içinde yapılmalı.
if os.environ.get("DUMAN_ONBELLEK_TEMIZLE"):
    st.cache_data.clear()
    from shared.veri_surumu import bagimlilari_temizle, SATIS_BAGIMLILAR   # uygulamanın kendi tazelik listeleri
    bagimlilari_temizle()
    bagimlilari_temizle(SATIS_BAGIMLILAR)
    # Muhasebe okumaları (hafta, ödeme, banka …) genel temizlikle boşalmıyor (önceki sayfanın boş
    # verisi kalıyordu — hafta seçici / ertelenen ödeme testleri); modülün bütün önbellekli okumaları tek tek.
    # SKU hareketleri sayfasının model listesi (teknikservis) ve ithalat partileri de aynı durumda (Ekim 2026).
    import kayranacc.database as _acc_db
    import teknikservis.database as _ts_db
    import ithalat.database as _ith_db
    for _mod in (_acc_db, _ts_db, _ith_db):
        for _fn in vars(_mod).values():
            if type(_fn).__name__ == "CachedFunc":
                _fn.clear()

# Bileşenler (components v2) ilk çağrıda bir kez kaydedilip modülde tutulur; kayıt Streamlit
# örneğine bağlı. Canlıda tek örnek var; test her sayfa için yeni örnek açtığından kayıt yenilenir.
for _ad in ("shared.palet", "shared.tablo", "shared.duzenle", "shared.ceviri", "shared.ipucu", "shared.islem",
            "shared.masa"):
    _m = sys.modules.get(_ad)
    if _m is not None and hasattr(_m, "_BILESEN"):
        _m._BILESEN = None
runpy.run_path(os.path.join(_KOK, "app.py"), run_name="__main__")
