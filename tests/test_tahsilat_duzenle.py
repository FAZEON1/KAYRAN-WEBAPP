# -*- coding: utf-8 -*-
"""Muhasebe › Gelenler Geçmişi: para girişini silmeden düzenleme (Ekim 2026).

Eskiden yalnız "Geri al" vardı (kaydı siler, tutarı bakiyeden düşer); yanlış girilen bir tahsilat
silinip yeniden girilmek zorundaydı. Artık tutar, banka, kimden, açıklama ve tarih düzeltilir;
tutar ya da banka değişirse banka bakiyeleri FARKLA düzelir.
"""
from pathlib import Path

import kayranacc.database as D

KOK = Path(__file__).resolve().parent.parent


class _Sorgu:
    def __init__(self, db, tablo):
        self.db, self.tablo, self.filtre, self.yeni = db, tablo, None, None

    def select(self, *_a):
        return self

    def update(self, yeni):
        self.yeni = yeni
        return self

    def eq(self, k, v):
        self.filtre = (k, v)
        return self

    def execute(self):
        k, v = self.filtre
        satirlar = [r for r in self.db.t[self.tablo] if r.get(k) == v]
        if self.yeni is not None:
            if self.tablo == "bankalar" and self.db.bakiye_patlasin:
                raise RuntimeError("bağlantı koptu")
            for r in satirlar:
                r.update(self.yeni)
        return type("R", (), {"data": [dict(r) for r in satirlar]})()


class _DB:
    def __init__(self):
        self.bakiye_patlasin = False
        self.t = {"bankalar": [{"id": 1, "hesap_adi": "Ziraat TL", "para_birimi": "TL", "bakiye": 1000.0},
                               {"id": 2, "hesap_adi": "Garanti TL", "para_birimi": "TL", "bakiye": 500.0}],
                  "tahsilatlar": [{"id": 9, "banka_id": 1, "hesap_adi": "Ziraat TL", "para_birimi": "TL",
                                   "tutar": 300.0, "kaynak": "ABC", "aciklama": "", "tarih": "2026-10-01"}]}

    def table(self, ad):
        return _Sorgu(self, ad)

    def bakiye(self, bid):
        return next(b["bakiye"] for b in self.t["bankalar"] if b["id"] == bid)


def _kur(monkeypatch):
    db = _DB()
    monkeypatch.setattr(D, "get_client", lambda: db)
    monkeypatch.setattr(D, "_cache_temizle", lambda: None)
    return db


def test_bakiye_farki():
    assert D.tahsilat_bakiye_farki(1, 300, 1, 350) == {1: 50.0}
    assert D.tahsilat_bakiye_farki(1, 300, 1, 300) == {}
    assert D.tahsilat_bakiye_farki(1, 300, 2, 280) == {1: -300.0, 2: 280.0}


def test_ayni_bankada_tutar_duzeltilir(monkeypatch):
    db = _kur(monkeypatch)
    ok, _ = D.tahsilat_guncelle(9, 1, 350, "ABC Ltd.", "Eylül hakediş", "2026-10-02")
    t = db.t["tahsilatlar"][0]
    assert ok and t["tutar"] == 350 and t["kaynak"] == "ABC Ltd." and t["tarih"] == "2026-10-02"
    assert db.bakiye(1) == 1050.0 and db.bakiye(2) == 500.0


def test_banka_degisince_iki_bakiye_duzelir(monkeypatch):
    db = _kur(monkeypatch)
    ok, _ = D.tahsilat_guncelle(9, 2, 300, "ABC", "", "2026-10-01")
    t = db.t["tahsilatlar"][0]
    assert ok and t["banka_id"] == 2 and t["hesap_adi"] == "Garanti TL"
    assert db.bakiye(1) == 700.0 and db.bakiye(2) == 800.0


def test_bakiye_yazilamazsa_kayit_eski_haline_doner(monkeypatch):
    db = _kur(monkeypatch)
    db.bakiye_patlasin = True
    ok, msg = D.tahsilat_guncelle(9, 1, 999, "X", "", "2026-10-05")
    t = db.t["tahsilatlar"][0]
    assert not ok and "geri alındı" in msg
    assert t["tutar"] == 300.0 and t["kaynak"] == "ABC" and db.bakiye(1) == 1000.0


def test_sifir_tutar_reddedilir(monkeypatch):
    _kur(monkeypatch)
    assert D.tahsilat_guncelle(9, 1, 0)[0] is False


def test_ekranda_duzenle_var():
    s = (KOK / "kayranacc/gelen_ekran.py").read_text(encoding="utf-8")
    assert 'st.expander("Düzenle"' in s and "tahsilat_guncelle(tid, bid, tutar" in s
