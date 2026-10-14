# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Yurt içi alış › Kayıtlı alımlar — LİSTE MASASI (Ekim 2026, ortak masa: shared/masa.py).

Eski tablo (shared.tablo, yi_liste) ortak masada: firma / tür seçimi, arama, sıralama; satıra tıklayınca yan
panel. Panelde:
  Düzenle : bugünkü düzenleme formu (kalemler data_editor, masraflar, kur) sayfada, masanın altında açılır —
            form karmaşık olduğu için panele taşınmadı; kayıt ithalat.database.guncelle_dosya ile (DEĞİŞMEDİ).
  Sil     : onaylı → ithalat.database.yurtici_sil(id) (eski düğmeyle aynı; stoğa eklenmişse geri çeker).
Rakamlar eski tablonun satırıyla aynı (mal bedeli = Σ adet × birim_fob, + masraflar; yurtici_hesap._f).

Geri almak için: kayranpm/yurtici_ekran.py → YURTICI_MASASI_YENI = False.
"""
from shared.tasarim import tr_sayi

from . import yurtici_hesap as H
from .masa_ortak import usd

SECIM_KEY = "yi_masa_sec"


def tablo_satirlari(dos, kal, masraf_dict, gun_ay_yil):
    """Eski tablonun satırları (CSV indirmesi de bunlarla) — sıra: depoya giriş, yeni üstte."""
    dos = sorted(dos or [], key=lambda d: str(d.get("teslim_tarihi") or d.get("tarih") or ""), reverse=True)
    out = []
    for d in dos:
        ks = kal.get(d.get("id"), [])
        mal = sum(H._f(k.get("adet")) * H._f(k.get("birim_fob")) for k in ks)
        masraf = sum(H._f(v) for v in masraf_dict(d).values())
        out.append({"_id": d.get("id"), "_giris_ham": str(d.get("teslim_tarihi") or "")[:10],
                    "_alis_ham": str(d.get("tarih") or "")[:10], "_tur_k": d.get("alim_turu"),
                    "_stok": d.get("stok_islendi") is True,
                    "Depoya giriş": gun_ay_yil(d.get("teslim_tarihi")), "Alış": gun_ay_yil(d.get("tarih")),
                    "Tür": H.TURLER.get(d.get("alim_turu"), ""), "Belge": d.get("dosya_no") or "",
                    "Firma": d.get("tedarikci") or "", "Kalem": len(ks),
                    "Adet": sum(H._f(k.get("adet")) for k in ks), "Tutar ($)": round(mal + masraf, 2),
                    "Stok": "eklendi" if d.get("stok_islendi") is True else "zaten depodaydı"})
    return out


def masa_verisi(tablo):
    """tablo: tablo_satirlari çıktısı."""
    satirlar = []
    for r in tablo:
        adet = r["Adet"]
        satirlar.append({
            "id": r["_id"], "belge": r["Belge"] or "—", "firma": r["Firma"], "tur": r["Tür"],
            "giris": r["Depoya giriş"] or "—", "giris__s": r["_giris_ham"], "alis": f"alış {r['Alış']}" if r["Alış"] else "",
            "kalem_m": f"{r['Kalem']} kalem", "kalem_m__s": r["Kalem"],
            "adet_m": tr_sayi(adet, 0 if float(adet).is_integer() else 2), "adet_m__s": adet,
            "tutar_m": usd(r["Tutar ($)"]), "tutar_m__s": r["Tutar ($)"],
            "stok": "eklendi" if r["_stok"] else "depoda",
            "_durum": {"ad": "Stoğa eklendi" if r["_stok"] else "Zaten depodaydı", "renk": "yesil" if r["_stok"] else "soluk"},
            "_baslik": r["Belge"] or "—", "_alt": r["Firma"],
            "_buyuk": usd(r["Tutar ($)"]), "_buyuk_alt": "mal + masraf",
            "_detay": [x for x in (["Tür", r["Tür"]], ["Depoya giriş", r["Depoya giriş"]], ["Alış", r["Alış"]],
                                   ["Kalem", str(r["Kalem"])], ["Adet", tr_sayi(adet, 0 if float(adet).is_integer() else 2)],
                                   ["Stok", r["Stok"]]) if x[1]],
            "_not": ("Stoğa eklenmiş alımda adet değişikliği stoğa da yansır; silinirse stoktan geri çekilir."
                     if r["_stok"] else "'Zaten depodaydı' kaydında stoğa dokunulmaz."),
        })
    firmalar = sorted({s["firma"] for s in satirlar if s["firma"]}, key=str.lower)
    turler = sorted({s["tur"] for s in satirlar if s["tur"]})
    return {
        "secimler": [{"alan": "firma", "ad": "Tüm firmalar", "secenekler": [{"k": f, "ad": f} for f in firmalar]},
                     {"alan": "tur", "ad": "Tüm türler", "secenekler": [{"k": t, "ad": t} for t in turler]}],
        "anahtarlar": [{"k": "stok", "ad": "Yalnız stoğa eklenenler", "f": [["stok", "eq", "eklendi"]]}],
        "ara": {"alanlar": ["belge", "firma"], "ipucu": "Belge no ya da firma"},
        "sutunlar": [
            {"alan": "giris", "ad": "Depoya giriş", "alt": "alis", "gen": "120px", "dar": "alt"},
            {"alan": "belge", "ad": "Belge", "tip": "ana", "alt": "firma"},
            {"alan": "tur", "ad": "Tür", "tip": "etiket", "gen": "130px", "genis": True},
            {"alan": "kalem_m", "ad": "Kalem", "sag": True, "gen": "84px", "genis": True},
            {"alan": "adet_m", "ad": "Adet", "sag": True, "gen": "90px"},
            {"alan": "tutar_m", "ad": "Tutar ($)", "sag": True, "gen": "130px", "dar": "sag"},
            {"alan": "stok", "ad": "Stok", "tip": "durum", "gen": "140px"},
        ],
        "satirlar": satirlar,
        "islemler": [
            {"k": "duzenle", "ad": "Düzenle", "dugme": "Düzenleme formunu aç", "birincil": True},
            {"k": "sil", "ad": "Sil", "dugme": "Alımı sil", "tehlike": True,
             "ipucu": "Stoğa eklenmiş alım silinirse adetler stoktan geri çekilir.",
             "alanlar": [{"ad": "onay", "et": "Silmeyi onaylıyorum", "tip": "onay", "zorunlu": True}]},
        ],
        "bos": {"liste": "Henüz yurt içi alış kaydı yok.", "suzgec": "Bu süzgece uyan alım yok."},
        "baslik_ipucu": "Kayıtlı alımlar",
    }


def yurutucu(state=None):
    """duzenle → seçili alım oturuma yazılır, sayfa yeniden çalışır ve bugünkü formu masanın altında açar.
    sil → ithalat.database.yurtici_sil(id)."""
    def yurut(temiz):
        i = temiz["ids"][0]
        if temiz["islem"] == "duzenle":
            ss = state
            if ss is None:
                import streamlit as st
                ss = st.session_state
            ss[SECIM_KEY] = i
            return {"ok": True, "sessiz": True, "onbellek": False}
        if temiz["islem"] == "sil":
            from ithalat.database import yurtici_sil
            ok, msg = yurtici_sil(i)
            return {"ok": bool(ok), "mesaj": msg}
        return {"ok": False, "mesaj": "Bilinmeyen işlem."}
    return yurut
