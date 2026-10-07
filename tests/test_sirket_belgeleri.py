# -*- coding: utf-8 -*-
"""Yönetim › Şirket belgeleri (Ekim 2026): tür/boyut denetimi, dosya yolu, geçerlilik uyarısı,
sürümler, ZIP, künye önceliği ve yükleme hatasında dosyanın geri silinmesi."""
import io
import zipfile
from datetime import date

import pytest

from shared import sirket_belge_hesap as H


def test_belge_kabul_tur_ve_boyut():
    assert H.belge_kabul("vergi levhası.PDF", 1000) == (True, "")
    assert not H.belge_kabul("program.exe", 1000)[0]
    assert not H.belge_kabul("bos.pdf", 0)[0]
    ok, sebep = H.belge_kabul("buyuk.pdf", 21 * 1024 * 1024)
    assert not ok and "20 MB" in sebep


def test_depo_yolu_turkce_karakter_ve_benzersiz():
    from datetime import datetime
    an = datetime(2026, 10, 7, 14, 30, 5)
    assert H.depo_yolu("İmza sirküleri", "İmza Sirküleri 2026.pdf", an) == \
        "imza-sirkuleri/20261007-143005-imza-sirkuleri-2026.pdf"
    assert H.depo_yolu("Banka bilgi yazısı (IBAN)", "a.jpeg", an).startswith("banka-bilgi-yazisi-iban/")
    assert H.guvenli_ad("...") == "belge"


@pytest.mark.parametrize("bitis,durum,kalan", [
    (None, "suresiz", None), ("2026-10-06", "dolmus", -1), ("2026-10-07", "yaklasiyor", 0),
    ("2026-11-06", "yaklasiyor", 30), ("2026-11-07", "gecerli", 31)])
def test_sure_durumu(bitis, durum, kalan):
    assert H.sure_durumu(bitis, date(2026, 10, 7)) == (durum, kalan)


def _kayitlar():
    return [
        {"id": 1, "tur": "Oda faaliyet belgesi", "zaman": "2026-01-05", "belge_tarihi": "2026-01-05",
         "bitis_tarihi": "2026-07-05", "ad": "faaliyet_ocak.pdf"},
        {"id": 2, "tur": "Oda faaliyet belgesi", "zaman": "2026-09-20", "belge_tarihi": "2026-09-20",
         "bitis_tarihi": "2026-10-20", "ad": "faaliyet_eylul.pdf"},
        {"id": 3, "tur": "Vergi levhası", "zaman": "2026-03-01", "belge_tarihi": "2026-03-01", "ad": "vl.pdf"},
        {"id": 4, "tur": "Kalite belgesi", "zaman": "2026-02-01", "belge_tarihi": "2026-02-01",
         "bitis_tarihi": "2026-09-01", "ad": "iso.pdf"},
    ]


def test_gruplandir_guncel_surum_ve_sira():
    g = H.gruplandir(_kayitlar())
    assert [x["tur"] for x in g] == ["Vergi levhası", "Oda faaliyet belgesi", "Kalite belgesi"]
    faal = g[1]
    assert faal["guncel"]["id"] == 2 and [r["id"] for r in faal["eskiler"]] == [1]


def test_uyarilar_yalniz_guncel_surum():
    u = H.uyarilar(_kayitlar(), date(2026, 10, 7))
    # Ocak'taki faaliyet belgesinin süresi doldu ama yenisi var: uyarı yok. Yenisi 13 gün sonra doluyor.
    assert [(x["tur"], x["durum"], x["kalan"]) for x in u] == [
        ("Kalite belgesi", "dolmus", -36), ("Oda faaliyet belgesi", "yaklasiyor", 13)]


def test_zip_ayni_ad_numaralanir():
    v = H.zip_icerik([("Vergi levhası.pdf", b"a"), ("vergi levhası.pdf", b"b"), ("Not", b"c")])
    z = zipfile.ZipFile(io.BytesIO(v))
    assert z.namelist() == ["Vergi levhası.pdf", "vergi levhası (2).pdf", "Not"]
    assert z.read("vergi levhası (2).pdf") == b"b"


def test_indirme_adi():
    assert H.indirme_adi({"tur": "Vergi levhası", "ad": "x.PDF", "belge_tarihi": "2026-03-01"}) == \
        "Vergi levhası - 2026-03-01.pdf"


def test_kunye_birlestir_oncelik_ve_bos_alan():
    v = {"unvan": "KAYRAN ELEKTRONİK", "vkn": "", "adres": ""}
    k = H.kunye_birlestir(v, {"vkn": "111", "adres": "secret adres"}, {"vkn": "3881881884", "adres": "  "})
    assert k == {"unvan": "KAYRAN ELEKTRONİK", "vkn": "3881881884", "adres": "secret adres"}


def test_edefter_kunye():
    a = {"unvan": "G5F TEKNOLOJI A.S.", "vkn": "3881881884", "telefon": "02164662888",
         "eposta": "info@g5f.com", "website": "", "adres_cadde": "YUKARI DUDULLU MAH.",
         "adres_cadde2": "NECIP FAZIL BLV.", "adres_bina": "NO: 44 /87", "adres_posta": "34775",
         "adres_il": "İSTANBUL"}
    k = H.edefter_kunye(a)
    assert k["adres"] == "YUKARI DUDULLU MAH. NECIP FAZIL BLV. NO: 44 /87, 34775 İSTANBUL"
    assert k["vkn"] == "3881881884" and "web" not in k
    assert H.kunye_metni(k).splitlines()[0] == "Ticari unvan: G5F TEKNOLOJI A.S."


def test_sirket_bilgi_ekranda_kaydedilen_kunyeyi_kullanir(monkeypatch):
    """Yazdırılan irsaliye / sevk belgesi başlığı: ekranda kaydedilen künye boş varsayılanı ezer."""
    from shared import sirket, sirket_belge
    monkeypatch.setattr(sirket_belge, "kunye_oku", lambda: {"vkn": "3881881884", "adres": "Ümraniye"})
    b = sirket.sirket_bilgi()
    assert b["vkn"] == "3881881884" and b["adres"] == "Ümraniye"
    assert b["marka"] == "FAZEON"


class _Alan:
    def __init__(self, kayit):
        self.k = kayit

    def upload(self, path, file, file_options):
        self.k.append(("upload", path))

    def remove(self, yollar):
        self.k.append(("remove", tuple(yollar)))


class _Tablo:
    def insert(self, _):
        return self

    def execute(self):
        raise RuntimeError("tablo yok")


class _Istemci:
    def __init__(self):
        self.k = []
        self.storage = self

    def from_(self, _):
        return _Alan(self.k)

    def table(self, _):
        return _Tablo()


def test_yukle_tablo_yazilamazsa_dosya_geri_silinir(monkeypatch):
    from shared import sirket_belge as D
    ist = _Istemci()
    monkeypatch.setattr(D, "_istemci", lambda: ist)
    ok, hata = D.yukle(b"%PDF", "vl.pdf", "Vergi levhası", date(2026, 3, 1))
    assert not ok and "kaydedilemedi" in hata
    assert ist.k[0][0] == "upload" and ist.k[1] == ("remove", (ist.k[0][1],))
    assert ist.k[0][1].startswith("vergi-levhasi/") and ist.k[0][1].endswith("-vl.pdf")
