# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Stok yaşı › Bizim stok › Tüm ürünler — SALT OKUR LİSTE MASASI (Ekim 2026,
ortak masa: shared/masa.py).

Eski "Tüm ürünler" tablosu (shared.tablo, sy_urunler) ortak masada: kategori seçimi, "90 günden yaşlı" ve
"Giriş kaydı yok" anahtarları, arama, sıralama. Satıra tıklayınca yan panelde yaş grupları ve elde kalan
partiler (eskiden tablonun altında açılan parti tablosu). İşlem yok (salt okunur).
Satırlar ve rakamlar stok_yasi.urun_satirlari'ndan (FIFO, değer = adet × paçal — satis.get_pacal_map);
Excel'e aktarma sayfadaki "Excel: tümü" düğmesinde (Ürünler ve Partiler sayfaları).

Yaş grubu özeti (sy_toplam_grup → grup ürünleri) ve müşteri tabloları eskisi gibi kaldı: grup tıklaması
alt listeyi ve gruba özel Excel'i besliyor; bu, masanın satır görünümüne birebir oturmuyor.

Geri almak için: kayranpm/stok_yasi_ekran.py → STOK_YASI_MASASI_YENI = False.
"""
from shared.tasarim import tr_sayi

from . import stok_yasi as Y
from .masa_ortak import usd

PANEL_PARTI = 25          # panelde gösterilen en çok parti (tamamı Excel'de)
_YASLI = ("91–180 gün", "180+ gün")


def _gun(v):
    return "—" if v is None else tr_sayi(v, 0)


def _tarih(s):
    s = str(s or "")[:10]
    return f"{s[8:10]}.{s[5:7]}.{s[:4]}" if len(s) == 10 and s[4] == "-" else s


def masa_verisi(bizim, pacal, bugun):
    """bizim: stok_yasi.hesapla()['bizim']; pacal: {sku anahtarı: $}."""
    rows = Y.urun_satirlari(bizim, pacal)
    satirlar = []
    for r in rows:
        oz, kal, _u = bizim[r["_id"]]
        yasli = sum(r.get(g, 0) for g in _YASLI)
        detay = [[g, f"{tr_sayi(r.get(g, 0))} adet"] for g, _a, _b in Y.GRUPLAR if r.get(g, 0)]
        if r.get(Y.KAYITSIZ):
            detay.append([Y.KAYITSIZ, f"{tr_sayi(r[Y.KAYITSIZ])} adet"])
        detay.append(["En eski parti", f"{_gun(r['En eski (gün)'])} gün"])
        detay.append(["Toplam değer", usd(r["Toplam değer ($)"])])
        partiler = list(reversed(kal or []))
        for p in partiler[:PANEL_PARTI]:
            g = Y._gun(p.get("tarih"), bugun)
            detay.append([f"{_tarih(p.get('tarih'))} · {p.get('belge') or '—'}",
                          f"{tr_sayi(p.get('kalan'))} adet · {_gun(g)} gün · {Y.TUR_AD.get(p.get('tur'), '')}".rstrip(" ·")])
        if not partiler:
            notu = "Elde kalan stoğu karşılayan giriş kaydı yok."
        elif len(partiler) > PANEL_PARTI:
            notu = f"İlk {PANEL_PARTI} parti gösterildi ({len(partiler)} parti); tamamı 'Excel: tümü' dosyasının Partiler sayfasında."
        else:
            notu = f"Elde kalan {len(partiler)} parti (en yeni üstte) · yaş depoya girişten, FIFO."
        satirlar.append({
            "id": r["_id"], "sku": r["SKU"], "ad": r["Ürün"] or r["SKU"], "alt": r["SKU"] if r["Ürün"] else "",
            "kat": r["Kategori"] or "",
            "stok_m": tr_sayi(r["Toplam stok"]), "stok_m__s": r["Toplam stok"],
            "ort_m": f"{_gun(r['Ort. yaş (gün)'])} gün", "ort_m__s": r["Ort. yaş (gün)"],
            "eski_m": f"{_gun(r['En eski (gün)'])} gün", "eski_m__s": r["En eski (gün)"],
            "yasli_m": tr_sayi(yasli) if yasli else "", "yasli_m__s": yasli, "yasli": yasli,
            "kayitsiz_m": tr_sayi(r[Y.KAYITSIZ]) if r.get(Y.KAYITSIZ) else "", "kayitsiz_m__s": r.get(Y.KAYITSIZ, 0),
            "kayitsiz": r.get(Y.KAYITSIZ, 0),
            "deger_m": usd(r["Toplam değer ($)"]), "deger_m__s": r["Toplam değer ($)"],
            "_baslik": r["SKU"], "_alt": r["Ürün"],
            "_buyuk": f"{tr_sayi(r['Toplam stok'])} adet", "_buyuk_alt": f"ort. {_gun(r['Ort. yaş (gün)'])} gün",
            "_detay": detay, "_not": notu,
        })
    katlar = sorted({s["kat"] for s in satirlar if s["kat"]}, key=str.lower)
    return {
        "secimler": [{"alan": "kat", "ad": "Tüm kategoriler", "secenekler": [{"k": k, "ad": k} for k in katlar]}],
        "anahtarlar": [{"k": "yasli", "ad": "90 günden yaşlı", "f": [["yasli", "gt", 0]]},
                       {"k": "kayitsiz", "ad": Y.KAYITSIZ, "f": [["kayitsiz", "gt", 0]]}],
        "ara": {"alanlar": ["sku", "ad", "kat"], "ipucu": "SKU, ürün ya da kategori"},
        "sutunlar": [
            {"alan": "ad", "ad": "Ürün", "tip": "ana", "alt": "alt"},
            {"alan": "kat", "ad": "Kategori", "tip": "etiket", "gen": "130px", "genis": True},
            {"alan": "stok_m", "ad": "Stok", "sag": True, "gen": "84px", "dar": "sag"},
            {"alan": "ort_m", "ad": "Ort. yaş", "sag": True, "gen": "92px", "dar": "alt"},
            {"alan": "eski_m", "ad": "En eski", "sag": True, "gen": "92px", "genis": True},
            {"alan": "yasli_m", "ad": "90+ gün", "sag": True, "gen": "84px"},
            {"alan": "kayitsiz_m", "ad": "Kaydı yok", "sag": True, "gen": "88px", "genis": True},
            {"alan": "deger_m", "ad": "Değer", "sag": True, "gen": "120px", "genis": True},
        ],
        "satirlar": satirlar,
        "islemler": [],
        "bos": {"liste": "Satılabilir depolarda stok yok.", "suzgec": "Bu süzgece uyan ürün yok."},
        "baslik_ipucu": "Stok yaşı · ürünler",
    }


def yurutucu():
    """Salt okunur masa: işlem yok (bileşen istek göndermez; gelirse reddedilir)."""
    def yurut(temiz):
        return {"ok": False, "mesaj": "Bu listede işlem yapılmaz."}
    return yurut
