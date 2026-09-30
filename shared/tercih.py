# -*- coding: utf-8 -*-
"""KAYRAN — Kullanıcı tercihleri (görünüm teması).

Tercih Supabase 'kullanici_tercih' tablosunda tutulur (veritabani/06_…sql);
böylece kullanıcı telefondan da bilgisayardan da aynı temayı görür.
Tablo yoksa ya da erişilemezse: okuma 'koyu' döner, yazma yalnız oturumda
kalır — akış hiçbir zaman bozulmaz, hata Sistem Kayıtları'na düşer.
"""
TABLO = "kullanici_tercih"
TEMALAR = ("koyu", "acik")


def _sb():
    from shared.auth import _get_supabase
    return _get_supabase()


def tema_oku(kullanici):
    k = (kullanici or "").strip().lower()
    if not k:
        return "koyu"
    try:
        r = _sb().table(TABLO).select("tema").eq("kullanici", k).limit(1).execute().data
        t = (r[0].get("tema") if r else None) or "koyu"
        return t if t in TEMALAR else "koyu"
    except Exception as e:  # noqa: BLE001 — tablo yok / ağ
        from shared.hata_log import kaydet
        kaydet("tercih.tema_oku", e)
        return "koyu"


def tema_yaz(kullanici, tema):
    k = (kullanici or "").strip().lower()
    if not k or tema not in TEMALAR:
        return False
    try:
        _sb().table(TABLO).upsert({"kullanici": k, "tema": tema}).execute()
        return True
    except Exception as e:  # noqa: BLE001
        from shared.hata_log import kaydet
        kaydet("tercih.tema_yaz", e)
        return False
