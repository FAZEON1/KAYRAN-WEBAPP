# -*- coding: utf-8 -*-
"""
Stok hareket defteri + hata kaydı — shared/stok_defteri.py, shared/hata_log.py

Kritik güvenceler:
  1) Başarılı her stok hareketi deftere önce/sonra değerleriyle yazılır.
  2) BAŞARISIZ her deneme de yazılır — nedeniyle (F4PE650BBM dersi).
  3) Defter/hata kaydı ASLA stok işlemini bozmaz.
  4) Satış akıllı düşümünde kısmi uygulama sonrası ÇİFT DÜŞÜM olmaz.
"""
import threading

import pytest

import kayranpm.database as pmdb
import shared.hata_log as HL
import shared.stok_defteri as SD


# ── Sahte Supabase: urunler tablosu (sku → depo_kirilim) ──────────────
class _Resp:
    def __init__(self, data):
        self.data = data


class _DB:
    def __init__(self, urunler, update_patlat=False):
        self.urunler = urunler            # {sku: {depo: adet}}
        self.update_patlat = update_patlat

    def table(self, ad):
        return _Q(self)


class _Q:
    def __init__(self, db):
        self.db, self._sku, self._upd, self._ins = db, None, None, None

    def select(self, *a, **k):
        return self

    def eq(self, kolon, deger):
        if kolon == "sku":
            self._sku = deger
        return self

    def update(self, payload):
        self._upd = payload
        return self

    def insert(self, payload):
        self._ins = payload
        return self

    def execute(self):
        if self._upd is not None:
            if self.db.update_patlat:
                raise RuntimeError("sahte update hatası")
            self.db.urunler[self._sku] = dict(self._upd["depo_kirilim"])
            return _Resp([])
        if self._ins is not None:
            self.db.urunler[self._ins["sku"]] = dict(self._ins.get("depo_kirilim") or {})
            return _Resp([self._ins])
        if self._sku in self.db.urunler:
            return _Resp([{"sku": self._sku, "depo_kirilim": dict(self.db.urunler[self._sku])}])
        return _Resp([])


@pytest.fixture
def defter(monkeypatch):
    """Deftere gidecek satırları yakala (veritabanına yazmadan)."""
    yazilan = []
    monkeypatch.setattr(SD, "_gonder", lambda satirlar: yazilan.extend(satirlar))
    monkeypatch.setattr(pmdb, "_cache_temizle", lambda: None)
    return yazilan


@pytest.fixture
def hatalar(monkeypatch):
    kayit = []
    monkeypatch.setattr(HL, "kaydet", lambda yer, hata, ayrinti="", kritik=False:
                        kayit.append((yer, str(hata), kritik)) or True)
    return kayit


# ═══════════════════════════════════════════════════════════════════════
# 1) Defter mantığı
# ═══════════════════════════════════════════════════════════════════════
def test_fark_yalniz_degisen_depolar():
    f = SD.fark({"MERKEZ DEPO": 10, "HAPPY LIFE": 5}, {"MERKEZ DEPO": 7, "HAPPY LIFE": 5, "İADE DEPO": 1})
    assert f == [("MERKEZ DEPO", 10.0, 7.0), ("İADE DEPO", 0.0, 1.0)]


def test_toplu_biriktirir_sonda_tek_seferde_yazar(monkeypatch):
    gonderimler = []
    monkeypatch.setattr(SD, "_gonder", lambda s: gonderimler.append(list(s)))
    with SD.toplu():
        SD.yaz("A", "MERKEZ DEPO", 1, 0, "cikis")
        with SD.toplu():                      # iç içe: yalnız dıştaki yazar
            SD.yaz("B", "MERKEZ DEPO", 2, 1, "cikis")
        assert gonderimler == []
    assert len(gonderimler) == 1 and [r["sku"] for r in gonderimler[0]] == ["A", "B"]


def test_toplu_disinda_aninda_yazar(monkeypatch):
    gonderimler = []
    monkeypatch.setattr(SD, "_gonder", lambda s: gonderimler.append(list(s)))
    SD.yaz("A", "MERKEZ DEPO", 1, 0, "cikis")
    assert len(gonderimler) == 1


def test_tampon_is_parcacigina_ozel(monkeypatch):
    """İki kullanıcının (iş parçacığının) kayıtları birbirine karışmamalı."""
    gonderimler = []
    monkeypatch.setattr(SD, "_gonder", lambda s: gonderimler.append(sorted(r["sku"] for r in s)))
    bariyer = threading.Barrier(2)

    def is_(sku):
        with SD.toplu():
            SD.yaz(sku, "D", 1, 0, "cikis")
            bariyer.wait()
            SD.yaz(sku + "2", "D", 1, 0, "cikis")

    t1, t2 = threading.Thread(target=is_, args=("X",)), threading.Thread(target=is_, args=("Y",))
    t1.start(); t2.start(); t1.join(); t2.join()
    assert sorted(gonderimler) == [["X", "X2"], ["Y", "Y2"]]


def test_defter_yazilamazsa_istisna_firlamaz(monkeypatch):
    def patla():
        raise RuntimeError("bağlantı yok")
    import shared.auth as A
    monkeypatch.setattr(A, "_get_supabase", patla)
    SD.yaz("A", "D", 1, 0, "cikis")            # patlamamalı
    with SD.toplu():
        SD.yaz("B", "D", 1, 0, "cikis")          # patlamamalı


def test_kaynak_bul_asil_cagirani_gosterir():
    def satis_fonksiyonu():
        return SD.kaynak_bul()
    k = satis_fonksiyonu()
    assert k.endswith(":satis_fonksiyonu") and "test_stok_defteri.py" in k


# ═══════════════════════════════════════════════════════════════════════
# 2) stok_hareket_coklu → defter
# ═══════════════════════════════════════════════════════════════════════
def test_basarili_hareket_once_sonra_ile_yazilir(monkeypatch, defter):
    db = _DB({"X24F241S": {"MERKEZ DEPO": 10}})
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    u, atl = pmdb.stok_hareket_coklu({"X24F241S": -3}, "MERKEZ DEPO", aciklama="test satış")
    assert (u, atl) == (1, [])
    assert db.urunler["X24F241S"]["MERKEZ DEPO"] == 7
    assert len(defter) == 1
    r = defter[0]
    assert (r["sku"], r["depo"], r["onceki"], r["sonraki"], r["degisim"], r["tur"]) == \
           ("X24F241S", "MERKEZ DEPO", 10, 7, -3, "cikis")
    assert r["basarili"] is True and r["aciklama"] == "test satış"


def test_kart_yoksa_basarisiz_ve_nedeni_yazilir(monkeypatch, defter, hatalar):
    """F4PE650BBM dersi: eskiden bu durum sessizce 'atlanan'a düşüyordu."""
    monkeypatch.setattr(pmdb, "get_client", lambda: _DB({}))
    u, atl = pmdb.stok_hareket_coklu({"YOK-SKU": -5}, "MERKEZ DEPO")
    assert (u, atl) == (0, ["YOK-SKU"])
    assert len(defter) == 1 and defter[0]["basarili"] is False
    assert "ürün kartı yok" in defter[0]["hata"]


def test_update_patlarsa_neden_yazilir_ve_kritik_hata(monkeypatch, defter, hatalar):
    monkeypatch.setattr(pmdb, "get_client", lambda: _DB({"A": {"MERKEZ DEPO": 5}}, update_patlat=True))
    u, atl = pmdb.stok_hareket_coklu({"A": -1}, "MERKEZ DEPO")
    assert atl == ["A"]
    assert defter[0]["basarili"] is False and "sahte update hatası" in defter[0]["hata"]
    assert hatalar and hatalar[0][0] == "kayranpm.stok_hareket_coklu" and hatalar[0][2] is True


def test_defter_modulu_yuklenemese_bile_stok_islenir(monkeypatch):
    monkeypatch.setattr(pmdb, "_defter", lambda: pmdb._DefterYok)
    monkeypatch.setattr(pmdb, "_cache_temizle", lambda: None)
    db = _DB({"A": {"MERKEZ DEPO": 5}})
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    assert pmdb.stok_hareket_coklu({"A": -2}, "MERKEZ DEPO") == (1, [])
    assert db.urunler["A"]["MERKEZ DEPO"] == 3


def test_coklu_hareket_tek_seferde_yazilir(monkeypatch):
    gonderimler = []
    monkeypatch.setattr(SD, "_gonder", lambda s: gonderimler.append(list(s)))
    monkeypatch.setattr(pmdb, "_cache_temizle", lambda: None)
    monkeypatch.setattr(pmdb, "get_client", lambda: _DB({"A": {"MERKEZ DEPO": 5}, "B": {"MERKEZ DEPO": 5}}))
    pmdb.stok_hareket_coklu({"A": -1, "B": -1, "C": -1}, "MERKEZ DEPO")
    assert len(gonderimler) == 1 and len(gonderimler[0]) == 3       # 2 başarılı + 1 başarısız


# ═══════════════════════════════════════════════════════════════════════
# 3) Hata kaydı
# ═══════════════════════════════════════════════════════════════════════
def test_hata_kaydi_tekrari_bastirir(monkeypatch):
    yazilan = []

    class _T:
        def table(self, ad):
            return self

        def insert(self, p):
            yazilan.append(p)
            return self

        def execute(self):
            return None
    import shared.auth as A
    monkeypatch.setattr(A, "_get_supabase", lambda: _T())
    HL._son_gorulme.clear()
    assert HL.kaydet("x.y", RuntimeError("aynı")) is True
    assert HL.kaydet("x.y", RuntimeError("aynı")) is False          # 5 dk içinde tekrar
    assert HL.kaydet("x.y", RuntimeError("farklı")) is True
    assert len(yazilan) == 2 and yazilan[0]["tur"] == "RuntimeError"


def test_hata_kaydi_asla_patlamaz(monkeypatch):
    import shared.auth as A
    monkeypatch.setattr(A, "_get_supabase", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    HL._son_gorulme.clear()
    HL.kaydet("x", ValueError("y"), kritik=True)          # istisna fırlatmamalı


# ═══════════════════════════════════════════════════════════════════════
# 4) Satış akıllı düşüm — çift düşüm koruması
# ═══════════════════════════════════════════════════════════════════════
def test_kismi_uygulamada_yedek_yol_calismaz(monkeypatch, hatalar):
    import satis.database as sdb
    db = _DB({"A": {"MERKEZ DEPO": 2, "HAPPY LIFE": 10}})
    monkeypatch.setattr(pmdb, "get_client", lambda: db)
    cagri = []

    def sahte_hareket(h, depo=None, **k):
        cagri.append(depo)
        if len(cagri) == 2:                               # ikinci depoda patla
            raise RuntimeError("ara hata")
        return len(h), []
    monkeypatch.setattr(pmdb, "stok_hareket_coklu", sahte_hareket)
    yedek = []
    monkeypatch.setattr(sdb, "_stok_uygula", lambda *a, **k: yedek.append(a))

    sdb._stok_akilli_dus({"A": 5})                        # 2 merkezden + 3 Happy Life
    assert len(cagri) == 2
    assert yedek == [], "KISMİ uygulamadan sonra yedek yol çalıştı → ÇİFT DÜŞÜM"
    assert hatalar and hatalar[0][2] is True             # kritik olarak kaydedildi


def test_planlama_hatasinda_yedek_yol_calisir(monkeypatch, hatalar):
    import satis.database as sdb
    monkeypatch.setattr(pmdb, "get_client", lambda: (_ for _ in ()).throw(RuntimeError("bağlantı")))
    yedek = []
    monkeypatch.setattr(sdb, "_stok_uygula", lambda *a, **k: yedek.append(a))
    sdb._stok_akilli_dus({"A": 5})
    assert len(yedek) == 1                                # hiçbir şey düşülmemişti → yedek güvenli
