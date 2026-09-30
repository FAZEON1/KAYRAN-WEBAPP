# -*- coding: utf-8 -*-
"""KAYRAN — Merkezi hata kaydı.

NEDEN: Kodda yüzlerce `except Exception: pass` var. Amaç kullanıcıyı
korkutmamaktı ama sonuç şu oldu: stok düşümü başarısız oluyor, kimse
bilmiyor, haftalar sonra "sanırım stok güncellenmiyor" deniyor ve neden
hiçbir zaman bulunamıyor (F4PE650BBM · 06.08.2026).

ŞİMDİ: Hata yine kullanıcıyı durdurmaz, ama 'hata_kayitlari' tablosuna
düşer. Kritik olanlar (para/stok) istenirse Telegram'a da gider.

KURALLAR
  · kaydet() ASLA istisna fırlatmaz — çağıranı bozamaz.
  · Aynı yerden aynı hata 5 dk içinde tekrar gelirse tekrar yazılmaz
    (bir döngüde 500 kez patlayan hata tabloyu doldurmasın).
  · Tablo yoksa sessizce geçer (kurulumdan önce de kod çalışsın).
"""
import threading
import time
import traceback

TABLO = "hata_kayitlari"
_TEKRAR_SN = 300
_son_gorulme = {}
_kilit = threading.Lock()


def _kullanici():
    try:
        import streamlit as st
        return str(st.session_state.get("aktif_kullanici", "") or "")
    except Exception:
        return ""


def _tekrar_mi(anahtar):
    simdi = time.time()
    with _kilit:
        onceki = _son_gorulme.get(anahtar)
        _son_gorulme[anahtar] = simdi
        if len(_son_gorulme) > 2000:                 # bellek sınırı
            for k in sorted(_son_gorulme, key=_son_gorulme.get)[:1000]:
                _son_gorulme.pop(k, None)
    return onceki is not None and (simdi - onceki) < _TEKRAR_SN


def kaydet(yer, hata, ayrinti="", kritik=False):
    """Hatayı kaydet. yer: 'satis._stok_uygula' gibi kısa konum.
    hata: Exception ya da metin. kritik=True → Telegram'a da bildir.
    Döner: True (yazıldı) / False (tekrar, tablo yok, ya da hata)."""
    try:
        if isinstance(hata, BaseException):
            tur = type(hata).__name__
            mesaj = str(hata)[:500]
            if not ayrinti:
                ayrinti = "".join(traceback.format_exception(type(hata), hata,
                                                             hata.__traceback__))[-3000:]
        else:
            tur, mesaj = "Uyari", str(hata)[:500]
        if _tekrar_mi((yer, tur, mesaj[:120])):
            return False
        try:
            from shared.auth import _get_supabase
            sb = _get_supabase()
            if sb:
                sb.table(TABLO).insert({
                    "yer": str(yer)[:120], "tur": tur[:60], "mesaj": mesaj,
                    "ayrinti": str(ayrinti or "")[:4000], "kullanici": _kullanici()[:40],
                    "kritik": bool(kritik),
                }).execute()
        except Exception:
            pass
        if kritik:
            try:
                from shared.telegram_gonder import gonder, kacis, aktif_mi
                if aktif_mi():
                    gonder(f"🧯 <b>Sistem hatası</b>\n<code>{kacis(yer)}</code>\n"
                           f"{kacis(tur)}: {kacis(mesaj[:300])}"
                           + (f"\n👤 {kacis(_kullanici())}" if _kullanici() else ""),
                           sessiz=True)
            except Exception:
                pass
        return True
    except Exception:
        return False


def son_hatalar(limit=200, yalniz_kritik=False):
    """Ekran için son hatalar (yeni üstte). Tablo yoksa []."""
    try:
        from shared.auth import _get_supabase
        q = _get_supabase().table(TABLO).select("*").order("zaman", desc=True).limit(limit)
        if yalniz_kritik:
            q = q.eq("kritik", True)
        return q.execute().data or []
    except Exception:
        return []
