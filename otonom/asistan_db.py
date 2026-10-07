# -*- coding: utf-8 -*-
"""Asistan görevlerinin veritabanı aracı (Ekim 2026): pazar araştırmacısı ve gümrük danışmanı.

claude.ai'deki görevlerde Supabase bağlayıcısı yok; görevler veritabanına yalnız bu betikle, ortam
değişkenleri SUPABASE_URL ve SUPABASE_KEY üzerinden (PostgREST, yalnız standart kütüphane) erişir.
Betik yalnız şu tablolara dokunur — talimattaki sınır kodla da sabit:
  satislar, urunler     yalnız okur
  asistan_rapor         okur, yeni rapor yazar
  gumruk_sorgulari      okur; durum / sonuç / özet alanlarını günceller

Kullanım:
  python otonom/asistan_db.py pazar-veri [--gun 90] [--en-cok 30]  → JSON: çok satan ürünler, kategoriler,
                                                                    önceki 4 pazar raporunun başlık+özeti
  python otonom/asistan_db.py rapor --baslik B --ozet O --icerik-dosya rapor.md   → yeni rapor id
  python otonom/asistan_db.py gumruk-bekleyen                       → JSON: sıradaki sorgular
  python otonom/asistan_db.py gumruk-al <id>                        → durum 'calisiyor'
  python otonom/asistan_db.py gumruk-yaz <id> --dosya sonuc.json --ozet "..."   → doğrular, 'tamam'
  python otonom/asistan_db.py gumruk-hata <id> --ozet "..."         → durum 'hata'
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone


def _asistan_hesap():
    """shared/asistan_hesap.py'yi DOSYADAN yükler (`shared` paketi Streamlit'i yükler; görevde yok)."""
    import importlib.util
    yol = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared", "asistan_hesap.py")
    spec = importlib.util.spec_from_file_location("asistan_hesap", yol)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_H = _asistan_hesap()
OKUNUR = {"satislar", "urunler"}
YAZILIR = {"asistan_rapor", "gumruk_sorgulari"}
TAKILMA_SAAT = 2          # 'calisiyor'da bu kadar kalan sorgu yeniden sıraya alınır


def _istek(yontem, tablo, sorgu="", govde=None):
    if tablo not in OKUNUR | YAZILIR:
        raise ValueError(f"izinsiz tablo: {tablo}")
    if tablo in OKUNUR and yontem != "GET":
        raise ValueError(f"{tablo} yalnız okunur")
    if yontem == "DELETE":
        raise ValueError("silme yok")
    url = os.environ["SUPABASE_URL"].rstrip("/") + f"/rest/v1/{tablo}?" + sorgu
    key = os.environ["SUPABASE_KEY"]
    r = urllib.request.Request(url, method=yontem, data=None if govde is None else json.dumps(govde).encode(),
                               headers={"apikey": key, "Authorization": f"Bearer {key}",
                                        "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(r, timeout=60) as y:
        return json.loads(y.read() or b"[]")


def _hepsi(tablo, sorgu):
    out, adim, i = [], 1000, 0
    while True:
        r = _istek("GET", tablo, f"{sorgu}&offset={i}&limit={adim}")
        out += r
        if len(r) < adim:
            return out
        i += adim


def _arg(args, ad, tip=str):
    if ad in args:
        i = args.index(ad)
        v = args[i + 1] if i + 1 < len(args) else ""
        return tip(v) if v != "" else None
    return None


def _simdi():
    return datetime.now(timezone.utc)


def pazar_veri(gun=90, en_cok=30):
    bas = (_simdi() - timedelta(days=gun)).date().isoformat()
    sat = _hepsi("satislar", f"select=sku,urun_adi,kanal,adet,birim_satis&tarih=gte.{bas}&order=id.asc")
    ur = _hepsi("urunler", "select=sku,urun_adi,kategori,marka,bizim_stok&order=sku.asc")
    oz = _H.pazar_ozeti(sat, ur, en_cok)
    oz["onceki_raporlar"] = _istek("GET", "asistan_rapor",
                                   "select=zaman,baslik,ozet&asistan=eq.pazar&order=zaman.desc&limit=4")
    oz["donem_gun"] = gun
    return oz


def gumruk_bekleyen():
    sinir = (_simdi() - timedelta(hours=TAKILMA_SAAT)).isoformat()
    bek = _istek("GET", "gumruk_sorgulari", "select=*&durum=eq.bekliyor&order=zaman.asc&limit=10")
    tak = _istek("GET", "gumruk_sorgulari",
                 f"select=*&durum=eq.calisiyor&guncelleme=lt.{urllib.parse.quote(sinir)}&order=zaman.asc&limit=10")
    return bek + tak


def _guncelle(sid, alanlar):
    alanlar = dict(alanlar, guncelleme=_simdi().isoformat())
    return _istek("PATCH", "gumruk_sorgulari", f"id=eq.{int(sid)}", alanlar)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    k, args = argv[0], argv[1:]
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_KEY"):
        print("HATA: SUPABASE_URL / SUPABASE_KEY tanımlı değil")
        return 1
    if k == "pazar-veri":
        print(json.dumps(pazar_veri(_arg(args, "--gun", int) or 90, _arg(args, "--en-cok", int) or 30),
                         ensure_ascii=False, indent=1, default=str))
    elif k == "rapor":
        baslik, ozet, dosya = _arg(args, "--baslik"), _arg(args, "--ozet"), _arg(args, "--icerik-dosya")
        if not baslik or not ozet or not dosya:
            raise ValueError("--baslik, --ozet ve --icerik-dosya gerekli")
        with open(dosya, encoding="utf-8") as f:
            icerik = f.read()
        r = _istek("POST", "asistan_rapor", "", {"asistan": "pazar", "baslik": baslik[:200], "ozet": ozet[:1200],
                                                 "icerik": icerik[:60000]})
        print(r[0]["id"] if r else "YAZILAMADI")
    elif k == "gumruk-bekleyen":
        print(json.dumps(gumruk_bekleyen(), ensure_ascii=False, indent=1, default=str))
    elif k == "gumruk-al":
        print("TAMAM" if _guncelle(args[0], {"durum": "calisiyor"}) else "BULUNAMADI")
    elif k == "gumruk-yaz":
        with open(_arg(args, "--dosya"), encoding="utf-8") as f:
            sonuc, hatalar = _H.sonuc_dogrula(json.load(f))
        if hatalar:
            print("YAZILMADI, sonuç biçimi hatalı:\n- " + "\n- ".join(hatalar))
            return 1
        r = _guncelle(args[0], {"durum": "tamam", "sonuc": sonuc, "ozet": (_arg(args, "--ozet") or "")[:2000]})
        print("TAMAM" if r else "BULUNAMADI")
    elif k == "gumruk-hata":
        r = _guncelle(args[0], {"durum": "hata", "ozet": (_arg(args, "--ozet") or "")[:2000]})
        print("TAMAM" if r else "BULUNAMADI")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
