# -*- coding: utf-8 -*-
"""Kullanıcı (22.10.2026): "Mikro'ya banka hareketi işledim; bakiye güncellendi ama hareketi Kayran'da göremedim."
Hesap penceresinde Mikro hareketleri (kayranacc/mikro_banka_hareket.py), bakiyeyle aynı kuralla. Canlı: Halkbank TL
22.10 dört hareket (Protek 100.000, Master gümrük KDV 844.163,75 …), son bakiye −823.432,21 TL."""
import pytest

try:
    from kayranacc import mikro_banka_hareket as BH
except ImportError:          # eski kodda yok
    BH = None
pytestmark = pytest.mark.skipif(BH is None, reason="kayranacc.mikro_banka_hareket yok")

BANKA = "102.01.007"


def _h(guid, tarih, tip, meblag, kod=BANKA, cins=2, karsi="", karsi_cins=-1, evrak=35, d_cins=0, d_kur=1.0, ack=""):
    return {"cha_guid": guid, "cha_tarihi": tarih, "cha_tip": tip, "cha_meblag": meblag, "cha_kod": kod,
            "cha_cari_cins": cins, "cha_kasa_hizkod": karsi, "cha_kasa_hizmet": karsi_cins, "cha_evrak_tip": evrak,
            "cha_d_cins": d_cins, "cha_d_kur": d_kur, "cha_karsidcinsi": 0, "cha_karsid_kur": 1.0, "cha_aciklama": ack}


def test_giris_cikis_ve_geriye_bakiye():
    h = [_h("a", "2026-10-21", 0, 5000, ack="VATAN GELEN"),                                     # banka borç: giriş
         _h("b", "2026-10-22", 0, 100000, kod="320.02.047", cins=0, karsi=BANKA, karsi_cins=2,
            ack="HALKBANK TL - PROTEK GÜMRÜK GİDEN"),                                            # cari borç: çıkış
         _h("c", "2026-10-22", 0, 32.43, kod="MASTER", cins=9, karsi=BANKA, karsi_cins=2, d_cins=1, d_kur=49.5),
         _h("d", "2026-10-20", 0, 7777, kod="320.02.047", cins=0, karsi=BANKA, karsi_cins=2, evrak=67),  # çek verildi
         _h("e", "2026-10-22", 0, 1, kod="120.01.003", cins=0)]                                   # başka hesap
    s = BH.hareket_listesi(h, BANKA, 0, -823432.21, {"320.02.047": "PROTEK GÜMRÜK"})
    assert [(r["tarih"], r["giris"], r["cikis"]) for r in s] == [
        ("2026-10-22", 0.0, pytest.approx(1605.29)), ("2026-10-22", 0.0, 100000.0), ("2026-10-21", 5000.0, 0.0)]
    assert s[0]["bakiye"] == -823432.21
    assert s[1]["bakiye"] == pytest.approx(-823432.21 + 1605.285) and s[1]["karsi"] == "PROTEK GÜMRÜK"
    assert s[2]["bakiye"] == pytest.approx(-823432.21 + 1605.285 + 100000)
