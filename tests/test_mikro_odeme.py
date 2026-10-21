# -*- coding: utf-8 -*-
"""Haftalık ödeme listesi — Mikro önerisi (kayranacc/mikro_odeme.py, Ekim 2026).

Kullanıcı: "Haftalık ödeme listesi - Mikro'daki vadeli borçlardan ve çeklerden hazır öneri doldur."
DEY ve UPS örnekleri 21.10.2026 canlı verisinden (aktif hafta "19.10.2026 GÜNCEL ÖDEME LİSTESİ" ile aynı tutar).
"""
import importlib.util
import sys
import types
from datetime import date
from pathlib import Path

import pytest

from kayranacc import mikro_muhasebe as M
from kayranacc import mikro_odeme as O

KOK = Path(__file__).resolve().parent.parent


def _h(**k):
    r = dict(cha_tip=1, cha_cari_cins=0, cha_kod="320.02.001", cha_d_cins=0, cha_d_kur=1, cha_karsidcinsi=0,
             cha_karsid_kur=1, cha_meblag=0, cha_evrak_tip=0, cha_evrakno_seri="A", cha_evrakno_sira=1,
             cha_belge_no=None, cha_tarihi="2026-10-01T00:00:00", cha_vade=0, cha_aciklama="")
    r.update(k)
    return r


KART = [{"cari_kod": "320.02.001", "cari_unvan1": "ÖRNEK TEDARİK A.Ş.", "cari_doviz_cinsi": 0},
        {"cari_kod": "320.01.001", "cari_unvan1": "DEY ELEKTRONİK BİLİŞİM HİZMETLERİ LİMİTED ŞİRKETİ",
         "cari_doviz_cinsi": 1},
        {"cari_kod": "320.50.001", "cari_unvan1": "AGI TECHNOLOGY CO., LTD.", "cari_doviz_cinsi": 1},
        {"cari_kod": "120.01.001", "cari_unvan1": "MÜŞTERİ A.Ş.", "cari_doviz_cinsi": 0},
        {"cari_kod": "340.01.001", "cari_unvan1": "AVANS VEREN MÜŞTERİ", "cari_doviz_cinsi": 0},
        {"cari_kod": "336.009", "cari_unvan1": "EURO HİZMET", "cari_doviz_cinsi": 2}]

# DEY ELEKTRONİK (320.01.001, USD hesap) — 21.10.2026 Mikro hareketleri birebir. Faturalar 1.548 $ (DYI-717,
# vade 0) + 3.600 $ (DEY-2078) + 5.148 $ (hesaplar arası virman, 30.12.2025); ödemeler 774 + 774 + 3.600 $;
# kur farkı fişleri (evrak 59) USD bakiyeyi değiştirmez. Açık: 30.12.2025 vadeli 5.148 $ — aktif haftadaki
# "DEY ELEKTRONİK … 5.148 $" satırı.
DEY = [
    _h(cha_kod="320.01.001", cha_tip=1, cha_d_cins=1, cha_d_kur=44.3841, cha_meblag=176.509748948825,
       cha_evrak_tip=59, cha_evrakno_seri=None, cha_evrakno_sira=120, cha_tarihi="2026-03-31T00:00:00",
       cha_vade=20260331),
    _h(cha_kod="320.01.001", cha_tip=1, cha_d_cins=1, cha_d_kur=42.8542, cha_meblag=5148, cha_evrak_tip=33,
       cha_evrakno_seri=None, cha_evrakno_sira=246, cha_tarihi="2025-12-30T00:00:00", cha_vade=0),
    _h(cha_kod="320.01.001", cha_tip=0, cha_d_cins=1, cha_d_kur=41.1816, cha_meblag=3600, cha_evrak_tip=57,
       cha_evrakno_seri=None, cha_evrakno_sira=15, cha_tarihi="2025-09-09T00:00:00", cha_vade=0),
    _h(cha_kod="320.01.001", cha_tip=1, cha_d_cins=1, cha_d_kur=41.1816, cha_meblag=3600, cha_evrak_tip=0,
       cha_evrakno_seri="DEY", cha_evrakno_sira=2078, cha_tarihi="2025-09-09T00:00:00", cha_vade=20250909),
    _h(cha_kod="320.01.001", cha_tip=0, cha_d_cins=1, cha_d_kur=35.3356, cha_meblag=774.000158480399,
       cha_evrak_tip=65, cha_evrakno_seri=None, cha_evrakno_sira=3, cha_tarihi="2025-04-30T00:00:00",
       cha_vade=20250430),
    _h(cha_kod="320.01.001", cha_tip=0, cha_d_cins=1, cha_d_kur=35.3356, cha_meblag=773.999875479686,
       cha_evrak_tip=65, cha_evrakno_seri=None, cha_evrakno_sira=4, cha_tarihi="2025-05-01T00:00:00",
       cha_vade=20250501),
    _h(cha_kod="320.01.001", cha_tip=1, cha_d_cins=1, cha_d_kur=35.3356, cha_karsidcinsi=1, cha_karsid_kur=35.3356,
       cha_meblag=1548, cha_evrak_tip=0, cha_evrakno_seri="DYI", cha_evrakno_sira=717,
       cha_tarihi="2025-01-11T00:00:00", cha_vade=0),
    _h(cha_kod="320.01.001", cha_tip=1, cha_d_cins=1, cha_d_kur=1, cha_meblag=0.01, cha_evrak_tip=59,
       cha_evrakno_seri="X", cha_evrakno_sira=14, cha_tarihi="2026-06-30T00:00:00", cha_vade=0),
]


# ── Vade ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("vade, planlar, beklenen, kesin", [
    (20261022, None, date(2026, 10, 22), True),        # yyyymmdd
    (-30, None, date(2026, 10, 31), True),             # negatif: fatura tarihinden gün
    (0, None, date(2026, 10, 1), True),                # peşin
    (8, {8: 15}, date(2026, 10, 16), True),            # ödeme planı 8 = 15 gün
    (8, None, date(2026, 10, 1), False),               # plan günü bilinmiyor → fatura tarihi, tahmini
])
def test_vade_cha_vade_uc_anlami(vade, planlar, beklenen, kesin):
    d, _kaynak, k = O.vade_bul(_h(cha_vade=vade), planlar)
    assert (d, k) == (beklenen, kesin)


def test_hafta_araligi_ve_adi():
    assert O.hafta_araligi(date(2026, 10, 21)) == (date(2026, 10, 19), date(2026, 10, 25))
    assert O.hafta_araligi(date(2026, 10, 25), 1) == (date(2026, 10, 26), date(2026, 11, 1))
    # mevcut hafta adlarıyla aynı biçim → aynı adlı hafta uyarısı çalışır
    from kayranacc.excel_islemler import ayni_hafta
    ad = O.hafta_adi(date(2026, 10, 19))
    assert ad == "19.10.2026 GÜNCEL ÖDEME LİSTESİ"
    assert ayni_hafta(ad, [{"id": 61, "hafta_adi": "19.10.2026 GÜNCEL ÖDEME LİSTESİ"}])["id"] == 61


# ── Açık kalemler (FIFO) ───────────────────────────────────────────
def test_dey_gercek_hareketler_acik_5148_dolar():
    k = O.acik_kalemler(DEY, KART)
    assert [(r["vade"], r["acik"], r["doviz"]) for r in k] == [(date(2025, 12, 30), 5148.0, 1)]
    assert M.cari_bakiyeleri(DEY, KART)["320.01.001"] == -5148.0


def test_odeme_en_eski_vadeyi_kapatir():
    h = [_h(cha_meblag=100, cha_vade=20261001, cha_evrakno_sira=1),
         _h(cha_meblag=200, cha_vade=20261022, cha_evrakno_sira=2),
         _h(cha_meblag=300, cha_vade=20261105, cha_evrakno_sira=3),
         _h(cha_tip=0, cha_meblag=250, cha_evrak_tip=35, cha_tarihi="2026-10-20T00:00:00", cha_vade=20261020)]
    k = O.acik_kalemler(h, KART)
    assert [(r["vade"].isoformat(), r["acik"]) for r in k] == [("2026-10-22", 50.0), ("2026-11-05", 300.0)]
    # açık kalemlerin toplamı = −bakiye (Mikro'da doğrulanmış bakiye formülü)
    assert sum(r["acik"] for r in k) == -M.cari_bakiyeleri(h, KART)["320.02.001"]


def test_alacakli_oldugumuz_ve_musteri_hesaplari_alinmaz():
    h = [_h(cha_meblag=100),                                   # tedarikçi faturası
         _h(cha_tip=0, cha_meblag=150, cha_evrak_tip=35),      # fazla ödeme → avans, borç yok
         _h(cha_kod="120.01.001", cha_meblag=500),             # müşteri hesabı (eksi bakiye = müşteri avansı)
         _h(cha_kod="340.01.001", cha_meblag=700)]             # alınan sipariş avansı
    assert O.acik_kalemler(h, KART) == []


def test_doviz_hesapta_tl_hareket_kurla_cevrilir():
    h = [_h(cha_kod="320.50.001", cha_d_cins=0, cha_d_kur=1, cha_karsidcinsi=1, cha_karsid_kur=40,
            cha_meblag=40000, cha_vade=20261023)]
    k = O.acik_kalemler(h, KART)
    assert k[0]["acik"] == 1000.0 and O.kategori_bul(k[0]["cari_kod"]) == "ithalat"


def test_taksitli_fatura_vadelere_bolunur():
    h = [_h(cha_meblag=900, cha_vade=8, cha_evrakno_seri="UPL", cha_evrakno_sira=7),
         _h(cha_tip=0, cha_meblag=300, cha_evrak_tip=35)]
    tk = O.taksit_haritasi([
        {"cop_evrak_tip": 0, "cop_evrakno_seri": "UPL", "cop_evrakno_sira": 7, "cop_vade": "2026-10-22T00:00:00", "cop_tutar": 450},
        {"cop_evrak_tip": 0, "cop_evrakno_seri": "UPL", "cop_evrakno_sira": 7, "cop_vade": "2026-11-21T00:00:00", "cop_tutar": 450}])
    k = O.acik_kalemler(h, KART, taksitler=tk)
    assert [(r["vade"].isoformat(), r["acik"]) for r in k] == [("2026-10-22", 150.0), ("2026-11-21", 450.0)]
    assert all(r["vade_kesin"] for r in k)
    assert O.plan_gunleri([{"odp_no": 8, "odp_ortgun": 15}, {"odp_no": 0, "odp_ortgun": 0}]) == {8: 15}


# ── Öneri satırları ────────────────────────────────────────────────
BAS, SON = date(2026, 10, 19), date(2026, 10, 25)


def _kalemler():
    # UPS'in 21.10.2026 durumu (sadeleştirilmiş): 07.10 iki fatura 177.264,16; 14.10 iki fatura 457.714,34
    h = [_h(cha_meblag=134367.79, cha_vade=20261022, cha_evrakno_seri="UPL", cha_evrakno_sira=24507,
            cha_tarihi="2026-10-07T00:00:00"),
         _h(cha_meblag=42896.37, cha_vade=20261022, cha_evrakno_seri="UPL", cha_evrakno_sira=25505,
            cha_tarihi="2026-10-07T00:00:00"),
         _h(cha_meblag=457714.34, cha_vade=20261030, cha_evrakno_seri="UPL", cha_evrakno_sira=27361,
            cha_tarihi="2026-10-14T00:00:00"),
         _h(cha_meblag=0.004, cha_vade=20261020, cha_evrakno_sira=9)]          # yuvarlama artığı
    return O.acik_kalemler(h + DEY, KART)


def test_oneri_haftadakiler_ve_gecikmisler():
    cekler = [
        {"cek_no": "1138988", "vade": "2026-10-23", "kalan": 8450, "durum": "Ciro edildi", "para_birimi": "USD",
         "banka": "YAPI VE KREDİ USD HESAP", "ch_ismi": "NMT LOJİSTİK ANONİM ŞİRKETİ"},
        {"cek_no": "9904121", "vade": "2026-10-20", "kalan": 0, "durum": "Ödendi", "para_birimi": "TL"},
        {"cek_no": "1138989", "vade": "2026-11-26", "kalan": 11000, "durum": "Ciro edildi", "para_birimi": "USD"},
    ]
    s, u = O.oneri_satirlari(_kalemler(), cekler, BAS, SON)
    ozet = [(r["vade"], r["durum"], r["firma"][:12], r["tl"], r["usd"], r["kategori"]) for r in s]
    assert ozet == [
        ("2025-12-30", "Gecikmiş", "DEY ELEKTRON", None, 5148.0, "cari"),
        ("2026-10-22", "Bu hafta", "ÖRNEK TEDARİ", 177264.16, None, "cari"),
        ("2026-10-23", "Bu hafta", "1138988 NOLU", None, 8450.0, "cek"),
    ]
    assert s[1]["aciklama"] == "07.10.2026 TARİHLİ 2 FATURA"          # iki evrak, satır sayısı değil
    assert s[2]["firma"] == "1138988 NOLU YKB FİRMA ÇEK ÖDEMESİ - USD" and s[2]["aciklama"].startswith("NMT")
    assert s[0]["aciklama"].startswith("GECİKMİŞ") and all(r["sec"] for r in s) and u == []
    # gecikmişsiz: yalnız haftanın vadelileri
    s2, _ = O.oneri_satirlari(_kalemler(), cekler, BAS, SON, gecikmis_dahil=False)
    assert [r["vade"] for r in s2] == ["2026-10-22", "2026-10-23"]
    # gelecek hafta: 30.10 vadeli fatura; 22.10 olan artık gecikmiş
    s3, _ = O.oneri_satirlari(_kalemler(), cekler, date(2026, 10, 26), date(2026, 11, 1))
    assert [(r["vade"], r["durum"]) for r in s3 if r["firma"].startswith("ÖRNEK")] == [
        ("2026-10-22", "Gecikmiş"), ("2026-10-30", "Bu hafta")]


def test_eur_borc_listeye_girmez_uyari_verir():
    k = O.acik_kalemler([_h(cha_kod="336.009", cha_d_cins=2, cha_meblag=1200, cha_vade=20261021)], KART)
    s, u = O.oneri_satirlari(k, [], BAS, SON)
    assert s == [] and len(u) == 1 and "1.200,00 EUR" in u[0]


def test_odemeye_cevir_excel_okuyucusuyla_ayni_alanlar():
    s, _ = O.oneri_satirlari(_kalemler(), [], BAS, SON)
    s[0]["sec"] = False                                     # DEY çıkarıldı
    s[1]["tl"] = 100000.0                                   # tutar elle düzeltildi
    s.append({"sec": True, "firma": "BOŞ", "tl": None, "usd": None, "vade": "2026-10-20"})
    odemeler, atlanan = O.odemeye_cevir(s)
    assert atlanan == 1
    assert odemeler == [{"firma": "ÖRNEK TEDARİK A.Ş.", "aciklama": "07.10.2026 TARİHLİ 2 FATURA", "cari_banka": "",
                         "vade": "2026-10-22", "tl": 100000.0, "usd": None, "kategori": "cari", "manuel": 0}]
    assert O.ozet(s) == {"adet": 2, "tl": 100000.0, "usd": 0.0}


# ── Aktif haftayla karşılaştırma ───────────────────────────────────
@pytest.mark.parametrize("a, b, ayni", [
    ("AV.HAKAN KALAFAT", "HAKAN KALAFAT", True),
    ("MULTİNET KURUMSAL HİZMETLER ANONİM ŞİRKETİ", "MULTİNET", True),
    ("TUBA YILMAZEREN", "TUBA YILMAZER", True),
    ("UPS HIZLI KARGO TAŞIMACILIĞI ANONİM ŞİRKETİ", "UPS HIZLI KARGO TAŞIMACILIĞI ANONİM ŞİRKETİ", True),
    ("HAPPY LİFE İLAÇ VE SAĞLIK ÜRÜNLERİ SANAYİ TİCARET ANONİM ŞİRKETİ", "HAPPY LİFE İLAÇ VE SAĞLIK ÜRÜNLERİ A.Ş.", True),
    ("KUMPORT LİMAN HİZMETLERİ", "KEYAP KASIM AYI AİDATI", False),
    ("", "KDV 1", False),
])
def test_ayni_firma(a, b, ayni):
    assert O.ayni_firma(a, b) is ayni


def test_karsilastir():
    oneri = [{"firma": "UPS HIZLI KARGO TAŞIMACILIĞI A.Ş.", "tl": 177264.16, "usd": None},
             {"firma": "AV.HAKAN KALAFAT", "tl": 7500.0, "usd": None},
             {"firma": "KUMPORT LİMAN", "tl": 3898.8, "usd": None}]
    mevcut = [{"firma": "UPS HIZLI KARGO TAŞIMACILIĞI ANONİM ŞİRKETİ", "tutar_tl": "177401.40", "tutar_usd": None},
              {"firma": "HAKAN KALAFAT", "tutar_tl": "9000.00", "tutar_usd": None},
              {"firma": "KDV 1", "tutar_tl": "475033.00", "tutar_usd": None}]
    k = O.karsilastir(oneri, mevcut)
    assert [o["firma"][:3] for o, _ in k["ayni"]] == ["UPS"]           # %1 içinde
    assert [o["firma"][:3] for o, _ in k["farkli"]] == ["AV."]
    assert [o["firma"][:3] for o in k["yalniz_oneri"]] == ["KUM"]
    assert [m["firma"] for m in k["yalniz_mevcut"]] == ["KDV 1"]


# ── Kayıt: Excel yüklemesiyle aynı yol ─────────────────────────────
def test_hafta_olustur_aktif_hafta_en_son_ve_hatada_geri_alir(monkeypatch):
    from kayranacc import database as D
    olay = []
    monkeypatch.setattr(D, "hafta_ekle", lambda ad: olay.append(("ekle", ad)) or 99)
    monkeypatch.setattr(D, "odeme_ekle_bulk", lambda hid, od: olay.append(("odeme", hid, len(od))))
    monkeypatch.setattr(D, "hafta_aktif_yap", lambda hid: olay.append(("aktif", hid)))
    monkeypatch.setattr(D, "hafta_sil", lambda hid: olay.append(("sil", hid)))
    assert D.hafta_olustur("19.10.2026 GÜNCEL ÖDEME LİSTESİ", [{}, {}]) == 99
    assert olay == [("ekle", "19.10.2026 GÜNCEL ÖDEME LİSTESİ"), ("odeme", 99, 2), ("aktif", 99)]

    olay.clear()

    def _patla(hid, od):
        raise RuntimeError("yazılamadı")
    monkeypatch.setattr(D, "odeme_ekle_bulk", _patla)
    with pytest.raises(RuntimeError):
        D.hafta_olustur("X", [{}])
    assert olay == [("ekle", "X"), ("sil", 99)]                         # eski aktif hafta yerinde kalır

    olay.clear()
    monkeypatch.setattr(D, "hafta_ekle", lambda ad: None)
    assert D.hafta_olustur("X", [{}]) is None and olay == []


def _hepsi(s, alt):
    i, out = s.find(alt), []
    while i >= 0:
        out.append(i)
        i = s.find(alt, i + 1)
    return out


def test_ekran_yalniz_dugmeyle_yazar():
    """Öneri penceresi veritabanına yalnız 'Haftaya kaydet' düğmesinin içinden yazar."""
    s = (KOK / "kayranacc" / "mikro_odeme_ekran.py").read_text(encoding="utf-8")
    dugme = s.index('st.button("Haftaya kaydet"')
    assert s.index("hafta_olustur(ad.strip(), odemeler)") > dugme
    assert s.count("hafta_olustur(") == 1
    for yazan in ("_yt_kaydet(", "_yg_kaydet(", ".insert(", ".update(", ".delete(", "set_ayar("):
        assert all(i > dugme for i in _hepsi(s, yazan)), yazan
    o = (KOK / "kayranacc" / "odeme_ekran.py").read_text(encoding="utf-8")
    assert o.count("oneri_penceresi(kategoriler)") == 2                # eski ve yeni Bu Hafta ekranında


# ── Aktarıcı: ödeme planları keşifte ───────────────────────────────
def test_aktarici_odeme_planlarini_ve_taksitleri_okur(monkeypatch):
    if importlib.util.find_spec("requests") is None:
        sahte = types.ModuleType("requests")
        sahte.Session, sahte.RequestException, sahte.Response = object, Exception, object
        monkeypatch.setitem(sys.modules, "requests", sahte)
    yol = KOK / "araclar" / "mikro_aktarici" / "mikro_kayran.py"
    spec = importlib.util.spec_from_file_location("mikro_kayran_odeme_test", yol)
    mk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mk)
    q = {k: " ".join(v.split()) for k, v in mk.KESIF_SORGULARI.items()}
    assert "FROM ODEME_PLANLARI" in q["odeme_planlari"] and "odp_ortgun" in q["odeme_planlari"]
    assert "FROM CARI_HAREKET_ODEME_VADELERI" in q["odeme_vadeleri"] and "cop_vade" in q["odeme_vadeleri"]
