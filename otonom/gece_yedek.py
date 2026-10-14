# -*- coding: utf-8 -*-
"""Gece yedeği — GitHub Actions tarafından zamanlı çalışır (Streamlit'ten bağımsız).

Çıktılar (ikisi de aynı artifact'a gider):
  kayran_yedek_<zaman>.xlsx          — her tablo ayrı sayfa (okumak / aramak için)
  kayran_yedek_<zaman>_json/         — ASIL YEDEK: tablo başına <tablo>.json.gz + manifest.json
                                       (Excel'in hücre/tarih/uzunluk sorunları yok;
                                        otonom/geri_yukle_tam.py bunu geri yükler)

Tablo listesi, hariç tutulanlar ve sayfalı okuma: shared/yedek_tablolari.py (tek kaynak;
dosyadan yüklenir, Streamlit gerekmez).
Her tablo 1.000'lik sayfalarla okunur ve count="exact" ile karşılaştırılır; bir tablo eksik
ya da okunamamışsa dosyalar yine yazılır ama çıkış kodu 1 olur (iş kırmızı görünür).

GÜVENLİK: şifre/sır içeren ve geçici/oturum tabloları yedeğe DAHİL EDİLMEZ (HARIC listesi).

Ortam değişkenleri (GitHub Secrets):
  SUPABASE_URL  — Supabase proje URL'i
  SUPABASE_KEY  — service_role anahtarı
"""

import gzip
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
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
HARIC, YEDEK_TABLOLAR = _YT.HARIC, _YT.YEDEK_TABLOLAR
excel_satirlari, tumunu_oku = _YT.excel_satirlari, _YT.tumunu_oku


def _zaman():
    return (datetime.now(timezone.utc) + timedelta(hours=3)).strftime("%Y-%m-%d_%H-%M")


def json_yaz(sonuclar, dizin, ts):
    """Tablo başına gzip JSON + manifest.json. Manifest dosya özetlerini (sha256) ve
    beklenen/okunan sayıları tutar; geri yükleme bunlarla doğrular."""
    dizin = Path(dizin)
    dizin.mkdir(parents=True, exist_ok=True)
    manifest = {"surum": 1, "zaman": ts, "haric": sorted(HARIC), "tablolar": []}
    for s in sonuclar:
        if s["durum"] == "yok":
            manifest["tablolar"].append({"tablo": s["tablo"], "durum": "yok"})
            continue
        govde = {"tablo": s["tablo"], "beklenen": s["beklenen"], "okunan": s["okunan"],
                 "sira": s["sira"], "satirlar": s["satirlar"]}
        ham = json.dumps(govde, ensure_ascii=False, default=str).encode("utf-8")
        ad = f"{s['tablo']}.json.gz"
        with gzip.open(dizin / ad, "wb") as f:
            f.write(ham)
        manifest["tablolar"].append({
            "tablo": s["tablo"], "dosya": ad, "durum": s["durum"],
            "beklenen": s["beklenen"], "okunan": s["okunan"],
            "sha256": hashlib.sha256(ham).hexdigest(), "mesaj": s["mesaj"],
        })
    with open(dizin / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    return dizin


def excel_yaz(sonuclar, dosya):
    import pandas as pd
    with pd.ExcelWriter(dosya, engine="openpyxl") as w:
        for s in sonuclar:
            rows = excel_satirlari(s["satirlar"])
            df = pd.DataFrame(rows) if rows else pd.DataFrame()
            df.to_excel(w, sheet_name=s["tablo"][:31], index=False)
    return dosya


def yedek_al(sb, cikti=".", ts=None, tablolar=None):
    """Okur, Excel + JSON yazar. Dönüş: (excel yolu, json dizini, sonuçlar, hatalılar)."""
    ts = ts or _zaman()
    cikti = Path(cikti)

    def _yaz(s):
        if s["durum"] == "tamam":
            print(f"  - {s['tablo']}: {s['okunan']} kayıt" + (f" ({s['mesaj']})" if s["mesaj"] else ""))
        elif s["durum"] == "yok":
            print(f"  - {s['tablo']}: {s['mesaj']}")
        else:
            print(f"  ! {s['tablo']}: {s['durum'].upper()} — {s['mesaj']}")

    sonuclar, hatali = tumunu_oku(sb, tablolar, ilerleme=_yaz)
    jdizin = json_yaz(sonuclar, cikti / f"kayran_yedek_{ts}_json", ts)
    xlsx = excel_yaz(sonuclar, cikti / f"kayran_yedek_{ts}.xlsx")
    return xlsx, jdizin, sonuclar, hatali


def main():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("HATA: SUPABASE_URL / SUPABASE_KEY ortam değişkenleri eksik.")
        sys.exit(1)

    from supabase import create_client
    sb = create_client(url, key)
    xlsx, jdizin, sonuclar, hatali = yedek_al(sb)
    toplam = sum(s["okunan"] for s in sonuclar)
    print(f"\nYedek yazıldı: {xlsx} + {jdizin}/  ({len(YEDEK_TABLOLAR)} tablo, {toplam} kayıt)")

    # ── Günlük P&L materialized view'ini tazele (Patron Panosu trendi güncel kalsın) ──
    try:
        _r = sb.rpc("mv_gunluk_pnl_tazele").execute()
        print(f"mv_gunluk_pnl tazelendi: {_r.data}")
    except Exception as e:
        print(f"  ! mv_gunluk_pnl tazelenemedi (view henüz kurulmamış olabilir): {e}")

    if hatali:
        print(f"\nHATA: YEDEK BAŞARISIZ — {len(hatali)} tablo eksik ya da okunamadı:")
        for s in hatali:
            print(f"  ! {s['tablo']}: {s['durum']} — {s['mesaj']}")
        sys.exit(1)
    print("Yedek TAMAM: her tablonun okunan satır sayısı veritabanındaki sayıyla aynı.")


if __name__ == "__main__":
    main()
