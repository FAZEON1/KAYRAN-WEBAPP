# -*- coding: utf-8 -*-
"""Türkiye resmi tatilleri — tek kaynak (Ekim 2026).

Kullanan: izin günü sayımı (shared.izin_hesap) ve ana sayfadaki "yaklaşan tatil" sayacı (gunluk.py).

Kaynak: 2429 sayılı Ulusal Bayram ve Genel Tatiller Hakkında Kanun. Arife günleri ve 28 Ekim saat
13.00'ten sonra yarım gün tatildir (izin sayımında 0,5 gün). Dini bayram tarihleri Diyanet İşleri
Başkanlığı takviminden (vakithesaplama.diyanet.gov.tr "Dini Günler"), 2025–2028 doğrulandı.
Yeni yıl eklenirken DINI_BAYRAMLAR'a yalnız 1. gün yazılır; arife ve diğer günler hesaplanır.
"""
from datetime import date, timedelta

# (ay, gün, ad) — her yıl aynı tarih
SABIT = [
    (1, 1, "Yılbaşı"),
    (4, 23, "Ulusal Egemenlik ve Çocuk Bayramı"),
    (5, 1, "Emek ve Dayanışma Günü"),
    (5, 19, "Atatürk'ü Anma, Gençlik ve Spor Bayramı"),
    (7, 15, "Demokrasi ve Millî Birlik Günü"),
    (8, 30, "Zafer Bayramı"),
    (10, 29, "Cumhuriyet Bayramı"),
]

# yıl → (Ramazan Bayramı 1. gün, Kurban Bayramı 1. gün). Ramazan 3 gün, Kurban 4 gün; arife bir gün önce.
DINI_BAYRAMLAR = {
    2025: (date(2025, 3, 30), date(2025, 6, 6)),
    2026: (date(2026, 3, 20), date(2026, 5, 27)),
    2027: (date(2027, 3, 9), date(2027, 5, 16)),
    2028: (date(2028, 2, 26), date(2028, 5, 5)),
}
ILK_YIL, SON_YIL = min(DINI_BAYRAMLAR), max(DINI_BAYRAMLAR)

TAM, YARIM = 1.0, 0.5


def yil_tatilleri(yil):
    """{tarih: (ad, oran)} — oran 1 tam gün, 0,5 yarım gün (arife, 28 Ekim öğleden sonra).
    Dini bayramı tanımlı olmayan yılda yalnız sabit tatiller döner (bilinen_yil ile denetlenir)."""
    t = {date(yil, a, g): (ad, TAM) for a, g, ad in SABIT}
    t[date(yil, 10, 28)] = ("Cumhuriyet Bayramı arifesi", YARIM)
    db = DINI_BAYRAMLAR.get(yil)
    if db:
        for ilk, ad, gun in ((db[0], "Ramazan Bayramı", 3), (db[1], "Kurban Bayramı", 4)):
            t.setdefault(ilk - timedelta(days=1), (f"{ad} arifesi", YARIM))
            for i in range(gun):
                t[ilk + timedelta(days=i)] = (f"{ad} {i + 1}. gün", TAM)   # bayram sabit tatille çakışırsa tam gün
    return t


def bilinen_yil(yil):
    """Dini bayram tarihleri tanımlı mı (izin sayımı bu yıl için eksiksiz mi)."""
    return yil in DINI_BAYRAMLAR


def tatil(gun):
    """(ad, oran) ya da None."""
    return yil_tatilleri(gun.year).get(gun)


def ilk_gunler():
    """Ana sayfa sayacı için: her tatilin ilk günü, sıralı [(iso, ad)]. Arifeler ve bayramın sonraki
    günleri sayılmaz (sayaç "Ramazan Bayramı" der, "1. gün" demez)."""
    out = []
    for yil in range(ILK_YIL, SON_YIL + 1):
        for g, (ad, oran) in sorted(yil_tatilleri(yil).items()):
            if oran < TAM:
                continue
            if ad.endswith(" gün"):
                if not ad.endswith(" 1. gün"):
                    continue
                ad = ad[:-len(" 1. gün")]
            out.append((g.isoformat(), ad))
    return out
