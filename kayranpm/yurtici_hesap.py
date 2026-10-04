# -*- coding: utf-8 -*-
"""Yurt içi alış / yerli üretim — saf hesaplar ve doğrulama (Ekim 2026).

Alımlar ithalat dosyalarıyla aynı tablolarda tutulur (ithalat_dosyalari.alim_turu, veritabani/18):
paçal maliyet, stok kartı alımları, Model sorgu ve FIFO stok yaşı onları kendiliğinden kullanır.
Tutarlar ithalatta olduğu gibi USD saklanır; TL girilen alımda kur ile çevrilir, 'doviz' girişin
para birimini, 'kur' TL/USD kurunu tutar (düzenlemede TL tutarlar geri hesaplanır).

Birim maliyet ithalatla AYNI kural (ithalat.database.dosya_hesapla): masraf oranı = toplam masraf /
mal bedeli; birim maliyet = birim fiyat × (1 + oran). Fiyatlar KDV HARİÇ girilir.
Testler: tests/test_yurtici_alis.py.
"""

TURLER = {"yurtici": "Yurt içi satın alma", "yerli": "Yerli üretim"}
MASRAFLAR = [("nakliye", "Nakliye"), ("diger", "Diğer")]
STOK_EKLE = "Stoğa ekle — yeni alım"
STOK_VAR = "Mal zaten depoda — geçmiş alımı kaydediyorum"
SATILABILIR_DEPOLAR = ["MERKEZ DEPO", "HAPPY LIFE"]


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def usd(tutar, para, kur):
    """Giriş para birimindeki tutarı USD'ye çevirir (TL / kur)."""
    return _f(tutar) / _f(kur) if str(para).upper() == "TL" and _f(kur) > 0 else _f(tutar)


def giris_tutari(tutar_usd, para, kur):
    """Saklanan USD tutarı giriş para birimine geri çevirir (düzenleme ekranı)."""
    return _f(tutar_usd) * _f(kur) if str(para).upper() == "TL" and _f(kur) > 0 else _f(tutar_usd)


def maliyet_hesapla(kalemler, masraflar, para, kur):
    """kalemler: [{sku, adet, fiyat}] (giriş para biriminde, KDV hariç); masraflar: {slug: tutar}.
    Döner: {mal_bedeli, masraf, oran (yüzde), satirlar:[{sku, adet, fiyat, birim_usd, maliyet_usd}]}
    — mal_bedeli / masraf giriş para biriminde, birim tutarlar USD."""
    sat = [k for k in (kalemler or []) if str(k.get("sku") or "").strip() and _f(k.get("adet")) > 0]
    mal = sum(_f(k["adet"]) * _f(k.get("fiyat")) for k in sat)
    masraf = sum(_f(v) for v in (masraflar or {}).values())
    oran = (masraf / mal * 100) if mal > 0 else 0.0
    out = []
    for k in sat:
        b = usd(k.get("fiyat"), para, kur)
        out.append({"sku": str(k["sku"]).strip(), "adet": _f(k["adet"]), "fiyat": _f(k.get("fiyat")),
                    "birim_usd": b, "maliyet_usd": b * (1 + oran / 100)})
    return {"mal_bedeli": mal, "masraf": masraf, "oran": oran, "satirlar": out}


def dogrula(f, kart_skulari):
    """Kayıttan önce eksikleri listeler (boş liste = kaydedilebilir).
    f: {tur, belge, alis_tarihi, giris_tarihi, depo, para, kur, kalemler, masraflar}."""
    h = []
    if f.get("tur") not in TURLER:
        h.append("Alım türü seçilmedi.")
    if not f.get("alis_tarihi"):
        h.append("Alış tarihi boş.")
    if not f.get("giris_tarihi"):
        h.append("Depoya giriş tarihi boş (stok yaşı bu tarihten başlar).")
    elif f.get("alis_tarihi") and str(f["giris_tarihi"]) < str(f["alis_tarihi"]):
        h.append("Depoya giriş tarihi alış tarihinden önce olamaz.")
    if f.get("depo") not in SATILABILIR_DEPOLAR:
        h.append("Teslim deposu seçilmedi.")
    if str(f.get("para")).upper() == "TL" and _f(f.get("kur")) <= 0:
        h.append("TL alımda kur girilmeli.")
    kart = {str(s).strip() for s in (kart_skulari or ())}
    dolu = [k for k in (f.get("kalemler") or []) if str(k.get("sku") or "").strip()
            or _f(k.get("adet")) or _f(k.get("fiyat"))]
    if not dolu:
        h.append("En az bir kalem girilmeli.")
    for i, k in enumerate(dolu, 1):
        s = str(k.get("sku") or "").strip()
        if not s:
            h.append(f"{i}. kalemde SKU boş.")
        elif kart and s not in kart:
            h.append(f"{s}: ürün kartı yok (önce Tüm ürünler'den kart açılmalı).")
        if _f(k.get("adet")) <= 0:
            h.append(f"{s or str(i) + '. kalem'}: adet girilmedi.")
        if _f(k.get("fiyat")) <= 0:
            h.append(f"{s or str(i) + '. kalem'}: birim fiyat girilmedi (maliyet eksik kalır).")
    if any(_f(v) < 0 for v in (f.get("masraflar") or {}).values()):
        h.append("Masraf eksi olamaz.")
    return h


def kayit_argumanlari(f, ad_bul=None):
    """ithalat.database.ekle_dosya / guncelle_dosya için alanlar (USD'ye çevrilmiş)."""
    para, kur = str(f.get("para") or "USD").upper(), _f(f.get("kur")) or 1.0
    kalemler = [{"sku": str(k["sku"]).strip(),
                 "urun_adi": (ad_bul(str(k["sku"]).strip()) if ad_bul else "") or "",
                 "adet": _f(k["adet"]), "birim_fob": usd(k.get("fiyat"), para, kur)}
                for k in (f.get("kalemler") or [])
                if str(k.get("sku") or "").strip() and _f(k.get("adet")) > 0]
    masraf = {s: round(usd(v, para, kur), 6) for s, v in (f.get("masraflar") or {}).items() if _f(v) > 0}
    return {"dosya_no": str(f.get("belge") or "").strip() or belge_no(f.get("tur"), f.get("alis_tarihi")),
            "tarih": str(f.get("alis_tarihi"))[:10], "tedarikci": str(f.get("firma") or "").strip(),
            "doviz": para, "kur": kur if para == "TL" else 1.0, "masraflar": masraf,
            "notlar": str(f.get("not") or "").strip(), "kalemler": kalemler,
            "teslim_tarihi": str(f.get("giris_tarihi"))[:10], "teslim_deposu": f.get("depo"),
            "alim_turu": f.get("tur")}


def belge_no(tur, tarih):
    """Belge no girilmezse: YI-20261004 / YU-20261004 (yurt içi / yerli üretim)."""
    on = "YU" if tur == "yerli" else "YI"
    return f"{on}-{str(tarih or '')[:10].replace('-', '')}"


def formdan(dosya, kalemler):
    """Kayıtlı alımı düzenleme formuna çevirir (USD → giriş para birimi)."""
    para = str(dosya.get("doviz") or "USD").upper()
    kur = _f(dosya.get("kur")) or 1.0
    m = dosya.get("masraflar") or {}
    if isinstance(m, str):
        import json
        try:
            m = json.loads(m)
        except ValueError:
            m = {}
    return {"tur": str(dosya.get("alim_turu") or "yurtici"), "belge": dosya.get("dosya_no") or "",
            "firma": dosya.get("tedarikci") or "", "alis_tarihi": str(dosya.get("tarih") or "")[:10],
            "giris_tarihi": str(dosya.get("teslim_tarihi") or "")[:10], "depo": dosya.get("teslim_deposu") or "",
            "para": para, "kur": kur, "not": dosya.get("notlar") or "",
            "masraflar": {s: round(giris_tutari(m.get(s), para, kur), 4) for s, _a in MASRAFLAR},
            "kalemler": [{"sku": k.get("sku") or "", "adet": _f(k.get("adet")),
                          "fiyat": round(giris_tutari(k.get("birim_fob"), para, kur), 4)} for k in kalemler or []]}


# ── Alış tarihinin kuru (Ekim 2026) ─────────────────────────────────
# Uygulamanın kur tablosu (kur_gunluk) 28.06.2026'dan beri tutuluyor; daha eski bir alışta form
# BUGÜNÜN kurunu getiriyordu (Aralık 2025 alımına 49,14). Artık alış tarihinin kuru aranır:
# TCMB döviz satış (o gün yayın yoksa — hafta sonu / tatil — önceki iş günü), yoksa kur tablosunun
# O GÜNKÜ kaydı. Hiçbiri yoksa 0 döner ve kullanıcı faturadaki kuru girer; bugünün kuru KULLANILMAZ.
def tcmb_url(gun):
    """TCMB günlük kur dosyası: https://www.tcmb.gov.tr/kurlar/202512/01122025.xml"""
    return f"https://www.tcmb.gov.tr/kurlar/{gun:%Y%m}/{gun:%d%m%Y}.xml"


def tcmb_usd_satis(xml_metni):
    """TCMB XML'inden USD döviz satış kuru (yoksa None)."""
    import xml.etree.ElementTree as ET
    try:
        kok = ET.fromstring(xml_metni)
    except ET.ParseError:
        return None
    for c in kok.iter("Currency"):
        if (c.get("CurrencyCode") or c.get("Kod")) == "USD":
            for alan in ("ForexSelling", "BanknoteSelling"):
                v = _f((c.findtext(alan) or "").replace(",", "."))
                if v > 0:
                    return v / (_f(c.findtext("Unit")) or 1.0)
    return None


def tarihli_kur(tarih, tcmb_getir, tablo_kuru, geri_gun=7):
    """(kur, kaynak açıklaması). tcmb_getir(date) → XML metni | None; tablo_kuru('YYYY-MM-DD') → kur | None."""
    from datetime import date, timedelta
    try:
        g0 = date.fromisoformat(str(tarih)[:10])
    except ValueError:
        return 0.0, ""
    for i in range(geri_gun + 1):
        g = g0 - timedelta(days=i)
        xml = tcmb_getir(g)
        k = tcmb_usd_satis(xml) if xml else None
        if k:
            return round(k, 4), f"TCMB döviz satış {g:%d.%m.%Y}"
    k = _f(tablo_kuru(g0.isoformat()))
    if k > 0:
        return round(k, 4), f"uygulamanın kur kaydı {g0:%d.%m.%Y}"
    return 0.0, ""
