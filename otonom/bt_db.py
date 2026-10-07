# -*- coding: utf-8 -*-
"""Bilgi işlem görevinin veritabanı aracı (Ekim 2026).

Rutinlerde Supabase bağlayıcısı yok; görev veritabanına yalnız bu betikle, ortam değişkenleri
SUPABASE_URL ve SUPABASE_KEY üzerinden (PostgREST, yalnız standart kütüphane) erişir.
Betik yalnız şu tablolara dokunur — talimattaki sınır kodla da sabit:
  bt_olcum        okur; 60 günden eski ölçümleri siler (temizle)
  bt_rapor        okur, yazar
  hata_kayitlari  yalnız okur

Kullanım (otonom/bt_gorevi.md):
  python otonom/bt_db.py ozet                       → JSON: sayfa süreleri (bu hafta / geçen hafta),
                                                       yavaşlayanlar, hatalar, sonucu ölçülecek iyileştirmeler
  python otonom/bt_db.py olcum <modul> [sayfa] [--gun N] [--once TARIH]
                                                    → o sayfanın süre özeti (sonuç ölçümü için)
  python otonom/bt_db.py rapor --tur T --baslik B [--ozet .] [--durum .] [--pr URL]
                                [--olcut .] [--once N] [--sonra N] [--birim .]   → yeni kayıt id
  python otonom/bt_db.py guncelle <id> [--durum .] [--sonra N] [--pr URL] [--ozet .]
  python otonom/bt_db.py temizle                    → 60 günden eski ölçümleri siler
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

def _bt_hesap():
    """shared/bt_hesap.py'yi DOSYADAN yükler: `shared` paketi içe aktarılırken Streamlit'i yükler,
    görev ve GitHub ortamında Streamlit yok."""
    import importlib.util
    yol = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared", "bt_hesap.py")
    spec = importlib.util.spec_from_file_location("bt_hesap", yol)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_H = _bt_hesap()
hata_ozeti, karsilastir, sure_ozeti = _H.hata_ozeti, _H.karsilastir, _H.sure_ozeti

TABLOLAR = {"bt_olcum", "bt_rapor", "hata_kayitlari"}
TURLER = {"calisma", "iyilestirme", "oneri", "sonuc"}
DURUMLAR = {"acik", "otomatik_birlesti", "birlesti", "reddedildi", "oneri", "bilgi"}
SAKLAMA_GUN = 60


def _istek(yontem, tablo, sorgu="", govde=None):
    if tablo not in TABLOLAR:
        raise ValueError(f"izinsiz tablo: {tablo}")
    if tablo == "hata_kayitlari" and yontem != "GET":
        raise ValueError("hata_kayitlari yalnız okunur")
    url = os.environ["SUPABASE_URL"].rstrip("/") + f"/rest/v1/{tablo}?" + sorgu
    key = os.environ["SUPABASE_KEY"]
    r = urllib.request.Request(url, method=yontem, data=None if govde is None else json.dumps(govde).encode(),
                               headers={"apikey": key, "Authorization": f"Bearer {key}",
                                        "Content-Type": "application/json",
                                        "Prefer": "return=representation"})
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


def _iso(d):
    return urllib.parse.quote(d.isoformat())


def ozet(simdi=None):
    simdi = simdi or datetime.now(timezone.utc)
    h1, h2 = simdi - timedelta(days=7), simdi - timedelta(days=14)
    olc = _hepsi("bt_olcum", f"select=zaman,modul,sayfa,ms,hata&zaman=gte.{_iso(h2)}&order=zaman.desc")
    bu = [o for o in olc if str(o.get("zaman")) >= h1.isoformat()]
    gecen = [o for o in olc if str(o.get("zaman")) < h1.isoformat()]
    s_bu, s_gecen = sure_ozeti(bu), sure_ozeti(gecen)
    hatalar = _hepsi("hata_kayitlari", f"select=zaman,yer,mesaj,kritik&zaman=gte.{_iso(h1)}&order=zaman.desc")
    bekleyen = _istek("GET", "bt_rapor", "select=id,zaman,baslik,olcut,once,birim,pr_url,durum"
                                         "&tur=eq.iyilestirme&sonra=is.null&order=zaman.asc&limit=20")
    en_yavas = sorted(({"modul": k[0], "sayfa": k[1], **v} for k, v in s_bu.items()),
                      key=lambda r: -r["p90"])[:10]
    return {"olcum_adedi": {"bu_hafta": len(bu), "gecen_hafta": len(gecen)},
            "en_yavas_bu_hafta": en_yavas,
            "yavaslayan": [r for r in karsilastir(s_gecen, s_bu) if r["fark_yuzde"] > 15][:10],
            "hatalar_bu_hafta": hata_ozeti(hatalar)[:15],
            "sonucu_olculecek": bekleyen}


def olcum(modul, sayfa=None, gun=7, once=None):
    """Bir sayfanın süre özeti. once verilirse o tarihten ÖNCEKİ `gun` gün, yoksa son `gun` gün."""
    bit = datetime.fromisoformat(once).replace(tzinfo=timezone.utc) if once else datetime.now(timezone.utc)
    bas = bit - timedelta(days=gun)
    q = (f"select=zaman,modul,sayfa,ms,hata&modul=eq.{urllib.parse.quote(modul)}"
         f"&zaman=gte.{_iso(bas)}&zaman=lt.{_iso(bit)}")
    if sayfa:
        q += f"&sayfa=eq.{urllib.parse.quote(sayfa)}"
    oz = sure_ozeti(_hepsi("bt_olcum", q))
    return {f"{k[0]}/{k[1]}": v for k, v in oz.items()}


def _arg(args, ad, tip=str):
    if ad in args:
        i = args.index(ad)
        v = args[i + 1] if i + 1 < len(args) else ""
        return tip(v) if v != "" else None
    return None


def _konumsal(args):
    """Bayrak ve bayrak değeri olmayan argümanlar."""
    out, atla = [], False
    for a in args:
        if atla:
            atla = False
        elif a.startswith("--"):
            atla = True
        else:
            out.append(a)
    return out


def rapor_satiri(args):
    tur, baslik = _arg(args, "--tur"), _arg(args, "--baslik")
    if tur not in TURLER or not baslik:
        raise ValueError(f"--tur {sorted(TURLER)} ve --baslik gerekli")
    durum = _arg(args, "--durum")
    if durum and durum not in DURUMLAR:
        raise ValueError(f"--durum {sorted(DURUMLAR)}")
    satir = {"tur": tur, "baslik": baslik[:300], "ozet": (_arg(args, "--ozet") or "")[:4000],
             "durum": durum, "pr_url": _arg(args, "--pr"), "olcut": _arg(args, "--olcut"),
             "once": _arg(args, "--once", float), "sonra": _arg(args, "--sonra", float),
             "birim": _arg(args, "--birim")}
    return {k: v for k, v in satir.items() if v not in (None, "")}


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    k, args = argv[0], argv[1:]
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_KEY"):
        print("HATA: SUPABASE_URL / SUPABASE_KEY tanımlı değil")
        return 1
    if k == "ozet":
        print(json.dumps(ozet(), ensure_ascii=False, indent=1, default=str))
    elif k == "olcum":
        pos = _konumsal(args)
        print(json.dumps(olcum(pos[0], pos[1] if len(pos) > 1 else None,
                               _arg(args, "--gun", int) or 7, _arg(args, "--once")), ensure_ascii=False))
    elif k == "rapor":
        r = _istek("POST", "bt_rapor", "", rapor_satiri(args))
        print(r[0]["id"] if r else "YAZILAMADI")
    elif k == "guncelle":
        rid = int(args[0])
        yama = {a: v for a, v in (("durum", _arg(args, "--durum")), ("sonra", _arg(args, "--sonra", float)),
                                  ("pr_url", _arg(args, "--pr")), ("ozet", _arg(args, "--ozet"))) if v is not None}
        if yama.get("durum") and yama["durum"] not in DURUMLAR:
            raise ValueError(f"--durum {sorted(DURUMLAR)}")
        r = _istek("PATCH", "bt_rapor", f"id=eq.{rid}", yama)
        print("TAMAM" if r else "BULUNAMADI")
    elif k == "temizle":
        sinir = datetime.now(timezone.utc) - timedelta(days=SAKLAMA_GUN)
        r = _istek("DELETE", "bt_olcum", f"zaman=lt.{_iso(sinir)}")
        print(f"{len(r)} eski ölçüm silindi")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
