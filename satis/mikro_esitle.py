# -*- coding: utf-8 -*-
"""Mikro → satışlar / iadeler otomatik eşitleme (Ekim 2026).

Kullanıcı isteği: "Bundan sonra tüm satışlar, iadeler API'den otomatik güncel gelsin."
Karar (kullanıcı): 01.07.2026'dan itibaren satışların ve iadelerin TEK KAYNAĞI Mikro faturaları.

Veri: aktarıcı (araclar/mikro_aktarici) 15 dakikada bir mikro_satis_satir tablosuna satış ve satış iadesi
faturalarının ürün satırlarını yazar. Bu modül o satırlardan satislar / iadeler kayıtlarını üretir:

  Satış   = fatura türü 63 (satış faturası), iade değil. Satır başına bir kayıt:
            fatura no (seri-sıra, ör. G5F26-2525), fatura tarihi, cari ünvanı, SKU, adet,
            birim fiyat = (tutar − iskonto) / kur / adet  → $, KDV HARİÇ.
            kur: fatura $ ise faturanın kuru, değilse satırın alternatif döviz ($) kuru.
            Tutarı 0 olan satır (bedelsiz değişim) alınmaz: teknik servis o satışı kendisi yazıyor.
  İade    = fatura türü 0 + iade işaretli (satış iadesi faturası) → iadeler (kaynak 'mikro', belge_no).
            Alış iadesi (63 + iade) alınmaz.
  Maliyet = aynı faturadaki önceki kaydın maliyeti; yoksa değiştirilen eski satırların (aynı firma + SKU)
            ortalaması; yoksa bugünkü paçal (satis.database.get_pacal_map — Excel yüklemesiyle aynı).

Değiştirilen kayıtlar (başlangıç tarihinden sonra):
  · Mikro dışı kaynaklı BÜTÜN satış satırları (elle sipariş, sipariş Excel'i, teknik servis / 2.el satışı):
    Mikro esas (kullanıcı, 21.10.2026). Faturası kesilmemiş sipariş Mikro'ya girilir, açık Mikro siparişi olarak
    gelir (siparis_kayitlari). Uygulamada yeni elle satış açılmaz (satis.database.mikro_esas_mi).
  · Excel'den gelen iade satırları (kaynak 'excel') — firması Mikro'da olan.
  · Mikro'da değişen faturanın eski satırları (fatura yeniden yazılır); Mikro'da iptal edilen fatura.

Yazma veritabanında TEK İŞLEMDE (mikro_esitle_uygula, veritabani/37_mikro_satis.sql): silinen her satır
önce mikro_esitleme_arsiv'e yazılır. STOK DEĞİŞMEZ (stok G5F sayımı + stok defterinden gelir).
İlk açılışta kullanıcı "önce ↔ sonra" karşılaştırmasını görüp onaylar; sonra otomatik() her turda çalışır.
"""
from collections import defaultdict

BASLANGIC = "2026-07-01"
SATIS_TIP = 63          # cha_evrak_tip: satış faturası
IADE_TIP = 0            # cha_evrak_tip 0 + iade işareti: satış iadesi faturası
TS_NOT_ONEKI = "TEKNİK SERVİS"
NOT_ONEKI = "Mikro"
SIPARIS_NOT_ONEKI = "Mikro sipariş"     # açık Mikro siparişinden gelen bekleyen satış (siparis_kayitlari)
ESLESME_GUN = 45        # elle satır ↔ Mikro fatura satırı: en çok bu kadar gün önce / sonra (elle_fatura_eslestir)


# ── küçük yardımcılar ───────────────────────────────────────────────
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


def _gun(v):
    return str(v or "")[:10]


def fatura_no(seri, sira):
    """Mikro fatura numarası, eski Excel yüklemesiyle aynı biçim: 'G5F26-2525'."""
    s, n = str(seri or "").strip(), str(sira or "").strip()
    if n.endswith(".0"):
        n = n[:-2]
    return f"{s}-{n}" if s else n


def _kanonik(ad):
    from shared.utils import firma_kanonik, normalize_tr
    return normalize_tr(firma_kanonik(ad))


def _sku_a(sku):
    from shared.utils import sku_anahtar
    return sku_anahtar(sku)


def kur_haritasi(satirlar):
    """{gün: $ kuru} — aynı gün kesilen $ faturalarının kuru (Mikro'nun kendi kuru). TL faturanın satırında
    $ kuru yok (alternatif kur 1): o günün ya da en yakın önceki günün $ kuru kullanılır. Ocak–Haziran 2026
    TL faturalarında eski Excel kayıtlarıyla 325 faturadan 324'ü birebir tuttu."""
    h = {}
    for r in satirlar or []:
        if _i(r.get("cha_d_cins")) == 1 and _f(r.get("cha_d_kur")) > 1:
            g = _gun(r.get("cha_tarihi"))
            h[g] = max(h.get(g, 0.0), _f(r.get("cha_d_kur")))
    return h


def _onceki_kur(kurlar, gun):
    aday = [g for g in kurlar if g <= gun]
    return kurlar[max(aday)] if aday else None


def usd_tutar(r, kurlar=None):
    """Satır tutarı (iskonto düşülmüş, KDV hariç) $ olarak. Mikro satır tutarı FATURANIN DÖVİZİNDE tutar:
    $ faturada doğrudan $ (Ocak–Haziran 2026: 1.501 faturanın hepsi eski Excel kaydıyla birebir); TL faturada
    TL → o günün $ kuruyla çevrilir; başka döviz (€) önce faturanın kuruyla TL'ye. Kur bilinmiyorsa None."""
    net = _f(r.get("sth_tutar")) - _f(r.get("sth_iskonto"))
    cins = _i(r.get("cha_d_cins"))
    if cins == 1:
        return net
    tl = net if cins == 0 else net * _f(r.get("cha_d_kur"))
    kur = _onceki_kur(kurlar or {}, _gun(r.get("cha_tarihi")))
    if not kur and _f(r.get("sth_alt_doviz_kuru")) > 1:
        kur = _f(r.get("sth_alt_doviz_kuru"))
    return tl / kur if kur else None


def satir_turu(r):
    """'satis' | 'iade' | None (alış iadesi vb. — alınmaz)."""
    tip, iade = _i(r.get("cha_evrak_tip"), -1), _i(r.get("cha_normal_iade"))
    if tip == SATIS_TIP and iade == 0:
        return "satis"
    if tip == IADE_TIP and iade == 1:
        return "iade"
    return None


# ── Mikro satırı → satış / iade kaydı ───────────────────────────────
def mikro_kayitlari(satirlar, baslangic=BASLANGIC, kurlar=None):
    """Döner: {satis: {fatura_no: [kayıt]}, iade: {belge_no: [kayıt]}, atlanan: {neden: adet},
    son_fatura: {kanonik firma: son satış faturası tarihi}, cariler: {kanonik firma}, iade_cari: {cari kodu}}.
    Kayıtlarda maliyet yok (maliyet_ata doldurur)."""
    satis, iade = defaultdict(list), defaultdict(list)
    atlanan = defaultdict(int)
    kurlar = kur_haritasi(satirlar) if kurlar is None else kurlar
    son_fatura, cariler, iade_cari = {}, set(), set()
    for r in satirlar or []:
        tur = satir_turu(r)
        if tur is None:
            continue
        tarih = _gun(r.get("cha_tarihi") or r.get("sth_tarih"))
        if not tarih or tarih < baslangic:
            continue
        no = fatura_no(r.get("cha_evrakno_seri"), r.get("cha_evrakno_sira"))
        kod = str(r.get("sth_cari_kodu") or "").strip()
        unvan = " ".join(str(r.get("cari_unvan1") or "").split()) or kod
        sku = _sku_a(r.get("sth_stok_kod"))      # 'Fazeon X24F200' → 'X24F200' (Excel içe aktarmayla aynı)
        adet = _i(r.get("sth_miktar"))
        tutar, isk = _f(r.get("sth_tutar")), _f(r.get("sth_iskonto"))
        if tur == "satis":
            cariler.add(_kanonik(unvan))
            if tarih > son_fatura.get(_kanonik(unvan), ""):
                son_fatura[_kanonik(unvan)] = tarih
        else:
            iade_cari.add(kod)
        if not sku or adet <= 0:
            atlanan["adetsiz"] += 1
            continue
        if tur == "satis" and abs(tutar - isk) < 0.005:
            atlanan["bedelsiz"] += 1          # bedelsiz değişim: teknik servis yazıyor
            continue
        net_usd = usd_tutar(r, kurlar)
        if net_usd is None:
            atlanan["kursuz"] += 1
            continue
        oran = net_usd / (tutar - isk) if abs(tutar - isk) > 1e-9 else 0.0     # satır dövizi → $
        ad = " ".join(str(r.get("sto_isim") or "").split())
        if tur == "satis":
            satis[no].append({
                "tarih": tarih, "kanal": unvan, "sku": sku, "urun_adi": ad, "adet": adet,
                "birim_satis": round(net_usd / adet, 4),
                "birim_firma_destek": 0, "birim_ek_destek": 0,
                "siparis_no": no, "notlar": f"{NOT_ONEKI} · Cari kodu: {kod}",
            })
        else:
            from kayranpm.database import depo_kanonik
            iade[no].append({
                "tarih": tarih, "kanal": f"{kod} {unvan}".strip(), "sku": sku, "urun_adi": ad,
                "iade_adet": adet, "iade_brut": round(tutar * oran, 4), "iade_iskonto": round(isk * oran, 4),
                "iade_masraf": 0, "iade_net": round(net_usd, 4),
                "donem_bas": tarih, "donem_bit": tarih,
                "depo": depo_kanonik(r.get("giris_depo_adi") or "") or "İADE DEPO", "belge_no": no,
            })
    return {"satis": dict(satis), "iade": dict(iade), "atlanan": dict(atlanan),
            "son_fatura": son_fatura, "cariler": cariler, "iade_cari": iade_cari}


def siparis_kayitlari(siparisler, unvanlar=None, baslangic=BASLANGIC, kurlar=None, ad_harita=None):
    """Mikro'da açık (henüz faturası kesilmemiş) müşteri siparişleri → bekleyen satış kaydı (Ekim 2026,
    kullanıcı: "Mikro'ya sipariş girildiğinde programa da yansısın"). Sipariş Excel'inin yaptığını yapar:
    sipariş satış olarak görünür, fatura kesilince Mikro sipariş satırının teslim miktarı artar, kalan düşer;
    satış faturanın satırından gelir. Yalnız müşteri siparişi (sip_tip 0), iptal / kapalı değil, kalan > 0.
    Fiyat siparişin dövizinde ($ ise aynen; TL ise o günün $ kuruyla). Döner: ({sipariş no: [kayıt]}, atlanan)."""
    out, atlanan = defaultdict(list), defaultdict(int)
    unvanlar, ad_harita = unvanlar or {}, ad_harita or {}
    for r in siparisler or []:
        if _i(r.get("sip_tip"), -1) != 0 or r.get("sip_kapat_fl") in (True, 1, "1", "true"):
            continue
        tarih = _gun(r.get("sip_tarih"))
        kalan = _i(r.get("kalan", _f(r.get("sip_miktar")) - _f(r.get("sip_teslim_miktar"))))
        if not tarih or tarih < baslangic or kalan <= 0:
            continue
        sku = _sku_a(r.get("sip_stok_kod"))
        fiyat = _f(r.get("sip_b_fiyat"))
        if not sku or fiyat <= 0:
            atlanan["siparis_fiyatsiz"] += 1
            continue
        cins = _i(r.get("sip_doviz_cinsi"))
        if cins == 1:
            usd = fiyat
        elif cins == 0:
            kur = _onceki_kur(kurlar or {}, tarih)
            if not kur:
                atlanan["siparis_kursuz"] += 1
                continue
            usd = fiyat / kur
        else:
            atlanan["siparis_kursuz"] += 1      # € sipariş: siparişte kur yok
            continue
        kod = str(r.get("sip_musteri_kod") or "").strip()
        no = fatura_no(r.get("sip_evrakno_seri"), r.get("sip_evrakno_sira"))
        out[no].append({
            "tarih": tarih, "kanal": " ".join(str(unvanlar.get(kod) or "").split()) or kod, "sku": sku,
            "urun_adi": ad_harita.get(sku, ""), "adet": kalan, "birim_satis": round(usd, 4),
            "birim_firma_destek": 0, "birim_ek_destek": 0,
            "siparis_no": no, "notlar": f"{SIPARIS_NOT_ONEKI} · Cari kodu: {kod}",
        })
    return dict(out), dict(atlanan)


def _siparis_satiri_mi(s):
    return str(s.get("notlar") or "").startswith(SIPARIS_NOT_ONEKI + " ·")


def _imza_satis(kayitlar):
    return sorted((_gun(k.get("tarih")), " ".join(str(k.get("kanal") or "").split()), _sku_a(k.get("sku")),
                   _i(k.get("adet")), round(_f(k.get("birim_satis")), 2)) for k in kayitlar)


def _imza_iade(kayitlar):
    return sorted((_gun(k.get("tarih")), _sku_a(k.get("sku")), _i(k.get("iade_adet")),
                   round(_f(k.get("iade_net")), 2)) for k in kayitlar)


def _mikro_satis_mi(s, fatura_nolari):
    return str(s.get("siparis_no") or "").strip() in fatura_nolari


def _ts_satiri_mi(s):
    return str(s.get("notlar") or "").strip().upper().startswith(TS_NOT_ONEKI)


def _gun_farki(a, b):
    from datetime import date
    try:
        return abs((date.fromisoformat(_gun(a)) - date.fromisoformat(_gun(b))).days)
    except ValueError:
        return None


def elle_fatura_eslestir(elle, fatura_satirlari, gun=ESLESME_GUN, kullanilan=None):
    """Elle (Mikro dışı) satış satırlarını Mikro fatura satırlarına bağlar (denetim, Ekim 2026: faturadan
    sonra tarihli elle satır silinmiyor, satış iki kez sayılıyordu). Eşleşme: aynı firma (firma_kanonik) +
    aynı SKU (sku_anahtar) + aynı adet, tarih farkı en çok `gun` gün. Bir fatura satırı yalnız bir elle
    satırı karşılar (kullanilan: tüketilen fatura satırlarının id()'leri; çağrılar arasında paylaşılır).
    Elle satırlar tarih sırasıyla; her biri en yakın tarihli boştaki fatura satırını alır.
    Döner: [(elle satır, fatura satırı)]."""
    kullanilan = set() if kullanilan is None else kullanilan
    havuz = defaultdict(list)
    for k in fatura_satirlari or []:
        havuz[(_kanonik(k.get("kanal")), _sku_a(k.get("sku")), _i(k.get("adet")))].append(k)
    out = []
    for s in sorted(elle or [], key=lambda x: (_gun(x.get("tarih")), str(x.get("id") or ""))):
        adaylar = []
        for k in havuz.get((_kanonik(s.get("kanal")), _sku_a(s.get("sku")), _i(s.get("adet"))), []):
            fark = _gun_farki(s.get("tarih"), k.get("tarih"))
            if id(k) not in kullanilan and fark is not None and fark <= gun:
                adaylar.append((fark, _gun(k.get("tarih")), str(k.get("siparis_no") or ""), k))
        if adaylar:
            k = min(adaylar, key=lambda a: a[:3])[3]
            kullanilan.add(id(k))
            out.append((s, k))
    return out


# ── plan ────────────────────────────────────────────────────────────
def plan_yap(mikro_satirlar, satislar, iadeler, baslangic=BASLANGIC, pacal_fn=None, basliklar=None,
             siparisler=None, unvanlar=None, ad_harita=None):
    """Yazmadan önce ne değişecek. satislar / iadeler: başlangıçtan sonraki mevcut kayıtlar (id'li).
    basliklar: Mikro satış faturası başlıkları [{fatura_no, tarih, kanal, tutar, doviz}] — ürün satırı
    olmayan (hizmet / masraf / fark) faturaları göstermek için. pacal_fn(sku) → $ maliyet.
    siparisler: mikro_siparis satırları (unvanlar: {cari kodu: ünvan}) — açık olanlar bekleyen satış olur,
    kapanan / faturalanan siparişin satırı silinir (siparis_kayitlari).
    Döner: {yuk: mikro_esitle_uygula girdisi, ozet: aylık önce/sonra, ...}."""
    mk = mikro_kayitlari(mikro_satirlar, baslangic)
    sip, sip_atlanan = siparis_kayitlari(siparisler, unvanlar, baslangic, kur_haritasi(mikro_satirlar), ad_harita)
    for k, v in sip_atlanan.items():
        mk["atlanan"][k] = mk["atlanan"].get(k, 0) + v
    satislar = [s for s in satislar or [] if _gun(s.get("tarih")) >= baslangic]
    iadeler = [r for r in iadeler or [] if _gun(r.get("tarih")) >= baslangic]
    mikro_nolari = set(mk["satis"]) | {str(b.get("fatura_no") or "") for b in basliklar or []}
    satirli_nolar = set(mk["satis"])

    # Mevcut Mikro kaynaklı satış satırları, fatura fatura (açık sipariş satırları sipariş sipariş)
    mevcut_fatura = defaultdict(list)
    mevcut_siparis = set()
    for s in satislar:
        if _siparis_satiri_mi(s):
            mevcut_siparis.add(str(s.get("siparis_no") or "").strip())
            mevcut_fatura[str(s.get("siparis_no") or "").strip()].append(s)
        elif _mikro_satis_mi(s, mikro_nolari) or str(s.get("notlar") or "").startswith(NOT_ONEKI + " ·"):
            mevcut_fatura[str(s.get("siparis_no") or "").strip()].append(s)

    # MİKRO ESAS (kullanıcı, 21.10.2026: "Mikro'daki datalar her zaman daha doğrudur … muhasebe, vergi beyanları
    # hepsi Mikro'ya göre"): başlangıçtan sonra Mikro faturası ya da açık Mikro siparişi olmayan HER satış satırı
    # kaldırılır (elle sipariş, teknik servis / 2.el satışı dahil; arşive yazılarak). Canlı 21.10: EERA'nın Mikro'da
    # olmayan iki elle siparişi (304 bin $), Mikro'da faturalı teknik servis satışlarının ikinci kopyası, yanlış
    # firmaya girilmiş TEKNORYA satırı. Rapor için elle satırın eşleştiği fatura da gösterilir (elle_fatura_eslestir).
    sil_satis = [s for s in satislar if str(s.get("siparis_no") or "").strip() not in mevcut_fatura]
    fatura_satirlari = [k for _no, ks in sorted(mk["satis"].items()) for k in ks]
    eslesen = elle_fatura_eslestir(sil_satis, fatura_satirlari)

    # Maliyet: aynı faturanın önceki kaydı → değiştirilen eski satırlar (firma + SKU) → paçal
    onceki = defaultdict(list)
    for no, ks in mevcut_fatura.items():
        for s in ks:
            onceki[(no, _sku_a(s.get("sku")))].append(s)
    eski = defaultdict(lambda: [0.0, 0])
    for s in sil_satis:
        e = eski[(_kanonik(s.get("kanal")), _sku_a(s.get("sku")))]
        e[0] += _f(s.get("birim_maliyet")) * _i(s.get("adet"))
        e[1] += _i(s.get("adet"))

    def _maliyet(k):
        o = onceki.get((k["siparis_no"], _sku_a(k["sku"])))
        if o:
            ad = sum(_i(x.get("adet")) for x in o)
            if ad:
                return sum(_f(x.get("birim_maliyet")) * _i(x.get("adet")) for x in o) / ad
        e = eski.get((_kanonik(k["kanal"]), _sku_a(k["sku"])))
        if e and e[1]:
            return e[0] / e[1]
        return _f(pacal_fn(k["sku"])) if pacal_fn else 0.0

    fatura_nolar, ekle_satis = [], []
    gruplar = dict(mk["satis"])
    gruplar.update({no: ks for no, ks in sip.items() if no not in gruplar})
    for no, ks in sorted(gruplar.items()):
        if _imza_satis(ks) == _imza_satis(mevcut_fatura.get(no, [])):
            continue                      # değişmemiş fatura: dokunulmaz (maliyet de korunur)
        if no in mevcut_fatura:
            fatura_nolar.append(no)
        for k in ks:
            ekle_satis.append(dict(k, birim_maliyet=round(_maliyet(k), 6)))
    # Mikro'da artık olmayan (iptal) faturalar: başlıklarda da yoksa sil. Başlığı olup satırı olmayan
    # faturaya DOKUNULMAZ (satır okunamamış olabilir; gerçek satış silinmesin).
    # Faturalanan / kapanan / iptal edilen siparişin bekleyen satırı silinir (satış faturadan gelir).
    for no in sorted(mevcut_fatura):
        if no in mevcut_siparis:
            if no not in sip and no not in fatura_nolar:
                fatura_nolar.append(no)
        elif no not in satirli_nolar and no not in mikro_nolari and no.startswith(_seri_onek(mikro_nolari)):
            fatura_nolar.append(no)

    # İadeler
    mevcut_iade = defaultdict(list)
    sil_iade = []
    for r in iadeler:
        kaynak = str(r.get("kaynak") or "")
        if kaynak == "mikro":
            mevcut_iade[str(r.get("belge_no") or "")].append(r)
        elif kaynak == "excel" and str(r.get("kanal") or "").split(" ")[0] in mk["iade_cari"]:
            sil_iade.append(r)
    iade_belgeler, ekle_iade = [], []
    for no, ks in sorted(mk["iade"].items()):
        if _imza_iade(ks) == _imza_iade(mevcut_iade.get(no, [])):
            continue
        if no in mevcut_iade:
            iade_belgeler.append(no)
        ekle_iade.extend(ks)
    for no in sorted(mevcut_iade):
        if no not in mk["iade"]:
            iade_belgeler.append(no)

    silinen_fatura_satir = [s for no in fatura_nolar for s in mevcut_fatura.get(no, [])]
    silinen_iade = sil_iade + [r for no in iade_belgeler for r in mevcut_iade.get(no, [])]
    ozet = aylik_ozet(satislar, silinen_fatura_satir + sil_satis, ekle_satis,
                      iadeler, silinen_iade, ekle_iade)
    hizmet = sorted((b for b in basliklar or [] if str(b.get("fatura_no")) not in satirli_nolar
                     and _gun(b.get("tarih")) >= baslangic), key=lambda b: (_gun(b.get("tarih")), b.get("fatura_no")))
    yuk = {"baslangic": baslangic,
           "sil_satis_id": [s["id"] for s in sil_satis if s.get("id") is not None],
           "fatura_nolar": fatura_nolar, "ekle_satis": ekle_satis,
           "sil_iade_id": [r["id"] for r in sil_iade if r.get("id") is not None],
           "iade_belgeler": iade_belgeler, "ekle_iade": ekle_iade}
    return {"yuk": yuk, "ozet": ozet, "hizmet_faturalari": hizmet, "atlanan": mk["atlanan"],
            "silinecek_satir": len(silinen_fatura_satir) + len(sil_satis), "mevcut_satir": len(satislar),
            "degisiklik_var": bool(yuk["sil_satis_id"] or fatura_nolar or ekle_satis
                                   or yuk["sil_iade_id"] or iade_belgeler or ekle_iade),
            "sil_satis_kanal": _kanal_sayim(sil_satis),
            "elle_eslesen": [{"id": s.get("id"), "tarih": _gun(s.get("tarih")), "kanal": s.get("kanal"),
                              "sku": s.get("sku"), "adet": _i(s.get("adet")),
                              "birim_satis": _f(s.get("birim_satis")), "fatura_no": k.get("siparis_no"),
                              "fatura_tarihi": k.get("tarih"), "fatura_birim": k.get("birim_satis")}
                             for s, k in eslesen],
            "yeni_fatura": len({k["siparis_no"] for k in ekle_satis if not _siparis_satiri_mi(k)}),
            "acik_siparis": len(sip), "acik_siparis_adet": sum(_i(k["adet"]) for ks in sip.values() for k in ks)}


# ── Okuma güvenliği (21.10.2026 olayı) ─────────────────────────────
# Saatlik GitHub işi Mikro satırlarını, aktarıcı aynı tabloya yazarken SIRASIZ sayfalarla okudu: bazı satırlar
# iki kez, bazıları hiç okunmadı; plan 1.639 satırı silip 1.684'ünü (yarısı kopya) yazdı (arşivden geri
# yüklendi). Üç kural: okumalar birincil anahtar sırasıyla; kopya anahtar görülürse okuma reddedilir; aktarıcı
# turu sürüyorsa otomatik eşitleme o turu atlar; otomatik plan mevcut satırların çoğunu silmek isterse yazmaz.
AKTARIM_SURUYOR_SN = 150          # son durum yazımından bu kadar saniye geçmediyse tur sürüyor sayılır
OTOMATIK_SILME_SINIRI = 0.25      # otomatik turda silinecek satır / mevcut satır üst sınırı
OTOMATIK_SILME_TABAN = 100        # küçük tablolarda oranın yanıltmaması için alt sınır


class OkumaTutarsiz(RuntimeError):
    """Mikro kopyası okunurken aynı kayıt iki kez geldi (okuma sırasında tablo değişti)."""


def kopyasiz(satirlar, anahtar):
    """Aynı anahtar iki kez geldiyse OkumaTutarsiz; yoksa satırları aynen döndürür."""
    gorulen = set()
    for r in satirlar:
        k = tuple(r.get(a) for a in anahtar) if isinstance(anahtar, (tuple, list)) else r.get(anahtar)
        if k in gorulen:
            raise OkumaTutarsiz(f"kopya kayıt: {k}")
        gorulen.add(k)
    return satirlar


def aktarim_suruyor_mu(guncellemeler, simdi):
    """guncellemeler: mikro_senk_durum.guncelleme değerleri (ISO). En yenisi AKTARIM_SURUYOR_SN'den yeniyse True."""
    from datetime import datetime
    en_yeni = None
    for g in guncellemeler:
        try:
            t = datetime.fromisoformat(str(g).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        en_yeni = t if en_yeni is None or t > en_yeni else en_yeni
    return en_yeni is not None and (simdi - en_yeni).total_seconds() < AKTARIM_SURUYOR_SN


def aktarim_suruyor():
    """Aktarıcı şu an Supabase'e yazıyor olabilir mi (otomatik eşitlemeler bu turu atlar). Okunamazsa False."""
    from datetime import datetime, timezone
    try:
        r = _cli().table("mikro_senk_durum").select("guncelleme").execute().data or []
        return aktarim_suruyor_mu([x.get("guncelleme") for x in r], datetime.now(timezone.utc))
    except Exception:  # noqa: BLE001
        return False


def otomatik_guvenli_mi(plan):
    """Otomatik turda plan, mevcut satış satırlarının büyük kısmını silmek istiyorsa yazılmaz (okuma hatası
    belirtisi). İlk onay (kullanıcı karşılaştırmayı görüyor) bu kontrolden geçmez."""
    sil = int(plan.get("silinecek_satir") or 0)
    mevcut = int(plan.get("mevcut_satir") or 0)
    return sil <= max(OTOMATIK_SILME_TABAN, OTOMATIK_SILME_SINIRI * mevcut)


def _seri_onek(nolar):
    """Mikro fatura serileri ('G5F26-'): iptal temizliği yalnız bu biçimdeki numaralara dokunsun."""
    seriler = {n.split("-")[0] + "-" for n in nolar if "-" in n}
    return tuple(sorted(seriler)) or ("\0",)


def _kanal_sayim(satirlar):
    d = defaultdict(lambda: [0, 0])
    for s in satirlar:
        d[" ".join(str(s.get("kanal") or "").split())][0] += 1
        d[" ".join(str(s.get("kanal") or "").split())][1] += _i(s.get("adet"))
    return sorted(([k, v[0], v[1]] for k, v in d.items()), key=lambda x: -x[2])


def aylik_ozet(satislar, silinen, eklenen, iadeler=(), silinen_iade=(), eklenen_iade=()):
    """Ay ay önce ↔ sonra: satış adedi, ciro ($), kâr ($), iade adedi, iade ($)."""
    def _top(rows):
        d = defaultdict(lambda: [0, 0.0, 0.0])
        for s in rows:
            a = d[_gun(s.get("tarih"))[:7]]
            ad = _i(s.get("adet"))
            a[0] += ad
            a[1] += ad * _f(s.get("birim_satis"))
            a[2] += ad * (_f(s.get("birim_satis")) - _f(s.get("birim_maliyet"))
                          + _f(s.get("birim_firma_destek")) + _f(s.get("birim_ek_destek")))
        return d

    def _itop(rows):
        d = defaultdict(lambda: [0, 0.0])
        for r in rows:
            a = d[_gun(r.get("tarih"))[:7]]
            a[0] += _i(r.get("iade_adet"))
            a[1] += _f(r.get("iade_net"))
        return d

    sil_id = {id(s) for s in silinen}
    sonra = [s for s in satislar if id(s) not in sil_id] + list(eklenen)
    isil = {id(r) for r in silinen_iade}
    isonra = [r for r in iadeler if id(r) not in isil] + list(eklenen_iade)
    o, s, io, isn = _top(satislar), _top(sonra), _itop(iadeler), _itop(isonra)
    aylar = sorted(set(o) | set(s) | set(io) | set(isn))
    return [{"ay": a, "adet_once": o[a][0], "adet_sonra": s[a][0], "ciro_once": round(o[a][1], 2),
             "ciro_sonra": round(s[a][1], 2), "kar_once": round(o[a][2], 2), "kar_sonra": round(s[a][2], 2),
             "iade_adet_once": io[a][0], "iade_adet_sonra": isn[a][0],
             "iade_once": round(io[a][1], 2), "iade_sonra": round(isn[a][1], 2)} for a in aylar]


# ── veritabanı ──────────────────────────────────────────────────────
def _cli():
    from satis.database import _get_client
    return _get_client()


def durum():
    """{acik, baslangic, son_calisma, son_ozet}; tablo yoksa None."""
    try:
        r = _cli().table("mikro_esitleme_durum").select("*").eq("id", 1).execute()
        return (getattr(r, "data", None) or [None])[0]
    except Exception:  # noqa: BLE001
        return None


def acik_mi():
    """Satış eşitlemesi açık mı. Açıksa satış dökümü ve iade Excel'i Dosya kapısında kaydedilmez, takvim
    hatırlatması çıkmaz. Durum okunamazsa kapalı sayılır (yükleme açık kalır)."""
    return bool((durum() or {}).get("acik"))


SAYFA = 1000


def sayfali_oku(sorgu, anahtar):
    """sorgu() → süzgeçli ve SIRALI yeni sorgu. Sayfaları .range() ile kendisi okur (oto-sayfalamaya güvenmez:
    21.10.2026'da canlı süreç shared.audit'in eski hâlini bellekte tuttuğu için 2. sayfada süzgeç düştü, aynı fatura
    iki kez okundu ve satış eşitlemesi 16:04'ten itibaren 'kopya kayıt' korumasıyla yazmadı). Kopya varsa
    OkumaTutarsiz (kopyasiz)."""
    out, bas = [], 0
    while True:
        parca = sorgu().range(bas, bas + SAYFA - 1).execute().data or []
        out += parca
        if len(parca) < SAYFA:
            return kopyasiz(out, anahtar)
        bas += SAYFA


def veri_oku(baslangic=BASLANGIC):
    """(mikro satırları, mevcut satışlar, mevcut iadeler, Mikro satış faturası başlıkları)."""
    from datetime import date, timedelta
    cli = _cli()
    # 15 gün önceden: başlangıcın ilk günlerindeki TL faturaları için önceki günlerin $ kuru lazım
    once = (date.fromisoformat(baslangic[:10]) - timedelta(days=15)).isoformat()
    mikro = sayfali_oku(lambda: cli.table("mikro_satis_satir").select("*").gte("cha_tarihi", once)
                        .order("sth_guid"), "sth_guid")
    satislar = sayfali_oku(lambda: cli.table("satislar").select("id,tarih,kanal,sku,adet,birim_satis,birim_maliyet,"
                                                                "birim_firma_destek,birim_ek_destek,siparis_no,notlar")
                           .gte("tarih", baslangic).order("id"), "id")
    iadeler = sayfali_oku(lambda: cli.table("iadeler").select("*").gte("tarih", baslangic).order("id"), "id")
    bas = sayfali_oku(lambda: cli.table("mikro_fatura").select("cha_guid,cha_evrakno_seri,cha_evrakno_sira,"
                                                               "cha_tarihi,cha_kod,cha_meblag,cha_d_cins")
                      .eq("cha_evrak_tip", SATIS_TIP).eq("cha_normal_iade", 0).gte("cha_tarihi", baslangic)
                      .order("cha_guid"), "cha_guid")
    unvan = {str(c.get("cari_kod") or ""): c.get("cari_unvan1") or ""
             for c in (cli.table("mikro_cari_bakiye").select("cari_kod,cari_unvan1").execute().data or [])}
    basliklar = [{"fatura_no": fatura_no(b.get("cha_evrakno_seri"), b.get("cha_evrakno_sira")),
                  "tarih": _gun(b.get("cha_tarihi")), "kanal": unvan.get(str(b.get("cha_kod") or ""), b.get("cha_kod")),
                  "cari_kod": b.get("cha_kod"), "tutar": _f(b.get("cha_meblag")),
                  "doviz": {0: "TL", 1: "$", 2: "€"}.get(_i(b.get("cha_d_cins")), "?")} for b in bas]
    return mikro, satislar, iadeler, basliklar


def siparis_oku(baslangic=BASLANGIC):
    """(Mikro müşteri sipariş satırları başlangıçtan beri, {cari kodu: ünvan}). Tablo yoksa ([], {})."""
    cli = _cli()
    try:
        sip = sayfali_oku(lambda: cli.table("mikro_siparis").select("*").eq("sip_tip", 0)
                          .gte("sip_tarih", baslangic).order("sip_guid"), "sip_guid")
    except OkumaTutarsiz:
        raise
    except Exception:  # noqa: BLE001
        return [], {}
    unvan = {str(c.get("cari_kod") or ""): c.get("cari_unvan1") or ""
             for c in (cli.table("mikro_cari_bakiye").select("cari_kod,cari_unvan1").execute().data or [])}
    return sip, unvan


def plan_hazirla(baslangic=BASLANGIC):
    from satis.database import get_pacal_map, pacal_bul
    from shared.ana_veri import get_urun_ad_haritasi
    mikro, satislar, iadeler, basliklar = veri_oku(baslangic)
    siparisler, unvanlar = siparis_oku(baslangic)
    pacal = get_pacal_map()
    return plan_yap(mikro, satislar, iadeler, baslangic, pacal_fn=lambda s: pacal_bul(pacal, s),
                    basliklar=basliklar, siparisler=siparisler, unvanlar=unvanlar,
                    ad_harita=get_urun_ad_haritasi())


def uygula(plan):
    """Planı tek işlemde yazar. Döner: (ok, mesaj, sayılar)."""
    yuk = dict(plan["yuk"], ozet={"aylar": plan["ozet"], "atlanan": plan.get("atlanan", {})})
    try:
        r = _cli().rpc("mikro_esitle_uygula", {"p": yuk}).execute()
        sonuc = getattr(r, "data", None) or {}
    except Exception as e:  # noqa: BLE001
        return False, f"Eşitleme yazılamadı, hiçbir şey değişmedi: {type(e).__name__}: {str(e)[:160]}", {}
    try:
        from satis.database import _temizle
        _temizle()
    except Exception:  # noqa: BLE001
        pass
    return True, "Mikro eşitlemesi yazıldı.", sonuc


def ac(kullanici):
    _cli().table("mikro_esitleme_durum").update({"acik": True, "acan": str(kullanici or "")}).eq("id", 1).execute()


def _son_aktarim():
    """Satış satırlarının son çekimi; sipariş tablosu daha yeni çekildiyse o (sipariş girilince de çalışsın).
    Satış satırı hiç gelmediyse boş (eşitleme çalışmaz)."""
    r = (_cli().table("mikro_senk_durum").select("tablo,son_cekim")
         .in_("tablo", ["mikro_satis_satir", "mikro_siparis"]).execute().data or [])
    son = {x.get("tablo"): str(x.get("son_cekim") or "") for x in r}
    if not son.get("mikro_satis_satir"):
        return ""
    return max(son.values())


def otomatik():
    """Açıksa ve aktarıcı son eşitlemeden sonra yeni veri getirdiyse eşitler. Hata fırlatmaz.
    Döner: sonuç sayıları ya da None (çalışmadı)."""
    try:
        d = durum()
        if not d or not d.get("acik"):
            return None
        son = _son_aktarim()
        if not son or (d.get("son_calisma") and str(d.get("son_calisma")) >= son):
            return None
        if aktarim_suruyor():
            return None                   # aktarıcı yazıyor: tutarlı okunamaz, sonraki turda
        plan = plan_hazirla(str(d.get("baslangic") or BASLANGIC)[:10])
        if not otomatik_guvenli_mi(plan):
            from shared.kayit import sessiz
            sessiz("satis.mikro_esitle.otomatik", RuntimeError(
                f"plan {plan.get('silinecek_satir')} / {plan.get('mevcut_satir')} satır silmek istedi; yazılmadı"))
            return None
        ok, _m, sonuc = uygula(plan)
        return sonuc if ok else None
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("satis.mikro_esitle.otomatik", e)
        return None



def _aktarici_yolu():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent / "araclar" / "mikro_aktarici" / "mikro_kayran.py"


def aktarici_ozeti():
    """Depodaki aktarıcı kodunun sha256 özeti; okunamazsa ''."""
    import hashlib
    try:
        return hashlib.sha256(_aktarici_yolu().read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    except Exception:  # noqa: BLE001
        return ""


def aktarici_yayinda_mi(ozet):
    """Supabase'teki sürüm bu özet mi."""
    try:
        r = _cli().table("mikro_aktarici_surum").select("sha256").eq("id", 1).execute().data or []
        return bool(r) and r[0].get("sha256") == ozet
    except Exception:  # noqa: BLE001
        return False


def aktarici_yayinla():
    """Depodaki aktarıcı kodunu Supabase'e koyar (mikro_aktarici_surum); sunucudaki aktarıcı sürüm farklıysa
    kendini günceller (kullanıcı: "sunucuya bir daha dosya taşımayayım", Ekim 2026). Aynıysa yazmaz.
    Döner: yayınlandı ya da zaten yayındaysa True. Hata fırlatmaz."""
    try:
        kod = _aktarici_yolu().read_text(encoding="utf-8")
        ozet = aktarici_ozeti()
        if not ozet:
            return False
        if aktarici_yayinda_mi(ozet):
            return True
        # yayin: tablonun DEFAULT now()'ı yalnız ilk eklemede çalışır; upsert'te açıkça yazılmazsa ilk yayının
        # zamanında kalıyordu (Ekim 2026).
        from datetime import datetime, timezone
        _cli().table("mikro_aktarici_surum").upsert(
            {"id": 1, "kod": kod, "sha256": ozet, "yayin": datetime.now(timezone.utc).isoformat()}).execute()
        return True
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("satis.mikro_esitle.aktarici_yayinla", e)
        return False
