# -*- coding: utf-8 -*-
"""KAYRAN — Yönetim P&L: TEK hesap (Ekim 2026).

Eskiden Yönetim Panosu ile Ay Kapanış Raporu ayrı kodla hesaplanıyordu ve aynı
ay için farklı net kâr verebiliyordu (rapor alınan desteği eklemiyor, kuru
bulunamayan TL desteği farklı ele alıyordu). Ayrıca okunamayan bileşenler
(iade, gider, destek, alınan destek) sessizce 0 sayılıyor, net kâr olduğundan
yüksek görünüyordu. Şimdi:

  pnl_topla(yil, donem, bas, bit, kaynak, bugun)
      → ciro, cogs, brut, destek, gider, alinan, net_kar, marj, kanal, urun,
        tur_usd (destek kırılımı), gider_tl, eksikler (ekranda gösterilir)

  Formül:  net kâr = (ciro − iade) − (COGS − iade maliyeti)
                    − destekler − işletme giderleri + alınan destekler

  Kur kuralı (destek ve gider için aynı): o günün kuru → yoksa güncel kur →
  o da yoksa kalem hesaba KATILMAZ ve eksiklerde bildirilir.

Veri getirme `Kaynak` sınıfında (veritabanı); hesap saf — sahte kaynakla test
edilir (tests/test_yonetim_yeni.py).
"""
import calendar
from datetime import date

GIDER_AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
               "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
_CEYREK = {"Q1": (0, 3), "Q2": (3, 6), "Q3": (6, 9), "Q4": (9, 12)}
_TL = ("TL", "TRY", "₺", "TRL")
GIDER_KAT = ("Sabit", "Değişken", "Yarı Değişken")


def ay_araligi(donem):
    """Dönem → GIDER_AYLAR indeks aralığı [i0, i1)."""
    if donem in GIDER_AYLAR:
        i = GIDER_AYLAR.index(donem)
        return i, i + 1
    return _CEYREK.get(donem, (0, 12))


def onceki_ay(bugun):
    """Ay Kapanış Raporu varsayılanı: (yıl, ay_idx). Ocak'ta önceki yılın Aralık'ı
    (eskiden max(0, ay-2) Ocak'ı seçiyordu)."""
    return (bugun.year - 1, 11) if bugun.month == 1 else (bugun.year, bugun.month - 2)


def ay_tarihleri(yil, ay_idx):
    son = calendar.monthrange(yil, ay_idx + 1)[1]
    return f"{yil}-{ay_idx + 1:02d}-01", f"{yil}-{ay_idx + 1:02d}-{son:02d}"


def _ay_listesi(adlar):
    return ", ".join(adlar)


def tl_usd(tutar, doviz, tarih, kmap, yedek):
    """TL tutarı kaydın TARİHİNDEKİ kurla USD'ye çevirir (yoksa yedek kur).
    USD ise olduğu gibi. Kur hiç yoksa None — çağıran eksiklere yazar.
    Yönetim P&L ve Satış P&L aynı kuralı kullanır (aynı destek iki ekranda aynı tutar)."""
    tutar = float(tutar or 0)
    if str(doviz or "USD").strip().upper() not in _TL:
        return tutar
    k = (kmap or {}).get(str(tarih or "")[:10]) or (yedek if (yedek or 0) > 1 else 0)
    return tutar / k if k else None


def pnl_topla(yil, donem, bas, bit, kaynak, bugun=None, aylar=None):
    """aylar=(i0, i1): gider aylarını açıkça verir (yılbaşından bugüne kıyası: geçen yılın
    yalnız aynı ayları). Verilmezse dönemden çıkar (ay_araligi) — bütün eski çağrılar aynı."""
    bugun = bugun or date.today()
    eksik = []
    r = {"yil": yil, "donem": donem, "bas": bas, "bit": bit, "ciro": 0.0, "cogs": 0.0,
         "ciro_brut": 0.0, "iade_tutar": 0.0, "destek": 0.0, "gider": 0.0, "gider_tl": 0.0,
         "alinan": 0.0, "kanal": {}, "urun": {}, "tur_usd": {}, "tl_cevrildi": False}

    # ── Satış ──
    try:
        top, r["kanal"], r["urun"] = kaynak.satis(bas, bit)
        r["ciro_brut"] = float(top.get("ciro", 0) or 0)
        r["ciro"] = r["ciro_brut"]
        r["cogs"] = float(top.get("maliyet", 0) or 0)
    except Exception as e:  # noqa: BLE001
        eksik.append(f"Satış verisi okunamadı ({type(e).__name__}) — ciro ve COGS 0")

    # ── İade ──
    try:
        it = kaynak.iade(bas, bit) or {}
        r["iade_tutar"] = float(it.get("i_tutar", 0) or 0)
        r["ciro"] -= r["iade_tutar"]
        r["cogs"] -= r["iade_tutar"] - float(it.get("i_kar", 0) or 0)
    except Exception as e:  # noqa: BLE001
        eksik.append(f"İadeler okunamadı ({type(e).__name__}) — net kâr iadeleri düşmüyor")
    r["brut"] = r["ciro"] - r["cogs"]

    # ── Kur ──
    try:
        kmap = kaynak.kur_haritasi(bas, bit) or {}
    except Exception:  # noqa: BLE001
        kmap = {}
    try:
        yedek = float(kaynak.yedek_kur() or 0)
    except Exception:  # noqa: BLE001
        yedek = 0.0
    yedek = yedek if yedek > 1 else 0.0
    kur_eksik = []

    def _usd(tutar, doviz, tarih, ne):
        u = tl_usd(tutar, doviz, tarih, kmap, yedek)
        tl = str(doviz or "USD").strip().upper() in _TL
        if u is None:
            kur_eksik.append(ne)
        elif tl:
            r["tl_cevrildi"] = True
        return u

    # ── Destekler ──
    try:
        for h in kaynak.destekler(bas, bit) or []:
            u = _usd(h.get("tutar"), h.get("doviz"), h.get("donem") or h.get("tarih"), "destek")
            if u is None:
                continue
            t = (h.get("tur") or "Diğer").strip() or "Diğer"
            r["tur_usd"][t] = r["tur_usd"].get(t, 0.0) + u
            r["destek"] += u
    except Exception as e:  # noqa: BLE001
        eksik.append(f"Destekler okunamadı ({type(e).__name__}) — net kâr destekleri düşmüyor")

    # ── İşletme giderleri ──
    i0, i1 = aylar if aylar else ay_araligi(donem)
    try:
        kat = kaynak.gider_kat(yil) or {}
    except Exception as e:  # noqa: BLE001
        kat = None
        eksik.append(f"{yil} gider tablosu okunamadı ({type(e).__name__}) — net kâr gider içermiyor")
    if kat is not None:
        if not any(kat.get(k) for k in GIDER_KAT):
            eksik.append(f"{yil} gider tablosu yüklenmedi — net kâr gider içermiyor")
        else:
            girilmemis = []
            for mi in range(i0, i1):
                ay_tl = sum(float(((list(kat.get(k) or []) + [0.0] * 12)[mi]) or 0) for k in GIDER_KAT)
                if not ay_tl:
                    # yalnız GEÇMİŞ aylar beklenir (içinde bulunulan ve gelecek aylar değil)
                    if (yil, mi + 1) < (bugun.year, bugun.month):
                        girilmemis.append(GIDER_AYLAR[mi])
                    continue
                r["gider_tl"] += ay_tl
                u = _usd(ay_tl, "TL", f"{yil}-{mi + 1:02d}-15", "gider")
                if u is not None:
                    r["gider"] += u
            if girilmemis:
                eksik.append(f"Gideri girilmemiş ay: {_ay_listesi(girilmemis)} — net kâr bu ayların giderini içermiyor")

    # ── Alınan destekler (gelir) ──
    try:
        r["alinan"] = float(kaynak.alinan(bas, bit) or 0)
    except Exception as e:  # noqa: BLE001
        eksik.append(f"Alınan destekler okunamadı ({type(e).__name__}) — net kâra eklenmedi")

    if kur_eksik:
        ne = " ve ".join(sorted(set(kur_eksik)))
        eksik.append(f"Kur bulunamadı: TL cinsi {ne} kalemleri hesaba katılmadı")

    r["net_kar"] = r["brut"] - r["destek"] - r["gider"] + r["alinan"]
    r["marj"] = (r["net_kar"] / r["ciro"] * 100) if r["ciro"] else 0.0
    r["brut_marj"] = (r["brut"] / r["ciro"] * 100) if r["ciro"] else 0.0
    r["eksikler"] = eksik
    return r


class Kaynak:
    """Gerçek veri kaynağı (veritabanı). Her yöntem hata FIRLATIR; yakalayıp
    eksiklere yazmak pnl_topla'nın işi — sessizce 0 dönmek yok."""

    def __init__(self, oturum_kuru=0.0):
        self._oturum_kuru = float(oturum_kuru or 0)

    def satis(self, bas, bit):
        from satis.database import get_satislar_yalin, ozet_hesapla, get_satis_pnl_view, ozet_from_view
        v = get_satis_pnl_view(bas, bit)
        return ozet_from_view(v) if v is not None else ozet_hesapla(get_satislar_yalin(bas, bit))

    def iade(self, bas, bit):
        from satis.database import iade_satis_net_ozet
        return iade_satis_net_ozet(bas, bit)[1]

    def destekler(self, bas, bit):
        from kayranpm.ref_no import get_destek_donem
        v = get_destek_donem(bas, bit)
        if v is not None:
            return v
        # Yedek dal (görünüm kurulmamışsa): bütçe harcamaları + ref tutarları
        from kayranpm.ref_no import get_tum_butce_harcamalari, get_tum_ref_tutarlari
        rows = [dict(h, donem=h.get("fatura_tarih")) for h in (get_tum_butce_harcamalari(bas, bit) or [])]
        rows += [dict(x, tur="Ref No") for x in (get_tum_ref_tutarlari(bas, bit) or [])]
        return rows

    def gider_kat(self, yil):
        from kayranacc.database import get_ayar
        g = get_ayar(f"gider_tablosu_{yil}")
        return (g or {}).get("kat") or {}

    def alinan(self, bas, bit):
        from kayranpm.ref_no import alinan_destek_aralik_usd
        return alinan_destek_aralik_usd(bas, bit)

    def kur_haritasi(self, bas, bit):
        from kayranacc.database import get_kur_araligi
        return get_kur_araligi(bas, bit)

    def yedek_kur(self):
        if self._oturum_kuru > 1:
            return self._oturum_kuru
        from gunluk import get_doviz
        return float(get_doviz().get("USD") or 0)
