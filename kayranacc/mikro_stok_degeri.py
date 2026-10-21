# -*- coding: utf-8 -*-
"""Toplam Aktifler · stok değeri — Excel yerine uygulamanın kendi verisinden (Ekim 2026, Mikro adım 2b).

Kullanıcı: "Olabildiğince az dosya upload; her şey Mikro'dan, tam otomatik." Toplam Aktifler'in stok kalemi
"Stok değeri raporu" Excel'inden geliyordu (Dosya kapısı aktif_stok → kayranacc.aktif_excel.parse_stok_excel).
Kayıt: aktif_excel_verileri "_SHARED_" / "stok", veri = [usd_stok, {pazaryeri: usd}].
  usd_stok   Excel'in 5. sütunu (USD SON DURUM) toplamı = BİZİM depolardaki stoğun USD değeri. Toplam
             Aktifler bunu × 1,20 (KDV) ile aktiflere katar — sayfadaki tek kullanılan rakam.
  pazaryeri  Excel'deki firma bloklarının "TOPLAM TUTAR" toplamları (müşterideki stok). Toplama GİRMEZ;
             yalnız saklanıyordu (bilgi).
Buradaki karşılık:
  usd_stok   = Σ (urunler.depo_kirilim, BÜTÜN depolar) × paçal (satis.database.get_pacal_map / pacal_bul —
               tek maliyet kaynağı). Depo stoğu Mikro'dan gelir (kayranpm/mikro_stok.py).
  pazaryeri  = Σ (her kanalın son stok raporu, kayranpm.stok_hesap.kanal_stoklari + kanal_kod_haritasi)
               × paçal; anahtar firma kodu (ITOPYA, HB, VATAN …; ekranda firma_gorunen_ad).

21.10.2026 karşılaştırması (20.10 Excel'i ↔ uygulama verisi):
  usd_stok   764.472,84 ↔ 737.742,84 (−%3,5). Excel bütün depoları sayıyor: yalnız Merkez + Happy Life
             616.564,54 (−%19) olurdu. Depo kırılımı: Merkez 323.285,83 · Happy Life 293.278,70 · İade 71.992,66
             · Teknik 35.617,14 · İkinci el 6.543,52 · Outlet 6.403,64 · Pazarlama 621,34. Kalan fark maliyet
             tabanından (Mikro'nun kendi USD maliyeti ↔ uygulamanın paçalı) ve paçalı olmayan 321 adetten
             (RMAFC005 kasa fanı 265, RMAFM001 monitör anakartı 50, 0001 fiyat farkı 6).
  pazaryeri  Excel HEPSIBURADA 301.852,50 · VATAN 1.118.287,10 · EERA 298.114,20 ↔ paçalla HB 204.346,45 ·
             VATAN 822.257,52 · ITOPYA 197.346,57 (18.10 kanal raporları). Oranlar firmadan firmaya farklı
             (1,36–1,51): Excel bu bloklarda paçal değil başka bir birim fiyat kullanıyor; yeniden üretilemedi.
             Toplam Aktifler'e girmediği için rakamı etkilemez.

İlk açılışta Toplam Aktifler sayfasında "şimdi ↔ uygulama" karşılaştırması ve onay; sonra otomatik() her aktarım
turunda (mikro_stok_miktar yenilendiğinde) hesaplar, yalnız değer değiştiyse yazar. Durum sistem_ayarlari'nda
(DURUM_ANAHTAR; şema değişikliği yok). Açıkken Stok değeri raporu yüklemesi kaydedilmez, hatırlatması çıkmaz.
"""
from collections import defaultdict

DURUM_ANAHTAR = "mikro_stok_degeri_durum"
KAYNAK_ADI = "Mikro"
KDV = 1.20
KURUS = 0.005
# Eski Excel'in firma blok adları → firma kodu (karşılaştırma tablosu aynı satıra düşsün)
ESKI_AD = {"HEPSIBURADA": "HB", "D-MARKET": "HB", "EERA": "ITOPYA", "İTOPYA": "ITOPYA"}


def _f(v, d=0.0):
    try:
        x = float(v)
        return x if x == x else d
    except (TypeError, ValueError):
        return d


def _birim(pacal, sku):
    from satis.database import pacal_bul
    return pacal_bul(pacal, sku)


# ── Hurda / outlet / ikinci el değerlemesi (kullanıcı, 21.10.2026) ─────
# "Sıddık kullanıcısına çıkan ürünlere bakıp maliyetin % ne kadar altında olduğunu hesapla; aynı korelasyonla hiç
# satılmamış ürünleri de o şekilde maliyetlendir … hurda, outlet ve 2.el fiyatları diye fiyatlar değişir."
# Bu depolardaki ürün paçal × oran ile sayılır. Oran = SIDDIK BAYRAKTAR'a o depo türünden yapılan satışların
# satış / maliyet toplamı (Mikro faturaları; satıldığı depo Mikro'daki çıkış deposundan). Ürün Sıddık'a satılmışsa
# kendi oranı, satılmamışsa deponun ortalama oranı. Oran 1'i geçmez (maliyetin üstünde değerlenmez). Canlı
# 21.10: İkinci el %78,8 · Outlet %97,6 · Servis (hurda) %23,1. Satış yoksa o depo tam paçalla kalır.
ALICI = "SIDDIK BAYRAKTAR"


def depo_turu(ad):
    """Depo adı (uygulama ya da Mikro) → 'hurda' | 'ikinci_el' | 'outlet' | None."""
    from shared.utils import tr_buyuk
    a = " ".join(tr_buyuk(str(ad or "")).replace(".", " ").split())
    if "OUTLET" in a:
        return "outlet"
    if "IKINCI EL" in a or "2 EL" in a:
        return "ikinci_el"
    if "TEKNIK" in a or "SERVIS" in a or "HURDA" in a:
        return "hurda"
    return None


def oranlar(satirlar):
    """satirlar: [{depo, sku, adet, birim_satis, birim_maliyet}] (Sıddık satışları, çıkış deposu ile) →
    {tür: {"ort": oran, "sku": {sku anahtarı: oran}, "adet": n}}. Maliyeti 0 olan satır sayılmaz."""
    from shared.utils import sku_anahtar
    top = defaultdict(lambda: [0.0, 0.0, 0])
    sku = defaultdict(lambda: [0.0, 0.0])
    for r in satirlar or []:
        t = depo_turu(r.get("depo"))
        a, s, m = _f(r.get("adet")), _f(r.get("birim_satis")), _f(r.get("birim_maliyet"))
        if not t or a <= 0 or m <= 0:
            continue
        top[t][0] += a * s
        top[t][1] += a * m
        top[t][2] += int(round(a))
        k = sku_anahtar(r.get("sku"))
        sku[(t, k)][0] += a * s
        sku[(t, k)][1] += a * m
    out = {}
    for t, (s, m, n) in top.items():
        out[t] = {"ort": round(min(max(s / m, 0.0), 1.0), 4), "adet": n,
                  "sku": {k: round(min(max(v[0] / v[1], 0.0), 1.0), 4) for (tt, k), v in sku.items() if tt == t}}
    return out


def oran_bul(orn, depo, sku):
    """Depo türü ve ürün için oran (yoksa 1,0: tam paçal)."""
    t = depo_turu(depo)
    if not t or t not in (orn or {}):
        return 1.0
    from shared.utils import sku_anahtar
    return orn[t]["sku"].get(sku_anahtar(sku), orn[t]["ort"])


# ── Saf ────────────────────────────────────────────────────────────
def depo_degerleri(urunler, pacal, orn=None):
    """urunler: [{sku, depo_kirilim}] → {"deger": {depo: $}, "adet": {depo: adet}, "pacalsiz": [(sku, depo, adet)],
    "indirim": {depo: $}}. Bütün depolar sayılır; hurda / outlet / ikinci el depoları oranla (orn, oranlar())."""
    deger, adet, pacalsiz, indirim = defaultdict(float), defaultdict(int), [], defaultdict(float)
    for u in urunler or []:
        dk = u.get("depo_kirilim") or {}
        if not isinstance(dk, dict):
            continue
        b = _birim(pacal, u.get("sku"))
        for depo, m in dk.items():
            m = _f(m)
            if not m:
                continue
            o = oran_bul(orn, depo, u.get("sku"))
            deger[depo] += m * b * o
            if o < 1.0:
                indirim[depo] += m * b * (1.0 - o)
            adet[depo] += int(round(m))
            if b <= 0:
                pacalsiz.append((str(u.get("sku") or ""), depo, int(round(m))))
    return {"deger": {d: round(v, 2) for d, v in sorted(deger.items())}, "adet": dict(sorted(adet.items())),
            "pacalsiz": sorted(pacalsiz), "indirim": {d: round(v, 2) for d, v in sorted(indirim.items())}}


def kanal_degerleri(kanal_stok, pacal):
    """kanal_stok: {firma: {sku: stok}} (stok_hesap.kanal_stoklari) → {firma: $}. Sıfır olan firma yazılmaz."""
    out = {}
    for firma, d in (kanal_stok or {}).items():
        t = sum(_f(m) * _birim(pacal, sku) for sku, m in (d or {}).items() if _f(m) > 0)
        if abs(t) >= KURUS:
            out[firma] = round(t, 2)
    return dict(sorted(out.items()))


def kayit_yap(depo, kanal):
    """Toplam Aktifler 'stok' kaydı: [usd_stok, {firma: $}] — Excel'in yazdığı biçim."""
    return [round(sum(depo["deger"].values()), 2), dict(kanal)]


def esit_mi(a, b):
    """İki stok kaydı kuruşu kuruşuna aynı mı (Excel'den gelen eski kayıt da olabilir)."""
    if not (isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)) and len(a) == 2 and len(b) == 2):
        return False
    if abs(_f(a[0]) - _f(b[0])) >= KURUS:
        return False
    pa, pb = (x if isinstance(x, dict) else {} for x in (a[1], b[1]))
    if set(pa) != set(pb):
        return False
    return all(abs(_f(pa[k]) - _f(pb[k])) < KURUS for k in pa)


def kanal_karsilastir(eski, yeni):
    """[(firma kodu, şimdi $ | None, yeni $ | None)] — eski kaydın Excel adları (HEPSIBURADA, EERA) koda çevrilir."""
    from shared.utils import firma_kanonik
    e = defaultdict(float)
    for ad, v in (eski or {}).items():
        k = ESKI_AD.get(str(ad).strip().upper(), firma_kanonik(ad))
        e[k] += _f(v)
    anahtar = sorted(set(e) | set(yeni or {}))
    return [(k, round(e[k], 2) if k in e else None, (yeni or {}).get(k)) for k in anahtar]


def plan_yap(urunler, kanal_stok, pacal, mevcut, orn=None):
    """Karşılaştırma + yazılacak kayıt. mevcut: şimdiki kayıt ([usd, {..}] ya da None).
    bos: paçal okunamadı ya da değer sıfır — yazılmaz (sıfır stok değeri aktifleri yanlış düşürürdü)."""
    depo = depo_degerleri(urunler, pacal, orn)
    kanal = kanal_degerleri(kanal_stok, pacal)
    kayit = kayit_yap(depo, kanal)
    m = mevcut if isinstance(mevcut, (list, tuple)) and len(mevcut) == 2 else None
    once = _f(m[0]) if m else None
    return {"kayit": kayit, "depo": depo, "kanal": kanal, "once": once,
            "once_kanal": (m[1] if m and isinstance(m[1], dict) else {}),
            "bos": not pacal or kayit[0] <= 0, "degisir": not esit_mi(m, kayit), "oranlar": orn or {}}


# ── Veritabanı ─────────────────────────────────────────────────────
def _cli():
    from kayranacc.database import get_client
    return get_client()


def veri_oku():
    """(urunler [{sku, depo_kirilim}], kanal stoğu {firma: {sku: stok}}, paçal haritası)."""
    from kayranpm import database as pdb
    from kayranpm.stok_hesap import kanal_stoklari
    from satis.database import get_pacal_map
    urunler = [{"sku": u.get("sku"), "depo_kirilim": u.get("depo_kirilim")} for u in (pdb.urunler_skuya_gore() or [])]
    fs = pdb._hepsi("firma_stok", "firma, sku, stok_miktari, yukleme_tarihi") or []
    kanal = kanal_stoklari(fs, harita=pdb.kanal_kod_haritasi() or {})
    return urunler, kanal, get_pacal_map() or {}


def alici_satislari():
    """Sıddık'a yapılan satışlar, çıkış deposuyla: [{depo, sku, adet, birim_satis, birim_maliyet}].
    Satış satırı (uygulamanın satislar tablosu; Mikro faturasından, $ ve paçal maliyetle) ↔ Mikro satır (çıkış
    deposu) fatura no + SKU ile eşlenir."""
    from satis.mikro_esitle import sayfali_oku
    from shared.utils import sku_anahtar
    cli = _cli()
    kodlar = [str(c.get("cari_kod")) for c in (cli.table("mikro_cari_kart").select("cari_kod,cari_unvan1")
                                              .ilike("cari_unvan1", f"%{ALICI}%").execute().data or [])]
    if not kodlar:
        return []
    mk = sayfali_oku(lambda: cli.table("mikro_satis_satir").select("sth_guid,cha_evrakno_seri,cha_evrakno_sira,"
                                                                   "sth_stok_kod,cikis_depo_adi")
                     .in_("sth_cari_kodu", kodlar).order("sth_guid"), "sth_guid")
    depo = {}
    for r in mk:
        no = f"{r.get('cha_evrakno_seri')}-{r.get('cha_evrakno_sira')}"
        depo.setdefault((no, sku_anahtar(r.get("sth_stok_kod"))), r.get("cikis_depo_adi"))
        depo.setdefault((no, None), r.get("cikis_depo_adi"))
    nolar = sorted({n for n, _s in depo})
    out = []
    for i in range(0, len(nolar), 100):
        for s in (cli.table("satislar").select("siparis_no,sku,adet,birim_satis,birim_maliyet")
                  .in_("siparis_no", nolar[i:i + 100]).execute().data or []):
            no = str(s.get("siparis_no") or "")
            d = depo.get((no, sku_anahtar(s.get("sku")))) or depo.get((no, None))
            out.append(dict(s, depo=d))
    return out


def plan_hazirla():
    from kayranacc.mikro_muhasebe import _aktif_veri
    urunler, kanal, pacal = veri_oku()
    try:
        orn = oranlar(alici_satislari())
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("kayranacc.mikro_stok_degeri.oranlar", e)
        orn = {}
    return plan_yap(urunler, kanal, pacal, _aktif_veri("stok"), orn)


def uygula(plan):
    """Değiştiyse kaydı yazar. Döner: True (yazıldı) / False (gerek yok ya da boş) / hata metni."""
    if plan["bos"] or not plan["degisir"]:
        return False
    from kayranacc import database as db
    if not db.aktif_excel_kaydet(KAYNAK_ADI, "stok", plan["kayit"]):
        return "Toplam Aktifler stok kaydı yazılamadı."
    return True


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
    """Depo stoğunun son aktarımı (aktarıcı her turda tam çeker; paçal değişikliği de bu turla girer)."""
    r = (_cli().table("mikro_senk_durum").select("son_cekim").eq("tablo", "mikro_stok_miktar").execute().data
         or [])
    return str((r[0] if r else {}).get("son_cekim") or "")


def otomatik():
    """Açıksa ve aktarıcı yeni stok verisi getirdiyse hesaplar; değer değiştiyse yazar. Hata fırlatmaz.
    Depo stoğu eşitlemesinden (kayranpm.mikro_stok.otomatik) SONRA çağrılmalı: yeni kırılımı görsün."""
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
            return None                   # aktarıcı yazıyor: sonraki turda
        sonuc = uygula(plan_hazirla())
        if isinstance(sonuc, str):
            from shared.kayit import sessiz
            sessiz("kayranacc.mikro_stok_degeri.otomatik", RuntimeError(sonuc))
            return None
        d["son_calisma"] = son
        set_ayar(DURUM_ANAHTAR, d)
        return sonuc
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("kayranacc.mikro_stok_degeri.otomatik", e)
        return None
