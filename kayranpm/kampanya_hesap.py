# -*- coding: utf-8 -*-
"""Kampanya Takip — hesap katmanı (SAF: veritabanına ve ekrana dokunmaz).

Kampanya ekranındaki HER rakam buradan gelir: liste kartları, üst özet,
detay penceresi ve kapanış. Eskiden aynı kâr dört farklı yerde dört farklı
kodla hesaplanıyordu ve birbirini tutmuyordu:
  • üst özet 'pacal_maliyet' adlı, ürün listesinde OLMAYAN bir alanı okuyordu
    → "Net Kâr" kutusu her zaman $0 gösteriyordu;
  • ürün eklerken marj = kâr / satış, tabloda marj = kâr / (satış − destek);
  • "Toplam Destek Verilen" yalnız ek desteği topluyordu.

TEK FORMÜL (birim):
    destek      = firma desteği + ek destek
    net satış   = satış fiyatı − destek
    net kâr     = net satış − paçal              (satış ve paçal > 0 ise)
    net marj    = net kâr / net satış
Kampanya toplamında spiff (TL ÷ kur → USD) net kârdan düşülür.

Paçal: kampanyaya eklenirken kaydedilen paçal esastır (o günün maliyeti).
Kayıtta paçal 0 ise ürünün GÜNCEL paçalı kullanılır — ama bu yalnız
gösterimdir; ekran açılırken veritabanına yazılmaz (eskiden detay penceresi
açılınca paçal sessizce güncelleniyordu: bakmak kaydı değiştiriyordu).
"""
from datetime import date

from shared.ana_veri import kategori_anahtar   # tek kaynak (Eki 2026)

KAMPANYA_TURLERI = ["Sellout", "Rebate", "Marketing", "Spiff"]
from shared.utils import FIRMA_KODLARI as _FK   # ANA firmalar (KANAL yok — Ekim 2026)
FIRMALAR = [*_FK, "DİĞER"]                      # yedek liste; 'DİĞER' kampanyalarda bu yazımla kayıtlı


def firma_secenekleri(ek=()):
    """Kampanya firma seçenekleri: ana firmalar + verideki/kayıtlı diğer cariler (firma_sirala
    sırası) + en sonda 'DİĞER'. Eski 'KANAL' kayıtları DİĞER'dir; 'KANAL' seçenek olmaz."""
    from shared.utils import firma_sirala, DIGER_KODU
    return [f for f in firma_sirala([*_FK, *(ek or ())]) if f != DIGER_KODU] + ["DİĞER"]

# Durum: tarihten hesaplanır (kayıttaki 'durum' yalnız aktif/kapalı tutar)
DURUMLAR = {
    "bekliyor": ("Kapanmayı bekliyor", "amber", "Süresi doldu; satış adetleri girilip kapatılmalı"),
    "suruyor":  ("Sürüyor", "yesil", "Bugün yürürlükte"),
    "yaklasan": ("Yaklaşan", "cyan", "Henüz başlamadı"),
    "kapali":   ("Kapalı", "silik", "Satışlar girildi, kampanya kapandı"),
}
DURUM_SIRA = ["bekliyor", "suruyor", "yaklasan", "kapali"]


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _tarih(v):
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def durum(kamp, bugun):
    """'kapali' | 'yaklasan' | 'suruyor' | 'bekliyor'."""
    if str(kamp.get("durum") or "").lower() == "kapali":
        return "kapali"
    bas, bit = _tarih(kamp.get("baslangic_tarihi")), _tarih(kamp.get("bitis_tarihi"))
    if bas and bugun < bas:
        return "yaklasan"
    if bit and bugun > bit:
        return "bekliyor"
    return "suruyor"


def zaman(kamp, bugun):
    """Zaman çizgisi: (geçen oran 0..1, kalan gün | None, toplam gün)."""
    bas, bit = _tarih(kamp.get("baslangic_tarihi")), _tarih(kamp.get("bitis_tarihi"))
    if not bas or not bit:
        return 0.0, None, 0
    toplam = max(1, (bit - bas).days + 1)
    gecen = (bugun - bas).days + 1
    return max(0.0, min(1.0, gecen / toplam)), (bit - bugun).days, toplam


def spiff_usd(kamp):
    tl, kur = _f(kamp.get("spiff_tl")), _f(kamp.get("spiff_kur"))
    return tl / kur if tl > 0 and kur > 0 else 0.0


def urun_hesap(ku, guncel_pacal=0.0):
    """Tek kampanya ürününün birim ve toplam hesabı."""
    satis = _f(ku.get("satis_fiyati"))
    fd, ed = _f(ku.get("birim_firma_destek")), _f(ku.get("birim_ek_destek"))
    adet = int(_f(ku.get("satilan_adet")))
    kayitli = _f(ku.get("pacal_maliyet"))
    pacal = kayitli if kayitli > 0 else _f(guncel_pacal)
    destek = fd + ed
    net_satis = satis - destek
    hesaplanir = satis > 0 and pacal > 0
    net_kar = (net_satis - pacal) if hesaplanir else None
    marj = (net_kar / net_satis * 100) if (hesaplanir and net_satis > 0) else None
    return {
        "satis": satis, "fd": fd, "ed": ed, "destek": destek, "adet": adet,
        "pacal": pacal, "pacal_guncelden": kayitli <= 0 and pacal > 0,
        "net_satis": net_satis, "net_kar": net_kar, "marj": marj,
        "t_ciro": net_satis * adet, "t_destek": destek * adet,
        "t_firma_destek": fd * adet, "t_ek_destek": ed * adet,
        "t_net": (net_kar or 0.0) * adet,
        "eksik_pacal": satis > 0 and pacal <= 0,
    }


def kampanya_ozet(kamp, urunler, pacal_map=None, bugun=None):
    """Kampanya toplamı. pacal_map: {sku: güncel paçal} — anahtar kanonik (sku_anahtar) ya da ham."""
    from shared.utils import sku_anahtar
    pacal_map = pacal_map or {}
    sat = [urun_hesap(u, pacal_map.get(sku_anahtar(u.get("sku")), pacal_map.get(u.get("sku"), 0)))
           for u in (urunler or [])]
    t = lambda k: sum(s[k] for s in sat)
    spf = spiff_usd(kamp)
    net = t("t_net") - spf
    ciro = t("t_ciro")
    o = {
        "urun": len(sat), "adet": sum(s["adet"] for s in sat),
        "ciro": ciro, "destek": t("t_destek"), "firma_destek": t("t_firma_destek"),
        "ek_destek": t("t_ek_destek"), "spiff": spf, "net": net,
        "marj": (net / ciro * 100) if ciro > 0 else None,
        "eksik_pacal": sum(1 for s in sat if s["eksik_pacal"]),
        "adet_yok": bool(sat) and all(s["adet"] == 0 for s in sat),
    }
    if bugun is not None:
        o["durum"] = durum(kamp, bugun)
        o["oran"], o["kalan"], o["gun"] = zaman(kamp, bugun)
    return o


def filtrele(kampanyalar, bugun, durum_sec="tumu", firma="Tümü", kategori="Tümü",
             yil="Tümü", ara=""):
    """Ekrandaki filtre çubuğunun tamamı (saf)."""
    from shared.utils import tr_kucuk
    a = tr_kucuk(ara)
    out = []
    for k in kampanyalar:
        if durum_sec != "tumu" and durum(k, bugun) != durum_sec:
            continue
        # Firma süzgeci kanonik (shared.utils.firma_kanonik): 'DİĞER' = firması belli olmayan
        # (eski 'KANAL' dahil). Yeni cariler kendi adıyla süzülür, DİĞER'e düşmez (Ekim 2026).
        from shared.utils import firma_kanonik, DIGER_KODU
        fk = firma_kanonik(k.get("firma"))
        if firma != "Tümü":
            if firma == "DİĞER" and fk != DIGER_KODU:
                continue
            if firma != "DİĞER" and fk != firma_kanonik(firma):
                continue
        if kategori != "Tümü" and kategori_anahtar(k.get("kategori")) != kategori_anahtar(kategori):
            continue
        if yil != "Tümü" and str(k.get("baslangic_tarihi") or "")[:4] != str(yil):
            continue
        if a and a not in tr_kucuk(f"{k.get('kampanya_adi','')} {k.get('firma','')} "
                                   f"{k.get('kategori','')} {k.get('kampanya_turu','')} {k.get('notlar','')}"):
            continue
        out.append(k)
    sira = {d: i for i, d in enumerate(DURUM_SIRA)}
    # Önce durum (dikkat isteyen üstte), sonra bitiş tarihi (yakın olan üstte);
    # kapalılar en yeni kapanan üstte.
    return sorted(out, key=lambda k: (
        sira[durum(k, bugun)],
        str(k.get("bitis_tarihi") or "") if durum(k, bugun) != "kapali" else "",
        "" if durum(k, bugun) != "kapali" else _ters(str(k.get("bitis_tarihi") or ""))))


def _ters(s):
    """Metni ters sıralamak için (yeni tarih önce)."""
    return "".join(chr(0x10FFFF - ord(c)) for c in s)
