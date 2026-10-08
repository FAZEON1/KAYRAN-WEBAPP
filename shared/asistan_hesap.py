# -*- coding: utf-8 -*-
"""Asistanlar — saf hesaplar (Ekim 2026). Streamlit'e ve veritabanına bağlı değil; hem uygulama hem
GitHub / claude.ai görevleri (otonom/telegram_soru.py, otonom/asistan_db.py) kullanır.

Telegram asistanı
  kimlik_kullanici(harita, kimlik)   Telegram kimliği → program kullanıcısı (tanımsızsa None)
  telegram_yanit(cevap)              soru kutusu cevabı → Telegram HTML mesajı (en fazla 10 satır tablo)
  yardim_metni(ornekler, kimlik, kullanici)
Gümrük danışmanı
  sonuc_dogrula(sonuc)               görevin yazdığı sonuç beklenen biçimde mi? → (sonuc, hatalar)
  vergi_hesabi(sorgu, oranlar)       CIF + gümrük vergisi + ilave gümrük vergisi + KDV (öneri)
Pazar araştırmacısı
  brifing_blogu(raporlar)            sabah brifingine eklenecek kısa blok
"""
import html

TELEGRAM_SINIR = 3800          # Telegram tek mesaj 4096 karakter; pay bırakılır
TABLO_SATIR = 10


# ── Telegram ────────────────────────────────────────────────────────
def kimlik_kullanici(harita, kimlik):
    """harita: {"123456": "ibrahim"} (sistem_ayarlari 'telegram_kullanicilar')."""
    k = str(kimlik or "").strip()
    v = (harita or {}).get(k)
    return str(v).strip().lower() if v and str(v).strip() else None


def komut(metin):
    """'/start', '/yardim@KayranBot' → 'start' / 'yardim'; komut değilse ''."""
    m = str(metin or "").strip()
    if not m.startswith("/"):
        return ""
    return m[1:].split()[0].split("@")[0].lower() if len(m) > 1 else ""


def _e(v):
    return html.escape(str(v if v is not None else ""))


def _sayi(v):
    tr = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return tr[:-3] if tr.endswith(",00") else tr


def _satir(r):
    """{'Ürün': 'X', 'Stok': 12, 'Maliyet ($)': 1234.5} → 'X · Stok 12 · Maliyet ($) 1.234,50'."""
    metin, sayi = [], []
    for k, v in r.items():
        if isinstance(v, bool) or v is None or not str(v).strip():
            continue
        if isinstance(v, (int, float)):
            sayi.append(f"{k} {_sayi(v)}")
        else:
            metin.append(str(v))
    return " · ".join(metin + sayi)


def telegram_yanit(cevap):
    """shared.soru_cevap.cevapla çıktısı → Telegram HTML metni. Cevap yoksa ''."""
    if not cevap:
        return ""
    s = [f"<b>{_e(cevap.get('baslik') or 'Cevap')}</b>"]
    if cevap.get("yetki"):
        return "\n".join(s + [_e(cevap["yetki"])])
    for u in cevap.get("uyarilar") or []:
        s.append(f"<i>{_e(u)}</i>")
    if cevap.get("bos"):
        return "\n".join(s + [_e(cevap["bos"])])
    for k in cevap.get("kartlar") or []:
        alt = f" <i>({_e(k['alt'])})</i>" if k.get("alt") else ""
        s.append(f"{_e(k.get('etiket'))}: <b>{_e(k.get('deger'))}</b>{alt}")
    satirlar = cevap.get("satirlar") or []
    if satirlar:
        s.append("")
        for i, r in enumerate(satirlar[:TABLO_SATIR], 1):
            s.append(f"{i}. " + _e(_satir(r)))
        if len(satirlar) > TABLO_SATIR:
            s.append(f"<i>… {len(satirlar) - TABLO_SATIR} satır daha; tamamı programda.</i>")
    if cevap.get("kaynak"):
        s.append(f"\n<i>Kaynak: {_e(cevap['kaynak'])}</i>")
    metin = "\n".join(s)
    return metin if len(metin) <= TELEGRAM_SINIR else metin[:TELEGRAM_SINIR].rsplit("\n", 1)[0] + "\n…"


def yardim_metni(ornekler, kimlik, kullanici=None):
    if not kullanici:
        return (f"Merhaba, ben Elif, KAYRAN'ın asistanıyım. Bu hesap programda tanımlı değil.\nTelegram kimliğin: <code>{_e(kimlik)}</code>\n"
                "Bir yönetici Sistem › Ofis › Elif bölümünden bu kimliği kullanıcına bağlayınca soru sorabilirsin.")
    ornek = "\n".join(f"• {_e(o)}" for o in list(ornekler or [])[:6])
    return (f"Merhaba {_e(kullanici)}, ben Elif. Türkçe soru yaz, cevabı programın kendi hesaplarından vereyim.\n"
            "Satış, kâr, iade, stok, yaşlı stok, arıza, kampanya, ödeme ve çek sorularını anlarım.\n\n"
            f"Örnekler:\n{ornek}")


def anlasilmadi_metni():
    return ("Bu soruyu anlayamadım. Konuyu (satış, kâr, stok, iade, arıza, kampanya, ödeme, çek) ve "
            "istersen dönemi yaz. Örnek sorular için /yardim.")


# ── Gümrük danışmanı ────────────────────────────────────────────────
DURUM_AD = {"bekliyor": "Sırada", "calisiyor": "Araştırılıyor", "tamam": "Hazır", "hata": "Tamamlanamadı"}
ORAN_ALANLARI = (("gumruk_vergisi", "Gümrük vergisi"), ("ilave_gumruk_vergisi", "İlave gümrük vergisi"),
                 ("kdv", "KDV"))


def _f(v):
    try:
        f = float(str(v).replace("%", "").replace(",", ".").strip())
        return f
    except (TypeError, ValueError):
        return None


def sonuc_dogrula(sonuc):
    """Görevin yazdığı sonuç → (temiz sonuç, hatalar). GTİP 12 hane (noktalı yazım olabilir), oranlar yüzde."""
    hatalar = []
    if not isinstance(sonuc, dict):
        return None, ["sonuç bir JSON nesnesi olmalı"]
    gtip = "".join(ch for ch in str(sonuc.get("gtip") or "") if ch.isdigit())
    if len(gtip) not in (8, 10, 12):
        hatalar.append("gtip 8, 10 ya da 12 haneli olmalı")
    oranlar = {}
    for k, ad in ORAN_ALANLARI:
        f = _f((sonuc.get("oranlar") or {}).get(k))
        if f is None or not 0 <= f <= 100:
            hatalar.append(f"oranlar.{k} 0-100 arası yüzde olmalı ({ad})")
        oranlar[k] = f
    temiz = {
        "gtip": gtip, "gtip_aciklama": str(sonuc.get("gtip_aciklama") or "").strip(),
        "oranlar": oranlar,
        "ek_vergiler": [str(x).strip() for x in sonuc.get("ek_vergiler") or [] if str(x).strip()],
        "belgeler": [str(x).strip() for x in sonuc.get("belgeler") or [] if str(x).strip()],
        "uyarilar": [str(x).strip() for x in sonuc.get("uyarilar") or [] if str(x).strip()],
        "kaynaklar": [str(x).strip() for x in sonuc.get("kaynaklar") or [] if str(x).strip()],
        "guven": str(sonuc.get("guven") or "").strip().lower() or "orta",
    }
    return temiz, hatalar


def vergi_hesabi(sorgu, oranlar):
    """Öneri niteliğinde vergi tutarları (sorgunun para biriminde). Matrah: CIF = FOB·adet + navlun + sigorta.
    GV ve İGV CIF üzerinden; KDV (CIF + GV + İGV) üzerinden. Eksik veri varsa None."""
    fob, adet = _f(sorgu.get("birim_fiyat")), _f(sorgu.get("adet"))
    if fob is None or not adet:
        return None
    o = {k: (_f((oranlar or {}).get(k)) or 0.0) for k, _ in ORAN_ALANLARI}
    cif = fob * adet + (_f(sorgu.get("navlun")) or 0.0) + (_f(sorgu.get("sigorta")) or 0.0)
    gv = cif * o["gumruk_vergisi"] / 100
    igv = cif * o["ilave_gumruk_vergisi"] / 100
    kdv = (cif + gv + igv) * o["kdv"] / 100
    return {"cif": round(cif, 2), "gumruk_vergisi": round(gv, 2), "ilave_gumruk_vergisi": round(igv, 2),
            "kdv": round(kdv, 2), "vergi_toplam": round(gv + igv + kdv, 2),
            "maliyet_kdv_haric": round(cif + gv + igv, 2),
            "birim_maliyet_kdv_haric": round((cif + gv + igv) / adet, 4)}


# ── Pazar araştırmacısı ─────────────────────────────────────────────
def _anahtar(sku):
    """Yaklaşık SKU anahtarı (görevde shared.utils yüklenemez; araştırma için yeterli)."""
    return "".join(str(sku or "").upper().split())


def pazar_ozeti(satislar, urunler, en_cok=30):
    """Son dönem satışları → araştırılacak ürün listesi ve kategori toplamları.
    Döner: {urunler: [{sku, ad, kategori, marka, adet, ciro, ort_fiyat, kanal_sayisi, stok}], kategoriler: [...]}.
    Tutarlar satış kaydındaki birim satış fiyatının birimiyle (USD)."""
    kart = {_anahtar(u.get("sku")): u for u in urunler or [] if u.get("sku")}
    g = {}
    for s in satislar or []:
        k = _anahtar(s.get("sku"))
        adet = _f(s.get("adet")) or 0.0
        if not k or adet <= 0:
            continue
        u = kart.get(k, {})
        d = g.setdefault(k, {"sku": s.get("sku"), "ad": u.get("urun_adi") or s.get("urun_adi") or "",
                             "kategori": u.get("kategori") or "", "marka": u.get("marka") or "",
                             "adet": 0.0, "ciro": 0.0, "kanallar": set(), "stok": _f(u.get("bizim_stok"))})
        d["adet"] += adet
        d["ciro"] += adet * (_f(s.get("birim_satis")) or 0.0)
        if s.get("kanal"):
            d["kanallar"].add(str(s["kanal"]).strip())
    liste = sorted(g.values(), key=lambda d: -d["ciro"])
    out = [{"sku": d["sku"], "ad": d["ad"], "kategori": d["kategori"], "marka": d["marka"],
            "adet": int(d["adet"]), "ciro": round(d["ciro"], 2),
            "ort_fiyat": round(d["ciro"] / d["adet"], 2) if d["adet"] else None,
            "kanal_sayisi": len(d["kanallar"]), "stok": d["stok"]} for d in liste[:en_cok]]
    kat = {}
    for d in liste:
        x = kat.setdefault(d["kategori"] or "Diğer", {"kategori": d["kategori"] or "Diğer", "adet": 0, "ciro": 0.0,
                                                      "urun": 0})
        x["adet"] += int(d["adet"])
        x["ciro"] = round(x["ciro"] + d["ciro"], 2)
        x["urun"] += 1
    return {"urunler": out, "kategoriler": sorted(kat.values(), key=lambda x: -x["ciro"])}


def brifing_blogu(raporlar):
    """Telegram'a gönderilmemiş raporlar → sabah brifingine eklenecek HTML blok ('' = yok)."""
    if not raporlar:
        return ""
    s = []
    for r in raporlar[:2]:
        s.append(f"<b>Kerem'in pazar raporu · {_e(r.get('baslik') or '')}</b>")
        if r.get("ozet"):
            s.append(_e(r["ozet"]).strip())
    s.append("<i>Tam rapor: Sistem › Ofis › Kerem</i>")
    return "\n".join(s)
