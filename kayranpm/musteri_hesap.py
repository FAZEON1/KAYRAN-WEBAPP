# -*- coding: utf-8 -*-
"""Müşteri Satışları — SAF hesap (Ekim 2026). Ekran: kayranpm/musteri_ekran.py.

Girdi: firma_stok haftalık satırları (get_musteri_haftalik_satis; haftada yalnız en
güncel yükleme). Dört kırılım: müşteri · marka · ürün · kategori.

Kurallar:
  satış   = aralıktaki haftaların toplamı (haftalik_satis + satis_magaza)
  stok    = her (müşteri, SKU) için aralıktaki SON rapor (stok_miktari + stok_magaza) —
            TOPLANMAZ. Eskiden aralıktaki bütün raporların stoğu üst üste ekleniyordu.
  haftalık ortalama = satış / aralıktaki rapor haftası sayısı
  kapsama = stok / haftalık ortalama (hafta)
"""

KIRILIM = {"musteri": "Müşteri", "marka": "Marka", "urun": "Ürün", "kategori": "Kategori"}
ALT = {"musteri": "urun", "urun": "musteri", "marka": "urun", "kategori": "urun"}


def _i(v):
    try:
        return int(float(v or 0))
    except (TypeError, ValueError):
        return 0


def satis(r):
    return _i(r.get("haftalik_satis")) + _i(r.get("satis_magaza"))


def stok(r):
    return _i(r.get("stok_miktari")) + _i(r.get("stok_magaza"))


def _hafta(r):
    return str(r.get("yukleme_tarihi") or "")[:10]


def _sku(r):
    return str(r.get("sku") or "").strip()


def _firma(r):
    """Kanonik firma (shared.utils.firma_kanonik): eski 'KANAL' kayıtları DİĞER'e katılır."""
    from shared.utils import firma_kanonik
    return firma_kanonik(r.get("firma"))


def haftalar(rows):
    return sorted({_hafta(r) for r in rows if _hafta(r)})


# ── Stok kartı eşleştirme + kategori çözümü ─────────────────────────
# SORUN: kırılım meta'yı HAM SKU ile arıyordu. Müşteri raporundaki SKU
# 'Fazeon X24F165S' / 'x24f165s ' yazılınca kart ('X24F165S') bulunamıyor,
# ürün 'Kategorisiz' + 'Markasız' görünüyordu. Ayrıca 'MONİTÖR' / 'monitör'
# ayrı kategori sayılıyordu.
# ÇÖZÜM: meta_hazirla() rapordaki her SKU için kartı sırayla arar (ayrıntı docstring'de):
#   birebir / normalize SKU → onaylı eşleme tablosu → tahmin adımları (SKU parçası, ürün adı,
#   addaki model kodu, önek). Tahminde birden çok aday çıkarsa kart BAĞLANMAZ ('belirsiz').
# Kategori/marka: kartın değeri; kart yok ya da alan boşsa ürün adından
# tahmin (kategori_oner / marka_oner). Kaynak 'kart' / 'tahmin' /
# '' olarak işaretlenir; ekran tahmin edilenleri sayar, Excel'de görünür.

def _sku_varsayilan(s):
    return str(s or "").strip().upper()


def _ad_norm(s):
    return " ".join(str(s or "").upper().replace("İ", "I").split())


def _kat_kucuk(s):
    return str(s or "").replace("İ", "i").replace("I", "ı").lower().strip()


def kategori_etiketi(kat, kategori_liste=()):
    """Tek yazım — shared.ana_veri.kategori_ad'a devreder (tek kaynak, Ekim 2026)."""
    from shared.ana_veri import kategori_ad
    return kategori_ad(kat, kural_liste=list(kategori_liste or ()))


def _marka_anahtar(s):
    from shared.ana_veri import marka_anahtar
    return marka_anahtar(s)


def marka_etiketi(marka, marka_liste=()):
    """Tek yazım — shared.ana_veri.marka_ad'a devreder (tek kaynak, Ekim 2026)."""
    from shared.ana_veri import marka_ad
    return marka_ad(marka, kural_liste=list(marka_liste or ()))


def _model_parcalari(metin):
    """Ad/SKU içindeki model kodu adayları: harf+rakam içeren, ≥5 karakterlik parçalar.
    'Fazeon 23.8' X24F180 FHD 180Hz' → ['X24F180']  (180HZ: 5 karakter ama rakam+harf → aday,
    kart SKU'su olmadığı için zararsız)."""
    import re
    out = []
    for p in re.split(r"[^0-9A-Z]+", str(metin or "").upper().replace("İ", "I")):
        if len(p) >= 5 and any(c.isdigit() for c in p) and any(c.isalpha() for c in p):
            out.append(p)
    return out


def meta_hazirla(rows, kartlar, sku_fn=None, oner=None, kategori_liste=(), marka_oner=None, marka_liste=(),
                 eslesme=None):
    """{ham rapor SKU'su: {marka, kategori, marka_kaynak, kategori_kaynak, kart_sku, kart_kaynak, adaylar}}
    — rows'taki HER SKU. kartlar: get_urun_marka_kategori() çıktısı {kart_sku: {marka, kategori, urun_adi}}.
    eslesme: onaylı eşleme tablosu {dış kod: kart SKU'su} (sku_eslesme; anahtar sku_fn ile normalize edilir).

    Kart arama sırası:
      1) birebir SKU  2) normalize SKU  (kart_kaynak 'sku')
      3) onaylı eşleme tablosu  (kart_kaynak 'tablo'; kartı silinmişse yok sayılır)
      Tahmin adımları — her adımda TEK aday varsa bağlanır (kart_kaynak 'kural'); BİRDEN ÇOK
      aday varsa durulur, kart bağlanmaz (kart_kaynak 'belirsiz', adaylar listelenir):
      4) SKU'daki parça = kart SKU'su (≥5 karakter)  5) ürün adı birebir
      6) ADDAKİ model kodu = kart SKU'su (pazaryeri kodu SKU olarak gelince: 'HBCV0000G0F6K6' ·
         'Fazeon 23.8' X24F180 …' → X24F180)
      7) addaki model kodu bir kart SKU'sunun ÖNEKİ (≥6 karakter; renk eki: X27F300 → X27F300S)
    Eskiden 7. adım birden çok aday aynı marka + kategorideyse alfabetik ilkini seçiyordu:
    'F11PA650B' adlı beyaz ürün F11PA650BBM (siyah) kartına bağlanıyordu (Ekim 2026).
    Belirsizde adayların hepsi aynı marka + kategorideyse o değerler kullanılır (kırılım değişmez).
    Kart yoksa ya da alan boşsa marka/kategori addan tahmin edilir (kaynak 'tahmin')."""
    skn = sku_fn or _sku_varsayilan
    kartlar = kartlar or {}
    norm, ad_idx = {}, {}
    for ks, m in kartlar.items():
        n = skn(ks)
        if n and n not in norm:
            norm[n] = ks
        a = _ad_norm((m or {}).get("urun_adi"))
        if a:
            ad_idx.setdefault(a, set()).add(ks)
    tablo = {}
    for dk, ks in (eslesme or {}).items():
        kn = skn(ks)
        if skn(dk) and kn in norm:
            tablo[skn(dk)] = norm[kn]

    def _imza(ks):
        m = kartlar.get(ks) or {}
        return (_kat_kucuk(m.get("marka")), _kat_kucuk(m.get("kategori")))

    def _kart_bul(ham, urun_adi):
        """(kart SKU'su | None, kart_kaynak, adaylar)."""
        if ham in kartlar:
            return ham, "sku", []
        n = skn(ham)
        if n in norm:
            return norm[n], "sku", []
        if n in tablo:
            return tablo[n], "tablo", []
        parcalar = _model_parcalari(urun_adi)
        adimlar = (
            lambda: {norm[p] for p in n.replace("-", " ").replace("_", " ").replace("/", " ").split()
                     if len(p) >= 5 and p in norm},
            lambda: set(ad_idx.get(_ad_norm(urun_adi), ())),
            lambda: {norm[p] for p in parcalar if p in norm},
            lambda: {ks for p in parcalar if len(p) >= 6 for nk, ks in norm.items() if nk.startswith(p)},
        )
        for adim in adimlar:
            aday = sorted(adim())
            if len(aday) == 1:
                return aday[0], "kural", []
            if aday:
                return None, "belirsiz", aday
        return None, "", []

    def _tahmin(fn, adaylar):
        if not fn:
            return ""
        for ad in adaylar:
            if not ad:
                continue
            try:
                v = (fn(ad) or "").strip()
            except Exception:  # noqa: BLE001
                v = ""
            if v:
                return v
        return ""

    out = {}
    for r in rows or []:
        ham = _sku(r)
        if ham in out:
            continue
        ks, kk, aday = _kart_bul(ham, r.get("urun_adi"))
        m = kartlar.get(ks) or {}
        if not ks and aday and len({_imza(k) for k in aday}) == 1:
            m = {k: (kartlar.get(aday[0]) or {}).get(k) for k in ("marka", "kategori")}
        adlar = (m.get("urun_adi"), r.get("urun_adi"))
        kat = str(m.get("kategori") or "").strip()
        kat_k = "kart" if kat else ""
        if not kat:
            kat = _tahmin(oner, adlar + (ham,))
            kat_k = "tahmin" if kat else ""
        mar = str(m.get("marka") or "").strip()
        mar_k = "kart" if mar else ""
        if not mar and marka_oner:
            # Önce BİLİNEN markaya çıkan tahmin (kart adı ya da rapor adı); bulunamazsa
            # marka_oner'in "ilk kelime" tahmini — rakam içeriyorsa model kodudur, marka değil
            # (kart adı yalnız 'X32F240S' ise marka 'X32F240S' yazılıyordu). Ham SKU'dan tahmin yok.
            bilinen = {_marka_anahtar(x) for x in marka_liste or ()}
            tahminler = [_tahmin(marka_oner, (ad,)) for ad in adlar]
            mar = next((t for t in tahminler if t and _marka_anahtar(t) in bilinen), "") or \
                next((t for t in tahminler if t and not any(c.isdigit() for c in t)), "")
            mar_k = "tahmin" if mar else ""
        out[ham] = {"marka": marka_etiketi(mar, marka_liste),
                    "kategori": kategori_etiketi(kat, kategori_liste),
                    "marka_kaynak": mar_k, "kategori_kaynak": kat_k,
                    "kart_sku": ks or "", "kart_kaynak": kk, "adaylar": aday}
    return out


def eslesme_dogrula(dis_kod, kart_sku, kartlar, sku_fn=None, mevcut=None):
    """Eşleme tablosuna yazmadan önce koruma. Döner: (ok, mesaj, {dis_kod, kart_sku} | None).
    Kurallar:
      - dış kod boş olamaz; kart SKU'su stok kartlarında bulunmalı;
      - dış kod KENDİSİ bir kart SKU'suysa başka bir karta eşlenemez (F11PA650BWM ≠ F11PA650BBM:
        iki ayrı ürün; kod yazım farkı değil);
      - dış kod zaten başka bir karta eşliyse önce o eşleme kaldırılmalı.
    Anahtarlar sku_fn ile normalize edilir ('Fazeon x' = 'X')."""
    skn = sku_fn or _sku_varsayilan
    norm = {}
    for ks in (kartlar or {}):
        norm.setdefault(skn(ks), ks)
    dis, kn = skn(dis_kod), skn(kart_sku)
    if not dis:
        return False, "Dış kod boş.", None
    if kn not in norm:
        return False, f"{str(kart_sku or '').strip() or '(boş)'} stok kartlarında yok.", None
    kart = norm[kn]
    if dis in norm:
        if norm[dis] == kart:
            return False, f"{dis} zaten {kart} kartının kendi kodu; eşleme gerekmez.", None
        return False, (f"{dis} kendi stok kartı olan bir kod; {kart} kartına bağlanamaz "
                       "(ayrı ürünler)."), None
    onceki = {skn(k): v for k, v in (mevcut or {}).items()}.get(dis)
    if onceki and skn(onceki) != kn:
        return False, f"{dis} zaten {onceki} kartına eşli; önce o eşlemeyi kaldır.", None
    return True, "", {"dis_kod": dis, "kart_sku": kart}


def _anahtar(r, kirilim, meta):
    sku = _sku(r)
    if kirilim == "musteri":
        return _firma(r)
    if kirilim == "urun":
        return sku
    m = (meta or {}).get(sku) or {}
    if kirilim == "marka":
        return (m.get("marka") or "").strip() or "Markasız"
    return (m.get("kategori") or "").strip() or "Kategorisiz"


def _son_raporlar(rows):
    """(müşteri, SKU) → aralıktaki son rapor satırı."""
    son = {}
    for r in rows:
        k = (_firma(r), _sku(r))
        if k not in son or _hafta(r) >= _hafta(son[k]):
            son[k] = r
    return son


def grupla(rows, kirilim, meta=None, ad_fn=None, hafta_sayisi=None):
    """Kırılıma göre gruplar, satışa göre azalan. hafta_sayisi verilmezse rows'tan."""
    hs = haftalar(rows)
    n = hafta_sayisi or len(hs) or 1
    toplam = sum(satis(r) for r in rows) or 0
    g = {}
    for r in rows:
        a = _anahtar(r, kirilim, meta)
        x = g.setdefault(a, {"anahtar": a, "satis": 0, "stok": 0, "_seri": {}, "urun_adi": ""})
        x["satis"] += satis(r)
        x["_seri"][_hafta(r)] = x["_seri"].get(_hafta(r), 0) + satis(r)
        if kirilim == "urun" and not x["urun_adi"]:
            x["urun_adi"] = str(r.get("urun_adi") or "").strip()
    for r in _son_raporlar(rows).values():
        g[_anahtar(r, kirilim, meta)]["stok"] += stok(r)
    out = []
    for a, x in g.items():
        ort = x["satis"] / n
        ad = a
        if kirilim == "musteri" and ad_fn:
            try:
                ad = ad_fn(a) or a
            except Exception:  # noqa: BLE001
                ad = a
        out.append({"anahtar": a, "ad": ad, "urun_adi": x["urun_adi"], "satis": x["satis"], "stok": x["stok"],
                    "haftalik_ort": ort, "kapsama": (x["stok"] / ort) if ort > 0 else None,
                    "pay": (x["satis"] / toplam * 100) if toplam else 0.0,
                    "seri": [x["_seri"].get(h, 0) for h in hs]})
    out.sort(key=lambda x: (-x["satis"], str(x["ad"])))
    return out


def detay(rows, kirilim, anahtar, meta=None, ad_fn=None):
    """Seçili grubun alt kırılımı (müşteri → ürünler, ürün → müşteriler, marka/kategori → ürünler).
    Haftalık ortalama aralığın TÜM haftalarına bölünür (grubun sattığı haftalara değil)."""
    alt = [r for r in rows if _anahtar(r, kirilim, meta) == anahtar]
    return grupla(alt, ALT[kirilim], meta, ad_fn=ad_fn, hafta_sayisi=len(haftalar(rows)) or 1)


def ozet(rows):
    hs = haftalar(rows)
    s = sum(satis(r) for r in rows)
    st = sum(stok(r) for r in _son_raporlar(rows).values())
    ort = (s / len(hs)) if hs else 0.0
    return {"satis": s, "stok": st, "hafta": len(hs), "haftalik_ort": ort,
            "kapsama": (st / ort) if ort > 0 else None, "seri": [sum(satis(r) for r in rows if _hafta(r) == h)
                                                                  for h in hs], "haftalar": hs}
