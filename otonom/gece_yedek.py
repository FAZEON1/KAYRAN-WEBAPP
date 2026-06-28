# -*- coding: utf-8 -*-
"""Gece yedeği — GitHub Actions tarafından zamanlı çalışır (Streamlit'ten bağımsız).

Tüm iş verisini tek çok-sayfalı Excel'e yazar; dosya artifact olarak saklanır.

GÜVENLİK: şifre tablosu ve geçici/oturum tabloları yedeğe DAHİL EDİLMEZ.

Ortam değişkenleri (GitHub Secrets):
  SUPABASE_URL  — Supabase proje URL'i
  SUPABASE_KEY  — service_role anahtarı
"""

import os
import sys
from datetime import datetime, timedelta

import pandas as pd
from supabase import create_client

YEDEK_TABLOLAR = [
    "urunler", "firma_stok", "stok_yas", "yoldaki_urunler",
    "kampanyalar", "kampanya_urunler",
    "ref_kayitlari", "ref_butce", "ref_firmalar",
    "ithalat_dosyalari", "ithalat_kalemleri",
    "satislar",
    "odemeler", "bankalar", "cekler", "virmanlar", "haftalar",
    "ts_kayitlar", "ts_gecmis",
    "siparis_onerileri", "talepler", "gorevler", "bildirimler",
    "kur_gunluk", "sistem_ayarlari", "pm_ayarlar",
    "gunluk_giris", "aktif_manuel_kalemler",
]

# Bilerek HARİÇ: kullanici_sifreler, kullanici_durum, aktif_excel_verileri, audit_log, giris_denemeleri

def main():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("HATA: SUPABASE_URL / SUPABASE_KEY ortam değişkenleri eksik.")
        sys.exit(1)

    sb = create_client(url, key)
    ts = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d_%H-%M")
    dosya = f"kayran_yedek_{ts}.xlsx"

    toplam = 0
    with pd.ExcelWriter(dosya, engine="openpyxl") as w:
        for tablo in YEDEK_TABLOLAR:
            try:
                rows = sb.table(tablo).select("*").execute().data or []
            except Exception as e:
                print(f"  ! {tablo}: okunamadı ({e})")
                rows = []
            df = pd.DataFrame(rows) if rows else pd.DataFrame()
            df.to_excel(w, sheet_name=tablo[:31], index=False)
            toplam += len(rows)
            print(f"  • {tablo}: {len(rows)} kayıt")

    print(f"\n✅ Yedek oluşturuldu: {dosya}  ({len(YEDEK_TABLOLAR)} tablo, {toplam} kayıt)")

if __name__ == "__main__":
    main()
