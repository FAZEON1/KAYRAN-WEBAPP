# -*- coding: utf-8 -*-
"""Firma bazlı Referans No + Havuz Bütçe (sellout / marketing destek) modülü.

Ref no formatı:  FZ<KOD>RF<YIL><SIRA:03d>   ör. FZVTNRF2025001

Havuz Bütçe mantığı:
  - TÜR = "BÜTÇE"  → önden verilen bütçe (GİRİŞ +)
  - Diğer türler   → sellout / destek harcaması (HARCAMA −)
  - Kalan havuz    = toplam giriş − toplam harcama
"""
from shared.tasarim import renk as trenk  # aktif temanın rengi (hex)
from shared.cop_kutusu import cop_kutusu_kapali  # birleştirme / sil-yeniden-yaz çöp kutusuna düşmesin
from shared.tasarim import tr_sayi  # TR sayı biçimi (1.234,56)
import re
import pandas as pd
import streamlit as st
from datetime import date, datetime

from .database import get_client, _rows, _cache_temizle
from shared.utils import metrik_satiri, normalize_tr

DURUMLAR = ["beklemede", "paylasildi", "iptal"]
DOVIZLER = ["USD", "TL", "EUR"]

# Türkçe ay adı → ay numarası (İ/I uyumlu)
_AY_NO = {"OCAK": 1, "SUBAT": 2, "MART": 3, "NISAN": 4, "MAYIS": 5, "HAZIRAN": 6,
          "TEMMUZ": 7, "AGUSTOS": 8, "EYLUL": 9, "EKIM": 10, "KASIM": 11, "ARALIK": 12}
_AY_AD = {1: "OCAK", 2: "ŞUBAT", 3: "MART", 4: "NİSAN", 5: "MAYIS", 6: "HAZİRAN",
          7: "TEMMUZ", 8: "AĞUSTOS", 9: "EYLÜL", 10: "EKİM", 11: "KASIM", 12: "ARALIK"}

# Ekranlarda görülen yaygın kategoriler (dropdown başlangıç seti).
# Sistemdeki mevcut kategoriler bunlara EKLENİR (kaybolmaz), liste dinamik büyür.
_VARSAYILAN_KATEGORILER = [
    "GENEL", "MONİTÖR", "EKRAN KARTI", "BİLGİSAYAR KASASI", "KABLO",
    "SOĞUTUCU", "GENEL SİSTEM", "SELLOUT", "MARKETING", "SPIFF", "KAMPANYA",
]


@st.cache_data(ttl=120, show_spinner=False)
def _urun_kategorileri():
    """Sisteme kayıtlı ürünlerin kategorileri — Kampanya Takip ile AYNI kaynak.
    Kampanya Takip dropdown'ı da 'urunler' tablosundaki 'kategori' alanından
    (tr_kucuk normalize + benzersiz + sıralı) besleniyor; birebir aynısı."""
    try:
        from shared.utils import tr_kucuk as _tk
        from .database import _hepsi as _hepsi_k
        rows = _hepsi_k("urunler", "kategori", "sku")
        return sorted({_tk(r.get("kategori")) for r in rows if _tk(r.get("kategori"))})
    except Exception:
        return []


def _kategori_listesi(refler=None):
    """Ref No kategori dropdown'ı. BİRİNCİL kaynak Kampanya Takip ile aynı:
    ürünlerin kategorileri (urunler tablosu). Ayrıca ref'lerde geçmiş kategoriler
    de eklenir (kaybolmasın). Hepsi Türkçe-büyük harfe normalize + tekil.
    Ürün kategorisi hiç yoksa varsayılan sete düşülür (boş dropdown olmasın)."""
    out = []
    for k in _urun_kategorileri():                     # Kampanya Takip kaynağı (birincil)
        ku = kategori_kanonik(k)
        if ku and ku not in out:
            out.append(ku)
    if not out:                                        # hiç ürün kategorisi yoksa
        out = list(_VARSAYILAN_KATEGORILER)
    for r in (refler or []):                            # ref'lerde geçmiş kategoriler
        ku = kategori_kanonik(r.get("kategori"))
        if ku and ku not in out:
            out.append(ku)
    return out


def _ay_no(ad):
    s = str(ad or "").strip()
    for a, b in (("İ", "I"), ("ı", "I"), ("Ş", "S"), ("ş", "S"), ("Ğ", "G"), ("ğ", "G"),
                 ("Ü", "U"), ("ü", "U"), ("Ö", "O"), ("ö", "O"), ("Ç", "C"), ("ç", "C")):
        s = s.replace(a, b)
    s = s.upper()
    if s.isdigit() and 1 <= int(s) <= 12:
        return int(s)
    return _AY_NO.get(s, 0)


def _tr_upper(s):
    """Türkçe-farkında büyük harf: i→İ, ı→I. Kategori tutarlılığı için
    ('monitör' → 'MONİTÖR', varsayılan listeyle eşleşsin)."""
    s = str(s or "")
    return (s.replace("i", "İ").replace("ı", "I").replace("ğ", "Ğ")
             .replace("ü", "Ü").replace("ş", "Ş").replace("ö", "Ö").replace("ç", "Ç")).upper()


def _kat_anahtar(s):
    """Karşılaştırma anahtarı: Türkçe büyük harf + TÜM boşluklar atılmış.
    'MOUSEPAD', 'Mouse Pad', 'mouse  pad' → 'MOUSEPAD'."""
    return re.sub(r"\s+", "", _tr_upper(s))


def _katalog_haritasi():
    """{boşluksuz anahtar: kanonik ad} — ürün kataloğundan (KATEGORI_LISTE).
    Elle alias listesi YOK; katalog neyse o."""
    try:
        from .database import KATEGORI_LISTE
    except Exception:
        return {}
    return {_kat_anahtar(k): _tr_upper(k).strip() for k in KATEGORI_LISTE}


def kategori_kanonik(ad):
    """Kategori adını tek bir kanonik yazıma indirir.
    - Katalogdaki bir kategoriyle boşluksuz eşleşirse → katalog yazımı (TR büyük harf)
    - Eşleşmezse → kendi adı (TR büyük harf, fazla boşluklar tekilleştirilmiş)
    Belirsiz adlar (ör. 'SOĞUTUCU') tahmin edilmez, olduğu gibi kalır."""
    s = re.sub(r"\s+", " ", _tr_upper(ad)).strip()
    if not s:
        return ""
    return _katalog_haritasi().get(_kat_anahtar(s), s)



def _ay_no_coz(ad):
    """Ay adını numaraya çevirir — Türkçe karakterli (ŞUBAT, HAZİRAN) dahil.
    _AY_AD (görüntü adları) ve _AY_NO (ASCII) ikisini de dener."""
    s = str(ad or "").strip().upper()
    if not s:
        return 0
    for no, adx in _AY_AD.items():          # ŞUBAT, HAZİRAN gibi tam adlar
        if adx == s:
            return no
    return _ay_no(s)                         # ASCII fallback (SUBAT vb.)


def _aylik_ozet(r):
    """Ref kaydının aylık kırılımından (Ay, Yıl) görüntü metinleri üretir.
    Örn. aylik={"2025-03":x,"2025-04":y} → ("MART · NİSAN", "2025")."""
    a = r.get("aylik") or {}
    if isinstance(a, str):
        try:
            import json
            a = json.loads(a)
        except Exception:
            a = {}
    aylar, yillar = [], []
    if isinstance(a, dict):
        for k in sorted(a.keys()):
            try:
                y, m = str(k).split("-")[:2]
                _ad = _AY_AD.get(int(m), "")
                if _ad and _ad not in aylar:
                    aylar.append(_ad)
                if y not in yillar:
                    yillar.append(y)
            except Exception:
                continue
    _yil = " · ".join(yillar) if yillar else str(r.get("yil") or "")
    return (" · ".join(aylar) if aylar else "—"), (_yil or "—")
DURUM_ETIKET = {
    "beklemede": "⏳ Beklemede (paylaşılmadı)",
    "paylasildi": "✅ Paylaşıldı",
    "iptal": "🚫 İptal",
}

# Havuz bütçe türleri (BÜTÇE = giriş; diğerleri = harcama)
BUTCE_TURLER = ["BÜTÇE", "KAMPANYA", "REBATE", "STOK KORUMA", "KREDİ KARTI",
                "BİRLİKTE SATIŞ", "BEDELSİZ ÜRÜN", "MARKETING", "PAZARLAMA"]
GIRIS_TURLER = {"BÜTÇE"}


# ════════════════════════════════════════════════════════════════════
#  ALINAN DESTEKLER — firmalardan/markalardan bize gelen sellout,
#  marketing, rebate vb. gelirler. AY (dönem) bazında tutulur ve
#  kârlılığa GELİR olarak eklenir. ref_butce'den ayrı tutulur ki
#  havuz bakiye hesapları bozulmasın.
# ════════════════════════════════════════════════════════════════════
ALINAN_TURLER = ["SELLOUT", "MARKETING", "REBATE", "PRICE PROTECTION",
                 "PAZARLAMA", "BEDELSİZ ÜRÜN", "DİĞER"]

_ALINAN_SQL = """create table if not exists alinan_destekler (
  id bigint generated always as identity primary key,
  firma text, tur text, donem text,
  tutar numeric, doviz text default 'USD',
  fatura_no text, aciklama text, kategori text,
  created_at timestamptz default now());"""


def _donem_parse(v):
    """'2026-07', '07.2026', '07/2026', tarih, datetime → 'YYYY-MM' (yoksa None)."""
    if v is None:
        return None
    if isinstance(v, (date, datetime)):
        return f"{v.year:04d}-{v.month:02d}"
    s = str(v).strip()
    m = re.match(r"^(\d{4})[-/.](\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}"
    m = re.match(r"^(\d{1,2})[-/.](\d{4})$", s)
    if m:
        return f"{int(m.group(2)):04d}-{int(m.group(1)):02d}"
    m = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", s)  # gg.aa.yyyy
    if m:
        return f"{int(m.group(3)):04d}-{int(m.group(2)):02d}"
    return None


def alinan_destek_ekle(firma, tur, donem, tutar, doviz="USD",
                       fatura_no="", aciklama="", kategori=""):
    """Returns (ok, msg). Tablo yoksa msg içinde kurulum SQL ipucu döner."""
    d = _donem_parse(donem)
    if not d:
        return False, "Dönem anlaşılamadı (örn: 2026-07)"
    if not tutar or _f(tutar) <= 0:
        return False, "Tutar 0'dan büyük olmalı"
    try:
        get_client().table("alinan_destekler").insert({
            "firma": (firma or "").strip(), "tur": (tur or "DİĞER").strip().upper(),
            "donem": d, "tutar": _f(tutar),
            "doviz": (doviz or "USD").strip().upper(),
            "fatura_no": (fatura_no or "").strip(),
            "aciklama": (aciklama or "").strip(),
            "kategori": (kategori or "").strip(),
        }).execute()
        _cache_temizle()
        return True, "✅ Alınan destek kaydedildi"
    except Exception as e:
        es = str(e)
        if "kategori" in es and "column" in es.lower():
            # kategori kolonu henüz yok → kolonsuz kaydet, kullanıcıyı bilgilendir
            try:
                get_client().table("alinan_destekler").insert({
                    "firma": (firma or "").strip(), "tur": (tur or "DİĞER").strip().upper(),
                    "donem": d, "tutar": _f(tutar),
                    "doviz": (doviz or "USD").strip().upper(),
                    "fatura_no": (fatura_no or "").strip(),
                    "aciklama": (aciklama or "").strip(),
                }).execute()
                _cache_temizle()
                return True, ("✅ Kaydedildi (kategori HARİÇ — tabloya kolon ekleyin: "
                              "`alter table alinan_destekler add column kategori text;`)")
            except Exception as e2:
                return False, f"Kaydedilemedi: {e2}"
        if "alinan_destekler" in es:
            return False, ("`alinan_destekler` tablosu bulunamadı. Supabase → "
                           "SQL Editor'de şunu bir kez çalıştırın:\n" + _ALINAN_SQL)
        return False, f"Kaydedilemedi: {e}"


@st.cache_data(ttl=60, show_spinner=False)
def get_alinan_destekler(yil=None):
    try:
        q = get_client().table("alinan_destekler").select("*")
        if yil:
            q = q.gte("donem", f"{yil}-01").lte("donem", f"{yil}-12")
        return (q.order("donem", desc=True).order("id", desc=True)
                .execute().data) or []
    except Exception:
        return []


def alinan_destek_sil(rid):
    try:
        get_client().table("alinan_destekler").delete().eq("id", rid).execute()
        _cache_temizle()
        return True
    except Exception:
        return False


@st.cache_data(ttl=3600, show_spinner=False)
def _eur_usd_kur():
    """1 EUR kaç USD — mevcut kur API'sinden (open.er-api.com). Alınamazsa 1.08.
    HIZ: saatlik önbellek. Eskiden EUR kaydı olan her ekran çiziminde internete
    gidiyordu (6 sn zaman aşımı; ağ yavaşsa sayfa 6 sn donuyordu)."""
    try:
        import requests
        d = requests.get("https://open.er-api.com/v6/latest/EUR", timeout=6).json()
        v = float(d["rates"]["USD"])
        return v if 0.5 < v < 2.5 else 1.08
    except Exception:
        return 1.08


def _alinan_kur():
    """TL→USD çevrimi için güncel kur (bulunamazsa None)."""
    try:
        from kayranacc.database import get_kur
        k = float(get_kur() or 0)
        return k if k > 0 else None
    except Exception:
        return None


def alinan_destek_aralik_usd(bas, bit):
    """[bas, bit] tarih aralığıyla KESİŞEN AYLARIN alınan destek toplamı (USD).
    Ay-bazlı gelir mantığı: aralık ayın herhangi bir gününü kapsıyorsa o ayın
    tamamı dahildir. TL kayıtlar güncel kurla çevrilir; kur yoksa atlanır."""
    b = _donem_parse(bas)
    e = _donem_parse(bit)
    if not b or not e:
        return 0.0
    kur = None
    toplam = 0.0
    for r in get_alinan_destekler():
        d = r.get("donem") or ""
        if not (b <= d <= e):
            continue
        t = _f(r.get("tutar"))
        dv = (r.get("doviz") or "USD").upper()
        if dv in ("TL", "TRY", "₺"):
            if kur is None:
                kur = _alinan_kur()
            if not kur:
                continue
            t = t / kur
        elif dv in ("EUR", "EURO", "€"):
            # DÜZELTME: EUR eskiden 1:1 dolar sayılıyordu → gerçek kurla çevrilir
            t = t * _eur_usd_kur()
        toplam += t
    return toplam


def alinan_destek_kirilim_usd(bas, bit):
    """Aralıkla kesişen ayların alınan destekleri, USD, iki kırılımla:
    → (marka_dict, kategori_dict, toplam)
    marka = kayıttaki 'firma' alanı (BÜYÜK normalize), kategori = 'kategori'.
    Boş kategori 'GENEL' altında toplanır (dağıtılamayan destek)."""
    b = _donem_parse(bas)
    e = _donem_parse(bit)
    marka, kat, toplam = {}, {}, 0.0
    if not b or not e:
        return marka, kat, toplam
    kur = None
    for r in get_alinan_destekler():
        d = r.get("donem") or ""
        if not (b <= d <= e):
            continue
        t = _f(r.get("tutar"))
        dv = (r.get("doviz") or "USD").upper()
        if dv in ("TL", "TRY", "₺"):
            if kur is None:
                kur = _alinan_kur()
            if not kur:
                continue
            t = t / kur
        elif dv in ("EUR", "EURO", "€"):
            # DÜZELTME: EUR eskiden 1:1 dolar sayılıyordu → gerçek kurla çevrilir
            t = t * _eur_usd_kur()
        mk = (r.get("firma") or "").strip().upper() or "GENEL"
        kt = (r.get("kategori") or "").strip().upper() or "GENEL"
        marka[mk] = marka.get(mk, 0.0) + t
        kat[kt] = kat.get(kt, 0.0) + t
        toplam += t
    return marka, kat, toplam


def alinan_destek_ay_usd(yyyy_mm=None):
    """Tek ayın alınan destek toplamı (USD). Varsayılan: içinde bulunulan ay."""
    d = _donem_parse(yyyy_mm) if yyyy_mm else f"{date.today().year:04d}-{date.today().month:02d}"
    return alinan_destek_aralik_usd(d, d)


def alinan_destek_excel_ice_aktar(df):
    """Kolon ADIYLA eşleşen esnek içe aktarım.
    Beklenen başlıklar (büyük/küçük duyarsız): FİRMA | TÜR | DÖNEM | TUTAR |
    DÖVİZ | FATURA NO | AÇIKLAMA. Returns (eklenen, atlanan, hatalar[])."""
    kolmap = {}
    for c in df.columns:
        n = normalize_tr(str(c))
        if "firma" in n or "marka" in n:
            kolmap["firma"] = c
        elif n.startswith("tur") or "tür" in str(c).lower():
            kolmap["tur"] = c
        elif "donem" in n or "ay" == n:
            kolmap["donem"] = c
        elif "tutar" in n:
            kolmap["tutar"] = c
        elif "doviz" in n or "birim" in n:
            kolmap["doviz"] = c
        elif "fatura" in n:
            kolmap["fatura_no"] = c
        elif "kategori" in n:
            kolmap["kategori"] = c
        elif "aciklama" in n:
            kolmap["aciklama"] = c
    eksik = [k for k in ("firma", "donem", "tutar") if k not in kolmap]
    if eksik:
        return 0, 0, [f"Zorunlu kolon(lar) yok: {', '.join(eksik).upper()}"]
    eklenen, atlanan, hatalar = 0, 0, []
    for i, r in df.iterrows():
        firma = str(r.get(kolmap["firma"], "") or "").strip()
        donem = r.get(kolmap["donem"])
        tutar = _f(r.get(kolmap["tutar"]))
        if not firma or firma.lower() == "nan" or tutar <= 0 or not _donem_parse(donem):
            atlanan += 1
            continue
        ok, msg = alinan_destek_ekle(
            firma,
            str(r.get(kolmap.get("tur"), "") or "DİĞER"),
            donem, tutar,
            str(r.get(kolmap.get("doviz"), "") or "USD"),
            str(r.get(kolmap.get("fatura_no"), "") or "").replace("nan", ""),
            str(r.get(kolmap.get("aciklama"), "") or "").replace("nan", ""),
            str(r.get(kolmap.get("kategori"), "") or "").replace("nan", ""),
        )
        if ok:
            eklenen += 1
        else:
            hatalar.append(f"Satır {i + 2}: {msg}")
            if "tablosu bulunamadı" in msg:
                break
    return eklenen, atlanan, hatalar



def _yil():
    return datetime.now().year


def _yon_belirle(tur):
    return "giris" if _norm(tur) in {_norm(t) for t in GIRIS_TURLER} else "harcama"


def _import_yon(tur, kisi, tutar):
    """Excel içe aktarımında yön tahmini: gerçek havuz depozitosu =
    TÜR=BÜTÇE + kişi yok (SIFIRLANDI/boş) + tutar >= 50.000. Diğer her şey harcama."""
    k = str(kisi or "").strip().lower()
    kisi_yok = (k == "" or k == "nan" or "sifirland" in k or "sıfırland" in k)
    if _norm(tur) == _norm("BÜTÇE") and kisi_yok and abs(_f(tutar)) >= 50000:
        return "giris"
    return "harcama"


def ref_uret(kod, yil, sira):
    return f"FZ{kod}RF{yil}{int(sira):03d}"


def _parse_ref(ref):
    m = re.match(r"^FZ(.+?)RF(\d{4})(\d+)$", str(ref).strip())
    if not m:
        return None, None, None
    return m.group(1), int(m.group(2)), int(m.group(3))


def _f(v, d=0.0):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return d
        return float(str(v).replace(",", "").replace("$", "").strip())
    except Exception:
        return d


# ── FİRMA DB ────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_firmalar():
    try:
        sb = get_client()
        return _rows(sb.table("ref_firmalar").select("*").order("firma_adi").execute())
    except Exception:
        return []


def kod_dogrula(kod):
    """Ref kodu geçerli mi? (basarili, temiz_kod_veya_hata)

    NEDEN: Bir kayıtta firma_kodu alanına tam ref no yazılmış
    ('FZMNDRF2025001') → ref_uret() bunun başına FZ, sonuna RF+yıl+sıra
    ekleyince 'FZFZMNDRF2025001RF2025001' gibi bozuk numaralar üretiliyordu.
    Kod artık kaynağında doğrulanır."""
    k = str(kod or "").strip().upper()
    if not k:
        return False, "Ref kodu boş olamaz."
    if not re.fullmatch(r"[A-Z0-9]{2,6}", k):
        return False, ("Ref kodu 2-6 karakter olmalı, yalnız harf/rakam "
                       f"içerebilir (girilen: '{k}').")
    if k.startswith("FZ") or "RF" in k:
        return False, ("Ref kodu 'FZ' ile başlayamaz ve içinde 'RF' geçemez — "
                       "bunlar numaranın kendisine otomatik eklenir. "
                       "Sadece firma kısaltmasını yaz (örn. VTN, INC, MND).")
    return True, k


def firma_ekle(adi, kodu):
    ok, sonuc = kod_dogrula(kodu)
    if not ok:
        return False, f"❌ {sonuc}"
    try:
        sb = get_client()
        sb.table("ref_firmalar").insert(
            {"firma_adi": adi.strip(), "firma_kodu": sonuc}
        ).execute()
        _cache_temizle()
        return True, f"✅ '{adi}' firması eklendi (kod: {sonuc})."
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}"


def firma_guncelle(fid, adi, kodu):
    ok, sonuc = kod_dogrula(kodu)
    if not ok:
        return False, f"❌ {sonuc}"
    try:
        sb = get_client()
        sb.table("ref_firmalar").update(
            {"firma_adi": str(adi or "").strip(), "firma_kodu": sonuc}
        ).eq("id", fid).execute()
        _cache_temizle()
        return True, "✅ Firma güncellendi."
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}"


def firma_ref_sayisi(fid):
    """Firmaya bağlı ref no adedi — silmeden önce uyarmak için."""
    try:
        return len(_rows(get_client().table("ref_no").select("id")
                         .eq("firma_id", fid).execute()) or [])
    except Exception:
        return 0


def firma_sil(fid, refleri_de_sil=False):
    """Firmayı siler. refleri_de_sil=False iken bağlı ref no varsa SİLMEZ."""
    try:
        sb = get_client()
        _adet = firma_ref_sayisi(fid)
        if _adet and not refleri_de_sil:
            return False, (f"Bu firmaya bağlı {_adet} ref no var. Önce onları "
                           "sil ya da 'ref no'ları da sil' kutusunu işaretle.")
        if _adet and refleri_de_sil:
            sb.table("ref_no").delete().eq("firma_id", fid).execute()
        sb.table("ref_firmalar").delete().eq("id", fid).execute()
        # Silme gerçekten oldu mu?
        _kalan = _rows(sb.table("ref_firmalar").select("id").eq("id", fid).execute())
        if _kalan:
            return False, "Silme komutu hata vermedi ama firma hâlâ duruyor."
        _cache_temizle()
        return True, (f"✅ Firma silindi" + (f" ({_adet} ref no ile birlikte)." if _adet else "."))
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}"


# ── CARİ EŞLEŞTİRME (firma adları muhasebe cari isimlerinden gelir) ───
# rol → tespit anahtarları (ad/kod), cari ismi öneki, döviz tercihi
from shared.utils import FIRMA_GORUNEN_AD   # cari önekleri tek kaynak (Faz 4)
FIRMA_ESLESME = {
    "ITOPYA": {"tespit": ("ITOPYA", "ITP", "EERA"),     "onek": FIRMA_GORUNEN_AD["ITOPYA"], "doviz": None},
    "HB":     {"tespit": ("HB", "D-MARKET", "DMARKET", "HEPSIBURADA", "HEPSİBURADA"), "onek": FIRMA_GORUNEN_AD["HB"], "doviz": None},
    "VATAN":  {"tespit": ("VATAN", "VTN"),              "onek": FIRMA_GORUNEN_AD["VATAN"], "doviz": "USD"},
}


def _norm(s):
    """Türkçe karakter normalizasyonu — merkezi shared.utils.normalize_tr'a delege eder."""
    return normalize_tr(s)


def _firma_rol(f):
    """Bir firmayı (ad/kod) eşleştirme rolüne bağlar: ITOPYA / HB / VATAN / None.
    Türkçe karakterler normalize edilir (İTOPYA = ITOPYA, FZİTRF kodu = IT)."""
    ad = _norm(f.get("firma_adi"))
    kod = _norm(f.get("firma_kodu"))
    for rol, cfg in FIRMA_ESLESME.items():
        for t in cfg["tespit"]:
            tn = _norm(t)
            if tn == kod or tn in ad:
                return rol
    return None


# Cari listesine yanlışlıkla düşmüş, firma OLMAYAN değerler
# (eski okuyucu 'Döviz' sütununu okuduğu için listeye para birimleri doluyordu)
_CARI_GECERSIZ = {
    "DOVIZ", "DÖVIZ", "USD", "EUR", "TL", "TRY", "TRL", "GBP", "CHF", "JPY",
    "HESAP ADI", "HESAP KODU", "TOPLAM BORC", "TOPLAM BORÇ", "TOPLAM ALACAK",
    "TOPLAM BAKIYE", "TOPLAM BAKİYE", "TOPLAM", "NAN", "-", "—",
}


def _cari_gecerli_mi(ad):
    """Bu metin gerçek bir firma adı mı? (para birimi / başlık / çöp değil mi)"""
    a = str(ad or "").strip()
    if len(a) < 3:
        return False
    if a.upper().replace("İ", "I") in _CARI_GECERSIZ:
        return False
    if not any(ch.isalpha() for ch in a):
        return False
    return True


@st.cache_data(ttl=120, show_spinner=False)
def _cari_isimleri():
    """Firma adı havuzu — ÜÇ kaynağın birleşimi:

      1) Muhasebe cari isimleri (Toplam Aktifler'de yüklenen cari Excel'i)
      2) Satışlarda fiilen geçen kanal/firma adları  ← ana kaynak
      3) İthalat dosyalarındaki tedarikçiler

    NEDEN: Tek kaynağa (cari) bağlıyken liste boş ya da bozuk kalabiliyordu —
    oysa programda zaten yüzlerce satışta firma adı mevcut. Artık cari hiç
    yüklenmemiş olsa bile liste dolu gelir.

    Para birimi / başlık gibi firma olmayan değerler süzülür."""
    havuz, gorulen = [], set()

    def _ekle(isimler):
        for x in (isimler or []):
            sx = str(x or "").strip()
            if not sx or not _cari_gecerli_mi(sx):
                continue
            _k = _norm(sx)
            if _k in gorulen:
                continue
            gorulen.add(_k)
            havuz.append(sx)

    # 1) Muhasebe cari isimleri
    try:
        from kayranacc.database import get_cari_isimler
        _ekle(get_cari_isimler())
    except Exception:
        pass
    # 2) Satış kanalları (cari + satışta geçenleri zaten birleştirir)
    try:
        from satis.database import get_kanallar
        _ekle(get_kanallar())
    except Exception:
        pass
    # 3) İthalat tedarikçileri
    try:
        from ithalat.database import get_dosyalar
        _ekle([d.get("tedarikci") for d in (get_dosyalar() or [])])
    except Exception:
        pass
    return sorted(havuz, key=lambda x: x.lower())


def _cari_esle(onek, doviz, cariler):
    """Önek ile başlayan cari ismini bul; döviz verilmişse o dövizi içeren önceliklidir.
    Türkçe karakterler normalize edilir."""
    ou = _norm(onek)
    adaylar = [c for c in cariler if _norm(c).startswith(ou)]
    if not adaylar:
        adaylar = [c for c in cariler if ou in _norm(c)]
    if not adaylar:
        return None
    if doviz:
        dn = _norm(doviz)
        tercih = [c for c in adaylar if dn in _norm(c)]
        if tercih:
            return tercih[0]
    return adaylar[0]


@st.cache_data(ttl=120, show_spinner=False)
def firma_tam_cari_adi(kod):
    """Firma stok kodunu (ITOPYA, HB, VATAN) muhasebedeki TAM cari adına çevirir.
    Cari listesinde önekle (EERA / D-MARKET / VATAN) eşleşen tam adı bulur.
    Eşleşme yoksa öneki, eşleme tanımı da yoksa kodu olduğu gibi döndürür."""
    if not kod:
        return ""
    k = _norm(kod).strip()
    cfg = FIRMA_ESLESME.get(k)
    if not cfg:
        return str(kod).strip()
    cariler = _cari_isimleri()
    tam = _cari_esle(cfg["onek"], cfg.get("doviz"), cariler) if cariler else None
    return tam or cfg["onek"]


def _senkronize_firmalar():
    """Firma adlarını muhasebe cari isimleriyle eşitler (kodlar değişmez);
    AYNI role ait mükerrer firmaları tek hedefte birleştirir (ref no + havuz
    bütçe taşınır, boşalan firma silinir); HB'ye yanlış girilmiş havuz bütçeyi
    ITOPYA (EERA) firmasına taşır. İdempotent — tekrar çalışınca bozulmaz."""
    cariler = _cari_isimleri()
    if not cariler:
        return
    firmalar = get_firmalar()
    if not firmalar:
        return
    sb = get_client()
    degisti = False

    def _kayit_say(fid):
        try:
            r = len(_rows(sb.table("ref_kayitlari").select("id").eq("firma_id", fid).execute()))
            b = len(_rows(sb.table("ref_butce").select("id").eq("firma_id", fid).execute()))
            return r + b
        except Exception:
            return 0

    # Rol bazlı grupla
    rol_gruplari = {}
    for f in firmalar:
        rol = _firma_rol(f)
        if rol:
            rol_gruplari.setdefault(rol, []).append(f)

    rol_hedef = {}  # rol → hedef firma id
    for rol, flist in rol_gruplari.items():
        cfg = FIRMA_ESLESME[rol]
        hedef_ad = _cari_esle(cfg["onek"], cfg["doviz"], cariler)
        # Hedef: adı cari ismine eşit olan; yoksa en çok kayıtlı olan; yoksa ilk
        hedef = None
        if hedef_ad:
            hedef = next((f for f in flist
                          if (f.get("firma_adi") or "").strip() == hedef_ad.strip()), None)
        if hedef is None:
            hedef = max(flist, key=lambda f: _kayit_say(f["id"]))
        hedef_id = hedef["id"]
        rol_hedef[rol] = hedef_id

        # Hedef adını cari ismine güncelle
        if hedef_ad and (hedef.get("firma_adi") or "") != hedef_ad:
            try:
                sb.table("ref_firmalar").update({"firma_adi": hedef_ad}).eq("id", hedef_id).execute()
                degisti = True
            except Exception:
                pass

        # Mükerrer firmaları hedefe birleştir + sil (önce taşı, sonra sil)
        for f in flist:
            if f["id"] == hedef_id:
                continue
            try:
                sb.table("ref_kayitlari").update({"firma_id": hedef_id}).eq("firma_id", f["id"]).execute()
                sb.table("ref_butce").update({"firma_id": hedef_id}).eq("firma_id", f["id"]).execute()
                with cop_kutusu_kapali():
                    sb.table("ref_firmalar").delete().eq("id", f["id"]).execute()
                degisti = True
            except Exception:
                pass

    # HB → ITOPYA havuz bütçe taşıma (yanlış girilmiş kayıtlar)
    itopya_id = rol_hedef.get("ITOPYA")
    hb_id = rol_hedef.get("HB")
    if itopya_id and hb_id and itopya_id != hb_id:
        try:
            hb_butce = _rows(sb.table("ref_butce").select("id").eq("firma_id", hb_id).execute())
            if hb_butce:
                sb.table("ref_butce").update({"firma_id": itopya_id}).eq("firma_id", hb_id).execute()
                degisti = True
        except Exception:
            pass

    if degisti:
        _cache_temizle()


# ── REF NO DB ───────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_refler(firma_id):
    try:
        sb = get_client()
        return _rows(sb.table("ref_kayitlari").select("*")
                     .eq("firma_id", firma_id).order("sira_no").execute())
    except Exception:
        return []


def _sonraki_sira(firma_id):
    """Sıradaki numara — hem sira_no alanına HEM de ref_no metnine bakar.

    NEDEN: ref_no elle düzenlenebildiği için ikisi ayrışabilir (numara
    ...005 yapılır ama sira_no 2 kalır) → sistem sonraki numarayı 003 diye
    üretip MÜKERRER numara oluştururdu. Artık ikisinin de maksimumu alınır."""
    refler = get_refler(firma_id)
    _enb = max((int(r.get("sira_no") or 0) for r in refler), default=0)
    for r in refler:
        # 'FZITRF2026007' ve 'FZITRF2026007-FZITRF2026008' gibi tireli biçimler
        for parca in str(r.get("ref_no") or "").split("-"):
            _, _, _s = _parse_ref(parca.strip())
            if _s:
                _enb = max(_enb, int(_s))
    return _enb + 1


def ref_ekle(firma_id, kod, aciklama, durum="beklemede", tarih=None, yil=None, tutar=0, doviz="USD",
             kategori="", donem_ay=None, donem_yil=None):
    """Ref no atar. kategori: serbest metin (örn. SELLOUT). donem_ay/donem_yil:
    ref'in ait olduğu dönem — verilirse aylik alanına {YYYY-AA: tutar} yazılır
    (Ay/Yıl kolonları dolar). NOT: donem_yil ref NUMARASINI etkilemez;
    numara her zaman içinde bulunulan yıldan (yil) üretilir."""
    try:
        sb = get_client()
        sira = _sonraki_sira(firma_id)
        yil = yil or _yil()
        ref_no = ref_uret(kod, yil, sira)
        _kayit = {
            "firma_id": firma_id, "sira_no": sira, "ref_no": ref_no,
            "aciklama": aciklama or "", "durum": durum, "yil": yil,
            "tarih": str(tarih) if tarih else None,
            "paylasim_tarihi": str(tarih) if (durum == "paylasildi" and tarih) else None,
            "tutar": _f(tutar), "doviz": doviz or "USD",
        }
        if (kategori or "").strip():
            _kayit["kategori"] = kategori_kanonik(kategori)
        if donem_ay:
            import json as _json
            _dy = int(donem_yil or yil)
            _kayit["aylik"] = _json.dumps({f"{_dy}-{int(donem_ay):02d}": _f(tutar)})
        try:
            sb.table("ref_kayitlari").insert(_kayit).execute()
        except Exception:
            # kategori/aylik kolonları yoksa onlarsız dene
            for _k in ("kategori", "aylik"):
                _kayit.pop(_k, None)
            sb.table("ref_kayitlari").insert(_kayit).execute()
        _cache_temizle()
        return True, f"✅ {ref_no} atandı."
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}"


def ref_guncelle(ref_id, ref_no, aciklama, durum, tarih, paylasim_tarihi=None, tutar=None, doviz=None,
                 kategori=None, aylik=None, kategori_tutar=None):
    try:
        sb = get_client()
        _d = {
            "ref_no": ref_no, "aciklama": aciklama or "", "durum": durum,
            "tarih": str(tarih) if tarih else None,
            "paylasim_tarihi": str(paylasim_tarihi) if paylasim_tarihi else None,
        }
        if tutar is not None:
            _d["tutar"] = _f(tutar)
        if doviz is not None:
            _d["doviz"] = doviz or "USD"
        if kategori is not None:
            _d["kategori"] = kategori_kanonik(kategori)
        if aylik is not None:
            _d["aylik"] = aylik  # "" = temizle, JSON string = dönem ata
        if kategori_tutar is not None:
            _d["kategori_tutar"] = kategori_tutar   # {} = temizle
        try:
            sb.table("ref_kayitlari").update(_d).eq("id", ref_id).execute()
        except Exception:
            for _opsiyonel in ("kategori", "aylik", "kategori_tutar"):  # kolon yoksa onsuz dene
                _d.pop(_opsiyonel, None)
            sb.table("ref_kayitlari").update(_d).eq("id", ref_id).execute()
        _cache_temizle()
        return True
    except Exception:
        return False


def ref_sil(ref_id):
    """Tek bir ref no kaydını siler."""
    try:
        get_client().table("ref_kayitlari").delete().eq("id", ref_id).execute()
        _cache_temizle()
        return True
    except Exception:
        return False


def ref_temizle(firma_id):
    """Bir firmanın TÜM ref no kayıtlarını siler (toplu)."""
    try:
        get_client().table("ref_kayitlari").delete().eq("firma_id", firma_id).execute()
        _cache_temizle()
        return True
    except Exception:
        return False


def excel_ice_aktar(firma_id, df, varsayilan_durum="paylasildi", guncelle_mevcut=False):
    """NUMARA / REF NUMARASI / AÇIKLAMA / TUTAR / DOVİZ başlıklı df'i içe aktarır.
    guncelle_mevcut=True → mevcut ref'ler atlanmaz, döviz/tutar/açıklaması güncellenir."""
    try:
        sb = get_client()

        def _nrm(s):
            s = str(s).strip()
            for a, b in (("İ", "i"), ("I", "i"), ("ı", "i"), ("Ş", "s"), ("ş", "s"),
                         ("Ğ", "g"), ("ğ", "g"), ("Ü", "u"), ("ü", "u"),
                         ("Ö", "o"), ("ö", "o"), ("Ç", "c"), ("ç", "c")):
                s = s.replace(a, b)
            return s.lower()
        kol = {_nrm(c): c for c in df.columns}

        def _bul(*adlar):
            for a in adlar:
                _a = _nrm(a)
                for k, v in kol.items():
                    if _a in k:
                        return v
            return None

        c_no = _bul("numara")
        c_ref = _bul("ref")
        c_ack = _bul("açıklama", "aciklama", "aklama", "klama")
        c_tutar = _bul("tutar", "tutarı", "miktar", "bedel", "amount")
        c_doviz = _bul("döviz", "doviz", "para", "currency", "kur")
        c_ay = _bul("ay")
        c_yil = _bul("yıl", "yil")
        c_kat = _bul("kategori", "kategorı")
        if not c_ref:
            return False, "REF NUMARASI sütunu bulunamadı.", 0
        mevcut_map = {str(r.get("ref_no", "")).strip(): r for r in get_refler(firma_id)}
        # 1) Excel satırlarını ref_no bazında BİRLEŞTİR (aynı ref birden çok satırda olabilir →
        #    tutar toplanır, açıklamalar birleştirilir). Böylece (firma_id, ref_no) benzersiz kısıtı ihlal olmaz.
        _agg = {}
        for _, r in df.iterrows():
            ref = str(r.get(c_ref, "") or "").strip()
            if not ref or ref.lower() == "nan":
                continue
            kod, yil, sira = _parse_ref(ref)
            if c_no is not None:
                try:
                    sira = int(float(r.get(c_no)))
                except Exception:
                    pass
            ack = str(r.get(c_ack, "") or "").strip() if c_ack else ""
            if ack.lower() == "nan":
                ack = ""
            tutar = _f(r.get(c_tutar)) if c_tutar is not None else 0.0
            doviz = (str(r.get(c_doviz) or "").strip().upper() if c_doviz is not None else "") or "USD"
            if doviz not in DOVIZLER:
                doviz = "USD"
            # AY + YIL → aylık kırılım anahtarı (YYYY-MM); yoksa yalnız yıllık sayılır
            _ayn = _ay_no(r.get(c_ay)) if c_ay is not None else 0
            _yln = 0
            if c_yil is not None:
                try:
                    _yln = int(float(r.get(c_yil)))
                except Exception:
                    _yln = 0
            if _yln:
                yil = _yln
            o = _agg.get(ref)
            if o is None:
                o = {"sira": sira or 0, "yil": yil, "ack": [], "tutar": 0.0, "doviz": doviz,
                     "aylik": {}, "kat": []}
                _agg[ref] = o
            o["tutar"] += tutar
            if _yln and _ayn and tutar:
                _ak = f"{_yln}-{_ayn:02d}"
                o["aylik"][_ak] = o["aylik"].get(_ak, 0.0) + tutar
            _katv = (str(r.get(c_kat) or "").strip() if c_kat is not None else "")
            if _katv and _katv.lower() != "nan" and _katv not in o["kat"]:
                o["kat"].append(_katv)
            if ack and ack not in o["ack"]:
                o["ack"].append(ack)

        # 2) Ekle / güncelle — satır satır (dayanıklı; bir mükerrer tüm aktarımı bozmaz)
        eklenen = guncellenen = atlanan = hatali = 0
        for ref, o in _agg.items():
            _ack = " · ".join(o["ack"])[:500]
            _kat_str = " · ".join(o.get("kat") or [])[:200]
            if ref in mevcut_map:
                if guncelle_mevcut:
                    _upd = {"tutar": o["tutar"], "doviz": o["doviz"], "yil": o["yil"]}
                    if _ack:
                        _upd["aciklama"] = _ack
                    if o.get("aylik"):
                        _upd["aylik"] = o["aylik"]
                    if _kat_str:
                        _upd["kategori"] = _kat_str
                    _yazildi = False
                    for _drop in (None, "aylik", "kategori"):
                        if _drop:
                            _upd.pop(_drop, None)  # kolon yoksa onsuz dene
                        try:
                            sb.table("ref_kayitlari").update(_upd).eq("id", mevcut_map[ref].get("id")).execute()
                            guncellenen += 1
                            _yazildi = True
                            break
                        except Exception:
                            continue
                    if not _yazildi:
                        hatali += 1
                else:
                    atlanan += 1
                continue
            _ins = {
                "firma_id": firma_id, "sira_no": o["sira"], "ref_no": ref,
                "aciklama": _ack, "durum": varsayilan_durum, "yil": o["yil"],
                "tutar": o["tutar"], "doviz": o["doviz"],
            }
            if o.get("aylik"):
                _ins["aylik"] = o["aylik"]
            if _kat_str:
                _ins["kategori"] = _kat_str
            _yazildi = False
            for _drop in (None, "aylik", "kategori"):
                if _drop:
                    _ins.pop(_drop, None)  # kolon yoksa onsuz dene
                try:
                    sb.table("ref_kayitlari").insert(_ins).execute()
                    eklenen += 1
                    _yazildi = True
                    break
                except Exception:
                    continue
            if not _yazildi:
                hatali += 1
        _cache_temizle()
        _msg = f"✅ {eklenen} yeni ref eklendi"
        if guncelle_mevcut:
            _msg += f", {guncellenen} güncellendi"
        if atlanan:
            _msg += f", {atlanan} mevcut atlandı (güncelleme kapalı)"
        if hatali:
            _msg += f", ⚠️ {hatali} yazılamadı"
        _msg += f". Aynı ref no'lu satırlar tek kayıtta toplandı ({len(_agg)} benzersiz ref)."
        return True, _msg, eklenen + guncellenen
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}", 0


# ── HAVUZ BÜTÇE DB ──────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_butce(firma_id):
    try:
        sb = get_client()
        return _rows(sb.table("ref_butce").select("*")
                     .eq("firma_id", firma_id).order("fatura_tarih").execute())
    except Exception:
        return []


def butce_ekle(firma_id, tur, aciklama, tutar, doviz, fatura_no, fatura_tarih,
               ref_no, kisi, yon=None, marka="FAZEON"):
    try:
        sb = get_client()
        sb.table("ref_butce").insert({
            "firma_id": firma_id, "tur": tur or "", "yon": yon or _yon_belirle(tur),
            "aciklama": aciklama or "", "marka": marka or "", "tutar": _f(tutar),
            "doviz": doviz or "USD", "fatura_no": fatura_no or "",
            "fatura_tarih": str(fatura_tarih) if fatura_tarih else None,
            "ref_no": ref_no or "", "kisi": kisi or "",
        }).execute()
        _cache_temizle()
        return True, "✅ Kayıt eklendi."
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}"


def butce_guncelle(rid, tur, aciklama, tutar, fatura_no, fatura_tarih, ref_no, kisi, yon=None):
    try:
        sb = get_client()
        sb.table("ref_butce").update({
            "tur": tur or "", "yon": yon or _yon_belirle(tur),
            "aciklama": aciklama or "", "tutar": _f(tutar),
            "fatura_no": fatura_no or "",
            "fatura_tarih": str(fatura_tarih) if fatura_tarih else None,
            "ref_no": ref_no or "", "kisi": kisi or "",
        }).eq("id", rid).execute()
        _cache_temizle()
        return True
    except Exception:
        return False


def butce_sil(rid):
    try:
        sb = get_client()
        sb.table("ref_butce").delete().eq("id", rid).execute()
        _cache_temizle()
        return True
    except Exception:
        return False


def butce_temizle(firma_id):
    try:
        sb = get_client()
        sb.table("ref_butce").delete().eq("firma_id", firma_id).execute()
        _cache_temizle()
        return True
    except Exception:
        return False


def butce_excel_ice_aktar(firma_id, df, temizle=False, dosya_adi=""):
    """ITOPYA_HAVUZ_BÜTÇE formatı (konuma göre):
    TÜR|MARKA|AÇIKLAMA|HAKEDİŞ BÜTÇE|TUTAR|DÖVİZ|FATURA NO|FATURA TARİH|FİRMA|REF NO|AÇIKLAMA(kişi)
    temizle=True ise mevcut kayıtlar SADECE geçerli yeni satır varsa silinir (veri kaybını önler)."""
    try:
        sb = get_client()
        rows = []
        for _, r in df.iterrows():
            v = list(r.values)

            def g(i):
                return v[i] if i < len(v) else None

            tur = str(g(0) or "").strip()
            if not tur or tur.lower() == "nan":
                continue
            marka = str(g(1) or "").strip()
            aciklama = str(g(2) or "").strip()
            tutar = _f(g(3))                       # HAKEDİŞ BÜTÇE = tutar
            doviz = str(g(5) or "USD").strip() or "USD"
            fatura_no = str(g(6) or "").strip()
            ft = g(7)
            if isinstance(ft, (datetime, date)):
                fatura_tarih = ft.strftime("%Y-%m-%d")
            else:
                s = str(ft or "").strip()
                fatura_tarih = s[:10] if s and s.lower() != "nan" else None
            ref_no = str(g(9) or "").strip()
            kisi = str(g(10) or "").strip()
            if kisi.lower() == "nan":
                kisi = ""
            rows.append({
                "firma_id": firma_id, "tur": tur, "yon": _import_yon(tur, kisi, tutar),
                "aciklama": (aciklama if aciklama.lower() != "nan" else ""),
                "marka": (marka if marka.lower() != "nan" else ""),
                "tutar": tutar, "doviz": doviz, "fatura_no": fatura_no,
                "fatura_tarih": fatura_tarih, "ref_no": ref_no, "kisi": kisi,
            })
        if not rows:
            return False, ("❌ Excel'de geçerli bütçe satırı bulunamadı (TÜR sütunu boş/yanlış olabilir). "
                           "Güvenlik için hiçbir mevcut kayıt silinmedi."), 0
        # Yükleme geçmişi (shared.yukleme_gecmisi): silinen eski bütçe + eklenen kimlikler → geri alınabilir.
        # Anahtar firma: aynı firmaya sonradan başka bir yükleme yapıldıysa önce o geri alınır.
        from shared.yukleme_gecmisi import Kayit as _YKayit
        _yk = _YKayit("havuz_butce", dosya_adi)
        _yk.anahtar(firma_id)
        # Geçerli satır var → (istenirse) önce temizle, sonra ekle
        if temizle:
            try:
                _yk.onceki("ref_butce", sb.table("ref_butce").select("*").eq("firma_id", firma_id).execute().data or [])
            except Exception:
                _yk.iptal("eski bütçe satırları okunamadı")
            with cop_kutusu_kapali():
                sb.table("ref_butce").delete().eq("firma_id", firma_id).execute()
        for i in range(0, len(rows), 200):
            _yk.eklenen("ref_butce", sb.table("ref_butce").insert(rows[i:i + 200]).execute().data,
                        beklenen=len(rows[i:i + 200]))
        _yk.kaydet(len(rows))
        _cache_temizle()
        return True, f"✅ {len(rows)} bütçe kaydı içe aktarıldı.", len(rows)
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}", 0


# ════════════════════════════════════════════════════════════════════
# UI
# ════════════════════════════════════════════════════════════════════
def render():
    """Ref No Takibi ekranı — Ekim 2026'dan itibaren kayranpm/ref_ekran.py.
    Bu modüldeki veri fonksiyonları, kalem paneli, tablo editörü (_render_refler)
    ve Alınan Destekler aynen kullanılır."""
    from .ref_ekran import render as _yeni_ekran
    _yeni_ekran()


def kalem_yonet_paneli(r, firma_adi=""):
    """Ref kayıtlarının KALEM listesini düzenler: ekle · değiştir · sil.

    tutar/aylik/kategori_tutar bu listeden TÜRETİLİR — üçünü elle senkron
    tutmaya gerek yok, kaydettiğin anda hepsi yeniden hesaplanır.
    """
    import pandas as _pd
    _rid = r.get("id")
    _dv = (r.get("doviz") or "USD").strip().upper()
    _sm = {"USD": "$", "TL": "₺", "TRY": "₺", "EUR": "€"}.get(_dv, "")
    _kalemler = kalemleri_oku(r)

    st.markdown(f"**{r.get('ref_no', '—')}** · {firma_adi}")

    if not _kalemler:
        st.info("Bu kayıtta henüz kalem yok. Aşağıdan ekleyebilirsin. "
                "Kalem girildiğinde **tutar, aylık kırılım ve kategori dağılımı** "
                "otomatik hesaplanır.")

    # ── Mevcut kalemler (düzenlenebilir) ──
    _kat_havuz = sorted({k["kategori"] for k in _kalemler if k["kategori"]}
                        | set(_urun_kategorileri() or []))
    _ay_havuz = sorted({k["ay"] for k in _kalemler if k["ay"]}, reverse=True)

    if _kalemler:
        _df = _pd.DataFrame([{
            "Sil": False,
            "Açıklama": k["aciklama"],
            "Tutar": k["tutar"],
            "Ay": k["ay"],
            "Kategori": k["kategori"],
        } for k in _kalemler])
        _duz = st.data_editor(
            _df, use_container_width=True, hide_index=True, num_rows="fixed",
            key=f"refkal_duz_{_rid}",
            column_config={
                "Sil": st.column_config.CheckboxColumn("Sil", width="small"),
                "Açıklama": st.column_config.TextColumn("Açıklama", width="large"),
                "Tutar": st.column_config.NumberColumn(
                    f"Tutar ({_sm})", min_value=0.0, step=0.0001, format="localized"),
                "Ay": st.column_config.TextColumn("Ay", help="YYYY-AA · örn 2026-04"),
                "Kategori": st.column_config.SelectboxColumn(
                    "Kategori", options=_kat_havuz or None),
            })
        _yeni_liste = []
        for _, _r2 in _duz.iterrows():
            if bool(_r2.get("Sil")):
                continue
            _ack = str(_r2.get("Açıklama") or "").strip()
            _tut = _f(_r2.get("Tutar"))
            if not _ack and _tut == 0:
                continue
            _yeni_liste.append({
                "aciklama": _ack, "tutar": round(_tut, 2),
                "ay": str(_r2.get("Ay") or "").strip(),
                "kategori": kategori_kanonik(_r2.get("Kategori")),
            })
    else:
        _yeni_liste = []

    # ── Yeni kalem ekle ──
    st.markdown("**Yeni kalem**")
    _c1, _c2 = st.columns([3, 1])
    _y_ack = _c1.text_input("Açıklama", key=f"refkal_ack_{_rid}",
                            placeholder="örn. TEMMUZ FAZEON SELLOUT EK DESTEK")
    _y_tut = _c2.number_input(f"Tutar ({_sm})", min_value=0.0, step=0.01,
                              format="%.4f", key=f"refkal_tut_{_rid}")
    _c3, _c4 = st.columns(2)
    _ay_sec = _c3.selectbox("Ay", ["(yaz)"] + _ay_havuz, key=f"refkal_aysec_{_rid}")
    _y_ay = (_c3.text_input("Ay (YYYY-AA)", key=f"refkal_ay_{_rid}",
                            placeholder="2026-07").strip()
             if _ay_sec == "(yaz)" else _ay_sec)
    _kat_sec = _c4.selectbox("Kategori", ["(yaz)"] + _kat_havuz, key=f"refkal_katsec_{_rid}")
    _y_kat = (_c4.text_input("Kategori", key=f"refkal_kat_{_rid}").strip()
              if _kat_sec == "(yaz)" else _kat_sec)

    _ekle = st.button("Kaleme ekle", key=f"refkal_ekle_{_rid}",
                      use_container_width=True,
                      disabled=not (_y_ack.strip() and _y_tut > 0), icon=":material/add:")
    if _ekle:
        _yeni_liste.append({"aciklama": _y_ack.strip(), "tutar": round(_y_tut, 2),
                            "ay": _y_ay, "kategori": kategori_kanonik(_y_kat)})

    # ── Önizleme: türetilen değerler ──
    _t = kalemlerden_turet(_yeni_liste)
    _ham = round(_f(r.get("tutar")), 2)
    _fark = round(_t["tutar"] - _ham, 2)
    st.markdown("---")
    _m1, _m2, _m3 = st.columns(3)
    _m1.metric("Kalem", f"{len(_yeni_liste)}")
    _m2.metric("Yeni toplam", f"{_sm}{tr_sayi(_t['tutar'], 2)}",
               delta=(f"{_fark:+,.2f}" if abs(_fark) >= 0.005 else None))
    _m3.metric("Kayıtlı tutar", f"{_sm}{tr_sayi(_ham, 2)}")
    if _t["aylik"]:
        st.caption("📅 " + " · ".join(f"**{a}** {_sm}{tr_sayi(v)}"
                                      for a, v in sorted(_t["aylik"].items())))
    if _t["kategori_tutar"]:
        st.caption("️ " + " · ".join(f"**{k}** {_sm}{tr_sayi(v)}" for k, v in
                                      sorted(_t["kategori_tutar"].items(),
                                             key=lambda x: -x[1])))
    _aysiz = [k for k in _yeni_liste if not k["ay"]]
    _katsiz = [k for k in _yeni_liste if not k["kategori"]]
    if _aysiz:
        st.warning(f"⚠️ {len(_aysiz)} kalemde **ay** yok — aylık kırılıma girmez.")
    if _katsiz:
        st.warning(f"⚠️ {len(_katsiz)} kalemde **kategori** yok — Kâr/P&L "
                   f"kategori filtresine yansımaz.")

    if st.button("Kalemleri kaydet", type="primary", use_container_width=True,
                 key=f"refkal_kaydet_{_rid}", icon=":material/save:"):
        _ok, _msg = kalemleri_yaz(_rid, _yeni_liste)
        (st.success if _ok else st.error)(_msg)
        if _ok:
            st.rerun()


def kategori_dagit_dialog(r, firma_adi=""):
    """Çok kategorili bir ref kaydının tutarını kategorilere böler.

    Açıklamadan kategori ÖNERİSİ gösterir ama tutarı önermez — açıklamalarda
    kalem bazlı tutar yok, uydurmak yanlış olur.
    """
    import json as _json
    _kats = _kat_liste(r.get("kategori"))
    _ham = _f(r.get("tutar"))
    _dv = (r.get("doviz") or "USD").strip().upper()
    _sm = {"USD": "$", "TL": "₺", "TRY": "₺", "EUR": "€"}.get(_dv, "")
    st.markdown(f"**{r.get('ref_no','—')}** · {firma_adi} · toplam **{_sm}{tr_sayi(_ham, 2)}**")

    _oneri = ref_kategori_onerisi(r.get("aciklama"), _kats)
    if _oneri:
        st.caption("Açıklamada geçen kategoriler: " + " · ".join(f"`{k}`" for k in _oneri))

    _mevcut = r.get("kategori_tutar") or {}
    if isinstance(_mevcut, str):
        try:
            _mevcut = _json.loads(_mevcut)
        except Exception:
            _mevcut = {}

    _giris, _kol = {}, st.columns(min(3, max(1, len(_kats))))
    for _i, _k in enumerate(_kats):
        with _kol[_i % len(_kol)]:
            _giris[_k] = st.number_input(
                _k, min_value=0.0, step=100.0, format="%.4f",
                value=float(_f(_mevcut.get(_k, 0))),
                key=f"refkt_{r.get('id')}_{_k}")
    _top = sum(_giris.values())
    _kalan = _ham - _top
    if abs(_kalan) < 0.005:
        st.success(f"✓ Dağıtım tam: {_sm}{tr_sayi(_top, 2)}")
    elif _top == 0:
        st.info(f"Henüz dağıtılmadı — tamamı **GENEL**'de kalır ve kategori "
                f"filtresine yansımaz.")
    else:
        st.warning(f"⚠️ Kalan: {_sm}{tr_sayi(_kalan, 2)} — toplam {_sm}{tr_sayi(_ham, 2)} olmalı.")

    _c1, _c2 = st.columns(2)
    if _c1.button("Kaydet", type="primary", use_container_width=True,
                  key=f"refkt_kaydet_{r.get('id')}",
                  disabled=abs(_kalan) >= 0.005 and _top > 0, icon=":material/save:"):
        ref_guncelle(r.get("id"), r.get("ref_no"), r.get("aciklama"), r.get("durum"),
                     r.get("tarih"), r.get("paylasim_tarihi"),
                     kategori_tutar={k: round(v, 2) for k, v in _giris.items() if v > 0})
        _cache_temizle()
        st.success("✅ Kategori dağılımı kaydedildi")
        st.rerun()
    if _c2.button("Dağılımı temizle", use_container_width=True,
                  key=f"refkt_temizle_{r.get('id')}", icon=":material/cleaning_services:"):
        ref_guncelle(r.get("id"), r.get("ref_no"), r.get("aciklama"), r.get("durum"),
                     r.get("tarih"), r.get("paylasim_tarihi"), kategori_tutar={})
        _cache_temizle()
        st.rerun()


def _ref_detay_govde(r, firma_adi=""):
    """Ref kaydının kırılımı — tutarlı tipografiyle."""
    from shared.ui import RENK
    _dv = (r.get("doviz") or "USD").strip().upper()
    _sm = {"USD": "$", "TL": "₺", "TRY": "₺", "EUR": "€"}.get(_dv, "")
    _durum = r.get("durum", "") or ""
    _dr = _durum_renk(_durum)
    _parcalar = [x.strip() for x in str(r.get("aciklama") or "").split("·") if x.strip()]
    _kats = [x.strip() for x in str(r.get("kategori") or "").split("·") if x.strip()]
    _ays, _yls = _aylik_ozet(r)

    st.markdown(_dt_baslik(r.get("ref_no", "—"),
                           DURUM_ETIKET.get(_durum, _durum), _dr,
                           (firma_adi or r.get("_firma") or "")), unsafe_allow_html=True)
    st.markdown(_dt_kutular([
        ("Tutar", f"{_sm}{tr_sayi(_f(r.get('tutar')), 2)}", RENK["metin"]),
        ("Döviz", _dv, RENK["soluk"]),
        ("Kalem", f"{len(_parcalar) or 1}", RENK["mor2"]),
        ("Dönem", (_ays if _ays != "—" else "—"), RENK["cyan"]),
    ]), unsafe_allow_html=True)

    # ── KALEM YÖNETİMİ — açıklama + tutar ekle/düzenle/sil ──
    # Kalem yapısı varsa tutar/aylik/kategori_tutar BURADAN türetilir;
    # aşağıdaki "kategori tutarını dağıt" paneline gerek kalmaz.
    _mev_kalem = kalemleri_oku(r)
    _kalem_btn = ("🧾 Kalemleri düzenle ({} kalem)".format(len(_mev_kalem))
                  if _mev_kalem else "🧾 Kalem ekle (açıklama + tutar)")
    if st.button(_kalem_btn, key=f"refkal_ac_{r.get('id')}", use_container_width=True):
        st.session_state[f"refkal_acik_{r.get('id')}"] = not st.session_state.get(
            f"refkal_acik_{r.get('id')}", False)
    if st.session_state.get(f"refkal_acik_{r.get('id')}"):
        with st.container(border=True):
            kalem_yonet_paneli(r, firma_adi)

    # Çok kategorili kayıtlarda tutar dağıtımı — YALNIZ kalem yapısı yoksa.
    # Kalemler varsa dağıtım zaten kalem bazında yapılıyor.
    if len(_kats) > 1 and not _mev_kalem:
        _kt = r.get("kategori_tutar") or {}
        if isinstance(_kt, str):
            try:
                import json as _j
                _kt = _j.loads(_kt)
            except Exception:
                _kt = {}
        _dagitildi = sum(_f(v) for v in (_kt or {}).values()) > 0.005
        if _dagitildi:
            st.caption("Kategori dağılımı: " + " · ".join(
                f"**{k}** {_sm}{tr_sayi(_f(v))}" for k, v in _kt.items() if _f(v) > 0))
        else:
            st.warning(f"🏷️ Bu kayıt **{len(_kats)} kategori** taşıyor ama tutar "
                       f"dağıtılmamış — kategori bazlı Kâr/P&L'de **GENEL**'de kalıyor "
                       f"ve filtreye yansımıyor.")
        if st.button("Kategori tutarını dağıt", key=f"refkt_ac_{r.get('id')}",
                     use_container_width=True, icon=":material/sell:"):
            st.session_state[f"refkt_acik_{r.get('id')}"] = True
        if st.session_state.get(f"refkt_acik_{r.get('id')}"):
            with st.container(border=True):
                kategori_dagit_dialog(r, firma_adi)

    c1, c2 = st.columns([1.25, 1])
    with c1:
        if len(_parcalar) > 1:
            _liste = "".join(
                f'<div style="display:flex;gap:10px;padding:6px 0;'
                f'border-bottom:1px solid color-mix(in srgb,var(--k-soluk) 8%,transparent)">'
                f'<span style="font-family:{_MONO};font-size:11px;color:{RENK["silik"]};'
                f'min-width:18px">{i:02d}</span>'
                f'<span style="font-size:13px;color:{RENK["metin"]};line-height:1.4">{p}</span>'
                f'</div>' for i, p in enumerate(_parcalar, 1))
            st.markdown(f'<div style="{_etiket_css(RENK["soluk"])};margin-bottom:8px">'
                        f'Açıklama kırılımı · {len(_parcalar)} kalem</div>{_liste}',
                        unsafe_allow_html=True)
        else:
            st.markdown(_dt_alan("Açıklama", _parcalar[0] if _parcalar else "—"),
                        unsafe_allow_html=True)
        st.markdown(f'<div style="margin-top:14px">'
                    f'<div style="{_etiket_css(RENK["soluk"])};margin-bottom:7px">Kategoriler</div>'
                    f'{_dt_cipler(_kats)}</div>', unsafe_allow_html=True)
    with c2:
        _ay = r.get("aylik") or {}
        if isinstance(_ay, str):
            try:
                import json
                _ay = json.loads(_ay)
            except Exception:
                _ay = {}
        st.markdown(f'<div style="{_etiket_css(RENK["soluk"])};margin-bottom:8px">'
                    f'Aylık kırılım</div>', unsafe_allow_html=True)
        if isinstance(_ay, dict) and _ay:
            _sat = ""
            _tp = 0.0
            for k in sorted(_ay.keys()):
                v = _f(_ay[k])
                _tp += v
                try:
                    yy, mm = str(k).split("-")[:2]
                    etk = f"{_AY_AD.get(int(mm), mm).title()} {yy}"
                except Exception:
                    etk = str(k)
                _sat += (f'<div style="display:flex;justify-content:space-between;'
                         f'padding:6px 0;border-bottom:1px solid color-mix(in srgb,var(--k-soluk) 8%,transparent)">'
                         f'<span style="font-size:13px;color:{RENK["soluk"]}">{etk}</span>'
                         f'<span style="font-family:{_MONO};font-size:13px;font-weight:700;'
                         f'color:{RENK["metin"]};font-variant-numeric:tabular-nums">'
                         f'{_sm}{tr_sayi(v, 2)}</span></div>')
            _fk = _f(r.get("tutar")) - _tp
            _uy = (trenk("yesil"), "kayıt tutarıyla uyumlu") if abs(_fk) <= 0.01 else \
                  (trenk("amber"), f"kayıt tutarıyla {_sm}{tr_sayi(_fk, 2)} fark")
            _sat += (f'<div style="display:flex;justify-content:space-between;padding:8px 0 0">'
                     f'<span style="{_etiket_css(RENK["silik"])}">Toplam</span>'
                     f'<span style="font-family:{_MONO};font-size:13px;font-weight:700;'
                     f'color:{_uy[0]};font-variant-numeric:tabular-nums">{_sm}{tr_sayi(_tp, 2)}</span></div>'
                     f'<div style="{_etiket_css(_uy[0])};margin-top:6px">{_uy[1]}</div>')
            st.markdown(_sat, unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="color:{RENK["silik"]};font-size:13px;line-height:1.5">'
                        f'Bu kayıtta aylık kırılım yok — tutar tek dönemde işlenir.</div>',
                        unsafe_allow_html=True)


def _durum_renk(d):
    return {"paylasildi": trenk("yesil"), "beklemede": trenk("amber")}.get(d, trenk("silik"))


# ══════════════════════════════════════════════════════════════════
#  ORTAK TASARIM KATMANI — özet şeridi ve detay pencereleri
#  Tipografi kuralı: etiketler 9.5px/1.4px aralık/UPPERCASE/700,
#  sayılar JetBrains Mono + tabular-nums (rakamlar alt alta hizalanır),
#  metinler sistem fontu. Tüm ölçüler tek yerden yönetilir.
# ══════════════════════════════════════════════════════════════════
_MONO = "'JetBrains Mono','SF Mono',ui-monospace,monospace"


def _etiket_css(renk):
    # Programın yeni dili: cümle düzeni (eskiden 10px büyük harf + 1.4px aralık)
    return f"font-size:12px;font-weight:500;color:{renk};line-height:1.2"


def _sayi_css(renk, boyut=19):
    return (f"font-family:{_MONO};font-size:{boyut}px;font-weight:700;color:{renk};"
            f"line-height:1.15;font-variant-numeric:tabular-nums;letter-spacing:-.3px")


def _dt_baslik(ana, rozet="", rozet_renk="#818CF8", alt=""):
    """Detay penceresi başlık bandı."""
    from shared.ui import RENK
    _r = (f'<span style="background:{rozet_renk}1F;color:{rozet_renk};padding:3px 10px;'
          f'border-radius:20px;font-size:11px;font-weight:700;letter-spacing:.5px;'
          f'white-space:nowrap">{rozet}</span>' if rozet else "")
    _a = (f'<div style="{_etiket_css(RENK["silik"])};margin-top:7px">{alt}</div>'
          if alt else "")
    return (f'<div style="border-left:3px solid {rozet_renk};padding:2px 0 2px 14px;'
            f'margin:0 0 16px">'
            f'<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">'
            f'<span style="font-family:{_MONO};font-size:16px;font-weight:700;'
            f'color:{RENK["metin"]};letter-spacing:-.2px">{ana}</span>{_r}</div>{_a}</div>')


def _dt_kutular(kalemler):
    """Detay penceresi üst metrikleri — st.metric yerine tutarlı tipografi."""
    from shared.ui import RENK
    ic = "".join(
        f'<div style="flex:1;min-width:112px;background:color-mix(in srgb,var(--k-metin) 2%,transparent);'
        f'border:1px solid color-mix(in srgb,var(--k-soluk) 10%,transparent);border-radius:10px;padding:10px 14px">'
        f'<div style="{_etiket_css(RENK["soluk"])};margin-bottom:7px">{e}</div>'
        f'<div style="{_sayi_css(c, 17)};white-space:nowrap">{v}</div></div>'
        for e, v, c in kalemler)
    return f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px">{ic}</div>'


def _dt_alan(etiket, deger, mono=False):
    """Detay penceresi etiket/değer satırı."""
    from shared.ui import RENK
    _st = (f"font-family:{_MONO};font-size:13px;font-variant-numeric:tabular-nums"
           if mono else "font-size:13px")
    return (f'<div style="margin-bottom:13px">'
            f'<div style="{_etiket_css(RENK["soluk"])};margin-bottom:5px">{etiket}</div>'
            f'<div style="{_st};color:{RENK["metin"]};line-height:1.45">{deger}</div></div>')


def _dt_cipler(degerler, renk="#A5B4FC"):
    if not degerler:
        return '<span style="color:var(--k-silik);font-size:13px">—</span>'
    return "".join(
        f'<span style="background:{renk}1F;color:{renk};padding:3px 10px;'
        f'border-radius:20px;font-size:11px;font-weight:600;margin:0 5px 5px 0;'
        f'display:inline-block">{d}</span>' for d in degerler)


# ── SEKME 1: REF NO'LAR ─────────────────────────────────────────────
def _tutar_ozet(refler):
    """Ref no'ların toplam tutarını döviz bazlı özetler: '$5.000 · ₺120.000'."""
    from collections import defaultdict
    d = defaultdict(float)
    for r in refler:
        dv = (r.get("doviz") or "USD").strip().upper()
        d[dv] += _f(r.get("tutar"))
    sembol = {"USD": "$", "TL": "₺", "TRY": "₺", "EUR": "€"}
    parcalar = [f"{sembol.get(k, k + ' ')}{tr_sayi(v)}" for k, v in d.items() if v]
    return " · ".join(parcalar) if parcalar else "—"


def _render_refler(fid, fkod):
    refler = get_refler(fid)
    _bekleyen = sum(1 for r in refler if r.get("durum") == "beklemede")
    _paylasilan = sum(1 for r in refler if r.get("durum") == "paylasildi")
    metrik_satiri([
        {"label": "Toplam Ref", "value": f"{tr_sayi(len(refler))}", "renk": trenk("mor")},
        {"label": "⏳ Beklemede", "value": f"{tr_sayi(_bekleyen)}", "renk": trenk("amber")},
        {"label": "✅ Paylaşılan", "value": f"{tr_sayi(_paylasilan)}", "renk": trenk("yesil")},
        {"label": "💰 Toplam Tutar", "value": _tutar_ozet(refler), "renk": trenk("mor")},
    ])

    _siradaki = _sonraki_sira(fid)
    _onizleme = ref_uret(fkod, _yil(), _siradaki)

    # ── Ekleme + içe aktarma tek kompakt panelde (varsayılan kapalı) ──
    with st.expander(f"➕ Yeni Ref No Ata / Excel İçe Aktar  ·  sıradaki: {_onizleme}", expanded=False):
        with st.form("ref_ekle_form", clear_on_submit=True):
            rc1, rc2 = st.columns([2.4, 1.2])
            yeni_ack = rc1.text_input("Açıklama *", placeholder="örn. TEMMUZ MONİTÖR SELLOUT")
            _kat_opts = _kategori_listesi(refler) + ["➕ Yeni kategori…"]
            yeni_kat_sec = rc2.selectbox("Kategori", ["—"] + _kat_opts, index=0)
            yeni_kat = ""
            if yeni_kat_sec == "➕ Yeni kategori…":
                yeni_kat = st.text_input("Yeni kategori adı", placeholder="örn. ANAKART",
                                         key="ref_yeni_kat_input")
            elif yeni_kat_sec != "—":
                yeni_kat = yeni_kat_sec
            rd1, rd2, rd3, rd4, rd5 = st.columns([1.1, 0.8, 1.0, 0.8, 1.3])
            yeni_tutar = rd1.number_input("Tutar", min_value=0.0, value=None,
                                          placeholder="0,00", step=100.0, format="%.4f")
            yeni_doviz = rd2.selectbox("Döviz", DOVIZLER, index=0)
            _ay_opts = ["—"] + [_AY_AD[m] for m in range(1, 13)]
            yeni_ay = rd3.selectbox("Dönem Ayı", _ay_opts, index=0,
                                    help="Ref'in ait olduğu ay (Ay/Yıl kolonuna yazılır)")
            yeni_donem_yil = rd4.number_input("Yıl", min_value=2020, max_value=2100,
                                              value=_yil(), step=1)
            yeni_durum = rd5.selectbox("Durum", DURUMLAR, format_func=lambda d: DURUM_ETIKET[d], index=0)
            if st.form_submit_button("Ref No Ata", type="primary", use_container_width=True, icon=":material/add:"):
                if not (yeni_ack or "").strip():
                    st.error("⚠️ Açıklama boş olamaz — boş ref no atanmaz. "
                             "Lütfen bir açıklama girip tekrar dene.")
                else:
                    _ay_no = (_ay_opts.index(yeni_ay) if yeni_ay != "—" else None)
                    ok, msg = ref_ekle(fid, fkod, yeni_ack.strip(), yeni_durum, date.today(),
                                       tutar=(yeni_tutar or 0.0), doviz=yeni_doviz,
                                       kategori=yeni_kat, donem_ay=_ay_no,
                                       donem_yil=int(yeni_donem_yil))
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.rerun()

        @st.dialog("📥 Excel'den İçe Aktar (NUMARA · REF NUMARASI · AÇIKLAMA)", width="large")
        def _dlg_ref_ice_aktar():
            up = st.file_uploader("Bu firmanın ref Excel'i", type=["xlsx", "xls"], key=f"ref_up_{fid}")
            if up is not None:
                try:
                    df_imp = pd.read_excel(up)
                    st.caption(f"Dosyada **{len(df_imp)} satır** var — tamamı aşağıda (kaydırarak görebilirsin).")
                    st.dataframe(df_imp, hide_index=True, use_container_width=True,
                                 height=min(38 + 35 * len(df_imp), 460))
                    imp_durum = st.selectbox("İçe aktarılan kayıtların durumu", DURUMLAR,
                                             format_func=lambda d: DURUM_ETIKET[d], index=1,
                                             key=f"ref_imp_durum_{fid}")
                    imp_guncelle = st.checkbox(
                        "🔁 Mevcut ref'leri de güncelle (döviz/tutar/açıklamayı düzelt)",
                        key=f"ref_imp_guncelle_{fid}",
                        help="İşaretli: sistemde zaten olan ref no'ların döviz ve tutarı Excel'e göre güncellenir "
                             "(ör. yanlış USD → TL). İşaretsiz: mevcut ref'ler atlanır, sadece yeniler eklenir.")
                    if st.button("İçe Aktar", type="primary", key=f"ref_imp_btn_{fid}", icon=":material/move_to_inbox:"):
                        ok, msg, _n = excel_ice_aktar(fid, df_imp, imp_durum, guncelle_mevcut=imp_guncelle)
                        (st.success if ok else st.error)(msg)
                        if ok:
                            from shared.yukleme_gecmisi import kaydet as _yg_kaydet
                            _yg_kaydet("ref_excel", _n, up.name)
                            st.rerun()
                except Exception as e:
                    st.error(f"Excel okunamadı: {e}")
        if st.button("Excel'den İçe Aktar", key="btn_ref_ice", use_container_width=True, icon=":material/move_to_inbox:"):
            _dlg_ref_ice_aktar()

    st.markdown("**Geçmiş Ref No'lar**")
    if not refler:
        st.info("Bu firma için henüz ref no yok. Yukarıdan atayabilir veya Excel'den içe aktarabilirsiniz.")
        return

    _ff1, _ff2, _ff3, _ff4 = st.columns(4)
    f_durum = _ff1.selectbox("Durum filtresi", ["Tümü"] + DURUMLAR,
                             format_func=lambda d: ("Tümü" if d == "Tümü" else DURUM_ETIKET[d]),
                             key=f"ref_durum_f_{fid}")
    _katlar = sorted({p.strip() for r in refler
                      for p in str(r.get("kategori") or "").split("·") if p.strip()})
    f_kat = _ff2.selectbox("Kategori", ["Tümü"] + _katlar, key=f"ref_kat_f_{fid}")
    _yillar = sorted({p.strip() for r in refler
                      for p in _aylik_ozet(r)[1].split("·") if p.strip() and p.strip() != "—"})
    f_yil = _ff3.selectbox("Yıl", ["Tümü"] + _yillar, key=f"ref_yil_f_{fid}")
    _ay_set = {p.strip() for r in refler
               for p in _aylik_ozet(r)[0].split("·") if p.strip() and p.strip() != "—"}
    _aylar_sirali = [a for a in _AY_AD.values() if a in _ay_set]
    f_ay = _ff4.selectbox("Ay", ["Tümü"] + _aylar_sirali, key=f"ref_ay_f_{fid}")

    def _ref_uygun(r):
        if f_durum != "Tümü" and r.get("durum") != f_durum:
            return False
        if f_kat != "Tümü" and f_kat not in str(r.get("kategori") or ""):
            return False
        _ays, _yls = _aylik_ozet(r)
        if f_yil != "Tümü" and f_yil not in _yls:
            return False
        if f_ay != "Tümü" and f_ay not in _ays:
            return False
        return True
    goster = [r for r in refler if _ref_uygun(r)]
    st.caption(f"{len(goster)} / {len(refler)} kayıt · ✏️ **Açıklama, Kategori, Tutar, Döviz, Dönem "
               f"(Ay/Yıl) ve Durum hücreleri tabloda doğrudan düzenlenebilir** — değiştirip altta "
               f"💾 Kaydet'e bas. Silmek için satırın 'Sil?' kutusunu işaretleyip Kaydet'e bas.")

    # 🔎 DETAY PENCERESİ — düzenlenebilir tabloda satır tıklaması olmadığı için
    # kayıt seçici + buton ile açılır. Aynı ref no altında birleşmiş kalemler,
    # kategoriler ve aylık kırılım burada tek tek görünür.
    @st.dialog("🔎 Ref No Detayı", width="large")
    def _dlg_ref_detay_firma(_kayit):
        st.markdown(f"### {_kayit.get('ref_no','')}")
        _ref_detay_govde(_kayit)

    if goster:
        _dt1, _dt2 = st.columns([3, 1])
        _dsec = _dt1.selectbox(
            "Detayını görmek istediğin kayıt", goster,
            format_func=lambda r: (f"{r.get('ref_no','')} · "
                                   f"{(r.get('aciklama') or '')[:48]} · "
                                   f"{tr_sayi(_f(r.get('tutar')))} {r.get('doviz','USD')}"),
            key=f"ref_detay_sec_{fid}", label_visibility="collapsed")
        if _dt2.button("Detayı Aç", use_container_width=True, key=f"ref_detay_btn_{fid}", icon=":material/search:"):
            _dlg_ref_detay_firma(_dsec)

    _kat_secenekler = _kategori_listesi(refler)
    df_ed = pd.DataFrame([{
        "id": r["id"], "Sil?": False, "No": int(r.get("sira_no") or 0), "Ref No": r.get("ref_no", "") or "",
        "Açıklama": r.get("aciklama", "") or "", "Tutar": _f(r.get("tutar")),
        "Döviz": (r.get("doviz") or "USD"),
        "Kategori": (_tr_upper((r.get("kategori") or "").strip()) or "—"),
        "Ay": _aylik_ozet(r)[0], "Yıl": _aylik_ozet(r)[1],
        "Durum": r.get("durum", "beklemede") or "beklemede",
    } for r in goster])

    # Kategori dropdown seçenekleri: mevcut değerler de dahil olmalı (yoksa hata verir)
    _kat_kolon_opts = list(dict.fromkeys(["—"] + _kat_secenekler +
                                         [str(x) for x in df_ed["Kategori"].tolist() if x]))
    # Ay dropdown: tek ay adları + boş; çok-aylı ref'ler serbest metin gibi görünür ama
    # düzenlenirse tek aya sabitlenir. Ay seçenekleri:
    _ay_kolon_opts = list(dict.fromkeys([""] + list(_AY_AD.values()) +
                                        [str(x) for x in df_ed["Ay"].tolist() if x]))

    edited = st.data_editor(
        df_ed, use_container_width=True, hide_index=True, num_rows="fixed",
        height=min(38 + 35 * max(len(df_ed), 1), 900),
        key=f"ref_editor_{fid}_{f_durum}",
        column_config={
            "id": None,
            "Sil?": st.column_config.CheckboxColumn("Sil?", width="small",
                                                    help="İşaretle → Kaydet'e basınca bu kayıt silinir"),
            "No": st.column_config.NumberColumn("No", disabled=True, width="small"),
            "Ref No": st.column_config.TextColumn(
                "Ref No",
                help="Düzenlenebilir. Bozuk numaraları elle düzeltmek için kullan "
                     "(örn. FZFZMNDRF2025001RF2026001 → FZMNDRF2026001). "
                     "Aynı firmada iki kayıt aynı numarayı alamaz."),
            "Açıklama": st.column_config.TextColumn("Açıklama", width="large"),
            "Tutar": st.column_config.NumberColumn("Tutar", format="localized", width="small", step=0.0001),
            "Döviz": st.column_config.SelectboxColumn("Döviz", options=DOVIZLER, required=True, width="small"),
            "Kategori": st.column_config.SelectboxColumn("Kategori", options=_kat_kolon_opts,
                                                         width="medium",
                                                         help="Açılır listeden seç. Yeni kategori eklemek "
                                                              "istersen üstteki '➕ Yeni Ref No Ata' panelinden "
                                                              "'Yeni kategori…' ile ekle."),
            "Ay": st.column_config.SelectboxColumn("Ay", options=_ay_kolon_opts, width="small",
                                                   help="Ref'in ait olduğu ay — düzenlenebilir. "
                                                        "Değiştirip Kaydet'e bas."),
            "Yıl": st.column_config.TextColumn("Yıl", width="small",
                                               help="Ref'in ait olduğu yıl (örn. 2026) — düzenlenebilir."),
            "Durum": st.column_config.SelectboxColumn("Durum", options=DURUMLAR, required=True),
        },
    )
    if st.button("Değişiklikleri Kaydet", type="primary", key=f"ref_save_{fid}", icon=":material/save:"):
        orijinal = {r["id"]: r for r in goster}
        degisen = silinen = 0
        _ref_hata = []
        # Bu firmadaki TÜM ref no'lar (filtre dışındakiler dahil) — mükerrer kontrolü
        _mevcut_refler = {str(r.get("ref_no") or "").strip().upper()
                          for r in refler if str(r.get("ref_no") or "").strip()}
        for _, row in edited.iterrows():
            rid = row["id"]
            if bool(row.get("Sil?")):
                if ref_sil(rid):
                    silinen += 1
                continue
            o = orijinal.get(rid, {})
            n_ack = str(row.get("Açıklama", "") or "")
            n_dur = str(row.get("Durum", "beklemede"))
            n_tar = (str(o.get("tarih") or "")[:10] or None)  # Tarih kolonu kaldırıldı; mevcut değer korunur
            n_tutar = _f(row.get("Tutar"))
            n_doviz = str(row.get("Döviz", "USD") or "USD")
            n_kat = str(row.get("Kategori", "") or "").strip()
            _o_kat = str(o.get("kategori") or "").strip()
            if n_kat == "—":
                n_kat = _o_kat  # placeholder tiresi değişiklik sayılmasın

            # ── Ay/Yıl değişikliği → aylik JSON'ı yeniden kur ──
            n_ay = str(row.get("Ay", "") or "").strip()
            n_yil = str(row.get("Yıl", "") or "").strip()
            _o_ays, _o_yls = _aylik_ozet(o)
            aylik_yeni = None  # None = değişiklik yok
            if n_ay != _o_ays or n_yil != _o_yls:
                # tek ay + tek yıl girildiyse temiz bir aylik kur; tutar ref tutarı
                _ay_no = _ay_no_coz(n_ay)
                _yil_i = "".join(ch for ch in n_yil if ch.isdigit())[:4]
                if _ay_no and len(_yil_i) == 4:
                    import json as _json
                    aylik_yeni = _json.dumps({f"{_yil_i}-{_ay_no:02d}": n_tutar})
                elif not n_ay and not n_yil:
                    aylik_yeni = ""  # ikisi de boşaltıldı → dönem temizle

            # ── REF NO artık düzenlenebilir — ama önce doğrula ──
            _o_ref = str(o.get("ref_no") or "").strip()
            n_ref = str(row.get("Ref No", "") or "").strip()
            if not n_ref:
                _ref_hata.append(f"#{rid}: Ref no boş bırakılamaz — eski değer korundu.")
                n_ref = _o_ref
            elif n_ref != _o_ref and n_ref.upper() in _mevcut_refler - {_o_ref.upper()}:
                _ref_hata.append(f"#{rid}: '{n_ref}' bu firmada zaten kullanılıyor — "
                                 "eski değer korundu.")
                n_ref = _o_ref

            _degisti = (n_ack != (o.get("aciklama", "") or "") or n_dur != (o.get("durum") or "") or
                        n_tutar != _f(o.get("tutar")) or n_doviz != (o.get("doviz") or "USD") or
                        n_kat != _o_kat or aylik_yeni is not None or n_ref != _o_ref)
            if _degisti:
                pay = n_tar if n_dur == "paylasildi" else o.get("paylasim_tarihi")
                ref_guncelle(rid, n_ref, n_ack, n_dur, n_tar, pay,
                             tutar=n_tutar, doviz=n_doviz,
                             kategori=(n_kat if n_kat != _o_kat else None),
                             aylik=aylik_yeni)
                if n_ref != _o_ref:
                    _mevcut_refler.discard(_o_ref.upper())
                    _mevcut_refler.add(n_ref.upper())
                degisen += 1
        if degisen or silinen:
            st.success(f"✅ {degisen} güncellendi, {silinen} silindi.")
        elif not _ref_hata:
            st.info("Değişiklik yok. (Hücreyi düzenleyip tekrar bu butona bas.)")
        if _ref_hata:
            st.error("⚠️ Bazı ref no değişiklikleri uygulanmadı:\n\n" + "\n\n".join(_ref_hata))
        if degisen or silinen:
            st.cache_data.clear()
            st.rerun()

    # ── Toplu sil (görünen kayıtlar / firmanın tümü) ──
    @st.dialog("🗑 Toplu Sil — filtredeki kayıtları veya tüm ref no'ları sil", width="large")
    def _dlg_ref_toplu_sil():
        st.caption("Silme geri alınamaz. 'Görünenleri sil' yalnızca yukarıdaki durum filtresine uyan "
                   "kayıtları siler; ya da bu firmanın tüm ref no kayıtlarını temizle. "
                   "(Tek tek silmek için tablodaki 'Sil?' kutusunu işaretleyip Kaydet'e de basabilirsin.)")
        _rs1, _rs2 = st.columns(2)
        with _rs1:
            # Eskiden onaysız siliyordu (yanındaki "Tümünü sil" onay istiyordu).
            _onay_g = st.checkbox(f"Onaylıyorum — görünen {len(goster)} kaydı sil",
                                  key=f"ref_bulk_onay_{fid}", disabled=(len(goster) == 0))
            if st.button(f"Görünen {len(goster)} kaydı sil", use_container_width=True,
                         key=f"ref_bulk_goster_{fid}", disabled=(len(goster) == 0 or not _onay_g),
                         icon=":material/delete:"):
                _sil = 0
                for _r in goster:
                    if ref_sil(_r["id"]):
                        _sil += 1
                st.cache_data.clear()
                st.success(f"✅ {_sil} kayıt silindi.")
                st.rerun()
        with _rs2:
            _onay = st.checkbox(f"Onaylıyorum — bu firmanın TÜM ({len(refler)}) ref no'sunu sil",
                                key=f"ref_temizle_onay_{fid}")
            if st.button("Tümünü Sil", type="primary", use_container_width=True,
                         key=f"ref_temizle_btn_{fid}", disabled=not _onay, icon=":material/delete:"):
                if ref_temizle(fid):
                    st.cache_data.clear()
                    st.success("✅ Bu firmanın tüm ref no kayıtları silindi.")
                    st.rerun()
                else:
                    st.error("Silme başarısız oldu.")
    if st.button("Toplu Sil", key="btn_ref_sil", use_container_width=True, icon=":material/delete:"):
        _dlg_ref_toplu_sil()


# ── SEKME 2: HAVUZ BÜTÇE ────────────────────────────────────────────
def _render_butce(fid, firma):
    kayitlar = get_butce(fid)
    giris = sum(_f(r.get("tutar")) for r in kayitlar if r.get("yon") == "giris")
    harcama = sum(_f(r.get("tutar")) for r in kayitlar if r.get("yon") != "giris")
    kalan = giris - harcama

    # Bu firmaya atanan ref no'ların toplamı (USD'ye çevrilmiş) — havuz kullanımını gösterir
    _kur = 0.0
    try:
        _kur = float(st.session_state.get("kur") or 0)
    except Exception:
        _kur = 0.0
    ref_usd = 0.0
    for r in get_refler(fid):
        if str(r.get("durum") or "").lower() == "iptal":
            continue
        t = _f(r.get("tutar"))
        dv = (r.get("doviz") or "USD").strip().upper()
        if dv in ("TL", "TRY", "₺", "TRL"):
            t = (t / _kur) if _kur else 0.0
        ref_usd += t

    metrik_satiri([
        {"label": "Toplam Bütçe (giriş)", "value": f"${tr_sayi(giris, 2)}", "renk": trenk("yesil")},
        {"label": "Toplam Harcama", "value": f"${tr_sayi(harcama, 2)}", "renk": trenk("kirmizi"), "anlam": "notr"},
        {"label": "Kalan Havuz", "value": f"${tr_sayi(kalan, 2)}", "renk": trenk("mor2")},
        {"label": "Atanan Ref No (USD)", "value": f"${tr_sayi(ref_usd, 2)}", "renk": trenk("mor")},
    ])

    # ── Yeni kayıt ekle ──
    @st.dialog("➕ Yeni Bütçe / Harcama Kaydı Ekle", width="large")
    def _dlg_butce_yeni():
        ref_secenek = [""] + [r.get("ref_no", "") for r in get_refler(fid)]
        with st.form(f"butce_ekle_{fid}", clear_on_submit=True):
            b1, b2, b3, b3b = st.columns([1.3, 1.1, 1, 0.9])
            b_tur = b1.selectbox("Tür", BUTCE_TURLER, index=0,
                                 help="BÜTÇE genelde giriş; sağdaki Yön ile kesinleştir")
            b_yon = b2.selectbox("Yön", ["harcama", "giris"],
                                 format_func=lambda y: "Giriş (+)" if y == "giris" else "Harcama (−)",
                                 help="Önden verilen bütçe = Giriş; sellout/destek = Harcama")
            b_tutar = b3.number_input("Tutar", min_value=0.0, value=0.0, step=100.0)
            b_doviz = b3b.selectbox("Döviz", ["USD", "EUR", "TL"], index=0)
            b_ack = st.text_input("Açıklama", placeholder="örn. TEMMUZ FAZEON SELLOUT")
            b4, b5, b6 = st.columns(3)
            b_fno = b4.text_input("Fatura No", placeholder="örn. UYSD-8459")
            b_ftar = b5.date_input("Fatura Tarihi", value=date.today(), format="DD.MM.YYYY")
            b_ref = b6.selectbox("Ref No", ref_secenek, index=0)
            b_kisi = st.text_input("Kişi / Sorumlu", placeholder="örn. DERYA MOLLAOĞLU")
            if st.form_submit_button("Kaydı Ekle", type="primary", use_container_width=True, icon=":material/add:"):
                ok, msg = butce_ekle(fid, b_tur, b_ack.strip(), b_tutar, b_doviz,
                                     b_fno.strip(), b_ftar, b_ref, b_kisi.strip(), yon=b_yon)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()
    if st.button("Yeni Bütçe / Harcama Kaydı Ekle", key="btn_but_yeni", use_container_width=True, icon=":material/add:"):
        _dlg_butce_yeni()

    # ── Excel içe aktar ──
    @st.dialog("📥 Excel'den İçe Aktar (Havuz Bütçe formatı)", width="large")
    def _dlg_butce_ice():
        st.caption("Sütunlar: TÜR · MARKA · AÇIKLAMA · HAKEDİŞ BÜTÇE · TUTAR · DÖVİZ · FATURA NO · FATURA TARİH · FİRMA · REF NO · AÇIKLAMA(kişi)")
        upb = st.file_uploader("Havuz bütçe Excel'i", type=["xlsx", "xls"], key=f"butce_up_{fid}")
        temizle = st.checkbox("Önce mevcut bütçe kayıtlarını sil (güncel listeyi baştan yükle)",
                              key=f"butce_temizle_{fid}")
        if upb is not None:
            try:
                df_b = pd.read_excel(upb)
                st.dataframe(df_b.head(15), use_container_width=True, height=200)
                if st.button("İçe Aktar", type="primary", key=f"butce_imp_{fid}", icon=":material/move_to_inbox:"):
                    ok, msg, _n = butce_excel_ice_aktar(fid, df_b, temizle=temizle, dosya_adi=upb.name)
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.rerun()
            except Exception as e:
                st.error(f"Excel okunamadı: {e}")
    if st.button("Excel'den İçe Aktar (Havuz Bütçe formatı)", key="btn_but_ice", use_container_width=True, icon=":material/move_to_inbox:"):
        _dlg_butce_ice()

    if not kayitlar:
        st.info("Bu firma için henüz havuz bütçe kaydı yok. Yukarıdan ekleyebilir veya Excel'den içe aktarabilirsiniz.")
        return

    # ── Hareket defteri (düzenlenebilir) ──
    st.markdown("##### 📋 Destek Kayıtları (düzenle / sil)")
    ara = st.text_input("🔍 Ara (açıklama / fatura / ref / kişi)", key=f"butce_ara_{fid}").strip().lower()

    def _eslesir(r):
        if not ara:
            return True
        return ara in (str(r.get("aciklama", "")) + " " + str(r.get("fatura_no", "")) + " " +
                       str(r.get("ref_no", "")) + " " + str(r.get("kisi", "")) + " " +
                       str(r.get("tur", ""))).lower()

    goster = [r for r in kayitlar if _eslesir(r)]
    st.caption(f"{len(goster)} / {len(kayitlar)} kayıt")

    df_b = pd.DataFrame([{
        "id": r["id"], "Sil?": False, "Tür": r.get("tur", "") or "",
        "Yön": r.get("yon", "harcama") or "harcama",
        "Açıklama": r.get("aciklama", "") or "", "Tutar": _f(r.get("tutar")),
        "Fatura No": r.get("fatura_no", "") or "", "Tarih": pd.to_datetime(r.get("fatura_tarih"), errors="coerce"),
        "Ref No": r.get("ref_no", "") or "", "Kişi": r.get("kisi", "") or "",
    } for r in goster])

    edited = st.data_editor(
        df_b, use_container_width=True, hide_index=True, num_rows="fixed",
        key=f"butce_editor_{fid}_{ara}",
        column_config={
            "id": None,
            "Sil?": st.column_config.CheckboxColumn("Sil?", width="small"),
            "Tür": st.column_config.TextColumn("Tür"),
            "Yön": st.column_config.SelectboxColumn("Yön", options=["giris", "harcama"],
                                                    required=True, width="small",
                                                    help="giris = bütçe girişi (+), harcama = destek (−)"),
            "Açıklama": st.column_config.TextColumn("Açıklama", width="large"),
            "Tutar": st.column_config.NumberColumn("Tutar ($)", format="localized", step=0.0001),
            "Fatura No": st.column_config.TextColumn("Fatura No"),
            "Tarih": st.column_config.DateColumn("Tarih", format="DD.MM.YYYY"),
            "Ref No": st.column_config.TextColumn("Ref No"),
            "Kişi": st.column_config.TextColumn("Kişi"),
        },
    )
    if st.button("Değişiklikleri Kaydet", type="primary", key=f"butce_save_{fid}", icon=":material/save:"):
        orijinal = {r["id"]: r for r in goster}
        silinen = degisen = 0
        # Silinemeyen kayıtlar. Eskiden bu liste HİÇ oluşturulmuyordu: her kaydetmede
        # NameError — değişiklik yoksa sayfa çöküyor, varsa güncelleme yazılıp önbellek
        # temizlenmeden hata veriyordu.
        _sil_hata = []
        for _, row in edited.iterrows():
            rid = row["id"]
            if bool(row.get("Sil?")):
                if butce_sil(rid):
                    silinen += 1
                else:
                    _o = orijinal.get(rid, {})
                    _sil_hata.append(f"{_o.get('aciklama') or _o.get('tur') or 'kayıt'} "
                                     f"({_o.get('fatura_no') or rid})")
                continue
            o = orijinal.get(rid, {})
            n_tur = str(row.get("Tür", "") or "")
            n_yon = str(row.get("Yön", "harcama") or "harcama")
            n_ack = str(row.get("Açıklama", "") or "")
            n_tut = _f(row.get("Tutar"))
            n_fno = str(row.get("Fatura No", "") or "")
            _tt = row.get("Tarih")
            n_tar = (_tt.strftime("%Y-%m-%d") if (pd.notna(_tt) and hasattr(_tt, "strftime")) else None)
            n_ref = str(row.get("Ref No", "") or "")
            n_kisi = str(row.get("Kişi", "") or "")
            if (n_tur != (o.get("tur", "") or "") or n_yon != (o.get("yon", "") or "") or
                    n_ack != (o.get("aciklama", "") or "") or
                    abs(n_tut - _f(o.get("tutar"))) > 0.001 or n_fno != (o.get("fatura_no", "") or "") or
                    (n_tar or "") != (str(o.get("fatura_tarih") or "")[:10]) or
                    n_ref != (o.get("ref_no", "") or "") or n_kisi != (o.get("kisi", "") or "")):
                butce_guncelle(rid, n_tur, n_ack, n_tut, n_fno, n_tar, n_ref, n_kisi, yon=n_yon)
                degisen += 1
        if degisen or silinen:
            st.success(f"✅ {degisen} güncellendi, {silinen} silindi.")
        elif not _sil_hata:
            st.info("Değişiklik yok. (Silmek için satırdaki 'Sil?' kutusunu işaretle, "
                    "sonra butona bas.)")
        if _sil_hata:
            st.error("❌ Silinemeyen kayıtlar:\n\n" + "\n\n".join(_sil_hata))
        if degisen or silinen:
            st.cache_data.clear()
            st.rerun()

    # ── Toplu sil (görünen kayıtlar / firmanın tümü) ──
    st.markdown("---")
    @st.dialog("🗑 Toplu Sil — arama sonucundaki kayıtları veya tüm bütçeyi sil", width="large")
    def _dlg_butce_sil():
        st.caption("Silme geri alınamaz. Önce yukarıdaki arama ile daralt → 'görünenleri sil' yalnızca "
                   "filtrelenen kayıtları siler; ya da bu firmanın tüm havuz bütçe kayıtlarını temizle.")
        _bs1, _bs2 = st.columns(2)
        with _bs1:
            if st.button(f"Aramada görünen {len(goster)} kaydı sil",
                         use_container_width=True, key=f"butce_bulk_goster_{fid}",
                         disabled=(len(goster) == 0), icon=":material/delete:"):
                _sil = 0
                for _r in goster:
                    if butce_sil(_r["id"]):
                        _sil += 1
                st.cache_data.clear()
                st.success(f"✅ {_sil} kayıt silindi.")
                st.rerun()
        with _bs2:
            _onay = st.checkbox(f"Onaylıyorum — bu firmanın TÜM ({len(kayitlar)}) kaydını sil",
                                key=f"butce_temizle_onay_{fid}")
            if st.button("Tümünü Sil", type="primary", use_container_width=True,
                         key=f"butce_temizle_btn_{fid}", disabled=not _onay, icon=":material/delete:"):
                if butce_temizle(fid):
                    st.cache_data.clear()
                    st.success("✅ Bu firmanın tüm bütçe kayıtları silindi.")
                    st.rerun()
                else:
                    st.error("Silme başarısız oldu.")
    if st.button("Toplu Sil — arama sonucundaki kayıtları veya tüm bütçeyi sil", key="btn_but_sil", use_container_width=True, icon=":material/delete:"):
        _dlg_butce_sil()


@st.cache_data(ttl=120, show_spinner=False)
def get_tum_butce_harcamalari(baslangic, bitis):
    """Yönetim Panosu (P&L) için: TÜM firmaların havuz bütçe HARCAMA kayıtları.
    Giriş (BÜTÇE/depozito) hariç tutulur; sadece sellout/destek harcamaları döner.
    fatura_tarih [baslangic, bitis] aralığında filtrelenir. Arayüzde kullanılmaz."""
    try:
        sb = get_client()
        rows = _rows(sb.table("ref_butce").select("*")
                     .gte("fatura_tarih", str(baslangic))
                     .lte("fatura_tarih", str(bitis)).execute())
    except Exception:
        return []
    out = []
    for r in (rows or []):
        yon = str(r.get("yon") or _yon_belirle(r.get("tur"))).strip().lower()
        tur = _norm(r.get("tur"))
        if yon in ("giris", "giriş") or tur == _norm("BÜTÇE"):
            continue
        out.append({
            "tur": r.get("tur") or "",
            "tutar": _f(r.get("tutar")),
            "doviz": r.get("doviz") or "USD",
            "fatura_tarih": r.get("fatura_tarih") or "",
            "marka": r.get("marka") or "",
            "firma_id": r.get("firma_id"),
        })
    return out


@st.cache_data(ttl=120, show_spinner=False)
def get_tum_ref_tutarlari(baslangic, bitis):
    """Yönetim/Satış P&L için: TÜM firmaların ref no tutarları (havuz bütçeden AYRI destek).
    İptal edilenler hariç. Öncelik sırası:
      1) 'aylik' JSONB ({"YYYY-MM": tutar}) varsa → ay bazında, dönemle KESİŞEN aylar dahil
         (aylık/çeyreklik/yıllık hepsinde doğru döner).
      2) yoksa 'tarih' varsa → tarih dönem içindeyse.
      3) o da yoksa 'yil' → dönem o yılın başına ulaşıyorsa (YTD/yıllık/tümü)."""
    try:
        sb = get_client()
        try:
            rows = _rows(sb.table("ref_kayitlari")
                         .select("tutar,doviz,tarih,durum,yil,firma_id,aylik,"
                                 "kategori,kategori_tutar,ref_no").execute())
        except Exception:
            try:  # 'kategori_tutar' kolonu henüz yoksa
                rows = _rows(sb.table("ref_kayitlari")
                             .select("tutar,doviz,tarih,durum,yil,firma_id,aylik,"
                                     "kategori,ref_no").execute())
            except Exception:  # 'aylik' kolonu da yoksa
                rows = _rows(sb.table("ref_kayitlari")
                             .select("tutar,doviz,tarih,durum,yil,firma_id").execute())
    except Exception:
        return []
    _b, _e = str(baslangic)[:10], str(bitis)[:10]

    def _ay_kesisiyor(yyyymm):
        # o ayın [ilk, son] günü ile [_b, _e] kesişiyor mu
        try:
            y, m = yyyymm.split("-")[:2]
            ilk = f"{int(y):04d}-{int(m):02d}-01"
            son = f"{int(y):04d}-{int(m):02d}-28"  # 28 yeterli (aralık kontrolü için)
        except Exception:
            return False
        return not (son < _b or ilk > _e)

    out = []
    for r in (rows or []):
        if str(r.get("durum") or "").lower() == "iptal":
            continue
        _doviz = (r.get("doviz") or "USD")
        _fid = r.get("firma_id")
        # Kategori bilgisi her çıktı satırına taşınır — kırılım bunun üzerine kurulur
        _kbilgi = {"kategori": r.get("kategori") or "",
                   "kategori_tutar": r.get("kategori_tutar") or {},
                   "ham_tutar": _f(r.get("tutar")),
                   "ref_no": r.get("ref_no") or ""}
        _aylik = r.get("aylik") or {}
        if isinstance(_aylik, str):
            try:
                import json
                _aylik = json.loads(_aylik)
            except Exception:
                _aylik = {}
        if isinstance(_aylik, dict) and _aylik:
            # 1) Aylık kırılım — dönemle kesişen ayların tutarları
            _aylik_toplam = 0.0
            for _ay, _tt in _aylik.items():
                _tt = _f(_tt)
                if _tt > 0:
                    _aylik_toplam += _tt
                    if _ay_kesisiyor(str(_ay)):
                        out.append({"tutar": _tt, "doviz": _doviz,
                                    "tarih": f"{_ay}-01", "firma_id": _fid, **_kbilgi})
            # ── EKSİK BAKİYE TELAFİSİ ──
            # aylik JSONB'sinin toplamı ham 'tutar'dan azsa (ay/yıl bilgisi eksik
            # satırlar aylik'e yazılmamışsa), kayıp bakiye vardır. Bu artığı kaydın
            # kendi tarih/yıl bilgisine göre dönem içindeyse ekle — yoksa sessizce yok olur.
            _ham = _f(r.get("tutar"))
            _artik = _ham - _aylik_toplam
            if _artik > 0.005:
                # Telafide de planlama yılı önceliklidir (tarih ikincil)
                _y = str(r.get("yil") or "").strip()
                _tar = str(r.get("tarih") or "").strip()
                _dahil = False
                if _y and _y.isdigit():
                    _dahil = not (f"{_y}-12-31" < _b or f"{_y}-01-01" > _e)
                elif _tar and _tar.lower() != "none":
                    _dahil = (_b <= _tar[:10] <= _e)
                if _dahil:
                    out.append({"tutar": _artik, "doviz": _doviz,
                                "tarih": (f"{_y}-01-01" if _y else (_tar or "")),
                                "firma_id": _fid, **_kbilgi})
            continue
        t = _f(r.get("tutar"))
        if t <= 0:
            continue
        # ── DÖNEM EŞLEME (aylik JSONB yok) ──
        # ÖNCELİK: 'yil' alanı (planlama yılı — Ref No sayfası da buna göre gruplar).
        # Bir kaydın fatura 'tarih'i başka yıla düşse bile planlama yılı esastır;
        # aksi halde tarih≠yil olan kayıtlar Yönetim'de dönem dışı kalıp KAYBOLUR.
        _y = str(r.get("yil") or "").strip()
        _tar = str(r.get("tarih") or "").strip()
        _dahil = False
        if _y and _y.isdigit():
            # planlama yılının [ilk, son] günü dönemle kesişiyor mu
            _dahil = not (f"{_y}-12-31" < _b or f"{_y}-01-01" > _e)
        elif _tar and _tar.lower() != "none":
            _dahil = (_b <= _tar[:10] <= _e)
        if not _dahil:
            continue
        out.append({"tutar": t, "doviz": _doviz,
                    "tarih": (f"{_y}-01-01" if _y else (r.get("tarih") or "")),
                    "firma_id": _fid, **_kbilgi})
    return out


def _kat_liste(metin):
    """'MOUSEPAD · monitör' → ['MOUSE PAD','MONİTÖR'] — kanonik, boşlar atılır.
    (kategori_kanonik ile: katalog yazımına indirir, filtrede kaybolmaz.)"""
    return [k for k in (kategori_kanonik(x) for x in str(metin or "").split("·")) if k]


# ═══════════════════════════════════════════════════════════════════
#  KALEM YAPISI  (ref_kayitlari.kalemler JSONB)
#
#  ESKİ: aciklama tek metin ("A · B · C"), tutar tek sayı, aylik ve
#  kategori_tutar AYRI JSON'lar. Üçü elle senkron tutuluyordu; biri
#  değişince diğerleri bozuluyordu.
#
#  YENİ: her kalem kendi tutarını/ayını/kategorisini taşır:
#     [{"aciklama": "...", "tutar": 249.0, "ay": "2026-03",
#       "kategori": "MONİTÖR"}, ...]
#  tutar · aylik · kategori_tutar artık BURADAN TÜRETİLİR → tek kaynak.
# ═══════════════════════════════════════════════════════════════════

_AY_ADI = {"OCAK": 1, "ŞUBAT": 2, "SUBAT": 2, "MART": 3, "NİSAN": 4, "NISAN": 4,
           "MAYIS": 5, "HAZİRAN": 6, "HAZIRAN": 6, "TEMMUZ": 7, "AĞUSTOS": 8,
           "AGUSTOS": 8, "EYLÜL": 9, "EYLUL": 9, "EKİM": 10, "EKIM": 10,
           "KASIM": 11, "ARALIK": 12}


def kalemleri_oku(kayit):
    """Kaydın kalem listesi. Yoksa [] döner (eski kayıtlar için güvenli)."""
    ham = (kayit or {}).get("kalemler")
    if isinstance(ham, str):
        try:
            import json as _j
            ham = _j.loads(ham)
        except Exception:
            ham = []
    if not isinstance(ham, list):
        return []
    out = []
    for k in ham:
        if not isinstance(k, dict):
            continue
        out.append({
            "aciklama": str(k.get("aciklama") or "").strip(),
            "tutar": _f(k.get("tutar")),
            "ay": str(k.get("ay") or "").strip(),
            "kategori": _tr_upper(str(k.get("kategori") or "").strip()),
        })
    return out


def kalemlerden_turet(kalemler):
    """Kalemlerden tutar · aylik · kategori_tutar · aciklama üretir.

    Bu fonksiyon TEK GERÇEK KAYNAK: kalem eklenince/silinince üç alan da
    kendiliğinden tutarlı kalır. Elle senkron tutmaya gerek yok.
    """
    kalemler = kalemler or []
    toplam = round(sum(_f(k.get("tutar")) for k in kalemler), 2)
    aylik, kat = {}, {}
    for k in kalemler:
        t = _f(k.get("tutar"))
        if t == 0:
            continue
        a = str(k.get("ay") or "").strip()
        if a:
            aylik[a] = round(aylik.get(a, 0.0) + t, 2)
        c = _tr_upper(str(k.get("kategori") or "").strip())
        if c:
            kat[c] = round(kat.get(c, 0.0) + t, 2)
    aciklama = " · ".join(str(k.get("aciklama") or "").strip()
                          for k in kalemler if str(k.get("aciklama") or "").strip())
    return {"tutar": toplam, "aylik": aylik, "kategori_tutar": kat,
            "aciklama": aciklama,
            "kategori": " · ".join(sorted(kat)) if kat else ""}


def kalemleri_yaz(ref_id, kalemler):
    """Kalemleri kaydeder ve türetilen alanları birlikte günceller."""
    t = kalemlerden_turet(kalemler)
    try:
        sb = get_client()
        _d = {"kalemler": kalemler,
              "tutar": t["tutar"],
              "aylik": t["aylik"],
              "kategori_tutar": t["kategori_tutar"],
              "aciklama": t["aciklama"]}
        if t["kategori"]:
            _d["kategori"] = t["kategori"]
        try:
            sb.table("ref_kayitlari").update(_d).eq("id", ref_id).execute()
        except Exception:
            # 'kalemler' kolonu henüz eklenmemişse onsuz yaz (bozulma olmasın)
            _d.pop("kalemler", None)
            sb.table("ref_kayitlari").update(_d).eq("id", ref_id).execute()
            _cache_temizle()
            return False, "⚠️ 'kalemler' kolonu yok — yalnız toplamlar güncellendi."
        _cache_temizle()
        return True, f"✅ {len(kalemler)} kalem kaydedildi · toplam {tr_sayi(t['tutar'], 2)}"
    except Exception as e:
        return False, f"❌ {type(e).__name__}: {str(e)[:140]}"


def ref_destek_kirilim_usd(baslangic, bitis):
    """Ref No desteklerinin KATEGORİ kırılımı (USD).

    Döner: {"kategori": {KAT: usd}, "genel": usd, "toplam": usd,
            "dagitilmayan": [{ref_no, kategoriler, usd}]}

    MARKA boyutu YOKTUR: ref kaydının firması bir CARİdir (müşteri), marka
    değil. Ref No desteği yalnız kategori boyutuna dağıtılabilir.

    Dağıtım kuralı:
      • Kayıt TEK kategoriliyse → tutarın tamamı o kategoriye.
      • kategori_tutar JSON'ı doluysa → o oranlara göre bölünür.
      • Çok kategorili ama kategori_tutar boşsa → GENEL'e yazılır ve
        'dagitilmayan' listesine düşer. Eşit bölme YAPILMAZ; uydurmak yerine
        eksik olduğu açıkça raporlanır.
    """
    kat, genel, toplam = {}, 0.0, 0.0
    # MARKA boyutu YOK — ref kaydının firması bir CARİdir (D-MARKET, VATAN),
    # marka değil. Marka kırılımına çevirmek "D-MARKET ELEKTRONİK HİZMETLER"
    # gibi carileri marka tablosuna sokuyordu.
    dagitilmayan, gorulen = {}, set()
    _kur_tl = None
    for r in (get_tum_ref_tutarlari(baslangic, bitis) or []):
        t = _f(r.get("tutar"))
        if t <= 0:
            continue
        dv = str(r.get("doviz") or "USD").upper()
        if dv in ("TL", "TRY", "₺", "TRL"):
            if _kur_tl is None:
                _kur_tl = _alinan_kur()
            if not _kur_tl:
                continue
            t = t / _kur_tl
        elif dv in ("EUR", "EURO", "€"):
            t = t * _eur_usd_kur()
        toplam += t

        kats = _kat_liste(r.get("kategori"))
        if len(kats) == 1:
            kat[kats[0]] = kat.get(kats[0], 0.0) + t
            continue
        if len(kats) > 1:
            kt = r.get("kategori_tutar") or {}
            if isinstance(kt, str):
                try:
                    import json
                    kt = json.loads(kt)
                except Exception:
                    kt = {}
            paylar = {_tr_upper(k): _f(v) for k, v in (kt or {}).items() if _f(v) > 0}
            _pt = sum(paylar.values())
            if _pt > 0.005:
                # Dönem tutarı, kayıttaki kategori oranlarına göre bölünür.
                # "TÜM KATEGORİLER" tek bir kategoriye ait değildir → GENEL'e
                # yazılır; filtreye yansıtmak yanlış olur.
                for k, v in paylar.items():
                    _pay = t * (v / _pt)
                    if k in ("TÜM KATEGORİLER", "TUM KATEGORILER", "GENEL"):
                        genel += _pay
                    else:
                        kat[k] = kat.get(k, 0.0) + _pay
                continue
            _rn = str(r.get("ref_no") or "").strip() or "—"
            if _rn not in gorulen:
                gorulen.add(_rn)
                dagitilmayan[_rn] = {"ref_no": _rn, "kategoriler": kats, "usd": 0.0}
            dagitilmayan[_rn]["usd"] += t
        genel += t
    return {"kategori": kat, "genel": genel, "toplam": toplam,
            "dagitilmayan": sorted(dagitilmayan.values(), key=lambda x: -x["usd"])}


def ref_kategori_onerisi(aciklama, kategoriler=None):
    """Açıklama metnini tarayıp hangi kategorilerin geçtiğini önerir.

    'Q425 FAZEON KASA SOĞUTUCU REBATE' → ['KASA','SOĞUTUCU'] gibi.
    Tutar ÖNERMEZ — açıklamalarda kalem bazlı tutar yok. Yalnız hangi
    kategorileri işaretlemen gerektiğini bulmanı kolaylaştırır.
    """
    metin = _tr_upper(str(aciklama or ""))
    if not metin:
        return []
    havuz = kategoriler if kategoriler is not None else _urun_kategorileri()
    bulunan = []
    for k in havuz:
        ku = _tr_upper(str(k or "").strip())
        if len(ku) >= 3 and ku in metin and ku not in bulunan:
            bulunan.append(ku)
    return bulunan


# ════════════════════════════════════════════════════════════════════
#  HAVUZ DESTEĞİ → KÂR/P&L ENTEGRASYONU
#  Sellout/marketing desteği bir GİDERdir: firmaya VERİLEN bütçe (GİRİŞ)
#  verildiği dönemde marj/kârdan düşülür. Firmanın bu bütçeden yaptığı
#  HARCAMA, yalnızca "ne kadar kullanıldı / ne kadar kaldı" takibidir;
#  Kâr/P&L'ye tekrar yansıtılmaz (çift sayım olmaması için).
#  → Kâr/P&L gideri = VERİLEN (giriş). Kalan = verilen − kullanılan.
# ════════════════════════════════════════════════════════════════════
def _havuz_hesapla(kayitlar, firmalar):
    """SAF: ref_butce kayıt listesi + {firma_id: firma} → firma/rol bazlı havuz.
    verilen = GİRİŞ toplamı (Kâr/P&L gideri), kullanilan = HARCAMA toplamı (takip),
    kalan = verilen − kullanilan. Sadece USD kayıtlar; farklı dövizli kayıt sayısı
    'atlanan_doviz'."""
    agg = {}
    atlanan_doviz = 0
    for k in kayitlar:
        if _norm(k.get("doviz") or "USD") != _norm("USD"):
            atlanan_doviz += 1
            continue
        fid = k.get("firma_id")
        o = agg.setdefault(fid, {"verilen": 0.0, "kullanilan": 0.0})
        t = _f(k.get("tutar"))
        if _norm(k.get("yon")) == _norm("GİRİŞ"):
            o["verilen"] += t
        else:
            o["kullanilan"] += t
    firma_list, rol_verilen = [], {}
    top_verilen = top_kullanilan = 0.0
    for fid, v in agg.items():
        kalan = v["verilen"] - v["kullanilan"]
        f = firmalar.get(fid) or {}
        rol = _firma_rol(f) if f else None
        firma_list.append({
            "firma": f.get("firma_adi") or "(bilinmeyen firma)",
            "kod": f.get("firma_kodu") or "", "rol": rol or "—",
            "verilen": v["verilen"], "kullanilan": v["kullanilan"], "kalan": kalan,
        })
        if rol:
            rol_verilen[rol] = rol_verilen.get(rol, 0.0) + v["verilen"]
        top_verilen += v["verilen"]
        top_kullanilan += v["kullanilan"]
    firma_list.sort(key=lambda x: -x["verilen"])
    return {"verilen": top_verilen, "kullanilan": top_kullanilan,
            "kalan": top_verilen - top_kullanilan, "firmalar": firma_list,
            "rol_verilen": rol_verilen, "atlanan_doviz": atlanan_doviz}


@st.cache_data(ttl=60, show_spinner=False)
def havuz_destek_donem(bas, bit):
    # HAVUZ KALDIRILDI: hiçbir dönemde kâr/aktif hesabına girmez.
    # (Geri açmak için aşağıdaki satırı sil.)
    return {"verilen": 0.0, "kullanilan": 0.0, "kalan": 0.0,
            "firmalar": [], "atlanan_doviz": 0}
    """Dönem (fatura_tarih ∈ [bas, bit]) içindeki havuz desteğini döndürür.
    Döner: {verilen, kullanilan, kalan, firmalar:[{firma,kod,rol,verilen,kullanilan,kalan}],
    rol_verilen:{rol:verilen}, atlanan_doviz}. Kâr/P&L gideri = 'verilen'.
    fatura_tarih boş olan kayıtlar döneme dahil edilmez."""
    bos = {"verilen": 0.0, "kullanilan": 0.0, "kalan": 0.0, "firmalar": [],
           "rol_verilen": {}, "atlanan_doviz": 0}
    sb = get_client()
    if not sb:
        return bos
    bas_s, bit_s = str(bas)[:10], str(bit)[:10]
    try:
        kayitlar = _rows(sb.table("ref_butce").select("*")
                         .gte("fatura_tarih", bas_s).lte("fatura_tarih", bit_s).execute())
    except Exception:
        return bos
    try:
        firmalar = {f["id"]: f for f in get_firmalar()}
    except Exception:
        firmalar = {}
    return _havuz_hesapla(kayitlar, firmalar)


# ════════════════════════════════════════════════════════════════════
#  TEK KAYNAK: v_destek_donem SQL VIEW
#  Kural veritabanında BİR kez tanımlı → tüm ekranlar aynı rakamı okur.
# ════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=120, show_spinner=False)
def get_destek_donem(baslangic, bitis):
    """v_destek_donem view'inden dönem destek satırları.
    Döner: list[{kaynak, tur, firma_id, doviz, donem, tutar}]
    View henüz kurulmadıysa/erişilemezse None döner → çağıran taraf
    eski Python hesabına düşer (sıfır riskli geçiş)."""
    try:
        sb = get_client()
        rows = (sb.table("v_destek_donem").select("*")
                .gte("donem", str(baslangic)[:10])
                .lte("donem", str(bitis)[:10])
                .limit(20000).execute().data)
        return rows if rows is not None else []
    except Exception:
        return None


_AD_TUR_RENK = {
    "SELLOUT": "#34D399", "MARKETING": "#818CF8", "REBATE": "#22D3EE",
    "PRICE PROTECTION": "#FBBF24", "PAZARLAMA": "#F9A8D4",
    "BEDELSİZ ÜRÜN": "#7DD3FC", "DİĞER": "#94A3B8",
}

