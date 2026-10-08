# -*- coding: utf-8 -*-
"""Ekip — programın dijital çalışanları tek yerde (Ekim 2026). Saf veri ve hesap; Streamlit'e bağlı değil.

Ekip (shared/ofis_ekran.py) her çalışanın kartını ve kendi bölümünü gösterir. İsimler ve
görev tanımları yalnız burada; görev talimatları (otonom/*.md) ve Telegram mesajları aynı adları kullanır.

  CALISANLAR                     kod, ad, unvan, ne zaman çalışır, ne yapar
  durumlar(...)                  her çalışanın kart durumu: son iş, sırada / kurulum bekliyor
"""
from datetime import datetime, timedelta, timezone

CALISANLAR = [
    {"kod": "serkan", "ad": "Serkan", "unvan": "Bilgi işlem", "ikon": "engineering",
     "ne_zaman": "Her gece 02:57",
     "is": "Programı kontrol eder; hata, eksik ve yavaşlığı bulur, küçük düzeltmeleri kendisi yapar, "
           "öğrendiklerini not eder."},
    {"kod": "elif", "ad": "Elif", "unvan": "Telegram asistanı", "ikon": "forum",
     "ne_zaman": "Mesaj gelince, yaklaşık 1 dakikada",
     "is": "Telegram'dan sorulan satış, kâr, stok, ödeme sorularını programın kendi hesabıyla cevaplar."},
    {"kod": "kerem", "ad": "Kerem", "unvan": "Pazar araştırmacısı", "ikon": "travel_explore",
     "ne_zaman": "Her pazartesi 06:47",
     "is": "Çok satan ürünlerin rakip fiyatlarını, yeni ürünleri, navlun, kur ve mevzuat haberlerini tarar."},
    {"kod": "hakan", "ad": "Hakan", "unvan": "Gümrük danışmanı", "ikon": "gavel",
     "ne_zaman": "Sorgu gelince; hafta içi 09-17 arası iki saatte bir",
     "is": "İthal edilecek ürün için GTİP önerisi, vergi oranları, ek vergiler ve gereken belgeleri araştırır."},
]
AD = {c["kod"]: c["ad"] for c in CALISANLAR}

_TR = timezone(timedelta(hours=3))


def _zaman(iso):
    try:
        z = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if z.tzinfo is None:
            z = z.replace(tzinfo=timezone.utc)
        return z.astimezone(_TR)
    except (TypeError, ValueError):
        return None


def _tr(iso, saat=True):
    z = _zaman(iso)
    return z.strftime("%d.%m %H:%M" if saat else "%d.%m.%Y") if z else ""


def durumlar(bt_raporlar=None, telegram_harita=None, pazar_raporlari=None, gumruk_sorgulari=None):
    """Kart durumları: {kod: {"durum": "calisiyor"|"sirada"|"bekliyor"|"kurulum", "metin": str}}.
    Girdiler None ise (tablo okunamadı) 'kurulum' sayılır."""
    out = {}
    if bt_raporlar is None:
        out["serkan"] = {"durum": "kurulum", "metin": "Rapor tablosu okunamadı"}
    else:
        son = next((r for r in bt_raporlar if r.get("tur") == "calisma"), None)
        out["serkan"] = ({"durum": "calisiyor", "metin": f"Son kontrol {_tr(son.get('zaman'))}"} if son
                         else {"durum": "bekliyor", "metin": "İlk gece kontrolünü bekliyor"})
    n = len(telegram_harita or {})
    out["elif"] = ({"durum": "calisiyor", "metin": f"{n} hesap bağlı"} if n
                   else {"durum": "kurulum", "metin": "Kurulum ve hesap bağlama bekliyor"})
    if pazar_raporlari is None:
        out["kerem"] = {"durum": "kurulum", "metin": "Rapor tablosu okunamadı"}
    elif pazar_raporlari:
        out["kerem"] = {"durum": "calisiyor",
                        "metin": f"Son rapor {_tr(pazar_raporlari[0].get('zaman'), saat=False)}"}
    else:
        out["kerem"] = {"durum": "bekliyor", "metin": "İlk rapor pazartesi sabahı"}
    if gumruk_sorgulari is None:
        out["hakan"] = {"durum": "kurulum", "metin": "Sorgu tablosu okunamadı"}
    else:
        sira = sum(1 for s in gumruk_sorgulari if s.get("durum") in ("bekliyor", "calisiyor"))
        son = next((s for s in gumruk_sorgulari if s.get("durum") == "tamam"), None)
        if sira:
            out["hakan"] = {"durum": "sirada", "metin": f"{sira} sorgu sırada"}
        elif son:
            out["hakan"] = {"durum": "calisiyor", "metin": f"Son cevap {_tr(son.get('guncelleme') or son.get('zaman'))}"}
        else:
            out["hakan"] = {"durum": "bekliyor", "metin": "Henüz sorgu yok"}
    return out
