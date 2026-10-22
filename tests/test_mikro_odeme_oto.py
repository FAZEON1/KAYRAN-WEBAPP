# -*- coding: utf-8 -*-
"""Haftalık ödeme listesi Mikro'dan, her pazartesi kendiliğinden (kayranacc/mikro_odeme_oto.py, 22.10.2026).

Kullanıcı: "Ödeme listesini de Mikro'dan çekelim" → "her pazartesi kendiliğinden açılsın".
Canlı karşılaştırma (22.10.2026, 19.10 haftasının elle yüklenen 22 satırı): tutarlar Mikro'yla aynı, ama
- ödeme planlarının günü Mikro'da 0 (gün yalnız adda: "30 GÜN VADE") → planlı faturalar gecikmiş görünüyordu;
- öneri hareketleri sayfasız okuyordu (320 + 336 = 5.364 hareket) → kesilince ödenmiş kiralar açık görünüyordu.
"""
import datetime as dt
import importlib.util
from pathlib import Path

import pytest

from kayranacc import mikro_odeme as O

try:
    from kayranacc import mikro_odeme_oto as OT
except ImportError:          # eski kodda modül yok: otomatik hafta testleri atlanır; plan günü, sayfalı okuma,
    OT = None                # öğrenme, tur ve kapı bağlantısı testleri kırmızı
_OT = pytest.mark.skipif(OT is None, reason="kayranacc.mikro_odeme_oto yok")
KOK = Path(__file__).resolve().parent.parent
D = dt.date


def _h(**k):
    r = dict(cha_guid="g", cha_tip=1, cha_cari_cins=0, cha_kod="336.092", cha_d_cins=0, cha_d_kur=1,
             cha_karsidcinsi=0, cha_karsid_kur=1, cha_meblag=0, cha_evrak_tip=0, cha_evrakno_seri="HAE",
             cha_evrakno_sira=1, cha_belge_no=None, cha_tarihi="2026-09-24T00:00:00", cha_vade=0, cha_aciklama="")
    r.update(k)
    return r


KART = [{"cari_kod": "336.092", "cari_unvan1": "HAPPY LİFE İLAÇ VE SAĞLIK ÜRÜNLERİ SANAYİ", "cari_doviz_cinsi": 0},
        {"cari_kod": "336.006", "cari_unvan1": "AYŞE AKBELEN", "cari_doviz_cinsi": 0},
        {"cari_kod": "320.02.025", "cari_unvan1": "UPS HIZLI KARGO TAŞIMACILIĞI ANONİM ŞİRKETİ",
         "cari_doviz_cinsi": 0}]

# Canlı ODEME_PLANLARI (mikro_kesif, 22.10.2026): odp_ortgun hepsinde 0
PLANLAR = [{"odp_no": 6, "odp_adi": "30 GÜN VADE", "odp_ortgun": 0},
           {"odp_no": 3, "odp_adi": "7 GÜN AÇIK HESAP", "odp_ortgun": 0},
           {"odp_no": 1, "odp_adi": "60 gün açık hesap", "odp_ortgun": 0},
           {"odp_no": 4, "odp_adi": "PEŞİN", "odp_ortgun": 0},
           {"odp_no": 9, "odp_adi": "21 GÜN VADE ( FİLLO KARGO )", "odp_ortgun": 0}]


# ── Ödeme planı günü adından ──────────────────────────────────────
def test_plan_gunu_adindan_okunur():
    assert O.plan_gunleri(PLANLAR) == {6: 30, 3: 7, 1: 60, 4: 0, 9: 21}
    assert O.plan_gunleri([{"odp_no": 8, "odp_ortgun": 15, "odp_adi": "X"}]) == {8: 15}     # gün doluysa o


def test_planli_fatura_vadesi_plan_gunu_kadar_sonra():
    """Canlı: Happy Life 24.09.2026 faturaları (plan 6, "30 GÜN VADE") elle listede 24.10 vadeli."""
    v, kaynak, kesin = O.vade_bul(_h(cha_vade=6), O.plan_gunleri(PLANLAR))
    assert v == D(2026, 10, 24) and kesin and "30" in kaynak


def test_vadesiz_faturaya_firma_gunu():
    assert O.vade_bul(_h(cha_vade=0), {}, 15)[0] == D(2026, 10, 9)
    assert O.vade_bul(_h(cha_vade=20261101), {}, 15)[0] == D(2026, 11, 1)        # Mikro'nun vadesi önce gelir
    assert O.vade_bul(_h(cha_vade=0), {})[0] == D(2026, 9, 24)                  # gün yoksa peşin


# ── Sayfalı okuma ─────────────────────────────────────────────────
class _Q:
    def __init__(self, satirlar):
        self.s, self.r = list(satirlar), None

    def select(self, *_a):
        return self

    def eq(self, k, v):
        self.s = [x for x in self.s if x.get(k) == v]
        return self

    def like(self, k, desen):
        self.s = [x for x in self.s if str(x.get(k) or "").startswith(desen.rstrip("%"))]
        return self

    def order(self, k, **_):
        self.s.sort(key=lambda x: str(x.get(k)))
        return self

    def range(self, a, b):
        self.r = (a, b)
        return self

    def execute(self):
        data = self.s[self.r[0]:self.r[1] + 1] if self.r else self.s[:1000]       # Supabase: en çok 1000 satır
        return type("R", (), {"data": data})()


class _Cli:
    def __init__(self, tablolar):
        self.t = tablolar

    def table(self, ad):
        return _Q(self.t.get(ad, []))


def test_hareketler_sayfali_okunur(monkeypatch):
    """1.000'den fazla hareket: ödemeler sonraki sayfadaysa eskiden okunmuyor, fatura açık görünüyordu."""
    fatura = [_h(cha_guid=f"a{i:04d}", cha_meblag=100, cha_evrakno_sira=i) for i in range(600)]
    odeme = [_h(cha_guid=f"b{i:04d}", cha_tip=0, cha_meblag=100, cha_evrak_tip=35) for i in range(600)]
    cli = _Cli({"mikro_cari_hareket": fatura + odeme, "mikro_cari_kart": KART, "cekler": []})
    monkeypatch.setattr(O, "_cli", lambda: cli)
    monkeypatch.setattr(O, "_kesif", lambda a: [])
    v = O.veri_oku()
    assert len(v["hareket"]) == 1200
    assert O.acik_kalemler(v["hareket"], v["cari_kart"]) == []                    # hepsi ödendi


# ── Firma vadesi öğrenme ──────────────────────────────────────────
def _fat(kod, tarih, tutar, evrak="E", unvan=None):
    return {"cari_kod": kod, "unvan": unvan or next(k["cari_unvan1"] for k in KART if k["cari_kod"] == kod),
            "doviz": 0, "tarih": tarih, "evrak": evrak, "tutar": tutar}


def test_firma_vadesi_gecmis_listelerden():
    f = [_fat("320.02.025", D(2026, 10, 7), 100_000, "U1"), _fat("320.02.025", D(2026, 10, 7), 76_610.71, "U2"),
         _fat("320.02.025", D(2026, 9, 9), 345_995.19, "U3")]
    gecmis = [{"firma": "UPS HIZLI KARGO TAŞIMACILIĞI ANONİM ŞİRKETİ", "vade": "2026-10-22", "tutar_tl": 176_610.71},
              {"firma": "UPS HIZLI KARGO TAŞIMACILIĞI ANONİM ŞİRKETİ", "vade": "2026-10-22", "tutar_tl": 176_610.71},
              {"firma": "UPS", "vade": "2026-09-24", "tutar_tl": 345_995.19},
              {"firma": "KDV 1", "vade": "2026-10-28", "tutar_tl": 475_033}]
    assert O.vade_gunleri_ogren(f, gecmis) == {"320.02.025": 15}


# ── Her ay aynı fatura (kira) ─────────────────────────────────────
def test_kira_tahmini_sonraki_ay():
    f = [_fat("336.006", D(2026, m, 1), 256_272, f"K{m}") for m in (7, 8, 9, 10)]
    t = O.tekrar_tahminleri(f, D(2026, 10, 26), D(2026, 12, 6), {"336.006": 4})
    assert [(r["anahtar"], r["vade"], r["tl"]) for r in t] == [("t|336.006|2026-11", "2026-11-05", 256_272),
                                                                ("t|336.006|2026-12", "2026-12-05", 256_272)]
    assert "tahmini" in t[0]["aciklama"] and t[0]["kesin"] is False
    duzensiz = [_fat("336.006", D(2026, 8, 1), 1000, "a"), _fat("336.006", D(2026, 9, 14), 1000, "b"),
                _fat("336.006", D(2026, 10, 1), 1000, "c")]
    assert O.tekrar_tahminleri(duzensiz, D(2026, 10, 26), D(2026, 12, 6)) == []


# ── Vergi, SGK, maaş ──────────────────────────────────────────────
def _m(kod, y, a, borc=0.0, alacak=0.0):
    return {"yil": y, "ay": a, "hesap_kod": kod, "borc": borc, "alacak": alacak}


# Canlı 361 / 360 / 335 (Ağustos–Ekim 2026)
MUH = [_m("361.01.001", 2026, 7, 0, 588_594.74), _m("361.01.002", 2026, 7, 0, 48_505.74),
       _m("361.01.001", 2026, 8, 588_594.74, 600_485.36), _m("361.01.002", 2026, 8, 48_505.74, 50_390.39),
       _m("361.01.001", 2026, 9, 600_485.36, 545_632.91), _m("361.01.002", 2026, 9, 50_390.44, 45_787.37),
       _m("360.01.001", 2026, 9, 375_679.99, 313_170.66), _m("360.01.002", 2026, 9, 64_068, 64_068),
       _m("360.01.002", 2026, 10, 0, 64_068), _m("360.02.001", 2026, 9, 11_309.62, 9_385.92),
       _m("360.01.006", 2026, 9, 0, 55_569.27), _m("360.01.003", 2026, 9, 1_500, 1_500),
       _m("360.01.001", 2026, 8, 0, 375_679.99), _m("360.01.002", 2026, 8, 0, 64_068),
       _m("360.01.003", 2026, 8, 0, 1_500), _m("360.02.001", 2026, 8, 0, 11_309.62),
       _m("335.001", 2026, 8, 1_357_169.52, 1_323_751.11), _m("335.001", 2026, 9, 1_323_751.11, 1_145_535),
       _m("335.001", 2026, 10, 1_400_963.43, 182_678.43), _m("335.001", 2026, 7, 0, 1_357_169.52)]


def test_sgk_ve_muhtasar_mikro_bakiyesinden():
    r = {x["anahtar"]: x for x in O.donem_borclari(MUH, D(2026, 10, 26), D(2026, 12, 6))}
    assert set(r) == {"d|sgk|2026-09", "d|muhtasar|2026-09"}                    # Ekim sürüyor: alınmaz
    assert r["d|sgk|2026-09"]["tl"] == pytest.approx(591_420.28) and r["d|sgk|2026-09"]["vade"] == "2026-10-31"
    assert r["d|muhtasar|2026-09"]["tl"] == pytest.approx(443_693.85)
    assert r["d|muhtasar|2026-09"]["vade"] == "2026-10-26" and r["d|muhtasar|2026-09"]["firma"] == "EYLÜL AYI MUHTASAR"


def test_maas_tahakkuk_yoksa_gecen_ay_tahmini():
    r = O.maas_satirlari(MUH, D(2026, 10, 26), D(2026, 12, 6))
    assert [(x["anahtar"], x["tl"], x["vade"], x["kesin"]) for x in r] == \
        [("d|maas|2026-10", 1_145_535, "2026-11-05", False)]                    # Eylül ödendi: satır yok
    tahakkuk = MUH + [_m("335.001", 2026, 10, 0, 1_000_000)]
    r = O.maas_satirlari(tahakkuk, D(2026, 10, 30), D(2026, 12, 6))
    assert r[0]["kesin"] and r[0]["tl"] == pytest.approx(1_000_000 - 72_750, abs=1)


# ── Liste ve taşınan satırlar ─────────────────────────────────────
def _veri():
    har = [_h(cha_guid="h1", cha_vade=6, cha_meblag=147_216, cha_evrakno_sira=739),
           _h(cha_guid="h2", cha_kod="336.006", cha_meblag=256_272, cha_tarihi=f"2026-0{8}-01", cha_evrakno_sira=8),
           _h(cha_guid="h3", cha_kod="336.006", cha_tip=0, cha_meblag=256_272, cha_tarihi="2026-08-05",
              cha_evrak_tip=35)]
    return {"hareket": har, "cari_kart": KART, "cekler": [{"cek_no": "1138988", "banka": "YKB", "vade": "2026-11-13",
                                                           "kalan": 8450, "para_birimi": "USD", "durum": "Bekliyor"}],
            "planlar": O.plan_gunleri(PLANLAR), "taksitler": {}, "muhasebe": MUH}


@_OT
def test_liste_satirlari_tum_kaynaklar():
    s, _u = OT.liste_satirlari(_veri(), D(2026, 10, 26), D(2026, 10, 26), {})
    k = {r["anahtar"] for r in s}
    assert {"c|336.092|2026-10-24", "k|1138988|YKB", "d|sgk|2026-09", "d|muhtasar|2026-09", "d|maas|2026-10"} <= k
    assert len(k) == len(s) and all(r["manuel"] == 0 for r in s)


@_OT
def test_onceki_haftadan_yalniz_karsiligi_olmayan_elle_satirlar():
    yeni, _u = OT.liste_satirlari(_veri(), D(2026, 10, 26), D(2026, 10, 26), {})
    yeni.append({"firma": "S.S.İSTANBUL ANADOLU YAKASI KERESTE", "vade": "2026-11-04", "tl": 12_180, "usd": None,
                 "anahtar": "t|320.02.009|2026-11"})
    onceki = [{"id": 1, "durum": "bekliyor", "firma": "EYLÜL AYI SGK", "vade": "2026-10-30", "tutar_tl": 591_419},
              {"id": 2, "durum": "bekliyor", "firma": "KDV 1", "vade": "2026-10-28", "tutar_tl": 475_033,
               "kategori": "vergi"},
              {"id": 3, "durum": "odendi", "firma": "MULTİNET", "vade": "2026-10-14", "tutar_tl": 20_299.07},
              {"id": 4, "durum": "bekliyor", "firma": "KEYAP KASIM AYI AİDATI", "vade": "2026-11-05",
               "tutar_tl": 12_180},
              {"id": 5, "durum": "bekliyor", "firma": "HAPPY LİFE İLAÇ VE SAĞLIK ÜRÜNLERİ A.Ş.", "vade": "2026-10-24",
               "tutar_tl": 147_216},
              {"id": 6, "durum": "bekliyor", "firma": "ESKİ MİKRO SATIRI", "vade": "2026-10-20", "tutar_tl": 5}]
    t = OT.tasinacaklar(onceki, {6}, yeni)
    assert [(r["firma"], r["manuel"]) for r in t] == [("KDV 1", 1)]


# ── Hafta içi güncelleme planı ────────────────────────────────────
def _y(anahtar, tl, aciklama="x"):
    return {"anahtar": anahtar, "tl": tl, "usd": None, "aciklama": aciklama, "firma": "F", "vade": "2026-10-30",
            "kategori": "cari"}


def _db(i, tl, aciklama="x", durum="bekliyor"):
    return {"id": i, "tutar_tl": tl, "tutar_usd": None, "aciklama": aciklama, "durum": durum}


@_OT
def test_guncelleme_plani():
    e = {"c|A|2026-10-30": {"id": 1, "tl": 100.0, "usd": None, "aciklama": "x"},     # Mikro'da kapandı
         "c|B|2026-10-30": {"id": 2, "tl": 200.0, "usd": None, "aciklama": "x"},     # yeni fatura: tutar arttı
         "c|C|2026-10-30": {"id": 3, "tl": 300.0, "usd": None, "aciklama": "x"},     # kullanıcı tutarı düzeltti
         "c|D|2026-10-30": {"id": 4, "tl": 400.0, "usd": None, "aciklama": "x"},     # kullanıcı sildi
         "c|E|2026-10-30": {"id": 5, "tl": 500.0, "usd": None, "aciklama": "x"},     # elle ödendi işaretlendi
         "t|F|2026-11": {"id": 6, "tl": 600.0, "usd": None, "aciklama": "x"},        # gerçek faturası geldi
         "d|sgk|2026-09": {"id": 7, "tl": 700.0, "usd": None, "aciklama": "x"}}     # değişmedi
    mevcut = {1: _db(1, 100), 2: _db(2, 200), 3: _db(3, 150), 5: _db(5, 500, durum="odendi"), 6: _db(6, 600),
              7: _db(7, 700)}
    yeni = [_y("c|B|2026-10-30", 250), _y("c|C|2026-10-30", 300), _y("c|D|2026-10-30", 400),
            _y("d|sgk|2026-09", 700), _y("c|G|2026-11-02", 50)]
    p = OT.guncelleme_plani(e, mevcut, yeni)
    assert [r["anahtar"] for r in p["ekle"]] == ["c|G|2026-11-02"]
    assert p["kapandi"] == [("c|A|2026-10-30", 1)]
    assert p["sil"] == [("t|F|2026-11", 6)]
    assert [(k, i, a["tutar_tl"]) for k, i, a, _iz in p["guncelle"]] == [("c|B|2026-10-30", 2, 250.0)]


# ── Pazartesi açılış / hafta içi yenileme (sahte veritabanı) ────────
@pytest.fixture
def ortam(monkeypatch):
    import kayranacc.database as db
    ayar, haftalar, odemeler, cagri = {}, [{"id": 61, "hafta_adi": "19.10.2026 GÜNCEL ÖDEME LİSTESİ", "aktif": 1}], {}, []
    odemeler[61] = [{"id": 1, "hafta_id": 61, "durum": "bekliyor", "firma": "KDV 1", "vade": "2026-10-28",
                     "tutar_tl": 475_033, "tutar_usd": None, "kategori": "vergi", "aciklama": ""}]
    monkeypatch.setattr(db, "get_ayar", lambda k, v=None: ayar.get(k, v))
    monkeypatch.setattr(db, "set_ayar", lambda k, v: ayar.__setitem__(k, v) or True)
    monkeypatch.setattr(db, "get_client", lambda: _Cli({"haftalar": haftalar}))
    monkeypatch.setattr(db, "get_aktif_hafta", lambda: next((h for h in haftalar if h["aktif"]), None))
    sayac = iter(range(100, 10_000))

    def hafta_olustur(ad, satirlar, idler=None):
        hid = max(h["id"] for h in haftalar) + 1
        for h in haftalar:
            h["aktif"] = 0
        haftalar.append({"id": hid, "hafta_adi": ad, "aktif": 1})
        odemeler[hid] = [dict(s, id=next(sayac), hafta_id=hid, durum="bekliyor", tutar_tl=s.get("tl"),
                              tutar_usd=s.get("usd")) for s in satirlar]
        if idler is not None:
            idler.extend(o["id"] for o in odemeler[hid])
        return hid

    def bul(oid):
        return next(o for h in odemeler.values() for o in h if o["id"] == oid)

    monkeypatch.setattr(db, "hafta_olustur", hafta_olustur)
    monkeypatch.setattr(db, "odeme_mikro_kapandi", lambda oid, *a: cagri.append(("kapandi", oid)) or
                        bul(oid).update(durum="odendi") or True)
    monkeypatch.setattr(db, "odeme_mikro_guncelle", lambda oid, al: cagri.append(("guncelle", oid)) or True)
    monkeypatch.setattr(db, "odeme_sil", lambda oid: cagri.append(("sil", oid)))
    monkeypatch.setattr(db, "odeme_ekle_bulk", lambda hid, s: [next(sayac) for _ in s])
    monkeypatch.setattr(db, "odeme_durum_guncelle", lambda *a, **k: pytest.fail("banka yoluna girilmemeli"))
    monkeypatch.setattr(OT, "son_aktarim", lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    monkeypatch.setattr(OT, "_hafta_odemeleri", lambda hid: list(odemeler.get(int(hid), [])))
    veri = {"v": _veri()}
    monkeypatch.setattr(OT, "veri_oku", lambda: veri["v"])
    monkeypatch.setattr(OT, "firma_gunleri", lambda d, v: {"336.006": 4})
    import shared.yukleme_takvimi as yt
    import shared.yukleme_gecmisi as yg
    monkeypatch.setattr(yt, "kaydet", lambda *a, **k: None)
    monkeypatch.setattr(yg, "kaydet", lambda *a, **k: None)
    return {"ayar": ayar, "haftalar": haftalar, "odemeler": odemeler, "cagri": cagri, "veri": veri}


@_OT
def test_elle_yuklenmis_haftaya_dokunulmaz(ortam):
    assert "elle yüklenmiş" in OT.hafta_ac(D(2026, 10, 22))
    assert len(ortam["haftalar"]) == 1
    assert OT.hafta_ac(D(2026, 10, 23)) is None                                   # aynı hafta bir kez bakılır


@_OT
def test_pazartesi_acilir_ve_hafta_icinde_guncellenir(ortam):
    s = OT.hafta_ac(D(2026, 10, 26))
    assert s and "açıldı" in s
    hid = max(h["id"] for h in ortam["haftalar"])
    assert ortam["haftalar"][-1]["hafta_adi"] == "26.10.2026 GÜNCEL ÖDEME LİSTESİ" and ortam["haftalar"][-1]["aktif"]
    satir = ortam["odemeler"][hid]
    assert any(o["firma"] == "KDV 1" and o["manuel"] == 1 for o in satir)            # elle satır taşındı
    esleme = ortam["ayar"][OT.DURUM_ANAHTAR]["haftalar"][str(hid)]["esleme"]
    assert "c|336.092|2026-10-24" in esleme and len(esleme) == len(satir) - 1
    assert OT.hafta_ac(D(2026, 10, 27)) is None                                   # ikinci kez açılmaz
    # Happy Life faturası Mikro'da ödendi → satır "ödendi" (yalnız durum, banka yolu yok)
    v = ortam["veri"]["v"]
    v["hareket"] = v["hareket"] + [_h(cha_guid="h9", cha_tip=0, cha_meblag=147_216, cha_tarihi="2026-10-27",
                                      cha_evrak_tip=35)]
    sonuc = OT.hafta_yenile(D(2026, 10, 27))
    assert sonuc and "kapanan 1" in sonuc
    assert ortam["cagri"] == [("kapandi", esleme["c|336.092|2026-10-24"]["id"])]
    assert OT.hafta_yenile(D(2026, 10, 27)) is None                               # değişiklik yok


@_OT
def test_kapaliyken_hicbir_sey_yapmaz(ortam):
    ortam["ayar"][OT.DURUM_ANAHTAR] = {"acik": False}
    assert not OT.acik_mi() and OT.otomatik() is None and len(ortam["haftalar"]) == 1
    ortam["ayar"][OT.DURUM_ANAHTAR] = {}
    assert OT.acik_mi()                                                            # varsayılan açık


def test_mikro_kapandi_bankaya_dokunmaz(monkeypatch):
    import kayranacc.database as db
    yazilan = []

    class _T:
        def __init__(self, ad):
            self.ad = ad

        def select(self, *_):
            return self

        def update(self, v):
            yazilan.append((self.ad, v))
            return self

        def eq(self, *_):
            return self

        def execute(self):
            return type("R", (), {"data": [{"durum": "bekliyor", "aciklama": "2 FATURA"}]})()

    monkeypatch.setattr(db, "get_client", lambda: type("C", (), {"table": lambda s, ad: _T(ad)})())
    assert db.odeme_mikro_kapandi(5, "2026-10-27")
    assert yazilan == [("odemeler", {"durum": "odendi", "odendi_tarih": "2026-10-27",
                                     "aciklama": "2 FATURA · Mikro'da kapandı"})]


# ── Bağlantılar ───────────────────────────────────────────────────
def test_esitleme_turunda_cekten_sonra():
    spec = importlib.util.spec_from_file_location("otonom_mikro_esitle_odeme", KOK / "otonom" / "mikro_esitle.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    adlar = [m for _a, m, _f in mod.ISLER]
    assert adlar.index("kayranacc.mikro_odeme_oto") > adlar.index("kayranacc.mikro_muhasebe")


def test_excel_yuklemesi_mikro_acikken_kaydetmez():
    s = (KOK / "kayranacc" / "main.py").read_text(encoding="utf-8")
    govde = s.split("def kapi_odeme_listesi", 1)[1].split("\ndef ", 1)[0]
    assert govde.index('_mikrodan_geliyor("Haftalık ödeme listesi", "odeme")') < govde.index("odeme_ekle_bulk(")
