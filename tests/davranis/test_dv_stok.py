# -*- coding: utf-8 -*-
"""Davranış kilidi — Stok: depo kırılımı, satılabilir stok, satışta / iadede depodan düşüm.

  kayranpm.database.depo_dagilimi, satilabilir_kontrol      (saf)
  kayranpm.database.stok_hareket_coklu                       (urunler.depo_kirilim + bizim_stok
                                                              + stok_hareketleri defteri)
  satis.database._stok_uygula_depolu                         (seçilen depodan düşüm / iade girişi)
  satis.database._stok_akilli_dus                            (Excel toplu satış: otomatik depo dağıtımı)

Sahte veritabanı (conftest.SahteDB) yazılanı saklar; sonuç urunler satırından ve stok_hareketleri
tablosundan OKUNUR. rpc() her zaman 'kurulu değil' hatası verir → atomik stok fonksiyonu
kurulmamışken bugünkü yolun sonucu kilitlenir.

Satılabilir depolar: MERKEZ DEPO + HAPPY LIFE (iade / ikinci el / teknik sayılmaz).
"""
import pytest


def _urun(sku, kirilim, **ek):
    from kayranpm.database import _bizim_stok_hesapla
    return dict({"sku": sku, "urun_adi": sku, "kategori": "", "depo_kirilim": dict(kirilim),
                 "bizim_stok": _bizim_stok_hesapla(kirilim)}, **ek)


@pytest.fixture
def stokdb(sahte_db, monkeypatch):
    import kayranpm.database as pdb
    import satis.database as sdb
    import shared.auth as auth
    db = sahte_db(urunler=[
        _urun("X24", {"MERKEZ DEPO": 10, "HAPPY LIFE": 5, "İADE DEPO": 3}),
        _urun("K1", {"HAPPY LIFE": 2, "MERKEZ DEPO": 1}),
        _urun("Mio MiVue J30", {"MERKEZ DEPO": 4}),
        _urun("KISA", {"MERKEZ": 10, "HAPPYLIFE": 2}),          # eski kısa depo yazımları
        _urun("A1", {"MERKEZ DEPO": 3, "HAPPY LIFE": 5, "ASEL DEPO": 8}),
    ], stok_hareketleri=[])
    monkeypatch.setattr(pdb, "get_client", lambda: db)
    monkeypatch.setattr(sdb, "_get_client", lambda: db)
    monkeypatch.setattr(auth, "_get_supabase", lambda: db)     # stok defteri + hata kaydı da buraya
    return db


def _dagilim(db, sku):
    from kayranpm.database import depo_dagilimi
    u = db.satir("urunler", sku=sku)
    return dict(depo_dagilimi(u["depo_kirilim"])[0]), u["bizim_stok"]


def _defter(db, basarili=True):
    return [(r["sku"], r["depo"], r["onceki"], r["sonraki"], r["degisim"], r["tur"])
            for r in db.tablolar.get("stok_hareketleri", []) if r.get("basarili") is basarili]


# ── Saf: depo_dagilimi / satilabilir_kontrol ─────────────────────────
def test_depo_dagilimi_kanonik_toplar_sifiri_atar_siralar():
    """'MERKEZ' 5 + 'Merkez Depo' 3 → MERKEZ DEPO 8 ; 'happy life' '4' → HAPPY LIFE 4 ;
       ASEL 0 atılır ; 'bozuk' değer 0 sayılır ve atılır ; İADE DEPO 4 (rozet olarak görünür).
       Sıra: adet azalan, eşitlikte ad: MERKEZ 8, HAPPY LIFE 4, İADE DEPO 4. Toplam 16."""
    from kayranpm.database import depo_dagilimi
    s, t = depo_dagilimi({"MERKEZ": 5, "Merkez Depo": 3, "happy life": "4", "ASEL": 0,
                          "TEKNIK": "bozuk", "iade": 4})
    assert s == [("MERKEZ DEPO", 8), ("HAPPY LIFE", 4), ("İADE DEPO", 4)]
    assert t == 16
    assert depo_dagilimi(None) == ([], 0) and depo_dagilimi("{}") == ([], 0)


def test_satilabilir_kontrol_fark():
    """Hesap = MERKEZ (kısa yazım dahil) 7 + HAPPY LIFE 3 = 10 ; iade 5 ve ikinci el 2 SAYILMAZ.
       Kayıtlı '12' → fark −2. Kırılım boşsa hesap/fark None (uyarı yok)."""
    from kayranpm.database import satilabilir_kontrol
    assert satilabilir_kontrol({"MERKEZ": 7, "HAPPY LIFE": 3, "IADE DEPO": 5, "2.el": 2}, "12") == \
        {"hesap": 10, "kayitli": 12, "fark": -2}
    assert satilabilir_kontrol({}, 4) == {"hesap": None, "kayitli": 4, "fark": None}
    assert satilabilir_kontrol({"MERKEZ DEPO": 3}, None) == {"hesap": 3, "kayitli": 0, "fark": 3}


# ── Satış: seçilen depodan düşüm ─────────────────────────────────────
def test_satis_secilen_depodan_duser_defter_yazar(stokdb):
    """X24: 4 + 1 adet MERKEZ DEPO'dan (aynı depo toplanır → −5): MERKEZ 10→5 ; bizim 15→10
       (iade deposu 3 bizim stoğa girmez). K1: 2 adet 'happy life' (yazım farkı) → HAPPY LIFE 2→0 ;
       bizim 3→1. Defter: X24 MERKEZ DEPO 10→5 (−5, çıkış), K1 HAPPY LIFE 2→0 (−2, çıkış)."""
    from satis.database import _stok_uygula_depolu
    _stok_uygula_depolu([("X24", 4, "MERKEZ DEPO"), ("X24", 1, "MERKEZ DEPO"), ("K1", 2, "happy life")], yon=-1)
    assert _dagilim(stokdb, "X24") == ({"MERKEZ DEPO": 5, "HAPPY LIFE": 5, "İADE DEPO": 3}, 10)
    assert _dagilim(stokdb, "K1") == ({"MERKEZ DEPO": 1}, 1)
    assert sorted(_defter(stokdb)) == [("K1", "HAPPY LIFE", 2.0, 0.0, -2.0, "cikis"),
                                       ("X24", "MERKEZ DEPO", 10.0, 5.0, -5.0, "cikis")]


def test_satis_sku_yazim_farki_karta_baglanir_depo_bossa_merkez(stokdb):
    """'Fazeon X24' 2 adet, depo BOŞ → MERKEZ DEPO ; kart X24'e yazılır: MERKEZ 10→8, bizim 13.
       'MIO MIVUE J30' 1 adet → kart 'Mio MiVue J30': MERKEZ 4→3, bizim 3. Kart açılmaz."""
    from satis.database import _stok_uygula_depolu
    _stok_uygula_depolu([("Fazeon X24", 2, ""), ("MIO MIVUE J30", 1, None)], yon=-1)
    assert _dagilim(stokdb, "X24") == ({"MERKEZ DEPO": 8, "HAPPY LIFE": 5, "İADE DEPO": 3}, 13)
    assert _dagilim(stokdb, "Mio MiVue J30") == ({"MERKEZ DEPO": 3}, 3)
    assert len(stokdb.tablolar["urunler"]) == 5


def test_satis_stoktan_fazla_eksiye_iner_kisa_depo_yazimi(stokdb):
    """Satış ENGELLENMEZ: X24 MERKEZ 10'dan 12 → −2 ; bizim = −2 + 5 = 3.
       Kırılımda kısa yazım 'MERKEZ' 10 olan KISA'dan 3 adet 'MERKEZ DEPO' → kanonik toplam
       MERKEZ DEPO 7 ; HAPPYLIFE 2 → HAPPY LIFE 2 ; bizim 9."""
    from satis.database import _stok_uygula_depolu
    _stok_uygula_depolu([("X24", 12, "MERKEZ DEPO"), ("KISA", 3, "MERKEZ DEPO")], yon=-1)
    assert _dagilim(stokdb, "X24") == ({"MERKEZ DEPO": -2, "HAPPY LIFE": 5, "İADE DEPO": 3}, 3)
    assert _dagilim(stokdb, "KISA") == ({"MERKEZ DEPO": 7, "HAPPY LIFE": 2}, 9)


def test_iade_girisi_iade_deposuna_bizim_stok_degismez(stokdb):
    """İade (+): X24 2 adet 'İADE DEPO' → 3→5 ; bizim 15 AYNEN (iade deposu satılabilir değil).
       Defter: giriş +2."""
    from satis.database import _stok_uygula_depolu
    _stok_uygula_depolu([("X24", 2, "İADE DEPO")], yon=+1)
    assert _dagilim(stokdb, "X24") == ({"MERKEZ DEPO": 10, "HAPPY LIFE": 5, "İADE DEPO": 5}, 15)
    assert _defter(stokdb) == [("X24", "İADE DEPO", 3.0, 5.0, 2.0, "giris")]


def test_karti_olmayan_sku_atlanir_nedeni_deftere(stokdb):
    """Kartı olmayan 'YOK1' (kart_ac=False): stok yazılmaz, (0, ['YOK1']) döner,
       defterde başarısız satır. Sıfır adet hareket yok sayılır."""
    from kayranpm.database import stok_hareket_coklu
    assert stok_hareket_coklu({"YOK1": -3, "X24": 0}, "MERKEZ DEPO") == (0, ["YOK1"])
    bas = [r for r in stokdb.tablolar["stok_hareketleri"] if r.get("basarili") is False]
    assert [(r["sku"], r["depo"]) for r in bas] == [("YOK1", "MERKEZ DEPO")]
    assert _dagilim(stokdb, "X24")[1] == 15


def test_kart_ac_ile_yeni_kart_ve_giris(stokdb):
    """kart_ac=True: 'YENI1' kartı açılır (bizim 0), +6 HAPPY LIFE girişi → bizim 6."""
    from kayranpm.database import stok_hareket_coklu
    assert stok_hareket_coklu({"YENI1": 6}, "HAPPY", kart_ac=True, kart_adlar={"YENI1": "Yeni"}) == (1, [])
    assert _dagilim(stokdb, "YENI1") == ({"HAPPY LIFE": 6}, 6)


# ── Excel toplu satış: akıllı depo düşümü ─────────────────────────────
def test_akilli_dusum_once_merkez_sonra_coktan_aza(stokdb):
    """A1 kırılımı MERKEZ 3, HAPPY 5, ASEL 8 ; satış 14:
       1) MERKEZ'den mevcut 3 → 0 ; 2) kalan 11 diğer SATILABİLİR depolardan (çoktan aza): HAPPY 5 → 0 ;
       ASEL satılabilir depo değil (bizim_stok'a da girmez) → dokunulmaz, 8 kalır ;
       3) kalan 6 MERKEZ'e eksi → −6 ; bizim = −6 + 0 = −6. (Ekim 2026 düzeltmesi: eskiden ASEL 8 → 0.)
       K1 (MERKEZ 1, HAPPY 2) satış 5: MERKEZ 1 → 0, HAPPY 2 → 0, kalan 2 MERKEZ'e eksi → −2 ;
       bizim −2."""
    from satis.database import _stok_akilli_dus
    _stok_akilli_dus({"A1": 14, "K1": 5})
    assert _dagilim(stokdb, "A1") == ({"ASEL DEPO": 8, "MERKEZ DEPO": -6}, -6)
    assert _dagilim(stokdb, "K1") == ({"MERKEZ DEPO": -2}, -2)


def test_akilli_dusum_secili_depo_tamamini_oradan(stokdb):
    """Kullanıcı depo seçtiyse ('happy') otomatik dağıtım YOK: X24 8 adet HAPPY LIFE'tan → 5−8 = −3 ;
       MERKEZ 10 dokunulmaz ; bizim 10 − 3 = 7. Sıfır/eksi adet yok sayılır."""
    from satis.database import _stok_akilli_dus
    _stok_akilli_dus({"X24": 8, "K1": 0, "K1 ": -1}, secili_depo="happy")
    assert _dagilim(stokdb, "X24") == ({"MERKEZ DEPO": 10, "HAPPY LIFE": -3, "İADE DEPO": 3}, 7)
    assert _dagilim(stokdb, "K1") == ({"HAPPY LIFE": 2, "MERKEZ DEPO": 1}, 3)
