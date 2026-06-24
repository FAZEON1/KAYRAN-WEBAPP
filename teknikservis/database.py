# -*- coding: utf-8 -*-
"""Teknik Servis / İade / RMA modülü — veritabanı katmanı.

Tablolar:
  ts_kayitlar : her serviste/iadede olan ürün kaydı (mevcut durum + tüm bilgiler)
  ts_gecmis   : her kaydın işlem durumu geçmişi (mal kabül → teknisyende → ...)

Form no:  G5F<5 hane>   ör. G5F00001
SLA    :  mal kabül tarihinden bu yana geçen İŞ GÜNÜ; 21 iş günü hedefi,
          haftalık renk: yeşil → sarı → turuncu → kırmızı
"""
from datetime import datetime, date, timedelta, timezone

import streamlit as st
from supabase import create_client, Client

# İstanbul saati (UTC+3) — sunucu UTC olabilir; kayıt saatleri TR'ye sabitlenir
TR_TZ = timezone(timedelta(hours=3))


def _simdi():
    """Şu anki İstanbul saati, ISO (saniye) — kayıt/işlem zaman damgaları için."""
    return datetime.now(TR_TZ).isoformat(timespec="seconds")

# ── Sabitler ─────────────────────────────────────────────────────────
ARAYUZLER = ["teknik", "iade"]
ARAYUZ_ETIKET = {"teknik": "🔧 Teknik Servis", "iade": "↩️ İade"}

DURUMLAR = [
    "mal kabül", "teknisyende", "tamir edildi", "NTF", "ürün değişimi",
    "sorunsuz", "iade alındı", "gönderildi", "hurda",
    "satışa hazır", "satıldı",
]
# Tamamlanmış (aktif listeden çıkan) durumlar
BITMIS_DURUMLAR = {"gönderildi", "hurda", "satıldı"}

DURUM_RENK = {
    "mal kabül": "#38BDF8", "teknisyende": "#A78BFA", "tamir edildi": "#34D399",
    "NTF": "#94A3B8", "ürün değişimi": "#FBBF24", "sorunsuz": "#34D399",
    "iade alındı": "#F472B6", "gönderildi": "#22D3EE", "hurda": "#F87171",
    "satışa hazır": "#A3E635", "satıldı": "#10B981",
}

DEPOLAR = ["teknik servis", "iade", "outlet", "ikinci el", "hurda", "merkez"]
FIRMA_ONERILER = ["EERA", "MONDAY", "VATAN", "İTOPYA", "HB", "ServisPoint", "DİĞER"]


@st.cache_resource
def get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    # service_role_key varsa onu kullan (RLS aşılır, kayranacc ile tutarlı); yoksa anon key.
    # Streamlit sunucu tarafında çalışır → bu anahtar tarayıcıya gönderilmez.
    key = st.secrets["supabase"].get("service_role_key") or st.secrets["supabase"]["key"]
    return create_client(url, key)


def _cache_temizle():
    try:
        st.cache_data.clear()
    except Exception:
        pass


def _rows(resp):
    return resp.data if resp.data else []


def _row(resp):
    d = resp.data
    return d[0] if d else None


# ── İş günü / SLA ────────────────────────────────────────────────────
def _parse_ts(v):
    if not v:
        return None
    if isinstance(v, (datetime, date)):
        return v if isinstance(v, datetime) else datetime(v.year, v.month, v.day)
    s = str(v)
    for f in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], f)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(s[:19])
    except Exception:
        return None


def is_gunu_farki(baslangic, bitis=None):
    """İki tarih arasındaki iş günü (hafta sonu hariç) sayısı."""
    b = _parse_ts(baslangic)
    if not b:
        return 0
    son = _parse_ts(bitis) or datetime.now(TR_TZ).replace(tzinfo=None)
    if son < b:
        return 0
    gun = 0
    d = b.date()
    sd = son.date()
    while d < sd:
        d += timedelta(days=1)
        if d.weekday() < 5:
            gun += 1
    return gun


def sla_renk(is_gunu, bitmis=False):
    """21 iş günü hedefi — haftalık renk eskalasyonu."""
    if bitmis:
        return "#64748B", "Tamamlandı"
    if is_gunu <= 5:
        return "#10B981", f"{is_gunu} iş günü"
    if is_gunu <= 10:
        return "#EAB308", f"{is_gunu} iş günü"
    if is_gunu <= 15:
        return "#F97316", f"{is_gunu} iş günü"
    return "#EF4444", f"{is_gunu} iş günü ⚠"


# ── Ürün Yönetimi entegrasyonu (otomatik eşleştirme) ─────────────────
def urun_getir(stok_kodu):
    """Ürün Yönetimi'ndeki ürün kartından stok adı / ürün grubu çeker."""
    try:
        from kayranpm.database import get_urun_detay
        u = get_urun_detay(str(stok_kodu).strip())
        if not u:
            return None
        return {
            "stok_adi": u.get("urun_adi", "") or "",
            "urun_grubu": u.get("kategori", "") or "",
            "ean": u.get("ean", "") or u.get("barkod", "") or "",
        }
    except Exception:
        return None


@st.cache_data(ttl=120, show_spinner=False)
def ithalat_model_listesi():
    """İthalat kalemlerindeki tüm modeller (stok kodu → ürün adı). Mal Kabül seçim listesi için."""
    try:
        from ithalat.database import get_tum_kalemler, get_urun_katalog
        ozet = {}
        for k in (get_tum_kalemler() or []):
            s = str(k.get("sku", "") or "").strip()
            if not s:
                continue
            ad = str(k.get("urun_adi", "") or "").strip()
            if s not in ozet or (not ozet[s] and ad):
                ozet[s] = ad
        if not ozet:  # İthalat kalemi yoksa ürün kataloğuna düş
            for s, a in (get_urun_katalog() or {}).items():
                s = str(s or "").strip()
                if s:
                    ozet[s] = str(a or "").strip()
        return sorted(ozet.items(), key=lambda x: x[0])
    except Exception:
        return []


# ── DB: kayıtlar ─────────────────────────────────────────────────────
@st.cache_data(ttl=30, show_spinner=False)
def get_kayitlar(arayuz=None, depolu=None):
    try:
        q = get_client().table("ts_kayitlar").select("*").order("id", desc=True)
        if arayuz:
            q = q.eq("arayuz", arayuz)
        rows = _rows(q.execute())
        if depolu is True:
            rows = [r for r in rows if (r.get("depo") or "").strip()]
        elif depolu is False:
            rows = [r for r in rows if not (r.get("depo") or "").strip()]
        return rows
    except Exception:
        return []


@st.cache_data(ttl=30, show_spinner=False)
def get_kayit(kayit_id):
    try:
        return _row(get_client().table("ts_kayitlar").select("*").eq("id", kayit_id).execute())
    except Exception:
        return None


def _sonraki_form_no():
    try:
        rows = _rows(get_client().table("ts_kayitlar").select("servis_form_no").execute())
        mx = 0
        for r in rows:
            s = str(r.get("servis_form_no", "") or "")
            num = "".join(ch for ch in s if ch.isdigit())
            if num:
                mx = max(mx, int(num))
        return f"G5F{mx + 1:05d}"
    except Exception:
        return "G5F00001"


def ekle_kayit(data, personel=""):
    """Yeni mal kabül kaydı. Form no üretir, durum 'mal kabül', geçmişe ekler."""
    try:
        sb = get_client()
        form_no = _sonraki_form_no()
        simdi = _simdi()
        kayit = dict(data)
        kayit.update({
            "servis_form_no": form_no,
            "mevcut_durum": "mal kabül",
            "mal_kabul_tarihi": simdi,
            "personel": personel or kayit.get("personel", ""),
        })
        res = sb.table("ts_kayitlar").insert(kayit).execute()
        yeni = _row(res)
        if yeni:
            sb.table("ts_gecmis").insert({
                "kayit_id": yeni["id"], "durum": "mal kabül",
                "aciklama": "Mal kabül yapıldı", "personel": personel or "",
                "tarih": simdi,
            }).execute()
        _cache_temizle()
        return True, f"✅ Kayıt oluşturuldu — Servis No: {form_no}", form_no
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}", ""


def durum_guncelle(kayit_id, yeni_durum, personel="", aciklama="", ekstra=None):
    """Durumu değiştirir, ts_gecmis'e satır ekler, opsiyonel ekstra alanları günceller."""
    try:
        sb = get_client()
        simdi = _simdi()
        guncelle = {"mevcut_durum": yeni_durum}
        if ekstra:
            guncelle.update(ekstra)
        sb.table("ts_kayitlar").update(guncelle).eq("id", kayit_id).execute()
        sb.table("ts_gecmis").insert({
            "kayit_id": kayit_id, "durum": yeni_durum,
            "aciklama": aciklama or "", "personel": personel or "", "tarih": simdi,
        }).execute()
        _cache_temizle()
        return True
    except Exception:
        return False


def kayit_guncelle(kayit_id, alanlar):
    try:
        get_client().table("ts_kayitlar").update(alanlar).eq("id", kayit_id).execute()
        _cache_temizle()
        return True
    except Exception:
        return False


@st.cache_data(ttl=30, show_spinner=False)
def get_gecmis(kayit_id):
    try:
        return _rows(get_client().table("ts_gecmis").select("*")
                     .eq("kayit_id", kayit_id).order("tarih").execute())
    except Exception:
        return []
