# -*- coding: utf-8 -*-
"""Haftalık ödeme listesi önerisi — Mikro'daki vadeli borçlardan ve firma çeklerinden (Ekim 2026).

Kullanıcı: "Haftalık ödeme listesi - Mikro'daki vadeli borçlardan ve çeklerden hazır öneri doldur."
Excel'le yüklenen haftalık listenin (Dosya kapısı › ödeme listesi) Mikro'dan hesaplanan karşılığı. Öneri
yalnız gösterilir; kullanıcı Muhasebe › Bu Hafta'da satırları seçip tutarları düzeltir, "Haftaya kaydet"
deyince Excel yüklemesiyle AYNI fonksiyonlar (database.hafta_olustur → hafta_ekle + odeme_ekle_bulk +
hafta_aktif_yap) yeni hafta açar. Otomatik yazım yok.

Kaynaklar:
  Cari borçlar  mikro_cari_hareket, satıcı / diğer borç hesapları (BORC_ONEK: 320 satıcılar, 336 diğer
                çeşitli borçlar). 120 (alıcılar) ve 340 (alınan avanslar) müşteri parasıdır, alınmaz.
                Bakiye mikro_muhasebe.hareket_tutari ile hesabın kendi dövizinde (kur farkı fişi döviz
                bakiyesini değiştirmez). Alacak (cha_tip 1) hareketleri borç kalemi, borç (cha_tip 0)
                hareketleri ödemedir; ödemeler en eski vadeli kalemden başlayarak kapatılır (FIFO). Açık
                kalemlerin toplamı her zaman −bakiye'dir (borçlu olduğumuz kısım).
  Vade          cha_vade tamsayısı Mikro'da dört anlamda (21.10.2026 canlı veri, tüm hareketler):
                  ≥ 19000101  vade tarihi (yyyymmdd), örn. 20261022
                  < 0         fatura tarihinden itibaren gün (yalnız 20 hareket, −4 … −45)
                  1 … 999     ödeme planı numarası (ODEME_PLANLARI.odp_no; Mikro'da 13 plan, veride 1–13)
                  0           vade yok: vade = hareket tarihi ("peşin")
                Ödeme planlı faturanın gerçek vadeleri CARI_HAREKET_ODEME_VADELERI'nde (taksit), planın
                ortalama günü ODEME_PLANLARI.odp_ortgun'da; ikisi de aktarıcının günlük keşfiyle
                mikro_kesif'e gelir ("odeme_vadeleri", "odeme_planlari"). Gelmemişse vade fatura tarihi
                sayılır ve satırda "vade tahmini" yazar (kullanıcı satırı düzeltebilir / çıkarabilir).
  Firma çekleri cekler tablosu (Mikro eşitlemesi açıksa Mikro'dan, değilse çek dökümü Excel'inden):
                Ödendi olmayan, kalanı olan çekler. Cariye verilen çek (evrak 67) carinin borcunu zaten
                kapatır; çek ve cari borç iki kez sayılmaz.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta

from .mikro_muhasebe import CARI_CINS, KURUS, _banka_imi, _f, _i, _s, hareket_tutari

BORC_ONEK = ("320", "336")
# Hesap grubu → ödeme kategorisi (Bu Hafta'nın KATEGORILER anahtarları). İlk eşleşen kazanır.
KATEGORI_GRUP = (("320.50", "ithalat"), ("320", "cari"), ("336", "cari"))
CEK_KATEGORI = "cek"
DOVIZ_ALAN = {0: "tl", 1: "usd"}       # odemeler tablosunda yalnız TL ve USD tutarı var
MIN_TUTAR = 1.0                        # bundan küçük açık cari satırı önerilmez (yuvarlama artığı)
HAFTA_EKI = "GÜNCEL ÖDEME LİSTESİ"     # mevcut hafta adlarıyla aynı biçim: "19.10.2026 GÜNCEL ÖDEME LİSTESİ"
_BANKA_KISA = {"YKB": "YKB", "HALK": "HALKBANK", "IS": "İŞ BANKASI", "ZIRAAT": "ZİRAAT", "GARANTI": "GARANTİ"}


# ── Saf: tarih ─────────────────────────────────────────────────────
def _tarih(v):
    """'2026-10-01 00:00:00' / '2026-10-01' / date → date; okunamazsa None."""
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = _s(v)[:10]
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def _yyyymmdd(n):
    try:
        return date(n // 10000, n // 100 % 100, n % 100)
    except ValueError:
        return None


def vade_bul(h, planlar=None):
    """Hareketin vadesi. Döner: (vade tarihi, kaynak açıklaması, kesin mi).
    planlar: {odp_no: ortalama gün} (ODEME_PLANLARI)."""
    t = _tarih(h.get("cha_tarihi"))
    v = _i(h.get("cha_vade"))
    if v >= 19000101:
        d = _yyyymmdd(v)
        if d:
            return d, "Mikro vade tarihi", True
    if t is None:
        return None, "tarih yok", False
    if v < 0:
        return t + timedelta(days=-v), f"{-v} gün", True
    if v == 0:
        return t, "peşin", True
    gun = (planlar or {}).get(v)
    if gun is not None:
        return t + timedelta(days=_i(gun)), f"ödeme planı {v} ({_i(gun)} gün)", True
    return t, f"ödeme planı {v}: gün bilinmiyor, fatura tarihi alındı", False


def hafta_araligi(bugun, kaydir=0):
    """(pazartesi, pazar) — kaydir=1 gelecek hafta."""
    bas = bugun - timedelta(days=bugun.weekday()) + timedelta(days=7 * int(kaydir))
    return bas, bas + timedelta(days=6)


def hafta_adi(bas):
    return f"{bas:%d.%m.%Y} {HAFTA_EKI}"


def kategori_bul(cari_kod):
    k = _s(cari_kod)
    return next((kat for onek, kat in KATEGORI_GRUP if k.startswith(onek)), "cari")


# ── Saf: keşif verisi (mikro_kesif) ────────────────────────────────
def plan_gunleri(satirlar):
    """ODEME_PLANLARI satırları → {odp_no: ortalama gün}."""
    out = {}
    for r in satirlar or []:
        no = _i(r.get("odp_no"), -1)
        if no > 0 and r.get("odp_ortgun") is not None:
            out[no] = _i(r.get("odp_ortgun"))
    return out


def _evrak_anahtar(tip, seri, sira):
    return (_i(tip, -1), _s(seri), _i(sira, -1))


def taksit_haritasi(satirlar):
    """CARI_HAREKET_ODEME_VADELERI satırları → {(evrak tipi, seri, sıra): [(vade, tutar), …]} (vade sıralı)."""
    out = defaultdict(list)
    for r in satirlar or []:
        d, t = _tarih(r.get("cop_vade")), _f(r.get("cop_tutar"))
        if d and t > 0:
            out[_evrak_anahtar(r.get("cop_evrak_tip"), r.get("cop_evrakno_seri"), r.get("cop_evrakno_sira"))].append((d, t))
    return {k: sorted(v) for k, v in out.items()}


# ── Saf: açık kalemler (FIFO) ──────────────────────────────────────
def _evrak_metni(h):
    seri, sira = _s(h.get("cha_evrakno_seri")), _i(h.get("cha_evrakno_sira"), 0)
    no = f"{seri}-{sira}" if seri else (str(sira) if sira else "")
    return _s(h.get("cha_belge_no")) or no


def acik_kalemler(hareketler, kartlar, planlar=None, taksitler=None, onekler=BORC_ONEK):
    """Borçlu olduğumuz carilerin açık kalemleri. Her cari için: alacak hareketleri (fatura vb.) vade
    sırasına dizilir, ödemelerin (borç hareketleri) toplamı en eski vadeden başlayarak düşülür.
    Döner: [{cari_kod, unvan, doviz, tarih, vade, tutar, acik, evrak, aciklama, vade_kaynak, vade_kesin}]."""
    dov = {_s(k.get("cari_kod")): _i(k.get("cari_doviz_cinsi")) for k in kartlar if _s(k.get("cari_kod"))}
    ad = {_s(k.get("cari_kod")): _s(k.get("cari_unvan1")) for k in kartlar}
    taksitler = taksitler or {}
    kalem, odenen = defaultdict(list), defaultdict(float)
    for h in hareketler:
        kod = _s(h.get("cha_kod"))
        if _i(h.get("cha_cari_cins"), -1) != CARI_CINS or kod not in dov or not kod.startswith(tuple(onekler)):
            continue
        t = hareket_tutari(h, dov[kod])
        if abs(t) < KURUS:
            continue
        if _i(h.get("cha_tip")) == 0:
            odenen[kod] += t
            continue
        tarih = _tarih(h.get("cha_tarihi"))
        ortak = {"cari_kod": kod, "unvan": ad.get(kod) or kod, "doviz": dov[kod], "tarih": tarih,
                 "evrak": _evrak_metni(h), "aciklama": _s(h.get("cha_aciklama"))}
        tk = taksitler.get(_evrak_anahtar(h.get("cha_evrak_tip"), h.get("cha_evrakno_seri"),
                                          h.get("cha_evrakno_sira")))
        if tk and 0 < _i(h.get("cha_vade")) < 1000:
            top = sum(x for _, x in tk)
            for i, (d, x) in enumerate(tk, 1):
                kalem[kod].append(dict(ortak, vade=d, tutar=t * x / top, vade_kesin=True,
                                       vade_kaynak=f"Mikro taksit {i}/{len(tk)}"))
            continue
        d, kaynak, kesin = vade_bul(h, planlar)
        kalem[kod].append(dict(ortak, vade=d or tarih, tutar=t, vade_kaynak=kaynak, vade_kesin=kesin))
    out = []
    for kod, liste in kalem.items():
        liste.sort(key=lambda r: (r["vade"] or date.max, r["tarih"] or date.max, r["evrak"]))
        kalan_odeme, birikim = odenen.get(kod, 0.0), 0.0
        for r in liste:
            birikim += r["tutar"]
            acik = min(r["tutar"], max(0.0, birikim - kalan_odeme))
            if acik >= KURUS:
                out.append(dict(r, tutar=round(r["tutar"], 2), acik=round(acik, 2)))
    out.sort(key=lambda r: (r["vade"] or date.max, r["unvan"]))
    return out


# ── Saf: öneri satırları ──────────────────────────────────────────
def _tr_tarih(d):
    return d.strftime("%d.%m.%Y") if d else ""


def _cari_aciklama(grup, gecikmis):
    # Mikro bir faturayı satır satır (KDV, masraf kalemi) yazar: fatura sayısı evrak numarasından
    n = len({r["evrak"] or id(r) for r in grup})
    tarihler = sorted({r["tarih"] for r in grup if r["tarih"]})
    if not tarihler:
        metin = f"{n} FATURA"
    elif len(tarihler) == 1:
        metin = f"{_tr_tarih(tarihler[0])} TARİHLİ {'FATURA' if n == 1 else f'{n} FATURA'}"
    else:
        metin = f"{n} FATURA ({_tr_tarih(tarihler[0])} – {_tr_tarih(tarihler[-1])})"
    if gecikmis:
        metin = "GECİKMİŞ · " + metin
    if any(not r["vade_kesin"] for r in grup):
        metin += " · vade tahmini"
    return metin


def _cek_firma(c):
    bi = _banka_imi(c.get("banka"))
    banka = _BANKA_KISA.get(bi, "")
    pb = _s(c.get("para_birimi")) or "TL"
    return f"{_s(c.get('cek_no'))} NOLU {banka + ' ' if banka else ''}FİRMA ÇEK ÖDEMESİ - {pb}"


def oneri_satirlari(kalemler, cekler, bas, son, gecikmis_dahil=True):
    """Seçilen haftanın önerisi. Cari: vadesi haftaya düşen açık kalemler, cari + vade gününe göre tek satır
    (elle hazırlanan listedeki gibi: "UPS · 2 FATURA · 22.10", "UPS · 2 FATURA · 30.10"); gecikmis_dahil=True ise
    vadesi geçmiş, hâlâ açık kalemler de aynı biçimde. Hepsi işaretli gelir (21.10.2026: gecikmiş 8 satırın 6'sı
    elle hazırlanan aktif listede de vardı — UPS, Happy Life, Tuba Yılmazeren, Av. Hakan Kalafat, Marmara OSB,
    DEY); kullanıcı ödemeyeceklerinin işaretini kaldırır.
    Çek: Ödendi olmayan, kalanı olan, vadesi haftada (gecikmiş dahilse önce de) olan firma çekleri.
    Döner: (satırlar, uyarılar). Satır: {sec, firma, aciklama, cari_banka, vade, tl, usd, kategori, kaynak,
    durum, kesin}."""
    satir, uyari = [], []
    grup = defaultdict(list)
    for r in kalemler:
        v = r["vade"]
        if v is None or v > son or (v < bas and not gecikmis_dahil):
            continue
        grup[(r["cari_kod"], v)].append(r)
    for (kod, vade), g in grup.items():
        dc = g[0]["doviz"]
        tutar = round(sum(r["acik"] for r in g), 2)
        if tutar < MIN_TUTAR:          # yuvarlama artığı (0,01 TL) satır olmasın
            continue
        if dc not in DOVIZ_ALAN:
            from shared.tasarim import tr_sayi
            uyari.append(f"{g[0]['unvan']}: {tr_sayi(tutar, 2)} EUR açık borç (ödeme listesinde EUR sütunu yok; "
                         "elle ekle).")
            continue
        gecikmis = vade < bas
        satir.append({"sec": True, "firma": g[0]["unvan"], "aciklama": _cari_aciklama(g, gecikmis),
                      "cari_banka": "", "vade": vade.isoformat(), "tl": tutar if dc == 0 else None,
                      "usd": tutar if dc == 1 else None, "kategori": kategori_bul(kod), "kaynak": f"Cari {kod}",
                      "durum": "Gecikmiş" if gecikmis else "Bu hafta", "kesin": all(r["vade_kesin"] for r in g)})
    for c in cekler or []:
        kalan = round(_f(c.get("kalan")), 2)
        v = _tarih(c.get("vade"))
        if _s(c.get("durum")) == "Ödendi" or kalan < KURUS or v is None or v > son:
            continue
        if v < bas and not gecikmis_dahil:
            continue
        pb = _s(c.get("para_birimi")) or "TL"
        if pb not in ("TL", "USD"):
            uyari.append(f"{_s(c.get('cek_no'))} nolu çek {pb}: ödeme listesinde bu para birimi yok; elle ekle.")
            continue
        satir.append({"sec": True, "firma": _cek_firma(c), "aciklama": _s(c.get("ch_ismi")), "cari_banka": "",
                      "vade": v.isoformat(), "tl": kalan if pb == "TL" else None, "usd": kalan if pb == "USD" else None,
                      "kategori": CEK_KATEGORI, "kaynak": f"Çek {_s(c.get('cek_no'))}",
                      "durum": "Gecikmiş" if v < bas else "Bu hafta", "kesin": True})
    satir.sort(key=lambda r: (r["vade"], r["kategori"] != CEK_KATEGORI, r["firma"]))
    return satir, uyari


def ozet(satirlar, yalniz_secili=True):
    """{adet, tl, usd} — seçili (ya da tüm) satırlar."""
    s = [r for r in satirlar if r.get("sec") or not yalniz_secili]
    return {"adet": len(s), "tl": round(sum(_f(r.get("tl")) for r in s), 2),
            "usd": round(sum(_f(r.get("usd")) for r in s), 2)}


def odemeye_cevir(satirlar):
    """Seçili satırlar → odeme_ekle_bulk girdisi (Excel okuyucusunun ürettiğiyle aynı alanlar).
    Tutarı olmayan ya da vadesi okunmayan satır alınmaz. Döner: (ödemeler, atlanan satır sayısı)."""
    out, atlanan = [], 0
    for r in satirlar:
        if not r.get("sec"):
            continue
        tl, usd = _f(r.get("tl")), _f(r.get("usd"))
        vade = _tarih(r.get("vade"))
        firma = _s(r.get("firma"))
        if (tl < KURUS and usd < KURUS) or vade is None or not firma:
            atlanan += 1
            continue
        out.append({"firma": firma, "aciklama": _s(r.get("aciklama")), "cari_banka": _s(r.get("cari_banka")),
                    "vade": vade.isoformat(), "tl": round(tl, 2) if tl >= KURUS else None,
                    "usd": round(usd, 2) if usd >= KURUS else None,
                    "kategori": _s(r.get("kategori")) or "diger", "manuel": 0})
    return out, atlanan


# ── Saf: mevcut haftayla karşılaştırma ─────────────────────────────
_TR = str.maketrans("İIŞĞÜÖÇışğüöç", "IISGUOCisguoc")
_EKLER = frozenset(("ANONIM", "SIRKETI", "LIMITED", "LTD", "STI", "AS", "SAN", "TIC", "VE", "TICARET", "SANAYI",
                    "AV"))


def firma_kelimeleri(ad):
    """Unvanın anlamlı kelimeleri: Türkçe harfler sadeleşir, noktalama ve şirket ekleri atılır.
    "AV.HAKAN KALAFAT" → (HAKAN, KALAFAT); "UPS HIZLI KARGO TAŞIMACILIĞI A.Ş." → (UPS, HIZLI, KARGO, TASIMACILIGI)."""
    t = "".join(ch if ch.isalnum() else " " for ch in _s(ad).translate(_TR).upper())
    return tuple(w for w in t.split() if len(w) > 1 and w not in _EKLER)


def ayni_firma(a, b):
    """Kısa adın ilk üç kelimesi uzun adda (kelime başı olarak) varsa aynı firma: "MULTİNET" ↔ "MULTİNET
    KURUMSAL HİZMETLER A.Ş.", "TUBA YILMAZER" ↔ "TUBA YILMAZEREN" (elle yazılan listede kısaltma / yazım)."""
    ka, kb = firma_kelimeleri(a), firma_kelimeleri(b)
    if not ka or not kb:
        return False
    kisa, uzun = (ka, kb) if len(ka) <= len(kb) else (kb, ka)
    return all(any(u.startswith(k) or k.startswith(u) for u in uzun) for k in kisa[:3])


def karsilastir(oneri, mevcut):
    """Öneri ↔ kayıtlı haftanın ödemeleri (odemeler tablosu satırları). Firma anahtarı + para birimi aynı ve
    tutar %1 içinde ise 'aynı' (ayni_firma); firma aynı tutar farklı ise 'tutar farklı'. Döner: {ayni, farkli, yalniz_oneri,
    yalniz_mevcut} (satır listeleri)."""
    def _pb_tutar(r, tl, usd):
        return ("USD", _f(r.get(usd))) if _f(r.get(usd)) >= KURUS else ("TL", _f(r.get(tl)))
    kalan = list(mevcut or [])
    out = {"ayni": [], "farkli": [], "yalniz_oneri": [], "yalniz_mevcut": []}
    for o in oneri:
        pb, t = _pb_tutar(o, "tl", "usd")
        aday = [m for m in kalan if ayni_firma(o.get("firma"), m.get("firma"))
                and _pb_tutar(m, "tutar_tl", "tutar_usd")[0] == pb]
        tam = next((m for m in aday if abs(_pb_tutar(m, "tutar_tl", "tutar_usd")[1] - t) <= max(1.0, 0.01 * t)), None)
        if tam is not None:
            out["ayni"].append((o, tam))
            kalan.remove(tam)
        elif aday:
            out["farkli"].append((o, aday[0]))
            kalan.remove(aday[0])
        else:
            out["yalniz_oneri"].append(o)
    out["yalniz_mevcut"] = kalan
    return out


# ── Veritabanı (yalnız okur) ───────────────────────────────────────
_HAREKET_ALANLARI = ("cha_tip,cha_cari_cins,cha_kod,cha_d_cins,cha_d_kur,cha_karsidcinsi,cha_karsid_kur,cha_meblag,"
                     "cha_evrak_tip,cha_evrakno_seri,cha_evrakno_sira,cha_belge_no,cha_tarihi,cha_vade,cha_aciklama")


def _cli():
    from kayranacc.database import get_client
    return get_client()


def _kesif(anahtar):
    """mikro_kesif'teki keşif sonucu (liste); yoksa / okunamazsa []."""
    import json
    try:
        r = _cli().table("mikro_kesif").select("veri").eq("anahtar", anahtar).execute().data or []
        v = (r[0] if r else {}).get("veri")
        v = json.loads(v) if isinstance(v, str) else v
        return v if isinstance(v, list) else []
    except Exception:  # noqa: BLE001
        return []


def veri_oku():
    """Öneri için ham veri: borç hesaplarının hareketleri, cari kartları, uygulamadaki çekler, ödeme planları."""
    cli = _cli()
    hareket = []
    for onek in BORC_ONEK:
        hareket += (cli.table("mikro_cari_hareket").select(_HAREKET_ALANLARI).eq("cha_cari_cins", CARI_CINS)
                    .like("cha_kod", f"{onek}%").order("cha_guid").execute().data or [])   # sıralı: sayfalar kaymasın
    return {
        "hareket": hareket,
        "cari_kart": cli.table("mikro_cari_kart").select("cari_kod,cari_unvan1,cari_doviz_cinsi").execute().data or [],
        "cekler": cli.table("cekler").select("*").execute().data or [],
        "planlar": plan_gunleri(_kesif("odeme_planlari")),
        "taksitler": taksit_haritasi(_kesif("odeme_vadeleri")),
    }


def oneri_hazirla(veri, bas, son, gecikmis_dahil=True):
    """veri_oku() çıktısından öneri. Döner: {satirlar, uyarilar, kalem_sayisi, tahmini_vade}."""
    kalem = acik_kalemler(veri["hareket"], veri["cari_kart"], veri.get("planlar"), veri.get("taksitler"))
    satir, uyari = oneri_satirlari(kalem, veri.get("cekler"), bas, son, gecikmis_dahil)
    # Mikro bir faturayı birkaç satırda yazar: sayılar evrak numarasına göre (tekil fatura)
    return {"satirlar": satir, "uyarilar": uyari,
            "kalem_sayisi": len({(r["cari_kod"], r["evrak"] or id(r)) for r in kalem}),
            "tahmini_vade": len({(r["cari_kod"], r["evrak"] or id(r)) for r in kalem if not r["vade_kesin"]}),
            "plan_bilgisi": bool(veri.get("planlar"))}
