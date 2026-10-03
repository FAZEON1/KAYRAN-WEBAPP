# -*- coding: utf-8 -*-
"""SKU yazım farkı — YAZMA tarafı (Ekim 2026, kayıtlı veri temizliği işi).

Sorunlar (canlı veride bulundu):
  - İade kaydı SKU'yu normalleştirmiyordu: 'Fazeon X24F200' olduğu gibi yazıldı (98 satır).
  - Stok hareketi kartı birebir ya da tamamı BÜYÜK harf SKU ile arıyordu: 'MIO MIVUE J30'
    satışı 'Mio MiVue J30' kartını, 'Fazeon X24F200' iadesi 'X24F200' kartını bulamazdı.
  - Stok kartı satış/iade listesi yazım farklı satırları yalnız hiç birebir eşleşme yoksa
    arıyordu: Mio MiVue J30'da 27 satışın 22'si görünüyordu.
"""
import kayranpm.database as pmdb

KARTLAR = {"X24F200": {}, "Mio MiVue J30": {}, "FAZE3": {}}


def _kartlar(monkeypatch):
    monkeypatch.setattr(pmdb, "get_urun_marka_kategori", lambda: KARTLAR)


# ── Kart yazımı çözümü ──────────────────────────────────────────────
def test_kart_sku_coz(monkeypatch):
    _kartlar(monkeypatch)
    assert pmdb.kart_sku_coz("Fazeon X24F200") == "X24F200"
    assert pmdb.kart_sku_coz("MIO MIVUE J30") == "Mio MiVue J30"
    assert pmdb.kart_sku_coz("Faze3") == "FAZE3"
    assert pmdb.kart_sku_coz(" yeni-kod ") == "YENI-KOD"          # kart yok → sku_anahtar


def test_ayni_anahtarli_iki_kart_varsa_secmez(monkeypatch):
    monkeypatch.setattr(pmdb, "get_urun_marka_kategori", lambda: {"AB1": {}, "ab1": {}})
    assert pmdb.kart_sku_coz("Ab1") == "AB1"                       # sku_anahtar; kart seçilmez
    assert "AB1" not in pmdb.kart_sku_haritasi()


# ── İade yazımı ─────────────────────────────────────────────────────
class _Yaz:
    def __init__(self):
        self.yazilan = []

    def table(self, ad):
        return self

    def insert(self, kayit):
        self.yazilan.extend(kayit if isinstance(kayit, list) else [kayit])
        return self

    def execute(self):
        return type("R", (), {"data": []})()


def _iade_ortami(monkeypatch):
    import satis.database as sdb
    _kartlar(monkeypatch)
    db, stok = _Yaz(), []
    monkeypatch.setattr(sdb, "_get_client", lambda: db)
    monkeypatch.setattr(sdb, "_temizle", lambda: None)
    monkeypatch.setattr(sdb, "_stok_uygula_depolu", lambda m, yon=-1: stok.extend(m))
    return sdb, db, stok


def test_tek_iade_kart_yazimiyla_kaydedilir(monkeypatch):
    sdb, db, stok = _iade_ortami(monkeypatch)
    ok, _ = sdb.ekle_iade("2026-10-01", "VATAN", "Fazeon X24F200", "Monitör", 1)
    assert ok
    assert db.yazilan[0]["sku"] == "X24F200"
    assert stok == [("X24F200", 1, "MERKEZ DEPO")]


def test_excel_iadeleri_kart_yazimiyla_kaydedilir(monkeypatch):
    sdb, db, stok = _iade_ortami(monkeypatch)
    r = sdb.ice_aktar_iadeler([{"sku": "Fazeon X24F200", "iade_adet": 2},
                               {"sku": "MIO MIVUE J30", "iade_adet": 1}], "2026-10-01")
    assert r["eklendi"] == 2
    assert [x["sku"] for x in db.yazilan] == ["X24F200", "Mio MiVue J30"]
    assert [x[0] for x in stok] == ["X24F200", "Mio MiVue J30"]


# ── Stok hareketi kartı yazım farkından bağımsız bulur ──────────────
class _UrunDB:
    def __init__(self, urunler):
        self.urunler = urunler

    def table(self, ad):
        return _UrunQ(self)


class _UrunQ:
    def __init__(self, db):
        self.db, self._sku, self._upd = db, None, None

    def select(self, *a, **k):
        return self

    def eq(self, kol, deger):
        self._sku = deger
        return self

    def update(self, p):
        self._upd = p
        return self

    def insert(self, p):
        raise AssertionError(f"sahte kart açılmamalı: {p.get('sku')}")

    def execute(self):
        if self._upd is not None:
            self.db.urunler[self._sku] = dict(self._upd["depo_kirilim"])
            return type("R", (), {"data": []})()
        d = self.db.urunler.get(self._sku)
        return type("R", (), {"data": [{"sku": self._sku, "depo_kirilim": dict(d)}] if d is not None else []})()


def test_stok_hareketi_mio_buyuk_harf_ve_onekli_kodu_karta_isler(monkeypatch):
    import shared.stok_defteri as SD
    _kartlar(monkeypatch)
    monkeypatch.setattr(SD, "_gonder", lambda s: None)
    monkeypatch.setattr(pmdb, "_cache_temizle", lambda: None)
    db = _UrunDB({"Mio MiVue J30": {"MERKEZ DEPO": 10}, "X24F200": {"MERKEZ DEPO": 5}})
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    u, atl = pmdb.stok_hareket_coklu({"MIO MIVUE J30": -2, "Fazeon X24F200": 1}, "MERKEZ DEPO",
                                     kart_ac=True)
    assert (u, atl) == (2, [])
    assert db.urunler["Mio MiVue J30"]["MERKEZ DEPO"] == 8
    assert db.urunler["X24F200"]["MERKEZ DEPO"] == 6


# ── Stok kartı satış/iade listesi ───────────────────────────────────
def test_stok_karti_satis_ve_iade_listesi_yazimdan_bagimsiz():
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "kayranpm" / "stok_karti.py").read_text(encoding="utf-8")
    assert 'sku_satirlari("satislar", sku' in src and 'sku_satirlari("iadeler", sku' in src
    assert '_sel("satislar"' not in src and '_sel("iadeler"' not in src


def test_sku_satirlari_tum_yazimlari_getirir(monkeypatch):
    import re

    class _Q:
        def __init__(self, rows):
            self.rows = rows

        def select(self, *a, **k):
            return self

        def ilike(self, kol, desen):
            rx = "^" + re.escape(desen).replace("%", ".*") + "$"
            self.rows = [r for r in self.rows if re.match(rx, r[kol], re.I)]
            return self

        def order(self, kol, desc=False):
            self.rows = sorted(self.rows, key=lambda r: r[kol], reverse=desc)
            return self

        def execute(self):
            return type("R", (), {"data": self.rows})()

    rows = [{"sku": "Mio MiVue J30", "tarih": "2026-09-01"}, {"sku": "MIO MIVUE J30", "tarih": "2026-05-01"},
            {"sku": "MIO MIVUE J300", "tarih": "2026-06-01"}]
    monkeypatch.setattr(pmdb, "get_client", lambda: type("C", (), {"table": lambda s, t: _Q(list(rows))})())
    out = pmdb.sku_satirlari("satislar", "Mio MiVue J30", order="tarih", desc=True)
    assert [r["tarih"] for r in out] == ["2026-09-01", "2026-05-01"]


def test_temizlik_araci_iadeleri_kapsar():
    assert "iadeler" in pmdb._SKU_TABLOLARI and "depo_manuel_takip" in pmdb._SKU_TABLOLARI


# ── Satış / İade / Net ürün özeti tek satırda birleşir ──────────────
def test_iade_satis_net_ozet_yazim_farkini_birlestirir(monkeypatch):
    """Eskiden ham SKU ile gruplanıyordu: 'X24F200' satışları ile 'Fazeon X24F200' iadeleri
    iki ayrı satırdı; ürünün net adedi/kârı bölünüyordu. Toplamlar değişmez."""
    import satis.database as sdb
    monkeypatch.setattr(sdb, "get_pacal_map", lambda: {"X24F200": 100.0})
    monkeypatch.setattr(sdb, "get_satislar_yalin", lambda b, e: [{"sku": "X24F200", "urun_adi": "Monitör"}])
    monkeypatch.setattr(sdb, "satir_kar", lambda s: {"adet": 5, "ciro": 1000.0, "net_kar": 200.0})
    monkeypatch.setattr(sdb, "get_iadeler", lambda b=None, e=None: [
        {"sku": "Fazeon X24F200", "iade_adet": 1, "iade_net": 200.0}])
    satirlar, toplam = sdb.iade_satis_net_ozet.__wrapped__("2026-01-01", "2026-12-31") \
        if hasattr(sdb.iade_satis_net_ozet, "__wrapped__") else sdb.iade_satis_net_ozet("2026-01-01", "2026-12-31")
    assert len(satirlar) == 1
    r = satirlar[0]
    assert (r["sku"], r["s_adet"], r["i_adet"], r["net_adet"]) == ("X24F200", 5, 1, 4)
    assert r["net_kar"] == 200.0 - (200.0 - 100.0)
    assert toplam["net_adet"] == 4
