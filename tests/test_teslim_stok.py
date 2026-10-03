# -*- coding: utf-8 -*-
"""İthalat teslim ⇄ depo stoğu: işlenme kaydı (stok_islendi), Ekim 2026.

Canlıda ithalat_dosyalari.stok_islendi sütunu HİÇ yoktu (kod "sütun yoksa sessiz devam" ediyordu):
  • bekleyen listesi 'Teslim Alındı' 129 dosyanın HEPSİNİ "stoğa işlenmemiş" sayıyordu
    (teslim_stok_isle çalıştırılsaydı 235.643 adet ikinci kez girecekti);
  • 'Teslim Alındı'dan geri alınan dosyanın stoğu düşülmüyor, yeniden teslimde İKİNCİ kez giriyordu;
  • teslim alınmış dosyada adet düzeltmesi stoğa yansımıyordu.
veritabani/17_stok_islendi.sql sütunu ekler. Kayıt: True = stok depoda (uygulamaya göre),
False = işlenmedi / geri çekildi, boş = bilinmiyor (kayıttan önceki dosya; dokunulmaz).
"""
from pathlib import Path

import pytest

import ithalat.database as I
import kayranpm.database as P

KOK = Path(__file__).resolve().parent.parent


class _Sonuc:
    def __init__(self, data):
        self.data = data


class _Sorgu:
    def __init__(self, db, tablo):
        self.db, self.tablo, self.suz, self.islem, self.veri = db, tablo, [], "select", None

    def select(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def range(self, *a, **k):
        return self

    def eq(self, s, v):
        self.suz.append((s, v))
        return self

    def update(self, p):
        self.islem, self.veri = "update", dict(p)
        return self

    def delete(self):
        self.islem = "delete"
        return self

    def insert(self, rows):
        self.islem, self.veri = "insert", rows if isinstance(rows, list) else [rows]
        return self

    def _uyar(self, r):
        return all(str(r.get(s)) == str(v) for s, v in self.suz)

    def execute(self):
        t = self.db.tablolar.setdefault(self.tablo, [])
        if self.islem == "update":
            for r in t:
                if self._uyar(r):
                    for k, v in self.veri.items():
                        if k not in r and self.db.kolonsuz and k == "stok_islendi":
                            raise Exception('column "stok_islendi" does not exist')
                        r[k] = v
            return _Sonuc([])
        if self.islem == "delete":
            self.db.tablolar[self.tablo] = [r for r in t if not self._uyar(r)]
            return _Sonuc([])
        if self.islem == "insert":
            for r in self.veri:
                t.append(dict(r, id=len(t) + 1000))
            return _Sonuc(self.veri)
        return _Sonuc([dict(r) for r in t if self._uyar(r)])


class _Db:
    def __init__(self, dosyalar, kalemler, kolonsuz=False):
        self.kolonsuz = kolonsuz
        self.tablolar = {"ithalat_dosyalari": [dict(d) for d in dosyalar],
                         "ithalat_kalemleri": [dict(k) for k in kalemler]}

    def table(self, ad):
        return _Sorgu(self, ad)

    def dosya(self, i):
        return next(d for d in self.tablolar["ithalat_dosyalari"] if d["id"] == i)


@pytest.fixture
def ortam(monkeypatch):
    hareket = []

    def kur(dosyalar, kalemler, kolonsuz=False):
        db = _Db(dosyalar, kalemler, kolonsuz)
        monkeypatch.setattr(I, "_get_client", lambda: db)
        monkeypatch.setattr(I, "_temizle", lambda: None)
        monkeypatch.setattr(I, "_yukleme_bildir", lambda *a, **k: None)
        monkeypatch.setattr(I, "_aktif_yukleme", lambda: None)
        monkeypatch.setattr(I, "get_dosyalar", lambda: [dict(d) for d in db.tablolar["ithalat_dosyalari"]])
        monkeypatch.setattr(I, "get_tum_kalemler", lambda: [dict(k) for k in db.tablolar["ithalat_kalemleri"]])
        monkeypatch.setattr(I, "get_kalemler",
                            lambda i: [dict(k) for k in db.tablolar["ithalat_kalemleri"] if k["dosya_id"] == i])

        def _hareket(h, depo=None, **k):
            hareket.append((dict(h), depo))
            return len(h), []
        monkeypatch.setattr(P, "stok_hareket_coklu", _hareket)
        for f in ("teslim_stok_bekleyenler",):
            g = getattr(I, f)
            if hasattr(g, "clear"):
                g.clear()
        return db
    kur.hareket = hareket
    return kur


def _stok(hareket):
    top = {}
    for h, _d in hareket:
        for s, a in h.items():
            top[s] = top.get(s, 0) + a
    return {s: a for s, a in top.items() if a}


KAL = [{"dosya_id": 1, "sku": "A", "adet": 10}, {"dosya_id": 1, "sku": "B", "adet": 5},
       {"dosya_id": 2, "sku": "C", "adet": 7}, {"dosya_id": 3, "sku": "D", "adet": 4},
       {"dosya_id": 4, "sku": "E", "adet": 3}]


# ── Bekleyen listesi: yalnız işlenmediği BİLİNEN dosyalar ───────────
def test_kayitsiz_dosyalar_bekleyen_sayilmaz(ortam):
    """Canlıdaki durum: sütun yok → eskiden 129 dosyanın hepsi 'bekleyen' çıkıyordu."""
    ortam([{"id": 1, "dosya_no": "D1", "durum": "Teslim Alındı", "teslim_deposu": "MERKEZ DEPO"},
           {"id": 2, "dosya_no": "D2", "durum": "Teslim Alındı", "teslim_deposu": "MERKEZ DEPO"}], KAL)
    assert I.teslim_stok_bekleyenler() == []
    assert [d["dosya_no"] for d in I.teslim_stok_kayitsiz()] == ["D1", "D2"]


def test_bekleyen_yalniz_islenmedi_kayitli(ortam):
    ortam([{"id": 1, "dosya_no": "D1", "durum": "Teslim Alındı", "teslim_deposu": "MERKEZ DEPO", "stok_islendi": True},
           {"id": 2, "dosya_no": "D2", "durum": "Teslim Alındı", "teslim_deposu": "MERKEZ DEPO", "stok_islendi": False},
           {"id": 3, "dosya_no": "D3", "durum": "Teslim Alındı", "teslim_deposu": "", "stok_islendi": None},
           {"id": 4, "dosya_no": "D4", "durum": "Antrepoda", "teslim_deposu": "", "stok_islendi": False}], KAL)
    assert [(d["dosya_no"], d["toplam_adet"]) for d in I.teslim_stok_bekleyenler()] == [("D2", 7)]
    assert [d["dosya_no"] for d in I.teslim_stok_kayitsiz()] == ["D3"]


def test_isle_kayitsiz_dosyayi_ikinci_kez_islemez(ortam):
    ortam([{"id": 1, "dosya_no": "D1", "durum": "Teslim Alındı", "teslim_deposu": "MERKEZ DEPO"}], KAL)
    assert I.teslim_stok_isle() == (0, 0, [])
    assert ortam.hareket == []


# ── Geçişler: geri alma düşer, yeniden teslim çift girmez ───────────
def test_geri_alma_stogu_duser_yeniden_teslim_tek_giris(ortam):
    db = ortam([{"id": 1, "dosya_no": "D1", "durum": "Antrepoda", "teslim_deposu": "MERKEZ DEPO",
                 "stok_islendi": None}], KAL)
    I.set_dosya_durum(1, "Teslim Alındı")
    assert _stok(ortam.hareket) == {"A": 10, "B": 5} and db.dosya(1)["stok_islendi"] is True
    I.set_dosya_durum(1, "Antrepoda")
    assert _stok(ortam.hareket) == {} and db.dosya(1)["stok_islendi"] is False
    I.set_dosya_durum(1, "Teslim Alındı")
    assert _stok(ortam.hareket) == {"A": 10, "B": 5}


def test_kayitsiz_eski_dosya_geri_alinip_yeniden_teslimde_cift_girmez(ortam):
    """Kayıttan önce teslim alınmış dosya: geri almada stoğa DOKUNULMAZ (nasıl girdiği bilinmiyor),
    'stok depoda' diye işaretlenir → yeniden teslimde ikinci kez EKLENMEZ."""
    db = ortam([{"id": 1, "dosya_no": "D1", "durum": "Teslim Alındı", "teslim_deposu": "MERKEZ DEPO",
                 "stok_islendi": None}], KAL)
    I.set_dosya_durum(1, "Antrepoda")
    assert ortam.hareket == [] and db.dosya(1)["stok_islendi"] is True
    I.set_dosya_durum(1, "Teslim Alındı")
    assert _stok(ortam.hareket) == {}


def test_sutun_yokken_bugunku_gibi_sessiz(ortam):
    """SQL 17 kurulmadan: yazma sütun hatası verir, yutulur; uygulama çökmez."""
    db = ortam([{"id": 1, "dosya_no": "D1", "durum": "Antrepoda", "teslim_deposu": "MERKEZ DEPO"}], KAL,
               kolonsuz=True)
    assert I.set_dosya_durum(1, "Teslim Alındı") is True
    assert _stok(ortam.hareket) == {"A": 10, "B": 5} and "stok_islendi" not in db.dosya(1)


def _guncelle(durum, kalemler, depo="MERKEZ DEPO"):
    return I.guncelle_dosya(1, "D1", "", "2026-01-01", "", "", "USD", 1, {}, "", kalemler,
                            durum=durum, teslim_deposu=depo)


def test_teslimli_dosyada_adet_duzeltmesi_stoga_yansir(ortam):
    db = ortam([{"id": 1, "dosya_no": "D1", "durum": "Teslim Alındı", "teslim_deposu": "MERKEZ DEPO",
                 "stok_islendi": True}], KAL)
    ok, _m = _guncelle("Teslim Alındı", [{"sku": "A", "adet": 12}, {"sku": "B", "adet": 5}])
    assert ok and _stok(ortam.hareket) == {"A": 2}
    ok, _m = _guncelle("Antrepoda", [{"sku": "A", "adet": 12}, {"sku": "B", "adet": 5}])
    assert ok and _stok(ortam.hareket) == {"A": -10, "B": -5} and db.dosya(1)["stok_islendi"] is False


def test_guncelle_kayitsiz_dosya_geri_alinip_yeniden_teslimde_cift_girmez(ortam):
    db = ortam([{"id": 1, "dosya_no": "D1", "durum": "Teslim Alındı", "teslim_deposu": "MERKEZ DEPO",
                 "stok_islendi": None}], KAL)
    _guncelle("Antrepoda", [{"sku": "A", "adet": 10}, {"sku": "B", "adet": 5}])
    assert ortam.hareket == [] and db.dosya(1)["stok_islendi"] is True
    _guncelle("Teslim Alındı", [{"sku": "A", "adet": 11}, {"sku": "B", "adet": 5}])
    assert _stok(ortam.hareket) == {"A": 1}          # yalnız aradaki düzeltme


def test_sql_dosyasi():
    s = (KOK / "veritabani" / "17_stok_islendi.sql").read_text(encoding="utf-8").lower()
    assert "add column if not exists stok_islendi boolean" in s
    assert "update " not in s                        # mevcut kayıtlara dokunulmaz
