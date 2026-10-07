# -*- coding: utf-8 -*-
"""Bilgi işlem elemanı — saf hesaplar (Ekim 2026). Streamlit'e bağlı değil; hem uygulama
(Bilgi İşlem sayfası) hem gece görevi (otonom/bt_db.py, otonom/bt_kapi.py) kullanır.

  sure_ozeti(olcumler)        sayfa başına açılış sayısı, ortanca (p50) ve p90 süre, hata oranı
  karsilastir(once, sonra)    iki dönemin sayfa sürelerini yan yana koyar (yavaşlayan / hızlanan)
  hata_ozeti(hatalar)         hata kayıtlarını yere göre gruplar
  kapi_karari(dosyalar, ...)  PR otomatik birleşebilir mi? (kullanıcı kararı, Ekim 2026)

OTOMATİK BİRLEŞTİRME KAPISI: kullanıcı "küçük düzeltmeleri kendi birleştirsin" dedi. Karar
elemanın kendisine bırakılmaz; GitHub iş akışı (.github/workflows/bt-birlestir.yml) bu kurallarla
denetler. Para/stok/kâr/yetki/veritabanı koduna, otonom zincire, iş akışlarına ve kurallara dokunan
ya da büyük olan PR otomatik birleşmez — kullanıcıya kalır.
"""

# Otomatik birleşmeyi ENGELLEYEN yollar (alt dize eşleşmesi, küçük harf)
YASAK_YOLLAR = (
    "otonom/", ".github/", "claude.md", "veritabani/", "requirements", ".streamlit/",
    "database.py", "_hesap.py", "hesap.py", "pacal", "maliyet", "stok", "kar_", "pnl", "kur",
    "yetki", "auth", "sifre", "eposta", "telegram", "yedek", "cop_kutusu", "yukleme_gecmisi",
    "ice_aktar", "excel_islemler", "dosya_tani", "dosya_kapisi", "tests/test_butunluk.py",
)
EN_FAZLA_DOSYA = 6
EN_FAZLA_SATIR = 200
DAL_ONEKI = "claude/"              # gece görevi oturumunun dalı (claude/…)
BASLIK_ONEKI = "Bilgi işlem:"      # görevin PR başlığı bununla başlar
ETIKET = "bt-otomatik"


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _yuzdelik(sirali, oran):
    """Sıralı listede yüzdelik: indeks int(oran·n) (n çiftse üst ortanca; p90 uç değeri kaçırmaz)."""
    if not sirali:
        return None
    return sirali[min(len(sirali) - 1, max(0, int(oran * len(sirali))))]


def sure_ozeti(olcumler):
    """[{modul, sayfa, ms, hata}] → {(modul, sayfa): {adet, p50, p90, hata}} (ms tamsayı)."""
    g = {}
    for o in olcumler or []:
        ms = _f(o.get("ms"))
        if ms is None or ms < 0:
            continue
        k = (str(o.get("modul") or "—"), str(o.get("sayfa") or ""))
        d = g.setdefault(k, {"sureler": [], "hata": 0})
        d["sureler"].append(ms)
        d["hata"] += 1 if o.get("hata") else 0
    out = {}
    for k, d in g.items():
        s = sorted(d["sureler"])
        out[k] = {"adet": len(s), "p50": int(_yuzdelik(s, 0.5)), "p90": int(_yuzdelik(s, 0.9)),
                  "hata": d["hata"]}
    return out


def karsilastir(once, sonra, en_az_adet=5):
    """İki dönemin sure_ozeti'ni karşılaştırır. Döner: [{modul, sayfa, once, sonra, fark_yuzde}],
    en çok yavaşlayan önce. Az ölçümlü (en_az_adet altı) sayfalar güvenilmez sayılıp atlanır."""
    satir = []
    for k, s in (sonra or {}).items():
        o = (once or {}).get(k)
        if not o or o["adet"] < en_az_adet or s["adet"] < en_az_adet or not o["p50"]:
            continue
        satir.append({"modul": k[0], "sayfa": k[1], "once": o["p50"], "sonra": s["p50"],
                      "fark_yuzde": round((s["p50"] - o["p50"]) / o["p50"] * 100, 1)})
    return sorted(satir, key=lambda r: -r["fark_yuzde"])


def hata_ozeti(hatalar):
    """[{yer, mesaj, zaman}] → [{yer, adet, son, mesaj}] en sık önce."""
    g = {}
    for h in hatalar or []:
        y = str(h.get("yer") or "—")
        d = g.setdefault(y, {"yer": y, "adet": 0, "son": "", "mesaj": ""})
        d["adet"] += 1
        z = str(h.get("zaman") or "")
        if z >= d["son"]:
            d["son"], d["mesaj"] = z, str(h.get("mesaj") or "")[:200]
    return sorted(g.values(), key=lambda d: (-d["adet"], d["yer"]))


def kapi_karari(dosyalar, dal="", etiketler=(), testler_yesil=False, baslik=""):
    """dosyalar: [{filename, additions, deletions}]. Döner: (otomatik_mi: bool, sebepler: [str]).
    Bütün koşullar sağlanmazsa PR kullanıcıya kalır."""
    sebep = []
    if not str(dal or "").startswith(DAL_ONEKI):
        sebep.append(f"dal '{DAL_ONEKI}' ile başlamıyor")
    if not str(baslik or "").startswith(BASLIK_ONEKI):
        sebep.append(f"başlık '{BASLIK_ONEKI}' ile başlamıyor")
    if ETIKET not in set(etiketler or ()):
        sebep.append(f"'{ETIKET}' etiketi yok")
    if not testler_yesil:
        sebep.append("testler yeşil değil")
    dosyalar = list(dosyalar or [])
    if not dosyalar:
        sebep.append("değişen dosya yok")
    if len(dosyalar) > EN_FAZLA_DOSYA:
        sebep.append(f"{len(dosyalar)} dosya (sınır {EN_FAZLA_DOSYA})")
    satir = sum(int(d.get("additions") or 0) + int(d.get("deletions") or 0) for d in dosyalar)
    if satir > EN_FAZLA_SATIR:
        sebep.append(f"{satir} satır değişiklik (sınır {EN_FAZLA_SATIR})")
    for d in dosyalar:
        ad = str(d.get("filename") or "").lower()
        y = next((y for y in YASAK_YOLLAR if y in ad), None)
        if y:
            sebep.append(f"{d.get('filename')}: korunan alan ({y})")
    return (not sebep), sebep


def gunluk_seri(olcumler, hatalar=()):
    """Gün başına sayfa açılışı p50 (ms), açılış adedi ve hata sayısı: [{gun, p50, adet, hata}] eskiden yeniye."""
    g = {}
    for o in olcumler or []:
        ms = _f(o.get("ms"))
        gun = str(o.get("zaman") or "")[:10]
        if ms is None or not gun:
            continue
        g.setdefault(gun, {"s": [], "hata": 0})["s"].append(ms)
    for h in hatalar or []:
        gun = str(h.get("zaman") or "")[:10]
        if gun:
            g.setdefault(gun, {"s": [], "hata": 0})["hata"] += 1
    out = []
    for gun in sorted(g):
        s = sorted(g[gun]["s"])
        out.append({"gun": gun, "p50": int(_yuzdelik(s, 0.5)) if s else None, "adet": len(s),
                    "hata": g[gun]["hata"]})
    return out


def iyilestirme_satiri(r):
    """bt_rapor iyileştirme/sonuç kaydı → ekran satırı: önce→sonra ve yüzde fark (azalış iyi)."""
    once, sonra = _f(r.get("once")), _f(r.get("sonra"))
    fark = None
    if once and sonra is not None:
        fark = round((sonra - once) / once * 100, 1)
    return {"zaman": str(r.get("zaman") or "")[:10], "baslik": r.get("baslik") or "",
            "durum": r.get("durum") or "", "olcut": r.get("olcut") or "", "once": once, "sonra": sonra,
            "birim": r.get("birim") or "", "fark_yuzde": fark, "pr_url": r.get("pr_url") or "",
            "ozet": r.get("ozet") or ""}


def karne(raporlar, gun=30, simdi=None):
    """Serkan'ın kendi karnesi (haftalık öz değerlendirme): son `gun` gündeki iyileştirmelerin
    durumları, sonucu ölçülenlerin ortalama farkı (eksi = iyileşme), öneri ve öğrenme sayısı."""
    from datetime import datetime, timedelta, timezone
    simdi = simdi or datetime.now(timezone.utc)
    sinir = (simdi - timedelta(days=gun)).isoformat()
    son = [r for r in raporlar or [] if str(r.get("zaman") or "") >= sinir]
    iyi = [r for r in son if r.get("tur") == "iyilestirme"]
    durum = {}
    for r in iyi:
        durum[r.get("durum") or "—"] = durum.get(r.get("durum") or "—", 0) + 1
    farklar = [x["fark_yuzde"] for x in (iyilestirme_satiri(r) for r in iyi) if x["fark_yuzde"] is not None]
    return {"gun": gun, "iyilestirme": len(iyi), "durum": durum,
            "olculen": len(farklar),
            "ortalama_fark_yuzde": round(sum(farklar) / len(farklar), 1) if farklar else None,
            "kotulesen": sum(1 for f in farklar if f > 0),
            "oneri": sum(1 for r in son if r.get("tur") == "oneri"),
            "ogrenme": sum(1 for r in son if r.get("tur") == "ogrenme"),
            "calisma": sum(1 for r in son if r.get("tur") == "calisma")}
