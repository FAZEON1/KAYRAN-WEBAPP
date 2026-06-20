import pandas as pd
from datetime import datetime
from .database import upsert_urun, upsert_firma_stok, get_client, upsert_yoldaki_urun
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
