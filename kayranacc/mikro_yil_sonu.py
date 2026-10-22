# -*- coding: utf-8 -*-
"""Mikro muhasebe aylık toplamları — yıl sonu kapanış ve açılış fişleri ayıklanmış (Ekim 2026).

Kullanıcı (22.10.2026): yıl sonu kapanış fişi süzgeci "yapalım". Canlı 2025 sonu (mikro_muhasebe_tur):
  - fis_tur 4 (kapanış) 31.12.2025: 111 satır, 130.629.641 TL — bütün BİLANÇO hesaplarını sıfırlar;
  - fis_tur 3 (açılış) 01.01.2026: aynı 111 satır, aynı tutar — geri açar. 01.01.2025 açılışı (20 satır,
    2024'ten devreden bakiyeler) verideki ilk açılıştır, önünde kapanış yoktur: kalmalı.
  - Gelir / gider hesaplarını (6xx, 7xx) kapatan fişler ise NORMAL mahsup (fis_tur 0): 600 borç 463 M (690'a),
    760 alacak 44 M (761 yansıtma), 690 / 691 / 692 iki taraflı. Aylık toplamda ayrılamaz; aktarıcının
    muhasebe_ay_tur sorgusu 69x ya da 7x1 yansıtma hesabına dokunan fişin bütün satırlarını
    YIL_SONU_MAHSUP (9) türüne yazar.
Kural (ayikla): tür 9 ve tür 4 hiç alınmaz; tür 3 yalnız önceki yılın kapanışı (tür 4) veride varsa alınmaz.
Böylece:
  - gider / gelir (P&L, alınan destek 602) Aralık'ta gerçek hareketini gösterir, sıfıra / eksiye düşmez;
  - bilanço bakiyeleri (Toplam Aktifler defter kalemleri, ödeme listesindeki SGK / muhtasar / maaş) kapanış
    yapılıp açılış henüz girilmemişken (Ocak başı) sıfır görünmez.
Fiş türlü tablo (mikro_muhasebe_ay_tur) boşsa eski tablo (mikro_muhasebe_ay) aynen okunur.
"""
from collections import defaultdict

ACILIS = 3
KAPANIS = 4
YIL_SONU_MAHSUP = 9          # aktarıcının muhasebe_ay_tur sorgusu verir (69x / 7x1 hesaplı fiş)
SAYFA = 1000


def _f(v, d=0.0):
    try:
        x = float(v)
        return x if x == x else d
    except (TypeError, ValueError):
        return d


def _i(v, d=-1):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


# ── Saf ────────────────────────────────────────────────────────────
def ayikla(satirlar):
    """mikro_muhasebe_ay_tur satırları → yıl sonu kapanış / açılış ayıklanmış satırlar (fis_tur alanı kalır)."""
    kapanis_yillari = {_i(r.get("yil")) for r in satirlar or [] if _i(r.get("fis_tur")) == KAPANIS}
    out = []
    for r in satirlar or []:
        t = _i(r.get("fis_tur"))
        if t in (YIL_SONU_MAHSUP, KAPANIS):
            continue
        if t == ACILIS and _i(r.get("yil")) - 1 in kapanis_yillari:
            continue
        out.append(r)
    return out


def topla(satirlar):
    """Fiş türlerini birleştirir: [{yil, ay, hesap_kod, borc, alacak}] (mikro_muhasebe_ay biçimi)."""
    t = defaultdict(lambda: [0.0, 0.0])
    for r in satirlar or []:
        k = (_i(r.get("yil")), _i(r.get("ay")), str(r.get("hesap_kod") or "").strip())
        t[k][0] += _f(r.get("borc"))
        t[k][1] += _f(r.get("alacak"))
    return [{"yil": y, "ay": a, "hesap_kod": h, "borc": round(b, 2), "alacak": round(al, 2)}
            for (y, a, h), (b, al) in sorted(t.items())]


# ── Veritabanı ─────────────────────────────────────────────────────
def _sayfali(sorgu, anahtar):
    from satis.mikro_esitle import sayfali_oku
    return sayfali_oku(sorgu, anahtar)


def oku(cli, onekler=None, ilk_yil=None):
    """Ayıklanmış aylık toplamlar ([{yil, ay, hesap_kod, borc, alacak}]). onekler: ("602",) gibi hesap önekleri
    (yoksa hepsi). Fiş türlü tablo boşsa / yoksa eski tablo (kapanış dahil). Döner: (satırlar, türlü mü)."""
    def _q(tablo, secim, sira, onek):
        def q():
            s = cli.table(tablo).select(secim)
            if onek:
                s = s.like("hesap_kod", f"{onek}%")
            if ilk_yil:
                s = s.gte("yil", int(ilk_yil))
            for k in sira:
                s = s.order(k)
            return s
        return q
    parcalar = list(onekler) if onekler else [None]
    try:
        satir = []
        for o in parcalar:
            satir += _sayfali(_q("mikro_muhasebe_ay_tur", "yil,ay,hesap_kod,fis_tur,borc,alacak",
                                 ("yil", "ay", "hesap_kod", "fis_tur"), o), ("yil", "ay", "hesap_kod", "fis_tur"))
    except Exception:  # noqa: BLE001 — tablo kurulmadıysa eski tabloya düş
        satir = []
    if satir:
        return topla(ayikla(satir)), True
    eski = []
    for o in parcalar:
        eski += _sayfali(_q("mikro_muhasebe_ay", "yil,ay,hesap_kod,borc,alacak", ("yil", "ay", "hesap_kod"), o),
                         ("yil", "ay", "hesap_kod"))
    return eski, False
