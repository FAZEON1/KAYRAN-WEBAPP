# -*- coding: utf-8 -*-
"""Depo liste masaları (Ekim 2026): Depo stok ve Bekleyen sevk takibi ortak masada (shared/masa.py).

Burada: ekrana giden veri eski ekranla aynı (liste_hazirla sırası, bekleyen_ozet rakamları ve grupları),
tarayıcıdan gelen isteğin doğrulanması (shared.masa.istek_al) ve düşüm / silmenin BUGÜNKÜ kodla (eski
"Düşümü kaydet" düğmesinin veritabanı yükü birebir) yürütülmesi."""
import sys
from datetime import date
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from depo import bekleyen_ekran as E  # noqa: E402
from depo import depo_masasi as M  # noqa: E402
from depo.yazdir import liste_hazirla  # noqa: E402
from shared import masa as MS  # noqa: E402

BUGUN = date(2026, 10, 14)


# ── Depo stok ────────────────────────────────────────────────────────
HAM = [{"sku": "FZ-SSD-512", "urun_adi": "FAZEON SSD 512", "adet": 12},
       {"sku": "AGI-RAM-16", "urun_adi": "AGI RAM 16", "adet": 1240},
       {"sku": "XS-PAD-XL", "urun_adi": "XASER PAD", "adet": 12}]


def test_stok_masasi_liste_hazirla_sirasi_ve_sayilar():
    liste = liste_hazirla(HAM, "", "adet")
    v = M.stok_masa_verisi("MERKEZ DEPO", liste, len(HAM), "")
    assert [s["sku"] for s in v["satirlar"]] == [u["sku"] for u in liste] == ["AGI-RAM-16", "FZ-SSD-512", "XS-PAD-XL"]
    assert v["satirlar"][0]["adet_m"] == "1.240" and v["satirlar"][0]["adet_m__s"] == 1240
    o = {k["k"]: k for k in v["ozet"]}
    assert o["cesit"]["dg"] == "3" and o["adet"]["dg"] == "1.264" and o["cesit"]["al"] == "MERKEZ DEPO"
    assert v["islemler"] == [] and "ara" not in v                       # arama (barkod dahil) yukarıdaki kutuda
    t, h = MS.istek_al(v, {"islem": "ac", "ids": [1]})
    assert t is None and "Bilinmeyen" in h


def test_stok_masasi_aramada_sayi_notu():
    liste = liste_hazirla(HAM, "pad", "adet")
    v = M.stok_masa_verisi("MERKEZ DEPO", liste, len(HAM), "pad")
    assert len(v["satirlar"]) == 1 and v["ozet"][0]["al"] == "3 çeşitten aramaya uyanlar"


# ── Bekleyen sevk ────────────────────────────────────────────────────
def _k(i, firma, fa, sevkler, notlar=""):
    hrk = [{"tarih": "2026-10-0%d" % (j + 1), "adet": a, "fis_no": f"KYR-2026-{i * 10 + j:05d}"}
           for j, a in enumerate(sevkler)]
    return {"id": i, "firma": firma, "sku": f"SKU-{i}", "urun_adi": f"Ürün {i}", "fatura_adet": fa,
            "sevk_edilen": sum(sevkler), "hareketler": hrk, "notlar": notlar}


MT = [_k(4, "VATAN", 100, [10]), _k(3, "MONDAY", 30, [30]), _k(2, "EERA", 50, [], "fatura 12"),
      _k(1, "ÖRNEK", 20, [5, 5])]


def test_bekleyen_masasi_sira_grup_ve_rakamlar():
    v = M.bekleyen_masa_verisi(MT, "KYR-2026-00041", BUGUN)
    r = v["satirlar"]
    assert [s["id"] for s in r] == [4, 2, 1, 3]                           # bekleyen çoktan aza, sonra bitenler
    assert [s["grup"] for s in r] == ["Sevk bekleyenler"] * 3 + ["Tamamı sevk edilenler"]
    assert r[0]["bek"] == 90 and r[0]["bek_m"] == "90 bekliyor" and r[0]["bek_alt"] == "10 / 100 sevk edildi"
    assert r[3]["bek_m"] == "tamamlandı" and r[3]["_durum"] == {"ad": "Tamamlandı", "renk": "yesil"}
    assert r[1]["alt"] == "SKU-2 · Ürün 2 · 0 sevk · fatura 12"
    assert dict(r[0]["_detay"])["Sevk edilen"] == "10 (%10)"
    o = {k["k"]: k for k in v["ozet"]}
    assert (o["kayit"]["dg"], o["fa"]["dg"], o["se"]["dg"], o["bek"]["dg"]) == ("4", "200", "50", "150")
    assert [s["k"] for s in v["secimler"][0]["secenekler"]] == ["EERA", "MONDAY", "VATAN", "ÖRNEK"]
    dus = next(i for i in v["islemler"] if i["k"] == "dus")
    assert dict((a["ad"], a) for a in dus["alanlar"])["tarih"]["varsayilan"] == "2026-10-14"
    assert "KYR-2026-00041" in dict((a["ad"], a) for a in dus["alanlar"])["fis"]["et"]


@pytest.mark.parametrize("istek, hata", [
    ({"islem": "dus", "ids": [3], "degerler": {"adet": 1, "tarih": "2026-10-14"}}, "uygun değil"),   # bitmiş kayıt
    ({"islem": "dus", "ids": [4], "degerler": {"adet": 91, "tarih": "2026-10-14"}}, "aşamaz"),      # bekleyenden çok
    ({"islem": "dus", "ids": [4], "degerler": {"adet": 0, "tarih": "2026-10-14"}}, "geçerli bir sayı"),
    ({"islem": "dus", "ids": [4], "degerler": {"adet": 5}}, "gerekli"),                             # tarih zorunlu
    ({"islem": "dus", "ids": [4, 2], "degerler": {"adet": 5, "tarih": "2026-10-14"}}, "tek kayıtla"),
    ({"islem": "sil", "ids": [4], "degerler": {}}, "gerekli"),                                      # onay zorunlu
])
def test_bekleyen_istek_reddedilir(istek, hata):
    t, h = MS.istek_al(M.bekleyen_masa_verisi(MT, "", BUGUN), istek)
    assert t is None and hata in h


@pytest.fixture
def db(monkeypatch):
    """Sahte istemci: depo_manuel_takip'e giden update / delete çağrılarını kaydeder."""
    kayit = []

    class _S:
        def __init__(self):
            self.op = None

        def table(self, ad):
            self.tablo = ad
            return self

        def update(self, yuk):
            self.op = ("update", yuk)
            return self

        def delete(self):
            self.op = ("delete", None)
            return self

        def eq(self, a, b):
            self.kosul = (a, b)
            return self

        def execute(self):
            kayit.append((self.tablo, self.op[0], self.op[1], self.kosul))

    monkeypatch.setattr(E, "_client", lambda: _S())
    return kayit


def _yurut(istek, mt=MT):
    t, h = MS.istek_al(M.bekleyen_masa_verisi(mt, "KYR-2026-00099", BUGUN), istek)
    assert h is None, h
    return M.bekleyen_uygula(t, mt, "ibrahim")


def test_sevk_dus_eski_dugmeyle_ayni_yuk(db):
    s = _yurut({"islem": "dus", "ids": [4], "degerler": {"adet": "15", "tarih": "2026-10-13", "fis": " KYR-2026-00777 ",
                                                         "belge": " FT-9 ", "eirs": "", "acik": " plaka 34 "}})
    yeni_h = {"tarih": "2026-10-13", "adet": 15, "belge_no": "FT-9", "fis_no": "KYR-2026-00777",
              "e_irsaliye_no": "", "aciklama": "plaka 34", "kullanici": "ibrahim"}
    assert db == [("depo_manuel_takip", "update",
                   {"sevk_edilen": 25, "hareketler": MT[0]["hareketler"] + [yeni_h]}, ("id", 4))]
    assert s["ok"] and s["son_fis"]["hareket"] == yeni_h and s["son_fis"]["kayit"]["sevk_edilen"] == 25
    assert s["mesaj"] == "15 adet sevk kaydedildi · fiş no KYR-2026-00777"
    assert MT[0]["sevk_edilen"] == 10                                     # kayıt kopyalandı, bellekteki satır aynı


def test_sevk_dus_fis_bossa_siradaki_numara(db):
    s = _yurut({"islem": "dus", "ids": [2], "degerler": {"adet": 5, "tarih": "2026-10-14"}})
    from depo.belge import fis_no_uret
    beklenen = fis_no_uret([h for r in MT for h in r["hareketler"]])
    assert s["son_fis"]["hareket"]["fis_no"] == beklenen                  # fis_no_uret: o yılın sıradaki numarası
    if date.today().year == 2026:
        assert beklenen == "KYR-2026-00041"                               # en büyük 00040 → 00041
    assert db[0][2]["sevk_edilen"] == 5


def test_sevk_dus_kesirli_adet_reddedilir(db):
    s = _yurut({"islem": "dus", "ids": [4], "degerler": {"adet": 2.5, "tarih": "2026-10-14"}})
    assert s["ok"] is False and db == []


def test_eski_ekran_ayni_fonksiyonu_kullanir(db):
    """Eski _detay ekranı da düşümü sevk_dus_kaydet ile yazar (refaktör: yük değişmedi)."""
    import inspect
    kaynak = inspect.getsource(E._detay)
    assert "sevk_dus_kaydet(r, adet, tarih, belge, fis, eirs, acik" in kaynak and "takip_sil(kid)" in kaynak
    snap, h = E.sevk_dus_kaydet(MT[3], 3, date(2026, 10, 1), "B", "F", "", "", "selcuk")
    assert db[0][2]["sevk_edilen"] == 13 and snap["sevk_edilen"] == 13 and h["kullanici"] == "selcuk"


def test_sil_ve_ayrinti(db):
    import streamlit as st
    s = _yurut({"islem": "sil", "ids": [2], "degerler": {"onay": True}})
    assert db == [("depo_manuel_takip", "delete", None, ("id", 2))] and s["ok"]
    s = _yurut({"islem": "ac", "ids": [3]})
    assert s == {"ok": True, "mesaj": "", "sessiz": True, "onbellek": False}
    assert st.session_state.get("_dpo_mt_secili") == 3
    st.session_state.pop("_dpo_mt_secili", None)
