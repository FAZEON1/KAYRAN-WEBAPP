# -*- coding: utf-8 -*-
"""KAYRAN — Telegram bildirim katmanı.

Uygulama içinden (Streamlit) Telegram'a mesaj gönderir.

═══ TASARIM İLKELERİ ═══════════════════════════════════════════════════
1) BİLDİRİM HATASI İŞLEMİ ASLA BOZMAZ.
   Her gönderim try/except ile sarılıdır ve (ok, mesaj) döner. Telegram
   erişilemezse sipariş yine kaydedilir; sadece bildirim gitmez.

2) KISA ZAMAN AŞIMI.
   Gönderim, kaydetme akışının içinde çalıştığı için 4 saniyede kesilir.
   Telegram yavaşlasa bile kullanıcı ekran başında beklemez.

3) TOKEN KODA YAZILMAZ.
   Önce Streamlit Secrets, sonra ortam değişkeni okunur. Böylece aynı
   modül hem uygulamada hem GitHub Actions betiklerinde çalışır.

Secrets yapılandırması (.streamlit/secrets.toml):

    [telegram]
    bot_token = "123456:ABC-DEF..."
    chat_id   = "-1001234567890"        # birden fazlaysa virgülle ayır
    aktif     = true                    # false → tüm bildirimler kapanır
"""
import os

_ZAMAN_ASIMI = 4          # saniye — kaydetme akışını bekletmemek için kısa
_API = "https://api.telegram.org/bot{token}/sendMessage"


def _ayar(anahtar, varsayilan=None):
    """Önce Streamlit Secrets, sonra ortam değişkeni."""
    try:
        import streamlit as st
        blok = st.secrets.get("telegram", {})
        if anahtar in blok:
            return blok[anahtar]
    except Exception:
        pass
    return os.environ.get(f"TELEGRAM_{anahtar.upper()}", varsayilan)


def aktif_mi():
    """Bildirimler açık ve token tanımlı mı?"""
    _a = _ayar("aktif", True)
    if isinstance(_a, str):
        _a = _a.strip().lower() not in ("false", "0", "hayir", "hayır", "kapali", "kapalı")
    return bool(_a) and bool(_ayar("bot_token")) and bool(_ayar("chat_id"))


def gonder(metin, chat_id=None, sessiz=False):
    """Telegram'a mesaj gönderir. Döner: (ok, mesaj).

    ASLA istisna fırlatmaz — çağıran akışı bozmaz.
    sessiz=True: bildirim sesi çalmaz (gece gönderimleri için).
    """
    token = _ayar("bot_token")
    hedef = chat_id or _ayar("chat_id")
    if not token or not hedef:
        return False, "Telegram yapılandırılmamış (bot_token / chat_id yok)"
    if not aktif_mi() and chat_id is None:
        return False, "Telegram bildirimleri kapalı"
    try:
        import requests
    except Exception:
        return False, "requests kurulu değil"

    basarili, hatalar = 0, []
    for c in [x.strip() for x in str(hedef).split(",") if x.strip()]:
        try:
            r = requests.post(
                _API.format(token=token),
                json={"chat_id": c, "text": metin, "parse_mode": "HTML",
                      "disable_web_page_preview": True,
                      "disable_notification": bool(sessiz)},
                timeout=_ZAMAN_ASIMI)
            if r.status_code == 200:
                basarili += 1
            else:
                hatalar.append(f"{c}: HTTP {r.status_code}")
        except Exception as e:
            hatalar.append(f"{c}: {type(e).__name__}")
    if basarili:
        return True, f"{basarili} alıcıya gönderildi"
    return False, "; ".join(hatalar) or "gönderilemedi"


def kacis(s):
    """Telegram HTML modu için kaçış (&, <, > özel karakterdir)."""
    return (str(s or "").replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;"))
