"""
KAYRANPM — Veritabanı Katmanı (Supabase PostgreSQL)
"""
import streamlit as st
from supabase import create_client, Client
from datetime import date
from collections import defaultdict

def get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

def get_today():
    return date.today().isoformat()

def initialize_db():
    pass

def _rows(response):
    return response.data if response.data else []

def _row(response):
    d = response.data
    return d[0] if d else None

# ── ÜRÜNLER ─────────────────────────────────────────────────────────

def upsert_urun(sku, urun_adi, kategori="", marka="", satis_fiyati=0.0,
                alis_fiyati=0.0, hedef_kar_marji=0.0, ozellikler="",
                bizim_stok=0, trendyol_stok=0):
    sb = get_client()
    bugun = get_today()
    mevcut = _row(sb.table("urunler").select("ilk_giris_tarihi").eq("sku", sku).execute())
    ilk_tarih = mevcut["ilk_giris_tarihi"] if mevcut and mevcut.get("ilk_giris_tarihi") else bugun
    sb.table("urunler").upsert({
        "sku": sku, "urun_adi": urun_adi, "kategori": kategori or "",
        "marka": marka or "", "satis_fiyati": float(satis_fiyati or 0),
        "alis_fiyati": float(alis_fiyati or 0),
        "hedef_kar_marji": float(hedef_kar_marji or 0),
        "ozellikler": ozellikler or "",
        "bizim_stok": int(bizim_stok or 0),
        "trendyol_stok": int(trendyol_stok or 0),
        "ilk_giris_tarihi": ilk_tarih,
        "guncelleme_tarihi": bugun,
    }, on_conflict="sku").execute()
    sb.table("stok_yas").upsert(
        {"sku": sku, "ilk_gorulen_tarih": bugun}, on_conflict="sku"
    ).execute()

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
    tum_firma_rows = _rows(sb.table("firma_stok").select("*").order("yukleme_tarihi").execute())
    gecmis_satislar = defaultdict(list)
    for row in tum_firma_rows:
        gecmis_satislar[row["sku"]].append(row.get("haftalik_satis", 0) or 0)
    return urunler, firma_data, stok_yas_data, yoldaki_data, dict(gecmis_satislar)

def get_urun_detay(sku):
    return _row(get_client().table("urunler").select("*").eq("sku", sku).execute())

def sil_urun(sku):
    sb = get_client()
    for tablo in ["urunler", "firma_stok", "satin_alma_gecmisi",
                  "yoldaki_urunler", "stok_yas", "siparis_onerileri"]:
        sb.table(tablo).delete().eq("sku", sku).execute()

@st.cache_data(ttl=300, show_spinner=False)
def get_tum_sku_listesi():
    return _rows(get_client().table("urunler").select("sku, urun_adi").order("sku").execute())

# ── FİRMA STOK ──────────────────────────────────────────────────────

def upsert_firma_stok(firma, sku, urun_adi, stok_miktari, haftalik_satis):
    get_client().table("firma_stok").upsert({
        "firma": firma, "sku": sku, "urun_adi": urun_adi or "",
        "stok_miktari": int(stok_miktari or 0),
        "haftalik_satis": int(haftalik_satis or 0),
        "yukleme_tarihi": get_today(),
    }, on_conflict="firma,sku,yukleme_tarihi").execute()

# ── YOLDAKI ─────────────────────────────────────────────────────────

def upsert_yoldaki_urun(sku, urun_adi, yoldaki_miktar, tahmini_varis_tarihi, yoldaki_tedarikci=""):
    get_client().table("yoldaki_urunler").upsert({
        "sku": sku, "urun_adi": urun_adi or "",
        "yoldaki_miktar": int(yoldaki_miktar or 0),
        "tahmini_varis_tarihi": str(tahmini_varis_tarihi or ""),
        "yoldaki_tedarikci": yoldaki_tedarikci or "",
        "yukleme_tarihi": get_today(),
    }, on_conflict="sku").execute()

@st.cache_data(ttl=300, show_spinner=False)
def get_yoldaki_urunler():
    rows = _rows(get_client().table("yoldaki_urunler").select("*").execute())
    return {r["sku"]: r for r in rows}

# ── SATIN ALMA ──────────────────────────────────────────────────────

def ekle_satin_alma(sku, urun_adi, tedarikci, tarih, adet, alis_fiyati, maliyet_yuzdesi, notlar=""):
    toplam_birim = float(alis_fiyati or 0) * (1 + float(maliyet_yuzdesi or 0) / 100)
    get_client().table("satin_alma_gecmisi").insert({
        "sku": sku, "urun_adi": urun_adi or "", "tedarikci": tedarikci or "",
        "satin_alma_tarihi": str(tarih), "adet": int(adet or 0),
        "alis_fiyati": float(alis_fiyati or 0),
        "maliyet_yuzdesi": float(maliyet_yuzdesi or 0),
        "toplam_maliyet": toplam_birim * int(adet or 0),
        "notlar": notlar or "", "kayit_tarihi": get_today(),
    }).execute()
    st.cache_data.clear()

def guncelle_satin_alma(kayit_id, tedarikci, tarih, adet, alis_fiyati, maliyet_yuzdesi, notlar=""):
    toplam_birim = float(alis_fiyati or 0) * (1 + float(maliyet_yuzdesi or 0) / 100)
    get_client().table("satin_alma_gecmisi").update({
        "tedarikci": tedarikci, "satin_alma_tarihi": str(tarih),
        "adet": int(adet), "alis_fiyati": float(alis_fiyati),
        "maliyet_yuzdesi": float(maliyet_yuzdesi),
        "toplam_maliyet": toplam_birim * int(adet),
        "notlar": notlar or "",
    }).eq("id", kayit_id).execute()

def sil_satin_alma(kayit_id):
    get_client().table("satin_alma_gecmisi").delete().eq("id", kayit_id).execute()
    st.cache_data.clear()

@st.cache_data(ttl=120, show_spinner=False)
def get_satin_alma_gecmisi(sku=None):
    sb = get_client()
    q = sb.table("satin_alma_gecmisi").select("*").order("satin_alma_tarihi", desc=True)
    if sku:
        q = q.eq("sku", sku)
    return _rows(q.execute())

def get_satin_alma_ozet(sku=None):
    sb = get_client()
    if sku:
        rows = _rows(sb.table("satin_alma_gecmisi").select("*").eq("sku", sku).execute())
        if not rows:
            return None
        toplam_adet = sum(r.get("adet", 0) or 0 for r in rows)
        toplam_mal = sum(r.get("toplam_maliyet", 0) or 0 for r in rows)
        ort_alis = sum(r.get("alis_fiyati", 0) or 0 for r in rows) / len(rows)
        ort_maliyet = toplam_mal / toplam_adet if toplam_adet > 0 else 0
        tarihleri = [r["satin_alma_tarihi"] for r in rows if r.get("satin_alma_tarihi")]
        return {
            "siparis_sayisi": len(rows), "toplam_adet": toplam_adet,
            "ort_alis": ort_alis, "ort_maliyet": ort_maliyet,
            "ilk_satin_alma": min(tarihleri) if tarihleri else "",
            "son_satin_alma": max(tarihleri) if tarihleri else "",
        }
    else:
        rows = _rows(sb.table("satin_alma_gecmisi").select("*").execute())
        sku_groups = defaultdict(list)
        for r in rows:
            sku_groups[r["sku"]].append(r)
        result = []
        for s, grup in sku_groups.items():
            toplam_adet = sum(r.get("adet", 0) or 0 for r in grup)
            ort_maliyet = sum(r.get("toplam_maliyet", 0) or 0 for r in grup) / toplam_adet if toplam_adet else 0
            result.append({"sku": s, "siparis_sayisi": len(grup), "toplam_adet": toplam_adet, "ort_maliyet": ort_maliyet})
        return result

@st.cache_data(ttl=300, show_spinner=False)
def get_tum_tedarikciler():
    rows = _rows(get_client().table("satin_alma_gecmisi").select("tedarikci").execute())
    return list(set(r["tedarikci"] for r in rows if r.get("tedarikci")))

# ── SİPARİŞ ÖNERİLERİ ───────────────────────────────────────────────

def ekle_siparis_onerisi(firma, sku, urun_adi, miktar):
    get_client().table("siparis_onerileri").insert({
        "firma": firma, "sku": sku, "urun_adi": urun_adi or "",
        "oneri_miktari": int(miktar or 0),
        "durum": "bekliyor", "olusturma_tarihi": get_today(),
    }).execute()

@st.cache_data(ttl=120, show_spinner=False)
def get_siparis_onerileri():
    return _rows(get_client().table("siparis_onerileri").select("*").order("olusturma_tarihi", desc=True).execute())

def onayla_siparis(kayit_id):
    get_client().table("siparis_onerileri").update(
        {"durum": "onaylandi", "onay_tarihi": get_today()}
    ).eq("id", kayit_id).execute()

def reddet_siparis(kayit_id):
    get_client().table("siparis_onerileri").update(
        {"durum": "reddedildi", "onay_tarihi": get_today()}
    ).eq("id", kayit_id).execute()

# ── KAMPANYALAR ─────────────────────────────────────────────────────

def ekle_kampanya(kampanya_adi, firma, baslangic, bitis, notlar=""):
    r = get_client().table("kampanyalar").insert({
        "kampanya_adi": kampanya_adi, "firma": firma,
        "baslangic_tarihi": str(baslangic), "bitis_tarihi": str(bitis),
        "durum": "aktif", "notlar": notlar or "",
        "olusturma_tarihi": get_today(),
    }).execute()
    return r.data[0]["id"] if r.data else None

@st.cache_data(ttl=120, show_spinner=False)
def get_kampanyalar(durum=None):
    sb = get_client()
    q = sb.table("kampanyalar").select("*").order("olusturma_tarihi", desc=True)
    if durum:
        q = q.eq("durum", durum)
    return _rows(q.execute())

def get_kampanya(kampanya_id):
    return _row(get_client().table("kampanyalar").select("*").eq("id", kampanya_id).execute())

def guncelle_kampanya(kampanya_id, kampanya_adi, firma, baslangic, bitis, notlar):
    get_client().table("kampanyalar").update({
        "kampanya_adi": kampanya_adi, "firma": firma,
        "baslangic_tarihi": str(baslangic), "bitis_tarihi": str(bitis),
        "notlar": notlar or "",
    }).eq("id", kampanya_id).execute()

def kapat_kampanya(kampanya_id):
    get_client().table("kampanyalar").update({"durum": "kapali"}).eq("id", kampanya_id).execute()
    st.cache_data.clear()

def sil_kampanya(kampanya_id):
    sb = get_client()
    sb.table("kampanya_urunler").delete().eq("kampanya_id", kampanya_id).execute()
    sb.table("kampanyalar").delete().eq("id", kampanya_id).execute()

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

@st.cache_data(ttl=120, show_spinner=False)
def get_kampanya_urunler(kampanya_id):
    return _rows(get_client().table("kampanya_urunler").select("*").eq("kampanya_id", kampanya_id).order("id").execute())

def guncelle_kampanya_urun(urun_id, satis_fiyati, birim_firma_destek, birim_ek_destek, satilan_adet, notlar=""):
    get_client().table("kampanya_urunler").update({
        "satis_fiyati": float(satis_fiyati or 0),
        "birim_firma_destek": float(birim_firma_destek or 0),
        "birim_ek_destek": float(birim_ek_destek or 0),
        "satilan_adet": int(satilan_adet or 0),
        "notlar": notlar or "",
    }).eq("id", urun_id).execute()
    st.cache_data.clear()

def sil_kampanya_urun(urun_id):
    get_client().table("kampanya_urunler").delete().eq("id", urun_id).execute()

# ── BİLDİRİM ────────────────────────────────────────────────────────

def get_bildirim_ayarlari_db():
    rows = _rows(get_client().table("bildirim_ayarlari").select("*").limit(1).execute())
    return rows[0] if rows else {}

def kaydet_bildirim_ayarlari_db(email, smtp_server, smtp_port, smtp_user, smtp_password, aktif):
    sb = get_client()
    mevcut = _rows(sb.table("bildirim_ayarlari").select("id").limit(1).execute())
    data = {"email": email, "smtp_server": smtp_server, "smtp_port": int(smtp_port or 587),
            "smtp_user": smtp_user, "smtp_password": smtp_password, "aktif": aktif}
    if mevcut:
        sb.table("bildirim_ayarlari").update(data).eq("id", mevcut[0]["id"]).execute()
    else:
        sb.table("bildirim_ayarlari").insert(data).execute()

# ── ANALİTİK ────────────────────────────────────────────────────────

def get_gecmis_satis_firma_bazli(sku, firma):
    rows = _rows(get_client().table("firma_stok").select("haftalik_satis, yukleme_tarihi")
                .eq("sku", sku).eq("firma", firma)
                .order("yukleme_tarihi", desc=True).limit(8).execute())
    return [r.get("haftalik_satis", 0) or 0 for r in rows]

def get_tum_gecmis_satislar():
    rows = _rows(get_client().table("firma_stok").select("sku, haftalik_satis, yukleme_tarihi").order("yukleme_tarihi").execute())
    result = defaultdict(list)
    for r in rows:
        result[r["sku"]].append(r.get("haftalik_satis", 0) or 0)
    return dict(result)

def get_muadil_oneriler(sku, kategori, marka, fiyat):
    return []

def get_connection():
    return None

def get_gecmis_satis_tum_firmalar(sku):
    """Bir SKU için tüm firmaların geçmiş satış verilerini döndürür"""
    rows = _rows(get_client().table("firma_stok")
                .select("firma, haftalik_satis, stok_miktari, yukleme_tarihi")
                .eq("sku", sku)
                .order("yukleme_tarihi").execute())
    return rows

@st.cache_data(ttl=120, show_spinner=False)
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
