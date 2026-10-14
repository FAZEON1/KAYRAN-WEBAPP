# -*- coding: utf-8 -*-
"""Kalıcı oturum deposu (Ekim 2026, veritabani/33_oturumlar.sql).

Eskiden oturumlar yalnız sunucu belleğindeydi: Streamlit yeniden başlayınca herkes çıkış yapmış
oluyordu. Artık her oturum `oturumlar` tablosuna da yazılır (anahtarın SHA-256 özeti); bellekte
olmayan anahtar tablodan okunur. Tablo yoksa / okunamazsa davranış bugünkü gibi (yalnız bellek)."""
import hashlib
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shared.oturum as O  # noqa: E402


class _Sorgu:
    def __init__(self, db, tablo):
        self.db, self.tablo, self.suz, self.islem, self.veri = db, tablo, [], "select", None

    def select(self, *_a, **_k):
        return self

    def eq(self, k, v):
        self.suz.append(lambda r, k=k, v=v: r.get(k) == v)
        return self

    def lt(self, k, v):
        self.suz.append(lambda r, k=k, v=v: r.get(k) < v)
        return self

    def limit(self, _n):
        return self

    def upsert(self, veri, **_k):
        self.islem, self.veri = "upsert", dict(veri)
        return self

    def update(self, veri):
        self.islem, self.veri = "update", dict(veri)
        return self

    def delete(self):
        self.islem = "delete"
        return self

    def execute(self):
        if self.db.get("_hata"):
            raise Exception(self.db["_hata"])
        t = self.db.setdefault(self.tablo, [])
        uy = [r for r in t if all(f(r) for f in self.suz)]
        if self.islem == "upsert":
            t[:] = [r for r in t if r["tok_ozet"] != self.veri["tok_ozet"]] + [self.veri]
            uy = [self.veri]
        elif self.islem == "update":
            for r in uy:
                r.update(self.veri)
        elif self.islem == "delete":
            t[:] = [r for r in t if r not in uy]

        class _C:
            data = [dict(r) for r in uy]
        return _C()


class _SB:
    def __init__(self, db):
        self.db = db

    def table(self, t):
        return _Sorgu(self.db, t)


@pytest.fixture
def ortam(monkeypatch):
    bellek, db = {}, {}
    monkeypatch.setattr(O, "oturum_store", lambda: bellek)
    import shared.auth as A
    monkeypatch.setattr(A, "_get_supabase", lambda: _SB(db))
    if hasattr(O, "_durum"):
        monkeypatch.setitem(O._durum, "yok_ts", 0.0)
    return bellek, db


def _satirlar(db):
    return db.get("oturumlar", [])


def _yeniden_baslat(bellek):
    bellek.clear()                        # Streamlit yeniden başladı: bellek boş


def test_yeniden_baslatmada_oturum_surer(ortam):
    """Giriş → bellek silinir (yeniden başlatma) → aynı tarayıcı aynı anahtarla gelir → içeride.
    Eski: None (giriş ekranı)."""
    bellek, db = ortam
    tok = O.oturum_olustur("serdar", "imza1")
    _yeniden_baslat(bellek)
    assert O.oturum_dogrula(tok, "imza1") == "serdar"
    assert tok in bellek                  # tablodan okunan kayıt belleğe alınır (sonraki tıklama hızlı)


def test_tabloda_anahtarin_kendisi_degil_ozeti(ortam):
    _bellek, db = ortam
    tok = O.oturum_olustur("serdar", "imza1")
    assert len(_satirlar(db)) == 1, "oturum tabloya yazılmadı"
    satir = _satirlar(db)[0]
    assert satir["tok_ozet"] == hashlib.sha256(tok.encode()).hexdigest()
    assert tok not in str(db)
    assert satir["kullanici"] == "serdar" and satir["cihaz"] == "imza1"


def test_cikista_tablodan_da_silinir(ortam, monkeypatch):
    bellek, db = ortam
    tok = O.oturum_olustur("serdar", "imza1")
    monkeypatch.setattr(O.st, "query_params", {"t": tok}, raising=False)
    assert len(_satirlar(db)) == 1, "oturum tabloya yazılmadı"
    O.oturum_kapat()
    _yeniden_baslat(bellek)
    assert _satirlar(db) == []
    assert O.oturum_dogrula(tok, "imza1") is None


def test_baska_tarayicidan_gelen_anahtar_tablodan_da_yakilir(ortam):
    bellek, db = ortam
    tok = O.oturum_olustur("serdar", "imza1")
    assert len(_satirlar(db)) == 1, "oturum tabloya yazılmadı"
    _yeniden_baslat(bellek)
    assert O.oturum_dogrula(tok, "baska") is None
    assert _satirlar(db) == []


def test_suresi_dolan_tablodaki_oturum_gecersiz(ortam):
    bellek, db = ortam
    tok = O.oturum_olustur("serdar", "imza1")
    assert len(_satirlar(db)) == 1, "oturum tabloya yazılmadı"
    _satirlar(db)[0]["ts"] = time.time() - 8 * 86400
    _yeniden_baslat(bellek)
    assert O.oturum_dogrula(tok, "imza1") is None


def test_kaydirma_saatte_bir_tabloya_yazilir(ortam):
    """Her tıklamada tabloya yazılmaz: 10 dk sonra kullanım → tablo aynı; 2 saat sonra → güncellenir."""
    bellek, db = ortam
    t0 = time.time()
    tok = O.oturum_olustur("serdar", "imza1")
    assert len(_satirlar(db)) == 1, "oturum tabloya yazılmadı"
    ilk = _satirlar(db)[0]["ts"]
    assert O.oturum_dogrula(tok, "imza1", simdi=t0 + 600) == "serdar"
    assert _satirlar(db)[0]["ts"] == ilk
    assert O.oturum_dogrula(tok, "imza1", simdi=t0 + 7200) == "serdar"
    assert _satirlar(db)[0]["ts"] == pytest.approx(t0 + 7200)


def test_kullanicinin_tum_oturumlari_silinir(ortam):
    _bellek, db = ortam
    O.oturum_olustur("serdar", "a")
    O.oturum_olustur("serdar", "b")
    O.oturum_olustur("derya", "c")
    assert len(_satirlar(db)) == 3, "oturumlar tabloya yazılmadı"
    getattr(O, "kullanici_oturumlarini_sil", lambda _k: None)("serdar")
    assert [r["kullanici"] for r in _satirlar(db)] == ["derya"]


def test_tablo_yoksa_bugunku_gibi_yalniz_bellek(ortam):
    """Tablo kurulmamış: giriş çalışır (bellek), hata fırlamaz; yeniden başlatmada düşer (eski davranış)."""
    bellek, db = ortam
    db["_hata"] = 'relation "public.oturumlar" does not exist (42P01)'
    tok = O.oturum_olustur("serdar", "imza1")
    assert O.oturum_dogrula(tok, "imza1") == "serdar"
    _yeniden_baslat(bellek)
    assert O.oturum_dogrula(tok, "imza1") is None
