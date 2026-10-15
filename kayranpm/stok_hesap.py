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


def _firma(r):
    """Firma kanonik (shared.utils.firma_kanonik): eski 'KANAL' kayıtları DİĞER'e katılır."""
    from shared.utils import firma_kanonik
    return firma_kanonik(r.get("firma"))


def _tarih(r):
    return str(r.get("yukleme_tarihi") or "")[:10]


def kanal_son_tarihleri(rows):
    """{firma: 'YYYY-MM-DD'} — verilen satırlardaki en yeni rapor tarihi."""
    son = {}
    for r in rows or []:
        f, t = _firma(r), _tarih(r)
        if f and t and t > son.get(f, ""):
            son[f] = t
    return son


def kanal_stoklari(rows, son_tarih=None, harita=None):
    """{firma: {sku: stok}} — yalnız her kanalın son raporundaki satırlar.

    son_tarih verilmezse satırların kendisinden çıkarılır; bu yalnız TÜM
    firma_stok tablosu okunduğunda doğrudur. Tek ürünün satırlarıyla
    çalışırken (stok kartı) kanalların genel son tarihi verilmelidir.
    SKU anahtarı shared.utils.sku_anahtar: rapor 'MIO MIVUE J30' yazar, kart 'Mio MiVue J30';
    arayan da sku_anahtar(kart_sku) ile bakmalı (Ekim 2026).
    harita: {sku_anahtar(rapor kodu): kart SKU'su} (kod_haritasi) — pazaryeri kodu gelen raporlar
    (D-market 'HBCV…', Avasya 'MON24FAZ…') kartın anahtarına yazılır; haritada olmayan kod aynen kalır."""
    from shared.utils import sku_anahtar
    son = son_tarih if son_tarih is not None else kanal_son_tarihleri(rows)
    harita = harita or {}
    out = {}
    for r in rows or []:
        f = _firma(r)
        if not f or _tarih(r) != son.get(f):
            continue
        sku = sku_anahtar(r.get("sku"))
        sku = sku_anahtar(harita.get(sku, sku))
        out.setdefault(f, {})
        out[f][sku] = out[f].get(sku, 0) + (r.get("stok_miktari") or 0)
    return out


def kod_haritasi(rows, kartlar, eslesme=None):
    """{sku_anahtar(rapor kodu): kart SKU'su} — kartın kendi kodu olmayan rapor kodları için
    (Ekim 2026). Kural Müşteri Satışları'nınki (musteri_hesap.meta_hazirla): onaylı eşleme
    tablosu, sonra addaki model kodu; birden çok aday varsa bağlamaz. rows: firma_stok satırları
    (sku, urun_adi); kartlar: {kart_sku: {urun_adi, ...}}; eslesme: {dış kod: kart SKU'su}."""
    from shared.utils import sku_anahtar
    meta = _kod_meta(rows, kartlar, eslesme)
    return {sku_anahtar(ham): m["kart_sku"] for ham, m in meta.items()
            if m.get("kart_sku") and m.get("kart_kaynak") in ("tablo", "kural")}


def _kod_meta(rows, kartlar, eslesme=None):
    """{ham rapor kodu: meta_hazirla sonucu} — kartın kendi kodu olmayan kodlar. Her kod BÜTÜN raporlardan
    EN UZUN adıyla aranır: D-market son raporda adı kısaltıyor ('…Argb 3X120MM'), eski raporda tam yazıyor
    ('…Fanlı Atx Beyaz Gamıng Kasa' = kart adı). Sıra rapor sırasına bağlı değil."""
    from shared.utils import sku_anahtar
    from .musteri_hesap import meta_hazirla
    kartlar = kartlar or {}
    kart_anahtar = {sku_anahtar(k) for k in kartlar}
    tekil = {}
    for r in rows or []:
        ham = str(r.get("sku") or "").strip()
        if not ham or sku_anahtar(ham) in kart_anahtar:
            continue
        ad = str(r.get("urun_adi") or "").strip()
        if ham not in tekil or (len(ad), ad) > (len(tekil[ham]["urun_adi"]), tekil[ham]["urun_adi"]):
            tekil[ham] = {"sku": ham, "urun_adi": ad}
    return meta_hazirla(list(tekil.values()), kartlar, sku_fn=sku_anahtar, eslesme=eslesme)


_DURUM_SIRA = {"yeni": 0, "belirsiz": 1, "yok": 2, "bagli": 3}


def kanal_kod_karsilastir(rows, kartlar, eslesme=None):
    """SALT OKUNUR karşılaştırma (Ekim 2026): kanal stoğu bugün rapor SKU'sunu karta birebir
    (sku_anahtar) bağlar; pazaryeri kodu gelen raporlar (HB 'HBCV…', AVASYA 'MON24FAZ…') hiçbir
    ürüne düşmez. Önerilen kural Müşteri Satışları'nınki: musteri_hesap.meta_hazirla (onaylı
    eşleme tablosu + addaki model kodu; birden çok aday varsa bağlamaz).

    rows: firma_stok satırları (firma, sku, urun_adi, stok_miktari, yukleme_tarihi) — TÜM tablo;
    her kanalın son raporu kullanılır (kanal_stoklari ile aynı kural).
    kartlar: {kart_sku: {urun_adi, ...}}; eslesme: {dış kod: kart SKU'su}.
    Döner: {"kodlar": [...], "musteriler": [...], "urunler": [...], "toplam": {...}} — hiçbir şey yazmaz."""
    from shared.utils import sku_anahtar
    son = kanal_son_tarihleri(rows)
    son_rows = [r for r in rows or [] if _firma(r) and _tarih(r) == son.get(_firma(r))]
    kartlar = kartlar or {}
    norm = {}
    for ks in kartlar:
        norm.setdefault(sku_anahtar(ks), ks)
    meta = _kod_meta(rows, kartlar, eslesme)       # kanal_stoklari'nın haritasıyla aynı (kod_haritasi)

    kod = {}
    for r in son_rows:
        ham = str(r.get("sku") or "").strip()
        k = kod.setdefault((_firma(r), ham), {"firma": _firma(r), "kod": ham, "ad": str(r.get("urun_adi") or "").strip(),
                                              "adet": 0})
        k["adet"] += r.get("stok_miktari") or 0
    kodlar = []
    for (f, ham), k in kod.items():
        m = meta.get(ham) or {}
        eski = norm.get(sku_anahtar(ham), "")
        yeni = eski or (m.get("kart_sku") if m.get("kart_kaynak") in ("tablo", "kural") else "") or ""
        durum = ("bagli" if eski else "yeni" if yeni else
                 "belirsiz" if m.get("kart_kaynak") == "belirsiz" else "yok")
        kodlar.append(dict(k, eski_kart=eski, yeni_kart=yeni, durum=durum,
                           kaynak="" if eski else {"tablo": "onaylı eşleme", "kural": "ürün adı / model kodu"}.get(
                               m.get("kart_kaynak"), ""),
                           adaylar=list(m.get("adaylar") or [])))
    kodlar.sort(key=lambda k: (_DURUM_SIRA[k["durum"]], k["firma"], -k["adet"], k["kod"]))

    mus, urun = {}, {}
    for k in kodlar:
        x = mus.setdefault(k["firma"], {"firma": k["firma"], "rapor": son.get(k["firma"], ""), "toplam": 0,
                                        "eski": 0, "yeni": 0})
        x["toplam"] += k["adet"]
        x["eski"] += k["adet"] if k["eski_kart"] else 0
        x["yeni"] += k["adet"] if k["yeni_kart"] else 0
        for alan, kart in (("eski", k["eski_kart"]), ("yeni", k["yeni_kart"])):
            if kart:
                u = urun.setdefault(kart, {"kart": kart, "ad": str((kartlar.get(kart) or {}).get("urun_adi") or ""),
                                           "eski": 0, "yeni": 0})
                u[alan] += k["adet"]
    musteriler = sorted(mus.values(), key=lambda x: -x["toplam"])
    for x in musteriler:
        x["bagsiz"] = x["toplam"] - x["yeni"]
    urunler = sorted((u for u in urun.values() if u["yeni"] != u["eski"]), key=lambda u: -(u["yeni"] - u["eski"]))
    toplam = {a: sum(x[a] for x in musteriler) for a in ("toplam", "eski", "yeni", "bagsiz")}
    return {"kodlar": kodlar, "musteriler": musteriler, "urunler": urunler, "toplam": toplam}


def stok_ozeti(bizim_stok, firma_stoklari):
    """firma_stoklari: {firma: adet} → üç tanım tek yerde."""
    bizim = bizim_stok or 0
    kanal = sum((v or 0) for v in (firma_stoklari or {}).values())
    return {"toplam_stok": bizim, "kanal_stok": kanal, "zincir_stok": bizim + kanal}
