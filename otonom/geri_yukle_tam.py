# -*- coding: utf-8 -*-
"""otonom/geri_yukle_tam.py — GECE YEDEĞİNDEN (JSON) TAM GERİ YÜKLEME

Gece yedeği artifact'ındaki `kayran_yedek_<zaman>_json/` klasörünü bir Supabase projesine
geri yazar (upsert, 500'lük partiler, shared/yedek_tablolari.YEDEK_TABLOLAR sırasıyla:
önce bağımsız tablolar, sonra onlara bağlı olanlar).

GÜVENLİK TASARIMI
  - VARSAYILAN KURU ÇALIŞMA: hiçbir yere bağlanmaz, yazmaz; dosyaları doğrular (manifest
    sha256 + satır sayısı) ve her tabloya kaç satır / kaç parti yazacağını sayar.
  - Gerçek yazma YALNIZ `--hedef-url` açıkça verilir VE `--onayliyorum` bayrağı varsa.
  - Hedef canlı proje (qspwlqegoeudifxxrxcj) ise ayrıca `--canli-uzerine-yaz` gerekir;
    yoksa reddeder.
  - Anahtar yalnız ortam değişkeninden okunur (HEDEF_SUPABASE_KEY), ekrana basılmaz.
  - HARİÇ tablolar (şifreler, sırlar) yedekte yoktur ve geri yüklenmez: kullanıcı şifreleri,
    bayi hesapları ve SMTP ayarı hedefte ayrıca kurulmalıdır.

Kullanım
  python otonom/geri_yukle_tam.py --yedek kayran_yedek_2026-10-14_05-00_json
  python otonom/geri_yukle_tam.py --yedek <klasör> --tablo satislar,iadeler
  HEDEF_SUPABASE_KEY=... python otonom/geri_yukle_tam.py --yedek <klasör> \\
      --hedef-url https://<yeni-proje>.supabase.co --onayliyorum

Notlar
  - Upsert birincil anahtara göre birleştirir: aynı kayıt varsa üzerine yazar, yoksa ekler.
    Hedefte yedekte olmayan fazladan satırlar SİLİNMEZ.
  - Sayaçlı (bigserial) id'ler elle yazıldığı için hedefte sıra sayaçları geride kalır;
    yazma sonunda her tablo için çalıştırılacak `setval` SQL'i yazdırılır.
  - `GENERATED ALWAYS` kimlikli tablolar (yuklemeler) PostgREST üzerinden id ile yazılamaz;
    o tablo hata verirse rapora düşer, diğerleri devam eder.
"""

import argparse
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path


def _yedek_tablolari():
    """shared/yedek_tablolari.py'yi DOSYADAN yükler: `shared` paketi içe aktarılırken Streamlit'i
    yükler, GitHub Actions görevinde Streamlit kurulu değil (bkz. otonom/bt_db.py)."""
    import importlib.util
    ad = "yedek_tablolari"
    if ad in sys.modules:
        return sys.modules[ad]
    yol = Path(__file__).resolve().parent.parent / "shared" / "yedek_tablolari.py"
    spec = importlib.util.spec_from_file_location(ad, yol)
    m = importlib.util.module_from_spec(spec)
    sys.modules[ad] = m
    spec.loader.exec_module(m)
    return m


_YT = _yedek_tablolari()
HARIC, YEDEK_TABLOLAR, canli_mi = _YT.HARIC, _YT.YEDEK_TABLOLAR, _YT.canli_mi

PARTI = 500
ANAHTAR_DEGISKENI = "HEDEF_SUPABASE_KEY"


class GeriYuklemeHatasi(Exception):
    pass


def yedegi_oku(dizin, tablolar=None):
    """[(tablo, satirlar)] — YEDEK_TABLOLAR sırasıyla; manifest'e göre doğrulanmış.
    Manifest'te listede olmayan tablolar en sona eklenir; HARİÇ tablolar atlanır."""
    dizin = Path(dizin)
    mpath = dizin / "manifest.json"
    if not mpath.exists():
        raise GeriYuklemeHatasi(f"manifest.json yok: {dizin}")
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    kayit = {m["tablo"]: m for m in manifest.get("tablolar", []) if m.get("dosya")}
    sira = [t for t in YEDEK_TABLOLAR if t in kayit] + \
           [t for t in kayit if t not in YEDEK_TABLOLAR]
    if tablolar:
        bilinmeyen = set(tablolar) - set(kayit)
        if bilinmeyen:
            raise GeriYuklemeHatasi(f"yedekte olmayan tablo: {sorted(bilinmeyen)}")
        sira = [t for t in sira if t in tablolar]
    out = []
    for t in sira:
        if t in HARIC:
            continue
        m = kayit[t]
        ham = gzip.open(dizin / m["dosya"], "rb").read()
        if m.get("sha256") and hashlib.sha256(ham).hexdigest() != m["sha256"]:
            raise GeriYuklemeHatasi(f"{t}: dosya özeti tutmuyor (bozuk ya da değiştirilmiş)")
        govde = json.loads(ham.decode("utf-8"))
        satirlar = govde.get("satirlar") or []
        if m.get("durum") != "tamam" or len(satirlar) != m.get("beklenen"):
            raise GeriYuklemeHatasi(
                f"{t}: yedek eksik (durum {m.get('durum')}, beklenen {m.get('beklenen')}, "
                f"dosyada {len(satirlar)}) — bu yedekten tam geri yükleme yapılamaz")
        out.append((t, satirlar))
    return out


def partiler(satirlar, n=PARTI):
    for i in range(0, len(satirlar), n):
        yield satirlar[i:i + n]


def plan_yazdir(veri):
    toplam = 0
    for t, satirlar in veri:
        p = (len(satirlar) + PARTI - 1) // PARTI
        print(f"  - {t}: {len(satirlar)} satır, {p} parti")
        toplam += len(satirlar)
    print(f"Toplam: {len(veri)} tablo, {toplam} satır.")
    return toplam


def setval_sql(veri):
    satir = []
    for t, satirlar in veri:
        if satirlar and isinstance(satirlar[0].get("id"), int):
            satir.append(f"SELECT setval(pg_get_serial_sequence('public.{t}', 'id'), "
                         f"(SELECT COALESCE(MAX(id), 1) FROM public.{t}));")
    return satir


def yaz(sb, veri, cikti=print):
    """Upsert, 500'lük partiler. Dönüş: {tablo: hata mesajı} (boşsa hepsi yazıldı)."""
    hatalar = {}
    for t, satirlar in veri:
        yazilan = 0
        try:
            for p in partiler(satirlar):
                sb.table(t).upsert(p).execute()
                yazilan += len(p)
            cikti(f"  - {t}: {yazilan} satır yazıldı")
        except Exception as e:
            hatalar[t] = f"{type(e).__name__}: {str(e)[:200]}"
            cikti(f"  ! {t}: {yazilan}/{len(satirlar)} satırdan sonra HATA — {hatalar[t]}")
    return hatalar


def calistir(argv=None, istemci_fabrikasi=None, ortam=None):
    """Komut satırı girişi. Dönüş: çıkış kodu (0 tamam, 1 yazma hatası, 2 reddedildi)."""
    ortam = os.environ if ortam is None else ortam
    ap = argparse.ArgumentParser(description="Gece yedeğinden (JSON) tam geri yükleme")
    ap.add_argument("--yedek", required=True, help="kayran_yedek_<zaman>_json klasörü")
    ap.add_argument("--tablo", default="", help="yalnız bu tablolar (virgülle)")
    ap.add_argument("--hedef-url", default="", help="hedef Supabase URL'i (yazmak için şart)")
    ap.add_argument("--onayliyorum", action="store_true", help="gerçekten yaz")
    ap.add_argument("--canli-uzerine-yaz", action="store_true",
                    help="hedef CANLI proje olsa bile yaz (yalnız felaket kurtarmada)")
    a = ap.parse_args(argv)

    tablolar = [t.strip() for t in a.tablo.split(",") if t.strip()]
    try:
        veri = yedegi_oku(a.yedek, tablolar or None)
    except GeriYuklemeHatasi as e:
        print(f"HATA: {e}")
        return 2

    yazacak = bool(a.hedef_url) and a.onayliyorum
    if not yazacak:
        print("KURU ÇALIŞMA — hiçbir şey yazılmayacak. Yazılacak olan:")
        plan_yazdir(veri)
        if a.hedef_url and not a.onayliyorum:
            print("Yazmak için --onayliyorum bayrağını da ver.")
        elif not a.hedef_url:
            print("Yazmak için --hedef-url ve --onayliyorum ver.")
        return 0

    if canli_mi(a.hedef_url) and not a.canli_uzerine_yaz:
        print("REDDEDİLDİ: hedef CANLI proje. Canlının üzerine yazmak için ayrıca "
              "--canli-uzerine-yaz gerekir (önce yeni/boş bir projede deneyin).")
        return 2
    key = ortam.get(ANAHTAR_DEGISKENI)
    if not key:
        print(f"HATA: {ANAHTAR_DEGISKENI} ortam değişkeni yok (hedef projenin service_role anahtarı).")
        return 2

    if istemci_fabrikasi is None:
        from supabase import create_client as istemci_fabrikasi
    sb = istemci_fabrikasi(a.hedef_url, key)
    print(f"YAZILIYOR → {a.hedef_url}")
    plan_yazdir(veri)
    hatalar = yaz(sb, veri)
    sql = setval_sql([(t, s) for t, s in veri if t not in hatalar])
    if sql:
        print("\nSıra sayaçlarını ileri almak için hedefte SQL düzenleyicide çalıştırın:")
        for s in sql:
            print("  " + s)
    print("\nHatırlatma: bu tablolar bilerek yedekte yoktur (şifreler/sırlar), hedefte ayrıca kurulmalı: "
          + ", ".join(sorted(HARIC)))
    if hatalar:
        print(f"\nHATA: {len(hatalar)} tablo yazılamadı: {', '.join(hatalar)}")
        return 1
    print("\nGeri yükleme TAMAM.")
    return 0


if __name__ == "__main__":
    sys.exit(calistir())
