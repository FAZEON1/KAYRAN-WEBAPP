# -*- coding: utf-8 -*-
"""Yedeklenecek tablolar ve eksiksiz (sayfalı, sayımla denetlenen) tablo okuma — TEK KAYNAK.

Kullananlar: otonom/gece_yedek.py (gece yedeği), otonom/geri_yukle_tam.py (tam geri yükleme),
yonetim.py (Sistem › Veri Yedekleme düğmesi).

Neden: Supabase tek sorguda en fazla 1.000 satır döndürür. Eski gece yedeği her tabloyu tek
select ile okuduğu için satislar (15.819), audit_log (27.708) gibi tablolar 1.000'de kesiliyordu
ve listede tabloların yarısı yoktu. Burada:
  - her tablo 1.000'lik sayfalarla, kararlı bir sıraya göre (birincil anahtar ya da tüm sütunlar)
    okunur;
  - okunan satır sayısı `count="exact"` ile alınan beklenen sayıyla karşılaştırılır; tutmazsa
    tablo EKSİK sayılır ve yedek başarısız olur;
  - kodda kullanılan her tablo YEDEK_TABLOLAR ya da HARIC/GORUNUMLER'de olmak zorundadır
    (tests/test_gece_yedek.py tarar).
"""

import json
import re

SAYFA = 1000

# Sıra GERİ YÜKLEME sırasıdır: önce bağımsız (ana) tablolar, sonra onlara bağlı olanlar.
YEDEK_TABLOLAR = [
    # Ayarlar / ana kartlar (bağımsız)
    "sistem_ayarlari", "pm_ayarlar", "kullanici_yetkileri", "kullanici_tercih",
    "veri_surumu", "kur_gunluk", "haftalar", "bankalar",
    "urunler", "sku_eslesme", "stok_yas",
    "ref_firmalar", "personel",
    "edefter_ayarlar", "edefter_hesap_plani", "edefter_donem_kilit",
    # Ürün / stok
    "firma_stok", "yoldaki_urunler", "stok_hareketleri",
    "depo_manuel_takip", "depo_sevk_log", "happylife_stok",
    # Kampanya / ref / destek
    "kampanyalar", "kampanya_urunler", "ref_butce", "ref_kayitlari",
    "alinan_destekler",
    # İthalat / alım
    "ithalat_dosyalari", "ithalat_kalemleri", "satin_alma_gecmisi",
    # Satış
    "satislar", "iadeler", "hm_urun_karliligi",
    "mikro_esitleme_durum", "mikro_esitleme_arsiv",   # Mikro eşitleme durumu + değiştirilen satırların arşivi
    # Muhasebe
    "odemeler", "cekler", "virmanlar", "tahsilatlar", "aktif_manuel_kalemler",
    # e-Defter (fiş satırları fişten sonra)
    "edefter_fisler", "edefter_fis_satirlari",
    # Teknik servis
    "ts_kayitlar", "ts_gecmis", "ts_urun_notlari",
    # Hesap Makinesi
    "prim_gecmis",
    # Ortak
    "siparis_onerileri", "talepler", "gorevler", "bildirimler",
    "gumruk_sorgulari", "sirket_belgeleri", "izin_talepleri", "gunluk_giris",
    # Kayıt / günlük (iş verisi değil ama geçmiş; geri dönüşü olmayan bilgi)
    "audit_log", "hata_kayitlari", "yuklemeler", "soru_kayitlari",
    "asistan_rapor", "bt_olcum", "bt_rapor",
    # Eski temizliklerden kalan elle alınmış yedek tablolar
    "_kanal_birlestirme_yedek", "_temizlik_yedek_202610",
]

# Bilerek HARİÇ (yedeğe ALINMAZ, geri yüklenmez) — açıkça yazılı kalsın.
HARIC = {
    "kullanici_sifreler":    "şifre özetleri (sır)",
    "bayi_kullanicilar":     "bayi hesapları, sifre_hash içerir (sır)",
    "bildirim_ayarlari":     "smtp_password içerir (sır)",
    "giris_denemeleri":      "giriş denemesi sayacı (oturum güvenliği, sır sayılır)",
    "bayi_giris_denemeleri": "bayi giriş denemesi sayacı (oturum güvenliği)",
    "aktif_excel_verileri":  "geçici yükleme önbelleği",
    "kullanici_durum":       "anlık oturum / çevrimiçi durumu",
    "cop_kutusu":            "silinenlerin 30 günlük kopyası; asıl tablolar zaten yedekte",
    "mikro_cari_bakiye":     "Mikro aktarıcısının kopyası; kaynak Mikro, her gece baştan çekilir",
    "mikro_fatura":          "Mikro aktarıcısının kopyası; kaynak Mikro, her gece baştan çekilir",
    "mikro_satis_satir":     "Mikro aktarıcısının kopyası; kaynak Mikro, her gece baştan çekilir",
    "mikro_senk_durum":      "Mikro aktarıcısının tur durumu (geçici)",
    "mikro_kesif":           "Mikro keşif sonucu; her gün yeniden okunur",
    "mikro_cari_hareket":    "Mikro aktarıcısının kopyası; kaynak Mikro, her gece baştan çekilir",
    "mikro_cari_kart":       "Mikro aktarıcısının kopyası",
    "mikro_banka_kart":      "Mikro aktarıcısının kopyası",
    "mikro_kasa_kart":       "Mikro aktarıcısının kopyası",
    "mikro_depo_kart":       "Mikro aktarıcısının kopyası",
    "mikro_cek":             "Mikro aktarıcısının kopyası",
    "mikro_muhasebe_ay":     "Mikro aktarıcısının kopyası (muhasebe ay × hesap toplamı)",
    "mikro_muhasebe_ay_tur": "Mikro aktarıcısının kopyası (muhasebe ay × hesap × fiş türü toplamı)",
    "mikro_muhasebe_tur":    "Mikro aktarıcısının kopyası (muhasebe ay × fiş türü dağılımı)",
    "mikro_hesap_plani":     "Mikro aktarıcısının kopyası",
    "mikro_stok_miktar":     "Mikro aktarıcısının kopyası (ürün × depo miktarı; her turda tam çekilir)",
    "mikro_siparis":         "Mikro aktarıcısının kopyası (müşteri ve tedarikçi siparişleri)",
    "mikro_ithalat":         "Mikro aktarıcısının kopyası (ithalat faturası ve masraf satırları)",
    "mikro_esitle_gunluk":   "Eşitleme turlarının günlüğü (14 gün; Sistem › Mikro bağlantısı)",
    "mikro_ithalat_dosya":   "Mikro aktarıcısının kopyası (ithalat dosyaları)",
    "mikro_alim_satir":      "Mikro aktarıcısının kopyası (alış satırları)",
    "mikro_depo_hareket":    "Mikro aktarıcısının kopyası (depo giriş / çıkış / sevk hareketleri)",
    "mikro_serino":          "Mikro aktarıcısının kopyası (seri numarası tanımları; teknik servis)",
    "mikro_stok_kart":       "Mikro aktarıcısının kopyası (ürün kartları)",
    "mikro_stok_barkod":     "Mikro aktarıcısının kopyası (barkodlar)",
    "mikro_satis_fiyat":     "Mikro aktarıcısının kopyası (satış fiyat listesi satırları)",
    "mikro_fiyat_liste":     "Mikro aktarıcısının kopyası (satış fiyat listesi tanımları)",
    "mikro_multikod":        "Mikro aktarıcısının kopyası (müşteri ürün kodları; her turda tam çekilir)",
    "mikro_aktarici_surum":  "aktarıcının kodu; depodan yayınlanır",
    "oturumlar":             "açık oturum özetleri (geçici; geri yüklenmez)",
    "sema_gecmisi":          "kurulan SQL dosyalarının kaydı (veritabani/uygula.py)",
}

# Veritabanı GÖRÜNÜMLERİ: veri değil, tablolardan hesaplanır.
GORUNUMLER = ("v_destek_donem", "v_satis_pnl", "mv_gunluk_pnl", "mv_kanal_ay_pnl")

# Kodda adı geçen ama canlı veritabanında bulunmayabilecek tablolar: yoksa yedek başarısız
# SAYILMAZ (uyarı verilir). Başka bir tablo bulunamazsa yedek BAŞARISIZ olur.
CANLIDA_OLMAYABILIR = set()   # canlıda bulunmayabilecek tablolar ("yok" → uyarı, hata değil)

# Birincil anahtarı "id" olmayan bilinen tablolar (veritabani/*.sql ve on_conflict kullanımları).
SIRA_ANAHTARI = {
    "veri_surumu": ["tablo"],
    "kullanici_tercih": ["kullanici"],
    "kullanici_yetkileri": ["kullanici"],
    "sku_eslesme": ["dis_kod"],
    "personel": ["kod"],
    "sistem_ayarlari": ["anahtar"],
    "pm_ayarlar": ["anahtar"],
    "stok_yas": ["sku"],
}

CANLI_PROJE = "qspwlqegoeudifxxrxcj"


class YedekHatasi(Exception):
    pass


def yedek_disi():
    """Yedeğe girmeyen her ad (hariç tablolar + görünümler)."""
    return set(HARIC) | set(GORUNUMLER)


def _tablo_yok_mu(hata):
    s = str(hata)
    return ("PGRST205" in s or "42P01" in s or "does not exist" in s
            or "Could not find the table" in s)


def _uygula_sira(q, sira):
    for c in sira or []:
        q = q.order(c)
    return q


def tum_satirlar(sb, tablo, sayfa=SAYFA, sira=None, beklenen=None):
    """Tablonun TÜM satırları, `range` ile `sayfa`'lık parçalar hâlinde.

    sira: kararlı sıra için sütunlar (sayfalar arası kayma/tekrar olmasın).
    beklenen: verilirse boş sayfa gelene kadar okunur. Her sayfa okunan satır kadar
    ilerlediği için sunucu sayfayı `sayfa`'dan küçük kesse de (ör. en fazla 500) eksik kalmaz.
    """
    out, bas = [], 0
    while True:
        q = _uygula_sira(sb.table(tablo).select("*"), sira)
        parca = q.range(bas, bas + sayfa - 1).execute().data or []
        out.extend(parca)
        if not parca:
            return out
        # beklenen biliniyorsa boş sayfaya kadar oku: okuma sırasında eklenen satır
        # gözden kaçmasın (sayı tutmazsa tablo_oku baştan okur).
        if beklenen is None and len(parca) < sayfa:
            return out
        bas += len(parca)


def sayim(sb, tablo):
    """(beklenen satır sayısı, örnek ilk satır ya da None) — count="exact"."""
    r = sb.table(tablo).select("*", count="exact").range(0, 0).execute()
    adet = getattr(r, "count", None)
    if adet is None:
        raise YedekHatasi(f"{tablo}: satır sayısı alınamadı (count boş döndü)")
    veri = r.data or []
    return int(adet), (veri[0] if veri else None)


def sira_adaylari(tablo, ornek):
    """Denenecek sıralama seçenekleri, en iyiden kötüye."""
    adaylar = []
    if tablo in SIRA_ANAHTARI:
        adaylar.append(list(SIRA_ANAHTARI[tablo]))
    sutunlar = list(ornek.keys()) if ornek else []
    if "id" in sutunlar:
        adaylar.append(["id"])
    if sutunlar:
        adaylar.append(sutunlar)                                     # PK'sız: tüm sütunlar
        duz = [c for c in sutunlar if not isinstance(ornek.get(c), (dict, list))]
        if duz and duz != sutunlar:
            adaylar.append(duz)                                      # json sütunu sıralanamazsa
        adaylar.append(sutunlar[:1])
    adaylar.append([])                                               # son çare: sırasız
    tekil = []
    for a in adaylar:
        if a not in tekil:
            tekil.append(a)
    return tekil


def tablo_oku(sb, tablo, deneme=2, oku=None):
    """Bir tabloyu eksiksiz okur ve sayımla doğrular.

    Dönüş: {"tablo", "satirlar", "beklenen", "okunan", "sira", "durum", "mesaj"}
      durum: "tamam" | "yok" (CANLIDA_OLMAYABILIR'de ve canlıda yok) | "eksik" | "hata"
    Okuma sırasında satır eklenirse sayı tutmayabilir: `deneme` kez baştan okunur.
    """
    oku = oku or tum_satirlar
    son = {"tablo": tablo, "satirlar": [], "beklenen": None, "okunan": 0,
           "sira": [], "durum": "hata", "mesaj": ""}
    for _ in range(max(1, deneme)):
        try:
            beklenen, ornek = sayim(sb, tablo)
        except Exception as e:
            if tablo in CANLIDA_OLMAYABILIR and _tablo_yok_mu(e):
                son.update(durum="yok", mesaj="tablo canlıda yok (beklenen durum)")
                return son
            son.update(durum="hata", mesaj=f"sayılamadı: {_kisa(e)}")
            continue
        son["beklenen"] = beklenen
        if beklenen == 0:
            son.update(satirlar=[], okunan=0, durum="tamam", mesaj="")
            return son
        satirlar, hata, kullanilan = None, None, []
        for sira in sira_adaylari(tablo, ornek):
            try:
                satirlar = oku(sb, tablo, sira=sira, beklenen=beklenen)
                kullanilan = sira
                break
            except Exception as e:                                   # sıralanamayan sütun vb.
                hata = e
        if satirlar is None:
            son.update(durum="hata", mesaj=f"okunamadı: {_kisa(hata)}")
            continue
        son.update(satirlar=satirlar, okunan=len(satirlar), sira=kullanilan)
        if len(satirlar) != beklenen:
            son.update(durum="eksik",
                       mesaj=f"beklenen {beklenen} satır, okunan {len(satirlar)}")
            continue
        if kullanilan == ["id"] and len({r.get("id") for r in satirlar}) != len(satirlar):
            son.update(durum="eksik", mesaj="sayfalar arası tekrar eden id (kararsız sıra)")
            continue
        son.update(durum="tamam", mesaj="" if kullanilan else "kararlı sıra kurulamadı")
        return son
    return son


def tumunu_oku(sb, tablolar=None, ilerleme=None, oku=None):
    """(sonuçlar listesi, hatalı sonuçlar listesi). Hatalı = durum "eksik" ya da "hata"."""
    sonuclar = []
    for t in (YEDEK_TABLOLAR if tablolar is None else tablolar):
        s = tablo_oku(sb, t, oku=oku)
        sonuclar.append(s)
        if ilerleme:
            ilerleme(s)
    return sonuclar, [s for s in sonuclar if s["durum"] in ("eksik", "hata")]


def _kisa(e, n=200):
    return f"{type(e).__name__}: {str(e)[:n]}"


# ── Excel'e yazılabilir hâle getirme ────────────────────────────────
_YASAK_KARAKTER = re.compile(r"[\000-\010]|[\013-\014]|[\016-\037]")
EXCEL_HUCRE_SINIRI = 32767


def excel_degeri(v):
    """Excel hücresine güvenle yazılacak değer. dict/list → JSON metni; Excel'in kabul
    etmediği denetim karakterleri atılır (yoksa bütün dosya IllegalCharacterError ile düşer).
    Asıl yedek JSON dosyalarıdır; Excel okumak/aramak içindir."""
    if isinstance(v, (dict, list)):
        v = json.dumps(v, ensure_ascii=False, default=str)
    if isinstance(v, str):
        v = _YASAK_KARAKTER.sub("", v)
        if len(v) > EXCEL_HUCRE_SINIRI:
            v = v[:EXCEL_HUCRE_SINIRI - 20] + " …[KESİLDİ, JSON'da tam]"
    return v


def excel_satirlari(rows):
    return [{k: excel_degeri(v) for k, v in r.items()} for r in rows]


def canli_mi(url):
    return CANLI_PROJE in str(url or "")
