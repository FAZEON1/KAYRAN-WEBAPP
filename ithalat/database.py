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


def masraf_sifirla(dosya_id, sluglar):
    """Seçilen masraf kalemlerini dosyadan KESİN siler (JSONB'den çıkarır).
    Kutu boşaltma davranışından bağımsız, doğrudan veritabanı işlemi. Döner (ok, mesaj)."""
    try:
        sb = _get_client()
        _dl = _rows(sb.table("ithalat_dosyalari").select("id, masraflar").eq("id", dosya_id).execute())
        d = _dl[0] if _dl else None
        if not d:
            return False, "Dosya bulunamadı."
        m = _masraf_dict(d)
        _silinen = [s for s in (sluglar or []) if s in m]
        for s in _silinen:
            m.pop(s, None)
        yeni = {k: v for k, v in m.items() if _f(v) != 0}
        guncel = {"masraflar": yeni}
        # eski sabit kolonlar da varsa sıfırla (geriye dönük kayıtlar)
        for s in _silinen:
            if s in _ESKI_MASRAF:
                guncel[s] = 0
        try:
            sb.table("ithalat_dosyalari").update(guncel).eq("id", dosya_id).execute()
        except Exception:
            sb.table("ithalat_dosyalari").update({"masraflar": yeni}).eq("id", dosya_id).execute()
        _temizle()
        _etk = ", ".join(MASRAF_ETIKET.get(s, s) for s in _silinen) or "—"
        return True, f"🧹 Sıfırlandı: {_etk}"
    except Exception as e:
        return False, f"Hata: {type(e).__name__}: {str(e)[:140]}"


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


# ══════════════════════════════════════════════════════════════════════
# ÇOKLU ÜRÜN GRUBU — maliyet dağıtımı (opsiyonel katman)
# Tek-grup dosyalar bu fonksiyonu KULLANMAZ; davranışları değişmez.
# Karar (kullanıcı): ORTAK masraf → grupların FOB payına göre; ÖZEL masraf
# → elle atandığı gruba direkt. Her grup kendi maliyet yüzdesini alır.
# ══════════════════════════════════════════════════════════════════════
ORTAK_GRUP = "__ortak__"   # grup_atama'da bu değer = masraf tüm gruplara FOB payıyla bölünür


def dosya_coklu_mu(dosya, kalemler):
    """Dosya çoklu ürun grubu mu? Kalemlerde 2+ farklı (boş olmayan) urun_grubu
    varsa ya da dosyada grup_masraf_atama tanımlıysa True."""
    gruplar = {(str(k.get("urun_grubu") or "").strip()) for k in (kalemler or [])}
    gruplar.discard("")
    if len(gruplar) >= 2:
        return True
    return bool((dosya or {}).get("grup_masraf_atama"))


def _grup_atama_dict(dosya):
    """Dosyanın {slug: hedef_grup|__ortak__} atama sözlüğü. Yoksa boş (=hepsi ortak)."""
    ga = (dosya or {}).get("grup_masraf_atama")
    if isinstance(ga, dict):
        return dict(ga)
    return {}


def dosya_hesapla_coklu(dosya, kalemler):
    """Çoklu ürün grubu maliyet dağıtımı. Döner:
    {
      gruplar: {grup: {fob, net_fob, ozel_masraf, ortak_pay, toplam_masraf,
                       yuzde, adet, birim_ek_maliyet_orani}},
      genel:   {toplam_fob, indirim, ortak_masraf, toplam_masraf, grup_sayisi}
    }
    ORTAK masraf gruplara FOB payına göre KURUŞ-DOĞRU dağıtılır (son grup farkı alır).
    ÖZEL masraf, grup_masraf_atama'da atandığı gruba doğrudan yazılır."""
    masraflar = _masraf_dict(dosya)
    grup_atama = _grup_atama_dict(dosya)

    grup_fob, grup_adet = {}, {}
    for k in (kalemler or []):
        g = (str(k.get("urun_grubu") or "").strip() or "GENEL")
        fob = _f(k.get("adet")) * _f(k.get("birim_fob"))
        grup_fob[g] = grup_fob.get(g, 0.0) + fob
        grup_adet[g] = grup_adet.get(g, 0.0) + _f(k.get("adet"))

    gruplar = list(grup_fob.keys())
    toplam_fob = sum(grup_fob.values())
    indirim = _f((dosya or {}).get("fatura_indirim", 0))
    indirim = max(0.0, min(indirim, toplam_fob))

    ortak_toplam = 0.0
    grup_ozel = {g: 0.0 for g in gruplar}
    for slug, tutar in masraflar.items():
        t = _f(tutar)
        if t == 0:
            continue
        hedef = grup_atama.get(slug, ORTAK_GRUP)
        if hedef == ORTAK_GRUP or hedef not in grup_fob:
            ortak_toplam += t
        else:
            grup_ozel[hedef] += t

    ortak_pay, atanan = {}, 0.0
    for i, g in enumerate(gruplar):
        if i < len(gruplar) - 1:
            pay = (grup_fob[g] / toplam_fob) if toplam_fob > 0 else (1.0 / len(gruplar))
            v = round(ortak_toplam * pay, 2)
            atanan = round(atanan + v, 2)
        else:
            v = round(ortak_toplam - atanan, 2)
        ortak_pay[g] = max(v, 0.0)

    sonuc = {}
    for g in gruplar:
        pay_orani = (grup_fob[g] / toplam_fob) if toplam_fob > 0 else (1.0 / len(gruplar))
        net_fob = grup_fob[g] - indirim * pay_orani
        grup_masraf = grup_ozel[g] + ortak_pay[g]
        yuzde = (grup_masraf / net_fob * 100) if net_fob > 0 else 0.0
        sonuc[g] = {
            "fob": round(grup_fob[g], 2),
            "net_fob": round(net_fob, 2),
            "ozel_masraf": round(grup_ozel[g], 2),
            "ortak_pay": ortak_pay[g],
            "toplam_masraf": round(grup_masraf, 2),
            "yuzde": round(yuzde, 4),
            "adet": grup_adet[g],
            "birim_ek_maliyet_orani": round(yuzde / 100, 6),
        }

    return {
        "gruplar": sonuc,
        "genel": {
            "toplam_fob": round(toplam_fob, 2),
            "indirim": round(indirim, 2),
            "ortak_masraf": round(ortak_toplam, 2),
            "toplam_masraf": round(ortak_toplam + sum(grup_ozel.values()), 2),
            "grup_sayisi": len(gruplar),
        },
    }


# ── MALİYET Excel formatı (2025-14 / 2026-12 gibi çoklu-grup sayfaları) parser ──
_MALIYET_ETIKET_SLUG = {
    "NAVLUN": "navlun", "LİMAN": "liman_ardiye", "MAL SİGORTASI": "mal_sigortasi",
    "DAMGA VERGİSİ": "damga_vergisi", "BANKA KOMİSYONU": "banka_komisyonu",
    "ARDİYE": "liman_ardiye", "GÜMRÜK MÜŞAVİRLİĞİ": "gumruk_musavirligi",
    "LİMAN-KITA NAKLİYE": "liman_depo_nakliye", "KITA-KAĞITHANE NAK.": "liman_depo_nakliye",
    "KITA TAHLİYE": "tahliye_depolama_tasima", "G.V": "gv", "İ.G.V": "igv",
    "KITA ARDİYE": "antrepo_ardiye", "YOLLUK": "yolluk", "HAMMALİYE": "diger",
    "ANTREPO BEY.": "antrepo_beyannamesi", "ANTREPO BEYANNAM": "antrepo_beyannamesi",
    "DEMURAJ": "demuraj", "TSE-TAREKS": "tse_tareks", "DTS-TAREKS": "tse_tareks",
    "KBF": "kbf", "ÖTV": "otv", "OTV": "otv",
}


def _maliyet_norm(s):
    return str(s or "").strip().upper()


def parse_maliyet_coklu_sayfa(ws):
    """MALİYET çoklu-grup Excel sayfasını okur (2025-14 / 2026-12 formatı).
    A sütunu masraf etiketi, C sütunu TL tutar. Sağ blok (I) grup adları.
    Döner: {tedarikci, tasima, mal_bedeli, kur, masraflar_tl{slug:tl},
            masraflar_usd{slug:usd}, gruplar[...], uyari[...]}
    Masraflar TL/kur ile USD'ye çevrilir (dosya para birimi USD varsayılır)."""
    def cell(r, c):
        return ws.cell(row=r + 1, column=c + 1).value

    def num(v):
        try:
            return float(v or 0)
        except Exception:
            return 0.0

    out = {"tedarikci": "", "tasima": "", "mal_bedeli": 0.0, "kur": 1.0,
           "masraflar_tl": {}, "masraflar_usd": {}, "gruplar": [], "uyari": []}
    out["tedarikci"] = str(cell(0, 0) or "").strip()
    out["tasima"] = str(cell(0, 1) or "").strip()

    for r in range(1, 6):
        a = _maliyet_norm(cell(r, 0))
        if "MAL BEDEL" in a:
            out["mal_bedeli"] = num(cell(r, 2))
        if "İŞLEM KURU" in a or "ISLEM KURU" in a:
            out["kur"] = num(cell(r, 2)) or 1.0

    kur = out["kur"] or 1.0
    for r in range(4, 24):
        a = str(cell(r, 0) or "").strip()
        if not a:
            continue
        au = _maliyet_norm(a)
        if au in ("TOPLAM", "ORAN", "GENEL"):
            break
        slug = None
        for et, sl in _MALIYET_ETIKET_SLUG.items():
            if _maliyet_norm(et) == au:
                slug = sl
                break
        if slug:
            tl = num(cell(r, 2))
            if tl != 0:
                out["masraflar_tl"][slug] = out["masraflar_tl"].get(slug, 0.0) + tl
                out["masraflar_usd"][slug] = round(
                    out["masraflar_usd"].get(slug, 0.0) + tl / kur, 2)
        elif au not in ("MAL BEDELİ", "İŞLEM KURU", "ISLEM KURU"):
            out["uyari"].append(f"Tanınmayan masraf satırı: '{a}' (atlandı)")

    # Grup adları: sağ blok I sütunu (index 8), satır 5-8
    for r in range(5, 9):
        gad = str(cell(r, 8) or "").strip()
        if not gad:
            continue
        gu = gad.upper()
        if gu in ("GENEL TOPLAM", "TOPLAM CBM / CFEET", "GENEL", "CBM ORANI"):
            continue
        if gad.replace(".", "").replace(",", "").isdigit():
            continue
        if gad not in out["gruplar"]:
            out["gruplar"].append(gad)

    return out


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
                       "teslim_tarihi", "teslim_deposu", "teslim_sekli",
                       "grup_masraf_atama")


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
               durum="", tahmini_varis="", fatura_indirim=0, teslim_tarihi="", teslim_deposu="", teslim_sekli="", sas_no=""):
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
            **({"grup_masraf_atama": grup_masraf_atama}
               if grup_masraf_atama is not None else {}),
            "ithalat_takip_no": ithalat_takip_no or "",
            "sas_no": sas_no or "",
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
            _kalem_row = {
                "dosya_id": dosya_id, "sku": sku,
                "urun_adi": (str(k.get("urun_adi") or "")).strip(),
                "adet": _f(k.get("adet")), "birim_fob": _f(k.get("birim_fob")),
            }
            _ug = (str(k.get("urun_grubu") or "")).strip()
            if _ug:
                _kalem_row["urun_grubu"] = _ug   # kolon yoksa aşağıda graceful düşer
            rows.append(_kalem_row)
        if rows:
            try:
                sb.table("ithalat_kalemleri").insert(rows).execute()
            except Exception as ke:
                # urun_grubu kolonu yoksa onu çıkarıp bir kez daha dene
                if "urun_grubu" in str(ke).lower() or "column" in str(ke).lower():
                    for _r in rows:
                        _r.pop("urun_grubu", None)
                    try:
                        sb.table("ithalat_kalemleri").insert(rows).execute()
                    except Exception as ke2:
                        try:
                            sb.table("ithalat_dosyalari").delete().eq("id", dosya_id).execute()
                        except Exception:
                            pass
                        return False, f"❌ Kalemler eklenemedi, dosya geri alındı: {str(ke2)[:150]}"
                else:
                    try:
                        sb.table("ithalat_dosyalari").delete().eq("id", dosya_id).execute()
                    except Exception:
                        pass
                    return False, f"❌ Kalemler eklenemedi, dosya geri alındı (yarım kayıt oluşmadı): {str(ke)[:150]}"
        if str(durum or "").strip() == "Teslim Alındı":
            _dosya_stok_uygula(dosya_id, +1,
                               kalem_agg=_dosya_kalem_agg(kalemler),
                               depo=teslim_deposu)
        _temizle()
        return True, f"✅ '{dosya_no}' dosyası {len(rows)} kalem ile eklendi."
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:200]}"


def guncelle_dosya(dosya_id, dosya_no, pi_no, tarih, tedarikci, mense_ulke, doviz, kur,
                   masraflar, notlar, kalemler, ithalat_takip_no="",
                   grup_masraf_atama=None,
                   durum="", tahmini_varis="", fatura_indirim=0, teslim_tarihi="", teslim_deposu="", teslim_sekli="", sas_no=""):
    """Dosya bilgileri + masraflar + kalemleri günceller (kalemler tamamen yenilenir)."""
    sb = _get_client()
    try:
        # MODEL B: geçiş tespiti için eski durum/depoyu ve bayrağı oku
        try:
            _md = _rows(sb.table("ithalat_dosyalari")
                        .select("durum, teslim_deposu, stok_islendi").eq("id", dosya_id).execute())
        except Exception:
            _md = _rows(sb.table("ithalat_dosyalari")
                        .select("durum, teslim_deposu").eq("id", dosya_id).execute())
        _md = _md[0] if _md else {}
        _eskiT = str(_md.get("durum") or "").strip() == "Teslim Alındı"
        _eski_islendi = _md.get("stok_islendi", None)
        _eski_depo = (_md.get("teslim_deposu") or "").strip()
        temiz_masraf = {k: _f(v) for k, v in (masraflar or {}).items() if _f(v) != 0}
        _payload = {
            "dosya_no": str(dosya_no), "pi_no": pi_no or "",
            "tarih": str(tarih) if tarih else None,
            "tedarikci": tedarikci or "", "mense_ulke": mense_ulke or "",
            "doviz": doviz or "USD", "kur": _f(kur, 1),
            "masraflar": temiz_masraf, "notlar": notlar or "",
            "ithalat_takip_no": ithalat_takip_no or "",
            "sas_no": sas_no or "",
            "durum": durum or "",
            "tahmini_varis": (str(tahmini_varis)[:10] if tahmini_varis else None),
            "fatura_indirim": _f(fatura_indirim, 0),
            "teslim_tarihi": (str(teslim_tarihi)[:10] if teslim_tarihi else None),
            "teslim_deposu": teslim_deposu or "",
            "teslim_sekli": teslim_sekli or "",
        }
        # TELAFİ için eski kalemleri silmeden ÖNCE yedekle (yeni yazma başarısız olursa geri yüklenir)
        _eski_kalem = _rows(sb.table("ithalat_kalemleri").select("*").eq("dosya_id", dosya_id).execute())
        _yaz_graceful(
            lambda p: sb.table("ithalat_dosyalari").update(p).eq("id", dosya_id).execute(), _payload)
        sb.table("ithalat_kalemleri").delete().eq("dosya_id", dosya_id).execute()
        rows = []
        for k in (kalemler or []):
            sku = (str(k.get("sku") or "")).strip()
            if not sku or sku.lower() == "nan":
                continue
            _kr = {
                "dosya_id": dosya_id, "sku": sku,
                "urun_adi": (str(k.get("urun_adi") or "")).strip(),
                "adet": _f(k.get("adet")), "birim_fob": _f(k.get("birim_fob")),
            }
            _ug = (str(k.get("urun_grubu") or "")).strip()
            if _ug:
                _kr["urun_grubu"] = _ug
            rows.append(_kr)
        if rows:
            def _geri_yukle():
                try:
                    if _eski_kalem:
                        _geri = [{kk: vv for kk, vv in r.items() if kk != "id"} for r in _eski_kalem]
                        sb.table("ithalat_kalemleri").insert(_geri).execute()
                except Exception:
                    pass
            try:
                sb.table("ithalat_kalemleri").insert(rows).execute()
            except Exception as ke:
                # urun_grubu kolonu yoksa onsuz bir kez daha dene
                if "urun_grubu" in str(ke).lower() or "column" in str(ke).lower():
                    for _r in rows:
                        _r.pop("urun_grubu", None)
                    try:
                        sb.table("ithalat_kalemleri").insert(rows).execute()
                    except Exception as ke2:
                        _geri_yukle()
                        return False, f"❌ Kalemler güncellenemedi, eski kalemler geri yüklendi: {str(ke2)[:150]}"
                else:
                    _geri_yukle()
                    return False, f"❌ Kalemler güncellenemedi, eski kalemler geri yüklendi (kayıp olmadı): {str(ke)[:150]}"
        # ── MODEL B stok geçişleri ──
        _yeniT = str(durum or "").strip() == "Teslim Alındı"
        _yeni_agg = _dosya_kalem_agg(kalemler)
        _eski_agg = _dosya_kalem_agg(_eski_kalem)
        if not _eskiT and _yeniT:
            _dosya_stok_uygula(dosya_id, +1, kalem_agg=_yeni_agg, depo=teslim_deposu)
        elif _eskiT and not _yeniT and _eski_islendi is True:
            _dosya_stok_uygula(dosya_id, -1, kalem_agg=_eski_agg, depo=_eski_depo)
        elif _eskiT and _yeniT and _eski_islendi is True:
            _delta = {}
            for _s in set(_yeni_agg) | set(_eski_agg):
                _d = _yeni_agg.get(_s, 0) - _eski_agg.get(_s, 0)
                if _d:
                    _delta[_s] = _d
            if _delta:
                _dosya_stok_uygula(dosya_id, +1, kalem_agg=_delta,
                                   depo=(teslim_deposu or _eski_depo))
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


def set_dosya_sas(dosya_id, sas_no):
    """Bir dosyanın SAS No'sunu günceller (kalemlere/masrafa dokunmaz)."""
    try:
        _get_client().table("ithalat_dosyalari").update(
            {"sas_no": sas_no or ""}).eq("id", dosya_id).execute()
        _temizle()
        return True
    except Exception:
        return False


def set_dosya_teslim_sekli(dosya_id, teslim_sekli):
    """Bir dosyanın Teslim Şekli (Incoterm) alanını günceller (kalemlere/masrafa dokunmaz)."""
    try:
        _get_client().table("ithalat_dosyalari").update(
            {"teslim_sekli": teslim_sekli or ""}).eq("id", dosya_id).execute()
        _temizle()
        return True
    except Exception:
        return False


def sas_no_excel_eslesti(dosya_yolu):
    """Mikro satın alma raporundan SAS no'larını okuyup sistemdeki ithalat dosyalarına eşleştirir.
    Eşleştirme anahtarı: 'Belge no' (= pi_no) — birebir; yedek olarak 'Dosya no'.
    Sistemdeki kayıtların sas_no alanını günceller. Veri (kalemler) değişmez.
    Döner: (ok, mesaj)."""
    import pandas as pd
    sb = _get_client()
    try:
        df = pd.read_excel(dosya_yolu, sheet_name=0)
    except Exception as e:
        return False, f"❌ Dosya okunamadı: {type(e).__name__}: {str(e)[:120]}"

    def _col(adaylar):
        low = {str(c).strip().lower(): c for c in df.columns}
        for a in adaylar:
            if a.lower() in low:
                return low[a.lower()]
        return None
    c_belge = _col(["belge no", "belgeno", "belge_no"])
    c_sas = _col(["sipariş no", "siparis no", "sipariş_no", "sas no", "sas"])
    if not c_belge or not c_sas:
        return False, "❌ Excel'de 'Belge no' ve 'Sipariş no' (SAS) sütunları bulunamadı."

    def _nk(s):  # eşleştirme anahtarı normalize (boşluk/harf duyarsız)
        return str(s or "").strip().upper().replace(" ", "")

    def _nsas(s):
        s = str(s or "").strip()
        if not s or s.lower() == "nan":
            return ""
        if s[:3].lower() == "sas":   # sas-33 → SAS-33 (prefiks tutarlı)
            s = "SAS" + s[3:]
        return s

    harita = {}  # normalize belge no → SAS no
    for _, r in df.iterrows():
        b = _nk(r.get(c_belge))
        s = _nsas(r.get(c_sas))
        if b and b != "NAN" and s:
            harita.setdefault(b, s)
    if not harita:
        return False, "❌ Excel'de eşleştirilecek (Belge no → SAS) verisi bulunamadı."

    try:
        dosyalar = _rows(sb.table("ithalat_dosyalari").select("id, pi_no, dosya_no, sas_no").execute())
    except Exception as e:
        return False, f"❌ İthalat dosyaları okunamadı: {str(e)[:120]}"

    guncellenen = zaten = 0
    eslesen_sas = set()
    eslesmeyen_dosya = []
    for d in dosyalar:
        sas = harita.get(_nk(d.get("pi_no"))) or harita.get(_nk(d.get("dosya_no")))
        if not sas:
            eslesmeyen_dosya.append(str(d.get("pi_no") or d.get("dosya_no") or d.get("id")))
            continue
        eslesen_sas.add(sas)
        if str(d.get("sas_no") or "").strip() == sas:
            zaten += 1
        else:
            try:
                sb.table("ithalat_dosyalari").update({"sas_no": sas}).eq("id", d["id"]).execute()
                guncellenen += 1
            except Exception:
                pass
    _temizle()

    eslesmeyen_sas = sorted(set(harita.values()) - eslesen_sas)
    mesaj = f"✅ {guncellenen} dosyaya SAS No yazıldı"
    if zaten:
        mesaj += f", {zaten} zaten doğruydu"
    mesaj += f". (Excel'de {len(harita)} benzersiz SAS)"
    if eslesmeyen_sas:
        mesaj += (f" | ⚠️ Belge no'su sistemde bulunamayan {len(eslesmeyen_sas)} SAS: "
                  + ", ".join(eslesmeyen_sas[:15]) + ("…" if len(eslesmeyen_sas) > 15 else ""))
    if eslesmeyen_dosya:
        mesaj += f" | ℹ️ SAS eşleşmeyen {len(eslesmeyen_dosya)} sistem dosyası (Excel'de belge no yok)."
    return True, mesaj


def dagit_ortak_masraf(dosya_ids, ortak_masraflar, kur=None, sil=None):
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
        • sil listesindeki slug'lar seçili TÜM belgelerden kaldırılır (silme).
        • KURUŞ-DOĞRU dağıtım: son belge, toplam − diğerleri farkını alır;
          böylece belgelere yazılanların toplamı girilen tutara BİREBİR eşittir
          (yuvarlama kaynaklı +0,01 kaymaları biter).
    Döner: (ok: bool, mesaj: str).
    """
    sb = _get_client()
    try:
        if not dosya_ids:
            return False, "Dosya seçilmedi."
        temiz = {k: _f(v) for k, v in (ortak_masraflar or {}).items() if _f(v) != 0}
        sil = [s for s in (sil or []) if s]
        if not temiz and not sil and kur is None:
            return False, "Dağıtılacak masraf tutarı girilmedi."
        # Her dosyanın mal bedeli (FOB) — tek sorguda
        kalemler = get_tum_kalemler()
        brut_by_dosya = {}
        for k in kalemler:
            did = k.get("dosya_id")
            if did in dosya_ids:
                brut_by_dosya[did] = brut_by_dosya.get(did, 0.0) + _f(k.get("adet")) * _f(k.get("birim_fob"))
        dosya_map = {d["id"]: d for d in get_dosyalar() if d["id"] in dosya_ids}
        # Pay = NET FOB (fatura altı indirim düşülmüş). Tek dosya maliyet mantığıyla
        # tutarlı: indirimli belge ortak masraftan daha az pay alır, indirim devre dışı kalmaz.
        fob_by_dosya = {}
        for did in dosya_ids:
            _brut = brut_by_dosya.get(did, 0.0)
            _ind = _f((dosya_map.get(did) or {}).get("fatura_indirim", 0))
            if _ind < 0:
                _ind = 0.0
            if _ind > _brut:
                _ind = _brut
            fob_by_dosya[did] = _brut - _ind
        toplam_fob = sum(fob_by_dosya.get(d, 0.0) for d in dosya_ids)
        n = len(dosya_ids)
        # ── KURUŞ-DOĞRU pay hesabı: her slug için ilk n-1 belge yuvarlanır,
        #    SON belge kalan farkı alır → toplam birebir korunur ──
        sirali_ids = [did for did in dosya_ids if did in dosya_map]
        atama = {did: {} for did in sirali_ids}
        for slug, toplam in temiz.items():
            atanan = 0.0
            for i, did in enumerate(sirali_ids):
                if i < len(sirali_ids) - 1:
                    pay = (fob_by_dosya.get(did, 0.0) / toplam_fob) if toplam_fob > 0 else (1.0 / n)
                    v = round(toplam * pay, 2)
                    atanan = round(atanan + v, 2)
                else:
                    v = round(toplam - atanan, 2)   # kalan fark → son belge
                atama[did][slug] = max(v, 0.0)

        guncellenen = 0
        for did in sirali_ids:
            d = dosya_map.get(did)
            _payload = {}
            if temiz or sil:
                mevcut = _masraf_dict(d)  # {slug: tutar} — mevcut masraflar korunur
                for s in sil:              # açıkça boşaltılan kalemler SİLİNİR
                    mevcut.pop(s, None)
                for slug, v in atama.get(did, {}).items():
                    mevcut[slug] = v
                mevcut = {k: v for k, v in mevcut.items() if _f(v) != 0}
                _payload["masraflar"] = mevcut
            if kur is not None:
                _payload["kur"] = _f(kur, 1)
            if _payload:
                sb.table("ithalat_dosyalari").update(_payload).eq("id", did).execute()
                guncellenen += 1
        _temizle()
        _kur_not = f" · kur {_f(kur):.5f} kaydedildi" if kur is not None else ""
        _sil_not = f" · {len(sil)} kalem silindi" if sil else ""
        if temiz or sil:
            return True, (f"✅ {guncellenen} belge güncellendi — masraflar FOB payına göre "
                          f"KURUŞ-DOĞRU dağıtıldı{_sil_not}{_kur_not}.")
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


def set_dosya_durum(dosya_id, durum):
    """Bir dosyanın SADECE aşama (durum) alanını günceller.
    MODEL B: 'Teslim Alındı'ya geçişte kalemler depoya EKLENİR; geri alınırsa ÇIKARILIR."""
    try:
        sb = _get_client()
        _rowsx = _rows(sb.table("ithalat_dosyalari").select("durum").eq("id", dosya_id).execute())
        _eski = str((_rowsx[0].get("durum") if _rowsx else "") or "").strip()
        _yeni = str(durum or "").strip()
        sb.table("ithalat_dosyalari").update({"durum": _yeni}).eq("id", dosya_id).execute()
        if _eski != "Teslim Alındı" and _yeni == "Teslim Alındı":
            _dosya_stok_uygula(dosya_id, +1)
        elif _eski == "Teslim Alındı" and _yeni != "Teslim Alındı":
            _dosya_stok_uygula(dosya_id, -1)
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


def urun_bilgi_toplu_yukle(satirlar):
    """[{sku, urun_adi, barkod}] → urunler tablosuna toplu upsert (on_conflict=sku).
    Boş hücre mevcut değeri EZMEZ (katalog/barkod haritasından korunur). Döner: (yazilan, hata)."""
    kat = get_urun_katalog() or {}
    bkm = get_barkod_map() or {}
    rows = []
    for s in (satirlar or []):
        sku = (str(s.get("sku") or "")).strip()
        if not sku:
            continue
        ad = (str(s.get("urun_adi") or "")).strip() or kat.get(sku, "")
        bk = (str(s.get("barkod") or "")).strip() or bkm.get(sku, "")
        rows.append({"sku": sku, "urun_adi": ad, "barkod": bk})
    if not rows:
        return 0, "Geçerli satır yok."
    try:
        _get_client().table("urunler").upsert(rows, on_conflict="sku").execute()
        for f in (get_barkod_map, get_urun_katalog):
            try:
                f.clear()
            except Exception:
                pass
        return len(rows), ""
    except Exception as e:
        return 0, f"{type(e).__name__}: {str(e)[:160]}"


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


# ═══════════ MODEL B — Teslim Alındı ⇄ depo stoğu ═══════════
def _dosya_kalem_agg(kalemler):
    agg = {}
    for k in (kalemler or []):
        sku = str(k.get("sku") or "").strip()
        adet = _f(k.get("adet"))
        if sku and adet:
            agg[sku] = agg.get(sku, 0) + adet
    return agg


def _dosya_stok_uygula(dosya_id, yon, kalem_agg=None, depo=None):
    """MODEL B: dosya kalemlerini depoya işler (yon=+1) / geri çeker (yon=-1).
    stok_islendi bayrağıyla çift işleme önlenir (kolon yoksa sessiz devam)."""
    try:
        sb = _get_client()
        try:
            rows = _rows(sb.table("ithalat_dosyalari")
                         .select("id, teslim_deposu, stok_islendi").eq("id", dosya_id).execute())
        except Exception:
            rows = _rows(sb.table("ithalat_dosyalari")
                         .select("id, teslim_deposu").eq("id", dosya_id).execute())
        d = rows[0] if rows else None
        if not d:
            return
        islendi = d.get("stok_islendi", None)
        if kalem_agg is None:
            if yon > 0 and islendi is True:
                return  # zaten işlenmiş
            if yon < 0 and islendi is not True:
                return  # hiç işlenmemişi geri çekme (eski/legacy dosyalar)
            kalem_agg = _dosya_kalem_agg(get_kalemler(dosya_id))
        if not kalem_agg:
            return
        _depo = (depo or d.get("teslim_deposu") or "").strip() or "MERKEZ DEPO"
        from kayranpm.database import stok_hareket_coklu
        stok_hareket_coklu({s: yon * a for s, a in kalem_agg.items()}, _depo)
        try:
            sb.table("ithalat_dosyalari").update({"stok_islendi": (yon > 0)}).eq("id", dosya_id).execute()
        except Exception:
            pass  # kolon henüz eklenmemişse bayraksız devam
    except Exception:
        pass


@st.cache_data(ttl=120, show_spinner=False)
def teslim_stok_bekleyenler(gercek_stok_kontrol=True):
    """'Teslim Alındı' olup stoğa İŞLENMEMİŞ dosyaları listeler.
    gercek_stok_kontrol=True: stok_islendi bayrağı True olsa BİLE, kalemlerin
    hiçbiri teslim deposunda görünmüyorsa 'işlenmemiş' sayar (yarım kalan/başarısız
    önceki işlemleri de yakalar). Döner: [{id, dosya_no, teslim_deposu, kalem_sayisi, toplam_adet}]."""
    out = []
    _depo_stok_cache = {}

    def _depoda_var_mi(depo, skular):
        depo = (depo or "").strip()
        if not depo:
            return False
        if depo not in _depo_stok_cache:
            try:
                from kayranpm.database import get_depo_stok
                _depo_stok_cache[depo] = {str(x.get("sku") or "").strip().upper()
                                          for x in (get_depo_stok(depo) or [])}
            except Exception:
                _depo_stok_cache[depo] = set()
        _set = _depo_stok_cache[depo]
        return any(str(s).strip().upper() in _set for s in skular)

    # Tüm kalemleri TEK sorguda çek, dosya_id'ye göre grupla (N+1 sorgusu yerine)
    _kalem_map = {}
    try:
        for _k in (get_tum_kalemler() or []):
            _kalem_map.setdefault(_k.get("dosya_id"), []).append(_k)
    except Exception:
        _kalem_map = None
    for d in (get_dosyalar() or []):
        if str(d.get("durum") or "").strip() != "Teslim Alındı":
            continue
        _kalemler_d = (_kalem_map.get(d["id"], []) if _kalem_map is not None
                       else get_kalemler(d["id"]))
        _agg = _dosya_kalem_agg(_kalemler_d)
        if not _agg:
            continue
        _islendi = d.get("stok_islendi") is True
        if _islendi and gercek_stok_kontrol:
            # Bayrak True ama stok gerçekten var mı? Yoksa yine bekleyen say.
            if _depoda_var_mi(d.get("teslim_deposu"), _agg.keys()):
                continue  # gerçekten stokta → tamam
        elif _islendi:
            continue
        out.append({
            "id": d["id"], "dosya_no": d.get("dosya_no", ""),
            "teslim_deposu": (d.get("teslim_deposu") or "").strip(),
            "kalem_sayisi": len(_agg), "toplam_adet": int(sum(_agg.values())),
        })
    return out


def teslim_stok_isle(dosya_idler=None):
    """Seçili (veya tüm bekleyen) 'Teslim Alındı' dosyalarının kalemlerini depoya İŞLER.
    Doğrudan stok_hareket_coklu çağırır; gerçek sonucu (uygulanan/atlanan SKU) raporlar.
    Döner: (islenen_dosya, eklenen_kalem, mesajlar[list])."""
    from kayranpm.database import stok_hareket_coklu
    bekleyen = teslim_stok_bekleyenler()
    if dosya_idler is not None:
        _set = set(dosya_idler)
        bekleyen = [b for b in bekleyen if b["id"] in _set]
    islenen, eklenen, mesajlar = 0, 0, []
    sb = _get_client()
    for b in bekleyen:
        _depo = (b.get("teslim_deposu") or "").strip()
        if not _depo:
            mesajlar.append(f"⏭️ {b['dosya_no']}: teslim deposu boş — atlandı")
            continue
        _agg = _dosya_kalem_agg(get_kalemler(b["id"]))
        if not _agg:
            mesajlar.append(f"⏭️ {b['dosya_no']}: kalem yok — atlandı")
            continue
        try:
            uyg, atl = stok_hareket_coklu({s: a for s, a in _agg.items()}, _depo)
        except Exception as e:
            mesajlar.append(f"❌ {b['dosya_no']}: {type(e).__name__}: {str(e)[:80]}")
            continue
        # Bayrağı yalnız GERÇEKTEN uygulanan varsa yaz (yoksa yeniden denenebilsin)
        if uyg := uyg:
            try:
                sb.table("ithalat_dosyalari").update({"stok_islendi": True}).eq("id", b["id"]).execute()
            except Exception:
                pass  # bayrak kolonu yoksa sorun değil; stok yine de işlendi
            islenen += 1
            eklenen += uyg
        if atl:
            mesajlar.append(f"⚠️ {b['dosya_no']}: kartı olmayan {len(atl)} SKU atlandı "
                            f"({', '.join(atl[:5])}{' …' if len(atl) > 5 else ''}) — "
                            f"bu SKU'lar için önce ürün kartı açılmalı")
    try:
        _temizle()
    except Exception:
        pass
    return islenen, eklenen, mesajlar
