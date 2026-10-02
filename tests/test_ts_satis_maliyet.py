# -*- coding: utf-8 -*-
"""Teknik Servis / 2.el satışları (Ekim 2026): maliyet artık ithalat PAÇALINDAN.

Eskiden birim maliyet 0 yazılıyordu ("orijinal alışta giderleşti, tekrar yazmak çift
sayım" gerekçesiyle). Bu depolara gelen ürünler çoğunlukla iade/değişim ürünü; iade
ilk satışın maliyetini zaten geri alıyor (COGS'tan düşülüyor), ürün maliyetiyle stoğa
dönüyor. Yeniden satışta maliyet yazılmazsa satış %100 marjlı görünüyordu.
"""
import sys
import types


def _kur(monkeypatch, pacal):
    import satis.database as SD
    yazilan = {}
    monkeypatch.setattr(SD, "ekle_satis", lambda **k: yazilan.update(k))
    monkeypatch.setattr(SD, "get_pacal_map", lambda: pacal)
    from teknikservis import stok
    return stok, yazilan


def test_maliyet_pacaldan(monkeypatch):
    from shared.utils import sku_anahtar
    stok, y = _kur(monkeypatch, {sku_anahtar("X24F240P"): 87.5})
    ok, m = stok.satis_kaydi_yaz({"stok_kodu": "X24F240P", "stok_adi": "24 monitör"}, 120)
    assert ok and y["birim_maliyet"] == 87.5 and y["birim_satis"] == 120
    assert y["kanal"] == "TEKNİK SERVİS / 2.EL"


def test_fazeon_onekli_sku_da_eslesir(monkeypatch):
    from shared.utils import sku_anahtar
    stok, y = _kur(monkeypatch, {sku_anahtar("X24F240P"): 87.5})
    stok.satis_kaydi_yaz({"stok_kodu": "Fazeon X24F240P"}, 120)
    assert y["birim_maliyet"] == 87.5


def test_bedelsizde_de_maliyet_yazilir(monkeypatch):
    """Bedelsiz verilen ürünün de bir maliyeti var: zarar olarak görünmeli."""
    from shared.utils import sku_anahtar
    stok, y = _kur(monkeypatch, {sku_anahtar("X24F240P"): 87.5})
    stok.satis_kaydi_yaz({"stok_kodu": "X24F240P"}, 120, bedelsiz=True)
    assert y["birim_satis"] == 0 and y["birim_maliyet"] == 87.5


def test_pacal_yoksa_0_ve_bildirilir(monkeypatch):
    stok, y = _kur(monkeypatch, {})
    ok, m = stok.satis_kaydi_yaz({"stok_kodu": "BILINMEZ"}, 50)
    assert ok and y["birim_maliyet"] == 0 and "paçal" in m


def test_pacal_okunamazsa_satis_yine_yazilir(monkeypatch):
    import satis.database as SD
    stok, y = _kur(monkeypatch, {})
    monkeypatch.setattr(SD, "get_pacal_map", lambda: (_ for _ in ()).throw(RuntimeError("ithalat yok")))
    ok, m = stok.satis_kaydi_yaz({"stok_kodu": "X24F240P"}, 50)
    assert ok and y["birim_maliyet"] == 0


def test_toplu_satista_paçalsiz_urun_uyarida():
    from pathlib import Path
    s = (Path(__file__).resolve().parent.parent / "teknikservis/main.py").read_text(encoding="utf-8")
    assert 'if not _o2 or "paçal" in (_m2 or ""):' in s
