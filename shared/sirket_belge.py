# -*- coding: utf-8 -*-
"""Şirket belgeleri — veritabanı ve dosya alanı (Ekim 2026).

Dosyalar Supabase Storage'da GİZLİ 'sirket-belgeleri' alanında, bilgileri 'sirket_belgeleri'
tablosunda (veritabani/24_sirket_belgeleri.sql). Görüntüleme 10 dakika geçerli imzalı linkle;
herkese açık link yok. Şirket künyesi sistem_ayarlari 'sirket_kunye' anahtarında (JSON).
Hesaplar shared.sirket_belge_hesap'ta.
"""
import json
from datetime import datetime, timedelta, timezone

import streamlit as st

from shared.sirket_belge_hesap import UZANTILAR, depo_yolu, uzanti

TABLO = "sirket_belgeleri"
ALAN = "sirket-belgeleri"
KUNYE_ANAHTAR = "sirket_kunye"
LINK_SN = 600


def _istemci():
    from shared.auth import _get_supabase
    return _get_supabase()


def _tr_simdi():
    return datetime.now(timezone(timedelta(hours=3)))


@st.cache_data(ttl=300, show_spinner=False)
def listele():
    """Bütün belge kayıtları. Tablo yoksa (SQL kurulmadan) None — ekran kurulum notu gösterir."""
    try:
        return (_istemci().table(TABLO).select("*").order("zaman", desc=True).range(0, 999)
                .execute().data or [])
    except Exception:  # noqa: BLE001
        return None


def yukle(veri, ad, tur, belge_tarihi=None, bitis_tarihi=None, notu="", kullanici=""):
    """Önce dosya alanına, sonra tabloya yazar; tablo yazılamazsa yüklenen dosya geri silinir.
    Döner: (True, kayıt) | (False, hata metni)."""
    yol = depo_yolu(tur, ad, _tr_simdi())
    mime = UZANTILAR.get(uzanti(ad), "application/octet-stream")
    sb = _istemci()
    try:
        sb.storage.from_(ALAN).upload(path=yol, file=veri, file_options={"content-type": mime, "upsert": "false"})
    except Exception as e:  # noqa: BLE001
        return False, f"Dosya yüklenemedi: {e}"
    satir = {"tur": tur, "ad": str(ad)[:200], "yol": yol, "boyut": len(veri), "mime": mime,
             "belge_tarihi": belge_tarihi.isoformat() if belge_tarihi else None,
             "bitis_tarihi": bitis_tarihi.isoformat() if bitis_tarihi else None,
             "notu": str(notu or "").strip()[:500], "yukleyen": str(kullanici or "")[:40]}
    try:
        r = sb.table(TABLO).insert(satir).execute().data or [satir]
    except Exception as e:  # noqa: BLE001
        try:
            sb.storage.from_(ALAN).remove([yol])
        except Exception:  # noqa: BLE001
            pass
        return False, f"Belge kaydedilemedi: {e}"
    listele.clear()
    return True, r[0]


def guncelle(kayit_id, belge_tarihi=None, bitis_tarihi=None, notu=""):
    try:
        _istemci().table(TABLO).update({
            "belge_tarihi": belge_tarihi.isoformat() if belge_tarihi else None,
            "bitis_tarihi": bitis_tarihi.isoformat() if bitis_tarihi else None,
            "notu": str(notu or "").strip()[:500]}).eq("id", kayit_id).execute()
    except Exception as e:  # noqa: BLE001
        return False, str(e)
    listele.clear()
    return True, ""


def sil(kayit):
    """Kaydı ve dosyasını siler (ekranda onay alındıktan sonra)."""
    sb = _istemci()
    try:
        sb.table(TABLO).delete().eq("id", kayit["id"]).execute()
    except Exception as e:  # noqa: BLE001
        return False, str(e)
    try:
        sb.storage.from_(ALAN).remove([kayit["yol"]])
    except Exception:  # noqa: BLE001
        pass                                   # kayıt silindi; sahipsiz dosya yer kaplar, zarar vermez
    listele.clear()
    return True, ""


def link(yol):
    """10 dakika geçerli görüntüleme linki; alınamazsa ''."""
    try:
        r = _istemci().storage.from_(ALAN).create_signed_url(yol, LINK_SN)
        return (r.get("signedURL") or r.get("signedUrl") or "") if isinstance(r, dict) else ""
    except Exception:  # noqa: BLE001
        return ""


def indir(yol):
    """Dosyanın içeriği (bytes); alınamazsa None."""
    try:
        v = _istemci().storage.from_(ALAN).download(yol)
        return v if isinstance(v, (bytes, bytearray)) else None
    except Exception:  # noqa: BLE001
        return None


@st.cache_data(ttl=300, show_spinner=False)
def kunye_oku():
    """Ekranda kaydedilen künye (dict); yoksa {}."""
    try:
        r = (_istemci().table("sistem_ayarlari").select("deger").eq("anahtar", KUNYE_ANAHTAR)
             .limit(1).execute().data or [])
        v = json.loads(r[0].get("deger") or "{}") if r else {}
        return v if isinstance(v, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def kunye_yaz(kunye):
    try:
        _istemci().table("sistem_ayarlari").upsert(
            {"anahtar": KUNYE_ANAHTAR,
             "deger": json.dumps({k: str(v or "").strip() for k, v in kunye.items()}, ensure_ascii=False),
             "guncelleme_tarihi": _tr_simdi().strftime("%Y-%m-%d %H:%M:%S")},
            on_conflict="anahtar").execute()
    except Exception as e:  # noqa: BLE001
        return False, str(e)
    kunye_oku.clear()
    return True, ""


def edefter_ayari():
    """e-Defter ayarları (künye önerisi için); okunamazsa {}."""
    try:
        r = _istemci().table("edefter_ayarlar").select("*").eq("id", 1).limit(1).execute().data or []
        return r[0] if r else {}
    except Exception:  # noqa: BLE001
        return {}
