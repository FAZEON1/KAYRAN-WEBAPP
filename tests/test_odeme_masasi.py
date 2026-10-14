# -*- coding: utf-8 -*-
"""Ödeme masası (Ekim 2026, hibrit yol B — prototip https://claude.ai/artifact/QeMhUiHWNK1sYnAtsRjkzW).

Bu Hafta sayfası tek bir JS bileşenine taşındı: liste, yan detay paneli, toplu işlem. Bileşen yalnız İSTEK
gönderir ("şu ödemeyi şu bankadan öde"); doğrulama ve yürütme Python'da, mevcut veritabanı fonksiyonlarıyla.
Burada: ekrana giden veri (rakamlar odeme_hesap ile aynı), isteğin doğrulanması ve doğru fonksiyona gitmesi.
"""
import sys
from datetime import date
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from kayranacc import odeme_masasi as M  # noqa: E402
from kayranacc import odeme_hesap as H  # noqa: E402

BUGUN = date(2026, 10, 14)
KAT = {"cek": {"label": "Çek", "oncelik": 1}, "sgk": {"label": "SGK", "oncelik": 5},
       "cari": {"label": "Cari Hesap", "oncelik": 8}, "diger": {"label": "Diğer", "oncelik": 99}}
BANKA = [{"id": 1, "hesap_adi": "Garanti TL", "para_birimi": "TL", "bakiye": 1240000},
         {"id": 2, "hesap_adi": "Ziraat USD", "para_birimi": "USD", "bakiye": 186420.5}]


def _o(i, firma, vade, tl=0, usd=0, kat="cari", durum="bekliyor", **k):
    return dict(id=i, firma=firma, aciklama=f"{firma} açıklama", vade=vade, tutar_tl=tl, tutar_usd=usd,
                kategori=kat, durum=durum, **k)


ODM = [
    _o(1, "Örnek Lojistik", "2026-10-08", tl=185000, usd=4490.29),
    _o(2, "Çek ödemesi", "2026-10-11", tl=400000, kat="cek"),
    _o(3, "SGK", "2026-10-14", tl=212000, kat="sgk"),
    _o(4, "Kargo", "2026-10-14", tl=27300.5),
    _o(5, "Tedarikçi", "2026-10-16", usd=18400),
    _o(6, "Turkcell", "2026-10-12", tl=6120, durum="odendi", banka_id=1, odendi_tarih="2026-10-12"),
]


# ── Ekrana giden veri ────────────────────────────────────────────────
def test_ozet_rakamlari_odeme_hesap_ile_ayni():
    v = M.masa_verisi(ODM, BANKA, KAT, 38.5, BUGUN)
    oz = H.ozet(ODM, BANKA, 38.5, BUGUN)
    d = {k["k"]: k for k in v["ozet"]}
    assert d["bugun"]["dg"] == "2 ödeme" and d["bugun"]["suz"] == "bugun"
    assert d["gecikmis"]["dg"] == "2 ödeme" and d["gecikmis"]["renk"] == "kirmizi"
    assert d["kalan"]["dg"] == "₺824.301"                         # kartta kuruş yok (görünüm cilası)
    assert d["kalan"]["al"] == f"+ $22.890,29 · {oz['odendi_adet']}/{oz['adet']} ödendi"
    hs = oz["hafta_sonu_tl"]                                     # 1.240.000 − 824.300,5 − 22.890,29×38,5 = −465.576,67
    assert hs < 0 and d["hafta_sonu"]["et"] == "Nakit açığı" and d["hafta_sonu"]["renk"] == "kirmizi"
    assert d["hafta_sonu"]["dg"] == "₺465.577"


def test_odeme_satirlari_sirasi_durumu_ve_metni():
    v = M.masa_verisi(ODM, BANKA, KAT, 38.5, BUGUN)
    r = {o["id"]: o for o in v["odemeler"]}
    assert [o["id"] for o in v["odemeler"]] == [1, 2, 6, 3, 4, 5]          # vade sırası; gün içinde öncelik
    assert r[1]["durum"] == "gecikmis" and r[1]["fark"] == -6 and r[1]["vade_kisa"] == "08.10"
    assert r[1]["tl_m"] == "₺185.000,00" and r[1]["usd_m"] == "$4.490,29" and r[1]["kat_ad"] == "Cari Hesap"
    assert r[3]["durum"] == "bugun" and r[3]["gun"].startswith("Bugün · Çarşamba, 14 Ekim")
    assert r[6]["durum"] == "odendi" and r[6]["banka_ad"] == "Garanti TL"
    assert r[5]["tl_m"] == "" and r[5]["usd"] == 18400.0
    assert r[4]["tl_try"] == 27300.5 and r[5]["tl_try"] == 18400 * 38.5      # TL karşılığı (detay paneli)


def test_bankalar_ve_kategoriler():
    v = M.masa_verisi(ODM, BANKA, KAT, 38.5, BUGUN)
    assert v["bankalar"][0] == {"id": 1, "ad": "Garanti TL", "para": "TL", "bakiye_m": "₺1.240.000,00"}
    assert v["bankalar"][1]["bakiye_m"] == "$186.420,50"
    eur = M.masa_verisi(ODM, [{"id": 3, "hesap_adi": "Katılım EUR", "para_birimi": "EUR", "bakiye": 24300}], KAT, 38.5, BUGUN)
    assert eur["bankalar"][0]["bakiye_m"] == "€24.300,00"
    assert [k["k"] for k in v["kategoriler"]] == ["cek", "sgk", "cari", "diger"]
    assert v["kur_m"] == "38,5000" and v["bugun"] == "2026-10-14" and v["salt"] is False


def test_bos_liste_ve_bozuk_alanlar_cokmez():
    v = M.masa_verisi([_o(9, None, None, tl=None, usd="abc", kat=None)], [], KAT, 0, BUGUN)
    o = v["odemeler"][0]
    assert o["firma"] == "—" and o["durum"] == "tarihsiz" and o["fark"] is None and o["kat"] == "diger"
    assert M.masa_verisi([], [], KAT, 0, BUGUN)["odemeler"] == []


# ── İsteğin doğrulanması ─────────────────────────────────────────────
def _coz(istek, salt=False):
    return M.istek_coz(istek, ODM, BANKA, KAT, salt=salt)


@pytest.mark.parametrize("istek, beklenen", [
    ({"tur": "ode", "ids": [3], "banka": 1}, {"tur": "ode", "ids": [3], "banka": 1}),
    ({"tur": "ode", "ids": [3], "banka": "_bankasiz"}, {"tur": "ode", "ids": [3], "banka": None}),
    ({"tur": "ode", "ids": [1, 3, 4], "banka": 1}, {"tur": "ode", "ids": [1, 3, 4], "banka": 1}),
    ({"tur": "kismi", "ids": [1], "banka": 1, "tl": 100000, "usd": 0},
     {"tur": "kismi", "ids": [1], "banka": 1, "tl": 100000.0, "usd": 0.0}),
    ({"tur": "otele", "ids": [3], "gun": 7}, {"tur": "otele", "ids": [3], "vadeler": {3: date(2026, 10, 21)}}),
    ({"tur": "otele", "ids": [1, 2], "gun": 3},
     {"tur": "otele", "ids": [1, 2], "vadeler": {1: date(2026, 10, 11), 2: date(2026, 10, 14)}}),
    ({"tur": "otele", "ids": [3], "vade": "2026-10-30"}, {"tur": "otele", "ids": [3], "vadeler": {3: date(2026, 10, 30)}}),
    ({"tur": "duzenle", "ids": [4], "tl": 30000, "usd": 0, "kategori": "sgk", "aciklama": " yeni "},
     {"tur": "duzenle", "ids": [4], "tl": 30000.0, "usd": 0.0, "kategori": "sgk", "aciklama": "yeni"}),
    ({"tur": "sil", "ids": [4]}, {"tur": "sil", "ids": [4]}),
    ({"tur": "geri_al", "ids": [6]}, {"tur": "geri_al", "ids": [6]}),
])
def test_gecerli_istekler(istek, beklenen):
    t, hata = _coz(dict(istek, n=123))
    assert hata is None and t == beklenen


@pytest.mark.parametrize("istek, parca", [
    ({"tur": "uydur", "ids": [3]}, "Bilinmeyen"),
    ({"tur": "ode", "ids": [3]}, "banka"),                              # banka seçilmeden ödeme yok
    ({"tur": "ode", "ids": [3], "banka": 99}, "banka"),
    ({"tur": "ode", "ids": [77], "banka": 1}, "bulunamadı"),
    ({"tur": "ode", "ids": [], "banka": 1}, "seçilmedi"),
    ({"tur": "ode", "ids": [6], "banka": 1}, "zaten ödenmiş"),
    ({"tur": "ode", "ids": ["3; drop"], "banka": 1}, "bulunamadı"),
    ({"tur": "kismi", "ids": [1], "banka": 1, "tl": 185000.01, "usd": 0}, "en çok"),
    ({"tur": "kismi", "ids": [1], "banka": 1, "tl": 0, "usd": 0}, "tutar"),
    ({"tur": "kismi", "ids": [1, 2], "banka": 1, "tl": 1, "usd": 0}, "tek"),
    ({"tur": "otele", "ids": [3]}, "tarih"),
    ({"tur": "otele", "ids": [3], "vade": "2026-10-14"}, "aynı"),
    ({"tur": "otele", "ids": [3], "vade": "bozuk"}, "tarih"),
    ({"tur": "otele", "ids": [3], "gun": 0}, "tarih"),
    ({"tur": "otele", "ids": [3], "gun": 400}, "tarih"),
    ({"tur": "duzenle", "ids": [4], "tl": 0, "usd": 0, "kategori": "sgk", "aciklama": ""}, "tutar"),
    ({"tur": "duzenle", "ids": [4], "tl": -5, "usd": 10, "kategori": "sgk", "aciklama": ""}, "tutar"),
    ({"tur": "duzenle", "ids": [4], "tl": 5, "usd": 0, "kategori": "yok", "aciklama": ""}, "Kategori"),
    ({"tur": "geri_al", "ids": [3]}, "ödenmemiş"),
    ({"tur": "sil", "ids": [3, 4]}, "tek"),
])
def test_gecersiz_istekler(istek, parca):
    t, hata = _coz(istek)
    assert t is None and parca in hata, hata


def test_salt_okur_hicbir_islem_yapamaz():
    t, hata = _coz({"tur": "ode", "ids": [3], "banka": 1}, salt=True)
    assert t is None and "Salt-okur" in hata


# ── Yürütme: doğru veritabanı fonksiyonu, doğru argüman ───────────────
@pytest.fixture
def kayit(monkeypatch):
    import kayranacc.database as D
    k = []
    monkeypatch.setattr(D, "odeme_durum_guncelle", lambda *a, **kw: k.append(("durum", a, kw)))
    monkeypatch.setattr(D, "odeme_kismi_ode", lambda *a, **kw: (k.append(("kismi", a, kw)), (True, "Kısmi ödendi"))[1])
    monkeypatch.setattr(D, "odeme_vade_guncelle", lambda *a, **kw: (k.append(("vade", a, kw)), True)[1])
    monkeypatch.setattr(D, "odeme_tutar_guncelle", lambda *a, **kw: k.append(("tutar", a, kw)))
    monkeypatch.setattr(D, "odeme_kategori_guncelle", lambda *a, **kw: k.append(("kategori", a, kw)))
    monkeypatch.setattr(D, "odeme_aciklama_guncelle", lambda *a, **kw: k.append(("aciklama", a, kw)))
    monkeypatch.setattr(D, "odeme_sil", lambda *a, **kw: k.append(("sil", a, kw)))
    return k


def test_ode_banka_ve_kur_ile(kayit):
    s = M.islem_uygula({"tur": "ode", "ids": [3, 4], "banka": 1}, ODM, 38.5)
    assert kayit == [("durum", (3, "odendi", 1, 38.5), {}), ("durum", (4, "odendi", 1, 38.5), {})]
    assert s == {"ok": True, "mesaj": "2 ödeme ödendi", "geri_al": [3, 4]}
    s = M.islem_uygula({"tur": "ode", "ids": [3], "banka": None}, ODM, 38.5)
    assert kayit[-1] == ("durum", (3, "odendi", None, 38.5), {}) and s["mesaj"] == "SGK ödendi"


def test_kismi_ve_hata_mesaji(kayit, monkeypatch):
    s = M.islem_uygula({"tur": "kismi", "ids": [1], "banka": 1, "tl": 100000.0, "usd": 0.0}, ODM, 38.5)
    assert kayit == [("kismi", (1, 100000.0, 0.0, 1, 38.5), {})] and s["ok"] and s["geri_al"] == []
    import kayranacc.database as D
    monkeypatch.setattr(D, "odeme_kismi_ode", lambda *a, **kw: (False, "Tutar fazla"))
    s = M.islem_uygula({"tur": "kismi", "ids": [1], "banka": 1, "tl": 1.0, "usd": 0.0}, ODM, 38.5)
    assert s == {"ok": False, "mesaj": "Tutar fazla", "geri_al": []}


def test_otele_kalici_kayit_eski_vade_ile(kayit):
    s = M.islem_uygula({"tur": "otele", "ids": [1, 3], "vadeler": {1: date(2026, 10, 15), 3: date(2026, 10, 21)}},
                       ODM, 38.5)
    assert kayit == [("vade", (1, date(2026, 10, 15)), {"ertele": True, "eski_vade": date(2026, 10, 8)}),
                     ("vade", (3, date(2026, 10, 21)), {"ertele": True, "eski_vade": date(2026, 10, 14)})]
    assert s["ok"] and s["mesaj"] == "2 ödeme ötelendi"


def test_otele_basarisizsa_soylenir(kayit, monkeypatch):
    import kayranacc.database as D
    monkeypatch.setattr(D, "odeme_vade_guncelle", lambda *a, **kw: False)
    s = M.islem_uygula({"tur": "otele", "ids": [3], "vadeler": {3: date(2026, 10, 21)}}, ODM, 38.5)
    assert not s["ok"] and "DEĞİŞMEDİ" in s["mesaj"]


def test_duzenle_yalniz_degisen_alanlar(kayit):
    M.islem_uygula({"tur": "duzenle", "ids": [4], "tl": 30000.0, "usd": 0.0, "kategori": "cari",
                    "aciklama": "Kargo açıklama"}, ODM, 38.5)
    assert kayit == [("tutar", (4,), {"tutar_tl": 30000.0, "tutar_usd": 0.0})]
    kayit.clear()
    M.islem_uygula({"tur": "duzenle", "ids": [4], "tl": 27300.5, "usd": 0.0, "kategori": "sgk",
                    "aciklama": "yeni"}, ODM, 38.5)
    assert [x[0] for x in kayit] == ["tutar", "kategori", "aciklama"]


def test_sil_ve_geri_al(kayit):
    assert M.islem_uygula({"tur": "sil", "ids": [4]}, ODM, 38.5)["mesaj"] == "Kargo ödemesi silindi"
    s = M.islem_uygula({"tur": "geri_al", "ids": [6]}, ODM, 38.5)
    assert kayit[-1] == ("durum", (6, "bekliyor"), {"kur": 38.5}) and "bekliyor" in s["mesaj"]
