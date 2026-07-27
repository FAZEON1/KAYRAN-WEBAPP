"""Toplam Aktifler ekranı — Excel okuyucuları (sağlam sürüm).

NEDEN AYRI DOSYA: Eski okuyucular sütunları SABİT KONUMDAN okuyordu
(örn. bakiye = 7. sütun). Mikro raporu bir sütun eksik/fazla üretince
okuyucu ya patlıyor ya da yanlış sütunu topluyordu — 27.07.2026 cari
dosyasında tam olarak bu oldu (dosyada 6 sütun var, kod 7.'yi istiyordu →
IndexError → yükleme sessizce başarısız).

ÇÖZÜM: sütunlar artık BAŞLIK ADINDAN bulunuyor. Mikro sütun ekler/çıkarır,
sırasını değiştirir — okuyucu yine doğru sütunu bulur. Başlık hiç
bulunamazsa anlaşılır bir hata mesajı döner (sessiz başarısızlık yok).

Her okuyucu (deger, detay) döndürür; detay kullanıcıya "ne okudum" diye
gösterilir ki yüklemenin gerçekten çalıştığı gözle doğrulanabilsin.
"""
from io import BytesIO


class ExcelBicimHatasi(Exception):
    """Dosya okundu ama beklenen sütunlar/veri bulunamadı."""


def _oku(file_bytes):
    import pandas as pd
    try:
        return pd.read_excel(BytesIO(file_bytes), header=None)
    except Exception as e:
        raise ExcelBicimHatasi(
            f"Dosya açılamadı ({type(e).__name__}). Mikro'dan .xls/.xlsx olarak "
            "yeniden dışa aktarıp tekrar dene."
        ) from e


def _norm(s):
    """Türkçe duyarsız, boşluksuz karşılaştırma anahtarı."""
    s = str(s or "").strip().lower()
    for a, b in (("ı", "i"), ("İ", "i"), ("ş", "s"), ("ğ", "g"),
                 ("ü", "u"), ("ö", "o"), ("ç", "c")):
        s = s.replace(a, b)
    return " ".join(s.split())


def _baslik_satiri_bul(df, aranan_kaliplar, tara=8):
    """İlk `tara` satırda, `aranan_kaliplar`ın hepsini içeren başlık satırını bulur.
    Döner: (satir_index, {kalıp: sütun_index}) — bulunamazsa (None, {})."""
    import pandas as pd
    for r in range(min(tara, len(df))):
        bulunan = {}
        for c in range(df.shape[1]):
            h = df.iloc[r, c]
            if pd.isna(h):
                continue
            hn = _norm(h)
            for kalip in aranan_kaliplar:
                if kalip in bulunan:
                    continue
                if kalip in hn:
                    bulunan[kalip] = c
        if len(bulunan) == len(aranan_kaliplar):
            return r, bulunan
    return None, {}


def _sayi(v):
    import pandas as pd
    if pd.isna(v):
        return None
    if isinstance(v, str):
        v = v.replace(".", "").replace(",", ".").strip()
        if not v:
            return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ════════════════════════════════════════════════════════════════
# 3) CARİ ALACAKLAR
# ════════════════════════════════════════════════════════════════
def parse_cari(file_bytes):
    """Cari listesinden borç/alacak toplamlarını çıkarır.

    Bakiye NEGATİF → biz borçluyuz (borc), POZİTİF → bize borçlular (alacak).
    Döner: (sonuc_dict, detay_dict)
    """
    import pandas as pd
    df = _oku(file_bytes)

    bas_satir, kol = _baslik_satiri_bul(df, ["doviz", "bakiye"])
    if bas_satir is None:
        raise ExcelBicimHatasi(
            "'Döviz' ve 'bakiye' başlıklı sütunlar bulunamadı. Bu dosya cari "
            "alacaklar listesi olmayabilir — Mikro → Cari → Alacaklar listesini "
            "kontrol et."
        )
    c_doviz, c_bakiye = kol["doviz"], kol["bakiye"]

    # Hesap adı / kodu sütunları (isim çıkarımı ve satır geçerliliği için)
    _, kol_ad = _baslik_satiri_bul(df, ["hesap adi"])
    c_ad = kol_ad.get("hesap adi")
    _, kol_kod = _baslik_satiri_bul(df, ["hesap kodu"])
    c_kod = kol_kod.get("hesap kodu")

    sonuc = {"borc": {"usd": 0.0, "tl": 0.0, "eur": 0.0},
             "alacak": {"usd": 0.0, "tl": 0.0, "eur": 0.0}}
    isimler, satir_sayisi, atlanan_doviz = [], 0, set()

    for i in range(bas_satir + 1, len(df)):
        # Alt toplam satırlarını ele: hesap kodu boşsa o satır tekrar/ara toplamdır
        if c_kod is not None and pd.isna(df.iloc[i, c_kod]):
            continue
        bak = _sayi(df.iloc[i, c_bakiye])
        if bak is None or bak == 0:
            continue
        d = _norm(df.iloc[i, c_doviz]).upper()
        yon = "borc" if bak < 0 else "alacak"
        if "USD" in d or "DOLAR" in d:
            sonuc[yon]["usd"] += abs(bak)
        elif d in ("TL", "TRY") or "TL" in d or "LIRA" in d:
            sonuc[yon]["tl"] += abs(bak)
        elif "EUR" in d or "AVRO" in d:
            sonuc[yon]["eur"] += abs(bak)
        else:
            if d:
                atlanan_doviz.add(d)
            continue
        satir_sayisi += 1
        if c_ad is not None:
            ad = df.iloc[i, c_ad]
            if pd.notna(ad):
                s = str(ad).strip()
                if s and s not in isimler:
                    isimler.append(s)

    if satir_sayisi == 0:
        raise ExcelBicimHatasi(
            "Sütunlar bulundu ama hiç bakiyeli satır okunamadı — dosya boş "
            "olabilir ya da tüm bakiyeler sıfır."
        )

    detay = {
        "satir": satir_sayisi,
        "isimler": isimler,
        "ozet": [
            f"Borç: USD {sonuc['borc']['usd']:,.0f} · TL {sonuc['borc']['tl']:,.0f} · EUR {sonuc['borc']['eur']:,.0f}",
            f"Alacak: USD {sonuc['alacak']['usd']:,.0f} · TL {sonuc['alacak']['tl']:,.0f} · EUR {sonuc['alacak']['eur']:,.0f}",
        ],
        "uyari": (f"Tanınmayan döviz kodu atlandı: {', '.join(sorted(atlanan_doviz))}"
                  if atlanan_doviz else ""),
    }
    return sonuc, detay


# ════════════════════════════════════════════════════════════════
# 2) İTHALAT ÖDEME TAKİP
# ════════════════════════════════════════════════════════════════
def parse_ithalat(file_bytes):
    """'Ödenen / USD' toplamını çıkarır. Döner: (toplam, detay)."""
    import pandas as pd
    df = _oku(file_bytes)

    # "ödenen" başlığını ara (USD kelimesi ayrı satırda olabilir)
    c_odenen = bas_satir = None
    for r in range(min(8, len(df))):
        for c in range(df.shape[1]):
            h = df.iloc[r, c]
            if pd.notna(h) and "odenen" in _norm(h):
                bas_satir, c_odenen = r, c
                break
        if c_odenen is not None:
            break
    if c_odenen is None:
        raise ExcelBicimHatasi(
            "'Ödenen' başlıklı sütun bulunamadı — bu dosya ithalat ödeme takip "
            "raporu olmayabilir."
        )

    # Önce TOPLAM satırı
    for i in range(len(df)):
        ilk = df.iloc[i, 0]
        if pd.notna(ilk) and "toplam" in _norm(ilk):
            v = _sayi(df.iloc[i, c_odenen])
            if v is not None:
                return v, {"kaynak": "TOPLAM satırı", "satir": 1,
                           "ozet": [f"Ödenen: ${v:,.0f}"], "uyari": ""}

    # TOPLAM yoksa elle topla
    toplam, adet = 0.0, 0
    for i in range(bas_satir + 1, len(df)):
        v = _sayi(df.iloc[i, c_odenen])
        if v is not None:
            toplam += v
            adet += 1
    if adet == 0:
        raise ExcelBicimHatasi("'Ödenen' sütunu bulundu ama hiç sayı okunamadı.")
    return toplam, {"kaynak": f"{adet} satır toplandı", "satir": adet,
                    "ozet": [f"Ödenen: ${toplam:,.0f}"], "uyari": ""}


# ════════════════════════════════════════════════════════════════
# 1) STOK DEĞERİ
# ════════════════════════════════════════════════════════════════
def parse_stok(file_bytes, eski_parser):
    """Stok raporu — mevcut (çalışan) okuyucuyu sarmalar, sonucu doğrular.

    Stok raporunun yapısı firma bloklarından oluştuğu için mevcut ayrıştırma
    mantığı korunur; buradaki katkı, sonucun boş/anlamsız gelmesi durumunda
    sessiz geçmek yerine anlaşılır hata vermek.
    """
    try:
        usd_stok, pazaryerleri = eski_parser(file_bytes)
    except Exception as e:
        raise ExcelBicimHatasi(
            f"Stok raporu okunamadı ({type(e).__name__}). Dosyanın Mikro stok "
            "değeri raporu olduğundan emin ol."
        ) from e
    if not usd_stok and not pazaryerleri:
        raise ExcelBicimHatasi(
            "Dosya okundu ama stok değeri bulunamadı — 'TOPLAM TUTAR' başlıklı "
            "sütun içeren bir rapor bekleniyor."
        )
    _ham = float(usd_stok or 0)
    ozet = [
        f"Ham stok değeri (dosyadan okunan): ${_ham:,.0f}",
        f"**KDV dahil (×1.20) → Toplam Aktifler'e giren: ${_ham * 1.20:,.0f}**",
    ]
    if pazaryerleri:
        ozet.append("Firmalar: " + " · ".join(
            f"{k} ${float(v):,.0f}" for k, v in list(pazaryerleri.items())[:4]))
    return (usd_stok, pazaryerleri), {
        "satir": len(pazaryerleri or {}), "ozet": ozet, "uyari": ""}
