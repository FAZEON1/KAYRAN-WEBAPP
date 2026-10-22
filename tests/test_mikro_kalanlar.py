# -*- coding: utf-8 -*-
"""Mikro sonrası kalanlar (kullanıcı 22.10.2026: "1- ürün kartlarını bağla, fiyat listesi Mikro'da da yok zaten.
2- yapalım. 7- ok").

1) Ürün kartları varsayılan açık; fiyat listesi okunmaz / yazılmaz; Mikro'nun harfsiz grup adı ('MONITOR')
   uygulamadaki yazıma ('monitör') bağlanır. Canlı fark: 3 yeni kart, 10 boş alan.
2) Yıl sonu: canlı 2025 sonu — bilanço kapanışı tür 4 (31.12, 111 satır, 130.629.641 TL), açılışı tür 3 (01.01.2026,
   aynı tutar); gelir / gider kapanışı normal mahsup (600 borç 463 M → 690, 760 alacak 44 M → 761). Aktarıcı 69x /
   7x1 hesaplı fişleri tür 9 verir; kayranacc/mikro_yil_sonu ayıklar. 01.01.2025 açılışı (önünde kapanış yok) kalır.
7) Aktarıcı çalışırken geride kalan tablo için ayrı uyarı (tablo adı ve süre)."""
from datetime import datetime, timedelta, timezone

import pytest

from kayranpm import mikro_urun as MU


# ── 1) Ürün kartları ──────────────────────────────────────────────
def test_urun_kartlari_varsayilan_acik(monkeypatch):
    for d, beklenen in (({}, True), ({"acik": True}, True), ({"acik": False}, False)):
        monkeypatch.setattr(MU, "durum", lambda d=d: d)
        assert MU.acik_mi() is beklenen, d


def test_fiyat_listesi_kapali_okunmaz(monkeypatch):
    okunan = []

    class _Q:
        def __init__(self, t):
            self.t = t

        def select(self, *_):
            return self

        def order(self, *_a, **_k):
            return self

        def range(self, *_):
            return self

        def execute(self):
            okunan.append(self.t)
            return type("R", (), {"data": []})()

    monkeypatch.setattr(MU, "_cli", lambda: type("C", (), {"table": lambda s, t: _Q(t)})())
    v = MU.veri_oku()
    assert MU.FIYAT_LISTESI is False
    assert v["fiyat"] == [] and v["liste"] == []
    assert not {"mikro_satis_fiyat", "mikro_fiyat_liste", "mikro_cari_kart"} & set(okunan)


@pytest.mark.parametrize("mikro,beklenen", [("MONITOR", "monitör"), ("MONİTÖR", "monitör"), ("KASA", "kasa"),
                                            ("EKRAN KARTI", "ekran kartı"), ("SOGUTUCU", "sogutucu")])
def test_mikro_harfsiz_grup_adi_uygulama_yazimina_baglanir(mikro, beklenen):
    mevcut = ["kasa", "monitör", "ekran kartı", "cpu soğutucu"]
    assert MU.kategori_yazimi(mikro, mevcut) == beklenen


# ── 2) Yıl sonu kapanış / açılış ──────────────────────────────────
try:
    from kayranacc import mikro_yil_sonu as YS
except ImportError:          # eski kodda yok: ayıklama testleri atlanır; tüketici / gider / aktarıcı testleri kırmızı
    YS = None
_YS = pytest.mark.skipif(YS is None, reason="kayranacc.mikro_yil_sonu yok")


def _r(yil, ay, kod, tur, borc=0.0, alacak=0.0):
    return {"yil": yil, "ay": ay, "hesap_kod": kod, "fis_tur": tur, "borc": borc, "alacak": alacak}


SATIR = [_r(2025, 1, "361.01.001", 3, 0, 500),                  # 2024'ten devir: kalır
         _r(2025, 11, "361.01.001", 0, 0, 600_000), _r(2025, 12, "361.01.001", 0, 600_000, 590_000),
         _r(2025, 12, "361.01.001", 4, 590_500, 0),             # kapanış: bakiyeyi sıfırlar
         _r(2026, 1, "361.01.001", 3, 0, 590_500),              # açılış
         _r(2025, 12, "760.03.005", 0, 10_000, 0), _r(2025, 12, "760.03.005", 9, 0, 120_000),   # yansıtma
         _r(2025, 12, "602.02.001", 0, 0, 40_000), _r(2025, 12, "602.02.001", 9, 480_000, 0)]   # 690'a kapanış


@_YS
def test_ayikla_kapanis_ve_eslesen_acilis():
    a = YS.ayikla(SATIR)
    turler = {(r["yil"], r["ay"], r["fis_tur"]) for r in a}
    assert (2025, 1, 3) in turler                                # ilk açılış kalır
    assert not {(2025, 12, 4), (2026, 1, 3), (2025, 12, 9)} & turler
    t = {(r["yil"], r["ay"], r["hesap_kod"]): r for r in YS.topla(a)}
    assert t[(2025, 12, "760.03.005")]["borc"] == 10_000 and t[(2025, 12, "760.03.005")]["alacak"] == 0
    assert t[(2025, 12, "602.02.001")]["alacak"] == 40_000 and t[(2025, 12, "602.02.001")]["borc"] == 0


@_YS
def test_kapanis_yapilip_acilis_girilmemisken_bakiye_kaybolmaz():
    """Ocak başı: kapanış (31.12) girildi, açılış henüz yok → Aralık SGK'sı (590.000) ödeme listesinde kalmalı;
    eskiden kapanış dahil toplamda bakiye 0, satır yoktu."""
    from kayranacc.mikro_odeme import donem_borclari
    gun, son = datetime(2026, 1, 5).date(), datetime(2026, 2, 28).date()
    ocak_basi = [r for r in SATIR if (r["yil"], r["fis_tur"]) != (2026, 3)]
    for veri in (ocak_basi, SATIR):
        d = {x["anahtar"]: x for x in donem_borclari(YS.topla(YS.ayikla(veri)), gun, son)}
        assert d["d|sgk|2025-12"]["tl"] == pytest.approx(590_000)
    assert not [x for x in donem_borclari(YS.topla(ocak_basi), gun, son) if x["anahtar"].startswith("d|sgk")]


@_YS
def test_alinan_destek_aralik_kapanissiz():
    from kayranacc import mikro_alinan as MA
    a = MA.aylik(YS.topla(YS.ayikla(SATIR)))
    assert a == {}                                               # 2026'dan önce alınmaz (ILK_AY)
    a = MA.aylik(YS.topla(YS.ayikla([dict(r, yil=r["yil"] + 1) for r in SATIR if r["hesap_kod"].startswith("602")])))
    assert a == {"2026-12": {"602.02.001": 40_000.0}}            # eskiden 40.000 − 480.000 = −440.000


@_YS
def test_oku_fis_turlu_yoksa_eski_tablo(monkeypatch):
    import satis.mikro_esitle as SE
    calls = []

    def sahte(sorgu, anahtar):
        calls.append(anahtar)
        return [] if "fis_tur" in anahtar else [{"yil": 2026, "ay": 1, "hesap_kod": "602", "borc": 0, "alacak": 5}]
    monkeypatch.setattr(SE, "sayfali_oku", sahte)
    satir, turlu = YS.oku(object(), ("602",))
    assert not turlu and satir[0]["alacak"] == 5 and len(calls) == 2


def test_tuketiciler_ortak_okuyucuyu_kullanir():
    from pathlib import Path
    kok = Path(__file__).resolve().parent.parent
    for dosya in ("kayranacc/mikro_alinan.py", "kayranacc/mikro_aktif.py", "kayranacc/mikro_odeme_oto.py"):
        s = (kok / dosya).read_text(encoding="utf-8")
        assert "mikro_yil_sonu import oku" in s, dosya
        assert 'table("mikro_muhasebe_ay")' not in s and '"mikro_muhasebe_ay", "yil' not in s, dosya
    from kayranacc import mikro_gider as G
    assert set(G.KAPANIS_TURLERI) == {4, 9}                      # bilanço kapanışı + yıl sonu mahsubu


# ── 7) Tablo bazlı uyarı ──────────────────────────────────────────
def test_geride_kalan_tablo_uyarisi():
    from shared import mikro_saglik as MS
    simdi = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    taze = (simdi - timedelta(minutes=5)).isoformat()
    senk = [{"tablo": "mikro_satis_satir", "son_cekim": taze, "guncelleme": taze},
            {"tablo": "mikro_cari_hareket", "son_cekim": (simdi - timedelta(hours=3)).isoformat(), "guncelleme": taze},
            {"tablo": "mikro_stok_kart", "son_cekim": (simdi - timedelta(minutes=60)).isoformat(), "guncelleme": taze}]
    s = [x for x in MS.sorunlar(senk, None, None, simdi) if x["kod"].startswith("tablo_geride")]
    assert len(s) == 1 and s[0]["kod"] == "tablo_geride:mikro_cari_hareket"
    assert "cari hareketler (3 sa" in s[0]["metin"] and "ürün kartları" not in s[0]["metin"]
    hepsi_taze = [dict(r, son_cekim=taze) for r in senk]
    assert not [x for x in MS.sorunlar(hepsi_taze, None, None, simdi) if x["kod"].startswith("tablo_geride")]
