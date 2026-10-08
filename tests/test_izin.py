# -*- coding: utf-8 -*-
"""Çalışan izinleri (Ekim 2026): 4857 sayılı İş Kanunu md. 53 / 56 / ek md. 2 kuralları, resmi tatil ve
arife sayımı, bakiye ve devir, talep denetimi, bordro dökümü, ekran parçaları ve programa bağlantılar."""
from datetime import date
from pathlib import Path

from shared import izin_hesap as H
from shared import tatil as T

KOK = Path(__file__).resolve().parent.parent
BUGUN = date(2026, 10, 8)
d = date


# ── Resmi tatiller ──────────────────────────────────────────────────
def test_tatil_2026_eksiksiz():
    t = T.yil_tatilleri(2026)
    assert t[d(2026, 3, 19)] == ("Ramazan Bayramı arifesi", 0.5)
    assert [t[d(2026, 3, g)][1] for g in (20, 21, 22)] == [1.0, 1.0, 1.0]
    assert t[d(2026, 5, 26)][1] == 0.5 and all(t[d(2026, 5, g)][1] == 1.0 for g in (27, 28, 29, 30))
    assert t[d(2026, 10, 28)] == ("Cumhuriyet Bayramı arifesi", 0.5) and t[d(2026, 10, 29)][1] == 1.0
    assert d(2026, 5, 31) not in t and d(2026, 3, 23) not in t
    # yıl toplamı: 7 sabit + 28 Ekim yarım + Ramazan 3,5 + Kurban 4,5 = 15,5 gün
    assert sum(o for _a, o in t.values()) == 15.5


def test_diyanet_tarihleri():
    assert T.DINI_BAYRAMLAR[2025] == (d(2025, 3, 30), d(2025, 6, 6))
    assert T.DINI_BAYRAMLAR[2027] == (d(2027, 3, 9), d(2027, 5, 16))
    assert T.DINI_BAYRAMLAR[2028] == (d(2028, 2, 26), d(2028, 5, 5))
    assert T.bilinen_yil(2028) and not T.bilinen_yil(2029)


def test_ana_sayfa_sayaci_ayni_kaynaktan():
    """Ana sayfa sayacı shared/tatil'den okur; 2028 Ramazan Bayramı 27 değil 26 Şubat (Diyanet)."""
    import gunluk
    assert ("2028-02-26", "Ramazan Bayramı") in gunluk._TATILLER
    assert ("2028-02-27", "Ramazan Bayramı") not in gunluk._TATILLER
    assert ("2027-05-16", "Kurban Bayramı") in gunluk._TATILLER
    assert not any("arife" in a or "gün" in a.split()[-1] for _g, a in gunluk._TATILLER)
    assert [g for g, _a in gunluk._TATILLER] == sorted(g for g, _a in gunluk._TATILLER)


# ── Gün sayımı ──────────────────────────────────────────────────────
def test_hafta_ici_ve_cumartesi():
    assert H.izin_gunu(d(2026, 10, 12), d(2026, 10, 16)) == 5            # Pzt–Cum
    assert H.izin_gunu(d(2026, 10, 12), d(2026, 10, 18)) == 5            # + hafta sonu düşmez
    assert H.izin_gunu(d(2026, 10, 12), d(2026, 10, 18), cumartesi=True) == 6
    assert H.izin_gunu(d(2026, 10, 17), d(2026, 10, 18)) == 0            # yalnız hafta sonu


def test_resmi_tatil_ve_arife_dusulmez():
    # 26–30 Ekim 2026: Pzt 1 + Sal 1 + Çar (28 Ekim) 0,5 + Per (29 Ekim) 0 + Cum 1 = 3,5
    assert H.izin_gunu(d(2026, 10, 26), d(2026, 10, 30)) == 3.5
    # 16–20 Mart 2026: 3 gün + arife 0,5 + bayram 1. gün 0
    assert H.izin_gunu(d(2026, 3, 16), d(2026, 3, 20)) == 3.5
    # Kurban 2026, 25 Mayıs Pzt – 1 Haziran Pzt: 25 (1) + 26 arife (0,5) + 27–30 bayram + 31 Pazar + 1 Haz (1)
    assert H.izin_gunu(d(2026, 5, 25), d(2026, 6, 1)) == 2.5


def test_yarim_gun():
    assert H.izin_gunu(d(2026, 10, 14), d(2026, 10, 14), yarim=True) == 0.5
    assert H.izin_gunu(d(2026, 10, 28), d(2026, 10, 28), yarim=True) == 0.5     # arife zaten yarım
    assert H.izin_gunu(d(2026, 10, 18), d(2026, 10, 18), yarim=True) == 0       # Pazar
    assert H.izin_gunu(d(2026, 10, 14), d(2026, 10, 15), yarim=True) == 0       # tek gün değil
    assert H.izin_gunu(d(2026, 10, 15), d(2026, 10, 14)) == 0                   # ters aralık


def test_gun_dokumu_nedenleri():
    dk = {g: (v, n) for g, v, n in H.gun_dokumu(d(2026, 10, 24), d(2026, 10, 29))}
    assert dk[d(2026, 10, 24)] == (0.0, "Cumartesi") and dk[d(2026, 10, 25)] == (0.0, "Pazar")
    assert dk[d(2026, 10, 28)] == (0.5, "Cumhuriyet Bayramı arifesi")
    assert dk[d(2026, 10, 29)] == (0.0, "Cumhuriyet Bayramı") and dk[d(2026, 10, 26)] == (1.0, "")
    assert H.takvim_gunu(d(2026, 10, 24), d(2026, 10, 29)) == 6


# ── Yıllık izin hakkı (md. 53) ──────────────────────────────────────
def test_kidem_sinirlari():
    assert [H.yillik_hak(n) for n in (0, 1, 5, 6, 14, 15, 30)] == [0, 14, 14, 20, 20, 26, 26]


def test_yas_kurali():
    assert H.yillik_hak(1, 18) == 20 and H.yillik_hak(1, 19) == 14
    assert H.yillik_hak(3, 50) == 20 and H.yillik_hak(3, 49) == 14
    assert H.yillik_hak(16, 55) == 26                                  # 26 zaten 20'den fazla
    assert H.yillik_hak(0, 17) == 0                                    # hak bir yıl dolmadan doğmaz


def test_hak_edisler_yil_donumunde():
    h = H.hak_edisler(d(2019, 10, 9), d(1974, 6, 1), BUGUN)
    assert [x["tarih"] for x in h] == [d(y, 10, 9) for y in range(2020, 2026)]   # 2026'nınki yarın
    assert [x["gun"] for x in h] == [14, 14, 14, 14, 20, 20]          # 2024'te 50 yaş (5. yıl) → en az 20
    assert H.sonraki_hak(d(2019, 10, 9), d(1975, 1, 1), BUGUN) == {"tarih": d(2026, 10, 9), "kidem": 7, "gun": 20}
    # 29 Şubat'ta işe giren: artık olmayan yılda 28 Şubat
    assert [x["tarih"] for x in H.hak_edisler(d(2020, 2, 29), None, d(2025, 3, 1))][:2] == [d(2021, 2, 28),
                                                                                          d(2022, 2, 28)]
    # işten çıkıştan sonra hak doğmaz
    assert len(H.hak_edisler(d(2020, 1, 10), None, BUGUN, cikis=d(2023, 1, 9))) == 2


def test_kidem_ve_yas():
    assert H.kidem(d(2021, 3, 15), BUGUN) == (5, 6)
    assert H.kidem(d(2026, 10, 9), BUGUN) == (0, 0)
    assert H.yas(d(1976, 10, 9), BUGUN) == 49 and H.yas(d(1976, 10, 8), BUGUN) == 50


# ── Bakiye ──────────────────────────────────────────────────────────
def _t(tur, bas, bit, gun, durum="onaylandi", i=0, **k):
    return dict(id=i, personel="ali", tur=tur, baslangic=bas.isoformat(), bitis=bit.isoformat(), gun=gun,
                durum=durum, **k)


ALI = {"kod": "ali", "ad": "Ali Veli", "ise_giris": "2021-03-15", "dogum_tarihi": "1990-05-05",
       "departman": "Depo"}


def test_bakiye_hak_kullanilan_planlanan_bekleyen():
    t = [_t("yillik", d(2026, 6, 1), d(2026, 6, 12), 10, i=1),
         _t("yillik", d(2026, 11, 2), d(2026, 11, 6), 5, i=2),               # ileri tarihli onaylı
         _t("yillik", d(2026, 12, 1), d(2026, 12, 3), 3, "bekliyor", i=3),
         _t("yillik", d(2026, 4, 1), d(2026, 4, 3), 3, "reddedildi", i=4),
         _t("yillik", d(2026, 2, 2), d(2026, 2, 2), 1, "iptal", i=5),
         _t("rapor", d(2026, 1, 5), d(2026, 1, 9), 5, i=6)]                  # yıllıktan düşmez
    b = H.bakiye(ALI, t, BUGUN)
    assert b["hak_edilen"] == 70                                             # 2022–2026, 5 × 14
    assert (b["kullanilan"], b["planlanan"], b["bekleyen"]) == (10, 5, 3)
    assert b["kalan"] == 55 and b["kullanilabilir"] == 52
    assert b["hak_basladi"] and b["bu_yil_hak"] == 14 and b["kidem"] == (5, 6)
    assert b["sonraki"] == {"tarih": d(2027, 3, 15), "kidem": 6, "gun": 20}


def test_bakiye_devir_sonrasi():
    p = dict(ALI, devir_tarihi="2025-12-31", devir_gun=12.5)
    t = [_t("yillik", d(2025, 8, 4), d(2025, 8, 8), 5, i=1),                 # devirden önce: sayılmaz
         _t("yillik", d(2026, 7, 6), d(2026, 7, 10), 5, i=2)]
    b = H.bakiye(p, t, BUGUN)
    assert b["devir"] == 12.5 and b["hak_edilen"] == 14                      # yalnız 15.03.2026
    assert b["kullanilan"] == 5 and b["kalan"] == 21.5


def test_bakiye_ilk_yil_ve_cikis():
    yeni = dict(ALI, ise_giris="2026-05-04")
    b = H.bakiye(yeni, [], BUGUN)
    assert b["hak_edilen"] == 0 and not b["hak_basladi"] and b["sonraki"]["tarih"] == d(2027, 5, 4)
    ayrilan = dict(ALI, cikis_tarihi="2024-01-31")
    b = H.bakiye(ayrilan, [], BUGUN)
    assert b["hak_edilen"] == 28 and b["sonraki"] is None and b["kidem"] == (2, 10)


# ── Talep denetimi ──────────────────────────────────────────────────
def _denetle(tur, bas, bit, talepler=(), p=ALI, yarim=False, ayni=None):
    return H.denetle(tur, bas, bit, H.izin_gunu(bas, bit, yarim=yarim), p, list(talepler), BUGUN,
                     yarim=yarim, ayni_bolum=ayni)


def test_denetim_hatalari():
    assert _denetle("yillik", d(2026, 10, 16), d(2026, 10, 12))[0] == ["Bitiş tarihi başlangıçtan önce olamaz."]
    assert "hafta sonu" in _denetle("yillik", d(2026, 10, 17), d(2026, 10, 18))[0][0]
    assert _denetle("yillik", d(2026, 10, 12), d(2026, 10, 13), yarim=True)[0] == [
        "Yarım gün izin tek bir gün için seçilebilir."]
    h, _u = _denetle("yillik", d(2021, 3, 1), d(2021, 3, 5))
    assert h and "İşe giriş" in h[0]
    var = [_t("yillik", d(2026, 10, 14), d(2026, 10, 20), 5, "bekliyor", i=9)]
    h, _u = _denetle("yillik", d(2026, 10, 19), d(2026, 10, 23), var)
    assert len(h) == 1 and "onay bekliyor" in h[0] and "14.10.2026 – 20.10.2026" in h[0]
    assert not _denetle("yillik", d(2026, 10, 21), d(2026, 10, 23), var)[0]            # bitişik, çakışmıyor
    reddedilen = [dict(var[0], durum="reddedildi")]
    assert not _denetle("yillik", d(2026, 10, 19), d(2026, 10, 23), reddedilen)[0]
    assert not _denetle("rapor", d(2026, 10, 17), d(2026, 10, 18))[0]                  # rapor hafta sonu olabilir


def test_denetim_uyarilari():
    _h, u = _denetle("yillik", d(2026, 10, 12), d(2026, 10, 16),
                     [_t("yillik", d(2026, 1, 5), d(2026, 3, 27), 67, i=1)])
    assert u == ["Kalan izin 3 gün; bu talep 5 gün. Onaylanırsa 2 gün avans izin olur."]
    _h, u = _denetle("yillik", d(2026, 10, 12), d(2026, 10, 13), p=dict(ALI, ise_giris="2026-05-04"))
    assert u[0].startswith("Yıllık izin hakkı henüz doğmadı (ilk hak 04.05.2027, 14 gün)")
    _h, u = _denetle("evlilik", d(2026, 10, 12), d(2026, 10, 15))
    assert u == ["Evlilik izni yasal olarak 3 gün; bu talep 4 gün."]
    _h, u = _denetle("engelli_cocuk", d(2026, 10, 12), d(2026, 10, 16),
                     [_t("engelli_cocuk", d(2026, 2, 2), d(2026, 2, 9), 6, i=1),
                      _t("engelli_cocuk", d(2025, 2, 3), d(2025, 2, 7), 5, i=2)])           # geçen yıl sayılmaz
    assert u == ["Engelli çocuk tedavi izni yılda en çok 10 gün; bu yıl 6 gün kullanıldı, bu talep 5 gün."]
    _h, u = _denetle("rapor", d(2029, 1, 8), d(2029, 1, 9))
    assert u == ["2029 yılının bayram tarihleri programda henüz yok; bayrama denk gelen günler izinden "
                 "düşülmüş olabilir."]
    _h, u = _denetle("idari", d(2026, 9, 1), d(2026, 9, 1))
    assert u == ["Geçmiş tarihli izin: kayıt amaçlı giriliyor."]
    _h, u = _denetle("idari", d(2026, 10, 12), d(2026, 10, 12),
                     ayni=[{"personel_ad": "Ayşe", "baslangic": "2026-10-12", "bitis": "2026-10-13"}])
    assert u == ["Aynı bölümden Ayşe da izinli: 12.10.2026 – 13.10.2026."]


def test_ayni_bolumdekiler():
    pers = [ALI, {"kod": "ayse", "ad": "Ayşe", "departman": "Depo"}, {"kod": "can", "ad": "Can",
                                                                       "departman": "Muhasebe"}]
    tal = [dict(_t("yillik", d(2026, 10, 12), d(2026, 10, 13), 2, i=1), personel="ayse"),
           dict(_t("yillik", d(2026, 10, 12), d(2026, 10, 13), 2, i=2), personel="can"),
           dict(_t("yillik", d(2026, 10, 12), d(2026, 10, 13), 2, "iptal", i=3), personel="ayse")]
    r = H.ayni_bolumdekiler(d(2026, 10, 13), d(2026, 10, 15), "ali", "Depo", pers, tal)
    assert [(x["personel_ad"], x["id"]) for x in r] == [("Ayşe", 1)]
    assert H.ayni_bolumdekiler(d(2026, 10, 13), d(2026, 10, 15), "ali", "", pers, tal) == []


# ── Takvim, döküm, rapor ────────────────────────────────────────────
def test_takvim_ay_siniri():
    tal = [_t("yillik", d(2026, 9, 28), d(2026, 10, 2), 5, i=1),
           _t("rapor", d(2026, 10, 30), d(2026, 11, 3), 3, "bekliyor", i=2),
           _t("idari", d(2026, 10, 20), d(2026, 10, 20), 1, "reddedildi", i=3)]
    s = H.takvim(2026, 10, [ALI], tal)[0]
    assert sorted(s["gunler"]) == [d(2026, 10, 1), d(2026, 10, 2), d(2026, 10, 30), d(2026, 10, 31)]
    assert s["gunler"][d(2026, 10, 30)] == ("rapor", "bekliyor")


def test_donem_dokumu_ay_sinirinda_boler():
    tal = [_t("yillik", d(2026, 9, 28), d(2026, 10, 2), 5, i=1),
           _t("ucretsiz", d(2026, 10, 12), d(2026, 10, 18), 5, i=2),
           _t("yillik", d(2026, 10, 20), d(2026, 10, 20), 1, "bekliyor", i=3)]       # onaysız: dökümde yok
    ek = H.donem_dokumu(tal, d(2026, 10, 1), d(2026, 10, 31), {"ali": "Ali Veli"})
    assert [(r["Tür"], r["Başlangıç"], r["İş günü"], r["Takvim günü"], r["Ücretli"]) for r in ek] == [
        ("Yıllık izin", d(2026, 10, 1), 2, 2, "Evet"), ("Ücretsiz izin", d(2026, 10, 12), 5, 7, "Hayır")]
    ey = H.donem_dokumu(tal, d(2026, 9, 1), d(2026, 9, 30), {"ali": "Ali Veli"})
    assert [(r["Bitiş"], r["İş günü"]) for r in ey] == [(d(2026, 9, 30), 3)]


def test_bakiye_tablosu():
    r = H.bakiye_tablosu([ALI, dict(ALI, kod="eski", ad="Eski", cikis_tarihi="2024-01-31")],
                         [_t("yillik", d(2026, 6, 1), d(2026, 6, 5), 5, i=1),
                          _t("rapor", d(2026, 2, 2), d(2026, 2, 3), 2, i=2)], BUGUN)
    assert [x["Personel"] for x in r] == ["Ali Veli", "Eski (ayrıldı)"]          # ayrılan en altta
    assert r[0]["Kalan"] == 65 and r[0]["Diğer izin 2026"] == 2 and r[0]["Kıdem"] == "5 yıl 6 ay"
    assert r[0]["Sonraki hak"] == "15.03.2027 · 20 gün"
    sira = sorted(["Zeynep", "İbrahim", "Çağlar", "Işıl", "Ali", "Ömer", "Derya"], key=H.tr_sira)
    assert sira == ["Ali", "Çağlar", "Derya", "Işıl", "İbrahim", "Ömer", "Zeynep"]


def test_bicim_ve_metinler():
    assert [H.tr_gun(x) for x in (3, 2.5, -1.5, 0)] == ["3 gün", "2,5 gün", "-1,5 gün", "0 gün"]
    t = _t("yillik", d(2026, 10, 12), d(2026, 10, 16), 5)
    assert H.talep_ozeti(t) == "Yıllık izin · 12.10.2026 – 16.10.2026 · 5 gün"
    assert H.talep_ozeti(dict(_t("idari", d(2026, 10, 12), d(2026, 10, 12), 0.5), yarim_gun=True)) == \
        "İdari izin · 12.10.2026 · 0,5 gün (yarım gün)"
    konu, html = H.mail_yeni("Ali Veli", t)
    assert konu == "[KAYRAN İzin] Ali Veli · Yıllık izin" and "12.10.2026 – 16.10.2026" in html and "?s=izin" in html
    konu, html = H.mail_karar(t, False, "İbrahim", "Yoğun dönem")
    assert konu == "[KAYRAN İzin] Talebin reddedildi" and "Yoğun dönem" in html
    assert H.bildirim_karar(t, True, "İbrahim").startswith("İzin talebin onaylandı: Yıllık izin")


def test_turler_yasal():
    assert {k: v["sinir"] for k, v in H.TURLER.items() if v["sinir"]} == {
        "evlilik": 3, "babalik": 5, "olum": 3, "evlat_edinme": 3, "engelli_cocuk": 10}
    assert [k for k, v in H.TURLER.items() if v["duser"]] == ["yillik"]
    assert {k for k, v in H.TURLER.items() if not v["ucretli"]} == {"rapor", "dogum", "ucretsiz"}


# ── Ekran parçaları (saf) ───────────────────────────────────────────
def test_takvim_html():
    from shared.izin_ekran import takvim_html
    s = H.takvim(2026, 10, [ALI], [_t("rapor", d(2026, 10, 12), d(2026, 10, 13), 2, i=1),
                                   _t("yillik", d(2026, 10, 20), d(2026, 10, 20), 1, "bekliyor", i=2)])
    h = takvim_html(2026, 10, s, BUGUN)
    assert h.count("<th class=") == 31 + 1 and 'title="Cumhuriyet Bayramı"' in h
    assert h.count('title="Sağlık raporu · Onaylandı"') == 2 and 'class="izn-c bk"' in h
    gizli = takvim_html(2026, 10, s, BUGUN, ayrinti=False)
    assert "Sağlık raporu" not in gizli and 'title="İzinli · Onaylandı"' in gizli


def test_personel_denetle():
    from shared.izin_ekran import personel_denetle
    assert personel_denetle("ahmet", True, d(2020, 1, 1), None, None, None, None, set()) == []
    assert "Kod" in personel_denetle("A", True, d(2020, 1, 1), None, None, None, None, set())[0]
    assert "zaten var" in personel_denetle("ali", True, d(2020, 1, 1), None, None, None, None, {"ali"})[0]
    assert personel_denetle("ali", False, None, None, None, None, None, {"ali"}) == [
        "İşe giriş tarihi gerekli (yıllık izin hakkı buna göre hesaplanır)."]
    h = personel_denetle("ali", False, d(2020, 1, 1), d(2010, 1, 1), d(2019, 1, 1), 5, d(2019, 6, 1), set())
    assert len(h) == 3                                    # 14 yaş altı, devir girişten önce, çıkış girişten önce


# ── Programa bağlantı ───────────────────────────────────────────────
def test_baglantilar():
    from shared.gezinme import SISTEM, hedef
    from shared.yetki import OZEL, OZEL_ADI
    assert ("izin", "İzinler", "event_available", None) in SISTEM and hedef("sistem/izin")["modul"] == "izin"
    assert "izin_yonetimi" in OZEL and OZEL_ADI["izin_yonetimi"] == "İzin yönetimi"
    app = (KOK / "app.py").read_text(encoding="utf-8")
    assert 'elif aktif == "izin":' in app and 'args=("izin",)' in app
    assert 'ozel_yetki(kullanici, "izin_yonetimi") or ozel_yetki(kullanici, "kullanici_yonetimi")' in app
    assert "izin_yoneticisi=izin_yoneticisi(aktif_kullanici)" in app
    from yonetim import YEDEK_TABLOLAR
    assert {"personel", "izin_talepleri"} <= set(YEDEK_TABLOLAR)
    from shared.bt_hesap import YASAK_YOLLAR
    assert "izin" in YASAK_YOLLAR and "personel" in YASAK_YOLLAR
    sql = (KOK / "veritabani/26_izin.sql").read_text(encoding="utf-8")
    for p in ("CREATE TABLE IF NOT EXISTS personel", "CREATE TABLE IF NOT EXISTS izin_talepleri",
              "REFERENCES personel (kod)", "CHECK (bitis >= baslangic)", "ENABLE ROW LEVEL SECURITY"):
        assert p in sql, p


def test_bugun_maddeleri():
    from shared.bugun import maddeler_izin
    tal = [_t("yillik", d(2026, 10, 20), d(2026, 10, 21), 2, "bekliyor", i=1),
           _t("yillik", d(2026, 10, 14), d(2026, 10, 14), 1, "bekliyor", i=2),
           _t("rapor", d(2026, 10, 7), d(2026, 10, 9), 3, i=3),
           _t("idari", d(2026, 10, 8), d(2026, 10, 8), 1, "iptal", i=4)]
    m = maddeler_izin(tal, [ALI], BUGUN)
    assert [(x["baslik"], x["sayi"], x["hedef"], x["oncelik"]) for x in m] == [
        ("Onay bekleyen izin talebi", 2, "izin", "uyari"), ("Bugün izinde", 1, "izin", "bilgi")]
    assert m[0]["detay"].startswith("En yakını 2026-10-14") and m[1]["detay"] == "Ali Veli"
    assert maddeler_izin([], [], BUGUN) == []


# ── İzin formu ve izin kayıt belgesi (içerik; PDF çizimi tests/duman/test_izin_formu.py) ──
def test_form_icerik_yillik():
    from shared.izin_belge import belge_no, form_icerik
    p = dict(ALI, sicil_no="0012")
    t = _t("yillik", d(2026, 10, 19), d(2026, 10, 23), 5, i=7, yol_izni=2, izin_adresi="Trabzon",
           karar_veren="ibrahim", karar_zamani="2026-10-08T15:20:00+03:00", takvim_gunu=5)
    onceki = _t("yillik", d(2026, 6, 1), d(2026, 6, 5), 5, i=3)
    sonraki = _t("yillik", d(2026, 12, 7), d(2026, 12, 11), 5, i=9)              # bu izinden sonra: düşülmez
    ic = form_icerik(t, p, [t, onceki, sonraki], BUGUN)
    assert ic["baslik"] == "YILLIK ÜCRETLİ İZİN FORMU" and ic["no"] == belge_no(t) == "IZN-2026-00007"
    c = dict(ic["calisan"])
    assert c["Sicil no"] == "0012" and c["İşe giriş tarihi"] == "15.03.2021"
    assert c["İşyerindeki çalışma süresi"] == "5 yıl 7 ay"
    z = dict(ic["izin"])
    assert z["İzin süresi"] == "5 gün (iş günü) · 5 takvim günü" and z["Yol izni (ücretsiz)"] == "2 gün"
    assert z["İşe başlama tarihi"] == "26.10.2026"                     # Cuma bitiş + 2 gün yol izni → Pazartesi
    assert z["İzinde bulunacağı adres / telefon"] == "Trabzon"
    b = dict(ic["bakiye"])
    assert b["Yıllık izne hak kazanılan son tarih"] == "15.03.2026"
    assert (b["Bu izinden önceki kalan"], b["Bu izinden sonra kalan"]) == ("65 gün", "60 gün")
    assert "başka bir işte ücret karşılığı çalışmayacağımı" in ic["beyan"]
    assert ic["onay"] == "Programda onaylandı: İbrahim, 2026-10-08 15:20"
    assert [r for r, _a in ic["imzalar"]] == ["İzni isteyen çalışan", "Birim yöneticisi", "İşveren / işveren vekili"]


def test_form_icerik_diger_turler():
    from shared.izin_belge import form_icerik
    r = form_icerik(_t("rapor", d(2026, 2, 2), d(2026, 2, 3), 2, i=4), ALI, [], BUGUN)
    assert r["baslik"] == "İZİN FORMU · SAĞLIK RAPORU" and r["bakiye"] is None
    assert dict(r["izin"])["İzin türü"] == "Sağlık raporu (ödeme SGK'dan)" and "hekim raporum" in r["beyan"]
    assert "Yol izni (ücretsiz)" not in dict(r["izin"])
    u = form_icerik(_t("ucretsiz", d(2026, 2, 2), d(2026, 2, 3), 2, "bekliyor", i=5), ALI, [], BUGUN)
    assert dict(u["izin"])["İzin türü"] == "Ücretsiz izin" and u["onay"] == "Programda onay bekliyor."
    e = form_icerik(_t("evlilik", d(2026, 2, 2), d(2026, 2, 4), 3, i=6), ALI, [], BUGUN)
    assert e["baslik"] == "İZİN FORMU · EVLİLİK İZNİ" and e["onay"] == "Programda onaylandı."


def test_kayit_belgesi_icerik():
    from shared.izin_belge import kayit_belgesi_icerik
    tal = [_t("yillik", d(2026, 10, 19), d(2026, 10, 23), 5, i=7, yol_izni=2),
           _t("yillik", d(2026, 6, 1), d(2026, 6, 5), 5, i=3),
           _t("yillik", d(2026, 12, 1), d(2026, 12, 2), 2, "bekliyor", i=8),          # onaysız: girmez
           _t("rapor", d(2026, 2, 2), d(2026, 2, 3), 2, i=4)]                        # yıllık değil: girmez
    ic = kayit_belgesi_icerik(dict(ALI, sicil_no="0012"), tal, BUGUN)
    assert [h["Yıllık izne hak kazanılan tarih"] for h in ic["haklar"]] == [
        "15.03.2022", "15.03.2023", "15.03.2024", "15.03.2025", "15.03.2026"]
    assert [(r["Belge no"], r["İzin günleri sayısı"], r["Yol izni günleri sayısı"]) for r in ic["izinler"]] == [
        ("IZN-2026-00003", 5.0, 0), ("IZN-2026-00007", 5.0, 2)]
    assert dict(ic["toplam"]) == {"Hak edilen toplam": "70 gün", "Kullanılan (onaylı)": "10 gün",
                                  "Kalan (08.10.2026)": "60 gün"}
    dv = kayit_belgesi_icerik(dict(ALI, devir_tarihi="2025-12-31", devir_gun=6.5), tal, BUGUN)
    assert list(dict(dv["toplam"]))[:2] == ["Devreden izin (31.12.2025 itibarıyla)", "Devirden sonra hak edilen"]


def test_donus_gunu_ve_buyuk_harf():
    from shared.izin_belge import _buyuk, donus_gunu
    assert donus_gunu(d(2026, 10, 23)) == d(2026, 10, 26)                    # Cuma → Pazartesi
    assert donus_gunu(d(2026, 10, 27)) == d(2026, 10, 28)                    # arife yarım gün: iş günü
    assert donus_gunu(d(2026, 10, 28)) == d(2026, 10, 30)                    # 29 Ekim tatil
    assert donus_gunu(d(2026, 10, 23), cumartesi=True) == d(2026, 10, 24)
    assert _buyuk("Evlilik izni") == "EVLİLİK İZNİ" and _buyuk("ışık") == "IŞIK"


def test_dokum_yol_izni():
    tal = [_t("yillik", d(2026, 9, 28), d(2026, 10, 2), 5, i=1, yol_izni=3)]
    assert H.donem_dokumu(tal, d(2026, 10, 1), d(2026, 10, 31), {})[0]["Yol izni (ücretsiz)"] == 3
    assert H.donem_dokumu(tal, d(2026, 9, 1), d(2026, 9, 30), {})[0]["Yol izni (ücretsiz)"] == 0


def test_logo_ve_sql_sutunlari():
    from shared.izin_belge import LOGO, LOGO_ORAN
    assert Path(LOGO).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" and abs(LOGO_ORAN - 386 / 900) < 1e-9
    sql = (KOK / "veritabani/26_izin.sql").read_text(encoding="utf-8")
    for p in ("sicil_no      text", "yol_izni      smallint NOT NULL DEFAULT 0 CHECK (yol_izni BETWEEN 0 AND 4)",
              "ALTER TABLE izin_talepleri ADD COLUMN IF NOT EXISTS yol_izni", "ADD COLUMN IF NOT EXISTS izin_adresi",
              "ALTER TABLE personel ADD COLUMN IF NOT EXISTS sicil_no"):
        assert p in sql, p
    assert "from shared.izin_belge import LOGO, LOGO_ORAN" in (KOK / "depo/belge.py").read_text(encoding="utf-8")


# ── Kart bilgilendirme e-postası (kart ilk açıldığında kendiliğinden, bir kez) ──
def test_bilgi_adresi_ve_kural():
    adr = {"ali": "ali.veli@g5fteknoloji.com"}
    assert H.bilgi_adresi(dict(ALI, eposta="ozel@ornek.com"), adr) == "ozel@ornek.com"      # kart önce
    assert H.bilgi_adresi(ALI, adr) == "ali.veli@g5fteknoloji.com"                         # yoksa kullanıcı adresi
    assert H.bilgi_adresi(dict(ALI, eposta="bozuk adres"), {}) == ""
    assert H.bilgi_gerekli(ALI, adr)
    assert not H.bilgi_gerekli(dict(ALI, bilgi_zamani="2026-10-08T15:00:00+03:00"), adr)    # bir kez
    assert not H.bilgi_gerekli(ALI, {})                                                      # adres yok
    assert not H.bilgi_gerekli(dict(ALI, cikis_tarihi="2026-01-31"), adr)                    # ayrılmış
    assert H.bilgi_durumu(dict(ALI, bilgi_zamani="2026-10-08T15:00:00+03:00"), {}) == "Gönderildi 08.10.2026"
    assert [H.bilgi_durumu(ALI, adr), H.bilgi_durumu(ALI, {}), H.bilgi_durumu(dict(ALI, cikis_tarihi="2026-01-31"), adr)] \
        == ["Gönderilmedi", "Adres yok", "Ayrıldı"]


def test_bilgilendirme_maili():
    konu, html = H.mail_bilgilendirme(dict(ALI, sicil_no="0012"), [_t("yillik", d(2026, 6, 1), d(2026, 6, 5), 5)],
                                      BUGUN, "Serdar")
    assert konu == "[G5F] Personel izin kartınız açıldı"
    for p in ("Merhaba Ali Veli", "0012", "15.03.2021", "5 yıl 6 ay", "14 gün", "65 gün (08.10.2026 itibarıyla)",
              "15.03.2027 · 20 gün", "Serdar ile görüşün", "cid:g5f-logo", "?s=izin", "Talep gönder"):
        assert p in html, p
    assert "parola" not in html.lower().replace("parolanız size ayrıca iletildi", "")


def test_eposta_gomulu_resim():
    from shared.eposta import mesaj_olustur
    m = mesaj_olustur("a@b.com", ["c@d.com"], "Konu", "<img src='cid:logo'><p>x</p>", gomulu=[("logo", b"\x89PNG", "png")])
    parcalar = [p.get_content_type() for p in m.walk()]
    assert parcalar[:4] == ["multipart/alternative", "text/plain", "multipart/related", "text/html"]
    resim = [p for p in m.walk() if p.get_content_type() == "image/png"][0]
    assert resim["Content-ID"] == "<logo>" and resim["Content-Disposition"].startswith("inline")
    sade = mesaj_olustur("a@b.com", ["c@d.com"], "Konu", "<p>x</p>")                          # eski davranış aynı
    assert [p.get_content_type() for p in sade.walk()] == ["multipart/alternative", "text/plain", "text/html"]
