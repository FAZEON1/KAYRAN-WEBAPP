# -*- coding: utf-8 -*-
"""Davranış testleri · 7 hesap düzeltmesi (Ekim 2026, kullanıcı onayıyla "7'sini de düzenle").

  1) Excel toplu satış: merkezde yetmeyen adet yalnız SATILABİLİR depodan (Happy Life) düşer; hurda / iade /
     ikinci el gibi depolara dokunulmaz, hiçbir satılabilir depoda kalmadıysa kalan merkeze eksi yazılır.
  2) Excel toplu satış: harf karışık SKU ("MIO MIVUE J30") kartın ("Mio MiVue J30") depo dağılımını bulur.
  3) Kur girilmeden USD ödeme TL bankadan: kur_gunluk'taki son kur; o da yoksa bakiye 1:1 DÜŞÜLMEZ.
  4) EUR bankadan ödeme: TL+USD toplamının EUR karşılığı düşer (eskiden yalnız TL kısmı).
  5) Çek toplam kartı ile çek listesi aynı kural (cek_tutarlari); EUR çek TL toplamına girmez, USD karşılığı.
  6) EUR→USD sabit değil: shared.kur.eur_usd (banka şeridi, para haritası).
  7) P&L ürün kırılımında SKU yazımları karta bağlanır ("Fazeon X24" + "X24" tek satır)."""
import pytest


# ── 1 + 2: akıllı depo düşümü ─────────────────────────────────────────
def _urun(sku, kirilim):
    from kayranpm.database import _bizim_stok_hesapla
    return {"sku": sku, "urun_adi": sku, "kategori": "", "depo_kirilim": dict(kirilim),
            "bizim_stok": _bizim_stok_hesapla(kirilim)}


@pytest.fixture
def stokdb(sahte_db, monkeypatch):
    import kayranpm.database as pdb
    import satis.database as sdb
    import shared.auth as auth
    db = sahte_db(urunler=[
        _urun("H1", {"MERKEZ DEPO": 1, "HAPPY LIFE": 9, "HURDA DEPO": 50}),
        _urun("Mio MiVue J30", {"MERKEZ DEPO": 1, "HAPPY LIFE": 9}),
    ], stok_hareketleri=[])
    monkeypatch.setattr(pdb, "get_client", lambda: db)
    monkeypatch.setattr(sdb, "_get_client", lambda: db)
    monkeypatch.setattr(auth, "_get_supabase", lambda: db)
    return db


def _kir(db, sku):
    return {k: v for k, v in db.satir("urunler", sku=sku)["depo_kirilim"].items()}


def test_1_akilli_dusum_hurdaya_dokunmaz(stokdb):
    """20 adet: MERKEZ 1 → 0 (1), HAPPY LIFE 9 → 0 (9), kalan 10 → MERKEZ −10. HURDA 50 aynı kalır.
       Eski: HURDA 50 → 31, HAPPY 9 olduğu gibi."""
    from satis.database import _stok_akilli_dus
    _stok_akilli_dus({"H1": 20})
    k = _kir(stokdb, "H1")
    assert k["HURDA DEPO"] == 50
    assert k["HAPPY LIFE"] == 0 and k["MERKEZ DEPO"] == -10


def test_2_akilli_dusum_harf_karisik_sku_karti_bulur(stokdb):
    """'MIO MIVUE J30' 5 adet → kart 'Mio MiVue J30': MERKEZ 1 → 0, HAPPY 9 → 5.
       Eski: kırılım bulunamıyor, 5'in tamamı merkezden → MERKEZ −4, HAPPY 9."""
    from satis.database import _stok_akilli_dus
    _stok_akilli_dus({"MIO MIVUE J30": 5})
    k = _kir(stokdb, "Mio MiVue J30")
    assert (k["MERKEZ DEPO"], k["HAPPY LIFE"]) == (0, 5)


# ── 3 + 4: ödeme banka düşümü ─────────────────────────────────────────
BANKALAR = [{"id": 1, "hesap_adi": "Garanti TL", "para_birimi": "TL", "bakiye": 100000},
            {"id": 3, "hesap_adi": "Garanti USD", "para_birimi": "USD", "bakiye": 5000},
            {"id": 4, "hesap_adi": "Garanti EUR", "para_birimi": "EUR", "bakiye": 1000}]


def _odemeler():
    return [{"id": 20, "hafta_id": 1, "firma": "ABC", "aciklama": "Fatura", "vade": "2026-10-14",
             "tutar_tl": None, "tutar_usd": 100, "kategori": "cari", "durum": "bekliyor", "banka_id": None},
            {"id": 21, "hafta_id": 1, "firma": "XYZ", "aciklama": "Mal", "vade": "2026-10-14",
             "tutar_tl": 4320, "tutar_usd": 108, "kategori": "cari", "durum": "bekliyor", "banka_id": None}]


@pytest.fixture
def muhdb(sahte_db, monkeypatch):
    import kayranacc.database as adb
    db = sahte_db(bankalar=[dict(b) for b in BANKALAR], odemeler=_odemeler(), virmanlar=[],
                  kur_gunluk=[{"tarih": "2026-10-13", "usd_try": 40.0}])
    monkeypatch.setattr(adb, "get_client", lambda: db)
    for f in ("get_kur", "_tum_kurlar"):
        c = getattr(getattr(adb, f, None), "clear", None)
        if c:
            c()
    return db


def _bakiye(db, bid):
    return db.satir("bankalar", id=bid)["bakiye"]


def test_3_kur_girilmeden_usd_odeme_kayitli_kurla(muhdb):
    """100 USD TL bankadan, kur verilmedi → kur_gunluk'taki son kur 40: 100.000 − 4.000 = 96.000.
       Eski: kur 1,0 kabul → 99.900."""
    from kayranacc.database import odeme_durum_guncelle
    odeme_durum_guncelle(20, "odendi", banka_id=1)
    assert _bakiye(muhdb, 1) == pytest.approx(96000)


def test_3_kur_hic_yoksa_bire_bir_dusmez(muhdb):
    """Kur ne verildi ne kayıtlı → bakiye DEĞİŞMEZ (100.000); ödeme yine 'odendi'. Eski: 99.900."""
    from kayranacc.database import odeme_durum_guncelle
    muhdb.tablolar["kur_gunluk"] = []
    odeme_durum_guncelle(20, "odendi", banka_id=1)
    assert _bakiye(muhdb, 1) == pytest.approx(100000)
    assert muhdb.satir("odemeler", id=20)["durum"] == "odendi"


def test_4_eur_bankadan_odeme_eur_karsiligi(muhdb):
    """4.320 TL + 108 USD, EUR bankadan, kur 40, EUR/USD 1,08 (testte yedek kur):
       USD toplamı 108 + 4.320/40 = 216 → EUR 200 → 1.000 − 200 = 800. Geri al → 1.000.
       Eski: yalnız TL kısmı düşülüyordu (1.000 − 4.320 = −3.320)."""
    from kayranacc.database import odeme_durum_guncelle
    odeme_durum_guncelle(21, "odendi", banka_id=4, kur=40)
    assert _bakiye(muhdb, 4) == pytest.approx(800)
    odeme_durum_guncelle(21, "bekliyor", kur=40)
    assert _bakiye(muhdb, 4) == pytest.approx(1000)


def test_4_kismi_odeme_eur_bankadan(muhdb):
    """108 USD'nin 54'ü EUR bankadan → 54 / 1,08 = 50 EUR → 950. Eski: 1.000 (hiç düşmüyordu)."""
    from kayranacc.database import odeme_kismi_ode
    ok, _ = odeme_kismi_ode(21, kismi_usd=54, banka_id=4, kur=40)
    assert ok and _bakiye(muhdb, 4) == pytest.approx(950)


# ── 5: çek toplamı ─────────────────────────────────────────────────────
CEKLER = [
    {"id": 1, "meblagh": 1000, "odenen": 0, "kalan": 300, "para_birimi": "TL", "durum": "Bekliyor"},
    {"id": 2, "meblagh": 500, "odenen": 0, "kalan": 500, "para_birimi": "EUR", "durum": "Bekliyor"},
    {"id": 3, "meblagh": 700, "odenen": 0, "kalan": 700, "para_birimi": "USD", "durum": "Ciro edildi"},
]


def test_5_cek_toplami_liste_ile_ayni_kural(sahte_db, monkeypatch):
    """#1: kalan sütunu 300 ama meblağ−ödenen 1.000 (uyuşmuyor) → liste 1.000 der; toplam da 1.000.
       #2 EUR 500 → TL'ye girmez; USD karşılığı 500 × 1,08 = 540. #3 USD 700.
       Toplam: TL 1.000 (1 adet), USD 700 + 540 = 1.240 (2 adet).
       Eski: TL 300 + 500 (EUR TL'ye ekleniyordu) = 800, USD 700."""
    import kayranacc.database as adb
    monkeypatch.setattr(adb, "get_client", lambda: sahte_db(cekler=CEKLER))
    tl, usd, a_tl, a_usd = adb.get_cek_toplamlari()
    assert tl == pytest.approx(1000) and a_tl == 1
    assert usd == pytest.approx(1240) and a_usd == 2
    assert tl == pytest.approx(sum(adb.cek_tutarlari(c)["kalan"] for c in CEKLER if c["para_birimi"] == "TL"))


# ── 6: EUR→USD güncel kur ──────────────────────────────────────────────
def test_6_banka_seridi_guncel_eur_kuru(monkeypatch):
    """TL 40.000, USD 1.000, EUR 1.000; kur 40; EUR/USD 1,15 → 1.000 + 1.000 + 1.150 = 3.150 $.
       Eski: sabit 1,08 → 3.080 $."""
    import shared.kur as K
    monkeypatch.setattr(K, "eur_usd", lambda: 1.15)
    from kayranacc.banka_ekran import banka_ozet_kalemleri
    b = [{"para_birimi": "TL", "bakiye": 40000}, {"para_birimi": "USD", "bakiye": 1000},
         {"para_birimi": "EUR", "bakiye": 1000}]
    k = {x["etiket"]: x for x in banka_ozet_kalemleri(b, 40)}
    assert k["Hepsi (USD karşılığı)"]["deger"] == "$3.150,00"


def test_6_kur_tek_kaynak_yedek_ve_banka_karsiligi():
    """Çevrimdışı (test) → yedek 1,08. banka_karsiligi: TL bankadan 100 USD kur 40 → 4.000 ;
       kur yoksa None ; USD bankadan 400 TL kur 40 → 10 ; EUR bankadan 108 USD (EUR 1,08) → 100."""
    from shared.kur import banka_karsiligi, eur_usd
    assert eur_usd() == 1.08
    assert banka_karsiligi("TL", 0, 100, 40) == pytest.approx(4000)
    assert banka_karsiligi("TL", 0, 100, None) is None
    assert banka_karsiligi("USD", 400, 0, 40) == pytest.approx(10)
    assert banka_karsiligi("EUR", 0, 108, 40, eur=1.08) == pytest.approx(100)
    assert banka_karsiligi("TL", 500, 0, None) == pytest.approx(500)


# ── 7: P&L ürün kırılımı ───────────────────────────────────────────────
def test_7_pnl_urun_kirilimi_sku_yazimlari_birlesir(monkeypatch):
    """'Fazeon X24' (2 adet × 100) ve 'X24' (3 × 100), kart 'X24' → tek satır X24: 5 adet, ciro 500.
       Toplamlar aynı. Eski: iki ayrı satır."""
    import satis.database as sdb
    monkeypatch.setattr(sdb, "_kart_sku_haritasi", lambda: {"X24": "X24"})
    sat = [{"sku": "Fazeon X24", "urun_adi": "Fazeon X24", "kanal": "VATAN", "adet": 2, "birim_satis": 100,
            "birim_maliyet": 60},
           {"sku": "X24", "urun_adi": "X24", "kanal": "VATAN", "adet": 3, "birim_satis": 100, "birim_maliyet": 60}]
    top, _kanal, urun = sdb.ozet_hesapla(sat)
    assert list(urun) == ["X24"]
    assert urun["X24"]["adet"] == 5 and urun["X24"]["ciro"] == pytest.approx(500)
    assert top["adet"] == 5 and top["ciro"] == pytest.approx(500)
