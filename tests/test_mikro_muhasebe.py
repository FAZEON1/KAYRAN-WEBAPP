# -*- coding: utf-8 -*-
"""Mikro → muhasebe eşitleme (kayranacc/mikro_muhasebe.py) — saf hesaplar.

Rakamlar 21.10.2026 canlı verisinden: formüller eski değerlerle (uygulamadaki banka bakiyeleri,
19.10 cari Excel'i, ithalat ödeme takip, çek dökümü) karşılaştırılarak kuruldu.
"""
import sys
import types

import pytest

from kayranacc import mikro_muhasebe as M


def _h(**k):
    r = dict(cha_tip=0, cha_cari_cins=0, cha_kod="", cha_kasa_hizmet=0, cha_kasa_hizkod=None, cha_d_cins=0,
             cha_d_kur=1, cha_karsidcinsi=0, cha_karsid_kur=1, cha_meblag=0, cha_evrak_tip=0, cha_trefno=None,
             cha_tarihi="2026-10-01 00:00:00")
    r.update(k)
    return r


BANKA_KART = [
    {"ban_kod": "102.01.001", "ban_ismi": "İŞ BANKASI TL", "ban_doviz_cinsi": 0},
    {"ban_kod": "102.01.002", "ban_ismi": "ZİRAAT BANKASI TL", "ban_doviz_cinsi": 0},
    {"ban_kod": "102.01.003", "ban_ismi": "YAPI VE KREDİ TL HESAP", "ban_doviz_cinsi": 0},
    {"ban_kod": "102.01.004", "ban_ismi": "GARANTİ BANKASI A.Ş. TL", "ban_doviz_cinsi": 0},
    {"ban_kod": "102.01.005", "ban_ismi": "İŞ BANKASI 6046 TL HESAP", "ban_doviz_cinsi": 0},
    {"ban_kod": "102.01.006", "ban_ismi": "GARANTİ BANKASI A.Ş.-DBS", "ban_doviz_cinsi": 0},
    {"ban_kod": "102.01.007", "ban_ismi": "HALK BANKASI A.Ş.", "ban_doviz_cinsi": 0},
    {"ban_kod": "102.01.008", "ban_ismi": "HALK BANKASI VADELİ HESAP", "ban_doviz_cinsi": 0},
    {"ban_kod": "102.01.009", "ban_ismi": "YAPI KREDİ VADELİ HESAP", "ban_doviz_cinsi": 0},
    {"ban_kod": "102.05.001", "ban_ismi": "İŞ BANKASI USD", "ban_doviz_cinsi": 1},
    {"ban_kod": "102.05.002", "ban_ismi": "YAPI VE KREDİ USD HESAP", "ban_doviz_cinsi": 1},
    {"ban_kod": "102.05.003", "ban_ismi": "GARANTİ BANKASI A.Ş.USD", "ban_doviz_cinsi": 1},
    {"ban_kod": "102.05.004", "ban_ismi": "HALK BANKASI A.Ş. USD", "ban_doviz_cinsi": 1},
    {"ban_kod": "102.06.001", "ban_ismi": "YAPI VE KREDİ EURO HESAP", "ban_doviz_cinsi": 2},
    {"ban_kod": "102.10.002", "ban_ismi": "ZİRAAT BANKASI 5003 VADELİ HESAP", "ban_doviz_cinsi": 0},
    {"ban_kod": "102.20.001", "ban_ismi": "İŞ BANKASI YATIRIM HS.", "ban_doviz_cinsi": 0},
    {"ban_kod": "309.01.001", "ban_ismi": "İŞ BANK K.KART 4508 0311 9802 8825", "ban_doviz_cinsi": 0},
    {"ban_kod": "309.01.002", "ban_ismi": "YKB K.KART 5526 4591 1602 6701", "ban_doviz_cinsi": 0},
    {"ban_kod": "309.01.003", "ban_ismi": "HALKBANK K.KART ASIL KART-4988 5215 8067 5976 ", "ban_doviz_cinsi": 0},
]

UYGULAMA_BANKALARI = [
    {"id": 3, "hesap_adi": "YAPI KREDİ BANKASI - USD", "para_birimi": "USD", "bakiye": "103788.57"},
    {"id": 4, "hesap_adi": "YAPI KREDİ BANKASI - TL", "para_birimi": "TL", "bakiye": "252219.64"},
    {"id": 5, "hesap_adi": "YAPI KREDİ BANKASI - EURO", "para_birimi": "EUR", "bakiye": "0.20"},
    {"id": 6, "hesap_adi": "HALK BANKASI - TL", "para_birimi": "TL", "bakiye": "22689.35"},
    {"id": 7, "hesap_adi": "HALK BANKASI - VADELİ", "para_birimi": "TL", "bakiye": "0.00"},
    {"id": 8, "hesap_adi": "HALK BANKASI - USD", "para_birimi": "USD", "bakiye": "57333.88"},
    {"id": 9, "hesap_adi": "GARANTİ BANKASI - USD", "para_birimi": "USD", "bakiye": "0.00"},
    {"id": 10, "hesap_adi": "GARANTİ BANKASI - TL", "para_birimi": "TL", "bakiye": "0.00"},
    {"id": 11, "hesap_adi": "GARANTİ BANKASI DBS - TL", "para_birimi": "TL", "bakiye": "0.00"},
    {"id": 12, "hesap_adi": "İŞ BANKASI - TL", "para_birimi": "TL", "bakiye": "11119.29"},
    {"id": 13, "hesap_adi": "İŞ BANKASI - USD", "para_birimi": "USD", "bakiye": "0.00"},
]


def test_banka_eslesmesi_gercek_adlarla():
    es = M.banka_eslestir(UYGULAMA_BANKALARI, BANKA_KART)
    assert es == {3: "102.05.002", 4: "102.01.003", 5: "102.06.001", 6: "102.01.007", 7: "102.01.008",
                  8: "102.05.004", 9: "102.05.003", 10: "102.01.004", 11: "102.01.006", 12: "102.01.001",
                  13: "102.05.001"}


def test_dovizli_banka_kur_farki_fisi_doviz_bakiyesini_degistirmez():
    """Halk USD: kur farkı virmanı (evrak 59) TL değer düzeltmesidir; sayılınca 57.333,88 yerine 54.000,94
    çıkıyordu. Karşı hesabı banka olan TL masraf ($ karşılığı) bakiyeden düşer."""
    kart = [{"ban_kod": "102.05.004", "ban_doviz_cinsi": 1}]
    h = [
        _h(cha_cari_cins=2, cha_kod="102.05.004", cha_tip=0, cha_d_cins=1, cha_meblag=57341.88),
        _h(cha_cari_cins=2, cha_kod="102.05.004", cha_tip=1, cha_d_cins=1, cha_d_kur=46.5551,
           cha_evrak_tip=59, cha_meblag=2639.00),
        # banka masrafı: gider hesabı borç, karşı hesap banka (alacak) — TL tutar, karşı döviz USD
        _h(cha_cari_cins=5, cha_kod="770.04.012", cha_tip=0, cha_kasa_hizmet=2, cha_kasa_hizkod="102.05.004",
           cha_d_cins=0, cha_karsidcinsi=1, cha_karsid_kur=46.9253, cha_meblag=375.4024),
    ]
    assert M.banka_bakiyeleri(h, kart)["102.05.004"] == pytest.approx(57333.88, abs=0.01)


def test_tl_banka_hareket_kuruyla_tl_ye_cevrilir():
    kart = [{"ban_kod": "102.01.001", "ban_doviz_cinsi": 0}]
    h = [
        _h(cha_cari_cins=2, cha_kod="102.01.001", cha_tip=0, cha_d_cins=0, cha_meblag=10000),
        # USD tahsilat TL hesaba: 100 $ × 49 = 4.900 TL (karşı hesap: banka)
        _h(cha_cari_cins=0, cha_kod="120.01.003", cha_tip=1, cha_kasa_hizmet=2, cha_kasa_hizkod="102.01.001",
           cha_d_cins=1, cha_d_kur=49, cha_meblag=100),
        _h(cha_cari_cins=0, cha_kod="336.004", cha_tip=0, cha_kasa_hizmet=2, cha_kasa_hizkod="102.01.001",
           cha_meblag=7129.80),
    ]
    assert M.banka_bakiyeleri(h, kart)["102.01.001"] == pytest.approx(10000 + 4900 - 7129.80)


CARI_KART = [
    {"cari_kod": "120.01.003", "cari_unvan1": "VATAN", "cari_doviz_cinsi": 1},
    {"cari_kod": "120.02.020", "cari_unvan1": "TL MÜŞTERİ", "cari_doviz_cinsi": 0},
    {"cari_kod": "340.01.001", "cari_unvan1": "AVANS", "cari_doviz_cinsi": 0},
    {"cari_kod": "320.50.101", "cari_unvan1": "INNOVISION", "cari_doviz_cinsi": 1},
    {"cari_kod": "320.50.003", "cari_unvan1": "LCCGAME", "cari_doviz_cinsi": 1},
    {"cari_kod": "320.05.003", "cari_unvan1": "NMT LOJİSTİK", "cari_doviz_cinsi": 1},
    {"cari_kod": "320.01.001", "cari_unvan1": "DEY", "cari_doviz_cinsi": 1},
]


def test_cari_ozeti_120_ve_340_alinir_320_alinmaz():
    cb = {"120.01.003": 1500.0, "120.02.020": -200.0, "340.01.001": -38713627.13, "320.50.101": 260800.0,
          "320.01.001": -5148.0}
    oz = M.cari_ozeti(cb, CARI_KART)
    assert oz["alacak"] == {"usd": 1500.0, "tl": 0.0, "eur": 0.0}
    assert oz["borc"] == {"usd": 0.0, "tl": 38713827.13, "eur": 0.0}


def test_ithalat_odenen_yurt_disi_tedarikci_avanslari():
    """19.10: 320.50 pozitif USD bakiyeleri toplamı = 622.888,27 (İthalat ödeme takip Excel'i). Yurt içi
    lojistik (320.05) ve borçlu olduğumuz tedarikçi (negatif) sayılmaz."""
    cb = {"320.50.101": 260800.0, "320.50.003": 54124.35, "320.50.008": -10.0, "320.05.003": 3.63,
          "320.01.001": -5148.0}
    kart = CARI_KART + [{"cari_kod": "320.50.008", "cari_doviz_cinsi": 1}]
    assert M.ithalat_odenen(cb, kart) == pytest.approx(314924.35)


def test_cari_bakiyesi_kur_farki_haric_karsi_dovizle():
    h = [
        _h(cha_kod="120.01.003", cha_tip=0, cha_d_cins=1, cha_meblag=1000),       # satış faturası $
        _h(cha_kod="120.01.003", cha_tip=1, cha_d_cins=0, cha_d_kur=1, cha_karsidcinsi=1, cha_karsid_kur=49,
           cha_meblag=9800),                                                     # TL tahsilat = 200 $
        _h(cha_kod="120.01.003", cha_tip=1, cha_d_cins=1, cha_evrak_tip=59, cha_meblag=14624.55),  # kur farkı
    ]
    assert M.cari_bakiyeleri(h, CARI_KART)["120.01.003"] == pytest.approx(800.0)


def test_cek_satirlari_verildigi_cari_ve_durum():
    cekler = [
        {"sck_tip": 2, "sck_refno": "FC-1", "sck_no": "1138988", "sck_vade": "2026-11-13 00:00:00", "sck_tutar": 8450,
         "sck_doviz": 1, "sck_odenen": 0, "sck_nerede_cari_cins": 0, "sck_nerede_cari_kodu": "320.05.003",
         "sck_sahip_cari_kodu": "102.05.002", "sck_bankano": "102.05.002"},
        {"sck_tip": 2, "sck_refno": "FC-2", "sck_no": "9904121", "sck_vade": "2025-12-12", "sck_tutar": 500000,
         "sck_doviz": 0, "sck_odenen": 500000, "sck_nerede_cari_cins": 2, "sck_nerede_cari_kodu": "102.01.003",
         "sck_sahip_cari_kodu": "102.01.003", "sck_bankano": "102.01.003"},
        {"sck_tip": 1, "sck_refno": "MC-1", "sck_no": "X", "sck_tutar": 5, "sck_doviz": 0},   # müşteri çeki
    ]
    h = [_h(cha_trefno="FC-1", cha_evrak_tip=67, cha_kod="320.05.003", cha_tarihi="2026-09-30 00:00:00"),
         _h(cha_trefno="FC-2", cha_evrak_tip=67, cha_kod="320.02.068", cha_tarihi="2025-12-09 00:00:00"),
         _h(cha_trefno="FC-2", cha_evrak_tip=38, cha_cari_cins=2, cha_kod="102.01.003")]
    s = M.cek_satirlari(cekler, h, {"320.05.003": "NMT LOJİSTİK", "320.02.068": "X TEDARİK"},
                        {"102.05.002": "YAPI VE KREDİ USD HESAP", "102.01.003": "YAPI VE KREDİ TL HESAP"})
    assert [c["cek_no"] for c in s] == ["9904121", "1138988"]
    odendi, ciro = s
    assert (odendi["durum"], odendi["kalan"], odendi["ch_ismi"], odendi["tarih"]) == \
        ("Ödendi", 0.0, "X TEDARİK", "2025-12-09")
    assert (ciro["durum"], ciro["kalan"], ciro["para_birimi"], ciro["banka"], ciro["vade"]) == \
        ("Ciro edildi", 8450.0, "USD", "YAPI VE KREDİ USD HESAP", "2026-11-13")
    assert M.cek_ozeti(s) == {"USD": (1, 8450.0)}


def _veri():
    return {"hareket": [_h(cha_cari_cins=2, cha_kod="102.05.004", cha_tip=0, cha_d_cins=1, cha_meblag=57333.88),
                        _h(cha_kod="120.01.003", cha_tip=0, cha_d_cins=1, cha_meblag=100)],
            "banka_kart": BANKA_KART, "cari_kart": CARI_KART, "cek": []}


def test_plan_yalniz_degisen_bankayi_yazar_eslesmeyen_mikro_hesabi_eklemez():
    p = M.plan_yap(_veri(), UYGULAMA_BANKALARI, [], None, None)
    degisen = {b["id"]: b["sonra"] for b in p["banka"] if b["degisir"]}
    # Halk USD tutuyor (yazılmaz); Mikro'da hareketi olmayan hesaplar 0 olur
    assert 8 not in degisen
    assert degisen[3] == 0.0 and degisen[12] == 0.0
    assert p["banka_disarida"] == []
    assert p["cari"]["alacak"]["usd"] == 100.0 and p["cari_degisir"] and p["ithalat_degisir"]
    assert not p["cek_degisir"]


def test_plan_ayni_veride_hicbir_sey_degismez():
    v = _veri()
    p1 = M.plan_yap(v, UYGULAMA_BANKALARI, [], None, None)
    bankalar = [dict(b, bakiye=x["sonra"]) for b, x in zip(UYGULAMA_BANKALARI, p1["banka"])]
    p2 = M.plan_yap(v, bankalar, p1["cek"], p1["cari"], p1["ithalat"])
    assert not any(b["degisir"] for b in p2["banka"])
    assert not (p2["cek_degisir"] or p2["cari_degisir"] or p2["ithalat_degisir"])


def test_mikro_esitlemesi_acikken_cari_ve_ithalat_hatirlatmasi_cikmaz(monkeypatch):
    """Excel yüklemesi kalkınca 'Toplam aktifler · cari / ithalat gecikti' uyarısı da kalkmalı."""
    from shared import yukleme_takvimi as Y
    sahte = types.ModuleType("kayranacc.mikro_muhasebe")
    sahte.acik_mi = lambda: True
    monkeypatch.setitem(sys.modules, "kayranacc.mikro_muhasebe", sahte)
    monkeypatch.setattr(Y, "_ayar", lambda anahtar, varsayilan: varsayilan)
    monkeypatch.setattr(Y, "_OKUYUCU", {})
    anahtarlar = {d["anahtar"] for d in Y.durumlar()}
    assert "aktif_cari" not in anahtarlar and "aktif_ithalat" not in anahtarlar
    assert "aktif_stok" in anahtarlar          # stok değeri şimdilik dosyayla
