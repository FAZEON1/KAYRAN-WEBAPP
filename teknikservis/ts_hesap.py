# -*- coding: utf-8 -*-
"""Teknik Servis — saf hesaplar (Ekim 2026). Veritabanına gitmez, test edilir.

  ilk_gecis_haritasi  ts_gecmis satırlarından {kayit_id: {durum: ilk geçiş tarihi}}
  sla_kademe          iş günü → (grup adı, RENK anahtarı, sıra)
  sla_gruplari        kayıtları SLA kademesine göre (en acil önce) gruplar
  depo_gruplari       kayıtları depo sırasına göre gruplar
  sayi_ya_da_bos      Excel sayı sütunu: boş/metin → None, sayı → float
  excel_bayt          satır sözlükleri → .xlsx baytları
"""
from io import BytesIO


def ilk_gecis_haritasi(gecmis_rows):
    """Satırlar tarihe göre sıralı gelmese de her durum için EN ERKEN tarihi tutar."""
    h = {}
    for r in gecmis_rows or []:
        kid, durum, tarih = r.get("kayit_id"), str(r.get("durum") or ""), r.get("tarih")
        if kid is None or not tarih:
            continue
        d = h.setdefault(kid, {})
        if durum not in d or str(tarih) < str(d[durum]):
            d[durum] = tarih
    return h


_KADEMELER = [            # (alt sınır, grup adı, renk) — en acil önce
    (16, "16+ iş günü", "kirmizi"),
    (11, "11–15 iş günü", "kirmizi2"),
    (6, "6–10 iş günü", "amber"),
    (0, "0–5 iş günü", "yesil"),
]


def sla_kademe(is_gunu, bitmis=False):
    """Döner: (grup adı, RENK anahtarı, sıra). Sıra küçük = daha acil."""
    if bitmis:
        return "Tamamlanan", "silik", len(_KADEMELER)
    g = int(is_gunu or 0)
    for i, (alt, ad, renk) in enumerate(_KADEMELER):
        if g >= alt:
            return ad, renk, i
    return _KADEMELER[-1][1], _KADEMELER[-1][2], len(_KADEMELER) - 1


def sla_gruplari(kayitlar, gun_fn, bitmis_fn=lambda k: False):
    """[(grup adı, [kayıt…])] — gruplar en acilden başlar, grup içinde gelen sıra korunur."""
    gr = {}
    for k in kayitlar:
        ad, _r, sira = sla_kademe(gun_fn(k), bitmis_fn(k))
        gr.setdefault((sira, ad), []).append(k)
    return [(ad, ks) for (_s, ad), ks in sorted(gr.items(), key=lambda x: x[0][0])]


def depo_gruplari(kayitlar, depo_sirasi):
    """[(depo, [kayıt…])] — bilinen depolar verilen sırada, bilinmeyenler sonda."""
    gr = {}
    for k in kayitlar:
        gr.setdefault((k.get("depo") or "").strip() or "—", []).append(k)
    sira = {d: i for i, d in enumerate(depo_sirasi)}
    return sorted(gr.items(), key=lambda x: (sira.get(x[0], len(sira)), x[0]))


def sayi_ya_da_bos(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def excel_bayt(satirlar, sayfa_adi):
    import pandas as pd
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame(satirlar).to_excel(w, index=False, sheet_name=str(sayfa_adi)[:28] or "Sayfa")
    return buf.getvalue()
