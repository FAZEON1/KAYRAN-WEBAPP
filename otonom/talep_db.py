# -*- coding: utf-8 -*-
"""Zamanlanmış Claude talep görevinin veritabanı aracı (Ekim 2026).

Rutinlerde Supabase bağlayıcısı kullanılamıyor; görev veritabanına bu betikle, ortam değişkenleri
SUPABASE_URL ve SUPABASE_KEY üzerinden (PostgREST, yalnız standart kütüphane) erişir. Betik yalnız
`talepler` tablosunu okur ve yalnız claude_* alanlarını yazar — talimattaki "veritabanına başka bir
şey yazma" kuralı kodla da sınırlı.

Kullanım (otonom/claude_talep_gorevi.md):
  python otonom/talep_db.py sonraki            → YOK | MESGUL | AL <id> (bayatları 'hata' yapar)
  python otonom/talep_db.py ustlen <id>        → talebin tamamı (JSON) ya da ALINAMADI
  python otonom/talep_db.py yaz <id> <durum> [--not METIN] [--pr URL]   (durum: soru|pr_hazir|hata)
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

BAYAT_SAAT = 3
YAZILABILIR = {"soru", "pr_hazir", "hata"}
_ALANLAR = ("id,gonderen,konu,mesaj,kategori,oncelik,cevap,durum,claude_durum,claude_onay_notu,"
            "claude_onaylayan,claude_not,claude_pr_url,claude_guncelleme,claude_onay_tarihi")


def _simdi():
    return datetime.now(timezone.utc)


def _istek(yontem, sorgu, govde=None):
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/talepler?" + sorgu
    key = os.environ["SUPABASE_KEY"]
    r = urllib.request.Request(url, method=yontem, data=None if govde is None else json.dumps(govde).encode(),
                               headers={"apikey": key, "Authorization": f"Bearer {key}",
                                        "Content-Type": "application/json",
                                        "Prefer": "return=representation"})
    with urllib.request.urlopen(r, timeout=30) as y:
        return json.loads(y.read() or b"[]")


def _zaman(v):
    try:
        z = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return z if z.tzinfo else z.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def karar(satirlar, simdi):
    """('YOK'|'MESGUL'|'AL', id, bayat_idler). Sıra: claude_onay_tarihi (en eski önce)."""
    bayat, mesgul = [], False
    for s in satirlar:
        if s.get("claude_durum") == "calisiyor":
            z = _zaman(s.get("claude_guncelleme"))
            if z and simdi - z < timedelta(hours=BAYAT_SAAT):
                mesgul = True
            else:
                bayat.append(s["id"])
    if mesgul:
        return "MESGUL", None, bayat
    bekleyen = sorted((s for s in satirlar if s.get("claude_durum") == "onaylandi"),
                      key=lambda s: str(s.get("claude_onay_tarihi") or ""))
    return ("AL", bekleyen[0]["id"], bayat) if bekleyen else ("YOK", None, bayat)


def yazilacak(durum, not_=None, pr=None, simdi=None):
    if durum not in YAZILABILIR:
        raise ValueError(f"durum {sorted(YAZILABILIR)} olmalı: {durum}")
    g = {"claude_durum": durum, "claude_guncelleme": (simdi or _simdi()).isoformat()}
    if not_ is not None:
        g["claude_not"] = not_
    if pr:
        g["claude_pr_url"] = pr
    return g


def sonraki():
    satirlar = _istek("GET", "select=id,claude_durum,claude_guncelleme,claude_onay_tarihi"
                             "&claude_durum=in.(onaylandi,calisiyor)")
    k, tid, bayat = karar(satirlar, _simdi())
    for b in bayat:
        _istek("PATCH", f"id=eq.{int(b)}&claude_durum=eq.calisiyor",
               yazilacak("hata", "Oturum yarıda kaldı; yeniden gönderilebilir."))
    return f"AL {tid}" if k == "AL" else k


def ustlen(tid):
    g = {"claude_durum": "calisiyor", "claude_guncelleme": _simdi().isoformat()}
    r = _istek("PATCH", f"id=eq.{int(tid)}&claude_durum=eq.onaylandi&select={_ALANLAR}", g)
    return r[0] if r else None


def yaz(tid, durum, not_=None, pr=None):
    r = _istek("PATCH", f"id=eq.{int(tid)}&select=id,claude_durum", yazilacak(durum, not_, pr))
    return bool(r)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == "sonraki":
        print(sonraki())
    elif argv[0] == "ustlen":
        r = ustlen(argv[1])
        print(json.dumps(r, ensure_ascii=False, indent=1) if r else "ALINAMADI")
    elif argv[0] == "yaz":
        tid, durum, ek = argv[1], argv[2], argv[3:]
        not_ = ek[ek.index("--not") + 1] if "--not" in ek else None
        pr = ek[ek.index("--pr") + 1] if "--pr" in ek else None
        print("YAZILDI" if yaz(tid, durum, not_, pr) else "BULUNAMADI")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
