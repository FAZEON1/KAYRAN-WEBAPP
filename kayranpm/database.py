"""
KAYRAN — Veritabanı Katmanı (Supabase PostgreSQL)
"""
import streamlit as st
# Türkiye saat dilimi için ortak yardımcılar
from shared.utils import tr_today, tr_now, tr_today_iso, tr_now_str, tr_tomorrow, tr_yesterday as _tr_today_iso_dummy
from shared.utils import tr_kucuk
from supabase import create_client, Client
from datetime import date
from collections import defaultdict


@st.cache_resource
def get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    # service_role_key varsa onu kullan (RLS aşılır, sunucuda kalır); yoksa anon key.
    key = st.secrets["supabase"].get("service_role_key") or st.secrets["supabase"]["key"]
    from shared.audit import wrap_client
    return wrap_client(create_client(url, key), "Ürün Yönetimi")


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
        "sku": sku, "urun_adi": urun_adi, "kategori": tr_kucuk(kategori),
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
    """Tüm kategori yazımlarını tek biçime indirger: Türkçe-doğru KÜÇÜK HARF.
    'KASA'/'Kasa' → 'kasa', 'MONİTÖR'/'Monitör' → 'monitör' (büyük/küçük farkı birleşir).
    (degisen_urun_sayisi, {eski: yeni}) döner."""
    sb = get_client()
    rows = sb.table("urunler").select("sku, kategori").execute().data or []
    sku_yeni, degisim = {}, {}
    for r in rows:
        eski = (r.get("kategori") or "").strip()
        if not eski:
            continue
        yeni = tr_kucuk(eski)
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

def upsert_g5f_stok(sku, urun_adi, bizim_stok_satilabilir, depo_kirilim):
    """G5F (bizim depo) çok-depolu stok günceller.
    bizim_stok = satılabilir depolar toplamı (sipariş önerisi bunu kullanır).
    depo_kirilim = {depo_adi: miktar} — TÜM depolar (gösterim/genel toplam için).
    Mevcut ürünün fiyat/kategori/marka/hedef kâr bilgilerine DOKUNMAZ."""
    sb = get_client()
    bugun = get_today()
    mevcut = _row(sb.table("urunler").select("urun_adi, ilk_giris_tarihi").eq("sku", sku).execute())
    if mevcut:
        _payload = {"bizim_stok": int(bizim_stok_satilabilir or 0),
                    "depo_kirilim": depo_kirilim or {}, "guncelleme_tarihi": bugun}
        if not str(mevcut.get("urun_adi") or "").strip() and urun_adi:
            _payload["urun_adi"] = urun_adi
        try:
            sb.table("urunler").update(_payload).eq("sku", sku).execute()
        except Exception:
            _payload.pop("depo_kirilim", None)
            sb.table("urunler").update(_payload).eq("sku", sku).execute()
    else:
        _payload = {"sku": sku, "urun_adi": urun_adi or "", "kategori": "", "marka": "",
                    "satis_fiyati": 0, "alis_fiyati": 0, "hedef_kar_marji": 0, "ozellikler": "",
                    "bizim_stok": int(bizim_stok_satilabilir or 0), "trendyol_stok": 0,
                    "depo_kirilim": depo_kirilim or {},
                    "ilk_giris_tarihi": bugun, "guncelleme_tarihi": bugun}
        try:
            sb.table("urunler").insert(_payload).execute()
        except Exception:
            _payload.pop("depo_kirilim", None)
            sb.table("urunler").insert(_payload).execute()
    try:
        sb.table("stok_yas").upsert({"sku": sku, "ilk_gorulen_tarih": bugun}, on_conflict="sku").execute()
    except Exception:
        pass
    _cache_temizle()


def get_firma_listesi():
    """firma_stok'taki benzersiz müşteri/firma adları (alfabetik)."""
    rows = _hepsi("firma_stok", "firma", "yukleme_tarihi")
    return sorted({(r.get("firma") or "").strip() for r in rows if (r.get("firma") or "").strip()})


# ── SKU TEMİZLEME · 'Fazeon' önekli kodları öneksiz kodla birleştir ──────────
_SKU_TABLOLARI = ["urunler", "satislar", "firma_stok", "kampanya_urunler",
                  "yoldaki_urunler", "stok_yas", "ithalat_kalemleri", "siparis_onerileri"]


def _fazeon_hedef(sku):
    """SKU 'Fazeon ' (her büyük/küçük varyant) ile başlıyorsa öneksiz + BÜYÜK harf hedefi döndürür.
    Değilse None. Örn: 'Fazeon X24F165S' → 'X24F165S'."""
    s = str(sku or "").strip()
    for p in ("FAZEON ", "Fazeon ", "fazeon "):
        if s.startswith(p) and len(s) > len(p):
            return s[len(p):].strip().upper()
    return None


def sku_fazeon_temizle_onizle():
    """Tüm tablolardaki 'Fazeon ' önekli SKU'ları, öneksiz hedeflerini, çakışmaları
    (hedef kod zaten var mı → birleşecek) ve etkilenen kayıt sayılarını döndürür.
    HİÇBİR ŞEY YAZMAZ — güvenli önizleme. Döner: list[{eski, yeni, catisma, toplam_kayit, tablolar}]."""
    try:
        urun_skular = {str(r.get("sku") or "").strip() for r in _hepsi("urunler", "sku", "sku")}
    except Exception:
        urun_skular = set()

    bulgular = {}  # eski_sku → {yeni, tablolar:{tablo:adet}}
    for tablo in _SKU_TABLOLARI:
        try:
            rows = _hepsi(tablo, "sku", "sku")
        except Exception:
            continue
        for r in rows:
            esku = str(r.get("sku") or "").strip()
            hedef = _fazeon_hedef(esku)
            if not hedef:
                continue
            b = bulgular.setdefault(esku, {"yeni": hedef, "tablolar": {}})
            b["tablolar"][tablo] = b["tablolar"].get(tablo, 0) + 1

    out = []
    for esku, b in sorted(bulgular.items()):
        out.append({
            "eski": esku, "yeni": b["yeni"],
            "catisma": (b["yeni"] in urun_skular),
            "tablolar": b["tablolar"],
            "toplam_kayit": sum(b["tablolar"].values()),
        })
    return out


def sku_fazeon_temizle_uygula():
    """'Fazeon ' önekli SKU'ları öneksiz hedeflerine taşır:
    - urunler DIŞI tablolar: sku alanı UPDATE (eski → yeni).
    - urunler: hedef kod zaten varsa kaynak (Fazeon) kayıt SİLİNİR (hedef korunur); yoksa yeniden adlandırılır.
    Geri alınamaz. Döner: (ok, mesaj)."""
    sb = get_client()
    onizle = sku_fazeon_temizle_onizle()
    if not onizle:
        return True, "Temizlenecek 'Fazeon' önekli SKU bulunamadı — sistem zaten temiz."
    try:
        urun_skular = {str(r.get("sku") or "").strip() for r in _hepsi("urunler", "sku", "sku")}
    except Exception:
        urun_skular = set()

    guncellenen_kayit = rename = birlesti = 0
    hatalar = []
    for it in onizle:
        esku, yeni = it["eski"], it["yeni"]
        for tablo in _SKU_TABLOLARI:
            if tablo == "urunler":
                continue
            try:
                sb.table(tablo).update({"sku": yeni}).eq("sku", esku).execute()
                guncellenen_kayit += it["tablolar"].get(tablo, 0)
            except Exception as e:
                hatalar.append(f"{tablo}/{esku}: {str(e)[:50]}")
        try:
            if yeni in urun_skular and yeni != esku:
                sb.table("urunler").delete().eq("sku", esku).execute()
                birlesti += 1
            else:
                sb.table("urunler").update({"sku": yeni}).eq("sku", esku).execute()
                urun_skular.add(yeni)
                rename += 1
        except Exception as e:
            hatalar.append(f"urunler/{esku}: {str(e)[:50]}")
    _cache_temizle()

    mesaj = (f"✅ {len(onizle)} 'Fazeon' SKU temizlendi — {rename} yeniden adlandırıldı, "
             f"{birlesti} mevcut kodla birleştirildi. Diğer tablolarda ~{guncellenen_kayit} kayıt güncellendi.")
    if hatalar:
        mesaj += f" | ⚠️ {len(hatalar)} sorun: " + "; ".join(hatalar[:3])
    return True, mesaj


def get_musteri_haftalik_satis(bas=None, bit=None, firma=None, sku_ara=None):
    """firma_stok'tan haftalık satış kayıtları — tarih aralığı + müşteri + SKU/ürün filtreli (sayfalı).
    Döner: [{firma, sku, urun_adi, haftalik_satis, stok_miktari, yukleme_tarihi}]."""
    sb = get_client()
    bas_s = str(bas)[:10] if bas else None
    bit_s = str(bit)[:10] if bit else None
    out, i, adim = [], 0, 1000
    while True:
        q = sb.table("firma_stok").select(
            "firma, sku, urun_adi, haftalik_satis, stok_miktari, yukleme_tarihi")
        if bas_s:
            q = q.gte("yukleme_tarihi", bas_s)
        if bit_s:
            q = q.lte("yukleme_tarihi", bit_s)
        if firma and firma != "Tümü":
            q = q.eq("firma", firma)
        q = q.order("yukleme_tarihi", desc=True).range(i, i + adim - 1)
        chunk = _rows(q.execute())
        out.extend(chunk)
        if len(chunk) < adim:
            break
        i += adim
        if i > 60000:
            break
    if sku_ara and sku_ara.strip():
        s = sku_ara.strip().lower()
        out = [r for r in out
               if s in str(r.get("sku", "")).lower() or s in str(r.get("urun_adi", "")).lower()]
    return out


def upsert_firma_stok(firma, sku, urun_adi, stok_miktari, haftalik_satis,
                      stok_magaza=0, satis_magaza=0):
    _kayit = {
        "firma": firma, "sku": sku, "urun_adi": urun_adi or "",
        "stok_miktari": int(stok_miktari or 0),
        "haftalik_satis": int(haftalik_satis or 0),
        "stok_magaza": int(stok_magaza or 0),
        "satis_magaza": int(satis_magaza or 0),
        "yukleme_tarihi": get_today(),
    }
    try:
        get_client().table("firma_stok").upsert(
            _kayit, on_conflict="firma,sku,yukleme_tarihi").execute()
    except Exception:
        # stok_magaza / satis_magaza kolonları tabloda yoksa onlarsız tekrar dene
        for _k in ("stok_magaza", "satis_magaza"):
            _kayit.pop(_k, None)
        get_client().table("firma_stok").upsert(
            _kayit, on_conflict="firma,sku,yukleme_tarihi").execute()
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

def ekle_kampanya(kampanya_adi, firma, baslangic, bitis, notlar="", kategori="",
                  kampanya_turu="", spiff_tl=0, spiff_kur=0, spiff_fatura=False):
    sb = get_client()
    payload = {
        "kampanya_adi": kampanya_adi, "firma": firma,
        "baslangic_tarihi": str(baslangic), "bitis_tarihi": str(bitis),
        "durum": "aktif", "notlar": notlar or "", "kategori": kategori or "",
        "kampanya_turu": kampanya_turu or "",
        "spiff_tl": float(spiff_tl or 0), "spiff_kur": float(spiff_kur or 0),
        "spiff_fatura": bool(spiff_fatura),
        "olusturma_tarihi": get_today(),
    }
    try:
        r = sb.table("kampanyalar").insert(payload).execute()
    except Exception:
        for _k in ("kampanya_turu", "spiff_tl", "spiff_kur", "spiff_fatura", "kategori"):
            payload.pop(_k, None)
        r = sb.table("kampanyalar").insert(payload).execute()
    _cache_temizle()
    return r.data[0]["id"] if r.data else None

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

def guncelle_kampanya(kampanya_id, kampanya_adi, firma, baslangic, bitis, notlar, kategori=None,
                      kampanya_turu=None, spiff_tl=None, spiff_kur=None, spiff_fatura=None):
    sb = get_client()
    payload = {
        "kampanya_adi": kampanya_adi, "firma": firma,
        "baslangic_tarihi": str(baslangic), "bitis_tarihi": str(bitis),
        "notlar": notlar or "",
    }
    if kategori is not None:
        payload["kategori"] = kategori
    if kampanya_turu is not None:
        payload["kampanya_turu"] = kampanya_turu
    if spiff_tl is not None:
        payload["spiff_tl"] = float(spiff_tl or 0)
    if spiff_kur is not None:
        payload["spiff_kur"] = float(spiff_kur or 0)
    if spiff_fatura is not None:
        payload["spiff_fatura"] = bool(spiff_fatura)
    try:
        sb.table("kampanyalar").update(payload).eq("id", kampanya_id).execute()
    except Exception:
        for _k in ("kategori", "kampanya_turu", "spiff_tl", "spiff_kur", "spiff_fatura"):
            payload.pop(_k, None)
        sb.table("kampanyalar").update(payload).eq("id", kampanya_id).execute()
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


def canli_stok(sku):
    """Tam canlı (perpetual) stok hesabı — fiziksel kayıt DEĞİŞTİRİLMEZ, her çağrıda hesaplanır.
        canlı = başlangıç snapshot + (baz tarihten sonra 'Teslim Alındı' ithalat) − (baz tarihten sonraki satış)
    Bu yöntem satış silme/düzeltmeye dayanıklıdır (stok otomatik doğru kalır).
    Dönen: {var, baz, baz_tarih, giris, cikis, canli}"""
    sb = get_client()
    sku_n = (sku or "").strip()
    if not sku_n:
        return {"var": False, "baz": 0, "baz_tarih": None, "giris": 0, "cikis": 0, "canli": 0}

    # 1) Başlangıç: SKU'nun her firmadaki EN SON snapshot'ını topla
    rows = _rows(sb.table("firma_stok").select("stok_miktari,yukleme_tarihi,firma")
                 .eq("sku", sku_n).execute())
    if not rows:
        return {"var": False, "baz": 0, "baz_tarih": None, "giris": 0, "cikis": 0, "canli": 0}
    firma_son = {}
    for r in rows:
        f = r.get("firma") or "—"
        t = str(r.get("yukleme_tarihi") or "")[:10]
        if (f not in firma_son) or (t > firma_son[f][0]):
            firma_son[f] = (t, float(r.get("stok_miktari") or 0))
    baz = sum(v[1] for v in firma_son.values())
    baz_tarih = max((v[0] for v in firma_son.values()), default=None)

    # 2) Giriş: baz tarihten SONRA "Teslim Alındı" olan ithalat adetleri
    giris = 0.0
    try:
        from ithalat.database import get_sku_alim_detay
        for p in (get_sku_alim_detay(sku_n) or []):
            tt = str(p.get("teslim_tarih") or "")[:10]
            if str(p.get("durum") or "").strip() == "Teslim Alındı" and baz_tarih and tt and tt > baz_tarih:
                giris += float(p.get("adet") or 0)
    except Exception:
        pass

    # 3) Çıkış: baz tarihten SONRAKİ satışlar
    cikis = 0.0
    try:
        sat = _rows(sb.table("satislar").select("adet,tarih").eq("sku", sku_n).execute())
        for s in sat:
            st = str(s.get("tarih") or "")[:10]
            if baz_tarih and st and st > baz_tarih:
                cikis += float(s.get("adet") or 0)
    except Exception:
        pass

    # 4) İade: baz tarihten SONRAKİ iadeler stoğa GERİ döner (net çıkış = satış − iade)
    iade_geri = 0.0
    try:
        iad = _rows(sb.table("iadeler").select("iade_adet,tarih").eq("sku", sku_n).execute())
        for r in iad:
            it = str(r.get("tarih") or "")[:10]
            if baz_tarih and it and it > baz_tarih:
                iade_geri += float(r.get("iade_adet") or 0)
    except Exception:
        pass

    return {"var": True, "baz": baz, "baz_tarih": baz_tarih,
            "giris": giris, "cikis": cikis, "iade": iade_geri,
            "canli": baz + giris - cikis + iade_geri}


# ── DEPO YÖNETİMİ · depo bazlı stok + depolar arası sevk ─────────────────────
# bizim_stok = satılabilir depoların (Merkez + Happy Life) toplamı; sevk sonrası
# yeniden hesaplanır. depo_kirilim {depo: adet} canlı güncellenir.
_SATILABILIR_DEPOLAR = {"MERKEZ DEPO", "HAPPY LIFE"}


def _depo_norm(s):
    return (str(s or "").strip().upper()
            .replace("İ", "I").replace("Ş", "S").replace("Ğ", "G")
            .replace("Ü", "U").replace("Ö", "O").replace("Ç", "C"))


# Bilinen depoların KANONİK yazımı — her yazım varyasyonu buraya toplanır.
# (normalize edilmiş anahtar → ekranda görünecek standart ad)
_DEPO_KANONIK = {
    "MERKEZ DEPO": "MERKEZ DEPO", "MERKEZDEPO": "MERKEZ DEPO", "MERKEZ": "MERKEZ DEPO",
    "HAPPY LIFE": "HAPPY LIFE", "HAPPYLIFE": "HAPPY LIFE", "HAPPY": "HAPPY LIFE",
    "ASEL DEPO": "ASEL DEPO", "ASELDEPO": "ASEL DEPO", "ASEL": "ASEL DEPO",
    "TEKNIK DEPO": "TEKNİK DEPO", "TEKNIKDEPO": "TEKNİK DEPO", "TEKNIK": "TEKNİK DEPO",
}


def depo_kanonik(s):
    """Depo adını standart yazıma çevirir: 'happy life' / 'HAPPYLIFE' / 'Happy Life' → 'HAPPY LIFE'.
    Bilinmeyen depolar boşluk sadeleştirilip BÜYÜK harfe çevrilerek döner (yine tutarlı olur)."""
    n = _depo_norm(s)
    n = " ".join(n.split())  # çoklu boşlukları teke indir
    if n in _DEPO_KANONIK:
        return _DEPO_KANONIK[n]
    n2 = n.replace(" ", "")
    if n2 in _DEPO_KANONIK:
        return _DEPO_KANONIK[n2]
    return n  # bilinmeyen depo: en azından BÜYÜK/tek-boşluk normalize


def _kirilim_kanonik(depo_kirilim):
    """Bir depo_kirilim sözlüğündeki tüm depo adlarını kanonikleştirir, aynı depoları TOPLAR."""
    out = {}
    for d, m in (depo_kirilim or {}).items():
        k = depo_kanonik(d)
        try:
            out[k] = out.get(k, 0) + int(float(m or 0))
        except Exception:
            out[k] = out.get(k, 0)
    return out


def _bizim_stok_hesapla(depo_kirilim):
    """Satılabilir depoların (Merkez + Happy Life) toplamı."""
    return int(sum(int(m or 0) for d, m in (depo_kirilim or {}).items()
                   if _depo_norm(d) in _SATILABILIR_DEPOLAR))


def _sevk_uygula(depo_kirilim, kaynak, hedef, adet):
    """SAF hesap: kaynak depodan hedefe 'adet' taşır. Yazmaz.
    Kaynak/hedef ve kırılım kanonikleştirilir (yazım farkı sorun olmaz).
    Döner: (yeni_kirilim | None, hata_mesaji)."""
    dk = _kirilim_kanonik(depo_kirilim or {})
    kaynak = depo_kanonik(kaynak)
    hedef = depo_kanonik(hedef)
    adet = int(adet or 0)
    if adet <= 0:
        return None, "Adet 0'dan büyük olmalı."
    if not str(kaynak).strip() or not str(hedef).strip():
        return None, "Kaynak ve hedef depo seçilmeli."
    if kaynak == hedef:
        return None, "Kaynak ve hedef depo aynı olamaz."
    mevcut = int(dk.get(kaynak, 0) or 0)
    if mevcut < adet:
        return None, f"Yetersiz stok: '{kaynak}' deposunda {mevcut} adet var, {adet} taşınamaz."
    dk[kaynak] = mevcut - adet
    dk[hedef] = int(dk.get(hedef, 0) or 0) + adet
    return dk, ""


def get_depo_listesi():
    """Tüm ürünlerin depo_kirilim'inde geçen benzersiz KANONİK depo adları (alfabetik).
    Ayrıca teslim alınmış ithalat dosyalarının teslim depolarını da dahil eder."""
    depolar = set()
    for u in _hepsi("urunler", "depo_kirilim"):
        dk = u.get("depo_kirilim") or {}
        if isinstance(dk, dict):
            for d in dk.keys():
                if str(d).strip():
                    depolar.add(depo_kanonik(d))
    try:
        from ithalat.database import get_dosyalar as _ith_dosyalar
        for d in (_ith_dosyalar() or []):
            if str(d.get("durum") or "").strip() == "Teslim Alındı":
                _td = (d.get("teslim_deposu") or "").strip()
                if _td:
                    depolar.add(depo_kanonik(_td))
    except Exception:
        pass
    return sorted(depolar)


def get_depo_ozet():
    """Her depo için {depo, cesit, toplam_adet, satilabilir} (adet>0 olanlar), KANONİK adlarla."""
    sayac = {}
    for u in _hepsi("urunler", "depo_kirilim"):
        dk = _kirilim_kanonik(u.get("depo_kirilim") or {})
        for d, m in dk.items():
            m = int(m or 0)
            if m <= 0:
                continue
            sayac.setdefault(d, [0, 0])
            sayac[d][0] += 1
            sayac[d][1] += m
    return [{"depo": d, "cesit": v[0], "toplam_adet": v[1],
             "satilabilir": _depo_norm(d) in _SATILABILIR_DEPOLAR}
            for d, v in sorted(sayac.items())]


def get_depo_stok(depo):
    """Belirli depodaki ürünler [{sku, urun_adi, adet}] (adet>0), adet azalan sıralı.
    Kaynak: ürün kartındaki depo_kirilim. Eğer bir ürünün kırılımı boşsa ama o depoya
    TESLİM ALINMIŞ ithalat dosyası varsa, teslim adedi de dahil edilir (böylece satın
    alınıp teslim edilen modeller depo_kirilim güncel olmasa bile sevk listesinde çıkar)."""
    depo = depo_kanonik(depo)
    stok = {}   # sku -> adet
    adlar = {}  # sku -> urun_adi
    for u in _hepsi("urunler", "sku, urun_adi, depo_kirilim"):
        sku = str(u.get("sku") or "").strip()
        if not sku:
            continue
        adlar[sku] = u.get("urun_adi", "") or ""
        dk = _kirilim_kanonik(u.get("depo_kirilim") or {})
        m = int(dk.get(depo, 0) or 0)
        if m != 0:
            stok[sku] = m

    # depo_kirilim'i olan SKU'lar dışında, bu depoya teslim edilmiş ithalat kalemlerini ekle
    try:
        from ithalat.database import get_dosyalar as _ith_dosyalar, get_kalemler as _ith_kalemler
        for d in (_ith_dosyalar() or []):
            if str(d.get("durum") or "").strip() != "Teslim Alındı":
                continue
            if depo_kanonik(d.get("teslim_deposu") or "") != depo:
                continue
            for k in (_ith_kalemler(d["id"]) or []):
                sku = str(k.get("sku") or "").strip()
                try:
                    adet = int(float(k.get("adet") or 0))
                except Exception:
                    adet = 0
                if not sku or adet <= 0:
                    continue
                # depo_kirilim'de zaten varsa ONU kullan (çift sayma); yoksa teslimden ekle
                if sku not in stok:
                    stok[sku] = stok.get(sku, 0) + adet
                    if not adlar.get(sku):
                        adlar[sku] = str(k.get("urun_adi") or "")
    except Exception:
        pass

    out = [{"sku": s, "urun_adi": adlar.get(s, ""), "adet": a}
           for s, a in stok.items() if a > 0]
    return sorted(out, key=lambda x: -x["adet"])


def depo_sevk(sku, kaynak_depo, hedef_depo, adet, kullanici="", sevk_tarihi="", belge_no=""):
    """Depolar arası sevk: kaynak→hedef 'adet' taşır, bizim_stok'u yeniden
    hesaplar, kalıcı yazar, geçmişe + audit'e ekler. Döner: (ok, mesaj).
    sevk_tarihi/belge_no: sevk loguna yazılır (kolonlar yoksa otomatik atlanır)."""
    try:
        sb = get_client()
        u = _row(sb.table("urunler").select("sku, urun_adi, depo_kirilim").eq("sku", sku).execute())
        if not u:
            return False, f"❌ Ürün bulunamadı: {sku}"
        dk = u.get("depo_kirilim") or {}
        if not isinstance(dk, dict):
            return False, "❌ Bu ürünün depo kırılımı yok (önce G5F stok yükleyin)."
        yeni_dk, hata = _sevk_uygula(dk, kaynak_depo, hedef_depo, adet)
        if hata:
            return False, f"❌ {hata}"
        sb.table("urunler").update({
            "depo_kirilim": yeni_dk,
            "bizim_stok": _bizim_stok_hesapla(yeni_dk),
            "guncelleme_tarihi": get_today(),
        }).eq("sku", sku).execute()
        _log = {
            "sku": sku, "urun_adi": u.get("urun_adi", ""),
            "kaynak_depo": kaynak_depo, "hedef_depo": hedef_depo,
            "adet": int(adet), "kullanici": kullanici or "", "tarih": tr_now_str(),
        }
        try:
            _log2 = dict(_log)
            if str(sevk_tarihi or "").strip():
                _log2["sevk_tarihi"] = str(sevk_tarihi)[:10]
            if str(belge_no or "").strip():
                _log2["belge_no"] = str(belge_no).strip()[:60]
            try:
                sb.table("depo_sevk_log").insert(_log2).execute()
            except Exception:
                # sevk_tarihi/belge_no kolonları tabloda yoksa temel logla devam et
                sb.table("depo_sevk_log").insert(_log).execute()
        except Exception:
            pass
        try:
            from shared.audit import log_yaz
            _ek = (f" · belge:{belge_no}" if str(belge_no or "").strip() else "")
            log_yaz("depo_sevk", "urunler", sku,
                    f"{adet} adet {kaynak_depo} → {hedef_depo}{_ek}", "kayranpm")
        except Exception:
            pass
        _cache_temizle()
        return True, f"✅ {adet} adet '{sku}': {kaynak_depo} → {hedef_depo}"
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}"


def get_depo_sevk_gecmisi(limit=50):
    """Son sevkler (depo_sevk_log). Tablo yoksa boş liste döner."""
    try:
        r = (get_client().table("depo_sevk_log").select("*")
             .order("id", desc=True).limit(limit).execute())
        return _rows(r)
    except Exception:
        return []


# ═══════════ MODEL B — HAREKET BAZLI STOK ÇEKİRDEĞİ ═══════════
def stok_hareket_coklu(hareketler, depo=None, kart_ac=False, kart_adlar=None):
    """MODEL B: {sku: delta} hareketlerini urunler.depo_kirilim'e uygular.
    delta + → giriş, − → çıkış. depo verilmezse 'MERKEZ DEPO'.
    kart_ac=True: ürün kartı olmayan SKU için otomatik boş kart açılır (adı kart_adlar[sku]).
    Ürün kartı yoksa ve kart_ac=False → SKU atlanır. Döner: (uygulanan, atlanan)."""
    depo = depo_kanonik((depo or "").strip() or "MERKEZ DEPO")
    kart_adlar = kart_adlar or {}
    uygulanan, atlanan = 0, []
    try:
        sb = get_client()
    except Exception:
        return 0, list(hareketler or {})
    for sku, delta in (hareketler or {}).items():
        sku = str(sku or "").strip()
        try:
            delta = float(delta or 0)
        except Exception:
            delta = 0
        if not sku or delta == 0:
            continue
        try:
            u = _row(sb.table("urunler").select("sku, depo_kirilim").eq("sku", sku).execute())
            if not u and sku != sku.upper():
                u = _row(sb.table("urunler").select("sku, depo_kirilim").eq("sku", sku.upper()).execute())
            if not u:
                if kart_ac:
                    # Otomatik boş kart aç (fiyat/paçal 0, sadece stok tutulur)
                    try:
                        sb.table("urunler").insert({
                            "sku": sku, "urun_adi": (kart_adlar.get(sku) or "")[:200],
                            "depo_kirilim": {}, "bizim_stok": 0,
                        }).execute()
                        u = {"sku": sku, "depo_kirilim": {}}
                    except Exception:
                        atlanan.append(sku)
                        continue
                else:
                    atlanan.append(sku)
                    continue
            dk = u.get("depo_kirilim") or {}
            if not isinstance(dk, dict):
                dk = {}
            dk[depo] = float(dk.get(depo, 0) or 0) + delta
            if abs(dk[depo]) < 1e-9:
                dk[depo] = 0
            sb.table("urunler").update({
                "depo_kirilim": dk,
                "bizim_stok": _bizim_stok_hesapla(dk),
                "guncelleme_tarihi": get_today(),
            }).eq("sku", u["sku"]).execute()
            uygulanan += 1
        except Exception:
            atlanan.append(sku)
    _cache_temizle()
    return uygulanan, atlanan


def stok_hareket(sku, delta, depo=None):
    """Tek SKU için hareket (bkz. stok_hareket_coklu)."""
    return stok_hareket_coklu({sku: delta}, depo)


# ═══════════ MÜKERRER SKU BİRLEŞTİRME (büyük/küçük harf farkı) ═══════════
def _ad_norm(s):
    """Ürün adını karşılaştırma için sadeleştirir: boşluk/harf/Türkçe farkını yok sayar."""
    s = _depo_norm(s)  # büyük harf + Türkçe sadeleştirme
    return " ".join(s.split())  # çoklu boşlukları teke indir


def mukerrer_sku_bul(ada_gore=False):
    """Mükerrer ürün kartlarını bulur.
    ada_gore=False: yalnız SKU'nun büyük/küçük harf farkı ('Mio1' vs 'MIO1').
    ada_gore=True : ek olarak ÜRÜN ADI aynı olan farklı SKU'ları da grup sayar
                    ('Mio MiVue 802' / 'MIO MIVUE 802' gibi).
    Döner: [{"kanonik", "kartlar":[...], "tur": "sku"|"ad"}]."""
    kartlar_all = []
    for u in _hepsi("urunler", "sku, urun_adi, kategori, marka, barkod, fiyat, pacal_maliyet, "
                              "hedef_kar, bizim_stok, depo_kirilim"):
        if str(u.get("sku") or "").strip():
            kartlar_all.append(u)

    out, kullanildi = [], set()

    # 1) SKU harf-farkı grupları
    by_sku = {}
    for u in kartlar_all:
        by_sku.setdefault(str(u["sku"]).strip().upper(), []).append(u)
    for anahtar, kartlar in by_sku.items():
        if len(kartlar) > 1:
            out.append({"kanonik": anahtar, "kartlar": kartlar, "tur": "sku"})
            for k in kartlar:
                kullanildi.add(str(k["sku"]))

    # 2) (opsiyonel) Ürün adı aynı, SKU farklı grupları
    if ada_gore:
        by_ad = {}
        for u in kartlar_all:
            if str(u["sku"]) in kullanildi:
                continue
            ad = _ad_norm(u.get("urun_adi"))
            if ad:
                by_ad.setdefault(ad, []).append(u)
        for ad, kartlar in by_ad.items():
            if len(kartlar) > 1:
                out.append({"kanonik": (kartlar[0].get("urun_adi") or ad),
                            "kartlar": kartlar, "tur": "ad"})
    return sorted(out, key=lambda g: str(g["kanonik"]))


def _kart_dolu_skor(k):
    """Bir kartın 'ne kadar dolu' olduğunu puanlar (birleştirmede ana kartı seçmek için)."""
    s = 0
    for alan in ("urun_adi", "kategori", "marka", "barkod"):
        if str(k.get(alan) or "").strip():
            s += 1
    for alan in ("fiyat", "pacal_maliyet", "hedef_kar", "bizim_stok"):
        try:
            if float(k.get(alan) or 0) != 0:
                s += 1
        except Exception:
            pass
    dk = k.get("depo_kirilim") or {}
    if isinstance(dk, dict):
        s += sum(1 for v in dk.values() if int(v or 0) != 0)
    return s


def mukerrer_sku_birlestir(kanonik_uppercase=None):
    """Büyük/küçük harf farkıyla mükerrer kartları TEK karta birleştirir.
    - Ana kart: en dolu olan (fiyat/kategori/depo_kirilim vb.). SKU'su BÜYÜK harfe çevrilir.
    - depo_kirilim'ler kanonikleştirilip TOPLANIR (stok kaybı olmaz).
    - Boş alanlar diğer karttan tamamlanır; dolu alanlara dokunulmaz.
    - Fazla kart(lar) silinir.
    kanonik_uppercase verilirse yalnız o grup; yoksa TÜM mükerrer gruplar işlenir.
    Döner: (birlesen_grup, silinen_kart, mesajlar[list])."""
    sb = get_client()
    gruplar = mukerrer_sku_bul()
    if kanonik_uppercase:
        gruplar = [g for g in gruplar if g["kanonik"] == str(kanonik_uppercase).upper()]
    birlesen, silinen, mesajlar = 0, 0, []
    for g in gruplar:
        kartlar = sorted(g["kartlar"], key=_kart_dolu_skor, reverse=True)
        ana = kartlar[0]
        digerleri = kartlar[1:]
        hedef_sku = str(ana.get("sku") or "").strip().upper()

        # depo_kirilim'leri kanonikleştirip TOPLA
        birlesik_dk = _kirilim_kanonik(ana.get("depo_kirilim") or {})
        payload = {}
        for d in digerleri:
            for k2, v2 in _kirilim_kanonik(d.get("depo_kirilim") or {}).items():
                birlesik_dk[k2] = birlesik_dk.get(k2, 0) + int(v2 or 0)
            # Ana kartta boş olan alanları diğerinden doldur
            for alan in ("urun_adi", "kategori", "marka", "barkod"):
                if not str(ana.get(alan) or "").strip() and str(d.get(alan) or "").strip():
                    payload[alan] = d.get(alan)
                    ana[alan] = d.get(alan)
            for alan in ("fiyat", "pacal_maliyet", "hedef_kar"):
                try:
                    if float(ana.get(alan) or 0) == 0 and float(d.get(alan) or 0) != 0:
                        payload[alan] = d.get(alan)
                        ana[alan] = d.get(alan)
                except Exception:
                    pass

        payload["depo_kirilim"] = birlesik_dk
        payload["bizim_stok"] = _bizim_stok_hesapla(birlesik_dk)
        payload["guncelleme_tarihi"] = get_today()

        # Ana kartın SKU'su küçük harfliyse BÜYÜK'e taşı (kanonik). Supabase PK sku ise:
        try:
            if str(ana.get("sku")) != hedef_sku:
                # Önce diğerlerini sil (çakışma olmasın), sonra ana kartı BÜYÜK SKU'ya çevir
                for d in digerleri:
                    if str(d.get("sku")).upper() == hedef_sku and str(d.get("sku")) != hedef_sku:
                        continue  # aynı upper — birazdan silinecek
                # Diğer kartları sil
                for d in digerleri:
                    sb.table("urunler").delete().eq("sku", d.get("sku")).execute()
                    silinen += 1
                # Ana kartı büyük SKU ile yeniden yaz (eski küçük kaydı sil, yeni ekle)
                _ana_full = {k: ana.get(k) for k in ("urun_adi", "kategori", "marka", "barkod",
                                                     "fiyat", "pacal_maliyet", "hedef_kar",
                                                     "ilk_giris_tarihi") if ana.get(k) is not None}
                _ana_full.update(payload)
                _ana_full["sku"] = hedef_sku
                sb.table("urunler").delete().eq("sku", ana.get("sku")).execute()
                try:
                    sb.table("urunler").insert(_ana_full).execute()
                except Exception:
                    _ana_full.pop("hedef_kar", None)
                    sb.table("urunler").insert(_ana_full).execute()
            else:
                # Ana SKU zaten büyük — sadece güncelle + diğerlerini sil
                sb.table("urunler").update(payload).eq("sku", ana.get("sku")).execute()
                for d in digerleri:
                    sb.table("urunler").delete().eq("sku", d.get("sku")).execute()
                    silinen += 1
            birlesen += 1
            _tekil = int(sum(birlesik_dk.values()))
            mesajlar.append(f"✅ {hedef_sku}: {len(kartlar)} kart → 1 (toplam depo stoğu {_tekil})")
        except Exception as e:
            mesajlar.append(f"❌ {hedef_sku}: birleştirilemedi — {type(e).__name__}: {str(e)[:90]}")
    _cache_temizle()
    return birlesen, silinen, mesajlar
