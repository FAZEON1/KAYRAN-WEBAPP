# -*- coding: utf-8 -*-
"""Mikro eşitleme turu kilidi (Ekim 2026). Veritabanı: veritabani/52_mikro_tur_kilidi.sql.

Tur iki yerden çalışır (GitHub işi ve uygulamanın arka plan iş parçacığı; uygulamanın birden çok sunucu örneği
olabilir). Kilitsiz iki tur aynı anda çalışınca çek listesi iki katına çıkabilir, satış satırı ya da Mikro'dan yeni
ithalat dosyası iki kez eklenebilirdi (21.10.2026 denetimi). Tur başında süreli kilit alınır; alamayan tur atlanır.
Kilit fonksiyonu kurulu değilse (eski veritabanı) tur kilitsiz çalışır — eşitleme durmaz.
"""
import os
import socket
import uuid
from contextlib import contextmanager

KILIT_ADI = "mikro_esitle"
SURE_SN = 600


def sahip_adi(kaynak=""):
    return f"{kaynak or 'tur'}:{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


def _cli():
    from kayranacc.database import get_client
    return get_client()


def al(sahip, sure_sn=SURE_SN, cli=None):
    """True: kilit alındı ya da kilit fonksiyonu kurulu değil (kilitsiz devam). False: başka tur çalışıyor."""
    try:
        r = (cli or _cli()).rpc("mikro_kilit_al", {"p_ad": KILIT_ADI, "p_sahip": sahip, "p_sn": int(sure_sn)}).execute()
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("shared.mikro_kilit.al", e, "debug")
        return True
    v = r.data
    if isinstance(v, list):
        v = v[0] if v else None
    if isinstance(v, dict):
        v = next(iter(v.values()), None)
    return bool(v) if v is not None else True


def birak(sahip, cli=None):
    try:
        (cli or _cli()).rpc("mikro_kilit_birak", {"p_ad": KILIT_ADI, "p_sahip": sahip}).execute()
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("shared.mikro_kilit.birak", e, "debug")


@contextmanager
def tur_kilidi(kaynak="", sure_sn=SURE_SN):
    """with tur_kilidi("github") as alindi: if not alindi: atla."""
    sahip = sahip_adi(kaynak)
    alindi = al(sahip, sure_sn)
    try:
        yield alindi
    finally:
        if alindi:
            birak(sahip)
