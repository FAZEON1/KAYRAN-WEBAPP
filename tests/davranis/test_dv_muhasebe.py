# -*- coding: utf-8 -*-
"""Davranış kilidi — Muhasebe (kayranacc): ödeme özetleri, banka bakiyesi, çek toplamları,
kur çevrimi, virman, cari ekstre bakiyesi ve vade yaşlandırma.

  kayranacc.odeme_hesap.ozet / gun_toplam          (saf: Bu Hafta / Genel Bakış rakamları)
  kayranacc.banka_ekran.banka_ozet_kalemleri       (saf: toplam şeridi, USD karşılığı, hafta sonu)
  kayranacc.database.cek_tutarlari / get_cek_toplamlari
  kayranacc.database.odeme_durum_guncelle / odeme_kismi_ode / virman_yap   (sahte DB)
  yonetim_hesap.tl_usd                              (TL → USD, kaydın tarihindeki kur)
  kayranacc.cari_ekstre.render                      (hesap sayfa içinde: ekrana giden sayılar yakalanır)

Bugün sabit: 14.10.2026. TL / USD ayrı tutulur.
"""
from datetime import date

import pytest

BUGUN = date(2026, 10, 14)


# ── Saf: ödeme özeti ──────────────────────────────────────────────────
ODEMELER = [
    {"id": 1, "firma": "ABC", "vade": "2026-10-10", "tutar_tl": 1000, "tutar_usd": None, "durum": "bekliyor"},
    {"id": 2, "firma": "ABC", "vade": "2026-10-14", "tutar_tl": 500, "tutar_usd": 100, "durum": "bekliyor"},
    {"id": 3, "firma": "XYZ", "vade": "2026-10-01", "tutar_tl": 2000, "tutar_usd": 0, "durum": "odendi"},
    {"id": 4, "firma": "XYZ", "vade": "2026-10-20", "tutar_tl": None, "tutar_usd": 50, "durum": "bekliyor"},
    {"id": 5, "firma": "XYZ", "vade": None, "tutar_tl": "300", "tutar_usd": "", "durum": "bekliyor"},
]
BANKALAR = [{"id": 1, "hesap_adi": "Garanti TL", "para_birimi": "TL", "bakiye": 100000},
            {"id": 2, "hesap_adi": "Kasa TL", "para_birimi": "TL", "bakiye": 20000},
            {"id": 3, "hesap_adi": "Garanti USD", "para_birimi": "USD", "bakiye": 5000}]


def test_odeme_ozeti_ve_hafta_sonu_tahmini():
    """TL toplam 1.000+500+2.000+300 = 3.800 ; USD 100+50 = 150 ; ödenen TL 2.000
       bekleyen TL 1.800, USD 150 ; gecikmiş (vade 10.10) 1.000 TL ; bugün vadeli 500 TL + 100 USD
       TL bankalar 120.000 (USD hesap girmez) ; kur 40
       hafta sonu = 120.000 − 1.800 − 150×40 = 112.200"""
    from kayranacc.odeme_hesap import ozet
    o = ozet(ODEMELER, BANKALAR, 40, BUGUN)
    assert {k: o[k] for k in ("adet", "odendi_adet", "tl", "usd", "odendi_tl", "odendi_usd", "bekleyen_tl",
                              "bekleyen_usd", "gecikmis_tl", "gecikmis_usd", "bugun_tl", "bugun_usd",
                              "banka_tl", "hafta_sonu_tl")} == pytest.approx(
        {"adet": 5, "odendi_adet": 1, "tl": 3800, "usd": 150, "odendi_tl": 2000, "odendi_usd": 0,
         "bekleyen_tl": 1800, "bekleyen_usd": 150, "gecikmis_tl": 1000, "gecikmis_usd": 0,
         "bugun_tl": 500, "bugun_usd": 100, "banka_tl": 120000, "hafta_sonu_tl": 112200})
    assert [x["id"] for x in o["gecikmis"]] == [1] and [x["id"] for x in o["bugun"]] == [2]


def test_odeme_ozeti_sinir_kur_yok_ve_gun_toplami():
    """Kur 0/None → USD bekleyen hafta sonundan düşülmez: 120.000 − 1.800 = 118.200.
       gun_toplam (10.10 + 14.10 kalemleri): TL 1.500, USD 100, bekleyen 2 adet."""
    from kayranacc.odeme_hesap import gun_toplam, ozet
    assert ozet(ODEMELER, BANKALAR, None, BUGUN)["hafta_sonu_tl"] == pytest.approx(118200)
    assert gun_toplam(ODEMELER[:2]) == pytest.approx({"tl": 1500, "usd": 100, "bekleyen": 2,
                                                      "bek_tl": 1500, "bek_usd": 100})


def test_banka_toplam_seridi_usd_karsiligi():
    """TL 120.000, USD 5.000 (EUR yok), kur 40 → USD karşılığı 5.000 + 120.000/40 = 8.000,00 $
       Hafta sonu (bekleyen 1.800 TL + 150 USD): 120.000 − 1.800 − 6.000 = ₺112.200,00 (yeşil).
       Kur yoksa TL USD karşılığına eklenmez: $5.000,00."""
    from kayranacc.banka_ekran import banka_ozet_kalemleri
    k = {x["etiket"]: x for x in banka_ozet_kalemleri(BANKALAR, 40, 1800, 150)}
    assert k["Toplam TL"]["deger"] == "₺120.000,00" and k["Toplam USD"]["deger"] == "$5.000,00"
    assert k["Hepsi (USD karşılığı)"]["deger"] == "$8.000,00"
    assert k["Hafta sonu tahmini"]["deger"] == "₺112.200,00" and k["Hafta sonu tahmini"]["renk"] == "yesil"
    assert "Toplam EUR" not in k
    k0 = {x["etiket"]: x for x in banka_ozet_kalemleri(BANKALAR, 0)}
    assert k0["Hepsi (USD karşılığı)"]["deger"] == "$5.000,00"


# ── Kur çevrimi ───────────────────────────────────────────────────────
def test_tl_usd_kaydin_tarihindeki_kur():
    """4.100 TL, 03.09 kuru 41 → 100 $ ; o gün kur yoksa yedek 50 → 82 $ ; yedek ≤ 1 → None (eksik).
       'TRY' de TL sayılır ; USD olduğu gibi ; döviz boş → USD."""
    from yonetim_hesap import tl_usd
    km = {"2026-09-03": 41.0}
    assert tl_usd(4100, "TL", "2026-09-03T10:00", km, 50) == pytest.approx(100)
    assert tl_usd(4100, "try", "2026-09-04", km, 50) == pytest.approx(82)
    assert tl_usd(4100, "TL", "2026-09-04", km, 1) is None
    assert tl_usd(70, "USD", None, {}, 0) == 70 and tl_usd("70", None, None, {}, 0) == 70


# ── Çekler ────────────────────────────────────────────────────────────
CEKLER = [
    # bekleyen, kalan sütunu meblağ−ödenen ile uyumlu → 6.000
    {"id": 1, "para_birimi": "TL", "durum": "Bekliyor", "meblagh": 10000, "odenen": 4000, "kalan": 6000},
    # ÖDENDİ (Türkçe büyük harf) → 0, toplama girmez
    {"id": 2, "para_birimi": "TL", "durum": "ÖDENDİ", "meblagh": 5000, "odenen": 0, "kalan": 5000},
    # kalan sütunu meblağa eşit ama ödeme var (güncellenmemiş) → 3.000 − 1.000 = 2.000
    {"id": 3, "para_birimi": "TL", "durum": "Ciro Edildi", "meblagh": 3000, "odenen": 1000, "kalan": 3000},
    # USD, kalan boş → meblağ 700
    {"id": 4, "para_birimi": "usd", "durum": "Portföyde", "meblagh": 700, "odenen": None, "kalan": None},
    # tamamen ödenmiş (durum yazılmamış) → 0
    {"id": 5, "para_birimi": "TL", "durum": "", "meblag": 800, "odenen": 800, "kalan": 0},
    {"id": 6, "para_birimi": "USD", "durum": "Tahsil Edildi", "meblagh": 900, "odenen": 900, "kalan": 0},
]


def test_cek_tutarlari_tek_kural():
    """Çek başına kalan: #1 6.000 ; #2 Ödendi → 0 (ödenen meblağa çekilir: 5.000) ; #3 2.000 ;
       #4 700 ; #5 0 ; #6 0."""
    from kayranacc.database import cek_tutarlari
    k = [cek_tutarlari(c) for c in CEKLER]
    assert [x["kalan"] for x in k] == pytest.approx([6000, 0, 2000, 700, 0, 0])
    assert (k[1]["odendi"], k[1]["odenen"]) == (True, 5000)
    assert [x["odendi"] for x in k] == [False, True, False, False, False, True]


def test_cek_toplamlari(sahte_db, monkeypatch):
    """Tahsil edilmemiş çekler: TL 6.000 + 2.000 = 8.000 (2 adet) ; USD 700 (1 adet; 'usd' yazımı).
       cek_tutarlari ile aynı sonuç (bu veri setinde)."""
    import kayranacc.database as adb
    monkeypatch.setattr(adb, "get_client", lambda: sahte_db(cekler=CEKLER))
    assert adb.get_cek_toplamlari() == (pytest.approx(8000), pytest.approx(700), 2, 1)
    k = [adb.cek_tutarlari(c) for c in CEKLER]
    assert sum(x["kalan"] for c, x in zip(CEKLER, k) if c["para_birimi"].upper() == "TL") == pytest.approx(8000)


# ── Ödeme / banka hareketleri (sahte DB) ──────────────────────────────
@pytest.fixture
def muhdb(sahte_db, monkeypatch):
    import kayranacc.database as adb
    db = sahte_db(bankalar=BANKALAR, odemeler=[
        {"id": 10, "hafta_id": 1, "firma": "ABC", "aciklama": "Fatura", "vade": "2026-10-14", "tutar_tl": 10000,
         "tutar_usd": 200, "kategori": "cari", "durum": "bekliyor", "banka_id": None},
        {"id": 11, "hafta_id": 1, "firma": "XYZ", "aciklama": "Kira", "vade": "2026-10-15", "tutar_tl": 4000,
         "tutar_usd": None, "kategori": "kira", "durum": "bekliyor", "banka_id": None},
        {"id": 12, "hafta_id": 1, "firma": "QQ", "aciklama": "Mal", "vade": "2026-10-16", "tutar_tl": 1000,
         "tutar_usd": None, "kategori": "cari", "durum": "bekliyor", "banka_id": None},
    ], virmanlar=[])
    monkeypatch.setattr(adb, "get_client", lambda: db)
    return db


def _bakiye(db, bid):
    return db.satir("bankalar", id=bid)["bakiye"]


def test_odeme_bankadan_duser_cift_dusum_yok_geri_al_iade(muhdb):
    """10.000 TL + 200 USD, TL hesaptan, kur 40: 100.000 − (10.000 + 200×40) = 82.000.
       Tekrar 'ödendi' → ikinci düşüm YOK (82.000). Geri al ('bekliyor') → +18.000 = 100.000,
       banka_id temizlenir."""
    from kayranacc.database import odeme_durum_guncelle
    odeme_durum_guncelle(10, "odendi", banka_id=1, kur=40)
    o = muhdb.satir("odemeler", id=10)
    assert (o["durum"], o["banka_id"], bool(o["odendi_tarih"])) == ("odendi", 1, True)
    assert _bakiye(muhdb, 1) == pytest.approx(82000)
    odeme_durum_guncelle(10, "odendi", banka_id=1, kur=40)
    assert _bakiye(muhdb, 1) == pytest.approx(82000)
    odeme_durum_guncelle(10, "bekliyor", kur=40)
    assert _bakiye(muhdb, 1) == pytest.approx(100000)
    assert muhdb.satir("odemeler", id=10)["banka_id"] is None


def test_odeme_usd_hesaptan_tl_tutar_kurla(muhdb):
    """4.000 TL'lik ödeme USD hesabından, kur 40 → 5.000 − 4.000/40 = 4.900 $."""
    from kayranacc.database import odeme_durum_guncelle
    odeme_durum_guncelle(11, "odendi", banka_id=3, kur=40)
    assert _bakiye(muhdb, 3) == pytest.approx(4900)


def test_kismi_odeme_kayit_boler_bankadan_duser(muhdb):
    """1.000 TL'nin 400'ü TL hesaptan: yeni 'odendi' kaydı 400 (banka_id 1), asıl kayıt kalan 600
       bekliyor ; banka 100.000 − 400 = 99.600. Kalanı aşan tutar (5.000) tamamına kırpılır →
       kayıt 'odendi', banka 99.600 − 600 = 99.000."""
    from kayranacc.database import odeme_kismi_ode
    ok, _ = odeme_kismi_ode(12, kismi_tl=400, banka_id=1, kur=40)
    assert ok
    asil = muhdb.satir("odemeler", id=12)
    assert (asil["tutar_tl"], asil["durum"]) == (600, "bekliyor")
    yeni = [o for o in muhdb.tablolar["odemeler"] if o["id"] not in (10, 11, 12)]
    assert [(o["tutar_tl"], o["tutar_usd"], o["durum"], o["banka_id"], o["firma"]) for o in yeni] == \
        [(400, None, "odendi", 1, "QQ")]
    assert _bakiye(muhdb, 1) == pytest.approx(99600)
    ok, _ = odeme_kismi_ode(12, kismi_tl=5000, banka_id=1, kur=40)
    assert ok and muhdb.satir("odemeler", id=12)["durum"] == "odendi"
    assert _bakiye(muhdb, 1) == pytest.approx(99000)


def test_virman_kur_yonu_ve_redler(muhdb):
    """TL→USD 41.000, kur 41 → zayıftan güçlüye BÖL: +1.000 $ (TL 59.000, USD 6.000).
       USD→TL 100 $, kur 41 → ÇARP: +4.100 ₺ (USD 5.900, TL 63.100).
       Red: aynı hesap, yetersiz bakiye, farklı para birimi kur yok — bakiyeler değişmez."""
    from kayranacc.database import virman_yap
    assert virman_yap(1, 3, 41000, kur_kullanilan=41)[0]
    assert (_bakiye(muhdb, 1), _bakiye(muhdb, 3)) == pytest.approx((59000, 6000))
    assert virman_yap(3, 1, 100, kur_kullanilan=41)[0]
    assert (_bakiye(muhdb, 1), _bakiye(muhdb, 3)) == pytest.approx((63100, 5900))
    assert muhdb.tablolar["virmanlar"][0]["hedef_tutar"] == pytest.approx(1000)
    assert virman_yap(1, 1, 10)[0] is False
    assert virman_yap(2, 1, 999999)[0] is False
    assert virman_yap(1, 3, 100)[0] is False
    assert (_bakiye(muhdb, 1), _bakiye(muhdb, 2), _bakiye(muhdb, 3)) == pytest.approx((63100, 20000, 5900))


# ── Cari ekstre + vade yaşlandırma (sayfa içi hesap) ──────────────────
class _Kap:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __getattr__(self, ad):
        return lambda *a, **k: _Kap()


class _St:
    """Sayfanın kullandığı streamlit yüzeyi; uyarıları toplar, seçimi sabit verir."""

    def __init__(self, firma):
        self.firma, self.uyarilar = firma, []

    def tabs(self, adlar):
        return [_Kap() for _ in adlar]

    def columns(self, n, **_k):
        return [_Kap() for _ in range(n if isinstance(n, int) else len(n))]

    def selectbox(self, _etiket, secenekler, **_k):
        assert self.firma in secenekler
        return self.firma

    def warning(self, m, **_k):
        self.uyarilar.append(m)

    def __getattr__(self, ad):
        return lambda *a, **k: _Kap()


EKSTRE = [
    {"firma": "ABC", "vade": "2026-09-01", "tutar_tl": 1000, "tutar_usd": None, "durum": "bekliyor", "kategori": "cari"},
    {"firma": "ABC", "vade": "2026-10-20", "tutar_tl": 500, "tutar_usd": 100, "durum": "bekliyor", "kategori": "kart"},
    {"firma": "ABC", "vade": "2026-08-01", "tutar_tl": 2000, "tutar_usd": None, "durum": "odendi", "kategori": "cari"},
    {"firma": "ABC", "vade": "2026-06-01", "tutar_tl": None, "tutar_usd": 50, "durum": "bekliyor", "kategori": "ithalat"},
    {"firma": "XYZ", "vade": "2026-10-10", "tutar_tl": 300, "tutar_usd": None, "durum": "bekliyor", "kategori": "kira"},
    {"firma": "XYZ", "vade": None, "tutar_tl": 200, "tutar_usd": None, "durum": "bekliyor", "kategori": "diger"},
    {"firma": None, "vade": "2026-07-20", "tutar_tl": 10, "tutar_usd": None, "durum": "bekliyor", "kategori": ""},
]


def _cari(monkeypatch, firma, pb):
    import kayranacc.cari_ekstre as ce
    import kayranacc.database as adb
    import shared.masa_liste as ml
    import shared.utils as su
    st = _St(firma)
    kartlar, masalar = [], []
    monkeypatch.setattr(ce, "st", st)
    monkeypatch.setattr(ce, "tr_today", lambda: BUGUN)
    monkeypatch.setattr(ce, "secim_serit", lambda *a, **k: pb)
    monkeypatch.setattr(adb, "get_tum_odemeler", lambda: [dict(o) for o in EKSTRE])
    monkeypatch.setattr(su, "metrik_satiri", lambda kart: kartlar.append(kart))
    monkeypatch.setattr(ml, "ciz", lambda satirlar, *a, **k: masalar.append(satirlar))
    ce.render()
    return st, kartlar, masalar


def test_cari_ekstre_firma_bakiyesi(monkeypatch):
    """ABC: açık TL = 1.000 + 500 = ₺1.500 ; açık USD = 100 + 50 = $150,00 ; ödenmiş TL ₺2.000 (USD $0,00).
       Vadesi geçmiş açık kalem: 01.09 (1.000 TL) + 01.06 (50 USD) → 2 kalem, TL toplamı ₺1.000.
       Ekstre satırları vade sırasıyla 4 kalem."""
    st, kartlar, masalar = _cari(monkeypatch, "ABC", "TL")
    ekstre = kartlar[0]
    assert [k["value"] for k in ekstre] == ["₺1.500", "$150,00", "₺2.000"]
    assert ekstre[2]["alt"] == "USD: $0,00"
    assert any("2 kalemin vadesi geçmiş" in u and "₺1.000" in u for u in st.uyarilar)
    assert [r["Vade"] for r in masalar[0]] == ["2026-06-01", "2026-08-01", "2026-09-01", "2026-10-20"]
    assert [(r["Tutar (TL)"], r["Tutar (USD)"]) for r in masalar[0]] == [(None, 50), (2000, None),
                                                                          (1000, None), (500, 100)]


def test_vade_yaslandirma_tl(monkeypatch):
    """Açık TL kalemleri (bugün 14.10): ABC 01.09 1.000 (43 gün → 31-60) ; ABC 20.10 500 (gelmemiş) ;
       XYZ 10.10 300 (4 gün → 0-30) ; XYZ vadesiz 200 (gelmemiş) ; '—' 20.07 10 (86 gün → 61-90).
       Kova toplamları: gelmemiş 700, 0-30 300, 31-60 1.000, 61-90 10, 90+ 0 ; gecikmiş 1.310.
       Firma satırları toplam azalan: ABC 1.500, XYZ 500, — 10."""
    st, kartlar, masalar = _cari(monkeypatch, "ABC", "TL")
    assert [k["value"] for k in kartlar[1]] == ["₺700", "₺300", "₺1.000", "₺10", "₺0"]
    assert any("₺1.310" in u for u in st.uyarilar)
    assert [(r["Cari"], r["Toplam"]) for r in masalar[1]] == [("ABC", 1500), ("XYZ", 500), ("—", 10)]
    assert masalar[1][0]["31-60 gün"] == 1000 and masalar[1][0]["Vadesi gelmemiş"] == 500


def test_vade_yaslandirma_usd(monkeypatch):
    """Açık USD: ABC 20.10 100 (gelmemiş) ; ABC 01.06 50 (135 gün → 90+). Diğer firmaların USD'si yok.
       Kova: gelmemiş $100,00, 90+ $50,00 ; gecikmiş toplam $50,00."""
    st, kartlar, masalar = _cari(monkeypatch, "XYZ", "USD")
    assert [k["value"] for k in kartlar[1]] == ["$100,00", "$0,00", "$0,00", "$0,00", "$50,00"]
    assert [(r["Cari"], r["Toplam"]) for r in masalar[1]] == [("ABC", 150)]
    assert any("$50,00" in u for u in st.uyarilar)
