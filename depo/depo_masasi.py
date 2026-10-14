# -*- coding: utf-8 -*-
"""Depo › Depo stok ve Bekleyen sevk takibi — ORTAK LİSTE MASASI (Ekim 2026).

Liste, süzgeç, yan detay paneli ve işlemler ortak masada (shared/masa.py); bu modül masanın tanımını
(stok_masa_verisi, bekleyen_masa_verisi) ve bekleyen sevk işlemlerinin yürütülmesini (bekleyen_uygula)
verir. Yazma bugünkü kodla: düşüm depo.bekleyen_ekran.sevk_dus_kaydet (eski "Düşümü kaydet" düğmesinin
kodu, yük birebir aynı), silme depo.bekleyen_ekran.takip_sil.

Depo stok: liste depo/yazdir.liste_hazirla çıktısıdır (ekran = kâğıt); depo seçimi, barkodlu arama,
sıralama ve Yazdır bugünkü Streamlit kutularında kalır.

Geri almak için: depo/main.py → DEPO_STOK_MASASI_YENI ve depo/bekleyen_ekran.py → BEKLEYEN_MASASI_YENI
= False (eski ekranlar aynen duruyor).
"""
from datetime import date

from .depo_hesap import bekleyen_ozet

ON_EK = "dpo_mt"


def _tr(v, ondalik=0):
    from shared.tasarim import tr_sayi
    return tr_sayi(v, ondalik)


# ── Depo stok (salt-okur) ───────────────────────────────────────────
def stok_masa_verisi(depo, liste, ham_sayisi=None, ara=""):
    """liste: liste_hazirla çıktısı [{sku, urun_adi, adet}] — sırası korunur (ekrandaki = kâğıttaki)."""
    satirlar = []
    for n, u in enumerate(liste or []):
        adet = int(u.get("adet") or 0)
        satirlar.append({
            "id": n + 1, "sku": str(u.get("sku") or ""), "urun": str(u.get("urun_adi") or ""),
            "adet": adet, "adet_m": _tr(adet), "adet_m__s": adet,
            "_baslik": str(u.get("sku") or ""), "_alt": str(u.get("urun_adi") or ""),
            "_buyuk": f"{_tr(adet)} adet", "_buyuk_alt": str(depo or ""),
        })
    toplam = sum(s["adet"] for s in satirlar)
    al = f"{ham_sayisi} çeşitten aramaya uyanlar" if str(ara or "").strip() and ham_sayisi is not None else ""
    return {
        "ozet": [
            {"k": "cesit", "et": "Çeşit", "dg": _tr(len(satirlar)), "renk": "mor", "al": al or str(depo or "")},
            {"k": "adet", "et": "Toplam adet", "dg": _tr(toplam), "renk": "yesil", "al": "stoklu ürünler"},
        ],
        "gorunumler": [{"k": "tum", "ad": "Tümü", "f": []}],
        "sutunlar": [
            {"alan": "sku", "ad": "SKU", "tip": "metin", "gen": "170px", "dar": "alt"},
            {"alan": "urun", "ad": "Ürün", "tip": "ana"},
            {"alan": "adet_m", "ad": "Adet", "sag": True, "gen": "100px", "dar": "sag"},
        ],
        "satirlar": satirlar,
        "islemler": [],
        "bos": {"liste": "Bu depoda stoklu ürün yok.", "suzgec": "Aramaya uyan ürün yok."},
        "baslik_ipucu": f"{depo or ''} stok",
    }


# ── Bekleyen sevk takibi ────────────────────────────────────────────
def bekleyen_masa_verisi(mt, fis_oneri="", bugun=None, salt=False):
    """mt: depo_manuel_takip satırları (id azalan). Sıra eski ekranla aynı: önce sevk bekleyenler
    (bekleyen çoktan aza), sonra tamamı sevk edilenler (kayıt sırasıyla)."""
    bugun = bugun or date.today()
    acik = sorted([r for r in mt or [] if bekleyen_ozet(r)[2] > 0], key=lambda r: -bekleyen_ozet(r)[2])
    biten = [r for r in mt or [] if bekleyen_ozet(r)[2] <= 0]
    satirlar = []
    for grup, liste in (("Sevk bekleyenler", acik), ("Tamamı sevk edilenler", biten)):
        for r in liste:
            fa, se, bek, oran = bekleyen_ozet(r)
            sku = str(r.get("sku") or "").strip()
            urun = str(r.get("urun_adi") or "").strip()
            notlar = str(r.get("notlar") or "").strip()
            n_sevk = len(r.get("hareketler") or [])
            satirlar.append({
                "id": r.get("id"), "firma": str(r.get("firma") or "").strip() or "—", "sku": sku, "urun": urun,
                "notlar": notlar, "fa": fa, "se": se, "bek": bek, "sevk_sayisi": n_sevk, "grup": grup,
                "alt": " · ".join(x for x in (sku, urun[:40], f"{n_sevk} sevk", notlar[:30]) if x),
                "bek_m": f"{_tr(bek)} bekliyor" if bek else "tamamlandı", "bek_m__s": bek,
                "bek_alt": f"{_tr(se)} / {_tr(fa)} sevk edildi", "bek_renk": "amber" if bek else "yesil",
                "fa_m": _tr(fa), "fa_m__s": fa, "se_m": _tr(se), "se_m__s": se,
                "durum": "Bekliyor" if bek else "Tamamlandı",
                "_durum": {"ad": "Bekliyor" if bek else "Tamamlandı", "renk": "amber" if bek else "yesil"},
                "_baslik": str(r.get("firma") or "").strip() or "—",
                "_alt": " · ".join(x for x in (sku, urun) if x),
                "_buyuk": f"{_tr(bek)} adet bekliyor" if bek else "Tamamı sevk edildi",
                "_buyuk_alt": f"{_tr(se)} / {_tr(fa)} sevk edildi",
                "_detay": [["Faturalanan", _tr(fa)], ["Sevk edilen", f"{_tr(se)} (%{_tr(oran * 100)})"],
                           ["Bekleyen", _tr(bek)], ["Sevk sayısı", f"{n_sevk} sevk"]]
                          + ([["Not", notlar]] if notlar else []),
                "_not": "" if bek else "Bu kaydın tamamı sevk edildi.",
            })
    ozt = [bekleyen_ozet(r) for r in mt or []]
    firmalar = sorted({s["firma"] for s in satirlar if s["firma"] != "—"})
    return {
        "ozet": [
            {"k": "kayit", "et": "Kayıt", "dg": _tr(len(satirlar)), "renk": "mor", "suz": "tum",
             "al": f"{len(acik)} kayıtta sevk bekliyor"},
            {"k": "fa", "et": "Faturalanan", "dg": _tr(sum(o[0] for o in ozt)), "renk": "", "al": "adet"},
            {"k": "se", "et": "Sevk edilen", "dg": _tr(sum(o[1] for o in ozt)), "renk": "yesil", "al": "adet"},
            {"k": "bek", "et": "Bekleyen", "dg": _tr(sum(o[2] for o in ozt)), "renk": "amber", "suz": "bekleyen",
             "al": "adet depoda bekliyor"},
        ],
        "gorunumler": [{"k": "tum", "ad": "Tümü", "f": []},
                       {"k": "bekleyen", "ad": "Sevk bekleyen", "f": [["bek", "gt", 0]]},
                       {"k": "biten", "ad": "Tamamı sevk edilen", "f": [["bek", "lt", 1]]}],
        "secimler": [{"alan": "firma", "ad": "Tüm firmalar", "secenekler": [{"k": f, "ad": f} for f in firmalar]}],
        "ara": {"alanlar": ["firma", "sku", "urun", "notlar"], "ipucu": "Firma, SKU, ürün ya da not"},
        "sutunlar": [
            {"alan": "firma", "ad": "Firma", "tip": "ana", "alt": "alt"},
            {"alan": "fa_m", "ad": "Faturalanan", "sag": True, "gen": "104px", "genis": True},
            {"alan": "se_m", "ad": "Sevk edilen", "sag": True, "gen": "104px", "genis": True},
            {"alan": "bek_m", "ad": "Bekleyen", "sag": True, "alt": "bek_alt", "gen": "150px", "dar": "sag"},
            {"alan": "durum", "ad": "Durum", "tip": "durum", "gen": "116px"},
        ],
        "grup": {"alan": "grup", "birim": "kayıt", "toplamlar": [{"alan": "bek", "son": " bekliyor", "ondalik": 0}]},
        "satirlar": satirlar,
        "islemler": [
            {"k": "dus", "ad": "Sevk düş", "dugme": "Düşümü kaydet", "f": [["bek", "gt", 0]], "birincil": True,
             "ipucu": "Kaydedince sevk fişi listenin üstünde indirilir.",
             "alanlar": [
                 {"ad": "adet", "et": "Sevk adedi", "tip": "sayi", "zorunlu": True, "en_az": 1, "en_cok_alan": "bek",
                  "varsayilan": 1, "ondalik": 0},
                 {"ad": "tarih", "et": "Sevk tarihi", "tip": "tarih", "zorunlu": True, "varsayilan": bugun.isoformat()},
                 {"ad": "fis", "et": f"Fiş no (boşsa sıradaki: {fis_oneri})" if fis_oneri else "Fiş no",
                  "tip": "metin", "tam": True, "en_uzun": 60},
                 {"ad": "belge", "et": "Fatura / belge no (ops.)", "tip": "metin", "tam": False, "en_uzun": 80},
                 {"ad": "eirs", "et": "e-İrsaliye no (ops.)", "tip": "metin", "tam": False, "en_uzun": 80},
                 {"ad": "acik", "et": "Açıklama (ops.)", "tip": "metin", "en_uzun": 300},
             ]},
            {"k": "ac", "ad": "Ayrıntı", "dugme": "Hareketler ve fişler", "okuma": True},
            {"k": "sil", "ad": "Sil", "dugme": "Kaydı sil", "tehlike": True,
             "ipucu": "Yanlış açılmış kayıtlar için. Kayıt bütün sevk hareketleriyle birlikte silinir; geri alınamaz.",
             "alanlar": [{"ad": "onay", "et": "Evet, {baslik} takip kaydını sevk hareketleriyle birlikte kalıcı olarak sil",
                          "tip": "onay", "zorunlu": True}]},
        ],
        "bos": {"liste": "Henüz takip kaydı yok.", "suzgec": "Bu süzgece uyan kayıt yok."},
        "baslik_ipucu": "Bekleyen sevk kayıtları",
        "salt": bool(salt),
    }


def bekleyen_uygula(temiz, mt, kullanici=""):
    """istek_al'dan geçmiş isteği bugünkü kodla yürütür. Döner: masa sonucu; düşümde "son_fis":
    {"kayit", "hareket"} (sayfa bunu fiş indirme kutusu için oturuma yazar)."""
    from shared import bilesen as B
    from depo.belge import fis_no_uret
    from . import bekleyen_ekran as E
    islem, ids, d = temiz["islem"], temiz["ids"], temiz["degerler"]
    r = next((x for x in mt or [] if x.get("id") == ids[0]), None)
    if r is None:
        return {"ok": False, "mesaj": "Kayıt bulunamadı; sayfayı yenileyip tekrar deneyin."}
    if islem == "ac":
        B.sec(ON_EK, r.get("id"))
        return {"ok": True, "mesaj": "", "sessiz": True, "onbellek": False}
    if islem == "dus":
        bek = bekleyen_ozet(r)[2]
        adet = d.get("adet")
        if adet is None or adet != int(adet) or not 1 <= int(adet) <= bek:
            return {"ok": False, "mesaj": f"Sevk adedi 1 ile {bek} arasında tam sayı olmalı."}
        tum_hrk = [h for x in mt or [] for h in (x.get("hareketler") or [])]
        fis = str(d.get("fis") or "").strip() or fis_no_uret(tum_hrk)
        snap, yeni_h = E.sevk_dus_kaydet(r, int(adet), d.get("tarih") or date.today(), str(d.get("belge") or ""),
                                         fis, str(d.get("eirs") or ""), str(d.get("acik") or ""), kullanici)
        return {"ok": True, "mesaj": f"{_tr(int(adet))} adet sevk kaydedildi · fiş no {yeni_h.get('fis_no')}",
                "son_fis": {"kayit": snap, "hareket": yeni_h}}
    if islem == "sil":
        E.takip_sil(r.get("id"))
        return {"ok": True, "mesaj": f"{r.get('firma', '')} · {r.get('sku', '')} takip kaydı silindi"}
    return {"ok": False, "mesaj": "Bilinmeyen işlem."}
