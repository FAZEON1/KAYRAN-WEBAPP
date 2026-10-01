# -*- coding: utf-8 -*-
"""Sipariş önerisi — İthalat yolda/antrepo miktarı okunamazsa SESSİZ kalınmasın.

Antrepodaki mal 13.08.2026'dan beri sipariş önerisinde stok kapsamına giriyor
(test_siparis_takvimi.py). Ama İthalat okunamadığında hata yutuluyor, {} dönülüyor
ve bu eksik sonuç önbellekte kalıyordu → ürün yanlışlıkla "ACİL", mükerrer sipariş.
Şimdi: hata kayda geçer (kritik → Telegram), eksik sonuç önbelleğe girmez.
"""
import sys
import types
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent


@pytest.fixture
def pm_db(monkeypatch):
    import kayranpm.database as db
    ham = ([{"sku": "A"}], {}, {}, {"A": {"sku": "A", "yoldaki_miktar": 10, "varis_tarihi": ""}}, {})
    import copy
    monkeypatch.setattr(db, "_dashboard_ham", lambda: copy.deepcopy(ham))
    kayitlar = []
    sahte_log = types.ModuleType("shared.hata_log")
    sahte_log.kaydet = lambda yer, hata, ayrinti="", kritik=False: kayitlar.append((yer, str(hata), kritik)) or True
    monkeypatch.setitem(sys.modules, "shared.hata_log", sahte_log)
    return db, kayitlar


def _ithalat(monkeypatch, fn):
    sahte = types.ModuleType("ithalat.database")
    sahte.get_ithalat_yolda_ozet = fn
    monkeypatch.setitem(sys.modules, "ithalat.database", sahte)


def test_antrepodaki_mal_eklenir(pm_db, monkeypatch):
    db, kayit = pm_db
    _ithalat(monkeypatch, lambda: {"A": {"yoldaki_miktar": 800, "varis_tarihi": "2026-11-01", "durumlar": ["Antrepoda"]},
                                   "B": {"yoldaki_miktar": 50, "varis_tarihi": "", "durumlar": ["Yolda"]}})
    _, _, _, yol, _ = db.get_all_dashboard_data()
    assert yol["A"]["yoldaki_miktar"] == 810 and yol["A"]["_ithalat_durumlar"] == ["Antrepoda"]
    assert yol["A"]["varis_tarihi"] == "2026-11-01" and yol["B"]["yoldaki_miktar"] == 50
    assert kayit == []


def test_ithalat_okunamazsa_sayfa_acilir_hata_kritik_kaydedilir(pm_db, monkeypatch):
    db, kayit = pm_db
    def _patla():
        raise ConnectionError("bağlantı koptu")
    _ithalat(monkeypatch, _patla)
    _, _, _, yol, _ = db.get_all_dashboard_data()
    assert yol["A"]["yoldaki_miktar"] == 10                   # elle girilen yoldaki korunur
    assert len(kayit) == 1 and kayit[0][0] == "kayranpm.get_all_dashboard_data" and kayit[0][2] is True


def test_tekrar_cagri_ham_veriyi_bozmaz(pm_db, monkeypatch):
    """Birleştirme önbellekli ham veriye değil kopyasına yapılır (iki kez eklenmez)."""
    db, _ = pm_db
    _ithalat(monkeypatch, lambda: {"A": {"yoldaki_miktar": 800, "varis_tarihi": "", "durumlar": ["Antrepoda"]}})
    db.get_all_dashboard_data()
    _, _, _, yol, _ = db.get_all_dashboard_data()
    assert yol["A"]["yoldaki_miktar"] == 810


def test_kod_yapisi():
    pm = (KOK / "kayranpm/database.py").read_text(encoding="utf-8")
    i = pm.index("def get_all_dashboard_data():")
    assert "@st.cache_data" not in pm[i - 60:i]                # dış katman önbelleksiz
    assert '@st.cache_data(ttl=300, show_spinner=False)\ndef _dashboard_ham():' in pm
    it = (KOK / "ithalat/database.py").read_text(encoding="utf-8")
    j = it.index("def get_ithalat_yolda_ozet():")
    govde = it[j:it.index("\n@st.cache_data", j)]
    assert "except Exception:\n        return {}" not in govde
    assert 'kaydet("ithalat.get_ithalat_yolda_ozet"' in govde and "        raise" in govde
