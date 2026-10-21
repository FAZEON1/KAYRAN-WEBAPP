# -*- coding: utf-8 -*-
"""Mikro → aylık gider tablosu (Ekim 2026, Mikro adım 1c).

Kullanıcı: "Olabildiğince az dosya upload; her şey Mikro'dan, tam otomatik." Muhasebenin her ay doldurduğu
gider tablosu (Yönetim › Destekler ve giderler; sistem_ayarlari gider_tablosu_<yıl>: {kat, detay, tarih})
aynı biçimde Mikro'nun muhasebe hesaplarından üretilir: her kalem = eşlenen hesapların aylık (borç − alacak)
toplamı (mikro_muhasebe_ay, aktarıcı çeker). Kalem adları ve kategoriler muhasebenin tablosundaki gibi.

Eşleme (KALEMLER) 2026 tablosundan çıkarıldı: Ocak'ta işçi ücreti (760.01 + 770.01 + huzur hakkı), yemek,
seyahat, araç, temsil, kırtasiye, damga, KKEG kalemleri kuruşu kuruşuna tuttu. Muhasebenin elle yaptığı
ay kaydırmaları (ör. Mart amortismanı Haziran'a, Şubat geri dönüşüm payı lojistiğe) Mikro'da kaydın
ayındadır. Eşlemede olmayan yeni bir gider hesabı (760 / 770 / 780 / 689) kaybolmaz: kendi adıyla
"Yarı Değişken" altına girer. Satış destek bedelleri (760.04.019–023) gider değil, destek: alınmaz.

Ay: geçmiş yıllar 12 ay; bu yıl yalnız BİTMİŞ aylar (içinde bulunulan ay muhasebe kapanmadan yarım kalır).
Yıl: Mikro'nun yıl sonu kapanış fişi Aralık'ta gider hesaplarını sıfırlıyor (canlı 2025 Aralık: borç
21.179.807,31 · alacak 63.071.734,60). Fiş türü ayrılmış tablo (mikro_muhasebe_ay_tur, aktarıcının
muhasebe_ay_tur sorgusu) doluysa ondan okunur ve kapanış türündeki fişler (KAPANIS_TURLERI) alınmaz; o
zaman 2025'ten (ILK_YIL_TURLU). Tablo yoksa / boşsa eski tablo (mikro_muhasebe_ay) ve 2026'dan (ILK_YIL).
Güvenlik: kapanış ayıklandıktan sonra bir yılın Aralık'ı hâlâ eksiyse (kapanış başka türde) o yıl hiç
hesaplanmaz — yanlış rakam yazılmaz, kayıtlı tablo kalır.
Otomatik tur yalnız onaylanan ilk yıldan (durum "ilk_yil", yoksa ILK_YIL) sonrasını yazar: 2025 tablosu
(muhasebenin Excel'i) kullanıcı karşılaştırmayı görüp onaylamadan değişmez.
İlk açılışta "Excel ↔ Mikro" karşılaştırması ve onay (Destekler ve giderler sayfası), sonra otomatik.
Durum sistem_ayarlari'nda (DURUM_ANAHTAR).
"""
from collections import defaultdict

DURUM_ANAHTAR = "mikro_gider_durum"
ILK_YIL = 2026          # fiş türü olmayan tablo (mikro_muhasebe_ay): 2025 Aralık kapanışla sıfır
ILK_YIL_TURLU = 2025    # fiş türü ayrılmış tablo (mikro_muhasebe_ay_tur) doluysa
# Mikro MUHASEBE_FISLERI.fis_tur içinde yıl sonu kapanış fişinin türü. DOĞRULANMADI (Mikro'da genelde
# 0 mahsup, 1 tahsil, 2 tediye, 3 açılış, 4 kapanış): veri gelince mikro_muhasebe_tur tablosunda Aralık'ta
# gider hesaplarını (gider_alacak) sıfırlayan türe bakılıp düzeltilmeli. Yanlışsa kapanis_kalmis_mi o yılı atlar.
KAPANIS_TURLERI = (4,)
SAYFA = 1000            # Supabase tek sorguda en fazla 1000 satır döndürür
KATEGORILER = ("Sabit", "Değişken", "Yarı Değişken")
GIDER_ONEK = ("760.", "770.", "780.", "689.")
HARIC = ("760.04.019", "760.04.020", "760.04.021", "760.04.022", "760.04.023")   # satış destek bedelleri
DIGER_KAT = "Yarı Değişken"
KURUS = 0.005

# (kategori, kalem, hesaplar) — hesap kodu tam ya da "760.01." gibi önek
KALEMLER = [
    ("Sabit", "İŞÇİ ÜCRET GİDERLERİ - HUZUR HAKKI",
     ("760.01.", "770.01.001", "770.01.002", "770.01.003", "770.01.015")),
    ("Sabit", "PERSONEL YEMEK GİDERLERİ", ("760.04.024", "770.01.005")),
    ("Sabit", "MERKEZ OFİS KİRA GİDERLERİ", ("770.02.001",)),
    ("Sabit", "BİLGİ İŞLEM GİDERLERİ", ("770.03.005",)),
    ("Sabit", "YAZILIM DESTEK GİDERİ", ("770.03.016", "770.03.017")),
    ("Sabit", "SERBEST MESLEK GİDERLERİ AVUKAT MUHASEBE VB", ("770.03.019", "770.03.003")),
    ("Sabit", "ORTAK KATILIM GİDERLERİ", ("770.04.007",)),
    ("Sabit", "BEYANNAME DAMGA VERGİSİ", ("770.05.001", "770.05.011")),
    ("Sabit", "BELEDİYE REKLAM İLAN VE TABELA VE ÇEVRE TEM.VERGİSİ", ("770.05.002",)),
    ("Sabit", "DEMİRBAŞ AMORTİSMAN GİDERİ", ("770.06.001", "760.06.")),
    ("Sabit", "TEKNİK SERVİS BEDELİ ANLAŞMASI", ("760.03.011",)),
    ("Sabit", "İŞ GÜVENLİĞİ VE İŞYERİ HEKİMLİĞİ GİDERLERİ", ("770.01.011", "770.01.006", "770.01.007")),
    ("Değişken", "LOJİSTİK VE NAKLİYE GİDERLERİ", ("760.03.005", "760.03.007", "770.05.010")),
    ("Değişken", "AMBALAJ VE PAKETLEME GİDERLERİ", ("760.03.008",)),
    ("Değişken", "ÜRÜN SATIŞI İÇİN DIŞARDAN SAĞ.FAY VE HİZ", ("760.03.018",)),
    ("Değişken", "ÜRÜN REKLAM VE TANITIM GİDERLERİ", ("760.04.001",)),
    ("Değişken", "KARGO VE POSTA GİDERLERİ", ("770.03.018",)),
    ("Değişken", "BANKA GİDERLERİ", ("770.04.012",)),
    ("Değişken", "NOTER VE TESCİL HARÇLARI", ("770.05.003",)),
    ("Değişken", "BANKA MASRAF B.S.M.V.", ("780.79.004", "780.72.")),
    ("Değişken", "TL KREDİ FAİZLERİ", ("780.79.006",)),
    ("Değişken", "KREDİ KARTI TAHSİLATLARI KOMİSYONLARI", ("780.79.007",)),
    ("Değişken", "KKEG CEZALAR, GİDER KSISITLAMASI VB.", ("689.",)),
    ("Değişken", "DEPOLAMA GİDERLERİ", ("760.03.013",)),
    ("Değişken", "TEKNİK SERVİS TAMİR BAKIM ONARIM", ("760.04.027",)),
    ("Değişken", "SİGORTA GİDERLERİ", ("770.04.001", "760.04.015")),
    ("Değişken", "ÖZEL MALİYET AMORSİTMAN", ("770.06.005",)),
    ("Değişken", "HAKLAR AMORTİSMAN", ("770.06.004",)),
    ("Değişken", "GERİ DÖNÜŞÜM KATKI PAYI", ("760.04.010",)),
    ("Değişken", "SATIŞ PROMOSYON VE HEDİYELİK EŞYA", ("760.04.003",)),
    ("Değişken", "DANIŞMANLIK HİZMETİ", ("760.03.017",)),
    ("Yarı Değişken", "HABERLEŞME GİDERLERİ", ("760.03.002",)),
    ("Yarı Değişken", "ARAÇ KİRALAMA GİDERLERİ", ("760.03.003", "770.04.014")),
    ("Yarı Değişken", "SEYAHAT GİDERLERİ", ("760.04.005", "760.04.004", "770.04.013")),
    ("Yarı Değişken", "ARAÇ YAKIT VE DİĞER TÜM GİDERLERİ", ("760.04.007", "760.04.017", "770.03.015", "770.04.004")),
    ("Yarı Değişken", "SATIŞ PAZ.DESTEK GİD.", ("760.04.011",)),
    ("Yarı Değişken", "PERSONEL YURTİÇİ YOL GİDERLERİ", ("760.04.026", "770.01.014")),
    ("Yarı Değişken", "ELEKTRİK VE SU VE GAZ GİDERLERİ", ("770.03.001",)),
    ("Yarı Değişken", "OFİS TAMİR-BAKIM ONARIM GİDERLERİ", ("770.03.013",)),
    ("Yarı Değişken", "TEMSİL, AĞIRLAMA VE İKRAM GİDERLERİ", ("760.04.016", "770.04.003")),
    ("Yarı Değişken", "KIRTASİYE GİDERLERİ", ("770.04.005", "760.04.025")),
    ("Yarı Değişken", "ÇEŞİTLİ OFİS GİDERLERİ", ("770.04.008",)),
    ("Yarı Değişken", "TİCARET ODASI AİDAT VE GİDERLERİ", ("770.05.004",)),
    ("Yarı Değişken", "GİDER YAZILAN DEMİRBAŞLAR", ("770.04.009",)),
]


def _f(v, d=0.0):
    try:
        x = float(v)
        return x if x == x else d
    except (TypeError, ValueError):
        return d


def _s(v):
    return str(v or "").strip()


# ── Saf ────────────────────────────────────────────────────────────
def gider_hesabi_mi(kod):
    return kod.startswith(GIDER_ONEK) and kod not in HARIC


def kapanis_mi(r):
    """Satır yıl sonu kapanış fişinden mi (fis_tur KAPANIS_TURLERI'nde). Fiş türü yoksa değil."""
    t = r.get("fis_tur")
    if t is None or t == "":
        return False
    return int(_f(t, -1)) in KAPANIS_TURLERI


def kapanis_kalmis_mi(satirlar, yil):
    """Yılın Aralık'ında gider hesaplarının toplamı (borç − alacak) eksi mi: yıl sonu kapanışı hâlâ içeride.
    Normal bir Aralık'ta gider artıdır; kapanış bütün yılın giderini alacağa yazınca eksiye düşer."""
    net = sum(_f(r.get("borc")) - _f(r.get("alacak")) for r in satirlar
              if int(_f(r.get("yil"))) == int(yil) and int(_f(r.get("ay"))) == 12
              and gider_hesabi_mi(_s(r.get("hesap_kod"))))
    return net < -KURUS


def kalem_bul(kod, hesap_adi=None):
    """Hesap kodu → (kategori, kalem). En uzun eşleşen önek kazanır; eşlemede yoksa hesabın adıyla Yarı Değişken.
    Gider hesabı değilse None."""
    if not gider_hesabi_mi(kod):
        return None
    en, uz = None, -1
    for kat, kalem, hesaplar in KALEMLER:
        for h in hesaplar:
            if (kod == h or (h.endswith(".") and kod.startswith(h))) and len(h) > uz:
                en, uz = (kat, kalem), len(h)
    return en or (DIGER_KAT, (hesap_adi or kod).strip())


def gider_tablosu(satirlar, yil, ay_siniri=12, hesap_adlari=None):
    """mikro_muhasebe_ay satırları → {"kat": {kategori: [12]}, "detay": [[kategori, kalem, [12]]]}.
    ay_siniri: bu aydan (1–12, dahil) sonrası 0 kalır."""
    ad = hesap_adlari or {}
    kalem = defaultdict(lambda: [0.0] * 12)
    for r in satirlar:
        if int(_f(r.get("yil"))) != int(yil):
            continue
        ay = int(_f(r.get("ay")))
        kod = _s(r.get("hesap_kod"))
        if not 1 <= ay <= ay_siniri:
            continue
        k = kalem_bul(kod, ad.get(kod))
        if k:
            kalem[k][ay - 1] += _f(r.get("borc")) - _f(r.get("alacak"))
    sira = {(kt, kl): i for i, (kt, kl, _) in enumerate(KALEMLER)}
    detay = sorted(([kt, kl, [round(v, 2) for v in aylik]] for (kt, kl), aylik in kalem.items()
                    if any(abs(v) >= KURUS for v in aylik)),
                   key=lambda d: (KATEGORILER.index(d[0]), sira.get((d[0], d[1]), 999), d[1]))
    kat = {k: [0.0] * 12 for k in KATEGORILER}
    for kt, _kl, aylik in detay:
        kat[kt] = [round(a + b, 2) for a, b in zip(kat[kt], aylik)]
    return {"kat": kat, "detay": detay}


def ay_siniri(yil, bugun):
    """Bu yıl: biten son ay (Ekim'de 9); geçmiş yıl 12; gelecek yıl 0."""
    if yil < bugun.year:
        return 12
    if yil > bugun.year:
        return 0
    return bugun.month - 1


def esit_mi(a, b):
    """İki gider tablosu aynı mı (kalem + ay, kuruş toleransı)."""
    def _harita(t):
        return {(d[0], d[1]): [round(_f(x), 2) for x in d[2]] for d in (t or {}).get("detay") or []}
    ha, hb = _harita(a), _harita(b)
    if set(ha) != set(hb):
        return False
    return all(abs(x - y) < KURUS for k in ha for x, y in zip(ha[k], hb[k]))


def karsilastir(eski, yeni):
    """Kategori × ay: [(kategori, [eski 12], [yeni 12])] ve kalem yıllık farkları [(kat, kalem, eski, yeni)]."""
    ek, yk = (eski or {}).get("kat") or {}, (yeni or {}).get("kat") or {}
    kat = [(k, [round(_f(x), 2) for x in (ek.get(k) or [0] * 12)], yk.get(k) or [0.0] * 12) for k in KATEGORILER]
    ed = {(d[0], d[1]): sum(_f(x) for x in d[2]) for d in (eski or {}).get("detay") or []}
    yd = {(d[0], d[1]): sum(_f(x) for x in d[2]) for d in (yeni or {}).get("detay") or []}
    kalem = sorted(((k[0], k[1], round(ed.get(k, 0.0), 2), round(yd.get(k, 0.0), 2)) for k in set(ed) | set(yd)
                    if abs(ed.get(k, 0.0) - yd.get(k, 0.0)) >= 1),
                   key=lambda r: -abs(r[3] - r[2]))
    return {"kat": kat, "kalem": kalem}


# ── Veritabanı ─────────────────────────────────────────────────────
def _cli():
    from kayranacc.database import get_client
    return get_client()


def _bugun():
    from shared.utils import tr_today
    return tr_today()


def yillar(bugun=None, turlu=False):
    bugun = bugun or _bugun()
    return [y for y in range(ILK_YIL_TURLU if turlu else ILK_YIL, bugun.year + 1)]


def _sayfali(cli, tablo, secim, siralama, ilk_yil=None):
    out, bas = [], 0
    while True:
        q = cli.table(tablo).select(secim)
        if ilk_yil is not None:
            q = q.gte("yil", ilk_yil)
        for kol in siralama:
            q = q.order(kol)
        parca = q.range(bas, bas + SAYFA - 1).execute().data or []
        out += parca
        if len(parca) < SAYFA:
            return out
        bas += SAYFA


def muhasebe_satirlari(cli):
    """(gider hesabı satırları, fiş türlü mü). Fiş türlü tablo doluysa kapanış fişleri ayıklanmış olarak ondan;
    yoksa / okunamazsa eski tablodan (kapanış dahil, yalnız ILK_YIL'dan)."""
    try:
        satir = _sayfali(cli, "mikro_muhasebe_ay_tur", "yil,ay,hesap_kod,fis_tur,borc,alacak",
                         ("yil", "ay", "hesap_kod", "fis_tur"), ILK_YIL_TURLU)
    except Exception:  # noqa: BLE001  (tablo henüz kurulmadı)
        satir = []
    turlu = bool(satir)
    if turlu:
        satir = [r for r in satir if not kapanis_mi(r)]
    else:
        satir = _sayfali(cli, "mikro_muhasebe_ay", "yil,ay,hesap_kod,borc,alacak", ("yil", "ay", "hesap_kod"),
                         ILK_YIL)
    return [r for r in satir if gider_hesabi_mi(_s(r.get("hesap_kod")))], turlu


def plan_hazirla(bugun=None):
    """{yil: {"eski": kayıtlı tablo, "yeni": Mikro tablosu, "degisir": bool}}. Kapanışı hâlâ içinde olan yıl
    (kapanis_kalmis_mi) plana girmez."""
    from kayranacc.database import get_ayar
    bugun = bugun or _bugun()
    cli = _cli()
    satir, turlu = muhasebe_satirlari(cli)
    ys = [y for y in yillar(bugun, turlu) if not kapanis_kalmis_mi(satir, y)]
    adlar = {_s(r.get("muh_hesap_kod")): _s(r.get("muh_hesap_isim1")) for r in
             _sayfali(cli, "mikro_hesap_plani", "muh_hesap_kod,muh_hesap_isim1", ("muh_hesap_kod",))}
    plan = {}
    for y in ys:
        yeni = gider_tablosu(satir, y, ay_siniri(y, bugun), adlar)
        eski = get_ayar(f"gider_tablosu_{y}", {}) or {}
        plan[y] = {"eski": eski, "yeni": yeni, "degisir": not esit_mi(eski, yeni)}
    return plan


def uygula(plan):
    """Değişen yılları yazar. Döner: yazılan yıllar."""
    from kayranacc.database import set_ayar
    bugun = _bugun().isoformat()
    yazilan = []
    for y, p in plan.items():
        if p["degisir"] and p["yeni"]["detay"]:
            set_ayar(f"gider_tablosu_{y}", dict(p["yeni"], tarih=bugun, kaynak="Mikro"))
            yazilan.append(y)
    if yazilan:
        try:
            from shared.yukleme_takvimi import _temizle
            _temizle()
        except Exception:  # noqa: BLE001
            pass
    return yazilan


def durum():
    try:
        from kayranacc.database import get_ayar
        return get_ayar(DURUM_ANAHTAR, {}) or {}
    except Exception:  # noqa: BLE001
        return {}


def acik_mi():
    return bool(durum().get("acik"))


def ac(kullanici, ilk_yil=None):
    """ilk_yil: karşılaştırmada gösterilip onaylanan ilk yıl; otomatik tur bundan öncesini yazmaz."""
    from kayranacc.database import set_ayar
    from shared.utils import tr_now
    d = durum()
    d.update(acik=True, acan=str(kullanici or ""), acilis=str(tr_now()), ilk_yil=int(ilk_yil or ILK_YIL))
    set_ayar(DURUM_ANAHTAR, d)


def son_aktarim():
    r = (_cli().table("mikro_senk_durum").select("son_cekim").eq("tablo", "mikro_muhasebe_ay").execute().data
         or [])
    return str((r[0] if r else {}).get("son_cekim") or "")


def otomatik():
    """Açıksa ve aktarıcı yeni muhasebe verisi getirdiyse gider tablolarını yeniler. Hata fırlatmaz."""
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
        ilk = int(_f(d.get("ilk_yil"), ILK_YIL) or ILK_YIL)      # onaylanmamış yıl (ör. 2025) yazılmaz
        yazilan = uygula({y: p for y, p in plan_hazirla().items() if y >= ilk})
        d["son_calisma"] = son
        set_ayar(DURUM_ANAHTAR, d)
        return yazilan
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("kayranacc.mikro_gider.otomatik", e)
        return None
