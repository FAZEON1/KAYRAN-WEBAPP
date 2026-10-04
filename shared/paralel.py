# -*- coding: utf-8 -*-
"""Bağımsız okumaları AYNI ANDA yapmak (Ekim 2026, hızlandırma).

Program ABD'de, veritabanı Frankfurt'ta: her istek ~0,2-0,3 sn. Birbirinden bağımsız beş okuma
sırayla 1-1,5 sn sürer, aynı anda ~0,3 sn. Burada çalıştırılan işler genellikle önbellekli okuma
fonksiyonlarıdır: iş bitince sonuç önbellekte durur, sayfa aynı fonksiyonu çağırınca anında alır.
Rakam ve hesap değişmez; yalnız sıra (bekleme) değişir.

Kural: iş başarısız olursa hata yutulur (None) — sayfa aynı fonksiyonu kendisi çağırınca hatayı
eskisi gibi kendi yolunda ele alır.
"""
import threading


def _baglam():
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx()
    except Exception:  # noqa: BLE001
        return None


def basla(isler):
    """isler: [(fonksiyon, args…)] ya da [fonksiyon]. Arka planda başlatır; döner: bekle() —
    çağrılınca işler bitene kadar bekler ve sonuç listesini (hata → None) verir."""
    ctx = _baglam()
    sonuc = [None] * len(isler)

    def _calis(i, fn, args):
        try:
            sonuc[i] = fn(*args)
        except Exception:  # noqa: BLE001
            sonuc[i] = None

    ipler = []
    for i, is_ in enumerate(isler):
        fn, args = (is_[0], tuple(is_[1:])) if isinstance(is_, (tuple, list)) else (is_, ())
        t = threading.Thread(target=_calis, args=(i, fn, args), daemon=True)
        if ctx is not None:
            try:
                from streamlit.runtime.scriptrunner import add_script_run_ctx
                add_script_run_ctx(t, ctx)
            except Exception:  # noqa: BLE001
                pass
        t.start()
        ipler.append(t)

    def bekle(sure=None):
        for t in ipler:
            t.join(sure)
        return sonuc
    return bekle


def hepsi(isler):
    """İşleri aynı anda çalıştırır, hepsi bitince sonuç listesini döner."""
    return basla(isler)()
