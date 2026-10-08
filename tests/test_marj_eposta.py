# -*- coding: utf-8 -*-
"""Zararına satış uyarısı e-postası (Ekim 2026): Telegram'a ek olarak İbrahim, Korkut ve Serkan'a e-posta.
Yalnız zararına kalem varsa gider; Telegram kapalı olsa da gider; e-posta hatası kaydı bozmaz."""
import shared.eposta as E
import shared.marj_uyari as M
import shared.telegram_gonder as T

ZARARLI = {"sku": "MON-27", "adet": 2, "birim_satis": 100, "birim_maliyet": 120}
KARLI = {"sku": "KLV-1", "adet": 1, "birim_satis": 50, "birim_maliyet": 30}
MALIYETSIZ = {"sku": "YENI-1", "adet": 1, "birim_satis": 50, "birim_maliyet": 0}
ADRES = {"ibrahim": "ibrahim@g5f.com", "korkut": "korkut@g5f.com", "serkan": "serkan@g5f.com",
         "derya": "derya@g5f.com"}


def _kur(monkeypatch, telegram=True, adres=ADRES):
    giden, tg = [], []
    monkeypatch.setattr(E, "adresler", lambda: dict(adres))
    monkeypatch.setattr(E, "arka_planda", lambda alicilar, konu, html, cc=None: giden.append((alicilar, konu, html)))
    monkeypatch.setattr(T, "aktif_mi", lambda: telegram)
    monkeypatch.setattr(T, "gonder", lambda metin, **k: tg.append(metin) or (True, "ok"))
    return giden, tg


def test_alicilar():
    assert M.MAIL_ALICILARI == ("ibrahim", "korkut", "serkan")


def test_zararli_satista_mail_ve_telegram(monkeypatch):
    giden, tg = _kur(monkeypatch)
    M.marj_uyarisi([ZARARLI, KARLI, MALIYETSIZ], kanal="EERA", siparis_no="S-77", tarih="2026-10-08",
                   kullanici="derya", kaynak="Satış Girişi", esik=0)
    assert len(giden) == 1 and len(tg) == 1
    alicilar, konu, html = giden[0]
    assert alicilar == ["ibrahim@g5f.com", "korkut@g5f.com", "serkan@g5f.com"]       # derya'ya gitmez
    assert konu == "[KAYRAN] Zararına satış · EERA · S-77"
    for p in ("MON-27", "-40,00", "Toplam etki: -40,00 $", "EERA", "S-77", "derya", "YENI-1", "Zararına satış: 1 kalem"):
        assert p in html, p
    assert "KLV-1" not in html


def test_telegram_kapaliyken_de_mail(monkeypatch):
    giden, tg = _kur(monkeypatch, telegram=False)
    ok, _ = M.marj_uyarisi([ZARARLI], kanal="EERA", esik=0)
    assert not ok and len(giden) == 1 and tg == []


def test_yalniz_maliyetsizde_mail_gitmez(monkeypatch):
    giden, tg = _kur(monkeypatch)
    M.marj_uyarisi([MALIYETSIZ, KARLI], kanal="EERA", esik=0)
    assert giden == [] and len(tg) == 1                       # Telegram eskisi gibi uyarır


def test_adres_yoksa_ve_hata_kaydi_bozmaz(monkeypatch):
    giden, tg = _kur(monkeypatch, adres={})
    M.marj_uyarisi([ZARARLI], esik=0)
    assert giden == [] and len(tg) == 1
    _kur(monkeypatch)
    monkeypatch.setattr(E, "arka_planda", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("smtp")))
    ok, _ = M.marj_uyarisi([ZARARLI], esik=0)
    assert ok                                                 # e-posta patlasa da Telegram gider
