from datetime import datetime, date
import streamlit as st
import logging

_log = logging.getLogger(__name__)
from .database import (get_all_dashboard_data,
                      ekle_siparis_onerisi, get_yoldaki_urunler,
                      get_tum_gecmis_satislar, get_gecmis_satis_firma_bazli,
                      get_client, get_uretim_suresi)

FIRMA_LISTESI = ["ITOPYA", "HB", "VATAN", "MONDAY", "KANAL", "DIGER"]

def stok_yasi_hesapla(ilk_giris_tarihi_str):
    """Stok yaşını gün olarak hesaplar ve renk döndürür"""
    if not ilk_giris_tarihi_str:
        return 0, "yok"
    try:
        ilk = datetime.strptime(ilk_giris_tarihi_str, "%Y-%m-%d").date()
        gun = (date.today() - ilk).days
        if gun >= 90:
            return gun, "kirmizi"
        elif gun >= 60:
            return gun, "turuncu"
        elif gun >= 30:
            return gun, "sari"
        else:
            return gun, "yesil"
    except:
        return 0, "yok"


def fifo_stok_yasi(partiler, mevcut_stok):
    """
    FIFO kuralıyla stok yaşı: en eski satılır, geriye kalan en eski partinin
    belge tarihinden bugüne geçen gün.
    partiler: [{"tarih": "YYYY-MM-DD", "adet": float}, ...] (ESKİ→YENİ)
    Döner: (gun, renk, anchor_tarih). Parti/stok yoksa (None, None, None).
    """
    if not partiler or not mevcut_stok or mevcut_stok <= 0:
        return None, None, None
    toplam = sum((p.get("adet") or 0) for p in partiler)
    if toplam <= 0:
        return None, None, None
    # FIFO: en eskiden tüketilir → tüketilen adet kadar en eski partileri düş
    tuketilen = max(0.0, toplam - mevcut_stok)
    anchor = None
    for p in partiler:
        ad = p.get("adet") or 0
        if tuketilen >= ad:
            tuketilen -= ad
            continue
        anchor = p.get("tarih")  # elde kalan en eski parti
        break
    if anchor is None:  # veri uyuşmazlığı (mevcut > toplam ithalat) → en yeni parti
        anchor = partiler[-1].get("tarih")
    gun, renk = stok_yasi_hesapla(anchor)
    return gun, renk, anchor

def kac_gunluk_satis(bizim_stok, haftalik_satis):
    """Bizim stok ile kaç günlük satış yapılabileceğini hesaplar"""
    if not haftalik_satis or haftalik_satis == 0:
        return None, "yok"
    gunluk_satis = haftalik_satis / 7
    gun = int(bizim_stok / gunluk_satis) if gunluk_satis > 0 else 0
    if gun <= 15:
        renk = "kirmizi"
    elif gun >= 30:
        renk = "yesil"
    else:
        renk = "turuncu"
    return gun, renk

def satis_performansi(satis_listesi):
    """Firmaların satışlarını karşılaştırarak performans sıralaması döndürür"""
    if not satis_listesi:
        return {}
    gecerli = [(f, s) for f, s in satis_listesi if s is not None and s > 0]
    if not gecerli:
        return {f: "veri yok" for f, _ in satis_listesi}
    
    maks = max(s for _, s in gecerli)
    if maks == 0:
        return {f: "veri yok" for f, _ in satis_listesi}
    
    sonuc = {}
    for firma, satis in satis_listesi:
        if satis is None:
            sonuc[firma] = "veri yok"
            continue
        oran = satis / maks
        if oran >= 0.7:
            sonuc[firma] = "Çok İyi"
        elif oran >= 0.4:
            sonuc[firma] = "İyi"
        else:
            sonuc[firma] = "Düşük"
    return sonuc

def stok_yayilimi(urun_sku, firma_data):
    """Ürünün tüm kanallardaki stok dağılımını döndürür"""
    yayilim = {}
    for firma in FIRMA_LISTESI:
        if urun_sku in firma_data.get(firma, {}):
            yayilim[firma] = firma_data[firma][urun_sku]["stok_miktari"]
        else:
            yayilim[firma] = 0
    return yayilim


def yoldaki_durum_hesapla(sku, bizim_stok, toplam_haftalik_satis, yoldaki_data):
    """
    Yoldaki ürün durumunu hesaplar.
    🟢 Yeşil: Yoldaki miktar stoğu zamanında karşılar
    🟡 Sarı: Varış gecikmeli / stok o tarihe kadar zor dayanır
    🔴 Kırmızı: Yolda ürün yok ve stok bitmek üzere
    """
    yol = yoldaki_data.get(sku)
    gunluk_satis = (toplam_haftalik_satis / 7) if toplam_haftalik_satis else 0

    if not yol or (yol.get("yoldaki_miktar", 0) or 0) == 0:
        # Yolda ürün yok
        if gunluk_satis > 0:
            kalan_gun = bizim_stok / gunluk_satis
            if kalan_gun <= 14:
                return "kirmizi", "Yolda ürün yok, stok bitmek üzere!", 0, ""
        return "yok", "", 0, ""

    yoldaki_miktar = yol.get("yoldaki_miktar", 0) or 0
    varis_tarihi_str = yol.get("tahmini_varis_tarihi", "") or ""

    if not varis_tarihi_str or varis_tarihi_str == "nan":
        return "sari", "Varış tarihi belirsiz", yoldaki_miktar, ""

    try:
        varis = datetime.strptime(varis_tarihi_str[:10], "%Y-%m-%d").date()
        gun_kaldi = (varis - date.today()).days

        if gunluk_satis > 0:
            stokun_bitmesi = bizim_stok / gunluk_satis  # kaç günde biter
            if gun_kaldi <= stokun_bitmesi:
                return "yesil", f"Varış: {varis_tarihi_str[:10]} ({gun_kaldi}g kaldı)", yoldaki_miktar, varis_tarihi_str[:10]
            else:
                return "sari", f"Gecikme riski! Stok {int(stokun_bitmesi)}g'de biter, varış {gun_kaldi}g sonra", yoldaki_miktar, varis_tarihi_str[:10]
        else:
            return "yesil", f"Varış: {varis_tarihi_str[:10]} ({gun_kaldi}g kaldı)", yoldaki_miktar, varis_tarihi_str[:10]
    except:
        return "sari", f"Varış: {varis_tarihi_str}", yoldaki_miktar, varis_tarihi_str


URETIM_SURESI_GUN = 135  # 4.5 ay sabit

def trend_hesapla(gecmis_satislar):
    """
    Son 4 haftanın satış trendini hesaplar.
    gecmis_satislar: [{"tarih":..., "satis":...}, ...] en yeni önce

    Döndürür:
      trend_yon: "yukseliyor" | "dusuyor" | "stabil" | "yetersiz_veri"
      trend_yuzdesi: float (+ artış, - düşüş)
      ortalama_satis: float (4 hafta ortalaması)
      trend_mesaji: str
    """
    if not gecmis_satislar or len(gecmis_satislar) < 2:
        ort = gecmis_satislar[0]["satis"] if gecmis_satislar else 0
        return "yetersiz_veri", 0.0, ort, "⚪ Yeterli geçmiş veri yok"

    satislar = [h["satis"] for h in gecmis_satislar]
    ortalama = sum(satislar) / len(satislar)

    # İlk yarı vs ikinci yarı karşılaştırması
    n = len(satislar)
    yeni = sum(satislar[:n//2]) / (n//2)       # Yeni haftalar
    eski = sum(satislar[n//2:]) / (n - n//2)   # Eski haftalar

    if eski == 0:
        yuzde = 100.0 if yeni > 0 else 0.0
    else:
        yuzde = ((yeni - eski) / eski) * 100

    if yuzde >= 15:
        return "yukseliyor", yuzde, ortalama, f"📈 Yükseliyor (+%{yuzde:.0f})"
    elif yuzde <= -15:
        return "dusuyor", yuzde, ortalama, f"📉 Düşüyor (-%{abs(yuzde):.0f})"
    else:
        return "stabil", yuzde, ortalama, f"➡️ Stabil (%{yuzde:+.0f})"


def siparis_miktari_oneri(bizim_stok, ortalama_haftalik_satis, trend_yon, trend_yuzdesi, yoldaki_miktar=0, uretim_suresi=None):
    """
    Sipariş verilmesi gereken miktarı hesaplar.

    Mantık:
    - Hedef: üretim süresi (varsayılan 135 gün) + güvenlik tamponu (30 gün)
    - Mevcut stok + yoldaki stok çıkarılır
    - Trend düşüyorsa miktar azaltılır, yüksekse artırılır
    - Sonuç 0'ın altına düşemez
    """
    if not ortalama_haftalik_satis or ortalama_haftalik_satis == 0:
        return 0, "Satış verisi yok, öneri yapılamıyor"

    _us = uretim_suresi if uretim_suresi is not None else get_uretim_suresi()
    hedef_gun = _us + 30  # üretim süresi + 30 gün tampon
    gunluk_satis = ortalama_haftalik_satis / 7
    hedef_stok = hedef_gun * gunluk_satis

    # Trend düzeltmesi
    if trend_yon == "yukseliyor":
        hedef_stok *= (1 + min(trend_yuzdesi / 100, 0.3))  # max %30 artır
        trend_notu = "📈 Trend yükseldiği için miktar artırıldı"
    elif trend_yon == "dusuyor":
        hedef_stok *= (1 + max(trend_yuzdesi / 100, -0.3))  # max %30 azalt
        trend_notu = "📉 Trend düştüğü için miktar azaltıldı"
    else:
        trend_notu = "➡️ Stabil trend"

    mevcut_toplam = bizim_stok + (yoldaki_miktar or 0)
    oneri = max(0, int(hedef_stok - mevcut_toplam))

    if oneri == 0:
        return 0, "✅ Yeterli stok var, sipariş gerekmiyor"

    return oneri, f"{trend_notu} → {oneri} adet sipariş önerilir"


def risk_skoru_hesapla(bizim_stok, ortalama_haftalik_satis, stok_gun, siparis_son_gun, trend_yon):
    """
    0-100 arası risk skoru hesaplar. 100 = çok riskli, 0 = güvenli.
    """
    skor = 0

    # Sipariş aciliyeti (max 50 puan)
    if siparis_son_gun is not None:
        if siparis_son_gun <= 0:
            skor += 50
        elif siparis_son_gun <= 14:
            skor += 40
        elif siparis_son_gun <= 30:
            skor += 30
        elif siparis_son_gun <= 60:
            skor += 15

    # Stok yaşı (max 30 puan)
    if stok_gun >= 90:
        skor += 30
    elif stok_gun >= 60:
        skor += 20
    elif stok_gun >= 30:
        skor += 10

    # Trend (max 20 puan)
    if trend_yon == "dusuyor":
        skor += 10
    elif trend_yon == "yukseliyor":
        skor -= 5  # Yükselen trend riski azaltır

    skor = max(0, min(100, skor))

    if skor >= 70:
        return skor, "🔴 Çok Yüksek Risk"
    elif skor >= 45:
        return skor, "🟠 Yüksek Risk"
    elif skor >= 25:
        return skor, "🟡 Orta Risk"
    else:
        return skor, "🟢 Düşük Risk"


def _ithalat_maliyet_map():
    """İthalat modülünden SKU bazlı paçal maliyet haritası (güvenli)."""
    try:
        from ithalat.database import get_sku_maliyet_ozet
        return get_sku_maliyet_ozet() or {}
    except Exception:
        return {}


def _ithalat_partiler_map():
    """İthalat modülünden SKU bazlı FIFO parti haritası (güvenli)."""
    try:
        from ithalat.database import get_sku_ithalat_partileri
        return get_sku_ithalat_partileri() or {}
    except Exception:
        return {}


def kar_marji_hesapla(satis_fiyati, alis_fiyati, toplam_maliyet=None):
    """
    Kar marjını ve durumunu hesaplar.
    toplam_maliyet varsa (alış + ek maliyetler) onu kullanır, yoksa alış fiyatını.
    Döndürür: marj_yuzdesi, kar_tl, durum, renk
    """
    if not satis_fiyati or satis_fiyati == 0:
        return None, None, "fiyat_yok", "yok"

    maliyet = toplam_maliyet if toplam_maliyet and toplam_maliyet > 0 else alis_fiyati
    if not maliyet or maliyet == 0:
        return None, None, "alis_yok", "yok"

    kar_tl = satis_fiyati - maliyet
    marj = (kar_tl / satis_fiyati) * 100

    if marj >= 35:
        return marj, kar_tl, "yuksek", "yesil"
    elif marj >= 20:
        return marj, kar_tl, "normal", "sari"
    elif marj >= 0:
        return marj, kar_tl, "dusuk", "turuncu"
    else:
        return marj, kar_tl, "zarar", "kirmizi"



@st.cache_data(ttl=120, show_spinner=False)
def olu_stok_tespiti(sku, bizim_stok, gecmis_satislar, stok_gun):
    """
    Ölü stok tespiti yapar.

    Kriterler:
    - Bizim stok > 0 (elimizde ürün var)
    - Son 4 haftada toplam satış çok düşük (haftalık ort < 1) VEYA hiç satış yok
    - Stok yaşı 60 günden fazla

    Döndürür:
      durum: "olu" | "yavas" | "normal" | "veri_yok"
      mesaj: str
    """
    if bizim_stok == 0:
        return "normal", ""

    if not gecmis_satislar:
        if stok_gun >= 60:
            return "veri_yok", "⚠️ Satış verisi yok, stok yaşlı"
        return "veri_yok", ""

    satislar = [h["satis"] for h in gecmis_satislar]
    toplam = sum(satislar)
    ortalama = toplam / len(satislar) if satislar else 0

    if ortalama == 0 and stok_gun >= 60:
        return "olu", f"🪦 ÖLÜSTOK: {len(satislar)} haftadır satış yok, {stok_gun} günlük stok"
    elif ortalama < 1 and stok_gun >= 45:
        return "yavas", f"🐢 YAVAŞ: Hft. ort. {ortalama:.1f} adet, {stok_gun} günlük stok"
    else:
        return "normal", ""


@st.cache_data(ttl=300, show_spinner=False)
def genel_analiz_hesapla():
    """
    Kategori ve marka bazında özet analiz döndürür.
    Dashboard verisi üzerinden çalışır.
    """
    veri = dashboard_hesapla()

    # Ürün başına tek satır (firma tekrarını kaldır)
    sku_goruldu = set()
    urunler = []
    for u in veri:
        if u["sku"] not in sku_goruldu:
            sku_goruldu.add(u["sku"])
            urunler.append(u)

    # Kategori bazında özet
    kategori_ozet = {}
    for u in urunler:
        kat = u.get("kategori", "Diğer") or "Diğer"
        if kat not in kategori_ozet:
            kategori_ozet[kat] = {
                "urun_sayisi": 0,
                "toplam_stok": 0,
                "toplam_satis": 0,
                "acil_sayisi": 0,
                "olu_sayisi": 0,
                "risk_toplam": 0,
            }
        k = kategori_ozet[kat]
        k["urun_sayisi"] += 1
        k["toplam_stok"] += u.get("bizim_stok", 0)
        k["toplam_satis"] += u.get("ortalama_haftalik_satis", 0)
        if u.get("siparis_durum") == "acil":
            k["acil_sayisi"] += 1
        if u.get("olu_stok_durum") in ("olu", "yavas"):
            k["olu_sayisi"] += 1
        k["risk_toplam"] += u.get("risk_skor", 0)

    for kat in kategori_ozet:
        n = kategori_ozet[kat]["urun_sayisi"]
        kategori_ozet[kat]["ort_risk"] = round(kategori_ozet[kat]["risk_toplam"] / n, 1) if n else 0

    # Marka bazında özet
    marka_ozet = {}
    for u in urunler:
        marka = u.get("marka", "Diğer") or "Diğer"
        if marka not in marka_ozet:
            marka_ozet[marka] = {"urun_sayisi": 0, "toplam_satis": 0, "acil_sayisi": 0}
        marka_ozet[marka]["urun_sayisi"] += 1
        marka_ozet[marka]["toplam_satis"] += u.get("ortalama_haftalik_satis", 0)
        if u.get("siparis_durum") == "acil":
            marka_ozet[marka]["acil_sayisi"] += 1

    # Öncelikli sipariş listesi
    siparis_listesi = sorted(
        [u for u in urunler if u.get("oneri_miktar", 0) > 0],
        key=lambda x: (
            {"acil": 0, "yaklasıyor": 1, "planlama": 2, "normal": 3}.get(x.get("siparis_durum", "normal"), 3),
            -x.get("risk_skor", 0)
        )
    )

    return {
        "urunler": urunler,
        "kategori_ozet": kategori_ozet,
        "marka_ozet": marka_ozet,
        "siparis_listesi": siparis_listesi,
    }


@st.cache_data(ttl=300, show_spinner=False)
def tum_urunler_listesi():
    """Tüm ürünlerin stok, fiyat ve FINAL COST PRICE hesabını döndürür."""
    sb = get_client()
    urunler = sb.table("urunler").select("*").order("urun_adi").execute().data or []
    try:
        from shared.utils import tr_buyuk as _tb_ad
        for _u in urunler:
            if _u.get("urun_adi"):
                _u["urun_adi"] = _tb_ad(_u["urun_adi"])  # gösterim: tüm modüllerde BÜYÜK harf
    except Exception:
        pass

    FIRMALAR = ["ITOPYA", "HB", "VATAN", "MONDAY", "KANAL", "DIGER"]

    # Toplu sorgular — her ürün için ayrı sorgu yerine tek seferde çek
    # Tüm firma stoklarını tek sorguda al (en son tarih bazında)
    tum_firma_rows = sb.table("firma_stok").select("firma, sku, stok_miktari, yukleme_tarihi").execute().data or []

    # Her firma+sku için en son tarihin stok miktarını bul
    firma_stok_map = {}  # (firma, sku) -> stok_miktari
    tarih_map = {}  # (firma, sku) -> en_son_tarih
    for r in tum_firma_rows:
        key = (r["firma"], r["sku"])
        if key not in tarih_map or r["yukleme_tarihi"] > tarih_map[key]:
            tarih_map[key] = r["yukleme_tarihi"]
            firma_stok_map[key] = r["stok_miktari"] or 0

    kayit_map = {}  # satın-alma geçmişi İthalat'a taşındı

    sonuclar = []
    _ith_map = _ithalat_maliyet_map()
    _ith_partiler = _ithalat_partiler_map()
    for u in urunler:
        sku = u["sku"]
        satis_fiyati = u.get("satis_fiyati") or u.get("fiyat") or 0
        hedef_marj = u.get("hedef_kar_marji") or 0
        bizim_stok = u.get("bizim_stok") or 0

        # Firma stoklarını map'ten al (sorgu yok)
        firma_stoklari = {firma: firma_stok_map.get((firma, sku), 0) for firma in FIRMALAR}

        # Satın alma geçmişini map'ten al (sorgu yok)
        kayitlar = kayit_map.get(sku, [])

        toplam_firma_stok = sum(firma_stoklari.values())
        toplam_stok = bizim_stok + toplam_firma_stok

        # Stok yaşı — FIFO (ithalat belge tarihleri), bizim depo stoğu bazlı;
        # ithalat partisi yoksa ürünün ilk giriş tarihine düşer
        _fifo_gun, _fifo_renk, _fifo_anchor = fifo_stok_yasi(_ith_partiler.get(sku, []), bizim_stok)
        if _fifo_gun is not None:
            stok_gun, stok_renk, ilk_giris = _fifo_gun, _fifo_renk, _fifo_anchor
        else:
            ilk_giris = u.get("ilk_giris_tarihi", "") or ""
            stok_gun, stok_renk = stok_yasi_hesapla(ilk_giris)

        # FINAL COST PRICE — İthalat paçal (adet-ağırlıklı landed maliyet)
        # + SON FOB / SON MALİYET (en yeni ithalat dosyasından) — yalnızca gösterim için
        _ith = _ith_map.get(sku)
        if _ith and _ith.get("toplam_adet", 0) > 0:
            fob_price = _ith["pacal_fob"]
            final_cost_price = _ith["pacal_final"]
            son_fob = _ith.get("son_fob", 0) or 0
            son_final = _ith.get("son_final", 0) or 0
            son_tarih = _ith.get("son_tarih", "") or ""
            toplam_adet = _ith["toplam_adet"]
            ithalat_dosya_sayisi = _ith.get("dosya_sayisi", 0)
        else:
            fob_price = 0
            final_cost_price = 0
            son_fob = 0
            son_final = 0
            son_tarih = ""
            toplam_adet = 0
            ithalat_dosya_sayisi = 0
        mal_yuzde = ((final_cost_price / fob_price - 1) * 100) if fob_price > 0 else 0
        cost = final_cost_price - fob_price
        cost_price = final_cost_price
        stok_degeri_fcp = bizim_stok * final_cost_price
        stok_degeri_satis = bizim_stok * satis_fiyati

        if satis_fiyati > 0 and final_cost_price > 0:
            kar_usd = satis_fiyati - final_cost_price
            kar_yuzde = (kar_usd / satis_fiyati) * 100
        else:
            kar_usd = None
            kar_yuzde = None

        sonuclar.append({
            "sku": sku,
            "urun_adi": u["urun_adi"],
            "kategori": u.get("kategori") or "",
            "marka": u.get("marka") or "",
            "bizim_stok": bizim_stok,
            "firma_stoklari": firma_stoklari,
            "toplam_firma_stok": toplam_firma_stok,
            "toplam_stok": toplam_stok,
            "stok_gun": stok_gun,
            "stok_renk": stok_renk,
            "ilk_giris": ilk_giris,
            "satis_fiyati": satis_fiyati,
            "hedef_marj": hedef_marj,
            "final_cost_price": final_cost_price,
            "fob_price": fob_price,
            "son_fob": son_fob,
            "son_final": son_final,
            "son_tarih": son_tarih,
            "ithalat_dosya_sayisi": ithalat_dosya_sayisi,
            "cost": cost,
            "cost_price": cost_price,
            "mal_yuzde": mal_yuzde,
            "stok_degeri_fcp": stok_degeri_fcp,
            "stok_degeri_satis": stok_degeri_satis,
            "kar_usd": kar_usd,
            "kar_yuzde": kar_yuzde,
            "siparis_sayisi": len(kayitlar),
            "toplam_alinan_adet": toplam_adet,
            "kayitlar": kayitlar,
        })

    return sonuclar



@st.cache_data(ttl=60, show_spinner=False)
def siparis_onerisi_listesi():
    """135 günden az stok kalan ürünleri otomatik listeler"""
    veri = dashboard_hesapla()
    sonuc = []
    sku_goruldu = set()
    for u in veri:
        if u["sku"] in sku_goruldu:
            continue
        sku_goruldu.add(u["sku"])
        if u.get("siparis_durum") in ("acil", "yaklasıyor", "planlama"):
            sonuc.append(u)
    sonuc.sort(key=lambda x: {"acil": 0, "yaklasıyor": 1, "planlama": 2}.get(x.get("siparis_durum",""), 3))
    return sonuc


def siparis_takvimi_hesapla(bizim_stok, toplam_haftalik_satis, uretim_suresi=None):
    """Üretim/tedarik süresi (varsayılan 135 gün) baz alınarak sipariş takvimi hesaplar."""
    if not toplam_haftalik_satis or toplam_haftalik_satis == 0:
        return None, None, "veri_yok", "Satış verisi yok"
    _us = uretim_suresi if uretim_suresi is not None else get_uretim_suresi()
    gunluk_satis = toplam_haftalik_satis / 7
    stok_bitis_gun = int(bizim_stok / gunluk_satis) if gunluk_satis > 0 else 0
    siparis_son_gun = stok_bitis_gun - _us
    if siparis_son_gun <= 0:
        return stok_bitis_gun, siparis_son_gun, "acil", f"ACİL — {stok_bitis_gun}g'de biter"
    elif siparis_son_gun <= 30:
        return stok_bitis_gun, siparis_son_gun, "yaklasıyor", f"{siparis_son_gun}g içinde sipariş"
    elif siparis_son_gun <= 60:
        return stok_bitis_gun, siparis_son_gun, "planlama", f"{siparis_son_gun}g sonra sipariş"
    else:
        return stok_bitis_gun, siparis_son_gun, "normal", f"✅ {siparis_son_gun}g sonra sipariş"


def siparis_uyarisi_kontrol(sku, firma, firma_data, bizim_stok):
    """
    Firma stoğu azaldıysa ve bizde stok varsa uyarı döndürür.
    'Azaldı' = stok < haftalık satışın 2 katı veya stok 0
    """
    firma_urun = firma_data.get(firma, {}).get(sku)
    if not firma_urun:
        return False
    
    firma_stok = firma_urun.get("stok_miktari", 0)
    haftalik_satis = firma_urun.get("haftalik_satis", 0)
    
    if bizim_stok <= 0:
        return False
    
    # Firma stoğu 0 veya haftalık satışın 2 katından az ise uyarı
    esik = (haftalik_satis * 2) if haftalik_satis > 0 else 5
    return firma_stok <= esik

@st.cache_data(ttl=300, show_spinner=False)
def dashboard_hesapla():
    """Tüm dashboard verilerini hesaplar ve döndürür"""
    urunler, firma_data, stok_yaslar, yoldaki_data, gecmis_satislar_raw = get_all_dashboard_data()
    _us = get_uretim_suresi()  # sipariş eşiği (gün) — bir kez oku, tüm ürünlere uygula
    # gecmis_satislar_raw: {sku: [satis1, satis2, ...]} — trend_hesapla formatına çevir
    gecmis_satislar = {}
    for sku, satislar in gecmis_satislar_raw.items():
        gecmis_satislar[sku] = [{"satis": s} for s in satislar]

    # stok_yaslar Supabase'den dict olarak geliyor
    stok_yas_map = {}
    for sku, v in stok_yaslar.items():
        if isinstance(v, dict):
            stok_yas_map[sku] = v.get("ilk_gorulen_tarih", "")
        else:
            stok_yas_map[sku] = v or ""

    dashboard_satirlar = []
    _ith_map = _ithalat_maliyet_map()
    _ith_partiler = _ithalat_partiler_map()

    for urun in urunler:
        sku = urun["sku"]
        urun_adi = urun["urun_adi"]
        bizim_stok = urun.get("bizim_stok", 0) or 0
        trendyol_stok = urun.get("trendyol_stok", 0) or 0
        kategori = urun.get("kategori", "")

        # Firma stok toplamı
        toplam_firma_stok = sum(
            (firma_data.get(f, {}).get(sku, {}) or {}).get("stok_miktari", 0) or 0
            for f in FIRMA_LISTESI
        )
        toplam_stok = bizim_stok + toplam_firma_stok

        # Stok yaşı — FIFO (ithalat belge tarihleri), bizim depo stoğu bazlı;
        # ithalat partisi yoksa eski yönteme (ilk görülen tarih) düşer
        _fifo_gun, _fifo_renk, _fifo_anchor = fifo_stok_yasi(_ith_partiler.get(sku, []), bizim_stok)
        if _fifo_gun is not None:
            stok_gun, stok_renk = _fifo_gun, _fifo_renk
            ilk_tarih = _fifo_anchor
        else:
            ilk_tarih = stok_yas_map.get(sku) or urun.get("ilk_giris_tarihi", "")
            stok_gun, stok_renk = stok_yasi_hesapla(ilk_tarih)

        # Firma bazlı veriler
        firma_satirlari = []
        satis_karsilastirma = []

        for firma in FIRMA_LISTESI:
            firma_urun = firma_data.get(firma, {}).get(sku)
            if firma_urun:
                f_stok = firma_urun.get("stok_miktari", 0) or 0
                f_satis = firma_urun.get("haftalik_satis", 0) or 0
            else:
                f_stok = 0
                f_satis = 0

            # Firmada stok yoksa satır oluşturma
            if f_stok == 0:
                satis_karsilastirma.append((firma, f_satis))
                continue

            gun_sayisi, gun_renk = kac_gunluk_satis(toplam_stok, f_satis)
            uyari = siparis_uyarisi_kontrol(sku, firma, firma_data, toplam_stok)
            muadil_gerekli = False
            satis_karsilastirma.append((firma, f_satis))

            firma_satirlari.append({
                "firma": firma,
                "stok": f_stok,
                "satis": f_satis,
                "gun_sayisi": gun_sayisi,
                "gun_renk": gun_renk,
                "siparis_uyarisi": uyari,
                "muadil_gerekli": muadil_gerekli,
            })

        # Satış performansı
        performans_map = satis_performansi(satis_karsilastirma)
        for fs in firma_satirlari:
            fs["performans"] = performans_map.get(fs["firma"], "veri yok")

        # Stok yayılımı
        yayilim = stok_yayilimi(sku, firma_data)
        yayilim["TRENDYOL"] = trendyol_stok

        # Toplam haftalık satış
        toplam_satis = sum(fd["satis"] for fd in firma_satirlari)

        # Trend hesaplama (geçmiş 4 hafta)
        gecmis = gecmis_satislar.get(sku, [])
        trend_yon, trend_yuzdesi, ortalama_satis, trend_mesaji = trend_hesapla(gecmis)

        # Yoldaki miktar
        yol = yoldaki_data.get(sku, {})
        yoldaki_miktar = yol.get("yoldaki_miktar", 0) or 0

        # Sipariş takvimi — TOPLAM STOK baz alınır
        stok_bitis_gun, siparis_son_gun, siparis_durum, siparis_mesaj = siparis_takvimi_hesapla(
            toplam_stok, ortalama_satis if ortalama_satis > 0 else toplam_satis, _us
        )

        # Sipariş miktarı önerisi — TOPLAM STOK baz alınır
        oneri_miktar, oneri_mesaj = siparis_miktari_oneri(
            toplam_stok, ortalama_satis if ortalama_satis > 0 else toplam_satis,
            trend_yon, trend_yuzdesi, yoldaki_miktar, _us
        )

        # Risk skoru — TOPLAM STOK baz alınır
        risk_skor, risk_etiketi = risk_skoru_hesapla(
            toplam_stok, ortalama_satis if ortalama_satis > 0 else toplam_satis,
            stok_gun, siparis_son_gun, trend_yon
        )

        # Kar marjı
        satis_f = urun.get("satis_fiyati") or urun.get("fiyat") or 0
        _ith = _ith_map.get(sku)
        alis_f = _ith["pacal_final"] if (_ith and _ith.get("toplam_adet", 0) > 0) else 0
        kar_marji, kar_tl, kar_durum, kar_renk = kar_marji_hesapla(satis_f, alis_f)

        # Ölü stok tespiti
        olu_durum, olu_mesaj = olu_stok_tespiti(sku, bizim_stok, gecmis, stok_gun)

        # Yoldaki durum
        yol_renk, yol_mesaj, yol_miktar, yol_varis = yoldaki_durum_hesapla(
            sku, bizim_stok, ortalama_satis if ortalama_satis > 0 else toplam_satis, yoldaki_data
        )

        # EOL (End of Life) — bu ürün için sipariş ÖNERİLMEZ
        _eol = bool(urun.get("eol"))
        if _eol:
            oneri_miktar = 0
            oneri_mesaj = "⛔ EOL — sipariş önerilmez"
            siparis_durum = "eol"
            siparis_mesaj = "⛔ EOL (üretimi/satışı sonlandı) — sipariş önerisi yapılmaz"

        dashboard_satirlar.append({
            "sku": sku,
            "eol": _eol,
            "satis_fiyat_listesi": urun.get("satis_fiyat_listesi") or {},
            "urun_adi": urun_adi,
            "kategori": kategori,
            "marka": urun.get("marka", ""),
            "alis_fiyati": alis_f,
            "ithalat_fob": (_ith["pacal_fob"] if _ith else 0),
            "ithalat_final": alis_f,
            "ithalat_son_fob": (_ith.get("son_fob", 0) or 0 if _ith else 0),
            "ithalat_son_final": (_ith.get("son_final", 0) or 0 if _ith else 0),
            "ithalat_son_tarih": (_ith.get("son_tarih", "") or "" if _ith else ""),
            "ithalat_dosya_sayisi": (_ith.get("dosya_sayisi", 0) if _ith else 0),
            "bizim_stok": bizim_stok,
            "toplam_stok": toplam_stok,
            "toplam_firma_stok": toplam_firma_stok,
            "trendyol_stok": trendyol_stok,
            "stok_gun": stok_gun,
            "stok_renk": stok_renk,
            "ilk_giris": ilk_tarih,
            "yayilim": yayilim,
            "firma_detay": firma_satirlari,
            "toplam_haftalik_satis": toplam_satis,
            "ortalama_haftalik_satis": round(ortalama_satis, 1),
            "gecmis_satislar": gecmis,
            "trend_yon": trend_yon,
            "trend_yuzdesi": round(trend_yuzdesi, 1),
            "trend_mesaji": trend_mesaji,
            "stok_bitis_gun": stok_bitis_gun,
            "siparis_son_gun": siparis_son_gun,
            "siparis_durum": siparis_durum,
            "siparis_mesaj": siparis_mesaj,
            "oneri_miktar": oneri_miktar,
            "oneri_mesaj": oneri_mesaj,
            "risk_skor": risk_skor,
            "risk_etiketi": risk_etiketi,
            "olu_stok_durum": olu_durum,
            "olu_stok_mesaj": olu_mesaj,
            "kar_marji": kar_marji,
            "kar_durum": kar_durum,
            "kar_renk": kar_renk,
            "yol_renk": yol_renk,
            "yol_mesaj": yol_mesaj,
            "yol_miktar": yol_miktar,
            "yol_varis": yol_varis,
        })

    return dashboard_satirlar
