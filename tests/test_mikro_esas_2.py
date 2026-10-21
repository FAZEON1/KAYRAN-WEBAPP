# -*- coding: utf-8 -*-
"""Mikro esas — 21.10.2026 kullanıcı kararları (2):
- 11: hurda / outlet / ikinci el depoları Sıddık'a satış oranıyla değerlenir (satılmamış ürün depo ortalamasıyla).
- 5 : dönem sonu 320 → 159 virmanı geri alınana kadar ithalat ödenen düşmez.
- 9 : alınan destekler 2026'dan itibaren Mikro 602 hesaplarından; uygulamada o dönem için yeni kayıt açılmaz.
Canlı (21.10): Sıddık oranları İkinci el %78,8 · Outlet %97,6 · Servis (hurda) %23,1."""
import datetime

import pytest

SD = pytest.importorskip("kayranacc.mikro_stok_degeri")


# ── 11) Depo türü oranları ───────────────────────────────────────
@pytest.mark.parametrize("ad,tur", [("TEKNİK DEPO", "hurda"), ("SERVİS DEPO", "hurda"), ("İKİNCİ EL DEPO", "ikinci_el"),
                                    ("OUTLET DEPO", "outlet"), ("OUTLET", "outlet"), ("MERKEZ DEPO", None),
                                    ("İADE DEPO", None), ("HAPPY LIFE", None)])
def test_depo_turu(ad, tur):
    assert SD.depo_turu(ad) == tur


def _sat(depo, sku, adet, satis, maliyet):
    return {"depo": depo, "sku": sku, "adet": adet, "birim_satis": satis, "birim_maliyet": maliyet}


def test_oranlar_urun_ve_depo_ortalamasi():
    s = [_sat("SERVİS DEPO", "X24F240P", 10, 20, 80), _sat("SERVİS DEPO", "Fazeon X27F241S", 10, 30, 100),
         _sat("OUTLET", "A", 5, 120, 100),                       # maliyetin üstünde satış → 1'e kırpılır
         _sat("İKİNCİ EL DEPO", "B", 2, 50, 0),                  # maliyetsiz → sayılmaz
         _sat("MERKEZ DEPO", "C", 1, 10, 100)]                   # normal depo → oran yok
    o = SD.oranlar(s)
    assert set(o) == {"hurda", "outlet"}
    assert o["hurda"]["ort"] == pytest.approx(500 / 1800, abs=1e-4)
    assert o["hurda"]["sku"]["X24F240P"] == pytest.approx(0.25) and o["hurda"]["sku"]["X27F241S"] == pytest.approx(0.3)
    assert o["outlet"]["ort"] == 1.0


def test_depo_degerleri_oranla_satilmamis_urun_depo_ortalamasi(monkeypatch):
    monkeypatch.setattr(SD, "_birim", lambda pacal, sku: 100.0)
    o = SD.oranlar([_sat("SERVİS DEPO", "X24F240P", 10, 20, 80), _sat("SERVİS DEPO", "Y", 10, 30, 100)])
    urunler = [{"sku": "X24F240P", "depo_kirilim": {"TEKNİK DEPO": 2, "MERKEZ DEPO": 3}},
               {"sku": "HIC_SATILMADI", "depo_kirilim": {"TEKNİK DEPO": 1}}]
    d = SD.depo_degerleri(urunler, {"x": 1}, o)
    ort = 500 / 1800
    assert d["deger"]["TEKNİK DEPO"] == pytest.approx(2 * 100 * 0.25 + 1 * 100 * ort, abs=0.01)
    assert d["deger"]["MERKEZ DEPO"] == pytest.approx(300)               # normal depo tam paçal
    assert d["indirim"]["TEKNİK DEPO"] == pytest.approx(300 - d["deger"]["TEKNİK DEPO"], abs=0.01)
    assert SD.depo_degerleri(urunler, {"x": 1})["deger"]["TEKNİK DEPO"] == pytest.approx(300)   # oran yoksa tam


# ── 5) Dönem sonu virmanı ────────────────────────────────────────
def _h(kod, tip, meblag, tarih, acik):
    return {"cha_kod": kod, "cha_tip": tip, "cha_meblag": meblag, "cha_tarihi": tarih, "cha_aciklama": acik}


def test_geri_alinmamis_donem_sonu_virmani_yok_sayilir():
    from kayranacc.mikro_muhasebe import donem_sonu_virmansiz
    bugun = datetime.date(2026, 12, 31)
    odeme = _h("320.50.101", 0, 260800, "2026-10-08", "YKB USD - INNOVISION İTH.ÖDEMESİ")
    vir = _h("320.50.101", 1, 260800, "2026-12-31", "320-159 VİRMANI")
    eski = _h("320.50.002", 0, 74736.54, "2025-01-01", "159-320 HS VİRMANI")        # kalıcı sınıflandırma
    assert donem_sonu_virmansiz([odeme, vir, eski], bugun) == [odeme, eski]
    geri = _h("320.50.101", 0, 260800, "2027-01-01", "320-159 VİRMANI")
    assert donem_sonu_virmansiz([odeme, vir, geri, eski], datetime.date(2027, 1, 1)) == [odeme, vir, geri, eski]
    assert donem_sonu_virmansiz([odeme, vir], datetime.date(2027, 1, 20)) == [odeme, vir]   # 10 günden eski: kalıcı


def test_ithalat_odenen_virman_gunu_dusmez():
    from kayranacc.mikro_muhasebe import cari_bakiyeleri, donem_sonu_virmansiz, ithalat_odenen
    kart = [{"cari_kod": "320.50.101", "cari_doviz_cinsi": 1}]
    h = [dict(_h("320.50.101", 0, 260800, "2026-10-08", "ödeme"), cha_d_cins=1, cha_cari_cins=0),
         dict(_h("320.50.101", 1, 260800, "2026-12-31", "320-159 VİRMANI"), cha_d_cins=1, cha_cari_cins=0)]
    assert ithalat_odenen(cari_bakiyeleri(h, kart), kart) == 0
    assert ithalat_odenen(cari_bakiyeleri(donem_sonu_virmansiz(h, datetime.date(2026, 12, 31)), kart), kart) \
        == pytest.approx(260800)


# ── 9) Alınan destekler Mikro 602 ────────────────────────────────
def test_602_aylik_ve_usd():
    from kayranacc import mikro_alinan as MA
    s = [{"yil": 2026, "ay": 1, "hesap_kod": "602.02.001", "borc": 0, "alacak": 39678},
         {"yil": 2026, "ay": 1, "hesap_kod": "602.02.002", "borc": 100, "alacak": 1166346},
         {"yil": 2025, "ay": 12, "hesap_kod": "602.02.001", "borc": 0, "alacak": 999},     # 2026'dan önce: alınmaz
         {"yil": 2026, "ay": 2, "hesap_kod": "649.002", "borc": 0, "alacak": 23228}]      # 602 değil
    a = MA.aylik(s)
    assert a == {"2026-01": {"602.02.001": 39678.0, "602.02.002": 1166246.0}}
    r = MA.usd_satirlari(a, "2026-01", "2026-03", {"2026-01-10": 40.0, "2026-01-20": 42.0}, 45.0,
                         {"602.02.001": "MIO HİZMET"})
    assert [(x["hesap"], x["usd"]) for x in r] == [("602.02.001", pytest.approx(39678 / 41)),
                                                    ("602.02.002", pytest.approx(1166246 / 41))]
    assert r[0]["ad"] == "MIO HİZMET"


def test_alinan_destek_mikro_donemi_uygulama_kaydini_saymaz(monkeypatch):
    import kayranpm.ref_no as RN
    from kayranacc import mikro_alinan as MA
    monkeypatch.setattr(MA, "acik_mi", lambda: True)
    monkeypatch.setattr(MA, "mikro_satirlari", lambda b, e: [{"donem": "2026-02", "hesap": "602.02.001",
                                                               "ad": "MIO", "tl": 41000, "usd": 1000.0}])
    monkeypatch.setattr(RN, "get_alinan_destekler", lambda yil=None: [
        {"donem": "2025-12", "tutar": 500, "doviz": "USD", "firma": "MIO"},
        {"donem": "2026-02", "tutar": 750, "doviz": "USD", "firma": "MIO"}])          # Mikro'da da var → sayılmaz
    assert RN.alinan_destek_aralik_usd("2025-12", "2026-03") == pytest.approx(1500)
    marka, _kat, top = RN.alinan_destek_kirilim_usd("2025-12", "2026-03")
    assert top == pytest.approx(1500) and marka["MİKRO · MIO"] == pytest.approx(1000)
    ok, mesaj = RN.alinan_destek_ekle("MIO", "HİZMET", "2026-11", 750, "EUR")
    assert not ok and "Mikro" in mesaj


def test_mikro_okunamazsa_uygulama_kaydina_duser(monkeypatch):
    import kayranpm.ref_no as RN
    from kayranacc import mikro_alinan as MA
    monkeypatch.setattr(MA, "acik_mi", lambda: True)
    monkeypatch.setattr(MA, "mikro_satirlari", lambda b, e: None)
    monkeypatch.setattr(RN, "get_alinan_destekler", lambda yil=None: [{"donem": "2026-02", "tutar": 750,
                                                                       "doviz": "USD", "firma": "MIO"}])
    assert RN.alinan_destek_aralik_usd("2026-01", "2026-03") == pytest.approx(750)


def test_excel_ice_aktarim_mikro_donemini_atlar(monkeypatch):
    import pandas as pd
    import kayranpm.ref_no as RN
    from kayranacc import mikro_alinan as MA
    monkeypatch.setattr(MA, "acik_mi", lambda: True)
    eklenen = []
    monkeypatch.setattr(RN, "alinan_destek_ekle", lambda *a, **k: eklenen.append(a[2]) or (True, "ok"))
    df = pd.DataFrame({"FİRMA": ["MIO", "MIO"], "DÖNEM": ["2025-11", "2026-03"], "TUTAR": [750, 750]})
    e, atl, hata = RN.alinan_destek_excel_ice_aktar(df)
    assert (e, atl, hata) == (1, 1, []) and eklenen == ["2025-11"]
