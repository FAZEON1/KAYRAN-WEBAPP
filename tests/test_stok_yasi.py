# -*- coding: utf-8 -*-
"""Stok yaşı — FIFO (kayranpm/stok_yasi.py, Ekim 2026).

Yaş mal depoya girdiği gün (teslim tarihi) başlar; en eski parti önce satılır, elde kalan stok en
yeni partilerdir. Bizim stok: satılabilir depolar; müşteri stoğu: son rapor ↔ o müşteriye satışlar.
"""
from datetime import date

import kayranpm.stok_yasi as Y
from shared.utils import sku_anahtar, normalize_tr

BUGUN = date(2026, 10, 4)


def test_fifo_en_yeniler_elde_kalir():
    p = [{"tarih": "2026-01-10", "adet": 100}, {"tarih": "2026-09-20", "adet": 50},
         {"tarih": "2026-06-01", "adet": 80}]
    kal, kaps = Y.fifo_kalan(p, 100)
    assert [(k["tarih"], k["kalan"]) for k in kal] == [("2026-06-01", 50), ("2026-09-20", 50)]
    assert kaps == 0


def test_fifo_stok_partilerden_fazla_kapsanmayan():
    kal, kaps = Y.fifo_kalan([{"tarih": "2026-09-01", "adet": 30}], 45)
    assert [k["kalan"] for k in kal] == [30] and kaps == 15
    assert Y.fifo_kalan([], 0) == ([], 0.0) and Y.fifo_kalan(None, 10) == ([], 10.0)
    assert Y.fifo_kalan([{"tarih": "", "adet": 5}, {"tarih": "2026-01-01", "adet": 0}], 3) == ([], 3.0)


def test_yas_ozeti_agirlikli_ortalama_ve_gruplar():
    kal = [{"tarih": "2026-06-01", "kalan": 50}, {"tarih": "2026-09-20", "kalan": 50}]
    o = Y.yas_ozeti(kal, 10, BUGUN)
    assert o["en_eski_gun"] == 125 and o["en_eski_tarih"] == "2026-06-01" and o["en_yeni_gun"] == 14
    assert round(o["ort_gun"], 1) == round((50 * 125 + 50 * 14) / 100, 1)
    assert o["gruplar"]["91–180 gün"] == 50 and o["gruplar"]["0–30 gün"] == 50
    assert o["gruplar"][Y.KAYITSIZ] == 10 and o["stok"] == 110 and o["kapsanan"] == 100
    assert Y.yas_ozeti([], 5, BUGUN)["ort_gun"] is None


def test_grup_sinirlari():
    assert [Y.grup_adi(g) for g in (0, 30, 31, 60, 61, 90, 91, 180, 181, 900)] == \
        ["0–30 gün", "0–30 gün", "31–60 gün", "31–60 gün", "61–90 gün", "61–90 gün",
         "91–180 gün", "91–180 gün", "180+ gün", "180+ gün"]


def test_bizim_partiler_yalniz_teslim_alinan_teslim_tarihiyle():
    dosyalar = [{"id": 1, "durum": "Teslim Alındı", "teslim_tarihi": "2026-05-02", "tarih": "2026-03-01",
                 "dosya_no": "D1", "teslim_deposu": "MERKEZ DEPO"},
                {"id": 2, "durum": "Antrepoda", "teslim_tarihi": None, "tarih": "2026-08-01", "dosya_no": "D2"},
                {"id": 3, "durum": "Teslim Alındı", "teslim_tarihi": "2026-07-03", "dosya_no": "YI-1",
                 "alim_turu": "yurtici"}]
    kalemler = [{"dosya_id": 1, "sku": "Fazeon X24", "adet": 10}, {"dosya_id": 2, "sku": "X24", "adet": 99},
                {"dosya_id": 3, "sku": "FAZE1", "adet": 500}, {"dosya_id": 1, "sku": "X24", "adet": 0}]
    p = Y.bizim_partiler(dosyalar, kalemler, sku_anahtar)
    assert p == {"X24": [{"tarih": "2026-05-02", "adet": 10, "belge": "D1", "tur": "ithalat",
                          "depo": "MERKEZ DEPO"}],
                 "FAZE1": [{"tarih": "2026-07-03", "adet": 500, "belge": "YI-1", "tur": "yurtici", "depo": ""}]}


def test_musteri_partileri_cari_adindan_firma_koduna():
    tam = {"VATAN": "VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI",
           "ITOPYA": "EERA ELEKTRONİK TİCARET VE BİLİŞİM HİZMETLERİ ANONİM ŞİRKETİ"}
    bul = Y.firma_cozucu(["VATAN", "ITOPYA"], lambda k: tam.get(k, k), normalize_tr)
    assert bul("Eera Elektronik Ticaret ve Bilişim Hizmetleri Anonim Şirketi") == "ITOPYA"
    assert bul("VATAN") == "VATAN" and bul("BAŞKA FİRMA") is None
    sat = [{"kanal": tam["VATAN"], "sku": "Fazeon X24", "adet": 20, "tarih": "2026-09-01", "siparis_no": "S1"},
           {"kanal": tam["VATAN"], "sku": "X24", "adet": -3, "tarih": "2026-09-02"},
           {"kanal": "BAŞKA FİRMA", "sku": "X24", "adet": 5, "tarih": "2026-09-03"}]
    assert Y.musteri_partileri(sat, bul, sku_anahtar) == \
        {"VATAN": {"X24": [{"tarih": "2026-09-01", "adet": 20, "belge": "S1"}]}}


def test_urun_yasi_ve_toplam():
    o1, kal = Y.urun_yasi(60, [{"tarih": "2026-09-04", "adet": 40}, {"tarih": "2026-03-08", "adet": 40}], BUGUN)
    assert [k["kalan"] for k in kal] == [20, 40] and o1["en_eski_gun"] == 210
    o2, _ = Y.urun_yasi(5, [], BUGUN)
    t = Y.toplam_ozet([o1, o2])
    assert t["stok"] == 65 and t["kapsanmayan"] == 5 and t["gruplar"]["180+ gün"] == 20
    assert round(t["ort_gun"], 2) == round(o1["ort_gun"], 2)
