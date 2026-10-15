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
            ic = [_kayitlari_bul(v) for v in veri[0].values() if isinstance(v, (list, dict, str))]
            ic = [x for x in ic if x]
            if ic and len(veri) == 1 and not _duz_satir_mi(veri[0]):
                return ic[0]
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


BOOL_KOLONLAR = {"sip_kapat_fl"}


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

    if args.bir_kez:
        if not kilit_al():
            log.warning("Başka bir aktarım sürüyor (%s); bu tur atlandı.", KILIT)
            return
        try:
            senkronize_et(istemci, sb, tam=args.tam)
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
