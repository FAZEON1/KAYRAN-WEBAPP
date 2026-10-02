# -*- coding: utf-8 -*-
"""Stok toplamları — TEK TANIM (Ekim 2026).

  toplam_stok  = bizim satılabilir depolar (Merkez + Happy Life) = urunler.bizim_stok
  kanal_stok   = kanallardaki (Vatan, İtopya…) mal — satılmış, bilgi amaçlı
  zincir_stok  = toplam_stok + kanal_stok — YALNIZ sipariş/kapsama hesabı
                 (kanalların son kullanıcıya satış hızına bölünür)

Kanal kuralı: her kanalın SON rapor tarihi esas alınır; o raporda olmayan
ürün o kanalda 0'dır. Yükleyiciler dosyada olmayan ürüne 0 satırı yazmaz;
"ürünün en son görüldüğü satır" kuralı satılıp biten malı eski haftanın
adediyle saymaya devam ediyordu (liste 625 / pano 614).
"""


def _tarih(r):
    return str(r.get("yukleme_tarihi") or "")[:10]


def kanal_son_tarihleri(rows):
    """{firma: 'YYYY-MM-DD'} — verilen satırlardaki en yeni rapor tarihi."""
    son = {}
    for r in rows or []:
        f, t = r.get("firma"), _tarih(r)
        if f and t and t > son.get(f, ""):
            son[f] = t
    return son


def kanal_stoklari(rows, son_tarih=None):
    """{firma: {sku: stok}} — yalnız her kanalın son raporundaki satırlar.

    son_tarih verilmezse satırların kendisinden çıkarılır; bu yalnız TÜM
    firma_stok tablosu okunduğunda doğrudur. Tek ürünün satırlarıyla
    çalışırken (stok kartı) kanalların genel son tarihi verilmelidir."""
    son = son_tarih if son_tarih is not None else kanal_son_tarihleri(rows)
    out = {}
    for r in rows or []:
        f = r.get("firma")
        if not f or _tarih(r) != son.get(f):
            continue
        sku = r.get("sku")
        out.setdefault(f, {})
        out[f][sku] = out[f].get(sku, 0) + (r.get("stok_miktari") or 0)
    return out


def stok_ozeti(bizim_stok, firma_stoklari):
    """firma_stoklari: {firma: adet} → üç tanım tek yerde."""
    bizim = bizim_stok or 0
    kanal = sum((v or 0) for v in (firma_stoklari or {}).values())
    return {"toplam_stok": bizim, "kanal_stok": kanal, "zincir_stok": bizim + kanal}
