import os
import math
import streamlit as st
# Türkiye saat dilimi için ortak yardımcılar
from shared.utils import tr_today, tr_now, tr_today_iso, tr_now_str, tr_tomorrow, tr_yesterday as _tr_today_iso_dummy
from supabase import create_client, Client
from datetime import date


# ── Supabase bağlantısı — cache ile tek seferlik oluştur ─────────────
@st.cache_resource
def get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["service_role_key"]
    from shared.audit import wrap_client
    return wrap_client(create_client(url, key), "Muhasebe")


# ── Cache yardımcısı ────────────────────────────────────────────────h
# Veri değişince cache'i temizlemek için
def _cache_temizle():
    """Tüm @st.cache_data önbelleklerini temizler.
    Her yazma (ekle/sil/güncelle) işleminden sonra çağrılır."""
    try:
        st.cache_data.clear()
    except Exception:
        pass


def initialize_db():
    pass


# ════════════════════════════════════════════════════════════════════
# HAFTALAR
# ════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def get_tum_haftalar():
    sb = get_client()
    res = sb.table("haftalar").select("*").order("id", desc=True).execute()
    return res.data or []


@st.cache_data(ttl=300, show_spinner=False)
def get_aktif_hafta():
    sb = get_client()
    res = sb.table("haftalar").select("*").eq("aktif", 1).limit(1).execute()
    return res.data[0] if res.data else None


def hafta_ekle(hafta_adi):
    sb = get_client()
    today = tr_now().strftime("%d.%m.%Y")
    res = sb.table("haftalar").insert({
        "hafta_adi": hafta_adi,
        "yuklendi_tarih": today,
        "aktif": 0
    }).execute()
    _cache_temizle()
    return res.data[0]["id"] if res.data else None


def hafta_aktif_yap(hafta_id):
    sb = get_client()
    sb.table("haftalar").update({"aktif": 0}).neq("id", 0).execute()
    sb.table("haftalar").update({"aktif": 1}).eq("id", hafta_id).execute()
    _cache_temizle()


def hafta_sil(hafta_id):
    sb = get_client()
    sb.table("odemeler").delete().eq("hafta_id", hafta_id).execute()
    sb.table("haftalar").delete().eq("id", hafta_id).execute()
    _cache_temizle()


# ════════════════════════════════════════════════════════════════════
# ODEMELER
# ════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def get_hafta_odemeler(hafta_id):
    sb = get_client()
    res = sb.table("odemeler").select("*").eq("hafta_id", hafta_id).order("vade").execute()
    return res.data or []


@st.cache_data(ttl=300, show_spinner=False)
def get_aktif_odemeler():
    hafta = get_aktif_hafta()
    if not hafta:
        return [], None
    odemeler = get_hafta_odemeler(hafta["id"])
    return odemeler, hafta


@st.cache_data(ttl=300, show_spinner=False)
def get_hafta_ozet(hafta_id):
    odemeler = get_hafta_odemeler(hafta_id)
    return {
        "toplam": len(odemeler),
        "odendi": sum(1 for o in odemeler if o["durum"] == "odendi"),
        "tl_toplam": sum(o.get("tutar_tl") or 0 for o in odemeler),
        "usd_toplam": sum(o.get("tutar_usd") or 0 for o in odemeler),
    }


def _temizle(v):
    """Sayısal değerlerde None, NaN ve inf değerleri temizler. Native float döner."""
    import math
    if v is None:
        return None
    try:
        if hasattr(v, 'item'):  # numpy tipi ise native'e çevir
            v = v.item()
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return float(f)  # kesinlikle native float
    except (TypeError, ValueError):
        return None


def _str(v, max_len=500):
    """String alanlarını güvenli şekilde temizler."""
    if v is None:
        return ""
    if hasattr(v, 'item'):
        v = v.item()
    s = str(v).strip()
    if s.lower() in ("nan", "none", "null", "nat", "<na>"):
        return ""
    return s[:max_len]


def _vade(v):
    """Vade tarihini YYYY-MM-DD string'ine çevirir. Boşsa None döner."""
    s = _str(v)
    if not s:
        return None
    try:
        import pandas as pd
        d = pd.to_datetime(s)
        return d.strftime("%Y-%m-%d")
    except Exception:
        return None


def odeme_ekle_bulk(hafta_id, odemeler):
    sb = get_client()
    rows = []
    for o in odemeler:
        tl = _temizle(o.get("tl"))
        usd = _temizle(o.get("usd"))
        if tl is None and usd is None:
            continue
        rows.append({
            "hafta_id": int(hafta_id),
            "firma": _str(o.get("firma")),
            "aciklama": _str(o.get("aciklama")),
            "cari_banka": _str(o.get("cari_banka")),
            "vade": _vade(o.get("vade")),
            "tutar_tl": tl,
            "tutar_usd": usd,
            "kategori": _str(o.get("kategori")) or "diger",
            "manuel": int(o.get("manuel") or 0),
            "durum": "bekliyor",
        })
    BATCH = 25
    for i in range(0, len(rows), BATCH):
        sb.table("odemeler").insert(rows[i:i+BATCH]).execute()
        _cache_temizle()


def odeme_ekle_manuel(hafta_id, firma, aciklama, cari_banka, vade, tutar_tl, tutar_usd, kategori):
    sb = get_client()
    sb.table("odemeler").insert({
        "hafta_id": hafta_id,
        "firma": firma,
        "aciklama": aciklama,
        "cari_banka": cari_banka or "",
        "vade": vade,
        "tutar_tl": tutar_tl or None,
        "tutar_usd": tutar_usd or None,
        "kategori": kategori,
        "manuel": 1,
        "durum": "bekliyor",
    }).execute()
    _cache_temizle()


def odeme_durum_guncelle(odeme_id, durum, banka_id=None, kur=None):
    """
    Ödeme durumunu günceller.
    - banka_id verilirse: Ödeme tutarı ilgili bankadan düşülür.
    - Geri alma (durum='bekliyor'): Banka bakiyesi iade edilir (banka_id kolonu varsa).

    ÖNEMLİ: Supabase'de 'banka_id' kolonu OLMASA BİLE bu fonksiyon çalışır.
    Sadece otomatik banka bakiye düşme/iade özelliği kapalı olur.
    """
    sb = get_client()
    today = tr_today_iso() if durum == "odendi" else None

    # Önce mevcut ödeme bilgisini al
    try:
        mevcut = sb.table("odemeler").select("*").eq("id", odeme_id).execute()
        if not mevcut.data:
            return
        odeme = mevcut.data[0]
    except Exception:
        return

    # Önceki banka_id (kolon yoksa None olur)
    onceki_banka_id = odeme.get("banka_id")
    onceki_durum = odeme.get("durum")

    # ─── Ödeme kaydını güncelle (banka_id ayrı deneyelim) ───
    update_data = {
        "durum": durum,
        "odendi_tarih": today,
    }
    try:
        sb.table("odemeler").update(update_data).eq("id", odeme_id).execute()
    except Exception:
        return

    # ─── banka_id kolonunu ayrı güncelle (varsa) ───
    banka_id_kolonu_var = True
    if durum == "odendi" and banka_id:
        try:
            sb.table("odemeler").update({"banka_id": banka_id}).eq("id", odeme_id).execute()
        except Exception:
            banka_id_kolonu_var = False  # kolon yok, ama ödeme durumu güncellendi

    # ─── Banka bakiyesi güncelleme (opsiyonel) ───
    try:
        tutar_tl = float(odeme.get("tutar_tl") or 0)
        tutar_usd = float(odeme.get("tutar_usd") or 0)
        kur_val = float(kur) if kur and float(kur) > 0 else 1.0

        # 1) Ödendi → banka bakiyesinden düş (sadece önceki durum "bekliyor" iken)
        # ÖNEMLİ: Eğer zaten "odendi" ise tekrar düşme yapma (çifte düşüm koruması)
        if durum == "odendi" and banka_id and onceki_durum != "odendi":
            banka_res = sb.table("bankalar").select("*").eq("id", banka_id).execute()
            if banka_res.data:
                banka = banka_res.data[0]
                yeni_bakiye = float(banka["bakiye"])
                if banka["para_birimi"] == "TL":
                    yeni_bakiye -= tutar_tl + (tutar_usd * kur_val)
                elif banka["para_birimi"] == "USD":
                    yeni_bakiye -= tutar_usd + (tutar_tl / kur_val)
                else:
                    yeni_bakiye -= tutar_tl
                sb.table("bankalar").update({"bakiye": yeni_bakiye}).eq("id", banka_id).execute()

        # 2) Geri al (odendi → bekliyor): önceki bankaya iade — sadece banka_id kolonu varsa
        elif durum == "bekliyor" and onceki_durum == "odendi" and onceki_banka_id:
            banka_res = sb.table("bankalar").select("*").eq("id", onceki_banka_id).execute()
            if banka_res.data:
                banka = banka_res.data[0]
                yeni_bakiye = float(banka["bakiye"])
                if banka["para_birimi"] == "TL":
                    yeni_bakiye += tutar_tl + (tutar_usd * kur_val)
                elif banka["para_birimi"] == "USD":
                    yeni_bakiye += tutar_usd + (tutar_tl / kur_val)
                else:
                    yeni_bakiye += tutar_tl
                sb.table("bankalar").update({"bakiye": yeni_bakiye}).eq("id", onceki_banka_id).execute()
                # banka_id'yi temizle (varsa)
                try:
                    sb.table("odemeler").update({"banka_id": None}).eq("id", odeme_id).execute()
                except Exception:
                    pass
    except Exception:
        # Banka güncellemesi başarısız olsa bile ödeme durumu güncellemiş olur
        pass
    _cache_temizle()


def odeme_sil(odeme_id):
    sb = get_client()
    sb.table("odemeler").delete().eq("id", odeme_id).execute()
    _cache_temizle()


def odeme_vade_guncelle(odeme_id, yeni_vade):
    """Sadece vadeyi günceller. Erteleme tracking app.py'de session_state ile yapılır."""
    sb = get_client()
    vade_str = yeni_vade.isoformat() if hasattr(yeni_vade, "isoformat") else str(yeni_vade)
    try:
        sb.table("odemeler").update({"vade": vade_str}).eq("id", odeme_id).execute()
    except Exception:
        pass
        _cache_temizle()


@st.cache_data(ttl=300, show_spinner=False)
def get_ertelenen_odemeler():
    """
    Ertelenmiş ödemeleri döndürür. İki yöntem dener:
    1) ertelendi_sayisi > 0 (Supabase'de kolon varsa)
    2) Fallback: orijinal_vade DOLU olan kayıtlar
    İkisi de yoksa boş liste döner.
    """
    sb = get_client()

    # Yöntem 1: ertelendi_sayisi kolonu varsa
    try:
        res = sb.table("odemeler").select("*").gt("ertelendi_sayisi", 0).execute()
        if res.data:
            return res.data
    except Exception:
        pass

    # Yöntem 2: orijinal_vade dolu olanlar (kolon varsa)
    try:
        res = sb.table("odemeler").select("*").not_.is_("orijinal_vade", "null").execute()
        if res.data:
            return res.data
    except Exception:
        pass

    return []


def odeme_tutar_guncelle(odeme_id, tutar_tl=None, tutar_usd=None):
    """
    Ödemenin TL/USD tutarlarını günceller.
    - 0 veya None → o alan NULL olarak kaydedilir (temizlenir).
    - Pozitif değer → güncellenir.
    Hem tutar_tl hem tutar_usd her zaman güncellenir.
    """
    sb = get_client()
    update_data = {
        "tutar_tl": float(tutar_tl) if tutar_tl and float(tutar_tl) > 0 else None,
        "tutar_usd": float(tutar_usd) if tutar_usd and float(tutar_usd) > 0 else None,
    }
    sb.table("odemeler").update(update_data).eq("id", odeme_id).execute()
    _cache_temizle()


def odeme_kategori_guncelle(odeme_id, yeni_kategori):
    """Ödemenin kategorisini günceller."""
    sb = get_client()
    try:
        sb.table("odemeler").update({"kategori": yeni_kategori}).eq("id", odeme_id).execute()
        return True
    except Exception:
        _cache_temizle()
        return False

def odeme_aciklama_guncelle(odeme_id, yeni_aciklama):
    """Ödemenin açıklama alanını günceller."""
    sb = get_client()
    try:
        aciklama_val = str(yeni_aciklama).strip() if yeni_aciklama else None
        sb.table("odemeler").update({"aciklama": aciklama_val}).eq("id", odeme_id).execute()
        _cache_temizle()
        return True
    except Exception:
        _cache_temizle()
        return False


# ════════════════════════════════════════════════════════════════════
# BANKALAR
# ════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def get_bankalar():
    sb = get_client()
    res = sb.table("bankalar").select("*").order("id").execute()
    return res.data or []


def banka_ekle(hesap_adi, bakiye, para_birimi):
    """Yeni banka hesabı ekler. Parametre sırası: hesap_adi, bakiye, para_birimi"""
    sb = get_client()
    sb.table("bankalar").insert({
        "hesap_adi": hesap_adi,
        "para_birimi": para_birimi,
        "bakiye": float(bakiye) if bakiye is not None else 0,
    }).execute()
    _cache_temizle()


def banka_guncelle(banka_id, hesap_adi, bakiye, para_birimi):
    """Banka hesabını günceller. app.py'deki çağrıya uygun."""
    sb = get_client()
    sb.table("bankalar").update({
        "hesap_adi": hesap_adi,
        "bakiye": float(bakiye) if bakiye is not None else 0,
        "para_birimi": para_birimi,
    }).eq("id", banka_id).execute()
    _cache_temizle()


def banka_sil(banka_id):
    sb = get_client()
    sb.table("bankalar").delete().eq("id", banka_id).execute()
    _cache_temizle()


# ════════════════════════════════════════════════════════════════════
# CEKLER
# ════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def get_cekler(para_birimi="TL"):
    sb = get_client()
    res = sb.table("cekler").select("*").eq("para_birimi", para_birimi).order("vade").execute()
    return res.data or []


def cek_sil_hepsi(para_birimi=None):
    """
    Çekleri siler.
    - para_birimi="TL" → Sadece TL çekleri siler
    - para_birimi="USD" → Sadece USD çekleri siler
    - para_birimi=None → TÜM çekleri siler
    """
    sb = get_client()
    if para_birimi:
        sb.table("cekler").delete().eq("para_birimi", para_birimi).execute()
    else:
        sb.table("cekler").delete().neq("id", 0).execute()
        _cache_temizle()


def cek_sil(cek_id):
    """Tek bir çeki siler."""
    sb = get_client()
    sb.table("cekler").delete().eq("id", cek_id).execute()
    _cache_temizle()


def cek_ekle_bulk(cekler, para_birimi="TL", temizle_onceki=True):
    """
    Çekleri toplu ekler.

    ÖNEMLİ: Varsayılan olarak (temizle_onceki=True), yüklemeden önce aynı
    para birimindeki TÜM eski çekleri siler. Bu sayede aynı Excel'i
    defalarca yüklesen bile duplicate oluşmaz.

    Eğer mevcut çeklerin üzerine eklemek istersen: temizle_onceki=False geç.
    """
    sb = get_client()

    # Ekleyeceğimiz çekler boşsa hiçbir şey yapma (yanlışlıkla tüm kayıtları silmeyelim)
    if not cekler:
        return

    # 1) Önce bu para birimindeki eski kayıtları temizle
    if temizle_onceki:
        sb.table("cekler").delete().eq("para_birimi", para_birimi).execute()

    # 2) Sonra yeni kayıtları ekle
    rows = []
    for c in cekler:
        rows.append({
            "ref_no": _str(c.get("ref_no")),
            "cek_no": _str(c.get("cek_no")),
            "tarih": _vade(c.get("tarih")),
            "vade": _vade(c.get("vade")),
            "meblagh": _temizle(c.get("meblagh")) or 0,
            "odenen": _temizle(c.get("odenen")) or 0,
            "kalan": _temizle(c.get("kalan")) or 0,
            "durum": _str(c.get("durum")) or "Bekliyor",
            "ch_kodu": _str(c.get("ch_kodu")),
            "ch_ismi": _str(c.get("ch_ismi")),
            "banka": _str(c.get("banka")),
            "sube": _str(c.get("sube")),
            "hesap_no": _str(c.get("hesap_no")),
            "para_birimi": _str(c.get("para_birimi")) or para_birimi,
        })
    BATCH = 25
    for i in range(0, len(rows), BATCH):
        sb.table("cekler").insert(rows[i:i+BATCH]).execute()
        _cache_temizle()


# ════════════════════════════════════════════════════════════════════
# VİRMANLAR (Bankalar Arası Para Transferi)
# ════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def get_virmanlar(limit=50):
    """Son virmanları döndürür (yenisiyle eskisine göre sıralı)."""
    sb = get_client()
    try:
        res = sb.table("virmanlar").select("*").order("id", desc=True).limit(limit).execute()
        return res.data or []
    except Exception:
        return []


def virman_yap(kaynak_banka_id, hedef_banka_id, tutar, aciklama="", kur_kullanilan=None):
    """
    Bankalar arası para transferi yapar:
    1) Kaynak banka bakiyesinden düşer
    2) Hedef banka bakiyesine ekler (kur dönüşümü ile gerekirse)
    3) virmanlar tablosuna kayıt atar
    Returns: (basarili: bool, mesaj: str)
    """
    sb = get_client()

    if kaynak_banka_id == hedef_banka_id:
        return False, "Kaynak ve hedef banka aynı olamaz"

    if not tutar or float(tutar) <= 0:
        return False, "Tutar 0'dan büyük olmalı"

    tutar = float(tutar)

    # Bankaları al
    try:
        kaynak_res = sb.table("bankalar").select("*").eq("id", kaynak_banka_id).execute()
        hedef_res = sb.table("bankalar").select("*").eq("id", hedef_banka_id).execute()
        if not kaynak_res.data or not hedef_res.data:
            return False, "Banka bulunamadı"
        kaynak = kaynak_res.data[0]
        hedef = hedef_res.data[0]
    except Exception as e:
        return False, f"Banka bilgisi alınamadı: {e}"

    kaynak_pb = kaynak["para_birimi"]
    hedef_pb = hedef["para_birimi"]

    # Bakiye yeterli mi?
    if float(kaynak["bakiye"]) < tutar:
        return False, f"Yetersiz bakiye. {kaynak['hesap_adi']} hesabında {float(kaynak['bakiye']):.2f} {kaynak_pb} var"

    # Hedefe gidecek tutar (kur dönüşümü)
    hedef_tutar = tutar  # aynı para birimi ise direkt
    if kaynak_pb != hedef_pb and kur_kullanilan:
        kur = float(kur_kullanilan)
        if kur <= 0:
            return False, "Geçersiz kur"
        if kaynak_pb == "TL" and hedef_pb == "USD":
            hedef_tutar = tutar / kur
        elif kaynak_pb == "USD" and hedef_pb == "TL":
            hedef_tutar = tutar * kur
        elif kaynak_pb == "EUR" and hedef_pb == "TL":
            hedef_tutar = tutar * kur  # basitleştirilmiş
        # Diğer kombinasyonlar için kullanıcı kuru manuel girer
    elif kaynak_pb != hedef_pb:
        return False, "Farklı para birimleri arası virman için kur gerekli"

    # ─── Bakiye güncellemeleri ───
    try:
        yeni_kaynak_bakiye = float(kaynak["bakiye"]) - tutar
        yeni_hedef_bakiye = float(hedef["bakiye"]) + hedef_tutar

        sb.table("bankalar").update({"bakiye": yeni_kaynak_bakiye}).eq("id", kaynak_banka_id).execute()
        sb.table("bankalar").update({"bakiye": yeni_hedef_bakiye}).eq("id", hedef_banka_id).execute()
    except Exception as e:
        return False, f"Bakiye güncellenemedi: {e}"

    # ─── Virman kaydı ekle (varsa) ───
    try:
        sb.table("virmanlar").insert({
            "kaynak_banka_id": kaynak_banka_id,
            "hedef_banka_id": hedef_banka_id,
            "kaynak_hesap_adi": kaynak["hesap_adi"],
            "hedef_hesap_adi": hedef["hesap_adi"],
            "kaynak_para_birimi": kaynak_pb,
            "hedef_para_birimi": hedef_pb,
            "tutar": tutar,
            "hedef_tutar": hedef_tutar,
            "kur_kullanilan": float(kur_kullanilan) if kur_kullanilan else None,
            "aciklama": aciklama,
            "tarih": tr_today_iso(),
        }).execute()
    except Exception:
        # virmanlar tablosu yoksa virman yine yapıldı, sadece kayıt tutulmadı
        pass

    _cache_temizle()
    return True, f"✅ {tutar:.2f} {kaynak_pb} → {hedef_tutar:.2f} {hedef_pb} virman tamamlandı"


def virman_geri_al(virman_id):
    """
    Virmanı geri alır:
    1) virman kaydını al
    2) Hedef bankadan eklenen tutarı düş
    3) Kaynak bankaya tutarı iade et
    4) Virman kaydını sil
    """
    sb = get_client()

    try:
        v_res = sb.table("virmanlar").select("*").eq("id", virman_id).execute()
        if not v_res.data:
            return False, "Virman bulunamadı"
        v = v_res.data[0]
    except Exception as e:
        return False, f"Virman bilgisi alınamadı: {e}"

    try:
        # Hedef banka bakiyesinden geri al
        hedef_res = sb.table("bankalar").select("*").eq("id", v["hedef_banka_id"]).execute()
        if hedef_res.data:
            hedef = hedef_res.data[0]
            yeni_hedef = float(hedef["bakiye"]) - float(v["hedef_tutar"])
            sb.table("bankalar").update({"bakiye": yeni_hedef}).eq("id", v["hedef_banka_id"]).execute()

        # Kaynak bankaya iade et
        kaynak_res = sb.table("bankalar").select("*").eq("id", v["kaynak_banka_id"]).execute()
        if kaynak_res.data:
            kaynak = kaynak_res.data[0]
            yeni_kaynak = float(kaynak["bakiye"]) + float(v["tutar"])
            sb.table("bankalar").update({"bakiye": yeni_kaynak}).eq("id", v["kaynak_banka_id"]).execute()

        # Virman kaydını sil
        sb.table("virmanlar").delete().eq("id", virman_id).execute()
        return True, "✅ Virman geri alındı"
    except Exception as e:
        _cache_temizle()
        return False, f"Geri alma hatası: {e}"


# ════════════════════════════════════════════════════════════════════
# AKTİF EXCEL VERİLERİ (Toplam Aktifler sayfası için kalıcı kayıt)
# ════════════════════════════════════════════════════════════════════
def aktif_excel_kaydet(kullanici, dosya_tipi, veri_json):
    """
    Excel parse sonuçlarını Supabase'e PAYLAŞIMLI olarak kaydeder.
    Her kullanıcı (ibrahim, cem...) aynı veriyi görür.
    Son yükleyen kullanıcının verisi geçerli olur.
    Parametre: kullanici (artık sadece kim yüklediğini loglamak için, filtre için değil)
    """
    sb = get_client()
    try:
        SHARED_KEY = "_SHARED_"
        # Önce eski kaydı sil
        sb.table("aktif_excel_verileri").delete().eq("kullanici", SHARED_KEY).eq("dosya_tipi", dosya_tipi).execute()
        # Yeni kayıt ekle (paylaşımlı key ile, ama son yükleyen bilgisini açıklamada tut)
        import json
        sb.table("aktif_excel_verileri").insert({
            "kullanici": SHARED_KEY,
            "dosya_tipi": dosya_tipi,
            "veri_json": json.dumps({
                "veri": veri_json,
                "son_yukleyen": kullanici,
                "yukleme_zamani": str(tr_now()),
            }),
        }).execute()
        return True
    except Exception:
        _cache_temizle()
        return False


@st.cache_data(ttl=300, show_spinner=False)
def aktif_excel_oku(kullanici, dosya_tipi):
    """
    Paylaşımlı Excel verisini okur (kullanici parametresi göz ardı edilir).
    Eski format (sadece veri) ve yeni format (veri + meta) ikisini de destekler.
    """
    sb = get_client()
    try:
        SHARED_KEY = "_SHARED_"
        # Önce paylaşımlı kaydı dene
        res = sb.table("aktif_excel_verileri").select("*").eq("kullanici", SHARED_KEY).eq("dosya_tipi", dosya_tipi).execute()
        if res.data:
            import json
            payload = json.loads(res.data[0]["veri_json"])
            # Yeni format: {veri, son_yukleyen, yukleme_zamani}
            if isinstance(payload, dict) and "veri" in payload and "son_yukleyen" in payload:
                return payload["veri"]
            # Eski format: direkt veri
            return payload

        # Geriye dönük uyumluluk: eski (kullanıcıya bağlı) kayıtları da kontrol et
        res2 = sb.table("aktif_excel_verileri").select("*").eq("kullanici", kullanici).eq("dosya_tipi", dosya_tipi).execute()
        if res2.data:
            import json
            return json.loads(res2.data[0]["veri_json"])
        return None
    except Exception:
        return None


@st.cache_data(ttl=15, show_spinner=False)
def aktif_excel_meta_oku(dosya_tipi):
    """
    Excel meta bilgisi okur: son_yukleyen, yukleme_zamani
    Returns: dict | None
    """
    sb = get_client()
    try:
        SHARED_KEY = "_SHARED_"
        res = sb.table("aktif_excel_verileri").select("*").eq("kullanici", SHARED_KEY).eq("dosya_tipi", dosya_tipi).execute()
        if res.data:
            import json
            payload = json.loads(res.data[0]["veri_json"])
            if isinstance(payload, dict) and "son_yukleyen" in payload:
                return {
                    "son_yukleyen": payload.get("son_yukleyen"),
                    "yukleme_zamani": payload.get("yukleme_zamani"),
                }
        return None
    except Exception:
        return None


def aktif_excel_sil(kullanici, dosya_tipi=None):
    """Paylaşımlı Excel verilerini siler. dosya_tipi None ise tümünü siler."""
    sb = get_client()
    try:
        SHARED_KEY = "_SHARED_"
        # Hem paylaşımlı hem eski kayıtları temizle
        q = sb.table("aktif_excel_verileri").delete().eq("kullanici", SHARED_KEY)
        if dosya_tipi:
            q = q.eq("dosya_tipi", dosya_tipi)
        q.execute()
        # Eski kullanıcı bağlı kayıtlar varsa onları da temizle
        try:
            q2 = sb.table("aktif_excel_verileri").delete().eq("kullanici", kullanici)
            if dosya_tipi:
                q2 = q2.eq("dosya_tipi", dosya_tipi)
            q2.execute()
        except Exception:
            pass
        return True
    except Exception:
        _cache_temizle()
        return False


# ════════════════════════════════════════════════════════════════════
# TOPLAM AKTİF MANUEL DÜZELTMELERİ
# ════════════════════════════════════════════════════════════════════
def aktif_manuel_ekle(kullanici, aciklama, tutar, para_birimi="USD", tip="ekle"):
    """
    Manuel ekleme/çıkarma kaydı (PAYLAŞIMLI - tüm yetkili kullanıcılar görür).
    tip: 'ekle' (toplam aktife ekle) | 'cikar' (toplam aktiften çıkar)
    kullanici parametresi: kim eklediği bilgisi için (filtreleme için değil)
    """
    sb = get_client()
    try:
        sb.table("aktif_manuel_kalemler").insert({
            "kullanici": kullanici,  # kim eklediği bilgisi
            "aciklama": aciklama,
            "tutar": float(tutar),
            "para_birimi": para_birimi,
            "tip": tip,
        }).execute()
        return True
    except Exception:
        _cache_temizle()
        return False


@st.cache_data(ttl=15, show_spinner=False)
def aktif_manuel_listele(kullanici=None):
    """
    TÜM manuel kalemleri döndürür (paylaşımlı).
    kullanici parametresi geriye dönük uyumluluk için var, kullanılmıyor.
    """
    sb = get_client()
    try:
        res = sb.table("aktif_manuel_kalemler").select("*").order("id", desc=True).execute()
        return res.data or []
    except Exception:
        return []


def aktif_manuel_sil(kalem_id):
    """Bir manuel kalemi sil."""
    sb = get_client()
    try:
        sb.table("aktif_manuel_kalemler").delete().eq("id", kalem_id).execute()
        return True
    except Exception:
        _cache_temizle()
        return False


@st.cache_data(ttl=300, show_spinner=False)
def get_cek_toplamlari():
    """
    Sistemdeki TAHSİL EDİLMEMİŞ (henüz nakde çevrilmemiş) çeklerin
    para birimine göre kalan tutarlarını ve adetlerini döndürür.

    "Ödenmiş" sayılma kuralları (DAHİL EDİLMEZ):
    - Durum: Ödendi / Tahsil Edildi / İptal / Portföyden Çıktı
    - Tamamen ödenmiş: meblagh ≈ odenen (ya da kalan ≤ 0)

    "Ciro Edildi" durumundakiler DAHİL EDİLİR (hala borç anlamında).
    Returns: (toplam_tl, toplam_usd, adet_tl, adet_usd)
    """
    sb = get_client()

    # Türkçe karakter normalize (Python upper(İ→I) sorunu için)
    def _tr_norm(s):
        if not s: return ""
        s = str(s)
        for tr, en in [("İ","i"),("I","i"),("Ş","s"),("ş","s"),("Ç","c"),("ç","c"),
                       ("Ğ","g"),("ğ","g"),("Ü","u"),("ü","u"),("Ö","o"),("ö","o"),("ı","i")]:
            s = s.replace(tr, en)
        return s.lower().strip()

    ODENDI_SET = {"odendi", "tahsil edildi", "tahsil", "iptal", "portfoyden cikti"}

    try:
        res = sb.table("cekler").select("*").execute()
        toplam_tl = 0.0
        toplam_usd = 0.0
        adet_tl = 0
        adet_usd = 0
        for c in res.data or []:
            try:
                # 1) Durumdan tahsil edilmiş/iptal çekleri atla
                if _tr_norm(c.get("durum")) in ODENDI_SET:
                    continue

                # 2) Tutarları al ve gerçek kalan hesapla
                meblag = float(c.get("meblagh") or c.get("meblag") or 0)
                odenen = float(c.get("odenen") or 0)
                kalan_kolon = c.get("kalan")

                # Gerçek kalan: meblagh - odenen (kalan kolonu yanıltıcı olabilir)
                gercek_kalan = meblag - odenen

                # 3) Tamamen ödenmiş (1 cent toleransla)
                if gercek_kalan <= 0.01:
                    continue

                # Kalan kolon dolu ve mantıklıysa onu kullan, değilse hesapla
                try:
                    kalan_v = float(kalan_kolon) if kalan_kolon else gercek_kalan
                    # Eğer kolon değeri meblag'a eşitse muhtemelen hiç güncellenmemiş — gerçek kalanı kullan
                    if kalan_v == meblag and odenen > 0:
                        kalan_v = gercek_kalan
                except (TypeError, ValueError):
                    kalan_v = gercek_kalan

                if kalan_v <= 0.01:
                    continue

                pb = (c.get("para_birimi") or "TL").upper().strip()
                if pb == "USD":
                    toplam_usd += kalan_v
                    adet_usd += 1
                else:
                    toplam_tl += kalan_v
                    adet_tl += 1
            except (TypeError, ValueError):
                pass
        return toplam_tl, toplam_usd, adet_tl, adet_usd
    except Exception:
        return 0.0, 0.0, 0, 0


def get_cari_isimler():
    """Muhasebe'ye yüklenen cari Excel'indeki 'Hesap adı' listesi (Satış kanal/firma seçimi için).
    Liste yoksa boş döner."""
    try:
        v = aktif_excel_oku("ortak", "cari_isimler")
        if isinstance(v, list):
            return sorted({str(x).strip() for x in v if str(x).strip()}, key=lambda s: s.lower())
    except Exception:
        pass
    return []


# ── Sistem ayarı / snapshot (Yönetim panosu için) ──────────────────
def set_ayar(anahtar, deger):
    """sistem_ayarlari tablosuna JSON değer yazar (anahtar bazlı upsert)."""
    import json as _json
    from datetime import datetime as _dt, timedelta as _td
    # guncelleme_tarihi: ISO format (YYYY-MM-DD HH:MM:SS) — Postgres timestamp ile uyumlu.
    # Türkçe format (28.06.2026) timestamp kolonunda 'out of range' hatası verir.
    _zaman = (_dt.utcnow() + _td(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        get_client().table("sistem_ayarlari").upsert(
            {"anahtar": anahtar,
             "deger": _json.dumps(deger, ensure_ascii=False),
             "guncelleme_tarihi": _zaman},
            on_conflict="anahtar").execute()
        return True
    except Exception as e:
        try:
            st.session_state["_son_ayar_hata"] = f"{type(e).__name__}: {str(e)[:300]}"
        except Exception:
            pass
        return False


def get_ayar(anahtar, varsayilan=None):
    """sistem_ayarlari'ndan JSON değer okur."""
    import json as _json
    try:
        res = get_client().table("sistem_ayarlari").select("deger").eq("anahtar", anahtar).execute()
        rows = res.data or []
        if not rows:
            return varsayilan
        return _json.loads(rows[0]["deger"])
    except Exception:
        return varsayilan


# ── Günlük kur (tarihsel kur — Yönetim P&L için) ─────────────────────
def kur_kaydet(tarih, kur):
    """O günün USD/TL kurunu kur_gunluk tablosuna yazar (idempotent, günde 1 kayıt)."""
    try:
        if not kur or float(kur) <= 1:
            return False
        get_client().table("kur_gunluk").upsert(
            {"tarih": str(tarih)[:10], "usd_try": float(kur)},
            on_conflict="tarih").execute()
        return True
    except Exception:
        return False


def get_kur_araligi(baslangic, bitis):
    """Dönem [baslangic, bitis] aralığındaki günlük kurları döndürür:
    {'2026-06-28': 38.5, ...}. Tablo yoksa/boşsa {} döner."""
    try:
        res = get_client().table("kur_gunluk").select("tarih,usd_try") \
            .gte("tarih", str(baslangic)[:10]).lte("tarih", str(bitis)[:10]).execute()
        rows = res.data or []
        return {str(r["tarih"])[:10]: float(r["usd_try"])
                for r in rows if r.get("usd_try")}
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def get_tum_odemeler():
    """Tüm haftalardaki tüm ödeme kayıtları — cari ekstre + vade yaşlandırma için.
    Dönen kayıt kolonları: firma, aciklama, cari_banka, vade, tutar_tl, tutar_usd, kategori, durum, hafta_id."""
    try:
        res = get_client().table("odemeler").select("*").order("vade").execute()
        return res.data or []
    except Exception:
        return []
