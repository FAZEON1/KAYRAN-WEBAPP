# -*- coding: utf-8 -*-
"""Dosya kapısı testleri için örnek Excel dosyaları — her yükleme türünün okuyucusunun beklediği biçimde.

ORNEKLER[tur]() → (dosya adı, bytes). tests/test_dosya_kapisi.py (tanıma) ve
tests/duman/test_dosya_kapisi.py (gerçek Streamlit'te kapı içinde akış) kullanır.
"""
from io import BytesIO

import pandas as pd

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim",
         "Kasım", "Aralık"]
SKULAR = ["X24F165S", "VG27AQ"]


def _xlsx(sayfalar, baslik=True):
    b = BytesIO()
    with pd.ExcelWriter(b, engine="openpyxl") as w:
        for ad, df in sayfalar.items():
            df.to_excel(w, index=False, header=baslik, sheet_name=ad)
    return b.getvalue()


def vatan():
    return "vatan_siparis.xlsx", _xlsx({"Siparisler": pd.DataFrame({
        "Sipariş Numarası": ["V100", "V100"], "Sipariş Tarih": ["2026-10-01", "2026-10-01"],
        "Stok Kodu": SKULAR, "Birim Fiyat": [120.0, 260.0], "Miktar": [3, 2], "Depo": [11, 11],
        "Depo Tanım": ["MERKEZ DEPO", ""]})})


def itopya():
    return "eera_siparis.xlsx", _xlsx({"EERA": pd.DataFrame({
        "TARİH": ["2026-10-01", "2026-10-01"], "DEPOTANIM": ["MERKEZ DEPO", ""], "MAĞAZALAR": ["A", "B"],
        "STOKKODU": SKULAR, "SONALFIYAT": [118.0, 255.0], "MIKTAR": [4, 1]})})


def mikro():
    return "FaturaDokum.xlsx", _xlsx({"Sayfa1": pd.DataFrame({
        "Fatura no": ["F1", "F2", ""], "Tarih": ["01.10.2026", "02.10.2026", ""], "Cari adı": ["EERA", "VATAN", ""],
        "Hesap kodu": [SKULAR[0], SKULAR[1], ""], "Hesap ismi": ["Monitör A", "Monitör B", ""],
        "Mik": [2, 1, 3], "Net Br.fy.": [119.0, 250.0, None]})})


def iade():
    return "iade.xlsx", _xlsx({"Sayfa1": pd.DataFrame({
        "Stok kodu": ["EERA BİLGİSAYAR", SKULAR[0]], "Stok ismi": ["", "Monitör A"],
        "Satış miktarı": [None, 10], "İade miktar": [None, 2], "İade brüt tutar": [None, 240.0],
        "İade iskonto": [None, 0], "İade masraf": [None, 0], "İade net": [None, 240.0]})})


def iade_fatura():
    """Mikro fatura bazlı iade dökümü: fatura başlık satırı (stok kodu boş), kalemler, Toplam satırı,
    dipnot. Gerçek dosyanın (İADE RAPORU 24 TEMMUZ-30 EYLÜL) sütunları birebir."""
    kol = ["Fatura no", "Belge No", "Cins", "İ N", "Tarih", "Cari kodu", "Cari adı",
           "Stok/hizmet/masraf/ demirbaş/ithalat kodu", "Stok/hizmet/masraf/ demirbaş/ithalat ismi", "Miktar",
           "Stok DVZ", "Ara toplam", "Vergi matrahı", "Toplam vergi", "Toplam", "Depo"]
    E, V = ("120.02.005", "EERA ELEKTRONİK TİCARET VE BİLİŞİM HİZMETLERİ ANONİM ŞİRKETİ"), \
        ("120.01.003", "VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI")
    bos = [None] * 16

    def fat(no, tarih, cari, kalemler):
        top = sum(k[3] for k in kalemler)
        r = [[no, no + "B", "Toptan fatura", "İade", tarih, *cari, None, None, None, None, top, top, 0, top,
              kalemler[0][4]]]
        r += [[no, no + "B", "Toptan fatura", "İade", tarih, *cari, k[0], k[1], k[2], "USD", k[3], k[3], 0, k[3],
               k[4]] for k in kalemler]
        r += [bos, [None] * 5 + ["Toplam"] + [None] * 3 + [sum(k[2] for k in kalemler), None, top, top, 0, top,
                                                           None], bos]
        return r
    satirlar = (fat("ITF-1", "2026-07-24", E, [("Faze2", "Mouse Pad M", 23, 80.5, "Merkez depo")])
                + fat("VTN-2", "2026-08-05", V, [(SKULAR[0], "Monitör A", 2, 240.0, "İADE DEPO "),
                                                 (SKULAR[1], "Monitör B", 1, 250.0, "İADE DEPO ")])
                + fat("VTN-3", "2026-09-30", V, [(SKULAR[0], "Monitör A", 1, 120.0, "İADE DEPO ")])
                + [["Ortalama belge değeri  :", "571,68"] + [None] * 14, bos,
                   [None] * 9 + [27, None, 690.5, 690.5, 0, 690.5, None]])
    return "IADE_RAPORU_24_TEMMUZ-30_EYLUL.xlsx", _xlsx({"İADE RAPORU": pd.DataFrame(satirlar, columns=kol)})


def ithalat():
    return "satin_alim.xlsx", _xlsx({"Rapor": pd.DataFrame({
        "İthalat takip no": ["T-77", "T-77"], "Sipariş tarihi": ["2026-09-01", "2026-09-01"],
        "Sipariş no": ["S1", "S1"], "Belge no": ["PI-9", "PI-9"], "Cari hesap adı": ["SHENZHEN X", "SHENZHEN X"],
        "Stok kodu": SKULAR, "Stok ismi": ["Monitör A", "Monitör B"], "Miktar": [100, 50],
        "Net fiyat": [90.0, 200.0], "Döviz": ["USD", "USD"]})})


def happylife():
    return "G5F_Stok.xlsx", _xlsx({"Ozet": pd.DataFrame({"x": [1]}), "G5F_Stok": pd.DataFrame({
        "SKU kodu": SKULAR, "SKU tanımı": ["Monitör A", "Monitör B"], "Giriş tarihi": ["2026-08-01", "2026-09-15"],
        "Palet etiketi": ["P1", "P2"], "Miktar": [40, 12], "Birim": ["ADET", "ADET"], "Miktar-2": [1, 1]})})


def mal_kabul():
    kol = ["İşlem Türü (Teknik/İade)", "Stok Kodu", "Stok Adı", "Ürün Grubu", "Seri No", "Arıza",
           "Firma (Cari Unvan)", "Mağaza / Müşteri Adı", "Telefon", "Mail", "Adres", "Sevk / Teslim Şekli",
           "Kargo Takip No", "Fatura No", "İrsaliye No", "Firma Servis Form No", "Fiziksel Durum"]
    satir = ["Teknik", SKULAR[0], "Monitör A", "MONİTÖR", "SN123", "Görüntü yok", "VATAN", "", "", "", "",
             "Kargo", "", "", "", "", "Temiz"]
    return "toplu_mal_kabul.xlsx", _xlsx({"MalKabul": pd.DataFrame([satir], columns=kol)})


def kampanya():
    kol = ["FİRMA ADI", "MARKA", "KATEGORİ", "STOK KODU", "STOK ADI", "BARKOD", "FİYAT", "REBATE", "SELLOUT",
           "EK SELLOUT", "SPIFF", "NET FİYAT", "KAMPANYA ADI", "KAMPANYA TÜRÜ", "BAŞLANGIÇ TARİHİ", "BİTİŞ TARİHİ"]
    s = ["VATAN", "FAZEON", "monitör", SKULAR[0], "Monitör A", "", 120, 0, 5, 1, 0, 114, "Ekim fırsat",
         "Sellout", "2026-10-01", "2026-10-31"]
    return "kampanya.xlsx", _xlsx({"Kampanya": pd.DataFrame([s], columns=kol)})


def g5f():
    return "g5f.xlsx", _xlsx({"Sayfa1": pd.DataFrame({
        "DEPO ADI": ["MERKEZ DEPO", "HAPPY LIFE"], "STOK KODU": SKULAR, "STOK İSMİ": ["Monitör A", "Monitör B"],
        "MİKTAR": [30, 8]})})


def ref():
    return "ref.xlsx", _xlsx({"Sayfa1": pd.DataFrame({
        "NUMARA": [1, 2], "REF NUMARASI": ["FZVTRF2026001", "FZVTRF2026002"], "AÇIKLAMA": ["Ekim sellout", "Spiff"],
        "TUTAR": [1500, 300], "DÖVİZ": ["USD", "TL"]})})


def destek():
    return "alinan_destek.xlsx", _xlsx({"Sayfa1": pd.DataFrame({
        "FİRMA": ["FAZEON"], "TÜR": ["SELLOUT"], "DÖNEM": ["2026-09"], "TUTAR": [1500.0], "DÖVİZ": ["USD"],
        "KATEGORİ": ["MONİTÖR"], "FATURA NO": [""], "AÇIKLAMA": ["Eylül"]})})


def gider():
    satirlar = [["2026 GİDER TABLOSU"] + [None] * 13,
                ["KATEGORİ", "KALEM"] + AYLAR,
                ["SABİT GİDERLER", None] + [None] * 12,
                ["Sabit", "Kira"] + [100000] * 12,
                ["Değişken", "Kargo"] + [25000] * 12]
    return "gider_2026.xlsx", _xlsx({"Gider": pd.DataFrame(satirlar)}, baslik=False)


def aktif_cari():
    satirlar = [["CARİ ALACAKLAR LİSTESİ", None, None, None],
                ["Hesap kodu", "Hesap adı", "Döviz", "Bakiye"],
                ["120.01", "VATAN BİLGİSAYAR", "TL", 1250000],
                ["320.05", "SHENZHEN X", "USD", -48000]]
    return "cari_alacaklar.xlsx", _xlsx({"Sayfa1": pd.DataFrame(satirlar)}, baslik=False)


def aktif_ithalat():
    satirlar = [["İTHALAT ÖDEME TAKİP", None, None],
                ["Dosya", "Tedarikçi", "Ödenen"],
                [None, None, "USD"],
                ["PI-9", "SHENZHEN X", 52000],
                ["PI-10", "SHENZHEN Y", 18000],
                ["TOPLAM", None, 70000]]
    return "ithalat_odeme_takip.xlsx", _xlsx({"Sayfa1": pd.DataFrame(satirlar)}, baslik=False)


def aktif_stok():
    satirlar = [["STOK DEĞERİ RAPORU", None, None, None, None, None, None, None],
                ["STOK KODU", "STOK ADI", "MİKTAR", "TL", "USD SON DURUM", "VATAN", "VATAN STOK", "TOPLAM TUTAR"],
                [SKULAR[0], "Monitör A", 30, 100000, 2700, "VT1", 4, 480],
                [SKULAR[1], "Monitör B", 8, 70000, 1600, "VT2", 2, 510],
                [None, None, None, None, 4300, None, None, 990]]
    return "stok_degeri.xlsx", _xlsx({"Sayfa1": pd.DataFrame(satirlar)}, baslik=False)


def haftalik():
    return "musteri_haftalik.xlsx", _xlsx({
        "VATAN STOK": pd.DataFrame({"STOKKODU": SKULAR, "ADET": [5, 7]}),
        "VATAN SATIŞ": pd.DataFrame({"STOKKODU": [SKULAR[0]], "MIKTAR": [2], "TARİH": ["2026-09-27"]})})


def odeme():
    satirlar = [["41. Hafta 06-12 Ekim 2026"] + [None] * 7,
                [None] * 8,
                ["HAFTA", "FİRMA", "AÇIKLAMA", "CARİ BANKA / IBAN", "VADE", "TUTAR TL", "TUTAR USD", "KATEGORİ"],
                [None, "ABC Lojistik", "Nakliye", "TR12", "2026-10-08", 45000, None, "cari"],
                [None, "Global Import", "USD ödeme", "TR55", "2026-10-09", None, 5000, "kredi"]]
    return "41.hafta.xlsx", _xlsx({"Ödeme Listesi": pd.DataFrame(satirlar)}, baslik=False)


def cek():
    satirlar = [["FİRMA ÇEKLERİ DÖKÜMÜ"] + [None] * 14,
                ["Sıra No", "Referans No", "Tarih", "Vade Tarihi", "Çek No", "Meblağ", "Ödenen", "Kalan",
                 "Para Birimi", "Son Pozisyon", "C/H Kodu", "C/H İsmi", "Banka", "Şube", "Hesap No"],
                [1, "R1", "2026-09-01", "2026-11-15", "C-1001", 120000, 0, 120000, "TL", "Portföyde", "320.1",
                 "AYKON", "Banka A", "Merkez", "123"],
                [2, "R2", "2026-09-05", "2026-12-01", "C-1002", 8000, 0, 8000, "USD", "Portföyde", "320.2",
                 "SHENZHEN X", "Banka B", "Merkez", "456"]]
    return "cek_dokumu.xlsx", _xlsx({"Sayfa1": pd.DataFrame(satirlar)}, baslik=False)


ORNEKLER = {
    "siparis_vatan": vatan, "siparis_itopya": itopya, "mikro_fatura": mikro, "iade_excel": iade,
    "ithalat_rapor": ithalat, "happylife": happylife, "toplu_mal_kabul": mal_kabul, "kampanya_sablon": kampanya,
    "g5f_sayim": g5f, "ref_excel": ref, "alinan_destek": destek, "gider_tablosu": gider, "aktif_cari": aktif_cari,
    "aktif_ithalat": aktif_ithalat, "aktif_stok": aktif_stok, "musteri_haftalik": haftalik,
    "odeme_listesi": odeme, "cek_listesi": cek,
}
