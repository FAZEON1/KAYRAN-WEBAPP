# -*- coding: utf-8 -*-
"""Soru kutusu — Türkçe soruyu parçalarına ayırır (Ekim 2026). Yapay zekâ YOK, kural tabanlı.

"geçen ay D-MARKET'te en çok kâr bıraktıran 5 monitör"
  → {tip: satis, olcu: net_kar, kirilim: urun, firma: D-MARKET, kategori: MONİTÖR,
     donem: Eylül 2026, sira: azalan, limit: 5}

Saf fonksiyonlar (Streamlit ve veritabanı yok): coz, donem_bul, sade. Firma / kategori /
marka / SKU adları VERİDEN gelir (sozluk); burada sabit ad listesi yok. Cevabı
shared/soru_cevap.py üretir; ekran shared/soru_ekran.py.
"""
import re
from datetime import date, timedelta

_HARF = str.maketrans("çğıöşüâîûÇĞIİÖŞÜÂÎÛ", "cgiosuaiuCGIIOSUAIU")

AYLAR = ["ocak", "subat", "mart", "nisan", "mayis", "haziran", "temmuz", "agustos", "eylul",
         "ekim", "kasim", "aralik"]
AY_AD = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül",
         "Ekim", "Kasım", "Aralık"]

OLCU_AD = {"net_kar": "Net kâr", "ciro": "Ciro", "adet": "Adet", "marj": "Marj"}
KIRILIM_AD = {"urun": "Ürün", "firma": "Firma", "kategori": "Kategori", "marka": "Marka", "ay": "Ay"}
TIP_AD = {"satis": "Satış", "seyir": "Aylık seyir", "iade": "İade", "stok": "Stok",
          "yasli_stok": "Yaşlı stok", "ariza": "Arıza oranı", "kampanya": "Kampanya",
          "odeme": "Ödemeler", "cek": "Çekler", "urun": "Ürün özeti"}
KAPSAM_AD = {"gecikmis": "Vadesi geçen", "bugun": "Bugün", "yarin": "Yarın", "hafta": "Bu hafta",
             "bekleyen": "Bekleyen"}
KAMPANYA_AD = {"suruyor": "Süren", "bekliyor": "Kapanmayı bekleyen", "yaklasan": "Yaklaşan",
               "kapali": "Kapalı"}

# Firma eş adları: mağaza adı → cari adının ilk kelimesi (ekranda cari adı görünür)
FIRMA_ESLERI = {"hepsiburada": "d-market", "hb": "d-market", "dmarket": "d-market",
                "itopya": "eera", "monday": "monday"}

# Kategori / marka sanılmaması gereken sıradan kelimeler
_YASAK = {"en", "ve", "ile", "bu", "su", "o", "ay", "yil", "gun", "kar", "net", "cok", "az", "ilk",
          "son", "ne", "kac", "hangi", "toplam", "stok", "satis", "ciro", "adet", "urun", "model",
          "firma", "diger", "genel", "marka", "kategori", "iade", "ariza", "kampanya"}


def sade(s):
    """Karşılaştırma biçimi: Türkçe-doğru küçük harf, Türkçe harfsiz, kesme işareti boşluk.
    "D-MARKET'te Monitörler" → "d-market te monitorler"."""
    s = str(s or "").replace("İ", "i").replace("I", "ı").lower().translate(_HARF)
    s = re.sub(r"[’'`´]", " ", s)
    s = re.sub(r"[^\w\s\-./]", " ", s)
    return " ".join(s.split())


def _kelimeler(s):
    return [k.strip(".,") for k in s.split() if k.strip(".,")]


def _var(metin, *kaliplar):
    """Kalıplardan biri metinde kelime başında geçiyor mu (ekler serbest: 'kârı', 'cirosu')."""
    return any(re.search(r"(?:^|[\s\-/])" + k, metin) for k in kaliplar)


def _ek_tolerans(kelime, kok):
    """'monitorler' / 'monitoru' / 'monitorde' → 'monitor' kökü. Kök en az 3 harf; ek en çok 8 harf."""
    return len(kok) >= 3 and kelime.startswith(kok) and len(kelime) - len(kok) <= 8   # 'kartlarının


# ── Dönem ───────────────────────────────────────────────────────────
def _ay_son(y, m):
    return (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1))


def _ceyrek(y, q):
    b = date(y, 3 * (q - 1) + 1, 1)
    return b, _ay_son(y, 3 * q)


def donem_bul(m, bugun):
    """Metindeki dönem → {bas, bit, ad} ya da None. m: sade() edilmiş metin."""
    def d(b, e, ad):
        return {"bas": b, "bit": min(e, bugun) if b <= bugun else e, "ad": ad}

    yil_m = re.search(r"\b(20\d\d)\b", m)
    yil = int(yil_m.group(1)) if yil_m else None

    n = re.search(r"\bson (\d+) (gun|hafta|ay)", m)
    if n:
        k, b = int(n.group(1)), n.group(2)
        gun = k if b == "gun" else (7 * k if b == "hafta" else 30 * k)
        return d(bugun - timedelta(days=gun - 1), bugun, f"Son {k} {'gün' if b == 'gun' else b}")
    if _var(m, "bugun"):
        return d(bugun, bugun, "Bugün")
    if _var(m, "dun\\b", "dunku"):
        x = bugun - timedelta(days=1)
        return d(x, x, "Dün")
    if _var(m, "bu hafta"):
        return d(bugun - timedelta(days=bugun.weekday()), bugun, "Bu hafta")
    if _var(m, "gecen hafta"):
        p = bugun - timedelta(days=bugun.weekday())
        return d(p - timedelta(days=7), p - timedelta(days=1), "Geçen hafta")
    q = re.search(r"\b(?:q([1-4])|([1-4])\s*\.?\s*ceyrek)", m)
    if q:
        qq = int(q.group(1) or q.group(2))
        y = yil or bugun.year
        b, e = _ceyrek(y, qq)
        return d(b, e, f"{qq}. çeyrek {y}")
    if _var(m, "bu ceyrek"):
        qq = (bugun.month - 1) // 3 + 1
        b, _ = _ceyrek(bugun.year, qq)
        return d(b, bugun, "Bu çeyrek")
    if _var(m, "gecen ceyrek"):
        qq = (bugun.month - 1) // 3
        y = bugun.year
        if qq == 0:
            qq, y = 4, y - 1
        b, e = _ceyrek(y, qq)
        return d(b, e, f"{qq}. çeyrek {y}")
    if _var(m, "bu ay"):
        return d(bugun.replace(day=1), bugun, "Bu ay")
    if _var(m, "gecen ay"):
        s = bugun.replace(day=1) - timedelta(days=1)
        return d(s.replace(day=1), s, f"{AY_AD[s.month - 1]} {s.year}")
    for i, a in enumerate(AYLAR):
        if re.search(r"(?:^|\s)" + a, m):
            y = yil or (bugun.year if i + 1 <= bugun.month else bugun.year - 1)
            return d(date(y, i + 1, 1), _ay_son(y, i + 1), f"{AY_AD[i]} {y}")
    if _var(m, "bu yil", "bu sene", "yil basindan"):
        return d(date(bugun.year, 1, 1), bugun, "Bu yıl")
    if _var(m, "gecen yil", "gecen sene", "gecen sezon"):
        y = bugun.year - 1
        return d(date(y, 1, 1), date(y, 12, 31), str(y))
    if yil:
        return d(date(yil, 1, 1), date(yil, 12, 31), str(yil))
    if _var(m, "tum zaman", "tumu", "simdiye kadar", "bugune kadar", "toplamda"):
        return d(date(2020, 1, 1), bugun, "Tüm zamanlar")
    return None


# ── Ad eşleştirme (veriden) ─────────────────────────────────────────
def firma_bul(m, firmalar, haric=()):
    """firmalar: {görünen ad: [kanal adı…]}. Görünen adın ilk kelimesi (ya da eş adı) metinde
    geçiyorsa o firma. Aynı ilk kelimeli cariler BİRLİKTE sayılır (eski / yeni unvan, TL / USD
    carisi). İlk kelimesi sıradan kelime ya da kategori / marka adı olan cari ('TEKNİK SERVİS',
    'MONİTÖR …') firma sayılmaz. Döner: (görünen ad, [kanal…]) ya da (None, [])."""
    kel = _kelimeler(m)
    esle = {}
    for ad, kanallar in (firmalar or {}).items():
        ilk = sade(ad).split(" ")[0] if ad else ""
        if len(ilk) < 2 or ilk in _YASAK or ilk in haric:
            continue
        if ilk in esle:
            esle[ilk] = (esle[ilk][0], list(esle[ilk][1]) + [k for k in kanallar if k not in esle[ilk][1]])
        else:
            esle[ilk] = (ad, list(kanallar))
    for k in kel:
        hedef = FIRMA_ESLERI.get(k, k)
        if hedef in esle:
            return esle[hedef]
        for ilk, v in esle.items():
            if len(ilk) >= 4 and _ek_tolerans(k, ilk):      # 'vatanda', 'eerada'
                return v
    return None, []


_KISA_EK = {"ler", "lar", "leri", "lari", "de", "da", "te", "ta", "in", "un", "nin", "nun", "e", "a", "i", "u"}


def _kok(s):
    """İyelik ekini at: 'kamerasi' → 'kamera', 'karti' → 'kart' ('kameralari', 'kartlar' de uysun)."""
    for ek in ("si", "i", "u"):
        if s.endswith(ek) and len(s) - len(ek) >= 3:
            return s[: -len(ek)]
    return s


def _kelime_uyar(k, s):
    if k == s:
        return True
    if len(s) == 3:                                    # ssd, ram, mio: yalnız bilinen kısa ekler
        return k.startswith(s) and k[3:] in _KISA_EK
    return _ek_tolerans(k, _kok(s)) and len(_kok(s)) >= 3


def _ad_bul(m, adlar, haric=()):
    """Metinde geçen ilk ad (kategori / marka). En uzun eşleşme kazanır ('oyuncu koltuğu' > 'koltuk').
    Çok kelimeli adda son kelime çekimli olabilir ('araç kameraları', 'ekran kartları')."""
    kel = _kelimeler(m)
    en, en_uz = None, 0
    for ad in adlar or ():
        s = sade(ad)
        if not s or s in _YASAK or s in haric or len(s) < 2:
            continue
        parca = s.split(" ")
        if len(parca) > 1:
            for i in range(len(kel) - len(parca) + 1):
                if kel[i:i + len(parca) - 1] == parca[:-1] and _kelime_uyar(kel[i + len(parca) - 1], parca[-1]):
                    if len(s) > en_uz:
                        en, en_uz = ad, len(s)
            continue
        for k in kel:
            if _kelime_uyar(k, s) and len(s) > en_uz:
                en, en_uz = ad, len(s)
    return en


def sku_bul(metin, skular):
    """Metinde kayıtlı bir SKU var mı (büyük/küçük harf ve tire farkı yok sayılır)."""
    if not skular:
        return None
    for t in re.split(r"[\s,;']+", str(metin or "")):
        k = re.sub(r"[^0-9A-Za-z]", "", t).upper()
        if len(k) >= 5 and k in skular:
            return skular[k]
    return None


# ── Ana çözümleyici ─────────────────────────────────────────────────
def coz(metin, sozluk=None, bugun=None):
    """Soru → niyet sözlüğü. sozluk: {firmalar: {ad: [kanal]}, kategoriler: [..], markalar: [..],
    skular: {ANAHTAR: sku}}. Anlaşılmazsa tip None ve 'oneri' dolu döner."""
    sozluk = sozluk or {}
    bugun = bugun or date.today()
    m = sade(metin)
    n = {"metin": str(metin or "").strip(), "tip": None, "olcu": None, "kirilim": None,
         "donem": None, "donem_varsayilan": False, "firma": None, "kanallar": [], "kategori": None,
         "marka": None, "sku": None, "sira": None, "limit": None, "esik": None, "kapsam": None,
         "kampanya_durum": None}
    if not m:
        return n

    n["donem"] = donem_bul(m, bugun)
    _adlar = {sade(x) for x in list(sozluk.get("kategoriler") or []) + list(sozluk.get("markalar") or [])}
    _adlar |= {"teknik", "servis", "donanim", "bilgisayar", "elektronik", "teknoloji", "bilisim"}
    n["firma"], n["kanallar"] = firma_bul(m, sozluk.get("firmalar"), haric=_adlar)
    n["kategori"] = _ad_bul(m, sozluk.get("kategoriler"))
    _kat_s = sade(n["kategori"]) if n["kategori"] else ""
    n["marka"] = _ad_bul(m, sozluk.get("markalar"), haric={_kat_s} | {sade(n["firma"] or "").split(" ")[0]})
    n["sku"] = sku_bul(metin, sozluk.get("skular"))

    # Sıra ve sayı
    if _var(m, "en az", "en dusuk", "en kotu", "en zayif", "en cok zarar", "zarar"):
        n["sira"] = "artan"
    if _var(m, "en cok", "en fazla", "en yuksek", "en iyi", "en karli", "en buyuk", "lider", "zirve"):
        n["sira"] = n["sira"] or "azalan"
    lim = re.search(r"\b(?:ilk|top)\s*(\d{1,3})\b", m) or re.search(
        r"\b(\d{1,3})\s+(?!gun|gunu|gunden|hafta|ay\b|ayl|yil|sene|adet|tane|\.?\s*ceyrek)[a-z]", m)
    if lim:
        n["limit"] = int(lim.group(1))
        n["sira"] = n["sira"] or "azalan"

    # Ölçü
    if _var(m, "marj", "karlilik oran", "kar oran", "kar yuzde"):
        n["olcu"] = "marj"
    elif _var(m, r"kar(?:i|in|ini|li|lilik|lar|imiz)?\b", "kazan", "birak", "zarar"):
        n["olcu"] = "net_kar"
    elif _var(m, "ciro", "hasilat", "satis tutar", "satis geliri"):
        n["olcu"] = "ciro"
    elif _var(m, "adet", "kac tane", "kac adet", "tane", "en cok sat", "en az sat", "satan", "satil"):
        n["olcu"] = "adet"

    # Kırılım
    if _var(m, "firma", "musteri", "kanal", "cari", "bayi", "pazar yeri", "pazaryeri"):
        n["kirilim"] = "firma"
    elif _var(m, "kategori"):
        n["kirilim"] = "kategori"
    elif _var(m, "marka"):
        n["kirilim"] = "marka"
    elif _var(m, "urun", "model", "sku", "hangi"):
        n["kirilim"] = "urun"
    if _var(m, "aylik", "ay ay", "aylara gore", "seyir", "trend", "gidisat", "ay bazinda"):
        n["kirilim"] = "ay"

    # Tip (öncelik sırasıyla)
    gun_m = re.search(r"\b(\d{2,4})\s*gun", m)
    if _var(m, "cek\\b", "cekler", "ceki\\b", "ceklerin"):
        n["tip"] = "cek"
    elif _var(m, "odeme", "odenec", "odeyec", "odenme", "vadesi", "vade\\b", "borc"):
        n["tip"] = "odeme"
        n["kapsam"] = ("gecikmis" if _var(m, "gecik", "vadesi gec", "vadesi dol", "geciken")
                       else "bugun" if _var(m, "bugun") else "yarin" if _var(m, "yarin")
                       else "hafta" if _var(m, "hafta") else "bekleyen")
    elif _var(m, "kampanya"):
        n["tip"] = "kampanya"
        n["kampanya_durum"] = ("suruyor" if _var(m, "suren", "aktif", "devam", "acik")
                               else "bekliyor" if _var(m, "kapanmay", "bitmis", "biten", "bekleyen")
                               else "yaklasan" if _var(m, "yaklasan", "baslayacak", "gelecek")
                               else "kapali" if _var(m, "kapali", "kapanmis", "kapanan") else None)
    elif _var(m, "ariza", "bozul", "bozuk", "defolu"):
        n["tip"] = "ariza"
    elif _var(m, "stok", "stog", "elde", "depoda", "envanter") and (gun_m or _var(m, "yasli", "eski stok", "bekleyen stok")):
        n["tip"] = "yasli_stok"
        n["esik"] = int(gun_m.group(1)) if gun_m else 90
    elif _var(m, "stok", "stog", "elde ne", "elde kac", "depoda", "envanter", "kac tane var"):
        n["tip"] = "stok"
    elif _var(m, "iade"):
        n["tip"] = "iade"
    elif n["kirilim"] == "ay":
        n["tip"] = "seyir"
    elif n["olcu"] or _var(m, "satis", "sattik", "sattig", "satt", "satan", "satil"):
        n["tip"] = "satis"
    elif n["sku"]:
        n["tip"] = "urun"
    elif n["firma"] and not n["kategori"]:
        n["tip"] = "satis"                         # "D-MARKET bu ay" → firmanın özeti

    # Varsayılanlar
    if n["tip"] in ("satis", "seyir", "iade", "ariza") and not n["donem"]:
        n["donem"] = {"bas": date(bugun.year, 1, 1), "bit": bugun, "ad": "Bu yıl"}
        n["donem_varsayilan"] = True
    if n["tip"] == "satis":
        n["olcu"] = n["olcu"] or "net_kar"
        if n["kirilim"] is None and (n["sira"] or n["limit"]):
            n["kirilim"] = "urun"
    if n["tip"] == "seyir":
        n["olcu"] = n["olcu"] if n["olcu"] in ("ciro", "net_kar", "adet") else "ciro"
    if n["tip"] in ("iade", "ariza", "yasli_stok", "stok") and n["kirilim"] in (None, "ay", "firma"):
        n["kirilim"] = "urun" if n["tip"] != "stok" or n["sira"] or n["limit"] else None
    if n["tip"] in ("satis", "iade", "ariza", "yasli_stok", "stok") and n["kirilim"]:
        n["sira"] = n["sira"] or "azalan"
        if n["kirilim"] == "urun" and n["tip"] != "yasli_stok":      # yaşlı stok: listenin tamamı
            n["limit"] = n["limit"] or 10
    if n["tip"] == "urun" or (n["sku"] and n["tip"] in ("stok", "satis") and not n["kirilim"]):
        n["tip"] = "urun" if not n["olcu"] or n["tip"] == "stok" else n["tip"]
    return n


def parcalar(n):
    """Ekranda gösterilecek anlaşılan parçalar: [(tür, etiket)]."""
    if not n.get("tip"):
        return []
    p = [("Konu", TIP_AD[n["tip"]])]
    if n["tip"] == "satis" and n.get("olcu"):
        p.append(("Ölçü", OLCU_AD[n["olcu"]]))
    if n["tip"] == "seyir":
        p.append(("Ölçü", OLCU_AD.get(n["olcu"], "Ciro")))
    if n.get("donem") and n["tip"] in ("satis", "seyir", "iade", "ariza"):
        p.append(("Dönem", n["donem"]["ad"] + (" (varsayılan)" if n.get("donem_varsayilan") else "")))
    if n.get("firma"):
        p.append(("Firma", n["firma"]))
    if n.get("kategori"):
        p.append(("Kategori", n["kategori"]))
    if n.get("marka"):
        p.append(("Marka", n["marka"]))
    if n.get("sku"):
        p.append(("Ürün", n["sku"]))
    if n.get("kirilim") and n["tip"] not in ("seyir",):
        p.append(("Kırılım", KIRILIM_AD[n["kirilim"]]))
    if n.get("esik"):
        p.append(("Eşik", f"{n['esik']} günden eski"))
    if n.get("kapsam"):
        p.append(("Kapsam", KAPSAM_AD[n["kapsam"]]))
    if n.get("kampanya_durum"):
        p.append(("Durum", KAMPANYA_AD[n["kampanya_durum"]]))
    if n.get("kirilim") and n["tip"] != "seyir" and (n.get("limit") or n.get("sira")):
        ust = f" {n['limit']}" if n.get("limit") else ""
        p.append(("Sıra", ("En yüksek" if n.get("sira") != "artan" else "En düşük") + ust))
    return p


ORNEKLER = [
    "Geçen ay D-MARKET'te en çok kâr bıraktıran 5 monitör",
    "Bu yıl firmalara göre ciro",
    "Bu yıl aylık net kâr",
    "Bu çeyrek en çok iade edilen ürünler",
    "120 günü geçen stok",
    "Bu çeyrek arıza oranı en yüksek 10 model",
    "Süren kampanyalar",
    "Vadesi geçen ödemeler",
    "Bekleyen çekler",
]
