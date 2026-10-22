# -*- coding: utf-8 -*-
"""Alınan destekler Mikro'dan (Ekim 2026). Kullanıcı (21.10.2026): "9 Mikro'dan çekilsin" — Mikro esas.

Alınan destek (tedarikçiden / markadan gelen destek, sell-out, rebate, MIO'nun aylık hizmet bedeli …) Mikro'da
602 "diğer gelirler" hesaplarına işlenir (canlı 2026: 602.02.001 aylık ~33–73 bin TL = MIO 750 €, 602.02.002
pazarlama destekleri). 2026'dan itibaren P&L'deki "Alınan destek" bu hesaplardan gelir: ay ay (alacak − borç), TL,
o ayın ortalama kuruyla $'a çevrilir. Uygulamadaki alinan_destekler kayıtları (elle / Excel) 2026'dan önceki aylar
için kullanılmaya devam eder; 2026 ve sonrası için yeni kayıt açılmaz (iki kez sayılmasın).
21.10.2026 karşılaştırması: Ocak–Eylül uygulama ≈ 80 bin $, Mikro 602 3,06 M TL ≈ 73–75 bin $ (aylar arası tarih
kayması; toplam tutuyor).

Kapatmak: sistem_ayarlari mikro_alinan_durum = {"acik": false} (varsayılan AÇIK).
Yıl sonu: Aralık'ta 602'yi 690'a kapatan mahsup fişi ayıklanır (kayranacc/mikro_yil_sonu.py, 22.10.2026).
"""
from collections import defaultdict

import streamlit as st

ILK_AY = "2026-01"
HESAP_ONEK = "602"
DURUM_ANAHTAR = "mikro_alinan_durum"
SAYFA = 1000
KURUS = 0.005


def _f(v, d=0.0):
    try:
        x = float(v)
        return x if x == x else d
    except (TypeError, ValueError):
        return d


def aylik(satirlar):
    """mikro_muhasebe_ay satırları → {"YYYY-MM": {hesap: TL}} (602 hesapları, alacak − borç)."""
    out = defaultdict(lambda: defaultdict(float))
    for r in satirlar or []:
        kod = str(r.get("hesap_kod") or "").strip()
        if not (kod == HESAP_ONEK or kod.startswith(HESAP_ONEK + ".")):
            continue
        ay = f"{int(_f(r.get('yil'))):04d}-{int(_f(r.get('ay'))):02d}"
        if ay < ILK_AY:
            continue
        out[ay][kod] += _f(r.get("alacak")) - _f(r.get("borc"))
    return {a: {k: round(v, 2) for k, v in h.items() if abs(v) >= KURUS} for a, h in out.items()}


def ay_kuru(kurlar, ay, yedek=0.0):
    """{"YYYY-MM-DD": kur} içinden o ayın ortalama kuru; yoksa yedek."""
    v = [k for t, k in (kurlar or {}).items() if str(t)[:7] == ay and _f(k) > 0]
    return sum(v) / len(v) if v else _f(yedek)


def usd_satirlari(aylar, bas, bit, kurlar, yedek_kur, adlar=None):
    """[bas, bit] (YYYY-MM) aylarının satırları: [{donem, hesap, ad, tl, usd}]. Kur yoksa usd None."""
    adlar = adlar or {}
    out = []
    for ay in sorted(aylar or {}):
        if not (bas <= ay <= bit):
            continue
        kur = ay_kuru(kurlar, ay, yedek_kur)
        for kod, tl in sorted(aylar[ay].items()):
            out.append({"donem": ay, "hesap": kod, "ad": adlar.get(kod) or kod, "tl": tl,
                        "usd": round(tl / kur, 4) if kur > 0 else None})
    return out


# ── Veritabanı ─────────────────────────────────────────────────────
def durum():
    try:
        from kayranacc.database import get_ayar
        return get_ayar(DURUM_ANAHTAR, {}) or {}
    except Exception:  # noqa: BLE001
        return {}


def acik_mi():
    """Varsayılan AÇIK (kullanıcı kararı); yalnız {"acik": false} kapatır."""
    return durum().get("acik", True) is not False


@st.cache_data(ttl=300, show_spinner=False)
def _oku():
    """602 satırları yıl sonu kapanış fişi ayıklanmış (kayranacc/mikro_yil_sonu): Aralık'ta 602'yi 690'a kapatan
    mahsup fişi alınmaz, Aralık desteği sıfır / eksi görünmez."""
    from kayranacc.database import get_client
    from kayranacc.mikro_yil_sonu import oku as _ys_oku
    cli = get_client()
    out, _turlu = _ys_oku(cli, (HESAP_ONEK,), int(ILK_AY[:4]))
    adlar = {str(r.get("muh_hesap_kod")): str(r.get("muh_hesap_isim1") or "") for r in
             (cli.table("mikro_hesap_plani").select("muh_hesap_kod,muh_hesap_isim1").like("muh_hesap_kod", "602%")
              .execute().data or [])}
    return aylik(out), adlar


def mikro_satirlari(bas, bit):
    """[bas, bit] (YYYY-MM) için Mikro 602 satırları ($). Okunamazsa None (çağıran eski kaynağa düşer)."""
    try:
        from kayranacc.database import get_kur, get_kur_araligi
        aylar, adlar = _oku()
        kurlar = get_kur_araligi(f"{bas}-01", f"{bit}-31")
        return usd_satirlari(aylar, max(bas, ILK_AY), bit, kurlar, get_kur() or 0, adlar)
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("kayranacc.mikro_alinan.mikro_satirlari", e)
        return None
