# -*- coding: utf-8 -*-
"""
Depo dağıtımı testleri — satis/database.py
  _stok_akilli_dus  : otomatik depo dağıtım kuralı + secili_depo davranışı
  ice_aktar_satislar: satır bazlı depo gruplaması ve id(_row) bağı

Veritabanı YOK: Supabase istemcisi ve stok_hareket_coklu sahteleniyor,
yalnız dağıtım MANTIĞI test ediliyor.

DİKKAT — monkeypatch hedefleri:
  _stok_akilli_dus fonksiyon İÇİNDE `from kayranpm.database import ...`
  yapar; bu yüzden yamalar satis.database'e değil kayranpm.database'e
  uygulanır. ice_aktar_satislar ise modül düzeyindeki adları kullanır;
  onun yamaları satis.database üzerindedir.
"""

import pytest

import kayranpm.database as pmdb
import satis.database as sdb


# ═══════════════════════════════════════════════════════════
#  Sahte Supabase — yalnız kullanılan zincirler
# ═══════════════════════════════════════════════════════════

class _Resp:
    def __init__(self, data):
        self.data = data


class _Sorgu:
    """table().select().eq().execute() ve table().insert().execute() zinciri."""

    def __init__(self, veri, insert_patlat=None, insert_kayit=None):
        self._veri = veri                      # {sku: depo_kirilim}
        self._patlat = insert_patlat or (lambda satir: False)
        self._kayit = insert_kayit if insert_kayit is not None else []
        self._sku = None
        self._insert = None

    def table(self, ad):
        return self

    def select(self, *a, **kw):
        return self

    def eq(self, kolon, deger):
        if kolon == "sku":
            self._sku = deger
        return self

    def limit(self, n):
        return self

    def range(self, a, b):
        return self

    def insert(self, payload):
        s = _Sorgu(self._veri, self._patlat, self._kayit)
        s._insert = payload
        return s

    def execute(self):
        if self._insert is not None:
            satirlar = self._insert if isinstance(self._insert, list) else [self._insert]
            for satir in satirlar:
                if self._patlat(satir):
                    raise RuntimeError("sahte insert hatası: " + str(satir.get("sku")))
            self._kayit.extend(satirlar)
            return _Resp(satirlar)
        if self._sku is not None:
            dk = self._veri.get(self._sku)
            return _Resp([{"depo_kirilim": dk}] if dk is not None else [])
        return _Resp([])


@pytest.fixture
def hareket_kaydi(monkeypatch):
    """stok_hareket_coklu çağrılarını yakalar: [(hareketler, depo), ...]"""
    kayit = []

    def sahte(hareketler, depo=None, **kw):
        kayit.append((dict(hareketler), depo))
        return len(hareketler), []

    monkeypatch.setattr(pmdb, "stok_hareket_coklu", sahte)
    return kayit


def _sahte_urunler(monkeypatch, veri):
    """kayranpm.database.get_client → sahte istemci (depo_kirilim okuma)."""
    monkeypatch.setattr(pmdb, "get_client", lambda: _Sorgu(veri))


# ═══════════════════════════════════════════════════════════
#  _stok_akilli_dus — secili_depo verilince otomatik dağıtım KAPALI
# ═══════════════════════════════════════════════════════════

def test_secili_depo_otomatik_dagitimi_devre_disi_birakir(hareket_kaydi, monkeypatch):
    """Kullanıcı depo seçtiyse TAMAMI oradan düşer — stok başka depoda olsa bile."""
    # Stok tamamen MERKEZ'de; otomatik dağıtım açık olsaydı merkezden düşerdi.
    _sahte_urunler(monkeypatch, {"X1": {"MERKEZ DEPO": 100}})

    sdb._stok_akilli_dus({"X1": 5}, secili_depo="happy life")

    assert hareket_kaydi == [({"X1": -5.0}, "HAPPY LIFE")]


def test_secili_depo_kanoniklestirilir(hareket_kaydi):
    sdb._stok_akilli_dus({"X1": 3}, secili_depo="MERKEZ")
    assert hareket_kaydi[0][1] == "MERKEZ DEPO"


def test_secili_depo_sifir_ve_eksi_adet_atlanir(hareket_kaydi):
    sdb._stok_akilli_dus({"X1": 0, "X2": -2, "X3": 4}, secili_depo="MERKEZ DEPO")
    assert hareket_kaydi == [({"X3": -4.0}, "MERKEZ DEPO")]


def test_secili_depo_hic_gecerli_satir_yoksa_cagri_yapilmaz(hareket_kaydi):
    sdb._stok_akilli_dus({"X1": 0}, secili_depo="MERKEZ DEPO")
    assert hareket_kaydi == []


# ═══════════════════════════════════════════════════════════
#  _stok_akilli_dus — otomatik dağıtım kuralı
#  1) merkezden mevcut kadar  2) diğerleri çoktan aza  3) kalan merkeze eksi
# ═══════════════════════════════════════════════════════════

def _dus_toplami(kayit):
    """Yakalanan çağrıları {depo: {sku: düşülen(+)}} biçimine indirger."""
    out = {}
    for hareketler, depo in kayit:
        d = out.setdefault(depo, {})
        for sku, delta in hareketler.items():
            d[sku] = d.get(sku, 0) + (-delta)   # çağrılar eksi delta taşır
    return out


def test_otomatik_once_merkez(hareket_kaydi, monkeypatch):
    _sahte_urunler(monkeypatch, {"X1": {"MERKEZ DEPO": 10, "HAPPY LIFE": 10}})
    sdb._stok_akilli_dus({"X1": 6}, None)
    assert _dus_toplami(hareket_kaydi) == {"MERKEZ DEPO": {"X1": 6}}


def test_otomatik_merkez_yetmezse_digerleri_coktan_aza(hareket_kaydi, monkeypatch):
    _sahte_urunler(monkeypatch, {
        "X1": {"MERKEZ DEPO": 2, "HAPPY LIFE": 3, "ASEL DEPO": 8},
    })
    sdb._stok_akilli_dus({"X1": 9}, None)
    # 2 merkez + 7 ASEL (8 > 3 olduğu için önce ASEL); HAPPY'e hiç gerek kalmaz
    assert _dus_toplami(hareket_kaydi) == {
        "MERKEZ DEPO": {"X1": 2},
        "ASEL DEPO": {"X1": 7},
    }


def test_otomatik_hicbir_yerde_kalmadiysa_kalan_merkeze_eksi(hareket_kaydi, monkeypatch):
    """Satış asla engellenmez: stok yetmese de kalan merkeze yazılır (eksiye iner)."""
    _sahte_urunler(monkeypatch, {"X1": {"MERKEZ DEPO": 1, "HAPPY LIFE": 2}})
    sdb._stok_akilli_dus({"X1": 10}, None)
    assert _dus_toplami(hareket_kaydi) == {
        "MERKEZ DEPO": {"X1": 8},   # 1 mevcut + 7 kalan
        "HAPPY LIFE": {"X1": 2},
    }


def test_otomatik_urun_kartsiz_sku_merkezden_duser(hareket_kaydi, monkeypatch):
    """Kırılımı okunamayan SKU'nun tamamı merkeze yazılır (3. kural)."""
    _sahte_urunler(monkeypatch, {})     # hiçbir SKU bulunamıyor
    sdb._stok_akilli_dus({"YOK1": 4}, None)
    assert _dus_toplami(hareket_kaydi) == {"MERKEZ DEPO": {"YOK1": 4}}


def test_otomatik_toplam_dusum_istenen_adede_esit(hareket_kaydi, monkeypatch):
    """Dağıtım kuralı değişse bile değişmez: düşülen toplam = satılan adet."""
    _sahte_urunler(monkeypatch, {
        "X1": {"MERKEZ DEPO": 3, "HAPPY LIFE": 5, "ASEL DEPO": 1},
    })
    sdb._stok_akilli_dus({"X1": 7}, None)
    toplam = sum(sum(v.values()) for v in _dus_toplami(hareket_kaydi).values())
    assert toplam == 7


# ═══════════════════════════════════════════════════════════
#  ice_aktar_satislar — satır bazlı depo gruplaması + id(_row) bağı
# ═══════════════════════════════════════════════════════════

def _satir(sno, sku, adet=1, depo="", kanal="VATAN"):
    return {"tarih": "2026-08-01", "kanal": kanal, "siparis_no": sno,
            "sku": sku, "urun_adi": "Ürün " + sku, "adet": adet,
            "birim_satis": 100.0, "depo": depo}


@pytest.fixture
def aktarim_ortami(monkeypatch):
    """ice_aktar_satislar'ı DB'siz koşturur; _stok_akilli_dus çağrılarını yakalar."""
    eklenen = []          # gerçekten insert edilen satırlar
    dus_cagrilari = []    # [(hareketler, secili_depo), ...]
    ortam = {"eklenen": eklenen, "dus": dus_cagrilari,
             "patlat": lambda satir: False}

    monkeypatch.setattr(sdb, "get_pacal_map", lambda: {})
    monkeypatch.setattr(sdb, "get_mevcut_satis_anahtarlari", lambda: set())
    monkeypatch.setattr(sdb, "_temizle", lambda: None)
    monkeypatch.setattr(sdb, "_get_client",
                        lambda: _Sorgu({}, lambda r: ortam["patlat"](r), eklenen))
    monkeypatch.setattr(sdb, "_stok_akilli_dus",
                        lambda h, d=None: dus_cagrilari.append((dict(h), d)))
    return ortam


def test_aktarim_satir_bazli_depo_gruplamasi(aktarim_ortami):
    """Tek Excel'de farklı çıkış depoları: her depo kendi grubunda düşülmeli."""
    sonuc = sdb.ice_aktar_satislar([
        _satir("S1", "A1", 2, depo="MERKEZ DEPO"),
        _satir("S2", "A1", 3, depo="HAPPY LIFE"),
        _satir("S3", "B2", 1, depo="MERKEZ DEPO"),
    ])
    assert sonuc["eklendi"] == 3 and sonuc["hatali"] == 0
    assert sorted(aktarim_ortami["dus"], key=str) == sorted([
        ({"A1": 2, "B2": 1}, "MERKEZ DEPO"),
        ({"A1": 3}, "HAPPY LIFE"),
    ], key=str)


def test_aktarim_deposuz_satirlar_otomatik_dagitima_gider(aktarim_ortami):
    sdb.ice_aktar_satislar([_satir("S1", "A1", 2, depo="")])
    assert aktarim_ortami["dus"] == [({"A1": 2}, None)]


def test_aktarim_ayni_siparis_ayni_sku_farkli_depo(aktarim_ortami):
    """id(_row) bağının varlık sebebi: (sipariş_no, sku) benzersiz DEĞİL.
    Anahtarla eşleştirilseydi iki satırdan biri yanlış depoya yazılırdı."""
    sdb.ice_aktar_satislar([
        _satir("S1", "A1", 2, depo="MERKEZ DEPO"),
        _satir("S1", "A1", 5, depo="HAPPY LIFE"),   # aynı sipariş, aynı SKU!
    ], atla_mevcut=False)
    assert sorted(aktarim_ortami["dus"], key=str) == sorted([
        ({"A1": 2}, "MERKEZ DEPO"),
        ({"A1": 5}, "HAPPY LIFE"),
    ], key=str)


def test_aktarim_insert_hatasi_sirayi_kaydirmaz(aktarim_ortami):
    """id(_row) bağının ikinci varlık sebebi: insert hatası alan satır
    _ins_rows'a girmez; sıra numarasıyla eşleştirilseydi sonraki satırların
    deposu kayardı. Patlayan satırın stoğu DÜŞÜLMEMELİ, diğerlerininki
    kendi deposundan düşülmeli."""
    aktarim_ortami["patlat"] = lambda satir: satir.get("sku") == "PATLAK"

    sonuc = sdb.ice_aktar_satislar([
        _satir("S1", "A1", 2, depo="MERKEZ DEPO"),
        _satir("S2", "PATLAK", 9, depo="MERKEZ DEPO"),
        _satir("S3", "B2", 3, depo="HAPPY LIFE"),
    ])
    assert sonuc["eklendi"] == 2 and sonuc["hatali"] == 1
    assert sonuc["hata"] and "PATLAK" in sonuc["hata"]

    dusulen = {}
    for h, d in aktarim_ortami["dus"]:
        for sku, adet in h.items():
            dusulen[(d, sku)] = dusulen.get((d, sku), 0) + adet
    assert dusulen == {("MERKEZ DEPO", "A1"): 2, ("HAPPY LIFE", "B2"): 3}
    assert not any(sku == "PATLAK" for _, sku in dusulen)


def test_aktarim_sku_normalize_edilir(aktarim_ortami):
    """'Fazeon X24F165S' kaynağında 'X24F165S' olarak kaydedilmeli."""
    sdb.ice_aktar_satislar([_satir("S1", "Fazeon X24F165S", 1, depo="MERKEZ DEPO")])
    assert aktarim_ortami["eklenen"][0]["sku"] == "X24F165S"
    assert aktarim_ortami["dus"] == [({"X24F165S": 1}, "MERKEZ DEPO")]


def test_aktarim_gecersiz_satirlar_elenir(aktarim_ortami):
    """SKU'suz, 0 adetli ve tarihsiz satırlar insert'e girmemeli."""
    sonuc = sdb.ice_aktar_satislar([
        _satir("S1", "", 2, depo="MERKEZ DEPO"),           # SKU yok
        _satir("S2", "A1", 0, depo="MERKEZ DEPO"),          # adet 0
        dict(_satir("S3", "B2", 1), tarih=""),              # tarih yok
        _satir("S4", "C3", 2, depo="MERKEZ DEPO"),          # geçerli
    ])
    assert sonuc["eklendi"] == 1
    assert [r["sku"] for r in aktarim_ortami["eklenen"]] == ["C3"]


def test_aktarim_mevcut_anahtarlar_atlanir(aktarim_ortami, monkeypatch):
    """atla_mevcut: kanal|sipariş|SKU|mağaza dörtlüsü kayıtlıysa satır eklenmez.
    Notlar boş olduğunda (VATAN) anahtar sonu boş mağaza ile biter."""
    monkeypatch.setattr(sdb, "get_mevcut_satis_anahtarlari",
                        lambda: {"VATAN|S1|A1|"})
    sonuc = sdb.ice_aktar_satislar([
        _satir("S1", "A1", 2, depo="MERKEZ DEPO"),   # zaten kayıtlı
        _satir("S2", "A1", 3, depo="MERKEZ DEPO"),   # yeni
    ])
    assert sonuc["eklendi"] == 1 and sonuc["atlandi"] == 1
    assert sonuc["maliyetsiz"] == 1 and sonuc["hata"] is None
    assert len(sonuc["atlanan_detay"]) == 1
    assert sonuc["atlanan_detay"][0]["sku"] == "A1"


def test_aktarim_maliyetsiz_sayaci(aktarim_ortami, monkeypatch):
    """Paçalda bulunmayan SKU maliyetsiz sayılmalı ama yine de eklenmeli."""
    monkeypatch.setattr(sdb, "get_pacal_map", lambda: {"A1": 12.5})
    sonuc = sdb.ice_aktar_satislar([
        _satir("S1", "A1", 1, depo="MERKEZ DEPO"),
        _satir("S2", "YOK", 1, depo="MERKEZ DEPO"),
    ])
    assert sonuc["eklendi"] == 2 and sonuc["maliyetsiz"] == 1
    maliyet = {r["sku"]: r["birim_maliyet"] for r in aktarim_ortami["eklenen"]}
    assert maliyet == {"A1": 12.5, "YOK": 0.0}
