# -*- coding: utf-8 -*-
"""Arıza oranı (Ekim 2026, kullanıcı kararı A).

SKU bazında: satın alınan → müşteriye satılan → son kullanıcıya ulaşan → servise ARIZALI gelen
→ arıza oranı = arızalı ÷ ulaşan.

Arızalı mı? Servis kaydındaki "Arıza sonucu" alanı (ts_kayitlar.ariza_sonucu, teknisyen seçer;
durum güncellenirken zorunlu). Alanı boş eski kayıtlarda sonuç metinden (arıza, yapılan işlem, test
süreci, fiziksel durum) kelime kurallarıyla TAHMİN edilir — kayda yazılmaz, ekranda "tahmini" diye
gösterilir; teknisyen kaydı açıp düzeltebilir. İade ile gelen ama arızalı olan ürün (ör. Vatan'dan
ölü pikselli monitör) arıza sayılır; koli hasarı, cayma, sağlam iade, arıza bulunamadı sayılmaz.

Son kullanıcıya ulaşan = bitiş tarihine kadar müşterilere net satılan (BÜTÜN satış geçmişi) − müşterinin
son stok raporundaki stok (raporu olmayan müşteriye satılanın tamamı ulaşmış sayılır). Dönem süzgeci
yalnız servis kayıtlarına uygulanır: dönemin satışını payda yapmak, dönemden önce satılıp dönemde
arızalanan ürünler yüzünden %100'ü aşan oranlar veriyordu (canlı veri, Ekim 2026). Servis kayıtları
23.06.2026'da başladığı için oran bir ALT SINIRDIR. Aynı seri numarası bir kez sayılır.

Mikro iadeleri (kullanıcı, 22.10.2026: "Mikro'dan gelen datalarla geçmişe dönük daha gerçekçi adet ve oranları
çekebilir miyiz?" → öneri onaylandı). Mikro'da arıza kaydı yok ama müşteri iadesi var (mikro_depo_hareket: iade
irsaliyesi, SERVİS DEPO'ya 2025'ten Haziran 2026'ya, İADE DEPO'ya Temmuz 2026'dan beri). İadenin sebebi Mikro'da
yazmaz; bu yüzden:
  İade oranı              Mikro'daki tekli iade ÷ ulaşan (tahmin yok). Toplu stok iadesi (satırda 3'ten fazla adet,
                          ör. SND'nin 3.120 adetlik iadesi) arıza değildir, sayılmaz.
  Arızalı tahmini         İLK servis kaydından ÖNCEKİ Mikro iadeleri × kategorinin Kayran'daki iade arıza payı
                          (iade kayıtlarının kaçı "Arıza doğrulandı"; az örnekli kategoride genel pay). İlk kayıttan
                          sonrası yalnız Kayran kaydından sayılır — aynı iade iki kez sayılmaz.
  Tahmini dahil oran      (arızalı + arızalı tahmini) ÷ ulaşan. Kesin oran ("Arıza oranı (%)") değişmez.
Haziran 2026 öncesi iadesiz teknik servis ürünleri Mikro'da yoktur: tahmini dahil oran da alt sınırdır.
"""
from shared.utils import normalize_tr

ARIZA = "Arıza doğrulandı"
NTF = "Arıza bulunamadı (NTF)"
FIZIKSEL = "Fiziksel / kargo hasarı"
SAGLAM = "Sağlam iade (cayma)"
EKSIK = "Eksik parça"
BELIRSIZ = "Belirlenemedi"
SONUCLAR = [ARIZA, NTF, FIZIKSEL, SAGLAM, EKSIK]          # teknisyenin seçebildikleri

# Kelime kuralları (normalize_tr: BÜYÜK harf, Türkçe harf yok). Önce teknisyenin yazdığı alanlara
# (yapılan işlem, test süreci, fiziksel durum) bakılır — teknisyenin tespiti müşterinin beyanından
# önce gelir; orada sonuç yoksa müşterinin arıza beyanına. Her metinde sıra: açık arıza → kesin
# fiziksel hasar → diğer arıza belirtileri → zayıf hasar → arıza bulunamadı → eksik → cayma.
_ARIZA_ACIK = ["ARIZA", "PIKSEL", "PIXEL"]
_ARIZA_BELIRTI = [
    "GUC GELM", "GUC ALM", "GUC VERM", "GUC YOK", "GUCU KES", "ELEKTRIK GELM", "GORUNTU YOK",
    "GORUNTU VERM", "GORUNTU GELM", "GORUNTU GID", "GORUNTU KES", "GORUNTU KAPAN", "CALISMIYOR",
    "CALISMAMAKTA", "CALISMADIG", "CALISMAZ", "SORUN",
    "PROBLEM", "CIZGI", "KARARMA", "SIYAH", "ISIK SIZMA", "SIGORTA", "KISA DEVRE", "RESET",
    "YENIDEN BASLA", "ISINMA", "ISINIYOR", "SICAKLIK", "SOGUTMA", "KAPANIYOR", "KAPANMA", "DONMA",
    "KITLIYOR", "GORMUYOR", "YUKLENMIYOR", "LEKE", "BOZUK", "YANIK", "YANMIS", "SES GEL", "SURTME",
    "SOKETI", "KOPUK", "KAYMA", "EKRAN ALTI TOZ", "ACILMAMI", "PATLAMIS",
]
# Parça değişimi: arızalı bileşen (PSU, fan…) — kasa/cam/ayak değişimi fiziksel hasardır.
_ARIZA_PARCA = ["PSU", "GUC KAYNAGI", "FAN", "KONTROLCU", "ADAPTOR", "ANAKART", "I/O PANEL",
                "GUC KABLOSU", "DP KABLO", "POWER"]
_FIZIKSEL_KESIN = ["KOLI HASAR", "KIRIK", "KIRIL", "KRIK", "CATLA", "YAMUK", "YAMUL", "DARBE", "EZIK", "DEFORME",
                   "EGIK", "CIZIK", "NEM ", "NEM.", "ISLAK", "SIVI", "PASLAN", "GOCMUS", "KARGODAN",
                   "CAMI PATLA", "URUN HASARLI"]
_FIZIKSEL_ZAYIF = ["PANEL DEGIS", "CAM DEGIS", "AYAK DEGIS", "HASAR", "EGRI", "EGIM", "BOSLUK", "ACIKLIK", "KUSUR", "SABIT DURMUYOR"]
_NTF_KELIME = ["NTF", "RASTLANILMADI", "RASTLANILAMADI", "RASTLANMADI", "SORUNSUZ", "STABIL",
               "TESPIT YAPILAMADI", "GORUNTU ALINMISTIR", "GORUNTU ALINDI"]
_EKSIK_KELIME = ["EKSIK", "BULUNMAMAKTA", "AYAGI YOK"]
_SAGLAM_KELIME = ["CAYMA", "MEMNUNIYET", "MEMNUN KALINMADI", "TESLIM ALINMAYAN"]
_BOS_BEYAN = {"", "NO INFO", "NO  INFO", "NOINFO", "-"}


def _var(metin, kelimeler):
    return any(w in metin for w in kelimeler)


def _sinifla(m):
    m = m.replace("HASARSIZ", " ")                       # "hasarsız" hasar değildir
    if not m.strip():
        return None
    if _var(m, _ARIZA_ACIK):
        return ARIZA
    if _var(m, _FIZIKSEL_KESIN):
        return FIZIKSEL
    if _var(m, _NTF_KELIME):
        return NTF
    if _var(m, _ARIZA_BELIRTI) or ("DEGIS" in m and _var(m, _ARIZA_PARCA)):
        return ARIZA
    if _var(m, _FIZIKSEL_ZAYIF):
        return FIZIKSEL
    if _var(m, _EKSIK_KELIME):
        return EKSIK
    if _var(m, _SAGLAM_KELIME):
        return SAGLAM
    return None


def tahmin(kayit):
    """Arıza sonucunu metinden tahmin eder (kayda yazılmaz)."""
    k = kayit or {}
    teknisyen = normalize_tr(" | ".join(str(k.get(a) or "") for a in
                                        ("yapilan_islem", "test_sureci", "fiziksel_durum")))
    beyan = normalize_tr(k.get("ariza")).strip()
    s = _sinifla(teknisyen) or _sinifla(beyan)
    if s:
        return s
    if k.get("arayuz") == "iade" and beyan in _BOS_BEYAN:
        return SAGLAM                                     # sebep yazılmamış iade: arıza sayılmaz
    return BELIRSIZ


# Bu durumlara geçerken (teknik / iade kaydında) arıza sonucu seçilmiş olmalı.
_SONUCSUZ_DURUMLAR = {"mal kabül", "teknisyende", "iptal"}


def sonuc_zorunlu(arayuz, yeni_durum):
    return arayuz in ("teknik", "iade") and yeni_durum not in _SONUCSUZ_DURUMLAR


def sonuc(kayit):
    """(sonuç, tahmini_mi). Teknisyenin seçtiği sonuç varsa o; yoksa tahmin."""
    s = str((kayit or {}).get("ariza_sonucu") or "").strip()
    if s in SONUCLAR:
        return s, False
    return tahmin(kayit), True


def _gun(v):
    return str(v or "")[:10]


def servis_ozeti(kayitlar, anahtar, bas=None, bit=None):
    """{sku: {"gelen", "arizali", "tahmini", "sonuclar": {sonuç: adet}}} — aynı SKU'da aynı seri
    numarası bir kez sayılır (önce teknisyenin kesin sonucu, sonra arıza sonucu öncelikli)."""
    sec = {}
    for k in kayitlar or []:
        g = _gun(k.get("mal_kabul_tarihi") or k.get("olusturma_tarihi"))
        if (bas and g and g < str(bas)) or (bit and g and g > str(bit)):
            continue
        sku = anahtar(k.get("stok_kodu"))
        if not sku:
            continue
        s, t = sonuc(k)
        seri = normalize_tr(k.get("seri_no")).strip() or f"_id{k.get('id')}"
        onceki = sec.get((sku, seri))
        aday = (not t, s == ARIZA, s, t)
        if onceki is None or aday[:2] > onceki[:2]:
            sec[(sku, seri)] = aday
    oz = {}
    for (sku, _seri), (_kesin, _ar, s, t) in sec.items():
        o = oz.setdefault(sku, {"gelen": 0, "arizali": 0, "tahmini": 0, "sonuclar": {}})
        o["gelen"] += 1
        o["sonuclar"][s] = o["sonuclar"].get(s, 0) + 1
        if s == ARIZA:
            o["arizali"] += 1
            o["tahmini"] += 1 if t else 0
    return oz


def satis_toplami(satislar, anahtar, bas=None, bit=None):
    """{sku: net adet} — dönemdeki müşteri satışları (iadeler eksi adetle düşer)."""
    t = {}
    for s in satislar or []:
        g = _gun(s.get("tarih"))
        if (bas and g < str(bas)) or (bit and g > str(bit)):
            continue
        k = anahtar(s.get("sku"))
        if k:
            t[k] = t.get(k, 0.0) + float(s.get("adet") or 0)
    return t


def musteri_stogu(kanal):
    """{sku: adet} — her müşterinin son raporundaki stok toplamı."""
    t = {}
    for skular in (kanal or {}).values():
        for k, a in skular.items():
            t[k] = t.get(k, 0.0) + max(0.0, float(a or 0))
    return t


def alim_toplami(partiler):
    """{sku: adet} — teslim alınmış alımlar (ithalat + yurt içi + yerli)."""
    return {k: sum(float(p.get("adet") or 0) for p in ps) for k, ps in (partiler or {}).items()}


def oran(arizali, ulasan):
    return (arizali / ulasan * 100.0) if ulasan and ulasan > 0 else None


def _yuzde(r):
    return None if r is None else round(r, 2)


def satirlar(kartlar, alim, satis, mstok, servis, mikro=None):
    """Ekran / Excel satırları — servise gelen, satılan ya da Mikro'da iadesi olan her SKU (en yüksek oran önce).
    mikro: mikro_ozeti(...) sonucu ya da None (Mikro sütunları eklenmez)."""
    mk = mikro or {}
    once, iade = mk.get("once") or {}, mk.get("iade") or {}
    out = []
    for k in set(satis) | set(servis) | (set(once) | set(iade) if mikro else set()):
        u = kartlar.get(k) or {}
        sv = servis.get(k) or {}
        sat = max(0.0, satis.get(k, 0.0))
        ul = max(0.0, sat - mstok.get(k, 0.0))
        r = oran(sv.get("arizali", 0), ul)
        s = {"_id": k, "SKU": u.get("sku") or k, "Ürün": u.get("urun_adi") or "",
             "Kategori": u.get("kategori") or "", "Marka": u.get("marka") or "",
             "Satın alınan": round(alim.get(k, 0.0)), "Müşteriye satılan": round(sat),
             "Müşteri stoğunda": round(mstok.get(k, 0.0)), "Son kullanıcıya ulaşan": round(ul),
             "Servise gelen": sv.get("gelen", 0), "Arızalı": sv.get("arizali", 0),
             "Arızalının tahmini": sv.get("tahmini", 0), "Arıza oranı (%)": _yuzde(r)}
        if mikro:
            tah = once.get(k, 0.0) * pay_bul(mk.get("paylar"), mk.get("genel_pay"), u.get("kategori"))
            s.update({"Mikro iadesi (kayıt öncesi)": round(once.get(k, 0.0)),
                      "Arızalı tahmini (Mikro iade)": round(tah, 1),
                      "Arıza oranı tahmini dahil (%)": _yuzde(oran(s["Arızalı"] + tah, ul)),
                      "Mikro iadesi (dönem)": round(iade.get(k, 0.0)),
                      "İade oranı (%)": _yuzde(oran(iade.get(k, 0.0), ul))})
        out.append(s)
    out.sort(key=lambda x: (x["Arıza oranı (%)"] is None, -(x["Arıza oranı (%)"] or 0), -x["Arızalı"]))
    return out


_MIKRO_TOPLAM = ("Mikro iadesi (kayıt öncesi)", "Arızalı tahmini (Mikro iade)", "Mikro iadesi (dönem)")


def grup_ozeti(satirlar_, alan):
    """Kategori / marka kırılımı: toplam ulaşan, arızalı, oran (+ Mikro sütunları varsa onların toplamı)."""
    g = {}
    for s in satirlar_:
        a = s.get(alan) or "—"
        o = g.setdefault(a, {alan: a, "Son kullanıcıya ulaşan": 0, "Arızalı": 0, "Servise gelen": 0})
        o["Son kullanıcıya ulaşan"] += s["Son kullanıcıya ulaşan"]
        o["Arızalı"] += s["Arızalı"]
        o["Servise gelen"] += s["Servise gelen"]
        for m in _MIKRO_TOPLAM:
            if m in s:
                o[m] = o.get(m, 0) + s[m]
    out = []
    for o in g.values():
        r = oran(o["Arızalı"], o["Son kullanıcıya ulaşan"])
        o["Arıza oranı (%)"] = _yuzde(r)
        if _MIKRO_TOPLAM[1] in o:
            o[_MIKRO_TOPLAM[1]] = round(o[_MIKRO_TOPLAM[1]], 1)
            o["Arıza oranı tahmini dahil (%)"] = _yuzde(oran(o["Arızalı"] + o[_MIKRO_TOPLAM[1]],
                                                             o["Son kullanıcıya ulaşan"]))
            o["İade oranı (%)"] = _yuzde(oran(o[_MIKRO_TOPLAM[2]], o["Son kullanıcıya ulaşan"]))
        out.append(o)
    out.sort(key=lambda x: (x["Arıza oranı (%)"] is None, -(x["Arıza oranı (%)"] or 0)))
    return out


# ── Mikro iadeleri ──────────────────────────────────────────────────
IADE_IRSALIYE = 3              # sth_evraktip: müşteri iade irsaliyesi
TOPLU_SINIR = 3                # satırda bundan fazla adet: toplu stok iadesi, arıza değil
IADE_DEPO_KELIME = ("SERVIS", "IADE")
PAY_ORNEK_ALT = 20             # kategoride bundan az iade kaydı varsa genel pay


def iade_depolari(depo_kartlar):
    """Mikro depo kartlarından iadenin girdiği depolar (adında SERVİS ya da İADE geçen) → {dep_no}."""
    out = set()
    for d in depo_kartlar or []:
        ad = normalize_tr(d.get("dep_adi"))
        if any(w in ad for w in IADE_DEPO_KELIME):
            try:
                out.add(int(d.get("dep_no")))
            except (TypeError, ValueError):
                pass
    return out


def _iptal(v):
    return v is True or str(v or "").strip().lower() in ("1", "true")


def mikro_iadeleri(hareketler, anahtar, depolar, bas=None, bit=None, once=None):
    """{sku: adet} — iade depolarına giren tekli müşteri iadeleri. once: bu günden ÖNCEKİLER (ilk servis kaydı)."""
    t = {}
    for h in hareketler or []:
        if _iptal(h.get("sth_iptal")):
            continue
        try:
            tip, ia, dep = int(h.get("sth_evraktip")), int(h.get("sth_normal_iade")), int(h.get("sth_giris_depo_no"))
            adet = float(h.get("sth_miktar") or 0)
        except (TypeError, ValueError):
            continue
        if tip != IADE_IRSALIYE or ia != 1 or dep not in depolar or not 0 < adet <= TOPLU_SINIR:
            continue
        g = _gun(h.get("sth_tarih"))
        if not g or (bas and g < str(bas)) or (bit and g > str(bit)) or (once and g >= str(once)):
            continue
        k = anahtar(h.get("sth_stok_kod"))
        if k:
            t[k] = t.get(k, 0.0) + adet
    return t


def iade_arizali_payi(kayitlar, anahtar, kategori_bul):
    """Kayran'daki iade kayıtlarında arızalı payı: ({kategori: pay}, genel pay). kategori_bul(sku) → kategori.
    Aynı seri bir kez; az örnekli kategori sözlüğe girmez (pay_bul genel payı kullanır)."""
    oz = servis_ozeti([k for k in kayitlar or [] if k.get("arayuz") == "iade"], anahtar)
    kat, gelen, ariz = {}, 0, 0
    for sku, o in oz.items():
        x = kat.setdefault(kategori_bul(sku) or "", [0, 0])
        x[0] += o["gelen"]
        x[1] += o["arizali"]
        gelen += o["gelen"]
        ariz += o["arizali"]
    paylar = {k: a / g for k, (g, a) in kat.items() if k and g >= PAY_ORNEK_ALT}
    return paylar, (ariz / gelen if gelen else 0.0)


def pay_bul(paylar, genel, kategori):
    return (paylar or {}).get(kategori or "", genel or 0.0)


def mikro_ozeti(hareketler, depo_kartlar, kayitlar, anahtar, kategori_bul, bas, bit, ilk_kayit):
    """satirlar(mikro=…) girdisi: kayıt öncesi iadeler, dönemin bütün iadeleri, kategori payları."""
    dep = iade_depolari(depo_kartlar)
    paylar, genel = iade_arizali_payi(kayitlar, anahtar, kategori_bul)
    return {"once": mikro_iadeleri(hareketler, anahtar, dep, bas, bit, once=ilk_kayit) if ilk_kayit else {},
            "iade": mikro_iadeleri(hareketler, anahtar, dep, bas, bit),
            "paylar": paylar, "genel_pay": genel}
