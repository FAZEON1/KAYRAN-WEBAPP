# -*- coding: utf-8 -*-
"""Davranış kilidi — İthalat masraf dağıtımı (ithalat.database).

  dosya_hesapla        tek dosya: brüt / indirim / net mal bedeli, masraf yüzdesi (net üzerinden)
  dosya_hesapla_coklu  grup dağıtımı: ORTAK (FOB payı, kuruş-doğru) / HACİM (cbm) / ÖZEL (grup adı)
                       / kategori başına doğrudan dağılım (masraf_grup_dagilim)
  kategori_yuzde_map + kalem_yuzde   kalemin kendi kategorisinin oranı
  dagit_ortak_masraf   birden çok belgeye ortak masrafı NET FOB payıyla yazar (sahte DB)

KURAL (CLAUDE.md): dağıtım kategori adının BİREBİR eşleşmesine dayanır; kayıtlı yazım korunur.
"""
import pytest

from ithalat.database import (dosya_hesapla, dosya_hesapla_coklu, kategori_yuzde_map, kalem_yuzde,
                              masraf_dokumu)


def _k(grup, adet, fob, sku="S"):
    return {"sku": sku, "adet": adet, "birim_fob": fob, "urun_grubu": grup}


# ── dosya_hesapla ─────────────────────────────────────────────────────
def test_tek_dosya_indirimli_yuzde():
    """brüt = 10×50 + 4×25 = 600 ; indirim 60 → net 540 ; masraf navlun 81 + gv 27 = 108
       yüzde = 108 / 540 = %20 (brüt üzerinden olsaydı %18) ; toplam adet 14, kalem 2."""
    h = dosya_hesapla({"masraflar": {"navlun": 81, "gv": 27}, "fatura_indirim": 60},
                      [_k("A", 10, 50), _k("A", 4, 25)])
    assert h == pytest.approx({"mal_bedeli": 600.0, "indirim": 60.0, "net_mal_bedeli": 540.0,
                               "toplam_masraf": 108.0, "maliyet_yuzde": 20.0,
                               "kalem_sayisi": 2, "toplam_adet": 14.0})


def test_tek_dosya_sinirlar_negatif_ve_asiri_indirim():
    """Sınır: negatif indirim 0 sayılır; mal bedelini aşan indirim mal bedeline kırpılır
       (net 0 → yüzde 0, sıfıra bölme yok). Masraf JSON metni de okunur."""
    neg = dosya_hesapla({"masraflar": '{"navlun": 10}', "fatura_indirim": -5}, [_k("A", 1, 100)])
    assert neg["indirim"] == 0 and neg["maliyet_yuzde"] == pytest.approx(10.0)
    asiri = dosya_hesapla({"masraflar": {"navlun": 10}, "fatura_indirim": 500}, [_k("A", 1, 100)])
    assert asiri["indirim"] == 100 and asiri["net_mal_bedeli"] == 0 and asiri["maliyet_yuzde"] == 0.0


def test_eski_sabit_kolonlar_ve_tanimsiz_slug():
    """masraflar boşsa eski kolonlar (navlun/gumruk/sigorta/nakliye/diger) okunur, sıfırlar atlanır:
       navlun 20 + gumruk 30 + nakliye 10 = 60. JSONB'de tanımsız slug ('ozel_x') da toplama girer."""
    eski = {"masraflar": {}, "navlun": 20, "gumruk": 30, "sigorta": 0, "nakliye": 10, "diger": None}
    assert dosya_hesapla(eski, [_k("A", 6, 100)])["toplam_masraf"] == pytest.approx(60.0)
    assert dosya_hesapla(eski, [_k("A", 6, 100)])["maliyet_yuzde"] == pytest.approx(10.0)
    yeni = {"masraflar": {"navlun": 5, "ozel_x": 7}}
    assert [t for _, t in masraf_dokumu(yeni)] == [5.0, 7.0]           # tanım sırası, bilinmeyen sonda
    assert dosya_hesapla(yeni, [_k("A", 1, 120)])["maliyet_yuzde"] == pytest.approx(10.0)


# ── dosya_hesapla_coklu ───────────────────────────────────────────────
def test_coklu_indirim_ortak_ve_ozel():
    """A: 6×100 = 600 FOB ; B: 4×100 = 400 FOB ; indirim 100 → net A 540, B 360 (FOB payıyla)
       navlun 90 ortak → A 90×0,6 = 54, B kalan 36 ; gv 36 → 'B' (özel)
       A: 54 / 540 = %10 ; B: (36+36) / 360 = %20 ; genel toplam masraf 126, ortak 90."""
    d = {"masraflar": {"navlun": 90, "gv": 36}, "fatura_indirim": 100, "grup_masraf_atama": {"gv": "B"}}
    r = dosya_hesapla_coklu(d, [_k("A", 6, 100), _k("B", 4, 100)])
    a, b = r["gruplar"]["A"], r["gruplar"]["B"]
    assert (a["net_fob"], a["ortak_pay"], a["ozel_masraf"], a["yuzde"]) == pytest.approx((540, 54, 0, 10))
    assert (b["net_fob"], b["ortak_pay"], b["ozel_masraf"], b["yuzde"]) == pytest.approx((360, 36, 36, 20))
    assert b["birim_ek_maliyet_orani"] == pytest.approx(0.2)
    assert r["genel"] == pytest.approx({"toplam_fob": 1000, "indirim": 100, "ortak_masraf": 90,
                                        "toplam_masraf": 126, "grup_sayisi": 2})


def test_coklu_kurus_dogru_son_grup_farki_alir():
    """Ortak 100, üç grup eşit FOB (1/3): ilk iki grup round(33,333..) = 33,33,
       SON grup kalan farkı alır: 100 − 66,66 = 33,34. Toplam birebir 100,00."""
    r = dosya_hesapla_coklu({"masraflar": {"navlun": 100}},
                            [_k("A", 1, 10), _k("B", 1, 10), _k("C", 1, 10)])
    paylar = [r["gruplar"][g]["ortak_pay"] for g in ("A", "B", "C")]
    assert paylar == pytest.approx([33.33, 33.33, 33.34])
    assert sum(paylar) == pytest.approx(100.0)


def test_coklu_hacim_cbm_yoksa_ortaga_duser():
    """navlun __hacim__ ama grup_cbm yok → ortak (FOB payı): A 600 / B 400 → 60 / 40 ; %10 / %10.
       cbm verilince (A 1, B 3): A 25, B 75 → %4,1667 / %18,75."""
    kal = [_k("A", 6, 100), _k("B", 4, 100)]
    r = dosya_hesapla_coklu({"masraflar": {"navlun": 100}, "grup_masraf_atama": {"navlun": "__hacim__"}}, kal)
    assert r["gruplar"]["A"]["ortak_pay"] == 60 and r["gruplar"]["A"]["hacim_pay"] == 0
    assert r["gruplar"]["B"]["yuzde"] == pytest.approx(10.0)
    r2 = dosya_hesapla_coklu({"masraflar": {"navlun": 100}, "grup_masraf_atama": {"navlun": "__hacim__"},
                              "grup_cbm": {"A": 1, "B": 3}}, kal)
    assert r2["gruplar"]["A"]["hacim_pay"] == 25 and r2["gruplar"]["B"]["hacim_pay"] == 75
    assert r2["gruplar"]["A"]["yuzde"] == pytest.approx(4.1667)
    assert r2["gruplar"]["B"]["yuzde"] == pytest.approx(18.75)


def test_coklu_kategori_dagilimi_kalan_ortaga():
    """masraf_grup_dagilim navlun {A: 70, B: 10}, navlun toplam 100 → yazılmayan 20 ortağa (FOB payı):
       A 70 + 12 = 82 → %13,6667 ; B 10 + 8 = 18 → %4,5. Dağılımlı kalem grup_atama'yı yok sayar."""
    d = {"masraflar": {"navlun": 100}, "masraf_grup_dagilim": {"navlun": {"A": 70, "B": 10}},
         "grup_masraf_atama": {"navlun": "B"}}
    r = dosya_hesapla_coklu(d, [_k("A", 6, 100), _k("B", 4, 100)])
    assert r["gruplar"]["A"]["toplam_masraf"] == pytest.approx(82)
    assert r["gruplar"]["B"]["toplam_masraf"] == pytest.approx(18)
    assert r["gruplar"]["A"]["yuzde"] == pytest.approx(13.6667)
    assert r["gruplar"]["B"]["yuzde"] == pytest.approx(4.5)


def test_coklu_kategori_adi_birebir_eslesir_yazim_farki_ortaga():
    """Grup adı BİREBİR eşleşir: atama 'monitör' (küçük) ama kalem grubu 'MONİTÖR' → hedef grup
       bulunmaz, gv 50 ORTAĞA düşer: MONİTÖR 600 / KASA 400 → 30 / 20 → ikisi de %5.
       (Okumada birleştirme yapılmaz; kayıtlı yazım korunur — bilinçli davranış.)
       Aynı yazımla ('MONİTÖR') gv tamamen MONİTÖR'e: 50/600 = %8,3333, KASA %0."""
    kal = [_k("MONİTÖR", 6, 100), _k("KASA", 4, 100)]
    r = dosya_hesapla_coklu({"masraflar": {"gv": 50}, "grup_masraf_atama": {"gv": "monitör"}}, kal)
    assert r["gruplar"]["MONİTÖR"]["yuzde"] == pytest.approx(5.0)
    assert r["gruplar"]["KASA"]["yuzde"] == pytest.approx(5.0)
    r2 = dosya_hesapla_coklu({"masraflar": {"gv": 50}, "grup_masraf_atama": {"gv": "MONİTÖR"}}, kal)
    assert r2["gruplar"]["MONİTÖR"]["yuzde"] == pytest.approx(8.3333)
    assert r2["gruplar"]["KASA"]["yuzde"] == 0


def test_kategori_yuzde_map_ve_kalem_yuzde():
    """Tek grup (atama yok) → yalnız '__vars__' dosya ortalaması: 40/400 = %10.
       Çoklu: A %10, B %20 (yukarıdaki indirimli örnek), bilinmeyen grup / boş grup ('GENEL' yok)
       → dosya ortalaması 126/900 = %14."""
    assert kategori_yuzde_map({"masraflar": {"navlun": 40}}, [_k("A", 4, 100)]) == pytest.approx({"__vars__": 10.0})
    d = {"masraflar": {"navlun": 90, "gv": 36}, "fatura_indirim": 100, "grup_masraf_atama": {"gv": "B"}}
    kal = [_k("A", 6, 100), _k("B", 4, 100)]
    y = kategori_yuzde_map(d, kal)
    assert y == pytest.approx({"__vars__": 14.0, "A": 10.0, "B": 20.0})
    assert kalem_yuzde(y, {"urun_grubu": " B "}) == pytest.approx(20.0)
    assert kalem_yuzde(y, {"urun_grubu": "C"}) == pytest.approx(14.0)
    assert kalem_yuzde(y, {"urun_grubu": ""}) == pytest.approx(14.0)


# ── dagit_ortak_masraf (sahte DB'ye yazar) ────────────────────────────
def _dagit_db(sahte_db):
    dosyalar = [{"id": 1, "tarih": "2026-01-01", "fatura_indirim": 100, "masraflar": {"navlun": 5, "gv": 77}},
                {"id": 2, "tarih": "2026-01-02", "masraflar": {}},
                {"id": 3, "tarih": "2026-01-03", "masraflar": {"diger": 9}}]
    kalemler = [{"id": 10, "dosya_id": 1, "sku": "A", "adet": 10, "birim_fob": 100, "urun_grubu": "X"},
                {"id": 20, "dosya_id": 2, "sku": "B", "adet": 6, "birim_fob": 100, "urun_grubu": "X"},
                {"id": 30, "dosya_id": 3, "sku": "C", "adet": 5, "birim_fob": 100, "urun_grubu": "X"}]
    return sahte_db(ithalat_dosyalari=dosyalar, ithalat_kalemleri=kalemler, urunler=[])


def test_dagit_ortak_masraf_net_fob_payi(sahte_db, monkeypatch):
    """Net FOB: D1 1.000−100 = 900, D2 600, D3 500 → toplam 2.000 (paylar %45 / %30 / %25)
       navlun 1.000 → 450 / 300 / 250 (D1'in eski navlun 5'i EZİLİR, gv 77 korunur)
       gumruk_musavirligi 100 → 45 / 30 / 25 ; D3'ün diger 9'u korunur ; kur 38,12345 yazılır."""
    import ithalat.database as idb
    db = _dagit_db(sahte_db)
    monkeypatch.setattr(idb, "_get_client", lambda: db)
    ok, _ = idb.dagit_ortak_masraf([1, 2, 3], {"navlun": 1000, "gumruk_musavirligi": 100}, kur=38.12345)
    assert ok
    m = {d["id"]: d["masraflar"] for d in db.tablolar["ithalat_dosyalari"]}
    assert m[1] == pytest.approx({"navlun": 450, "gv": 77, "gumruk_musavirligi": 45})
    assert m[2] == pytest.approx({"navlun": 300, "gumruk_musavirligi": 30})
    assert m[3] == pytest.approx({"diger": 9, "navlun": 250, "gumruk_musavirligi": 25})
    assert all(d["kur"] == pytest.approx(38.12345) for d in db.tablolar["ithalat_dosyalari"])


def test_dagit_ortak_masraf_esit_bolum_ve_silme(sahte_db, monkeypatch):
    """Sınır: seçili belgelerin FOB'u 0 → eşit bölüm, kuruş-doğru: 100 → 33,33 / 33,33 / 33,34.
       sil=['gv'] → D1'in gv'si kaldırılır."""
    import ithalat.database as idb
    db = _dagit_db(sahte_db)
    db.tablolar["ithalat_kalemleri"] = []
    monkeypatch.setattr(idb, "_get_client", lambda: db)
    ok, _ = idb.dagit_ortak_masraf([1, 2, 3], {"navlun": 100}, sil=["gv"])
    assert ok
    m = {d["id"]: d["masraflar"] for d in db.tablolar["ithalat_dosyalari"]}
    assert [m[i]["navlun"] for i in (1, 2, 3)] == pytest.approx([33.33, 33.33, 33.34])
    assert "gv" not in m[1]


def test_dagit_ortak_masraf_bos_giris_yazmaz(sahte_db, monkeypatch):
    """Tutar / silme / kur yok → reddedilir, veritabanına hiçbir şey yazılmaz."""
    import ithalat.database as idb
    db = _dagit_db(sahte_db)
    monkeypatch.setattr(idb, "_get_client", lambda: db)
    ok, _ = idb.dagit_ortak_masraf([1, 2], {"navlun": 0})
    assert ok is False
    assert not [g for g in db.gunluk if g[0] != "select"]
