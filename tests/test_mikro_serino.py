# -*- coding: utf-8 -*-
"""Seri numaraları Mikro'dan, teknik servise (Ekim 2026).

Kullanıcı isteği: seri no bilgisi dosya yükleme / elle giriş yerine Mikro'dan. Aktarıcı STOK_SERINO_TANIMLARI'nı
mikro_serino'ya kopyalar (47_mikro_serino.sql); teknik servis mal kabulü seri no'dan stok kodu, kime satıldığı,
satış belgesi, garanti bitişi ve "garantide / garanti dışı" bilgisini gösterir; toplu mal kabulde BOŞ Stok Kodu /
Firma doldurulur, dolu ve çelişen alan değiştirilmez (uyarı). Tablo yoksa ekran eski davranışına döner."""
import importlib
import importlib.util
import re
import sys
import types
from datetime import date
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
BUGUN = date(2026, 10, 21)


@pytest.fixture()
def MS():
    assert importlib.util.find_spec("teknikservis.mikro_serino") is not None, \
        "teknikservis/mikro_serino.py yok: seri no Mikro'dan okunmuyor"
    return importlib.import_module("teknikservis.mikro_serino")


def _k(**alan):
    t = {"chz_guid": "00000000-0000-0000-0000-000000000001", "chz_serino": "M2503M00018", "chz_stok_kodu": "X24F165S",
         "chz_iptal": 0, "chz_st_tarih": None, "chz_al_tarih": None, "chz_lastup_date": "2026-01-01T00:00:00"}
    t.update(alan)
    return t


# ── Saf fonksiyonlar ────────────────────────────────────────────────
def test_seri_anahtar_bosluk_ve_buyuk_harf(MS):
    assert MS.seri_anahtar(" m2503 m00018 ") == "M2503M00018"
    assert MS.seri_anahtar("50-005-250472143") == "50-005-250472143"
    for yok in ("NO SERIAL NUMBER", "no serial number", "N/A", "-", "", None, "YOK"):
        assert MS.seri_anahtar(yok) == "", yok        # seri no yerine yazılanlar Mikro'da aranmaz


def test_mikro_bos_tarihi_yok_sayilir(MS):
    assert MS.tarih("1899-12-30T00:00:00") is None and MS.tarih("1900-01-01") is None
    assert MS.tarih("2026-03-05T00:00:00") == date(2026, 3, 5)
    assert MS.tarih(None) is None and MS.tarih("bozuk") is None


def test_kayit_sec_iptal_stok_ve_son_satis(MS):
    eski = _k(chz_guid="a", chz_st_tarih="2025-01-10T00:00:00", chz_st_cari_kodu="120.01")
    yeni = _k(chz_guid="b", chz_st_tarih="2026-02-10T00:00:00", chz_st_cari_kodu="120.02")
    iptal = _k(chz_guid="c", chz_st_tarih="2026-09-10T00:00:00", chz_iptal=1)
    assert MS.kayit_sec([eski, yeni, iptal])["chz_guid"] == "b"        # iptal atılır, en yeni satış
    baska = _k(chz_guid="d", chz_stok_kodu="F11A750BBM", chz_st_tarih="2026-05-01T00:00:00")
    # girilen stok koduyla uyan tanım önce ('Fazeon X24F165S' → 'X24F165S')
    assert MS.kayit_sec([eski, baska], "Fazeon X24F165S")["chz_guid"] == "a"
    assert MS.kayit_sec([iptal]) is None and MS.kayit_sec([]) is None


def test_belge_no_uygulama_bicimi(MS):
    assert MS.belge_no("G5F26", 2525) == "G5F26-2525"
    assert MS.belge_no("G5F26", "2525.0") == "G5F26-2525"
    assert MS.belge_no("", 0) == "" and MS.belge_no(None, None) == ""


def test_garanti_musteri_garantisi_once(MS):
    k = _k(chz_musteri_garanti_bitis="2027-03-01T00:00:00", chz_grn_bit_tarihi="2026-01-01T00:00:00")
    assert MS.garanti(k, BUGUN) == (date(2027, 3, 1), MS.GARANTIDE)
    k = _k(chz_musteri_garanti_bitis="1899-12-30T00:00:00", chz_grn_bit_tarihi="2026-10-20T00:00:00")
    assert MS.garanti(k, BUGUN) == (date(2026, 10, 20), MS.GARANTI_DISI)
    assert MS.garanti(_k(), BUGUN) == (None, MS.GARANTI_BILINMIYOR)
    assert MS.garanti(_k(chz_grn_bit_tarihi="2026-10-21"), BUGUN)[1] == MS.GARANTIDE    # bitiş günü dahil


def test_bilgi_ve_metin(MS):
    k = _k(chz_stok_kodu="Fazeon X24F165S", chz_st_cari_kodu="120.01", chz_st_evr_seri="G5F25",
           chz_st_evr_sira=812, chz_st_tarih="2025-04-02T00:00:00", chz_grn_bit_tarihi="2027-04-02T00:00:00",
           sto_isim="Fazeon 24 monitör")
    b = MS.bilgi(k, {"120.01": "VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI"}, BUGUN)
    assert b["stok_kodu"] == "X24F165S" and b["mikro_adi"] == "Fazeon 24 monitör"
    assert b["cari_unvan"].startswith("VATAN") and b["satis_belge_no"] == "G5F25-812"
    assert b["satis_tarihi"] == date(2025, 4, 2) and b["garanti_durumu"] == MS.GARANTIDE
    m = MS.bilgi_metni(b, "VATAN BILGISAYAR", "FAZEON 24")
    assert "X24F165S (FAZEON 24)" in m and "VATAN BILGISAYAR" in m and "G5F25-812" in m
    assert "02.04.2025" in m and "02.04.2027 (garantide)" in m
    satilmamis = MS.bilgi(_k(), {}, BUGUN)
    assert "Mikro'da satışı yok" in MS.bilgi_metni(satilmamis) and MS.GARANTI_BILINMIYOR in MS.bilgi_metni(satilmamis)


LISTE = ["VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI",
         "D-MARKET ELEKTRONİK HİZMETLER VE TİCARET ANONİM ŞİRKETİ",
         "EERA ELEKTRONİK TİCARET VE BİLİŞİM HİZMETLERİ ANONİM ŞİRKETİ", "SON KULLANICI", "DİĞER"]


def test_firma_esle_liste_yazimi(MS):
    assert MS.firma_esle("VATAN BİLGİSAYAR SANAYİ VE TİCARET A.Ş.", LISTE) == LISTE[0]   # kısa ad aynı
    assert MS.firma_esle("Vatan Bilgisayar Sanayi ve Ticaret Anonim Şirketi", LISTE) == LISTE[0]
    assert MS.firma_esle("D-MARKET ELEKTRONİK HİZMETLER VE TİCARET ANONİM ŞİRKETİ USD", LISTE) == LISTE[1]
    assert MS.firma_esle("BAŞKA FİRMA LTD", LISTE) is None and MS.firma_esle("", LISTE) is None


def test_firma_uyumlu_mu(MS):
    u = "D-MARKET ELEKTRONİK HİZMETLER VE TİCARET ANONİM ŞİRKETİ"
    assert MS.firma_uyumlu_mu("HB", u) is True                   # firma kodu → D-MARKET
    assert MS.firma_uyumlu_mu("d-market", u) is True             # kısa yazım
    assert MS.firma_uyumlu_mu(u, u) is True
    assert MS.firma_uyumlu_mu("VATAN BİLGİSAYAR SANAYİ VE TİCARET A.Ş.", LISTE[0]) is True
    assert MS.firma_uyumlu_mu("VATAN", u) is False
    assert MS.firma_uyumlu_mu("SON KULLANICI", u) is None and MS.firma_uyumlu_mu("DİĞER", u) is None
    assert MS.firma_uyumlu_mu("", u) is None and MS.firma_uyumlu_mu("VATAN", "") is None


def test_satir_tamamla_bosu_doldurur_doluyu_degistirmez(MS):
    b = {"stok_kodu": "X24F165S", "cari_unvan": "VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI"}
    sk, f, doldu, uyari = MS.satir_tamamla("", "", b, LISTE)
    assert (sk, f, doldu, uyari) == ("X24F165S", LISTE[0], ["Stok Kodu", "Firma"], [])
    sk, f, doldu, uyari = MS.satir_tamamla("Fazeon X24F165S", "VATAN", b, LISTE)
    assert (sk, f, doldu, uyari) == ("Fazeon X24F165S", "VATAN", [], [])       # uyumlu: dokunulmaz
    sk, f, doldu, uyari = MS.satir_tamamla("F11A750BBM", "HB", b, LISTE)
    assert (sk, f, doldu) == ("F11A750BBM", "HB", [])                           # çelişen değiştirilmez
    assert len(uyari) == 2 and "X24F165S" in uyari[0] and "VATAN" in uyari[1]
    # Mikro'da satılmamış (alıcı yok): firma boş kalır, zorunlu alan denetimi aynen çalışır
    assert MS.satir_tamamla("", "", {"stok_kodu": "X", "cari_unvan": ""}, LISTE)[:3] == ("X", "", ["Stok Kodu"])
    assert MS.satir_tamamla("A", "B", None) == ("A", "B", [], [])


# ── Okuma: sıralı, kopya denetimli; tablo yoksa / boşsa None ──────────
class _Sorgu:
    def __init__(self, cli, tablo):
        self.cli, self.tablo, self.sec, self.suz, self.sira, self.lim = cli, tablo, "", None, [], None

    def select(self, s):
        self.sec = s
        return self

    def limit(self, n):
        self.lim = n
        return self

    def in_(self, kolon, degerler):
        self.suz = (kolon, list(degerler))
        return self

    def order(self, kolon):
        self.sira.append(kolon)
        return self

    def execute(self):
        self.cli.sorgular.append(self)
        if self.tablo in self.cli.hata:
            raise RuntimeError("relation does not exist")
        satirlar = list(self.cli.veri.get(self.tablo, []))
        if self.suz:
            k, d = self.suz
            satirlar = [r for r in satirlar if r.get(k) in d]
        if self.lim:
            satirlar = satirlar[:self.lim]
        return types.SimpleNamespace(data=satirlar)


class _Cli:
    def __init__(self, veri=None, hata=()):
        self.veri, self.hata, self.sorgular = veri or {}, set(hata), []

    def table(self, t):
        return _Sorgu(self, t)


def _satir(guid, seri, **alan):
    return _k(chz_guid=guid, chz_serino=seri, seri_anahtar="".join(seri.split()).upper(), **alan)


@pytest.fixture()
def kopyasiz_hazir(monkeypatch):
    """satis.mikro_esitle ağır bağımlılık getirmesin: yalnız kopyasiz gerekiyor (aynı kural)."""
    if "satis.mikro_esitle" in sys.modules:
        return
    try:
        importlib.import_module("satis.mikro_esitle")
    except Exception:  # noqa: BLE001
        m = types.ModuleType("satis.mikro_esitle")

        def kopyasiz(satirlar, anahtar):
            gorulen = set()
            for r in satirlar:
                k = tuple(r.get(a) for a in anahtar) if isinstance(anahtar, (tuple, list)) else r.get(anahtar)
                if k in gorulen:
                    raise RuntimeError(f"kopya kayıt: {k}")
                gorulen.add(k)
            return satirlar
        m.kopyasiz = kopyasiz
        monkeypatch.setitem(sys.modules, "satis.mikro_esitle", m)


def test_tablo_yoksa_ya_da_bossa_eski_davranis(MS, kopyasiz_hazir):
    assert MS.oku(["M2503M00018"], cli=_Cli(hata={"mikro_serino"})) is None     # göç kurulmadı
    assert MS.oku(["M2503M00018"], cli=_Cli({"mikro_serino": []})) is None      # aktarıcı henüz doldurmadı
    assert MS.bul(["M2503M00018"], cli=_Cli(hata={"mikro_serino"})) is None


def test_okuma_sirali_ve_kopya_reddedilir(MS, kopyasiz_hazir):
    veri = {"mikro_serino": [_satir("g1", "M2503M00018"), _satir("g2", "PD2408M00069"), _satir("g3", "BASKA")]}
    cli = _Cli(veri)
    g = MS.oku([" m2503m00018", "PD2408M00069", "NO SERIAL NUMBER", "YOKBOYLE"], cli=cli)
    assert set(g) == {"M2503M00018", "PD2408M00069"}
    arama = [s for s in cli.sorgular if s.suz]
    assert arama and all(s.sira == ["chz_guid"] and s.suz[0] == "seri_anahtar" for s in arama)
    assert sorted(arama[0].suz[1]) == ["M2503M00018", "PD2408M00069", "YOKBOYLE"]
    kopya = {"mikro_serino": [_satir("g1", "M2503M00018"), _satir("g1", "M2503M00018")]}
    assert MS.oku(["M2503M00018"], cli=_Cli(kopya)) is None       # okuma sırasında tablo değişti


def test_okuma_parcali(MS, kopyasiz_hazir):
    seriler = [f"S{i:04d}" for i in range(250)]
    cli = _Cli({"mikro_serino": [_satir(f"g{i:04d}", s) for i, s in enumerate(seriler)]})
    g = MS.oku(seriler, cli=cli)
    assert len(g) == 250
    assert max(len(s.suz[1]) for s in cli.sorgular if s.suz) <= MS.PARCA


def test_bul_unvan_kart_sonra_bakiye(MS, kopyasiz_hazir):
    veri = {
        "mikro_serino": [
            _satir("g1", "M2503M00018", chz_st_cari_kodu="120.01", chz_st_evr_seri="G5F25", chz_st_evr_sira=7,
                   chz_st_tarih="2025-06-01T00:00:00", chz_grn_bit_tarihi="2027-06-01T00:00:00"),
            _satir("g2", "PD2408M00069", chz_stok_kodu="X24F100", chz_st_cari_kodu="120.09",
                   chz_grn_bit_tarihi="2026-01-01T00:00:00"),
            _satir("g3", "PD2408M00069", chz_stok_kodu="F1M650BBM", chz_iptal=1),
        ],
        "mikro_cari_kart": [{"cari_kod": "120.01", "cari_unvan1": "VATAN BILGISAYAR"}],
        "mikro_cari_bakiye": [{"cari_kod": "120.09", "cari_unvan1": "EERA ELEKTRONİK", "doviz": 0},
                              {"cari_kod": "120.09", "cari_unvan1": "EERA ELEKTRONİK", "doviz": 1}],
    }
    b = MS.bul(["M2503M00018", "PD2408M00069"], bugun=BUGUN, cli=_Cli(veri))
    assert b["M2503M00018"]["cari_unvan"] == "VATAN BILGISAYAR"
    assert b["M2503M00018"]["satis_belge_no"] == "G5F25-7" and b["M2503M00018"]["garanti_durumu"] == MS.GARANTIDE
    assert b["PD2408M00069"]["stok_kodu"] == "X24F100"              # iptal edilen tanım seçilmez
    assert b["PD2408M00069"]["cari_unvan"] == "EERA ELEKTRONİK"      # kartta yok → bakiye tablosu
    assert b["PD2408M00069"]["garanti_durumu"] == MS.GARANTI_DISI


# ── Aktarıcı, göç, yedek ────────────────────────────────────────────
@pytest.fixture()
def mk(monkeypatch):
    if importlib.util.find_spec("requests") is None:
        sahte = types.ModuleType("requests")
        sahte.Session = object
        sahte.RequestException = Exception
        sahte.Response = object
        monkeypatch.setitem(sys.modules, "requests", sahte)
    spec = importlib.util.spec_from_file_location("mikro_kayran_serino",
                                                  KOK / "araclar" / "mikro_aktarici" / "mikro_kayran.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _kolonlar(sql):
    sec = " ".join(sql.split()).split(" FROM ", 1)[0][len("SELECT "):]
    out = []
    for p in re.split(r",\s*(?![^()]*\))", sec):
        p = p.strip()
        out.append((p.split(" AS ")[-1] if " AS " in p else p.split(".")[-1]).lower())
    return out


def test_aktarici_seri_no_sorgusu(mk):
    assert "serino" in mk.SORGULAR, "aktarıcıda seri no sorgusu yok"
    t = mk.SORGULAR["serino"]
    assert t["tablo"] == "mikro_serino" and t["anahtar"] == "chz_guid" and t["artimli"] is True
    sql = " ".join(t["sql"].split())
    assert sql.startswith("SELECT ") and "FROM STOK_SERINO_TANIMLARI" in sql
    assert "chz_lastup_date > '{SON}'" in sql and "chz_iptal" not in sql.split("WHERE", 1)[1]   # iptal süzülmez
    assert "CIHAZ_HAREKETLERI" not in sql                        # belge ve cari seri no satırında
    kol = _kolonlar(t["sql"])
    for gerekli in ("chz_guid", "chz_serino", "chz_stok_kodu", "chz_iptal", "chz_st_tarih", "chz_st_evr_seri",
                    "chz_st_evr_sira", "chz_st_cari_kodu", "chz_grn_bit_tarihi", "chz_musteri_garanti_bitis",
                    "chz_al_tarih", "chz_lotno", "chz_uretim_tarihi", "chz_lastup_date"):
        assert gerekli in kol, gerekli
    assert len(kol) == len(set(kol))
    kod = (KOK / "araclar" / "mikro_aktarici" / "mikro_kayran.py").read_text(encoding="utf-8")
    assert not re.search(r"(Kaydet|Sil|Guncelle|Duzelt)V\d", kod)


def test_goc_aktarici_kolonlariyla_ayni(mk):
    yol = KOK / "veritabani" / "47_mikro_serino.sql"
    assert yol.exists(), "47_mikro_serino.sql yok"
    sema = yol.read_text(encoding="utf-8")
    govde = sema.split("CREATE TABLE IF NOT EXISTS public.mikro_serino (", 1)[1].split(";", 1)[0]
    tablo_kol = set(re.findall(r"(?:^|,)\s*([a-z_0-9]+)\s+(?:uuid|text|integer|numeric|timestamp|timestamptz)\b",
                               govde, re.M))
    for k in _kolonlar(mk.SORGULAR["serino"]["sql"]):
        assert k in tablo_kol, f"{k} tabloda yok: aktarıcı upsert'i reddedilir"
    assert "chz_guid uuid PRIMARY KEY" in sema
    assert "GENERATED ALWAYS AS (upper(regexp_replace(coalesce(chz_serino, ''), '\\s', '', 'g'))) STORED" in sema
    assert "(seri_anahtar)" in sema and "(chz_stok_kodu)" in sema            # indeksler
    assert "ENABLE ROW LEVEL SECURITY" in sema and "TO service_role" in sema and "FROM anon" in sema
    assert "GERİ ALMA: DROP TABLE mikro_serino" in sema


def test_yedek_disi():
    from shared import yedek_tablolari as YT
    assert "mikro_serino" in YT.HARIC


def test_ekran_baglantisi():
    """Toplu mal kabul ve tekli mal kabul Mikro bilgisini kullanır; tablo yoksa eski davranış (None → atlanır)."""
    kod = (KOK / "teknikservis" / "main.py").read_text(encoding="utf-8")
    kapi = kod.split("def kapi_mal_kabul(", 1)[1].split("\ndef ", 1)[0]
    assert "_MS.satir_tamamla(" in kapi and "_mikro_seri_bilgileri(" in kapi
    assert "_mk_mikro_paneli()" in kod.split("def _mal_kabul_dialog(", 1)[1]
