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
    ("mal_sigortasi",          "Sigorta"),
    ("damga_vergisi",          "Damga Vergisi"),
    ("banka_komisyonu",        "Banka Komisyonu"),
    ("liman_ardiye",           "Gümrük Ardiye"),
    ("gumruk_musavirligi",     "Gümrük Müşavirliği"),
    ("antrepo_beyannamesi",    "Antrepo Gümrük Müşavirliği"),
    ("liman_depo_nakliye",     "Gümrük - Depo Nakliye"),
    ("antrepo_ardiye",         "Antrepo Ardiye"),
    ("tahliye_depolama_tasima","Depo Tahliye-Depolama"),
    ("gv",                     "GV"),
    ("igv",                    "İGV"),
    ("otv",                    "ÖTV"),
    ("tse_tareks",             "TSE-Tareks"),
    ("kbf",                    "KBF"),
    ("yolluk",                 "Yolluk"),
    ("demuraj",                "Demuraj"),
    ("diger",                  "Diğer"),
]
MASRAF_ETIKET = dict(MASRAF_TANIM)
# Eski sürüm (5 sabit kolon) — geriye dönük okuma için
_ESKI_MASRAF = ["navlun", "gumruk", "sigorta", "nakliye", "diger"]

# İthalat aşama (durum) seçenekleri. İlk 4'ü "yolda" sayılır; "Teslim Alındı" depoya girmiştir.
DURUM_SECENEKLER = ["Üretimde", "Yolda", "Gümrükte", "Antrepoda", "Teslim Alındı"]
IN_TRANSIT_DURUMLAR = {"Üretimde", "Yolda", "Gümrükte", "Antrepoda"}
VARSAYILAN_DURUM = "Yolda"


@st.cache_resource
def _get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    # service_role_key varsa onu kullan (RLS aşılır, sunucuda kalır); yoksa anon key.
    key = st.secrets["supabase"].get("service_role_key") or st.secrets["supabase"]["key"]
    from shared.audit import wrap_client
    return wrap_client(create_client(url, key), "İthalat")


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
    """Türetilmiş değerler: mal_bedeli (brüt), indirim, net_mal_bedeli,
    toplam_masraf, maliyet_yuzde (masraf / NET mal bedeli), kalem_sayisi, toplam_adet.

    Fatura altı indirim: net_mal_bedeli = brüt − indirim. % maliyet ve SKU birim
    maliyetleri NET üzerinden hesaplanır (indirim yoksa net = brüt, davranış değişmez).
    """
    mal_bedeli = sum(_f(k.get("adet")) * _f(k.get("birim_fob")) for k in kalemler)  # brüt FOB
    indirim = _f((dosya or {}).get("fatura_indirim", 0))
    if indirim < 0:
        indirim = 0.0
    if indirim > mal_bedeli:
        indirim = mal_bedeli  # net negatif olmasın
    net_mal_bedeli = mal_bedeli - indirim
    toplam_masraf = sum(v for _, v in masraf_dokumu(dosya))
    yuzde = (toplam_masraf / net_mal_bedeli * 100) if net_mal_bedeli > 0 else 0.0
    toplam_adet = sum(_f(k.get("adet")) for k in kalemler)
    return {
        "mal_bedeli": mal_bedeli,          # brüt (indirimsiz)
        "indirim": indirim,                # fatura altı indirim (tutar)
        "net_mal_bedeli": net_mal_bedeli,  # brüt − indirim
        "toplam_masraf": toplam_masraf,
        "maliyet_yuzde": yuzde,            # masraf / NET mal bedeli
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
    Her SKU için ithalat verisinden PAÇAL (adet-ağırlıklı ortalama) + SON (en yeni dosya) maliyet.
    Dönen: {sku: {pacal_fob, pacal_final, son_fob, son_final, son_tarih, toplam_adet, dosya_sayisi}}
      • dosya_yuzde = toplam_masraf / FOB * 100  (dosya bazında)
      • birim landed = birim_fob * (1 + dosya_yuzde/100)
      • paçal = tüm partilerdeki landed/fob değerlerinin adet-ağırlıklı ortalaması
      • son   = en yeni TARİHLİ dosyadaki landed/fob (aynı dosyada birden çok kalem varsa
                o dosya içinde adet-ağırlıklı ortalama)
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
        # Her dosyanın masraf yüzdesi (NET üzerinden) + indirim oranı + tarihi
        dosya_map = {d.get("id"): d for d in dosyalar}
        dosya_yuzde = {}
        dosya_indirim_orani = {}  # indirim / brüt mal bedeli (0..1)
        dosya_tarih = {}
        for did, ks in by_dosya.items():
            _h = dosya_hesapla(dosya_map.get(did, {}), ks)
            dosya_yuzde[did] = _h.get("maliyet_yuzde", 0.0)
            _brut = _h.get("mal_bedeli", 0.0)
            dosya_indirim_orani[did] = (_h.get("indirim", 0.0) / _brut) if _brut > 0 else 0.0
            dosya_tarih[did] = str((dosya_map.get(did, {}) or {}).get("tarih") or "")[:10]
        # SKU bazında ağırlıklı topla (paçal) + dosya kırılımı (son için)
        agg = {}
        son_agg = {}  # {sku: {dosya_id: {"fob_x","final_x","adet"}}}
        for k in kalemler:
            sku = (str(k.get("sku") or "")).strip()
            if not sku:
                continue
            adet = _f(k.get("adet"))
            fob = _f(k.get("birim_fob")) * (1.0 - dosya_indirim_orani.get(k.get("dosya_id"), 0.0))  # NET birim FOB
            if adet <= 0:
                continue
            did = k.get("dosya_id")
            yuzde = dosya_yuzde.get(did, 0.0)
            final = fob * (1 + yuzde / 100.0)
            a = agg.setdefault(sku, {"fob_x": 0.0, "final_x": 0.0, "adet": 0.0, "dosyalar": set()})
            a["fob_x"] += fob * adet
            a["final_x"] += final * adet
            a["adet"] += adet
            a["dosyalar"].add(did)
            # Son için: SKU+dosya kırılımında ağırlıklı topla
            sd = son_agg.setdefault(sku, {}).setdefault(did, {"fob_x": 0.0, "final_x": 0.0, "adet": 0.0})
            sd["fob_x"] += fob * adet
            sd["final_x"] += final * adet
            sd["adet"] += adet
        sonuc = {}
        for sku, a in agg.items():
            ad = a["adet"]
            if ad <= 0:
                continue
            # SON: en yeni tarihli dosyayı seç (tarih boşsa en geriye düşer)
            son_fob = son_final = 0.0
            son_tarih = ""
            best_did = best_tarih = None
            for did in son_agg.get(sku, {}):
                t = dosya_tarih.get(did, "") or ""
                if best_tarih is None or t > best_tarih:
                    best_tarih, best_did = t, did
            if best_did is not None:
                sd = son_agg[sku][best_did]
                if sd["adet"] > 0:
                    son_fob = sd["fob_x"] / sd["adet"]
                    son_final = sd["final_x"] / sd["adet"]
                    son_tarih = dosya_tarih.get(best_did, "")
            sonuc[sku] = {
                "pacal_fob": a["fob_x"] / ad,
                "pacal_final": a["final_x"] / ad,
                "son_fob": son_fob,
                "son_final": son_final,
                "son_tarih": son_tarih,
                "toplam_adet": ad,
                "dosya_sayisi": len(a["dosyalar"]),
            }
        return sonuc
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def get_sku_ithalat_partileri():
    """Her SKU için ithalat partileri (FIFO için), belge tarihine göre ESKİ→YENİ.
    Dönen: {sku: [{"tarih": "YYYY-MM-DD", "adet": float}, ...]}
    """
    try:
        dosyalar = get_dosyalar()
        # Stok yaşı için parti tarihi = TESLİM tarihi (yoksa sipariş/belge tarihi)
        tarih_map = {d.get("id"): (str(d.get("teslim_tarihi") or d.get("tarih") or "")[:10])
                     for d in dosyalar}
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


# Tabloda sonradan eklenen, eksik olabilecek opsiyonel kolonlar
_OPSIYONEL_KOLONLAR = ("fatura_indirim", "durum", "tahmini_varis", "ithalat_takip_no",
                       "teslim_tarihi", "teslim_deposu", "teslim_sekli")


def _yaz_graceful(islem, payload):
    """islem(payload) çağırır; tabloda OLMAYAN bir opsiyonel kolon hatası gelirse
    YALNIZCA hatada geçen o kolonu düşürüp tekrar dener (diğer opsiyonelleri korur).
    Böylece bir kolon eksik diye fatura_indirim gibi diğer alanlar boşa düşmez."""
    p = dict(payload)
    for _ in range(len(_OPSIYONEL_KOLONLAR) + 1):
        try:
            return islem(p)
        except Exception as e:
            _msg = str(e).lower()
            _dus = [k for k in _OPSIYONEL_KOLONLAR if k in p and k.lower() in _msg]
            if not _dus:
                raise
            for k in _dus:
                p.pop(k, None)
    return islem(p)


def ekle_dosya(dosya_no, tarih, tedarikci, mense_ulke, doviz, kur,
               masraflar, notlar, kalemler, pi_no="", ithalat_takip_no="",
               durum="", tahmini_varis="", fatura_indirim=0, teslim_tarihi="", teslim_deposu="", teslim_sekli=""):
    """Bir ithalat dosyası + kalemlerini ekler.
    masraflar: {slug: tutar}  (örn. {'navlun': 1200, 'damga_vergisi': 80})
    kalemler:  list[dict(sku, urun_adi, adet, birim_fob)]
    durum:     "Üretimde"|"Yolda"|"Gümrükte"|"Antrepoda"|"Teslim Alındı"
    tahmini_varis: "YYYY-MM-DD" (gecikme riski hesabı için)
    fatura_indirim: fatura altı indirim tutarı (dosya para biriminde)
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
            "durum": durum or "",
            "tahmini_varis": (str(tahmini_varis)[:10] if tahmini_varis else None),
            "fatura_indirim": _f(fatura_indirim, 0),
            "teslim_tarihi": (str(teslim_tarihi)[:10] if teslim_tarihi else None),
            "teslim_deposu": teslim_deposu or "",
            "teslim_sekli": teslim_sekli or "",
        }
        d = _rows(_yaz_graceful(
            lambda p: sb.table("ithalat_dosyalari").insert(p).execute(), _payload))
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
                   masraflar, notlar, kalemler, ithalat_takip_no="",
                   durum="", tahmini_varis="", fatura_indirim=0, teslim_tarihi="", teslim_deposu="", teslim_sekli=""):
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
            "durum": durum or "",
            "tahmini_varis": (str(tahmini_varis)[:10] if tahmini_varis else None),
            "fatura_indirim": _f(fatura_indirim, 0),
            "teslim_tarihi": (str(teslim_tarihi)[:10] if teslim_tarihi else None),
            "teslim_deposu": teslim_deposu or "",
            "teslim_sekli": teslim_sekli or "",
        }
        _yaz_graceful(
            lambda p: sb.table("ithalat_dosyalari").update(p).eq("id", dosya_id).execute(), _payload)
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


def dagit_ortak_masraf(dosya_ids, ortak_masraflar, kur=None):
    """Ortak masrafları (tek takip nolu birden çok belge) seçili dosyalara
    FOB (mal bedeli) payına göre ORANSAL dağıtır ve kaydeder.

    Args:
        dosya_ids       : dağıtım yapılacak dosya id listesi
        ortak_masraflar : {slug: grup_toplam_tutar}  — grubun TOPLAM ortak masrafı
        kur             : verilirse seçili belgelerin 'kur' alanı da güncellenir (5 haneye kadar, yuvarlanmaz)

    Davranış:
        • Her dosyanın payı = dosya_mal_bedeli / grup_toplam_mal_bedeli (FOB).
        • Toplam FOB 0 ise eşit bölüştürülür.
        • Yalnızca GİRİLEN (≠0) slug'lar dosyaya yazılır; diğer mevcut masraflar korunur.
    Döner: (ok: bool, mesaj: str).
    """
    sb = _get_client()
    try:
        if not dosya_ids:
            return False, "Dosya seçilmedi."
        temiz = {k: _f(v) for k, v in (ortak_masraflar or {}).items() if _f(v) != 0}
        if not temiz and kur is None:
            return False, "Dağıtılacak masraf tutarı girilmedi."
        # Her dosyanın mal bedeli (FOB) — tek sorguda
        kalemler = get_tum_kalemler()
        fob_by_dosya = {}
        for k in kalemler:
            did = k.get("dosya_id")
            if did in dosya_ids:
                fob_by_dosya[did] = fob_by_dosya.get(did, 0.0) + _f(k.get("adet")) * _f(k.get("birim_fob"))
        toplam_fob = sum(fob_by_dosya.get(d, 0.0) for d in dosya_ids)
        dosya_map = {d["id"]: d for d in get_dosyalar() if d["id"] in dosya_ids}
        n = len(dosya_ids)
        guncellenen = 0
        for did in dosya_ids:
            d = dosya_map.get(did)
            if not d:
                continue
            _payload = {}
            if temiz:
                pay = (fob_by_dosya.get(did, 0.0) / toplam_fob) if toplam_fob > 0 else (1.0 / n)
                mevcut = _masraf_dict(d)  # {slug: tutar} — mevcut masraflar korunur
                for slug, toplam in temiz.items():
                    mevcut[slug] = round(toplam * pay, 2)
                mevcut = {k: v for k, v in mevcut.items() if _f(v) != 0}
                _payload["masraflar"] = mevcut
            if kur is not None:
                _payload["kur"] = _f(kur, 1)
            if _payload:
                sb.table("ithalat_dosyalari").update(_payload).eq("id", did).execute()
                guncellenen += 1
        _temizle()
        _kur_not = f" · kur {_f(kur):.5f} kaydedildi" if kur is not None else ""
        if temiz:
            return True, f"✅ Ortak masraf {guncellenen} belgeye FOB payına göre dağıtıldı{_kur_not}."
        return True, f"✅ {guncellenen} belgenin kuru güncellendi{_kur_not}."
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:200]}"


@st.cache_data(ttl=120, show_spinner=False)
def get_ithalat_yolda_ozet():
    """Yolda sayılan (Teslim Alınmamış) ithalat dosyalarının SKU bazında toplam miktarı
    + en yakın tahmini varış tarihi.

    Yolda sayılan durumlar: Üretimde / Yolda / Gümrükte / Antrepoda.
    'Teslim Alındı' veya boş durum (eski kayıtlar) yolda SAYILMAZ.

    Dönen: {sku: {"yoldaki_miktar": float, "varis_tarihi": "YYYY-MM-DD"|"", "durumlar": [..]}}
    """
    try:
        dosyalar = get_dosyalar()
        kalemler = get_tum_kalemler()
        if not kalemler:
            return {}
        durum_map, varis_map = {}, {}
        for d in dosyalar:
            durum = str(d.get("durum", "") or "").strip()
            if durum in IN_TRANSIT_DURUMLAR:
                durum_map[d.get("id")] = durum
                varis_map[d.get("id")] = str(d.get("tahmini_varis", "") or "")[:10]
        if not durum_map:
            return {}
        agg = {}
        for k in kalemler:
            did = k.get("dosya_id")
            if did not in durum_map:
                continue
            sku = str(k.get("sku") or "").strip()
            if not sku:
                continue
            adet = _f(k.get("adet"))
            if adet <= 0:
                continue
            a = agg.setdefault(sku, {"miktar": 0.0, "varis_set": set(), "durumlar": set()})
            a["miktar"] += adet
            a["durumlar"].add(durum_map[did])
            v = varis_map.get(did, "")
            if v:
                a["varis_set"].add(v)
        out = {}
        for sku, a in agg.items():
            varis = min(a["varis_set"]) if a["varis_set"] else ""  # en yakın tarih
            out[sku] = {
                "yoldaki_miktar": a["miktar"],
                "varis_tarihi": varis,
                "durumlar": sorted(a["durumlar"]),
            }
        return out
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def get_tedarikciler():
    """Mevcut ithalatlardaki benzersiz tedarikçi adları (alfabetik) — yeni ithalatta seçim için."""
    try:
        adlar = {str(d.get("tedarikci", "") or "").strip()
                 for d in get_dosyalar() if str(d.get("tedarikci", "") or "").strip()}
        return sorted(adlar, key=lambda x: x.lower())
    except Exception:
        return []


def set_dosya_teslim(dosya_id, teslim_tarihi=None, teslim_deposu=None):
    """Bir dosyanın SADECE teslim tarihi ve/veya teslim deposunu günceller.
    Diğer hiçbir alana dokunmaz. Verilmeyen (None) alan güncellenmez."""
    sb = _get_client()
    payload = {}
    if teslim_tarihi is not None:
        payload["teslim_tarihi"] = (str(teslim_tarihi)[:10] if teslim_tarihi else None)
    if teslim_deposu is not None:
        payload["teslim_deposu"] = teslim_deposu or ""
    if not payload:
        return False
    try:
        _yaz_graceful(lambda p: sb.table("ithalat_dosyalari").update(p).eq("id", dosya_id).execute(), payload)
        _temizle()
        return True
    except Exception:
        return False


def teslim_tarihleri_uygula(belge_map, takip_map):
    """Satın alım raporundan gelen teslim tarihlerini mevcut dosyalara yazar.
    SADECE teslim_tarihi alanı güncellenir; başka hiçbir veri değişmez.
    Eşleştirme: önce dosya_no (Belge no), eşleşmezse ithalat_takip_no.
    belge_map / takip_map: {ANAHTAR(upper,strip): 'YYYY-MM-DD'}
    Döner: (guncellenen, eslesmeyen, atlanan_zaten_ayni)."""
    sb = _get_client()
    dosyalar = get_dosyalar()
    guncellenen = eslesmeyen = ayni = 0
    for d in dosyalar:
        belge = str(d.get("dosya_no") or "").strip().upper()
        takip = str(d.get("ithalat_takip_no") or "").strip().upper()
        yeni = belge_map.get(belge) or takip_map.get(takip)
        if not yeni:
            eslesmeyen += 1
            continue
        mevcut = str(d.get("teslim_tarihi") or "")[:10]
        if mevcut == yeni:
            ayni += 1
            continue
        try:
            _yaz_graceful(
                lambda p: sb.table("ithalat_dosyalari").update(p).eq("id", d["id"]).execute(),
                {"teslim_tarihi": yeni})
            guncellenen += 1
        except Exception:
            eslesmeyen += 1
    _temizle()
    return guncellenen, eslesmeyen, ayni


# ── Barkod (urunler.barkod — SKU bazlı global) ──
@st.cache_data(ttl=120, show_spinner=False)
def get_barkod_map():
    """{sku: barkod} — urunler tablosundan."""
    try:
        rows = _rows(_get_client().table("urunler").select("sku, barkod").execute())
        return {r["sku"]: (r.get("barkod") or "") for r in rows if r.get("sku")}
    except Exception:
        return {}


def set_barkod(sku, barkod):
    """Tek SKU'nun barkodunu urunler tablosuna yazar (varsa günceller, yoksa ekler)."""
    sku = (str(sku) or "").strip()
    if not sku:
        return False
    try:
        _get_client().table("urunler").upsert(
            {"sku": sku, "barkod": (str(barkod) or "").strip()}, on_conflict="sku").execute()
        try:
            get_barkod_map.clear()
        except Exception:
            pass
        return True
    except Exception:
        return False


def barkod_toplu_yukle(eslesme):
    """{sku: barkod} sözlüğünü urunler tablosuna toplu yazar (upsert on_conflict=sku).
    Döner: (yazilan, hata)."""
    rows = []
    for sku, bk in (eslesme or {}).items():
        sku = (str(sku) or "").strip()
        if not sku:
            continue
        rows.append({"sku": sku, "barkod": (str(bk) or "").strip()})
    if not rows:
        return 0, "Geçerli satır yok."
    try:
        _get_client().table("urunler").upsert(rows, on_conflict="sku").execute()
        try:
            get_barkod_map.clear()
        except Exception:
            pass
        return len(rows), ""
    except Exception as e:
        return 0, f"{type(e).__name__}: {str(e)[:160]}"


@st.cache_data(ttl=300, show_spinner=False)
def get_sku_alim_detay(sku):
    """Bir SKU'nun her ithalat alım partisi (yeni→eski). Stok Kartı için.
    Dönen: [{tarih, belge_no, tedarikci, ulke, doviz, adet, birim_fob, maliyet_yuzde, final_birim}]"""
    try:
        sku = (str(sku) or "").strip()
        if not sku:
            return []
        dosyalar = {d.get("id"): d for d in get_dosyalar()}
        kalemler = get_tum_kalemler()
        by_dosya = {}
        for k in kalemler:
            by_dosya.setdefault(k.get("dosya_id"), []).append(k)
        dosya_yuzde, dosya_indirim = {}, {}
        for did, ks in by_dosya.items():
            _h = dosya_hesapla(dosyalar.get(did, {}), ks)
            dosya_yuzde[did] = _h.get("maliyet_yuzde", 0.0)
            _brut = _h.get("mal_bedeli", 0.0)
            dosya_indirim[did] = (_h.get("indirim", 0.0) / _brut) if _brut > 0 else 0.0
        out = []
        for k in kalemler:
            if (str(k.get("sku") or "").strip()) != sku:
                continue
            adet = _f(k.get("adet"))
            if adet <= 0:
                continue
            did = k.get("dosya_id")
            d = dosyalar.get(did, {})
            fob = _f(k.get("birim_fob")) * (1.0 - dosya_indirim.get(did, 0.0))
            yuzde = dosya_yuzde.get(did, 0.0)
            out.append({
                "tarih": str(d.get("teslim_tarihi") or d.get("tarih") or "")[:10],
                "belge_no": d.get("pi_no") or d.get("dosya_no") or "",
                "tedarikci": d.get("tedarikci") or "",
                "ulke": d.get("mense_ulke") or "",
                "doviz": d.get("doviz") or "USD",
                "adet": adet,
                "birim_fob": fob,
                "maliyet_yuzde": yuzde,
                "final_birim": fob * (1 + yuzde / 100.0),
                "takip_no": d.get("ithalat_takip_no") or "",
                "kur": _f(d.get("kur")),
                "durum": d.get("durum") or "",
                "siparis_tarih": str(d.get("tarih") or "")[:10],
                "teslim_tarih": str(d.get("teslim_tarihi") or "")[:10],
                "indirim_orani": dosya_indirim.get(did, 0.0),
                "_dosya": d,
            })
        out.sort(key=lambda x: x["tarih"], reverse=True)
        return out
    except Exception:
        return []
