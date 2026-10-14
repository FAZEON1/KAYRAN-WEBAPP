# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Ref No Takibi liste masaları (Ekim 2026, ortak masa shared/masa.py).

Ref No'lar: özet bandı eski kpi_serit ile aynı (ref_hesap.toplam, USD karşılığı; iptal hariç), sıra ve dönem
grupları ref_hesap.grupla, tutar ve "≈ $" metni eski satırla aynı. Paylaşıldı / Beklemeye al / İptal
eski penceredeki düğmelerle AYNI çağrı (ref_ekran._durum_yaz → N.ref_guncelle). Alınan destekler: sıra dönem
(yeni üstte) + tutar; silme N.alinan_destek_sil.
"""
from datetime import date

import pytest

from kayranpm import ref_hesap as R
from kayranpm import ref_masasi as M
from shared.masa import istek_al, kosul_uyar
from shared.tasarim import sayi

EUR, TL = 1.08, 40.0
REFLER = [
    {"id": 1, "ref_no": "FZVTNRF2026003", "aciklama": "EYLÜL MONİTÖR", "durum": "beklemede", "tutar": 1000,
     "doviz": "USD", "kategori": "MONİTÖR", "aylik": {"2026-09": 1000}, "tarih": "2026-09-30", "_firma": "VATAN", "_fid": 3},
    {"id": 2, "ref_no": "FZVTNRF2026004", "aciklama": "EYLÜL SSD · EK", "durum": "paylasildi", "tutar": 40000,
     "doviz": "TL", "kategori": "SSD · RAM", "aylik": {"2026-09": 40000}, "_firma": "VATAN", "_fid": 3,
     "paylasim_tarihi": "2026-10-02"},
    {"id": 3, "ref_no": "FZHBRF2026001", "aciklama": "AĞUSTOS", "durum": "iptal", "tutar": 500, "doviz": "EUR",
     "aylik": {"2026-08": 500}, "_firma": "HB", "_fid": 4},
    {"id": 4, "ref_no": "FZHBRF2026002", "aciklama": "TARİHSİZ", "durum": None, "tutar": 70, "doviz": "GBP",
     "_firma": "HB", "_fid": 4},
]


def test_ozet_eski_kpi_ile_ayni():
    oz, t_all = M.ref_ozet(REFLER, EUR, TL)
    d = {k["k"]: k for k in oz}
    assert d["beklemede"]["dg"] == "2" and d["beklemede"]["al"] == f"≈ {sayi(1000, '$')} paylaşılmayı bekliyor"
    assert d["paylasildi"]["dg"] == "1" and d["paylasildi"]["al"] == f"≈ {sayi(40000 / TL, '$')}"
    assert t_all == R.toplam([r for r in REFLER if r.get("durum") != "iptal"], EUR, TL)
    assert d["toplam"]["dg"] == sayi(2000, "$") and t_all["cevrilmeyen"] == {"GBP": 70.0}


def test_sira_gruplar_ve_satir_metinleri():
    v = M.ref_verisi(REFLER, True, EUR, TL)
    assert [s["id"] for s in v["satirlar"]] == [r["id"] for _d, g in R.grupla(REFLER) for r in g] == [2, 1, 3, 4]
    r = {s["id"]: s for s in v["satirlar"]}
    assert r[2]["donem_ad"] == "Eylül 2026" and r[4]["donem_ad"] == "Dönemsiz"
    assert r[2]["tutar_m"] == "₺40.000,00" and r[2]["usd_alt"] == f"≈ {sayi(1000, '$')}" and r[2]["usd_top"] == 1000
    assert r[2]["meta"] == "Ssd · Ram · Eylül 2026 · VATAN · 2 kalem"
    assert r[3]["usd_top"] == 0.0 and r[3]["_soluk"]                         # iptal grup toplamına girmez
    assert r[4]["durum"] == "beklemede" and r[4]["usd_alt"] == "GBP · kur yok"
    assert r[1]["_detay"][0] == ["Açıklama", "EYLÜL MONİTÖR"] and ["Kayıt tarihi", "30.09.2026"] in r[1]["_detay"]
    gor = {g["k"]: g["f"] for g in v["gorunumler"]}
    assert [s["id"] for s in v["satirlar"] if kosul_uyar(s, gor["beklemede"])] == [1, 4]
    assert [o["k"] for o in v["secimler"][0]["secenekler"]] == ["2026"]
    assert "VATAN" not in M.ref_verisi(REFLER, False, EUR, TL)["satirlar"][0]["meta"]


def test_istek_dogrulama():
    v = M.ref_verisi(REFLER, True, EUR, TL)
    t, h = istek_al(v, {"islem": "paylas", "ids": [1, 4]})
    assert h is None and t["ids"] == [1, 4]
    for istek, parca in [({"islem": "paylas", "ids": [2]}, "uygun değil"), ({"islem": "iptal", "ids": [3]}, "uygun değil"),
                         ({"islem": "iptal", "ids": [1, 2]}, "tek"), ({"islem": "bekle", "ids": [1]}, "uygun değil"),
                         ({"islem": "sil", "ids": [1]}, "Bilinmeyen")]:
        assert parca in istek_al(v, istek)[1]
    assert istek_al(v, {"islem": "bekle", "ids": [2]})[1] is None
    assert istek_al(v, {"islem": "ac", "ids": [3]})[1] is None


@pytest.fixture
def guncelle(monkeypatch):
    from kayranpm import ref_no as N
    k = []
    monkeypatch.setattr(N, "ref_guncelle", lambda *a, **kw: (k.append((a, kw)), True)[1])
    return k


def test_durum_degisimi_eski_cagri(guncelle):
    v = M.ref_verisi(REFLER, True, EUR, TL)
    s = M.ref_yurutucu(REFLER)(istek_al(v, {"islem": "paylas", "ids": [1, 4]})[0])
    bugun = str(date.today())
    assert guncelle == [((1, "FZVTNRF2026003", "EYLÜL MONİTÖR", "paylasildi", "2026-09-30", bugun), {}),
                        ((4, "FZHBRF2026002", "TARİHSİZ", "paylasildi", None, bugun), {})]
    assert s["ok"] and s["mesaj"] == "2 ref paylaşıldı olarak işaretlendi" and s["geri"] == {"islem": "bekle", "ids": [1, 4]}
    guncelle.clear()
    s = M.ref_yurutucu(REFLER)(istek_al(v, {"islem": "iptal", "ids": [2]})[0])
    assert guncelle == [((2, "FZVTNRF2026004", "EYLÜL SSD · EK", "iptal", None, "2026-10-02"), {})]   # paylaşım tarihi korunur
    assert s["mesaj"] == "FZVTNRF2026004 iptal edildi" and s["geri"] is None
    guncelle.clear()
    M.ref_yurutucu(REFLER)(istek_al(v, {"islem": "bekle", "ids": [2]})[0])
    assert guncelle[0][0][3:] == ("beklemede", None, None)


def test_veritabani_yazamazsa_soylenir(monkeypatch):
    from kayranpm import ref_no as N
    monkeypatch.setattr(N, "ref_guncelle", lambda *a, **kw: False)
    v = M.ref_verisi(REFLER, True, EUR, TL)
    s = M.ref_yurutucu(REFLER)(istek_al(v, {"islem": "paylas", "ids": [1]})[0])
    assert not s["ok"] and "DEĞİŞMEDİ" in s["mesaj"]


def test_ac_bugunku_pencere(monkeypatch):
    from shared import bilesen as B
    c = []
    monkeypatch.setattr(B, "detay_ac", lambda *a: c.append(a))
    v = M.ref_verisi(REFLER, True, EUR, TL)
    assert M.ref_yurutucu(REFLER)(istek_al(v, {"islem": "ac", "ids": [2]})[0]) == \
        {"ok": True, "yenileme": False, "sessiz": True} and c == [("ref", 2)]


# ── Alınan destekler ────────────────────────────────────────────────
ALINAN = [
    {"id": 1, "firma": "FAZEON", "tur": "sellout", "donem": "2026-09", "tutar": 100, "doviz": "USD", "kategori": "MONİTÖR"},
    {"id": 2, "firma": "MSI", "tur": "rebate", "donem": "2026-10", "tutar": 50, "doviz": "USD", "fatura_no": "F1"},
    {"id": 3, "firma": "FAZEON", "tur": "sellout", "donem": "2026-10", "tutar": 4000, "doviz": "TL"},
]


def test_alinan_ozet_sira_ve_metin():
    v = M.alinan_verisi(ALINAN, 2026, date(2026, 10, 14), EUR, TL, kat_ad=lambda k: {"MONİTÖR": "Monitör"}.get(k, k))
    d = {k["k"]: k for k in v["ozet"]}
    assert d["toplam"]["dg"] == sayi(100 + 50 + 100, "$") and d["toplam"]["al"] == f"₺{sayi(4000)} · ${sayi(150)}"
    assert d["ay"]["et"] == "Bu ay · Ekim 2026" and d["ay"]["dg"] == sayi(150, "$") and d["ay"]["al"] == "2 kayıt"
    assert d["kayit"]["dg"] == "3" and d["kayit"]["al"] == "2 firma"
    assert [s["id"] for s in v["satirlar"]] == [3, 2, 1]               # dönem yeni üstte, içinde tutar büyükten
    r = {s["id"]: s for s in v["satirlar"]}
    assert r[3]["tutar_m"] == "₺4.000,00" and r[3]["usd_alt"] == f"≈ {sayi(100, '$')}"
    assert r[1]["etk"] == "Sellout · Monitör" and r[2]["fat"] == "Fatura F1"
    assert [o["k"] for o in v["secimler"][0]["secenekler"]] == ["FAZEON", "MSI"]


def test_alinan_sil(monkeypatch):
    from kayranpm import ref_no as N
    c = []
    monkeypatch.setattr(N, "alinan_destek_sil", lambda i: (c.append(i), True)[1])
    v = M.alinan_verisi(ALINAN, 2026, date(2026, 10, 14), EUR, TL)
    assert "gerekli" in istek_al(v, {"islem": "sil", "ids": [2], "degerler": {}})[1]
    s = M.alinan_yurutucu()(istek_al(v, {"islem": "sil", "ids": [2], "degerler": {"onay": True}})[0])
    assert c == [2] and s == {"ok": True, "mesaj": "Kayıt silindi"}
    monkeypatch.setattr(N, "alinan_destek_sil", lambda i: False)
    assert not M.alinan_yurutucu()(istek_al(v, {"islem": "sil", "ids": [2], "degerler": {"onay": True}})[0])["ok"]
