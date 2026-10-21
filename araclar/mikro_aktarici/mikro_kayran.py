"""
Mikro ERP -> KAYRAN canlı veri aktarımı
=======================================

Mikro Desktop API'nin SqlVeriOkuV2 endpoint'i üzerinden stok, cari bakiye,
sipariş, fatura, iade, ithalat ve masraf verilerini belirli aralıklarla çeker.

Kurulum (sunucu 10.0.1.11, Python 3.11 veya üstü):
    pip install requests tzdata

Ayarlar (ortam değişkeni olarak veya aşağıdaki AYARLAR sözlüğünde):
    MIKRO_URL            örn. http://192.168.1.10:8094   (v16 ise 8084)
    MIKRO_API_KEY        Mikro'dan alınan ApiKey
    MIKRO_FIRMA_KODU     Mikro firma kodu
    MIKRO_KULLANICI      Mikro kullanıcı kodu
    MIKRO_SIFRE          Mikro kullanıcı şifresi (düz metin; hash'i kod üretir)
    MIKRO_CALISMA_YILI   örn. 2026 (boşsa içinde bulunulan yıl)
    MIKRO_SSL_DOGRULA    "0" ise HTTPS sertifikası doğrulanmaz (self-signed için)
    SUPABASE_URL         varsayılan: KAYRAN WEB-APP projesi
    SUPABASE_SERVICE_KEY Supabase > Project Settings > API Keys > service_role (secret)

Çalıştırma:
    python mikro_kayran.py --test            # bağlantı + her sorgudan ilk 3 kayıt
    python mikro_kayran.py --bir-kez         # tek seferlik aktarım
    python mikro_kayran.py --aralik 900      # 15 dakikada bir sürekli aktarım
    python mikro_kayran.py --tam --bir-kez   # her şeyi baştan çek (gece 1 kez)

Zamanlama (Ekim 2026 kararı): Windows Görev Zamanlayıcısı 15 dakikada bir --bir-kez, gece 03:00'te
--tam --bir-kez çalıştırır (gorev_kur.bat). İki çalıştırma üst üste binmesin diye kilit dosyası var.

Veriler Supabase'deki mikro_* tablolarına upsert edilir; son çekim zamanı ve
hatalar mikro_senk_durum tablosunda tutulur.
"""

from __future__ import annotations

import sys

if sys.version_info < (3, 11):
    sys.exit("Python 3.11 veya üstü gerekli (şu an %d.%d). python.org'dan güncel sürümü kurun."
             % sys.version_info[:2])

import argparse
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

# --------------------------------------------------------------------------- #
# Ayarlar
# --------------------------------------------------------------------------- #
# Windows'ta saat dilimi verisi Python'la gelmez (tzdata paketi gerekir); yoksa sabit +03:00
# (Türkiye 2016'dan beri yaz saati uygulamıyor, sonuç aynı).
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Istanbul")
except Exception:  # noqa: BLE001
    TZ = timezone(timedelta(hours=3), "Europe/Istanbul")

AYARLAR = {
    "url": os.getenv("MIKRO_URL", "http://localhost:8094").rstrip("/"),
    "api_key": os.getenv("MIKRO_API_KEY", ""),
    "firma_kodu": os.getenv("MIKRO_FIRMA_KODU", ""),
    "kullanici": os.getenv("MIKRO_KULLANICI", ""),
    "sifre": os.getenv("MIKRO_SIFRE", ""),
    "calisma_yili": os.getenv("MIKRO_CALISMA_YILI", ""),
    "ssl_dogrula": os.getenv("MIKRO_SSL_DOGRULA", "1") != "0",
    "zaman_asimi": 120,  # saniye
}

SUPABASE = {
    "url": os.getenv("SUPABASE_URL", "https://qspwlqegoeudifxxrxcj.supabase.co").rstrip("/"),
    "key": os.getenv("SUPABASE_SERVICE_KEY", ""),
}
PARTI_BOYUTU = 500  # tek istekte gönderilecek satır sayısı
ARALIK_SN = 900  # sürekli modda tur aralığı: 15 dakika (bütün hareket geçmişini tarayan sorgular var)
KILIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aktarim.kilit")
KILIT_ESKI_SN = 3 * 3600  # bu kadar eski kilit, çökmüş bir çalıştırmadan kalmıştır
GUVENLIK_PAYI = timedelta(minutes=2)  # saat farkı / geç kaydedilen hareketler için

log = logging.getLogger("mikro_kayran")

# --------------------------------------------------------------------------- #
# Sorgular  (iadeler mikro_fatura / mikro_fatura_satir içinde; Supabase'de
#            mikro_iade ve mikro_iade_satir görünümleriyle okunur)
#   {SON} -> son çekim zamanı ile değiştirilir (artımlı sorgular).
#   artimli=False olan sorgular (bakiye hesapları) her seferinde tam çekilir.
# --------------------------------------------------------------------------- #
SORGULAR: dict[str, dict[str, Any]] = {
    "stok_miktar": {
        "tablo": "mikro_stok_miktar", "anahtar": "sto_kod,depo",
        "artimli": False,
        "sql": """
SELECT s.sto_kod, s.sto_isim, s.sto_birim1_ad, x.depo, SUM(x.m) AS miktar
FROM STOKLAR s
JOIN (SELECT sth_stok_kod k, sth_giris_depo_no depo, sth_miktar m
        FROM STOK_HAREKETLERI WHERE sth_tip IN (0,2) AND sth_iptal=0
      UNION ALL
      SELECT sth_stok_kod, sth_cikis_depo_no, -sth_miktar
        FROM STOK_HAREKETLERI WHERE sth_tip IN (1,2) AND sth_iptal=0) x
  ON x.k = s.sto_kod
GROUP BY s.sto_kod, s.sto_isim, s.sto_birim1_ad, x.depo
""",
    },
    "cari_bakiye": {
        "tablo": "mikro_cari_bakiye", "anahtar": "cari_kod,doviz",
        "artimli": False,
        "sql": """
SELECT c.cari_kod, c.cari_unvan1, h.cha_d_cins AS doviz,
       SUM(CASE WHEN h.cha_tip=0 THEN h.cha_meblag ELSE -h.cha_meblag END) AS bakiye
FROM CARI_HESAPLAR c
JOIN CARI_HESAP_HAREKETLERI h
  ON h.cha_kod=c.cari_kod AND h.cha_cari_cins=0 AND h.cha_iptal=0
GROUP BY c.cari_kod, c.cari_unvan1, h.cha_d_cins
""",
    },
    "siparis": {
        "tablo": "mikro_siparis", "anahtar": "sip_guid",
        "artimli": True,
        "sql": """
SELECT sip_Guid, sip_tip, sip_cins, sip_tarih, sip_teslim_tarih,
       sip_evrakno_seri, sip_evrakno_sira, sip_satirno,
       sip_musteri_kod, sip_stok_kod, sip_miktar, sip_teslim_miktar,
       sip_miktar - sip_teslim_miktar AS kalan,
       sip_b_fiyat, sip_tutar, sip_doviz_cinsi, sip_depono, sip_kapat_fl, sip_lastup_date
FROM SIPARISLER
WHERE sip_iptal=0 AND sip_lastup_date > '{SON}'
""",
    },
    "fatura": {
        "tablo": "mikro_fatura", "anahtar": "cha_guid",
        "artimli": True,
        "sql": """
SELECT cha_Guid, cha_evrak_tip, cha_tarihi, cha_evrakno_seri, cha_evrakno_sira, cha_kod,
       cha_meblag, cha_d_cins, cha_d_kur, cha_normal_Iade, cha_lastup_date
FROM CARI_HESAP_HAREKETLERI
WHERE cha_evrak_tip IN (0,63) AND cha_iptal=0
  AND cha_lastup_date > '{SON}'
""",
    },
    "fatura_satir": {
        "tablo": "mikro_fatura_satir", "anahtar": "sth_guid",
        "artimli": True,
        "sql": """
SELECT sth_Guid, sth_fat_uid, sth_evraktip, sth_tarih, sth_stok_kod, sth_cari_kodu,
       sth_miktar, sth_tutar, sth_giris_depo_no, sth_cikis_depo_no,
       sth_normal_iade, sth_lastup_date
FROM STOK_HAREKETLERI
WHERE sth_evraktip IN (3,4) AND sth_iptal=0 AND sth_lastup_date > '{SON}'
""",
    },
    "ithalat": {
        "tablo": "mikro_ithalat", "anahtar": "cha_guid",
        "artimli": True,
        "sql": """
SELECT cha_Guid, cha_tarihi, cha_evrak_tip, cha_cinsi, cha_cari_cins,
       cha_kod AS dosya_veya_cari, cha_meblag, cha_d_cins, cha_d_kur,
       cha_EXIMkodu, cha_lastup_date
FROM CARI_HESAP_HAREKETLERI
WHERE cha_iptal=0 AND (cha_cari_cins=9 OR cha_cinsi IN (28,29) OR cha_evrak_tip=95)
  AND cha_lastup_date > '{SON}'
""",
    },
    "ithalat_stok": {
        "tablo": "mikro_ithalat_stok", "anahtar": "sth_guid",
        "artimli": True,
        "sql": """
SELECT sth_Guid, sth_tarih, sth_evraktip, sth_stok_kod, sth_cari_kodu,
       sth_miktar, sth_tutar, sth_giris_depo_no, sth_lastup_date
FROM STOK_HAREKETLERI
WHERE sth_cins=12 AND sth_iptal=0 AND sth_lastup_date > '{SON}'
""",
    },
    # Satış ve satış iadesi faturalarının ürün satırları (Ekim 2026, kullanıcı: "bundan sonra tüm satışlar,
    # iadeler API'den otomatik gelsin"). Satış satırları faturaya bağlı irsaliye satırında durur
    # (sth_fat_uid = fatura cha_Guid); yalnız sth_evraktip'e bakınca çoğu görünmüyordu.
    # Fatura türü: cha_evrak_tip 63 = satış faturası (iade işaretliyse alış iadesi),
    # 0 + iade = satış iadesi faturası. Tutarlar TL, KDV hariç; $ çevirisi uygulamada (satis/mikro_esitle).
    "satis_satir": {
        "tablo": "mikro_satis_satir", "anahtar": "sth_guid",
        "artimli": True,
        "sql": """
SELECT h.sth_Guid, h.sth_fat_uid, h.sth_tarih, h.sth_tip, h.sth_evraktip, h.sth_normal_iade,
       h.sth_stok_kod, s.sto_isim, h.sth_cari_kodu, ca.cari_unvan1,
       h.sth_miktar, h.sth_tutar,
       h.sth_iskonto1 + h.sth_iskonto2 + h.sth_iskonto3 + h.sth_iskonto4 + h.sth_iskonto5 + h.sth_iskonto6
           AS sth_iskonto,
       h.sth_vergi, h.sth_alt_doviz_kuru, h.sth_giris_depo_no, h.sth_cikis_depo_no,
       dg.dep_adi AS giris_depo_adi, dc.dep_adi AS cikis_depo_adi,
       c.cha_evrak_tip, c.cha_normal_Iade AS cha_normal_iade, c.cha_evrakno_seri, c.cha_evrakno_sira,
       c.cha_tarihi, c.cha_d_cins, c.cha_d_kur, h.sth_lastup_date, c.cha_lastup_date
FROM STOK_HAREKETLERI h
JOIN CARI_HESAP_HAREKETLERI c ON c.cha_Guid = h.sth_fat_uid
LEFT JOIN STOKLAR s ON s.sto_kod = h.sth_stok_kod
LEFT JOIN CARI_HESAPLAR ca ON ca.cari_kod = c.cha_kod
LEFT JOIN DEPOLAR dg ON dg.dep_no = h.sth_giris_depo_no
LEFT JOIN DEPOLAR dc ON dc.dep_no = h.sth_cikis_depo_no
WHERE h.sth_iptal=0 AND c.cha_iptal=0 AND c.cha_tarihi >= '20260101'
  AND (c.cha_evrak_tip=63 OR (c.cha_evrak_tip=0 AND c.cha_normal_Iade=1))
  AND (h.sth_lastup_date > '{SON}' OR c.cha_lastup_date > '{SON}')
""",
    },
    # ── Muhasebe adımı 1 (Ekim 2026): ham veri; bakiye / eşleme hesapları uygulamada (kayranacc/mikro_muhasebe) ──
    # Cari, banka (cari_cins 2), kasa (4) ve diğer bütün cari hareketleri — bakiye formülü uygulamada doğrulanır.
    "cari_hareket": {
        "tablo": "mikro_cari_hareket", "anahtar": "cha_guid",
        "artimli": True,
        "sql": """
SELECT cha_Guid, cha_evrak_tip, cha_evrakno_seri, cha_evrakno_sira, cha_satir_no, cha_tarihi, cha_tip, cha_cinsi,
       cha_normal_Iade AS cha_normal_iade, cha_cari_cins, cha_kod, cha_ciro_cari_kodu, cha_d_cins, cha_d_kur,
       cha_altd_kur, cha_karsidcinsi, cha_karsid_kur, cha_meblag, cha_vade, cha_aciklama, cha_belge_no,
       cha_EXIMkodu AS cha_eximkodu, cha_srmrkkodu, cha_kasa_hizmet, cha_kasa_hizkod, cha_trefno, cha_sntck_poz,
       cha_lastup_date
FROM CARI_HESAP_HAREKETLERI
WHERE cha_iptal=0 AND cha_lastup_date > '{SON}'
""",
    },
    "cari_kart": {
        "tablo": "mikro_cari_kart", "anahtar": "cari_kod",
        "artimli": False,
        "sql": """
SELECT cari_kod, cari_unvan1, cari_doviz_cinsi, cari_muh_kod, cari_grup_kodu, cari_sektor_kodu, cari_lastup_date
FROM CARI_HESAPLAR WHERE cari_iptal=0
""",
    },
    "banka_kart": {
        "tablo": "mikro_banka_kart", "anahtar": "ban_kod",
        "artimli": False,
        "sql": "SELECT ban_kod, ban_ismi, ban_sube, ban_doviz_cinsi, ban_hesap_tip, ban_muh_kod FROM BANKALAR WHERE ban_iptal=0",
    },
    "kasa_kart": {
        "tablo": "mikro_kasa_kart", "anahtar": "kas_kod",
        "artimli": False,
        "sql": "SELECT kas_kod, kas_isim, kas_doviz_cinsi, kas_tip FROM KASALAR WHERE kas_iptal=0",
    },
    "depo_kart": {
        "tablo": "mikro_depo_kart", "anahtar": "dep_no",
        "artimli": False,
        "sql": "SELECT dep_no, dep_adi FROM DEPOLAR WHERE dep_iptal=0",
    },
    "cek_senet": {
        "tablo": "mikro_cek", "anahtar": "sck_guid",
        "artimli": False,
        "sql": """
SELECT sck_Guid, sck_tip, sck_refno, sck_no, sck_vade, sck_tutar, sck_doviz, sck_doviz_kur, sck_odenen, sck_borclu,
       sck_sonpoz, sck_sahip_cari_cins, sck_sahip_cari_kodu, sck_nerede_cari_cins, sck_nerede_cari_kodu,
       sck_bankano, sck_banka_adres1, sck_sube_adres2, sck_hesapno_sehir, sck_duzen_tarih, sck_son_hareket_tarihi,
       sck_lastup_date
FROM ODEME_EMIRLERI WHERE sck_iptal=0
""",
    },
    # Muhasebe: ay × hesap toplamları (gider tablosu için; fiş ayrıntısı gerekmez)
    "muhasebe_ay": {
        "tablo": "mikro_muhasebe_ay", "anahtar": "yil,ay,hesap_kod",
        "artimli": False,
        "sql": """
SELECT YEAR(fis_tarih) AS yil, MONTH(fis_tarih) AS ay, fis_hesap_kod AS hesap_kod,
       SUM(CASE WHEN fis_meblag0 > 0 THEN fis_meblag0 ELSE 0 END) AS borc,
       SUM(CASE WHEN fis_meblag0 < 0 THEN -fis_meblag0 ELSE 0 END) AS alacak,
       COUNT(*) AS satir
FROM MUHASEBE_FISLERI WHERE fis_iptal=0 AND fis_tarih >= '20250101'
GROUP BY YEAR(fis_tarih), MONTH(fis_tarih), fis_hesap_kod
""",
    },
    # Muhasebe fiş türü dağılımı (Ekim 2026): yıl sonu kapanış fişi Aralık'ta 6xx/7xx hesaplarını sıfırlıyor.
    # Kapanışın hangi fis_tur olduğu buradan doğrulanır (gider_* = 6xx/7xx hesaplarının toplamı). Küçük tablo.
    "muhasebe_tur": {
        "tablo": "mikro_muhasebe_tur", "anahtar": "yil,ay,fis_tur",
        "artimli": False,
        "sql": """
SELECT YEAR(fis_tarih) AS yil, MONTH(fis_tarih) AS ay, COALESCE(CAST(fis_tur AS int), -1) AS fis_tur,
       COUNT(*) AS satir,
       SUM(CASE WHEN fis_meblag0 > 0 THEN fis_meblag0 ELSE 0 END) AS borc,
       SUM(CASE WHEN fis_meblag0 < 0 THEN -fis_meblag0 ELSE 0 END) AS alacak,
       SUM(CASE WHEN fis_meblag0 > 0 AND (fis_hesap_kod LIKE '6%' OR fis_hesap_kod LIKE '7%')
                THEN fis_meblag0 ELSE 0 END) AS gider_borc,
       SUM(CASE WHEN fis_meblag0 < 0 AND (fis_hesap_kod LIKE '6%' OR fis_hesap_kod LIKE '7%')
                THEN -fis_meblag0 ELSE 0 END) AS gider_alacak
FROM MUHASEBE_FISLERI WHERE fis_iptal=0 AND fis_tarih >= '20250101'
GROUP BY YEAR(fis_tarih), MONTH(fis_tarih), COALESCE(CAST(fis_tur AS int), -1)
""",
    },
    # Muhasebe ay × hesap × fiş türü: gider tablosu kapanış fişini ayıklayabilsin (muhasebe_ay ile aynı toplam)
    "muhasebe_ay_tur": {
        "tablo": "mikro_muhasebe_ay_tur", "anahtar": "yil,ay,hesap_kod,fis_tur",
        "artimli": False,
        "sql": """
SELECT YEAR(fis_tarih) AS yil, MONTH(fis_tarih) AS ay, fis_hesap_kod AS hesap_kod,
       COALESCE(CAST(fis_tur AS int), -1) AS fis_tur,
       SUM(CASE WHEN fis_meblag0 > 0 THEN fis_meblag0 ELSE 0 END) AS borc,
       SUM(CASE WHEN fis_meblag0 < 0 THEN -fis_meblag0 ELSE 0 END) AS alacak,
       COUNT(*) AS satir
FROM MUHASEBE_FISLERI WHERE fis_iptal=0 AND fis_tarih >= '20250101'
GROUP BY YEAR(fis_tarih), MONTH(fis_tarih), fis_hesap_kod, COALESCE(CAST(fis_tur AS int), -1)
""",
    },
    "hesap_plani": {
        "tablo": "mikro_hesap_plani", "anahtar": "muh_hesap_kod",
        "artimli": False,
        "sql": "SELECT muh_hesap_kod, muh_hesap_isim1 FROM MUHASEBE_HESAP_PLANI WHERE muh_iptal=0",
    },
    # ── Alımlar adımı 3 (Ekim 2026): ithalat dosyaları + bütün alış satırları (ithalat ve yurt içi) ──
    # Ürün satırı ithalat dosyasına sth_exim_kodu ile bağlı (ith_kodu, ör. VANEX-015). Cari koduyla süzülür
    # (ilk sürümdeki sth_cari_cinsi=0 süzgeci 21.10'da hiç satır döndürmedi). Paçal / masraf dağıtımı
    # uygulamada eski değerlerle karşılaştırılarak kurulur.
    "ithalat_dosya": {
        "tablo": "mikro_ithalat_dosya", "anahtar": "ith_kodu",
        "artimli": False,
        "sql": """
SELECT ith_kodu, ith_ismi, ith_satici, ith_dovizcinsi, ith_teslimsekli, ith_odemesekli, ith_GGB_tarihi AS ith_ggb_tarihi,
       ith_GGB_no AS ith_ggb_no, ith_serbestdolasimagiristarihi AS ith_serbest_dolasim_tarihi, ith_create_date,
       ith_lastup_date
FROM ITHALAT_DOSYALARI WHERE ith_iptal=0
""",
    },
    "alim_satir": {
        "tablo": "mikro_alim_satir", "anahtar": "sth_guid",
        "artimli": True,
        "sql": """
SELECT sth_Guid, sth_tarih, sth_tip, sth_cins, sth_evraktip, sth_normal_iade, sth_evrakno_seri, sth_evrakno_sira,
       sth_stok_kod, sth_cari_kodu, sth_miktar, sth_tutar,
       sth_iskonto1 + sth_iskonto2 + sth_iskonto3 + sth_iskonto4 + sth_iskonto5 + sth_iskonto6 AS sth_iskonto,
       sth_masraf1 + sth_masraf2 + sth_masraf3 + sth_masraf4 AS sth_masraf,
       sth_har_doviz_cinsi, sth_har_doviz_kuru, sth_alt_doviz_kuru, sth_giris_depo_no, sth_exim_kodu,
       sth_bagli_ithalat_kodu, sth_fat_uid, sth_lastup_date
FROM STOK_HAREKETLERI
WHERE sth_iptal=0 AND sth_tip=0 AND ISNULL(sth_cari_kodu, '') <> '' AND sth_tarih >= '20250101'
  AND sth_lastup_date > '{SON}'
""",
    },
    # ── Adım 4 (Ekim 2026): depo hareketleri — Happy Life raporu ve stok yaşı (depoya giriş tarihi, FIFO) ──
    # Bir depoya giren ya da depodan çıkan bütün hareketler: giriş (sth_tip 0), çıkış (1), depolar arası sevk (2).
    # İptal işareti de çekilir (WHERE'de süzülmez): sonradan iptal edilen satır artımlı turda güncellenir.
    # Hesap uygulamada (kayranpm/mikro_depo.py).
    "depo_hareket": {
        "tablo": "mikro_depo_hareket", "anahtar": "sth_guid",
        "artimli": True,
        "sql": """
SELECT sth_Guid, sth_tarih, sth_tip, sth_cins, sth_evraktip, sth_normal_iade, sth_evrakno_seri, sth_evrakno_sira,
       sth_stok_kod, sth_miktar, sth_giris_depo_no, sth_cikis_depo_no, sth_cari_kodu, sth_exim_kodu,
       sth_parti_kodu, sth_iptal, sth_lastup_date
FROM STOK_HAREKETLERI
WHERE sth_tarih >= '20250101' AND sth_tip IN (0,1,2) AND (sth_giris_depo_no > 0 OR sth_cikis_depo_no > 0)
  AND sth_lastup_date > '{SON}'
""",
    },
    "masraf": {
        "tablo": "mikro_masraf", "anahtar": "cha_guid",
        "artimli": True,
        "sql": """
SELECT cha_Guid, cha_tarihi, cha_evrak_tip, cha_cari_cins, cha_kod,
       cha_meblag, cha_d_cins, cha_d_kur, cha_evrakno_seri, cha_evrakno_sira, cha_lastup_date
FROM CARI_HESAP_HAREKETLERI
WHERE cha_iptal=0 AND (cha_evrak_tip IN (37,55) OR cha_cari_cins=5)
  AND cha_lastup_date > '{SON}'
""",
    },
    # ── Teknik servis (Ekim 2026): seri numarası tanımları (kullanıcı: seri no dosya / elle giriş yerine Mikro'dan) ──
    # Seri no → stok kodu, alış ve satış belgesi (seri + sıra), alıcı cari, garanti tarihleri. Belge ve cari seri no
    # satırının kendisinde olduğu için CIHAZ_HAREKETLERI (seri no → hareket) çekilmez. İptal işareti WHERE'de
    # süzülmez (sonradan iptal edilen tanım artımlı turda güncellenir); bit alan tamsayıya çevrilir.
    # İlk tam çekim ~22 bin satır (gece tam aktarım da her şeyi baştan çeker). Hesap uygulamada
    # (teknikservis/mikro_serino.py).
    "serino": {
        "tablo": "mikro_serino", "anahtar": "chz_guid",
        "artimli": True,
        "sql": """
SELECT z.chz_Guid, z.chz_serino, z.chz_stok_kodu, s.sto_isim, CAST(z.chz_iptal AS int) AS chz_iptal,
       z.chz_lotno, z.chz_uretim_tarihi, z.chz_aciklama1,
       z.chz_al_tarih, z.chz_al_evr_seri, z.chz_al_evr_sira, z.chz_al_cari_kodu,
       z.chz_al_fiati_ana, z.chz_al_fiati_alt, z.chz_al_fiati_orj,
       z.chz_st_tarih, z.chz_st_evr_seri, z.chz_st_evr_sira, z.chz_st_cari_kodu,
       z.chz_st_fiati_ana, z.chz_st_fiati_alt, z.chz_st_fiati_orj,
       z.chz_GrnBasTarihi AS chz_grn_bas_tarihi, z.chz_GrnBitTarihi AS chz_grn_bit_tarihi,
       z.chz_musteri_garanti_baslangic, z.chz_musteri_garanti_bitis, z.chz_create_date, z.chz_lastup_date
FROM STOK_SERINO_TANIMLARI z
LEFT JOIN STOKLAR s ON s.sto_kod = z.chz_stok_kodu
WHERE z.chz_lastup_date > '{SON}'
""",
    },
    # ── Ürün kartları, barkod, satış fiyat listeleri (Ekim 2026, kullanıcı: "Mikro'da yeni ürün açılınca programa
    # da gelsin"). Küçük tablolar (197 kart, 172 barkod, 496 fiyat, 5 liste): her turda tam çekilir. Kart ↔
    # uygulama eşleşmesi ve "yalnız boş alan dolar" kuralı uygulamada (kayranpm/mikro_urun.py). Ana / alt grup
    # adı alt sorguyla (TOP 1): aynı kodlu iki grup kaydı kartı iki kez döndürmesin. Bit alanlar int'e çevrilir.
    "stok_kart": {
        "tablo": "mikro_stok_kart", "anahtar": "sto_kod",
        "artimli": False,
        "sql": """
SELECT s.sto_kod, s.sto_isim, s.sto_kisa_ismi, s.sto_yabanci_isim, s.sto_marka_kodu, s.sto_kategori_kodu,
       s.sto_anagrup_kod,
       (SELECT TOP 1 g.san_isim FROM STOK_ANA_GRUPLARI g WHERE g.san_kod = s.sto_anagrup_kod AND g.san_iptal=0)
           AS anagrup_isim,
       s.sto_altgrup_kod,
       (SELECT TOP 1 a.sta_isim FROM STOK_ALT_GRUPLARI a WHERE a.sta_kod = s.sto_altgrup_kod AND a.sta_iptal=0)
           AS altgrup_isim,
       s.sto_model_kodu, s.sto_uretici_kodu, s.sto_garanti_sure, s.sto_garanti_sure_tipi, s.sto_GtipNo AS sto_gtipno,
       s.sto_mensei, s.sto_birim1_ad, s.sto_birim1_agirlik, s.sto_birim1_en, s.sto_birim1_boy, s.sto_birim1_yukseklik,
       CAST(s.sto_pasif_fl AS int) AS sto_pasif, s.sto_satis_dursun, s.sto_create_date, s.sto_lastup_date
FROM STOKLAR s WHERE s.sto_iptal=0
""",
    },
    "stok_barkod": {
        "tablo": "mikro_stok_barkod", "anahtar": "bar_guid",
        "artimli": False,
        "sql": """
SELECT bar_Guid, bar_kodu, bar_stokkodu, bar_barkodtipi, bar_birimpntr, CAST(bar_master AS int) AS bar_master,
       bar_lastup_date
FROM BARKOD_TANIMLARI WHERE bar_iptal=0
""",
    },
    "satis_fiyat": {
        "tablo": "mikro_satis_fiyat", "anahtar": "sfiyat_guid",
        "artimli": False,
        "sql": """
SELECT sfiyat_Guid, sfiyat_stokkod, sfiyat_listesirano, sfiyat_deposirano, sfiyat_odemeplan, sfiyat_birim_pntr,
       sfiyat_fiyati, sfiyat_doviz, sfiyat_lastup_date
FROM STOK_SATIS_FIYAT_LISTELERI WHERE sfiyat_iptal=0
""",
    },
    "fiyat_liste": {
        "tablo": "mikro_fiyat_liste", "anahtar": "sfl_sirano",
        "artimli": False,
        "sql": """
SELECT sfl_sirano, sfl_aciklama, CAST(sfl_kdvdahil AS int) AS sfl_kdvdahil, sfl_doviz_uygulama, sfl_sabit_doviz,
       sfl_ilktarih, sfl_sontarih, sfl_lastup_date
FROM STOK_SATIS_FIYAT_LISTE_TANIMLARI WHERE sfl_iptal=0
""",
    },
}

# --------------------------------------------------------------------------- #
# Mikro API istemcisi
# --------------------------------------------------------------------------- #
class MikroHata(Exception):
    pass


def _bos_mu(deger: Any) -> bool:
    """Boş ya da ayarlar_ornek.bat'taki "<...>" yer tutucusu olduğu gibi kalmış."""
    d = str(deger or "").strip()
    return not d or (d.startswith("<") and d.endswith(">"))


class MikroIstemci:
    SQL_ENDPOINT = "/Api/apiMethods/SqlVeriOkuV2"
    SAGLIK_ENDPOINT = "/Api/APIMethods/HealthCheck"

    def __init__(self, ayarlar: dict[str, Any]):
        eksik = [k for k in ("api_key", "firma_kodu", "kullanici", "sifre") if _bos_mu(ayarlar.get(k))]
        if eksik:
            raise MikroHata(f"Eksik ayar(lar): {', '.join(eksik)}")
        self.a = ayarlar
        self.oturum = requests.Session()
        self.oturum.verify = ayarlar["ssl_dogrula"]
        if not ayarlar["ssl_dogrula"]:
            requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]

    # Şifre: MD5("YYYY-MM-DD" + " " + şifre) — her gün değişir.
    def _sifre_hash(self) -> str:
        bugun = datetime.now(TZ).strftime("%Y-%m-%d")
        return hashlib.md5(f"{bugun} {self.a['sifre']}".encode("utf-8")).hexdigest()

    def _mikro_blogu(self) -> dict[str, str]:
        return {
            "ApiKey": self.a["api_key"],
            "CalismaYili": self.a["calisma_yili"] or str(datetime.now(TZ).year),
            "FirmaKodu": self.a["firma_kodu"],
            "KullaniciKodu": self.a["kullanici"],
            "Sifre": self._sifre_hash(),
        }

    def saglik(self) -> bool:
        try:
            r = self.oturum.get(self.a["url"] + self.SAGLIK_ENDPOINT, timeout=15)
            return r.ok
        except requests.RequestException as e:
            log.error("HealthCheck başarısız: %s", e)
            return False

    def sql_oku(self, sql: str) -> list[dict[str, Any]]:
        govde = {"Mikro": self._mikro_blogu(), "SQLSorgu": " ".join(sql.split())}
        try:
            r = self.oturum.post(
                self.a["url"] + self.SQL_ENDPOINT, json=govde, timeout=self.a["zaman_asimi"]
            )
        except requests.RequestException as e:
            raise MikroHata(f"Bağlantı hatası: {e}") from e

        if not r.ok:
            raise MikroHata(f"HTTP {r.status_code}: {r.text[:500]}")
        try:
            veri = r.json()
        except ValueError as e:
            raise MikroHata(f"JSON olmayan yanıt: {r.text[:500]}") from e

        _hata_kontrol(veri)
        return _kayitlari_bul(veri)


def _hata_kontrol(veri: Any) -> None:
    """Yanıtta IsError / ErrorMessage benzeri bir hata işareti varsa fırlatır."""
    stack = [veri]
    while stack:
        d = stack.pop()
        if isinstance(d, dict):
            low = {k.lower(): v for k, v in d.items()}
            if low.get("iserror") is True or low.get("success") is False:
                mesaj = low.get("errormessage") or low.get("message") or json.dumps(d)[:500]
                raise MikroHata(f"Mikro hata döndü: {mesaj}")
            stack.extend(v for v in d.values() if isinstance(v, (dict, list)))
        elif isinstance(d, list):
            stack.extend(x for x in d if isinstance(x, (dict, list)))


def _kayitlari_bul(veri: Any) -> list[dict[str, Any]]:
    """
    SqlVeriOkuV2 yanıt yapısı dokümanda tanımlı değil. Yanıt içindeki ilk
    'satır listesi'ni (dict'lerden oluşan liste) bulup döndürür. Yanıt veriyi
    JSON metni olarak gömüyorsa onu da açar.
    """
    if isinstance(veri, str):
        try:
            veri = json.loads(veri)
        except ValueError:
            return []

    if isinstance(veri, list):
        if veri and all(isinstance(x, dict) for x in veri):
            # Satır listesi mi, yoksa sarmalayıcı listesi mi? (ör. [{"Data":[...]}])
            if len(veri) == 1 and not _duz_satir_mi(veri[0]):
                # Sarmalayıcı: [{"SQLResult1": [...]}]. Sonuç BOŞSA da sarmalayıcı döner; eskiden sarmalayıcının
                # kendisi satır sanılıp yazılıyordu ("sqlresult1 kolonu yok", Ekim 2026 ilk otomatik tur).
                ic = [_kayitlari_bul(v) for v in veri[0].values() if isinstance(v, (list, dict, str))]
                ic = [x for x in ic if x]
                return ic[0] if ic else []
            return veri
        return []

    if isinstance(veri, dict):
        # Öncelikli anahtarlar
        for anahtar in ("Data", "data", "Result", "result", "Rows", "rows", "Value", "value"):
            if anahtar in veri:
                sonuc = _kayitlari_bul(veri[anahtar])
                if sonuc:
                    return sonuc
        for v in veri.values():
            if isinstance(v, (list, dict, str)):
                sonuc = _kayitlari_bul(v)
                if sonuc:
                    return sonuc
    return []


def _duz_satir_mi(d: dict[str, Any]) -> bool:
    """Tüm değerleri skaler olan dict gerçek bir veri satırıdır."""
    return all(not isinstance(v, (list, dict)) for v in d.values())


# --------------------------------------------------------------------------- #
# Supabase istemcisi (PostgREST, service_role anahtarıyla)
# --------------------------------------------------------------------------- #
class Supabase:
    def __init__(self, url: str, key: str):
        if _bos_mu(key):
            raise MikroHata("SUPABASE_SERVICE_KEY tanımlı değil (ayarlar.bat)")
        self.rest = f"{url}/rest/v1"
        self.oturum = requests.Session()
        self.oturum.headers.update({"apikey": key, "Content-Type": "application/json"})
        # Eski tip service_role anahtarı (JWT, "eyJ..." ile başlar) Authorization'da da gönderilir.
        # Yeni tip secret anahtar ("sb_secret_...") yalnızca apikey başlığıyla gönderilir.
        if key.startswith("eyJ"):
            self.oturum.headers["Authorization"] = f"Bearer {key}"

    def _kontrol(self, r: requests.Response) -> requests.Response:
        if not r.ok:
            raise MikroHata(f"Supabase HTTP {r.status_code}: {r.text[:500]}")
        return r

    def upsert(self, tablo: str, satirlar: list[dict[str, Any]], anahtar: str) -> None:
        for i in range(0, len(satirlar), PARTI_BOYUTU):
            self._kontrol(self.oturum.post(
                f"{self.rest}/{tablo}",
                params={"on_conflict": anahtar},
                headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
                data=json.dumps(satirlar[i:i + PARTI_BOYUTU], default=str),
                timeout=120,
            ))

    def eskileri_sil(self, tablo: str, once: datetime) -> None:
        self._kontrol(self.oturum.delete(
            f"{self.rest}/{tablo}",
            params={"senk_zamani": f"lt.{once.isoformat()}"},
            headers={"Prefer": "return=minimal"},
            timeout=120,
        ))

    def durum_oku(self) -> dict[str, str]:
        r = self._kontrol(self.oturum.get(
            f"{self.rest}/mikro_senk_durum",
            params={"select": "tablo,son_cekim", "son_cekim": "not.is.null"},
            timeout=30,
        ))
        return {d["tablo"]: d["son_cekim"] for d in r.json()}

    def durum_yaz(self, tablo: str, **alanlar: Any) -> None:
        alanlar.update(tablo=tablo, guncelleme=datetime.now(TZ).isoformat())
        try:
            self.upsert("mikro_senk_durum", [alanlar], "tablo")
        except MikroHata as e:
            log.error("Durum yazılamadı (%s): %s", tablo, e)


def _sql_tarih(dt: datetime) -> str:
    # SQL Server'ın dil ayarından bağımsız format: YYYYMMDD HH:MM:SS
    return dt.astimezone(TZ).strftime("%Y%m%d %H:%M:%S")


BOOL_KOLONLAR = {"sip_kapat_fl", "sth_iptal"}


def _satiri_hazirla(kayit: dict[str, Any], zaman: str) -> dict[str, Any]:
    """Mikro alan adlarını küçük harfe çevirir, tipleri Postgres'e uygun hale getirir."""
    satir: dict[str, Any] = {}
    for k, v in kayit.items():
        k = k.lower()
        if isinstance(v, str) and v.strip() == "":
            v = None
        if k in BOOL_KOLONLAR and v is not None:
            v = str(v).strip().lower() in ("1", "true")
        satir[k] = v
    satir["senk_zamani"] = zaman
    return satir


# --------------------------------------------------------------------------- #
# Senkronizasyon
# --------------------------------------------------------------------------- #
def senkronize_et(istemci: MikroIstemci, sb: Supabase, tam: bool = False) -> None:
    durum = {} if tam else sb.durum_oku()

    for ad, tanim in SORGULAR.items():
        tablo = tanim["tablo"]
        baslangic = datetime.now(TZ)
        sql = tanim["sql"]
        artimli = tanim["artimli"] and tablo in durum

        if tanim["artimli"]:
            son = (
                datetime.fromisoformat(durum[tablo]) - GUVENLIK_PAYI
                if artimli
                else datetime(1900, 1, 1, tzinfo=TZ)
            )
            sql = sql.replace("{SON}", _sql_tarih(son))

        try:
            kayitlar = istemci.sql_oku(sql)
            satirlar = [_satiri_hazirla(k, baslangic.isoformat()) for k in kayitlar]
            sb.upsert(tablo, satirlar, tanim["anahtar"])
            # Tam çekimde Mikro'da artık olmayan kayıtları temizle.
            # Boş sonuçta silme yapılmaz (bağlantı/okuma sorununa karşı koruma).
            if not artimli and satirlar:
                sb.eskileri_sil(tablo, baslangic)
        except MikroHata as e:
            log.error("[%s] başarısız: %s", tablo, e)
            sb.durum_yaz(tablo, son_hata=str(e)[:1000])
            continue  # son_cekim güncellenmez; bir sonraki turda tekrar dener

        sb.durum_yaz(tablo, son_cekim=baslangic.isoformat(),
                     son_kayit_sayisi=len(satirlar), son_hata=None)
        log.info("[%s] %d kayıt (%s)", tablo, len(satirlar), "artımlı" if artimli else "tam")


# --------------------------------------------------------------------------- #
# Kendini güncelleme (Ekim 2026, kullanıcı: "sunucuya bir daha dosya taşımayayım")
# Uygulama, depodaki mikro_kayran.py'nin güncel hâlini Supabase'e (mikro_aktarici_surum, yalnız service_role
# yazar) koyar. Her tur başında sürüm farklıysa yeni kod indirilir, derlenip denetlenir, dosyanın yerine
# yazılır ve bir SONRAKİ turda çalışır. Bozuk / yarım kod yazılmaz (derlenmezse ya da Mikro'ya yazan uç
# nokta içeriyorsa reddedilir); eski dosya .yedek olarak kalır.
# --------------------------------------------------------------------------- #
# Mikro'ya yazan API uçları (Kaydet / Sil / Guncelle + sürüm no): yeni kodda olursa güncelleme reddedilir
YAZAN_UC_DESENI = r"(Kaydet|Sil|Guncelle|Duzelt)" + r"V\d"
# sys.tables okunamazsa kolonları alınacak temel tablolar
ONEMLI_TABLOLAR = ("STOKLAR", "STOK_HAREKETLERI", "CARI_HESAPLAR", "CARI_HESAP_HAREKETLERI", "BANKALAR",
                   "KASALAR", "ODEME_EMIRLERI", "SIPARISLER", "DEPOLAR", "MUHASEBE_FISLERI", "BARKOD_TANIMLARI",
                   "STOK_SATIS_FIYAT_LISTELERI", "DOVIZ_KURLARI", "MUHASEBE_HESAP_PLANI", "PERSONELLER",
                   "ITHALAT_DOSYALARI")


def _dosya_sha(yol: str) -> str:
    with open(yol, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def guncelleme_uygun_mu(kod: str) -> str:
    """Yeni kod yazılabilir mi; değilse nedeni. Boşsa uygun."""
    if "def senkronize_et(" not in kod or "SqlVeriOkuV2" not in kod:
        return "beklenen içerik yok"
    import re
    if re.search(YAZAN_UC_DESENI, kod):
        return "Mikro'ya yazan uç nokta içeriyor"
    try:
        compile(kod, "mikro_kayran.py", "exec")
    except SyntaxError as e:
        return f"derlenmiyor: {e}"
    return ""


def kendini_guncelle(sb: "Supabase", yol: str | None = None) -> bool:
    """Supabase'teki sürüm dosyadan farklıysa dosyayı günceller. Döner: güncellendi mi. Hata fırlatmaz."""
    yol = yol or os.path.abspath(__file__)
    try:
        r = sb._kontrol(sb.oturum.get(f"{sb.rest}/mikro_aktarici_surum",
                                      params={"select": "kod,sha256", "id": "eq.1"}, timeout=30)).json()
        if not r or not r[0].get("kod"):
            return False
        kod, sha = r[0]["kod"], r[0].get("sha256") or ""
        if hashlib.sha256(kod.encode("utf-8")).hexdigest() != sha:
            log.warning("Güncelleme atlandı: sürüm özeti tutmuyor")
            return False
        if sha == _dosya_sha(yol):
            return False
        neden = guncelleme_uygun_mu(kod)
        if neden:
            log.warning("Güncelleme reddedildi: %s", neden)
            return False
        gecici = yol + ".yeni"
        with open(gecici, "w", encoding="utf-8", newline="\n") as f:
            f.write(kod)
        try:
            os.replace(yol, yol + ".yedek")
        except OSError:
            pass
        os.replace(gecici, yol)
        log.info("Aktarıcı güncellendi (%s); yeni sürüm sonraki turda çalışır.", sha[:12])
        return True
    except Exception as e:  # noqa: BLE001
        log.error("Kendini güncelleme başarısız: %s", e)
        return False


# --------------------------------------------------------------------------- #
# Keşif (Ekim 2026): Mikro'da hangi veri var? Tablolar + satır sayıları, dolu tabloların kolonları,
# depo / banka / kasa listeleri, hareket türü dağılımları. Yalnız okur; günde bir kez çalışır,
# sonuç mikro_kesif tablosuna (anahtar → json). Her sorgu ayrı: biri başarısız olsa da diğerleri yazılır.
# --------------------------------------------------------------------------- #
KESIF_SORGULARI: dict[str, str] = {
    "tablolar": """
SELECT t.name AS tablo, SUM(p.rows) AS satir
FROM sys.tables t JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0, 1)
GROUP BY t.name
""",
    "depolar": "SELECT * FROM DEPOLAR",
    "bankalar": "SELECT * FROM BANKALAR",
    "kasalar": "SELECT * FROM KASALAR",
    "cha_dagilim": """
SELECT cha_evrak_tip, cha_cinsi, cha_cari_cins, cha_tip, cha_normal_Iade AS iade, COUNT(*) AS adet,
       MIN(cha_tarihi) AS ilk, MAX(cha_tarihi) AS son
FROM CARI_HESAP_HAREKETLERI WHERE cha_iptal = 0 AND cha_tarihi >= '20250101'
GROUP BY cha_evrak_tip, cha_cinsi, cha_cari_cins, cha_tip, cha_normal_Iade
""",
    "sth_dagilim": """
SELECT sth_tip, sth_cins, sth_evraktip, sth_normal_iade AS iade, COUNT(*) AS adet,
       MIN(sth_tarih) AS ilk, MAX(sth_tarih) AS son
FROM STOK_HAREKETLERI WHERE sth_iptal = 0 AND sth_tarih >= '20250101'
GROUP BY sth_tip, sth_cins, sth_evraktip, sth_normal_iade
""",
    "cek_senet": """
SELECT sck_tip, sck_sonpoz, sck_doviz, COUNT(*) AS adet, SUM(sck_tutar) AS tutar, MIN(sck_vade) AS ilk_vade,
       MAX(sck_vade) AS son_vade
FROM ODEME_EMIRLERI WHERE sck_iptal = 0 GROUP BY sck_tip, sck_sonpoz, sck_doviz
""",
    "siparis_dagilim": """
SELECT sip_tip, sip_cins, COUNT(*) AS adet, MIN(sip_tarih) AS ilk, MAX(sip_tarih) AS son
FROM SIPARISLER WHERE sip_iptal = 0 GROUP BY sip_tip, sip_cins
""",
    "muhasebe": """
SELECT YEAR(fis_tarih) AS yil, COUNT(*) AS satir FROM MUHASEBE_FISLERI GROUP BY YEAR(fis_tarih)
""",
    # Haftalık ödeme önerisi (kayranacc/mikro_odeme.py): cha_vade 1…999 ödeme planı numarası; planın ortalama
    # günü ve ödeme planlı faturaların taksit vadeleri (Ekim 2026). Küçük tablolar (13 ve ~750 satır).
    # İthalat Mikro'dan (Ekim 2026, kullanıcı: "Geçmiş ithalatlar datalarını Mikro'dan al"): masraf satırlarının
    # dosyaya ve masraf kalemine (navlun, gümrük, ardiye…) nasıl bağlandığını görmek için örnek dosyaların bütün
    # kolonları. Uygulamadaki karşılıkları biliniyor (MASTER-008 = PIFAZ251125-2/-4-1/-5, ZHANYU-005 = GTS251211,
    # VANEX-012). Küçük sorgular, salt okunur.
    "ithalat_masraf_ornek": """
SELECT * FROM CARI_HESAP_HAREKETLERI
WHERE cha_iptal = 0 AND (cha_EXIMkodu IN ('MASTER-008', 'ZHANYU-005', 'VANEX-012')
      OR (cha_cari_cins = 9 AND cha_kod IN ('MASTER-008', 'ZHANYU-005', 'VANEX-012')))
""",
    "ithalat_dosya_ornek": """
SELECT * FROM ITHALAT_DOSYALARI WHERE ith_kodu IN ('MASTER-008', 'ZHANYU-005', 'VANEX-012', 'INNOVISION-017')
""",
    "ithalat_stok_ornek": """
SELECT * FROM STOK_HAREKETLERI WHERE sth_iptal = 0 AND sth_exim_kodu IN ('MASTER-008', 'VANEX-012')
""",
    "ithalat_muhasebe_gruplari": "SELECT * FROM ITHALAT_MUHASEBE_GRUPLARI WHERE IthMuh_iptal = 0",
    "masraf_hesaplari": "SELECT his_kod, his_isim, his_muhkod, his_dovcinsi FROM MASRAF_HESAPLARI WHERE his_iptal = 0",
    "ithalat_masraf_dagilim": """
SELECT cha_evrak_tip, cha_cinsi, cha_cari_cins, cha_tip, COUNT(*) AS adet, COUNT(DISTINCT cha_EXIMkodu) AS dosya,
       MIN(cha_tarihi) AS ilk, MAX(cha_tarihi) AS son
FROM CARI_HESAP_HAREKETLERI WHERE cha_iptal = 0 AND ISNULL(cha_EXIMkodu, '') <> ''
GROUP BY cha_evrak_tip, cha_cinsi, cha_cari_cins, cha_tip
""",
    "odeme_planlari": "SELECT odp_no, odp_kodu, odp_adi, odp_ortgun FROM ODEME_PLANLARI WHERE odp_iptal = 0",
    "odeme_vadeleri": """
SELECT cop_evrak_tip, cop_evrakno_seri, cop_evrakno_sira, cop_vade, cop_tutar, cop_hangi_tutar
FROM CARI_HAREKET_ODEME_VADELERI WHERE cop_iptal = 0
""",
}
KESIF_KOLON_SAYFA = 40      # INFORMATION_SCHEMA sorgusu başına tablo sayısı


def kesif_yap(istemci: "MikroIstemci", sb: "Supabase") -> dict[str, str]:
    """Keşif sorgularını çalıştırıp mikro_kesif'e yazar. Döner: {anahtar: hata ya da ''}."""
    sonuc: dict[str, str] = {}
    simdi = datetime.now(TZ).isoformat()

    def yaz(anahtar: str, veri: Any, hata: str = "") -> None:
        try:
            sb.upsert("mikro_kesif", [{"anahtar": anahtar, "veri": veri, "hata": hata or None, "zaman": simdi}],
                      "anahtar")
        except MikroHata as e:
            log.error("Keşif yazılamadı (%s): %s", anahtar, e)

    tablolar: list[dict[str, Any]] = []
    for anahtar, sql in KESIF_SORGULARI.items():
        try:
            kayit = istemci.sql_oku(" ".join(sql.split()))
            yaz(anahtar, kayit)
            sonuc[anahtar] = ""
            if anahtar == "tablolar":
                tablolar = kayit
        except MikroHata as e:
            yaz(anahtar, None, str(e)[:500])
            sonuc[anahtar] = str(e)[:200]
    dolu = sorted(str(t.get("tablo") or t.get("TABLO") or "") for t in tablolar
                  if float(t.get("satir") or t.get("SATIR") or 0) > 0) or list(ONEMLI_TABLOLAR)
    kolonlar: list[dict[str, Any]] = []
    hata = ""
    for i in range(0, len(dolu), KESIF_KOLON_SAYFA):
        adlar = ",".join("'" + a.replace("'", "''") + "'" for a in dolu[i:i + KESIF_KOLON_SAYFA] if a)
        if not adlar:
            continue
        try:
            kolonlar += istemci.sql_oku(
                "SELECT TABLE_NAME AS tablo, COLUMN_NAME AS kolon, DATA_TYPE AS tip, ORDINAL_POSITION AS sira "
                f"FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME IN ({adlar})")
        except MikroHata as e:
            hata = str(e)[:500]
    yaz("kolonlar", kolonlar, hata)
    sonuc["kolonlar"] = hata
    log.info("Keşif: %d dolu tablo, %d kolon, %d hata", len(dolu), len(kolonlar), sum(1 for h in sonuc.values() if h))
    return sonuc


def kesif_gerekli_mi(sb: "Supabase") -> bool:
    """Bugün keşif yapılmadıysa True."""
    try:
        r = sb._kontrol(sb.oturum.get(f"{sb.rest}/mikro_kesif",
                                      params={"select": "zaman", "anahtar": "eq.tablolar"}, timeout=30)).json()
        if not r:
            return True
        return str(r[0].get("zaman") or "")[:10] < datetime.now(TZ).date().isoformat()
    except Exception:  # noqa: BLE001
        return False


def test_et(istemci: MikroIstemci) -> None:
    print("HealthCheck:", "OK" if istemci.saglik() else "BAŞARISIZ")
    for ad, tanim in SORGULAR.items():
        sql = tanim["sql"].replace("{SON}", _sql_tarih(datetime.now(TZ) - timedelta(days=30)))
        sql = sql.replace("SELECT ", "SELECT TOP 3 ", 1)
        try:
            kayitlar = istemci.sql_oku(sql)
            print(f"\n[{ad}] {len(kayitlar)} kayıt")
            for k in kayitlar:
                print("  ", json.dumps(k, ensure_ascii=False, default=str))
        except MikroHata as e:
            print(f"\n[{ad}] HATA: {e}")


def kilit_al() -> bool:
    """Aynı anda tek aktarım (15 dakikalık tur ile gecelik tam aktarım üst üste binmesin)."""
    try:
        if time.time() - os.path.getmtime(KILIT) > KILIT_ESKI_SN:
            os.remove(KILIT)
    except OSError:
        pass
    try:
        fd = os.open(KILIT, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    return True


def kilit_birak() -> None:
    try:
        os.remove(KILIT)
    except OSError:
        pass


def main() -> None:
    p = argparse.ArgumentParser(description="Mikro -> KAYRAN veri aktarımı")
    p.add_argument("--test", action="store_true", help="bağlantıyı ve sorguları dene")
    p.add_argument("--bir-kez", action="store_true", help="tek sefer aktar ve çık")
    p.add_argument("--tam", action="store_true", help="son çekim tarihini yok say")
    p.add_argument("--aralik", type=int, default=ARALIK_SN, help="sürekli modda saniye aralığı")
    p.add_argument("--ham", action="store_true", help="--test ile ham yanıtı da yazdır")
    p.add_argument("--kesif", action="store_true", help="Mikro'da hangi veri var: keşif sorgularını çalıştır")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    istemci = MikroIstemci(AYARLAR)

    if args.test:
        if args.ham:
            r = istemci.oturum.post(
                AYARLAR["url"] + MikroIstemci.SQL_ENDPOINT,
                json={"Mikro": istemci._mikro_blogu(), "SQLSorgu": "SELECT TOP 2 sto_kod, sto_isim FROM STOKLAR"},
                timeout=60,
            )
            print("HAM YANIT:", r.status_code, r.text[:2000])
        test_et(istemci)
        return

    sb = Supabase(SUPABASE["url"], SUPABASE["key"])

    if args.kesif:
        kesif_yap(istemci, sb)
        return

    if args.bir_kez:
        if not kilit_al():
            log.warning("Başka bir aktarım sürüyor (%s); bu tur atlandı.", KILIT)
            return
        try:
            kendini_guncelle(sb)               # yeni sürüm varsa dosyaya yazılır, sonraki turda çalışır
            senkronize_et(istemci, sb, tam=args.tam)
            if kesif_gerekli_mi(sb):
                kesif_yap(istemci, sb)
        finally:
            kilit_birak()
        return

    tam = args.tam
    while True:
        if kilit_al():
            try:
                senkronize_et(istemci, sb, tam=tam)
                tam = False
            except (MikroHata, requests.RequestException) as e:
                log.error("Tur başarısız: %s", e)
            finally:
                kilit_birak()
        else:
            log.warning("Başka bir aktarım sürüyor; bu tur atlandı.")
        time.sleep(args.aralik)


if __name__ == "__main__":
    main()
