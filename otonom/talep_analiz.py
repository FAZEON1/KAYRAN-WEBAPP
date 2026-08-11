# -*- coding: utf-8 -*-
"""Talep Analizi — GitHub Actions ile gece çalışır (Streamlit'ten bağımsız).

NE YAPAR: Açık talepleri okur, sınıflandırır, RİSK puanı verir, benzer
olanları gruplar ve Telegram'a özet gönderir.

NE YAPMAZ: Kod YAZMAZ, dosya DEĞİŞTİRMEZ, veritabanına YAZMAZ (yalnız
analiz sonucunu talep kaydına işler — o da açıkça isteğe bağlı).

Bu, kademeli otonominin 1. AŞAMASI. Amaç güven inşa etmek: bir süre
çalıştırıp sınıflandırmanın isabetli olup olmadığını görüyoruz. İsabetliyse
2. aşamaya (dal açma + PR) geçilir.

Ortam değişkenleri (GitHub Secrets):
  SUPABASE_URL, SUPABASE_KEY          — zorunlu
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID — isteğe bağlı
  YAZ=1                                — analizi talep kaydına da işler
"""

import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

TR = timezone(timedelta(hours=3))


# ═══════════════════════════════════════════════════════════════════
#  SINIFLANDIRMA KURALLARI
#  Anahtar kelime tabanlı — kasıtlı olarak BASİT ve OKUNUR tutuldu.
#  Yanlış sınıflandırma tespit edilirse buraya kelime eklenir.
# ═══════════════════════════════════════════════════════════════════

TUR_KURALLARI = [
    ("hata", ["hata", "çalışmıyor", "calismiyor", "bozuk", "yanlış", "yanlis",
              "eksik çıkıyor", "görünmüyor", "gorunmuyor", "açılmıyor",
              "acilmiyor", "kayboluyor", "patlıyor", "tutmuyor", "uyuşmuyor",
              "uyusmuyor", "sorun", "düzelt", "duzelt"]),
    ("iyilestirme", ["daha iyi", "kolaylaş", "kolaylas", "hızlan", "hizlan",
                     "yavaş", "yavas", "zor oluyor", "pratik", "otomatik olsa",
                     "keşke", "keske", "olsa iyi", "güzel olur", "guzel olur",
                     "sadeleş", "sadeles"]),
    ("yeni_ozellik", ["ekle", "eklensin", "olsun", "yapabilir mi", "istiyorum",
                      "gerekiyor", "lazım", "lazim", "yeni", "ilave", "koy"]),
]

# Riskli alanlar — bu kelimeler geçiyorsa İNSAN BAKMALI.
# Para, stok ve yetki hesaplarına dokunan hiçbir şey otomatik geçmez.
YUKSEK_RISK = [
    "stok", "maliyet", "paçal", "pacal", "kâr", "kar ", "marj", "fiyat",
    "ödeme", "odeme", "bakiye", "cari", "fatura", "tahsilat", "borç", "borc",
    "yetki", "şifre", "sifre", "kullanıcı", "kullanici",
    "veritaban", "tablo", "kolon", "depo", "iade", "ithalat", "vergi",
]

# Bu kelimeler TAM KELİME olarak aranır. "sil" alt dizge olarak arandığında
# "siliniyor", "silindi", "temsilci" gibi masum kelimeleri yakalıyordu.
YUKSEK_RISK_TAM = ["sil", "silme", "sildim", "silinsin", "kaldır", "kaldir"]

ORTA_RISK = [
    "rapor", "excel", "filtre", "hesap", "toplam", "kırılım", "kirilim",
    "kampanya", "destek", "sipariş", "siparis", "satış", "satis",
]

# Modül tahmini — hangi kod alanını ilgilendiriyor
MODUL_KELIME = {
    "satis": ["satış", "satis", "sipariş", "siparis", "kanal", "cari", "p&l",
              "kâr", "kar ", "iade", "müşteri", "musteri"],
    "ithalat": ["ithalat", "gümrük", "gumruk", "navlun", "paçal", "pacal",
                "konteyner", "antrepo", "tedarikçi", "tedarikci", "fob"],
    "kayranpm": ["ürün", "urun", "stok kartı", "kategori", "marka", "kampanya",
                 "ref no", "sipariş öneri", "siparis oneri", "sku"],
    "kayranacc": ["muhasebe", "ödeme", "odeme", "banka", "çek", "cek",
                  "virman", "bakiye", "aktif", "gider"],
    "depo": ["depo", "sevk", "transfer", "raf", "sayım", "sayim"],
    "teknikservis": ["servis", "arıza", "ariza", "garanti", "rma", "tamir"],
    "yonetim": ["yönetim", "yonetim", "pano", "dashboard", "özet", "ozet"],
    "app": ["giriş", "giris", "menü", "menu", "tema", "arama", "bildirim",
            "yetki", "şifre", "sifre", "arayüz", "arayuz", "buton", "düğme",
            "pencere", "ekran", "yazı", "yazi", "renk", "font", "hane",
            "küsurat", "kusurat", "ondalık", "ondalik", "biçim", "bicim"],
}


def _norm(s):
    return str(s or "").strip().lower()


def tur_bul(metin):
    """Talebin türü: hata > iyilestirme > yeni_ozellik (ilk eşleşen kazanır).

    Sıra ÖNEMLİ: "hata" öncelikli, çünkü bozuk bir şey varsa onu yeni özellik
    talebi sanmak öncelik hatası yaratır.
    """
    m = _norm(metin)
    for tur, kelimeler in TUR_KURALLARI:
        if any(k in m for k in kelimeler):
            return tur
    return "belirsiz"


def risk_bul(metin):
    """(seviye, gerekce) — hangi kelime tetikledi, açıkça söylenir."""
    m = _norm(metin)
    yuksek = [k for k in YUKSEK_RISK if k in m]
    # Tam kelime eşleşmesi: "siliniyor" ≠ "sil"
    _kelimeler = set(re.findall(r"[a-zçğıöşü]+", m))
    yuksek += [k for k in YUKSEK_RISK_TAM if k in _kelimeler]
    if yuksek:
        return "yuksek", yuksek[:4]
    orta = [k for k in ORTA_RISK if k in m]
    if orta:
        return "orta", orta[:4]
    return "dusuk", []


def modul_bul(metin):
    """En çok kelime eşleşen modül. Eşitlikte hepsi döner."""
    m = _norm(metin)
    puan = {}
    for mod, kelimeler in MODUL_KELIME.items():
        n = sum(1 for k in kelimeler if k in m)
        if n:
            puan[mod] = n
    if not puan:
        return ["?"]
    en = max(puan.values())
    return sorted([k for k, v in puan.items() if v == en])


def benzer_grupla(talepler):
    """Aynı konuya değen talepleri gruplar (ortak kelime oranına göre).

    Amaç: '5 kişi aynı şeyi istemiş' durumunu görmek. Basit bir yaklaşım —
    kelime kümesi kesişimi %40'ı geçiyorsa aynı grup sayılır.
    """
    # Çok yaygın kelimeler gruplamayı bozar ("için", "olan", "gibi"...)
    DURAK = {"için", "icin", "olan", "gibi", "daha", "sonra", "ancak", "bunu",
             "şunu", "sunu", "bize", "bana", "oluyor", "yapıyor", "yapiyor",
             "lazım", "lazim", "gerek", "diye", "kadar", "çünkü", "cunku"}

    def kelimeler(t):
        # Konu başlığı 2 kez sayılır — aynı konudaki talepler daha iyi eşleşsin
        m = _norm(f"{t.get('konu','')} {t.get('konu','')} {t.get('mesaj','')}")
        return {w for w in re.findall(r"[a-zçğıöşü0-9]{4,}", m) if w not in DURAK}

    gruplar = []
    for t in talepler:
        k = kelimeler(t)
        if not k:
            gruplar.append([t])
            continue
        yerlesti = False
        for g in gruplar:
            k0 = kelimeler(g[0])
            if not k0:
                continue
            ortak = len(k & k0) / max(1, min(len(k), len(k0)))
            if ortak >= 0.28:
                g.append(t)
                yerlesti = True
                break
        if not yerlesti:
            gruplar.append([t])
    return gruplar


def analiz_et(t):
    metin = f"{t.get('konu','')} {t.get('mesaj','')}"
    seviye, gerekce = risk_bul(metin)
    return {
        "id": t.get("id"),
        "gonderen": t.get("gonderen") or "?",
        "konu": (t.get("konu") or "").strip()[:70],
        "mesaj": (t.get("mesaj") or "").strip(),
        "tarih": str(t.get("olusturma_tarihi") or "")[:10],
        "tur": tur_bul(metin),
        "risk": seviye,
        "risk_gerekce": gerekce,
        "moduller": modul_bul(metin),
        "otomatik_uygun": seviye == "dusuk",
    }


TUR_SIMGE = {"hata": "🔴", "iyilestirme": "🟡",
             "yeni_ozellik": "🔵", "belirsiz": "⚪"}
RISK_SIMGE = {"yuksek": "⛔", "orta": "⚠️", "dusuk": "✅"}


def rapor_yaz(gruplar, toplam_acik):
    s = []
    s.append("TALEP ANALİZİ  ·  " + datetime.now(TR).strftime("%d.%m.%Y %H:%M"))
    s.append("=" * 46)
    s.append(f"{toplam_acik} açık talep · {len(gruplar)} konu")
    s.append("")

    # Risk sırasına göre: önce insan bakması gerekenler
    sira = {"yuksek": 0, "orta": 1, "dusuk": 2}
    gruplar = sorted(gruplar, key=lambda g: (sira.get(g[0]["risk"], 3), -len(g)))

    for g in gruplar:
        a = g[0]
        kac = len(g)
        s.append(f"{TUR_SIMGE.get(a['tur'],'⚪')} {RISK_SIMGE.get(a['risk'],'')} "
                 f"{a['konu'] or '(konusuz)'}")
        s.append(f"   modül: {' · '.join(a['moduller'])}"
                 + (f"   ({kac} kişi istedi)" if kac > 1 else ""))
        if a["risk_gerekce"]:
            s.append(f"   riskli alan: {', '.join(a['risk_gerekce'])}")
        s.append(f"   {a['gonderen']} · {a['tarih']}")
        _m = a["mesaj"].replace("\n", " ")[:110]
        if _m:
            s.append(f"   \"{_m}\"")
        s.append("")

    dusuk = [g for g in gruplar if g[0]["risk"] == "dusuk"]
    yuksek = [g for g in gruplar if g[0]["risk"] == "yuksek"]
    s.append("-" * 46)
    s.append(f"✅ otomatik uygun aday : {len(dusuk)}")
    s.append(f"⛔ elle bakılmalı      : {len(yuksek)}")
    s.append("")
    s.append("NOT: Bu analiz KOD DEĞİŞTİRMEZ. Yalnız sınıflandırır.")
    return "\n".join(s)


def telegram(metin):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("\n(Telegram atlandı — token/chat id yok)")
        return
    import requests
    for c in [x.strip() for x in chat.split(",") if x.strip()]:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": c, "text": f"<pre>{metin}</pre>",
                      "parse_mode": "HTML"}, timeout=20)
            print(f"Telegram {c}: {r.status_code}")
        except Exception as e:
            print(f"Telegram {c} hata: {e}")


def main():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("HATA: SUPABASE_URL / SUPABASE_KEY eksik.")
        sys.exit(1)

    from supabase import create_client
    sb = create_client(url, key)

    try:
        rows = (sb.table("talepler").select("*")
                .order("olusturma_tarihi", desc=True).limit(300).execute().data) or []
    except Exception as e:
        print(f"HATA: talepler okunamadı — {e}")
        sys.exit(1)

    acik = [t for t in rows if str(t.get("durum") or "").strip() != "tamamlandi"]
    if not acik:
        rapor = ("TALEP ANALİZİ  ·  "
                 + datetime.now(TR).strftime("%d.%m.%Y %H:%M")
                 + "\n" + "=" * 46 + "\nAçık talep yok.")
        print(rapor)
        telegram(rapor)
        return

    analizler = [analiz_et(t) for t in acik]
    gruplar = benzer_grupla(analizler)
    rapor = rapor_yaz(gruplar, len(acik))
    print(rapor)
    telegram(rapor)

    # İsteğe bağlı: analizi talep kaydına işle (YAZ=1)
    if os.environ.get("YAZ", "").strip() == "1":
        n = 0
        for a in analizler:
            try:
                sb.table("talepler").update({
                    "analiz_tur": a["tur"],
                    "analiz_risk": a["risk"],
                    "analiz_modul": " · ".join(a["moduller"]),
                }).eq("id", a["id"]).execute()
                n += 1
            except Exception:
                pass          # kolonlar yoksa sessiz geç — rapor yine üretildi
        print(f"\n{n} talebe analiz işlendi.")


if __name__ == "__main__":
    main()
