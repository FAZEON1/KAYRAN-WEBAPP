# -*- coding: utf-8 -*-
"""Ana sayfa "Kısayollarım" (Ekim 2026) — kullanıcının son 30 günde en çok açtığı sayfalar.

Kaynak: bt_olcum (her sayfa açılışı; Serkan'ın ölçümü, kullanıcı adıyla). Yetkisi olmayan modül ve ana
sayfanın kendisi listeye girmez. Saf kısım `sec` (test edilir); `oku` veritabanından getirir.
"""
EN_FAZLA = 6
GUN = 30
_HARIC = {"anasayfa", "arama", ""}


def _etiket(modul, sayfa):
    """(etiket, ikon, sayfa_kodu) ya da None (tanınmayan sayfa)."""
    from shared.gezinme import MODULLER, SISTEM
    m = next((x for x in MODULLER if x.get("kod") == modul), None)
    if m:
        for _sec, kod, ad, _k in m.get("sayfalar") or []:
            if kod == sayfa:
                return f'{m["ad"]} · {ad}', m.get("ikon") or "apps", kod
        return m["ad"], m.get("ikon") or "apps", None
    s = next((x for x in SISTEM if x[0] == modul), None)
    return (s[1], s[2], None) if s else None


def sec(olcumler, izinli, n=EN_FAZLA):
    """olcumler: [{modul, sayfa}] · izinli(modul) → bool.
    Döner: [{modul, sayfa, etiket, ikon, adet}] en çok açılan önce (eşitse son açılan önce)."""
    sayac, son = {}, {}
    for i, o in enumerate(olcumler or []):
        k = (str(o.get("modul") or ""), str(o.get("sayfa") or ""))
        if k[0] in _HARIC:
            continue
        sayac[k] = sayac.get(k, 0) + 1
        son.setdefault(k, i)                         # olcumler yeni → eski sıralı gelir
    out = []
    for (modul, sayfa), adet in sorted(sayac.items(), key=lambda kv: (-kv[1], son[kv[0]])):
        if not izinli(modul):
            continue
        e = _etiket(modul, sayfa)
        if not e:
            continue
        etiket, ikon, kod = e
        if any(x["etiket"] == etiket for x in out):
            continue
        out.append({"modul": modul, "sayfa": kod, "etiket": etiket, "ikon": ikon, "adet": adet})
        if len(out) >= n:
            break
    return out


def oku(kullanici):
    """Kullanıcının son 30 gündeki sayfa açılışları (yeni → eski); okunamazsa []."""
    import streamlit as st

    @st.cache_data(ttl=600, show_spinner=False)
    def _o(k):
        from datetime import datetime, timedelta, timezone
        from shared.auth import _get_supabase
        bas = (datetime.now(timezone.utc) - timedelta(days=GUN)).isoformat()
        return (_get_supabase().table("bt_olcum").select("modul,sayfa").eq("kullanici", k).gte("zaman", bas)
                .order("zaman", desc=True).range(0, 1999).execute().data or [])
    try:
        return _o(str(kullanici or "").strip().lower())
    except Exception:  # noqa: BLE001
        return []
