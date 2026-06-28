# -*- coding: utf-8 -*-
"""Merkezi veri doğrulama yardımcıları — saf fonksiyonlar (DB gerektirmez).
İş kuralı kontrolleri için modüllerde tekrar tekrar yazmak yerine buradan kullanılır."""


def _f(x, vars=0.0):
    try:
        return float(x)
    except Exception:
        return vars


def zararina_mi(birim_satis, maliyet):
    """Birim satış, maliyetin altında mı? (zararına satış). Maliyet 0/bilinmiyorsa False."""
    m = _f(maliyet)
    return m > 0 and _f(birim_satis) < m


def gecerli_sku(sku, sku_listesi):
    """SKU, geçerli ürün listesinde mi?"""
    return bool(sku) and sku in set(sku_listesi or [])


def pozitif_mi(deger):
    """Değer 0'dan büyük mü?"""
    return _f(deger) > 0


def zorunlu_dolu(*degerler):
    """Verilen tüm alanlar dolu mu (boş string/None değil)?"""
    return all((v is not None and str(v).strip() != "") for v in degerler)
