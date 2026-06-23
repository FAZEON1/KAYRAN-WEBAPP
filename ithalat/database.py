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
        rows, start = [], 0
        while True:
            chunk = _rows(sb.table("ithalat_dosyalari").select("*")
                          .order("tarih", desc=True).range(start, start + 999).execute())
            rows.extend(chunk)
            if len(chunk) < 1000:
                break
            start += 1000
        return rows
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
        rows, start = [], 0
        while True:
            chunk = _rows(sb.table("ithalat_kalemleri").select("*")
                          .range(start, start + 999).execute())
            rows.extend(chunk)
            if len(chunk) < 1000:
                break
            start += 1000
        return rows
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def get_sku_maliyet_ozet():
    """
    Her SKU için ithalat verisinden PAÇAL (adet-ağırlıklı ortalama) maliyet.
    Dönen: {sku: {pacal_fob, pacal_final, toplam_adet, dosya_sayisi}}
      • dosya_yuzde = toplam_masraf / FOB * 100  (dosya bazında)
      • birim landed = birim_fob * (1 + dosya_yuzde/100)
      • paçal = tüm partilerdeki landed/fob değerlerinin adet-ağırlıklı ortalaması
    Not: Tüm tutarların aynı para biriminde (USD) olduğu varsayılır.
    """
    try:
        dosyalar = get_dosyalar()
        kalemler = get_tum_kalemler()
        if not kalemler:
            return {}
        # Kalemleri dosyaya göre grupla
        by_dosya = {}
        for k in kalemler:
            by_dosya.setdefault(k.get("dosya_id"), []).append(k)
        # Her dosyanın masraf yüzdesi
        dosya_map = {d.get("id"): d for d in dosyalar}
        dosya_yuzde = {}
        for did, ks in by_dosya.items():
            dosya_yuzde[did] = dosya_hesapla(dosya_map.get(did, {}), ks).get("maliyet_yuzde", 0.0)
        # SKU bazında ağırlıklı topla
        agg = {}
        for k in kalemler:
            sku = (str(k.get("sku") or "")).strip()
            if not sku:
                continue
            adet = _f(k.get("adet"))
            fob = _f(k.get("birim_fob"))
            if adet <= 0:
                continue
            yuzde = dosya_yuzde.get(k.get("dosya_id"), 0.0)
            final = fob * (1 + yuzde / 100.0)
            a = agg.setdefault(sku, {"fob_x": 0.0, "final_x": 0.0, "adet": 0.0, "dosyalar": set()})
            a["fob_x"] += fob * adet
            a["final_x"] += final * adet
            a["adet"] += adet
            a["dosyalar"].add(k.get("dosya_id"))
        sonuc = {}
        for sku, a in agg.items():
            ad = a["adet"]
            if ad <= 0:
                continue
            sonuc[sku] = {
                "pacal_fob": a["fob_x"] / ad,
                "pacal_final": a["final_x"] / ad,
                "toplam_adet": ad,
                "dosya_sayisi": len(a["dosyalar"]),
            }
        return sonuc
    except Exception:
        return {}


def get_sku_ithalat_partileri():
    """Her SKU için ithalat partileri (FIFO için), belge tarihine göre ESKİ→YENİ.
    Dönen: {sku: [{"tarih": "YYYY-MM-DD", "adet": float}, ...]}
    """
    try:
        dosyalar = get_dosyalar()
        tarih_map = {d.get("id"): (str(d.get("tarih") or "")[:10]) for d in dosyalar}
        kalemler = get_tum_kalemler()
        agg = {}
        for k in kalemler:
            sku = (str(k.get("sku") or "")).strip()
            if not sku:
                continue
            adet = _f(k.get("adet"))
            if adet <= 0:
                continue
            tarih = tarih_map.get(k.get("dosya_id"), "")
            if not tarih:
                continue
            agg.setdefault(sku, []).append({"tarih": tarih, "adet": adet})
        for sku in agg:
            agg[sku].sort(key=lambda x: x["tarih"])
        return agg
    except Exception:
        return {}


def ekle_dosya(dosya_no, tarih, tedarikci, mense_ulke, doviz, kur,
               masraflar, notlar, kalemler, pi_no="", ithalat_takip_no=""):
    """Bir ithalat dosyası + kalemlerini ekler.
    masraflar: {slug: tutar}  (örn. {'navlun': 1200, 'damga_vergisi': 80})
    kalemler:  list[dict(sku, urun_adi, adet, birim_fob)]
    Döner: (ok: bool, mesaj: str)."""
    sb = _get_client()
    try:
        temiz_masraf = {k: _f(v) for k, v in (masraflar or {}).items() if _f(v) != 0}
        _payload = {
            "dosya_no": str(dosya_no), "pi_no": pi_no or "", "tarih": str(tarih) if tarih else None,
            "tedarikci": tedarikci or "", "mense_ulke": mense_ulke or "",
            "doviz": doviz or "USD", "kur": _f(kur, 1),
            "masraflar": temiz_masraf, "notlar": notlar or "",
            "ithalat_takip_no": ithalat_takip_no or "",
        }
        try:
            d = _rows(sb.table("ithalat_dosyalari").insert(_payload).execute())
        except Exception:
            # ithalat_takip_no kolonu yoksa o alan olmadan tekrar dene
            _payload.pop("ithalat_takip_no", None)
            d = _rows(sb.table("ithalat_dosyalari").insert(_payload).execute())
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


def guncelle_dosya(dosya_id, dosya_no, pi_no, tarih, tedarikci, mense_ulke, doviz, kur,
                   masraflar, notlar, kalemler, ithalat_takip_no=""):
    """Dosya bilgileri + masraflar + kalemleri günceller (kalemler tamamen yenilenir)."""
    sb = _get_client()
    try:
        temiz_masraf = {k: _f(v) for k, v in (masraflar or {}).items() if _f(v) != 0}
        _payload = {
            "dosya_no": str(dosya_no), "pi_no": pi_no or "",
            "tarih": str(tarih) if tarih else None,
            "tedarikci": tedarikci or "", "mense_ulke": mense_ulke or "",
            "doviz": doviz or "USD", "kur": _f(kur, 1),
            "masraflar": temiz_masraf, "notlar": notlar or "",
            "ithalat_takip_no": ithalat_takip_no or "",
        }
        try:
            sb.table("ithalat_dosyalari").update(_payload).eq("id", dosya_id).execute()
        except Exception:
            # ithalat_takip_no kolonu tabloda yoksa o alan olmadan tekrar dene
            # (masraf ve diğer bilgiler yine kaydedilsin).
            _payload.pop("ithalat_takip_no", None)
            sb.table("ithalat_dosyalari").update(_payload).eq("id", dosya_id).execute()
        sb.table("ithalat_kalemleri").delete().eq("dosya_id", dosya_id).execute()
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
        return True, f"✅ Dosya güncellendi ({len(rows)} kalem)."
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


def set_dosya_takip_no(dosya_id, takip_no):
    """Bir dosyanın İthalat Takip No'sunu günceller (toplu eşleştirme için)."""
    try:
        _get_client().table("ithalat_dosyalari").update(
            {"ithalat_takip_no": takip_no or ""}).eq("id", dosya_id).execute()
        _temizle()
        return True
    except Exception:
        return False
