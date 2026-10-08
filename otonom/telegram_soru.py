# -*- coding: utf-8 -*-
"""Telegram asistanı — gelen soruya programın soru kutusuyla cevap (Ekim 2026).

Akış (anlık, ~1 dk): Telegram → Supabase fonksiyonu telegram-webhook (kaynak: veritabani/fonksiyonlar) → GitHub
repository_dispatch 'telegram_soru' → .github/workflows/telegram-soru.yml → bu betik → Telegram.
Cevap shared.soru + shared.soru_cevap'tan gelir: programdaki "Soru sor" ile aynı motor, aynı rakam.
YALNIZ OKUR; hiçbir iş kaydını değiştirmez (soru_kayitlari'na soru metni yazılır).

Güvenlik: yalnız Sistem › Ofis › Elif bölümünde bir program kullanıcısına bağlanmış Telegram kimlikleri cevap
alır ve o kullanıcının modül yetkileri / kâr görünürlüğü geçerlidir. Tanımsız kimliğe yalnız kendi
kimliği söylenir.

Ortam: PAYLOAD (JSON: chat_id, kimlik, metin), TELEGRAM_BOT_TOKEN; Supabase erişimi iş akışının yazdığı
.streamlit/secrets.toml'dan. Kurulum: `python otonom/telegram_soru.py --kurulum` (SUPABASE_URL de gerekir)
Telegram'a webhook adresini ve gizli değeri bildirir.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

KULLANICI_ANAHTAR = "telegram_kullanicilar"
GIZLI_ANAHTAR = "telegram_webhook_gizli"
FONKSIYON = "/functions/v1/telegram-webhook"


def _sb():
    from shared.auth import _get_supabase
    return _get_supabase()


def ayar(anahtar, varsayilan=None):
    try:
        r = _sb().table("sistem_ayarlari").select("deger").eq("anahtar", anahtar).limit(1).execute().data or []
        return r[0].get("deger") if r else varsayilan
    except Exception:  # noqa: BLE001
        return varsayilan


def _telegram(yontem, govde):
    import requests
    r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{yontem}",
                      json=govde, timeout=20)
    if not r.ok:
        print(f"Telegram {yontem}: {r.status_code} {r.text[:200]}")
    return r


def gonder(chat_id, metin, yanit_id=None):
    g = {"chat_id": chat_id, "text": metin, "parse_mode": "HTML", "disable_web_page_preview": True}
    if yanit_id:
        g["reply_parameters"] = {"message_id": yanit_id, "allow_sending_without_reply": True}
    _telegram("sendMessage", g)


def cevap_uret(metin, kullanici):
    """Soru metni → Telegram HTML. Soru kutusunun kendi akışı (coz → cevapla)."""
    from shared.asistan_hesap import anlasilmadi_metni, telegram_yanit
    from shared.kar_gizle import kar_gorunur_kullanici
    from shared.soru import coz
    from shared.soru_cevap import cevapla, sozluk_kur
    from shared.yetki import MODULLER, moduller
    n = coz(metin, sozluk_kur())
    try:
        _sb().table("soru_kayitlari").insert({"kullanici": kullanici, "metin": metin[:500],
                                              "anlasildi": bool(n.get("tip")), "konu": n.get("tip")}).execute()
    except Exception:  # noqa: BLE001
        pass
    if not n.get("tip"):
        return anlasilmadi_metni()
    izin = moduller(kullanici, {m: False for m in MODULLER})
    izin["kar"] = kar_gorunur_kullanici(kullanici)
    return telegram_yanit(cevapla(n, izin)) or anlasilmadi_metni()


def isle(p):
    from shared.asistan_hesap import kimlik_kullanici, komut, yardim_metni
    from shared.soru import ORNEKLER
    chat_id, kimlik = p.get("chat_id"), p.get("kimlik")
    metin = str(p.get("metin") or "").strip()[:500]
    if not chat_id or not metin:
        return
    try:
        harita = json.loads(ayar(KULLANICI_ANAHTAR, "{}") or "{}")
    except ValueError:
        harita = {}
    kullanici = kimlik_kullanici(harita, kimlik)
    if not kullanici or komut(metin) in ("start", "yardim", "help", "kimlik"):
        gonder(chat_id, yardim_metni(ORNEKLER, kimlik, kullanici))
        return
    try:
        cevap = cevap_uret(metin, kullanici)
    except Exception as e:  # noqa: BLE001
        try:
            from shared.hata_log import kaydet
            kaydet("telegram.soru", e)
        except Exception:  # noqa: BLE001
            pass
        print("HATA:", type(e).__name__, str(e)[:200])
        cevap = "Cevap hazırlanırken bir sorun oldu; programdaki Soru sor sayfasından bakabilirsin."
    gonder(chat_id, cevap, p.get("mesaj_id"))


def kurulum():
    gizli = ayar(GIZLI_ANAHTAR)
    if not gizli:
        print("HATA: sistem_ayarlari'nda telegram_webhook_gizli yok (veritabani/25_asistanlar.sql kurulmalı).")
        return 1
    url = os.environ["SUPABASE_URL"].rstrip("/") + FONKSIYON
    r = _telegram("setWebhook", {"url": url, "secret_token": gizli, "allowed_updates": ["message"],
                                 "drop_pending_updates": True})
    print("setWebhook:", r.status_code, r.json().get("description") if r.ok else "")
    bilgi = _telegram("getWebhookInfo", {}).json().get("result", {})
    print("Webhook adresi:", bilgi.get("url"), "· bekleyen:", bilgi.get("pending_update_count"),
          "· son hata:", bilgi.get("last_error_message") or "yok")
    return 0 if r.ok else 1


def main(argv):
    if "--kurulum" in argv:
        return kurulum()
    isle(json.loads(os.environ.get("PAYLOAD") or "{}"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
