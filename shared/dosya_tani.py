# -*- coding: utf-8 -*-
"""Dosya kapısı · tanıma (Ekim 2026). Bırakılan Excel'in hangi yükleme türü olduğunu bulur.

Saf hesap: Streamlit yok, veritabanı yok, kayıt yok. Kurallar YENİ değil — her yükleme
ekranının kendi okuyucusunun aradığı başlıklar (satis._siparis_excel_oku, _parse_mikro_satislar,
iade_excel_oku, ithalat Excel'i, excel_yukle_g5f_depolar, hl_excel_parse, toplu mal kabul,
kampanya şablonu, ref / alınan destek, gider_tablosu_parse, aktif_excel.parse_*, ödeme ve çek
listesi). Okuyucunun okuyamayacağı dosya "kesin" sayılmaz; tanınmayan dosya tahminle hiçbir
türe bağlanmaz.

tani(ad, veri) → [{"tur", "guven": "kesin"|"olasi", "gerekce"}], kesinler önce.
"""
from io import BytesIO

KESIN = "kesin"
OLASI = "olasi"
# Konumsal okuyucular (ödeme / çek listesi) tüm dosyayı okur: büyük dosyada çalıştırılmaz
KONUMSAL_SINIR = 2 * 1024 * 1024

AYLAR = ("OCAK", "ŞUBAT", "MART", "NİSAN", "MAYIS", "HAZİRAN", "TEMMUZ", "AĞUSTOS", "EYLÜL",
         "EKİM", "KASIM", "ARALIK")
# Haftalık müşteri dosyası: sekme adındaki firma işaretleri (kayranpm.excel_islemler._HSS_FIRMA_TOKEN)
HSS_FIRMA = ("ITOPYA", "EERA", "VATAN", "HEPSIBURADA", "HB", "MONDAY", "KANAL", "DIGER")


def norm(s):
    """Türkçe duyarsız, tek boşluklu küçük harf (kayranacc.aktif_excel._norm ile aynı)."""
    s = str("" if s is None else s).strip()
    for a, b in (("İ", "i"), ("I", "ı"), ("ı", "i"), ("Ş", "s"), ("ş", "s"), ("Ğ", "g"), ("ğ", "g"),
                 ("Ü", "u"), ("ü", "u"), ("Ö", "o"), ("ö", "o"), ("Ç", "c"), ("ç", "c")):
        s = s.replace(a, b)
    s = s.lower().replace("i̇", "i")
    return " ".join(s.split())


def _tr_ust(s):
    """kayranpm.excel_islemler.tr_upper ile aynı (G5F başlıkları böyle karşılaştırılır)."""
    return (str(s).strip().upper().replace("İ", "I").replace("Ğ", "G").replace("Ü", "U")
            .replace("Ş", "S").replace("Ç", "C").replace("Ö", "O"))


def _hucre(v):
    try:
        import pandas as pd
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ""
    except Exception:  # noqa: BLE001
        pass
    return str(v).strip()


def sayfalari_oku(veri, ad="", satir=20):
    """{sayfa adı: [[hücre metni, …], …]} — her sayfanın yalnız ilk `satir` satırı.
    Okunamazsa (bozuk / şifreli / desteklenmeyen biçim) None."""
    import pandas as pd
    motor = "xlrd" if str(ad).lower().endswith(".xls") else None
    try:
        xls = pd.ExcelFile(BytesIO(veri), engine=motor)
    except Exception:  # noqa: BLE001
        return None
    out = {}
    for sn in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=sn, header=None, nrows=satir)
        except Exception:  # noqa: BLE001
            out[str(sn)] = []
            continue
        out[str(sn)] = [[_hucre(v) for v in r] for r in df.values.tolist()]
    return out


def _bas(sayfa):
    """Sayfanın ilk satırı (okuyucuların çoğu başlığı 1. satırdan alır)."""
    return [h for h in (sayfa[0] if sayfa else []) if h]


def _ilk(sayfalar):
    return next(iter(sayfalar.values()), []) if sayfalar else []


# ── Tür kuralları: her biri (sayfalar, veri, ad) → (guven, gerekce) ya da None ──
def _vatan(s, *_):
    for sn, sy in s.items():
        b = set(_bas(sy))
        if {"Sipariş Numarası", "Stok Kodu", "Birim Fiyat", "Miktar"} <= b:
            return KESIN, "Sipariş Numarası, Stok Kodu, Birim Fiyat, Miktar sütunları"
    return None


def _itopya(s, *_):
    for sn, sy in s.items():
        b = set(_bas(sy))
        if {"STOKKODU", "SONALFIYAT", "MIKTAR"} <= b:
            return KESIN, "STOKKODU, SONALFIYAT, MIKTAR sütunları"
    return None


def _mikro(s, *_):
    b = set(_bas(_ilk(s)))
    if {"Fatura no", "Tarih", "Cari adı", "Hesap kodu", "Hesap ismi", "Mik", "Net Br.fy."} <= b:
        return KESIN, "Fatura no, Cari adı, Hesap kodu, Mik, Net Br.fy. sütunları"
    return None


def _iade(s, *_):
    # Okuyucu (iade_excel_oku) iki tarafı da str.lower() ile karşılaştırır ("İ" → "i̇"); aynısı
    b = {h.lower() for h in _bas(_ilk(s))}
    if ({"Stok kodu".lower(), "SKU".lower()} & b) and ({"İade miktar".lower(), "İade miktarı".lower()} & b):
        return KESIN, "Stok kodu ve İade miktar sütunları"
    return None


_ITH = {"ithalat takip no": "takip_no", "siparis tarihi": "tarih", "siparis no": "dosya_no",
        "belge no": "pi_no", "cari hesap adi": "tedarikci", "stok kodu": "sku", "stok ismi": "urun_adi",
        "miktar": "adet", "net fiyat": "net_fiyat", "birim fiyat": "birim_fiyat", "doviz": "doviz"}


def _ithalat(s, *_):
    alan = {_ITH.get(norm(h)) for h in _bas(_ilk(s))} - {None}
    if {"sku", "adet"} <= alan and alan & {"pi_no", "dosya_no"} and alan & {"net_fiyat", "birim_fiyat"}:
        return KESIN, "Stok kodu, Miktar, Belge / Sipariş no, Net fiyat sütunları"
    return None


def _g5f(s, *_):
    b = {_tr_ust(h) for h in _bas(_ilk(s))}
    depo = b & {"DEPO ADI", "DEPO", "DEPO ISMI", "AMBAR"}
    sku = b & {"STOK KODU", "SKU", "KOD", "URUN KODU", "BARKOD"}
    mik = b & {"MIKTAR", "ADET", "STOK", "STOK MIKTARI"}
    if not (depo and sku and mik):
        return None
    # Sipariş / fatura dosyalarında da "Depo" sütunu olur (VATAN siparişi) — fiyatlı dosya sayım değildir
    if b & {"SIPARIS NUMARASI", "BIRIM FIYAT", "SONALFIYAT", "NET FIYAT", "FIYAT"}:
        return None
    gerekce = "Depo adı, Stok kodu, Miktar sütunları (fiyat sütunu yok)"
    return (KESIN if depo & {"DEPO ADI", "DEPO ISMI", "AMBAR"} else OLASI), gerekce


def _happylife(s, *_):
    for sn, sy in s.items():
        if {"SKU kodu", "Giriş tarihi", "Palet etiketi"} <= set(_bas(sy)):
            return KESIN, f"'{sn}' sayfasında SKU kodu, Giriş tarihi, Palet etiketi sütunları"
    return None


def _mal_kabul(s, *_):
    b = {h.lower() for h in _bas(_ilk(s))}
    if {"stok kodu", "seri no", "arıza"} <= b:
        return KESIN, "Stok Kodu, Seri No, Arıza sütunları"
    return None


def _kampanya(s, *_):
    b = {norm(h) for h in _bas(_ilk(s))}
    if "stok kodu" in b and ({"rebate", "sellout", "spiff"} & b):
        return KESIN, "Stok kodu ve Rebate / Sellout / Spiff sütunları"
    return None


def _ref(s, *_):
    b = [norm(h) for h in _bas(_ilk(s))]
    if any("ref" in h for h in b) and any(k in h for h in b for k in ("tutar", "doviz", "numara")):
        return KESIN, "Ref ve tutar / döviz sütunları"
    return None


def _destek(s, *_):
    b = [norm(h) for h in _bas(_ilk(s))]
    if (any("firma" in h or "marka" in h for h in b) and any("donem" in h or h == "ay" for h in b)
            and any("tutar" in h for h in b)):
        return KESIN, "Firma, Dönem, Tutar sütunları"
    return None


def _gider(s, *_):
    for sn, sy in s.items():
        for r in sy[:15]:
            ust = {h.replace("i", "İ").replace("ı", "I").upper() for h in r if h}
            if len(ust & set(AYLAR)) >= 3:
                if any("KATEGORİ" in h or "KATEGORI" in h or "KALEM" in h or "GİDER" in h for h in ust):
                    return KESIN, "Ocak…Aralık başlıkları ve Kategori sütunu"
                return OLASI, "Ocak…Aralık başlıkları"
    return None


def _haftalik(s, *_):
    stoklu = [sn for sn in s if "STOK" in _tr_ust(sn) or "SATIS" in _tr_ust(sn)]
    if not stoklu:
        return None
    if any(t in _tr_ust(sn) for sn in stoklu for t in HSS_FIRMA):
        return KESIN, "sayfa adlarında firma + STOK / SATIŞ (" + ", ".join(stoklu[:4]) + ")"
    return OLASI, "sayfa adlarında STOK / SATIŞ (" + ", ".join(stoklu[:4]) + ")"


def _aktif_cari(s, *_):
    for r in _ilk(s)[:8]:
        n = [norm(h) for h in r]
        if any("doviz" in h for h in n) and any("bakiye" in h for h in n):
            return KESIN, "Döviz ve Bakiye sütunları"
    return None


def _aktif_ithalat(s, *_):
    sy = _ilk(s)
    if not any("odenen" in norm(h) for r in sy[:8] for h in r):
        return None
    if any(r and "toplam" in norm(r[0]) for r in sy):
        return KESIN, "Ödenen başlığı ve TOPLAM satırı"
    return OLASI, "Ödenen başlığı"


def _aktif_stok(s, *_):
    sy = _ilk(s)
    if len(sy) > 1 and any("TOPLAM TUTAR" in h.upper() for h in sy[1]):
        return KESIN, "2. satırda TOPLAM TUTAR blokları"
    return None


def _odeme(s, veri, ad):
    if len(veri) > KONUMSAL_SINIR:
        return None
    try:
        from kayranacc.excel_islemler import excel_yukle_odeme_listesi
        _h, odemeler, _e = excel_yukle_odeme_listesi(veri)
    except Exception:  # noqa: BLE001
        return None
    if not odemeler:
        return None
    sy = _ilk(s)
    b = {norm(h) for h in (sy[2] if len(sy) > 2 else [])}
    if {"firma", "vade"} <= b:
        return KESIN, f"başlıksız düzen: 3. satırda FİRMA / VADE, {len(odemeler)} ödeme satırı"
    return OLASI, f"başlıksız düzen: A1'de hafta adı, {len(odemeler)} vadeli ödeme satırı"


def _cek(s, veri, ad):
    if len(veri) > KONUMSAL_SINIR:
        return None
    try:
        from kayranacc.excel_islemler import excel_yukle_cek_listesi
        tl, usd = excel_yukle_cek_listesi(veri)[:2]
    except Exception:  # noqa: BLE001
        return None
    n = len(tl or []) + len(usd or [])
    if not n:
        return None
    metin = " ".join(norm(h) for r in _ilk(s)[:10] for h in r)
    if "cek no" in metin or "meblag" in metin:
        return KESIN, f"Çek No / Meblağ başlıkları, {n} çek satırı"
    return OLASI, f"başlıksız düzen: A sütununda sıra no, {n} çek satırı"


# Sıra önemlidir: önce kendine özgü başlıklar, en son yapıdan tanınanlar
KURALLAR = [
    ("siparis_vatan", _vatan), ("siparis_itopya", _itopya), ("mikro_fatura", _mikro),
    ("iade_excel", _iade), ("ithalat_rapor", _ithalat), ("happylife", _happylife),
    ("toplu_mal_kabul", _mal_kabul), ("kampanya_sablon", _kampanya), ("g5f_sayim", _g5f),
    ("ref_excel", _ref), ("alinan_destek", _destek), ("gider_tablosu", _gider),
    ("aktif_cari", _aktif_cari), ("aktif_ithalat", _aktif_ithalat), ("aktif_stok", _aktif_stok),
    ("musteri_haftalik", _haftalik), ("odeme_listesi", _odeme), ("cek_listesi", _cek),
]
_KONUMSAL = {"odeme_listesi", "cek_listesi"}


def tani(ad, veri):
    """Bırakılan dosyanın olası türleri, kesinler önce. Okunamazsa [{"tur": None, …}]."""
    sayfalar = sayfalari_oku(veri, ad)
    if sayfalar is None:
        return [{"tur": None, "guven": None, "gerekce": "Excel olarak açılamadı (bozuk, şifreli ya da "
                 "Excel dışı bir dosya)."}]
    sonuc = []
    for tur, kural in KURALLAR:
        if tur in _KONUMSAL and any(x["guven"] == KESIN for x in sonuc):
            continue            # başlıktan kesin tanındıysa tüm dosyayı yeniden okuma
        try:
            r = kural(sayfalar, veri, ad)
        except Exception:  # noqa: BLE001 — bir kuralın hatası diğerlerini durdurmasın
            r = None
        if r:
            sonuc.append({"tur": tur, "guven": r[0], "gerekce": r[1]})
    # Kendine özgü başlıklarla KESİN tanınan bir tür varsa zayıf (olası) eşleşmeler gösterilmez:
    # ör. Happy Life dosyasının "G5F_Stok" sayfa adı haftalık müşteri dosyasına da benzer.
    if any(x["guven"] == KESIN for x in sonuc):
        sonuc = [x for x in sonuc if x["guven"] == KESIN]
    return sonuc


def sayfa_adlari(ad, veri):
    s = sayfalari_oku(veri, ad)
    return list(s) if s else []
