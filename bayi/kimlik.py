# -*- coding: utf-8 -*-
"""Bayi Portalı — kimlik doğrulama & oturum.

Şifreleme personel tarafıyla AYNI (shared.auth · PBKDF2-SHA256). Kullanıcılar
bayi_kullanicilar tablosunda tutulur (personel st.secrets'ta; bayi DB'de).
Brute-force kilidi ayrı tablodadır (bayi_giris_denemeleri) — böylece bayi ve
personel kilitleri karışmaz.

Oturum st.session_state içinde tutulur:
  bayi_giris        : bool
  bayi_kullanici    : str  (kullanıcı adı)
  bayi_kayit        : dict (bayi_kullanicilar satırı)
"""
from datetime import datetime, timedelta, timezone

import streamlit as st

from shared.auth import sifre_hash_uret, sifre_dogrula
from bayi.veri import get_client, bayi_kullanici_getir, son_giris_yaz

TR_TZ = timezone(timedelta(hours=3))

# Brute-force: shared.auth ile aynı eşik/ceza mantığı
_BF_ESIK = 5
_BF_CEZA_DK = {5: 1, 6: 2, 7: 5, 8: 10}   # üstü 15 dk


def _now():
    return datetime.utcnow()


def _parse(ts):
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "").split("+")[0].split(".")[0])
    except Exception:
        return None


# ── Brute-force kilidi (bayi_giris_denemeleri) ──────────────────────
def _kilit_kontrol(k):
    """Dönen: (izin_var, kalan_saniye). Hata olursa engellemez."""
    try:
        res = get_client().table("bayi_giris_denemeleri").select("kilit_bitis") \
            .eq("kullanici_adi", k).limit(1).execute()
        if res.data:
            kb = res.data[0].get("kilit_bitis")
            kbt = _parse(kb) if kb else None
            if kbt:
                kalan = (kbt - _now()).total_seconds()
                if kalan > 0:
                    return False, int(kalan)
        return True, 0
    except Exception:
        return True, 0


def _basarisiz_say(k):
    """Başarısız denemeyi işler, eşikte kilitler. Dönen: (toplam, kilit_saniye)."""
    try:
        res = get_client().table("bayi_giris_denemeleri").select("basarisiz_sayi") \
            .eq("kullanici_adi", k).limit(1).execute()
        sayi = ((res.data[0].get("basarisiz_sayi") or 0) if res.data else 0) + 1
        kayit = {"kullanici_adi": k, "basarisiz_sayi": sayi, "son_deneme": _now().isoformat()}
        kilit_saniye = 0
        if sayi >= _BF_ESIK:
            dk = _BF_CEZA_DK.get(sayi, 15)
            kilit_saniye = dk * 60
            kayit["kilit_bitis"] = (_now() + timedelta(minutes=dk)).isoformat()
        get_client().table("bayi_giris_denemeleri").upsert(
            kayit, on_conflict="kullanici_adi").execute()
        return sayi, kilit_saniye
    except Exception:
        return 0, 0


def _sifirla(k):
    """Başarılı giriş → sayaç ve kilidi sıfırla."""
    try:
        get_client().table("bayi_giris_denemeleri").upsert(
            {"kullanici_adi": k, "basarisiz_sayi": 0, "kilit_bitis": None,
             "son_deneme": _now().isoformat()}, on_conflict="kullanici_adi").execute()
    except Exception:
        pass


# ── Giriş ────────────────────────────────────────────────────────────
def giris_yap(kullanici_adi, sifre):
    """Bayi girişini dener.

    Döner: (ok, mesaj, kayit|None). Başarılıysa oturumu da başlatır.
    """
    k = (kullanici_adi or "").strip().lower()
    if not k or not sifre:
        return False, "Kullanıcı adı ve şifre gerekli.", None

    izin, kalan = _kilit_kontrol(k)
    if not izin:
        dk = (kalan + 59) // 60
        return False, f"🔒 Çok fazla hatalı deneme. {dk} dk sonra tekrar deneyin.", None

    kayit = bayi_kullanici_getir(k)
    if not kayit:
        # Kullanıcı yokluğu timing'den anlaşılmasın — sahte hash doğrula
        sifre_dogrula(sifre, sifre_hash_uret("__dummy__"))
        _basarisiz_say(k)
        return False, "Kullanıcı adı veya şifre hatalı.", None

    if not kayit.get("aktif", True):
        return False, "Bu hesap pasif durumda. Lütfen yetkiliyle görüşün.", None

    if not sifre_dogrula(sifre, kayit.get("sifre_hash", "")):
        sayi, kilit = _basarisiz_say(k)
        if kilit:
            return False, f"🔒 Hesap {kilit // 60} dk kilitlendi ({sayi}. hata).", None
        return False, "Kullanıcı adı veya şifre hatalı.", None

    # Başarılı
    _sifirla(k)
    son_giris_yaz(k)
    oturum_baslat(kayit)
    return True, f"Hoş geldiniz, {kayit.get('ad_soyad') or k}.", kayit


# ── Oturum ────────────────────────────────────────────────────────────
def oturum_baslat(kayit):
    st.session_state["bayi_giris"] = True
    st.session_state["bayi_kullanici"] = kayit.get("kullanici_adi")
    st.session_state["bayi_kayit"] = kayit


def oturum_kapat():
    for a in ("bayi_giris", "bayi_kullanici", "bayi_kayit"):
        st.session_state.pop(a, None)


def giris_var_mi():
    return bool(st.session_state.get("bayi_giris"))


def aktif_bayi():
    """Oturumdaki bayi kaydı (dict) veya None."""
    return st.session_state.get("bayi_kayit")


# ── Şifre değiştirme (bayi kendi şifresini) ─────────────────────────
def sifre_degistir(kullanici_id, eski_sifre, yeni_sifre):
    """Bayinin kendi şifresini değiştirmesi. Döner: (ok, mesaj)."""
    from bayi.veri import bayi_sifre_guncelle
    kayit = aktif_bayi()
    if not kayit or kayit.get("id") != kullanici_id:
        return False, "Oturum bulunamadı."
    if not sifre_dogrula(eski_sifre, kayit.get("sifre_hash", "")):
        return False, "Mevcut şifre hatalı."
    if len(yeni_sifre or "") < 6:
        return False, "Yeni şifre en az 6 karakter olmalı."
    yeni_hash = sifre_hash_uret(yeni_sifre)
    ok, msg = bayi_sifre_guncelle(kullanici_id, yeni_hash)
    if ok:
        kayit["sifre_hash"] = yeni_hash
        st.session_state["bayi_kayit"] = kayit
    return ok, ("✅ Şifreniz güncellendi." if ok else msg)
