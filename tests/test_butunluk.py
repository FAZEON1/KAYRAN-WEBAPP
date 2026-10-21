# -*- coding: utf-8 -*-
"""
BÜTÜNLÜK TESTLERİ — dosya yüklemelerinin sessizce bir şey geri almadığını doğrular.

NEDEN VAR: Dosyalar GitHub'a elle yükleniyor. Bir düzeltme için yüklenen
dosya, aynı dosyaya daha önce yapılmış BAŞKA bir düzeltmeyi taşımıyorsa
onu sessizce siler ve kimse fark etmez. Bir günde beş kez yaşandı:

  · get_yurtici_kategoriler silindi → Maliyet Girişi ImportError verdi
  · Depo garanti listesi geri alındı → "Servis Depo" seçeneği kayboldu
  · Serdar'ın yetkileri silindi → "erişim yetkiniz yok"
  · kategori_kanonik testi, hiç uygulanmamış bir özelliği import ediyordu
  · Toplam Aktifler listesi iki yerde tekrarlanıyordu, biri güncellenmedi

Bu dosya her push'ta CI'da koşar ve bunların hepsini SANİYELER içinde
yakalar. Yeni bir düzeltme yaptığında buraya bir satır ekle: "bu
fonksiyon var olmalı", "bu kullanıcı bu listede olmalı" gibi.
"""
import ast
import os
import re
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent

# Ölü kopyalar — bunlar CANLI değildir, taranmaz.
OLU_DESENLER = ("(", "/shared/shared", "/shared/kayran", "/shared/satis",
                "/shared/depo", "/shared/ithalat", "/shared/teknik",
                "/kayranpm/kayranpm", "/satis/satis", "_tek.py", "/.git",
                "/tests/", "/bekleyen/")
KOK_KOPYALAR = {"main.py", "kayranpm/app.py"}      # kökteki eski sürümler


def _canli_py_dosyalar():
    for k, _, fs in os.walk(KOK):
        for f in fs:
            p = os.path.join(k, f)
            rel = os.path.relpath(p, KOK).replace(os.sep, "/")
            if (f.endswith(".py") and not any(x in ("/" + rel) for x in OLU_DESENLER)
                    and rel not in KOK_KOPYALAR):
                yield rel, p


def _ust_duzey_isimler(dosya):
    """Bir modülün üst düzey fonksiyon / sınıf / değişken adları."""
    try:
        t = ast.parse(open(dosya, encoding="utf-8").read())
    except SyntaxError:
        return set()
    adlar = set()
    for n in t.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            adlar.add(n.name)
        elif isinstance(n, ast.Assign):
            for tg in n.targets:
                if isinstance(tg, ast.Name):
                    adlar.add(tg.id)
    return adlar


# ═══════════════════════════════════════════════════════════════════════
# 1) KIRIK İMPORT TARAMASI
#    "from X import Y" yazan her yer için Y gerçekten X'te tanımlı mı?
#    Sessiz fonksiyon kayıplarını yakalar.
# ═══════════════════════════════════════════════════════════════════════
_TARANAN_MODULLER = {}
for _mod in ("kayranpm", "kayranacc", "satis", "depo", "ithalat", "teknikservis", "shared", "hesap_makinesi"):
    for _d in ("database.py", "utils.py", "auth.py", "tasarim.py", "irsaliye.py",
               "stok.py", "arama.py", "audit.py", "dogrula.py", "kar_gizle.py",
               "sirket.py", "tarih.py", "telegram_gonder.py", "marj_uyari.py", "yetki.py", "stok_defteri.py", "hata_log.py", "kayit.py", "oturum.py",
               "stok_karti.py", "ref_no.py", "bildirim.py", "belge.py", "excel_islemler.py",
               "musteri_hesap.py", "ana_veri.py", "pacal_hesap.py", "veri_surumu.py", "yukleme_gecmisi.py", "izgara.py", "duzenle.py", "veri_sagligi.py",
               "stok_yasi.py", "stok_yasi_ekran.py", "satilamayan.py", "ts_mutabakat.py", "stok_karti_palet.py", "palet.py", "yurtici_hesap.py", "yurtici_ekran.py", "islem.py", "modul_tazele.py",
               "claude_talep.py", "ariza_orani.py", "ariza_ekran.py", "ceviri.py", "ipucu.py",
               "soru.py", "soru_cevap.py", "soru_ekran.py", "paralel.py", "urun_karnesi.py", "gezinme.py",
               "dosya_tani.py", "dosya_kapisi.py", "aktif_excel.py", "dataframe_yamasi.py", "kampanya_ref.py", "stok_tamamla.py", "bt_hesap.py",
               "bt_olcum.py", "bt_ekran.py", "mikro_esitle.py", "mikro_esitle_ekran.py", "mikro_muhasebe.py", "mikro_muhasebe_ekran.py", "mikro_gider.py", "mikro_gider_ekran.py", "mikro_odeme.py", "mikro_odeme_ekran.py", "mikro_stok.py", "mikro_stok_ekran.py", "mikro_stok_degeri.py", "mikro_stok_degeri_ekran.py", "mikro_depo.py", "mikro_depo_ekran.py", "mikro_sevk.py", "mikro_urun.py", "mikro_urun_ekran.py", "mikro_multikod.py", "sirket_belge_hesap.py", "sirket_belge.py", "sirket_belge_ekran.py",
               "asistan_hesap.py", "asistan.py", "asistan_ekran.py", "ofis.py", "ofis_ekran.py",
               "bugun.py", "masa.py", "masa_liste.py", "form.py", "ikon.py", "kisayol.py", "pwa.py", "gumruk_ekran.py", "kar_gizle.py", "claude_talep.py",
               "tatil.py", "izin_hesap.py", "izin.py", "izin_ekran.py", "izin_belge.py", "ts_hesap.py", "iade_belge.py", "urun_notlari.py", "iade_fatura.py", "canli_pacal.py", "odeme_hesap.py", "odeme_masasi.py", "satis_masasi.py", "ts_masasi.py", "ithalat_masasi.py", "depo_masasi.py", "bekleyen_ekran.py", "urun_masasi.py", "kampanya_masasi.py", "siparis_masasi.py", "ref_masasi.py", "yurtici_masasi.py", "stok_yasi_masasi.py", "masa_ortak.py", "urunler_ekran.py", "muhasebe_masalari.py", "cek_ekran.py", "banka_ekran.py", "sol_menu.py", "stok_karti_yeni.py", "hm_hesap.py", "bilesen.py",
               "mikro_serino.py",      # seri no → Mikro (teknik servis, Eki 2026)
               "yedek_tablolari.py",   # gece yedeği tablo listesi + sayfalı okuma (Eki 2026)
               "sirket_ayar.py", "kur.py",
               "stok_hesap.py", "musteri_ekran.py",   # kanal stoğu kod eşleşmesi karşılaştırması (Eki 2026)
               "main.py"):
        _p = KOK / _mod / _d
        if _p.exists():
            _TARANAN_MODULLER[f"{_mod}.{_d[:-3]}"] = _ust_duzey_isimler(_p)
for _d in ("yonetim_hesap.py", "yonetim_pano.py", "yonetim_para.py"):   # kökteki modüller
    _TARANAN_MODULLER[_d[:-3]] = _ust_duzey_isimler(KOK / _d)
_TARANAN_MODULLER["shared.surum"] = _ust_duzey_isimler(KOK / "shared" / "surum.py")   # sürüm tek kaynak
_TARANAN_MODULLER["veritabani.uygula"] = _ust_duzey_isimler(KOK / "veritabani" / "uygula.py")   # kayıtlı migration


def _kirik_importlar():
    kirik = []
    for rel, p in _canli_py_dosyalar():
        try:
            t = ast.parse(open(p, encoding="utf-8").read())
        except SyntaxError as e:
            kirik.append((rel, 0, "SÖZDİZİMİ HATASI", str(e)[:60]))
            continue
        paket = rel.split("/")[0] if "/" in rel else ""
        for n in ast.walk(t):
            if not isinstance(n, ast.ImportFrom) or not n.module:
                continue
            m = f"{paket}.{n.module}" if (n.level and paket) else n.module
            if m not in _TARANAN_MODULLER:
                continue
            for a in n.names:
                if a.name != "*" and a.name not in _TARANAN_MODULLER[m]:
                    kirik.append((rel, n.lineno, m, a.name))
    return kirik


# Bilinen ölü dosya — hiçbir yerden import edilmiyor, kırık importu zararsız.
_BILINEN_OLU = {("kayranpm/bildirim.py", "kayranpm.database", "get_connection")}


def test_kirik_import_yok():
    kirik = [(r, ln, m, ad) for r, ln, m, ad in _kirik_importlar()
             if (r, m, ad) not in _BILINEN_OLU]
    assert not kirik, (
        "KIRIK İMPORT — bir dosya artık var olmayan bir şeyi import ediyor. "
        "Muhtemelen eski bir sürüm yüklendi ve fonksiyon silindi:\n  "
        + "\n  ".join(f"{r}:{ln} → {m}.{ad}" for r, ln, m, ad in kirik))


# ═══════════════════════════════════════════════════════════════════════
# 2) KRİTİK FONKSİYONLAR — bugüne kadar en az bir kez KAYBOLMUŞ olanlar
#    Yeni bir düzeltme eklediğinde buraya da ekle.
# ═══════════════════════════════════════════════════════════════════════
KRITIK_FONKSIYONLAR = {
    "veritabani.uygula": ["dosyalari_bul", "dosya_sha", "oneri_mi", "plan_yap", "canli_mi",
                          "gecmisi_oku", "uygula", "main"],   # kayıtlı şema değişikliği (Eki 2026)
    "kayranpm.database": ["_kampanya_cache_temizle",
        "get_yurtici_kategoriler", "set_yurtici_kategoriler",   # 04.08'de silinmişti
        "get_satis_depolari", "depo_kanonik", "stok_hareket_coklu",
        "get_talepler", "get_talepler_kullanici", "acik_talep_sayisi", "ekle_talep",
        "depo_dagilimi", "satilabilir_kontrol",   # G5F kırılım rozetleri + satılabilir farkı (Eki 2026)
        "kategori_oner", "marka_oner",            # Müşteri Satışları kategori/marka tahmini buna dayanır
        "get_sku_eslesme", "sku_eslesme_kaydet", "sku_eslesme_sil",   # onaylı SKU eşleme (Eki 2026)
        "firma_stok_satirlari",                   # stok kartı kanal stoğu, SKU yazımından bağımsız
        "kanal_kod_haritasi", "kanal_kod_satirlari",   # kanal stoğunda pazaryeri kodları karta (Eki 2026)
        "sku_satirlari", "kart_sku_haritasi", "kart_sku_coz",   # SKU yazımı: okuma + yazma (Eki 2026)
        "urunler_ada_gore", "urunler_skuya_gore",   # tek urunler okuması (Eki 2026)
        # atomik stok (veritabani/29_atomik_stok.sql, Eki 2026): RPC önce, yoksa bugünkü yol
        "atomik_rpc", "atomik_hazir", "atomik_ortam", "atomik_audit", "AtomikHata", "stok_kalemleri",
        "stok_adaylari", "stok_aday_haritasi", "stok_atomik_sonuc", "stok_hareket_gruplu",
        "_stok_atomik", "_stok_hareket_coklu_eski", "_rpc_yok_mu", "depo_sevk", "_sevk_kart_bul",
        # G5F aktarımı tek işlem (veritabani/34_g5f_aktarim_tek_islem.sql, Eki 2026)
        "g5f_aktarim_atomik", "g5f_yeni_kart", "upsert_g5f_stok",
        "stok_yas_ilk_gorulen",                   # ilk görülme tarihi korunur (veritabani/35, Eki 2026)
    ],
    "ithalat.pacal_hesap": ["eski_tum_urunler", "eski_stok_karti", "eski_pnl", "yeni_pacal",
                            "karsilastir"],                       # Faz 2a karşılaştırma (Eki 2026)
    "ithalat.database": ["get_parti_satirlari", "get_sku_maliyet_ozet", "get_sku_alim_detay",
                         "_kategori_doldur", "_parti_satirlari_hesapla",   # paçal önbelleği (Eki 2026)
                         "teslim_stok_bekleyenler", "teslim_stok_kayitsiz", "_teslim_ayir",
                         "_islendi_yaz",   # stok işlenme kaydı (Eki 2026)
                         "alim_turu", "ithalat_mi", "yurtici_sil", "ALIM_TURLERI"],   # yurt içi alış (Eki 2026)
    "shared.ana_veri": ["kategori_anahtar", "kategori_ad", "kategori_secenekleri", "kayit_degeri",
                        "tr_buyuk_harf", "marka_anahtar", "marka_ad", "get_kategori_havuzu",
                        "urun_ad", "get_urun_ad_haritasi", "kategori_ad_haritasi_ek", "kategori_secenekleri_ek"],   # tek kaynak (Eki 2026)
    "shared.veri_surumu": ["tazelik_kontrol", "bagimlilari_temizle", "imza", "satis_imza"],   # önbellek tazeliği (Eki 2026)
    "shared.veri_sagligi": ["sayfa", "gorunur_kontroller", "maliyetsiz_satislar", "satilabilir_farklari", "eslesmeyen_rapor_kodlari",
                           "teslim_notu"],   # veri sağlığı sayfası (Eki 2026)
    "shared.duzenle": ["duzenle", "duzenle_veri", "uygula", "gecerli_durum", "destekli_mi"],   # sade düzenlenebilir tablo (Eki 2026)
    "shared.izgara": ["izgara_ayar", "izgara_sonuc", "dataframe_hazirla", "kur"],   # ortak ızgara görünümü (Eki 2026)
    "shared.yukleme_gecmisi": ["Kayit", "kaydet", "aktif", "geri_alma_engeli", "kontrol_farki", "stok_net", "stok_etkisi", "geri_al", "sayfa"],   # yükleme geçmişi (Eki 2026)
    "kayranpm.stok_yasi": ["fifo_kalan", "yas_ozeti", "bizim_partiler", "musteri_partileri", "firma_cozucu",
                           "urun_yasi", "toplam_ozet", "hesapla", "_bizim_partiler_oku", "_alim_partileri_oku", "bizim_stoklari",
                           "urun_satirlari", "parti_satirlari", "musteri_satirlari", "excel_bytes",
                           "ayar_birlestir", "ayar_oku", "haric_mi", "kategori_sorumlulari", "yasli_satirlar",
                           "kisi_listeleri", "mail_html", "musteri_kategorileri", "musteri_kategori_suz"],   # stok yaşı FIFO (Eki 2026)
    "kayranpm.stok_yasi_ekran": ["goster", "kart_bolumu"],
    "kayranpm.yurtici_hesap": ["maliyet_hesapla", "dogrula", "kayit_argumanlari", "formdan", "belge_no", "usd"],
    "kayranpm.yurtici_ekran": ["goster"],
    "shared.islem": ["kur", "bekle"],
    "shared.modul_tazele": ["tazelenmeli", "proje_modullerini_sil", "degisen_moduller", "bayatlari_tazele", "yuklenenleri_kaydet"],                                                         # işlem göstergesi (Eki 2026)                                                    # yurt içi alış (Eki 2026)
    "kayranpm.musteri_hesap": ["meta_hazirla", "addan_kod", "kategori_etiketi", "marka_etiketi", "eslesme_dogrula",
                               "kategori_musteri", "harita_ile_tamamla"],   # rapor SKU'su ↔ stok kartı (Eki 2026)
    "kayranpm.stok_hesap": ["kanal_stoklari", "kanal_son_tarihleri", "stok_ozeti",
                            "kanal_kod_karsilastir", "kod_haritasi"],   # kanal stoğu kod eşleşmesi, salt okunur (Eki 2026)
    "kayranpm.musteri_ekran": ["render", "_kanal_karsilastirma"],
    "kayranacc.database": [
        "get_kur",                                # hiç yoktu, ref_no sessizce None alıyordu
        "_ayarlar_hepsi", "_tum_kurlar",          # tek istekte ayarlar / kurlar (hızlandırma)
        "aktif_manuel_guncelle",                  # manuel kalem revizyonu
        "virman_yap",
        "tahsilat_guncelle", "tahsilat_bakiye_farki",   # para girişi düzenleme (Ekim 2026)
        "hafta_olustur",                          # yeni hafta + ödemeler + aktif (Mikro önerisi, Ekim 2026)
    ],
    "satis.database": ["pacal_bul", "satis_sku_listesi",
        "satis_anahtar", "_magaza_ayikla",        # mağazalı mükerrer anahtarı
        "_tum_satislar_yalin", "_satislar_yalin_aralik", "_tum_iadeler", "_iadeler_aralik",  # ortak okuma
        "kanal_kok", "kanal_bolunmeleri",         # kanal adı tekilleştirme
        "ice_aktar_satislar", "ekle_siparis",
        # atomik kayıt + stok (veritabani/29_atomik_stok.sql, Eki 2026)
        "_atomik_kayit", "_atomik_iz", "_depo_gruplari", "_stok_sorunu_bildir", "_iadeler_atomik",
        "_iade_aktarim_satirlari", "guncelle_satis", "sil_satis", "sil_siparis", "sil_siparisler",
        "sil_iade", "ice_aktar_iadeler",
        # Excel satış yüklemesi tek işlem (Eki 2026)
        "_ice_aktar_atomik", "_excel_stok_plani", "_akilli_plan", "_akilli_depo_kurallari",
        "_KirilimOkuyucu", "_stok_akilli_dus", "_sil_hatasi",
    ],
    "teknikservis.database": [
        "kullanilmis_irsaliye_nolari", "irsaliye_no_ayir", "irsaliye_isle", "fatura_kayitlari",
        "ts_urun_gruplari", "ts_grup_haritasi", "ts_grup_ad", "form_durumu", "servis_formu_pdf",
    ],
    "shared.telegram_gonder": ["gonder", "aktif_mi"],
    "shared.marj_uyari": ["marj_uyarisi", "sorunlu_kalemler", "mail_uret", "mail_alicilari"],
    "shared.sirket_ayar": ["rol_sahipleri", "rol_var_mi", "yonetici_kullanici", "talep_onaycisi",
                           "yukleme_sorumlusu", "kimlik", "talep_eposta", "yedek_liste", "temizle"],
    "teknikservis.ariza_orani": ["tahmin", "sonuc", "sonuc_zorunlu", "servis_ozeti", "satis_toplami",
                                 "musteri_stogu", "alim_toplami", "oran", "satirlar", "grup_ozeti"],
    "teknikservis.ariza_ekran": ["goster"],
    "shared.tarih": ["hizli_tarih_araligi", "donem_coz", "donem_etiketi", "kisa_aralik"],
    "satis.stok_tamamla": ["eksikler", "dagit", "uygula"],
    "satis.mikro_esitle": ["fatura_no", "usd_tutar", "kur_haritasi", "satir_turu", "mikro_kayitlari", "plan_yap", "aylik_ozet",
                           "veri_oku", "plan_hazirla", "uygula", "otomatik", "durum", "acik_mi", "ac", "aktarici_yayinla", "aktarici_ozeti", "aktarici_yayinda_mi", "kopyasiz", "aktarim_suruyor_mu", "aktarim_suruyor", "otomatik_guvenli_mi", "acik_mi",
                           "siparis_kayitlari", "siparis_oku"],
    "satis.mikro_esitle_ekran": ["ilk_onay_kutusu"],
    "kayranacc.mikro_muhasebe": ["hareket_tutari", "bakiyeler", "banka_bakiyeleri", "cari_bakiyeleri", "cari_ozeti",
                                 "ithalat_odenen", "banka_eslestir", "cek_satirlari", "cek_imzasi", "cek_ozeti",
                                 "plan_yap", "veri_oku", "plan_hazirla", "uygula", "durum", "acik_mi", "ac",
                                 "son_aktarim", "otomatik"],
    "kayranacc.mikro_muhasebe_ekran": ["ilk_onay_kutusu"],
    "kayranacc.mikro_gider": ["gider_hesabi_mi", "kalem_bul", "gider_tablosu", "ay_siniri", "esit_mi", "karsilastir",
                              "yillar", "plan_hazirla", "uygula", "durum", "acik_mi", "ac", "son_aktarim", "otomatik",
                              "kapanis_mi", "kapanis_kalmis_mi", "muhasebe_satirlari"],
    "kayranacc.mikro_gider_ekran": ["ilk_onay_kutusu"],
    "kayranacc.mikro_odeme": ["vade_bul", "hafta_araligi", "hafta_adi", "kategori_bul", "plan_gunleri",
                              "taksit_haritasi", "acik_kalemler", "oneri_satirlari", "ozet", "odemeye_cevir",
                              "firma_kelimeleri", "ayni_firma", "karsilastir", "veri_oku", "oneri_hazirla"],
    "kayranacc.mikro_odeme_ekran": ["oneri_penceresi"],   # Bu Hafta › Mikro'dan öneri (Eki 2026)
    "kayranpm.mikro_stok": ["kirilim_yap", "farklar", "depo_ozeti", "plan_hazirla", "uygula", "durum", "acik_mi",
                            "ac", "son_aktarim", "otomatik"],
    "kayranpm.mikro_stok_ekran": ["ilk_onay_kutusu"],
    "kayranacc.mikro_stok_degeri": ["depo_degerleri", "kanal_degerleri", "kayit_yap", "esit_mi",
                                    "kanal_karsilastir", "plan_yap", "veri_oku", "plan_hazirla", "uygula",
                                    "durum", "acik_mi", "ac", "son_aktarim", "otomatik"],
    "kayranacc.mikro_stok_degeri_ekran": ["ilk_onay_kutusu"],
    "kayranpm.mikro_depo": ["hareket_turu", "hareketler", "depo_partileri", "havuz_partileri", "depo_yaslari",
                            "depo_ozet_satirlari", "depo_parti_satirlari", "toplam", "excel_karsilastir",
                            "yas_karsilastir", "veri_oku", "hesapla", "havuz_partileri_oku", "depo_partileri_oku",
                            "plan_hazirla", "durum", "acik_mi", "ac", "uygula", "son_aktarim"],
    "kayranpm.mikro_depo_ekran": ["ilk_onay_kutusu", "hl_sayfasi"],
    "teknikservis.mikro_serino": ["seri_anahtar", "tarih", "kayit_sec", "belge_no", "garanti", "bilgi", "gruplandir",
                                  "firma_esle", "firma_uyumlu_mu", "stok_uyumlu_mu", "satir_tamamla", "bilgi_metni",
                                  "oku", "unvanlari_oku", "bul"],
    "kayranpm.mikro_urun": ["mikro_kategori", "kategori_yazimi", "marka_yazimi", "barkod_haritasi", "mikro_kartlari",
                            "fazeon_kodlari", "kart_plani", "liste_musterisi", "liste_eslesmesi", "fiyat_plani",
                            "birlesik_liste", "kart_cipleri_hazirla", "veri_oku", "hesapla", "plan_hazirla", "uygula",
                            "durum", "acik_mi", "ac", "son_aktarim", "otomatik", "kart_cipleri"],
    "kayranpm.mikro_urun_ekran": ["ilk_onay_kutusu"],
    "kayranpm.mikro_multikod": ["firma_anahtar", "cari_firma", "harita_kur", "belirsizler", "uygula", "oku",
                                "yukleme_haritasi", "firma_esle"],   # Mikro müşteri kodu → SKU (Eki 2026)
    "shared.bt_hesap": ["sure_ozeti", "karsilastir", "hata_ozeti", "kapi_karari", "gunluk_seri",
                        "iyilestirme_satiri", "karne"],
    "shared.bt_olcum": ["kaydet", "alt_sayfa", "son_olcumler", "raporlar"],
    "shared.bt_ekran": ["sayfa"],
    "shared.sirket_belge_hesap": ["belge_kabul", "depo_yolu", "sure_durumu", "gruplandir", "uyarilar",
                                  "zip_icerik", "kunye_birlestir", "edefter_kunye", "kunye_metni"],
    "shared.sirket_belge": ["listele", "yukle", "guncelle", "sil", "link", "indir", "kunye_oku", "kunye_yaz"],
    "shared.sirket_belge_ekran": ["sayfa"],
    "shared.sirket": ["sirket_bilgi"],
    "shared.asistan_hesap": ["kimlik_kullanici", "komut", "telegram_yanit", "yardim_metni", "sonuc_dogrula",
                             "vergi_hesabi", "pazar_ozeti", "brifing_blogu"],
    "shared.asistan": ["telegram_haritasi", "telegram_haritasi_yaz", "raporlar", "gumruk_sorgulari", "gumruk_ekle",
                       "gumruk_tetikle", "gumruk_yeniden", "sql_kurulu"],
    "shared.asistan_ekran": ["telegram_bolumu", "pazar_bolumu"],
    "shared.ofis": ["durumlar"],
    "shared.bugun": ["maddeler_teknik_servis", "maddeler_ithalat", "maddeler_depo_sevk", "maddeler_izin", "topla"],
    # Çalışan izinleri (Ekim 2026)
    "shared.tatil": ["yil_tatilleri", "bilinen_yil", "tatil", "ilk_gunler"],
    "shared.izin_hesap": ["gun_degeri", "gun_dokumu", "izin_gunu", "takvim_gunu", "yillik_hak", "hak_edisler",
                          "sonraki_hak", "bakiye", "cakisanlar", "denetle", "ayni_bolumdekiler", "takvim",
                          "donem_dokumu", "bakiye_tablosu", "talep_ozeti", "mail_yeni", "mail_karar",
                          "bilgi_adresi", "bilgi_gerekli", "bilgi_durumu", "mail_bilgilendirme"],
    "shared.izin": ["personeller", "talepler", "personel_kaydet", "talep_ekle", "karar_ver", "iptal_et", "ayar",
                    "ayar_yaz", "bildir", "bilgi_isaretle"],
    "shared.izin_ekran": ["sayfa", "takvim_html", "personel_denetle"],
    "shared.izin_belge": ["form_icerik", "kayit_belgesi_icerik", "izin_formu_pdf", "kayit_belgesi_pdf", "donus_gunu",
                          "belge_no"],
    "shared.kisayol": ["sec", "oku"],
    "shared.pwa": ["kurulum_betigi"],
    "shared.ofis_ekran": ["run"],
    "shared.gumruk_ekran": ["sayfa"],
    "shared.kar_gizle": ["kar_gorunur", "kar_gorunur_kullanici"],
    "teknikservis.stok": ["satis_kaydi_yaz", "ts_satisi_mi", "toplu_siparis_no", "mal_kabul_girisi",
                          "giris_depo_coz", "giris_deposu", "iade_kaydi_yaz", "tutar_coz",
                          "iade_usd", "kur_bul", "iade_fiyat_metni", "iade_fiyat_guncelle",
                          "dogrudan_giris_mi", "giris_sekli", "degisim_cari", "degisim_depodan_ver"],
    "teknikservis.ts_hesap": ["depolar_kayitlari", "konum", "depo_gruplari", "satis_disi_neden", "merkezde_mi",
                              "gorunen_durum"],
    "teknikservis.urun_notlari": ["not_satiri", "notlari_sirala", "notlari_oku", "not_ekle", "not_sil", "sayfa"],
    "teknikservis.iade_belge": ["iade_belgesi_uygun", "iade_onay_tarihi", "belge_metni", "iade_belgesi_pdf"],
    "kayranacc.odeme_hesap": ["hafta_secenekleri", "hafta_etiketi"],   # hafta adı (görünüm cilası)
    "kayranacc.odeme_masasi": ["masa_verisi", "istek_coz", "islem_uygula", "motor_istegi", "yurutucu"],
    "shared.masa": ["masa", "istek_al", "kosul_uyar", "calistir", "onceki_durum", "sutun_duzeni"],   # ortak liste masası (Eki 2026)
    "shared.masa_liste": ["kolon", "bicim", "veri", "excel_bayt", "ciz"],   # salt-okur liste masası (Eki 2026)
    "shared.form": ["tr_sayi_oku", "tr_sayi_yaz", "sayi_kutusu", "ozet_paneli", "css"],   # giriş formları (Eki 2026)
    "shared.ikon": ["bas_emoji", "ic_temizle", "metin", "mesaj", "toast", "kur"],   # merkezi emoji → ikon (Eki 2026)
    "satis.satis_masasi": ["siparis_masa_verisi", "siparis_ozeti", "siparis_satirlari", "kalem_masa_verisi",
                           "iade_masa_verisi", "siparis_yurutucu", "iade_yurutucu", "siparis_anahtari",
                           "usd_tam", "usd_kisa", "usd_birim"],
    "teknikservis.ts_masasi": ["kayit_masa_verisi", "kayit_yurutucu", "depo_masa_verisi", "depo_yurutucu",
                               "depo_ozeti", "durum_uyar", "ara_uyar", "fatura_var", "toplu_etiket",
                               "transfer_anahtari", "transfer_gunu", "donem_baslangic", "tek_arama", "ara_kat",
                               "ara_uyar"],
    "teknikservis.main": ["_mikro_seri_bilgileri", "_mikro_urun_adi", "_mk_mikro_doldur", "_mk_mikro_paneli",
                          "_mk_mikro_sonrasi", "_liste_masa", "_depolar_masa", "_toplu_satis_formu", "_dlg_toplu_satis", "_ozet_kirilim",
                          "_iade_belgesi_dugmesi", "_tek_arama", "_tek_arama_ac", "_diger_firma", "_dp_ad"],
    "ithalat.ithalat_masasi": ["masa_verisi", "islem_uygula", "yurutucu", "masraf_masa_verisi", "varis_metni"],
    "depo.depo_masasi": ["stok_masa_verisi", "bekleyen_masa_verisi", "bekleyen_uygula"],
    "depo.bekleyen_ekran": ["sevk_dus_kaydet", "takip_sil", "render"],
    "depo.mikro_sevk": ["kayit_serbest", "sevk_satirlari", "eski_uygulama_kayitlari", "ozet", "sevk_oku",
                        "sevk_gecmisi", "ekran"],   # depolar arası sevk Mikro'dan (Eki 2026)
    "depo.satilamayan": ["partiler", "satirlar", "depo_ozeti", "hesapla", "render", "_mutabakat_bolumu", "_mikro_partileri"],   # satılamayan stok (Eki 2026)
    "depo.ts_mutabakat": ["acik_kayitlar", "karsilastir", "depo_ozeti", "uzun_bekleyenler", "ts_partileri",
                          "konum", "acik_oku"],   # servis kaydı ↔ depo stoğu (Eki 2026)
    "kayranpm.urun_masasi": ["masa_verisi", "ozet_kartlari", "sirali_satirlar", "aktarilacak", "yurutucu"],
    "kayranpm.kampanya_masasi": ["masa_verisi", "ozet_kartlari", "yurutucu"],
    "kayranpm.siparis_masasi": ["oneri_verisi", "kayit_verisi", "oneri_yurutucu", "kayit_yurutucu"],
    "kayranpm.ref_masasi": ["ref_ozet", "ref_verisi", "ref_yurutucu", "alinan_verisi", "alinan_yurutucu"],
    "kayranpm.yurtici_masasi": ["tablo_satirlari", "masa_verisi", "yurutucu"],
    "kayranpm.stok_yasi_masasi": ["masa_verisi", "yurutucu"],
    "kayranpm.masa_ortak": ["kisa", "usd", "csv_bayt", "ac_islemi"],
    "kayranpm.urunler_ekran": ["masa_liste", "masa_yan_yana"],
    "kayranacc.muhasebe_masalari": ["ertelenen_verisi", "ertelenen_yurutucu", "odenenler_verisi", "odenenler_yurutucu",
                                    "haftalar_verisi", "haftalar_yurutucu", "cek_arsivi_verisi", "cek_arsivi_yurutucu",
                                    "gelenler_verisi", "gelenler_yurutucu", "kimden_ne_kadar", "firma_cekleri_verisi",
                                    "salt_okunur_yurutucu", "banka_verisi", "banka_yurutucu"],
    "kayranacc.banka_ekran": ["banka_ozet_kalemleri", "banka_listesi"],
    "kayranacc.cek_ekran": ["render_firma_cekleri"],
    "shared.sol_menu": ["menu_yapisi", "secili_sayfa", "css", "ciz", "konum_adi"],   # sol menü (Eki 2026)
    "kayranpm.stok_karti_yeni": ["ciz", "haftalik_seri", "son_hareketler", "durum_uyarilari", "stok_yerleri",
                                 "satis_masa_verisi"],                              # stok kartı yeni tasarım
    "hesap_makinesi.hm_hesap": ["karlilik", "kirilma", "gokhan_prim", "donem_var_mi", "not_ekle", "notlari_ayir"],
    "hesap_makinesi.main": ["run", "prim_not_guncelle"],
    "kayranpm.canli_pacal": ["hesapla", "eldeki_stoklar", "teslim_partileri", "harita_hesapla", "harita",
                             "bul", "aciklama"],
    "teknikservis.iade_fatura": ["firma_koku", "son_fiyat_haritasi", "fiyat_onerisi", "para_cevir", "kalem_ekle",
                                 "sepet_toplam", "fatura_daha_once", "birim_kayitlari"],
    "yonetim_pano": ["donem_araligi", "kiyas_donemleri", "devam_ediyor", "trend_aylari", "degisim",
                     "kanal_satirlari", "urun_satirlari", "destek_satirlari", "gider_satirlari",
                     "ay_kurlari", "gider_usd_satirlari", "serit_hedefi",
                     "pnl_satirlari", "kucuk_trend_svg", "ay_etiketi"],
    "shared.surum": ["SURUM", "surum_etiketi"],          # sürüm tek kaynak (ürün paketi, Eki 2026)
    "shared.ceviri": ["kur"],
    "shared.ipucu": ["kur"],
    "shared.soru": ["coz", "parcalar", "donem_bul", "sade", "firma_bul", "sku_bul"],
    "shared.soru_cevap": ["cevapla", "sozluk_kur", "Veri"],
    "shared.soru_ekran": ["sayfa", "sor", "anlasilir_mi"],
    "shared.paralel": ["basla", "hepsi"],
    "shared.gezinme": ["serit_kur", "serit_kabi", "sayfa_menusu", "secenekler", "sayfa_grubu",
                       "aktif_sekme_yaz"],   # başlık sekme adıyla (görünüm cilası, Eki 2026)   # şerit sağında modül aracı (Eki 2026)
    "shared.tasarim": ["baslik", "sayfa_baslik", "pencere", "pencere_grid", "pencere_css", "pencere_bos",
                       "genel_tema_css", "detay_karti", "mesaj",   # shared/ui.py buraya katıldı (Eki 2026)
                       "kayran_logo_svg", "kayran_logo_uri",   # logo tek kaynak (Eki 2026)
                       "kart_hucresi", "kart_degeri_kisa"],    # kartta kuruşsuz tutar (görünüm cilası)
    "shared.bilesen": ["baslik_eylem", "baslik_yuvasi_kur", "baslik_yuvasi_ac", "baslik_yaz"],   # başlık yuvası
    "yonetim_para": ["usd", "harita", "ozet_cumlesi", "veri_topla", "sayfa"],
    # Dosya kapısı (Ekim 2026): bütün Excel yüklemeleri tek pencerede
    "shared.dosya_tani": ["tani", "sayfalari_oku", "norm"],
    "satis.main": ["iade_excel_oku", "iade_fatura_satirlari", "iade_fatura_ozetle", "kapi_iade",
                   # sayfa gövdeleri run()'dan ayrı fonksiyonlara taşındı (Ekim 2026, mimari)
                   "run", "_sayfa_satis_girisi", "_sayfa_satislar", "_sayfa_kar_pnl", "_sayfa_iade"],
    "kayranacc.main": ["run", "_sayfa_dashboard", "_sayfa_bu_hafta", "_sayfa_banka_bakiyeleri", "_sayfa_nakit_akis",
                       "_sayfa_firma_cekleri", "_sayfa_odenenler_gecmis", "_sayfa_gelenler_gecmisi",
                       "_sayfa_e_defter", "_sayfa_raporlar_bildirim", "_sayfa_ertelenen_odemeler",
                       "_sayfa_cari_ekstre", "_sayfa_toplam_aktifler"],
    "kayranpm.main": ["run", "_sayfa_dashboard", "_sayfa_tum_urunler", "_sayfa_stok_yasi", "_sayfa_yurt_ici_alis",
                      "_sayfa_musteri_satislari", "_sayfa_kampanya_takip", "_sayfa_siparis_onerisi",
                      "_sayfa_ref_no_takibi", "_sayfa_toplu_islemler"],
    "shared.dataframe_yamasi": ["kur", "asil_fonksiyon", "html_uygun_mu"],
    "yonetim_hesap": ["gider_yili_bul"],
    "kayranpm.ref_no": ["alinan_destek_kolonlari", "alinan_destek_excel_ice_aktar", "ref_ekle", "ref_ekle_no",
                        "ref_firma_kodu"],
    "kayranpm.kampanya_ref": ["ref_firmasi_sec", "ref_plani", "mevcut_refler", "elle_benzerler", "onizleme",
                              "kapaninca_ref_ac", "ekran_mesaji", "mail_icerigi", "mail_alicilari"],
    "shared.dosya_kapisi": ["ac", "acik", "kapat", "ciz", "izinli", "izinli_turler", "gorunur",
                            "yetkiler_topla", "dosyalari_ekle", "ana_sayfa_alani"],
    "kayranacc.aktif_excel": ["parse_stok_excel", "aktif_kaydet"],
    "kayranacc.excel_islemler": ["ayni_hafta", "cek_degisim_ozeti"],
    "kayranpm.excel_islemler": ["excel_yukle_g5f_depolar", "_g5f_tek_islem", "_g5f_mesaj", "_kart_skulari"],   # G5F tek işlem
    "kayranpm.stok_karti": ["ac", "ac_ve_ciz", "kapat", "acik_sku", "acik_karti_ciz", "goster",
                            "baska_sku_secici", "_gec_sec"],   # tek kaynaktan açılan stok kartı (Eki 2026)
    "kayranpm.stok_karti_palet": ["ozet_satirlari", "palet_urunleri"],
    "shared.palet": ["palet", "git"],
    "kayranpm.urun_karnesi": ["puan", "karne", "oneri", "olculer", "portfoy_hesapla", "baglam", "portfoy",
                              "kart_html", "ciz"],
    "shared.claude_talep": ["onaylayabilir_mi", "gonderilebilir_mi", "etiket", "onaya_gonder",
                            "rutin_ayari", "rutin_ayari_coz", "rutini_tetikle",
                            "baslik_talep_id", "pr_guncellemesi", "pr_mailleri"],
    "shared.yetki": ["yetki_tablosu", "moduller", "ozel_yetki", "ozel_sahipleri",
                     "salt_okur", "kullanici_kaydi", "kaydet"],
    "shared.stok_defteri": ["yaz", "yaz_fark", "toplu", "gecmis", "kaynak_bul", "yukleme", "aktif_yukleme"],
    "shared.hata_log": ["kaydet", "son_hatalar"],
    "shared.kur": ["eur_usd", "usd_try", "banka_karsiligi"],   # kur tek kaynak (Eki 2026)
    "shared.kayit": ["sessiz", "yapilandir", "baslat", "sentry_baslat"],   # yutulan hatalar loga (Eki 2026)
    "shared.oturum": ["oturum_store", "oturum_kapat", "cikis_yap",
                      "oturum_olustur", "oturum_dogrula", "oturum_anahtari",
                      "kullanici_oturumlarini_sil"],
    "shared.auth": ["sifre_dogrula", "kullanici_dogrula_v2", "supabase_sifre_kaydet",
                    "giris_kontrol", "giris_basarisiz", "giris_basarili"],
    "shared.audit": ["log_yaz", "wrap_client", "guvenlik_kaydi", "yetki_degisikligi_kaydet"],
    "shared.utils": ["tarih_metni", "sidebar_ust", "sidebar_baslik", "sidebar_kullanici",
                     "sku_anahtar"],                     # SKU eşleştirme tek kural (Faz 3)
    # Gece yedeği: tablo listesi tek kaynak, sayfalı + sayımla denetlenen okuma (Eki 2026)
    "shared.yedek_tablolari": ["tum_satirlar", "sayim", "sira_adaylari", "tablo_oku", "tumunu_oku",
                               "yedek_disi", "excel_degeri", "excel_satirlari", "canli_mi"],
}


@pytest.mark.parametrize("modul,fonksiyonlar", KRITIK_FONKSIYONLAR.items())
def test_kritik_fonksiyonlar_duruyor(modul, fonksiyonlar):
    assert modul in _TARANAN_MODULLER, f"{modul} bulunamadı"
    eksik = [f for f in fonksiyonlar if f not in _TARANAN_MODULLER[modul]]
    assert not eksik, (
        f"{modul} içinden fonksiyon KAYBOLDU: {eksik}\n"
        "Bu fonksiyonlar daha önce yazılmıştı. Muhtemelen bu dosyanın eski "
        "bir sürümü yüklendi.")


# ═══════════════════════════════════════════════════════════════════════
# 3) YETKİ LİSTELERİ — kim hangi modüle girmeli
#    Yeni kullanıcı eklendiğinde buraya da ekle; kaybolursa test kırılır.
# ═══════════════════════════════════════════════════════════════════════
def _app_yetkileri():
    src = open(KOK / "app.py", encoding="utf-8").read()
    ns = {}
    for ad in ("KAYRANACC_KULLANICILAR", "KAYRANPM_KULLANICILAR",
               "HESAP_MAKINESI_KULLANICILAR", "ITHALAT_KULLANICILAR",
               "TEKNIKSERVIS_KULLANICILAR", "SATIS_KULLANICILAR",
               "DEPO_KULLANICILAR", "YONETIM_KULLANICILAR", "PATRON_PANEL_KULLANICILAR"):
        m = re.search(rf"^{ad}\s*=\s*(.*?)(?=\n[A-Z_]+\s*=|\n#|\nY0)", src, re.S | re.M)
        assert m, f"app.py içinde {ad} bulunamadı"
        exec(m.group(0).split("\n#")[0], ns)
    exec(re.search(r"^def _statik_yetkiler\(.*?^    \}", src, re.S | re.M).group(0), ns)
    return ns["_statik_yetkiler"]


# kullanıcı → sahip OLMASI gereken modüller
BEKLENEN_YETKILER = {
    "ibrahim": {"kayranacc", "kayranpm", "ithalat", "teknikservis", "satis", "depo",
                "hesap_makinesi"},
    "serdar":  {"kayranacc", "ithalat", "depo", "teknikservis"},   # 21.09'da iki kez kayboldu
    "samet":   {"teknikservis", "depo"},
    "selcuk":  {"depo"},
}
# kullanıcı → sahip OLMAMASI gereken modüller (yetki sızması kontrolü)
YASAK_YETKILER = {
    "serdar": {"kayranpm", "satis", "hesap_makinesi"},
    "selcuk": {"kayranacc", "kayranpm", "satis"},
}


@pytest.mark.parametrize("kullanici,moduller", BEKLENEN_YETKILER.items())
def test_kullanici_yetkileri_duruyor(kullanici, moduller):
    y = _app_yetkileri()(kullanici)
    eksik = [m for m in moduller if not y.get(m)]
    assert not eksik, (
        f"'{kullanici}' kullanıcısının yetkisi KAYBOLDU: {eksik}\n"
        "app.py'nin eski bir sürümü yüklenmiş olabilir.")


@pytest.mark.parametrize("kullanici,moduller", YASAK_YETKILER.items())
def test_kullanici_yetki_sizmasi_yok(kullanici, moduller):
    y = _app_yetkileri()(kullanici)
    sizan = [m for m in moduller if y.get(m)]
    assert not sizan, f"'{kullanici}' sahip olmaması gereken yetkiye sahip: {sizan}"


def test_toplam_aktifler_tek_kaynak():
    """Toplam Aktifler beyaz listesi TEK yerde tanımlı olmalı ve iki kontrol
    de oradan okumalı. Eskiden iki ayrı sabit liste vardı, biri güncellenmedi."""
    src = open(KOK / "kayranacc" / "main.py", encoding="utf-8").read()
    assert re.search(r"^TOPLAM_AKTIFLER_YETKILI\s*=\s*\{", src, re.M), \
        "TOPLAM_AKTIFLER_YETKILI modül düzeyinde tanımlı değil"
    assert "YETKILI_KULLANICILAR_TOPLAM_AKTIFLER = _toplam_aktifler_yetkilileri()" in src, \
        "sol menü tek kaynaktan okumuyor"
    assert "YETKILI_TOPLAM_AKTIFLER = _toplam_aktifler_yetkilileri()" in src, \
        "sayfa gövdesi tek kaynaktan okumuyor"
    # Elde yazılmış ikinci bir liste kalmamalı
    sabit = re.findall(r'YETKILI\w*TOPLAM\w*\s*=\s*\{"ibrahim"', src)
    assert not sabit, "Toplam Aktifler için elle yazılmış ikinci liste var"
    ns = {}
    exec(re.search(r"^TOPLAM_AKTIFLER_YETKILI\s*=\s*\{.*?\}", src, re.S | re.M).group(0), ns)
    assert "serdar" in ns["TOPLAM_AKTIFLER_YETKILI"]


# ═══════════════════════════════════════════════════════════════════════
# 4) DEPO GARANTİ LİSTESİ — stok sıfır olsa bile hepsi seçilebilir olmalı
# ═══════════════════════════════════════════════════════════════════════
def test_depo_garanti_listesi_eksiksiz():
    src = open(KOK / "kayranpm" / "database.py", encoding="utf-8").read()
    m = re.search(r"def get_satis_depolari\(.*?return adlar", src, re.S)
    assert m, "get_satis_depolari bulunamadı"
    govde = m.group(0)
    for depo in ("TEKNİK DEPO", "İADE DEPO", "İKİNCİ EL DEPO", "OUTLET DEPO", "HURDA DEPO"):
        assert depo in govde, (
            f"'{depo}' garanti listesinde YOK — stoğu sıfırlanınca seçeneklerden "
            "kaybolur (09.09'da Servis Depo'nun kaybolma sebebi).")


def test_depo_kanonik_servis_teknik_ayni():
    from kayranpm.database import depo_kanonik
    assert depo_kanonik("SERVIS DEPO") == depo_kanonik("TEKNİK DEPO") == "TEKNİK DEPO"


# ═══════════════════════════════════════════════════════════════════════
# 5) ÇALIŞMA ZAMANI KORUMALARI — Streamlit'e özgü tuzaklar
# ═══════════════════════════════════════════════════════════════════════
def test_dialog_icinde_duz_rerun_yok():
    """@st.dialog içinde st.rerun() değil _rerun_app() kullanılmalı.
    Fragment kapsamında kalan rerun dialog'u kapatmaz (mal kabul bug'ı)."""
    src = open(KOK / "teknikservis" / "main.py", encoding="utf-8").read()
    lines = src.split("\n")
    sorun = []
    for i, l in enumerate(lines):
        if "@st.dialog" not in l or l.strip().startswith("#"):
            continue
        j = i + 1
        while j < len(lines) and not re.match(r"\s*def\s+\w+", lines[j]):
            j += 1
        ind = len(lines[j]) - len(lines[j].lstrip())
        k = j + 1
        while k < len(lines):
            cur = lines[k]
            if cur.strip() and (len(cur) - len(cur.lstrip())) <= ind:
                break
            if re.search(r"(?<!_)\bst\.rerun\(\)", cur) and not cur.strip().startswith("#"):
                sorun.append(k + 1)
            k += 1
    assert not sorun, f"teknikservis/main.py dialog içinde düz st.rerun(): satır {sorun}"


def test_requirements_ust_sinirli():
    """Platform sürüm atlaması sessizce bozmasın diye üst sınır olmalı."""
    req = open(KOK / "requirements.txt", encoding="utf-8").read()
    for paket in ("streamlit", "supabase", "pandas"):
        satir = next((l for l in req.splitlines() if l.strip().startswith(paket)), "")
        assert satir and "<" in satir, f"requirements.txt: {paket} için üst sınır yok"


# ═══════════════════════════════════════════════════════════════════════
# 6) ÇERÇEVE (D1) — tek standart, geri dönmesin
# ═══════════════════════════════════════════════════════════════════════
_MODULLER = ["satis", "ithalat", "kayranpm", "teknikservis", "kayranacc", "depo"]


@pytest.mark.parametrize("modul", _MODULLER)
def test_modul_kendi_cikis_dugmesini_yazmiyor(modul):
    """Modüllerdeki elle yazılmış 'Çıkış Yap' düğmeleri oturum anahtarını
    YAKMIYORDU — kullanıcı yenileyince 7 gün boyunca geri içerideydi.
    Çıkış yalnız shared.oturum.cikis_yap() üzerinden yapılmalı."""
    src = open(KOK / modul / "main.py", encoding="utf-8").read()
    assert not re.search(r'st\.button\(\s*["\'][^"\']*Çıkış Yap', src), (
        f"{modul}/main.py kendi Çıkış düğmesini çiziyor — shared.utils.sidebar_ust kullanılmalı")
    assert "sidebar_ust(" in src, f"{modul}/main.py ortak sidebar üst bileşenini kullanmıyor"


def test_cikis_yap_anahtari_yakar_ve_urlyi_temizler():
    src = open(KOK / "shared" / "oturum.py", encoding="utf-8").read()
    govde = src[src.index("def cikis_yap"):]
    assert "oturum_kapat()" in govde and "query_params.clear()" in govde


@pytest.mark.parametrize("modul", ["kayranacc", "kayranpm"])
def test_elle_yazilmis_buyuk_baslik_kalmadi(modul):
    """Sayfa başlıkları tek standart (shared/tasarim.baslik). Muhasebe'de
    eskiden her sayfada başlık İKİ KEZ çıkıyordu."""
    src = open(KOK / modul / "main.py", encoding="utf-8").read()
    assert 'class="baslik"' not in src


def test_gorunmez_eleman_boslugu_kurali_var():
    """Sayfa başındaki ~200px boşluğu kapatan kural çekirdek CSS'te durmalı."""
    src = open(KOK / "shared" / "tasarim.py", encoding="utf-8").read()
    assert '[data-testid="stElementContainer"][height="0px"]' in src
    assert 'style:only-child' in src


def test_oturum_hata_yutmuyor():
    """shared/oturum.py'de 'except ...: pass' olmamalı. Anahtar yakma hatası
    sessizce geçerse çıkış yapan kullanıcı yenileyince içeride kalır."""
    import re
    src = open(KOK / "shared" / "oturum.py", encoding="utf-8").read()
    assert not re.search(r"except[^\n]*:\s*\n\s*pass\b", src)
    assert "kritik=True" in src


def test_ust_menu_etiketleri_kesilmiyor():
    """Üst menüde etiketler '…' ile kesilmemeli ve ikon gizlenince ikonun
    KUTUSU da gizlenmeli (yoksa yazı sağa itilip 'Ana Sa…' oluyordu)."""
    src = open(KOK / "app.py", encoding="utf-8").read()
    bas = src.index("def ust_navigasyon")
    govde = src[bas:src.index("\ndef ", bas + 10)]
    assert "text-overflow:ellipsis" not in govde
    assert 'span:has(> [data-testid="stIconMaterial"])' in govde
    assert "min-width:max-content" in govde
