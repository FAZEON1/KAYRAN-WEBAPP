# -*- coding: utf-8 -*-
"""API testleri: gerçek veritabanına gitmez. Supabase'e dokunan iki nokta (şifre tablosu, yetki tablosu,
deneme kilidi) her testte sahte sözlüklerle değiştirilir. Çalıştırma (depo kökünden):
    pip install -r api/requirements.txt pytest httpx && python -m pytest api/tests -q
"""
import os
import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[2]
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))
os.environ.setdefault("OTURUM_ANAHTARI", "t" * 48)
os.environ.setdefault("ORTAM", "gelistirme")
os.environ.setdefault("ESKI_UYGULAMA_URL", "https://kayran.streamlit.app")


@pytest.fixture
def ortam(monkeypatch):
    """Sahte kullanıcılar: ibrahim (Muhasebe + kâr, şifre veritabanında), serdar (Satış, şifre yalnız
    gizli ayarda), pasif (pasif hesap). Döner: kilit sayaçları ve hazır TestClient."""
    from fastapi.testclient import TestClient
    import api.main as M
    import shared.auth as A
    import shared.yetki as Y
    import streamlit as st
    from shared.auth import sifre_hash_uret

    tablo = {
        "ibrahim": {"moduller": ["kayranacc"], "ozel": ["kar"], "salt_okur": False, "aktif": True},
        "serdar": {"moduller": ["satis"], "ozel": [], "salt_okur": False, "aktif": True},
        "pasif": {"moduller": ["kayranacc"], "ozel": [], "salt_okur": False, "aktif": False},
    }
    db_sifre = {"ibrahim": sifre_hash_uret("dogru-sifre", 1000), "pasif": sifre_hash_uret("x", 1000)}
    monkeypatch.setattr(Y, "yetki_tablosu", lambda: tablo)
    monkeypatch.setattr(A, "supabase_sifre_oku", lambda k: db_sifre.get(k))
    monkeypatch.setitem(st.secrets, "kullanicilar", {"serdar": sifre_hash_uret("serdar-sifre", 1000)})
    kayit = {"basarisiz": {}, "basarili": [], "kilitli": set()}

    def _basarisiz(k):
        n = kayit["basarisiz"][k] = kayit["basarisiz"].get(k, 0) + 1
        return n, (60 if n >= 5 else 0)

    monkeypatch.setattr(A, "giris_kontrol", lambda k: (False, 75) if k in kayit["kilitli"] else (True, 0))
    monkeypatch.setattr(A, "giris_basarisiz", _basarisiz)
    monkeypatch.setattr(A, "giris_basarili", lambda k: kayit["basarili"].append(k))
    kayit["tablo"] = tablo
    kayit["istemci"] = TestClient(M.app)
    return kayit
