# -*- coding: utf-8 -*-
"""Mikro → aylık gider tablosu (kayranacc/mikro_gider.py). Rakamlar 2026 Ocak canlı verisinden: muhasebenin
yüklediği gider tablosunun Ocak sütunu (toplam 5.147.403,06) Mikro hesaplarından kuruşu kuruşuna çıkmalı."""
import sys
import types
from datetime import date

import pytest

from kayranacc import mikro_gider as G

OCAK = """689.001:48318.79 689.002:2395.63 689.003:431.46 689.005:2559.75 689.006:86140.29 760.01.001:856164.17
760.01.002:197101.91 760.01.003:18124.31 760.03.002:6848.27 760.03.003:116958.33 760.03.005:670278.57
760.03.008:6000.00 760.03.018:381677.50 760.04.001:32500.00 760.04.004:262.50 760.04.005:532020.35
760.04.007:27089.41 760.04.011:1000.00 760.04.016:65013.85 760.04.017:13000.00 760.04.020:948228.32
760.04.022:327912.32 760.04.024:23327.26 760.04.025:283.10 760.04.026:3000.00 770.01.001:797473.70
770.01.002:172367.35 770.01.003:14495.50 770.01.005:103305.09 770.01.011:3780.00 770.01.014:3010.00
770.01.015:149022.41 770.02.001:320340.00 770.03.001:11571.51 770.03.005:5000.00 770.03.013:37640.00
770.03.015:2909.72 770.03.016:55940.68 770.03.018:41.58 770.03.019:7500.00 770.04.003:30955.91
770.04.004:3334.33 770.04.005:5001.56 770.04.007:10150.00 770.04.008:17012.15 770.04.012:47913.23
770.04.013:36916.88 770.04.014:27708.33 770.05.001:2521.70 770.05.002:5001.30 770.05.003:1015.11
770.05.004:75.00 780.79.004:1068.30 780.79.006:20995.26 780.79.007:162841.01 600.01.001:-70477042.71"""

# Muhasebenin 2026 tablosundaki Ocak değerleri (gider_tablosu_2026)
EXCEL_OCAK = {
    "İŞÇİ ÜCRET GİDERLERİ - HUZUR HAKKI": 2204749.35, "PERSONEL YEMEK GİDERLERİ": 126632.35,
    "MERKEZ OFİS KİRA GİDERLERİ": 320340, "BİLGİ İŞLEM GİDERLERİ": 5000, "YAZILIM DESTEK GİDERİ": 55940.68,
    "SERBEST MESLEK GİDERLERİ AVUKAT MUHASEBE VB": 7500, "ORTAK KATILIM GİDERLERİ": 10150,
    "BEYANNAME DAMGA VERGİSİ": 2521.7, "BELEDİYE REKLAM İLAN VE TABELA VE ÇEVRE TEM.VERGİSİ": 5001.3,
    "İŞ GÜVENLİĞİ VE İŞYERİ HEKİMLİĞİ GİDERLERİ": 3780, "LOJİSTİK VE NAKLİYE GİDERLERİ": 670278.57,
    "AMBALAJ VE PAKETLEME GİDERLERİ": 6000, "ÜRÜN SATIŞI İÇİN DIŞARDAN SAĞ.FAY VE HİZ": 381677.5,
    "ÜRÜN REKLAM VE TANITIM GİDERLERİ": 32500, "KARGO VE POSTA GİDERLERİ": 41.58, "BANKA GİDERLERİ": 47913.23,
    "NOTER VE TESCİL HARÇLARI": 1015.11, "BANKA MASRAF B.S.M.V.": 1068.3, "TL KREDİ FAİZLERİ": 20995.26,
    "KREDİ KARTI TAHSİLATLARI KOMİSYONLARI": 162841.01, "KKEG CEZALAR, GİDER KSISITLAMASI VB.": 139845.92,
    "HABERLEŞME GİDERLERİ": 6848.27, "ARAÇ KİRALAMA GİDERLERİ": 144666.66, "SEYAHAT GİDERLERİ": 569199.73,
    "ARAÇ YAKIT VE DİĞER TÜM GİDERLERİ": 46333.46, "SATIŞ PAZ.DESTEK GİD.": 1000,
    "PERSONEL YURTİÇİ YOL GİDERLERİ": 6010, "ELEKTRİK VE SU VE GAZ GİDERLERİ": 11571.51,
    "OFİS TAMİR-BAKIM ONARIM GİDERLERİ": 37640, "TEMSİL, AĞIRLAMA VE İKRAM GİDERLERİ": 95969.76,
    "KIRTASİYE GİDERLERİ": 5284.66, "ÇEŞİTLİ OFİS GİDERLERİ": 17012.15, "TİCARET ODASI AİDAT VE GİDERLERİ": 75,
}


def _satirlar(metin, ay=1, yil=2026):
    out = []
    for p in metin.split():
        kod, v = p.split(":")
        v = float(v)
        out.append({"yil": yil, "ay": ay, "hesap_kod": kod, "borc": max(v, 0), "alacak": max(-v, 0)})
    return out


def test_ocak_muhasebenin_tablosuyla_kurusu_kurusuna():
    t = G.gider_tablosu(_satirlar(OCAK), 2026)
    ocak = {d[1]: d[2][0] for d in t["detay"]}
    assert ocak == pytest.approx(EXCEL_OCAK, abs=0.005)
    assert sum(t["kat"][k][0] for k in G.KATEGORILER) == pytest.approx(5147403.06, abs=0.01)
    assert t["kat"]["Sabit"][0] == pytest.approx(2741615.38, abs=0.01)


def test_satis_destek_bedeli_ve_gider_disi_hesap_alinmaz_yeni_hesap_kaybolmaz():
    s = _satirlar("760.04.019:9332098.11 621.01.001:100 770.09.001:500", ay=3)
    t = G.gider_tablosu(s, 2026, hesap_adlari={"770.09.001": "YENİ GİDER"})
    assert t["detay"] == [["Yarı Değişken", "YENİ GİDER", [0, 0, 500.0] + [0.0] * 9]]


def test_bitmemis_ay_alinmaz():
    s = _satirlar("770.02.001:320340", ay=9) + _satirlar("770.02.001:320340", ay=10)
    sinir = G.ay_siniri(2026, date(2026, 10, 21))
    assert sinir == 9
    kira = G.gider_tablosu(s, 2026, sinir)["detay"][0][2]
    assert kira[8] == 320340 and kira[9] == 0
    assert G.ay_siniri(2025, date(2026, 10, 21)) == 12


def test_esit_mi_ve_karsilastir():
    a = G.gider_tablosu(_satirlar(OCAK), 2026)
    b = {"kat": a["kat"], "detay": [list(d) for d in a["detay"]]}
    assert G.esit_mi(a, b)
    b["detay"][0] = [b["detay"][0][0], b["detay"][0][1], [b["detay"][0][2][0] + 10] + b["detay"][0][2][1:]]
    assert not G.esit_mi(a, b)
    k = G.karsilastir(b, a)
    assert k["kalem"][0][1] == "İŞÇİ ÜCRET GİDERLERİ - HUZUR HAKKI"
    assert not G.esit_mi({}, a)


def test_gider_eslesmesi_acikken_gider_hatirlatmasi_cikmaz(monkeypatch):
    from shared import yukleme_takvimi as Y
    sahte = types.ModuleType("kayranacc.mikro_gider")
    sahte.acik_mi = lambda: True
    monkeypatch.setitem(sys.modules, "kayranacc.mikro_gider", sahte)
    monkeypatch.setattr(Y, "_ayar", lambda anahtar, varsayilan: varsayilan)
    monkeypatch.setattr(Y, "_OKUYUCU", {})
    assert "gider_tablosu" not in {d["anahtar"] for d in Y.durumlar()}
