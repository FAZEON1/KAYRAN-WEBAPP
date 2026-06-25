import pandas as pd
from datetime import datetime
from .database import upsert_urun, upsert_firma_stok, get_client, upsert_yoldaki_urun, upsert_g5f_stok
import math

def safe_float(val, default=0.0):
    """NaN ve None değerlerini güvenli şekilde float'a çevirir."""
    try:
        v = float(val or default)
        return default if (math.isnan(v) or math.isinf(v)) else v
    except:
        return default

def safe_int(val, default=0):
    """NaN ve None değerlerini güvenli şekilde int'e çevirir."""
    try:
        v = float(val or default)
        if math.isnan(v) or math.isinf(v):
            return default
        return int(v)
    except:
        return default

def safe_str(val, default=""):
    """NaN ve None değerlerini güvenli şekilde str'ye çevirir."""
    if val is None:
        return default
    s = str(val).strip()
    return default if s.lower() in ("nan", "none", "nat") else s


def tr_upper(s):
    """Türkçe karakterleri de doğru büyüten upper fonksiyonu"""
    return str(s).strip().upper().replace("İ","I").replace("Ğ","G").replace("Ü","U").replace("Ş","S").replace("Ç","C").replace("Ö","O")

def normalize_sku(sku):
    """Fazeon/FAZEON gibi marka prefix'lerini SKU'dan temizler ve büyük harfe çevirir."""
    sku = str(sku).strip()
    for prefix in ["FAZEON ", "Fazeon ", "fazeon "]:
        if sku.startswith(prefix):
            sku = sku[len(prefix):]
            break
    return sku.strip().upper()


FIRMA_LISTESI = ["ITOPYA", "HB", "VATAN", "MONDAY", "KANAL", "DIGER"]

def excel_yukle_ana_stok(dosya_yolu):
    """
    Ana stok sekmesini yükler.
    Beklenen kolonlar: SKU, Ürün Adı, Kategori, Marka, Fiyat, Özellikler, Bizim Stok, Trendyol Stok
    """
    try:
        df = pd.read_excel(dosya_yolu, sheet_name=0)  # İlk sekmeyi oku (G5F STOK)
        df.columns = [tr_upper(c) for c in df.columns]
        
        kolon_esleme = {
            "SKU": ["SKU", "KOD", "URUN KODU", "BARKOD"],
            "URUN_ADI": ["URUN ADI", "AD", "URUN", "PRODUCT"],
            "KATEGORI": ["KATEGORI", "CATEGORY"],
            "MARKA": ["MARKA", "BRAND"],
            "SATIS_FIYATI": ["SATIS FIYATI ($)", "SATIS FIYATI", "FIYAT", "PRICE"],
            "HEDEF_KAR": ["HEDEF KAR MARJI (%)", "HEDEF KAR MARJI", "HEDEF KAR", "KAR MARJI", "MARGIN"],
            "BIZIM_STOK": ["BIZIM STOK", "DEPO STOK", "STOK", "G5F STOK"],
            "YOLDAKI_MIKTAR": ["YOLDAKI MIKTAR", "YOL MIKTAR", "YOLDA"],
            "VARIS_TARIHI": ["TAHMINI VARIS TARIHI", "VARIS TARIHI", "TAHMINI VARIS", "ETA"],
            "YOLDAKI_TEDARIKCI": ["YOLDAKI TEDARIKCI", "TEDARIKCI"],
        }
        
        kolon_map = {}
        for hedef, alternatifler in kolon_esleme.items():
            for alt in alternatifler:
                if tr_upper(alt) in df.columns:
                    kolon_map[hedef] = tr_upper(alt)
                    break
        
        if "SKU" not in kolon_map:
            return False, "SKU/Ürün Kodu kolonu bulunamadı."
        if "URUN_ADI" not in kolon_map:
            return False, "Ürün Adı kolonu bulunamadı."
        
        basarili = 0
        hatali = 0
        hata_mesajlari = []
        for _, row in df.iterrows():
            try:
                sku = str(row[kolon_map["SKU"]]).strip()
                if not sku or sku == "nan":
                    continue
                urun_adi = str(row.get(kolon_map.get("URUN_ADI", ""), "")).strip()
                kategori = str(row.get(kolon_map.get("KATEGORI", ""), "")).strip() if "KATEGORI" in kolon_map else ""
                marka = str(row.get(kolon_map.get("MARKA", ""), "")).strip() if "MARKA" in kolon_map else ""
                ozellikler = str(row.get(kolon_map.get("OZELLIKLER", ""), "")).strip() if "OZELLIKLER" in kolon_map else ""
                satis_fiyati = safe_float(row.get(kolon_map.get("SATIS_FIYATI", ""), 0))
                hedef_kar = safe_float(row.get(kolon_map.get("HEDEF_KAR", ""), 0))
                bizim_stok = safe_int(row.get(kolon_map.get("BIZIM_STOK", ""), 0))
                yoldaki_miktar = safe_int(row.get(kolon_map.get("YOLDAKI_MIKTAR", ""), 0))
                varis_tarihi = safe_str(row.get(kolon_map.get("VARIS_TARIHI", ""), ""))
                yoldaki_tedarikci = safe_str(row.get(kolon_map.get("YOLDAKI_TEDARIKCI", ""), ""))
                kategori = safe_str(row.get(kolon_map.get("KATEGORI", ""), ""))
                marka = safe_str(row.get(kolon_map.get("MARKA", ""), ""))

                upsert_urun(sku, urun_adi, kategori, marka, satis_fiyati, 0, hedef_kar, "", bizim_stok, 0)

                # Yoldaki veriyi de kaydet
                if yoldaki_miktar > 0 or varis_tarihi:
                    upsert_yoldaki_urun(sku, urun_adi, yoldaki_miktar, varis_tarihi)
                basarili += 1
            except Exception as e:
                hatali += 1
                hata_mesajlari.append(f"{sku}: {str(e)}")
        
        hata_detay = f" | Hatalar: {'; '.join(hata_mesajlari[:3])}" if hata_mesajlari else ""
        return True, f"{basarili} ürün başarıyla yüklendi. {hatali} satır atlandı.{hata_detay}"
    except Exception as e:
        return False, f"Dosya okunamadı: {str(e)}"


def excel_yukle_firma_stoklari(dosya_yolu):
    """
    Firma stok sekmelerini yükler.
    Her firma için ayrı sekme: ITOPYA, HB, VATAN, MONDAY, KANAL, DIGER
    Beklenen kolonlar: SKU, Ürün Adı, Stok Miktarı, Haftalık Satış
    """
    try:
        xl = pd.ExcelFile(dosya_yolu)
        mevcut_sekmeler = [s.strip().upper() for s in xl.sheet_names]
        
        sonuclar = []
        for firma in FIRMA_LISTESI:
            # Sekme adı eşleştirme (DİĞER -> DIGER vb.)
            eslesen_sekme = None
            for sekme in xl.sheet_names:
                if sekme.strip().upper().replace("İ", "I").replace("Ğ", "G").replace("Ü", "U").replace("Ş", "S").replace("Ç", "C").replace("Ö", "O") == firma.replace("İ", "I").replace("Ğ", "G").replace("Ü", "U").replace("Ş", "S").replace("Ç", "C").replace("Ö", "O"):
                    eslesen_sekme = sekme
                    break
                if firma in sekme.strip().upper():
                    eslesen_sekme = sekme
                    break
            
            if not eslesen_sekme:
                sonuclar.append(f"⚠️ {firma}: Sekme bulunamadı, atlandı.")
                continue
            
            df = pd.read_excel(dosya_yolu, sheet_name=eslesen_sekme)
            df.columns = [tr_upper(c) for c in df.columns]
            
            kolon_esleme = {
                "SKU": ["SKU", "KOD", "URUN KODU", "BARKOD"],
                "URUN_ADI": ["URUN ADI", "AD", "URUN"],
                "STOK": ["STOK MIKTARI", "STOK", "MEVCUT STOK", "ADET"],
                "SATIS": ["HAFTALIK SATIS", "SATIS", "SATIS ADEDI"],
            }
            
            kolon_map = {}
            for hedef, alternatifler in kolon_esleme.items():
                for alt in alternatifler:
                    if tr_upper(alt) in df.columns:
                        kolon_map[hedef] = tr_upper(alt)
                        break
            
            if "SKU" not in kolon_map:
                sonuclar.append(f"❌ {firma}: SKU kolonu bulunamadı.")
                continue
            
            basarili = 0
            for _, row in df.iterrows():
                try:
                    sku = normalize_sku(row[kolon_map["SKU"]])
                    if not sku or sku == "NAN":
                        continue
                    urun_adi = safe_str(row.get(kolon_map.get("URUN_ADI", ""), "")) if "URUN_ADI" in kolon_map else ""
                    stok = safe_int(row.get(kolon_map.get("STOK", ""), 0)) if "STOK" in kolon_map else 0
                    satis = safe_int(row.get(kolon_map.get("SATIS", ""), 0)) if "SATIS" in kolon_map else 0

                    # Eğer SKU urunler tablosunda yoksa otomatik ekle
                    _sb = get_client()
                    _mev = _sb.table("urunler").select("sku").eq("sku", sku).execute().data
                    if not _mev:
                        from datetime import date as _date
                        _sb.table("urunler").insert({
                            "sku": sku, "urun_adi": urun_adi or sku,
                            "kategori": "", "marka": "", "satis_fiyati": 0,
                            "alis_fiyati": 0, "hedef_kar_marji": 0, "ozellikler": "",
                            "bizim_stok": 0, "trendyol_stok": 0,
                            "guncelleme_tarihi": _date.today().isoformat(),
                        }).execute()

                    upsert_firma_stok(firma, sku, urun_adi, stok, satis)
                    basarili += 1
                except Exception as ex:
                    pass
            
            sonuclar.append(f"✅ {firma}: {basarili} ürün yüklendi.")
        
        return True, "\n".join(sonuclar)
    except Exception as e:
        return False, f"Dosya okunamadı: {str(e)}"


def excel_yukle_yoldaki_urunler(dosya_yolu):
    """
    Yoldaki ürünler sekmesini yükler.
    Beklenen kolonlar: SKU, Ürün Adı, Yoldaki Miktar, Tahmini Varış Tarihi
    """
    try:
        xl = pd.ExcelFile(dosya_yolu)
        eslesen_sekme = None
        for sekme in xl.sheet_names:
            s = sekme.strip().upper()
            if "YOLDAK" in s or "YOL" in s or "TRANSIT" in s or "SIPARIS" in s:
                eslesen_sekme = sekme
                break

        if not eslesen_sekme:
            return False, "❌ 'YOLDAKI' adında sekme bulunamadı."

        df = pd.read_excel(dosya_yolu, sheet_name=eslesen_sekme)
        df.columns = [str(c).strip().upper() for c in df.columns]

        kolon_esleme = {
            "SKU": ["SKU", "KOD", "ÜRÜN KODU", "URUN KODU"],
            "URUN_ADI": ["ÜRÜN ADI", "URUN ADI", "AD", "ÜRÜN"],
            "MIKTAR": ["YOLDAKI MIKTAR", "YOLDAKİ MİKTAR", "MİKTAR", "MIKTAR", "ADET", "SİPARİŞ MİKTARI"],
            "VARIS": ["TAHMİNİ VARIŞ", "TAHMINI VARIS", "VARIŞ TARİHİ", "VARIS TARIHI", "ETD", "ETA"],
        }

        kolon_map = {}
        for hedef, alternatifler in kolon_esleme.items():
            for alt in alternatifler:
                if tr_upper(alt) in df.columns:
                    kolon_map[hedef] = tr_upper(alt)
                    break

        if "SKU" not in kolon_map:
            return False, "❌ SKU kolonu bulunamadı."

        basarili = 0
        for _, row in df.iterrows():
            try:
                sku = str(row[kolon_map["SKU"]]).strip()
                if not sku or sku == "nan":
                    continue
                urun_adi = str(row.get(kolon_map.get("URUN_ADI", ""), "")).strip() if "URUN_ADI" in kolon_map else ""
                miktar = int(row.get(kolon_map.get("MIKTAR", ""), 0) or 0) if "MIKTAR" in kolon_map else 0
                varis = str(row.get(kolon_map.get("VARIS", ""), "")).strip() if "VARIS" in kolon_map else ""
                if varis == "nan":
                    varis = ""
                upsert_yoldaki_urun(sku, urun_adi, miktar, varis)
                basarili += 1
            except:
                pass

        return True, f"✅ Yoldaki ürünler: {basarili} satır yüklendi."
    except Exception as e:
        return False, f"Dosya okunamadı: {str(e)}"



def create_sample_excel_bytes():
    """Örnek Excel şablonunu bellekte oluşturur ve bytes döndürür (Streamlit Cloud için)"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from io import BytesIO

    wb = Workbook()

    ws1 = wb.active
    ws1.title = "G5F STOK"
    basliklar = ["SKU", "Ürün Adı", "Kategori", "Marka", "Satış Fiyatı ($)", "Hedef Kar Marjı (%)", "Bizim Stok", "Yoldaki Miktar", "Tahmini Varış Tarihi", "Yoldaki Tedarikçi"]
    for i, b in enumerate(basliklar, 1):
        cell = ws1.cell(row=1, column=i, value=b)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", start_color="1F4E79")
        cell.alignment = Alignment(horizontal="center")

    for row in [
        ["SKU001", "Samsung Galaxy S24", "Telefon", "Samsung", 980, 30, 50, 100, "2026-05-15", "ABC Elektronik"],
        ["SKU002", "iPhone 15", "Telefon", "Apple", 1500, 25, 20, 0, "", ""],
        ["SKU003", "Xiaomi Redmi Note 13", "Telefon", "Xiaomi", 340, 35, 80, 50, "2026-06-01", "XYZ İthalat"],
    ]:
        ws1.append(row)
    for col in ws1.columns:
        ws1.column_dimensions[col[0].column_letter].width = 18

    for firma in ["ITOPYA", "HB", "VATAN", "MONDAY", "KANAL", "DIGER"]:
        ws = wb.create_sheet(firma)
        for i, b in enumerate(["SKU", "Ürün Adı", "Stok Miktarı", "Haftalık Satış"], 1):
            cell = ws.cell(row=1, column=i, value=b)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", start_color="2E7D32")
            cell.alignment = Alignment(horizontal="center")
        for row in [["SKU001", "Samsung Galaxy S24", 10, 5], ["SKU002", "iPhone 15", 3, 2], ["SKU003", "Xiaomi Redmi Note 13", 25, 12]]:
            ws.append(row)
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = 18

    ws_yol = wb.create_sheet("YOLDAKI")
    for i, b in enumerate(["SKU", "Ürün Adı", "Yoldaki Miktar", "Tahmini Varış Tarihi"], 1):
        cell = ws_yol.cell(row=1, column=i, value=b)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", start_color="6A1B9A")
        cell.alignment = Alignment(horizontal="center")
    for row in [["SKU001", "Samsung Galaxy S24", 30, "2026-05-01"], ["SKU002", "iPhone 15", 10, "2026-04-25"]]:
        ws_yol.append(row)
    for col in ws_yol.columns:
        ws_yol.column_dimensions[col[0].column_letter].width = 22

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def create_sample_excel():
    """Örnek Excel şablonu oluşturur"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    
    wb = Workbook()
    
    # Ana Stok sekmesi
    ws1 = wb.active
    ws1.title = "G5F STOK"
    basliklar = ["SKU", "Ürün Adı", "Kategori", "Marka", "Satış Fiyatı ($)", "Hedef Kar Marjı (%)", "Bizim Stok", "Yoldaki Miktar", "Tahmini Varış Tarihi", "Yoldaki Tedarikçi"]
    for i, b in enumerate(basliklar, 1):
        cell = ws1.cell(row=1, column=i, value=b)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", start_color="1F4E79")
        cell.alignment = Alignment(horizontal="center")

    ornek_veri = [
        ["SKU001", "Samsung Galaxy S24", "Telefon", "Samsung", 980, 30, 50, 100, "2026-05-15", "ABC Elektronik"],
        ["SKU002", "iPhone 15", "Telefon", "Apple", 1500, 25, 20, 0, "", ""],
        ["SKU003", "Xiaomi Redmi Note 13", "Telefon", "Xiaomi", 340, 35, 80, 50, "2026-06-01", "XYZ İthalat"],
    ]
    for row in ornek_veri:
        ws1.append(row)
    for col in ws1.columns:
        ws1.column_dimensions[col[0].column_letter].width = 18
    
    # Firma sekmeleri
    firma_listesi_tr = ["ITOPYA", "HB", "VATAN", "MONDAY", "KANAL", "DIGER"]
    for firma in firma_listesi_tr:
        ws = wb.create_sheet(firma)
        firma_basliklar = ["SKU", "Ürün Adı", "Stok Miktarı", "Haftalık Satış"]
        for i, b in enumerate(firma_basliklar, 1):
            cell = ws.cell(row=1, column=i, value=b)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", start_color="2E7D32")
            cell.alignment = Alignment(horizontal="center")
        ornek = [
            ["SKU001", "Samsung Galaxy S24", 10, 5],
            ["SKU002", "iPhone 15", 3, 2],
            ["SKU003", "Xiaomi Redmi Note 13", 25, 12],
        ]
        for row in ornek:
            ws.append(row)
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = 18

    # Yoldaki ürünler sekmesi
    ws_yol = wb.create_sheet("YOLDAKI")
    yol_basliklar = ["SKU", "Ürün Adı", "Yoldaki Miktar", "Tahmini Varış Tarihi"]
    for i, b in enumerate(yol_basliklar, 1):
        cell = ws_yol.cell(row=1, column=i, value=b)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", start_color="6A1B9A")
        cell.alignment = Alignment(horizontal="center")
    ornek_yol = [
        ["SKU001", "Samsung Galaxy S24", 30, "2026-05-01"],
        ["SKU002", "iPhone 15", 10, "2026-04-25"],
    ]
    for row in ornek_yol:
        ws_yol.append(row)
    for col in ws_yol.columns:
        ws_yol.column_dimensions[col[0].column_letter].width = 22

    path = "/home/claude/stok_app/SABLON_STOK_TAKIP.xlsx"
    wb.save(path)
    return path


def _firma_normalize(s):
    """Türkçe karakterleri sadeleştirip büyük harfe çevirir (İTOPYA → ITOPYA)."""
    return (str(s or "").strip().upper()
            .replace("İ", "I").replace("Ğ", "G").replace("Ü", "U")
            .replace("Ş", "S").replace("Ç", "C").replace("Ö", "O"))


def excel_yukle_firma_birlesik(dosya_yolu):
    """YENİ birleşik tek-sayfa firma stok+satış şablonunu yükler.
    Beklenen sütunlar: FİRMA ADI · KATEGORİ · MARKA · STOK KODU · STOK ADI ·
                       STOK · STOK-MAĞAZA · SATIŞ · SATIŞ-MAĞAZA
    Her satır bir firma-SKU. STOK ve STOK-MAĞAZA / SATIŞ ve SATIŞ-MAĞAZA AYRI saklanır.
    Sadece firma satırları işlenir; GSF STOK / YOLDAKI bu sayfada beklenmez (atlanır)."""
    try:
        df = pd.read_excel(dosya_yolu, sheet_name=0)
        df.columns = [tr_upper(c) for c in df.columns]

        kolon_esleme = {
            "FIRMA":        ["FIRMA ADI", "FIRMA", "MAGAZA", "FIRMA ADI "],
            "SKU":          ["STOK KODU", "SKU", "KOD", "URUN KODU", "BARKOD"],
            "URUN_ADI":     ["STOK ADI", "URUN ADI", "AD", "URUN"],
            "KATEGORI":     ["KATEGORI", "CATEGORY"],
            "MARKA":        ["MARKA", "BRAND"],
            "STOK":         ["STOK", "STOK MIKTARI", "ONLINE STOK"],
            "STOK_MAGAZA":  ["STOK-MAGAZA", "STOK MAGAZA", "MAGAZA STOK", "STOK_MAGAZA"],
            "SATIS":        ["SATIS", "HAFTALIK SATIS", "SATIS ADEDI", "ONLINE SATIS"],
            "SATIS_MAGAZA": ["SATIS-MAGAZA", "SATIS MAGAZA", "MAGAZA SATIS", "SATIS_MAGAZA"],
        }
        kolon_map = {}
        for hedef, alternatifler in kolon_esleme.items():
            for alt in alternatifler:
                if tr_upper(alt) in df.columns:
                    kolon_map[hedef] = tr_upper(alt)
                    break

        if "FIRMA" not in kolon_map:
            return False, "❌ 'FİRMA ADI' kolonu bulunamadı."
        if "SKU" not in kolon_map:
            return False, "❌ 'STOK KODU' kolonu bulunamadı."

        gecerli_firmalar = {f: f for f in FIRMA_LISTESI}  # normalize edilmiş hâlleri
        basarili, atlanan = 0, 0
        firma_sayac = {}
        atlanan_firma = set()

        for _, row in df.iterrows():
            try:
                firma_ham = safe_str(row.get(kolon_map["FIRMA"], ""))
                sku = safe_str(row.get(kolon_map["SKU"], ""))
                if not sku or sku.lower() == "nan" or not firma_ham:
                    atlanan += 1
                    continue
                firma_n = _firma_normalize(firma_ham)
                # GSF STOK / YOLDAKI bu sayfaya ait değil → atla
                if firma_n in ("GSF STOK", "G5F STOK", "YOLDAKI", "YOLDAKİ", "BIZIM STOK", "DEPO"):
                    atlanan += 1
                    continue
                firma = gecerli_firmalar.get(firma_n)
                if not firma:
                    atlanan += 1
                    atlanan_firma.add(firma_ham)
                    continue

                urun_adi = safe_str(row.get(kolon_map.get("URUN_ADI", ""), ""))
                stok = safe_int(row.get(kolon_map.get("STOK", ""), 0))
                stok_magaza = safe_int(row.get(kolon_map.get("STOK_MAGAZA", ""), 0))
                satis = safe_int(row.get(kolon_map.get("SATIS", ""), 0))
                satis_magaza = safe_int(row.get(kolon_map.get("SATIS_MAGAZA", ""), 0))

                upsert_firma_stok(firma, sku, urun_adi, stok, satis,
                                  stok_magaza=stok_magaza, satis_magaza=satis_magaza)
                firma_sayac[firma] = firma_sayac.get(firma, 0) + 1
                basarili += 1
            except Exception:
                atlanan += 1

        ozet = " · ".join(f"{f}: {n}" for f, n in firma_sayac.items()) or "kayıt yok"
        uyari = ""
        if atlanan_firma:
            uyari = f" | ⚠️ Tanınmayan firma(lar) atlandı: {', '.join(sorted(atlanan_firma)[:5])}"
        return True, f"✅ {basarili} firma-SKU yüklendi ({ozet}). {atlanan} satır atlandı.{uyari}"
    except Exception as e:
        return False, f"❌ Dosya okunamadı: {type(e).__name__}: {str(e)[:160]}"


# G5F depo kırılımı — "satılabilir ana stok" sayılan depolar (sipariş önerisi/analitik için)
G5F_SATILABILIR_DEPOLAR = {"MERKEZ DEPO", "HAPPY LIFE"}


def excel_yukle_g5f_depolar(dosya_yolu):
    """G5F (bizim depo) çok-depolu stok şablonu.
    Beklenen sütunlar: DEPO ADI · STOK KODU · STOK İSMİ · MİKTAR
    Her SKU için depo kırılımı saklanır (TÜM depolar). bizim_stok (analitik) =
    satılabilir depolar (Merkez + Happy Life) toplamı. Fiyat/kategori/marka KORUNUR."""
    try:
        from collections import defaultdict
        df = pd.read_excel(dosya_yolu, sheet_name=0)
        df.columns = [tr_upper(c) for c in df.columns]
        kolon_esleme = {
            "DEPO":     ["DEPO ADI", "DEPO", "DEPO ISMI", "AMBAR", "DEPO ISMI "],
            "SKU":      ["STOK KODU", "SKU", "KOD", "URUN KODU", "BARKOD"],
            "URUN_ADI": ["STOK ISMI", "STOK ADI", "URUN ADI", "AD", "URUN"],
            "MIKTAR":   ["MIKTAR", "ADET", "STOK", "STOK MIKTARI"],
        }
        kolon_map = {}
        for hedef, alts in kolon_esleme.items():
            for alt in alts:
                if tr_upper(alt) in df.columns:
                    kolon_map[hedef] = tr_upper(alt)
                    break
        if "SKU" not in kolon_map:
            return False, "❌ 'STOK KODU' kolonu bulunamadı."
        if "DEPO" not in kolon_map:
            return False, "❌ 'DEPO ADI' kolonu bulunamadı."
        if "MIKTAR" not in kolon_map:
            return False, "❌ 'MİKTAR' kolonu bulunamadı."

        kirilim = defaultdict(dict)   # sku -> {depo: miktar}
        adlar = {}
        depolar_set = set()
        atlanan = 0
        for _, row in df.iterrows():
            sku = safe_str(row.get(kolon_map["SKU"], ""))
            if not sku or sku.lower() == "nan":
                atlanan += 1
                continue
            depo = safe_str(row.get(kolon_map["DEPO"], "")) or "Bilinmeyen"
            mik = safe_int(row.get(kolon_map["MIKTAR"], 0))
            kirilim[sku][depo] = kirilim[sku].get(depo, 0) + mik
            depolar_set.add(depo)
            if "URUN_ADI" in kolon_map and not adlar.get(sku):
                adlar[sku] = safe_str(row.get(kolon_map["URUN_ADI"], ""))

        basarili, toplam_adet = 0, 0
        for sku, dd in kirilim.items():
            satilabilir = sum(m for d, m in dd.items()
                              if _firma_normalize(d) in G5F_SATILABILIR_DEPOLAR)
            upsert_g5f_stok(sku, adlar.get(sku, ""), satilabilir, dd)
            basarili += 1
            toplam_adet += sum(dd.values())

        depo_liste = ", ".join(sorted(depolar_set))
        return True, (f"✅ {basarili} ürün yüklendi · {len(depolar_set)} depo "
                      f"({depo_liste}) · toplam {toplam_adet:,} adet. "
                      f"Sipariş önerisi 'bizim stok' = Merkez + Happy Life.")
    except Exception as e:
        return False, f"❌ Dosya okunamadı: {type(e).__name__}: {str(e)[:160]}"
