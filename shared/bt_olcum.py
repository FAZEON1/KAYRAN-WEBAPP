# -*- coding: utf-8 -*-
"""Sayfa açılış süresi ölçümü (Ekim 2026, bilgi işlem elemanı).

app.py her sayfa çiziminin süresini buraya verir; kayıt arka planda (ayrı iş parçacığında)
bt_olcum tablosuna yazılır — sayfayı bekletmez. KURALLAR (hata_log ile aynı):
  · kaydet() ASLA istisna fırlatmaz, çağıranı bozamaz.
  · Tablo yoksa (veritabani/23_bilgi_islem.sql kurulmadan) sessizce geçer.
"""
import threading

TABLO = "bt_olcum"


def alt_sayfa(modul, oturum):
    """Modülün açık alt sayfasının kodu (shared.gezinme); yoksa boş."""
    try:
        from shared.gezinme import MODULLER
        m = next((m for m in MODULLER if m.get("kod") == modul), None)
        if not m or not m.get("anahtar"):
            return ""
        secim = oturum.get(m["anahtar"])
        for secenek, kod, *_ in m.get("sayfalar") or []:
            if secim == secenek:
                return kod
        return str(secim or "")[:60]
    except Exception:  # noqa: BLE001
        return ""


def _yaz(istemci, satir):
    try:
        istemci.table(TABLO).insert(satir).execute()
    except Exception:  # noqa: BLE001
        pass


def kaydet(modul, sayfa, ms, hata=False, kullanici=""):
    """İstemci ana akışta alınır (Streamlit önbelleği iş parçacığında uyarı verir); yazma arka planda."""
    try:
        from shared.auth import _get_supabase
        istemci = _get_supabase()
        satir = {"modul": str(modul or "")[:40], "sayfa": str(sayfa or "")[:60], "ms": int(max(ms, 0)),
                 "hata": bool(hata), "kullanici": str(kullanici or "")[:40]}
        threading.Thread(target=_yaz, args=(istemci, satir), daemon=True).start()
    except Exception:  # noqa: BLE001
        pass


def son_olcumler(gun=14, limit=20000):
    """Ekran için son ölçümler (yeni üstte). Tablo yoksa []."""
    try:
        from datetime import datetime, timedelta, timezone
        from shared.auth import _get_supabase
        bas = (datetime.now(timezone.utc) - timedelta(days=gun)).isoformat()
        out, adim = [], 1000
        for i in range(0, limit, adim):
            r = (_get_supabase().table(TABLO).select("zaman,modul,sayfa,ms,hata").gte("zaman", bas)
                 .order("zaman", desc=True).range(i, i + adim - 1).execute().data or [])
            out += r
            if len(r) < adim:
                break
        return out
    except Exception:  # noqa: BLE001
        return []


def raporlar(limit=200):
    """bt_rapor kayıtları (yeni üstte). Tablo yoksa []."""
    try:
        from shared.auth import _get_supabase
        return (_get_supabase().table("bt_rapor").select("*").order("zaman", desc=True)
                .limit(limit).execute().data or [])
    except Exception:  # noqa: BLE001
        return []
