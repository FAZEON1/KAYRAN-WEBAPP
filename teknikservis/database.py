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
    "mal kabül", "teknisyende", "tamir edildi", "ürün değişimi",
    "sorunsuz", "iade alındı", "gönderildi", "hurda",
    "satışa hazır", "satıldı", "iptal",
]
# Tamamlanmış (aktif listeden çıkan) durumlar
BITMIS_DURUMLAR = {"gönderildi", "hurda", "satıldı", "iptal"}

DURUM_RENK = {
    "mal kabül": "#38BDF8", "teknisyende": "#A78BFA", "tamir edildi": "#34D399",
    "ürün değişimi": "#FBBF24", "sorunsuz": "#34D399",
    "iade alındı": "#F472B6", "gönderildi": "#22D3EE", "hurda": "#F87171",
    "satışa hazır": "#A3E635", "satıldı": "#10B981", "iptal": "#FB7185",
}

DEPOLAR = ["teknik servis", "iade", "outlet", "ikinci el", "hurda", "merkez"]
FIRMA_ONERILER = ["EERA", "MONDAY", "VATAN", "İTOPYA", "HB", "ServisPoint", "DİĞER"]

# Teknik servis / iade mal kabulünde kullanılan TAM cari unvanlar (profesyonel gösterim).
# Listede olmayan firma, mal kabul ekranında elle yazılarak eklenebilir.
TS_FIRMALAR = [
    "VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI",
    "D-MARKET ELEKTRONİK HİZMETLER VE TİCARET ANONİM ŞİRKETİ",
    "EERA ELEKTRONİK TİCARET VE BİLİŞİM HİZMETLERİ ANONİM ŞİRKETİ",
    "SERVİS NOKTASI TEKNOLOJİ ANONİM ŞİRKETİ",
    "MONDAY BİLİŞİM SANAYİ VE TİCARET ANONİM ŞİRKETİ",
    "DİĞER",
]

# Tabloda henüz olmayabilecek (sonradan eklenen) opsiyonel kolonlar — insert/update başarısız
# olursa bunlar düşülüp tekrar denenir (graceful).
_YENI_KOLONLAR = ("fatura_mevcut", "depo_aciklama",
                  "degisim_stok_kodu", "degisim_stok_adi", "degisim_seri_no", "degisim_depo")


@st.cache_resource
def get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    # service_role_key varsa onu kullan (RLS aşılır, kayranacc ile tutarlı); yoksa anon key.
    # Streamlit sunucu tarafında çalışır → bu anahtar tarayıcıya gönderilmez.
    key = st.secrets["supabase"].get("service_role_key") or st.secrets["supabase"]["key"]
    from shared.audit import wrap_client
    return wrap_client(create_client(url, key), "Teknik Servis")


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
        try:
            res = sb.table("ts_kayitlar").insert(kayit).execute()
        except Exception:
            # Yeni kolonlar tabloda yoksa onlarsız tekrar dene
            kayit = {k: v for k, v in kayit.items() if k not in _YENI_KOLONLAR}
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
        try:
            sb.table("ts_kayitlar").update(guncelle).eq("id", kayit_id).execute()
        except Exception:
            guncelle = {k: v for k, v in guncelle.items() if k not in _YENI_KOLONLAR}
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
        sb = get_client()
        try:
            sb.table("ts_kayitlar").update(alanlar).eq("id", kayit_id).execute()
        except Exception:
            alanlar = {k: v for k, v in alanlar.items() if k not in _YENI_KOLONLAR}
            sb.table("ts_kayitlar").update(alanlar).eq("id", kayit_id).execute()
        _cache_temizle()
        return True
    except Exception:
        return False


def sil_kayit(kayit_id):
    """Teknik servis kaydını ve tüm durum geçmişini KALICI siler.
    Hatalı / mükerrer kayıtları temizlemek için. Döner: (ok, hata)."""
    try:
        sb = get_client()
        sb.table("ts_gecmis").delete().eq("kayit_id", kayit_id).execute()
        sb.table("ts_kayitlar").delete().eq("id", kayit_id).execute()
        _cache_temizle()
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:160]}"


@st.cache_data(ttl=30, show_spinner=False)
def get_gecmis(kayit_id):
    try:
        return _rows(get_client().table("ts_gecmis").select("*")
                     .eq("kayit_id", kayit_id).order("tarih").execute())
    except Exception:
        return []


def ts_urun_gruplari():
    """Kayıtlarda geçen benzersiz ürün gruplarını döndürür (açılır liste için)."""
    try:
        gruplar = {(r.get("urun_grubu") or "").strip()
                   for r in get_kayitlar() if (r.get("urun_grubu") or "").strip()}
        return sorted(gruplar)
    except Exception:
        return []


def servis_formu_pdf(kayit, gecmis=None):
    """Bir kayıt için yazdırılabilir PDF form üretir (bytes döner).
    Başlık arayüze/duruma göre: Teknik Servis Formu / İade Formu / Ürün Değişim Formu."""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                    TableStyle)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    durum = (kayit.get("mevcut_durum") or "").strip()
    arayuz = kayit.get("arayuz", "")
    if durum == "ürün değişimi":
        baslik = "ÜRÜN DEĞİŞİM FORMU"
    elif arayuz == "iade":
        baslik = "İADE FORMU"
    else:
        baslik = "TEKNİK SERVİS FORMU"

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            title=f"{kayit.get('servis_form_no','')} {baslik}")
    styles = getSampleStyleSheet()
    from shared.utils import pdf_turkce_font, pdf_stilleri_turkcele
    PDF_NORMAL, PDF_BOLD = pdf_turkce_font()
    pdf_stilleri_turkcele(styles, PDF_NORMAL, PDF_BOLD)
    h_style = ParagraphStyle("h", parent=styles["Title"], fontName=PDF_BOLD, fontSize=16, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=styles["Normal"], fontName=PDF_NORMAL, fontSize=9, textColor=colors.HexColor("#666666"))
    sec = ParagraphStyle("sec", parent=styles["Normal"], fontName=PDF_BOLD, fontSize=10, textColor=colors.white,
                         backColor=colors.HexColor("#334155"), leftIndent=4, spaceBefore=8,
                         spaceAfter=2, leading=16)
    el = []

    def _v(k, b="—"):
        x = kayit.get(k)
        return str(x).strip() if x not in (None, "") else b

    el.append(Paragraph("KAYRAN / FAZEON", ParagraphStyle("co", parent=styles["Normal"],
              fontSize=11, textColor=colors.HexColor("#0EA5E9"))))
    el.append(Paragraph(baslik, h_style))
    el.append(Paragraph(f"Servis No: <b>{_v('servis_form_no')}</b> &nbsp;|&nbsp; "
                        f"Mal Kabül: {(_v('mal_kabul_tarihi'))[:16].replace('T',' ')}", sub))
    el.append(Spacer(1, 6))

    def _tablo(satirlar):
        t = Table([[Paragraph(f"<b>{a}</b>", styles["Normal"]), Paragraph(b, styles["Normal"])]
                   for a, b in satirlar], colWidths=[45 * mm, 120 * mm])
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return t

    el.append(Paragraph("ÜRÜN BİLGİSİ", sec))
    el.append(_tablo([
        ("Stok Kodu", _v("stok_kodu")), ("Stok Adı", _v("stok_adi")),
        ("Ürün Grubu", _v("urun_grubu")), ("Seri No", _v("seri_no")),
        ("EAN", _v("ean")), ("Arıza", _v("ariza")),
        ("İçerik Durumu", _v("icerik_durumu")), ("Fiziksel Durum", _v("fiziksel_durum")),
        ("Detay / Not", _v("detay")), ("Mevcut Durum", durum or "—"),
    ]))
    el.append(Paragraph("MÜŞTERİ / FİRMA", sec))
    el.append(_tablo([
        ("Firma Bilgisi", _v("firma_bilgisi")), ("Müşteri / Firma Adı", _v("musteri_adi")),
        ("Telefon", _v("musteri_tel")), ("Mail", _v("musteri_mail")),
        ("Adres", _v("musteri_adres")), ("Sevk / Kargo", _v("sevk_kargo_bilgisi")),
    ]))
    if any(kayit.get(a) for a in ("degisim_stok_kodu", "degisim_stok_adi", "degisim_seri_no", "degisim_depo")):
        el.append(Paragraph("DEĞİŞİM ÜRÜNÜ (yeni verilen)", sec))
        el.append(_tablo([
            ("Stok Kodu", _v("degisim_stok_kodu")), ("Stok Adı", _v("degisim_stok_adi")),
            ("Seri No", _v("degisim_seri_no")), ("Depo", _v("degisim_depo")),
        ]))
    el.append(Paragraph("BELGE", sec))
    el.append(_tablo([
        ("Fatura No", _v("fatura_no")), ("İrsaliye No", _v("irsaliye_no")),
        ("Firma Servis Form No", _v("firma_servis_form_no")),
    ]))

    _gec_goster = [h for h in (gecmis or [])
                   if "deposuna transfer" not in str(h.get("aciklama", "") or "").lower()]
    if _gec_goster:
        el.append(Paragraph("İŞLEM GEÇMİŞİ", sec))
        gsat = [("Tarih", "Durum / Açıklama / Personel")]
        for h in _gec_goster:
            t = str(h.get("tarih", "") or "")[:16].replace("T", " ")
            d = f"{h.get('durum','')} — {h.get('aciklama','') or ''} ({h.get('personel','') or '—'})"
            gsat.append((t, d))
        gt = Table([[Paragraph(a, styles["Normal"]), Paragraph(b, styles["Normal"])] for a, b in gsat],
                   colWidths=[35 * mm, 130 * mm])
        gt.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        el.append(gt)

    el.append(Spacer(1, 22))
    imza = Table([[Paragraph("Teslim Eden<br/><br/>_______________", styles["Normal"]),
                   Paragraph("Teslim Alan<br/><br/>_______________", styles["Normal"])]],
                 colWidths=[82 * mm, 82 * mm])
    imza.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 6)]))
    el.append(imza)

    doc.build(el)
    return buf.getvalue()
