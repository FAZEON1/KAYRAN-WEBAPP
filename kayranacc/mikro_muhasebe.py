# -*- coding: utf-8 -*-
"""Mikro → muhasebe otomatik eşitleme (Ekim 2026, Mikro adım 1).

Kullanıcı: "Olabildiğince az dosya upload / elle giriş; olabilecek tüm veriler Mikro'dan, tam otomatik."
Ham veri aktarıcıdan gelir (araclar/mikro_aktarici, 15 dakikada bir): mikro_cari_hareket, mikro_banka_kart,
mikro_cari_kart, mikro_cek. Bu modül o veriden şunları üretir ve uygulamanın mevcut tablolarına yazar
(okuyan ekranlar değişmez):

  Banka bakiyesi  → bankalar.bakiye       (eşleşen hesaplar; Mikro'da olup uygulamada olmayan hesap eklenmez)
  Firma çekleri   → cekler                (Firma çek dökümü Excel'i yerine)
  Cari borç/alacak→ Toplam Aktifler "cari"     (Cari alacaklar Excel'i yerine)
  İthalat ödenen  → Toplam Aktifler "ithalat"  (İthalat ödeme takip Excel'i yerine)

Formüller (21.10.2026'da eski değerlerle doğrulandı):
  Bakiye = Σ borç − Σ alacak (cha_tip 0 borç, 1 alacak), hesabın kendi dövizinde:
    TL hesap: tutar × hareket kuru (cha_meblag × cha_d_kur)
    döviz hesap: hareket aynı dövizdeyse tutar; karşı döviz hesabın dövizi ise tutar × kur / karşı kur;
                 kur değerleme / kur farkı fişi (evrak 59) döviz bakiyesini değiştirmez (yalnız TL değeri).
  Banka: hareketin kendisi banka (cari_cins 2) + karşı hesabı banka olan hareketler (kasa_hizmet 2, ters yönde).
    Firma çeki bankadan ödendiği gün düşer (verildiği gün değil; _banka_hareketleri).
    Uygulamadaki 11 hesabın 10'u kuruşu kuruşuna tuttu; İş TL farkı uygulamaya girilmemiş bir ödemeden.
  Cari (Toplam Aktifler): 120 (alıcılar) + 340 (alınan avanslar); bakiye > 0 alacak, < 0 borç (19.10 Excel'i:
    TL ve alacak birebir, USD borç 2.093 $ fark — 120.01.001 eski EERA hesabı, Mikro raporu 0 gösteriyor).
  İthalat ödenen: 320.50 (yurt dışı tedarikçiler) USD hesaplarının pozitif bakiyeleri (verilen avans) — 19.10
    Excel'i 622.888,27 birebir.
  Çek: ODEME_EMIRLERI'nde firma çekleri (sck_tip 2); verildiği cari ve tarih çekin referans numaralı
    "çek verildi" hareketinden (evrak 67); ödenen ≥ tutar ise Ödendi.

İlk açılışta kullanıcı "şimdi ↔ Mikro" karşılaştırmasını görüp onaylar (Muhasebe › Bankalar üstünde bir kez);
sonra otomatik() her aktarım turunda çalışır. Durum sistem_ayarlari'nda (DURUM_ANAHTAR; şema değişikliği yok).
Stok değeri (Toplam Aktifler) ve gider tablosu bu adımda Excel'den gelmeye devam eder.
"""
from collections import defaultdict

DURUM_ANAHTAR = "mikro_muhasebe_durum"
DOVIZ = {0: "TL", 1: "USD", 2: "EUR"}
KUR_FARKI_TIP = 59      # cha_evrak_tip: kur değerleme / kur farkı fişi
CEK_VERILDI_TIP = 67    # cha_evrak_tip: firma çeki cariye verildi
CEK_ODENDI_TIP = 38     # cha_evrak_tip: firma çeki bankadan ödendi
FIRMA_CEKI = 2          # sck_tip: kendi çekimiz
BANKA_CINS = 2          # cha_cari_cins / cha_kasa_hizmet: banka
CARI_CINS = 0
CARI_ONEK = ("120", "340")
ITHALAT_ONEK = "320.50"
KURUS = 0.005


def _f(v, d=0.0):
    try:
        x = float(v)
        return x if x == x else d
    except (TypeError, ValueError):
        return d


def _i(v, d=0):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return d


def _s(v):
    return str(v or "").strip()


# ── Saf: bakiye ─────────────────────────────────────────────────────
def hareket_tutari(h, dc):
    """Bir hareketin dc dövizli (0 TL, 1 USD, 2 EUR) hesaptaki tutarı, işaretsiz."""
    m = _f(h.get("cha_meblag"))
    if dc == 0:
        return m * (_f(h.get("cha_d_kur")) or 1.0)
    if _i(h.get("cha_evrak_tip"), -1) == KUR_FARKI_TIP:
        return 0.0
    if _i(h.get("cha_d_cins")) == dc:
        return m
    kk = _f(h.get("cha_karsid_kur"))
    if _i(h.get("cha_karsidcinsi"), -1) == dc and kk > 0:
        return m * (_f(h.get("cha_d_kur")) or 1.0) / kk
    return 0.0


def bakiyeler(hareketler, dovizler, cins, karsi=False):
    """{hesap kodu: bakiye} — dovizler: {kod: döviz cinsi}. cins: cha_cari_cins (0 cari, 2 banka).
    karsi=True: karşı hesabı (cha_kasa_hizmet + cha_kasa_hizkod) bu cinsten olan hareketler de ters yönde sayılır."""
    out = defaultdict(float)
    for h in hareketler:
        borc = _i(h.get("cha_tip")) == 0
        kod = _s(h.get("cha_kod"))
        if _i(h.get("cha_cari_cins"), -1) == cins and kod in dovizler:
            t = hareket_tutari(h, dovizler[kod])
            out[kod] += t if borc else -t
        kk = _s(h.get("cha_kasa_hizkod"))
        if karsi and _i(h.get("cha_kasa_hizmet"), -1) == cins and kk in dovizler:
            t = hareket_tutari(h, dovizler[kk])
            out[kk] += -t if borc else t
    return {k: round(v, 2) for k, v in out.items()}


def _banka_hareketleri(hareketler):
    """Firma çeki bankayı ÖDENDİĞİ gün etkiler (gerçek banka gibi). Mikro çeki cariye verdiği gün (evrak 67)
    karşı hesap olarak bankadan düşüyor, ödendiği gün (evrak 38) banka ↔ aynı banka sıfır kayıt atıyor:
    ödenmemiş çek bakiyeden erken düşüyordu (YKB USD 19.450 $; Toplam Aktifler çekleri ayrıca düştüğü için
    iki kez). Burada: 67'nin banka etkisi yok, 38'in yalnız çıkış (karşı) tarafı sayılır."""
    for h in hareketler:
        tip = _i(h.get("cha_evrak_tip"), -1)
        if tip == CEK_VERILDI_TIP:
            continue
        if (tip == CEK_ODENDI_TIP and _i(h.get("cha_cari_cins"), -1) == BANKA_CINS
                and _s(h.get("cha_kod")) == _s(h.get("cha_kasa_hizkod"))):
            h = dict(h, cha_cari_cins=-1)
        yield h


def banka_bakiyeleri(hareketler, kartlar):
    """{ban_kod: bakiye} (hesabın dövizinde)."""
    dov = {_s(k.get("ban_kod")): _i(k.get("ban_doviz_cinsi")) for k in kartlar if _s(k.get("ban_kod"))}
    b = bakiyeler(_banka_hareketleri(hareketler), dov, BANKA_CINS, karsi=True)
    return {k: b.get(k, 0.0) for k in dov}


def cari_bakiyeleri(hareketler, kartlar):
    """{cari_kod: bakiye} (carinin dövizinde)."""
    dov = {_s(k.get("cari_kod")): _i(k.get("cari_doviz_cinsi")) for k in kartlar if _s(k.get("cari_kod"))}
    return bakiyeler(hareketler, dov, CARI_CINS)


def cari_ozeti(cari_bak, kartlar):
    """Toplam Aktifler 'cari' kaydı: {"borc": {usd, tl, eur}, "alacak": {...}} — 120 + 340 hesapları."""
    dov = {_s(k.get("cari_kod")): _i(k.get("cari_doviz_cinsi")) for k in kartlar}
    ad = {0: "tl", 1: "usd", 2: "eur"}
    out = {"borc": {"usd": 0.0, "tl": 0.0, "eur": 0.0}, "alacak": {"usd": 0.0, "tl": 0.0, "eur": 0.0}}
    for kod, b in cari_bak.items():
        if not kod.startswith(CARI_ONEK) or abs(b) < KURUS or dov.get(kod) not in ad:
            continue
        out["alacak" if b > 0 else "borc"][ad[dov[kod]]] += abs(b)
    return {y: {k: round(v, 2) for k, v in d.items()} for y, d in out.items()}


VIRMAN_GERI_GUN = 10


def _virman_159_mu(h):
    from shared.utils import tr_buyuk
    a = tr_buyuk(_s(h.get("cha_aciklama")))
    return _s(h.get("cha_kod")).startswith(ITHALAT_ONEK) and "VIRMAN" in a and "159" in a


def donem_sonu_virmansiz(hareketler, bugun=None, gun=VIRMAN_GERI_GUN):
    """Dönem sonu 320 → 159 virmanı (canlı: 31.12 "320-159 VİRMANI", ertesi gün aynı tutarla geri alınıyor) henüz
    geri alınmamışken avans bir günlüğüne 159'a geçiyor ve ithalat ödenen o tutar kadar düşük görünüyordu
    (30.06'da ~140 bin $). Kullanıcı (21.10.2026): "5'te ne gerekirse yap". Kural: 320.50'deki, açıklamasında
    VİRMAN ve 159 geçen, son `gun` gün içindeki ve aynı hesapta aynı tutarlı TERS kaydı henüz olmayan hareket yok
    sayılır. Geri alınmış çiftler (net sıfır) ve eski kalıcı sınıflandırmalar olduğu gibi kalır."""
    from datetime import date, timedelta
    bugun = bugun or date.today()
    sinir = (bugun - timedelta(days=gun)).isoformat()
    vir = [h for h in hareketler if _virman_159_mu(h)]
    kullanilan, at = set(), set()
    for i, h in enumerate(vir):
        if id(h) in kullanilan:
            continue
        es = next((x for x in vir[i + 1:] if id(x) not in kullanilan and _s(x.get("cha_kod")) == _s(h.get("cha_kod"))
                   and _i(x.get("cha_tip")) != _i(h.get("cha_tip"))
                   and abs(_f(x.get("cha_meblag")) - _f(h.get("cha_meblag"))) < KURUS), None)
        if es is not None:
            kullanilan.update((id(h), id(es)))
        elif str(h.get("cha_tarihi") or "")[:10] >= sinir:
            at.add(id(h))
    return [h for h in hareketler if id(h) not in at] if at else hareketler


ITHALAT_IRSALIYE = 13          # sth_evraktip: ithalat irsaliyesi (mal teslim alındı)
BOS_UID = ("", "00000000-0000-0000-0000-000000000000")


def faturasiz_teslimler(alim_satirlari):
    """Teslim alınmış ama tedarikçi faturası Mikro'ya girilmemiş ithalat ($): {320.50 cari: tutar}.
    Kullanıcı (22.10.2026, "A olsun"): INNOVISION-017 20.10'da irsaliyeyle girdi ve EERA'ya satıldı, faturası
    girilmediği için 260.800 $ ödeme 320.50.101'de avans olarak kaldı; malın maliyeti hem avans hem satış olarak
    aktifte sayılıyordu. Satır: ithalat irsaliyesi (evrak 13), iade değil, faturaya bağlanmamış (sth_fat_uid boş),
    dövizi USD (tutar hareket dövizinde)."""
    out = defaultdict(float)
    for s in alim_satirlari or []:
        kod = _s(s.get("sth_cari_kodu"))
        if (_i(s.get("sth_evraktip"), -1) != ITHALAT_IRSALIYE or not kod.startswith(ITHALAT_ONEK)
                or _i(s.get("sth_normal_iade")) == 1 or _s(s.get("sth_fat_uid")).lower() not in BOS_UID
                or _i(s.get("sth_har_doviz_cinsi"), -1) != 1):
            continue
        out[kod] += _f(s.get("sth_tutar")) - _f(s.get("sth_iskonto"))
    return {k: round(v, 2) for k, v in out.items() if v > KURUS}


def ithalat_odenen(cari_bak, kartlar, faturasiz=None):
    """Yurt dışı tedarikçilere verilen avans ($): 320.50 USD hesaplarının pozitif bakiyeleri; teslim alınmış ama
    faturası girilmemiş mal (faturasiz_teslimler) avanstan düşülür — bakiyeyi aşmadan (mal o tedarikçiden geldi,
    avans karşılığını buldu; stokta ya da satışta zaten sayılıyor)."""
    dov = {_s(k.get("cari_kod")): _i(k.get("cari_doviz_cinsi")) for k in kartlar}
    faturasiz = faturasiz or {}
    return round(sum(max(b - faturasiz.get(kod, 0.0), 0.0) for kod, b in cari_bak.items()
                     if kod.startswith(ITHALAT_ONEK) and dov.get(kod) == 1 and b > KURUS), 2)


# ── Saf: uygulamadaki banka hesabı ↔ Mikro banka kartı ──────────────
_BANKALAR = (("ZIRAAT", ("ZIRAAT",)), ("GARANTI", ("GARANTI",)), ("HALK", ("HALK",)),
             ("YKB", ("YAPI", "YKB")), ("IS", ("IS BANK", "ISBANK")))
_ISARETLER = ("VADELI", "DBS", "YATIRIM", "KART", "EURO")
_TR = str.maketrans("İIŞĞÜÖÇışğüöç", "IISGUOCisguoc")


def _norm(ad):
    return " ".join(_s(ad).translate(_TR).upper().replace("K.KART", "KART").replace("-", " ").split())


def _banka_imi(ad):
    n = _norm(ad)
    for b, kaliplar in _BANKALAR:
        if any(k in n for k in kaliplar):
            return b
    return ""


def _isaretler(ad):
    n = _norm(ad)
    return frozenset(i for i in _ISARETLER if i in n) - {"EURO"}


def banka_eslestir(bankalar, kartlar):
    """{uygulama banka id: ban_kod}. Banka adı + döviz + işaret (VADELİ, DBS, YATIRIM, KART) aynı olmalı;
    birden çok aday kalırsa adında rakam olmayan (ana hesap) seçilir, yine de tek değilse eşleşmez."""
    pb = {"TL": 0, "TRY": 0, "USD": 1, "EUR": 2, "EURO": 2}
    out = {}
    for b in bankalar:
        dc = pb.get(_norm(b.get("para_birimi")))
        bi, isr = _banka_imi(b.get("hesap_adi")), _isaretler(b.get("hesap_adi"))
        if dc is None or not bi:
            continue
        aday = [k for k in kartlar
                if _i(k.get("ban_doviz_cinsi")) == dc and _banka_imi(k.get("ban_ismi")) == bi
                and _isaretler(k.get("ban_ismi")) == isr]
        if len(aday) > 1:
            aday = [k for k in aday if not any(ch.isdigit() for ch in _s(k.get("ban_ismi")))]
        if len(aday) == 1:
            out[b.get("id")] = _s(aday[0].get("ban_kod"))
    return out


# ── Saf: çekler ────────────────────────────────────────────────────
def cek_satirlari(cekler, hareketler, cari_ad, banka_ad):
    """mikro_cek → cekler tablosu satırları (Firma çek dökümü Excel'inin karşılığı)."""
    verildi = {}
    for h in hareketler:
        ref = _s(h.get("cha_trefno"))
        if ref and _i(h.get("cha_evrak_tip"), -1) == CEK_VERILDI_TIP and _i(h.get("cha_cari_cins"), -1) == CARI_CINS:
            verildi.setdefault(ref, h)
    out = []
    for c in cekler:
        if _i(c.get("sck_tip"), -1) != FIRMA_CEKI:
            continue
        tutar, odenen = round(_f(c.get("sck_tutar")), 2), round(_f(c.get("sck_odenen")), 2)
        ref = _s(c.get("sck_refno"))
        v = verildi.get(ref) or {}
        kod = _s(v.get("cha_kod")) or _s(c.get("sck_nerede_cari_kodu")) or _s(c.get("sck_sahip_cari_kodu"))
        if odenen >= tutar - KURUS and tutar > 0:
            durum = "Ödendi"
        elif v or _i(c.get("sck_nerede_cari_cins"), -1) == CARI_CINS:
            durum = "Ciro edildi"
        else:
            durum = "Bekliyor"
        bankano = _s(c.get("sck_bankano"))
        out.append({
            "ref_no": ref, "cek_no": _s(c.get("sck_no")),
            "tarih": _s(v.get("cha_tarihi"))[:10] or None, "vade": _s(c.get("sck_vade"))[:10] or None,
            "meblagh": tutar, "odenen": odenen, "kalan": round(max(0.0, tutar - odenen), 2), "durum": durum,
            "ch_kodu": kod, "ch_ismi": cari_ad.get(kod) or banka_ad.get(kod) or "",
            "banka": banka_ad.get(bankano) or _s(c.get("sck_banka_adres1")),
            "sube": _s(c.get("sck_sube_adres2")), "hesap_no": _s(c.get("sck_hesapno_sehir")),
            "para_birimi": DOVIZ.get(_i(c.get("sck_doviz")), "TL"),
        })
    out.sort(key=lambda r: (r["vade"] or "", r["cek_no"]))
    return out


_CEK_ALANLARI = ("ref_no", "cek_no", "tarih", "vade", "meblagh", "odenen", "kalan", "durum", "ch_kodu", "ch_ismi",
                 "banka", "sube", "hesap_no", "para_birimi")


def cek_imzasi(satirlar):
    """Çek listesinin karşılaştırma imzası (değişmediyse yeniden yazılmaz)."""
    def _d(r, a):
        v = r.get(a)
        if a in ("meblagh", "odenen", "kalan"):
            return round(_f(v), 2)
        return _s(v)[:10] if a in ("tarih", "vade") else _s(v)
    return sorted(tuple(_d(r, a) for a in _CEK_ALANLARI) for r in satirlar)


def cek_ozeti(satirlar):
    """{para birimi: (adet, kalan toplamı)} — kalan > 0 olanlar."""
    out = defaultdict(lambda: [0, 0.0])
    for r in satirlar:
        k = _f(r.get("kalan"))
        if r.get("durum") != "Ödendi" and k > KURUS:
            out[r.get("para_birimi") or "TL"][0] += 1
            out[r.get("para_birimi") or "TL"][1] += k
    return {pb: (n, round(t, 2)) for pb, (n, t) in out.items()}


# ── Saf: plan ──────────────────────────────────────────────────────
def plan_yap(veri, bankalar, mevcut_cekler, mevcut_cari, mevcut_ithalat):
    """veri: {hareket, banka_kart, cari_kart, cek}. Döner: karşılaştırma + yazılacaklar."""
    hareket, bk, ck = veri["hareket"], veri["banka_kart"], veri["cari_kart"]
    bb = banka_bakiyeleri(hareket, bk)
    cb = cari_bakiyeleri(hareket, ck)
    es = banka_eslestir(bankalar, bk)
    bad = {_s(k.get("ban_kod")): _s(k.get("ban_ismi")) for k in bk}
    banka = []
    for b in bankalar:
        kod = es.get(b.get("id"))
        once = round(_f(b.get("bakiye")), 2)
        sonra = bb.get(kod, 0.0) if kod else None
        banka.append({"id": b.get("id"), "hesap": b.get("hesap_adi"), "para_birimi": b.get("para_birimi"),
                      "mikro_kod": kod or "", "mikro_ad": bad.get(kod, ""), "once": once, "sonra": sonra,
                      "degisir": sonra is not None and abs(sonra - once) >= KURUS})
    eslesen = set(es.values())
    disarida = [{"mikro_kod": k, "mikro_ad": bad.get(k, ""), "bakiye": v} for k, v in sorted(bb.items())
                if k not in eslesen and abs(v) >= KURUS]
    cad = {_s(k.get("cari_kod")): _s(k.get("cari_unvan1")) for k in ck}
    cek = cek_satirlari(veri["cek"], hareket, cad, bad)
    cari = cari_ozeti(cb, ck)
    fts = faturasiz_teslimler(veri.get("alim"))
    ith = ithalat_odenen(cari_bakiyeleri(donem_sonu_virmansiz(hareket), ck), ck, fts)
    return {
        "faturasiz_teslim": fts,
        "banka": banka, "banka_disarida": disarida,
        "cek": cek, "cek_degisir": cek_imzasi(cek) != cek_imzasi(mevcut_cekler),
        "cek_eski_id": [c.get("id") for c in mevcut_cekler if c.get("id") is not None],
        "cek_once": cek_ozeti(mevcut_cekler), "cek_sonra": cek_ozeti(cek),
        "cari": cari, "cari_once": mevcut_cari, "cari_degisir": cari != _cari_yuvarla(mevcut_cari),
        "ithalat": ith, "ithalat_once": mevcut_ithalat,
        "ithalat_degisir": mevcut_ithalat is None or abs(ith - _f(mevcut_ithalat)) >= KURUS,
    }


def _cari_yuvarla(c):
    if not isinstance(c, dict):
        return None
    return {y: {k: round(_f((c.get(y) or {}).get(k)), 2) for k in ("usd", "tl", "eur")} for y in ("borc", "alacak")}


# ── Veritabanı ─────────────────────────────────────────────────────
def _cli():
    from kayranacc.database import get_client
    return get_client()


_HAREKET_ALANLARI = ("cha_tip,cha_cari_cins,cha_kod,cha_kasa_hizmet,cha_kasa_hizkod,cha_d_cins,cha_d_kur,"
                     "cha_karsidcinsi,cha_karsid_kur,cha_meblag,cha_evrak_tip,cha_trefno,cha_tarihi,cha_aciklama")


def veri_oku():
    """Birincil anahtar sırasıyla, sayfaları kendisi okur (satis.mikro_esitle.sayfali_oku: oto-sayfalamanın bellekte
    eski kalan hâline güvenmez); kopya kayıt gelirse (okuma sırasında tablo değişti) reddeder (21.10.2026 olayı)."""
    from satis.mikro_esitle import sayfali_oku
    cli = _cli()
    return {
        "hareket": sayfali_oku(lambda: cli.table("mikro_cari_hareket").select("cha_guid," + _HAREKET_ALANLARI)
                               .order("cha_guid"), "cha_guid"),
        "banka_kart": sayfali_oku(lambda: cli.table("mikro_banka_kart").select("*").order("ban_kod"), "ban_kod"),
        "cari_kart": sayfali_oku(lambda: cli.table("mikro_cari_kart").select("cari_kod,cari_unvan1,cari_doviz_cinsi")
                                 .order("cari_kod"), "cari_kod"),
        "cek": sayfali_oku(lambda: cli.table("mikro_cek").select("*").order("sck_guid"), "sck_guid"),
        "alim": sayfali_oku(lambda: cli.table("mikro_alim_satir")
                            .select("sth_guid,sth_evraktip,sth_cari_kodu,sth_normal_iade,sth_fat_uid,"
                                    "sth_har_doviz_cinsi,sth_tutar,sth_iskonto")
                            .eq("sth_evraktip", ITHALAT_IRSALIYE).like("sth_cari_kodu", f"{ITHALAT_ONEK}%")
                            .order("sth_guid"), "sth_guid"),
    }


def _aktif_veri(tip):
    """Toplam Aktifler kaydının değeri (önbelleksiz)."""
    import json
    try:
        r = (_cli().table("aktif_excel_verileri").select("veri_json").eq("kullanici", "_SHARED_")
             .eq("dosya_tipi", tip).execute().data or [])
        if not r:
            return None
        v = json.loads(r[0]["veri_json"]) if isinstance(r[0]["veri_json"], str) else r[0]["veri_json"]
        return v.get("veri") if isinstance(v, dict) and "veri" in v else v
    except Exception:  # noqa: BLE001
        return None


def plan_hazirla():
    cli = _cli()
    bankalar = cli.table("bankalar").select("*").order("id").execute().data or []
    cekler = cli.table("cekler").select("*").execute().data or []
    return plan_yap(veri_oku(), bankalar, cekler, _aktif_veri("cari"), _aktif_veri("ithalat"))


KAYNAK_ADI = "Mikro"


def uygula(plan, ilk=False):
    """Değişenleri yazar. ilk=True (onay anı): silinen eski çekler çöp kutusuna düşer (geri alınabilir);
    otomatik turlarda düşmez (her çek hareketinde çöp kutusu dolmasın). Döner: {banka: n, cek, cari, ithalat}."""
    from contextlib import nullcontext
    from kayranacc import database as db
    from shared.cop_kutusu import cop_kutusu_kapali
    cli = _cli()
    sonuc = {"banka": 0, "cek": False, "cari": False, "ithalat": False}
    for b in plan["banka"]:
        if b["degisir"]:
            cli.table("bankalar").update({"bakiye": b["sonra"]}).eq("id", b["id"]).execute()
            sonuc["banka"] += 1
    if plan["cek_degisir"] and plan["cek"]:
        # Önce yeniler eklenir, sonra eskiler silinir: arada hata olursa liste boş kalmaz (sonraki tur düzeltir)
        for i in range(0, len(plan["cek"]), 50):
            cli.table("cekler").insert(plan["cek"][i:i + 50]).execute()
        eski = plan.get("cek_eski_id") or []
        with nullcontext() if ilk else cop_kutusu_kapali():
            for i in range(0, len(eski), 100):
                cli.table("cekler").delete().in_("id", eski[i:i + 100]).execute()
        sonuc["cek"] = True
    if plan["cari_degisir"]:
        sonuc["cari"] = bool(db.aktif_excel_kaydet(KAYNAK_ADI, "cari", plan["cari"]))
    if plan["ithalat_degisir"]:
        sonuc["ithalat"] = bool(db.aktif_excel_kaydet(KAYNAK_ADI, "ithalat", plan["ithalat"]))
    bagli = sorted(b["id"] for b in plan["banka"] if b.get("mikro_kod") and b.get("id") is not None)
    d = durum()
    if d.get("bagli_bankalar") != bagli:
        d["bagli_bankalar"] = bagli
        _durum_yaz(d)
    if sonuc["banka"] or sonuc["cek"]:
        db._cache_temizle()
    return sonuc


def durum():
    """{acik, acan, acilis, son_calisma}; okunamazsa {}."""
    try:
        from kayranacc.database import get_ayar
        return get_ayar(DURUM_ANAHTAR, {}) or {}
    except Exception:  # noqa: BLE001
        return {}


def acik_mi():
    return bool(durum().get("acik"))


def _durum_yaz(d):
    from kayranacc.database import set_ayar
    set_ayar(DURUM_ANAHTAR, d)


def bagli_banka_mi(banka_id):
    """Eşitleme açık ve bu uygulama hesabı Mikro'daki bir banka hesabına bağlı mı (bakiyeyi Mikro yazar)."""
    d = durum()
    return bool(d.get("acik")) and banka_id in (d.get("bagli_bankalar") or [])


def yalniz_bagli_mi(banka_idleri):
    """Eşitleme açık ve verilen hesapların HEPSİ Mikro'ya bağlı mı (boş liste: hayır). Öyleyse virman / tahsilat /
    arbitraj Mikro'ya girilir, uygulamadaki pencere yerine not gösterilir (kullanıcı kararı, 22.10.2026).
    Bağlı olmayan tek hesap bile varsa eski davranış sürer."""
    idler = [i for i in (banka_idleri or []) if i is not None]
    if not idler:
        return False
    d = durum()
    if not d.get("acik"):
        return False
    bagli = d.get("bagli_bankalar") or []
    return all(i in bagli for i in idler)


def ac(kullanici):
    from shared.utils import tr_now
    d = durum()
    d.update(acik=True, acan=str(kullanici or ""), acilis=str(tr_now()))
    _durum_yaz(d)


def son_aktarim():
    """Cari hareketin ya da alım satırının (faturasız teslim, 22.10.2026) en son çekim zamanı."""
    r = (_cli().table("mikro_senk_durum").select("son_cekim")
         .in_("tablo", ["mikro_cari_hareket", "mikro_alim_satir"]).execute().data or [])
    return max((str(x.get("son_cekim") or "") for x in r), default="")


def otomatik():
    """Açıksa ve aktarıcı son çalışmadan sonra yeni veri getirdiyse eşitler. Hata fırlatmaz."""
    try:
        d = durum()
        if not d.get("acik"):
            return None
        son = son_aktarim()
        if not son or (d.get("son_calisma") and str(d.get("son_calisma")) >= son):
            return None
        from satis.mikro_esitle import aktarim_suruyor
        if aktarim_suruyor():
            return None                   # aktarıcı yazıyor: sonraki turda
        sonuc = uygula(plan_hazirla())
        # uygula() bagli_bankalar'ı yazar: durum YENİDEN okunur. Eskiden turun başındaki kopya geri yazılıyordu,
        # bagli_bankalar her turda siliniyordu (canlı, 22.10.2026: hiçbir hesap "Mikro'ya bağlı" sayılmıyor,
        # tahsilat / virman formları açılıyor ve bakiyeye yazıyordu).
        d = durum()
        d["son_calisma"] = son
        _durum_yaz(d)
        return sonuc
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("kayranacc.mikro_muhasebe.otomatik", e)
        return None
