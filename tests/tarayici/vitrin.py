# -*- coding: utf-8 -*-
"""Tarayıcı taraması için uygulama girişi (Ekim 2026): sahte veritabanı + örnek veri, giriş atlanır.

    streamlit run tests/tarayici/vitrin.py --server.port 8601 --server.headless true
    (.streamlit/secrets.toml'da [supabase] url/key sahte değerler olmalı — CI iş akışı yazar)

Adres: ?mod=<modül>&anahtar=<sayfa anahtarı>&sec=<sayfa seçeneği>. Gerçek veritabanına bağlanmaz;
yazma işlemleri bellekteki sahte tablolara gider ve sunucu kapanınca kaybolur."""
import os
import runpy
import sys

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DUMAN = os.path.join(KOK, "tests", "duman")
for _y in (KOK, DUMAN):
    if _y not in sys.path:
        sys.path.insert(0, _y)

import sahte_db  # noqa: E402
import ornek_veri  # noqa: E402

sahte_db.kur()
if not sahte_db.TABLOLAR.get("urunler"):
    ornek_veri.doldur(sahte_db.TABLOLAR)
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]

import streamlit as st  # noqa: E402

_q = st.query_params
if not st.session_state.get("_vitrin"):
    st.session_state["_vitrin"] = 1
    st.session_state["giris_yapildi"] = True
    st.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    if _q.get("mod"):
        st.session_state["aktif_uygulama"] = _q["mod"]
    if _q.get("anahtar"):
        st.session_state[_q["anahtar"]] = _q.get("sec")

runpy.run_path(os.path.join(KOK, "app.py"), run_name="__main__")
