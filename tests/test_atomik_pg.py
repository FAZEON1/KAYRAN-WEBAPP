# -*- coding: utf-8 -*-
"""Atomik stok (veritabani/29_atomik_stok.sql) — GERÇEK Postgres'te eşdeğerlik ve eşzamanlılık kanıtı.

Aynı başlangıç verisiyle iki ayrı veritabanında aynı akışlar çalıştırılır:
  · ESKİ : SQL fonksiyonları KURULU DEĞİL → uygulama bugünkü yola düşer (PGRST202 benzeri hata),
  · YENİ : 29_atomik_stok.sql kurulu → uygulama atomik fonksiyonları çağırır.
Sonda urunler (depo_kirilim, bizim_stok, guncelleme_tarihi), stok_hareketleri, satislar, iadeler ve
depo_sevk_log birebir karşılaştırılır. Uygulama kodu Supabase istemcisi yerine aynı arayüzü taklit eden
ince bir psycopg bağdaştırıcısıyla gerçek Postgres'e yazar (her istek ayrı işlem — PostgREST gibi).

Çalıştırmak için: psycopg (3) kurulu ve KAYRAN_TEST_PG_DSN tanımlı olmalı, ör.
  KAYRAN_TEST_PG_DSN="host=127.0.0.1 port=54329 user=postgres dbname=postgres"
Kullanıcının CREATE DATABASE yetkisi gerekir. Yoksa bu dosyadaki testler ATLANIR (CI'da atlanır).
"""
import json
import os
import threading
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")
DSN = os.environ.get("KAYRAN_TEST_PG_DSN", "")
if not DSN:
    pytest.skip("KAYRAN_TEST_PG_DSN tanımlı değil — gerçek Postgres testi atlandı", allow_module_level=True)

import kayranpm.database as pmdb          # noqa: E402
import satis.database as sdb              # noqa: E402
import shared.audit as AU                 # noqa: E402
import shared.cop_kutusu as CK            # noqa: E402
import shared.hata_log as HL              # noqa: E402
import shared.stok_defteri as SD          # noqa: E402

KOK = Path(__file__).resolve().parent.parent
SQL = (KOK / "veritabani" / "29_atomik_stok.sql").read_text(encoding="utf-8")

SEMA = """
CREATE TABLE urunler (sku text PRIMARY KEY, urun_adi text, bizim_stok integer DEFAULT 0,
                      depo_kirilim jsonb, guncelleme_tarihi date);
CREATE TABLE stok_hareketleri (id bigserial PRIMARY KEY, zaman timestamptz NOT NULL DEFAULT now(),
    sku text NOT NULL, depo text, onceki numeric, sonraki numeric, degisim numeric, tur text,
    aciklama text, kaynak text, kullanici text, basarili boolean NOT NULL DEFAULT true, hata text,
    yukleme_kodu text);
CREATE TABLE satislar (id bigserial PRIMARY KEY, tarih date, kanal text, sku text, urun_adi text,
    adet integer, birim_satis numeric, birim_maliyet numeric, birim_firma_destek numeric,
    birim_ek_destek numeric, kampanya_id bigint, notlar text, olusturma_tarihi timestamptz, siparis_no text);
CREATE TABLE iadeler (id bigserial PRIMARY KEY, tarih date, kanal text, sku text, urun_adi text,
    iade_adet integer, iade_brut numeric, iade_iskonto numeric, iade_masraf numeric, iade_net numeric,
    depo text, kaynak text, donem_bas date, donem_bit date);
CREATE TABLE depo_sevk_log (id bigserial PRIMARY KEY, sku text, urun_adi text, kaynak_depo text,
    hedef_depo text, adet integer, kullanici text, tarih text, sevk_tarihi date, belge_no text);
"""

BASLANGIC = [  # (sku, ad, depo_kirilim, bizim_stok)
    ("X24F241S", "Monitör 24", {"MERKEZ DEPO": 10, "HAPPY LIFE": 4}, 14),
    ("X24F200", "Monitör 200", {"MERKEZ DEPO": 3}, 3),
    ("Mio MiVue J30", "Kamera", {"MERKEZ DEPO": 5, "İADE DEPO": 1}, 5),
    ("ABC", "Kablo", {"Merkez": 7, "HAPPY LIFE": 2.0, "ASEL DEPO": 9}, 9),
    ("BOS", "Boş kırılım", None, 0),
    ("METIN", "Metin değer", {"MERKEZ DEPO": "6", "TEKNİK DEPO": 1}, 6),
    ("KESIR", "Kesirli", {"MERKEZ DEPO": 2.5}, 2),
]


# ── Supabase istemcisini taklit eden psycopg bağdaştırıcısı ─────────────
class ApiHata(Exception):
    def __init__(self, code, message):
        super().__init__(json.dumps({"code": code, "message": message}, ensure_ascii=False))
        self.code, self.message = code, message


class _Yanit:
    def __init__(self, data):
        self.data = data


class _Sorgu:
    def __init__(self, cli, tablo):
        self.cli, self.t = cli, tablo
        self.islem, self.secim, self.yuk = "select", "*", None
        self.filtre, self.sira, self.sinir = [], [], None

    def select(self, secim="*", **k):
        self.secim = secim
        return self

    def eq(self, k, v):
        self.filtre.append((k, "=", v))
        return self

    def in_(self, k, v):
        self.filtre.append((k, "in", list(v)))
        return self

    def gte(self, k, v):
        self.filtre.append((k, ">=", v))
        return self

    def lte(self, k, v):
        self.filtre.append((k, "<=", v))
        return self

    def order(self, k, desc=False):
        self.sira.append(f"{k} {'DESC' if desc else 'ASC'}")
        return self

    def limit(self, n):
        self.sinir = (0, n - 1)
        return self

    def range(self, a, b):
        self.sinir = (a, b)
        return self

    def insert(self, yuk, *a, **k):
        self.islem, self.yuk = "insert", yuk
        return self

    def update(self, yuk, *a, **k):
        self.islem, self.yuk = "update", yuk
        return self

    def delete(self, *a, **k):
        self.islem = "delete"
        return self

    def _where(self):
        parca, deg = [], []
        for k, op, v in self.filtre:
            if op == "in":
                parca.append(f"{k}::text = ANY(%s)")
                deg.append([str(x) for x in v])
            else:
                parca.append(f"{k}::text {op} %s")
                deg.append(str(v))
        return (" WHERE " + " AND ".join(parca)) if parca else "", deg

    def execute(self):
        w, deg = self._where()
        t = self.t
        if self.islem == "select":
            q = f"SELECT {self.secim} FROM {t}{w}"
            if self.sira:
                q += " ORDER BY " + ", ".join(self.sira)
            if self.sinir:
                q += f" OFFSET {self.sinir[0]} LIMIT {self.sinir[1] - self.sinir[0] + 1}"
            return _Yanit(self.cli.json(f"SELECT coalesce(jsonb_agg(to_jsonb(r)), '[]')::text FROM ({q}) r", deg))
        if self.islem == "delete":
            return _Yanit(self.cli.json(f"WITH r AS (DELETE FROM {t}{w} RETURNING *) "
                                        "SELECT coalesce(jsonb_agg(to_jsonb(r)), '[]')::text FROM r", deg))
        satirlar = self.yuk if isinstance(self.yuk, list) else [self.yuk]
        kolon = []
        for s in satirlar:
            kolon += [k for k in s if k not in kolon]
        kl = ", ".join(kolon)
        if self.islem == "insert":
            q = (f"WITH r AS (INSERT INTO {t} ({kl}) SELECT {kl} FROM jsonb_populate_recordset(NULL::{t}, %s::jsonb) "
                 "RETURNING *) SELECT coalesce(jsonb_agg(to_jsonb(r)), '[]')::text FROM r")
            return _Yanit(self.cli.json(q, [json.dumps(satirlar)]))
        q = (f"WITH r AS (UPDATE {t} SET ({kl}) = (SELECT {kl} FROM jsonb_populate_record(NULL::{t}, %s::jsonb))"
             f"{w} RETURNING *) SELECT coalesce(jsonb_agg(to_jsonb(r)), '[]')::text FROM r")
        return _Yanit(self.cli.json(q, [json.dumps(satirlar[0])] + deg))


class _Rpc:
    def __init__(self, cli, ad, params):
        self.cli, self.ad, self.params = cli, ad, params

    def execute(self):
        return _Yanit(self.cli.cagir(self.ad, self.params))


class PgIstemci:
    """Her istek ayrı bağlantı/işlem (PostgREST gibi) — iş parçacıkları güvenle paylaşır."""

    def __init__(self, dsn, araya=None):
        self.dsn, self.araya = dsn, araya
        self.rpc_sayac = {"basarili": 0, "yok": 0}

    def _baglan(self):
        return psycopg.connect(self.dsn, autocommit=True)

    def json(self, q, deg):
        try:
            with self._baglan() as c:
                r = c.execute(q, deg).fetchone()[0]
        except psycopg.Error as e:
            raise ApiHata(e.sqlstate or "", (e.diag.message_primary or str(e))) from None
        if self.araya:
            self.araya(q)
        return json.loads(r)

    def table(self, ad):
        return _Sorgu(self, ad)

    def rpc(self, ad, params):
        return _Rpc(self, ad, params)

    def cagir(self, ad, params):
        with self._baglan() as c:
            r = c.execute("SELECT proargnames, proargtypes::regtype[]::text[] FROM pg_proc p "
                          "JOIN pg_namespace n ON n.oid = p.pronamespace "
                          "WHERE n.nspname = 'public' AND proname = %s", [ad]).fetchone()
            if not r:
                self.rpc_sayac["yok"] += 1
                raise ApiHata("PGRST202", f"Could not find the function public.{ad} in the schema cache")
            adlar, tipler = r
            parca, deg = [], []
            for a, tp in zip(adlar, tipler):
                v = params.get(a)
                parca.append(f"{a} => %s::{tp}")
                if v is None:
                    deg.append(None)
                elif tp in ("jsonb", "json"):
                    deg.append(json.dumps(v))
                else:
                    deg.append(str(v))
            try:
                sonuc = c.execute(f"SELECT {ad}({', '.join(parca)})::text", deg).fetchone()[0]
            except psycopg.Error as e:
                raise ApiHata(e.sqlstate or "", e.diag.message_primary or str(e)) from None
        self.rpc_sayac["basarili"] += 1
        return json.loads(sonuc) if sonuc is not None else None


def _atomik_sifirla():
    """'Fonksiyon yok' önbelleğini sıfırla (iki veritabanı arasında geçerken)."""
    if hasattr(pmdb, "_ATOMIK"):
        pmdb._ATOMIK["yok_zaman"] = 0.0


# ── Veritabanı kurulumu ─────────────────────────────────────────────
def _dsn_db(ad):
    parca = [p for p in DSN.split() if not p.startswith("dbname=")]
    return " ".join(parca + [f"dbname={ad}"])


@pytest.fixture(scope="module")
def veritabanlari():
    try:
        kok = psycopg.connect(DSN, autocommit=True)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres'e bağlanılamadı: {e}")
    adlar = {"eski": "kayran_atomik_eski", "yeni": "kayran_atomik_yeni"}
    for ad in adlar.values():
        kok.execute(f"DROP DATABASE IF EXISTS {ad}")
        kok.execute(f"CREATE DATABASE {ad}")
    kok.close()
    with psycopg.connect(_dsn_db(adlar["yeni"]), autocommit=True) as c:
        c.execute(SEMA)
        c.execute(SQL)
        c.execute(SQL)                                     # tekrar çalıştırılabilir
    with psycopg.connect(_dsn_db(adlar["eski"]), autocommit=True) as c:
        c.execute(SEMA)
    yield {k: _dsn_db(v) for k, v in adlar.items()}


def _sifirla(dsn, baslangic=BASLANGIC):
    with psycopg.connect(dsn, autocommit=True) as c:
        c.execute("TRUNCATE urunler, stok_hareketleri, satislar, iadeler, depo_sevk_log RESTART IDENTITY")
        for sku, ad, dk, bs in baslangic:
            c.execute("INSERT INTO urunler (sku, urun_adi, depo_kirilim, bizim_stok, guncelleme_tarihi) "
                      "VALUES (%s, %s, %s::jsonb, %s, '2026-01-01')",
                      [sku, ad, json.dumps(dk) if dk is not None else None, bs])


def _durum(dsn, sirasiz_defter=False):
    with psycopg.connect(dsn, autocommit=True) as c:
        urun = c.execute("SELECT sku, urun_adi, bizim_stok, depo_kirilim::text, guncelleme_tarihi::text "
                         "FROM urunler ORDER BY sku").fetchall()
        defter = [(s, d, float(o), float(n), float(g), t, a, k, ku, b, h, y) for s, d, o, n, g, t, a, k, ku, b, h, y in
                  c.execute("SELECT sku, depo, onceki, sonraki, degisim, tur, aciklama, kaynak, kullanici, "
                            "basarili, hata, yukleme_kodu FROM stok_hareketleri ORDER BY id").fetchall()]
        satis = c.execute("SELECT id, tarih::text, kanal, sku, urun_adi, adet, birim_satis::float8, "
                          "birim_maliyet::float8, notlar, siparis_no FROM satislar ORDER BY id").fetchall()
        iade = c.execute("SELECT id, tarih::text, kanal, sku, iade_adet, iade_net::float8, depo, kaynak, "
                         "donem_bas::text, donem_bit::text FROM iadeler ORDER BY id").fetchall()
        sevk = c.execute("SELECT sku, urun_adi, kaynak_depo, hedef_depo, adet, kullanici, sevk_tarihi::text, "
                         "belge_no FROM depo_sevk_log ORDER BY id").fetchall()
    if sirasiz_defter:
        defter = sorted(defter, key=repr)
    return {"urunler": urun, "defter": defter, "satislar": satis, "iadeler": iade, "sevk": sevk}


@pytest.fixture
def ortam(monkeypatch, veritabanlari):
    """İki veritabanında aynı senaryoyu koşturan yardımcı. Döner: calistir(senaryo) → (eski, yeni)."""
    hatalar = []
    monkeypatch.setattr(HL, "kaydet", lambda yer, hata, ayrinti="", kritik=False:
                        hatalar.append((yer, str(hata), kritik)) or True)
    monkeypatch.setattr(AU, "log_yaz", lambda *a, **k: None)
    monkeypatch.setattr(CK, "sakla", lambda *a, **k: None)
    monkeypatch.setattr(sdb, "_marj_uyarisi_gonder", lambda *a, **k: (False, "test"))
    monkeypatch.setattr(sdb, "_temizle", lambda: None)
    monkeypatch.setattr(pmdb, "_cache_temizle", lambda: None)
    monkeypatch.setattr(pmdb, "get_today", lambda: "2026-10-14")
    monkeypatch.setattr(pmdb, "tr_now_str", lambda *a, **k: "14.10.2026 12:00")

    def calistir(senaryo, sirasiz_defter=False, baslangic=BASLANGIC):
        sonuc = {}
        for tur in ("eski", "yeni"):
            dsn = veritabanlari[tur]
            _sifirla(dsn, baslangic)
            cli = PgIstemci(dsn)
            monkeypatch.setattr(pmdb, "get_client", lambda c=cli: c)
            monkeypatch.setattr(sdb, "_get_client", lambda c=cli: c)
            import shared.auth as A
            monkeypatch.setattr(A, "_get_supabase", lambda c=cli: c)

            def _kartlar(c=cli):
                return {r["sku"]: {"marka": "", "kategori": "", "urun_adi": r.get("urun_adi") or ""}
                        for r in c.table("urunler").select("sku, urun_adi").execute().data}
            monkeypatch.setattr(pmdb, "get_urun_marka_kategori", _kartlar)
            _atomik_sifirla()
            donus = senaryo()
            sonuc[tur] = {"durum": _durum(dsn, sirasiz_defter), "donus": donus, "rpc": dict(cli.rpc_sayac)}
        _atomik_sifirla()
        # eski yol fonksiyonu GERÇEKTEN bulamadı ve hiç başarılı çağrı olmadı; yeni yol çağırdı
        assert sonuc["eski"]["rpc"]["basarili"] == 0
        assert sonuc["yeni"]["rpc"]["basarili"] >= 1 and sonuc["yeni"]["rpc"]["yok"] == 0
        return sonuc["eski"], sonuc["yeni"]

    calistir.hatalar = hatalar
    return calistir


def _ayni(eski, yeni):
    for anahtar in ("urunler", "defter", "satislar", "iadeler", "sevk"):
        assert eski["durum"][anahtar] == yeni["durum"][anahtar], anahtar
    assert eski["donus"] == yeni["donus"]


# ═══════════════════════════════════════════════════════════════════
# 1) SQL yardımcıları Python'la aynı
# ═══════════════════════════════════════════════════════════════════
DEPO_ORNEKLERI = ["MERKEZ DEPO", "merkez", " Merkez  Depo ", "MERKEZDEPO", "happy life", "HappyLife", "happy",
                  "asel", "Teknik", "teknik servis", "servis depo", "Servis", "iade", "İade Depo", "İADE DEPO",
                  "outlet", "ikinci el", "2.el", "2 el", "İkinci El Depo", "hurda", "şube çıkış", "Özel  depo",
                  "ığüşöç", "", "  ", "x\ty", "ACB Depo"]


def test_depo_kanonik_ve_bizim_stok_python_ile_ayni(veritabanlari):
    with psycopg.connect(veritabanlari["yeni"], autocommit=True) as c:
        for d in DEPO_ORNEKLERI:
            assert c.execute("SELECT kayran_depo_kanonik(%s)", [d]).fetchone()[0] == pmdb.depo_kanonik(d), d
        for dk in [{"MERKEZ": 3, "Happy Life": 2.7, "ASEL": 9}, {}, {"MERKEZ DEPO": -4.0, "MERKEZ": 1},
                   {"HAPPY LIFE": "5", "merkez depo": None}, {"MERKEZ DEPO": True}]:
            assert c.execute("SELECT kayran_bizim_stok(%s::jsonb)", [json.dumps(dk)]).fetchone()[0] \
                == pmdb._bizim_stok_hesapla(dk), dk


# ═══════════════════════════════════════════════════════════════════
# 2) Eşdeğerlik senaryoları (eski yol ↔ atomik yol, aynı başlangıç)
# ═══════════════════════════════════════════════════════════════════
def test_stok_hareket_coklu_cok_depo_eksik_depo_eksiye_yazim_farki(ortam):
    def senaryo():
        out = [pmdb.stok_hareket_coklu({"X24F241S": -3, "x24f241s": -1, "Fazeon X24F200": -5, "MIO MIVUE J30": 2,
                                        "YOK-SKU": -1, "ABC": -2, "BOS": -1, "METIN": -1, "KESIR": -2.5,
                                        "": 4, "SIFIR": 0}, "MERKEZ DEPO", aciklama="")]
        out.append(pmdb.stok_hareket_coklu({"X24F241S": 6, "ABC": 1}, "happy life"))
        out.append(pmdb.stok_hareket_coklu({"X24F241S": 2}, "Asel"))            # kırılımda olmayan depo
        out.append(pmdb.stok_hareket_coklu({"X24F241S": -1}, None, aciklama="elle"))
        out.append(pmdb.stok_hareket_coklu({"YENI-KART": 3}, "MERKEZ DEPO", kart_ac=True,
                                           kart_adlar={"YENI-KART": "Yeni ürün"}))
        return out
    eski, yeni = ortam(senaryo)
    _ayni(eski, yeni)
    u = dict((r[0], r) for r in yeni["durum"]["urunler"])
    assert json.loads(u["X24F200"][3])["MERKEZ DEPO"] == -2.0                 # eksiye düştü
    assert yeni["donus"][0][1] == ["YOK-SKU"]                                 # kartı olmayan atlandı


def test_satis_kaydi_depolu_ve_ayni_sku_iki_kalem(ortam):
    def senaryo():
        kalemler = [{"sku": "X24F241S", "adet": 2, "birim_satis": 100, "birim_maliyet": 60, "depo": "HAPPY LIFE"},
                    {"sku": "X24F241S", "adet": 1, "birim_satis": 100, "birim_maliyet": 60, "depo": "HAPPY LIFE"},
                    {"sku": "ABC", "adet": 3, "birim_satis": 5, "birim_maliyet": 2, "depo": ""},
                    {"sku": "YOK-SKU", "adet": 1, "birim_satis": 5, "birim_maliyet": 2, "depo": "MERKEZ DEPO"},
                    {"sku": "X24F200", "adet": 0, "birim_satis": 5}]
        return sdb.ekle_siparis("2026-10-14", "VATAN", "S-1", "not", kalemler)
    eski, yeni = ortam(senaryo)
    _ayni(eski, yeni)
    assert yeni["donus"][0] is True and "YOK-SKU" in yeni["donus"][1]          # stok sorunu görünür


def test_satis_silme_ve_siparis_silme(ortam):
    def senaryo():
        sdb.ekle_siparis("2026-10-14", "VATAN", "S-1", "", [{"sku": "X24F241S", "adet": 2, "depo": "MERKEZ DEPO"},
                                                            {"sku": "ABC", "adet": 1}])
        sdb.ekle_siparis("2026-10-14", "HB", "S-2", "", [{"sku": "Mio MiVue J30", "adet": 1},
                                                         {"sku": "YOK-SKU", "adet": 2}])
        sdb.ekle_siparis("2026-10-14", "HB", "S-3", "", [{"sku": "X24F241S", "adet": 4}])
        return [sdb.sil_satis(1), sdb.sil_siparis("S-2"), sdb.sil_satis(999)]
    eski, yeni = ortam(senaryo)
    _ayni(eski, yeni)


def test_toplu_siparis_silme(ortam):
    def senaryo():
        for i, sku in enumerate(["X24F241S", "ABC", "X24F241S", "METIN"]):
            sdb.ekle_siparis("2026-10-14", "VATAN", f"F-{i % 2}", "", [{"sku": sku, "adet": i + 1}])
        return sdb.sil_siparisler(["F-0", "F-1", "F-YOK"])
    eski, yeni = ortam(senaryo, sirasiz_defter=True)
    _ayni(eski, yeni)


def test_satis_duzenleme(ortam):
    def senaryo():
        sdb.ekle_siparis("2026-10-14", "VATAN", "S-1", "", [{"sku": "X24F241S", "adet": 2},
                                                            {"sku": "ABC", "adet": 1}])
        return [sdb.guncelle_satis(1, {"adet": 5}),
                sdb.guncelle_satis(2, {"sku": " x24f200 ", "adet": 2}),
                sdb.guncelle_satis(1, {"notlar": "yalnız not"}),
                sdb.guncelle_satis(1, {"adet": 5}),               # değişmedi → stok hareketi yok
                sdb.guncelle_satis(77, {"adet": 1})]              # olmayan satır
    eski, yeni = ortam(senaryo)
    _ayni(eski, yeni)


def test_iade_ekle_sil_ve_toplu_iade(ortam):
    def senaryo():
        out = [sdb.ekle_iade("2026-10-10", "VATAN", "X24F241S", "M", 2, iade_net=50, depo="İADE DEPO"),
               sdb.ekle_iade("2026-10-10", "VATAN", "Fazeon X24F200", "M", 1, depo=None),
               sdb.ekle_iade("2026-10-10", "VATAN", "ABC", "K", 1, depo="MERKEZ DEPO", stok_isle=False)]
        out.append(sdb.sil_iade(1))
        out.append(sdb.ice_aktar_iadeler([{"sku": "X24F241S", "kanal": "HB", "iade_adet": 3, "depo": "outlet"},
                                          {"sku": "MIO MIVUE J30", "kanal": "HB", "iade_adet": 1},
                                          {"sku": "", "iade_adet": 1}], "2026-09-30", donem_bas="2026-09-01"))
        out.append(sdb.ice_aktar_iadeler([{"sku": "ABC", "kanal": "HB", "iade_adet": 2}], "2026-09-30",
                                         temizle_once=True, donem_bas="2026-09-01", varsayilan_depo="HAPPY LIFE"))
        return [o[:2] if isinstance(o, tuple) else o for o in out]
    eski, yeni = ortam(senaryo)
    _ayni(eski, yeni)


def test_depo_sevk(ortam):
    def senaryo():
        return [pmdb.depo_sevk("X24F241S", "MERKEZ DEPO", "happy life", 4, "ali", "2026-10-14", "B-1"),
                pmdb.depo_sevk("abc", "merkez", "ASEL", 2, "ali"),             # yazım farkı + 'Merkez' anahtarı
                pmdb.depo_sevk("X24F200", "MERKEZ DEPO", "HAPPY LIFE", 9),      # yetersiz stok
                pmdb.depo_sevk("X24F200", "MERKEZ DEPO", "merkez", 1),          # aynı depo
                pmdb.depo_sevk("X24F200", "MERKEZ DEPO", "HAPPY LIFE", 0),      # adet 0
                pmdb.depo_sevk("YOK", "MERKEZ DEPO", "HAPPY LIFE", 1),          # ürün yok
                pmdb.depo_sevk("METIN", "MERKEZ DEPO", "OUTLET", 6)]            # metin değer
    eski, yeni = ortam(senaryo)
    _ayni(eski, yeni)
    assert yeni["donus"][2] == (False, "❌ Yetersiz stok: 'MERKEZ DEPO' deposunda 3 adet var, 9 taşınamaz.")


def test_excel_satis_aktarimi_akilli_dusum_ve_yukleme_kodu(ortam, monkeypatch):
    monkeypatch.setattr(sdb, "get_pacal_map", lambda: {"X24F241S": 60.0})

    def senaryo():
        with SD.yukleme("YK-1"):
            return sdb.ice_aktar_satislar(
                [{"tarih": "2026-10-01", "kanal": "VATAN", "siparis_no": "E-1", "sku": "X24F241S", "adet": 12},
                 {"tarih": "2026-10-01", "kanal": "VATAN", "siparis_no": "E-1", "sku": "ABC", "adet": 2,
                  "depo": "ASEL DEPO"},
                 {"tarih": "2026-10-01", "kanal": "VATAN", "siparis_no": "E-2", "sku": "YOK-SKU", "adet": 1}],
                atla_mevcut=False)
    eski, yeni = ortam(senaryo)
    _ayni(eski, yeni)
    assert {r[-1] for r in yeni["durum"]["defter"]} == {"YK-1"}


# ═══════════════════════════════════════════════════════════════════
# 3) Atomiklik ve eşzamanlılık
# ═══════════════════════════════════════════════════════════════════
def _kirilim(dsn, sku):
    with psycopg.connect(dsn, autocommit=True) as c:
        r = c.execute("SELECT depo_kirilim, bizim_stok FROM urunler WHERE sku = %s", [sku]).fetchone()
    return r[0], r[1]


def test_eski_yolda_kayip_guncelleme_olur_kanit(veritabanlari, monkeypatch):
    """Bugünkü yol: iki satış aynı anda okursa biri diğerini ezer (hatanın kendisi — kanıt)."""
    dsn = veritabanlari["eski"]
    _sifirla(dsn)
    bariyer = threading.Barrier(2, timeout=10)

    def araya(q):                               # ikisi de kartı okuduktan SONRA yazsın
        if q.lstrip().startswith("SELECT coalesce") and "FROM urunler" in q and "depo_kirilim" in q:
            bariyer.wait()
    cli = PgIstemci(dsn, araya=araya)
    monkeypatch.setattr(pmdb, "get_client", lambda: cli)
    monkeypatch.setattr(pmdb, "_cache_temizle", lambda: None)
    monkeypatch.setattr(SD, "_gonder", lambda s: None)
    _atomik_sifirla()
    eski_yol = getattr(pmdb, "_stok_hareket_coklu_eski", pmdb.stok_hareket_coklu)
    t = [threading.Thread(target=eski_yol, args=({"X24F241S": -1}, "MERKEZ DEPO")) for _ in range(2)]
    [x.start() for x in t]
    [x.join() for x in t]
    dk, _ = _kirilim(dsn, "X24F241S")
    assert dk["MERKEZ DEPO"] == 9.0, "iki düşümden biri kayboldu (10 − 2 = 8 olmalıydı)"


def test_atomik_yolda_eszamanli_satislar_kaybolmaz(veritabanlari, monkeypatch):
    dsn = veritabanlari["yeni"]
    _sifirla(dsn)
    cli = PgIstemci(dsn)
    monkeypatch.setattr(pmdb, "get_client", lambda: cli)
    monkeypatch.setattr(sdb, "_get_client", lambda: cli)
    monkeypatch.setattr(pmdb, "_cache_temizle", lambda: None)
    monkeypatch.setattr(pmdb, "get_urun_marka_kategori", lambda: {})
    monkeypatch.setattr(sdb, "_marj_uyarisi_gonder", lambda *a, **k: None)
    monkeypatch.setattr(sdb, "_temizle", lambda: None)
    monkeypatch.setattr(AU, "log_yaz", lambda *a, **k: None)
    _atomik_sifirla()
    N = 24
    hatalar = []

    def is_(i):
        try:
            if i % 3 == 0:
                ok, msg, _ = sdb.ekle_siparis("2026-10-14", "VATAN", f"P-{i}", "",
                                              [{"sku": "X24F241S", "adet": 1, "depo": "MERKEZ DEPO"},
                                               {"sku": "ABC", "adet": 1, "depo": "MERKEZ DEPO"}])
                assert ok, msg
            elif i % 3 == 1:
                assert pmdb.stok_hareket_coklu({"ABC": -1, "X24F241S": -1}, "MERKEZ DEPO") == (2, [])
            else:
                ok, msg = pmdb.depo_sevk("X24F241S", "HAPPY LIFE", "MERKEZ DEPO", 1) \
                    if i < 10 else (True, "")
                assert ok, msg
        except Exception as e:  # noqa: BLE001
            hatalar.append(repr(e))
    t = [threading.Thread(target=is_, args=(i,)) for i in range(N)]
    [x.start() for x in t]
    [x.join() for x in t]
    assert not hatalar, hatalar
    dk, bs = _kirilim(dsn, "X24F241S")
    satis_sayisi = len([i for i in range(N) if i % 3 in (0, 1)])            # 16 düşüm
    sevk = len([i for i in range(N) if i % 3 == 2 and i < 10])              # 3 sevk (HAPPY → MERKEZ)
    assert dk["MERKEZ DEPO"] == 10 - satis_sayisi + sevk
    assert dk["HAPPY LIFE"] == 4 - sevk
    assert bs == dk["MERKEZ DEPO"] + dk["HAPPY LIFE"]
    with psycopg.connect(dsn, autocommit=True) as c:
        n = c.execute("SELECT count(*) FROM stok_hareketleri WHERE sku = 'X24F241S'").fetchone()[0]
        assert n == satis_sayisi + 2 * sevk
        assert c.execute("SELECT count(*) FROM satislar").fetchone()[0] == 2 * len(range(0, N, 3))


def test_stok_adimi_hata_verirse_satis_da_yazilmaz(veritabanlari, monkeypatch):
    """Satış + stok tek işlem: stok adımı veritabanında patlarsa satış satırı da yazılmaz ve kullanıcı açık
    hata görür (bugünkü yolda satış yazılı, stok düşülmemiş kalırdı)."""
    dsn = veritabanlari["yeni"]
    _sifirla(dsn)
    with psycopg.connect(dsn, autocommit=True) as c:      # bozuk kırılım değeri → stok adımı hata verir
        c.execute("""UPDATE urunler SET depo_kirilim = '{"MERKEZ DEPO": "bozuk"}' WHERE sku = 'ABC'""")
    cli = PgIstemci(dsn)
    monkeypatch.setattr(pmdb, "get_client", lambda: cli)
    monkeypatch.setattr(sdb, "_get_client", lambda: cli)
    monkeypatch.setattr(pmdb, "get_urun_marka_kategori", lambda: {})
    monkeypatch.setattr(pmdb, "_cache_temizle", lambda: None)
    monkeypatch.setattr(sdb, "_temizle", lambda: None)
    monkeypatch.setattr(HL, "kaydet", lambda *a, **k: True)
    _atomik_sifirla()
    ok, msg, n = sdb.ekle_siparis("2026-10-14", "VATAN", "S-1", "", [{"sku": "X24F241S", "adet": 1},
                                                                     {"sku": "ABC", "adet": 1}])
    assert (ok, n) == (False, 0) and "kaydedilmedi" in msg
    with psycopg.connect(dsn, autocommit=True) as c:
        assert c.execute("SELECT count(*) FROM satislar").fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM stok_hareketleri").fetchone()[0] == 0
    assert _kirilim(dsn, "X24F241S")[0]["MERKEZ DEPO"] == 10          # ilk kalem de geri alındı
