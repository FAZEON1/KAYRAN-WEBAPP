# -*- coding: utf-8 -*-
"""Streamlit uyum katmanı (yeni uygulama, Faz 0 — Ekim 2026).

Mevcut iş kuralları (shared/, kayranacc/, kayranpm/ …) `import streamlit as st` ile yazıldı ve üç şeyini
kullanır: `st.cache_data` / `st.cache_resource` (önbellek), `st.secrets` (Supabase adresi, şifre özetleri)
ve ara sıra `st.session_state`. API bu kodu YENİDEN YAZMADAN kullanmak için gerçek Streamlit yerine bu
küçük modülü koyar:

  • cache_data(ttl=…) / cache_resource → süreç içi, süreli bellek önbelleği (.clear() de çalışır)
  • secrets → ortam değişkenlerinden (Render panelinde girilir; koda ve sohbete yazılmaz):
        SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY   → st.secrets["supabase"]
        KULLANICILAR_JSON  ({"ad": "pbkdf2…özet"})  → st.secrets["kullanicilar"]
  • ekran çağrıları (st.markdown, st.error …) → sessiz; API'de ekran yok

`kur()` shared/ içe aktarılmadan ÖNCE bir kez çağrılır (api/main.py en üstte).
"""
import functools
import json
import os
import sys
import threading
import time
import types


class _Sir(dict):
    """st.secrets yerine: sözlük; bulunmayan anahtar KeyError (Streamlit gibi)."""


def gizli_ayarlar(ortam=None):
    """Ortam değişkenlerinden st.secrets karşılığı (saf; test edilir)."""
    o = os.environ if ortam is None else ortam
    s = _Sir()
    if o.get("SUPABASE_URL"):
        s["supabase"] = {"url": o["SUPABASE_URL"],
                         "service_role_key": o.get("SUPABASE_SERVICE_ROLE_KEY", ""),
                         "key": o.get("SUPABASE_SERVICE_ROLE_KEY", "")}
    try:
        kul = json.loads(o.get("KULLANICILAR_JSON") or "{}")
    except ValueError:
        kul = {}
    s["kullanicilar"] = {str(k): str(v) for k, v in (kul or {}).items()} if isinstance(kul, dict) else {}
    return s


def _onbellek(ttl=None, **_):
    """@st.cache_data / @st.cache_resource karşılığı: argümanlara göre süreli bellek önbelleği."""
    def sar(fn):
        kayit, kilit = {}, threading.Lock()

        @functools.wraps(fn)
        def ic(*a, **k):
            try:
                anahtar = (a, tuple(sorted(k.items())))
                hash(anahtar)
            except TypeError:                       # sözlük / liste argüman → önbelleksiz
                return fn(*a, **k)
            simdi = time.monotonic()
            with kilit:
                v = kayit.get(anahtar)
                if v is not None and (ttl is None or simdi - v[0] < _saniye(ttl)):
                    return v[1]
            sonuc = fn(*a, **k)
            with kilit:
                kayit[anahtar] = (simdi, sonuc)
            return sonuc

        ic.clear = lambda *_a, **_k: kayit.clear()
        return ic
    return sar


def _saniye(ttl):
    if isinstance(ttl, (int, float)):
        return float(ttl)
    try:
        return float(getattr(ttl, "total_seconds")())
    except Exception:  # noqa: BLE001 — "1h" gibi metin: güvenli tarafta kısa tut
        return 60.0


def _bezeme(*a, **k):
    """Hem @st.cache_data hem @st.cache_data(ttl=…) biçimi."""
    if a and callable(a[0]) and not k:
        return _onbellek()(a[0])
    return _onbellek(**k)


def _sessiz(*_a, **_k):
    return None


def modul():
    """Sahte `streamlit` modülü (kurmadan da test edilebilsin diye ayrı)."""
    st = types.ModuleType("streamlit")
    st.__kayran_uyum__ = True
    st.cache_data = _bezeme
    st.cache_resource = _bezeme
    st.secrets = gizli_ayarlar()
    st.session_state = {}
    st.query_params = {}
    st.fragment = _bezeme
    st.dialog = lambda *a, **k: (lambda fn: fn)
    st.__getattr__ = lambda ad: _sessiz          # st.markdown, st.error … ekran yok
    return st


def kur():
    """sys.modules['streamlit'] yerine uyum modülünü koyar (gerçek Streamlit kurulu olsa bile)."""
    mevcut = sys.modules.get("streamlit")
    if mevcut is not None and getattr(mevcut, "__kayran_uyum__", False):
        return mevcut
    st = modul()
    sys.modules["streamlit"] = st
    return st
