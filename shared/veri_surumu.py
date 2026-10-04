# -*- coding: utf-8 -*-
"""Veri sürümü — ağır ekran önbelleklerini VERİ DEĞİŞİNCE tazeleme (Ekim 2026).

SORUN: Tüm Ürünler / Genel bakış / paçal önbellekleri 1-5 dk'da kendiliğinden siliniyordu;
5 dk'dan uzun aradan sonra açılan sayfa veri değişmemiş olsa da her şeyi baştan okuyup
hesaplıyordu. Süreyi uzatmak uygulama DIŞI değişikliği (gece işi, elle düzeltme) geç
gösterirdi.

ÇÖZÜM: veritabanında veri_surumu tablosu (veritabani/11_veri_surumu.sql): izlenen
tablolarda her ekleme/değişiklik/silmede tetikleyici o tablonun sayacını artırır —
değişiklik nereden gelirse gelsin. tazelik_kontrol() her sayfa çiziminde çağrılır;
sayaçları en fazla 15 sn'de bir okur (tek küçük sorgu). Sayaç değiştiyse BAGIMLILAR
listesindeki önbellekler temizlenir. Böylece bu önbellekler uzun tutulabilir (UZUN_TTL):
veri değişmedikçe sayfa anında açılır, değişince en geç 15 sn'de tazelenir.

Uygulama içinden yapılan kayıtlar önbelleği zaten ANINDA temizler (app.py
_akilli_cache_clear); bu modül yalnız ek güvencedir.

Tablo henüz kurulmamışsa (ya da okunamazsa) eski davranış: BAGIMLILAR her
YEDEK_SURE_SN'de bir temizlenir — bugünkü 5 dk sınırıyla aynı.
"""
import time

IZLENEN_TABLOLAR = ("urunler", "firma_stok", "stok_yas", "yoldaki_urunler",
                    "ithalat_dosyalari", "ithalat_kalemleri", "pm_ayarlar")
UZUN_TTL = 3600          # BAGIMLILAR'daki ağır önbelleklerin süresi (bellek sınırı; tazelik sayaçtan)
KONTROL_SN = 15          # sayaç en fazla bu sıklıkla okunur
YEDEK_SURE_SN = 300      # sayaç okunamazsa bu aralıkla temizle (eski 5 dk davranışı)

# İzlenen tablolardan beslenen BÜTÜN önbellekli fonksiyonlar (modül, ad). Zincirdeki ara
# önbellekler de burada olmalı: dış hesap yeniden yapılırken içteki eski kalmasın.
# Kural (tests/test_veri_surumu.py): UZUN_TTL kullanan her fonksiyon bu listede.
BAGIMLILAR = (
    ("kayranpm.database", "urunler_ada_gore"),
    ("kayranpm.database", "urunler_skuya_gore"),
    ("kayranpm.database", "_dashboard_ham"),
    ("kayranpm.database", "get_urun_marka_kategori"),
    ("kayranpm.database", "get_tum_sku_listesi"),
    ("kayranpm.database", "get_urun_detay"),
    ("kayranpm.database", "get_uretim_suresi"),
    ("kayranpm.database", "firma_son_tarihleri"),
    ("kayranpm.database", "get_firma_listesi"),
    ("kayranpm.database", "canli_stok"),
    ("kayranpm.analitik", "tum_urunler_listesi"),
    ("kayranpm.analitik", "dashboard_hesapla"),
    ("kayranpm.analitik", "siparis_onerisi_listesi"),
    ("kayranpm.stok_yasi", "hesapla"),
    ("satis.database", "_urunler_hepsi"),
    ("satis.database", "get_urunler"),
    ("satis.database", "get_sku_kategori"),
    ("satis.database", "get_pacal_map"),
    ("satis.database", "iade_satis_net_ozet"),
    ("ithalat.database", "get_dosyalar"),
    ("ithalat.database", "get_tum_kalemler"),
    ("ithalat.database", "get_kategoriler"),
    ("ithalat.database", "get_sku_kategori_map"),
    ("ithalat.database", "get_urun_katalog"),
    ("ithalat.database", "get_barkod_map"),
    ("ithalat.database", "_parti_satirlari_hesapla"),
    ("ithalat.database", "get_sku_ithalat_partileri"),
    ("ithalat.database", "get_ithalat_yolda_ozet"),
    ("shared.ana_veri", "get_kategori_ad_haritasi"),
    ("shared.ana_veri", "get_urun_ad_haritasi"),
)


def _onbellek(ttl):
    try:
        import streamlit as st
        return st.cache_data(ttl=ttl, show_spinner=False)
    except Exception:  # noqa: BLE001
        return lambda fn: fn


def _surec_durumu():
    """Süreç (sunucu) başına TEK durum: önbellek de süreç başına ortak."""
    try:
        import streamlit as st

        @st.cache_resource(show_spinner=False)
        def _durum():
            return {"surum": None, "temizlik": time.time()}
        return _durum()
    except Exception:  # noqa: BLE001
        return _YEREL


_YEREL = {"surum": None, "temizlik": time.time()}


@_onbellek(KONTROL_SN)
def _surumler():
    """{tablo: sayaç} ya da None (tablo yok / okunamadı). En fazla KONTROL_SN'de bir okunur."""
    try:
        from kayranpm.database import get_client
        rows = get_client().table("veri_surumu").select("tablo, surum").execute().data or []
        return {str(r.get("tablo")): int(r.get("surum") or 0) for r in rows}
    except Exception:  # noqa: BLE001
        return None


def imza(surumler):
    """İzlenen tabloların sayaç imzası (tabloda satırı olmayan tablo 0)."""
    s = surumler or {}
    return tuple(int(s.get(t, 0)) for t in IZLENEN_TABLOLAR)


def bagimlilari_temizle():
    """BAGIMLILAR'ı temizler (yalnız yüklenmiş modüllerde). Döner: temizlenen sayısı."""
    import sys
    n = 0
    for mod_adi, ad in BAGIMLILAR:
        fn = getattr(sys.modules.get(mod_adi), ad, None)
        if fn is not None and hasattr(fn, "clear"):
            try:
                fn.clear()
                n += 1
            except Exception:  # noqa: BLE001
                pass
    return n


def tazelik_kontrol(simdi=None):
    """Her sayfa çiziminde çağrılır. Döner: "degisti" | "ayni" | "ilk" | "yedek" | "bekle".
    Hiçbir koşulda hata fırlatmaz (sayfa çizimi bunun yüzünden durmaz)."""
    try:
        simdi = time.time() if simdi is None else simdi
        d = _surec_durumu()
        s = _surumler()
        if s is None:                                   # tablo yok → eski 5 dk davranışı
            if simdi - d["temizlik"] >= YEDEK_SURE_SN:
                bagimlilari_temizle()
                d["temizlik"] = simdi
                return "yedek"
            return "bekle"
        yeni = imza(s)
        if d["surum"] is None:                          # süreç yeni başladı: önbellek zaten boş
            d["surum"], d["temizlik"] = yeni, simdi
            return "ilk"
        if yeni != d["surum"]:
            bagimlilari_temizle()
            d["surum"], d["temizlik"] = yeni, simdi
            return "degisti"
        return "ayni"
    except Exception:  # noqa: BLE001
        return "bekle"
