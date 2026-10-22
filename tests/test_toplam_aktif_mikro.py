# -*- coding: utf-8 -*-
"""Kullanıcı (22.10.2026):
- "A olsun": teslim alınmış ama tedarikçi faturası Mikro'ya girilmemiş ithalat, ithalat avansından düşülür
  (canlı: INNOVISION-017 20.10'da irsaliyeyle girdi ve EERA'ya satıldı; 260.800 $ ödeme 320.50.101'de avans olarak
  kaldığı için maliyet iki kez sayılıyordu → ithalat ödenen 622.888 → 362.088 $).
- "Toplam aktiflerden artık upload edilecek dosya olmadığı için muhasebe modülünden toplam aktifleri kaldır": toplam
  her Mikro eşitleme turunda kayranacc/toplam_aktif.py ile hesaplanır, Yönetim panosunda görünür. Canlı karşılaştırma:
  eski sayfanın kaydıyla her kalem ve toplam (1.142.753,22 $) kuruşu kuruşuna aynı.
- 0 bedelli satışta marj "%-26.069.604,0" yerine "bedelsiz".
- Ödemeler Mikro'dan geldiği için Bu hafta'da Mikro satırına "Öde / Geri al / Düzenle / Sil" yok."""
from datetime import date

import pytest

from kayranacc import mikro_muhasebe as MM


# ── (A) Faturası girilmemiş teslim ───────────────────────────────────
def _irs(kod, tutar, fat="", tip=13, doviz=1, iade=0):
    return {"sth_evraktip": tip, "sth_cari_kodu": kod, "sth_normal_iade": iade, "sth_fat_uid": fat,
            "sth_har_doviz_cinsi": doviz, "sth_tutar": tutar, "sth_iskonto": 0}


def _h(kod, tip, meblag, tarih):
    return {"cha_kod": kod, "cha_tip": tip, "cha_meblag": meblag, "cha_tarihi": tarih, "cha_aciklama": "",
            "cha_cari_cins": 0, "cha_d_cins": 1, "cha_d_kur": 49.2, "cha_karsidcinsi": 1, "cha_karsid_kur": 49.2,
            "cha_evrak_tip": 35}


KART = [{"cari_kod": "320.50.101", "cari_unvan1": "INNOVISION", "cari_doviz_cinsi": 1},
        {"cari_kod": "320.50.005", "cari_unvan1": "MASTER", "cari_doviz_cinsi": 1}]


def test_faturasi_girilmemis_teslim_avanstan_duser():
    veri = {"hareket": [_h("320.50.101", 0, 260800, "2026-10-08"), _h("320.50.005", 0, 122425, "2026-10-01")],
            "banka_kart": [], "cari_kart": KART, "cek": [],
            "alim": [_irs("320.50.101", 100000), _irs("320.50.101", 160800),           # INNOVISION-017, faturasız
                     _irs("320.50.005", 50000, fat="8a234955-7b5c-44b4-89d4-065b88a87b33"),  # faturalanmış
                     _irs("320.50.005", 999, fat="00000000-0000-0000-0000-000000000000", iade=1),  # iade
                     _irs("320.50.005", 777, tip=3)]}                                    # ithalat irsaliyesi değil
    p = MM.plan_yap(veri, [], [], None, 622888.27)
    assert p["ithalat"] == pytest.approx(122425)                   # eski kod: 383.225 (avans iki kez)


def test_teslim_avansi_asarsa_eksiye_dusmez():
    assert MM.ithalat_odenen({"320.50.101": 100.0}, KART, {"320.50.101": 260800.0}) == 0
    assert MM.faturasiz_teslimler([_irs("320.50.101", 5, doviz=0)]) == {}       # TL tutarlı satır sayılmaz


# ── Toplam Aktifler hesabı (eski sayfanın formülü) ────────────────────
def _g(**k):
    g = {"stok": [700000.0, {"VATAN": 1.0}], "ithalat": 300000.0,
         "cari": {"borc": {"usd": 1000.0, "tl": 4960.0, "eur": 0.0}, "alacak": {"usd": 5000.0, "tl": 0.0, "eur": 100.0}},
         "bankalar": [{"para_birimi": "USD", "bakiye": 2000}, {"para_birimi": "TL", "bakiye": 49600},
                      {"para_birimi": "EUR", "bakiye": 999}],
         "cek": (9920.0, 500.0), "manuel": [{"id": 4, "aciklama": "EERA HAVUZ BÜTÇE", "tutar": 119000, "tip": "ekle"},
                                           {"id": 5, "aciklama": "Nakit kasa", "tutar": 4960, "para_birimi": "TL",
                                            "tip": "cikar"}],
         "defter": None, "defter_acik": False, "kur": 49.6, "eur_usd": 1.1}
    g.update(k)
    return g


def test_formul_defter_kapali_eski_sayfa_gibi():
    from kayranacc import toplam_aktif as T
    r = T.hesapla(_g())
    assert r["stok"] == pytest.approx(700000 * 1.2) and r["stok_carpan"] == pytest.approx(1.2)
    assert r["banka"] == pytest.approx(2000 + 1000)                      # EUR hesap sayılmaz (eski sayfa)
    assert r["borc"] == pytest.approx(1100) and r["alacak"] == pytest.approx(5110)
    assert r["cek"] == pytest.approx(700) and r["manuel_ekle"] == 119000 and r["manuel_cikar"] == pytest.approx(100)
    assert r["toplam"] == pytest.approx(840000 + 300000 + 3000 + 5110 + 119000 - 1100 - 700 - 100)
    assert r["eksik"] == []


def test_formul_defter_acik_stok_maliyetle_cakisan_manuel_sayilmaz():
    from kayranacc import toplam_aktif as T
    defter = {"kalemler": [{"ad": "Kasa", "tl": 99200.0}, {"ad": "Ödenecek SGK", "tl": -49600.0}],
              "satis_maliyeti": {"oran": 0.02}}
    r = T.hesapla(_g(defter=defter, defter_acik=True))
    assert r["stok_carpan"] == 1.0 and r["stok"] == pytest.approx(700000)
    assert r["defter_arti"] == pytest.approx(2000) and r["defter_eksi"] == pytest.approx(1000)
    assert r["satis_maliyeti"] == pytest.approx(14000)
    assert r["manuel_cikar"] == 0 and r["cakisan"] == {5: "Kasa"}       # "Nakit kasa" Mikro'dan geliyor
    assert r["toplam"] == pytest.approx(700000 + 300000 + 3000 + 5110 + 119000 - 1100 - 700 + 2000 - 1000 - 14000)


def test_eksik_kaynakta_yazilmaz_degisince_yazilir():
    from kayranacc import toplam_aktif as T
    bugun = date(2026, 10, 22)
    r = T.hesapla(_g(cari=None))
    assert r["eksik"] == ["Cari"] and not T.yazilmali_mi(r, {}, bugun)
    r = T.hesapla(_g())
    k = T.kayit(r, bugun)
    assert "eksik" not in k and k["tarih"] == "2026-10-22"
    assert not T.yazilmali_mi(r, k, bugun)                               # aynı gün, aynı toplam
    assert T.yazilmali_mi(r, k, date(2026, 10, 23)) and T.yazilmali_mi(r, dict(k, toplam=1), bugun)


def test_esitleme_turunda_ve_muhasebe_menusunde_degil():
    import otonom.mikro_esitle as E
    from shared.gezinme import secenekler
    moduller = [m for _a, m, _f in E.ISLER]
    assert moduller.index("kayranacc.toplam_aktif") > moduller.index("kayranacc.mikro_aktif")
    assert moduller.index("kayranacc.toplam_aktif") > moduller.index("kayranacc.mikro_stok_degeri")
    assert "💰 Toplam Aktifler" not in secenekler("kayranacc")


# ── 0 bedelli satış ─────────────────────────────────────────────────
def test_bedelsiz_satista_marj_yuzdesi_yok():
    from satis import satis_hesap as SH
    from satis.database import satir_kar
    from satis.satis_masasi import marj_metni, siparis_satirlari
    s = [{"id": 1, "siparis_no": "G5F26-2985", "tarih": "2026-10-22", "kanal": "ÇAĞLAR ENES SEZGİN", "sku": "X24F182S",
          "adet": 1, "birim_satis": 0.0002, "birim_maliyet": 52.14}]
    o = SH.siparis_grupla(s, satir_kar)
    assert o[0]["marj"] is None                                          # eski: -26.069.900
    assert siparis_satirlari(o, True)[0]["marj_m"] == "bedelsiz"
    assert marj_metni(-12.34, 100) == "%-12,3" and marj_metni(-5000, 1) == "%-999,9'dan düşük"
    assert satir_kar(s[0])["marj"] == 0.0


# ── Ödeme listesi: Mikro satırında elle ödeme yok ─────────────────────
def test_mikro_satirinda_ode_yok_elle_satirda_var():
    from kayranacc import odeme_masasi as OM
    odm = [dict(id=1, firma="UPS", vade="2026-10-22", tutar_tl=1000, tutar_usd=0, kategori="cari", durum="bekliyor"),
           dict(id=2, firma="Kira", vade="2026-10-22", tutar_tl=500, tutar_usd=0, kategori="cari", durum="bekliyor")]
    banka = [{"id": 1, "hesap_adi": "YKB TL", "para_birimi": "TL", "bakiye": 5000}]
    v = OM.masa_verisi(odm, banka, {"cari": {"label": "Cari"}}, 49.6, date(2026, 10, 22), mikro_idler={1})
    s = {r["id"]: r for r in v["satirlar"]}
    assert s[1]["mikro"] and not s[2]["mikro"] and "Mikro'dan geliyor" in s[1]["_not"]
    ode = next(i for i in v["islemler"] if i["k"] == "ode")
    assert ["mikro", "ne", True] in ode["f"]
    _t, hata = OM.istek_coz({"tur": "ode", "ids": [1], "banka": 1}, odm, banka, {}, mikro_idler={1})
    assert hata and "Mikro" in hata
    t, hata = OM.istek_coz({"tur": "ode", "ids": [2], "banka": 1}, odm, banka, {}, mikro_idler={1})
    assert hata is None and t["ids"] == [2]
    t, hata = OM.istek_coz({"tur": "otele", "ids": [1], "gun": 7}, odm, banka, {}, mikro_idler={1})
    assert hata is None                                                  # öteleme Mikro satırında da var


def test_mikro_idleri_esleme_kaydindan():
    from kayranacc.mikro_odeme_oto import mikro_idleri
    d = {"haftalar": {"12": {"esleme": {"c|320|2026-10-22": {"id": 7}, "k|1|YKB": {"id": "8"}, "x": {}}}}}
    assert mikro_idleri(12, d) == {7, 8} and mikro_idleri(13, d) == set()
