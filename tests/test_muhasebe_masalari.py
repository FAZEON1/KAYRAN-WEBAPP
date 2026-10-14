# -*- coding: utf-8 -*-
"""Muhasebe liste sayfaları ortak liste masasında (Ekim 2026, kayranacc/muhasebe_masalari.py).

Ertelenen ödemeler · Bu hafta ödenenler · Geçmiş haftalar · Çek arşivi · Gelenler geçmişi · Firma çekleri ·
Banka bakiyeleri. Burada: masanın tanımı (sıra, alanlar, rakamlar eski ekranın formülleriyle aynı), ortak
doğrulamanın (shared.masa.istek_al) bu tanımlarla geçerli isteği kabul edip geçersizi reddetmesi ve
yürütücünün BUGÜNKÜ veritabanı fonksiyonunu aynı argümanlarla çağırması."""
import sys
from datetime import date
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from kayranacc import muhasebe_masalari as M  # noqa: E402
from shared.masa import istek_al  # noqa: E402
from shared.tasarim import kart_degeri_kisa, tr_sayi  # noqa: E402

BUGUN = date(2026, 10, 14)
KAT = {"cek": {"label": "Çek", "oncelik": 1}, "sgk": {"label": "SGK", "oncelik": 5},
       "cari": {"label": "Cari Hesap", "oncelik": 8}, "diger": {"label": "Diğer", "oncelik": 99}}
BANKA = [{"id": 1, "hesap_adi": "Garanti TL", "para_birimi": "TL", "bakiye": 1240000},
         {"id": 2, "hesap_adi": "Ziraat USD", "para_birimi": "USD", "bakiye": 186420.5},
         {"id": 3, "hesap_adi": "Kasa TL", "para_birimi": "TL", "bakiye": -1500.25},
         {"id": 4, "hesap_adi": "Katılım EUR", "para_birimi": "EUR", "bakiye": 24300}]


def _kisa(m):
    return kart_degeri_kisa(m)[0]


def _o(i, firma, vade, tl=0, usd=0, kat="cari", durum="bekliyor", **k):
    return dict(id=i, firma=firma, aciklama=f"{firma} açıklama", vade=vade, tutar_tl=tl, tutar_usd=usd,
                kategori=kat, durum=durum, **k)


@pytest.fixture
def db(monkeypatch):
    """kayranacc.database'in yazan fonksiyonları kayda alınır (gerçek veritabanına gidilmez)."""
    import kayranacc.database as D
    k = []

    def kaydet(ad, donus=None):
        def f(*a, **kw):
            k.append((ad, a, kw))
            return donus
        return f
    for ad in ("odeme_durum_guncelle", "odeme_tutar_guncelle", "odeme_kategori_guncelle", "odeme_aciklama_guncelle",
               "odeme_sil", "hafta_aktif_yap", "hafta_sil", "cek_sil", "cek_sil_hepsi"):
        monkeypatch.setattr(D, ad, kaydet(ad))
    monkeypatch.setattr(D, "odeme_vade_guncelle", kaydet("odeme_vade_guncelle", True))
    monkeypatch.setattr(D, "odeme_kismi_ode", kaydet("odeme_kismi_ode", (True, "Kısmi ödendi")))
    monkeypatch.setattr(D, "tahsilat_guncelle", kaydet("tahsilat_guncelle", (True, "Tahsilat düzeltildi")))
    monkeypatch.setattr(D, "tahsilat_geri_al", kaydet("tahsilat_geri_al", (True, "✅ Tahsilat geri alındı")))
    monkeypatch.setattr(D, "get_kur", lambda *a, **kw: 41.2)
    return k


def _calis(veri, yurut, istek):
    t, h = istek_al(veri, istek)
    assert h is None, h
    return yurut(t)


# ════════════════════════════════════════════════════════════════════
# Ertelenen ödemeler
# ════════════════════════════════════════════════════════════════════
ERT = [
    _o(41, "Lccgame", "2026-12-31", tl=1_350_000, kat="sgk", orijinal_vade="2026-08-24", ertelendi_sayisi=2),
    _o(42, "Örnek Lojistik", "2026-10-10", tl=185000, usd=4490.29, orijinal_vade="2026-10-01", ertelendi_sayisi=1),
    _o(43, "Turkcell", "2026-10-09", tl=6120, durum="odendi", banka_id=1, odendi_tarih="2026-10-12",
       orijinal_vade="2026-10-02", ertelendi_sayisi=3),
    _o(44, "Tedarikçi", "2026-10-20", usd=18400, orijinal_vade="2026-10-16", ertelendi_sayisi=None),
]


def test_ertelenen_sira_ve_erteleme_bilgisi():
    v = M.ertelenen_verisi(ERT, BANKA, KAT, 38.5, BUGUN)
    assert [s["id"] for s in v["satirlar"]] == [42, 44, 41, 43]          # eski ekran: önce bekleyen, vadeye göre
    r = {s["id"]: s for s in v["satirlar"]}
    assert r[41]["kez_m"] == "2× ertelendi" and r[41]["simdi_m"] == "31.12.2026" and r[41]["ilk_m"] == "ilk 24.08.2026"
    assert r[41]["kayma"] == 129 and r[41]["firma_alt"] == "ilk vade 24.08.2026 · 129 gün kaydı · SGK"
    assert r[42]["vade_alt"] == "4 gün gecikti" and r[42]["vade_renk"] == "kirmizi"   # Bu hafta ile aynı ipucu
    assert r[44]["kez"] == 1                                             # boş sayı → 1 (eski ekranla aynı)
    assert r[42]["durum"] == "gecikmis" and r[42]["tl_m"] == "₺185.000,00" and r[42]["usd_m"] == "$4.490,29"
    assert r[43]["durum"] == "odendi" and r[43]["_soluk"] is True
    assert ["İlk vade", "24.08.2026"] in r[41]["_detay"] and ["Ertelenme", "2 kez"] in r[41]["_detay"]
    assert v["gorunumler"][0]["k"] == "tum" and v["grup"] is None


def test_ertelenen_ozet_eski_kartlarla_ayni():
    v = M.ertelenen_verisi(ERT, BANKA, KAT, 38.5, BUGUN)
    d = {k["k"]: k for k in v["ozet"]}
    bek = [o for o in ERT if o["durum"] != "odendi"]
    assert d["ert"]["dg"] == "4 ödeme" and d["ert"]["al"] == "3 hâlâ bekliyor"
    eski = f"₺{tr_sayi(sum(o['tutar_tl'] for o in bek), 2)}"            # eski kart: _tl(toplam)
    assert eski == "₺1.535.000,00" and d["bek"]["dg"] == _kisa(eski) == "₺1.535.000"
    assert d["bek"]["al"] == "+ $22.890,29" and d["en_cok"]["dg"] == "3 kez"


def test_ertelenen_odeme_islemleri_ayni_veritabani_cagrilari(db):
    v = M.ertelenen_verisi(ERT, BANKA, KAT, 38.5, BUGUN)
    y = M.ertelenen_yurutucu(ERT, BANKA, KAT, 38.5, BUGUN)
    s = _calis(v, y, {"islem": "ode", "ids": [42, 41], "degerler": {"banka": "1"}})
    assert db == [("odeme_durum_guncelle", (42, "odendi", 1, 38.5), {}),
                  ("odeme_durum_guncelle", (41, "odendi", 1, 38.5), {})]
    assert s["ok"] and s["geri"] == {"islem": "geri_al", "ids": [42, 41]}
    db.clear()
    _calis(v, y, {"islem": "otele", "ids": [44], "degerler": {"gun": 7}})
    assert db == [("odeme_vade_guncelle", (44, date(2026, 10, 27)), {"ertele": True, "eski_vade": date(2026, 10, 20)})]
    db.clear()
    _calis(v, y, {"islem": "ode", "ids": [42], "degerler": {"banka": "_bankasiz", "tl": 100000, "usd": 4490.29}})
    assert db == [("odeme_kismi_ode", (42, 100000.0, 4490.29, None, 38.5), {})]          # kısmi ödeme
    db.clear()
    _calis(v, y, {"islem": "geri_al", "ids": [43]})
    assert db == [("odeme_durum_guncelle", (43, "bekliyor"), {"kur": 38.5})]


def test_ertelenen_gecersiz_istekler():
    v = M.ertelenen_verisi(ERT, BANKA, KAT, 38.5, BUGUN)
    assert istek_al(v, {"islem": "ode", "ids": [43], "degerler": {"banka": 1}})[0] is None       # ödenmiş
    assert istek_al(v, {"islem": "ode", "ids": [42]})[0] is None                                  # banka yok
    assert istek_al(v, {"islem": "sil", "ids": [42, 44], "degerler": {"onay": True}})[0] is None   # tek kayıt
    assert istek_al(dict(v, salt=True), {"islem": "ode", "ids": [42], "degerler": {"banka": 1}})[0] is None


# ════════════════════════════════════════════════════════════════════
# Ödenenler & Geçmiş › Bu hafta ödenenler
# ════════════════════════════════════════════════════════════════════
ODM = [
    _o(1, "Turkcell", "2026-10-12", tl=6120, durum="odendi", banka_id=1, odendi_tarih="2026-10-12"),
    _o(2, "SGK", "2026-10-13", tl=212000, kat="sgk", durum="odendi", banka_id=None, odendi_tarih="2026-10-14"),
    _o(3, "Tedarikçi", "2026-10-13", usd=18400, durum="odendi", banka_id=2, odendi_tarih="2026-10-14"),
    _o(4, "Kargo", "2026-10-14", tl=27300.5),
]


def test_odenenler_gruplar_rakamlar():
    v = M.odenenler_verisi(ODM, BANKA, BUGUN)
    assert [s["id"] for s in v["satirlar"]] == [2, 3, 1]                  # ödeme günü yeni → eski
    r = {s["id"]: s for s in v["satirlar"]}
    assert r[2]["gun"].startswith("Bugün · Çarşamba, 14 Ekim") and r[1]["gun"].startswith("Pazartesi, 12 Ekim")
    assert r[2]["banka"] == "banka seçilmemiş" and r[1]["banka"] == "Garanti TL" and r[3]["usd_m"] == "$18.400,00"
    assert r[2]["kat_ad"] == "SGK" and r[2]["vade_m"] == "13.10.2026" and r[2]["_buyuk"] == "₺212.000,00"
    assert ["Ödendi", "14.10.2026"] in r[2]["_detay"]
    d = {k["k"]: k for k in v["ozet"]}
    assert d["tl"]["dg"] == _kisa("₺218.120,00") == "₺218.120" and d["usd"]["dg"] == "$18.400"
    assert d["adet"]["dg"] == "3" and d["adet"]["al"] == "4 ödemeden"


def test_odenenler_geri_al(db):
    v = M.odenenler_verisi(ODM, BANKA, BUGUN)
    s = _calis(v, M.odenenler_yurutucu(), {"islem": "geri_al", "ids": [2]})
    assert db == [("odeme_durum_guncelle", (2, "bekliyor"), {"kur": 41.2})]          # eski: kur=get_kur()
    assert s == {"ok": True, "mesaj": "SGK ödemesi geri alındı"}
    assert istek_al(v, {"islem": "geri_al", "ids": [4]})[0] is None                  # ödenmemiş listede yok
    assert istek_al(v, {"islem": "geri_al", "ids": [1, 2]})[0] is None               # tek tek
    assert istek_al(dict(v, salt=True), {"islem": "geri_al", "ids": [2]})[0] is None


# ════════════════════════════════════════════════════════════════════
# Ödenenler & Geçmiş › Geçmiş haftalar
# ════════════════════════════════════════════════════════════════════
HAFTA = [{"id": 9, "hafta_adi": "13.10.2026 LİSTE", "yuklendi_tarih": "13.10.2026"},
         {"id": 8, "hafta_adi": "06.10.2026 LİSTE", "yuklendi_tarih": "06.10.2026"}]
HOZ = {9: {"toplam": 10, "odendi": 4, "tl_toplam": 1250000.5, "usd_toplam": 1200},
       8: {"toplam": 8, "odendi": 8, "tl_toplam": 900000, "usd_toplam": 0}}


def test_haftalar_satirlari():
    v = M.haftalar_verisi(HAFTA, HOZ, 9)
    assert [s["id"] for s in v["satirlar"]] == [9, 8]
    r = {s["id"]: s for s in v["satirlar"]}
    assert r[9]["aktif"] is True and r[9]["_durum"] == {"ad": "Aktif", "renk": "mor"} and r[8]["_durum"] == {}
    assert r[9]["odendi_m"] == "4/10 ödendi" and r[9]["oran_m"] == "%40" and r[8]["oran_m"] == "%100"
    assert r[9]["tl_m"] == "₺1.250.000,50" and r[9]["usd_m"] == "$1.200,00" and r[8]["usd_m"] == "$0,00"


def test_haftalar_islemleri(db):
    v = M.haftalar_verisi(HAFTA, HOZ, 9)
    acilan = []
    y = M.haftalar_yurutucu(acilan.append)
    s = _calis(v, y, {"islem": "ac", "ids": [8]})
    assert acilan == [8] and s == {"ok": True, "yenileme": False, "sessiz": True} and db == []
    assert _calis(v, y, {"islem": "aktif_yap", "ids": [8]})["mesaj"] == "'06.10.2026 LİSTE' aktif yapıldı"
    assert db[-1] == ("hafta_aktif_yap", (8,), {})
    assert istek_al(v, {"islem": "aktif_yap", "ids": [9]})[0] is None                # zaten aktif
    assert istek_al(v, {"islem": "sil", "ids": [8]})[0] is None                      # onaysız silinmez
    assert _calis(v, y, {"islem": "sil", "ids": [8], "degerler": {"onay": True}})["mesaj"] == "Hafta silindi"
    assert db[-1] == ("hafta_sil", (8,), {})
    sv = dict(v, salt=True)
    assert istek_al(sv, {"islem": "ac", "ids": [8]})[1] is None                      # okuma salt-okurda da
    assert istek_al(sv, {"islem": "sil", "ids": [8], "degerler": {"onay": True}})[0] is None


# ════════════════════════════════════════════════════════════════════
# Ödenenler & Geçmiş › Çek arşivi
# ════════════════════════════════════════════════════════════════════
CEK = [
    {"id": 1, "ref_no": "C0001", "cek_no": "700100", "ch_ismi": "Örnek Tedarik", "banka": "Örnek Bankası",
     "vade": "2026-10-24", "meblagh": 150000.0, "kalan": 150000.0, "odenen": 0, "durum": "Ödendi"},
    {"id": 2, "ref_no": "C0002", "cek_no": "700101", "ch_ismi": "Deneme Ltd", "banka": "Deneme Bank",
     "vade": "2026-11-13", "meblagh": 175000.0, "kalan": 75000.0, "odenen": 100000, "durum": "Ciro edildi"},
    {"id": 3, "ref_no": None, "cek_no": None, "ch_ismi": None, "banka": None,
     "vade": "2026-09-01", "meblagh": 20000.5, "kalan": 0, "odenen": 0, "durum": None},
]


def test_cek_arsivi_tanimi_ve_ozeti():
    from kayranacc.database import cek_tutarlari
    v = M.cek_arsivi_verisi(CEK, "TL")
    assert [s["id"] for s in v["satirlar"]] == [2, 1, 3]                  # vade yeni → eski
    r = {s["id"]: s for s in v["satirlar"]}
    assert r[1]["_durum"] == {"ad": "Ödendi", "renk": "yesil"} and r[1]["kalan_m"] == "kapandı"
    assert r[2]["_durum"]["renk"] == "cyan" and r[2]["kalan_m"] == "₺75.000,00" and r[2]["alt"] == "Deneme Bank · ref C0002"
    assert r[3]["_durum"] == {"ad": "Bekliyor", "renk": "amber"} and r[3]["firma"] == "—" and r[3]["no_m"] == "no —"
    assert r[3]["kalan_m"] == "₺20.000,50"                                 # cek_tutarlari: meblağ − ödenen
    t = [cek_tutarlari(c) for c in CEK]
    d = {k["k"]: k for k in v["ozet"]}
    assert d["adet"]["dg"] == "3" and d["adet"]["al"] == "1 ödendi"
    assert d["meblag"]["dg"] == _kisa(f"₺{tr_sayi(sum(x['meblag'] for x in t), 2)}") == "₺345.001"
    assert d["kalan"]["dg"] == _kisa(f"₺{tr_sayi(sum(x['kalan'] for x in t), 2)}") == "₺95.001"
    assert M.cek_arsivi_verisi(CEK[:1], "USD")["satirlar"][0]["meblag_m"] == "$150.000,00"


def test_cek_arsivi_sil(db):
    v = M.cek_arsivi_verisi(CEK, "TL")
    assert istek_al(v, {"islem": "sil", "ids": [2]})[0] is None
    s = _calis(v, M.cek_arsivi_yurutucu(), {"islem": "sil", "ids": [2], "degerler": {"onay": True}})
    assert db == [("cek_sil", (2,), {})] and s["mesaj"] == "Çek silindi"


# ════════════════════════════════════════════════════════════════════
# Gelenler geçmişi
# ════════════════════════════════════════════════════════════════════
GEL = [
    {"id": 1, "banka_id": 1, "hesap_adi": "Garanti TL", "para_birimi": "TL", "tutar": 120000.0,
     "kaynak": " D-MARKET ", "aciklama": "Hakediş", "tarih": "2026-10-14"},
    {"id": 2, "banka_id": 2, "hesap_adi": "Ziraat USD", "para_birimi": "USD", "tutar": 8500.5,
     "kaynak": "VATAN", "aciklama": "", "tarih": "2026-10-02"},
    {"id": 3, "banka_id": 1, "hesap_adi": "Garanti TL", "para_birimi": None, "tutar": 15000,
     "kaynak": "", "aciklama": None, "tarih": "2026-09-28"},
    {"id": 4, "banka_id": 4, "hesap_adi": "Katılım EUR", "para_birimi": "EUR", "tutar": 2000,
     "kaynak": "EERA", "aciklama": "", "tarih": "2026-10-14"},
]


def test_gelenler_sira_grup_ve_ozet():
    v = M.gelenler_verisi(GEL, BANKA)
    assert [s["id"] for s in v["satirlar"]] == [4, 1, 2, 3]               # tarih, id yeni → eski
    r = {s["id"]: s for s in v["satirlar"]}
    assert r[1]["ay"] == "Ekim 2026" and r[3]["ay"] == "Eylül 2026" and r[1]["gun_m"] == "14 Ekim, Çar"
    assert r[1]["tutar_m"] == "₺120.000,00" and r[2]["tutar_m"] == "$8.500,50" and r[4]["tutar_m"] == "€2.000,00"
    assert r[3]["pb"] == "TL" and r[3]["kaynak"] == "—" and r[1]["kaynak_k"] == "D-MARKET"
    assert r[2]["usd"] == 8500.5 and r[2]["tl"] == 0
    d = {k["k"]: k for k in v["ozet"]}
    assert d["tl"]["dg"] == _kisa("₺135.000,00") and d["usd"]["dg"] == "$8.501" and d["eur"]["dg"] == "€2.000"
    assert d["adet"]["dg"] == "4" and d["adet"]["al"] == "4 kaynak"
    sec = {s["alan"]: [o["k"] for o in s["secenekler"]] for s in v["secimler"]}
    assert sec["kaynak_k"] == ["D-MARKET", "EERA", "VATAN"] and sec["pb"] == ["TL", "USD", "EUR"]
    assert "eur" not in {k["k"] for k in M.gelenler_verisi(GEL[:3], BANKA)["ozet"]}       # EUR yoksa kart yok


def test_gelenler_kimden_ne_kadar():
    s = M.kimden_ne_kadar(GEL)
    assert [k for k, _ in s] == ["VATAN", "D-MARKET", "EERA", "—"]       # eski sıra kuralı: USD×40, EUR×44
    assert s[0] == ("VATAN", {"USD": 8500.5}) and dict(s)["—"] == {"TL": 15000.0}


def test_gelenler_duzenle_ve_geri_al(db):
    v = M.gelenler_verisi(GEL, BANKA)
    y = M.gelenler_yurutucu(BANKA)
    s = _calis(v, y, {"islem": "duzenle", "ids": [1], "degerler": {
        "banka": "3", "tutar": "125000", "tarih": "2026-10-13", "kaynak": " D-MARKET A.Ş. ", "aciklama": " Hakediş "}})
    assert db == [("tahsilat_guncelle", (1, 3, 125000.0, "D-MARKET A.Ş.", "Hakediş", date(2026, 10, 13)), {})]
    assert s["ok"] and s["mesaj"] == "Tahsilat düzeltildi · Garanti TL −₺120.000,00 · Kasa TL +₺125.000,00"
    db.clear()
    _calis(v, y, {"islem": "duzenle", "ids": [3], "degerler": {"banka": 1, "tutar": 15000}})
    assert db == [("tahsilat_guncelle", (3, 1, 15000.0, "", "", date(2026, 9, 28)), {})]  # boşaltılan alan boş kalır
    db.clear()
    s = _calis(v, y, {"islem": "geri_al", "ids": [2], "degerler": {"onay": True}})
    assert db == [("tahsilat_geri_al", (2,), {})] and s == {"ok": True, "mesaj": "Tahsilat geri alındı"}


def test_gelenler_gecersiz_istekler():
    v = M.gelenler_verisi(GEL, BANKA)
    assert istek_al(v, {"islem": "geri_al", "ids": [2]})[0] is None                       # onaysız
    assert istek_al(v, {"islem": "duzenle", "ids": [1], "degerler": {"banka": 99, "tutar": 5}})[0] is None
    assert istek_al(v, {"islem": "duzenle", "ids": [1], "degerler": {"banka": 1}})[0] is None   # tutar zorunlu
    assert istek_al(v, {"islem": "duzenle", "ids": [1], "degerler": {"banka": 1, "tutar": "-5"}})[0] is None
    assert "duzenle" not in {i["k"] for i in M.gelenler_verisi(GEL, [])["islemler"]}       # banka okunamadıysa


# ════════════════════════════════════════════════════════════════════
# Firma çekleri (salt okunur)
# ════════════════════════════════════════════════════════════════════
FC = [
    {"id": 1, "ref_no": "R1", "cek_no": "11", "tarih": "2026-09-01", "vade": "2026-10-01", "meblagh": 100000.0,
     "odenen": 0, "kalan": 100000.0, "durum": "Bekliyor", "ch_kodu": "320.01", "ch_ismi": "Gecikmiş Firma",
     "banka": "Örnek", "sube": "Merkez", "hesap_no": "1"},
    {"id": 2, "ref_no": "R2", "cek_no": "12", "tarih": "2026-09-02", "vade": "2026-10-14", "meblagh": 50000.0,
     "odenen": 10000, "kalan": 40000, "durum": "Ciro edildi", "ch_ismi": "Bugün Firma", "banka": "Deneme"},
    {"id": 3, "ref_no": "R3", "cek_no": "13", "vade": "2026-09-14", "meblagh": 70000.0, "odenen": 0,
     "kalan": 70000, "durum": "ÖDENDİ", "ch_ismi": "", "banka": ""},
]


def test_firma_cekleri_ozet_eski_kartlarla_ayni():
    v = M.firma_cekleri_verisi(FC, "TL", BUGUN)
    d = {k["k"]: k for k in v["ozet"]}
    assert d["meblag"]["dg"] == _kisa("₺220.000,00") and d["meblag"]["al"] == "3 çek (tümü)"
    assert d["odenen"]["dg"] == _kisa("₺80.000,00") and d["odenen"]["al"] == "1 adet ödendi"
    assert d["kalan"]["dg"] == _kisa("₺140.000,00") and d["kalan"]["al"] == "2 bekleyen/ciro"
    assert d["kalan"]["ipucu"] == "₺140.000,00" and v["islemler"] == []


def test_firma_cekleri_satirlari():
    v = M.firma_cekleri_verisi(FC, "USD", BUGUN)
    assert [s["id"] for s in v["satirlar"]] == [1, 2, 3]                  # eski tabloyla aynı (veri sırası)
    r = {s["id"]: s for s in v["satirlar"]}
    assert r[1]["vade_m"] == "01.10.2026" and r[1]["vade_renk"] == "kirmizi" and r[1]["gecikmis"] is True
    assert r[2]["vade_renk"] == "amber" and r[2]["vade_alt"] == "bugün" and r[3]["vade_renk"] == ""
    assert r[1]["_durum"] == {"ad": "Bekliyor", "renk": "amber"} and r[3]["_durum"] == {"ad": "Ödendi", "renk": "yesil"}
    assert r[2]["_durum"] == {"ad": "Ciro edildi", "renk": "soluk"}
    assert r[1]["meblag_m"] == "$100.000,00" and r[2]["odenen_m"] == "$10.000,00" and r[3]["kalan_m"] == ""
    assert r[3]["firma"] == "—" and r[3]["banka"] == "—"
    assert ["C/H kodu", "320.01"] in r[1]["_detay"] and ["Tarih", "01.09.2026"] in r[1]["_detay"]
    t, h = istek_al(v, {"islem": "ac", "ids": [1]})
    assert t is None and "Bilinmeyen" in h                                 # salt okunur: işlem yok


# ════════════════════════════════════════════════════════════════════
# Banka bakiyeleri
# ════════════════════════════════════════════════════════════════════
def test_banka_ozeti_eski_seritle_ayni_formul():
    from kayranacc.banka_ekran import banka_ozet_kalemleri
    kal = banka_ozet_kalemleri(BANKA, 38.5, 824300.5, 22890.29)
    v = M.banka_verisi(BANKA, kal, [])
    assert [k["et"] for k in v["ozet"]] == ["Toplam TL", "Toplam USD", "Toplam EUR", "Hepsi (USD karşılığı)",
                                            "Hafta sonu tahmini"]
    assert [k["dg"] for k in v["ozet"]] == [_kisa(k["deger"]) for k in kal]
    assert kal[0]["deger"] == "₺1.238.499,75" and v["ozet"][0]["dg"] == "₺1.238.500"
    hs = 1238499.75 - 824300.5 - 22890.29 * 38.5
    assert v["ozet"][-1]["renk"] == ("yesil" if hs >= 0 else "kirmizi") and v["ozet"][-1]["nokta"] is False


def test_banka_satirlari_ve_ac():
    son = [{"id": 9, "banka_id": 1, "tarih": "2026-10-14", "tutar": 120000, "para_birimi": "TL", "kaynak": "VATAN"},
           {"id": 8, "banka_id": 1, "tarih": "2026-10-10", "tutar": 5, "para_birimi": "TL", "kaynak": "eski"}]
    v = M.banka_verisi(BANKA, [], son)
    assert [s["id"] for s in v["satirlar"]] == [1, 3, 2, 4]                # TL → USD → EUR, bakiye büyükten
    r = {s["id"]: s for s in v["satirlar"]}
    assert r[3]["bakiye_m"] == "-₺1.500,25" and r[2]["bakiye_m"] == "$186.420,50" and r[4]["bakiye_m"] == "€24.300,00"
    assert r[1]["son_m"] == "14.10.2026" and r[1]["son_alt"] == "+₺120.000,00 · VATAN" and r[2]["son_alt"] == "tahsilat yok"
    assert r[1]["pb_grup"] == "TL hesapları" and v["tik"] == "ac"
    acilan = []
    s = _calis(v, M.banka_yurutucu(acilan.append), {"islem": "ac", "ids": [2]})
    assert acilan == [2] and s["yenileme"] is False and s["sessiz"] is True
    assert istek_al(dict(v, salt=True), {"islem": "ac", "ids": [2]})[1] is None    # salt-okur da açabilir


def test_bos_ve_bozuk_veri_cokmez():
    assert M.ertelenen_verisi([], [], KAT, 0, BUGUN)["satirlar"] == []
    assert M.odenenler_verisi([], [], BUGUN)["satirlar"] == []
    assert M.haftalar_verisi([{"id": 1}], {}, None)["satirlar"][0]["odendi_m"] == "0/0 ödendi"
    assert M.cek_arsivi_verisi([{"id": 1, "meblagh": "abc"}], "TL")["satirlar"][0]["meblag_m"] == "₺0,00"
    assert M.gelenler_verisi([{"id": 1, "tarih": None, "tutar": None}], [])["satirlar"][0]["ay"] == "Tarihsiz"
    assert M.firma_cekleri_verisi([{"id": 1}], "TL", BUGUN)["satirlar"][0]["vade_m"] == "—"
    assert M.banka_verisi([], [], None)["satirlar"] == []
