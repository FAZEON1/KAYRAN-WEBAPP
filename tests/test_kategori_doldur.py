# -*- coding: utf-8 -*-
"""İthalat — boş kategorinin karttan doldurulması (Ekim 2026, ana veri).

Masraf dağıtımı grup adının BİREBİR eşleşmesine dayanır. Eskiden kartın kategorisi
Python .upper() ile yazılıyordu ('monitör' → noktasız 'MONITÖR'); aynı dosyada elle
girilmiş 'MONİTÖR' ayrı grup sayılıyordu. Doldurma artık dosyada zaten geçen yazımı alır;
kaydedilmiş masraf ataması / hacim yazımı her zaman korunur.
"""
import pytest

import ithalat.database as idb


@pytest.fixture
def kur(monkeypatch):
    def _kur(dosyalar, kart_kat):
        monkeypatch.setattr(idb, "get_dosyalar", lambda: dosyalar)
        monkeypatch.setattr(idb, "get_sku_kategori_map", lambda: kart_kat)
    return _kur


def _k(did, sku, grup=""):
    return {"dosya_id": did, "sku": sku, "urun_grubu": grup, "adet": 1, "birim_fob": 1}


def test_dosyadaki_elle_yazim_alinir(kur):
    kur([{"id": 1}], {"X1": "monitör", "K1": "kasa"})
    out = idb._kategori_doldur([_k(1, "X1"), _k(1, "Y9", "MONİTÖR"), _k(1, "K1")])
    assert out[0]["urun_grubu"] == "MONİTÖR"            # eskiden 'MONITÖR' → ayrı grup
    assert out[2]["urun_grubu"] == "KASA"


def test_kayitli_masraf_atamasi_yazimi_korunur(kur):
    """Kullanıcı atamayı eski doldurulmuş yazımla ('MONITÖR') kaydettiyse o bozulmamalı."""
    kur([{"id": 1, "grup_masraf_atama": {"gv": "MONITÖR", "navlun": "__ortak__"}}], {"X1": "monitör"})
    out = idb._kategori_doldur([_k(1, "X1"), _k(1, "Y9", "MONİTÖR")])
    assert out[0]["urun_grubu"] == "MONITÖR"


def test_hacim_yazimi_korunur(kur):
    kur([{"id": 1, "grup_cbm": {"MONITÖR": 3.5}}], {"X1": "monitör"})
    assert idb._kategori_doldur([_k(1, "X1")])[0]["urun_grubu"] == "MONITÖR"


def test_dosyada_yoksa_turkce_dogru_buyuk_harf(kur):
    kur([{"id": 1}], {"X1": "monitör", "E1": "Ekran Kartı"})
    out = idb._kategori_doldur([_k(1, "X1"), _k(1, "E1")])
    assert [k["urun_grubu"] for k in out] == ["MONİTÖR", "EKRAN KARTI"]


def test_elle_yazilan_degere_dokunulmaz_ve_dosyalar_karismaz(kur):
    kur([{"id": 1}, {"id": 2}], {"X1": "monitör"})
    out = idb._kategori_doldur([_k(1, "X1", "Özel Grup"), _k(2, "Y9", "MONITÖR"), _k(1, "X1")])
    assert out[0]["urun_grubu"] == "Özel Grup"
    assert out[2]["urun_grubu"] == "MONİTÖR"            # dosya 2'nin yazımı dosya 1'e taşmaz
