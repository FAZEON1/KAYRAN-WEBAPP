# -*- coding: utf-8 -*-
"""Çalışan izinleri — veritabanı (Ekim 2026). Tablolar veritabani/26_izin.sql:
  personel        : kişi kartı (işe giriş, doğum tarihi, departman, devreden bakiye, çıkış)
  izin_talepleri  : talepler ve kararlar (gün sayısı talep anında hesaplanıp yazılır)
Ayar: sistem_ayarlari 'izin_ayar' (JSON) — {"cumartesi": false}. Hesaplar shared.izin_hesap'ta.
Yazmalar shared.auth istemcisinden geçer, değişiklik günlüğüne (audit_log) kendiliğinden düşer.
"""
import json
from datetime import datetime, timedelta, timezone

import streamlit as st

PERSONEL = "personel"
TALEP = "izin_talepleri"
AYAR_ANAHTAR = "izin_ayar"
VARSAYILAN_AYAR = {"cumartesi": False}


def _istemci():
    from shared.auth import _get_supabase
    return _get_supabase()


def _simdi():
    return datetime.now(timezone(timedelta(hours=3))).isoformat(timespec="seconds")


def _hepsi(tablo, siralama):
    """Tablonun tamamı (Supabase tek sorguda en çok 1000 satır döndürür; sayfalı okur)."""
    out, bas = [], 0
    while True:
        p = (_istemci().table(tablo).select("*").order(siralama).range(bas, bas + 999).execute().data or [])
        out += p
        if len(p) < 1000:
            return out
        bas += 1000


@st.cache_data(ttl=120, show_spinner=False)
def personeller():
    """Bütün personel kartları; tablo yoksa (SQL kurulmadan) None."""
    try:
        return _hepsi(PERSONEL, "ad")
    except Exception:  # noqa: BLE001
        return None


@st.cache_data(ttl=60, show_spinner=False)
def talepler():
    """Bütün izin kayıtları (yeni → eski sıralamayı ekran yapar); tablo yoksa None."""
    try:
        return _hepsi(TALEP, "id")
    except Exception:  # noqa: BLE001
        return None


def _tazele():
    personeller.clear()
    talepler.clear()


def _iso(d):
    return d.isoformat() if d else None


def personel_kaydet(kod, ad, departman="", ise_giris=None, dogum_tarihi=None, devir_tarihi=None,
                    devir_gun=None, cikis_tarihi=None, notu="", sicil_no=""):
    """Kartı ekler ya da günceller (kod = kullanıcı adı ya da programa girmeyen çalışan için kısa ad)."""
    kod = str(kod or "").strip().lower()
    if not kod:
        return False, "Kod boş olamaz."
    satir = {"kod": kod, "ad": str(ad or "").strip()[:80] or kod, "departman": str(departman or "").strip()[:40],
             "ise_giris": _iso(ise_giris), "dogum_tarihi": _iso(dogum_tarihi),
             "devir_tarihi": _iso(devir_tarihi),
             "devir_gun": float(devir_gun) if (devir_tarihi and devir_gun is not None) else None,
             "cikis_tarihi": _iso(cikis_tarihi), "notu": str(notu or "").strip()[:300],
             "sicil_no": str(sicil_no or "").strip()[:30], "guncelleme": _simdi()}
    try:
        _istemci().table(PERSONEL).upsert(satir, on_conflict="kod").execute()
    except Exception as e:  # noqa: BLE001
        return False, f"Personel kaydedilemedi: {e}"
    _tazele()
    return True, ""


def talep_ekle(personel, tur, baslangic, bitis, gun, takvim_gunu, yarim_gun=False, aciklama="",
               talep_eden="", durum="bekliyor", karar_notu="", yol_izni=0, izin_adresi=""):
    """Yeni izin kaydı. durum 'onaylandi' ise (yöneticinin doğrudan girdiği kayıt) karar alanları da dolar."""
    satir = {"personel": personel, "tur": tur, "baslangic": _iso(baslangic), "bitis": _iso(bitis),
             "yarim_gun": bool(yarim_gun), "gun": float(gun), "takvim_gunu": int(takvim_gunu),
             "aciklama": str(aciklama or "").strip()[:300], "durum": durum,
             "yol_izni": max(0, min(4, int(yol_izni or 0))), "izin_adresi": str(izin_adresi or "").strip()[:300],
             "talep_eden": talep_eden, "talep_zamani": _simdi()}
    if durum == "onaylandi":
        satir.update(karar_veren=talep_eden, karar_zamani=_simdi(), karar_notu=str(karar_notu or "")[:300])
    try:
        r = _istemci().table(TALEP).insert(satir).execute().data or [satir]
    except Exception as e:  # noqa: BLE001
        return False, f"İzin kaydedilemedi: {e}"
    _tazele()
    return True, r[0]


def karar_ver(talep_id, onay, kim, notu=""):
    """Bekleyen talebi onaylar / reddeder. Başkası aynı anda karar verdiyse (durum artık 'bekliyor'
    değilse) dokunmaz ve bunu söyler."""
    try:
        r = (_istemci().table(TALEP)
             .update({"durum": "onaylandi" if onay else "reddedildi", "karar_veren": kim,
                      "karar_zamani": _simdi(), "karar_notu": str(notu or "").strip()[:300]})
             .eq("id", talep_id).eq("durum", "bekliyor").execute().data)
    except Exception as e:  # noqa: BLE001
        return False, f"Karar kaydedilemedi: {e}"
    _tazele()
    if not r:
        return False, "Bu talep artık beklemede değil (başka biri karar vermiş ya da iptal edilmiş)."
    return True, ""


def iptal_et(talep_id, kim, notu="", eski_durum=("bekliyor",)):
    """Talebi iptal eder. Çalışan yalnız bekleyenini, yönetici onaylıyı da iptal edebilir (ekran denetler);
    eski_durum dışındaki kayda dokunulmaz."""
    try:
        r = (_istemci().table(TALEP)
             .update({"durum": "iptal", "iptal_eden": kim, "iptal_zamani": _simdi(),
                      "karar_notu": str(notu or "").strip()[:300]})
             .eq("id", talep_id).in_("durum", list(eski_durum)).execute().data)
    except Exception as e:  # noqa: BLE001
        return False, f"İptal kaydedilemedi: {e}"
    _tazele()
    if not r:
        return False, "Bu kayıt artık iptal edilebilir durumda değil."
    return True, ""


@st.cache_data(ttl=300, show_spinner=False)
def ayar():
    try:
        r = (_istemci().table("sistem_ayarlari").select("deger").eq("anahtar", AYAR_ANAHTAR)
             .limit(1).execute().data or [])
        v = json.loads(r[0].get("deger") or "{}") if r else {}
        return {**VARSAYILAN_AYAR, **(v if isinstance(v, dict) else {})}
    except Exception:  # noqa: BLE001
        return dict(VARSAYILAN_AYAR)


def ayar_yaz(deger):
    try:
        _istemci().table("sistem_ayarlari").upsert(
            {"anahtar": AYAR_ANAHTAR, "deger": json.dumps(deger, ensure_ascii=False),
             "guncelleme_tarihi": _simdi()[:19].replace("T", " ")}, on_conflict="anahtar").execute()
    except Exception as e:  # noqa: BLE001
        return False, str(e)
    ayar.clear()
    return True, ""


def bildir(alicilar, mesaj, gonderen):
    """Program içi bildirim (zil). Hata işlemi bozmaz."""
    try:
        rows = [{"gonderen": gonderen, "alici": a, "mesaj": mesaj, "okundu": False}
                for a in sorted(set(alicilar or [])) if a and a != gonderen]
        if rows:
            _istemci().table("bildirimler").insert(rows).execute()
    except Exception:  # noqa: BLE001
        pass
