# -*- coding: utf-8 -*-
"""shared.kayit.sessiz — yutulan hatalar günlüğe düşer, akış değişmez (Ekim 2026).

Eskiden ~170 yerde `except Exception: pass` vardı: para/stok yazımına yakın yerlerde hata
olduğunda hiçbir iz kalmıyordu. Artık sessiz(yer, hata) WARNING satırı yazar; ama:
  · kendisi ASLA fırlatmaz (çağıranın akışı bozulamaz),
  · aynı yer+tür süreç başına TEKRAR_SINIRI kez yazılır (log seli yok),
  · Sentry kurulu/ayarlı değilse hiçbir şey yapmaz,
  · çağıran fonksiyonların dönüş değerleri ESKİSİYLE AYNI (aşağıdaki kritik yer testleri).
"""
import logging
import sys
import types

import pytest

from shared import kayit as K


class _Toplayici(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.kayitlar = []

    def emit(self, record):
        self.kayitlar.append(record)

    def mesajlar(self, seviye=logging.WARNING):
        return [r.getMessage() for r in self.kayitlar if r.levelno >= seviye]


@pytest.fixture
def log(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.delenv("KAYRAN_LOG_DUZEYI", raising=False)
    K._sifirla()
    K.yapilandir()
    lg = logging.getLogger(K.KOK_LOGGER)
    h = _Toplayici()
    lg.addHandler(h)
    yield h
    lg.removeHandler(h)
    K._sifirla()
    lg.setLevel(logging.WARNING)


# ── sessiz(): asla fırlatmaz ───────────────────────────────────────
class _BozukHata(Exception):
    def __str__(self):
        raise RuntimeError("str de patladı")


@pytest.mark.parametrize("yer,hata", [
    ("a.b", ValueError("x")),
    ("a.b", _BozukHata()),
    (None, None),
    (123, "metin uyarı"),
    ("", object()),
])
def test_sessiz_asla_firlatmaz(log, yer, hata):
    assert K.sessiz(yer, hata) is None
    assert K.sessiz(yer, hata, "debug") is None
    assert K.sessiz(yer, hata, duzey="bilinmeyen-düzey") is None


def test_sessiz_logging_bozulsa_da_firlatmaz(log, monkeypatch):
    def _patla(*a, **k):
        raise RuntimeError("logging çöktü")
    sahte = types.SimpleNamespace(**{a: getattr(logging, a) for a in
                                     ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")},
                                  getLogger=_patla)
    monkeypatch.setattr(K, "logging", sahte)       # yalnız kayit modülünün gördüğü logging
    assert K.sessiz("x.y", ValueError("z")) is None


def test_sessiz_uyari_yazar_ve_yer_tur_mesaj_icerir(log):
    K.sessiz("ithalat.database.ornek", KeyError("SKU-1"))
    m = log.mesajlar()
    assert len(m) == 1
    assert "ithalat.database.ornek" in m[0] and "KeyError" in m[0] and "SKU-1" in m[0]
    assert log.kayitlar[0].name == "kayran.ithalat"
    assert log.kayitlar[0].levelno == logging.WARNING


def test_yigin_izi_yalniz_debugda(log, monkeypatch):
    try:
        raise ValueError("iz")
    except ValueError as e:
        K.sessiz("a.iz", e)
    assert not any(r.exc_info for r in log.kayitlar)          # WARNING düzeyinde iz yok
    K._sifirla()
    monkeypatch.setenv("KAYRAN_LOG_DUZEYI", "DEBUG")
    K.yapilandir()
    log.kayitlar.clear()
    try:
        raise ValueError("iz")
    except ValueError as e:
        K.sessiz("a.iz", e)
    assert any(r.exc_info and r.levelno == logging.DEBUG for r in log.kayitlar)


def test_debug_duzeyi_varsayilanda_yazilmaz_ve_sayilmaz(log):
    for _ in range(20):
        K.sessiz("teknikservis.main.oneri", ValueError("x"), "debug")
    assert log.kayitlar == []
    assert K._sayac == {}


# ── tekrar sınırı ──────────────────────────────────────────────────
def test_tekrar_siniri(log):
    for _ in range(50):
        K.sessiz("dongu.yer", ValueError("aynı"))
    assert len(log.mesajlar()) == K.TEKRAR_SINIRI
    assert "bastırılır" in log.mesajlar()[-1]
    for _ in range(50):                                         # 100. tekrarda tek özet satırı
        K.sessiz("dongu.yer", ValueError("aynı"))
    m = log.mesajlar()
    assert len(m) == K.TEKRAR_SINIRI + 1 and "100 kez" in m[-1]


def test_tekrar_siniri_yer_ve_ture_gore_ayri(log):
    for _ in range(10):
        K.sessiz("bir.yer", ValueError("a"))
        K.sessiz("bir.yer", KeyError("a"))
        K.sessiz("baska.yer", ValueError("a"))
    assert len(log.mesajlar()) == 3 * K.TEKRAR_SINIRI


def test_sayac_bellegi_sinirli(log, monkeypatch):
    monkeypatch.setattr(K, "_ANAHTAR_SINIRI", 10)
    for i in range(35):
        K.sessiz(f"yer.{i}", ValueError("a"))
    assert len(K._sayac) <= 10


# ── yapılandırma ───────────────────────────────────────────────────
def test_yapilandir_tek_sefer_ve_duzey_ortamdan(monkeypatch):
    K._sifirla()
    monkeypatch.setenv("KAYRAN_LOG_DUZEYI", "ERROR")
    for _ in range(3):
        K.yapilandir()
        K.baslat()
    lg = logging.getLogger(K.KOK_LOGGER)
    assert sum(1 for h in lg.handlers if getattr(h, "_kayran", False)) == 1
    assert lg.level == logging.ERROR
    K._sifirla()
    monkeypatch.delenv("KAYRAN_LOG_DUZEYI")
    K.yapilandir()
    assert lg.level == logging.WARNING
    K._sifirla()


# ── Sentry: isteğe bağlı, yoksa no-op ─────────────────────────────
def test_sentry_dsn_yoksa_hicbir_sey(log, monkeypatch):
    sahte = types.ModuleType("sentry_sdk")
    sahte.init = lambda **k: pytest.fail("DSN yokken init çağrılmamalı")
    monkeypatch.setitem(sys.modules, "sentry_sdk", sahte)
    assert K.sentry_baslat() is False
    assert K.sessiz("a.b", ValueError("x")) is None


def test_sentry_kurulu_degilse_hicbir_sey(log, monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://ornek@sentry.invalid/1")
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)     # import → ImportError
    assert K.sentry_baslat() is False
    assert K.sessiz("a.b", ValueError("x")) is None
    assert len(log.mesajlar()) == 1                          # log yine çalışır


def test_sentry_varsa_baslar_ve_hatayi_gonderir(log, monkeypatch):
    cagri = {"init": [], "yakala": []}

    class _Kapsam:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def set_tag(self, k, v):
            cagri.setdefault("etiket", []).append((k, v))

    sahte = types.ModuleType("sentry_sdk")
    sahte.init = lambda **k: cagri["init"].append(k)
    sahte.new_scope = lambda: _Kapsam()
    sahte.capture_exception = lambda e: cagri["yakala"].append(e)
    monkeypatch.setitem(sys.modules, "sentry_sdk", sahte)
    monkeypatch.setenv("SENTRY_DSN", "https://ornek@sentry.invalid/1")
    assert K.sentry_baslat() is True
    assert cagri["init"][0]["dsn"] == "https://ornek@sentry.invalid/1"
    assert cagri["init"][0]["send_default_pii"] is False
    for _ in range(20):
        K.sessiz("para.yer", ValueError("x"))
    K.sessiz("para.yer", ValueError("x"), "debug")
    assert len(cagri["yakala"]) == K.TEKRAR_SINIRI           # aynı tekrar sınırı
    assert ("yer", "para.yer") in cagri["etiket"]


def test_sentry_capture_patlasa_da_firlatmaz(log, monkeypatch):
    sahte = types.ModuleType("sentry_sdk")
    sahte.init = lambda **k: None
    sahte.push_scope = lambda: (_ for _ in ()).throw(RuntimeError("ağ yok"))
    monkeypatch.setitem(sys.modules, "sentry_sdk", sahte)
    monkeypatch.setenv("SENTRY_DSN", "https://ornek@sentry.invalid/1")
    assert K.sentry_baslat() is True
    assert K.sessiz("x.y", ValueError("z")) is None


# ═══════════════════════════════════════════════════════════════════
# Kritik yerler (para / stok yazımına yakın): hata loga düşer, sonuç AYNI
# ═══════════════════════════════════════════════════════════════════
class _Sonuc:
    def __init__(self, data):
        self.data = data


class _Sorgu:
    def __init__(self, db, tablo):
        self.db, self.tablo, self.islem, self.veri = db, tablo, "select", None

    def __getattr__(self, ad):                     # eq / order / limit / ... zincir
        return lambda *a, **k: self

    def select(self, *a, **k):
        return self

    def update(self, v):
        self.islem, self.veri = "update", v
        return self

    def insert(self, v):
        self.islem, self.veri = "insert", v
        return self

    def execute(self):
        return _Sonuc(self.db.cevap(self.tablo, self.islem, self.veri))


class _Db:
    def __init__(self, cevap):
        self.cevap = cevap
        self.yazilan = []

    def table(self, ad):
        return _Sorgu(self, ad)


def test_tahsilat_kaydi_yazilamazsa_loga_duser_sonuc_ayni(log, monkeypatch):
    import kayranacc.database as D

    def cevap(tablo, islem, veri):
        if tablo == "bankalar" and islem == "select":
            return [{"id": 7, "bakiye": 100.0, "para_birimi": "TL", "hesap_adi": "Ana"}]
        if tablo == "tahsilatlar" and islem == "insert":
            raise RuntimeError("tahsilatlar insert reddedildi")
        db.yazilan.append((tablo, islem, veri))
        return []
    db = _Db(cevap)
    monkeypatch.setattr(D, "get_client", lambda: db)
    monkeypatch.setattr(D, "_cache_temizle", lambda: None)
    monkeypatch.setattr(D, "_mikro_yonetir", lambda banka_id: False)   # Mikro eşitlemesi kapalı hesap
    ok, mesaj = D.tahsilat_ekle(7, 50, kaynak="müşteri", tarih="2026-10-14")
    assert ok is True and "tahsilat Ana hesabına eklendi" in mesaj      # eski davranış
    assert db.yazilan == [("bankalar", "update", {"bakiye": 150.0})]    # bakiye yine yazıldı
    m = log.mesajlar()
    assert len(m) == 1 and "kayranacc.database.tahsilat_ekle" in m[0] and "reddedildi" in m[0]


def test_odeme_banka_bakiyesi_dusulemezse_loga_duser(log, monkeypatch):
    import kayranacc.database as D

    def cevap(tablo, islem, veri):
        if tablo == "odemeler" and islem == "select":
            return [{"id": 3, "durum": "bekliyor", "tutar_tl": 10.0, "tutar_usd": 0}]
        if tablo == "bankalar" and islem == "select":
            raise ConnectionError("bankalar okunamadı")
        db.yazilan.append((tablo, islem, veri))
        return []
    db = _Db(cevap)
    monkeypatch.setattr(D, "get_client", lambda: db)
    monkeypatch.setattr(D, "_cache_temizle", lambda: None)
    assert D.odeme_durum_guncelle(3, "odendi", banka_id=9, kur=40) is None
    assert ("odemeler", "update", {"banka_id": 9}) in db.yazilan             # akış aynı
    m = log.mesajlar()
    assert len(m) == 1 and "odeme_durum_guncelle.banka" in m[0] and "ConnectionError" in m[0]


def test_teslim_kismi_geri_cekme_basarisizsa_loga_duser_sonuc_ayni(log, monkeypatch):
    import ithalat.database as I
    import kayranpm.database as P

    monkeypatch.setattr(I, "teslim_stok_bekleyenler",
                        lambda: [{"id": 1, "dosya_no": "IT-1", "teslim_deposu": "MERKEZ DEPO"}])
    monkeypatch.setattr(I, "get_kalemler", lambda i: [{"dosya_id": 1, "sku": "A", "adet": 4},
                                                      {"dosya_id": 1, "sku": "B", "adet": 2}])
    monkeypatch.setattr(I, "_get_client", lambda: _Db(lambda *a: []))

    def _temizle():
        raise RuntimeError("önbellek")
    monkeypatch.setattr(I, "_temizle", _temizle)
    cagri = []

    def _hareket(h, depo=None, **k):
        cagri.append(dict(h))
        if len(cagri) == 1:
            return 1, ["B"]                               # kısmi: B işlenemedi
        raise RuntimeError("geri çekme reddedildi")      # A geri çekilemedi
    monkeypatch.setattr(P, "stok_hareket_coklu", _hareket)

    islenen, eklenen, mesajlar = I.teslim_stok_isle()
    assert (islenen, eklenen) == (0, 0)
    assert len(mesajlar) == 1 and "IT-1" in mesajlar[0] and "İŞLENMEDİ" in mesajlar[0]
    m = log.mesajlar()
    assert any("teslim_stok_isle.geri_cekme" in x and "geri çekme reddedildi" in x for x in m)
    assert any("teslim_stok_isle.onbellek" in x for x in m)
