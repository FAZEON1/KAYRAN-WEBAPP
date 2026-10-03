# -*- coding: utf-8 -*-
"""Kanal / firma adı tek kaynak (Ekim 2026, ana veri entegrasyonu Faz 4a).

Kullanıcı kararı: kanal ekranda CARİ adıyla görünür ('D-MARKET', 'EERA'), mağaza adıyla
('Hepsiburada', 'İtopya') değil. Eskiden: kanal kodu listesi 8 yerde ayrı yazılıydı,
cari önekleri iki kopyaydı (shared.utils + ref_no), Tüm Ürünler kartları KANAL_AD ile
mağaza adı, ürün kartı kampanya satırı ve Sipariş önerisi ham kod ('HB') gösteriyordu.
"""
import pathlib
import re

KOK = pathlib.Path(__file__).resolve().parent.parent


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


def test_kanal_kodu_listesi_tek_yerde():
    kalip = re.compile(r'\[\s*"ITOPYA",\s*"HB",\s*"VATAN"')
    tekrar = [str(p.relative_to(KOK)) for p in (KOK / "kayranpm").glob("*.py") if kalip.search(p.read_text(encoding="utf-8"))]
    assert not tekrar, f"Kanal kodu listesi yeniden elle yazılmış (shared.utils.FIRMA_KODLARI kullan): {tekrar}"


def test_listeler_ayni_kaynaktan():
    from shared.utils import FIRMA_KODLARI, FIRMA_KODLARI_DIGER
    from kayranpm import analitik, excel_islemler, urun_hesap, kampanya_hesap, genel_bakis
    assert tuple(analitik.FIRMA_LISTESI) == tuple(excel_islemler.FIRMA_LISTESI) == FIRMA_KODLARI_DIGER
    assert tuple(urun_hesap.KANALLAR) == FIRMA_KODLARI
    assert kampanya_hesap.FIRMALAR == [*FIRMA_KODLARI, "DİĞER"]
    assert genel_bakis.FIRMALAR == ["Tüm Firmalar", *FIRMA_KODLARI, "DİĞER"]


def test_cari_onekleri_tek_kaynak():
    from shared.utils import FIRMA_GORUNEN_AD
    from kayranpm.ref_no import FIRMA_ESLESME
    for kod, cfg in FIRMA_ESLESME.items():
        assert cfg["onek"] == FIRMA_GORUNEN_AD[kod]
    assert FIRMA_GORUNEN_AD["HB"] == "D-MARKET" and FIRMA_GORUNEN_AD["ITOPYA"] == "EERA"


def test_magaza_adi_kalkti_ham_kod_basilmiyor():
    assert "KANAL_AD = {" not in _oku("kayranpm/urun_hesap.py") and "\"HB\": \"Hepsiburada\"" not in _oku("kayranpm/urun_hesap.py")
    assert '{firma_gorunen_ad(_k.get("firma"))' in _oku("kayranpm/stok_karti.py")
    assert "{firma_gorunen_ad(fd[\"firma\"])}" in _oku("kayranpm/siparis_ekran.py")
