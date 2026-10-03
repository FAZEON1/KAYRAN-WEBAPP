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
    return str(r.get("firma") or "").strip()


def haftalar(rows):
    return sorted({_hafta(r) for r in rows if _hafta(r)})


# ── Stok kartı eşleştirme + kategori çözümü ─────────────────────────
# SORUN: kırılım meta'yı HAM SKU ile arıyordu. Müşteri raporundaki SKU
# 'Fazeon X24F165S' / 'x24f165s ' yazılınca kart ('X24F165S') bulunamıyor,
# ürün 'Kategorisiz' + 'Markasız' görünüyordu. Ayrıca 'MONİTÖR' / 'monitör'
# ayrı kategori sayılıyordu.
# ÇÖZÜM: meta_hazirla() rapordaki her SKU için kartı sırayla arar:
#   1) birebir SKU  2) normalize SKU (sku_fn)  3) SKU'daki bir parça bir kart
#   SKU'suna eşitse (≥5 karakter)  4) ürün adı birebir (boşluk/harf farkı yok sayılır)
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
    """Aynı kategorinin farklı yazımlarını tek etikete indirger.
    Kural listesindeki yazım öncelikli ('KABLO/KONNEKTÖR' → 'Kablo/Konnektör');
    listede yoksa Türkçe-doğru baş harf büyük ('MİCROSD KART' → 'Microsd kart')."""
    k = _kat_kucuk(kat)
    if not k:
        return ""
    for x in kategori_liste or ():
        if _kat_kucuk(x) == k:
            return x
    return {"i": "İ", "ı": "I"}.get(k[0], k[0].upper()) + k[1:]


def _marka_anahtar(s):
    """Marka karşılaştırma anahtarı: marka adları Latin ('MIO' Türkçe küçültmede 'mıo' olur,
    'Mio' ile tutmaz) → ı/i ayrımı yok sayılır."""
    return _kat_kucuk(s).replace("ı", "i")


def marka_etiketi(marka, marka_liste=()):
    """'Fazeon' / 'FAZEON' / 'fazeon' → tek etiket. Kural listesindeki yazım öncelikli
    ('MIO' → 'Mio'); listede yoksa BÜYÜK harf ('kaspersky' → 'KASPERSKY')."""
    m = " ".join(str(marka or "").split())
    if not m:
        return ""
    k = _marka_anahtar(m)
    for x in marka_liste or ():
        if _marka_anahtar(x) == k:
            return x
    return m.replace("i", "İ").replace("ı", "I").upper()


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


def meta_hazirla(rows, kartlar, sku_fn=None, oner=None, kategori_liste=(), marka_oner=None, marka_liste=()):
    """{ham rapor SKU'su: {marka, kategori, marka_kaynak, kategori_kaynak, kart_sku}} — rows'taki HER SKU.
    kartlar: get_urun_marka_kategori() çıktısı {kart_sku: {marka, kategori, urun_adi}}.

    Kart arama sırası:
      1) birebir SKU  2) normalize SKU  3) SKU'daki bir parça = kart SKU'su
      4) ürün adı birebir  5) ADDAKİ model kodu = kart SKU'su (pazaryeri kodu SKU
         olarak gelince: 'HBCV0000G0F6K6' · 'Fazeon 23.8' X24F180 …' → X24F180)
      6) addaki model kodu bir kart SKU'sunun ÖNEKİ ise (renk eki: X27F300 → X27F300S/B)
         — yalnız tüm adaylar aynı marka + kategoriye çıkıyorsa (yanlış karta bağlamaz).
    Kart yoksa ya da alan boşsa marka/kategori addan tahmin edilir (kaynak 'tahmin')."""
    skn = sku_fn or _sku_varsayilan
    kartlar = kartlar or {}
    norm, ad_idx = {}, {}
    for ks, m in kartlar.items():
        n = skn(ks)
        if n and n not in norm:
            norm[n] = ks
        a = _ad_norm((m or {}).get("urun_adi"))
        if a and a not in ad_idx:
            ad_idx[a] = ks

    def _imza(ks):
        m = kartlar.get(ks) or {}
        return (_kat_kucuk(m.get("marka")), _kat_kucuk(m.get("kategori")))

    def _onek_bul(parca):
        if len(parca) < 6:
            return None
        aday = sorted(ks for n, ks in norm.items() if n.startswith(parca))
        if aday and len({_imza(k) for k in aday}) == 1:
            return aday[0]
        return None

    def _kart_bul(ham, urun_adi):
        if ham in kartlar:
            return ham
        n = skn(ham)
        if n in norm:
            return norm[n]
        for parca in n.replace("-", " ").replace("_", " ").replace("/", " ").split():
            if len(parca) >= 5 and parca in norm:
                return norm[parca]
        if _ad_norm(urun_adi) in ad_idx:
            return ad_idx[_ad_norm(urun_adi)]
        parcalar = _model_parcalari(urun_adi)
        for parca in parcalar:
            if parca in norm:
                return norm[parca]
        for parca in parcalar:
            ks = _onek_bul(parca)
            if ks:
                return ks
        return None

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
        ks = _kart_bul(ham, r.get("urun_adi"))
        m = kartlar.get(ks) or {}
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
                    "kart_sku": ks or ""}
    return out


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
