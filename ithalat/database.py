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

# İthalat aşama (durum) seçenekleri. İlk 4'ü "yolda" sayılır; "Teslim Alındı" depoya girmiştir.
DURUM_SECENEKLER = ["Üretimde", "Yolda", "Gümrükte", "Antrepoda", "Teslim Alındı"]
IN_TRANSIT_DURUMLAR = {"Üretimde", "Yolda", "Gümrükte", "Antrepoda"}
VARSAYILAN_DURUM = "Yolda"


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
        # Her dosyanın masraf yüzdesi + tarihi
        dosya_map = {d.get("id"): d for d in dosyalar}
        dosya_yuzde = {}
        dosya_tarih = {}
        for did, ks in by_dosya.items():
            dosya_yuzde[did] = dosya_hesapla(dosya_map.get(did, {}), ks).get("maliyet_yuzde", 0.0)
            dosya_tarih[did] = str((dosya_map.get(did, {}) or {}).get("tarih") or "")[:10]
        # SKU bazında ağırlıklı topla (paçal) + dosya kırılımı (son için)
        agg = {}
        son_agg = {}  # {sku: {dosya_id: {"fob_x","final_x","adet"}}}
        for k in kalemler:
            sku = (str(k.get("sku") or "")).strip()
            if not sku:
                continue
            adet = _f(k.get("adet"))
            fob = _f(k.get("birim_fob"))
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
               masraflar, notlar, kalemler, pi_no="", ithalat_takip_no="",
               durum="", tahmini_varis=""):
    """Bir ithalat dosyası + kalemlerini ekler.
    masraflar: {slug: tutar}  (örn. {'navlun': 1200, 'damga_vergisi': 80})
    kalemler:  list[dict(sku, urun_adi, adet, birim_fob)]
    durum:     "Üretimde"|"Yolda"|"Gümrükte"|"Antrepoda"|"Teslim Alındı"
    tahmini_varis: "YYYY-MM-DD" (gecikme riski hesabı için)
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
        }
        try:
            d = _rows(sb.table("ithalat_dosyalari").insert(_payload).execute())
        except Exception:
            # Yeni opsiyonel kolonlar (ithalat_takip_no/durum/tahmini_varis) tabloda yoksa onlarsız tekrar dene
            for _opt in ("durum", "tahmini_varis", "ithalat_takip_no"):
                _payload.pop(_opt, None)
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
                   masraflar, notlar, kalemler, ithalat_takip_no="",
                   durum="", tahmini_varis=""):
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
        }
        try:
            sb.table("ithalat_dosyalari").update(_payload).eq("id", dosya_id).execute()
        except Exception:
            # Yeni opsiyonel kolonlar tabloda yoksa onlarsız tekrar dene
            # (masraf ve diğer bilgiler yine kaydedilsin).
            for _opt in ("durum", "tahmini_varis", "ithalat_takip_no"):
                _payload.pop(_opt, None)
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
