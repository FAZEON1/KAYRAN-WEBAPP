# -*- coding: utf-8 -*-
"""Ref No firması silinirken bağlı ref kayıtları sayılır (Eki 2026).
Eskiden sayım canlıda olmayan "ref_no" tablosuna gidiyordu; hata yutulup 0 dönünce firma uyarısız
siliniyor, ref_kayitlari_firma_id_fkey ON DELETE CASCADE bağlı ref kayıtlarını da götürüyordu."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class _Sorgu:
    def __init__(self, db, tablo):
        self.db, self.tablo, self.suz, self.sil = db, tablo, {}, False

    def select(self, *_a, **_k):
        return self

    def eq(self, k, v):
        self.suz[k] = v
        return self

    def delete(self):
        self.sil = True
        return self

    def execute(self):
        if self.tablo not in self.db:
            raise Exception(f'relation "public.{self.tablo}" does not exist')
        satir = [r for r in self.db[self.tablo] if all(r.get(k) == v for k, v in self.suz.items())]
        if self.sil:
            self.db[self.tablo] = [r for r in self.db[self.tablo] if r not in satir]
            if self.tablo == "ref_firmalar":          # canlıdaki ON DELETE CASCADE
                ids = {r["id"] for r in satir}
                self.db["ref_kayitlari"] = [r for r in self.db["ref_kayitlari"] if r["firma_id"] not in ids]

        class _C:
            data = satir
        return _C()


class _SB:
    def __init__(self, db):
        self.db = db

    def table(self, t):
        return _Sorgu(self.db, t)


def _hazirla(monkeypatch):
    from kayranpm import ref_no as R
    db = {"ref_firmalar": [{"id": 7, "firma_adi": "VATAN"}],
          "ref_kayitlari": [{"id": 1, "firma_id": 7, "ref_no": "V-1"}, {"id": 2, "firma_id": 7, "ref_no": "V-2"}]}
    monkeypatch.setattr(R, "get_client", lambda: _SB(db))
    monkeypatch.setattr(R, "_cache_temizle", lambda: None)
    return R, db


def test_ref_sayisi_ref_kayitlarindan(monkeypatch):
    R, _db = _hazirla(monkeypatch)
    assert R.firma_ref_sayisi(7) == 2


def test_bagli_ref_varken_firma_silinmez(monkeypatch):
    R, db = _hazirla(monkeypatch)
    ok, _mesaj = R.firma_sil(7)
    assert ok is False
    assert len(db["ref_firmalar"]) == 1 and len(db["ref_kayitlari"]) == 2


def test_onayla_refler_de_silinir(monkeypatch):
    R, db = _hazirla(monkeypatch)
    ok, _mesaj = R.firma_sil(7, refleri_de_sil=True)
    assert ok is True
    assert db["ref_firmalar"] == [] and db["ref_kayitlari"] == []
