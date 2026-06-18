"""
KAYRAN — İthalat Veritabanı Katmanı (Supabase PostgreSQL)

Tablolar:
  ithalat_dosyalari  (parti/sipariş başlığı + masraf kalemleri)
  ithalat_kalemleri  (ürün satırları; sku = urunler.sku ile eşleşir)

Maliyet mantığı (kullanıcı kararı):
  • Dosya % maliyeti  = toplam_masraf / mal_bedeli(FOB) * 100
  • Masraf dağıtımı   = satır tutarına (FOB) orantılı
    → tutara orantılı dağıtımda her satırın % maliyeti = dosya %'sine eşittir.
  • final_birim_maliyet = birim_fob * (1 + dosya_yuzde/100)
Tüm tutarlar dosyanın para biriminde tutulur; kur yalnızca TL karşılığı içindir.
"""
import streamlit as st
from supabase import create_client, Client
from collections import defaultdict


@st.cache_resource
def _get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)


def _rows(resp):
    return resp.data if resp.data else []


def _temizle():
    try:
        st.cache_data.clear()
    except Exception:
        pass


# Masraf kalemleri (dosya seviyesinde)
MASRAF_KOLONLARI = ["navlun", "gumruk", "sigorta", "nakliye", "diger"]


def dosya_hesapla(dosya, kalemler):
    """Bir dosya + kalemleri için türetilmiş değerler.
    Döner: dict(mal_bedeli, toplam_masraf, maliyet_yuzde, kalem_sayisi, toplam_adet)."""
    mal_bedeli = sum(float(k.get("adet", 0) or 0) * float(k.get("birim_fob", 0) or 0) for k in kalemler)
    toplam_masraf = sum(float((dosya or {}).get(m, 0) or 0) for m in MASRAF_KOLONLARI)
    yuzde = (toplam_masraf / mal_bedeli * 100) if mal_bedeli > 0 else 0.0
    toplam_adet = sum(float(k.get("adet", 0) or 0) for k in kalemler)
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
    """Tüm kalemler (model sorgusu için)."""
    try:
        sb = _get_client()
        return _rows(sb.table("ithalat_kalemleri").select("*").execute())
    except Exception:
        return []


def ekle_dosya(dosya_no, tarih, tedarikci, mense_ulke, doviz, kur,
               navlun, gumruk, sigorta, nakliye, diger, notlar, kalemler):
    """Bir ithalat dosyası + kalemlerini ekler.
    kalemler: list[dict(sku, urun_adi, adet, birim_fob)].
    Döner: (ok: bool, mesaj: str)."""
    sb = _get_client()
    try:
        d = _rows(sb.table("ithalat_dosyalari").insert({
            "dosya_no": str(dosya_no), "tarih": str(tarih) if tarih else None,
            "tedarikci": tedarikci or "", "mense_ulke": mense_ulke or "",
            "doviz": doviz or "USD", "kur": float(kur or 1),
            "navlun": float(navlun or 0), "gumruk": float(gumruk or 0),
            "sigorta": float(sigorta or 0), "nakliye": float(nakliye or 0),
            "diger": float(diger or 0), "notlar": notlar or "",
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
                "dosya_id": dosya_id,
                "sku": sku,
                "urun_adi": (str(k.get("urun_adi") or "")).strip(),
                "adet": float(k.get("adet", 0) or 0),
                "birim_fob": float(k.get("birim_fob", 0) or 0),
            })
        if rows:
            sb.table("ithalat_kalemleri").insert(rows).execute()
        _temizle()
        return True, f"✅ '{dosya_no}' dosyası {len(rows)} kalem ile eklendi."
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:200]}"


def sil_dosya(dosya_id):
    """Dosyayı ve tüm kalemlerini siler."""
    sb = _get_client()
    try:
        sb.table("ithalat_kalemleri").delete().eq("dosya_id", dosya_id).execute()
        sb.table("ithalat_dosyalari").delete().eq("id", dosya_id).execute()
        _temizle()
        return True
    except Exception:
        return False
