"""
KAYRAN — Veritabanı Katmanı (Supabase PostgreSQL)
"""
import streamlit as st
# Türkiye saat dilimi için ortak yardımcılar
from shared.utils import tr_today, tr_now, tr_today_iso, tr_now_str, tr_tomorrow, tr_yesterday as _tr_today_iso_dummy
from supabase import create_client, Client
from datetime import date
from collections import defaultdict


@st.cache_resource
def get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    # service_role_key varsa onu kullan (RLS aşılır, sunucuda kalır); yoksa anon key.
    key = st.secrets["supabase"].get("service_role_key") or st.secrets["supabase"]["key"]
    return create_client(url, key)


def _cache_temizle():
    """Tüm @st.cache_data önbelleklerini temizler.
    Her yazma (ekle/sil/güncelle) işleminden sonra çağrılır."""
    try:
        st.cache_data.clear()
    except Exception:
        pass


def get_today():
    return tr_today_iso()

def initialize_db():
    pass

def _rows(response):
    return response.data if response.data else []

def _row(response):
    d = response.data
    return d[0] if d else None

def _hepsi(table, secim="*", order_col=None, desc=False):
    """Supabase 1000 satır limitini aşarak bir tablodaki TÜM satırları sayfalayarak çeker."""
    sb = get_client()
    rows, start = [], 0
    while True:
        q = sb.table(table).select(secim)
        if order_col:
            q = q.order(order_col, desc=desc)
        chunk = _rows(q.range(start, start + 999).execute())
        rows.extend(chunk)
        if len(chunk) < 1000:
            break
        start += 1000
    return rows

# ── ÜRÜNLER ─────────────────────────────────────────────────────────

# Satış fiyat listesinde hazır gelen ana müşteriler (ekstra müşteri serbestçe eklenebilir)
ANA_MUSTERILER = ["Vatan", "Hepsiburada", "İtopya", "Trendyol", "Teknosa"]


def upsert_urun(sku, urun_adi, kategori="", marka="", satis_fiyati=0.0,
                alis_fiyati=0.0, hedef_kar_marji=0.0, ozellikler="",
                bizim_stok=0, trendyol_stok=0,
                satis_fiyat_listesi=None, eol=None):
    """Ürün ekler/günceller.
    satis_fiyat_listesi: {musteri: fiyat} — müşteri bazlı fiyatlar (opsiyonel, None ise dokunulmaz).
    eol: True/False — End of Life işareti (opsiyonel, None ise dokunulmaz). EOL ürünler sipariş önerisine girmez.
    """
    sb = get_client()
    bugun = get_today()
    mevcut = _row(sb.table("urunler").select("ilk_giris_tarihi").eq("sku", sku).execute())
    ilk_tarih = mevcut["ilk_giris_tarihi"] if mevcut and mevcut.get("ilk_giris_tarihi") else bugun
    _payload = {
        "sku": sku, "urun_adi": urun_adi, "kategori": kategori or "",
        "marka": marka or "", "satis_fiyati": float(satis_fiyati or 0),
        "alis_fiyati": float(alis_fiyati or 0),
        "hedef_kar_marji": float(hedef_kar_marji or 0),
        "ozellikler": ozellikler or "",
        "bizim_stok": int(bizim_stok or 0),
        "trendyol_stok": int(trendyol_stok or 0),
        "ilk_giris_tarihi": ilk_tarih,
        "guncelleme_tarihi": bugun,
    }
    # Opsiyonel yeni kolonlar — sadece verildiyse yaz (None ise mevcut değer korunur)
    if satis_fiyat_listesi is not None:
        _payload["satis_fiyat_listesi"] = {
            str(k).strip(): float(v or 0)
            for k, v in (satis_fiyat_listesi or {}).items()
            if str(k).strip() and float(v or 0) != 0
        }
    if eol is not None:
        _payload["eol"] = bool(eol)
    try:
        sb.table("urunler").upsert(_payload, on_conflict="sku").execute()
    except Exception:
        # Yeni kolonlar (satis_fiyat_listesi/eol) tabloda yoksa onlarsız tekrar dene
        for _opt in ("satis_fiyat_listesi", "eol"):
            _payload.pop(_opt, None)
        sb.table("urunler").upsert(_payload, on_conflict="sku").execute()
    sb.table("stok_yas").upsert(
        {"sku": sku, "ilk_gorulen_tarih": bugun}, on_conflict="sku"
    ).execute()
    _cache_temizle()


# ── Kategori yönetimi ──────────────────────────────────────────────
# Öneri kuralları: (kategori, anahtar kelime regex). Sıra önemli — ilk eşleşen kazanır.
import re as _re
KATEGORI_KURALLAR = [
    ("Araç Kamerası",   r"MIVUE|DASHCAM|ARAÇ\s*İÇİ|ARAC ICI|G-SENSOR|STARVIS"),
    ("Ekran Kartı",     r"EKRAN KARTI|GEFORCE|RADEON|\bRTX\b|\bGTX\b|GDDR"),
    ("Ekran Koruyucu",  r"EKRAN KORUYUCU|HYDROGEL|TEMPERED|CAM KORUYUCU|NANO CAM"),
    ("Monitör",         r"MONITOR|MONİTÖR|GAMING MONITOR|\bIPS\b|\bVA\b|\d+\s*HZ|\bHDMI\b"),
    ("CPU Soğutucu",    r"İŞLEMCİ|ISLEMCI|\bCPU\b"),
    ("Kule Soğutucu",   r"KULE"),
    ("Sıvı Soğutma",    r"\bAIO\b|SIVI|LIQUID|WATER COOL|RADYATÖR|RADYATOR"),
    ("Fan",             r"\bFAN\b|FANI|RGB FAN"),
    ("Güç Kaynağı",     r"\bPSU\b|POWER SUPPLY|GÜÇ KAYNA|GUC KAYNA"),
    ("Kasa",            r"KASA|\bCASE\b|\bATX\b|MESH|\bMID\s*TOWER\b"),
    ("Kablo/Konnektör", r"KONNEKTÖR|KONNEKTOR|\bKABLO\b|\bSATA\b|ADAPTÖR|ADAPTOR|5V3PIN"),
    ("El Aleti",        r"TORNAVIDA|ALET SET|ŞARJLI HASSAS|HASSAS TORNAVIDA"),
    ("Klavye/Mouse",    r"KLAVYE|MOUSE|\bFARE\b|KEYBOARD"),
    ("Kulaklık",        r"KULAKLIK|HEADSET|EARBUD"),
]
KATEGORI_LISTE = [k for k, _ in KATEGORI_KURALLAR]


def kategori_oner(urun_adi):
    """Ürün adından kategori önerir; eşleşme yoksa boş döner."""
    ad = str(urun_adi or "").upper()
    for kat, pat in KATEGORI_KURALLAR:
        if _re.search(pat, ad):
            return kat
    return ""


def set_kategori(sku, kategori):
    """Tek bir ürünün kategorisini günceller."""
    try:
        get_client().table("urunler").update({"kategori": kategori or ""}).eq("sku", str(sku)).execute()
        return True
    except Exception:
        return False


def toplu_kategori_kaydet(sku_kategori):
    """{sku: kategori} sözlüğüyle toplu günceller. (guncellenen_sayisi, hata_sayisi) döner."""
    ok, hata = 0, 0
    sb = get_client()
    for sku, kat in (sku_kategori or {}).items():
        try:
            sb.table("urunler").update({"kategori": (kat or "").strip()}).eq("sku", str(sku)).execute()
            ok += 1
        except Exception:
            hata += 1
    _cache_temizle()
    return ok, hata


# ── Marka önerisi ──────────────────────────────────────────────────
MARKA_KURALLAR = [
    ("FAZEON",    r"\bFAZEON\b"),
    ("INNO3D",    r"\bINNO ?3D\b"),
    ("EXCAVATOR", r"\bEXCAVATOR\b"),
    ("Mio",       r"\bMIO\b|MIVUE"),
]


def marka_oner(urun_adi):
    """Ürün adından marka önerir. Bilinen markalar + ilk kelime tahmini."""
    ad = str(urun_adi or "").upper()
    for marka, pat in MARKA_KURALLAR:
        if _re.search(pat, ad):
            return marka
    # Fallback: ilk kelime (markalar genelde başta yazılır)
    parcalar = str(urun_adi or "").strip().split()
    if parcalar:
        ilk = parcalar[0].strip()
        if len(ilk) >= 2 and any(c.isalpha() for c in ilk):
            return ilk.upper()
    return ""


def toplu_kategori_marka_kaydet(sku_data):
    """{sku: {"kategori": ..., "marka": ...}} ile kategori ve/veya markayı toplu günceller.
    Sadece sözlükte bulunan alanlar yazılır. (guncellenen, hata) döner."""
    ok, hata = 0, 0
    sb = get_client()
    for sku, d in (sku_data or {}).items():
        try:
            upd = {}
            if "kategori" in d:
                upd["kategori"] = (d.get("kategori") or "").strip()
            if "marka" in d:
                upd["marka"] = (d.get("marka") or "").strip()
            if upd:
                sb.table("urunler").update(upd).eq("sku", str(sku)).execute()
                ok += 1
        except Exception:
            hata += 1
    _cache_temizle()
    return ok, hata


def toplu_satis_kaydet(sku_data):
    """{sku: {"satis_fiyati": float, "hedef_kar_marji": float}} ile satış fiyatı / hedef marjı
    toplu günceller. Sadece sözlükte bulunan alanlar yazılır. (guncellenen, hata) döner."""
    ok, hata = 0, 0
    sb = get_client()
    for sku, d in (sku_data or {}).items():
        try:
            upd = {}
            if "satis_fiyati" in d:
                upd["satis_fiyati"] = float(d.get("satis_fiyati") or 0)
            if "hedef_kar_marji" in d:
                upd["hedef_kar_marji"] = float(d.get("hedef_kar_marji") or 0)
            if upd:
                sb.table("urunler").update(upd).eq("sku", str(sku)).execute()
                ok += 1
        except Exception:
            hata += 1
    _cache_temizle()
    return ok, hata


def _kat_norm(s):
    """Karşılaştırma için kategori adını normalize eder (büyük/küçük + Türkçe harf farkını yok sayar)."""
    s = str(s or "").strip().lower().replace("i̇", "i")
    for a, b in (("ı", "i"), ("ş", "s"), ("ğ", "g"), ("ü", "u"), ("ö", "o"), ("ç", "c")):
        s = s.replace(a, b)
    return s


def kategori_standartlastir():
    """Aynı kategorinin farklı yazımlarını (ör. MONİTÖR / Monitör) tek standart biçimde birleştirir.
    Bilinen kategoriler KATEGORI_LISTE'deki yazıma çevrilir. (degisen_urun, {eski: yeni}) döner."""
    sb = get_client()
    rows = sb.table("urunler").select("sku, kategori").execute().data or []
    canon = {_kat_norm(k): k for k in KATEGORI_LISTE}
    sku_yeni, degisim = {}, {}
    for r in rows:
        eski = (r.get("kategori") or "").strip()
        if not eski:
            continue
        yeni = canon.get(_kat_norm(eski), eski)  # bilinen listede varsa standart yazım, yoksa olduğu gibi
        if yeni != eski:
            sku_yeni[r["sku"]] = yeni
            degisim[eski] = yeni
    for sku, yeni in sku_yeni.items():
        try:
            sb.table("urunler").update({"kategori": yeni}).eq("sku", str(sku)).execute()
        except Exception:
            pass
    _cache_temizle()
    return len(sku_yeni), degisim


# ── Ayarlar (sipariş eşiği) ─────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_uretim_suresi():
    """Sipariş eşiği = üretim/tedarik süresi (gün). pm_ayarlar tablosu yoksa varsayılan 135."""
    try:
        rows = _rows(get_client().table("pm_ayarlar").select("deger")
                     .eq("anahtar", "uretim_suresi_gun").limit(1).execute())
        if rows and str(rows[0].get("deger") or "").strip():
            return max(1, int(float(rows[0]["deger"])))
    except Exception:
        pass
    return 135


def set_uretim_suresi(gun):
    """Sipariş eşiğini kaydeder. Tablo yoksa False döner (varsayılan 135 kullanılmaya devam eder)."""
    try:
        get_client().table("pm_ayarlar").upsert(
            {"anahtar": "uretim_suresi_gun", "deger": str(int(gun))},
            on_conflict="anahtar").execute()
        _cache_temizle()
        return True
    except Exception:
        return False

@st.cache_data(ttl=300, show_spinner=False)
def get_all_dashboard_data():
    sb = get_client()
    urunler = _rows(sb.table("urunler").select("*").order("urun_adi").execute())
    firma_listesi = ["ITOPYA", "HB", "VATAN", "MONDAY", "KANAL", "DIGER"]
    firma_data = {}
    for firma in firma_listesi:
        son = _row(sb.table("firma_stok").select("yukleme_tarihi").eq("firma", firma)
                   .order("yukleme_tarihi", desc=True).limit(1).execute())
        if son:
            rows = _rows(sb.table("firma_stok").select("*")
                        .eq("firma", firma).eq("yukleme_tarihi", son["yukleme_tarihi"]).execute())
            firma_data[firma] = {r["sku"]: r for r in rows}
        else:
            firma_data[firma] = {}
    stok_yas_data = {r["sku"]: r for r in _rows(sb.table("stok_yas").select("*").execute())}
    yoldaki_data = {r["sku"]: r for r in _rows(sb.table("yoldaki_urunler").select("*").execute())}
    # İthalat'tan gelen yolda (Üretimde/Yolda/Gümrükte/Antrepoda) miktarını mevcut elle veriye EKLE
    try:
        from ithalat.database import get_ithalat_yolda_ozet
        _ith_yolda = get_ithalat_yolda_ozet() or {}
    except Exception:
        _ith_yolda = {}
    for _sku, _iy in _ith_yolda.items():
        _mev = yoldaki_data.get(_sku)
        if _mev:
            _mev["yoldaki_miktar"] = (_mev.get("yoldaki_miktar", 0) or 0) + _iy["yoldaki_miktar"]
            if not (str(_mev.get("varis_tarihi", "") or "").strip()) and _iy.get("varis_tarihi"):
                _mev["varis_tarihi"] = _iy["varis_tarihi"]
            _mev["_ithalat_yolda"] = _iy["yoldaki_miktar"]
            _mev["_ithalat_durumlar"] = _iy.get("durumlar", [])
        else:
            yoldaki_data[_sku] = {
                "sku": _sku,
                "yoldaki_miktar": _iy["yoldaki_miktar"],
                "varis_tarihi": _iy.get("varis_tarihi", ""),
                "_ithalat_yolda": _iy["yoldaki_miktar"],
                "_ithalat_durumlar": _iy.get("durumlar", []),
            }
    tum_firma_rows = _hepsi("firma_stok", "*", "yukleme_tarihi")
    gecmis_satislar = defaultdict(list)
    for row in tum_firma_rows:
        gecmis_satislar[row["sku"]].append(row.get("haftalik_satis", 0) or 0)
    return urunler, firma_data, stok_yas_data, yoldaki_data, dict(gecmis_satislar)

@st.cache_data(ttl=300, show_spinner=False)
def get_urun_detay(sku):
    return _row(get_client().table("urunler").select("*").eq("sku", sku).execute())

def sil_urun(sku):
    sb = get_client()
    for tablo in ["urunler", "firma_stok",
                  "yoldaki_urunler", "stok_yas", "siparis_onerileri"]:
        sb.table(tablo).delete().eq("sku", sku).execute()
        _cache_temizle()

@st.cache_data(ttl=300, show_spinner=False)
def get_tum_sku_listesi():
    return _rows(get_client().table("urunler").select("sku, urun_adi").order("sku").execute())


# ── İTHALAT SENKRONİZASYONU ─────────────────────────────────────────
def ithalat_sku_ozet():
    """İthalat'taki distinct SKU'lar → {sku: {'urun_adi':..., 'adet':...}}."""
    try:
        from ithalat.database import get_tum_kalemler
        kalemler = get_tum_kalemler()
    except Exception:
        return {}
    out = {}
    for k in (kalemler or []):
        sku = str(k.get("sku") or "").strip()
        if not sku or sku.lower() == "nan":
            continue
        if sku not in out:
            out[sku] = {"urun_adi": str(k.get("urun_adi") or "").strip(), "adet": 0.0}
        try:
            out[sku]["adet"] += float(k.get("adet") or 0)
        except Exception:
            pass
        if not out[sku]["urun_adi"] and k.get("urun_adi"):
            out[sku]["urun_adi"] = str(k.get("urun_adi")).strip()
    return out


def ithalat_senkron_onizleme():
    """Senkron öncesi fark: (eklenecek_set, silinecek_set, korunan_set, ith_ozet, mevcut_map)."""
    ith = ithalat_sku_ozet()
    ith_skus = set(ith.keys())
    mevcut = get_tum_sku_listesi()
    mevcut_map = {str(u.get("sku") or "").strip(): (u.get("urun_adi") or "")
                  for u in mevcut if str(u.get("sku") or "").strip()}
    mevcut_skus = set(mevcut_map.keys())
    return (ith_skus - mevcut_skus, mevcut_skus - ith_skus,
            ith_skus & mevcut_skus, ith, mevcut_map)


def senkronize_urunler_ithalattan(sil_eski=True):
    """urunler tablosunu İthalat SKU'larına eşitler.
    - İthalat'ta olup üründe olmayanları EKLER (urun_adi İthalat'tan, diğer alanlar boş/0).
    - sil_eski=True ise üründe olup İthalat'ta olmayanları SİLER (eski modeller).
    - Ortak SKU'lar dokunulmaz (satış/stok/hedef korunur).
    Döner: dict(eklendi, silindi, korundu, hata, eklenenler, silinenler, hatalar)."""
    eklenecek, silinecek, korunan, ith, _ = ithalat_senkron_onizleme()
    eklendi, hata, hatalar = 0, 0, []
    for sku in eklenecek:
        try:
            _ad = ith.get(sku, {}).get("urun_adi", "") or ""
            upsert_urun(sku, _ad, kategori_oner(_ad), marka_oner(_ad))
            eklendi += 1
        except Exception as e:
            hata += 1
            if len(hatalar) < 5:
                hatalar.append(f"{sku}: {type(e).__name__}: {str(e)[:80]}")
    silindi = 0
    if sil_eski:
        for sku in silinecek:
            try:
                sil_urun(sku)
                silindi += 1
            except Exception:
                pass
    _cache_temizle()
    return {"eklendi": eklendi, "silindi": silindi, "korundu": len(korunan),
            "hata": hata, "eklenenler": sorted(eklenecek), "silinenler": sorted(silinecek),
            "hatalar": hatalar}


def ithalat_eksikleri_ekle():
    """İthalat'ta olup üründe olmayan SKU'ları TEK upsert ile ekler (hızlı · silme YOK).
    Otomatik senkron için kullanılır. Döner: eklenen sayısı."""
    try:
        eklenecek, _sil, _kor, ith, _ = ithalat_senkron_onizleme()
        if not eklenecek:
            return 0
        sb = get_client()
        bugun = get_today()
        rows, stok_yas_rows = [], []
        for sku in eklenecek:
            _ad = ith.get(sku, {}).get("urun_adi", "") or ""
            rows.append({
                "sku": sku, "urun_adi": _ad,
                "kategori": kategori_oner(_ad), "marka": marka_oner(_ad),
                "satis_fiyati": 0.0, "alis_fiyati": 0.0,
                "hedef_kar_marji": 0.0, "ozellikler": "", "bizim_stok": 0,
                "trendyol_stok": 0, "ilk_giris_tarihi": bugun, "guncelleme_tarihi": bugun,
            })
            stok_yas_rows.append({"sku": sku, "ilk_gorulen_tarih": bugun})
        sb.table("urunler").upsert(rows, on_conflict="sku").execute()
        try:
            sb.table("stok_yas").upsert(stok_yas_rows, on_conflict="sku").execute()
        except Exception:
            pass
        _cache_temizle()
        return len(rows)
    except Exception:
        return 0

# ── FİRMA STOK ──────────────────────────────────────────────────────

def upsert_firma_stok(firma, sku, urun_adi, stok_miktari, haftalik_satis):
    get_client().table("firma_stok").upsert({
        "firma": firma, "sku": sku, "urun_adi": urun_adi or "",
        "stok_miktari": int(stok_miktari or 0),
        "haftalik_satis": int(haftalik_satis or 0),
        "yukleme_tarihi": get_today(),
    }, on_conflict="firma,sku,yukleme_tarihi").execute()
    _cache_temizle()

# ── YOLDAKI ─────────────────────────────────────────────────────────

def upsert_yoldaki_urun(sku, urun_adi, yoldaki_miktar, tahmini_varis_tarihi, yoldaki_tedarikci=""):
    get_client().table("yoldaki_urunler").upsert({
        "sku": sku, "urun_adi": urun_adi or "",
        "yoldaki_miktar": int(yoldaki_miktar or 0),
        "tahmini_varis_tarihi": str(tahmini_varis_tarihi or ""),
        "yoldaki_tedarikci": yoldaki_tedarikci or "",
        "yukleme_tarihi": get_today(),
    }, on_conflict="sku").execute()
    _cache_temizle()

@st.cache_data(ttl=300, show_spinner=False)
def get_yoldaki_urunler():
    rows = _rows(get_client().table("yoldaki_urunler").select("*").execute())
    return {r["sku"]: r for r in rows}

# ── SİPARİŞ ÖNERİLERİ ───────────────────────────────────────────────

def ekle_siparis_onerisi(firma, sku, urun_adi, miktar):
    get_client().table("siparis_onerileri").insert({
        "firma": firma, "sku": sku, "urun_adi": urun_adi or "",
        "oneri_miktari": int(miktar or 0),
        "durum": "bekliyor", "olusturma_tarihi": get_today(),
    }).execute()
    _cache_temizle()

@st.cache_data(ttl=300, show_spinner=False)
def get_siparis_onerileri():
    return _rows(get_client().table("siparis_onerileri").select("*").order("olusturma_tarihi", desc=True).execute())

def onayla_siparis(kayit_id):
    get_client().table("siparis_onerileri").update(
        {"durum": "onaylandi", "onay_tarihi": get_today()}
    ).eq("id", kayit_id).execute()
    _cache_temizle()

def reddet_siparis(kayit_id):
    get_client().table("siparis_onerileri").update(
        {"durum": "reddedildi", "onay_tarihi": get_today()}
    ).eq("id", kayit_id).execute()
    _cache_temizle()

# ── KAMPANYALAR ─────────────────────────────────────────────────────

def ekle_kampanya(kampanya_adi, firma, baslangic, bitis, notlar="", kategori=""):
    r = get_client().table("kampanyalar").insert({
        "kampanya_adi": kampanya_adi, "firma": firma,
        "baslangic_tarihi": str(baslangic), "bitis_tarihi": str(bitis),
        "durum": "aktif", "notlar": notlar or "", "kategori": kategori or "",
        "olusturma_tarihi": get_today(),
    }).execute()
    return r.data[0]["id"] if r.data else None
    _cache_temizle()

@st.cache_data(ttl=300, show_spinner=False)
def get_kampanyalar(durum=None):
    sb = get_client()
    q = sb.table("kampanyalar").select("*").order("olusturma_tarihi", desc=True)
    if durum:
        q = q.eq("durum", durum)
    return _rows(q.execute())

@st.cache_data(ttl=300, show_spinner=False)
def get_kampanya(kampanya_id):
    return _row(get_client().table("kampanyalar").select("*").eq("id", kampanya_id).execute())

def guncelle_kampanya(kampanya_id, kampanya_adi, firma, baslangic, bitis, notlar):
    get_client().table("kampanyalar").update({
        "kampanya_adi": kampanya_adi, "firma": firma,
        "baslangic_tarihi": str(baslangic), "bitis_tarihi": str(bitis),
        "notlar": notlar or "",
    }).eq("id", kampanya_id).execute()
    _cache_temizle()

def kapat_kampanya(kampanya_id):
    get_client().table("kampanyalar").update({"durum": "kapali"}).eq("id", kampanya_id).execute()
    st.cache_data.clear()
    _cache_temizle()

def sil_kampanya(kampanya_id):
    sb = get_client()
    sb.table("kampanya_urunler").delete().eq("kampanya_id", kampanya_id).execute()
    sb.table("kampanyalar").delete().eq("id", kampanya_id).execute()
    _cache_temizle()

def ekle_kampanya_urun(kampanya_id, sku, urun_adi, pacal_maliyet, satis_fiyati,
                       birim_firma_destek, birim_ek_destek, notlar=""):
    get_client().table("kampanya_urunler").insert({
        "kampanya_id": kampanya_id, "sku": sku, "urun_adi": urun_adi or "",
        "pacal_maliyet": float(pacal_maliyet or 0),
        "satis_fiyati": float(satis_fiyati or 0),
        "birim_firma_destek": float(birim_firma_destek or 0),
        "birim_ek_destek": float(birim_ek_destek or 0),
        "satilan_adet": 0, "notlar": notlar or "",
    }).execute()
    _cache_temizle()

@st.cache_data(ttl=300, show_spinner=False)
def get_kampanya_urunler(kampanya_id):
    return _rows(get_client().table("kampanya_urunler").select("*").eq("kampanya_id", kampanya_id).order("id").execute())

@st.cache_data(ttl=300, show_spinner=False)
def get_tum_kampanya_urunler():
    """Tüm kampanya ürünlerini TEK sorguda döndürür (N+1 önleme)."""
    return _rows(get_client().table("kampanya_urunler").select("*").order("id").execute())

def guncelle_kampanya_urun(urun_id, satis_fiyati, birim_firma_destek, birim_ek_destek, satilan_adet, notlar=""):
    get_client().table("kampanya_urunler").update({
        "satis_fiyati": float(satis_fiyati or 0),
        "birim_firma_destek": float(birim_firma_destek or 0),
        "birim_ek_destek": float(birim_ek_destek or 0),
        "satilan_adet": int(satilan_adet or 0),
        "notlar": notlar or "",
    }).eq("id", urun_id).execute()
    st.cache_data.clear()
    _cache_temizle()

def sil_kampanya_urun(urun_id):
    get_client().table("kampanya_urunler").delete().eq("id", urun_id).execute()
    _cache_temizle()

# ── BİLDİRİM ────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)


# ── ANALİTİK ────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def get_gecmis_satis_firma_bazli(sku, firma):
    rows = _rows(get_client().table("firma_stok").select("haftalik_satis, yukleme_tarihi")
                .eq("sku", sku).eq("firma", firma)
                .order("yukleme_tarihi", desc=True).limit(8).execute())
    return [r.get("haftalik_satis", 0) or 0 for r in rows]

@st.cache_data(ttl=300, show_spinner=False)
def get_tum_gecmis_satislar():
    rows = _hepsi("firma_stok", "sku, haftalik_satis, yukleme_tarihi", "yukleme_tarihi")
    result = defaultdict(list)
    for r in rows:
        result[r["sku"]].append(r.get("haftalik_satis", 0) or 0)
    return dict(result)

@st.cache_data(ttl=300, show_spinner=False)
def get_gecmis_satis_tum_firmalar(sku):
    """Bir SKU için tüm firmaların geçmiş satış verilerini döndürür"""
    rows = _rows(get_client().table("firma_stok")
                .select("firma, haftalik_satis, stok_miktari, yukleme_tarihi")
                .eq("sku", sku)
                .order("yukleme_tarihi").execute())
    return rows

@st.cache_data(ttl=300, show_spinner=False)
def get_kampanya_destek_ortalamalari():
    """
    Tüm kampanyalardaki ürün bazında ortalama birim destek tutarlarını döndürür.
    Dönen dict: {sku: {'ort_firma_destek': float, 'ort_ek_destek': float, 'kampanya_sayisi': int}}
    """
    rows = _rows(get_client().table("kampanya_urunler").select(
        "sku, birim_firma_destek, birim_ek_destek"
    ).execute())
    
    from collections import defaultdict
    sku_data = defaultdict(list)
    for r in rows:
        sku_data[r["sku"]].append({
            "firma": float(r.get("birim_firma_destek") or 0),
            "ek": float(r.get("birim_ek_destek") or 0),
        })
    
    result = {}
    for sku, kayitlar in sku_data.items():
        if kayitlar:
            ort_firma = sum(k["firma"] for k in kayitlar) / len(kayitlar)
            ort_ek = sum(k["ek"] for k in kayitlar) / len(kayitlar)
            result[sku] = {
                "ort_firma_destek": round(ort_firma, 2),
                "ort_ek_destek": round(ort_ek, 2),
                "ort_toplam_destek": round(ort_firma + ort_ek, 2),
                "kampanya_sayisi": len(kayitlar),
            }
    return result



# ── TALEPLER ────────────────────────────────────────────────────────

def ekle_talep(gonderen, konu, mesaj):
    """Kullanicinin talebini talepler tablosuna kaydeder."""
    try:
        get_client().table("talepler").insert({
            "gonderen": gonderen or "",
            "konu": konu or "",
            "mesaj": mesaj or "",
            "durum": "bekliyor",
        }).execute()
        return True
    except Exception as e:
        return False

@st.cache_data(ttl=60, show_spinner=False)
def get_talepler():
    """Tum talepleri tarihe gore sirali getirir."""
    return _rows(get_client().table("talepler").select("*").order("olusturma_tarihi", desc=True).execute())

def guncelle_talep_cevap(talep_id, cevap, yeni_durum="tamamlandi"):
    """Talebin cevap alanini ve durumunu gunceller. Hata olursa yukari firlatir."""
    get_client().table("talepler").update({
        "cevap": cevap or "",
        "durum": yeni_durum,
    }).eq("id", talep_id).execute()
    _cache_temizle()
    return True
