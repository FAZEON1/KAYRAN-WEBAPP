# -*- coding: utf-8 -*-
"""Oturum belirteci (yeni uygulama, Faz 0): imzalı, süreli, tarayıcıda HttpOnly çerezde durur.

Biçim: base64url(json{"k": kullanıcı, "son": bitiş unix sn, "s": 1}) + "." + base64url(HMAC-SHA256).
Anahtar OTURUM_ANAHTARI ortam değişkeninden (Render'da kendiliğinden üretilir); yoksa API giriş
kabul etmez. Belirteç şifre ya da yetki taşımaz: yetkiler her istekte veritabanından okunur, böylece
pasife alınan kullanıcı en geç bir dakikada (yetki önbelleği) dışarıda kalır.
"""
import base64
import hashlib
import hmac
import json
import time

CEREZ = "kayran_oturum"
SURE_SN = 12 * 3600          # bir iş günü
SURUM = 1


def _b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64_coz(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _imza(govde, anahtar):
    return _b64(hmac.new(anahtar.encode("utf-8"), govde.encode("ascii"), hashlib.sha256).digest())


def uret(kullanici, anahtar, simdi=None, sure=SURE_SN):
    """Belirteç üretir. Anahtar boş ya da kısaysa ValueError (imzasız oturum açılmasın)."""
    if not anahtar or len(anahtar) < 32:
        raise ValueError("OTURUM_ANAHTARI en az 32 karakter olmalı")
    son = int((time.time() if simdi is None else simdi) + sure)
    govde = _b64(json.dumps({"k": str(kullanici), "son": son, "s": SURUM}, separators=(",", ":")).encode("utf-8"))
    return f"{govde}.{_imza(govde, anahtar)}"


def coz(belirtec, anahtar, simdi=None):
    """Geçerliyse kullanıcı adını, değilse (bozuk, imza tutmuyor, süresi geçmiş) None döner."""
    if not belirtec or not anahtar or len(anahtar) < 32 or belirtec.count(".") != 1:
        return None
    govde, imza = belirtec.split(".", 1)
    if not hmac.compare_digest(imza, _imza(govde, anahtar)):
        return None
    try:
        v = json.loads(_b64_coz(govde))
    except (ValueError, TypeError):
        return None
    if v.get("s") != SURUM or not isinstance(v.get("son"), int):
        return None
    if v["son"] <= (time.time() if simdi is None else simdi):
        return None
    return str(v.get("k") or "") or None
