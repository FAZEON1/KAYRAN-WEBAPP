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
from shared.tasarim import tr_sayi  # TR sayı biçimi (1.234,56)
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
            f"Borç: USD {tr_sayi(sonuc['borc']['usd'])} · TL {tr_sayi(sonuc['borc']['tl'])} · EUR {tr_sayi(sonuc['borc']['eur'])}",
            f"Alacak: USD {tr_sayi(sonuc['alacak']['usd'])} · TL {tr_sayi(sonuc['alacak']['tl'])} · EUR {tr_sayi(sonuc['alacak']['eur'])}",
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
                           "ozet": [f"Ödenen: ${tr_sayi(v)}"], "uyari": ""}

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
                    "ozet": [f"Ödenen: ${tr_sayi(toplam)}"], "uyari": ""}


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
        f"Ham stok değeri (dosyadan okunan): ${tr_sayi(_ham)}",
        f"**KDV dahil (×1.20) → Toplam Aktifler'e giren: ${tr_sayi(_ham * 1.20)}**",
    ]
    if pazaryerleri:
        ozet.append("Firmalar: " + " · ".join(
            f"{k} ${tr_sayi(float(v))}" for k, v in list(pazaryerleri.items())[:4]))
    return (usd_stok, pazaryerleri), {
        "satir": len(pazaryerleri or {}), "ozet": ozet, "uyari": ""}


# ── Toplam Aktifler kaydı (Ekim 2026: sayfadan Dosya kapısına taşındı) ──
def parse_stok_excel(file_bytes):
    """
    Stok Excel'inden değerleri çıkar.
    ÖNEMLİ: Excel'in son satırlarında zaten toplam satırı var. Onu kullan.
    Yoksa elle topla ama "TOPLAM" satırlarını atla.
    """
    import pandas as pd
    from io import BytesIO
    df = pd.read_excel(BytesIO(file_bytes), header=None)

    # ─── Sütun 4 = USD SON DURUM STOK DEĞERİ ───
    # Önce alt taraftaki TOPLAM satırını bul (genelde son ~3 satırda)
    usd_stok = 0.0
    toplam_bulundu = False
    for i in range(len(df) - 1, max(2, len(df) - 10), -1):
        v = df.iloc[i, 4]
        if pd.notna(v):
            try:
                val = float(v)
                # Toplam satırı genelde stok kodu boş ama büyük tutar var
                stok_kodu = df.iloc[i, 0]
                if pd.isna(stok_kodu) or str(stok_kodu).strip() == "" or "TOPLAM" in str(stok_kodu).upper():
                    usd_stok = val
                    toplam_bulundu = True
                    break
            except (ValueError, TypeError):
                continue

    # Toplam yoksa elle topla (header'ları atla, son toplam satırlarını da atla)
    if not toplam_bulundu:
        for i in range(2, len(df)):
            stok_kodu = df.iloc[i, 0]
            if pd.isna(stok_kodu) or str(stok_kodu).strip() == "":
                continue  # boş satır = muhtemel toplam
            if "TOPLAM" in str(stok_kodu).upper():
                continue
            v = df.iloc[i, 4]
            if pd.notna(v):
                try:
                    usd_stok += float(v)
                except (ValueError, TypeError):
                    pass

    # ─── Pazaryeri firmaları: "TOPLAM TUTAR" sütunlarını bul ───
    # ÖNEMLİ: Excel'de her pazaryerinin altında bir ALT TOPLAM satırı var
    # (firma kodu boş, ama toplam değer dolu). Bunları atlamak için
    # firma kodu sütununu (col_idx - 3) kontrol ediyoruz.
    pazaryerleri = {}
    try:
        for col_idx in range(df.shape[1]):
            header = df.iloc[1, col_idx]
            if pd.notna(header) and isinstance(header, str) and "TOPLAM TUTAR" in header.upper():
                # Firma adı için geriye doğru tara
                firma_adi = "Bilinmeyen"
                blacklist = ["STOK", "SATIŞ", "FIYAT", "FİYAT", "MIKT", "MİKT", "ADET", "İADE", "TOPLAM"]
                firma_kod_col = None  # firma kodu sütunu (header'da firma adı olan)
                for back in range(1, 5):
                    check_col = col_idx - back
                    if check_col < 0:
                        break
                    candidate = df.iloc[1, check_col]
                    if pd.notna(candidate) and isinstance(candidate, str):
                        cand_str = candidate.strip()
                        cand_upper = cand_str.upper()
                        if cand_str and not any(bl in cand_upper for bl in blacklist):
                            firma_adi = cand_str
                            firma_kod_col = check_col  # ← bu sütun firma stok kodu içerir
                            break

                # Toplama yaparken firma kodu sütunu BOŞ olan satırları atla (alt toplam = duplicate)
                toplam = 0.0
                for i in range(2, len(df)):
                    v = df.iloc[i, col_idx]
                    if pd.notna(v):
                        # Firma kodu sütunu kontrolü
                        if firma_kod_col is not None:
                            kod = df.iloc[i, firma_kod_col]
                            if pd.isna(kod) or str(kod).strip() == "":
                                continue  # alt toplam satırı, atla
                        try:
                            toplam += float(v)
                        except (ValueError, TypeError):
                            pass
                if firma_adi and firma_adi != "Bilinmeyen":
                    pazaryerleri[firma_adi] = toplam
    except Exception:
        pass

    return usd_stok, pazaryerleri

def _cari_isimleri_cikar(file_bytes):
    """Cari Excel'inden firma (Hesap adı) listesini çıkarır — Satış kanalları
    ve Ref No 'Yeni Firma Ekle' listesi için.

    ESKİ HATA: sütun 2 sabit okunuyordu. Mikro'nun yeni raporunda sütun 2
    'Döviz' olduğu için listeye firma adı yerine EUR/TL/USD düşüyordu.
    Artık sütun BAŞLIK ADINDAN bulunur (aktif_excel ile aynı yöntem)."""
    try:
        from kayranacc.aktif_excel import parse_cari as _pc
        _, _detay = _pc(file_bytes)
        return list(_detay.get("isimler") or [])
    except Exception:
        pass
    # Yedek yol: başlığı elle ara
    import pandas as pd
    from io import BytesIO
    try:
        df = pd.read_excel(BytesIO(file_bytes), header=None)
    except Exception:
        return []
    _c = None
    for r in range(min(8, len(df))):
        for c in range(df.shape[1]):
            v = df.iloc[r, c]
            if pd.notna(v) and "hesap ad" in str(v).strip().lower().replace("ı", "i"):
                _c = c
                break
        if _c is not None:
            break
    if _c is None:
        return []
    isimler = []
    for i in range(len(df)):
        ad = df.iloc[i, _c]
        if pd.notna(ad):
            s = str(ad).strip()
            if (s and s.lower() not in ("nan", "hesap adı", "hesap adi")
                    and s not in isimler):
                isimler.append(s)
    return isimler


def aktif_kaydet(tip, deger, ham, kullanici, detay=None):
    """Toplam Aktifler: okunan değeri paylaşımlı kayda yazar. kullanici = son yükleyen (gerçek
    kullanıcı; eskiden hep 'ortak' yazılıyordu). Döner: True / False (yazılamadı)."""
    from kayranacc import database as _db
    if tip == "stok":
        usd_v, pazar = deger
        return bool(_db.aktif_excel_kaydet(kullanici, "stok", [float(usd_v), pazar]))
    if tip == "ithalat":
        return bool(_db.aktif_excel_kaydet(kullanici, "ithalat", float(deger)))
    ok = bool(_db.aktif_excel_kaydet(kullanici, "cari", deger))
    if ok:
        try:  # cari isimleri — Satış kanalları ve Ref No firma listesi için
            _isim = (detay or {}).get("isimler") or _cari_isimleri_cikar(ham)
            if _isim:
                _db.aktif_excel_kaydet(kullanici, "cari_isimler", _isim)
        except Exception:
            pass
    return ok
