# -*- coding: utf-8 -*-
"""Toplam Aktifler · Mikro defterinden ek kalemler ve satış maliyeti (Ekim 2026). Ekran: mikro_aktif_ekran.py.

Kullanıcı: "Toplam aktifler upload olmadan Mikro'dan; kargo, depolama vs. Mikro'dan bulabileceğin masrafları da
düşsün" — seçenek A (21.10.2026): kargo / lojistik, depolama, kredi kartı komisyonu ve teknik servis düşülür,
satış destek bedelleri düşülmez. "Aynı masraf farklı şekilde programa yükleniyorsa 2 defa yüklenmesin."

Toplam Aktifler'in eski kalemleri (stok, ithalat ödenen, banka, çek, cari) zaten Mikro'dan geliyor. Bu modül
iki şey ekler:

1) Defter kalemleri — Mikro'nun muhasebe bakiyelerinden (mikro_muhasebe_ay, kümülatif borç − alacak, TL),
   Toplam Aktifler'de hiç olmayanlar: kasa, iş / personel avansları, verilen depozitolar, peşin ödenen vergi
   (artı); net KDV, ödenecek vergi ve SGK, gider tahakkukları, personele / diğer borçlar, kredi ve kart
   borçları, yurt içi satıcılar (eksi). TL bakiye ekranda o günün kuruyla dolara çevrilir.
   İKİ KEZ SAYILMASIN: Toplam Aktifler'in kendi kalemlerinin hesapları (KAPSANAN: banka 102, çek 103,
   cari 120 / 340, ithalat avansı 320.50, stok 153) hiçbir kaleme girmez; testte denetlenir.
   159 (verilen sipariş avansları) 22.10.2026'dan beri GİRER ("Antrepodaki mal ve sipariş avansları"; kullanıcı:
   "159'u doğrudan ekle"): antrepoda bekleyen 57.283 adet (FOB 1.171.793 $) Mikro depo stoğunda yok, yalnız bir
   kısmı 320.50 avansında; antrepo dönemi ödemeleri ve antrepodaki konteynerlerin masrafı 159.02'de birikiyor
   (24,3 milyon TL). Eski kural ("159'da yalnız teslim alınmış dosyaların paçalda olan masrafı var") bu malı
   aktiflerden düşürüyordu. Teslim alınan dosyanın masrafı 159'dan 153'e aktarılınca 159'dan düşer.
   KDV (kullanıcı, 21.10: "gümrükte %20 KDV'yi peşin ödüyoruz, göstermezsek eksik olur mu — sen belirle"):
   gümrükte ödenen KDV Mikro'da 191 indirilecek KDV'dedir; "KDV" kalemi 190 + 191 − 391 netidir, yani peşin
   ödenen KDV satışta tahsil edilecek KDV'den mahsup edilmiş olarak sayılır. Bu yüzden açıkken stok × 1,00
   (stok_carpani): eski × 1,20 stoğun gelecekteki satış KDV'sini de varlık sayıyordu, o KDV devlete aittir.
   Aynı şey elle de girilmişse (manuel kalem açıklaması bir defter kalemiyle eşleşiyorsa) manuel kalem
   toplama girmez, ekranda "Mikro'dan geliyor, sayılmadı" diye görünür.

2) Satış maliyeti — stoğu satarken çıkacak masraf: son 12 bitmiş ayda (Aralık hariç: yıl sonu kapanış fişi
   gider hesaplarını sıfırlıyor) kargo / nakliye / lojistik, depolama, kredi kartı komisyonu ve teknik servis
   giderleri ÷ net satış. Oran, Toplam Aktifler'e giren stok değerine (× 1,20) uygulanır, ayrı satır olarak
   düşülür. Hesaplar ada göre bulunur (SATIS_MALIYETI_KELIME); satış destek bedelleri (760.04.019–023) hariç.
   Geçmiş masraf (ödenmemişse yurt içi satıcı / tahakkuk kaleminde) ile bu oran çakışmaz: oran eldeki stoğun
   İLERİDE satılırken doğuracağı masraf. Paçal ithalat masraflarını (navlun, ardiye, gümrük) zaten içerir;
   bu oran yalnız satış tarafındaki masraf.

İlk açılışta "şimdi ↔ Mikro ile" karşılaştırması ve onay (Toplam Aktifler üstünde, bir kez); sonra her aktarım
turunda otomatik(). Sonuç aktif_excel_verileri "mikro_defter" kaydına yazılır; Toplam Aktifler onu okur.
"""
from collections import defaultdict

DURUM_ANAHTAR = "mikro_aktif_durum"
KAYIT_TIPI = "mikro_defter"
KAYNAK_ADI = "Mikro"
SAYFA = 1000
KURUS = 0.005

# Toplam Aktifler'in kendi kalemlerinin hesapları — defter kalemlerine GİRMEZ (iki kez sayılmasın)
KAPSANAN = ("102", "103", "120", "340", "153", "320.50")

# (ad, hesap önekleri, hariç önekler) — tutar işaretli: borç bakiyesi artı (varlık), alacak bakiyesi eksi (borç)
DEFTER_KALEMLERI = (
    ("İş ve personel avansları", ("195", "196"), ()),
    ("Verilen depozito ve teminatlar", ("226",), ()),
    ("Peşin ödenen vergiler", ("193",), ()),
    ("Antrepodaki mal ve sipariş avansları", ("159",), ()),
    ("KDV (indirilecek − hesaplanan)", ("190", "191", "391"), ()),
    ("Ödenecek vergi ve fonlar", ("360",), ()),
    ("Ödenecek SGK", ("361",), ()),
    ("Gider tahakkukları", ("381",), ()),
    ("Personele ve diğer borçlar", ("335", "336"), ()),
    ("Kredi ve kart borçları", ("300", "303", "309"), ()),
    ("Yurt içi satıcılar", ("320",), ("320.50",)),
)
# Kasa (100) hiçbir kaleme girmez (kullanıcı, 23.10.2026: "kasa kaldırılacak, başlığı hiç olmasın, tutar bir yere
# yansımasın"). DEFTER_KALEMLERI'nde 100 yok; hiçbir önek 100'ü tutmaz (testte denetlenir).
HARIC_HESAP = ("100",)

# "Evrakı gelmemiş ithalat işlemleri" ve "Yönetim diğer borçlar" (kullanıcı, 23.10.2026; Mikro'da cari 320.99.001 /
# .002, genel amaçlı virman dekontuyla). Toplam Aktifler'e CARİ bakiyeden girer (kayranacc.mikro_muhasebe.
# ozel_cari_ozeti): biri muhasebe kodsuz açıldı, muhasebe tarafı gecikebilir. Burada iki kez sayılmasınlar diye
# muhasebe tarafında hiçbir kaleme girmezler: 320.99 öneki ve hesap planında adı bu adlarla aynı olan hesaplar.
OZEL_HESAPLAR = ("Evrakı gelmemiş ithalat işlemleri", "Yönetim diğer borçlar")
OZEL_ONEK = ("320.99",)

# Manuel kalem bu kelimelerden birini taşıyorsa aynı şey Mikro'dan geliyor sayılır (kalem adı → kelimeler)
MANUEL_KELIME = {
    "İş ve personel avansları": ("AVANS",),
    "Verilen depozito ve teminatlar": ("DEPOZİTO", "TEMİNAT"),
    "Peşin ödenen vergiler": ("PEŞİN VERGİ", "GEÇİCİ VERGİ"),
    "Antrepodaki mal ve sipariş avansları": ("ANTREPO", "SİPARİŞ AVANS"),
    "KDV (indirilecek − hesaplanan)": ("KDV",),
    "Ödenecek vergi ve fonlar": ("VERGİ", "STOPAJ", "MUHTASAR"),
    "Ödenecek SGK": ("SGK", "SSK", "PRİM"),
    "Gider tahakkukları": ("TAHAKKUK",),
    "Personele ve diğer borçlar": ("MAAŞ", "PERSONEL"),
    "Kredi ve kart borçları": ("KREDİ", "KART BORC", "KART BORÇ"),
    "Yurt içi satıcılar": ("KARGO", "NAKLİYE", "LOJİSTİK", "DEPOLAMA", "DEPO KİRA", "GÜMRÜK MÜŞAVİR"),
}
SATIS_MALIYETI_KELIME = ("KARGO", "NAKLİYE", "LOJİSTİK", "DEPOLAMA", "KREDİ KARTI", "TEKNİK SERVİS")
SATIS_MALIYETI_HESAP = ("760.", "770.", "780.")
SATIS_DESTEK = ("760.04.019", "760.04.020", "760.04.021", "760.04.022", "760.04.023")


def _f(v, d=0.0):
    try:
        x = float(v)
        return x if x == x else d
    except (TypeError, ValueError):
        return d


def _s(v):
    return str(v or "").strip()


def _buyuk(s):
    """Karşılaştırma biçimi (tr_buyuk + NFC). Kelimeler de aynı biçimden geçer: tr_buyuk İ'yi düz I'ya indirdiği için
    ham "LOJİSTİK" kelimesi hesap adıyla eşleşmiyor, lojistik gideri oranın dışında kalıyordu."""
    import unicodedata
    from shared.utils import tr_buyuk
    return unicodedata.normalize("NFC", tr_buyuk(unicodedata.normalize("NFC", _s(s))))


def stok_carpani(acik):
    """Toplam Aktifler'e giren stok çarpanı: defter kalemleri açıkken 1,00 (bilanço: stok maliyetle, KDV ayrı
    kalemde), kapalıyken eski 1,20 (KDV dahil)."""
    return 1.0 if acik else 1.20


def onek_uyar(kod, onekler):
    """'320' → '320' ve '320.01.001'; '32' gibi yarım önek '320'yi tutmaz."""
    return any(kod == o or kod.startswith(o + ".") for o in onekler)


def _ad_anahtar(ad):
    from shared.utils import normalize_tr
    return " ".join(normalize_tr(ad).split())


def ozel_kodlar(hesap_adlari):
    """{hesap kodu: OZEL_HESAPLAR adı} — hesap planında adı birebir (Türkçe harf / büyük-küçük / boşluk farkı
    gözetmeden) tutan hesaplar."""
    hedef = {_ad_anahtar(a): a for a in OZEL_HESAPLAR}
    return {_s(k): hedef[_ad_anahtar(ad)] for k, ad in (hesap_adlari or {}).items() if _ad_anahtar(ad) in hedef}


def kalem_bul(kod, ozel=None):
    if onek_uyar(kod, HARIC_HESAP + OZEL_ONEK + tuple(ozel or ())):
        return None
    for ad, onek, haric in DEFTER_KALEMLERI:
        if onek_uyar(kod, onek) and not onek_uyar(kod, haric):
            return ad
    return None


def defter_kalemleri(satirlar, hesap_adlari=None):
    """mikro_muhasebe_ay satırları → [{ad, tl, hesaplar {kod: tl}}] (kümülatif bakiye, TL; DEFTER_KALEMLERI sırası).
    hesap_adlari: {kod: ad} — adı OZEL_HESAPLAR'dan biri olan hesap sayılmaz (cari bakiyeden gelir)."""
    bak = defaultdict(float)
    for r in satirlar or []:
        kod = _s(r.get("hesap_kod"))
        if kod:
            bak[kod] += _f(r.get("borc")) - _f(r.get("alacak"))
    ozel = ozel_kodlar(hesap_adlari)
    out = {ad: {"ad": ad, "tl": 0.0, "hesaplar": {}} for ad, _o, _h in DEFTER_KALEMLERI}
    for kod, v in sorted(bak.items()):
        ad = kalem_bul(kod, ozel)
        if ad and abs(v) >= KURUS:
            out[ad]["tl"] += v
            out[ad]["hesaplar"][kod] = round(v, 2)
    return [dict(k, tl=round(k["tl"], 2)) for k in out.values()]


def _ay_no(yil, ay):
    return int(yil) * 12 + int(ay) - 1


def satis_maliyeti_orani(satirlar, hesap_adlari, bugun):
    """Son 12 bitmiş ay (Aralık hariç). Döner: {oran, satis_tl, masraf_tl, kalemler [{kod, ad, tl}], donem}."""
    son = _ay_no(bugun.year, bugun.month) - 1             # içinde bulunulan ay yarım: alınmaz
    ilk = son - 11
    satis = 0.0
    masraf = defaultdict(float)
    aylar = set()
    for r in satirlar or []:
        n = _ay_no(_f(r.get("yil")), _f(r.get("ay")))
        if not (ilk <= n <= son) or int(_f(r.get("ay"))) == 12:
            continue
        kod = _s(r.get("hesap_kod"))
        b, a = _f(r.get("borc")), _f(r.get("alacak"))
        if onek_uyar(kod, ("600", "601", "602")):
            satis += a - b
            aylar.add(n)
        elif onek_uyar(kod, ("610", "611", "612")):
            satis -= b - a
        elif kod.startswith(SATIS_MALIYETI_HESAP) and kod not in SATIS_DESTEK:
            ad = _buyuk(hesap_adlari.get(kod))
            if any(_buyuk(k) in ad for k in SATIS_MALIYETI_KELIME):
                masraf[kod] += b - a
    top = sum(masraf.values())
    donem = ""
    if aylar:
        a0, a1 = min(aylar), max(aylar)
        donem = f"{a0 % 12 + 1:02d}.{a0 // 12} – {a1 % 12 + 1:02d}.{a1 // 12}"
    return {"oran": round(top / satis, 6) if satis > 0 else 0.0, "satis_tl": round(satis, 2),
            "masraf_tl": round(top, 2), "donem": donem,
            "kalemler": [{"kod": k, "ad": _s(hesap_adlari.get(k)), "tl": round(v, 2)}
                         for k, v in sorted(masraf.items(), key=lambda x: -x[1]) if abs(v) >= KURUS]}


def kayit_yap(satirlar, hesap_adlari, bugun):
    return {"kalemler": defter_kalemleri(satirlar, hesap_adlari), "satis_maliyeti": satis_maliyeti_orani(satirlar, hesap_adlari, bugun)}


def manuel_cakisan(manuel_kalemler, kayit):
    """Mikro'dan da gelen manuel kalemler: {kalem id ya da sıra: defter kalemi adı}. Yalnız tutarı olan defter
    kalemleri ve satış maliyeti (kargo / depolama) için."""
    var = {k["ad"] for k in (kayit or {}).get("kalemler") or [] if abs(_f(k.get("tl"))) >= KURUS}
    sm = (kayit or {}).get("satis_maliyeti") or {}
    out = {}
    for i, m in enumerate(manuel_kalemler or []):
        aciklama = _buyuk(m.get("aciklama"))
        anahtar = m.get("id", i)
        for ad, kelimeler in MANUEL_KELIME.items():
            if ad in var and any(_buyuk(k) in aciklama for k in kelimeler):
                out[anahtar] = ad
                break
        else:
            if _f(sm.get("oran")) > 0 and any(_buyuk(k) in aciklama for k in SATIS_MALIYETI_KELIME):
                out[anahtar] = "Satış maliyeti"
    return out


def manuel_usd(m, kur):
    """Manuel kalemin toplama işaretli etkisi ($): ekle +, çıkar −."""
    t = _f(m.get("tutar"))
    t = t if _s(m.get("para_birimi") or "USD").upper() == "USD" else (t / kur if kur > 0 else 0.0)
    return t if m.get("tip") == "ekle" else -t


def cakisan_etki(manuel_kalemler, cakisan, kur):
    """Mikro'dan geldiği için toplama girmeyen manuel kalemlerin işaretli toplamı ($)."""
    return round(sum(manuel_usd(m, kur) for i, m in enumerate(manuel_kalemler or []) if m.get("id", i) in cakisan), 2)


def usd_ozeti(kayit, kur, stok_aktif):
    """Ekran için: {arti, eksi, kalemler [{ad, usd}], satis_maliyeti_usd, oran}. kur: TL/USD."""
    kalemler = [{"ad": k["ad"], "usd": round(_f(k["tl"]) / kur, 2) if kur > 0 else 0.0, "hesaplar": k.get("hesaplar")}
                for k in (kayit or {}).get("kalemler") or [] if abs(_f(k.get("tl"))) >= KURUS]
    oran = _f(((kayit or {}).get("satis_maliyeti") or {}).get("oran"))
    return {"kalemler": kalemler, "arti": round(sum(k["usd"] for k in kalemler if k["usd"] > 0), 2),
            "eksi": round(-sum(k["usd"] for k in kalemler if k["usd"] < 0), 2), "oran": oran,
            "satis_maliyeti_usd": round(max(_f(stok_aktif), 0.0) * oran, 2)}


def esit_mi(a, b):
    import json
    return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


# ── Veritabanı ─────────────────────────────────────────────────────
def _cli():
    from kayranacc.database import get_client
    return get_client()


def _bugun():
    from shared.utils import tr_today
    return tr_today()


def _sayfali(cli, tablo, secim, siralama):
    from satis.mikro_esitle import kopyasiz
    out, bas = [], 0
    while True:
        q = cli.table(tablo).select(secim)
        for kol in siralama:
            q = q.order(kol)
        parca = q.range(bas, bas + SAYFA - 1).execute().data or []
        out += parca
        if len(parca) < SAYFA:
            return kopyasiz(out, siralama)
        bas += SAYFA


def veri_oku():
    cli = _cli()
    # Yıl sonu kapanış / açılış ve gelir-gider kapanış mahsubu ayıklanmış (kayranacc/mikro_yil_sonu): kapanış
    # yapılıp açılış girilmemişken (Ocak başı) bilanço kalemleri sıfır görünmesin
    from kayranacc.mikro_yil_sonu import oku as _ys_oku
    satir, _turlu = _ys_oku(cli)
    plan = _sayfali(cli, "mikro_hesap_plani", "muh_hesap_kod,muh_hesap_isim1", ("muh_hesap_kod",))
    return satir, {_s(p.get("muh_hesap_kod")): _s(p.get("muh_hesap_isim1")) for p in plan}


def plan_hazirla(bugun=None):
    satir, adlar = veri_oku()
    from kayranacc.database import aktif_excel_oku
    return {"kayit": kayit_yap(satir, adlar, bugun or _bugun()), "once": aktif_excel_oku("ortak", KAYIT_TIPI),
            "bos": not satir}


def kayitli():
    from kayranacc.database import aktif_excel_oku
    return aktif_excel_oku("ortak", KAYIT_TIPI)


def uygula(plan):
    """Döner: True (yazdı) / False (değişmedi) / str (hata)."""
    if plan.get("bos"):
        return "Mikro muhasebe bakiyeleri okunamadı; yazılmadı."
    if plan.get("once") is not None and esit_mi(plan["once"], plan["kayit"]):
        return False
    from kayranacc.database import aktif_excel_kaydet
    return True if aktif_excel_kaydet(KAYNAK_ADI, KAYIT_TIPI, plan["kayit"]) else "Kaydedilemedi."


def durum():
    try:
        from kayranacc.database import get_ayar
        return get_ayar(DURUM_ANAHTAR, {}) or {}
    except Exception:  # noqa: BLE001
        return {}


def acik_mi():
    return bool(durum().get("acik"))


def ac(kullanici):
    from kayranacc.database import set_ayar
    from shared.utils import tr_now
    d = durum()
    d.update(acik=True, acan=str(kullanici or ""), acilis=str(tr_now()))
    set_ayar(DURUM_ANAHTAR, d)


def son_aktarim():
    r = (_cli().table("mikro_senk_durum").select("son_cekim").eq("tablo", "mikro_muhasebe_ay").execute().data
         or [])
    return str((r[0] if r else {}).get("son_cekim") or "")


def otomatik():
    """Açıksa ve aktarıcı yeni muhasebe verisi getirdiyse yeniden hesaplar; değiştiyse yazar. Hata fırlatmaz."""
    try:
        from kayranacc.database import set_ayar
        d = durum()
        if not d.get("acik"):
            return None
        son = son_aktarim()
        if not son or (d.get("son_calisma") and str(d.get("son_calisma")) >= son):
            return None
        from satis.mikro_esitle import aktarim_suruyor
        if aktarim_suruyor():
            return None
        sonuc = uygula(plan_hazirla())
        if isinstance(sonuc, str):
            from shared.kayit import sessiz
            sessiz("kayranacc.mikro_aktif.otomatik", RuntimeError(sonuc))
            return None
        d["son_calisma"] = son
        set_ayar(DURUM_ANAHTAR, d)
        return "defter kalemleri yazıldı" if sonuc else None
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("kayranacc.mikro_aktif.otomatik", e)
        return None
