# -*- coding: utf-8 -*-
"""Asistanlar — uygulama tarafı veritabanı işleri (Ekim 2026). Hesaplar shared.asistan_hesap'ta.

  Telegram asistanı : Telegram kimliği ↔ program kullanıcısı eşlemesi (sistem_ayarlari 'telegram_kullanicilar')
  Pazar araştırmacısı: asistan_rapor tablosundaki raporlar
  Gümrük danışmanı  : gumruk_sorgulari; yeni sorgu kaydedilince görev [gumruk_rutin] ayarı varsa hemen başlar,
                      yoksa iş saatlerindeki düzenli çalışmasında alır.
"""
import json
from datetime import datetime, timedelta, timezone

import streamlit as st

KULLANICI_ANAHTAR = "telegram_kullanicilar"
GIZLI_ANAHTAR = "telegram_webhook_gizli"


def _sb():
    from shared.auth import _get_supabase
    return _get_supabase()


def _tr_simdi():
    return datetime.now(timezone(timedelta(hours=3)))


def _ayar(anahtar):
    r = (_sb().table("sistem_ayarlari").select("deger").eq("anahtar", anahtar).limit(1).execute().data or [])
    return r[0].get("deger") if r else None


# ── Telegram ────────────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def telegram_haritasi():
    """{telegram_kimlik: kullanici}; okunamazsa {}."""
    try:
        v = json.loads(_ayar(KULLANICI_ANAHTAR) or "{}")
        return {str(k): str(u) for k, u in v.items()} if isinstance(v, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def telegram_haritasi_yaz(harita):
    try:
        _sb().table("sistem_ayarlari").upsert(
            {"anahtar": KULLANICI_ANAHTAR, "deger": json.dumps(harita, ensure_ascii=False),
             "guncelleme_tarihi": _tr_simdi().strftime("%Y-%m-%d %H:%M:%S")}, on_conflict="anahtar").execute()
    except Exception as e:  # noqa: BLE001
        return False, str(e)
    telegram_haritasi.clear()
    return True, ""


@st.cache_data(ttl=60, show_spinner=False)
def sql_kurulu():
    """veritabani/25_asistanlar.sql kurulmuş mu (webhook gizli değeri üretilmiş mi)."""
    try:
        return bool(_ayar(GIZLI_ANAHTAR))
    except Exception:  # noqa: BLE001
        return False


# ── Pazar araştırmacısı ─────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def raporlar(limit=30):
    """Yeni üstte; tablo yoksa None."""
    try:
        return (_sb().table("asistan_rapor").select("*").order("zaman", desc=True).range(0, limit - 1)
                .execute().data or [])
    except Exception:  # noqa: BLE001
        return None


# ── Gümrük danışmanı ────────────────────────────────────────────────
@st.cache_data(ttl=20, show_spinner=False)
def gumruk_sorgulari(limit=50):
    """Yeni üstte; tablo yoksa None."""
    try:
        return (_sb().table("gumruk_sorgulari").select("*").order("zaman", desc=True).range(0, limit - 1)
                .execute().data or [])
    except Exception:  # noqa: BLE001
        return None


def gumruk_ekle(satir, kullanici=""):
    """Yeni sorgu; ardından görevi hemen başlatmayı dener. Döner (ok, mesaj)."""
    satir = dict(satir, kullanici=str(kullanici or "")[:40], durum="bekliyor")
    try:
        r = _sb().table("gumruk_sorgulari").insert(satir).execute().data or [{}]
    except Exception as e:  # noqa: BLE001
        return False, f"Kaydedilemedi: {e}"
    gumruk_sorgulari.clear()
    basladi, sebep = gumruk_tetikle(r[0].get("id"))
    if basladi:
        return True, "Hakan şimdi başladı; sonuç birkaç dakika içinde burada görünür."
    return True, ("Sorgu sıraya alındı. Hakan iş saatlerinde en geç 2 saat içinde bakar"
                  + (f" (anında başlatılamadı: {sebep})." if sebep and sebep != "rutin ayarı yok" else "."))


def gumruk_tetikle(sorgu_id):
    try:
        from shared.claude_talep import rutin_ayari_coz, rutini_tetikle
        return rutini_tetikle(sorgu_id, rutin_ayari_coz(bolum="gumruk_rutin"),
                              metin=f"Gümrük sorgusu #{sorgu_id} sıraya alındı.")[:2]
    except Exception as e:  # noqa: BLE001
        return False, f"tetiklenemedi ({type(e).__name__})"


def gumruk_yeniden(sorgu_id):
    """Hatalı / takılmış sorguyu yeniden sıraya alır."""
    try:
        _sb().table("gumruk_sorgulari").update({"durum": "bekliyor", "guncelleme": None}).eq("id", sorgu_id).execute()
    except Exception as e:  # noqa: BLE001
        return False, str(e)
    gumruk_sorgulari.clear()
    gumruk_tetikle(sorgu_id)
    return True, ""
