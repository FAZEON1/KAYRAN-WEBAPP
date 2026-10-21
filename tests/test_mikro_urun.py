# -*- coding: utf-8 -*-
"""Mikro → ürün kartları, barkod, müşteri fiyat listeleri (kayranpm/mikro_urun.py, Ekim 2026).

Kodlar ve adlar canlı veriden (21.10.2026): Mikro'da 21 kod 'Fazeon ' önekli ('Fazeon X24F165S', 'FAZEON A2120TRA'),
uygulamada aynı ürünler öneksiz; kategori uygulamada Türkçe küçük harf ('monitör'), marka 'FAZEON' / 'Mio'."""
import importlib.util
import re
from pathlib import Path

import pytest

from kayranpm import mikro_urun as M

KOK = Path(__file__).resolve().parent.parent

URUNLER = [
    {"sku": "X24F165S", "urun_adi": "FAZEON 24 MONİTÖR", "kategori": "monitör", "marka": "FAZEON", "barkod": "869001"},
    {"sku": "A2120TRA", "urun_adi": "FAZEON A2 KASA", "kategori": "kasa", "marka": "FAZEON", "barkod": ""},
    {"sku": "RMAFM001", "urun_adi": "FAZEON Monitör Anakart", "kategori": "", "marka": "FAZEON", "barkod": ""},
    {"sku": "N50602-08D7-198072N", "urun_adi": "", "kategori": "", "marka": "", "barkod": "888630770441-2"},
]


def _kart(kod, isim="", grup="", marka="", pasif=0, **ek):
    return dict(sto_kod=kod, sto_isim=isim, anagrup_isim=grup, sto_marka_kodu=marka, sto_pasif=pasif, **ek)


KARTLAR = [
    _kart("Fazeon X24F165S", "Fazeon X24F165S 24 inç", "MONİTÖR", "Fazeon"),
    _kart("FAZEON A2120TRA", "A2 KASA", "KASA", "FAZEON"),
    _kart("RMAFM001", "MONİTÖR ANAKART", "YEDEK PARÇA", "BAŞKA"),
    _kart("N50602-08D7-198072N", "RTX 5060", "EKRAN KARTI", "INNO3D"),
    _kart("Fazeon X27F400", "FAZEON 27 YENİ", "MONİTÖR", "fazeon"),
    _kart("MIVUE 999", "MIO MIVUE 999", "ARAÇ KAMERASI", "MIO"),
    _kart("ESKI01", "ESKİ ÜRÜN", "KASA", "FAZEON", pasif=1),
]
BARKODLAR = [
    {"bar_stokkodu": "Fazeon X27F400", "bar_kodu": "8690000000002", "bar_master": 0},
    {"bar_stokkodu": "Fazeon X27F400", "bar_kodu": "8690000000009", "bar_master": 1},
    {"bar_stokkodu": "FAZEON A2120TRA", "bar_kodu": "8691111111111", "bar_master": 0},
    {"bar_stokkodu": "Fazeon X24F165S", "bar_kodu": "8692222222222", "bar_master": 1},
]
CARILER = ["VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI",
           "D-MARKET ELEKTRONİK HİZMETLER VE TİCARET ANONİM ŞİRKETİ",
           "EERA ELEKTRONİK TİCARET VE BİLİŞİM HİZMETLERİ ANONİM ŞİRKETİ",
           "GÜNEŞ BİLGİSAYAR İLETİŞİM SİSTEMLERİ ANONİM ŞİRKETİ", "GÜNEŞ ELEKTRİK LİMİTED ŞİRKETİ"]
VATAN = CARILER[0]


# ── Kartlar ─────────────────────────────────────────────────────────
def test_fazeon_onekli_kod_mevcut_karta_baglanir_kopya_kart_acilmaz():
    """Kullanıcı: 'Fazeon olmasın, kodun önünde sadece kod olsun.' Birebir karşılaştırmada 'Fazeon X24F165S' ve
    'FAZEON A2120TRA' yeni kart sanılır, aynı ürün iki kart olurdu."""
    p = M.kart_plani(KARTLAR, BARKODLAR, URUNLER)
    yeni = {y["sku"] for y in p["yeni"]}
    assert yeni == {"X27F400", "MIVUE 999"}
    assert not any(s.upper().startswith("FAZEON") for s in yeni)
    assert M.fazeon_kodlari(KARTLAR, URUNLER) == [("FAZEON A2120TRA", "A2120TRA", True),
                                                   ("Fazeon X24F165S", "X24F165S", True),
                                                   ("Fazeon X27F400", "X27F400", False)]


def test_yeni_kart_uygulamanin_yazimiyla_acilir():
    """Kategori uygulamadaki yazımla ('MONİTÖR' → 'monitör'; P&L ve masraf dağıtımı birebir yazıma dayanır),
    marka da ('fazeon' → 'FAZEON'); uygulamada olmayan marka kural yazımıyla ('MIO' → 'Mio'). Ana barkod önce."""
    p = M.kart_plani(KARTLAR, BARKODLAR, URUNLER)
    y = {x["sku"]: x for x in p["yeni"]}
    assert y["X27F400"] == {"sku": "X27F400", "mikro_kod": "Fazeon X27F400", "urun_adi": "FAZEON 27 YENİ",
                            "kategori": "monitör", "marka": "FAZEON", "barkod": "8690000000009"}
    assert y["MIVUE 999"]["kategori"] == "araç kamerası" and y["MIVUE 999"]["marka"] == "Mio"


def test_pasif_mikro_karti_yeni_acilmaz():
    p = M.kart_plani(KARTLAR, BARKODLAR, URUNLER)
    assert p["pasif_atlanan"] == ["ESKI01"]
    assert "ESKI01" not in {y["sku"] for y in p["yeni"]}


def test_dolu_alan_degismez_yalniz_bos_alan_dolar():
    """X24F165S'nin adı, kategorisi, markası, barkodu dolu: Mikro farklı yazsa da hiçbiri değişmez. RMAFM001'in
    markası FAZEON (Mikro 'BAŞKA' diyor) korunur, boş kategorisi dolar. Boş barkod Mikro'dan dolar."""
    p = M.kart_plani(KARTLAR, BARKODLAR, URUNLER)
    d = dict(p["doldur"])
    assert "X24F165S" not in d
    assert d["A2120TRA"] == {"barkod": "8691111111111"}
    assert d["RMAFM001"] == {"kategori": "yedek parça"}
    assert d["N50602-08D7-198072N"] == {"urun_adi": "RTX 5060", "kategori": "ekran kartı", "marka": "INNO3D"}


def test_ayni_anahtara_iki_mikro_kodu_dusunce_etkin_ve_oneksiz_kazanir():
    k = M.mikro_kartlari([_kart("Fazeon X1", "ÖNEKLİ"), _kart("X1", "ÖNEKSİZ"),
                          _kart("Y1", "ETKİN"), _kart("Fazeon Y1", "PASİF", pasif=1)])
    assert k["X1"]["sto_isim"] == "ÖNEKSİZ" and k["Y1"]["sto_isim"] == "ETKİN"


def test_barkod_ana_barkod_once_yoksa_en_kucuk():
    assert M.barkod_haritasi(BARKODLAR + [{"bar_stokkodu": "Z", "bar_kodu": "2"}, {"bar_stokkodu": "Z", "bar_kodu": "1"},
                                          {"bar_stokkodu": "", "bar_kodu": "9"}]) == {
        "X27F400": "8690000000009", "A2120TRA": "8691111111111", "X24F165S": "8692222222222", "Z": "1"}


def test_kategori_kaynagi_ana_grup_sonra_alt_grup_sonra_kod():
    assert M.mikro_kategori({"anagrup_isim": "MONİTÖR", "altgrup_isim": "X", "sto_kategori_kodu": "K"}) == "MONİTÖR"
    assert M.mikro_kategori({"altgrup_isim": "FAN", "sto_kategori_kodu": "K"}) == "FAN"
    assert M.mikro_kategori({"sto_kategori_kodu": " SSD "}) == "SSD"
    assert M.kategori_yazimi("", ["kasa"]) == "" and M.marka_yazimi("", ["FAZEON"]) == ""


# ── Fiyat listeleri ────────────────────────────────────────────────
def test_liste_adi_tek_cariye_baglanir_belirsizse_baglanmaz():
    assert M.liste_musterisi("VATAN FİYAT LİSTESİ", CARILER) == VATAN
    assert M.liste_musterisi("Vatan", CARILER) == VATAN
    assert M.liste_musterisi("D-MARKET", CARILER) == CARILER[1]
    assert M.liste_musterisi("GÜNEŞ", CARILER) is None            # iki cari uyuyor: yanlış müşteriye yazılmasın
    assert M.liste_musterisi("PERAKENDE SATIŞ FİYATI", CARILER) is None
    assert M.liste_musterisi("", CARILER) is None


def _fiyat(stok, liste, fiyat, doviz=1, depo=0, plan=0, birim=1, t="2026-10-01"):
    return {"sfiyat_stokkod": stok, "sfiyat_listesirano": liste, "sfiyat_fiyati": fiyat, "sfiyat_doviz": doviz,
            "sfiyat_deposirano": depo, "sfiyat_odemeplan": plan, "sfiyat_birim_pntr": birim, "sfiyat_lastup_date": t}


LISTELER = [{"sfl_sirano": 1, "sfl_aciklama": "VATAN", "sfl_kdvdahil": 0},
            {"sfl_sirano": 2, "sfl_aciklama": "PERAKENDE", "sfl_kdvdahil": 0},
            {"sfl_sirano": 3, "sfl_aciklama": "D-MARKET", "sfl_kdvdahil": 1}]


def test_fiyat_plani_yalniz_dolar_kdv_haric_eslesen_liste():
    """Uygulamadaki fiyat listesi dolar ve KDV hariç: TL / KDV dahil fiyat dolar diye yazılırsa öneri 30-40 kat
    şişerdi. Eşleşmeyen liste, depoya / ödeme planına özel fiyat ve kartı olmayan ürün yazılmaz."""
    es = M.liste_eslesmesi(LISTELER, CARILER)
    assert [(e["sirano"], e["musteri"], e["kdv_dahil"]) for e in es] == [(1, VATAN, False), (2, None, False),
                                                                         (3, CARILER[1], True)]
    urunler = [dict(URUNLER[0], satis_fiyat_listesi={"Vatan Bilgisayar Sanayi ve Ticaret Anonim Şirketi": 120.0,
                                                     "Trendyol": 99.0}),
               dict(URUNLER[1], satis_fiyat_listesi={})]
    fiyatlar = [_fiyat("Fazeon X24F165S", 1, 125.5),
                _fiyat("Fazeon X24F165S", 1, 110, t="2026-01-01"),         # eski satır: son değiştirilen kazanır
                _fiyat("FAZEON A2120TRA", 1, 4250, doviz=0),               # TL
                _fiyat("FAZEON A2120TRA", 2, 50),                          # eşleşmeyen liste
                _fiyat("FAZEON A2120TRA", 3, 60),                          # KDV dahil liste
                _fiyat("FAZEON A2120TRA", 1, 55, depo=4),                  # depoya özel
                _fiyat("YOK01", 1, 10),                                    # kartı yok
                _fiyat("Fazeon X27F400", 1, 140),                          # bu turda açılacak kart
                _fiyat("FAZEON A2120TRA", 9, 1)]                           # liste tanımı yok
    p = M.fiyat_plani(fiyatlar, es, urunler, yeni_skular=["X27F400"])
    assert p["degisen"] == [("X24F165S", "Vatan Bilgisayar Sanayi ve Ticaret Anonim Şirketi", 120.0, 125.5),
                            ("X27F400", VATAN, None, 140.0)]
    assert p["atlanan"] == {"KDV dahil liste": 1, "depoya / ödeme planına / birime özel": 1, "dolar dışı fiyat": 1,
                            "liste müşteriyle eşleşmedi": 1, "liste tanımı yok": 1, "uygulamada kartı yok": 1}


def test_ayni_fiyat_degisen_sayilmaz():
    es = M.liste_eslesmesi(LISTELER[:1], CARILER)
    urunler = [dict(URUNLER[0], satis_fiyat_listesi={VATAN: 125.5})]
    assert M.fiyat_plani([_fiyat("Fazeon X24F165S", 1, 125.5)], es, urunler)["degisen"] == []


def test_birlesik_liste_diger_musterilere_dokunmaz():
    assert M.birlesik_liste({"Trendyol": 99.0, VATAN: 120.0}, [(VATAN, 125.5)]) == {"Trendyol": 99.0, VATAN: 125.5}
    assert M.birlesik_liste(None, [(VATAN, 1)]) == {VATAN: 1.0}


# ── Yazım ──────────────────────────────────────────────────────────
class _Sorgu:
    def __init__(self, db, tablo):
        self.db, self.tablo, self.islem, self.veri, self.kosul = db, tablo, "select", None, None

    def select(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def in_(self, alan, degerler):
        self.kosul = (alan, set(degerler))
        return self

    def eq(self, alan, deger):
        self.kosul = (alan, {deger})
        return self

    def insert(self, veri):
        self.islem, self.veri = "insert", veri
        return self

    def update(self, veri):
        self.islem, self.veri = "update", veri
        return self

    def upsert(self, veri, **_k):
        self.islem, self.veri = "upsert", veri
        return self

    def execute(self):
        rows = self.db.setdefault(self.tablo, [])
        self.db.setdefault("_yazim", []).append((self.tablo, self.islem, self.veri, self.kosul))
        if self.islem == "insert":
            rows.append(dict(self.veri))
        elif self.islem == "update":
            alan, d = self.kosul
            for r in rows:
                if r.get(alan) in d:
                    r.update(self.veri)
        out = rows
        if self.islem == "select" and self.kosul:
            alan, d = self.kosul
            out = [r for r in rows if r.get(alan) in d]
        return type("C", (), {"data": [dict(r) for r in out]})()


class _Cli:
    def __init__(self, db):
        self.db = db

    def table(self, ad):
        return _Sorgu(self.db, ad)


@pytest.fixture()
def db(monkeypatch):
    d = {"urunler": [dict(u, satis_fiyat_listesi={}) for u in URUNLER]}
    monkeypatch.setattr(M, "_cli", lambda: _Cli(d))
    import kayranpm.database as pmdb
    monkeypatch.setattr(pmdb, "get_today", lambda: "2026-10-21")
    return d


def _plan(urunler=None):
    return M.hesapla({"kart": KARTLAR, "barkod": BARKODLAR, "liste": LISTELER, "cari": CARILER,
                      "fiyat": [_fiyat("Fazeon X24F165S", 1, 125.5)], "urunler": urunler or URUNLER})


def test_uygula_kart_acar_bos_alani_doldurur_fiyati_yazar(db):
    sonuc = M.uygula(_plan())
    assert sonuc == 6                          # 2 yeni kart + 3 kartta boş alan + X24F165S'de yalnız fiyat
    u = {r["sku"]: r for r in db["urunler"]}
    assert u["X27F400"]["kategori"] == "monitör" and u["X27F400"]["bizim_stok"] == 0
    assert u["X24F165S"]["satis_fiyat_listesi"] == {VATAN: 125.5}
    assert u["X24F165S"]["kategori"] == "monitör" and u["X24F165S"]["urun_adi"] == "FAZEON 24 MONİTÖR"
    assert u["RMAFM001"]["marka"] == "FAZEON" and u["RMAFM001"]["kategori"] == "yedek parça"
    yas = [v for t, i, v, _ in db["_yazim"] if t == "stok_yas"]
    assert [x["sku"] for x in yas[0]] == ["MIVUE 999", "X27F400"]


def test_uygula_arada_acilan_karta_ve_arada_dolan_alana_yazmaz(db):
    """Plan ekranda gösterildikten sonra biri kartı elle açtı / kategoriyi girdi: onay bunların üzerine yazmaz."""
    plan = _plan()
    db["urunler"].append({"sku": "X27F400", "urun_adi": "ELLE", "kategori": "kasa", "marka": "", "barkod": "",
                          "bizim_stok": 7, "satis_fiyat_listesi": {}})
    next(r for r in db["urunler"] if r["sku"] == "RMAFM001")["kategori"] = "diğer"
    M.uygula(plan)
    u = {r["sku"]: r for r in db["urunler"]}
    assert [r["sku"] for r in db["urunler"]].count("X27F400") == 1
    assert u["X27F400"]["urun_adi"] == "ELLE" and u["X27F400"]["bizim_stok"] == 7
    assert u["RMAFM001"]["kategori"] == "diğer"


def test_bos_mikro_verisi_yazmaz(db):
    assert M.uygula({"bos": True, "yeni": [{"sku": "X"}], "doldur": [], "fiyat": []}) == 0
    assert "_yazim" not in db


def test_otomatik_kapaliyken_hicbir_sey_yapmaz(monkeypatch):
    monkeypatch.setattr(M, "durum", lambda: {})
    monkeypatch.setattr(M, "plan_hazirla", lambda: pytest.fail("kapalıyken okunmamalı"))
    assert M.otomatik() is None


def test_otomatik_yeni_veri_yoksa_calismaz(monkeypatch):
    monkeypatch.setattr(M, "durum", lambda: {"acik": True, "son_calisma": "2026-10-21T10:00:00+03:00"})
    monkeypatch.setattr(M, "son_aktarim", lambda: "2026-10-21T10:00:00+03:00")
    monkeypatch.setattr(M, "plan_hazirla", lambda: pytest.fail("yeni veri yokken okunmamalı"))
    assert M.otomatik() is None


def test_son_aktarim_kart_tablosu_cekilmediyse_bos(monkeypatch):
    d = {"mikro_senk_durum": [{"tablo": "mikro_stok_barkod", "son_cekim": "2026-10-21T10:00"}]}
    monkeypatch.setattr(M, "_cli", lambda: _Cli(d))
    assert M.son_aktarim() == ""
    d["mikro_senk_durum"].append({"tablo": "mikro_stok_kart", "son_cekim": "2026-10-21T09:00"})
    d["mikro_senk_durum"].append({"tablo": "mikro_satis_fiyat", "son_cekim": "2026-10-21T11:00"})
    assert M.son_aktarim() == "2026-10-21T11:00"


# ── Stok kartı ─────────────────────────────────────────────────────
def test_kart_cipleri_garanti_gtip_olcu():
    k = {"sto_garanti_sure": 24, "sto_gtipno": "8528.52.91.00.00", "sto_birim1_agirlik": 5.25,
         "sto_birim1_en": 60, "sto_birim1_boy": 15, "sto_birim1_yukseklik": 45.5, "sto_pasif": 1}
    assert M.kart_cipleri_hazirla(k) == [("Garanti", "24"), ("GTİP", "8528.52.91.00.00"), ("Ağırlık", "5,25"),
                                         ("Ölçü", "60,0 × 15,0 × 45,5"), ("Mikro", "pasif")]
    assert M.kart_cipleri_hazirla({"sto_garanti_sure": 0}) == [] and M.kart_cipleri_hazirla(None) == []


def test_kart_cipleri_okunamazsa_bos(monkeypatch):
    monkeypatch.setattr(M, "_cli", lambda: 1 / 0)
    monkeypatch.setitem(M._KART_ONBELLEK, "t", 0.0)
    assert M.kart_cipleri("X24F165S") == []


def test_stok_karti_basliginda_mikro_cipleri():
    from kayranpm.stok_karti_yeni import _bas_html
    h = _bas_html("X24F165S", {"urun_adi": "A"}, 0, "FAZEON", "Monitör", "", ek=[("GTİP", "8528")])
    assert "GTİP <b>8528</b>" in h
    assert "GTİP" not in _bas_html("X24F165S", {"urun_adi": "A"}, 0, "FAZEON", "Monitör", "")


# ── Aktarıcı, şema, otomatik çalışma ───────────────────────────────
@pytest.fixture()
def mk(monkeypatch):
    import sys
    import types
    if importlib.util.find_spec("requests") is None:
        sahte = types.ModuleType("requests")
        sahte.Session = object
        sahte.RequestException = Exception
        sahte.Response = object
        monkeypatch.setitem(sys.modules, "requests", sahte)
    spec = importlib.util.spec_from_file_location("mikro_kayran_urun_test",
                                                  KOK / "araclar" / "mikro_aktarici" / "mikro_kayran.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


SORGU_TABLO = {"stok_kart": ("mikro_stok_kart", "sto_kod"), "stok_barkod": ("mikro_stok_barkod", "bar_guid"),
               "satis_fiyat": ("mikro_satis_fiyat", "sfiyat_guid"), "fiyat_liste": ("mikro_fiyat_liste", "sfl_sirano")}


def _secilen_kolonlar(sql):
    govde = " ".join(sql.split())
    govde = re.sub(r"\([^()]*\)", "", re.sub(r"\([^()]*\)", "", govde))     # alt sorgu / CAST içi
    secim = govde.split(" FROM ", 1)[0][len("SELECT "):]
    out = []
    for parca in secim.split(","):
        p = re.split(r"(?:^|\s)AS\s+", parca.strip())[-1]
        out.append(p.split(".")[-1].strip().lower())
    return out


def test_aktarici_urun_sorgulari_tam_ve_semayla_uyumlu(mk):
    """Dört küçük tablo her turda tam çekilir; seçilen her kolon 46_mikro_urun.sql'de var (yoksa upsert reddedilir,
    tablo hiç dolmaz); anahtar seçimde; tablolar gece yedeğinin dışında (kaynak Mikro)."""
    from shared.yedek_tablolari import HARIC
    sema = (KOK / "veritabani" / "46_mikro_urun.sql").read_text(encoding="utf-8")
    for ad, (tablo, anahtar) in SORGU_TABLO.items():
        t = mk.SORGULAR[ad]
        assert t["tablo"] == tablo and t["anahtar"] == anahtar and t["artimli"] is False
        kolonlar = _secilen_kolonlar(t["sql"])
        assert anahtar in kolonlar
        blok = sema.split(f"public.{tablo} (", 1)[1].split(");", 1)[0]
        for k in kolonlar:
            assert re.search(rf"\b{k}\b", blok), (ad, k)
        assert tablo in HARIC
    assert list(mk.SORGULAR)[-4:] == list(SORGU_TABLO)        # diğer sorgulardan sonra tek blok
    assert "iptal=0" in " ".join(mk.SORGULAR["stok_kart"]["sql"].split())
    assert "GERİ ALMA" in sema and "service_role" in sema


def test_otomatik_calismaya_eklendi():
    app = (KOK / "app.py").read_text(encoding="utf-8")
    assert "from kayranpm.mikro_urun import otomatik" in app.split("def _mikro_esitle_dene", 1)[1].split("\ndef ", 1)[0]
    spec = importlib.util.spec_from_file_location("otonom_mikro_esitle_urun", KOK / "otonom" / "mikro_esitle.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert ("kayranpm.mikro_urun", "otomatik") in {(m, f) for _a, m, f in mod.ISLER}
