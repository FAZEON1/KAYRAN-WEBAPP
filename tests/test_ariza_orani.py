# -*- coding: utf-8 -*-
"""Arıza oranı (teknikservis/ariza_orani.py, Ekim 2026, kullanıcı kararı A).

Arıza oranı = servise ARIZALI gelen (aynı seri bir kez) ÷ son kullanıcıya ulaşan. İade arıza değildir
(koli hasarı, cayma, sağlam iade); iade yoluyla gelen gerçek arıza (ölü piksel) arızadır. Arıza sonucu
girilmemiş eski kayıtlarda sonuç metinden tahmin edilir — teknisyenin tespiti müşteri beyanından önce.
"""
from pathlib import Path

import teknikservis.ariza_orani as A
from shared.utils import sku_anahtar

KOK = Path(__file__).resolve().parent.parent


def _k(**kw):
    return dict({"arayuz": "teknik", "ariza": "", "yapilan_islem": "", "test_sureci": "", "fiziksel_durum": ""}, **kw)


def test_tahmin_canli_ornekler():
    # Gerçek kayıtlardan (Ekim 2026) — beklenen sonuçlar elle doğrulandı.
    beklenen = [
        (_k(arayuz="iade", ariza="İade talep ediliyor. Üründe ölü piksel vardır"), A.ARIZA),
        (_k(arayuz="iade", ariza="no info", yapilan_islem="güç kaynağı değiştirildi"), A.ARIZA),
        (_k(ariza="GÜÇ GELMİYOR", yapilan_islem="güç yok"), A.ARIZA),
        (_k(arayuz="iade", ariza="İade talep ediliyor. MONİTÖR GÜÇ ALMIYOR"), A.ARIZA),
        (_k(arayuz="iade", ariza="koli hasarlı teslim alınmayan ürünler",
            yapilan_islem="ÜRÜN HASARLI (YAN CAM PANEL KIRIK)"), A.FIZIKSEL),
        (_k(arayuz="iade", ariza="İade talep ediliyor. Köşesinde yamulma mevcut",
            yapilan_islem="ön panel değiştirildi"), A.FIZIKSEL),
        (_k(arayuz="iade", ariza="no info", yapilan_islem="yan panel değiştirildi"), A.FIZIKSEL),
        # teknisyen arıza bulamadı → müşterinin "görüntü gidiyor" beyanı arıza sayılmaz
        (_k(ariza="fişe takıldığında bazen açılmıyor, görüntü gidiyor",
            yapilan_islem="müşteri şikayetinde ki bulgulara rastlanılmadı",
            test_sureci="Monitör defalarca kapatılıp açılmıştır. Ürün stabil çalışmaktadır."), A.NTF),
        (_k(ariza="güç kablosu çalışmıyor", yapilan_islem="müşteri memnuniyeti adına iade alındı.",
            fiziksel_durum="sağlam"), A.SAGLAM),
        (_k(ariza="sabitleme çubuklarından 1 tanesi eksik", yapilan_islem="aparatlar eksik"), A.EKSIK),
        (_k(arayuz="iade", ariza="no info"), A.SAGLAM),
        (_k(arayuz="iade", ariza="CAYMA HAKKIMI KULLANMAK İSTİYORUM"), A.SAGLAM),
        (_k(arayuz=None), A.BELIRSIZ),
        (_k(ariza="BERKAY BEY BİLGİSİNDE İADE AMAÇLI GÖNDERİLDİ"), A.BELIRSIZ),
        (_k(ariza="ekran", fiziksel_durum="hasarsız"), A.BELIRSIZ),           # "hasarsız" hasar değil
    ]
    for k, s in beklenen:
        assert A.tahmin(k) == s, (k, A.tahmin(k))


def test_teknisyen_sonucu_tahminden_once_gelir():
    k = _k(arayuz="iade", ariza="ölü piksel", ariza_sonucu=A.NTF)
    assert A.sonuc(k) == (A.NTF, False)
    assert A.sonuc(_k(ariza="ölü piksel")) == (A.ARIZA, True)
    assert A.sonuc(_k(ariza="ölü piksel", ariza_sonucu="saçma")) == (A.ARIZA, True)


def test_sonuc_zorunlu():
    assert A.sonuc_zorunlu("teknik", "tamir edildi") and A.sonuc_zorunlu("iade", "satışa hazır")
    assert not A.sonuc_zorunlu("teknik", "teknisyende") and not A.sonuc_zorunlu("iade", "mal kabül")
    assert not A.sonuc_zorunlu(None, "satışa hazır")                       # evraksız depo kaydı


def test_servis_ozeti_seri_bir_kez_ve_donem():
    kay = [
        dict(_k(ariza="ölü piksel"), id=1, stok_kodu="Fazeon X24", seri_no="S1", mal_kabul_tarihi="2026-07-01"),
        dict(_k(ariza="no info", arayuz="iade"), id=2, stok_kodu="X24", seri_no="s1", mal_kabul_tarihi="2026-08-01"),
        dict(_k(ariza="güç gelmiyor"), id=3, stok_kodu="X24", seri_no="S2", mal_kabul_tarihi="2026-07-05",
             ariza_sonucu=A.NTF),
        dict(_k(arayuz="iade", ariza="koli hasarlı"), id=4, stok_kodu="X24", seri_no="S3",
             mal_kabul_tarihi="2026-07-09"),
        dict(_k(ariza="ölü piksel"), id=5, stok_kodu="X24", seri_no="S4", mal_kabul_tarihi="2026-05-01"),
    ]
    oz = A.servis_ozeti(kay, sku_anahtar, "2026-06-23", "2026-10-04")
    assert oz == {"X24": {"gelen": 3, "arizali": 1, "tahmini": 1,
                          "sonuclar": {A.ARIZA: 1, A.NTF: 1, A.FIZIKSEL: 1}}}


def test_satirlar_ulasan_ve_oran():
    satis = A.satis_toplami([{"tarih": "2026-07-01", "sku": "X24", "adet": 120},
                             {"tarih": "2026-07-03", "sku": "Fazeon X24", "adet": -20},
                             {"tarih": "2026-05-01", "sku": "X24", "adet": 999}], sku_anahtar, "2026-06-23", "2026-10-04")
    assert satis == {"X24": 100.0}
    assert A.satis_toplami([{"tarih": "2025-03-01", "sku": "X24", "adet": 5},
                            {"tarih": "2026-11-01", "sku": "X24", "adet": 7}], sku_anahtar, None, "2026-10-04") \
        == {"X24": 5.0}                                       # payda: bitişe kadar bütün geçmiş
    mstok = A.musteri_stogu({"VATAN": {"X24": 30}, "ITOPYA": {"X24": 10, "Y": -5}})
    assert mstok == {"X24": 40.0, "Y": 0.0}
    servis = {"X24": {"gelen": 3, "arizali": 3, "tahmini": 2, "sonuclar": {}},
              "Z9": {"gelen": 1, "arizali": 1, "tahmini": 1, "sonuclar": {}}}
    kart = {"X24": {"sku": "Fazeon X24", "urun_adi": "Monitör", "kategori": "Monitör", "marka": "Fazeon"}}
    r = A.satirlar(kart, {"X24": 500.0}, satis, mstok, servis)
    x = next(s for s in r if s["_id"] == "X24")
    assert (x["Satın alınan"], x["Müşteriye satılan"], x["Müşteri stoğunda"], x["Son kullanıcıya ulaşan"],
            x["Arızalı"], x["Arıza oranı (%)"]) == (500, 100, 40, 60, 3, 5.0)
    z = next(s for s in r if s["_id"] == "Z9")
    assert z["Son kullanıcıya ulaşan"] == 0 and z["Arıza oranı (%)"] is None    # sıfıra bölme yok
    assert r[0]["_id"] == "X24"                                                  # oranlı önce
    g = A.grup_ozeti(r, "Kategori")
    assert g[0] == {"Kategori": "Monitör", "Son kullanıcıya ulaşan": 60, "Arızalı": 3, "Servise gelen": 3,
                    "Arıza oranı (%)": 5.0}


def test_ekran_paydasi_butun_satis_gecmisi():
    e = (KOK / "teknikservis" / "ariza_ekran.py").read_text(encoding="utf-8")
    assert "get_satislar_yalin(None, bit)" in e and "A.servis_ozeti(kayitlar, sku_anahtar, bas, bit)" in e


def test_ekran_menu_ve_kayit_baglantisi():
    from shared.gezinme import secenekler
    assert "Arıza Oranı" in secenekler("teknikservis")
    m = (KOK / "teknikservis" / "main.py").read_text(encoding="utf-8")
    assert 'ekstra["ariza_sonucu"] = _as' in m and "_AO.sonuc_zorunlu(kayit.get(\"arayuz\"), yeni_durum)" in m
    assert "if _as_eksik:" in m and "elif durum_guncelle(kid, yeni_durum" in m
    assert 'elif sayfa == "Arıza Oranı":' in m
    s = (KOK / "veritabani" / "20_ariza_sonucu.sql").read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS ariza_sonucu text" in s
