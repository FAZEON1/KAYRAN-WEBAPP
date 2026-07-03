# -*- coding: utf-8 -*-
"""Firma bazlı Referans No + Havuz Bütçe (sellout / marketing destek) modülü.

Ref no formatı:  FZ<KOD>RF<YIL><SIRA:03d>   ör. FZVTNRF2025001

Havuz Bütçe mantığı:
  - TÜR = "BÜTÇE"  → önden verilen bütçe (GİRİŞ +)
  - Diğer türler   → sellout / destek harcaması (HARCAMA −)
  - Kalan havuz    = toplam giriş − toplam harcama
"""
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


def _ay_no(ad):
    s = str(ad or "").strip()
    for a, b in (("İ", "I"), ("ı", "I"), ("Ş", "S"), ("ş", "S"), ("Ğ", "G"), ("ğ", "G"),
                 ("Ü", "U"), ("ü", "U"), ("Ö", "O"), ("ö", "O"), ("Ç", "C"), ("ç", "C")):
        s = s.replace(a, b)
    s = s.upper()
    if s.isdigit() and 1 <= int(s) <= 12:
        return int(s)
    return _AY_NO.get(s, 0)


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
@st.cache_data(ttl=30, show_spinner=False)
def get_firmalar():
    try:
        sb = get_client()
        return _rows(sb.table("ref_firmalar").select("*").order("firma_adi").execute())
    except Exception:
        return []


def firma_ekle(adi, kodu):
    try:
        sb = get_client()
        sb.table("ref_firmalar").insert(
            {"firma_adi": adi.strip(), "firma_kodu": kodu.strip().upper()}
        ).execute()
        _cache_temizle()
        return True, f"✅ '{adi}' firması eklendi."
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}"


# ── CARİ EŞLEŞTİRME (firma adları muhasebe cari isimlerinden gelir) ───
# rol → tespit anahtarları (ad/kod), cari ismi öneki, döviz tercihi
FIRMA_ESLESME = {
    "ITOPYA": {"tespit": ("ITOPYA", "ITP", "EERA"),     "onek": "EERA",     "doviz": None},
    "HB":     {"tespit": ("HB", "D-MARKET", "DMARKET", "HEPSIBURADA", "HEPSİBURADA"), "onek": "D-MARKET", "doviz": None},
    "VATAN":  {"tespit": ("VATAN", "VTN"),              "onek": "VATAN",    "doviz": "USD"},
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


@st.cache_data(ttl=120, show_spinner=False)
def _cari_isimleri():
    try:
        from kayranacc.database import get_cari_isimler
        return [str(c).strip() for c in (get_cari_isimler() or []) if str(c).strip()]
    except Exception:
        return []


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
@st.cache_data(ttl=30, show_spinner=False)
def get_refler(firma_id):
    try:
        sb = get_client()
        return _rows(sb.table("ref_kayitlari").select("*")
                     .eq("firma_id", firma_id).order("sira_no").execute())
    except Exception:
        return []


def _sonraki_sira(firma_id):
    refler = get_refler(firma_id)
    return max((int(r.get("sira_no") or 0) for r in refler), default=0) + 1


def ref_ekle(firma_id, kod, aciklama, durum="beklemede", tarih=None, yil=None, tutar=0, doviz="USD"):
    try:
        sb = get_client()
        sira = _sonraki_sira(firma_id)
        yil = yil or _yil()
        ref_no = ref_uret(kod, yil, sira)
        sb.table("ref_kayitlari").insert({
            "firma_id": firma_id, "sira_no": sira, "ref_no": ref_no,
            "aciklama": aciklama or "", "durum": durum, "yil": yil,
            "tarih": str(tarih) if tarih else None,
            "paylasim_tarihi": str(tarih) if (durum == "paylasildi" and tarih) else None,
            "tutar": _f(tutar), "doviz": doviz or "USD",
        }).execute()
        _cache_temizle()
        return True, f"✅ {ref_no} atandı."
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}"


def ref_guncelle(ref_id, ref_no, aciklama, durum, tarih, paylasim_tarihi=None, tutar=None, doviz=None):
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
                     "aylik": {}}
                _agg[ref] = o
            o["tutar"] += tutar
            if _yln and _ayn and tutar:
                _ak = f"{_yln}-{_ayn:02d}"
                o["aylik"][_ak] = o["aylik"].get(_ak, 0.0) + tutar
            if ack and ack not in o["ack"]:
                o["ack"].append(ack)

        # 2) Ekle / güncelle — satır satır (dayanıklı; bir mükerrer tüm aktarımı bozmaz)
        eklenen = guncellenen = atlanan = hatali = 0
        for ref, o in _agg.items():
            _ack = " · ".join(o["ack"])[:500]
            if ref in mevcut_map:
                if guncelle_mevcut:
                    _upd = {"tutar": o["tutar"], "doviz": o["doviz"], "yil": o["yil"]}
                    if _ack:
                        _upd["aciklama"] = _ack
                    if o.get("aylik"):
                        _upd["aylik"] = o["aylik"]
                    try:
                        sb.table("ref_kayitlari").update(_upd).eq("id", mevcut_map[ref].get("id")).execute()
                        guncellenen += 1
                    except Exception:
                        _upd.pop("aylik", None)  # aylik kolonu yoksa onsuz dene
                        try:
                            sb.table("ref_kayitlari").update(_upd).eq("id", mevcut_map[ref].get("id")).execute()
                            guncellenen += 1
                        except Exception:
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
            try:
                sb.table("ref_kayitlari").insert(_ins).execute()
                eklenen += 1
            except Exception:
                _ins.pop("aylik", None)  # aylik kolonu yoksa onsuz dene
                try:
                    sb.table("ref_kayitlari").insert(_ins).execute()
                    eklenen += 1
                except Exception:
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
@st.cache_data(ttl=30, show_spinner=False)
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


def butce_excel_ice_aktar(firma_id, df, temizle=False):
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
        # Geçerli satır var → (istenirse) önce temizle, sonra ekle
        if temizle:
            sb.table("ref_butce").delete().eq("firma_id", firma_id).execute()
        for i in range(0, len(rows), 200):
            sb.table("ref_butce").insert(rows[i:i + 200]).execute()
        _cache_temizle()
        return True, f"✅ {len(rows)} bütçe kaydı içe aktarıldı.", len(rows)
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}", 0


# ════════════════════════════════════════════════════════════════════
# UI
# ════════════════════════════════════════════════════════════════════
def render():
    st.markdown('<div class="baslik">🔖 Ref No Takibi</div>', unsafe_allow_html=True)
    st.markdown('<div class="alt-baslik">Firma bazlı ref no atama + havuz bütçe takibi</div>',
                unsafe_allow_html=True)

    # Firma adlarını muhasebe cari isimleriyle eşitle + havuz bütçe düzelt (oturum başına bir kez)
    if not st.session_state.get("_ref_senk3"):
        try:
            _senkronize_firmalar()
        except Exception:
            pass
        st.session_state["_ref_senk3"] = True

    firmalar = get_firmalar()

    with st.expander("🏢 Yeni Firma Ekle"):
        _cariler = sorted(set(_cari_isimleri()), key=lambda s: s.lower())
        _mevcut = {_norm(f.get("firma_adi")) for f in firmalar}
        _secilebilir = [c for c in _cariler if _norm(c) not in _mevcut]
        with st.form("ref_firma_ekle", clear_on_submit=True):
            if _secilebilir:
                fa = st.selectbox("Firma (cari listesinden)", ["— seç —"] + _secilebilir)
                yf_adi = "" if fa == "— seç —" else fa
            else:
                yf_adi = st.text_input("Firma Adı", placeholder="örn. INCEHESAP")
                st.caption("Cari listesi boş — Muhasebe → Cari yükleyince buradan seçebilirsin.")
            yf_kod = st.text_input("Ref Kodu (kısaltma)", placeholder="örn. INC",
                                   help="Ref no'da kullanılır: FZ<KOD>RF<yıl><sıra>")
            if st.form_submit_button("➕ Firma Ekle", type="primary"):
                if not yf_adi.strip() or not yf_kod.strip():
                    st.warning("Firma (cari) ve ref kodu zorunlu.")
                else:
                    ok, msg = firma_ekle(yf_adi, yf_kod)
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.rerun()

    if not firmalar:
        st.info("Henüz firma yok. Yukarıdan 'Yeni Firma Ekle' ile başlayın (örn. VATAN / kod: VTN).")
        return

    _TUMU = "🌐 Tümü (tüm firmalar · birleşik liste)"
    fmap = {f"{f['firma_adi']}  ·  FZ{f['firma_kodu']}RF…": f for f in firmalar}
    sec_label = st.selectbox("Firma seç", [_TUMU] + list(fmap.keys()), key="ref_firma_sec")
    if sec_label == _TUMU:
        _render_tumu(firmalar)
        return
    firma = fmap[sec_label]

    tab1, tab2 = st.tabs(["🔖 Ref No'lar", "💰 Havuz Bütçe"])
    with tab1:
        _render_refler(firma["id"], firma["firma_kodu"])
    with tab2:
        if _firma_rol(firma) == "ITOPYA":
            _render_butce(firma["id"], firma)
        else:
            st.info("💰 Havuz bütçe yalnızca **EERA (ITOPYA)** firması için tutulur. "
                    "Şu an başka cariye havuz bütçe verilmiyor.")


def _render_tumu(firmalar):
    """Tüm firmaların ref no'larını firma sütunuyla birleşik, aramalı/filtreli gösterir (salt-okunur)."""
    def _trl(s):
        return str(s or "").replace("İ", "i").replace("I", "ı").lower()
    _hepsi = []
    for f in firmalar:
        _fad = f.get("firma_adi", "") or ""
        for r in get_refler(f["id"]):
            _r = dict(r)
            _r["_firma"] = _fad
            _hepsi.append(_r)
    _bekleyen = sum(1 for r in _hepsi if r.get("durum") == "beklemede")
    _paylasilan = sum(1 for r in _hepsi if r.get("durum") == "paylasildi")
    metrik_satiri([
        {"label": "Toplam Ref (tüm firmalar)", "value": f"{len(_hepsi):,}", "renk": "#818CF8"},
        {"label": "⏳ Beklemede", "value": f"{_bekleyen:,}", "renk": "#FBBF24"},
        {"label": "✅ Paylaşılan", "value": f"{_paylasilan:,}", "renk": "#34D399"},
        {"label": "💰 Toplam Tutar", "value": _tutar_ozet(_hepsi), "renk": "#A78BFA"},
    ])
    _c1, _c2 = st.columns([1, 2])
    durum_f = _c1.selectbox("Durum filtresi", ["Tümü"] + DURUMLAR,
                            format_func=lambda d: DURUM_ETIKET.get(d, d) if d != "Tümü" else d,
                            key="ref_tumu_durum")
    ara = _c2.text_input("🔍 Ara — Firma · Ref No · Açıklama · Tutar", key="ref_tumu_ara")
    _aral = _trl(ara)

    def _uy(r):
        if durum_f != "Tümü" and r.get("durum") != durum_f:
            return False
        if _aral:
            blob = _trl(f"{r.get('_firma','')} {r.get('ref_no','')} {r.get('aciklama','')} "
                        f"{r.get('tutar','')} {r.get('doviz','')} {r.get('yil','')}")
            if _aral not in blob:
                return False
        return True
    goster = [r for r in _hepsi if _uy(r)]
    st.caption(f"{len(goster)} / {len(_hepsi)} kayıt gösteriliyor · birleşik (tüm firmalar)")
    import pandas as pd
    st.dataframe(pd.DataFrame([{
        "Firma": (r.get("_firma", "") or "")[:32],
        "Ref No": r.get("ref_no", "") or "",
        "Açıklama": r.get("aciklama", "") or "",
        "Durum": DURUM_ETIKET.get(r.get("durum", ""), r.get("durum", "")),
        "Tutar": _f(r.get("tutar")),
        "Döviz": (r.get("doviz", "") or "USD"),
        "Ay": _aylik_ozet(r)[0],
        "Yıl": _aylik_ozet(r)[1],
    } for r in goster]), hide_index=True, use_container_width=True, height=460)
    st.caption("ℹ️ Birleşik görünüm salt-okunurdur. Ekleme · Excel içe aktarma · düzenleme · silme · bütçe için "
               "yukarıdan **tek bir firma** seç.")


# ── SEKME 1: REF NO'LAR ─────────────────────────────────────────────
def _tutar_ozet(refler):
    """Ref no'ların toplam tutarını döviz bazlı özetler: '$5.000 · ₺120.000'."""
    from collections import defaultdict
    d = defaultdict(float)
    for r in refler:
        dv = (r.get("doviz") or "USD").strip().upper()
        d[dv] += _f(r.get("tutar"))
    sembol = {"USD": "$", "TL": "₺", "TRY": "₺", "EUR": "€"}
    parcalar = [f"{sembol.get(k, k + ' ')}{v:,.0f}" for k, v in d.items() if v]
    return " · ".join(parcalar) if parcalar else "—"


def _render_refler(fid, fkod):
    refler = get_refler(fid)
    _bekleyen = sum(1 for r in refler if r.get("durum") == "beklemede")
    _paylasilan = sum(1 for r in refler if r.get("durum") == "paylasildi")
    metrik_satiri([
        {"label": "Toplam Ref", "value": f"{len(refler):,}", "renk": "#818CF8"},
        {"label": "⏳ Beklemede", "value": f"{_bekleyen:,}", "renk": "#FBBF24"},
        {"label": "✅ Paylaşılan", "value": f"{_paylasilan:,}", "renk": "#34D399"},
        {"label": "💰 Toplam Tutar", "value": _tutar_ozet(refler), "renk": "#A78BFA"},
    ])

    _siradaki = _sonraki_sira(fid)
    _onizleme = ref_uret(fkod, _yil(), _siradaki)
    st.markdown(
        '<div style="background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);'
        'border-radius:10px;padding:11px 16px;margin:8px 0 6px">'
        f'Sıradaki otomatik ref no: <b style="color:#A5B4FC;font-family:monospace;font-size:15px">{_onizleme}</b></div>',
        unsafe_allow_html=True,
    )
    with st.form("ref_ekle_form", clear_on_submit=True):
        yeni_ack = st.text_input("Açıklama", placeholder="örn. TEMMUZ MONİTÖR SELLOUT")
        rc1, rc2, rc3 = st.columns([1.4, 1, 1.4])
        yeni_tutar = rc1.number_input("Tutar", min_value=0.0, value=0.0, step=100.0, format="%.2f")
        yeni_doviz = rc2.selectbox("Döviz", DOVIZLER, index=0)
        yeni_durum = rc3.selectbox("Durum", DURUMLAR, format_func=lambda d: DURUM_ETIKET[d], index=0)
        yeni_tarih = st.date_input("Tarih", value=date.today())
        if st.form_submit_button("➕ Ref No Ata", type="primary", use_container_width=True):
            ok, msg = ref_ekle(fid, fkod, yeni_ack.strip(), yeni_durum, yeni_tarih,
                               tutar=yeni_tutar, doviz=yeni_doviz)
            (st.success if ok else st.error)(msg)
            if ok:
                st.rerun()

    with st.expander("📥 Excel'den İçe Aktar (NUMARA · REF NUMARASI · AÇIKLAMA)"):
        up = st.file_uploader("Bu firmanın ref Excel'i", type=["xlsx", "xls"], key=f"ref_up_{fid}")
        if up is not None:
            try:
                df_imp = pd.read_excel(up)
                st.dataframe(df_imp.head(20), use_container_width=True, height=200)
                imp_durum = st.selectbox("İçe aktarılan kayıtların durumu", DURUMLAR,
                                         format_func=lambda d: DURUM_ETIKET[d], index=1,
                                         key=f"ref_imp_durum_{fid}")
                imp_guncelle = st.checkbox(
                    "🔁 Mevcut ref'leri de güncelle (döviz/tutar/açıklamayı düzelt)",
                    key=f"ref_imp_guncelle_{fid}",
                    help="İşaretli: sistemde zaten olan ref no'ların döviz ve tutarı Excel'e göre güncellenir "
                         "(ör. yanlış USD → TL). İşaretsiz: mevcut ref'ler atlanır, sadece yeniler eklenir.")
                if st.button("📥 İçe Aktar", type="primary", key=f"ref_imp_btn_{fid}"):
                    ok, msg, _n = excel_ice_aktar(fid, df_imp, imp_durum, guncelle_mevcut=imp_guncelle)
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.rerun()
            except Exception as e:
                st.error(f"Excel okunamadı: {e}")

    st.markdown("#### 📋 Geçmiş Ref No'lar")
    if not refler:
        st.info("Bu firma için henüz ref no yok. Yukarıdan atayabilir veya Excel'den içe aktarabilirsiniz.")
        return

    f_durum = st.selectbox("Durum filtresi", ["Tümü"] + DURUMLAR,
                           format_func=lambda d: ("Tümü" if d == "Tümü" else DURUM_ETIKET[d]),
                           key=f"ref_durum_f_{fid}")
    goster = refler if f_durum == "Tümü" else [r for r in refler if r.get("durum") == f_durum]
    st.caption(f"{len(goster)} / {len(refler)} kayıt gösteriliyor")

    df_ed = pd.DataFrame([{
        "id": r["id"], "Sil?": False, "No": int(r.get("sira_no") or 0), "Ref No": r.get("ref_no", "") or "",
        "Açıklama": r.get("aciklama", "") or "", "Tutar": _f(r.get("tutar")),
        "Döviz": (r.get("doviz") or "USD"),
        "Ay": _aylik_ozet(r)[0], "Yıl": _aylik_ozet(r)[1],
        "Durum": r.get("durum", "beklemede") or "beklemede",
        "Tarih": pd.to_datetime(r.get("tarih"), errors="coerce"),
    } for r in goster])

    edited = st.data_editor(
        df_ed, use_container_width=True, hide_index=True, num_rows="fixed",
        key=f"ref_editor_{fid}_{f_durum}",
        column_config={
            "id": None,
            "Sil?": st.column_config.CheckboxColumn("Sil?", width="small",
                                                    help="İşaretle → Kaydet'e basınca bu kayıt silinir"),
            "No": st.column_config.NumberColumn("No", disabled=True, width="small"),
            "Ref No": st.column_config.TextColumn("Ref No", disabled=True),
            "Açıklama": st.column_config.TextColumn("Açıklama", width="large"),
            "Tutar": st.column_config.NumberColumn("Tutar", format="%.2f", width="small"),
            "Döviz": st.column_config.SelectboxColumn("Döviz", options=DOVIZLER, required=True, width="small"),
            "Ay": st.column_config.TextColumn("Ay", disabled=True,
                                              help="Excel'deki AY/YIL kolonlarından gelir; birden çok aya "
                                                   "yayılan ref'lerde aylar birlikte görünür. Değiştirmek için "
                                                   "Excel'i 'Mevcut ref'leri de güncelle' ile yeniden yükle."),
            "Yıl": st.column_config.TextColumn("Yıl", disabled=True, width="small"),
            "Durum": st.column_config.SelectboxColumn("Durum", options=DURUMLAR, required=True),
            "Tarih": st.column_config.DateColumn("Tarih", format="DD-MM-YYYY"),
        },
    )
    if st.button("💾 Değişiklikleri Kaydet", type="primary", key=f"ref_save_{fid}"):
        orijinal = {r["id"]: r for r in goster}
        degisen = silinen = 0
        for _, row in edited.iterrows():
            rid = row["id"]
            if bool(row.get("Sil?")):
                if ref_sil(rid):
                    silinen += 1
                continue
            o = orijinal.get(rid, {})
            n_ack = str(row.get("Açıklama", "") or "")
            n_dur = str(row.get("Durum", "beklemede"))
            _tt = row.get("Tarih")
            n_tar = (_tt.strftime("%Y-%m-%d") if (pd.notna(_tt) and hasattr(_tt, "strftime")) else None)
            n_tutar = _f(row.get("Tutar"))
            n_doviz = str(row.get("Döviz", "USD") or "USD")
            if (n_ack != (o.get("aciklama", "") or "") or n_dur != (o.get("durum") or "") or
                    (n_tar or "") != (str(o.get("tarih") or "")[:10]) or
                    n_tutar != _f(o.get("tutar")) or n_doviz != (o.get("doviz") or "USD")):
                pay = n_tar if n_dur == "paylasildi" else o.get("paylasim_tarihi")
                ref_guncelle(rid, str(row.get("Ref No", "")), n_ack, n_dur, n_tar, pay,
                             tutar=n_tutar, doviz=n_doviz)
                degisen += 1
        st.success(f"✅ {degisen} güncellendi, {silinen} silindi." if (degisen or silinen) else "Değişiklik yok.")
        if degisen or silinen:
            st.rerun()

    # ── Toplu sil (görünen kayıtlar / firmanın tümü) ──
    st.markdown("---")
    with st.expander("🗑 Toplu Sil — filtredeki kayıtları veya tüm ref no'ları sil"):
        st.caption("⚠️ Silme geri alınamaz. 'Görünenleri sil' yalnızca yukarıdaki durum filtresine uyan "
                   "kayıtları siler; ya da bu firmanın tüm ref no kayıtlarını temizle. "
                   "(Tek tek silmek için tablodaki 'Sil?' kutusunu işaretleyip Kaydet'e de basabilirsin.)")
        _rs1, _rs2 = st.columns(2)
        with _rs1:
            if st.button(f"🗑 Görünen {len(goster)} kaydı sil", use_container_width=True,
                         key=f"ref_bulk_goster_{fid}", disabled=(len(goster) == 0)):
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
            if st.button("🗑 Tümünü Sil", type="primary", use_container_width=True,
                         key=f"ref_temizle_btn_{fid}", disabled=not _onay):
                if ref_temizle(fid):
                    st.cache_data.clear()
                    st.success("✅ Bu firmanın tüm ref no kayıtları silindi.")
                    st.rerun()
                else:
                    st.error("Silme başarısız oldu.")


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
        {"label": "Toplam Bütçe (giriş)", "value": f"${giris:,.2f}", "renk": "#34D399"},
        {"label": "Toplam Harcama", "value": f"${harcama:,.2f}", "renk": "#F87171"},
        {"label": "Kalan Havuz", "value": f"${kalan:,.2f}", "renk": "#A5B4FC"},
        {"label": "Atanan Ref No (USD)", "value": f"${ref_usd:,.2f}", "renk": "#A78BFA"},
    ])

    # ── Yeni kayıt ekle ──
    with st.expander("➕ Yeni Bütçe / Harcama Kaydı Ekle"):
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
            b_ftar = b5.date_input("Fatura Tarihi", value=date.today())
            b_ref = b6.selectbox("Ref No", ref_secenek, index=0)
            b_kisi = st.text_input("Kişi / Sorumlu", placeholder="örn. DERYA MOLLAOĞLU")
            if st.form_submit_button("➕ Kaydı Ekle", type="primary", use_container_width=True):
                ok, msg = butce_ekle(fid, b_tur, b_ack.strip(), b_tutar, b_doviz,
                                     b_fno.strip(), b_ftar, b_ref, b_kisi.strip(), yon=b_yon)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()

    # ── Excel içe aktar ──
    with st.expander("📥 Excel'den İçe Aktar (Havuz Bütçe formatı)"):
        st.caption("Sütunlar: TÜR · MARKA · AÇIKLAMA · HAKEDİŞ BÜTÇE · TUTAR · DÖVİZ · FATURA NO · FATURA TARİH · FİRMA · REF NO · AÇIKLAMA(kişi)")
        upb = st.file_uploader("Havuz bütçe Excel'i", type=["xlsx", "xls"], key=f"butce_up_{fid}")
        temizle = st.checkbox("Önce mevcut bütçe kayıtlarını sil (güncel listeyi baştan yükle)",
                              key=f"butce_temizle_{fid}")
        if upb is not None:
            try:
                df_b = pd.read_excel(upb)
                st.dataframe(df_b.head(15), use_container_width=True, height=200)
                if st.button("📥 İçe Aktar", type="primary", key=f"butce_imp_{fid}"):
                    ok, msg, _n = butce_excel_ice_aktar(fid, df_b, temizle=temizle)
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.rerun()
            except Exception as e:
                st.error(f"Excel okunamadı: {e}")

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
            "Tutar": st.column_config.NumberColumn("Tutar ($)", format="%.2f"),
            "Fatura No": st.column_config.TextColumn("Fatura No"),
            "Tarih": st.column_config.DateColumn("Tarih", format="DD-MM-YYYY"),
            "Ref No": st.column_config.TextColumn("Ref No"),
            "Kişi": st.column_config.TextColumn("Kişi"),
        },
    )
    if st.button("💾 Değişiklikleri Kaydet", type="primary", key=f"butce_save_{fid}"):
        orijinal = {r["id"]: r for r in goster}
        silinen = degisen = 0
        for _, row in edited.iterrows():
            rid = row["id"]
            if bool(row.get("Sil?")):
                if butce_sil(rid):
                    silinen += 1
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
        st.success(f"✅ {degisen} güncellendi, {silinen} silindi." if (degisen or silinen) else "Değişiklik yok.")
        if degisen or silinen:
            st.rerun()

    # ── Toplu sil (görünen kayıtlar / firmanın tümü) ──
    st.markdown("---")
    with st.expander("🗑 Toplu Sil — arama sonucundaki kayıtları veya tüm bütçeyi sil"):
        st.caption("⚠️ Silme geri alınamaz. Önce yukarıdaki arama ile daralt → 'görünenleri sil' yalnızca "
                   "filtrelenen kayıtları siler; ya da bu firmanın tüm havuz bütçe kayıtlarını temizle.")
        _bs1, _bs2 = st.columns(2)
        with _bs1:
            if st.button(f"🗑 Aramada görünen {len(goster)} kaydı sil",
                         use_container_width=True, key=f"butce_bulk_goster_{fid}",
                         disabled=(len(goster) == 0)):
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
            if st.button("🗑 Tümünü Sil", type="primary", use_container_width=True,
                         key=f"butce_temizle_btn_{fid}", disabled=not _onay):
                if butce_temizle(fid):
                    st.cache_data.clear()
                    st.success("✅ Bu firmanın tüm bütçe kayıtları silindi.")
                    st.rerun()
                else:
                    st.error("Silme başarısız oldu.")


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
                         .select("tutar,doviz,tarih,durum,yil,firma_id,aylik").execute())
        except Exception:  # 'aylik' kolonu henüz yoksa
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
        _aylik = r.get("aylik") or {}
        if isinstance(_aylik, str):
            try:
                import json
                _aylik = json.loads(_aylik)
            except Exception:
                _aylik = {}
        if isinstance(_aylik, dict) and _aylik:
            # 1) Aylık kırılım — dönemle kesişen ayların tutarları
            for _ay, _tt in _aylik.items():
                _tt = _f(_tt)
                if _tt > 0 and _ay_kesisiyor(str(_ay)):
                    out.append({"tutar": _tt, "doviz": _doviz,
                                "tarih": f"{_ay}-01", "firma_id": _fid})
            continue
        t = _f(r.get("tutar"))
        if t <= 0:
            continue
        _tar = str(r.get("tarih") or "").strip()
        if _tar and _tar.lower() != "none":
            if not (_b <= _tar[:10] <= _e):
                continue
        else:
            _y = str(r.get("yil") or "").strip()
            if not _y or not (_b <= f"{_y}-01-01" <= _e):
                continue
        out.append({"tutar": t, "doviz": _doviz, "tarih": r.get("tarih") or "", "firma_id": _fid})
    return out


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
