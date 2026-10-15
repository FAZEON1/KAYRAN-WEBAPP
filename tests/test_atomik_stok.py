# -*- coding: utf-8 -*-
"""Atomik stok yazımı — uygulama tarafı (veritabani/29_atomik_stok.sql). Veritabanı YOK, sahte istemci.

Güvenceler:
  1) SQL kurulu DEĞİLKEN (PGRST202 / 404 / "Could not find the function") bugünkü yol çalışır, sonuç
     rpc'siz istemciyle birebir aynı; 'yok' bilgisi önbelleğe alınır (her yazımda boşuna denenmez).
  2) SQL kuruluyken doğru fonksiyon doğru yükle çağrılır ve tablo yazımı YAPILMAZ (her şey tek işlemde).
  3) Fonksiyon hata verirse (iş kuralı / veritabanı hatası) satış/iade YAZILMAZ, kullanıcı açık hata görür;
     eski yola düşülmez (çift yazım yok).
  4) Eski yolda stok adımı yine satışı bozmaz ama sorun artık görünür (hata kaydı + mesaj eki).
Gerçek Postgres'te eşdeğerlik ve eşzamanlılık: tests/test_atomik_pg.py.
"""
import json

import pytest

import kayranpm.database as pmdb
import satis.database as sdb
import shared.audit as AU
import shared.hata_log as HL
import shared.stok_defteri as SD


class ApiHata(Exception):
    """postgrest.APIError benzeri: .code / .message."""

    def __init__(self, code, message):
        super().__init__(str({"code": code, "message": message}))
        self.code, self.message = code, message


class _Yanit:
    def __init__(self, data):
        self.data = data


class SahteDB:
    """urunler + satislar + iadeler bellekte; rpc davranışı dışarıdan verilir (None → rpc yok)."""

    def __init__(self, urunler=None, satislar=None, iadeler=None, rpc=None):
        self.t = {"urunler": urunler or [], "satislar": satislar or [], "iadeler": iadeler or []}
        self.yazimlar = []          # (tablo, islem, yük)
        self.rpc_cagrilari = []     # (ad, params)
        if rpc is not None:
            def _rpc(ad, params):
                self.rpc_cagrilari.append((ad, json.loads(json.dumps(params))))
                return _RpcSorgu(lambda: rpc(ad, params))
            self.rpc = _rpc

    def table(self, ad):
        return _Sorgu(self, ad)


class _RpcSorgu:
    def __init__(self, f):
        self.f = f

    def execute(self):
        return _Yanit(self.f())


class _Sorgu:
    def __init__(self, db, ad):
        self.db, self.ad, self.f, self.islem, self.yuk = db, ad, [], "select", None

    def select(self, *a, **k):
        return self

    def eq(self, k, v):
        self.f.append((k, [v]))
        return self

    def in_(self, k, v):
        self.f.append((k, list(v)))
        return self

    def order(self, *a, **k):
        return self

    def insert(self, yuk):
        self.islem, self.yuk = "insert", yuk
        return self

    def update(self, yuk):
        self.islem, self.yuk = "update", yuk
        return self

    def delete(self):
        self.islem = "delete"
        return self

    def _uyan(self):
        return [r for r in self.db.t.setdefault(self.ad, [])
                if all(str(r.get(k)) in [str(x) for x in v] for k, v in self.f)]

    def execute(self):
        if self.islem == "select":
            return _Yanit([dict(r) for r in self._uyan()])
        self.db.yazimlar.append((self.ad, self.islem, self.yuk))
        if self.islem == "insert":
            satir = self.yuk if isinstance(self.yuk, list) else [self.yuk]
            for i, r in enumerate(satir):
                self.db.t[self.ad].append(dict(r, id=100 + len(self.db.t[self.ad]) + i))
            return _Yanit(satir)
        if self.islem == "update":
            for r in self._uyan():
                r.update(json.loads(json.dumps(self.yuk)))
            return _Yanit([])
        sil = self._uyan()
        self.db.t[self.ad] = [r for r in self.db.t[self.ad] if r not in sil]
        return _Yanit(sil)


URUNLER = [{"sku": "X24F241S", "depo_kirilim": {"MERKEZ DEPO": 10, "HAPPY LIFE": 4}},
           {"sku": "ABC", "depo_kirilim": {"Merkez": 7, "ASEL DEPO": 9}},
           {"sku": "Mio MiVue J30", "depo_kirilim": {"MERKEZ DEPO": 5}}]


def _atomik_sifirla():
    if hasattr(pmdb, "_ATOMIK"):
        pmdb._ATOMIK["yok_zaman"] = 0.0


@pytest.fixture(autouse=True)
def temiz(monkeypatch):
    _atomik_sifirla()
    defter, hatalar, audit = [], [], []
    monkeypatch.setattr(SD, "_gonder", lambda s: defter.extend(s))
    monkeypatch.setattr(HL, "kaydet", lambda yer, hata, ayrinti="", kritik=False:
                        hatalar.append((yer, str(hata), kritik)) or True)
    monkeypatch.setattr(AU, "log_yaz", lambda *a, **k: audit.append(a))
    monkeypatch.setattr(pmdb, "_cache_temizle", lambda: None)
    monkeypatch.setattr(pmdb, "get_today", lambda: "2026-10-14")
    monkeypatch.setattr(pmdb, "get_urun_marka_kategori",
                        lambda: {"X24F241S": {}, "ABC": {}, "Mio MiVue J30": {}})
    monkeypatch.setattr(sdb, "_temizle", lambda: None)
    monkeypatch.setattr(sdb, "_marj_uyarisi_gonder", lambda *a, **k: (False, "test"))
    yield {"defter": defter, "hatalar": hatalar, "audit": audit}
    _atomik_sifirla()


def _kopya(x):
    return json.loads(json.dumps(x))


def _yok(ad, params):
    raise ApiHata("PGRST202", f"Could not find the function public.{ad}(p_hareketler, p_ortam) in the schema cache")


# ═══════════════════════════════════════════════════════════════════
# 1) Fonksiyon kurulu değil → bugünkü yol, aynı sonuç
# ═══════════════════════════════════════════════════════════════════
def test_rpc_yokken_stok_hareketi_eski_yolla_birebir(monkeypatch, temiz):
    h = {"X24F241S": -3, "abc": -2, "Fazeon Mio MiVue J30": 1, "YOK": -1}
    sonuc = {}
    for tur, rpc in (("rpcsiz", None), ("pgrst202", _yok)):
        _atomik_sifirla()
        temiz["defter"].clear()
        db = SahteDB(urunler=_kopya(URUNLER), rpc=rpc)
        monkeypatch.setattr(pmdb, "get_client", lambda d=db: d)
        donus = pmdb.stok_hareket_coklu(h, "merkez")
        sonuc[tur] = (donus, _kopya(db.t["urunler"]),
                      [(r["sku"], r["depo"], r["onceki"], r["sonraki"], r["tur"], r["basarili"])
                       for r in temiz["defter"]], len(db.rpc_cagrilari))
    assert sonuc["rpcsiz"][:3] == sonuc["pgrst202"][:3]
    assert sonuc["pgrst202"][3] == 1                       # denendi, yoktu, bugünkü yola düştü
    assert sonuc["rpcsiz"][0] == (3, ["YOK"])
    assert sonuc["rpcsiz"][1][1]["depo_kirilim"] == {"Merkez": 7, "ASEL DEPO": 9, "MERKEZ DEPO": -2.0}


def test_yok_bilgisi_onbellege_alinir_ikinci_yazimda_denenmez(monkeypatch):
    db = SahteDB(urunler=_kopya(URUNLER), rpc=_yok)
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    pmdb.stok_hareket_coklu({"X24F241S": -1}, "MERKEZ DEPO")
    pmdb.stok_hareket_coklu({"X24F241S": -1}, "MERKEZ DEPO")
    assert len(db.rpc_cagrilari) == 1
    assert db.t["urunler"][0]["depo_kirilim"]["MERKEZ DEPO"] == 8.0


@pytest.mark.parametrize("hata,yok", [
    (ApiHata("PGRST202", "Could not find the function public.stok_uygula"), True),
    (ApiHata("42883", "function stok_uygula(jsonb, jsonb) does not exist"), True),
    (ApiHata("42501", "permission denied for function stok_uygula"), True),
    (Exception("{'code': 'PGRST202', 'message': 'Could not find the function public.x'}"), True),
    (Exception("404 Not Found: Could not find the function"), True),
    (ApiHata("P0001", "Yetersiz stok"), False),
    (ApiHata("23505", "duplicate key value"), False),
    (ApiHata("42501", "permission denied for table urunler"), False),
    (Exception("bağlantı koptu"), False),
])
def test_fonksiyon_yok_siniflamasi(hata, yok):
    assert pmdb._rpc_yok_mu(hata) is yok


def test_nesne_donmeyen_rpc_bizim_fonksiyon_sayilmaz(monkeypatch):
    """Sahte / yabancı istemci rpc'ye boş liste döner (sayfa testi istemcisi gibi) → bugünkü yol."""
    db = SahteDB(urunler=_kopya(URUNLER), rpc=lambda ad, p: [])
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    monkeypatch.setattr(sdb, "_get_client", lambda: db)
    r = sdb.ice_aktar_iadeler([{"sku": "ABC", "iade_adet": 2}], "2026-09-30")
    assert r == {"eklendi": 1, "atlandi": 0} and len(db.t["iadeler"]) == 1
    assert db.t["urunler"][1]["depo_kirilim"]["MERKEZ DEPO"] == 2.0


def test_rpc_yokken_satis_kaydi_bugunku_gibi(monkeypatch):
    db = SahteDB(urunler=_kopya(URUNLER), rpc=_yok)
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    monkeypatch.setattr(sdb, "_get_client", lambda: db)
    ok, msg, n = sdb.ekle_siparis("2026-10-14", "VATAN", "S-1", "", [{"sku": "X24F241S", "adet": 2,
                                                                     "depo": "HAPPY LIFE"}])
    assert (ok, n) == (True, 1) and msg == "✅ Sipariş kaydedildi — 1 kalem."
    assert db.t["satislar"][0]["sku"] == "X24F241S"
    assert db.t["urunler"][0]["depo_kirilim"] == {"MERKEZ DEPO": 10, "HAPPY LIFE": 2.0}


# ═══════════════════════════════════════════════════════════════════
# 2) Fonksiyon kurulu → doğru yük, tablo yazımı yok
# ═══════════════════════════════════════════════════════════════════
def _basarili(cevap):
    def f(ad, params):
        return cevap(ad, params) if callable(cevap) else cevap
    return f


def test_satis_kaydi_tek_cagri_dogru_yuk(monkeypatch, temiz):
    db = SahteDB(urunler=_kopya(URUNLER), rpc=_basarili(
        {"silinen": [], "eklenen": [{"id": 1}, {"id": 2}], "uygulanan": 2, "atlanan": []}))
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    monkeypatch.setattr(sdb, "_get_client", lambda: db)
    ok, msg, n = sdb.ekle_siparis("2026-10-14", "VATAN", "S-1", "not",
                                  [{"sku": " abc ", "adet": 2, "birim_satis": 10, "depo": "merkez"},
                                   {"sku": "X24F241S", "adet": 1, "depo": "happy life"},
                                   {"sku": "X24F241S", "adet": 3, "depo": "happy life"}])
    assert (ok, n, msg) == (True, 3, "✅ Sipariş kaydedildi — 3 kalem.")
    assert db.yazimlar == []                                         # tablo yazımı YOK
    (ad, p), = db.rpc_cagrilari
    assert ad == "kayit_stok_islem" and p["p_tablo"] == "satislar" and p["p_sil"] is None
    assert [r["sku"] for r in p["p_satirlar"]] == ["abc", "X24F241S", "X24F241S"]
    assert [(k["sku"], k["depo"], k["delta"]) for k in p["p_hareketler"]] == \
        [("abc", "MERKEZ DEPO", -2.0), ("X24F241S", "HAPPY LIFE", -4.0)]
    assert p["p_hareketler"][0]["adaylar"] == ["abc", "ABC"]
    assert p["p_hareketler"][0]["hata_aciklama"] == "-2 uygulanamadı"
    assert p["p_ortam"]["kaynak"] == "satis/database.py:_stok_uygula_depolu"
    assert p["p_ortam"]["bugun"] == "2026-10-14"
    assert ("ekle", "satislar", 1, "2 kayıt", "Satış") in temiz["audit"]


def test_stok_hareketi_tek_cagri_kart_yazimi_adaylari(monkeypatch):
    db = SahteDB(urunler=_kopya(URUNLER), rpc=_basarili({"uygulanan": 1, "atlanan": ["YOK"]}))
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    assert pmdb.stok_hareket_coklu({"Fazeon Mio MiVue J30": -1, "YOK": 2, "": 5, "S": 0}, "Happy",
                                   kart_ac=True, kart_adlar={"YOK": "Yeni"}, aciklama="teslim") == (1, ["YOK"])
    assert db.yazimlar == []
    (ad, p), = db.rpc_cagrilari
    assert ad == "stok_uygula"
    k1, k2 = p["p_hareketler"]
    assert k1["adaylar"] == ["Fazeon Mio MiVue J30", "FAZEON MIO MIVUE J30", "Mio MiVue J30"]
    assert (k1["depo"], k1["delta"], k1["aciklama"], k1["hata_aciklama"]) == ("HAPPY LIFE", -1.0, "teslim", "teslim")
    assert (k2["kart_ac"], k2["kart_ad"]) == (True, "Yeni")
    assert p["p_ortam"]["kaynak"].endswith("test_atomik_stok.py:test_stok_hareketi_tek_cagri_kart_yazimi_adaylari")


def test_yukleme_kodu_ve_kullanici_yuke_girer(monkeypatch):
    db = SahteDB(urunler=_kopya(URUNLER), rpc=_basarili({"uygulanan": 1, "atlanan": []}))
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    monkeypatch.setattr(SD, "_kullanici", lambda: "ayse")
    with SD.yukleme("YK-9"):
        pmdb.stok_hareket_coklu({"ABC": -1}, None)
    o = db.rpc_cagrilari[0][1]["p_ortam"]
    assert (o["yukleme_kodu"], o["kullanici"]) == ("YK-9", "ayse")


def test_silme_ve_duzenleme_yukleri(monkeypatch, temiz):
    import shared.cop_kutusu as CK
    saklanan = []
    monkeypatch.setattr(CK, "sakla", lambda t, r, m="": saklanan.append((t, r, m)))
    db = SahteDB(urunler=_kopya(URUNLER),
                 satislar=[{"id": 5, "sku": "abc", "adet": 2, "siparis_no": "S-1"}],
                 rpc=_basarili({"silinen": [{"id": 5, "sku": "abc"}], "eklenen": [], "uygulanan": 1, "atlanan": [],
                                "guncellenen": 1}))
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    monkeypatch.setattr(sdb, "_get_client", lambda: db)
    import numpy as np
    assert sdb.sil_satis(np.int64(5)) is True
    assert sdb.guncelle_satis(5, {"sku": " x24f241s ", "adet": "3"}) is True
    assert sdb.sil_siparisler(["S-1", "S-1", ""]) == (1, None)
    assert db.yazimlar == []
    (a1, p1), (a2, p2), (a3, p3) = db.rpc_cagrilari
    assert a1 == "kayit_stok_islem" and p1["p_sil"] == {"kolon": "id", "degerler": [5]}
    assert p1["p_aday"] == {"abc": ["abc", "ABC"]} and p1["p_ortam"]["kaynak"] == "satis/database.py:_stok_uygula"
    assert a2 == "satis_guncelle_stok"
    assert (p2["p_id"], p2["p_stoklu"], p2["p_yeni_sku"], p2["p_yeni_adet"]) == (5, True, "x24f241s", 3)
    assert set(p2["p_aday"]) == {"abc", "x24f241s"}
    assert p3["p_sil"] == {"kolon": "siparis_no", "degerler": ["S-1"]}
    # sil_satis çöp kutusuna düşer; sil_siparisler (üzerine yaz) düşmez
    assert saklanan[0][:2] == ("satislar", [{"id": 5, "sku": "abc"}])


def test_iade_yuku_ve_depo(monkeypatch):
    db = SahteDB(urunler=_kopya(URUNLER), rpc=_basarili(
        {"silinen": [], "eklenen": [{"id": 41}], "uygulanan": 1, "atlanan": []}))
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    monkeypatch.setattr(sdb, "_get_client", lambda: db)
    ok, msg, kid = sdb.ekle_iade("2026-10-10", "VATAN", "Fazeon X24F241S", "M", 2, depo="iade", kimlik=True)
    assert (ok, kid) == (True, 41) and msg == "✅ İade kaydedildi → iade"
    (ad, p), = db.rpc_cagrilari
    assert p["p_tablo"] == "iadeler" and p["p_satirlar"][0]["sku"] == "X24F241S"
    assert [(k["sku"], k["depo"], k["delta"]) for k in p["p_hareketler"]] == [("X24F241S", "İADE DEPO", 2.0)]
    db.rpc_cagrilari.clear()
    sdb.ekle_iade("2026-10-10", "VATAN", "ABC", "K", 1, stok_isle=False)
    assert db.rpc_cagrilari[0][1]["p_hareketler"] == []


def test_toplu_iade_tek_islem_ve_yukleme_gecmisi(monkeypatch):
    db = SahteDB(urunler=_kopya(URUNLER),
                 iadeler=[{"id": 7, "tarih": "2026-09-30", "sku": "ABC", "iade_adet": 1, "donem_bit": "2026-09-30"}],
                 rpc=_basarili({"silinen": [{"id": 7, "sku": "ABC", "iade_net": 50}],
                                "eklenen": [{"id": 8}, {"id": 9}], "uygulanan": 3, "atlanan": []}))
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    monkeypatch.setattr(sdb, "_get_client", lambda: db)
    bildirilen = []

    class _Yk:
        def onceki(self, t, r):
            bildirilen.append(("onceki", t, r))

        def anahtar(self, a):
            bildirilen.append(("anahtar", a))

        def eklenen(self, t, r, beklenen=None):
            bildirilen.append(("eklenen", t, [x["id"] for x in r], beklenen))
    monkeypatch.setattr(sdb, "_aktif_yukleme", lambda: _Yk())
    r = sdb.ice_aktar_iadeler([{"sku": "X24F241S", "iade_adet": 2, "depo": "outlet"},
                               {"sku": "abc", "iade_adet": 1}], "2026-09-30", temizle_once=True)
    assert r == {"eklendi": 2, "atlandi": 0}
    assert db.yazimlar == []
    (ad, p), = db.rpc_cagrilari
    assert p["p_sil"] == {"kolon": "id", "degerler": [7]} and len(p["p_satirlar"]) == 2
    assert [(k["sku"], k["depo"], k["delta"]) for k in p["p_hareketler"]] == \
        [("X24F241S", "OUTLET DEPO", 2.0), ("ABC", "MERKEZ DEPO", 1.0)]     # iade kartın yazımıyla
    assert ("onceki", "iadeler", [{"id": 7, "sku": "ABC", "iade_net": 50}]) in bildirilen
    assert ("eklenen", "iadeler", [8, 9], 2) in bildirilen


def test_sevk_yuku(monkeypatch):
    db = SahteDB(urunler=_kopya(URUNLER), rpc=_basarili({"sku": "ABC"}))
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    monkeypatch.setattr(pmdb, "tr_now_str", lambda *a, **k: "14.10.2026 12:00")
    ok, msg = pmdb.depo_sevk("ABC", "merkez", "asel", 3, "ali", "2026-10-14", "B-1")
    assert (ok, msg) == (True, "✅ 3 adet 'ABC': merkez → asel")
    assert db.yazimlar == []
    (ad, p), = db.rpc_cagrilari
    assert ad == "depo_sevk_islem"
    assert (p["p_sku"], p["p_kaynak"], p["p_hedef"], p["p_adet"]) == ("ABC", "MERKEZ DEPO", "ASEL DEPO", 3)
    assert p["p_aciklama"] == "merkez → asel · belge B-1"
    assert p["p_log"] == {"kaynak_depo": "merkez", "hedef_depo": "asel", "adet": 3, "kullanici": "ali",
                          "tarih": "14.10.2026 12:00", "sevk_tarihi": "2026-10-14", "belge_no": "B-1"}


def test_salt_okur_hesapta_rpc_denenmez(monkeypatch):
    db = SahteDB(urunler=_kopya(URUNLER), rpc=_basarili({"uygulanan": 1, "atlanan": []}))
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    monkeypatch.setattr(AU, "salt_okur_mu", lambda: True)
    pmdb.stok_hareket_coklu({"X24F241S": -1}, "MERKEZ DEPO")
    assert db.rpc_cagrilari == []


def test_kilitlenmede_bir_kez_yeniden_dener(monkeypatch):
    sayac = []

    def rpc(ad, params):
        sayac.append(1)
        if len(sayac) == 1:
            raise ApiHata("40P01", "deadlock detected")
        return {"uygulanan": 1, "atlanan": []}
    db = SahteDB(urunler=_kopya(URUNLER), rpc=rpc)
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    assert pmdb.stok_hareket_coklu({"X24F241S": -1}, "MERKEZ DEPO") == (1, [])
    assert len(sayac) == 2


# ═══════════════════════════════════════════════════════════════════
# 3) Fonksiyon hata verirse hiçbir şey yazılmaz, açık hata
# ═══════════════════════════════════════════════════════════════════
def _patla(ad, params):
    raise ApiHata("22P02", "invalid input syntax for type double precision: \"bozuk\"")


def test_rpc_hatasinda_satis_yazilmaz_eski_yola_dusulmez(monkeypatch, temiz):
    db = SahteDB(urunler=_kopya(URUNLER), rpc=_patla)
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    monkeypatch.setattr(sdb, "_get_client", lambda: db)
    ok, msg, n = sdb.ekle_siparis("2026-10-14", "VATAN", "S-1", "", [{"sku": "ABC", "adet": 1}])
    assert (ok, n) == (False, 0)
    assert "kaydedilmedi" in msg and "bozuk" in msg
    assert db.t["satislar"] == [] and db.yazimlar == []                 # eski yola düşmedi
    assert db.t["urunler"][1]["depo_kirilim"] == {"Merkez": 7, "ASEL DEPO": 9}
    assert getattr(pmdb, "_ATOMIK", {}).get("yok_zaman") == 0.0                          # 'yok' sanılmadı


def test_rpc_hatasinda_iade_silme_duzenleme_reddedilir(monkeypatch):
    db = SahteDB(urunler=_kopya(URUNLER), satislar=[{"id": 5, "sku": "ABC", "adet": 1, "siparis_no": "S"}],
                 iadeler=[{"id": 6, "sku": "ABC", "iade_adet": 1}], rpc=_patla)
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    monkeypatch.setattr(sdb, "_get_client", lambda: db)
    assert sdb.ekle_iade("2026-10-10", "VATAN", "ABC", "K", 1)[0] is False
    assert sdb.sil_satis(5) is False and sdb.sil_siparis("S") is False and sdb.sil_iade(6) is False
    assert sdb.guncelle_satis(5, {"adet": 4}) is False
    assert sdb.sil_siparisler(["S"])[0] == 0
    assert "hata" in sdb.ice_aktar_iadeler([{"sku": "ABC", "iade_adet": 1}], "2026-09-30")
    assert db.yazimlar == [] and len(db.t["satislar"]) == 1 and len(db.t["iadeler"]) == 1


def test_rpc_hatasinda_stok_hareketi_hepsi_basarisiz_ve_gorunur(monkeypatch, temiz):
    db = SahteDB(urunler=_kopya(URUNLER), rpc=_patla)
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    assert pmdb.stok_hareket_coklu({"X24F241S": -1, "ABC": -1}, "MERKEZ DEPO") == (0, ["X24F241S", "ABC"])
    assert db.yazimlar == []
    assert [(r["sku"], r["basarili"]) for r in temiz["defter"]] == [("X24F241S", False), ("ABC", False)]
    assert "hiçbir şey yazılmadı" in temiz["defter"][0]["hata"]
    assert temiz["hatalar"] and temiz["hatalar"][0][2] is True


def test_sevk_is_kurali_hatasi_bugunku_mesajla(monkeypatch):
    def rpc(ad, params):
        raise ApiHata("P0001", "Yetersiz stok: 'MERKEZ DEPO' deposunda 3 adet var, 9 taşınamaz.")
    db = SahteDB(urunler=_kopya(URUNLER), rpc=rpc)
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    assert pmdb.depo_sevk("ABC", "MERKEZ DEPO", "ASEL", 9) == \
        (False, "❌ Yetersiz stok: 'MERKEZ DEPO' deposunda 3 adet var, 9 taşınamaz.")
    assert db.yazimlar == []


# ═══════════════════════════════════════════════════════════════════
# 4) Eski yolda stok sorunu görünür (satış yine kaydedilir — canlı uyumu)
# ═══════════════════════════════════════════════════════════════════
def test_eski_yolda_kartsiz_urun_satisi_kaydedilir_sorun_gorunur(monkeypatch, temiz):
    db = SahteDB(urunler=_kopya(URUNLER))                  # rpc yok → bugünkü yol
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    monkeypatch.setattr(sdb, "_get_client", lambda: db)
    ok, msg, n = sdb.ekle_siparis("2026-10-14", "VATAN", "S-1", "", [{"sku": "YOK-SKU", "adet": 1}])
    assert (ok, n) == (True, 1) and len(db.t["satislar"]) == 1
    assert "Stoğa işlenemeyen ürün: YOK-SKU" in msg
    assert [r["hata"] for r in temiz["defter"]] == ["ürün kartı yok — stok işlenmedi"]   # nedeni defterde


def test_eski_yolda_stok_adimi_patlarsa_satis_durur_mesajda_uyari(monkeypatch, temiz):
    db = SahteDB(urunler=_kopya(URUNLER))
    monkeypatch.setattr(sdb, "_get_client", lambda: db)

    def patla(*a, **k):
        raise RuntimeError("stok çöktü")
    monkeypatch.setattr(pmdb, "stok_hareket_gruplu", patla, raising=False)
    monkeypatch.setattr(pmdb, "stok_hareket_coklu", patla)
    ok, msg, n = sdb.ekle_siparis("2026-10-14", "VATAN", "S-1", "", [{"sku": "ABC", "adet": 1}])
    assert ok and len(db.t["satislar"]) == 1 and "Stok adımı hata verdi" in msg
    assert temiz["hatalar"][0][0] == "satis.stok_yolu"


# ═══════════════════════════════════════════════════════════════════
# 5) Excel yüklemeleri tek işlem (Ekim 2026): toplu satış + G5F stok aktarımı
# ═══════════════════════════════════════════════════════════════════
def _excel_satirlar():
    return [{"tarih": "2026-10-01", "kanal": "VATAN", "siparis_no": "E-1", "sku": "X24F241S", "adet": 12},
            {"tarih": "2026-10-01", "kanal": "VATAN", "siparis_no": "E-1", "sku": "ABC", "adet": 2,
             "depo": "asel"}]


def test_excel_satis_yuklemesi_tek_cagri(monkeypatch, temiz):
    """Üzerine yaz + satış satırları + stok düşümü TEK çağrıda; tabloya ayrıca hiçbir şey yazılmaz.
    Eski: önce silme çağrısı, sonra 200'lük satış eklemeleri, sonra depo depo stok çağrıları."""
    db = SahteDB(urunler=_kopya(URUNLER),
                 satislar=[{"id": 3, "siparis_no": "E-1", "sku": "X24F241S", "adet": 2}],
                 rpc=_basarili({"silinen": [{"id": 3}], "eklenen": [{"id": 10}, {"id": 11}],
                                "uygulanan": 4, "atlanan": []}))
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    monkeypatch.setattr(sdb, "_get_client", lambda: db)
    monkeypatch.setattr(sdb, "get_pacal_map", lambda: {})
    r = sdb.ice_aktar_satislar(_excel_satirlar(), temizle_once=True)
    assert db.yazimlar == [], "Excel satış yüklemesi tek işlemde değil (tabloya ayrı yazım var)"
    assert [ad for ad, _ in db.rpc_cagrilari] == ["kayit_stok_islem"], "tek çağrı değil"
    p = db.rpc_cagrilari[0][1]
    assert p["p_sil"] == {"kolon": "siparis_no", "degerler": ["E-1"]} and len(p["p_satirlar"]) == 2
    # silinen 2 adet merkeze dönecek → merkez 12 görünür: 12'nin tamamı merkezden; ABC seçilen depodan
    assert [(k["sku"], k["depo"], k["delta"]) for k in p["p_hareketler"]] == \
        [("ABC", "ASEL DEPO", -2.0), ("X24F241S", "MERKEZ DEPO", -12.0)]
    assert p["p_ortam"]["kaynak"] == "satis/database.py:_stok_akilli_dus"
    assert (r["eklendi"], r["silinen_fatura"], r["hatali"], r["hata"]) == (2, 1, 0, None)


def test_excel_satis_reddedilirse_hicbir_sey_yazilmaz(monkeypatch, temiz):
    db = SahteDB(urunler=_kopya(URUNLER),
                 satislar=[{"id": 3, "siparis_no": "E-1", "sku": "X24F241S", "adet": 2}], rpc=_patla)
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    monkeypatch.setattr(sdb, "_get_client", lambda: db)
    monkeypatch.setattr(sdb, "get_pacal_map", lambda: {})
    r = sdb.ice_aktar_satislar(_excel_satirlar(), atla_mevcut=False)
    assert db.yazimlar == [] and len(db.t["satislar"]) == 1, "reddedilen yükleme yarım yazıldı"
    assert r["eklendi"] == 0 and "hiçbir şey değişmedi" in (r["hata"] or "")


def test_excel_satis_fonksiyon_yoksa_bugunku_yol(monkeypatch, temiz):
    db = SahteDB(urunler=_kopya(URUNLER), rpc=_yok)
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    monkeypatch.setattr(sdb, "_get_client", lambda: db)
    monkeypatch.setattr(sdb, "get_pacal_map", lambda: {})
    r = sdb.ice_aktar_satislar(_excel_satirlar(), atla_mevcut=False)
    assert r["eklendi"] == 2 and len(db.t["satislar"]) == 2
    assert db.t["urunler"][0]["depo_kirilim"] == {"MERKEZ DEPO": 0, "HAPPY LIFE": 2.0}   # 10 merkez + 2 HL


def _g5f_excel(tmp_path):
    import pandas as pd
    yol = tmp_path / "g5f.xlsx"
    pd.DataFrame({"DEPO ADI": ["MERKEZ DEPO", "HAPPY LIFE", "MERKEZ DEPO"],
                  "STOK KODU": ["x24f241s", "x24f241s", "YENI1"], "STOK İSMİ": ["Monitör", "Monitör", "Yeni"],
                  "MİKTAR": [7, 3, 5]}).to_excel(yol, index=False)
    return str(yol)


def test_g5f_aktarim_tek_cagri(monkeypatch, temiz, tmp_path):
    """Bütün ürünler + Excel'de olmayanların sıfırlanması TEK çağrıda (g5f_stok_aktar).
    Eski: ürün ürün güncelleme + ayrı sıfırlama yazımları."""
    import kayranpm.excel_islemler as E
    db = SahteDB(urunler=_kopya(URUNLER), rpc=_basarili({"guncellenen": 1, "yeni": 1, "sifirlanan": 2}))
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    monkeypatch.setattr(E, "get_client", lambda: db)
    monkeypatch.setattr(E, "get_today", lambda: "2026-10-14")
    oz = {}
    ok, msg = E.excel_yukle_g5f_depolar(_g5f_excel(tmp_path), ozet=oz)
    assert db.yazimlar == [], "G5F aktarımı tek işlemde değil (ürün ürün yazım var)"
    assert [ad for ad, _ in db.rpc_cagrilari] == ["g5f_stok_aktar"]
    p = db.rpc_cagrilari[0][1]
    assert [(u["sku"], u["bizim_stok"], u["depo_kirilim"]) for u in p["p_urunler"]] == \
        [("X24F241S", 10, {"MERKEZ DEPO": 7, "HAPPY LIFE": 3}), ("YENI1", 5, {"MERKEZ DEPO": 5})]
    assert p["p_urunler"][1]["yeni_kart"]["ilk_giris_tarihi"] == "2026-10-14"
    assert p["p_sifirla"] == ["ABC", "Mio MiVue J30"]
    assert p["p_ortam"]["kaynak"] == "kayranpm/excel_islemler.py:excel_yukle_g5f_depolar"
    assert ok and oz["guncellenen"] == 2 and "2 ürünün eski kırılımı sıfırlandı" in msg


def test_g5f_aktarim_reddedilirse_hicbir_sey_yazilmaz(monkeypatch, temiz, tmp_path):
    import kayranpm.excel_islemler as E
    db = SahteDB(urunler=_kopya(URUNLER), rpc=_patla)
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    monkeypatch.setattr(E, "get_client", lambda: db)
    ok, msg = E.excel_yukle_g5f_depolar(_g5f_excel(tmp_path), ozet={})
    assert db.yazimlar == [], "reddedilen aktarım yarım yazıldı"
    assert not ok and "hiçbir şey değişmedi" in msg
    assert temiz["hatalar"] and temiz["hatalar"][-1][2] is True
