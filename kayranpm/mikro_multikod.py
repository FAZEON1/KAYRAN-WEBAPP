# -*- coding: utf-8 -*-
"""Mikro müşteri ürün kodları → bizim SKU (Ekim 2026).

Kullanıcı: "Olabildiğince az dosya upload; her şey Mikro'dan." Haftalık müşteri raporu müşteriden geldiği
için yükleme kalır (Dosya kapısı "musteri_haftalik", kayranpm.excel_islemler.excel_yukle_haftalik_stok_satis);
yalnız rapordaki kodun bizim karta bağlanması Mikro'dan gelir. Mikro'da MULTIKOD_TANIMLARI her cari için
müşterinin kendi kodunu (mcod_caristok_kod, ör. D-market 'HBCV0000G0F6K6') bizim stok koduna (mcod_stokkod)
bağlar; aktarıcı tabloyu mikro_multikod'a tam çeker (veritabani/48_mikro_multikod.sql).

Kurallar:
  firma   mcod_carikodu → cari ünvanı (mikro_cari_kart, yoksa mikro_cari_bakiye) → firma_stok'taki firma
          değeri (kayranpm.ref_no.ref_firma_kodu: EERA… → ITOPYA, D-MARKET… → HB, diğerleri cari adı);
          karşılaştırma shared.utils.firma_kanonik + normalize_tr ile.
  kod     shared.utils.sku_anahtar ('Fazeon X' → 'X', büyük harf). Aynı firmada aynı müşteri kodu iki farklı
          stok koduna gidiyorsa kod KULLANILMAZ (belirsiz; program seçim yapmaz).
  sıra    Mikro eşleşmesi mevcut zincirin YEDEĞİDİR: kod bugün birebir SKU, onaylı eşleme, ürün adı / model
          kodu kuralı ya da kanal kod haritasıyla bir karta bağlanıyorsa olduğu gibi kalır (Mikro başka bir
          kart gösteriyorsa yalnız "çelişki" olarak sayılır). Yalnız bağlanamayan ya da birden çok karta
          benzeyen (belirsiz) kod Mikro'nun gösterdiği karta çevrilir — o kart stok kartlarında varsa.
          Gerekçe: bugün eşleşen satırların rakamı değişmez; artış yalnız eşleşmeyen satırlardan gelir.
  zaman   Eşleşme YÜKLEME anında yapılır: satır bizim SKU'yla yazılır, raporun kodu firma_stok.musteri_kodu'na
          (ekranda "Mikro kod eşleşmesi"). Kayıtlı (eski) raporlar yeniden eşleşmez; toplu değişiklik yok.
  yoksa   Tablo yok / boş / okunamıyorsa hiçbir şey değişmez (eski davranış aynen).
"""

TABLO = "mikro_multikod"
KOLONLAR = "mcod_guid,mcod_carikodu,mcod_stokkod,mcod_caristok_kod,mcod_caristok_ismi,mcod_tipi"
KART_KAYNAK = "mikro"                     # musteri_hesap.meta_hazirla kart_kaynak değeri
KAYNAK_ETIKETI = "Mikro kod eşleşmesi"    # ekranda
_SAYI_ALANLARI = ("stok", "stok_magaza", "satis", "satis_magaza")
_MEVCUT_KAYNAK = ("sku", "tablo", "kural")


def _s(v):
    return str(v or "").strip()


# ── Saf ────────────────────────────────────────────────────────────
def firma_anahtar(f):
    """firma_stok firma değeri / cari ünvanından türetilen firma — karşılaştırma anahtarı."""
    from shared.utils import firma_kanonik, normalize_tr
    return " ".join(normalize_tr(firma_kanonik(f)).split())


def cari_firma(unvan):
    """Mikro cari ünvanı → firma_stok'a yazılan firma değeri (ana firmalar kodu, diğerleri cari adı)."""
    from kayranpm.ref_no import ref_firma_kodu
    return ref_firma_kodu({"firma_adi": unvan, "firma_kodu": ""})


def harita_kur(satirlar, cari_unvan, firma_fn=None):
    """mikro_multikod satırları → {firma_anahtar: {sku_anahtar(müşteri kodu): bizim stok kodu}}.
    cari_unvan: {cari_kod: ünvan}. Ünvanı bilinmeyen cari, eksik alanlı satır atlanır. Aynı firmada aynı
    müşteri kodu iki farklı stok koduna gidiyorsa o kod haritaya girmez (belirsiz)."""
    from shared.utils import sku_anahtar
    ff = firma_fn or cari_firma
    aday = {}
    for r in satirlar or ():
        cari, stok, kod = _s(r.get("mcod_carikodu")), _s(r.get("mcod_stokkod")), _s(r.get("mcod_caristok_kod"))
        unvan = _s((cari_unvan or {}).get(cari))
        if not (cari and stok and kod and unvan):
            continue
        fa = firma_anahtar(ff(unvan))
        ka = sku_anahtar(kod)
        if not fa or not ka:
            continue
        aday.setdefault(fa, {}).setdefault(ka, {})[sku_anahtar(stok)] = stok
    out = {}
    for fa, kodlar in aday.items():
        tek = {ka: next(iter(sk.values())) for ka, sk in kodlar.items() if len(sk) == 1}
        if tek:
            out[fa] = tek
    return out


def belirsizler(satirlar, cari_unvan, firma_fn=None):
    """[(firma_anahtar, müşteri kodu, [stok kodları])] — haritaya alınmayan (birden çok stok koduna giden) kodlar."""
    from shared.utils import sku_anahtar
    ff = firma_fn or cari_firma
    aday = {}
    for r in satirlar or ():
        cari, stok, kod = _s(r.get("mcod_carikodu")), _s(r.get("mcod_stokkod")), _s(r.get("mcod_caristok_kod"))
        unvan = _s((cari_unvan or {}).get(cari))
        if cari and stok and kod and unvan:
            aday.setdefault((firma_anahtar(ff(unvan)), sku_anahtar(kod)), set()).add(sku_anahtar(stok))
    return sorted((fa, ka, sorted(sk)) for (fa, ka), sk in aday.items() if len(sk) > 1)


def uygula(agg, firma_harita, kartlar, meta=None, kod_haritasi=None, sku_fn=None):
    """Bir firmanın rapor özetini ({rapor kodu: {ad, stok, stok_magaza, satis, satis_magaza}}) Mikro koduyla
    tamamlar. Döner: (yeni özet, {"eslesen": [(rapor kodu, kart)], "celiski": [(rapor kodu, mevcut kart,
    Mikro kartı)], "kartsiz": [(rapor kodu, Mikro stok kodu)]}).
    meta: musteri_hesap.meta_hazirla sonucu (rapor kodu → kart_sku / kart_kaynak); kod_haritasi:
    {sku_anahtar(rapor kodu): kart} (kanal_kod_haritasi). İkisinden biri kodu bir karta bağlıyorsa kod
    değişmez. Çevrilen satır bizim kart SKU'suna yazılır, raporun kodu 'musteri_kodu'nda kalır; aynı karta
    düşen satırlar toplanır."""
    from shared.utils import sku_anahtar
    skn = sku_fn or sku_anahtar
    kartlar = kartlar or {}
    kart_norm = {}
    for k in kartlar:
        n = skn(k)
        if n and n not in kart_norm:
            kart_norm[n] = k
    ozet = {"eslesen": [], "celiski": [], "kartsiz": []}
    out = {}
    for ham, o in (agg or {}).items():
        hedef = ham
        mk = (firma_harita or {}).get(skn(ham))
        if mk:
            mikro_kart = kart_norm.get(skn(mk))
            m = (meta or {}).get(ham) or {}
            mevcut = m.get("kart_sku") if m.get("kart_kaynak") in _MEVCUT_KAYNAK else None
            if not mevcut:
                hk = (kod_haritasi or {}).get(skn(ham))
                mevcut = hk if hk in kartlar else None
            if not mikro_kart:
                ozet["kartsiz"].append((ham, mk))
            elif mevcut:
                if skn(mevcut) != skn(mikro_kart):
                    ozet["celiski"].append((ham, mevcut, mikro_kart))
            else:
                hedef = mikro_kart
                ozet["eslesen"].append((ham, mikro_kart))
        h = out.get(hedef)
        if h is None:
            h = out[hedef] = dict(o)
            if hedef != ham:
                h["musteri_kodu"] = ham
            continue
        for a in _SAYI_ALANLARI:
            h[a] = (h.get(a) or 0) + (o.get(a) or 0)
        if not h.get("ad") and o.get("ad"):
            h["ad"] = o["ad"]
        kodlar = {k for k in str(h.get("musteri_kodu") or "").split(", ") if k}
        kodlar |= {k for k in str(o.get("musteri_kodu") or "").split(", ") if k}
        if hedef != ham:
            kodlar.add(ham)
        if kodlar:
            h["musteri_kodu"] = ", ".join(sorted(kodlar))
    return out, ozet


# ── Veritabanı ─────────────────────────────────────────────────────
def oku(cli=None):
    """(mikro_multikod satırları, {cari_kod: ünvan}). Sıralı okuma + kopya denetimi (satis.mikro_esitle.kopyasiz).
    Tablo yok / boş / okuma tutarsızsa ([], {})."""
    from satis.mikro_esitle import kopyasiz
    if cli is None:
        from kayranpm.database import get_client
        cli = get_client()
    try:
        satir = kopyasiz(cli.table(TABLO).select(KOLONLAR).order("mcod_guid").execute().data or [], "mcod_guid")
    except Exception:  # noqa: BLE001 — göç (48) uygulanmadıysa tablo yok / okuma tutarsız
        return [], {}
    if not satir:
        return [], {}
    unvan = {}
    for tablo, sira in (("mikro_cari_bakiye", ("cari_kod", "doviz")), ("mikro_cari_kart", ("cari_kod",))):
        try:                                       # cari kartı sonra: ünvanı bakiyedekini geçer
            q = cli.table(tablo).select("cari_kod,cari_unvan1")
            for k in sira:
                q = q.order(k)
            for r in q.execute().data or []:
                if _s(r.get("cari_kod")) and _s(r.get("cari_unvan1")):
                    unvan[_s(r.get("cari_kod"))] = _s(r.get("cari_unvan1"))
        except Exception:  # noqa: BLE001
            continue
    return satir, unvan


def yukleme_haritasi(cli=None):
    """Yükleme başına bir kez: {firma_anahtar: {müşteri kodu: stok kodu}}. Okunamazsa {} (eski davranış)."""
    try:
        satir, unvan = oku(cli)
        return harita_kur(satir, unvan) if satir else {}
    except Exception:  # noqa: BLE001
        return {}


def firma_esle(firma, agg, harita, baglam=None):
    """Yükleyicinin firma özeti için: (yeni özet, özet | None). Haritada bu firmanın rapordaki hiçbir kodu
    yoksa özet aynen döner (ek okuma yok). Kartlar, onaylı eşlemeler ve kanal kod haritası baglam'da
    yükleme başına bir kez okunur."""
    from shared.utils import sku_anahtar
    fh = (harita or {}).get(firma_anahtar(firma))
    if not fh or not any(sku_anahtar(h) in fh for h in agg or {}):
        return agg, None
    b = baglam if baglam is not None else {}
    if "kartlar" not in b:
        from kayranpm import database as D
        b["kartlar"] = D.get_urun_marka_kategori() or {}
        b["eslesme"] = {r.get("dis_kod"): r.get("kart_sku") for r in (D.get_sku_eslesme() or [])}
        try:
            b["kod_haritasi"] = D.kanal_kod_haritasi() or {}
        except Exception:  # noqa: BLE001
            b["kod_haritasi"] = {}
    from kayranpm.musteri_hesap import meta_hazirla
    meta = meta_hazirla([{"sku": h, "urun_adi": (o or {}).get("ad")} for h, o in agg.items()], b["kartlar"],
                        sku_fn=sku_anahtar, eslesme=b["eslesme"])
    return uygula(agg, fh, b["kartlar"], meta, b["kod_haritasi"])
