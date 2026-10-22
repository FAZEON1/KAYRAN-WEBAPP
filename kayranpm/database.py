"""
KAYRAN — Veritabanı Katmanı (Supabase PostgreSQL)
"""
import sys

import streamlit as st
from shared.cop_kutusu import cop_kutusu_kapali  # birleştirme / sil-yeniden-yaz çöp kutusuna düşmesin
# Türkiye saat dilimi için ortak yardımcılar
from shared.utils import tr_today, tr_now, tr_today_iso, tr_now_str, tr_tomorrow, tr_yesterday as _tr_today_iso_dummy
from shared.utils import tr_kucuk
from shared.kayit import sessiz
from supabase import create_client, Client
from datetime import date
from collections import defaultdict


@st.cache_resource
def get_client() -> Client:
    """Supabase istemcisi (önbellekli).
    DAYANIKLILIK: Streamlit Cloud uygulamayı bir süre kullanılmayınca uykuya
    alır; uyanışta ağ/DNS geç gelebiliyor ve bağlantı ilk denemede kurulamayıp
    uygulama açılışta çökebiliyor ('Oh no' ekranı). Bu yüzden bağlantı kurulumu
    kısa beklemelerle 3 kez denenir."""
    import time
    url = st.secrets["supabase"]["url"]
    # service_role_key varsa onu kullan (RLS aşılır, sunucuda kalır); yoksa anon key.
    key = st.secrets["supabase"].get("service_role_key") or st.secrets["supabase"]["key"]
    from shared.audit import wrap_client
    _son_hata = None
    for _deneme in range(3):
        try:
            return wrap_client(create_client(url, key), "Ürün Yönetimi")
        except Exception as e:      # ağ/DNS/geçici hata → kısa bekle, tekrar dene
            _son_hata = e
            time.sleep(0.6 * (_deneme + 1))
    raise _son_hata


def db_yeniden_baglan():
    """Ölü/bayat bağlantıyı atıp yeniden kurar (uyanış sonrası onarım)."""
    try:
        get_client.clear()          # önbellekteki eski (ölü) istemciyi at
    except Exception:
        pass
    try:
        st.cache_data.clear()       # bayat veri önbelleğini de temizle
    except Exception:
        pass
    return get_client()


def db_saglik_kontrol():
    """Bağlantı canlı mı? Değilse bir kez yeniden bağlanmayı dener.
    Döner: (saglikli, mesaj).

    KRİTİK AYRIM: Sunucudan HATA CEVABI gelmesi, bağlantının ÇALIŞTIĞI
    anlamına gelir (ör. 'column does not exist' → Supabase cevap verdi).
    Bunu 'bağlantı yok' sayıp uygulamayı kilitlemek YANLIŞTIR. Bu yüzden:
      • Ağ/DNS/timeout hatası  → bağlantı ölü, yeniden bağlan.
      • Sunucudan gelen API hatası → bağlantı SAĞLIKLI (şema sorunu olabilir,
        o zaten ilgili ekranda görünür; tüm uygulamayı engellemeyiz).
    Şüpheye düşersek FAIL-OPEN: uygulamayı açarız, hatayı yerinde gösteririz.
    """
    _AG_HATALARI = ("timeout", "timed out", "connection", "resolve", "dns",
                    "unreachable", "refused", "reset", "ssl", "network",
                    "max retries", "name resolution")

    def _ag_hatasi_mi(e):
        s = f"{type(e).__name__}: {e}".lower()
        return any(k in s for k in _AG_HATALARI)

    def _dene(c):
        c.table("urunler").select("*").limit(1).execute()

    try:
        _dene(get_client())
        return True, ""
    except Exception as e1:
        if not _ag_hatasi_mi(e1):
            # Sunucu cevap verdi (şema/izin vb.) → bağlantı ayakta. Engelleme.
            return True, ""
        try:
            _dene(db_yeniden_baglan())
            return True, "yeniden baglandi"
        except Exception as e2:
            if not _ag_hatasi_mi(e2):
                return True, ""      # yine sunucu cevabı → aç
            return False, f"{type(e2).__name__}: {str(e2)[:150]}"


def _cache_temizle():
    """Tüm @st.cache_data önbelleklerini temizler.
    Her yazma (ekle/sil/güncelle) işleminden sonra çağrılır."""
    try:
        st.cache_data.clear()
    except Exception:
        pass


def get_today():
    return tr_today_iso()

def initialize_db():
    pass

def _rows(response):
    return response.data if response.data else []

def _row(response):
    d = response.data
    return d[0] if d else None

def _hepsi(table, secim="*", order_col=None, desc=False):
    """Bir tablodaki TÜM satırları çeker. HIZ: 1000+ satırda sayfalama
    merkezi katmanda (shared/audit) 8'erli dalgalarla PARALEL yapılır —
    eski ardışık range döngüsü kaldırıldı."""
    q = get_client().table(table).select(secim)
    if order_col:
        q = q.order(order_col, desc=desc)
    return _rows(q.execute())

# ── ÜRÜNLER ─────────────────────────────────────────────────────────

# Satış fiyat listesinde hazır gelen ana müşteriler (ekstra müşteri serbestçe eklenebilir)
ANA_MUSTERILER = ["Vatan", "Hepsiburada", "İtopya", "Trendyol", "Teknosa"]


def upsert_urun(sku, urun_adi, kategori="", marka="", satis_fiyati=0.0,
                alis_fiyati=0.0, hedef_kar_marji=0.0, ozellikler="",
                bizim_stok=0, trendyol_stok=0,
                satis_fiyat_listesi=None, eol=None):
    """Ürün ekler/günceller.
    satis_fiyat_listesi: {musteri: fiyat} — müşteri bazlı fiyatlar (opsiyonel, None ise dokunulmaz).
    eol: True/False — End of Life işareti (opsiyonel, None ise dokunulmaz). EOL ürünler sipariş önerisine girmez.
    """
    sb = get_client()
    bugun = get_today()
    mevcut = _row(sb.table("urunler").select("ilk_giris_tarihi").eq("sku", sku).execute())
    ilk_tarih = mevcut["ilk_giris_tarihi"] if mevcut and mevcut.get("ilk_giris_tarihi") else bugun
    _payload = {
        "sku": sku, "urun_adi": urun_adi, "kategori": tr_kucuk(kategori),
        "marka": marka or "", "satis_fiyati": float(satis_fiyati or 0),
        "alis_fiyati": float(alis_fiyati or 0),
        "hedef_kar_marji": float(hedef_kar_marji or 0),
        "ozellikler": ozellikler or "",
        "bizim_stok": int(bizim_stok or 0),
        "trendyol_stok": int(trendyol_stok or 0),
        "ilk_giris_tarihi": ilk_tarih,
        "guncelleme_tarihi": bugun,
    }
    # Opsiyonel yeni kolonlar — sadece verildiyse yaz (None ise mevcut değer korunur)
    if satis_fiyat_listesi is not None:
        _payload["satis_fiyat_listesi"] = {
            str(k).strip(): float(v or 0)
            for k, v in (satis_fiyat_listesi or {}).items()
            if str(k).strip() and float(v or 0) != 0
        }
    if eol is not None:
        _payload["eol"] = bool(eol)
    if _mikro_stok_yonetir():
        # Depo stoğu Mikro'dan gelir (kayranpm.mikro_stok, 15 dakikada bir): elle / dosyadan stok yazılmaz,
        # diğer alanlar yazılır (kullanıcı kararı 22.10.2026)
        _payload.pop("bizim_stok", None)
    try:
        sb.table("urunler").upsert(_payload, on_conflict="sku").execute()
    except Exception:
        # Yeni kolonlar (satis_fiyat_listesi/eol) tabloda yoksa onlarsız tekrar dene
        for _opt in ("satis_fiyat_listesi", "eol"):
            _payload.pop(_opt, None)
        sb.table("urunler").upsert(_payload, on_conflict="sku").execute()
    stok_yas_ilk_gorulen(sb, [sku], bugun)
    _cache_temizle()


def eol_isaretle(sku, eol):
    """Ürünü EOL (üretimi / satışı sonlandı) işaretler ya da işareti kaldırır; başka alana dokunmaz.
    Talep #40 (22.10.2026): EOL yalnız sayfanın en altındaki "Ürün Düzenle" formundaydı, bulunamıyordu.
    Döner: yazıldı mı."""
    try:
        get_client().table("urunler").update({"eol": bool(eol), "guncelleme_tarihi": get_today()}) \
            .eq("sku", sku).execute()
        _cache_temizle()
        return True
    except Exception as e:  # noqa: BLE001
        sessiz("kayranpm.database.eol_isaretle", e)
        return False


# ── Kategori yönetimi ──────────────────────────────────────────────
# Öneri kuralları: (kategori, anahtar kelime regex). Sıra önemli — ilk eşleşen kazanır.
import re as _re
KATEGORI_KURALLAR = [
    ("Araç Kamerası",   r"MIVUE|DASHCAM|ARAÇ\s*İÇİ|ARAC ICI|G-SENSOR|STARVIS"),
    ("Ekran Kartı",     r"EKRAN KARTI|GEFORCE|RADEON|\bRTX\b|\bGTX\b|GDDR"),
    ("Ekran Koruyucu",  r"EKRAN KORUYUCU|HYDROGEL|TEMPERED|CAM KORUYUCU|NANO CAM"),
    ("Monitör",         r"MONITOR|MONİTÖR|GAMING MONITOR|\bIPS\b|\bVA\b|\d+\s*HZ|\bHDMI\b"),
    ("CPU Soğutucu",    r"İŞLEMCİ|ISLEMCI|\bCPU\b"),
    ("Kule Soğutucu",   r"KULE"),
    ("Sıvı Soğutma",    r"\bAIO\b|SIVI|LIQUID|WATER COOL|RADYATÖR|RADYATOR"),
    ("Fan",             r"\bFAN\b|FANI|RGB FAN"),
    ("Güç Kaynağı",     r"\bPSU\b|POWER SUPPLY|GÜÇ KAYNA|GUC KAYNA"),
    ("Kasa",            r"KASA|\bCASE\b|\bATX\b|MESH|\bMID\s*TOWER\b"),
    ("Kablo/Konnektör", r"KONNEKTÖR|KONNEKTOR|\bKABLO\b|\bSATA\b|ADAPTÖR|ADAPTOR|5V3PIN"),
    ("El Aleti",        r"TORNAVIDA|ALET SET|ŞARJLI HASSAS|HASSAS TORNAVIDA"),
    ("Mouse Pad",       r"MOUSE\s*PAD|MOUSEPAD"),
    ("Klavye/Mouse",    r"KLAVYE|MOUSE|\bFARE\b|KEYBOARD"),
    ("Kulaklık",        r"KULAKLIK|HEADSET|EARBUD"),
    # Micro SD SSD'den ÖNCE: "MICRO SD" adı SSD kuralına takılmaz ama sıra açık olsun.
    ("Micro SD Kart",   r"MICRO\s*SD|MİCRO\s*SD|\bMICROSD|\bSD\s*KART|HAFIZA KARTI|MEMORY CARD"),
    ("SSD",             r"\bSSD\b|\bNVME\b|\bM\.2\b"),
    ("RAM",             r"\bRAM\b|\bDDR[345]\b|\bDIMM\b|SODIMM"),
    ("Yedek Parça",     r"YEDEK\s*PARÇA|YEDEK\s*PARCA|SPARE\s*PART"),
    ("Anti Virüs",      r"ANTİ\s*VİRÜS|ANTI\s*VIRUS|ANTIVIRUS|KASPERSKY|BITDEFENDER|NORTON|\bESET\b|TOTAL SECURITY|INTERNET SECURITY"),
]
KATEGORI_LISTE = [k for k, _ in KATEGORI_KURALLAR]


# ── Yurt içi kategoriler (Maliyet Girişi ekranı) ─────────────────────
# NOT: Bu iki fonksiyon 03.08.2026'da eklenmiş, 04.08.2026'da yüklenen eski
# bir database.py sürümüyle YANLIŞLIKLA SİLİNMİŞTİ. kayranpm/main.py onları
# çağırmaya devam ettiği için Maliyet Girişi ekranı ImportError veriyordu.
# Git geçmişinden (commit 9a465b2) aynen geri alındı.
#
# Yurt içinden alınan ürünlerin kategorileri. Maliyet Girişi ekranı YALNIZ
# bu kategorileri listeler. Neden kategori bazlı: ithalatı olan ürünlerin bir
# kısmında SKU yazımı ürün kartıyla tutmuyor (F11PA650BWM ↔ F11PA650BBM gibi),
# bu yüzden "ithalatta geçiyor mu" ölçütü tek başına yetmiyordu.
YURTICI_KATEGORI_VARSAYILAN = ["anti virüs", "mouse pad"]


@st.cache_data(ttl=300, show_spinner=False)
def get_yurtici_kategoriler():
    """Maliyet Girişi ekranında listelenecek kategoriler."""
    try:
        rows = _rows(get_client().table("pm_ayarlar").select("deger")
                     .eq("anahtar", "yurtici_kategoriler").limit(1).execute())
        if rows:
            ham = str(rows[0].get("deger") or "").strip()
            if ham:
                return [k.strip() for k in ham.split("·") if k.strip()]
    except Exception:
        pass
    return list(YURTICI_KATEGORI_VARSAYILAN)


def set_yurtici_kategoriler(kategoriler):
    """Kategori listesini kaydeder. Tablo yoksa False döner."""
    try:
        get_client().table("pm_ayarlar").upsert(
            {"anahtar": "yurtici_kategoriler",
             "deger": " · ".join(str(k).strip() for k in (kategoriler or []) if str(k).strip())},
            on_conflict="anahtar").execute()
        _cache_temizle()
        return True
    except Exception:
        return False


def kategori_oner(urun_adi):
    """Ürün adından kategori önerir; eşleşme yoksa boş döner."""
    ad = str(urun_adi or "").upper()
    for kat, pat in KATEGORI_KURALLAR:
        if _re.search(pat, ad):
            return kat
    return ""


# ── Marka önerisi ──────────────────────────────────────────────────
MARKA_KURALLAR = [
    ("FAZEON",    r"\bFAZEON\b"),
    ("INNO3D",    r"\bINNO ?3D\b"),
    ("EXCAVATOR", r"\bEXCAVATOR\b"),
    ("Mio",       r"\bMIO\b|MIVUE"),
    ("NZXT",      r"\bNZXT\b"),
    ("AGI",       r"\bAGI\b"),
    # SSD/RAM ithal ediliyor — adda geçen yaygın kategori ipuçları da eklendi
]


def marka_oner(urun_adi):
    """Ürün adından marka önerir. Bilinen markalar + ilk kelime tahmini."""
    ad = str(urun_adi or "").upper()
    for marka, pat in MARKA_KURALLAR:
        if _re.search(pat, ad):
            return marka
    # Fallback: ilk kelime (markalar genelde başta yazılır)
    parcalar = str(urun_adi or "").strip().split()
    if parcalar:
        ilk = parcalar[0].strip()
        if len(ilk) >= 2 and any(c.isalpha() for c in ilk):
            return ilk.upper()
    return ""


def toplu_kategori_marka_kaydet(sku_data):
    """{sku: {"kategori": ..., "marka": ...}} ile kategori ve/veya markayı toplu günceller.
    Sadece sözlükte bulunan alanlar yazılır. (guncellenen, hata) döner."""
    ok, hata = 0, 0
    sb = get_client()
    for sku, d in (sku_data or {}).items():
        try:
            upd = {}
            if "kategori" in d:
                upd["kategori"] = (d.get("kategori") or "").strip()
            if "marka" in d:
                upd["marka"] = (d.get("marka") or "").strip()
            if upd:
                sb.table("urunler").update(upd).eq("sku", str(sku)).execute()
                ok += 1
        except Exception:
            hata += 1
    _cache_temizle()
    return ok, hata


def toplu_satis_kaydet(sku_data):
    """{sku: {"satis_fiyati": float, "hedef_kar_marji": float}} ile satış fiyatı / hedef marjı
    toplu günceller. Sadece sözlükte bulunan alanlar yazılır. (guncellenen, hata) döner."""
    ok, hata = 0, 0
    sb = get_client()
    for sku, d in (sku_data or {}).items():
        try:
            upd = {}
            if "satis_fiyati" in d:
                upd["satis_fiyati"] = float(d.get("satis_fiyati") or 0)
            if "hedef_kar_marji" in d:
                upd["hedef_kar_marji"] = float(d.get("hedef_kar_marji") or 0)
            if upd:
                sb.table("urunler").update(upd).eq("sku", str(sku)).execute()
                ok += 1
        except Exception:
            hata += 1
    _cache_temizle()
    return ok, hata


def _kat_norm(s):
    """Karşılaştırma için kategori adını normalize eder (büyük/küçük + Türkçe harf farkını yok sayar)."""
    s = str(s or "").strip().lower().replace("i̇", "i")
    for a, b in (("ı", "i"), ("ş", "s"), ("ğ", "g"), ("ü", "u"), ("ö", "o"), ("ç", "c")):
        s = s.replace(a, b)
    return s


def kategori_standartlastir():
    """Tüm kategori yazımlarını tek biçime indirger: Türkçe-doğru KÜÇÜK HARF.
    'KASA'/'Kasa' → 'kasa', 'MONİTÖR'/'Monitör' → 'monitör' (büyük/küçük farkı birleşir).
    (degisen_urun_sayisi, {eski: yeni}) döner."""
    sb = get_client()
    rows = _hepsi("urunler", "sku, kategori", "sku")
    sku_yeni, degisim = {}, {}
    for r in rows:
        eski = (r.get("kategori") or "").strip()
        if not eski:
            continue
        yeni = tr_kucuk(eski)
        if yeni != eski:
            sku_yeni[r["sku"]] = yeni
            degisim[eski] = yeni
    for sku, yeni in sku_yeni.items():
        try:
            sb.table("urunler").update({"kategori": yeni}).eq("sku", str(sku)).execute()
        except Exception:
            pass
    _cache_temizle()
    return len(sku_yeni), degisim


# ── Ayarlar (sipariş eşiği) ─────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)   # tazelik: shared.veri_surumu (veri değişince temizlenir)
def get_uretim_suresi():
    """Sipariş eşiği = üretim/tedarik süresi (gün). pm_ayarlar tablosu yoksa varsayılan 135."""
    try:
        rows = _rows(get_client().table("pm_ayarlar").select("deger")
                     .eq("anahtar", "uretim_suresi_gun").limit(1).execute())
        if rows and str(rows[0].get("deger") or "").strip():
            return max(1, int(float(rows[0]["deger"])))
    except Exception:
        pass
    return 135


def set_uretim_suresi(gun):
    """Sipariş eşiğini kaydeder. Tablo yoksa False döner (varsayılan 135 kullanılmaya devam eder)."""
    try:
        get_client().table("pm_ayarlar").upsert(
            {"anahtar": "uretim_suresi_gun", "deger": str(int(gun))},
            on_conflict="anahtar").execute()
        _cache_temizle()
        return True
    except Exception:
        return False

@st.cache_data(ttl=3600, show_spinner=False)   # tazelik: shared.veri_surumu (veri değişince temizlenir)
def firma_son_tarihleri():
    """{firma: 'YYYY-MM-DD'} — her kanalın en son rapor tarihi (tüm ürünler).
    Tek ürünün satırlarını okuyan ekranlar (stok kartı) kanal stoğunu bu
    tarihle süzer: son raporda olmayan ürün o kanalda 0 (bkz. stok_hesap)."""
    # Firma listesi SABİT DEĞİL (KANAL kaldırıldı, Ekim 2026): veride görünen her firma.
    # stok_hesap ile aynı kural (firma_kanonik; eski 'KANAL' → DİĞER).
    from .stok_hesap import kanal_son_tarihleri
    return kanal_son_tarihleri(_hepsi("firma_stok", "firma, yukleme_tarihi"))


@st.cache_data(ttl=3600, show_spinner=False)   # tazelik: shared.veri_surumu (veri değişince temizlenir)
def get_firma_listesi():
    """Ekranlardaki firma seçenekleri: veride görünen firmalar + ana firmalar, firma_sirala
    sırasıyla (EERA, D-MARKET, VATAN, MONDAY, diğer cariler, DİĞER). Kodlar; görünen ad için
    shared.utils.firma_gorunen_ad."""
    from shared.utils import firma_sirala, FIRMA_KODLARI_DIGER
    try:
        gorulen = list(firma_son_tarihleri())
    except Exception:  # noqa: BLE001
        gorulen = []
    return firma_sirala(list(FIRMA_KODLARI_DIGER) + gorulen)


@st.cache_data(ttl=3600, show_spinner=False)   # tazelik: shared.veri_surumu (veri değişince temizlenir)
def _dashboard_ham():
    """Veritabanından ham panel verisi (5 dk önbellek). İthalat yolda/antrepo
    eklemesi BURADA DEĞİL, get_all_dashboard_data'da yapılır (bkz. orası)."""
    sb = get_client()
    # Sayfalama şart: 1000+ üründe panel toplamları sessizce eksik çıkıyordu
    urunler = urunler_ada_gore()
    from shared.utils import tr_buyuk as _tb_ad
    for _u in urunler:
        if _u.get("urun_adi"):
            _u["urun_adi"] = _tb_ad(_u["urun_adi"])  # gösterim: tüm modüllerde BÜYÜK harf
    stok_yas_data = {r["sku"]: r for r in _rows(sb.table("stok_yas").select("*").execute())}
    yoldaki_data = {r["sku"]: r for r in _rows(sb.table("yoldaki_urunler").select("*").execute())}
    # Yalnız kullanılan sütunlar (eskiden *: id ve ürün adı da bütün geçmişle okunuyordu)
    tum_firma_rows = _hepsi("firma_stok", "firma, sku, stok_miktari, haftalik_satis, stok_magaza, "
                                          "satis_magaza, yukleme_tarihi", "yukleme_tarihi")
    # Firma verisi: her firmanın SON raporu (stok_hesap — kanal_stoklari ile aynı kural). Firma
    # listesi veriden gelir (KANAL kaldırıldı, Ekim 2026); eski 'KANAL' satırları DİĞER'e katılır.
    # Eskiden sabit 6 kod için firma başına 2 sorgu atılıyordu; liste dışı firmalar hiç görünmüyordu.
    # Anahtar sku_anahtar (Ekim 2026): rapor 'MIO MIVUE J30', kart 'Mio MiVue J30' yazar; ham
    # SKU ile bakınca Mio ürünlerinin kanal stoğu ve satış geçmişi boş görünüyordu.
    from shared.utils import firma_kanonik, FIRMA_KODLARI_DIGER, sku_anahtar
    from .stok_hesap import kanal_son_tarihleri
    _son = kanal_son_tarihleri(tum_firma_rows)
    # Pazaryeri kodlu raporlar (D-market 'HBCV…', Avasya) kartın anahtarına — liste ve stok kartıyla
    # aynı harita (stok_hesap.kanal_stoklari, Ekim 2026).
    _har = kanal_kod_haritasi() or {}

    def _anh(s):
        k = sku_anahtar(s)
        return sku_anahtar(_har.get(k, k))
    firma_data = {f: {} for f in FIRMA_KODLARI_DIGER}
    for r in tum_firma_rows:
        f = firma_kanonik(r.get("firma"))
        if f and str(r.get("yukleme_tarihi") or "")[:10] == _son.get(f):
            _fd = firma_data.setdefault(f, {})
            _k = _anh(r["sku"])
            if _k in _fd:                     # aynı tarihte 'KANAL' + 'DİĞER' / iki yazım → TOPLA
                _o = dict(_fd[_k])
                for _a in ("stok_miktari", "haftalik_satis", "stok_magaza", "satis_magaza"):
                    _o[_a] = (_o.get(_a) or 0) + (r.get(_a) or 0)
                _fd[_k] = _o
            else:
                _fd[_k] = r
    gecmis_satislar = defaultdict(list)
    for row in tum_firma_rows:
        gecmis_satislar[_anh(row["sku"])].append(row.get("haftalik_satis", 0) or 0)
    return urunler, firma_data, stok_yas_data, yoldaki_data, dict(gecmis_satislar)


def sku_satirlari(tablo, sku, order=None, desc=False):
    """Bir ürünün bir tablodaki TÜM satırları, SKU yazımından bağımsız (stok kartı).
    Rapor/Excel 'MIO MIVUE J30' ya da 'Fazeon X24F200', kart 'Mio MiVue J30' / 'X24F200' yazar;
    .eq("sku") bu satırları bulmuyordu. Geniş ara (ilike), sku_anahtar ile kesin doğrula
    ('J300' gibi yanlış adaylar elenir). Okunamazsa boş liste (kart yine açılır)."""
    from shared.utils import sku_anahtar
    k = sku_anahtar(sku)
    if not k:
        return []
    try:
        q = get_client().table(tablo).select("*").ilike("sku", f"%{k}")
        if order:
            q = q.order(order, desc=desc)
        rows = _rows(q.execute())
    except Exception:  # noqa: BLE001
        return []
    return [r for r in rows if sku_anahtar(r.get("sku")) == k]


def firma_stok_satirlari(sku):
    """Bir ürünün TÜM firma_stok satırları, SKU yazımından bağımsız (stok kartı kanal stoğu)."""
    return sku_satirlari("firma_stok", sku)


def kart_sku_haritasi():
    """{sku_anahtar: kart SKU'su} — yalnız anahtarı TEK karta çıkanlar (iki kart aynı anahtara
    düşerse hiçbiri seçilmez, yanlış karta yazılmaz)."""
    from shared.utils import sku_anahtar
    say, h = {}, {}
    for ks in (get_urun_marka_kategori() or {}):
        k = sku_anahtar(ks)
        if k:
            say[k] = say.get(k, 0) + 1
            h[k] = ks
    return {k: v for k, v in h.items() if say[k] == 1}


def kart_sku_coz(sku, harita=None):
    """Kayda yazılacak SKU: aynı anahtarlı stok kartı varsa KARTIN yazımı ('Fazeon X24F200' →
    'X24F200', 'MIO MIVUE J30' → 'Mio MiVue J30'), yoksa sku_anahtar. Kart okunamazsa sku_anahtar."""
    from shared.utils import sku_anahtar
    k = sku_anahtar(sku)
    if not k:
        return ""
    try:
        h = kart_sku_haritasi() if harita is None else harita
    except Exception:  # noqa: BLE001
        h = {}
    return h.get(k, k)


def get_all_dashboard_data():
    """Panel verisi + İthalat'tan yolda/antrepo miktarı (ÖNBELLEKSİZ katman).

    Neden ayrı: ekleme önbellekli fonksiyonun içindeyken İthalat okunamazsa
    "yoldakisiz" eksik sonuç 5 dk saklanıyor, antrepodaki mal sipariş önerisinde
    sıfır sayılıyordu. Ham veri ve İthalat özeti kendi önbelleklerinde; bu katman
    yalnız birleştirir, hatalı turu saklamaz → sonraki açılış yeniden dener.
    """
    urunler, firma_data, stok_yas_data, yoldaki_data, gecmis_satislar = _dashboard_ham()
    # İthalat'tan gelen yolda (Üretimde/Yolda/Gümrükte/Antrepoda) miktarını mevcut elle veriye EKLE
    try:
        from ithalat.database import get_ithalat_yolda_ozet
        _ith_yolda = get_ithalat_yolda_ozet() or {}
    except Exception as e:
        # Sayfa açılmaya devam etsin ama SESSİZ kalmasın: yoldaki/antrepodaki mal bu
        # turda sayılamadı → sipariş önerisi yanlış "ACİL" diyebilir. Sistem Kayıtları'na
        # yazılır ve sipariş kararını etkilediği için Telegram'a bildirilir (kritik).
        from shared.hata_log import kaydet
        kaydet("kayranpm.get_all_dashboard_data", e,
               "İthalat yolda/antrepo miktarı okunamadı — sipariş önerisi bu turda yoldakini saymıyor",
               kritik=True)
        _ith_yolda = {}
    for _sku, _iy in _ith_yolda.items():
        _mev = yoldaki_data.get(_sku)
        if _mev:
            _mev["yoldaki_miktar"] = (_mev.get("yoldaki_miktar", 0) or 0) + _iy["yoldaki_miktar"]
            if not (str(_mev.get("varis_tarihi", "") or "").strip()) and _iy.get("varis_tarihi"):
                _mev["varis_tarihi"] = _iy["varis_tarihi"]
            _mev["_ithalat_yolda"] = _iy["yoldaki_miktar"]
            _mev["_ithalat_durumlar"] = _iy.get("durumlar", [])
        else:
            yoldaki_data[_sku] = {
                "sku": _sku,
                "yoldaki_miktar": _iy["yoldaki_miktar"],
                "varis_tarihi": _iy.get("varis_tarihi", ""),
                "_ithalat_yolda": _iy["yoldaki_miktar"],
                "_ithalat_durumlar": _iy.get("durumlar", []),
            }
    return urunler, firma_data, stok_yas_data, yoldaki_data, gecmis_satislar

@st.cache_data(ttl=300, show_spinner=False)
def get_urun_detay(sku):
    _u = _row(get_client().table("urunler").select("*").eq("sku", sku).execute())
    if _u and _u.get("urun_adi"):
        from shared.utils import tr_buyuk as _tb_ad
        _u["urun_adi"] = _tb_ad(_u["urun_adi"])  # gösterim: BÜYÜK harf
    return _u

def sil_urun(sku):
    sb = get_client()
    for tablo in ["urunler", "firma_stok",
                  "yoldaki_urunler", "stok_yas", "siparis_onerileri"]:
        sb.table(tablo).delete().eq("sku", sku).execute()
        _cache_temizle()

@st.cache_data(ttl=3600, show_spinner=False)   # tazelik: shared.veri_surumu (veri değişince temizlenir)
def urunler_ada_gore():
    """urunler tablosunun TAMAMI (*), ürün adına göre sıralı (veritabanı sıralaması). Tüm Ürünler
    ve Genel bakış buradan okur. Eskiden her biri ayrı okuyordu (sayfa başına 4 urunler sorgusu)."""
    return _hepsi("urunler", "*", "urun_adi")


@st.cache_data(ttl=3600, show_spinner=False)   # tazelik: shared.veri_surumu (veri değişince temizlenir)
def urunler_skuya_gore():
    """urunler tablosunun TAMAMI (*), SKU'ya göre sıralı. SKU listesi, marka/kategori haritası ve
    satis._urunler_hepsi buradan türer (sıralama veritabanında — Python sıralaması farklıdır)."""
    return _hepsi("urunler", "*", "sku")


@st.cache_data(ttl=300, show_spinner=False)
def get_tum_sku_listesi():
    # SAYFALAMA ŞART: Supabase tek sorguda en fazla 1000 satır döndürür (urunler_skuya_gore sayfalı).
    _rws = [{"sku": r.get("sku"), "urun_adi": r.get("urun_adi"), "marka": r.get("marka")}
            for r in urunler_skuya_gore()]
    from shared.utils import tr_buyuk as _tb_ad
    for _r in _rws:
        if _r.get("urun_adi"):
            _r["urun_adi"] = _tb_ad(_r["urun_adi"])
    return _rws


@st.cache_data(ttl=300, show_spinner=False)
def get_urun_marka_kategori():
    """{sku: {"marka", "kategori", "urun_adi"}} — Müşteri Satışları'nın marka/kategori
    kırılımı için (sayfalı; 1000 satır sınırına takılmaz)."""
    try:
        return {str(r.get("sku") or "").strip(): {"marka": r.get("marka") or "", "kategori": r.get("kategori") or "",
                                                  "urun_adi": r.get("urun_adi") or ""}
                for r in urunler_skuya_gore()}
    except Exception:  # noqa: BLE001 — kırılım "Markasız/Kategorisiz" görünür, sayfa çalışır
        return {}


# ── SKU EŞLEME (onaylı rapor kodu → stok kartı, Ekim 2026) ──────────
# Kural ve koruma: kayranpm.musteri_hesap (meta_hazirla, eslesme_dogrula). Tablo kurulumu:
# veritabani/10_sku_eslesme.sql. Program bu tabloya tahminle yazmaz; yalnız kullanıcı onayı.
SKU_ESLESME_SQL = ("create table if not exists sku_eslesme (dis_kod text primary key, "
                   "kart_sku text not null, onaylayan text, created_at timestamptz not null default now());\n"
                   "alter table sku_eslesme enable row level security;\n"
                   "drop policy if exists allow_all_sku_eslesme on sku_eslesme;\n"
                   "create policy allow_all_sku_eslesme on sku_eslesme for all to public "
                   "using (true) with check (true);")


@st.cache_data(ttl=300, show_spinner=False)
def get_sku_eslesme():
    """[{dis_kod, kart_sku, onaylayan, created_at}] — tablo yoksa None (ekran kurulum SQL'ini gösterir)."""
    try:
        return _hepsi("sku_eslesme", "dis_kod, kart_sku, onaylayan, created_at", "dis_kod")
    except Exception:  # noqa: BLE001 — tablo henüz kurulmadı; eşleştirme kurallarla sürer
        return None


@st.cache_data(ttl=300, show_spinner=False)
def kanal_kod_haritasi():
    """{sku_anahtar(rapor kodu): kart SKU'su} — kanal stoğunda pazaryeri kodlarını (D-market 'HBCV…',
    Avasya 'MON24FAZ…') karta bağlar (stok_hesap.kod_haritasi; Müşteri Satışları'yla aynı kural,
    Ekim 2026). Okunamazsa {} (kanal stoğu eski birebir kurala döner, sayfa çalışır)."""
    try:
        from .stok_hesap import kod_haritasi
        es = get_sku_eslesme() or []
        return kod_haritasi(_hepsi("firma_stok", "sku, urun_adi") or [], get_urun_marka_kategori() or {},
                            eslesme={r.get("dis_kod"): r.get("kart_sku") for r in es})
    except Exception:  # noqa: BLE001
        return {}


def kanal_kod_satirlari(sku):
    """Stok kartı: bu karta haritayla bağlanan rapor kodlarının firma_stok satırları ('HBCV…')."""
    from shared.utils import sku_anahtar
    k = sku_anahtar(sku)
    out = []
    for dis, kart in (kanal_kod_haritasi() or {}).items():
        if sku_anahtar(kart) == k:
            out += sku_satirlari("firma_stok", dis)
    return out


def sku_eslesme_kaydet(dis_kod, kart_sku, onaylayan=""):
    """Onaylı eşleme yazar. Döner: (ok, mesaj). Önce musteri_hesap.eslesme_dogrula denetler:
    kart SKU'su başka karta eşlenemez, olmayan karta eşlenemez, başka karta eşli kod ezilmez."""
    from shared.utils import sku_anahtar
    from .musteri_hesap import eslesme_dogrula
    mevcut = {r.get("dis_kod"): r.get("kart_sku") for r in (get_sku_eslesme() or [])}
    ok, msg, kayit = eslesme_dogrula(dis_kod, kart_sku, get_urun_marka_kategori() or {},
                                     sku_fn=sku_anahtar, mevcut=mevcut)
    if not ok:
        return False, msg
    try:
        get_client().table("sku_eslesme").upsert(
            dict(kayit, onaylayan=str(onaylayan or "")), on_conflict="dis_kod").execute()
    except Exception as e:  # noqa: BLE001
        return False, f"Kaydedilemedi: {e}"
    _cache_temizle()
    return True, f"{kayit['dis_kod']} → {kayit['kart_sku']} eşlemesi kaydedildi."


def sku_eslesme_sil(dis_kod):
    """Onaylı eşlemeyi kaldırır (satış/stok verisine dokunmaz). Döner: (ok, mesaj)."""
    from shared.utils import sku_anahtar
    dk = sku_anahtar(dis_kod)
    if not dk:
        return False, "Dış kod boş."
    try:
        get_client().table("sku_eslesme").delete().eq("dis_kod", dk).execute()
    except Exception as e:  # noqa: BLE001
        return False, f"Kaldırılamadı: {e}"
    _cache_temizle()
    return True, f"{dk} eşlemesi kaldırıldı."


# ── İTHALAT SENKRONİZASYONU ─────────────────────────────────────────
def ithalat_sku_ozet():
    """İthalat'taki distinct SKU'lar → {sku: {'urun_adi':..., 'adet':...}}."""
    try:
        from ithalat.database import get_tum_kalemler
        kalemler = get_tum_kalemler()
    except Exception:
        return {}
    out = {}
    for k in (kalemler or []):
        sku = str(k.get("sku") or "").strip()
        if not sku or sku.lower() == "nan":
            continue
        if sku not in out:
            out[sku] = {"urun_adi": str(k.get("urun_adi") or "").strip(), "adet": 0.0}
        try:
            out[sku]["adet"] += float(k.get("adet") or 0)
        except Exception:
            pass
        if not out[sku]["urun_adi"] and k.get("urun_adi"):
            out[sku]["urun_adi"] = str(k.get("urun_adi")).strip()
    return out


def ithalat_senkron_onizleme():
    """Senkron öncesi fark: (eklenecek_set, silinecek_set, korunan_set, ith_ozet, mevcut_map)."""
    ith = ithalat_sku_ozet()
    ith_skus = set(ith.keys())
    mevcut = get_tum_sku_listesi()
    mevcut_map = {str(u.get("sku") or "").strip(): (u.get("urun_adi") or "")
                  for u in mevcut if str(u.get("sku") or "").strip()}
    mevcut_skus = set(mevcut_map.keys())
    return (ith_skus - mevcut_skus, mevcut_skus - ith_skus,
            ith_skus & mevcut_skus, ith, mevcut_map)


def ithalat_eksikleri_ekle():
    """İthalat'ta olup üründe olmayan SKU'ları TEK upsert ile ekler (hızlı · silme YOK).
    Otomatik senkron için kullanılır. Döner: eklenen sayısı."""
    try:
        eklenecek, _sil, _kor, ith, _ = ithalat_senkron_onizleme()
        if not eklenecek:
            return 0
        sb = get_client()
        bugun = get_today()
        rows, stok_yas_rows = [], []
        for sku in eklenecek:
            _ad = ith.get(sku, {}).get("urun_adi", "") or ""
            rows.append({
                "sku": sku, "urun_adi": _ad,
                "kategori": kategori_oner(_ad), "marka": marka_oner(_ad),
                "satis_fiyati": 0.0, "alis_fiyati": 0.0,
                "hedef_kar_marji": 0.0, "ozellikler": "", "bizim_stok": 0,
                "trendyol_stok": 0, "ilk_giris_tarihi": bugun, "guncelleme_tarihi": bugun,
            })
            stok_yas_rows.append({"sku": sku, "ilk_gorulen_tarih": bugun})
        sb.table("urunler").upsert(rows, on_conflict="sku").execute()
        stok_yas_ilk_gorulen(sb, [r["sku"] for r in stok_yas_rows], bugun)
        _cache_temizle()
        return len(rows)
    except Exception:
        return 0

# ── FİRMA STOK ──────────────────────────────────────────────────────

def stok_yas_ilk_gorulen(sb, skular, bugun):
    """stok_yas: ürünün İLK görüldüğü gün — yalnız kaydı olmayan SKU için yazılır, var olan tarih korunur.
    Eskiden her ürün kaydında / G5F aktarımında bugünün tarihiyle EZİLİYORDU (13.10.2026 aktarımı 116
    ürünün tarihini sıfırladı; stok kartı 'İlk görülme' ve partisiz ürünün yedek stok yaşı bunu kullanır).
    Tablo yoksa / yazılamazsa sessiz geçer (bugünkü gibi)."""
    satir = [{"sku": s, "ilk_gorulen_tarih": bugun} for s in dict.fromkeys(skular or []) if s]
    if not satir:
        return
    try:
        sb.table("stok_yas").upsert(satir, on_conflict="sku", ignore_duplicates=True).execute()
    except Exception as e:
        sessiz("kayranpm.stok_yas_ilk_gorulen", e)


def g5f_yeni_kart(sku, urun_adi, bizim_stok_satilabilir, depo_kirilim, bugun):
    """G5F aktarımında kartı olmayan SKU için açılan kart satırı."""
    return {"sku": sku, "urun_adi": urun_adi or "", "kategori": "", "marka": "",
            "satis_fiyati": 0, "alis_fiyati": 0, "hedef_kar_marji": 0, "ozellikler": "",
            "bizim_stok": int(bizim_stok_satilabilir or 0), "trendyol_stok": 0,
            "depo_kirilim": depo_kirilim or {},
            "ilk_giris_tarihi": bugun, "guncelleme_tarihi": bugun}


def g5f_aktarim_atomik(urunler, sifirla, kaynak=None):
    """G5F aktarımının tamamı tek işlemde (veritabani/34_g5f_aktarim_tek_islem.sql): ürünler, Excel'de
    olmayanların sıfırlanması, stok defteri, stok_yas — ya hepsi ya hiçbiri.
    urunler: [{sku, urun_adi, bizim_stok, depo_kirilim, yeni_kart}], sifirla: [sku].
    Döner: {guncellenen, yeni, sifirlanan} | None (fonksiyon kurulu değil → bugünkü yol).
    Reddedilirse AtomikHata (hiçbir şey yazılmamıştır)."""
    try:
        sb = get_client()
    except Exception:
        return None
    ok, veri = atomik_rpc(sb, "g5f_stok_aktar", {"p_urunler": list(urunler or []),
                                                 "p_sifirla": list(sifirla or []),
                                                 "p_ortam": atomik_ortam(kaynak)})
    if not ok:
        return None
    veri = veri if isinstance(veri, dict) else {}
    atomik_audit("güncelle", "urunler", "",
                 f"G5F aktarım: {len(urunler or [])} ürün, {int(veri.get('sifirlanan') or 0)} sıfırlama (tek işlem)",
                 "kayranpm")
    _cache_temizle()
    return veri


def upsert_g5f_stok(sku, urun_adi, bizim_stok_satilabilir, depo_kirilim):
    """G5F (bizim depo) çok-depolu stok günceller.
    bizim_stok = satılabilir depolar toplamı (sipariş önerisi bunu kullanır).
    depo_kirilim = {depo_adi: miktar} — TÜM depolar (gösterim/genel toplam için).
    Mevcut ürünün fiyat/kategori/marka/hedef kâr bilgilerine DOKUNMAZ."""
    sb = get_client()
    bugun = get_today()
    try:
        mevcut = _row(sb.table("urunler").select("urun_adi, ilk_giris_tarihi, depo_kirilim")
                      .eq("sku", sku).execute())
    except Exception:
        mevcut = _row(sb.table("urunler").select("urun_adi, ilk_giris_tarihi").eq("sku", sku).execute())
    _sd = _defter()
    if mevcut:
        _payload = {"bizim_stok": int(bizim_stok_satilabilir or 0),
                    "depo_kirilim": depo_kirilim or {}, "guncelleme_tarihi": bugun}
        if not str(mevcut.get("urun_adi") or "").strip() and urun_adi:
            _payload["urun_adi"] = urun_adi
        try:
            sb.table("urunler").update(_payload).eq("sku", sku).execute()
            _sd.yaz_fark(sku, mevcut.get("depo_kirilim") or {}, depo_kirilim or {},
                         "aktarim", "Excel/G5F stok aktarımı")
        except Exception:
            _payload.pop("depo_kirilim", None)
            sb.table("urunler").update(_payload).eq("sku", sku).execute()
    else:
        _payload = g5f_yeni_kart(sku, urun_adi, bizim_stok_satilabilir, depo_kirilim, bugun)
        try:
            sb.table("urunler").insert(_payload).execute()
            _sd.yaz_fark(sku, {}, depo_kirilim or {}, "aktarim", "Excel/G5F stok aktarımı · yeni kart")
        except Exception:
            _payload.pop("depo_kirilim", None)
            sb.table("urunler").insert(_payload).execute()
    stok_yas_ilk_gorulen(sb, [sku], bugun)
    _cache_temizle()


def sil_firma_stok_tarihi(tarih):
    """Veri Yükleme › bir yükleme tarihinin TÜM firma stok satırlarını siler.
    Döner: silinen satır sayısı. Önbellek boşaltılır (eskiden boşaltılmıyordu;
    Dashboard ve Sipariş Önerisi silinmiş veriyi göstermeye devam ediyordu).
    Önbelleğe ALINMAZ (Ekim 2026): @st.cache_data ile sarılıydı; aynı tarih 5 dk içinde
    yeniden yüklenip yeniden silinince silme çalışmadan eski sayı dönebiliyordu."""
    res = get_client().table("firma_stok").delete().eq("yukleme_tarihi", tarih).execute()
    st.cache_data.clear()
    return len(getattr(res, "data", None) or [])


# ── SKU TEMİZLEME · 'Fazeon' önekli kodları öneksiz kodla birleştir ──────────
_SKU_TABLOLARI = ["urunler", "satislar", "firma_stok", "kampanya_urunler",
                  "yoldaki_urunler", "stok_yas", "ithalat_kalemleri", "siparis_onerileri",
                  "iadeler", "depo_manuel_takip"]   # iadeler: 98 önekli satır kalmıştı (Eki 2026)


def _fazeon_hedef(sku):
    """SKU 'Fazeon ' (her büyük/küçük varyant) ile başlıyorsa öneksiz + BÜYÜK harf hedefi döndürür.
    Değilse None. Örn: 'Fazeon X24F165S' → 'X24F165S'."""
    s = str(sku or "").strip()
    for p in ("FAZEON ", "Fazeon ", "fazeon "):
        if s.startswith(p) and len(s) > len(p):
            return s[len(p):].strip().upper()
    return None


def sku_fazeon_temizle_onizle():
    """Tüm tablolardaki 'Fazeon ' önekli SKU'ları, öneksiz hedeflerini, çakışmaları
    (hedef kod zaten var mı → birleşecek) ve etkilenen kayıt sayılarını döndürür.
    HİÇBİR ŞEY YAZMAZ — güvenli önizleme. Döner: list[{eski, yeni, catisma, toplam_kayit, tablolar}]."""
    try:
        urun_skular = {str(r.get("sku") or "").strip() for r in _hepsi("urunler", "sku", "sku")}
    except Exception:
        urun_skular = set()

    bulgular = {}  # eski_sku → {yeni, tablolar:{tablo:adet}}
    for tablo in _SKU_TABLOLARI:
        try:
            rows = _hepsi(tablo, "sku", "sku")
        except Exception:
            continue
        for r in rows:
            esku = str(r.get("sku") or "").strip()
            hedef = _fazeon_hedef(esku)
            if not hedef:
                continue
            b = bulgular.setdefault(esku, {"yeni": hedef, "tablolar": {}})
            b["tablolar"][tablo] = b["tablolar"].get(tablo, 0) + 1

    out = []
    for esku, b in sorted(bulgular.items()):
        out.append({
            "eski": esku, "yeni": b["yeni"],
            "catisma": (b["yeni"] in urun_skular),
            "tablolar": b["tablolar"],
            "toplam_kayit": sum(b["tablolar"].values()),
        })
    return out


def sku_fazeon_temizle_uygula():
    """'Fazeon ' önekli SKU'ları öneksiz hedeflerine taşır:
    - urunler DIŞI tablolar: sku alanı UPDATE (eski → yeni).
    - urunler: hedef kod zaten varsa kaynak (Fazeon) kayıt SİLİNİR (hedef korunur); yoksa yeniden adlandırılır.
    Geri alınamaz. Döner: (ok, mesaj)."""
    sb = get_client()
    onizle = sku_fazeon_temizle_onizle()
    if not onizle:
        return True, "Temizlenecek 'Fazeon' önekli SKU bulunamadı — sistem zaten temiz."
    try:
        urun_skular = {str(r.get("sku") or "").strip() for r in _hepsi("urunler", "sku", "sku")}
    except Exception:
        urun_skular = set()

    guncellenen_kayit = rename = birlesti = 0
    hatalar = []
    for it in onizle:
        esku, yeni = it["eski"], it["yeni"]
        for tablo in _SKU_TABLOLARI:
            if tablo == "urunler":
                continue
            try:
                sb.table(tablo).update({"sku": yeni}).eq("sku", esku).execute()
                guncellenen_kayit += it["tablolar"].get(tablo, 0)
            except Exception as e:
                hatalar.append(f"{tablo}/{esku}: {str(e)[:50]}")
        try:
            if yeni in urun_skular and yeni != esku:
                with cop_kutusu_kapali():
                    sb.table("urunler").delete().eq("sku", esku).execute()
                birlesti += 1
            else:
                sb.table("urunler").update({"sku": yeni}).eq("sku", esku).execute()
                urun_skular.add(yeni)
                rename += 1
        except Exception as e:
            hatalar.append(f"urunler/{esku}: {str(e)[:50]}")
    _cache_temizle()

    mesaj = (f"✅ {len(onizle)} 'Fazeon' SKU temizlendi — {rename} yeniden adlandırıldı, "
             f"{birlesti} mevcut kodla birleştirildi. Diğer tablolarda ~{guncellenen_kayit} kayıt güncellendi.")
    if hatalar:
        mesaj += f" | ⚠️ {len(hatalar)} sorun: " + "; ".join(hatalar[:3])
    return True, mesaj


@st.cache_data(ttl=300, show_spinner=False)
def get_musteri_haftalik_satis(bas=None, bit=None, firma=None, sku_ara=None):
    """firma_stok'tan haftalık satış kayıtları — tarih aralığı + müşteri + SKU/ürün filtreli (sayfalı).
    Döner: [{firma, sku, urun_adi, haftalik_satis, stok_miktari, yukleme_tarihi, musteri_kodu?}]."""
    sb = get_client()
    bas_s = str(bas)[:10] if bas else None
    bit_s = str(bit)[:10] if bit else None
    out, i, adim = [], 0, 1000
    # Kolon seçimi sırayla denenir (geriye dönük): musteri_kodu (Mikro kod eşleşmesi, 48_mikro_multikod.sql)
    # yoksa onsuz; satis_magaza / stok_magaza da yoksa onlarsız. Tutan seçim sonraki sayfalarda da kullanılır.
    secimler = ["firma, sku, urun_adi, haftalik_satis, satis_magaza, stok_miktari, stok_magaza, yukleme_tarihi, "
                "musteri_kodu",
                "firma, sku, urun_adi, haftalik_satis, satis_magaza, stok_miktari, stok_magaza, yukleme_tarihi",
                "firma, sku, urun_adi, haftalik_satis, stok_miktari, yukleme_tarihi"]
    while True:
        for _j, _secim in enumerate(secimler):
            q = sb.table("firma_stok").select(_secim)
            if bas_s:
                q = q.gte("yukleme_tarihi", bas_s)
            if bit_s:
                q = q.lte("yukleme_tarihi", bit_s)
            if firma and firma != "Tümü":
                q = q.eq("firma", firma)
            q = q.order("yukleme_tarihi", desc=True).range(i, i + adim - 1)
            try:
                chunk = _rows(q.execute())
            except Exception:
                if _j == len(secimler) - 1:
                    raise
                continue
            secimler = secimler[_j:]
            break
        out.extend(chunk)
        if len(chunk) < adim:
            break
        i += adim
        if i > 60000:
            break
    # ── HAFTA TEKİLLEŞTİRME: aynı ISO-haftada aynı firma+SKU için yalnız
    #    EN GÜNCEL yükleme sayılır (aynı haftanın dosyası iki farklı gün
    #    yüklenirse çift sayım olmaz). Liste tarih-azalan geldiği için ilk
    #    görülen kayıt en güncelidir. ──
    import datetime as _dtx
    _gorulen, _tekil = set(), []
    for r in out:
        _t = str(r.get("yukleme_tarihi", ""))[:10]
        try:
            _iy, _iw, _ = _dtx.date.fromisoformat(_t).isocalendar()
        except Exception:
            _iy, _iw = _t, 0
        _k = (r.get("firma"), r.get("sku"), _iy, _iw)
        if _k in _gorulen:
            continue
        _gorulen.add(_k)
        _tekil.append(r)
    out = _tekil

    if sku_ara and sku_ara.strip():
        s = sku_ara.strip().lower()
        out = [r for r in out
               if s in str(r.get("sku", "")).lower() or s in str(r.get("urun_adi", "")).lower()]
    return out


def upsert_firma_stok(firma, sku, urun_adi, stok_miktari, haftalik_satis,
                      stok_magaza=0, satis_magaza=0, rapor_tarihi=None):
    _kayit = {
        "firma": firma, "sku": sku, "urun_adi": urun_adi or "",
        "stok_miktari": int(stok_miktari or 0),
        "haftalik_satis": int(haftalik_satis or 0),
        "stok_magaza": int(stok_magaza or 0),
        "satis_magaza": int(satis_magaza or 0),
        "yukleme_tarihi": str(rapor_tarihi)[:10] if rapor_tarihi else get_today(),
    }

    def _yaz(kayit):
        """Önce upsert (unique constraint varsa). Constraint YOKSA
        (PostgREST 'no unique or exclusion constraint' hatası) →
        elle delete + insert ile aynı sonucu üret. Böylece tabloda
        firma+sku+yukleme_tarihi unique kısıtı olmasa bile yazma çalışır."""
        cl = get_client()
        try:
            cl.table("firma_stok").upsert(
                kayit, on_conflict="firma,sku,yukleme_tarihi").execute()
            return
        except Exception as e:
            _msg = str(e).lower()
            _constraint_yok = ("no unique" in _msg or "exclusion constraint" in _msg
                               or "on conflict" in _msg or "42p10" in _msg)
            if not _constraint_yok:
                raise  # başka bir hata (kolon vs) → üst katman ele alsın
        # Constraint yok → aynı anahtarı sil, sonra ekle (upsert taklidi)
        with cop_kutusu_kapali():
            cl.table("firma_stok").delete() \
                .eq("firma", kayit["firma"]).eq("sku", kayit["sku"]) \
                .eq("yukleme_tarihi", kayit["yukleme_tarihi"]).execute()
        cl.table("firma_stok").insert(kayit).execute()

    try:
        _yaz(_kayit)
    except Exception:
        # stok_magaza / satis_magaza kolonları tabloda yoksa onlarsız tekrar dene
        for _k in ("stok_magaza", "satis_magaza"):
            _kayit.pop(_k, None)
        _yaz(_kayit)
    _cache_temizle()

# ── YOLDAKI ─────────────────────────────────────────────────────────

def upsert_yoldaki_urun(sku, urun_adi, yoldaki_miktar, tahmini_varis_tarihi, yoldaki_tedarikci=""):
    get_client().table("yoldaki_urunler").upsert({
        "sku": sku, "urun_adi": urun_adi or "",
        "yoldaki_miktar": int(yoldaki_miktar or 0),
        "tahmini_varis_tarihi": str(tahmini_varis_tarihi or ""),
        "yoldaki_tedarikci": yoldaki_tedarikci or "",
        "yukleme_tarihi": get_today(),
    }, on_conflict="sku").execute()
    _cache_temizle()

@st.cache_data(ttl=300, show_spinner=False)
def get_yoldaki_urunler():
    rows = _rows(get_client().table("yoldaki_urunler").select("*").execute())
    return {r["sku"]: r for r in rows}

# ── SİPARİŞ ÖNERİLERİ ───────────────────────────────────────────────

def ekle_siparis_onerisi(firma, sku, urun_adi, miktar):
    get_client().table("siparis_onerileri").insert({
        "firma": firma, "sku": sku, "urun_adi": urun_adi or "",
        "oneri_miktari": int(miktar or 0),
        "durum": "bekliyor", "olusturma_tarihi": get_today(),
    }).execute()
    _cache_temizle()

@st.cache_data(ttl=300, show_spinner=False)
def get_siparis_onerileri():
    return _rows(get_client().table("siparis_onerileri").select("*").order("olusturma_tarihi", desc=True).execute())

def onayla_siparis(kayit_id):
    get_client().table("siparis_onerileri").update(
        {"durum": "onaylandi", "onay_tarihi": get_today()}
    ).eq("id", kayit_id).execute()
    _cache_temizle()

def reddet_siparis(kayit_id):
    get_client().table("siparis_onerileri").update(
        {"durum": "reddedildi", "onay_tarihi": get_today()}
    ).eq("id", kayit_id).execute()
    _cache_temizle()

# ── KAMPANYALAR ─────────────────────────────────────────────────────

def _kampanya_cache_temizle():
    """Kampanya yazımından sonra YALNIZ kampanya verisine bağlı önbellekleri siler (Ekim 2026).
    Eskiden _cache_temizle / st.cache_data.clear çağrılıyordu; app.py'deki akıllı temizlik kayranpm
    grubunu (kayranpm + satış + depo + ithalat + shared) silip tüm ürünler listesini soğuktan hesaplatıyordu
    (kampanya sayfası açılışı p50 ~5,2 sn). Kampanya verisini okuyan önbellekli fonksiyonların tamamı:"""
    from kayranpm import urun_karnesi as _uk
    from satis import database as _sdb
    _mod = sys.modules[__name__]
    for f in (*(getattr(_mod, ad, None) for ad in ("get_kampanyalar", "get_kampanya", "get_kampanya_urunler",
                                                    "get_tum_kampanya_urunler", "get_kampanya_destek_ortalamalari")),
              getattr(_sdb, "kampanya_destek_bul", None), getattr(_uk, "portfoy", None)):
        try:
            f.clear()
        except Exception as _e:
            from shared.kayit import sessiz
            sessiz("kayranpm.database._kampanya_cache_temizle", _e, "debug")

def ekle_kampanya(kampanya_adi, firma, baslangic, bitis, notlar="", kategori="",
                  kampanya_turu="", spiff_tl=0, spiff_kur=0, spiff_fatura=False):
    sb = get_client()
    payload = {
        "kampanya_adi": kampanya_adi, "firma": firma,
        "baslangic_tarihi": str(baslangic), "bitis_tarihi": str(bitis),
        "durum": "aktif", "notlar": notlar or "", "kategori": kategori or "",
        "kampanya_turu": kampanya_turu or "",
        "spiff_tl": float(spiff_tl or 0), "spiff_kur": float(spiff_kur or 0),
        "spiff_fatura": bool(spiff_fatura),
        "olusturma_tarihi": get_today(),
    }
    try:
        r = sb.table("kampanyalar").insert(payload).execute()
    except Exception:
        for _k in ("kampanya_turu", "spiff_tl", "spiff_kur", "spiff_fatura", "kategori"):
            payload.pop(_k, None)
        r = sb.table("kampanyalar").insert(payload).execute()
    _kampanya_cache_temizle()
    return r.data[0]["id"] if r.data else None

@st.cache_data(ttl=300, show_spinner=False)
def get_kampanyalar(durum=None):
    sb = get_client()
    q = sb.table("kampanyalar").select("*").order("olusturma_tarihi", desc=True)
    if durum:
        q = q.eq("durum", durum)
    return _rows(q.execute())

@st.cache_data(ttl=300, show_spinner=False)
def get_kampanya(kampanya_id):
    return _row(get_client().table("kampanyalar").select("*").eq("id", kampanya_id).execute())

def guncelle_kampanya(kampanya_id, kampanya_adi, firma, baslangic, bitis, notlar, kategori=None,
                      kampanya_turu=None, spiff_tl=None, spiff_kur=None, spiff_fatura=None):
    sb = get_client()
    payload = {
        "kampanya_adi": kampanya_adi, "firma": firma,
        "baslangic_tarihi": str(baslangic), "bitis_tarihi": str(bitis),
        "notlar": notlar or "",
    }
    if kategori is not None:
        payload["kategori"] = kategori
    if kampanya_turu is not None:
        payload["kampanya_turu"] = kampanya_turu
    if spiff_tl is not None:
        payload["spiff_tl"] = float(spiff_tl or 0)
    if spiff_kur is not None:
        payload["spiff_kur"] = float(spiff_kur or 0)
    if spiff_fatura is not None:
        payload["spiff_fatura"] = bool(spiff_fatura)
    try:
        sb.table("kampanyalar").update(payload).eq("id", kampanya_id).execute()
    except Exception:
        for _k in ("kategori", "kampanya_turu", "spiff_tl", "spiff_kur", "spiff_fatura"):
            payload.pop(_k, None)
        sb.table("kampanyalar").update(payload).eq("id", kampanya_id).execute()
    _kampanya_cache_temizle()

def kapat_kampanya(kampanya_id):
    get_client().table("kampanyalar").update({"durum": "kapali"}).eq("id", kampanya_id).execute()
    _kampanya_cache_temizle()

def sil_kampanya(kampanya_id):
    sb = get_client()
    sb.table("kampanya_urunler").delete().eq("kampanya_id", kampanya_id).execute()
    sb.table("kampanyalar").delete().eq("id", kampanya_id).execute()
    _kampanya_cache_temizle()

def ekle_kampanya_urun(kampanya_id, sku, urun_adi, pacal_maliyet, satis_fiyati,
                       birim_firma_destek, birim_ek_destek, notlar=""):
    get_client().table("kampanya_urunler").insert({
        "kampanya_id": kampanya_id, "sku": sku, "urun_adi": urun_adi or "",
        "pacal_maliyet": float(pacal_maliyet or 0),
        "satis_fiyati": float(satis_fiyati or 0),
        "birim_firma_destek": float(birim_firma_destek or 0),
        "birim_ek_destek": float(birim_ek_destek or 0),
        "satilan_adet": 0, "notlar": notlar or "",
    }).execute()
    _kampanya_cache_temizle()

@st.cache_data(ttl=300, show_spinner=False)
def get_kampanya_urunler(kampanya_id):
    return _rows(get_client().table("kampanya_urunler").select("*").eq("kampanya_id", kampanya_id).order("id").execute())

@st.cache_data(ttl=300, show_spinner=False)
def get_tum_kampanya_urunler():
    """Tüm kampanya ürünlerini TEK sorguda döndürür (N+1 önleme)."""
    return _rows(get_client().table("kampanya_urunler").select("*").order("id").execute())

def guncelle_kampanya_urun(urun_id, satis_fiyati, birim_firma_destek, birim_ek_destek, satilan_adet, notlar=""):
    get_client().table("kampanya_urunler").update({
        "satis_fiyati": float(satis_fiyati or 0),
        "birim_firma_destek": float(birim_firma_destek or 0),
        "birim_ek_destek": float(birim_ek_destek or 0),
        "satilan_adet": int(satilan_adet or 0),
        "notlar": notlar or "",
    }).eq("id", urun_id).execute()
    _kampanya_cache_temizle()

def sil_kampanya_urun(urun_id):
    get_client().table("kampanya_urunler").delete().eq("id", urun_id).execute()
    _kampanya_cache_temizle()

# ── BİLDİRİM ────────────────────────────────────────────────────────


# ── ANALİTİK ────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def get_gecmis_satis_firma_bazli(sku, firma):
    rows = _rows(get_client().table("firma_stok").select("haftalik_satis, yukleme_tarihi")
                .eq("sku", sku).eq("firma", firma)
                .order("yukleme_tarihi", desc=True).limit(8).execute())
    return [r.get("haftalik_satis", 0) or 0 for r in rows]

@st.cache_data(ttl=300, show_spinner=False)
def get_tum_gecmis_satislar():
    rows = _hepsi("firma_stok", "sku, haftalik_satis, yukleme_tarihi", "yukleme_tarihi")
    result = defaultdict(list)
    for r in rows:
        result[r["sku"]].append(r.get("haftalik_satis", 0) or 0)
    return dict(result)

@st.cache_data(ttl=300, show_spinner=False)
def get_gecmis_satis_tum_firmalar(sku):
    """Bir SKU için tüm firmaların geçmiş satış verilerini döndürür"""
    rows = _rows(get_client().table("firma_stok")
                .select("firma, haftalik_satis, stok_miktari, yukleme_tarihi")
                .eq("sku", sku)
                .order("yukleme_tarihi").execute())
    return rows

@st.cache_data(ttl=300, show_spinner=False)
def get_kampanya_destek_ortalamalari():
    """
    Tüm kampanyalardaki ürün bazında ortalama birim destek tutarlarını döndürür.
    Dönen dict: {sku: {'ort_firma_destek': float, 'ort_ek_destek': float, 'kampanya_sayisi': int}}
    """
    rows = _rows(get_client().table("kampanya_urunler").select(
        "sku, birim_firma_destek, birim_ek_destek"
    ).execute())
    
    from collections import defaultdict
    sku_data = defaultdict(list)
    for r in rows:
        sku_data[r["sku"]].append({
            "firma": float(r.get("birim_firma_destek") or 0),
            "ek": float(r.get("birim_ek_destek") or 0),
        })
    
    result = {}
    for sku, kayitlar in sku_data.items():
        if kayitlar:
            ort_firma = sum(k["firma"] for k in kayitlar) / len(kayitlar)
            ort_ek = sum(k["ek"] for k in kayitlar) / len(kayitlar)
            result[sku] = {
                "ort_firma_destek": round(ort_firma, 2),
                "ort_ek_destek": round(ort_ek, 2),
                "ort_toplam_destek": round(ort_firma + ort_ek, 2),
                "kampanya_sayisi": len(kayitlar),
            }
    return result



# ── TALEPLER ────────────────────────────────────────────────────────

def ekle_talep(gonderen, konu, mesaj, kategori=None, oncelik=None):
    """Kullanıcının talebini talepler tablosuna kaydeder.

    kategori / oncelik kolonları tabloda YOKSA da çalışır: önce onlarla
    denenir, hata alınırsa temel alanlarla tekrar denenir. Böylece SQL
    çalıştırılmadan da talep gönderilebilir, kolon eklenince zenginleşir.
    """
    _temel = {"gonderen": gonderen or "", "konu": konu or "",
              "mesaj": mesaj or "", "durum": "bekliyor"}
    _zengin = dict(_temel)
    if kategori:
        _zengin["kategori"] = str(kategori)
    if oncelik:
        _zengin["oncelik"] = str(oncelik)
    try:
        get_client().table("talepler").insert(_zengin).execute()
        _cache_temizle()
        return True
    except Exception:
        if _zengin == _temel:
            return False
    try:
        get_client().table("talepler").insert(_temel).execute()   # kolonsuz yeniden dene
        _cache_temizle()
        return True
    except Exception:
        return False


def get_talepler_kullanici(gonderen):
    """Bir kullanıcının KENDİ talepleri (en yeni üstte)."""
    _ad = str(gonderen or "").strip()
    if not _ad:
        return []
    try:
        return [t for t in (get_talepler() or [])
                if str(t.get("gonderen") or "").strip().lower() == _ad.lower()]
    except Exception:
        return []


def acik_talep_sayisi():
    """Tamamlanmamış talep sayısı — bildirim rozeti için."""
    try:
        return sum(1 for t in (get_talepler() or [])
                   if str(t.get("durum") or "") != "tamamlandi")
    except Exception:
        return 0


@st.cache_data(ttl=60, show_spinner=False)
def get_talepler():
    """Tum talepleri tarihe gore sirali getirir."""
    return _rows(get_client().table("talepler").select("*").order("olusturma_tarihi", desc=True).execute())

def guncelle_talep_cevap(talep_id, cevap, yeni_durum="tamamlandi"):
    """Talebin cevap alanini ve durumunu gunceller. Hata olursa yukari firlatir."""
    get_client().table("talepler").update({
        "cevap": cevap or "",
        "durum": yeni_durum,
    }).eq("id", talep_id).execute()
    _cache_temizle()
    return True


@st.cache_data(ttl=120, show_spinner=False)
def canli_stok(sku):
    """Satılabilir canlı stok — BİZİM depolarımız.

    ESKİ FORMÜL YANLIŞTI: firma_stok (müşterilerin haftalık stok raporu)
    tabanlı çalışıyordu. Vatan'ın deposundaki 328 adetten, bizim Happy
    Life'tan yaptığımız satışlar düşülünce sonuç eksiye iniyordu (-272)
    ve satış girişinde yanlış uyarı çıkıyordu.

    Gerçek durum:
      • urunler.depo_kirilim = BİZİM depolarımız (Happy Life, Merkez…).
        Bu alan zaten CANLI bakiye: ithalat teslim alınınca artar
        (stok_hareket_coklu), satışta azalır, iadede geri döner.
        Dolayısıyla ayrıca "snapshot + giriş − çıkış" hesabı YAPILMAZ,
        çift sayım olur.
      • firma_stok = MÜŞTERİDEKİ mal (Vatan'ın deposu). Bilgi amaçlı;
        satılabilir stoğa dahil DEĞİL, sipariş önerisinde ayrı gösterilir.

    Dönen: {var, baz, baz_tarih, giris, cikis, canli, musteri, iade_depo}
    (baz/giris/cikis alanları geriye uyumluluk için korunur.)
    """
    sb = get_client()
    sku_n = (sku or "").strip()
    bos = {"var": False, "baz": 0, "baz_tarih": None, "giris": 0,
           "cikis": 0, "canli": 0, "musteri": 0, "iade_depo": 0}
    if not sku_n:
        return bos

    # ── 1) Bizim depolar (satılabilir) ──
    try:
        u = _rows(sb.table("urunler").select("bizim_stok, depo_kirilim")
                  .eq("sku", sku_n).limit(1).execute())
    except Exception:
        u = []
    if not u:
        return bos

    kirilim = u[0].get("depo_kirilim")
    if isinstance(kirilim, str):
        try:
            import json as _j
            kirilim = _j.loads(kirilim)
        except Exception:
            kirilim = {}
    kirilim = kirilim if isinstance(kirilim, dict) else {}

    # İADE ve İKİNCİ EL depoları SATILABİLİR sayılmaz — fiziksel takip için.
    _haric = ("IADE DEPO", "IKINCI EL DEPO", "İADE DEPO", "İKİNCİ EL DEPO")
    satilabilir, iade_depo = 0.0, 0.0
    for _d, _a in kirilim.items():
        try:
            _a = float(_a or 0)
        except Exception:
            _a = 0.0
        if str(_d or "").strip().upper() in _haric:
            iade_depo += _a
        else:
            satilabilir += _a

    if not kirilim:                       # kırılım yoksa toplam alana düş
        try:
            satilabilir = float(u[0].get("bizim_stok") or 0)
        except Exception:
            satilabilir = 0.0

    # ── 2) Müşterideki mal (bilgi) ──
    musteri = 0.0
    try:
        rows = _rows(sb.table("firma_stok").select("stok_miktari,yukleme_tarihi,firma")
                     .eq("sku", sku_n).execute())
        firma_son = {}
        for r in rows:
            f = r.get("firma") or "—"
            t = str(r.get("yukleme_tarihi") or "")[:10]
            if (f not in firma_son) or (t > firma_son[f][0]):
                firma_son[f] = (t, float(r.get("stok_miktari") or 0))
        musteri = sum(v[1] for v in firma_son.values())
    except Exception:
        musteri = 0.0

    return {"var": True, "baz": satilabilir, "baz_tarih": None,
            "giris": 0, "cikis": 0,
            "canli": satilabilir,          # SATILABİLİR = bizim depolar
            "musteri": musteri,            # müşterideki (bilgi)
            "iade_depo": iade_depo}


def _depo_norm(s):
    return (str(s or "").strip().upper()
            .replace("İ", "I").replace("Ş", "S").replace("Ğ", "G")
            .replace("Ü", "U").replace("Ö", "O").replace("Ç", "C"))


# Bilinen depoların KANONİK yazımı — her yazım varyasyonu buraya toplanır.
# (normalize edilmiş anahtar → ekranda görünecek standart ad)
_DEPO_KANONIK = {
    "MERKEZ DEPO": "MERKEZ DEPO", "MERKEZDEPO": "MERKEZ DEPO", "MERKEZ": "MERKEZ DEPO",
    "HAPPY LIFE": "HAPPY LIFE", "HAPPYLIFE": "HAPPY LIFE", "HAPPY": "HAPPY LIFE",
    "ASEL DEPO": "ASEL DEPO", "ASELDEPO": "ASEL DEPO", "ASEL": "ASEL DEPO",
    "TEKNIK DEPO": "TEKNİK DEPO", "TEKNIKDEPO": "TEKNİK DEPO", "TEKNIK": "TEKNİK DEPO",
    # ── Teknik Servis modülü depoları ──────────────────────────────────
    # NOT: anahtarlar _depo_norm çıktısı biçiminde olmalı (İ→I, Ş→S, ...).
    # "servis depo" AYRI bir depo değildir — mevcut TEKNİK DEPO'ya eşlenir,
    # yoksa aynı fiziksel depo için ikiz kayıt oluşurdu.
    "SERVIS DEPO": "TEKNİK DEPO", "SERVISDEPO": "TEKNİK DEPO",
    "SERVIS": "TEKNİK DEPO", "TEKNIK SERVIS": "TEKNİK DEPO",
    "IADE DEPO": "İADE DEPO", "IADEDEPO": "İADE DEPO", "IADE": "İADE DEPO",
    "OUTLET DEPO": "OUTLET DEPO", "OUTLETDEPO": "OUTLET DEPO", "OUTLET": "OUTLET DEPO",
    "IKINCI EL DEPO": "İKİNCİ EL DEPO", "IKINCI EL": "İKİNCİ EL DEPO",
    "IKINCIEL": "İKİNCİ EL DEPO", "2.EL": "İKİNCİ EL DEPO", "2 EL": "İKİNCİ EL DEPO",
    "HURDA DEPO": "HURDA DEPO", "HURDADEPO": "HURDA DEPO", "HURDA": "HURDA DEPO",
    # Ekim 2026 (teknik servis isteği): Mikro'daki Pazarlama deposu ve yedek parça stoğu (kasa fanı, koli...)
    "PAZARLAMA": "PAZARLAMA", "PAZARLAMA DEPO": "PAZARLAMA", "PAZARLAMA DEPOSU": "PAZARLAMA",
    "YEDEK PARCA DEPO": "YEDEK PARÇA DEPO", "YEDEK PARCA": "YEDEK PARÇA DEPO",
    "YEDEKPARCA": "YEDEK PARÇA DEPO", "YEDEK PARCA DEPOSU": "YEDEK PARÇA DEPO",
}


@st.cache_data(ttl=300, show_spinner=False)
def get_satis_depolari(sku=None):
    """Satışta çıkış yapılabilecek depolar — VERİDEN çıkarılır, sabit liste değil.

    sku verilirse: O ÜRÜNÜN stoğu olan depolar, adetle birlikte.
        [{"depo": "HAPPY LIFE", "adet": 1892}, ...]  (adede göre azalan)
    sku verilmezse: sistemde KAYITLI TÜM depo adları.

    HİÇBİR DEPO HARİÇ TUTULMAZ. İade deposundaki mal ikinci el olarak,
    teknik servisten çıkan ürün de satılabilir — hangi depodan çıkacağına
    kullanıcı karar verir. (canli_stok bunları "satılabilir" saymaz; o
    ayrı bir hesap: uyarı eşiği. Buradaki liste satış seçeneğidir.)
    """
    _haric = set()
    try:
        sb = get_client()
        if sku:
            rows = _rows(sb.table("urunler").select("depo_kirilim")
                         .eq("sku", str(sku).strip()).limit(1).execute())
        else:
            rows, start = [], 0
            while True:
                ch = _rows(sb.table("urunler").select("depo_kirilim")
                           .range(start, start + 999).execute())
                rows.extend(ch)
                if len(ch) < 1000:
                    break
                start += 1000
    except Exception:
        return [{"depo": "MERKEZ DEPO", "adet": 0}] if sku else ["MERKEZ DEPO"]

    toplam = {}
    for r in rows:
        k = r.get("depo_kirilim")
        if isinstance(k, str):
            try:
                import json as _j
                k = _j.loads(k)
            except Exception:
                k = {}
        if not isinstance(k, dict):
            continue
        for d, a in k.items():
            d = depo_kanonik(d)
            if not d or d.upper() in _haric:
                continue
            try:
                a = float(a or 0)
            except Exception:
                a = 0.0
            toplam[d] = toplam.get(d, 0.0) + a

    if sku:
        # Stoğu olan depolar önce; hiç yoksa MERKEZ DEPO'yu seçenek bırak
        cikti = [{"depo": d, "adet": int(a)} for d, a in toplam.items()]
        cikti.sort(key=lambda x: -x["adet"])
        return cikti or [{"depo": "MERKEZ DEPO", "adet": 0}]

    adlar = sorted(toplam, key=lambda d: -toplam[d])
    # Stoğu 0 olsa bile bu depolar listede DURSUN (mal girdiğinde seçilebilsin).
    #
    # TEKNİK / HURDA / OUTLET eskiden bu listede YOKTU: o depodaki stok sıfıra
    # düşünce depo, seçeneklerden tamamen kayboluyordu. 09.09'da Sıddık
    # Bayraktar siparişinde "Servis Depo" seçeneğinin çıkmamasının sebebi buydu.
    #
    # NOT: "Servis Depo" ile "Teknik Depo" AYNI fiziksel yerdir; veritabanında
    # hangi yazımla durursa dursun ekranda tek isimle (TEKNİK DEPO) görünür.
    for _v in ("MERKEZ DEPO", "HAPPY LIFE", "TEKNİK DEPO", "İADE DEPO",
               "İKİNCİ EL DEPO", "OUTLET DEPO", "HURDA DEPO", "ASEL DEPO", "PAZARLAMA", "YEDEK PARÇA DEPO"):
        _k = depo_kanonik(_v)
        if _k not in adlar:
            adlar.append(_k)
    return adlar


def depo_kanonik(s):
    """Depo adını standart yazıma çevirir: 'happy life' / 'HAPPYLIFE' / 'Happy Life' → 'HAPPY LIFE'.
    Bilinmeyen depolar boşluk sadeleştirilip BÜYÜK harfe çevrilerek döner (yine tutarlı olur)."""
    n = _depo_norm(s)
    n = " ".join(n.split())  # çoklu boşlukları teke indir
    if n in _DEPO_KANONIK:
        return _DEPO_KANONIK[n]
    n2 = n.replace(" ", "")
    if n2 in _DEPO_KANONIK:
        return _DEPO_KANONIK[n2]
    return n  # bilinmeyen depo: en azından BÜYÜK/tek-boşluk normalize


def _kirilim_kanonik(depo_kirilim):
    """Bir depo_kirilim sözlüğündeki tüm depo adlarını kanonikleştirir, aynı depoları TOPLAR."""
    out = {}
    for d, m in (depo_kirilim or {}).items():
        k = depo_kanonik(d)
        try:
            out[k] = out.get(k, 0) + int(float(m or 0))
        except Exception:
            out[k] = out.get(k, 0)
    return out


def depo_dagilimi(depo_kirilim):
    """G5F depo kırılımı rozetleri için TEK kaynak (Tüm Ürünler detayı + stok kartı).
    Adları kanonikleştirip aynı depoyu toplar ('MERKEZ' + 'MERKEZ DEPO' tek rozet),
    sıfır depoları atar, adede göre azalan sıralar. Bozuk değer çökertmez (0 sayılır).
    Döner: ([(depo, adet), ...], toplam)."""
    if not isinstance(depo_kirilim, dict):
        return [], 0
    dk = _kirilim_kanonik(depo_kirilim)
    satirlar = sorted(((d, a) for d, a in dk.items() if a), key=lambda x: (-x[1], x[0]))
    return satirlar, sum(a for _, a in satirlar)


# "Satılabilir" sayılan depolar — bizim_stok toplamı ve depo listesindeki
# satilabilir işareti bunu kullanır. TANIMLI DEĞİLDİ: _bizim_stok_hesapla ve
# depo_ozet çağrıldığında NameError atıyor, Depolar Arası Sevk sayfası
# açılmıyordu. (excel_islemler.py'de G5F_SATILABILIR_DEPOLAR adıyla ayrı bir
# kopyası var; burada da lazım.)
# NOT: iade/ikinci el depoları buraya DAHİL DEĞİL — oradaki mal fiziksel
# takipte. Satışta seçilebilir ama "satılabilir stok" sayılmaz.
_SATILABILIR_DEPOLAR = {"MERKEZ DEPO", "HAPPY LIFE"}


def _bizim_stok_hesapla(depo_kirilim):
    """Satılabilir depoların (Merkez + Happy Life) toplamı."""
    # depo_kanonik ŞART: _depo_norm yalnız boşluk/büyük harf düzeltir,
    # "MERKEZ" → "MERKEZ DEPO" eşlemesini yapmaz. Kırılımda kısa yazım
    # varsa o depo satılabilir sayılmaz ve stok eksik görünürdü.
    return int(sum(int(m or 0) for d, m in (depo_kirilim or {}).items()
                   if depo_kanonik(d) in _SATILABILIR_DEPOLAR))


def satilabilir_kontrol(depo_kirilim, kayitli):
    """Kırılımdan hesaplanan satılabilir stok (Merkez + Happy Life) ↔ kayıtlı bizim_stok.
    Ekranlar kayıtlı değeri gösterir; ikisi ayrı zamanda yazıldıysa tutmayabilir —
    bu fonksiyon farkı görünür kılar, hiçbir şey YAZMAZ (hangisi doğru, sayım söyler).
    Döner: {"hesap": int | None, "kayitli": int, "fark": hesap − kayitli | None}.
    Kırılım yoksa hesap/fark None (karşılaştıracak veri yok, uyarı çıkmamalı)."""
    try:
        k = int(float(kayitli or 0))
    except (TypeError, ValueError):
        k = 0
    if not isinstance(depo_kirilim, dict) or not depo_kirilim:
        return {"hesap": None, "kayitli": k, "fark": None}
    h = _bizim_stok_hesapla(_kirilim_kanonik(depo_kirilim))
    return {"hesap": h, "kayitli": k, "fark": h - k}


def _sevk_uygula(depo_kirilim, kaynak, hedef, adet):
    """SAF hesap: kaynak depodan hedefe 'adet' taşır. Yazmaz.
    Kaynak/hedef ve kırılım kanonikleştirilir (yazım farkı sorun olmaz).
    Döner: (yeni_kirilim | None, hata_mesaji)."""
    dk = _kirilim_kanonik(depo_kirilim or {})
    kaynak = depo_kanonik(kaynak)
    hedef = depo_kanonik(hedef)
    adet = int(adet or 0)
    if adet <= 0:
        return None, "Adet 0'dan büyük olmalı."
    if not str(kaynak).strip() or not str(hedef).strip():
        return None, "Kaynak ve hedef depo seçilmeli."
    if kaynak == hedef:
        return None, "Kaynak ve hedef depo aynı olamaz."
    mevcut = int(dk.get(kaynak, 0) or 0)
    if mevcut < adet:
        return None, f"Yetersiz stok: '{kaynak}' deposunda {mevcut} adet var, {adet} taşınamaz."
    dk[kaynak] = mevcut - adet
    dk[hedef] = int(dk.get(hedef, 0) or 0) + adet
    return dk, ""


@st.cache_data(ttl=120, show_spinner=False)
def get_depo_listesi():
    """Tüm ürünlerin depo_kirilim'inde geçen benzersiz KANONİK depo adları (alfabetik).
    Ayrıca teslim alınmış ithalat dosyalarının teslim depolarını da dahil eder."""
    depolar = set()
    for u in _hepsi("urunler", "depo_kirilim"):
        dk = u.get("depo_kirilim") or {}
        if isinstance(dk, dict):
            for d in dk.keys():
                if str(d).strip():
                    depolar.add(depo_kanonik(d))
    try:
        from ithalat.database import get_dosyalar as _ith_dosyalar
        for d in (_ith_dosyalar() or []):
            if str(d.get("durum") or "").strip() == "Teslim Alındı":
                _td = (d.get("teslim_deposu") or "").strip()
                if _td:
                    depolar.add(depo_kanonik(_td))
    except Exception:
        pass
    # Stoğu olmasa da seçilebilsin (Ekim 2026: yeni açılan yedek parça deposu, Mikro'daki pazarlama deposu)
    depolar |= {"PAZARLAMA", "YEDEK PARÇA DEPO"}
    return sorted(depolar)


@st.cache_data(ttl=120, show_spinner=False)
def get_depo_ozet():
    """Her depo için {depo, cesit, toplam_adet, satilabilir} (adet>0 olanlar), KANONİK adlarla."""
    sayac = {}
    for u in _hepsi("urunler", "depo_kirilim"):
        dk = _kirilim_kanonik(u.get("depo_kirilim") or {})
        for d, m in dk.items():
            m = int(m or 0)
            if m <= 0:
                continue
            sayac.setdefault(d, [0, 0])
            sayac[d][0] += 1
            sayac[d][1] += m
    return [{"depo": d, "cesit": v[0], "toplam_adet": v[1],
             "satilabilir": depo_kanonik(d) in _SATILABILIR_DEPOLAR}
            for d, v in sorted(sayac.items())]


@st.cache_data(ttl=120, show_spinner=False)
def get_tum_depo_stok():
    """Depo Stok › Tüm depolar: [{sku, urun_adi, adet, depolar: [(depo, adet)]}] (depo.depo_hesap.tum_depo_stok).
    Kaynak get_depo_stok ile aynı: ürün kartındaki depo_kirilim."""
    from depo.depo_hesap import tum_depo_stok
    return tum_depo_stok(_hepsi("urunler", "sku, urun_adi, depo_kirilim"), depo_dagilimi)


@st.cache_data(ttl=120, show_spinner=False)
def get_depo_stok(depo):
    """Belirli depodaki ürünler [{sku, urun_adi, adet}] (adet>0), adet azalan sıralı.
    TEK kaynak: ürün kartındaki depo_kirilim (Stok Kartı ile birebir aynı)."""
    depo = depo_kanonik(depo)
    stok = {}   # sku_norm -> adet
    adlar = {}  # sku_norm -> urun_adi
    goster = {} # sku_norm -> ekranda gösterilecek SKU (ilk görülen yazım, BÜYÜK)

    def _skun(s):
        return " ".join(str(s or "").strip().upper().split())  # BÜYÜK + tek boşluk

    for u in _hepsi("urunler", "sku, urun_adi, depo_kirilim"):
        sku = str(u.get("sku") or "").strip()
        if not sku:
            continue
        key = _skun(sku)
        goster.setdefault(key, key)
        if not adlar.get(key):
            adlar[key] = u.get("urun_adi", "") or ""
        dk = _kirilim_kanonik(u.get("depo_kirilim") or {})
        m = int(dk.get(depo, 0) or 0)
        if m != 0:
            stok[key] = stok.get(key, 0) + m

    # NOT: Eski sürüm burada "Teslim Alındı" ithalat kalemlerinin ÖMÜRLÜK toplamını
    # ekliyordu — satışlar düşülmediği için stok şişiyordu. Miktarın tek gerçek
    # kaynağı artık ürün kartındaki depo_kirilim'dir. İşlenmemiş teslim dosyaları:
    # ithalat.database.teslim_stok_bekleyenler (Veri sağlığı sayfasında listelenir).

    out = [{"sku": goster.get(s, s), "urun_adi": adlar.get(s, ""), "adet": a}
           for s, a in stok.items() if a > 0]
    return sorted(out, key=lambda x: -x["adet"])


def _sevk_kart_bul(sb, sku):
    """Sevk edilecek ürün kartı: önce birebir SKU, yoksa harf/boşluk farkıyla eşleşen kart
    (liste normalize SKU gösteriyor). Döner: (kart | None, kartın gerçek SKU yazımı)."""
    u = _row(sb.table("urunler").select("sku, urun_adi, depo_kirilim").eq("sku", sku).execute())
    if not u:
        _hedef = " ".join(str(sku or "").strip().upper().split())
        for _u in _hepsi("urunler", "sku, urun_adi, depo_kirilim"):
            if " ".join(str(_u.get("sku") or "").strip().upper().split()) == _hedef:
                u = _u
                sku = _u.get("sku")  # gerçek yazımla devam et
                break
    return u, sku


def _sevk_aciklama(kaynak_depo, hedef_depo, belge_no):
    return (f"{kaynak_depo} → {hedef_depo}"
            + (f" · belge {belge_no}" if str(belge_no or "").strip() else ""))


def depo_sevk(sku, kaynak_depo, hedef_depo, adet, kullanici="", sevk_tarihi="", belge_no=""):
    """Depolar arası sevk: kaynak→hedef 'adet' taşır, bizim_stok'u yeniden
    hesaplar, kalıcı yazar, geçmişe + audit'e ekler. Döner: (ok, mesaj).
    sevk_tarihi/belge_no: sevk loguna yazılır (kolonlar yoksa otomatik atlanır).

    ATOMİK (veritabani/29_atomik_stok.sql kuruluysa): kart kilitlenir, yeterlilik kilit altında
    denetlenir; kırılım + stok defteri + sevk geçmişi tek işlemde yazılır (aynı anda iki sevk birbirini
    ezmez). Fonksiyon kurulu değilse bugünkü yol çalışır — aynı hesap, aynı mesajlar."""
    try:
        sb = get_client()
        u, sku = _sevk_kart_bul(sb, sku)
        if not u:
            return False, f"❌ Ürün bulunamadı: {sku}"
        _log = {
            "sku": sku, "urun_adi": u.get("urun_adi", ""),
            "kaynak_depo": kaynak_depo, "hedef_depo": hedef_depo,
            "adet": int(adet or 0), "kullanici": kullanici or "", "tarih": tr_now_str(),
        }
        _log2 = dict(_log)
        if str(sevk_tarihi or "").strip():
            _log2["sevk_tarihi"] = str(sevk_tarihi)[:10]
        if str(belge_no or "").strip():
            _log2["belge_no"] = str(belge_no).strip()[:60]
        # ── Atomik yol ──
        hata, atomik = "", False
        try:
            atomik, _ = atomik_rpc(sb, "depo_sevk_islem", {
                "p_sku": sku, "p_kaynak": depo_kanonik(kaynak_depo), "p_hedef": depo_kanonik(hedef_depo),
                "p_adet": int(adet or 0), "p_aciklama": _sevk_aciklama(kaynak_depo, hedef_depo, belge_no),
                "p_log": {k: v for k, v in _log2.items() if k not in ("sku", "urun_adi")},
                "p_ortam": atomik_ortam(),
            })
        except AtomikHata as e:
            # iş kuralı (yetersiz stok vb.) bugünkü mesajla; diğerleri 'hiçbir şey değişmedi'
            hata = e.mesaj if e.kod == "P0001" else f"Sevk yapılmadı, hiçbir şey değişmedi: {e.mesaj[:160]}"
        # ── Bugünkü yol (fonksiyon kurulu değil) ──
        if not atomik and not hata:
            dk = u.get("depo_kirilim") or {}
            if not isinstance(dk, dict):
                return False, "❌ Bu ürünün depo kırılımı yok (önce G5F stok yükleyin)."
            yeni_dk, hata = _sevk_uygula(dk, kaynak_depo, hedef_depo, adet)
            if not hata:
                sb.table("urunler").update({
                    "depo_kirilim": yeni_dk,
                    "bizim_stok": _bizim_stok_hesapla(yeni_dk),
                    "guncelleme_tarihi": get_today(),
                }).eq("sku", sku).execute()
                try:
                    _sd = _defter()
                    _sd.yaz_fark(sku, dk, yeni_dk, "sevk", _sevk_aciklama(kaynak_depo, hedef_depo, belge_no))
                except Exception:
                    pass
                try:
                    try:
                        sb.table("depo_sevk_log").insert(_log2).execute()
                    except Exception:
                        # sevk_tarihi/belge_no kolonları tabloda yoksa temel logla devam et
                        sb.table("depo_sevk_log").insert(_log).execute()
                except Exception:
                    pass
        if hata:
            return False, f"❌ {hata}"
        if atomik:
            atomik_audit("güncelle", "urunler", sku, "depo_kirilim (sevk, tek işlem)", "kayranpm")
        try:
            from shared.audit import log_yaz
            _ek = (f" · belge:{belge_no}" if str(belge_no or "").strip() else "")
            log_yaz("depo_sevk", "urunler", sku,
                    f"{adet} adet {kaynak_depo} → {hedef_depo}{_ek}", "kayranpm")
        except Exception:
            pass
        _cache_temizle()
        return True, f"✅ {adet} adet '{sku}': {kaynak_depo} → {hedef_depo}"
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}"


@st.cache_data(ttl=120, show_spinner=False)
def get_depo_sevk_gecmisi(limit=50):
    """Son sevkler (depo_sevk_log). Tablo yoksa boş liste döner."""
    try:
        r = (get_client().table("depo_sevk_log").select("*")
             .order("id", desc=True).limit(limit).execute())
        return _rows(r)
    except Exception:
        return []


# ═══════════ MODEL B — HAREKET BAZLI STOK ÇEKİRDEĞİ ═══════════
class _DefterYok:
    """Stok defteri yüklenemezse kullanılan etkisiz yedek — stok işlemleri DURMASIN."""
    @staticmethod
    def kaynak_bul():
        return ""

    @staticmethod
    def yaz(*a, **k):
        return None

    @staticmethod
    def yaz_fark(*a, **k):
        return None

    @staticmethod
    def toplu():
        import contextlib
        return contextlib.nullcontext()


def _defter():
    try:
        from shared import stok_defteri
        return stok_defteri
    except Exception:
        return _DefterYok


# ═══════════ ATOMİK STOK (veritabani/29_atomik_stok.sql) ═══════════
# Kayıt + stok + defter tek veritabanı işleminde, ürün satırı kilitli yazılır (kayıp güncelleme yok).
# Fonksiyonlar kurulu DEĞİLSE her yazım bugünkü yoldan yürür — aynı sonuç. Kurulu ama işlem
# reddedildiyse (AtomikHata) hiçbir şey yazılmamıştır; çağıran kullanıcıya açık hata gösterir.
class AtomikHata(Exception):
    """Atomik fonksiyon kurulu, işlem veritabanında reddedildi ve GERİ ALINDI (hiçbir şey yazılmadı)."""

    def __init__(self, mesaj, kod=""):
        super().__init__(mesaj)
        self.mesaj = str(mesaj or "")
        self.kod = str(kod or "")


_ATOMIK = {"yok_zaman": 0.0}      # fonksiyon bulunamadıysa ne zaman (bu süre boyunca hiç denenmez)
_ATOMIK_YOK_SURE = 600            # sn — SQL sonradan kurulursa en geç 10 dk içinde devreye girer


def _rpc_hata_bilgi(e):
    """PostgREST hatasından (kod, mesaj). APIError .code / .message taşır; yoksa metinden."""
    kod = str(getattr(e, "code", "") or "")
    msg = str(getattr(e, "message", "") or "")
    if not kod or not msg:
        import re as _r
        t = str(e)
        if not kod:
            m = _r.search(r"['\"]code['\"]\s*:\s*['\"]?([A-Za-z0-9]+)", t)
            kod = m.group(1) if m else ""
        if not msg:
            m = _r.search(r"['\"]message['\"]\s*:\s*['\"](.+?)['\"]\s*[,}]", t)
            msg = m.group(1) if m else t
    return kod, msg


def _rpc_yok_mu(e):
    """Fonksiyon kurulu değil / çağrılamıyor mu? (O zaman bugünkü yola düşülür; çağrı hiçbir şey
    yazmamıştır.) PGRST202 = PostgREST şema önbelleğinde yok; 42883 = Postgres'te yok;
    42501 + function = çalıştırma yetkisi yok; 404 = uç nokta yok."""
    kod, msg = _rpc_hata_bilgi(e)
    t = f"{kod} {msg} {e}".lower()
    return (kod in ("PGRST202", "42883", "404")
            or "could not find the function" in t
            or (kod == "42501" and "function" in t))


def _json_temiz(v):
    """RPC parametresi JSON'a sığsın: numpy sayısı (ekran tablosundan gelen kimlik), tarih, Decimal."""
    import json as _json
    from decimal import Decimal

    def _donustur(o):
        if isinstance(o, Decimal):
            return float(o)
        if hasattr(o, "item"):
            try:
                return o.item()
            except Exception:
                pass
        if hasattr(o, "isoformat"):
            return o.isoformat()
        if isinstance(o, (set, frozenset, tuple)):
            return list(o)
        return str(o)
    return _json.loads(_json.dumps(v, default=_donustur))


def atomik_hazir(sb):
    """Atomik yol denenebilir mi? (istemci rpc destekliyor, fonksiyon yakın zamanda 'yok' çıkmadı,
    hesap salt-okur değil). Hazır değilse çağıranlar yük hazırlamadan bugünkü yola geçer."""
    import time as _t
    if _t.time() - _ATOMIK["yok_zaman"] < _ATOMIK_YOK_SURE:
        return False
    if not callable(getattr(sb, "rpc", None)):
        return False
    try:
        from shared.audit import salt_okur_mu
        if salt_okur_mu():
            return False
    except Exception:
        pass
    return True


def atomik_rpc(sb, ad, params):
    """Atomik fonksiyonu çağırır. Döner: (True, veri) | (False, None) = fonksiyon yok → bugünkü yol.
    Fonksiyon var ama hata verdiyse AtomikHata (işlem geri alınmıştır). Kilitlenme (40P01) /
    serileştirme (40001) hatasında bir kez yeniden dener. Salt-okur hesapta denemez (bugünkü yol
    yazmayı zaten engeller ve uyarır)."""
    import time as _t
    if not atomik_hazir(sb):
        return False, None
    rpc = sb.rpc
    params = _json_temiz(params)
    for _deneme in range(2):
        try:
            veri = rpc(ad, params).execute().data
        except Exception as e:
            if _rpc_yok_mu(e):
                _ATOMIK["yok_zaman"] = _t.time()
                return False, None
            kod, msg = _rpc_hata_bilgi(e)
            if kod in ("40P01", "40001") and _deneme == 0:
                continue
            raise AtomikHata(msg, kod) from e
        if not isinstance(veri, dict):
            # Bizim fonksiyonlarımız her zaman nesne döner; başka bir şey geldiyse bu ad bizim
            # fonksiyonumuz değildir (ör. sahte istemci) → kurulu sayılmaz, bugünkü yol.
            _ATOMIK["yok_zaman"] = _t.time()
            return False, None
        return True, veri
    return False, None


def atomik_ortam(kaynak=None):
    """Stok defteri satırlarının ortak alanları (shared/stok_defteri.yaz ile aynı)."""
    _sd = _defter()
    try:
        k = _sd.kaynak_bul() if kaynak is None else kaynak
    except Exception:
        k = ""
    try:
        kul = _sd._kullanici()
    except Exception:
        kul = ""
    try:
        yk = _sd.aktif_yukleme()
    except Exception:
        yk = ""
    return {"kaynak": str(k or "")[:120], "kullanici": str(kul or "")[:40],
            "yukleme_kodu": yk or None, "bugun": get_today()}


def atomik_audit(islem, tablo, kayit_id="", detay="", modul=""):
    """Atomik çağrı tablo sarmalayıcısından geçmez; değişiklik kaydı elle yazılır."""
    try:
        from shared.audit import log_yaz
        log_yaz(islem, tablo, kayit_id, detay, modul)
    except Exception:
        pass


def stok_adaylari(sku):
    """Hareketin uygulanacağı kartı bulmak için denenecek SKU yazımları — stok_hareket_coklu'daki
    sırayla: girilen, BÜYÜK harf (farklıysa), kartın yazımı (kart_sku_coz, öncekilerden farklıysa)."""
    sku = str(sku or "").strip()
    out = [sku]
    if sku != sku.upper():
        out.append(sku.upper())
    try:
        ks = kart_sku_coz(sku)
    except Exception:
        ks = ""
    if ks and ks not in (sku, sku.upper()):
        out.append(ks)
    return out


def stok_kalemleri(gruplar, aciklama="", kart_ac=False, kart_adlar=None):
    """[(depo, {sku: delta}), ...] → atomik fonksiyonun hareket listesi. Süzme / depo adı / mesaj
    kuralları stok_hareket_coklu ile birebir (sku strip, delta 0 ise atla, depo kanonik)."""
    kart_adlar = kart_adlar or {}
    out = []
    for depo, hareketler in (gruplar or []):
        d = depo_kanonik((depo or "").strip() or "MERKEZ DEPO")
        for sku, delta in (hareketler or {}).items():
            sku = str(sku or "").strip()
            try:
                delta = float(delta or 0)
            except Exception:
                delta = 0
            if not sku or delta == 0:
                continue
            out.append({"sku": sku, "adaylar": stok_adaylari(sku), "depo": d, "delta": delta,
                        "aciklama": aciklama or "",
                        "hata_aciklama": aciklama or f"{delta:+g} uygulanamadı",
                        "kart_ac": bool(kart_ac), "kart_ad": (kart_adlar.get(sku) or "")[:200]})
    return out


def stok_aday_haritasi(skular):
    """{sku: [aday yazımlar]} — veritabanında türetilen hareketler (silme/düzenleme) için."""
    out = {}
    for s in (skular or []):
        s = str(s or "").strip()
        if s and s not in out:
            out[s] = stok_adaylari(s)
    return out


def stok_atomik_sonuc(veri):
    """Atomik çağrının (uygulanan, atlanan) özeti."""
    veri = veri if isinstance(veri, dict) else {}
    try:
        uyg = int(veri.get("uygulanan") or 0)
    except Exception:
        uyg = 0
    return uyg, [str(s) for s in (veri.get("atlanan") or [])]


def _stok_atomik(gruplar, kart_ac=False, kart_adlar=None, aciklama=""):
    """Hareketleri tek atomik çağrıyla uygular. Fonksiyon yoksa None (çağıran bugünkü yola düşer).
    Reddedilirse hiçbir şey yazılmamıştır: her SKU deftere başarısız yazılır, kritik hata kaydı
    düşülür ve (0, tüm SKU'lar) döner — bugünkü 'atlanan' sözleşmesiyle aynı."""
    _sd = _defter()
    try:
        sb = get_client()
    except Exception:
        return None                       # bağlantı yok → bugünkü yol kendi hatasını yazar
    if not atomik_hazir(sb):
        return None
    kalemler = stok_kalemleri(gruplar, aciklama, kart_ac, kart_adlar)
    if not kalemler:
        return None
    ortam = atomik_ortam()
    try:
        ok, veri = atomik_rpc(sb, "stok_uygula", {"p_hareketler": kalemler, "p_ortam": ortam})
    except AtomikHata as e:
        with _sd.toplu():
            for k in kalemler:
                _sd.yaz(k["sku"], k["depo"], 0, 0, "hata", k["hata_aciklama"], basarili=False,
                        hata=f"işlem reddedildi, hiçbir şey yazılmadı: {e.mesaj}"[:500],
                        kaynak=ortam["kaynak"])
        try:
            from shared.hata_log import kaydet
            kaydet("kayranpm.stok_hareket_coklu", e,
                   f"atomik stok_uygula reddedildi ({len(kalemler)} hareket) kaynak={ortam['kaynak']}",
                   kritik=True)
        except Exception:
            pass
        _cache_temizle()
        return 0, [k["sku"] for k in kalemler]
    if not ok:
        return None
    uyg, atl = stok_atomik_sonuc(veri)
    for k in kalemler:
        if k["sku"] not in atl:
            atomik_audit("güncelle", "urunler", k["sku"], f"depo_kirilim {k['depo']} {k['delta']:+g}",
                         "kayranpm")
    _cache_temizle()
    return uyg, atl


def _mikro_stok_yonetir():
    try:
        from kayranpm.mikro_stok import acik_mi
        return bool(acik_mi())
    except Exception:  # noqa: BLE001
        return False


def _mikro_kabul(hareketler):
    """Mikro yönetirken: sıfır olmayan hareket sayısı 'uygulandı' sayılır, hiçbir şey yazılmaz."""
    n = 0
    for sku, delta in (hareketler or {}).items():
        try:
            if str(sku or "").strip() and float(delta or 0):
                n += 1
        except (TypeError, ValueError):
            pass
    return n, []


def stok_hareket_gruplu(gruplar, aciklama=""):
    """Birden çok depoya hareket: [(depo, {sku: delta}), ...]. Atomik fonksiyon kuruluysa HEPSİ tek
    işlemde (ya hepsi ya hiçbiri); değilse her depo için sırayla bugünkü stok_hareket_coklu.
    Döner: (uygulanan, atlanan)."""
    gruplar = [(d, h) for d, h in (gruplar or []) if h]
    if _mikro_stok_yonetir():
        uyg = 0
        for _d, h in gruplar:
            uyg += _mikro_kabul(h)[0]
        return uyg, []
    sonuc = _stok_atomik(gruplar, aciklama=aciklama)
    if sonuc is not None:
        return sonuc
    uyg, atl = 0, []
    for depo, h in gruplar:
        # stok_hareket_coklu üzerinden: atomik yol burada zaten 'yok' çıktı, o da bugünkü yola düşer
        u, a = stok_hareket_coklu(h, depo, aciklama=aciklama)
        uyg += u
        atl.extend(a or [])
    return uyg, atl


def stok_hareket_coklu(hareketler, depo=None, kart_ac=False, kart_adlar=None, aciklama=""):
    """MODEL B: {sku: delta} hareketlerini urunler.depo_kirilim'e uygular.
    delta + → giriş, − → çıkış. depo verilmezse 'MERKEZ DEPO'.
    kart_ac=True: ürün kartı olmayan SKU için otomatik boş kart açılır (adı kart_adlar[sku]).
    Ürün kartı yoksa ve kart_ac=False → SKU atlanır. Döner: (uygulanan, atlanan).

    ATOMİK: veritabani/29_atomik_stok.sql kuruluysa kartlar kilitlenip hepsi tek işlemde yazılır
    (eşzamanlı iki yazım birbirini ezmez). Kurulu değilse aşağıdaki bugünkü yol — aynı hesap.

    MİKRO: depo stoğu eşitlemesi (kayranpm.mikro_stok) açıksa miktar YAZILMAZ — stok Mikro'dan gelir; yazılsaydı
    15 dakika sonra Mikro'nun rakamıyla ezilir, arada yanlış stok görünür (Ekim 2026 denetimi). Hareket kabul edilmiş
    sayılır (çağıran akış — ithalat teslimi, satış, teknik servis — işini bitirir)."""
    if _mikro_stok_yonetir():
        return _mikro_kabul(hareketler)
    sonuc = _stok_atomik([(depo, hareketler)], kart_ac, kart_adlar, aciklama)
    if sonuc is not None:
        return sonuc
    return _stok_hareket_coklu_eski(hareketler, depo, kart_ac, kart_adlar, aciklama)


def _stok_hareket_coklu_eski(hareketler, depo=None, kart_ac=False, kart_adlar=None, aciklama=""):
    """Bugünkü yol (atomik fonksiyon kurulu değilken): oku → Python'da değiştir → yaz.

    STOK DEFTERİ: her uygulanan hareket VE her başarısız deneme (nedeniyle)
    'stok_hareketleri' tablosuna yazılır. Eskiden başarısız SKU sessizce
    'atlanan' listesine düşüyor, nedeni kayboluyordu."""
    _sd = _defter()
    depo = depo_kanonik((depo or "").strip() or "MERKEZ DEPO")
    kart_adlar = kart_adlar or {}
    uygulanan, atlanan = 0, []
    _kaynak = _sd.kaynak_bul()

    def _basarisiz(sku, delta, neden, istisna=None):
        atlanan.append(sku)
        _sd.yaz(sku, depo, 0, 0, "hata", aciklama or f"{delta:+g} uygulanamadı",
                basarili=False, hata=neden, kaynak=_kaynak)
        if istisna is not None:
            try:
                from shared.hata_log import kaydet
                kaydet("kayranpm.stok_hareket_coklu", istisna,
                       f"sku={sku} depo={depo} delta={delta} kaynak={_kaynak}", kritik=True)
            except Exception:
                pass

    try:
        sb = get_client()
    except Exception as e:
        with _sd.toplu():
            for _s, _d in (hareketler or {}).items():
                _basarisiz(str(_s), _d, f"veritabanı bağlantısı yok: {type(e).__name__}", e)
        return 0, list(hareketler or {})

    with _sd.toplu():
        for sku, delta in (hareketler or {}).items():
            sku = str(sku or "").strip()
            try:
                delta = float(delta or 0)
            except Exception:
                delta = 0
            if not sku or delta == 0:
                continue
            try:
                u = _row(sb.table("urunler").select("sku, depo_kirilim").eq("sku", sku).execute())
                if not u and sku != sku.upper():
                    u = _row(sb.table("urunler").select("sku, depo_kirilim").eq("sku", sku.upper()).execute())
                if not u:
                    # Yazım farkı: 'MIO MIVUE J30' → kart 'Mio MiVue J30', 'Fazeon X' → 'X' (Ekim 2026)
                    _ks = kart_sku_coz(sku)
                    if _ks and _ks not in (sku, sku.upper()):
                        u = _row(sb.table("urunler").select("sku, depo_kirilim").eq("sku", _ks).execute())
                if not u:
                    if kart_ac:
                        # Otomatik boş kart aç (fiyat/paçal 0, sadece stok tutulur)
                        try:
                            sb.table("urunler").insert({
                                "sku": sku, "urun_adi": (kart_adlar.get(sku) or "")[:200],
                                "depo_kirilim": {}, "bizim_stok": 0,
                            }).execute()
                            u = {"sku": sku, "depo_kirilim": {}}
                        except Exception as e:
                            _basarisiz(sku, delta, f"ürün kartı açılamadı: {type(e).__name__}: {str(e)[:120]}", e)
                            continue
                    else:
                        _basarisiz(sku, delta, "ürün kartı yok — stok işlenmedi")
                        continue
                dk = u.get("depo_kirilim") or {}
                if not isinstance(dk, dict):
                    dk = {}
                once = float(dk.get(depo, 0) or 0)
                dk[depo] = once + delta
                if abs(dk[depo]) < 1e-9:
                    dk[depo] = 0
                sb.table("urunler").update({
                    "depo_kirilim": dk,
                    "bizim_stok": _bizim_stok_hesapla(dk),
                    "guncelleme_tarihi": get_today(),
                }).eq("sku", u["sku"]).execute()
                uygulanan += 1
                _sd.yaz(u["sku"], depo, once, dk[depo], "cikis" if delta < 0 else "giris",
                        aciklama, kaynak=_kaynak)
            except Exception as e:
                _basarisiz(sku, delta, f"{type(e).__name__}: {str(e)[:200]}", e)
    _cache_temizle()
    return uygulanan, atlanan


# ═══════════ MÜKERRER SKU BİRLEŞTİRME (büyük/küçük harf farkı) ═══════════
def _ad_norm(s):
    """Ürün adını karşılaştırma için sadeleştirir: boşluk/harf/Türkçe farkını yok sayar."""
    s = _depo_norm(s)  # büyük harf + Türkçe sadeleştirme
    return " ".join(s.split())  # çoklu boşlukları teke indir


def mukerrer_sku_bul(ada_gore=False):
    """Mükerrer ürün kartlarını bulur.
    ada_gore=False: yalnız SKU'nun büyük/küçük harf farkı ('Mio1' vs 'MIO1').
    ada_gore=True : ek olarak ÜRÜN ADI aynı olan farklı SKU'ları da grup sayar
                    ('Mio MiVue 802' / 'MIO MIVUE 802' gibi).
    Döner: [{"kanonik", "kartlar":[...], "tur": "sku"|"ad"}]."""
    kartlar_all = []
    for u in _hepsi("urunler", "sku, urun_adi, kategori, marka, barkod, satis_fiyati, "
                              "alis_fiyati, hedef_kar_marji, bizim_stok, depo_kirilim"):
        if str(u.get("sku") or "").strip():
            kartlar_all.append(u)

    out, kullanildi = [], set()

    # 1) SKU harf-farkı grupları
    by_sku = {}
    for u in kartlar_all:
        by_sku.setdefault(str(u["sku"]).strip().upper(), []).append(u)
    for anahtar, kartlar in by_sku.items():
        if len(kartlar) > 1:
            out.append({"kanonik": anahtar, "kartlar": kartlar, "tur": "sku"})
            for k in kartlar:
                kullanildi.add(str(k["sku"]))

    # 2) (opsiyonel) Ürün adı aynı, SKU farklı grupları
    if ada_gore:
        by_ad = {}
        for u in kartlar_all:
            if str(u["sku"]) in kullanildi:
                continue
            ad = _ad_norm(u.get("urun_adi"))
            if ad:
                by_ad.setdefault(ad, []).append(u)
        for ad, kartlar in by_ad.items():
            if len(kartlar) > 1:
                out.append({"kanonik": (kartlar[0].get("urun_adi") or ad),
                            "kartlar": kartlar, "tur": "ad"})
    return sorted(out, key=lambda g: str(g["kanonik"]))


def _kart_dolu_skor(k):
    """Bir kartın 'ne kadar dolu' olduğunu puanlar (birleştirmede ana kartı seçmek için)."""
    s = 0
    for alan in ("urun_adi", "kategori", "marka", "barkod"):
        if str(k.get(alan) or "").strip():
            s += 1
    for alan in ("satis_fiyati", "alis_fiyati", "hedef_kar_marji", "bizim_stok"):
        try:
            if float(k.get(alan) or 0) != 0:
                s += 1
        except Exception:
            pass
    dk = k.get("depo_kirilim") or {}
    if isinstance(dk, dict):
        s += sum(1 for v in dk.values() if int(v or 0) != 0)
    return s


def mukerrer_sku_birlestir(kanonik_uppercase=None):
    """Büyük/küçük harf farkıyla mükerrer kartları TEK karta birleştirir.
    - Ana kart: en dolu olan (fiyat/kategori/depo_kirilim vb.). SKU'su BÜYÜK harfe çevrilir.
    - depo_kirilim'ler kanonikleştirilip TOPLANIR (stok kaybı olmaz).
    - Boş alanlar diğer karttan tamamlanır; dolu alanlara dokunulmaz.
    - Fazla kart(lar) silinir.
    kanonik_uppercase verilirse yalnız o grup; yoksa TÜM mükerrer gruplar işlenir.
    Döner: (birlesen_grup, silinen_kart, mesajlar[list])."""
    sb = get_client()
    gruplar = mukerrer_sku_bul()
    if kanonik_uppercase:
        gruplar = [g for g in gruplar if g["kanonik"] == str(kanonik_uppercase).upper()]
    birlesen, silinen, mesajlar = 0, 0, []
    for g in gruplar:
        kartlar = sorted(g["kartlar"], key=_kart_dolu_skor, reverse=True)
        ana = kartlar[0]
        digerleri = kartlar[1:]
        hedef_sku = str(ana.get("sku") or "").strip().upper()

        # depo_kirilim'leri kanonikleştirip TOPLA
        birlesik_dk = _kirilim_kanonik(ana.get("depo_kirilim") or {})
        payload = {}
        for d in digerleri:
            for k2, v2 in _kirilim_kanonik(d.get("depo_kirilim") or {}).items():
                birlesik_dk[k2] = birlesik_dk.get(k2, 0) + int(v2 or 0)
            # Ana kartta boş olan alanları diğerinden doldur
            for alan in ("urun_adi", "kategori", "marka", "barkod"):
                if not str(ana.get(alan) or "").strip() and str(d.get(alan) or "").strip():
                    payload[alan] = d.get(alan)
                    ana[alan] = d.get(alan)
            for alan in ("satis_fiyati", "alis_fiyati", "hedef_kar_marji"):
                try:
                    if float(ana.get(alan) or 0) == 0 and float(d.get(alan) or 0) != 0:
                        payload[alan] = d.get(alan)
                        ana[alan] = d.get(alan)
                except Exception:
                    pass

        payload["depo_kirilim"] = birlesik_dk
        payload["bizim_stok"] = _bizim_stok_hesapla(birlesik_dk)
        payload["guncelleme_tarihi"] = get_today()

        # Ana kartın SKU'su küçük harfliyse BÜYÜK'e taşı (kanonik). Supabase PK sku ise:
        try:
            if str(ana.get("sku")) != hedef_sku:
                # Önce diğerlerini sil (çakışma olmasın), sonra ana kartı BÜYÜK SKU'ya çevir
                for d in digerleri:
                    if str(d.get("sku")).upper() == hedef_sku and str(d.get("sku")) != hedef_sku:
                        continue  # aynı upper — birazdan silinecek
                # Diğer kartları sil
                for d in digerleri:
                    with cop_kutusu_kapali():
                        sb.table("urunler").delete().eq("sku", d.get("sku")).execute()
                    silinen += 1
                # Ana kartı büyük SKU ile yeniden yaz (eski küçük kaydı sil, yeni ekle)
                _ana_full = {k: ana.get(k) for k in ("urun_adi", "kategori", "marka", "barkod",
                                                     "satis_fiyati", "alis_fiyati", "hedef_kar_marji",
                                                     "ozellikler", "trendyol_stok", "ilk_giris_tarihi")
                             if ana.get(k) is not None}
                _ana_full.update(payload)
                _ana_full["sku"] = hedef_sku
                with cop_kutusu_kapali():
                    sb.table("urunler").delete().eq("sku", ana.get("sku")).execute()
                try:
                    sb.table("urunler").insert(_ana_full).execute()
                except Exception:
                    _ana_full.pop("hedef_kar_marji", None)
                    sb.table("urunler").insert(_ana_full).execute()
            else:
                # Ana SKU zaten büyük — sadece güncelle + diğerlerini sil
                sb.table("urunler").update(payload).eq("sku", ana.get("sku")).execute()
                for d in digerleri:
                    with cop_kutusu_kapali():
                        sb.table("urunler").delete().eq("sku", d.get("sku")).execute()
                    silinen += 1
            birlesen += 1
            _tekil = int(sum(birlesik_dk.values()))
            mesajlar.append(f"✅ {hedef_sku}: {len(kartlar)} kart → 1 (toplam depo stoğu {_tekil})")
        except Exception as e:
            mesajlar.append(f"❌ {hedef_sku}: birleştirilemedi — {type(e).__name__}: {str(e)[:90]}")
    _cache_temizle()
    return birlesen, silinen, mesajlar


@st.cache_data(ttl=120, show_spinner=False)
def get_sku_depo_dagilim(sku):
    """Bir SKU'nun hangi depolarda kaç adet olduğunu döndürür (kanonik depo adlarıyla).
    Döner: {depo_adi: adet} — yalnız adet>0 olanlar. Satışta depo seçimi için kullanılır."""
    try:
        sb = get_client()
        u = _row(sb.table("urunler").select("depo_kirilim").eq("sku", sku).execute())
        if not u:
            # harf/boşluk farkıyla eşleşen kartı bul
            _hedef = " ".join(str(sku or "").strip().upper().split())
            for _u in _hepsi("urunler", "sku, depo_kirilim"):
                if " ".join(str(_u.get("sku") or "").strip().upper().split()) == _hedef:
                    u = _u
                    break
        dk = _kirilim_kanonik((u or {}).get("depo_kirilim") or {})
        return {d: int(m) for d, m in dk.items() if int(m or 0) > 0}
    except Exception:
        return {}
