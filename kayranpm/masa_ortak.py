# -*- coding: utf-8 -*-
"""Ürün Yönetimi liste masaları için küçük ortak yardımcılar (Ekim 2026).

Sayfaların masa tanımları (urun_masasi, kampanya_masasi, siparis_masasi, ref_masasi, yurtici_masasi,
stok_yasi_masasi) ortak liste masasını (shared/masa.py) kullanır; burada yalnız biçim ve dışa aktarma
yardımcıları var. Hesap yok: rakamlar sayfaların bugünkü fonksiyonlarından gelir.
"""
from shared.tasarim import tr_sayi


def kisa(metin):
    """Büyük özet rakamı: 1.000 ve üstünde kuruşsuz (shared.tasarim.kart_degeri_kisa, kartlarla aynı kural)."""
    from shared.tasarim import kart_degeri_kisa
    return kart_degeri_kisa(metin)[0]


def usd(v, ondalik=2):
    """'$1.234,56' · eksi '-$12,00' · boş/None → ''."""
    if v is None or v == "":
        return ""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return ""
    return ("-" if f < 0 else "") + "$" + tr_sayi(abs(f), ondalik)


def sayi_mi(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def csv_bayt(satirlar, kolonlar=None):
    """Excel'in açtığı CSV (shared.tablo'nun indirme düğmesiyle aynı biçim: UTF-8 BOM, ';' ayraç,
    sayılarda ondalık virgül). '_' ile başlayan alanlar yazılmaz."""
    satirlar = list(satirlar or [])
    if kolonlar is None:
        kolonlar = []
        for r in satirlar:
            for k in r:
                if not str(k).startswith("_") and k not in kolonlar:
                    kolonlar.append(k)

    def hucre(v):
        if v is None:
            return ""
        if isinstance(v, bool):
            v = "evet" if v else "hayır"
        if isinstance(v, (int, float)):
            s = repr(float(v)) if isinstance(v, float) else str(v)
            if isinstance(v, float) and float(v).is_integer():
                s = str(int(v))
            return s.replace(".", ",")
        s = str(v)
        if any(c in s for c in ';"\n\r'):
            s = '"' + s.replace('"', '""') + '"'
        return s

    satir = [";".join(hucre(k) for k in kolonlar)]
    satir += [";".join(hucre(r.get(k)) for k in kolonlar) for r in satirlar]
    return ("﻿" + "\r\n".join(satir)).encode("utf-8")


def ac_islemi(ad="Ayrıntı", dugme=None):
    """Ayrıntıyı (bugünkü pencere ya da sayfa içi detay) açan işlem; salt-okur oturumda da çalışır."""
    return {"k": "ac", "ad": ad, "dugme": dugme or ad, "okuma": True}
