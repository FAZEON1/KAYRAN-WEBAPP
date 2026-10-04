# -*- coding: utf-8 -*-
"""Stok yaşı — FIFO (Ekim 2026).

Yaş, mal DEPOYA GİRDİĞİ gün başlar ve FIFO kuralıyla hesaplanır: en eski parti önce satılır,
elde kalan stok EN YENİ partilerden oluşur. Her partinin elde kalan adedi ve yaşı çıkar; ürünün
ağırlıklı ortalama yaşı, en eski kalan partisi ve yaş grupları bunlardan hesaplanır.

  Bizim stok      satılabilir depolar (Merkez + Happy Life = urunler.bizim_stok). İade, teknik,
                  ikinci el, outlet depoları SAYILMAZ (kullanıcı kararı: oradaki mal geri gelmiş /
                  arızalı, giriş tarihi partiyle ilgisiz).
                  Partiler: 'Teslim Alındı' alım dosyalarının kalemleri — ithalat, yurt içi satın
                  alma, yerli üretim (ithalat_dosyalari.alim_turu). Parti tarihi TESLİM tarihi
                  (yoksa belge tarihi). Yolda / gümrükte / antrepodaki dosyalar sayılmaz.
  Müşteri stoğu   her kanalın SON raporundaki stok (stok_hesap.kanal_stoklari — Tüm Ürünler ile
                  aynı kural). Partiler: o müşteriye yaptığımız satışlar (fatura tarihi). Yaş,
                  malın müşteride ne kadar süredir beklediğidir.
  Kapsanmayan     stok, kayıtlı partilerden fazlaysa aradaki adet 'giriş kaydı yok' sayılır; yaşı
                  hesaplanmaz (uydurulmaz). Yurt içi alış sayfasından alım girilince kapanır.

Saf fonksiyonlar test edilir (tests/test_stok_yasi.py); okuma fonksiyonları önbellekli.
"""
from datetime import date

GRUPLAR = [("0–30 gün", 0, 30), ("31–60 gün", 31, 60), ("61–90 gün", 61, 90),
           ("91–180 gün", 91, 180), ("180+ gün", 181, None)]
KAYITSIZ = "Giriş kaydı yok"
TESLIM = "Teslim Alındı"


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _gun(tarih, bugun):
    try:
        return max(0, (bugun - date.fromisoformat(str(tarih)[:10])).days)
    except (TypeError, ValueError):
        return None


def grup_adi(gun):
    for ad, alt, ust in GRUPLAR:
        if gun >= alt and (ust is None or gun <= ust):
            return ad
    return GRUPLAR[0][0]


# ── Saf: FIFO ───────────────────────────────────────────────────────
def fifo_kalan(partiler, stok):
    """Elde kalan stoğu partilere dağıtır (FIFO: en yeniler elde kalır).
    partiler: [{"tarih": "YYYY-MM-DD", "adet": n, ...}] (sıra önemsiz).
    Döner: (kalanlar ESKİ→YENİ, her biri partinin kopyası + "kalan"; kapsanmayan adet)."""
    stok = _f(stok)
    if stok <= 0:
        return [], 0.0
    gecerli = [p for p in (partiler or []) if _f(p.get("adet")) > 0 and str(p.get("tarih") or "")[:10]]
    sirali = sorted(enumerate(gecerli), key=lambda x: (str(x[1]["tarih"])[:10], x[0]), reverse=True)
    kalan_stok, out = stok, []
    for _i, p in sirali:
        if kalan_stok <= 0:
            break
        al = min(_f(p["adet"]), kalan_stok)
        out.append(dict(p, kalan=al))
        kalan_stok -= al
    out.reverse()
    return out, max(0.0, kalan_stok)


def yas_ozeti(kalanlar, kapsanmayan, bugun):
    """{stok, kapsanan, kapsanmayan, ort_gun, en_eski_gun, en_eski_tarih, en_yeni_gun, gruplar}
    gruplar: {grup adı: adet} (+ KAYITSIZ). ort_gun: kalan adetle ağırlıklı; parti yoksa None."""
    gruplar = {ad: 0.0 for ad, _a, _u in GRUPLAR}
    toplam = agirlik = 0.0
    eski_gun = yeni_gun = None
    eski_tarih = ""
    for k in kalanlar or []:
        g = _gun(k.get("tarih"), bugun)
        if g is None:
            continue
        a = _f(k.get("kalan"))
        gruplar[grup_adi(g)] += a
        toplam += a
        agirlik += a * g
        if eski_gun is None or g > eski_gun:
            eski_gun, eski_tarih = g, str(k.get("tarih"))[:10]
        if yeni_gun is None or g < yeni_gun:
            yeni_gun = g
    kaps = _f(kapsanmayan)
    if kaps > 0:
        gruplar[KAYITSIZ] = kaps
    return {"stok": toplam + kaps, "kapsanan": toplam, "kapsanmayan": kaps,
            "ort_gun": (agirlik / toplam) if toplam > 0 else None,
            "en_eski_gun": eski_gun, "en_eski_tarih": eski_tarih, "en_yeni_gun": yeni_gun,
            "gruplar": gruplar}


# ── Saf: partiler ───────────────────────────────────────────────────
def bizim_partiler(dosyalar, kalemler, anahtar):
    """{sku anahtarı: [{tarih, adet, belge, tur, depo}]} — yalnız 'Teslim Alındı' dosyalar.
    anahtar: SKU yazımlarını birleştiren fonksiyon (shared.utils.sku_anahtar)."""
    dmap = {d.get("id"): d for d in (dosyalar or [])}
    out = {}
    for k in kalemler or []:
        d = dmap.get(k.get("dosya_id"))
        if not d or str(d.get("durum") or "").strip() != TESLIM:
            continue
        adet = _f(k.get("adet"))
        sku = anahtar(k.get("sku"))
        tarih = str(d.get("teslim_tarihi") or d.get("tarih") or "")[:10]
        if not sku or adet <= 0 or not tarih:
            continue
        tur = str(d.get("alim_turu") or "").strip().lower() or "ithalat"
        out.setdefault(sku, []).append({"tarih": tarih, "adet": adet,
                                        "belge": d.get("dosya_no") or d.get("pi_no") or "",
                                        "tur": tur, "depo": d.get("teslim_deposu") or ""})
    return out


def musteri_partileri(satislar, firma_bul, anahtar):
    """{firma kodu: {sku anahtarı: [{tarih, adet, belge}]}} — bizim o müşteriye satışlarımız.
    firma_bul(kanal) → firma kodu ya da None (stok raporu olmayan müşteriler atlanır)."""
    out = {}
    for s in satislar or []:
        adet = _f(s.get("adet"))
        tarih = str(s.get("tarih") or "")[:10]
        sku = anahtar(s.get("sku"))
        if adet <= 0 or not tarih or not sku:
            continue
        f = firma_bul(s.get("kanal"))
        if not f:
            continue
        out.setdefault(f, {}).setdefault(sku, []).append(
            {"tarih": tarih, "adet": adet, "belge": s.get("siparis_no") or ""})
    return out


def firma_cozucu(firma_kodlari, tam_ad, normalize):
    """Satıştaki kanal adını (cari adı) stok raporundaki firma koduna çeviren fonksiyon.
    Kod ya da kodun tam cari adı (tam_ad) birebir eşleşir (normalize: Türkçe/boşluk farkı yok)."""
    h = {}
    for kod in firma_kodlari or ():
        for ad in (kod, tam_ad(kod)):
            n = " ".join(normalize(ad or "").split())
            if n:
                h.setdefault(n, kod)

    def bul(kanal):
        return h.get(" ".join(normalize(kanal or "").split()))
    return bul


def urun_yasi(stok, partiler, bugun):
    """Tek ürün: (özet, kalan partiler)."""
    kalanlar, kaps = fifo_kalan(partiler, stok)
    return yas_ozeti(kalanlar, kaps, bugun), kalanlar


def toplam_ozet(ozetler):
    """Birden çok özetin toplamı (sayfa üstü)."""
    gruplar, stok, kaps, kapsanan, agirlik = {}, 0.0, 0.0, 0.0, 0.0
    for o in ozetler or []:
        for g, a in (o.get("gruplar") or {}).items():
            gruplar[g] = gruplar.get(g, 0.0) + a
        stok += o.get("stok", 0.0)
        kaps += o.get("kapsanmayan", 0.0)
        kapsanan += o.get("kapsanan", 0.0)
        if o.get("ort_gun") is not None:
            agirlik += o["ort_gun"] * o.get("kapsanan", 0.0)
    return {"stok": stok, "kapsanan": kapsanan, "kapsanmayan": kaps,
            "ort_gun": (agirlik / kapsanan) if kapsanan > 0 else None, "gruplar": gruplar}


# ── Saf: liste ve Excel satırları (Stok yaşı sayfası) ───────────────
TUR_AD = {"ithalat": "İthalat", "yurtici": "Yurt içi", "yerli": "Yerli üretim"}


def _yuvarla(v):
    return None if v is None else round(v)


def urun_satirlari(bizim, pacal, grup=None):
    """Ürün listesi. grup verilirse yalnız o yaş grubunda adedi olan ürünler, o gruptaki adet ve
    değeriyle (KAYITSIZ: giriş kaydı olmayan adet). bizim: hesapla()['bizim']; pacal: {sku: $}."""
    out = []
    for k, (oz, _kal, u) in (bizim or {}).items():
        p = float(pacal.get(k, 0) or 0)
        r = {"_id": k, "SKU": u.get("sku") or k, "Ürün": u.get("urun_adi") or "", "Kategori": u.get("kategori") or ""}
        if grup is not None:
            a = oz["gruplar"].get(grup, 0) if grup != KAYITSIZ else oz["kapsanmayan"]
            if a <= 0:
                continue
            r.update({"Bu yaştaki adet": a, "Bu yaştaki değer ($)": round(a * p, 2)})
        r.update({"Toplam stok": oz["stok"], "Ort. yaş (gün)": _yuvarla(oz["ort_gun"]),
                  "En eski (gün)": oz["en_eski_gun"]})
        if grup is None:
            for g, _a, _u in GRUPLAR:
                r[g] = oz["gruplar"].get(g, 0)
            r[KAYITSIZ] = oz["kapsanmayan"]
        r["Toplam değer ($)"] = round(oz["stok"] * p, 2)
        out.append(r)
    if grup is None:
        out.sort(key=lambda r: (-(r["Ort. yaş (gün)"] or -1), r["SKU"]))
    else:
        out.sort(key=lambda r: (-r["Bu yaştaki adet"], r["SKU"]))
    return out


def parti_satirlari(bizim, bugun, grup=None, skular=None):
    """Elde kalan her parti bir satır (Excel 'Partiler' sayfası). grup: yalnız o yaş grubundaki
    partiler; skular: yalnız bu ürünler."""
    out = []
    for k, (_oz, kal, u) in (bizim or {}).items():
        if skular is not None and k not in skular:
            continue
        for p in reversed(kal):
            g = _gun(p.get("tarih"), bugun)
            ga = grup_adi(g or 0)
            if grup is not None and ga != grup:
                continue
            out.append({"SKU": u.get("sku") or k, "Ürün": u.get("urun_adi") or "", "Belge": p.get("belge") or "",
                        "Tür": TUR_AD.get(p.get("tur"), ""), "Depoya giriş": str(p.get("tarih"))[:10],
                        "Kalan adet": p.get("kalan"), "Yaş (gün)": g, "Yaş grubu": ga})
    return out


def musteri_satirlari(musteri, firma_ad=lambda f: f):
    out = []
    for firma, skular in (musteri or {}).items():
        for sku, (oz, _kal) in skular.items():
            r = {"Müşteri": firma_ad(firma), "SKU": sku, "Stok": oz["stok"],
                 "Ort. yaş (gün)": _yuvarla(oz["ort_gun"]), "En eski (gün)": oz["en_eski_gun"]}
            for g, _a, _u in GRUPLAR:
                r[g] = oz["gruplar"].get(g, 0)
            r["Kaydı yok"] = oz["kapsanmayan"]
            out.append(r)
    out.sort(key=lambda r: (r["Müşteri"], -(r["Ort. yaş (gün)"] or -1)))
    return out


def excel_bytes(sayfalar):
    """{sayfa adı: satırlar} → .xlsx baytları. '_' ile başlayan sütunlar yazılmaz."""
    import io
    import pandas as pd
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for ad, rows in sayfalar.items():
            temiz = [{k: v for k, v in r.items() if not str(k).startswith("_")} for r in (rows or [])]
            pd.DataFrame(temiz or [{"Bilgi": "Kayıt yok"}]).to_excel(w, index=False, sheet_name=str(ad)[:31])
    return buf.getvalue()


# ── Okuma (önbellekli) ──────────────────────────────────────────────
def _bugun():
    try:
        from shared.utils import tr_now
        return tr_now().date()
    except Exception:  # noqa: BLE001
        return date.today()


def _bizim_partiler_oku():
    from ithalat.database import get_dosyalar, get_tum_kalemler
    from shared.utils import sku_anahtar
    return bizim_partiler(get_dosyalar() or [], get_tum_kalemler() or [], sku_anahtar)


def _musteri_oku():
    """(kanal stokları {firma: {sku: adet}}, müşteri partileri)."""
    from kayranpm.database import _hepsi
    from kayranpm.stok_hesap import kanal_stoklari
    from satis.database import get_satislar
    from shared.utils import sku_anahtar, firma_gorunen_ad, normalize_tr
    kanal = kanal_stoklari(_hepsi("firma_stok", "firma, sku, stok_miktari, yukleme_tarihi"))
    bul = firma_cozucu(list(kanal), lambda k: firma_gorunen_ad(k, kisa=False), normalize_tr)
    return kanal, musteri_partileri(get_satislar() or [], bul, sku_anahtar)


def hesapla():
    """Sayfa ve stok kartı için tek hesap: {"bizim": {sku: (özet, kalanlar, urun)},
    "musteri": {firma: {sku: (özet, kalanlar)}}, "bugun"}."""
    from kayranpm.database import _hepsi
    from shared.utils import sku_anahtar
    bugun = _bugun()
    part = _bizim_partiler_oku()
    stoklar, kartlar = {}, {}
    for u in _hepsi("urunler", "sku, urun_adi, kategori, marka, bizim_stok"):
        stok = _f(u.get("bizim_stok"))
        k = sku_anahtar(u.get("sku"))
        if stok <= 0 or not k:
            continue
        stoklar[k] = stoklar.get(k, 0.0) + stok          # aynı anahtarlı iki kart: stok toplanır
        kartlar.setdefault(k, u)
    bizim = {}
    for k, stok in stoklar.items():
        oz, kal = urun_yasi(stok, part.get(k, []), bugun)
        bizim[k] = (oz, kal, kartlar[k])
    kanal, mpart = _musteri_oku()
    musteri = {}
    for firma, skular in kanal.items():
        for sku, adet in skular.items():
            if _f(adet) <= 0:
                continue
            oz, kal = urun_yasi(adet, mpart.get(firma, {}).get(sku, []), bugun)
            musteri.setdefault(firma, {})[sku] = (oz, kal)
    return {"bizim": bizim, "musteri": musteri, "bugun": bugun}


try:                                      # 5 dk önbellek (veri değişince sayfa Yenile temizler)
    import streamlit as _st
    hesapla = _st.cache_data(ttl=300, show_spinner=False)(hesapla)
except Exception:  # noqa: BLE001
    pass
