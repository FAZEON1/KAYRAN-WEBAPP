# -*- coding: utf-8 -*-
"""ANA VERİ — kategori ve marka için TEK KAYNAK (Ekim 2026, entegrasyon Faz 1).

SORUN: Kategori dört ayrı yerden besleniyordu — İthalat listesi eski ithalat
kalemlerinden (hiç ithal edilmemiş 'Ekran Kartı' seçilemiyordu), stok kartları,
Ürün Yönetimi kural listesi, Ref No'nun kendi listesi. Aynı kategori ekrana göre
'MONİTÖR' / 'MONITÖR' / 'monitör' / 'Monitör' görünüyordu; marka 'FAZEON' / 'Fazeon'.

KURAL:
  • Karşılaştırma HER ZAMAN anahtarla: kategori_anahtar / marka_anahtar
    (büyük-küçük, ı/i, boşluk ve noktalama yok sayılır).
  • Ekranda HER ZAMAN tek yazım: kategori_ad / marka_ad
    (kural listesindeki yazım öncelikli: 'Monitör', 'Ekran Kartı', 'FAZEON', 'Mio').
  • Seçenek listesi HER ZAMAN havuzdan: get_kategori_havuzu / get_marka_havuzu
    (kural listesi + tüm stok kartları + İthalat'ta kullanılmışlar).
  • KAYITLI DEĞERLER DEĞİŞTİRİLMEZ. İthalat masraf dağıtımı ve Ref No kırılımı
    kategori adının birebir eşleşmesine dayanır; o modüller kendi yazımlarıyla
    kaydetmeye devam eder — kayit_degeri() mevcut yazımı korur.

Saf fonksiyonlar en üstte (test edilir); veritabanı okuyanlar en altta.
"""
import re

_AYRAC = re.compile(r"[^0-9a-zçğıöşü]+")


def _kucuk(s):
    """Türkçe-doğru küçük harf: İ→i, I→ı."""
    return str(s or "").replace("İ", "i").replace("I", "ı").lower().strip()


# ── Kategori ────────────────────────────────────────────────────────
def kategori_anahtar(s):
    """Karşılaştırma anahtarı. 'MONİTÖR' = 'MONITÖR' = 'monitör' = 'Monitör';
    'KABLO / KONNEKTÖR' = 'Kablo/Konnektör'. ı/i ayrımı yok sayılır: Python'un
    .upper()'ı 'monitör'ü noktasız 'MONITÖR' yaptığı için kayıtlarda ikisi de var."""
    return _AYRAC.sub("", _kucuk(s).replace("ı", "i"))


def _bas_buyuk(s):
    s = " ".join(str(s or "").split())
    if not s:
        return ""
    k = _kucuk(s)
    return {"i": "İ", "ı": "I"}.get(k[0], k[0].upper()) + k[1:]


def _karisik(s):
    """Büyük-küçük karışık yazılmış mı ('Micro SD kart') — tamamı büyük/küçük değil."""
    harf = [c for c in str(s) if c.isalpha()]
    return any(c.isupper() for c in harf) and any(c.islower() for c in harf)


def kategori_ad_haritasi(*kaynaklar, kural_liste=None):
    """{anahtar: görünen ad}. Öncelik: 1) kural listesindeki yazım  2) kaynaklarda
    büyük-küçük KARIŞIK yazılmış bir hâl (kullanıcının özenle yazdığı)  3) baş harf
    büyük. Tamamı büyük 'MICRO SD KART' Türkçe küçültmede 'Mıcro' olurdu (ı/i belirsiz);
    karışık bir yazım varsa o kullanılır."""
    kural = list(kural_liste if kural_liste is not None else _kural_kategoriler())
    out = {kategori_anahtar(x): x for x in kural if kategori_anahtar(x)}
    aday = {}
    for kaynak in kaynaklar:
        for k in kaynak or ():
            a = kategori_anahtar(k)
            if a and a not in out:
                aday.setdefault(a, []).append(" ".join(str(k).split()))
    for a, yazimlar in aday.items():
        out[a] = next((y for y in yazimlar if _karisik(y)), None) or _bas_buyuk(yazimlar[0])
    return out


def kategori_ad(s, kural_liste=None, harita=None):
    """Ekranda gösterilecek TEK yazım ('EKRAN KARTI' → 'Ekran Kartı', 'MONITÖR' → 'Monitör').
    kural_liste verilmezse kural listesi + veritabanı havuzundan kurulan harita kullanılır
    (get_kategori_ad_haritasi, önbellekli). Boş → ''."""
    a = kategori_anahtar(s)
    if not a:
        return ""
    if harita is None:
        harita = (kategori_ad_haritasi(kural_liste=kural_liste) if kural_liste is not None
                  else get_kategori_ad_haritasi())
    return harita.get(a) or _bas_buyuk(s)


def kategori_secenekleri(*kaynaklar, kural_liste=None):
    """Birden çok kaynaktaki kategorileri tek listeye indirir: anahtara göre tekil,
    görünen adla, alfabetik (Türkçe). Kural listesi her zaman dahil."""
    h = kategori_ad_haritasi(*kaynaklar, kural_liste=kural_liste)
    return sorted(h.values(), key=lambda x: _kucuk(x).replace("ı", "i"))


def kayit_degeri(secilen, mevcut_yazimlar, bicim=None):
    """Seçilen kategoriyi bir modülün KENDİ kayıt yazımına çevirir.
    Aynı anahtarlı bir yazım o modülde zaten varsa AYNEN o döner (masraf grubu /
    Ref kırılımı bölünmesin); yoksa bicim(secilen) (ör. büyük harf)."""
    a = kategori_anahtar(secilen)
    if not a:
        return ""
    for m in mevcut_yazimlar or ():
        if kategori_anahtar(m) == a:
            return str(m).strip()
    return (bicim or (lambda x: x))(str(secilen).strip())


def tr_buyuk_harf(s):
    """Türkçe-doğru BÜYÜK harf (i→İ, ı→I) — İthalat ve Ref No'nun kayıt biçimi."""
    s = str(s or "").strip()
    return s.replace("i", "İ").replace("ı", "I").upper()


# ── Marka ───────────────────────────────────────────────────────────
def marka_anahtar(s):
    """'FAZEON' = 'Fazeon' = 'fazeon'; 'MIO' = 'Mio' (Latin ad, ı/i ayrımı yok)."""
    return _AYRAC.sub("", _kucuk(s).replace("ı", "i"))


def marka_ad(s, kural_liste=None):
    """Ekranda TEK yazım: kural listesindeki yazım ('MIO' → 'Mio'), yoksa BÜYÜK harf."""
    m = " ".join(str(s or "").split())
    a = marka_anahtar(m)
    if not a:
        return ""
    for x in (kural_liste if kural_liste is not None else _kural_markalar()):
        if marka_anahtar(x) == a:
            return x
    return m.replace("i", "I").replace("ı", "I").upper()


def marka_secenekleri(*kaynaklar, kural_liste=None):
    kural = list(kural_liste if kural_liste is not None else _kural_markalar())
    gor = {}
    for kaynak in (kural,) + kaynaklar:
        for m in kaynak or ():
            a = marka_anahtar(m)
            if a and a not in gor:
                gor[a] = marka_ad(m, kural)
    return sorted(gor.values(), key=lambda x: x.upper())


# ── Kural listeleri (kayranpm.database tek tanım) ───────────────────
def _kural_kategoriler():
    try:
        from kayranpm.database import KATEGORI_LISTE
        return list(KATEGORI_LISTE)
    except Exception:  # noqa: BLE001
        return []


def _kural_markalar():
    try:
        from kayranpm.database import MARKA_KURALLAR
        return [m for m, _ in MARKA_KURALLAR]
    except Exception:  # noqa: BLE001
        return []


# ── Havuzlar (veritabanı) ───────────────────────────────────────────
def _kategori_kaynaklari():
    kart, ith = [], []
    try:
        from kayranpm.database import get_urun_marka_kategori
        kart = [m.get("kategori") for m in (get_urun_marka_kategori() or {}).values()]
    except Exception:  # noqa: BLE001
        pass
    try:
        from ithalat.database import get_kategoriler
        ith = get_kategoriler() or []
    except Exception:  # noqa: BLE001
        pass
    return kart, ith


def _onbellek(ttl):
    """st.cache_data varsa onu kullan (Yenile düğmesi de temizler); yoksa önbelleksiz."""
    try:
        import streamlit as st
        return st.cache_data(ttl=ttl, show_spinner=False)
    except Exception:  # noqa: BLE001
        return lambda fn: fn


@_onbellek(300)
def get_kategori_ad_haritasi():
    """kategori_ad'ın varsayılan haritası: kural listesi + stok kartları + İthalat.
    Önbellekli: listeler ürün başına kategori_ad çağırır, harita her satırda kurulmaz."""
    return kategori_ad_haritasi(*_kategori_kaynaklari())


def get_kategori_havuzu():
    """Tüm ekranların kategori seçenekleri: kural listesi + stok kartları + İthalat'ta
    kullanılmışlar. Okunamayan kaynak atlanır (liste yine kural listesiyle dolu gelir)."""
    return kategori_secenekleri(*_kategori_kaynaklari())


def get_marka_havuzu():
    kart = []
    try:
        from kayranpm.database import get_urun_marka_kategori
        kart = [m.get("marka") for m in (get_urun_marka_kategori() or {}).values()]
    except Exception:  # noqa: BLE001
        pass
    return marka_secenekleri(kart)
