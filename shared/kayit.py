# -*- coding: utf-8 -*-
"""KAYRAN — Yutulan hataları görünür kılan hafif kayıt katmanı.

NEDEN: Kodda yüzlerce `except Exception: pass` vardı. Kullanıcıyı durdurmamak
doğru, ama hata hiçbir yere düşmeyince "neden olmadı?" sorusunun cevabı
yoktu. `sessiz(yer, hata)` hatayı yine yutar (akış aynı kalır), ama sunucu
günlüğüne (Streamlit Cloud → Manage app → Logs) bir satır yazar.

shared.hata_log.kaydet'ten farkı:
  · kaydet()  → veritabanına yazar (hata_kayitlari), kritik olanı Telegram'a.
                Ağ çağrısı yapar; para/stok gibi seyrek ve önemli yerler için.
  · sessiz()  → yalnız stdlib logging (+ kuruluysa Sentry). Veritabanına
                YAZMAZ; döngüde/sıcak yolda da güvenle çağrılabilir.

KURALLAR
  · sessiz() ASLA istisna fırlatmaz.
  · Aynı (yer, hata türü) süreç başına en çok TEKRAR_SINIRI kez yazılır;
    sonra yalnız 100., 1000., ... tekrarda bir özet satırı (log seli olmasın).
  · Yığın izi (traceback) yalnız DEBUG düzeyinde yazılır.
  · Düzey ortam değişkeninden: KAYRAN_LOG_DUZEYI=DEBUG|INFO|WARNING|ERROR
    (varsayılan WARNING).

İSTEĞE BAĞLI SENTRY
  `sentry_sdk` kuruluysa VE `st.secrets["sentry"]["dsn"]` ya da SENTRY_DSN
  ortam değişkeni varsa başlatılır; sessiz()'e düşen WARNING düzeyindeki
  hatalar Sentry'ye de gider (aynı tekrar sınırıyla). Biri eksikse hiçbir şey
  yapılmaz. requirements.txt'ye sentry-sdk eklemek kullanıcının kararıdır.
"""
import logging
import os
import sys
import threading

KOK_LOGGER = "kayran"
TEKRAR_SINIRI = 5            # aynı yer+tür için süreç başına tam satır sayısı
_ANAHTAR_SINIRI = 5000       # sayaç sözlüğü bellek sınırı

_sayac = {}
_kilit = threading.Lock()
_yapilandirildi = False
_sentry_aktif = False

_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def _duzey_coz(deger, varsayilan=logging.WARNING):
    if isinstance(deger, int):
        return deger
    d = str(deger or "").strip().upper()
    return {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING,
            "UYARI": logging.WARNING, "ERROR": logging.ERROR, "HATA": logging.ERROR,
            "CRITICAL": logging.CRITICAL}.get(d, varsayilan)


def _sentry_dsn():
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if dsn:
        return dsn
    try:
        import streamlit as st
        bolum = st.secrets.get("sentry") if hasattr(st, "secrets") else None
        if bolum:
            return str(bolum.get("dsn") or "").strip()
    except Exception:
        return ""
    return ""


def sentry_baslat():
    """Sentry'yi kuruluysa ve DSN varsa başlat. Döner: True (aktif) / False.
    Hiçbir durumda istisna fırlatmaz; eksik parça varsa sessizce False."""
    global _sentry_aktif
    if _sentry_aktif:
        return True
    try:
        dsn = _sentry_dsn()
        if not dsn:
            return False
        try:
            import sentry_sdk
        except ImportError:
            return False
        sentry_sdk.init(
            dsn=dsn,
            send_default_pii=False,          # kullanıcı/IP gönderme
            traces_sample_rate=0.0,          # yalnız hata, performans izi yok
            environment=os.environ.get("KAYRAN_ORTAM", "canli"),
        )
        _sentry_aktif = True
        return True
    except Exception:
        return False


def yapilandir():
    """Tek seferlik logging yapılandırması (idempotent). Uygulama açılışında
    çağrılması yeterli; çağrılmasa da ilk sessiz() çağrısı yapar."""
    global _yapilandirildi
    if _yapilandirildi:
        return
    _yapilandirildi = True
    try:
        lg = logging.getLogger(KOK_LOGGER)
        lg.setLevel(_duzey_coz(os.environ.get("KAYRAN_LOG_DUZEYI")))
        if not any(getattr(h, "_kayran", False) for h in lg.handlers):
            h = logging.StreamHandler(sys.stderr)
            h.setFormatter(logging.Formatter(_FORMAT))
            h._kayran = True
            lg.addHandler(h)
        lg.propagate = False             # kök logger'da ikinci kez basılmasın
    except Exception:
        pass
    sentry_baslat()


def baslat():
    """app.py açılışı için: logging + (varsa) Sentry."""
    yapilandir()
    return _sentry_aktif


def _say(anahtar):
    """Bu anahtarın kaçıncı görülüşü (1'den başlar)."""
    with _kilit:
        n = _sayac.get(anahtar, 0) + 1
        if n == 1 and len(_sayac) >= _ANAHTAR_SINIRI:
            _sayac.clear()
        _sayac[anahtar] = n
    return n


def _ozet_mi(n):
    """TEKRAR_SINIRI aşıldıktan sonra 100, 1000, 10000... tekrarda özet."""
    if n < 100:
        return False
    while n % 10 == 0:
        n //= 10
    return n == 1


def sessiz(yer, hata, duzey=logging.WARNING):
    """Yutulan hatayı günlüğe yaz. Akışı DEĞİŞTİRMEZ, asla fırlatmaz, None döner.

    yer  : 'ithalat.teslim_stok_isle' gibi kısa konum (modul.fonksiyon)
    hata : Exception ya da metin
    duzey: logging düzeyi ya da 'debug'/'warning' metni (beklenen, zararsız
           durumlar için 'debug')."""
    try:
        if not _yapilandirildi:
            yapilandir()
        seviye = _duzey_coz(duzey)
        yer = str(yer)
        tur = type(hata).__name__ if isinstance(hata, BaseException) else "Uyari"
        lg = logging.getLogger(f"{KOK_LOGGER}.{yer.split('.', 1)[0] or 'genel'}")
        if not lg.isEnabledFor(seviye):
            return None
        n = _say((yer, tur))
        if n > TEKRAR_SINIRI:
            if _ozet_mi(n):
                lg.log(seviye, "%s: %s %d kez tekrarlandı (ayrıntı bastırıldı)", yer, tur, n)
            return None
        mesaj = str(hata)[:500]
        lg.log(seviye, "%s: %s: %s%s", yer, tur, mesaj,
               " (bundan sonrası bastırılır)" if n == TEKRAR_SINIRI else "")
        if isinstance(hata, BaseException) and lg.isEnabledFor(logging.DEBUG):
            lg.debug("%s yığın izi", yer, exc_info=(type(hata), hata, hata.__traceback__))
        if _sentry_aktif and seviye >= logging.WARNING and isinstance(hata, BaseException):
            try:
                import sentry_sdk
                kapsam_ac = getattr(sentry_sdk, "new_scope", None) or sentry_sdk.push_scope
                with kapsam_ac() as kapsam:
                    kapsam.set_tag("yer", yer)
                    sentry_sdk.capture_exception(hata)
            except Exception:
                pass
    except Exception:
        pass
    return None


def _sifirla():
    """Yalnız testler için: sayaçları ve yapılandırma bayrağını sıfırla."""
    global _yapilandirildi, _sentry_aktif
    with _kilit:
        _sayac.clear()
    _yapilandirildi = False
    _sentry_aktif = False
