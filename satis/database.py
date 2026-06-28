# -*- coding: utf-8 -*-
"""Satış & Kârlılık — veritabanı katmanı (USD bazlı).

Tablo: satislar — her satır bir satış işlemi.
COGS = güncel paçal (ağırlıklı ortalama landed) — İthalat'tan çekilir, kayıt anında
birim_maliyet olarak SABİTLENİR (sonradan maliyet değişse de geçmiş kâr bozulmaz).
Kâr (USD):
  ciro     = adet * birim_satis
  maliyet  = adet * birim_maliyet
  destek   = adet * (birim_firma_destek + birim_ek_destek)
  net_kar  = ciro - maliyet - destek
  marj %   = net_kar / ciro * 100
"""
from datetime import datetime, timezone, timedelta

import streamlit as st
from supabase import create_client, Client

TR_TZ = timezone(timedelta(hours=3))

# Satış kanalları (firma/pazar) — varsayılan; Muhasebe carileri varsa onlar kullanılır.
KANALLAR = ["İTOPYA", "HB", "VATAN", "MONDAY", "KANAL", "Trendyol", "Direkt", "DİGER"]


@st.cache_data(ttl=120, show_spinner=False)
def get_kanallar():
    """Kanal/firma listesi: Muhasebe'deki cari isimleri (varsa); yoksa varsayılan KANALLAR."""
    try:
        from kayranacc.database import get_cari_isimler
        cari = get_cari_isimler() or []
        if cari:
            return cari
    except Exception:
        pass
    return KANALLAR


@st.cache_resource
def _get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"].get("service_role_key") or st.secrets["supabase"]["key"]
    from shared.audit import wrap_client
    return wrap_client(create_client(url, key), "Satış")


def _rows(resp):
    return resp.data if resp.data else []


def _row(resp):
    d = resp.data if resp.data else None
    return d[0] if isinstance(d, list) and d else (d or None)


def _f(v, d=0.0):
    try:
        if v is None or v == "":
            return float(d)
        return float(v)
    except (TypeError, ValueError):
        return float(d)


def _i(v, d=0):
    try:
        return int(round(_f(v, d)))
    except (TypeError, ValueError):
        return int(d)


def _bugun():
    return datetime.now(TR_TZ).date().isoformat()


# ── Maliyet (paçal) ve ürün katalogu — İthalat / Ürün Yönetimi'nden ──
@st.cache_data(ttl=120, show_spinner=False)
def get_pacal_map():
    """{sku: pacal_final} — güncel ağırlıklı ortalama landed maliyet (USD)."""
    try:
        from ithalat.database import get_sku_maliyet_ozet
        ozet = get_sku_maliyet_ozet() or {}
        return {sku: _f(v.get("pacal_final")) for sku, v in ozet.items()}
    except Exception:
        return {}


@st.cache_data(ttl=120, show_spinner=False)
def get_urunler():
    """Ürün katalogu: [{sku, urun_adi, satis_fiyati, satis_fiyat_listesi}]."""
    try:
        rows = _rows(_get_client().table("urunler")
                     .select("sku, urun_adi, satis_fiyati, satis_fiyat_listesi").execute())
        return rows
    except Exception:
        return []


@st.cache_data(ttl=120, show_spinner=False)
def kampanya_destek_bul(sku, kanal, tarih):
    """Verilen SKU + kanal + tarih için aktif kampanyadaki destekleri döndürür.
    Döner: (birim_firma_destek, birim_ek_destek, kampanya_id) veya (0, 0, None)."""
    try:
        sb = _get_client()
        t = str(tarih)[:10]
        kampanyalar = _rows(sb.table("kampanyalar").select("*").execute())
        uygun = [k for k in kampanyalar
                 if str(k.get("firma", "")).strip().upper() == str(kanal).strip().upper()
                 and str(k.get("baslangic_tarihi", ""))[:10] <= t <= str(k.get("bitis_tarihi", "9999"))[:10]]
        if not uygun:
            return 0.0, 0.0, None
        kids = [k["id"] for k in uygun]
        kurunler = _rows(sb.table("kampanya_urunler").select("*").in_("kampanya_id", kids).eq("sku", sku).execute())
        if not kurunler:
            return 0.0, 0.0, None
        ku = kurunler[0]
        return _f(ku.get("birim_firma_destek")), _f(ku.get("birim_ek_destek")), ku.get("kampanya_id")
    except Exception:
        return 0.0, 0.0, None


# ── Satış CRUD ──
def ekle_satis(tarih, kanal, sku, urun_adi, adet, birim_satis, birim_maliyet,
               birim_firma_destek=0, birim_ek_destek=0, kampanya_id=None, notlar="", siparis_no=""):
    try:
        _get_client().table("satislar").insert({
            "tarih": str(tarih)[:10], "kanal": kanal or "", "sku": sku or "",
            "urun_adi": urun_adi or "", "adet": _i(adet),
            "birim_satis": _f(birim_satis), "birim_maliyet": _f(birim_maliyet),
            "birim_firma_destek": _f(birim_firma_destek), "birim_ek_destek": _f(birim_ek_destek),
            "kampanya_id": kampanya_id, "notlar": notlar or "", "siparis_no": siparis_no or "",
            "olusturma_tarihi": datetime.now(TR_TZ).isoformat(timespec="seconds"),
        }).execute()
        _temizle()
        return True, "✅ Satış kaydedildi."
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}"


def ekle_siparis(tarih, kanal, siparis_no, notlar, kalemler):
    """Tek siparişte birden çok kalemi TEK seferde kaydeder (toplu insert).
    kalemler: [{sku, urun_adi, adet, birim_satis, birim_maliyet,
                birim_firma_destek, birim_ek_destek, kampanya_id}, ...]
    Döner: (ok, mesaj, kalem_sayisi)."""
    rows = []
    zaman = datetime.now(TR_TZ).isoformat(timespec="seconds")
    for k in (kalemler or []):
        sku = str(k.get("sku") or "").strip()
        if not sku or _i(k.get("adet")) <= 0:
            continue
        rows.append({
            "tarih": str(tarih)[:10], "kanal": kanal or "", "siparis_no": siparis_no or "",
            "sku": sku, "urun_adi": k.get("urun_adi") or "", "adet": _i(k.get("adet")),
            "birim_satis": _f(k.get("birim_satis")), "birim_maliyet": _f(k.get("birim_maliyet")),
            "birim_firma_destek": _f(k.get("birim_firma_destek")), "birim_ek_destek": _f(k.get("birim_ek_destek")),
            "kampanya_id": k.get("kampanya_id"), "notlar": notlar or "", "olusturma_tarihi": zaman,
        })
    if not rows:
        return False, "Geçerli kalem yok.", 0
    try:
        _get_client().table("satislar").insert(rows).execute()
        _temizle()
        return True, f"✅ Sipariş kaydedildi — {len(rows)} kalem.", len(rows)
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}", 0


def guncelle_satis(satis_id, alanlar):
    try:
        _get_client().table("satislar").update(alanlar).eq("id", satis_id).execute()
        _temizle()
        return True
    except Exception:
        return False


def sil_satis(satis_id):
    try:
        _get_client().table("satislar").delete().eq("id", satis_id).execute()
        _temizle()
        return True
    except Exception:
        return False


def sil_siparis(siparis_no):
    """Bir sipariş numarasına ait tüm kalemleri siler."""
    try:
        _get_client().table("satislar").delete().eq("siparis_no", siparis_no).execute()
        _temizle()
        return True
    except Exception:
        return False


@st.cache_data(ttl=30, show_spinner=False)
def get_satislar(baslangic=None, bitis=None):
    """Tarih aralığına göre satışlar (yeni→eski). baslangic/bitis: 'YYYY-MM-DD' veya None."""
    try:
        q = _get_client().table("satislar").select("*")
        if baslangic:
            q = q.gte("tarih", str(baslangic)[:10])
        if bitis:
            q = q.lte("tarih", str(bitis)[:10])
        return _rows(q.order("tarih", desc=True).order("id", desc=True).execute())
    except Exception:
        return []


def _temizle():
    try:
        get_satislar.clear()
    except Exception:
        pass


# ── Kâr hesabı ──
def satir_kar(s):
    """Tek satış satırı için kâr metrikleri (USD)."""
    adet = _i(s.get("adet"))
    ciro = adet * _f(s.get("birim_satis"))
    maliyet = adet * _f(s.get("birim_maliyet"))
    destek = adet * (_f(s.get("birim_firma_destek")) + _f(s.get("birim_ek_destek")))
    net = ciro - maliyet - destek
    marj = (net / ciro * 100) if ciro > 0 else 0.0
    return {"adet": adet, "ciro": ciro, "maliyet": maliyet, "destek": destek,
            "net_kar": net, "marj": marj}


def ozet_hesapla(satislar):
    """Liste için toplam P&L + kanal/SKU kırılımı."""
    top = {"ciro": 0.0, "maliyet": 0.0, "destek": 0.0, "net_kar": 0.0, "adet": 0}
    kanal, urun = {}, {}
    for s in satislar:
        k = satir_kar(s)
        for f in ("ciro", "maliyet", "destek", "net_kar", "adet"):
            top[f] += k[f]
        kn = s.get("kanal", "") or "—"
        kanal.setdefault(kn, {"ciro": 0.0, "net_kar": 0.0, "adet": 0})
        kanal[kn]["ciro"] += k["ciro"]; kanal[kn]["net_kar"] += k["net_kar"]; kanal[kn]["adet"] += k["adet"]
        su = s.get("sku", "") or "—"
        urun.setdefault(su, {"urun_adi": s.get("urun_adi", ""), "ciro": 0.0, "net_kar": 0.0, "adet": 0})
        urun[su]["ciro"] += k["ciro"]; urun[su]["net_kar"] += k["net_kar"]; urun[su]["adet"] += k["adet"]
    top["marj"] = (top["net_kar"] / top["ciro"] * 100) if top["ciro"] > 0 else 0.0
    return top, kanal, urun
