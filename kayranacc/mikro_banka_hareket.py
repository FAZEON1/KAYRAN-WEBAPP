# -*- coding: utf-8 -*-
"""Banka hesabının Mikro hareketleri (Ekim 2026). Ekran: kayranacc/banka_ekran.py (hesap penceresi › Hareketler).

Kullanıcı (22.10.2026): "Bugün Mikro'ya banka hareketi işledim. 15 dakika sonra bakiye güncellendi ama işlediğim
hareketi Kayran'da göremedim." Bakiye Mikro'dan geliyordu (kayranacc.mikro_muhasebe) ama hesabın penceresi yalnız
uygulamanın eski tahsilat tablosunu listeliyordu. Burada hesabın Mikro'daki hareketleri, bakiyeyle AYNI kuralla
(mikro_muhasebe._banka_hareketleri + hareket_tutari: firma çeki ödendiği gün düşer, kur farkı fişi döviz bakiyesini
değiştirmez) giriş / çıkış ve her satırdan sonraki bakiye ile gösterilir. Yalnız okur.
"""
from datetime import timedelta

from . import mikro_muhasebe as MM

GUN = 45                  # pencerede gösterilen dönem


def _karsi(h, ban_kod, adlar):
    """Hareketin karşı tarafı: banka kendi kaydıysa (cha_kod) karşı hesap, karşı hesapsa cari / muhasebe kodu."""
    if MM._s(h.get("cha_kod")) == ban_kod and MM._i(h.get("cha_cari_cins"), -1) == MM.BANKA_CINS:
        kod = MM._s(h.get("cha_kasa_hizkod"))
    else:
        kod = MM._s(h.get("cha_kod"))
    return adlar.get(kod) or kod


def hareket_listesi(hareketler, ban_kod, doviz, bakiye, adlar=None):
    """Hesabın hareketleri, yeni → eski: [{tarih, aciklama, karsi, giris, cikis, bakiye}]. bakiye: hesabın şimdiki
    bakiyesi (satır bakiyesi ondan geriye hesaplanır). Etkisi sıfır olan satır (kur farkı, çek verildi) gösterilmez."""
    adlar = adlar or {}
    satir = []
    for h in MM._banka_hareketleri(hareketler or []):
        borc = MM._i(h.get("cha_tip")) == 0
        etki = 0.0
        if MM._s(h.get("cha_kod")) == ban_kod and MM._i(h.get("cha_cari_cins"), -1) == MM.BANKA_CINS:
            t = MM.hareket_tutari(h, doviz)
            etki += t if borc else -t
        if MM._s(h.get("cha_kasa_hizkod")) == ban_kod and MM._i(h.get("cha_kasa_hizmet"), -1) == MM.BANKA_CINS:
            t = MM.hareket_tutari(h, doviz)
            etki += -t if borc else t
        if abs(etki) < MM.KURUS:
            continue
        satir.append({"tarih": str(h.get("cha_tarihi") or "")[:10], "aciklama": MM._s(h.get("cha_aciklama")),
                      "karsi": _karsi(h, ban_kod, adlar), "etki": etki, "_sira": str(h.get("cha_guid") or "")})
    satir.sort(key=lambda r: (r["tarih"], r["_sira"]), reverse=True)
    kalan = float(bakiye or 0)
    out = []
    for r in satir:
        out.append({"tarih": r["tarih"], "aciklama": r["aciklama"], "karsi": r["karsi"],
                    "giris": round(r["etki"], 2) if r["etki"] > 0 else 0.0,
                    "cikis": round(-r["etki"], 2) if r["etki"] < 0 else 0.0, "bakiye": round(kalan, 2)})
        kalan -= r["etki"]
    return out


# ── Veritabanı (yalnız okur) ───────────────────────────────────────
def hesap_kodu(banka):
    """Uygulama hesabının Mikro banka kodu ve dövizi: (ban_kod, döviz) ya da (None, None)."""
    cli = MM._cli()
    kartlar = cli.table("mikro_banka_kart").select("*").execute().data or []
    kod = MM.banka_eslestir([banka], kartlar).get(banka.get("id"))
    if not kod:
        return None, None
    k = next((x for x in kartlar if MM._s(x.get("ban_kod")) == kod), {})
    return kod, MM._i(k.get("ban_doviz_cinsi"))


def oku(banka, bugun, gun=GUN):
    """Hesap penceresi için: (satırlar, ban_kod) — eşleşmezse ([], None)."""
    from satis.mikro_esitle import sayfali_oku
    kod, doviz = hesap_kodu(banka)
    if not kod:
        return [], None
    cli = MM._cli()
    ilk = (bugun - timedelta(days=gun)).isoformat()
    har = sayfali_oku(lambda: cli.table("mikro_cari_hareket").select("cha_guid," + MM._HAREKET_ALANLARI)
                      .or_(f"cha_kod.eq.{kod},cha_kasa_hizkod.eq.{kod}").gte("cha_tarihi", ilk)
                      .order("cha_guid"), "cha_guid")
    kodlar = sorted({MM._s(h.get("cha_kod")) for h in har} | {MM._s(h.get("cha_kasa_hizkod")) for h in har})
    adlar = {}
    if kodlar:
        for r in cli.table("mikro_cari_kart").select("cari_kod,cari_unvan1").in_("cari_kod", kodlar).execute().data or []:
            adlar[MM._s(r.get("cari_kod"))] = " ".join(MM._s(r.get("cari_unvan1")).split())
        for r in (cli.table("mikro_hesap_plani").select("muh_hesap_kod,muh_hesap_isim1")
                  .in_("muh_hesap_kod", kodlar).execute().data or []):
            adlar.setdefault(MM._s(r.get("muh_hesap_kod")), MM._s(r.get("muh_hesap_isim1")))
        for r in cli.table("mikro_banka_kart").select("ban_kod,ban_ismi").in_("ban_kod", kodlar).execute().data or []:
            adlar.setdefault(MM._s(r.get("ban_kod")), MM._s(r.get("ban_ismi")))
    return hareket_listesi(har, kod, doviz, banka.get("bakiye"), adlar), kod
