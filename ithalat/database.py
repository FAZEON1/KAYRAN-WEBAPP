"""
KAYRAN — İthalat Veritabanı Katmanı (Supabase PostgreSQL)

Tablolar:
  ithalat_dosyalari  (parti/sipariş başlığı; masraflar JSONB içinde {slug: tutar})
  ithalat_kalemleri  (ürün satırları; sku = urunler.sku ile eşleşir)

Maliyet mantığı:
  • Dosya % maliyeti  = toplam_masraf / mal_bedeli(FOB) * 100
  • Masraf dağıtımı   = satır tutarına (FOB) orantılı
  • final_birim_maliyet = birim_fob * (1 + dosya_yuzde/100)
"""
import streamlit as st
from supabase import create_client, Client


# Masraf kalemleri — (slug, görünen ad). Liste değişebilir; masraflar JSONB'de saklanır.
MASRAF_TANIM = [
    ("navlun",                 "Navlun"),
    ("mal_sigortasi",          "Mal Sigortası"),
    ("damga_vergisi",          "Damga Vergisi"),
    ("banka_komisyonu",        "Banka Komisyonu"),
    ("liman_ardiye",           "Liman Ardiye"),
    ("gumruk_musavirligi",     "Gümrük Müşavirliği"),
    ("antrepo_beyannamesi",    "Antrepo Beyannamesi"),
    ("liman_depo_nakliye",     "Liman - Depo Nakliye"),
    ("antrepo_ardiye",         "Antrepo Ardiye"),
    ("yolluk",                 "Yolluk"),
    ("demuraj",                "Demuraj"),
    ("tahliye_depolama_tasima","Tahliye-Depolama+Taşıma"),
    ("igv",                    "İGV"),
    ("diger",                  "Diğer"),
]
MASRAF_ETIKET = dict(MASRAF_TANIM)
# Eski sürüm (5 sabit kolon) — geriye dönük okuma için
_ESKI_MASRAF = ["navlun", "gumruk", "sigorta", "nakliye", "diger"]


@st.cache_resource
def _get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)


def _rows(resp):
    return resp.data if resp.data else []


def _f(v, d=0.0):
    try:
        if v is None:
            return float(d)
        return float(v)
    except Exception:
        return float(d)


def _temizle():
    try:
        st.cache_data.clear()
    except Exception:
        pass


def _masraf_dict(dosya):
    """Dosyanın masraflarını {slug: tutar} olarak döner (yeni JSONB ya da eski kolonlar)."""
    dosya = dosya or {}
    m = dosya.get("masraflar")
    if isinstance(m, str):
        import json
        try:
            m = json.loads(m)
        except Exception:
            m = {}
    if isinstance(m, dict) and m:
        return {k: _f(v) for k, v in m.items()}
    # Geriye dönük: eski sabit kolonlar
    return {k: _f(dosya.get(k, 0)) for k in _ESKI_MASRAF if _f(dosya.get(k, 0)) != 0}


def masraf_dokumu(dosya):
    """Sıfırdan farklı masrafları [(görünen_ad, tutar)] olarak döner (tanım sırasında)."""
    m = _masraf_dict(dosya)
    sirali = [(MASRAF_ETIKET.get(s, s), m[s]) for s, _ in MASRAF_TANIM if m.get(s)]
    # tanımda olmayan slug'lar (eski) varsa sona ekle
    bilinen = {s for s, _ in MASRAF_TANIM}
    for k, v in m.items():
        if k not in bilinen and v:
            sirali.append((k, v))
    return sirali


def dosya_hesapla(dosya, kalemler):
    """Türetilmiş değerler: mal_bedeli, toplam_masraf, maliyet_yuzde, kalem_sayisi, toplam_adet."""
    mal_bedeli = sum(_f(k.get("adet")) * _f(k.get("birim_fob")) for k in kalemler)
    toplam_masraf = sum(v for _, v in masraf_dokumu(dosya))
    yuzde = (toplam_masraf / mal_bedeli * 100) if mal_bedeli > 0 else 0.0
    toplam_adet = sum(_f(k.get("adet")) for k in kalemler)
    return {
        "mal_bedeli": mal_bedeli,
        "toplam_masraf": toplam_masraf,
        "maliyet_yuzde": yuzde,
        "kalem_sayisi": len(kalemler),
        "toplam_adet": toplam_adet,
    }


# ── Mevcut ürün kataloğu (SKU eşleştirme) ──
@st.cache_data(ttl=120, show_spinner=False)
def get_urun_katalog():
    """urunler tablosundan {sku: urun_adi}."""
    try:
        sb = _get_client()
        rows = _rows(sb.table("urunler").select("sku, urun_adi").order("sku").execute())
        return {r["sku"]: (r.get("urun_adi") or "") for r in rows}
    except Exception:
        return {}


# ── İthalat dosyaları / kalemleri ──
@st.cache_data(ttl=60, show_spinner=False)
def get_dosyalar():
    try:
        sb = _get_client()
        return _rows(sb.table("ithalat_dosyalari").select("*").order("tarih", desc=True).execute())
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def get_kalemler(dosya_id):
    try:
        sb = _get_client()
        return _rows(sb.table("ithalat_kalemleri").select("*").eq("dosya_id", dosya_id).execute())
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def get_tum_kalemler():
    try:
        sb = _get_client()
        return _rows(sb.table("ithalat_kalemleri").select("*").execute())
    except Exception:
        return []


def ekle_dosya(dosya_no, tarih, tedarikci, mense_ulke, doviz, kur,
               masraflar, notlar, kalemler):
    """Bir ithalat dosyası + kalemlerini ekler.
    masraflar: {slug: tutar}  (örn. {'navlun': 1200, 'damga_vergisi': 80})
    kalemler:  list[dict(sku, urun_adi, adet, birim_fob)]
    Döner: (ok: bool, mesaj: str)."""
    sb = _get_client()
    try:
        temiz_masraf = {k: _f(v) for k, v in (masraflar or {}).items() if _f(v) != 0}
        d = _rows(sb.table("ithalat_dosyalari").insert({
            "dosya_no": str(dosya_no), "tarih": str(tarih) if tarih else None,
            "tedarikci": tedarikci or "", "mense_ulke": mense_ulke or "",
            "doviz": doviz or "USD", "kur": _f(kur, 1),
            "masraflar": temiz_masraf, "notlar": notlar or "",
        }).execute())
        if not d:
            return False, "Dosya eklenemedi (boş yanıt)."
        dosya_id = d[0]["id"]
        rows = []
        for k in (kalemler or []):
            sku = (str(k.get("sku") or "")).strip()
            if not sku or sku.lower() == "nan":
                continue
            rows.append({
                "dosya_id": dosya_id, "sku": sku,
                "urun_adi": (str(k.get("urun_adi") or "")).strip(),
                "adet": _f(k.get("adet")), "birim_fob": _f(k.get("birim_fob")),
            })
        if rows:
            sb.table("ithalat_kalemleri").insert(rows).execute()
        _temizle()
        return True, f"✅ '{dosya_no}' dosyası {len(rows)} kalem ile eklendi."
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:200]}"


def sil_dosya(dosya_id):
    sb = _get_client()
    try:
        sb.table("ithalat_kalemleri").delete().eq("dosya_id", dosya_id).execute()
        sb.table("ithalat_dosyalari").delete().eq("id", dosya_id).execute()
        _temizle()
        return True
    except Exception:
        return False
