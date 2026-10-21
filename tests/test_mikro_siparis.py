# -*- coding: utf-8 -*-
"""Mikro siparişleri otomatik (Ekim 2026). Kullanıcı: "Tüm siparişler Mikro'dan çekilsin; Mikro'ya sipariş
girildiğinde programa da yansısın."

Müşteri siparişi (sip_tip 0): açık kalan adet, faturası kesilene kadar bekleyen satış olur (sipariş Excel'inin
yaptığı gibi); fatura kesilince Mikro'da teslim miktarı artar, bekleyen satır silinir, satış faturadan gelir.
Canlı veri (21.10.2026): VATAN siparişi G5I26-2358, F4PE650BBM 8 × 69,75 $ — aynı gün kesilen G5F26-2948
faturasında da 69,75 $ (sipariş fiyatı $ ve faturayla birebir).
Satın alma siparişi (sip_tip 1) satışa girmez; ithalat verisi Mikro'dan ayrı işte gelir."""
from pathlib import Path

import pytest

M = pytest.importorskip("satis.mikro_esitle")
KOK = Path(__file__).resolve().parent.parent
VATAN = "VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI"
UNVAN = {"120.01.003": VATAN, "320.50.101": "INNOVISION MULTIMEDIA LIMITED"}


def _sip(sira, sku, miktar, teslim, fiyat, tarih="2026-10-13", tip=0, doviz=1, cari="120.01.003", kapali=False):
    return {"sip_guid": f"s-{tip}-{sira}-{sku}", "sip_tip": tip, "sip_cins": 0, "sip_tarih": tarih + "T00:00:00",
            "sip_evrakno_seri": "G5I26", "sip_evrakno_sira": sira, "sip_musteri_kod": cari, "sip_stok_kod": sku,
            "sip_miktar": miktar, "sip_teslim_miktar": teslim, "kalan": miktar - teslim, "sip_b_fiyat": fiyat,
            "sip_tutar": miktar * fiyat, "sip_doviz_cinsi": doviz, "sip_kapat_fl": kapali}


def _fat(sira, sku, adet, tutar, tarih="2026-10-13", doviz=1, kur=42.0):
    return {"sth_guid": f"f-{sira}-{sku}", "cha_evrak_tip": 63, "cha_normal_iade": 0, "cha_evrakno_seri": "G5F26",
            "cha_evrakno_sira": sira, "cha_tarihi": tarih + " 00:00:00", "cha_d_cins": doviz,
            "cha_d_kur": kur if doviz == 1 else 1, "sth_alt_doviz_kuru": 0, "sth_stok_kod": sku, "sto_isim": sku,
            "sth_cari_kodu": "120.01.003", "cari_unvan1": VATAN, "sth_miktar": adet, "sth_tutar": tutar,
            "sth_iskonto": 0}


def test_acik_siparis_bekleyen_satis_olur():
    """Kalan adet × siparişin $ fiyatı; firma Mikro satış faturasındaki ünvanla aynı (firma_kanonik birleşir)."""
    k, atl = M.siparis_kayitlari([_sip(2358, "F4PE650BBM", 8, 3, 69.75)], UNVAN)
    r = k["G5I26-2358"][0]
    assert (r["adet"], r["birim_satis"], r["kanal"], r["tarih"]) == (5, 69.75, VATAN, "2026-10-13")
    assert r["notlar"].startswith(M.SIPARIS_NOT_ONEKI + " ·") and r["siparis_no"] == "G5I26-2358"
    assert atl == {}


@pytest.mark.parametrize("satir", [
    _sip(1, "A", 5, 5, 70),                          # tamamı faturalandı
    _sip(2, "A", 5, 0, 70, kapali=True),             # Mikro'da kapatıldı
    _sip(3, "A", 5, 0, 70, tip=1, cari="320.50.101"),  # tedarikçi siparişi: satış değil
    _sip(4, "A", 5, 0, 70, tarih="2026-06-30"),      # eşitleme başlangıcından önce
])
def test_kapali_tedarikci_ve_eski_siparis_satisa_girmez(satir):
    assert M.siparis_kayitlari([satir], UNVAN)[0] == {}


def test_tl_siparis_gunun_dolar_kuruyla():
    kur = M.kur_haritasi([_fat(1, "B", 1, 100, tarih="2026-10-12", kur=42.0)])
    k, _ = M.siparis_kayitlari([_sip(9, "A", 2, 0, 4200, doviz=0)], UNVAN, kurlar=kur)
    assert k["G5I26-9"][0]["birim_satis"] == pytest.approx(100.0)
    k2, atl = M.siparis_kayitlari([_sip(9, "A", 2, 0, 4200, doviz=0)], UNVAN, kurlar={})
    assert k2 == {} and atl == {"siparis_kursuz": 1}


def _mevcut(no, sku, adet, fiyat, id_, tarih="2026-10-13", notlar=None):
    return {"id": id_, "tarih": tarih, "kanal": VATAN, "sku": sku, "adet": adet, "birim_satis": fiyat,
            "birim_maliyet": 40.0, "birim_firma_destek": 0, "birim_ek_destek": 0, "siparis_no": no,
            "notlar": notlar or f"{M.SIPARIS_NOT_ONEKI} · Cari kodu: 120.01.003"}


def test_yeni_siparis_eklenir_degismeyen_dokunulmaz():
    sip = [_sip(2358, "F4PE650BBM", 8, 0, 69.75)]
    p = M.plan_yap([], [], [], siparisler=sip, unvanlar=UNVAN, pacal_fn=lambda s: 40.0)
    assert [(k["siparis_no"], k["adet"], k["birim_maliyet"]) for k in p["yuk"]["ekle_satis"]] == \
        [("G5I26-2358", 8, 40.0)]
    assert p["acik_siparis"] == 1 and p["acik_siparis_adet"] == 8 and p["yeni_fatura"] == 0
    # ikinci tur: aynı sipariş kayıtlı → yazılacak bir şey yok
    p2 = M.plan_yap([], [_mevcut("G5I26-2358", "F4PE650BBM", 8, 69.75, 1)], [], siparisler=sip, unvanlar=UNVAN)
    assert not p2["degisiklik_var"]


def test_faturalanan_siparisin_bekleyen_satiri_silinir_satis_faturadan_gelir():
    """Sipariş faturalandı: Mikro'da teslim = miktar → bekleyen satır silinir, fatura satırı eklenir; çift sayım
    yok. Eski kod sipariş satırını tanımıyordu: ne yazıyor ne siliyordu."""
    mevcut = [_mevcut("G5I26-2358", "F4PE650BBM", 8, 69.75, 1)]
    p = M.plan_yap([_fat(2948, "F4PE650BBM", 8, 558)], mevcut, [],
                   siparisler=[_sip(2358, "F4PE650BBM", 8, 8, 69.75)], unvanlar=UNVAN)
    assert "G5I26-2358" in p["yuk"]["fatura_nolar"] and p["yuk"]["sil_satis_id"] == []
    assert [(k["siparis_no"], k["adet"]) for k in p["yuk"]["ekle_satis"]] == [("G5F26-2948", 8)]
    a = {o["ay"]: o for o in p["ozet"]}["2026-10"]
    assert (a["adet_once"], a["adet_sonra"]) == (8, 8)


def test_kismi_teslimde_kalan_adet_guncellenir_maliyet_korunur():
    mevcut = [_mevcut("G5I26-2358", "F4PE650BBM", 8, 69.75, 1)]
    p = M.plan_yap([], mevcut, [], siparisler=[_sip(2358, "F4PE650BBM", 8, 3, 69.75)], unvanlar=UNVAN,
                   pacal_fn=lambda s: 99.0)
    assert p["yuk"]["fatura_nolar"] == ["G5I26-2358"]
    assert [(k["adet"], k["birim_maliyet"]) for k in p["yuk"]["ekle_satis"]] == [(5, 40.0)]


def test_siparis_satiri_mikro_disi_satir_gibi_silinmez():
    """Firmanın son faturasından önceki Mikro dışı satırlar (sipariş Excel'i) faturayla değişir; açık Mikro
    siparişinin bekleyen satırı bu kurala takılmaz (yoksa her tur silinip yeniden yazılırdı)."""
    mevcut = [_mevcut("G5I26-2358", "F4PE650BBM", 5, 69.75, 1, tarih="2026-10-10")]
    p = M.plan_yap([_fat(2948, "X", 1, 70, tarih="2026-10-13")], mevcut, [],
                   siparisler=[_sip(2358, "F4PE650BBM", 8, 3, 69.75, tarih="2026-10-10")], unvanlar=UNVAN)
    assert p["yuk"]["sil_satis_id"] == [] and "G5I26-2358" not in p["yuk"]["fatura_nolar"]


class _Yol:
    name = "siparis.xlsx"

    def __getattr__(self, ad):
        raise AssertionError(f"dosya kaydedilmemeli ({ad})")


@pytest.mark.parametrize("govde", ["kapi_siparis_vatan", "kapi_siparis_itopya"])
def test_esitleme_acikken_siparis_exceli_kaydedilmez(monkeypatch, govde):
    import sys
    import types
    SM = pytest.importorskip("satis.main")
    sahte = types.ModuleType("satis.mikro_esitle")
    sahte.acik_mi = lambda: True
    monkeypatch.setitem(sys.modules, "satis.mikro_esitle", sahte)
    bilgi = []
    monkeypatch.setattr(SM.st, "info", lambda m, *a, **k: bilgi.append(m), raising=False)
    assert getattr(SM, govde)(_Yol(), _Yol()) is None
    assert bilgi and "Mikro siparişlerinden" in bilgi[0] and "kaydedilmez" in bilgi[0]
