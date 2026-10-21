# -*- coding: utf-8 -*-
"""Mikro müşteri ürün kodları → bizim SKU (kayranpm/mikro_multikod.py, Ekim 2026).

Haftalık müşteri raporundaki kod pazaryeri kodu olabilir (D-market 'HBCV…'); bugün kart yalnız addaki model
kodundan tahmin ediliyor ve adında model kodu olmayan satır ('Fazeon F3 750W 80PLUS …') hiçbir karta
bağlanmıyordu. Mikro'daki MULTIKOD_TANIMLARI müşteri kodunu bizim stok koduna bağlar. Kurallar:
  - yalnız bugünkü zincirin bağlayamadığı kod çevrilir; eşleşen kod olduğu gibi kalır (rakamı değişmez);
  - eşleşme yükleme anında: satır bizim SKU'yla yazılır, raporun kodu musteri_kodu'nda; eski raporlar değişmez;
  - tablo yok / boşsa eski davranış aynen.
"""
import re
import sys
import types
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

import shared.yukleme_gecmisi as Y

KOK = Path(__file__).resolve().parent.parent
DMARKET = "D-MARKET ELEKTRONİK HİZMETLER VE TİCARET ANONİM ŞİRKETİ"
AVASYA = "AVASYA TEKNOLOJİ SANAYİ VE DIŞ TİCARET LİMİTED ŞİRKETİ"
F3_AD = "Fazeon F3 750W 80PLUS Bronze 7X120MM Argb Fanlı Atx Bilgisayar Kasası"      # canlıda eşleşmeyen satır
X24_AD = "Fazeon 23.8' X24F182S 1ms 180Hz Fhd IPS Gamıng Monıtor"                    # bugün addan eşleşen satır
KARTLAR = {"F3A750BBQ": {"marka": "Fazeon", "kategori": "Kasa", "urun_adi": "FAZEON F3 750W …"},
           "X24F182S": {"marka": "Fazeon", "kategori": "Monitör", "urun_adi": "Fazeon x24f182s …"},
           "X24F240P": {"marka": "Fazeon", "kategori": "Monitör", "urun_adi": "Fazeon x24f240p …"}}


def _mc(guid, cari, stok, kod, ad=""):
    return {"mcod_guid": guid, "mcod_carikodu": cari, "mcod_stokkod": stok, "mcod_caristok_kod": kod,
            "mcod_caristok_ismi": ad, "mcod_tipi": 0}


MULTIKOD = [_mc("g1", "120.01.004", "F3A750BBQ", "HBCV00008RSHI5"),
            _mc("g2", "120.01.004", "X24F240P", "HBCV0000G0F6K6"),     # bugünkü kural X24F182S der → çelişki
            _mc("g3", "120.02.017", "Fazeon X24F240P", "MON24FAZX24F240PZ"),
            _mc("g4", "120.01.004", "YOKKART", "HBCVYOK")]
CARI = [{"cari_kod": "120.01.004", "cari_unvan1": DMARKET}, {"cari_kod": "320.02.057", "cari_unvan1": DMARKET},
        {"cari_kod": "120.02.017", "cari_unvan1": AVASYA}]


# ── Saf ────────────────────────────────────────────────────────────
def test_harita_firma_ve_kod_anahtari():
    from kayranpm import mikro_multikod as M
    h = M.harita_kur(MULTIKOD, {r["cari_kod"]: r["cari_unvan1"] for r in CARI})
    assert set(h) == {M.firma_anahtar("HB"), M.firma_anahtar(AVASYA)}      # D-MARKET cari → firma_stok 'HB'
    assert h[M.firma_anahtar("HB")]["HBCV00008RSHI5"] == "F3A750BBQ"
    assert h[M.firma_anahtar(AVASYA)]["MON24FAZX24F240PZ"] == "Fazeon X24F240P"
    # ünvanı bilinmeyen cari atlanır
    assert M.harita_kur([_mc("g9", "999", "A1", "K1")], {}) == {}


def test_ayni_kod_iki_stoga_gidiyorsa_kullanilmaz():
    from kayranpm import mikro_multikod as M
    satir = [_mc("a", "120.01.004", "F3A750BBQ", "K1"), _mc("b", "320.02.057", "F3A750BWQ", "k1 "),
             _mc("c", "120.01.004", "Fazeon F3A750BBQ", "K2"), _mc("d", "120.01.004", "F3A750BBQ", "K2")]
    unvan = {r["cari_kod"]: r["cari_unvan1"] for r in CARI}
    h = M.harita_kur(satir, unvan)[M.firma_anahtar("HB")]
    assert "K1" not in h and h["K2"] in ("F3A750BBQ", "Fazeon F3A750BBQ")   # aynı SKU'nun iki yazımı belirsiz değil
    assert M.belirsizler(satir, unvan) == [(M.firma_anahtar("HB"), "K1", ["F3A750BBQ", "F3A750BWQ"])]


def test_yalniz_eslesmeyen_kod_cevrilir():
    from kayranpm import mikro_multikod as M
    from kayranpm.musteri_hesap import meta_hazirla
    from shared.utils import sku_anahtar
    agg = {"HBCV00008RSHI5": {"ad": F3_AD, "stok": 4, "stok_magaza": 0, "satis": 1, "satis_magaza": 0},
           "HBCV0000G0F6K6": {"ad": X24_AD, "stok": 10, "stok_magaza": 0, "satis": 5, "satis_magaza": 0},
           "HBCVYOK": {"ad": "Bilinmeyen", "stok": 1, "stok_magaza": 0, "satis": 0, "satis_magaza": 0},
           "F3A750BBQ": {"ad": "", "stok": 2, "stok_magaza": 1, "satis": 3, "satis_magaza": 0}}
    meta = meta_hazirla([{"sku": k, "urun_adi": o["ad"]} for k, o in agg.items()], KARTLAR, sku_fn=sku_anahtar)
    assert meta["HBCV00008RSHI5"]["kart_kaynak"] == ""          # bugün eşleşmiyor (kırmızı kanıtın temeli)
    fh = M.harita_kur(MULTIKOD, {r["cari_kod"]: r["cari_unvan1"] for r in CARI})[M.firma_anahtar("HB")]
    out, oz = M.uygula(agg, fh, KARTLAR, meta)
    assert set(out) == {"F3A750BBQ", "HBCV0000G0F6K6", "HBCVYOK"}
    f3 = out["F3A750BBQ"]                                         # karttaki satırla toplandı
    assert (f3["stok"], f3["stok_magaza"], f3["satis"], f3["musteri_kodu"]) == (6, 1, 4, "HBCV00008RSHI5")
    assert f3["ad"] == F3_AD
    assert out["HBCV0000G0F6K6"]["stok"] == 10 and "musteri_kodu" not in out["HBCV0000G0F6K6"]
    assert oz["eslesen"] == [("HBCV00008RSHI5", "F3A750BBQ")]
    assert oz["celiski"] == [("HBCV0000G0F6K6", "X24F182S", "X24F240P")]   # mevcut kural korunur
    assert oz["kartsiz"] == [("HBCVYOK", "YOKKART")]


def test_kod_haritasi_eslesmesi_de_korunur():
    from kayranpm import mikro_multikod as M
    agg = {"HBCV00008RSHI5": {"ad": F3_AD, "stok": 4, "satis": 1}}
    out, oz = M.uygula(agg, {"HBCV00008RSHI5": "F3A750BBQ"}, KARTLAR, meta={},
                       kod_haritasi={"HBCV00008RSHI5": "X24F240P"})
    assert list(out) == ["HBCV00008RSHI5"] and oz["celiski"] == [("HBCV00008RSHI5", "X24F240P", "F3A750BBQ")]


def test_meta_mikro_kaynagini_isaretler():
    from kayranpm.musteri_hesap import meta_hazirla
    from shared.utils import sku_anahtar
    rows = [{"sku": "F3A750BBQ", "urun_adi": F3_AD, "musteri_kodu": "HBCV00008RSHI5"},
            {"sku": "X24F182S", "urun_adi": "", "musteri_kodu": None}]
    meta = meta_hazirla(rows, KARTLAR, sku_fn=sku_anahtar)
    assert meta["F3A750BBQ"]["kart_kaynak"] == "mikro" and meta["F3A750BBQ"]["kart_sku"] == "F3A750BBQ"
    assert meta["X24F182S"]["kart_kaynak"] == "sku"
    from kayranpm import musteri_ekran
    assert musteri_ekran._KART_KAYNAK["mikro"] == "Mikro kod eşleşmesi"


# ── Yükleyici (Dosya kapısı "musteri_haftalik") ─────────────────────
class _Q:
    def __init__(self, db, t):
        self.db, self.t, self.f, self.ins, self.sil, self.sira = db, t, {}, None, False, []

    def select(self, *a, **k):
        return self

    def order(self, c, desc=False):
        self.sira.append(c)
        return self

    def eq(self, c, v):
        self.f[c] = v
        return self

    def delete(self):
        self.sil = True
        return self

    def insert(self, rows):
        self.ins = rows if isinstance(rows, list) else [rows]
        return self

    def execute(self):
        if self.t in self.db.get("_yok", ()):
            raise RuntimeError("PGRST205 tablo yok")
        rows = self.db.setdefault(self.t, [])
        uy = [r for r in rows if all(r.get(c) == v for c, v in self.f.items())]
        if self.ins is not None:
            keys = {tuple(sorted(r)) for r in self.ins}
            assert len(keys) == 1, "toplu insert'te satırların anahtarları aynı olmalı"
            out = []
            for r in self.ins:
                self.db["_id"] = self.db.get("_id", 100) + 1
                out.append(dict(r, id=self.db["_id"]))
            rows.extend(out)
            return type("R", (), {"data": out})()
        if self.sil:
            self.db[self.t] = [r for r in rows if r not in uy]
            return type("R", (), {"data": uy})()
        if self.t == "mikro_multikod":
            assert self.sira == ["mcod_guid"], "sıralı okuma"
        return type("R", (), {"data": [dict(r) for r in uy]})()


class _DB:
    def __init__(self, tablolar, yok=()):
        self.v = {k: [dict(r) for r in v] for k, v in tablolar.items()}
        self.v["_yok"] = set(yok)

    def table(self, t):
        return _Q(self.v, t)


def _dosya():
    b = BytesIO()
    with pd.ExcelWriter(b, engine="openpyxl") as w:
        pd.DataFrame({"Sku": ["HBCV00008RSHI5", "HBCV0000G0F6K6"], "Ürün Adı": [F3_AD, X24_AD],
                      "Stok": [4, 10]}).to_excel(w, index=False, sheet_name="HB STOK")
        pd.DataFrame({"Sku": ["HBCV00008RSHI5", "HBCV0000G0F6K6"], "Miktar": [1, 5],
                      "Tarih": ["2026-10-18", "2026-10-18"]}).to_excel(w, index=False, sheet_name="HB SATIŞ")
    b.seek(0)
    return b


@pytest.fixture
def ortam(monkeypatch):
    import kayranpm.database as D
    import kayranpm.excel_islemler as E
    monkeypatch.setattr(Y, "kaydet", lambda *a, **k: 1)
    monkeypatch.setattr(D, "get_urun_marka_kategori", lambda: dict(KARTLAR))
    monkeypatch.setattr(D, "get_sku_eslesme", lambda: [])
    monkeypatch.setattr(D, "kanal_kod_haritasi", lambda: {})

    def kur(**k):
        db = _DB({"firma_stok": [], "mikro_multikod": MULTIKOD, "mikro_cari_kart": CARI,
                  "mikro_cari_bakiye": []}, **k)
        monkeypatch.setattr(E, "get_client", lambda: db)
        return E, db
    return kur


def test_yeni_yuklemede_mikro_kodu_bizim_skuya_yazilir(ortam):
    """Eski kodda 'HBCV00008RSHI5' rapor koduyla yazılıyor, hiçbir karta bağlanmıyordu."""
    E, db = ortam()
    ok, msg = E.excel_yukle_haftalik_stok_satis(_dosya(), dosya_adi="h.xlsx")
    assert ok, msg
    yaz = {r["sku"]: r for r in db.v["firma_stok"]}
    assert set(yaz) == {"F3A750BBQ", "HBCV0000G0F6K6"}
    assert (yaz["F3A750BBQ"]["stok_miktari"], yaz["F3A750BBQ"]["haftalik_satis"]) == (4, 1)
    assert yaz["F3A750BBQ"]["musteri_kodu"] == "HBCV00008RSHI5"
    assert yaz["HBCV0000G0F6K6"]["musteri_kodu"] is None                # bugün eşleşen kod değişmedi
    assert "Mikro kod eşleşmesi: HB 1 kod" in msg


def test_onizleme_mikro_sayisini_gosterir(ortam):
    E, db = ortam()
    ok, oz = E.excel_yukle_haftalik_stok_satis(_dosya(), dosya_adi="h.xlsx", onizle=True)
    assert ok and oz["firmalar"]["HB"].get("mikro") == 1 and oz["firmalar"]["HB"]["sku"] == 2
    assert db.v["firma_stok"] == []


@pytest.mark.parametrize("durum", ["yok", "bos", "kopya"])
def test_tablo_yoksa_bossa_eski_davranis(ortam, durum):
    E, db = ortam(yok=("mikro_multikod",) if durum == "yok" else ())
    if durum == "bos":
        db.v["mikro_multikod"] = []
    if durum == "kopya":                                     # tutarsız okuma (aynı guid iki kez) → kullanılmaz
        db.v["mikro_multikod"] = MULTIKOD + [dict(MULTIKOD[0])]
    ok, msg = E.excel_yukle_haftalik_stok_satis(_dosya(), dosya_adi="h.xlsx")
    assert ok, msg
    assert sorted(r["sku"] for r in db.v["firma_stok"]) == ["HBCV00008RSHI5", "HBCV0000G0F6K6"]
    assert all("musteri_kodu" not in r for r in db.v["firma_stok"]) and "Mikro" not in msg


# ── Aktarıcı + göç + yedek ──────────────────────────────────────────
def test_aktarici_multikod_sorgusu_ve_goc(monkeypatch):
    import importlib.util
    if importlib.util.find_spec("requests") is None:
        sahte = types.ModuleType("requests")
        sahte.Session, sahte.RequestException, sahte.Response = object, Exception, object
        monkeypatch.setitem(sys.modules, "requests", sahte)
    yol = KOK / "araclar" / "mikro_aktarici" / "mikro_kayran.py"
    spec = importlib.util.spec_from_file_location("mikro_kayran_mc", yol)
    mk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mk)
    from kayranpm import mikro_multikod as M
    assert "multikod" in mk.SORGULAR
    t = mk.SORGULAR["multikod"]
    assert t["tablo"] == M.TABLO and t["anahtar"] == "mcod_guid" and not t["artimli"]
    sql = " ".join(t["sql"].split())
    assert sql.startswith("SELECT ") and "FROM MULTIKOD_TANIMLARI" in sql and "mcod_Iptal=0" in sql
    for yasak in ("INSERT", "UPDATE", "DELETE", "MERGE", "EXEC", "DROP"):
        assert not re.search(rf"\b{yasak}\b", sql.upper())
    assert not re.search(r"(Kaydet|Sil|Guncelle|Duzelt)" + r"V\d", yol.read_text(encoding="utf-8"))
    secilen = {c.strip().lower() for c in sql[len("SELECT "):sql.index(" FROM ")].split(",")}
    goc = (KOK / "veritabani" / "48_mikro_multikod.sql").read_text(encoding="utf-8")
    i = goc.index("TABLE IF NOT EXISTS public.mikro_multikod (")
    govde = goc[i:goc.index(");", i)]
    kolon = {m.group(1) for m in re.finditer(r"(\w+) (?:uuid|timestamp|integer|text|numeric|boolean|timestamptz)",
                                             govde)} - {"senk_zamani"}
    assert secilen == kolon
    assert set(M.KOLONLAR.split(",")) <= kolon
    assert "ADD COLUMN IF NOT EXISTS musteri_kodu text" in goc and "GERİ ALMA" in goc
    assert "service_role" in goc and "ENABLE ROW LEVEL SECURITY" in goc
    from shared.yedek_tablolari import HARIC
    assert M.TABLO in HARIC


def test_okuma_musteri_kodunu_getirir_kolon_yoksa_eskisi(monkeypatch):
    import kayranpm.database as D
    secimler = []

    class Q:
        def __init__(self, s):
            self.s = s

        def __getattr__(self, ad):
            return lambda *a, **k: self

        def execute(self):
            secimler.append(self.s)
            if "musteri_kodu" in self.s:
                raise RuntimeError("42703 column firma_stok.musteri_kodu does not exist")
            return type("R", (), {"data": [{"firma": "HB", "sku": "A1", "yukleme_tarihi": "2026-10-18"}]})()

    class C:
        def table(self, t):
            return type("T", (), {"select": lambda _s, s: Q(s)})()

    monkeypatch.setattr(D, "get_client", lambda: C())
    fn = getattr(D.get_musteri_haftalik_satis, "__wrapped__", D.get_musteri_haftalik_satis)
    rows = fn("2026-10-12", "2026-10-18")
    assert [r["sku"] for r in rows] == ["A1"]
    assert "musteri_kodu" in secimler[0] and "musteri_kodu" not in secimler[1] and "satis_magaza" in secimler[1]
