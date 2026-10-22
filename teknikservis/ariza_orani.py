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

Mikro depo hareketleri (kullanıcı, 22.10.2026: "İade değil arızalı ürün oranı önemli. Müşteri iyi satamıyor diye
başka yere verdiğimiz iadeler üründen kaynaklı değil. Ürün outlet, ikinci el, spot, hurda gibi depolara girmişse
demek ki üründen kaynaklı sorun; onları göreyim yeter."). Mikro'da arıza sonucu yazmaz ama ürünün nereye gittiği
yazar (mikro_depo_hareket, 2025'ten beri):
  Sorunlu depoya giren    adında OUTLET, İKİNCİ EL, HURDA ya da SPOT geçen depoya DIŞARIDAN giren adet (servis /
                          iade deposundan, merkezden…). Sorunlu depolar arası sevk (outlet → ikinci el) aynı ürünü
                          ikinci kez saymaz. Mikro arıza oranı = bu adet ÷ son kullanıcıya ulaşan.
  Servis deposundan satış servis / iade deposundan doğrudan satış faturası (spot satış) — ayrı sütun, orana girmez.
  Servis deposundan fire  servis / iade deposundan çıkış fişi (hurda / fire) — ayrı sütun, orana girmez.
Müşteri iadesi, iade deposuna giriş ve oradan merkeze dönüş (sağlam ürün) sayılmaz. Kayran'daki teknisyen sonucuna
dayanan "Arıza oranı (%)" ayrıca durur, iki oran toplanmaz.
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


MIKRO_SUTUN = ("Sorunlu depoya giren (Mikro)", "Servis deposundan satış (Mikro)", "Servis deposundan fire (Mikro)")
MIKRO_ORAN = "Arıza oranı Mikro depo (%)"


def satirlar(kartlar, alim, satis, mstok, servis, mikro=None):
    """Ekran / Excel satırları — servise gelen, satılan ya da Mikro'da sorunlu depoya giren her SKU (en yüksek oran
    önce). mikro: mikro_sorunlu(...) sonucu {sku: {"giren", "satis", "fire"}} ya da None (Mikro sütunları yok)."""
    mk = mikro or {}
    out = []
    for k in set(satis) | set(servis) | set(mk):
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
        if mikro is not None:
            m = mk.get(k) or {}
            s.update({MIKRO_SUTUN[0]: round(m.get("giren", 0.0)), MIKRO_ORAN: _yuzde(oran(m.get("giren", 0.0), ul)),
                      MIKRO_SUTUN[1]: round(m.get("satis", 0.0)), MIKRO_SUTUN[2]: round(m.get("fire", 0.0))})
        out.append(s)
    anahtar = MIKRO_ORAN if mikro is not None else "Arıza oranı (%)"
    out.sort(key=lambda x: (x[anahtar] is None, -(x[anahtar] or 0), -x["Arızalı"]))
    return out


def grup_ozeti(satirlar_, alan):
    """Kategori / marka kırılımı: toplam ulaşan, arızalı, oran (+ Mikro sütunları varsa onların toplamı)."""
    g = {}
    for s in satirlar_:
        a = s.get(alan) or "—"
        o = g.setdefault(a, {alan: a, "Son kullanıcıya ulaşan": 0, "Arızalı": 0, "Servise gelen": 0})
        o["Son kullanıcıya ulaşan"] += s["Son kullanıcıya ulaşan"]
        o["Arızalı"] += s["Arızalı"]
        o["Servise gelen"] += s["Servise gelen"]
        for m in MIKRO_SUTUN:
            if m in s:
                o[m] = o.get(m, 0) + s[m]
    out = []
    for o in g.values():
        o["Arıza oranı (%)"] = _yuzde(oran(o["Arızalı"], o["Son kullanıcıya ulaşan"]))
        if MIKRO_SUTUN[0] in o:
            o[MIKRO_ORAN] = _yuzde(oran(o[MIKRO_SUTUN[0]], o["Son kullanıcıya ulaşan"]))
        out.append(o)
    anahtar = MIKRO_ORAN if any(MIKRO_ORAN in o for o in out) else "Arıza oranı (%)"
    out.sort(key=lambda x: (x[anahtar] is None, -(x[anahtar] or 0)))
    return out


# ── Mikro depo hareketleri ───────────────────────────────────────────
SORUNLU_DEPO_KELIME = ("OUTLET", "IKINCI EL", "HURDA", "SPOT")
SERVIS_DEPO_KELIME = ("SERVIS", "IADE")
GIRIS, CIKIS, SEVK = 0, 1, 2           # sth_tip
SATIS_FATURASI, CIKIS_FISI = 1, 0      # sth_evraktip (çıkış hareketinde)
DEGER_FARKI = 9                        # sth_cins: tutar düzeltmesi, mal hareketi değil
SAYIM = (10, 11)                       # sth_cins: sayım farkı


def depo_gruplari(depo_kartlar):
    """Mikro depo kartları → (sorunlu depolar, servis / iade depoları) {dep_no}."""
    sorunlu, servis = set(), set()
    for d in depo_kartlar or []:
        ad = normalize_tr(d.get("dep_adi"))
        try:
            no = int(d.get("dep_no"))
        except (TypeError, ValueError):
            continue
        if any(w in ad for w in SORUNLU_DEPO_KELIME):
            sorunlu.add(no)
        elif any(w in ad for w in SERVIS_DEPO_KELIME):
            servis.add(no)
    return sorunlu, servis


def _iptal(v):
    return v is True or str(v or "").strip().lower() in ("1", "true")


def _int(v, d=-1):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def mikro_sorunlu(hareketler, anahtar, sorunlu, servis, bas=None, bit=None):
    """{sku: {"giren", "satis", "fire"}} — dönemde sorunlu depoya dışarıdan giren, servis / iade deposundan satılan
    ve fire çıkışı yapılan adet."""
    t = {}
    for h in hareketler or []:
        if _iptal(h.get("sth_iptal")) or _int(h.get("sth_cins")) in (DEGER_FARKI, *SAYIM):
            continue
        g = _gun(h.get("sth_tarih"))
        if not g or (bas and g < str(bas)) or (bit and g > str(bit)):
            continue
        tip, evr = _int(h.get("sth_tip")), _int(h.get("sth_evraktip"))
        gir, cik = _int(h.get("sth_giris_depo_no")), _int(h.get("sth_cikis_depo_no"))
        if tip in (GIRIS, SEVK) and gir in sorunlu and (tip == GIRIS or cik not in sorunlu):
            alan = "giren"
        elif tip == CIKIS and cik in servis and evr == SATIS_FATURASI:
            alan = "satis"
        elif tip == CIKIS and cik in servis and evr == CIKIS_FISI:
            alan = "fire"
        else:
            continue
        k = anahtar(h.get("sth_stok_kod"))
        try:
            adet = float(h.get("sth_miktar") or 0)
        except (TypeError, ValueError):
            adet = 0.0
        if k and adet > 0:
            o = t.setdefault(k, {"giren": 0.0, "satis": 0.0, "fire": 0.0})
            o[alan] += adet
    return t
