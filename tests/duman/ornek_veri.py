# -*- coding: utf-8 -*-
"""Sahte veritabanı için UYDURMA ama gerçekçi örnek veri (tests/duman).

Tablo ve sütun adları canlı şemayla aynıdır; değerler tamamen uydurmadır (canlı veriden kopya
yoktur). Amaç sayfaların DOLU hâlini görmek: kartlar, tablolar, grafikler. Ekran görüntüsü
karşılaştırması (eski ↔ yeni) ve dolu veride çöken sayfaları yakalamak için kullanılır.

Tarihler bugüne göre üretilir (bu hafta / geçen ay her zaman dolu); rastgelelik sabit tohumlu,
her çalıştırmada aynı veri.

    import sahte_db, ornek_veri
    ornek_veri.doldur(sahte_db.TABLOLAR)
"""
import random
from datetime import date, datetime, timedelta

# (sku, ad, kategori, marka, alış $, satış $)
URUNLER = [
    ("FZ-SSD-512", "Fazeon Hızlı 512 GB NVMe SSD", "ssd", "FAZEON", 24.5, 34.9),
    ("FZ-SSD-1TB", "Fazeon Hızlı 1 TB NVMe SSD", "ssd", "FAZEON", 41.0, 57.5),
    ("FZ-SSD-2TB", "Fazeon Hızlı 2 TB NVMe SSD", "ssd", "FAZEON", 78.0, 104.0),
    ("AGI-RAM-16", "AGI 16 GB DDR4 3200 MHz Bellek", "ram", "AGI", 18.2, 26.0),
    ("AGI-RAM-32", "AGI 32 GB DDR5 6000 MHz Bellek", "ram", "AGI", 52.0, 71.0),
    ("IN3-4060", "Inno3D RTX 4060 Twin X2 8 GB", "ekran kartı", "INNO3D", 262.0, 309.0),
    ("IN3-4070S", "Inno3D RTX 4070 Super Twin 12 GB", "ekran kartı", "INNO3D", 512.0, 589.0),
    ("XS-KASA-M1", "Xaser M1 ARGB Mid Tower Kasa", "kasa", "XASER", 31.0, 45.0),
    ("XS-SOG-240", "Xaser 240 mm Sıvı Soğutucu", "cpu soğutucu", "XASER", 38.0, 54.0),
    ("FZ-MON-27Q", "Fazeon 27 inç QHD 165 Hz Monitör", "monitör", "FAZEON", 142.0, 189.0),
    ("FZ-MON-24F", "Fazeon 24 inç FHD 144 Hz Monitör", "monitör", "FAZEON", 84.0, 112.0),
    ("MIO-C580", "Mio MiVue C580 Araç Kamerası", "araç kamerası", "Mio", 46.0, 69.0),
    ("EXC-SET-40", "Excavator 40 Parça Tamir Seti", "el aleti", "EXCAVATOR", 9.5, 16.0),
    ("KSP-TS-1Y", "Kaspersky Total Security 1 Yıl", "anti virüs", "KASPERSKY", 7.2, 12.5),
    ("XS-PAD-XL", "Xaser XL Mouse Pad", "mouse pad", "XASER", 3.1, 6.5),
    ("FZ-KBL-HDMI", "Fazeon HDMI 2.1 Kablo 2 m", "kablo/konnektör", "FAZEON", 2.4, 5.0),
]
KANALLAR = [  # (kanal adı, satış payı)
    ("D-MARKET ELEKTRONİK HİZMETLER VE TİCARET ANONİM ŞİRKETİ", 0.30),
    ("VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI", 0.24),
    ("EERA ELEKTRONİK TİCARET VE BİLİŞİM HİZMETLERİ ANONİM ŞİRKETİ", 0.18),
    ("MONDAY BİLİŞİM SANAYİ VE TİCARET ANONİM ŞİRKETİ", 0.12),
    ("ÖRNEK BİLGİSAYAR TİCARET LİMİTED ŞİRKETİ", 0.10),
    ("DENEME TEKNOLOJİ ANONİM ŞİRKETİ", 0.06),
]
DEPOLAR = ["MERKEZ DEPO", "OUTLET DEPO", "İKİNCİ EL DEPO", "SERVIS DEPO", "İADE DEPO"]
KUR = 41.20
# Canlı şemada id sütunu olmayan tablolar
_ID_YOK = {"urunler", "stok_yas", "kur_gunluk", "yoldaki_urunler", "sistem_ayarlari"}


def _g(d):
    return d.isoformat()


def _zaman(d, saat=10):
    return datetime(d.year, d.month, d.day, saat, 15).isoformat() + "+03:00"


def doldur(tablolar, bugun=None):
    r = random.Random(20261004)
    bugun = bugun or date.today()
    T = {}

    # ── Ürünler ve stok ──
    T["urunler"] = []
    for i, (sku, ad, kat, marka, alis, satis) in enumerate(URUNLER):
        stok = r.choice([0, 6, 18, 35, 60, 120, 240, 410])
        kir = {"MERKEZ DEPO": int(stok * 0.8), "OUTLET DEPO": int(stok * 0.1)}
        if i % 3 == 0:
            kir.update({"İKİNCİ EL DEPO": r.randint(1, 9), "İADE DEPO": r.randint(1, 6)})
        T["urunler"].append({
            "sku": sku, "urun_adi": ad, "kategori": kat, "marka": marka,
            "satis_fiyati": satis, "alis_fiyati": alis, "hedef_kar_marji": 20,
            "bizim_stok": stok, "trendyol_stok": 0, "eol": i == 14,
            "ilk_giris_tarihi": _g(bugun - timedelta(days=40 + i * 23)),
            "guncelleme_tarihi": _g(bugun - timedelta(days=2)),
            "depo_kirilim": kir, "barkod": f"86900000{i:05d}", "ozellikler": "",
        })
    T["stok_yas"] = [{"sku": u[0], "ilk_gorulen_tarih": _g(bugun - timedelta(days=40 + i * 23))}
                     for i, u in enumerate(URUNLER)]
    T["firma_stok"] = []
    for hafta in range(8):                       # son 8 haftalık müşteri raporu (satış eğilimi)
        for firma in ("VATAN", "HB", "MONDAY", "ITOPYA"):
            for sku, ad, *_ in URUNLER[:12]:
                T["firma_stok"].append({"firma": firma, "sku": sku, "urun_adi": ad,
                                        "stok_miktari": r.randint(0, 80), "haftalik_satis": r.randint(2, 14),
                                        "stok_magaza": r.randint(0, 20), "satis_magaza": r.randint(0, 5),
                                        "yukleme_tarihi": _g(bugun - timedelta(days=3 + 7 * hafta))})

    # ── Satışlar: son 14 ay ──
    T["satislar"] = []
    for gun in range(0, 420, 3):
        d = bugun - timedelta(days=gun)
        for _ in range(r.randint(2, 5)):
            kanal = r.choices([k for k, _ in KANALLAR], [p for _, p in KANALLAR])[0]
            sku, ad, _k, _m, alis, satis = r.choice(URUNLER)
            maliyet = round(alis * r.uniform(1.04, 1.12), 2)
            T["satislar"].append({
                "tarih": _g(d), "kanal": kanal, "sku": sku, "urun_adi": ad,
                "adet": r.randint(1, 25), "birim_satis": round(satis * r.uniform(0.92, 1.03), 2),
                "birim_maliyet": maliyet, "birim_firma_destek": round(satis * r.choice([0, 0, 0.02, 0.05]), 2),
                "birim_ek_destek": 0, "siparis_no": f"SP{d:%y%m%d}{r.randint(100, 999)}",
                "olusturma_tarihi": _zaman(d)})
    T["iadeler"] = [{"tarih": _g(bugun - timedelta(days=d)), "kanal": KANALLAR[d % 4][0],
                     "sku": URUNLER[d % 10][0], "urun_adi": URUNLER[d % 10][1], "iade_adet": 1 + d % 3,
                     "iade_brut": 120.0 + d, "iade_iskonto": 0, "iade_masraf": 4.5, "iade_net": 115.5 + d,
                     "depo": "İADE DEPO", "kaynak": "excel"} for d in range(3, 120, 9)]

    # ── Kampanyalar ──
    T["kampanyalar"], T["kampanya_urunler"] = [], []
    for i, (ad, firma, durum) in enumerate([
            ("Okula dönüş SSD fırsatı", "D-MARKET", "aktif"), ("Ekran kartı haftası", "VATAN", "aktif"),
            ("Yaz monitör kampanyası", "EERA", "kapali"), ("Bellek yükseltme", "MONDAY", "kapali")]):
        bas = bugun - timedelta(days=10 + i * 35)
        T["kampanyalar"].append({"id": i + 1, "kampanya_adi": ad, "firma": firma, "durum": durum,
                                 "baslangic_tarihi": _g(bas), "bitis_tarihi": _g(bas + timedelta(days=30)),
                                 "olusturma_tarihi": _g(bas), "kategori": URUNLER[i * 3][2],
                                 "kampanya_turu": "fiyat", "spiff_tl": 0, "spiff_kur": KUR, "notlar": ""})
        for sku, ad2, _k, _m, alis, satis in URUNLER[i * 3:i * 3 + 3]:
            T["kampanya_urunler"].append({"kampanya_id": i + 1, "sku": sku, "urun_adi": ad2,
                                          "pacal_maliyet": alis * 1.08, "satis_fiyati": satis * 0.95,
                                          "birim_firma_destek": round(satis * 0.04, 2), "birim_ek_destek": 0,
                                          "satilan_adet": r.randint(20, 300), "notlar": ""})

    # ── İthalat ve yurt içi alım ──
    T["ithalat_dosyalari"], T["ithalat_kalemleri"] = [], []
    tedarikci = ["Shenzhen Ornek Electronics Co.", "Taipei Deneme Tech Ltd.", "Guangzhou Sample Trading"]
    durumlar = ["Teslim Alındı"] * 5 + ["Gümrükte", "Antrepoda", "Yolda"]
    for i in range(8):
        d = bugun - timedelta(days=15 + i * 38)
        did = i + 1
        T["ithalat_dosyalari"].append({
            "id": did, "dosya_no": f"ITH-2026-{did:03d}", "tarih": _g(d), "tedarikci": tedarikci[i % 3],
            "mense_ulke": "Çin" if i % 3 != 1 else "Tayvan", "doviz": "USD", "kur": KUR - i * 0.4,
            "navlun": 4200 + i * 150, "gumruk": 900, "sigorta": 70, "nakliye": 300, "diger": 450,
            "masraflar": {"navlun": 4200 + i * 150, "gumruk_musavirligi": 350, "liman_ardiye": 1800,
                          "mal_sigortasi": 70, "damga_vergisi": 15, "diger": 450},
            "pi_no": f"PI-{2600 + did}", "ithalat_takip_no": f"TK{did:05d}", "durum": durumlar[-1 - i] if i < 3 else "Teslim Alındı",
            "tahmini_varis": _g(d + timedelta(days=35)), "teslim_tarihi": _g(d + timedelta(days=38)) if i >= 3 else None,
            "teslim_deposu": "MERKEZ DEPO", "alim_turu": "ithalat", "stok_islendi": i >= 3,
            "olusturma_tarihi": _zaman(d), "notlar": ""})
        for sku, ad, kat, _m, alis, _s in r.sample(URUNLER[:12], 4):
            T["ithalat_kalemleri"].append({"dosya_id": did, "sku": sku, "urun_adi": ad,
                                           "adet": r.choice([100, 200, 300, 500]), "birim_fob": alis * 0.9,
                                           "urun_grubu": kat})
    for i in range(3):
        did = 20 + i
        d = bugun - timedelta(days=20 + i * 45)
        T["ithalat_dosyalari"].append({"id": did, "dosya_no": f"YI-2026-{i + 1:03d}", "tarih": _g(d),
                                       "tedarikci": "Örnek Dağıtım A.Ş.", "doviz": "USD", "kur": KUR,
                                       "durum": "Teslim Alındı", "alim_turu": "yurtici", "masraflar": {},
                                       "teslim_tarihi": _g(d), "teslim_deposu": "MERKEZ DEPO",
                                       "stok_islendi": True, "olusturma_tarihi": _zaman(d)})
        sku, ad, kat, _m, alis, _s = URUNLER[12 + i]
        T["ithalat_kalemleri"].append({"dosya_id": did, "sku": sku, "urun_adi": ad, "adet": 150,
                                       "birim_fob": alis, "urun_grubu": kat})
    T["yoldaki_urunler"] = [{"sku": URUNLER[i][0], "urun_adi": URUNLER[i][1], "yoldaki_miktar": 200,
                             "tahmini_varis_tarihi": _g(bugun + timedelta(days=12)),
                             "yoldaki_tedarikci": tedarikci[0], "yukleme_tarihi": _g(bugun)} for i in (0, 5)]

    # ── Muhasebe: banka, haftalık ödeme listesi, çek, tahsilat ──
    T["bankalar"] = [
        {"id": 1, "hesap_adi": "Örnek Bankası TL", "para_birimi": "TL", "bakiye": 2_845_300.0},
        {"id": 2, "hesap_adi": "Örnek Bankası USD", "para_birimi": "USD", "bakiye": 186_420.0},
        {"id": 3, "hesap_adi": "Deneme Katılım TL", "para_birimi": "TL", "bakiye": 612_950.0},
        {"id": 4, "hesap_adi": "Deneme Katılım EUR", "para_birimi": "EUR", "bakiye": 24_300.0},
    ]
    pzt = bugun - timedelta(days=bugun.weekday())
    T["haftalar"] = [{"id": 1, "hafta_adi": f"{pzt:%d.%m.%Y} GÜNCEL ÖDEME LİSTESİ",
                      "yuklendi_tarih": f"{pzt:%d.%m.%Y}", "aktif": 1}]
    kalemler = [("Örnek Lojistik A.Ş.", "cari", 185_000), ("Deneme Ambalaj Ltd.", "cari", 64_500),
                ("SGK prim ödemesi", "sgk", 212_000), ("KDV beyannamesi", "vergi", 348_000),
                ("Kira", "sabit", 95_000), ("Personel maaşları", "maas", 640_000),
                ("Gümrük müşaviri", "ithalat", 41_800), ("Elektrik ve internet", "masraf", 18_400),
                ("Örnek Kargo", "cari", 27_300), ("Çek ödemesi", "cek", 400_000)]
    T["odemeler"] = []
    for i, (firma, kat, tl) in enumerate(kalemler * 2):
        vade = bugun + timedelta(days=(i * 3) % 24 - 6)
        odendi = vade < bugun and i % 3 != 0
        T["odemeler"].append({"id": i + 1, "hafta_id": 1, "firma": firma, "aciklama": f"{firma} ödemesi",
                              "cari_banka": "Örnek Bankası TL", "vade": _g(vade), "tutar_tl": float(tl),
                              "tutar_usd": round(tl / KUR, 2), "kategori": kat, "manuel": 0,
                              "durum": "odendi" if odendi else "bekliyor",
                              "odendi_tarih": _g(vade) if odendi else None, "orijinal_vade": _g(vade),
                              "ertelendi_sayisi": 0, "banka_id": 1})
    T["cekler"] = [{"id": i + 1, "ref_no": f"C{i + 1:04d}", "vade": _g(bugun + timedelta(days=10 + i * 20)),
                    "meblagh": 150_000.0 + i * 25_000, "kalan": 150_000.0 + i * 25_000, "odenen": 0,
                    "alici": "Örnek Tedarik A.Ş.", "para_birimi": "TL", "durum": "Ciro edildi" if i else "Ödendi",
                    "cek_no": f"{700100 + i}", "tarih": _g(bugun - timedelta(days=30)), "ch_kodu": f"320.{i:02d}",
                    "ch_ismi": "Örnek Tedarik A.Ş.", "banka": "Örnek Bankası", "sube": "Merkez", "hesap_no": ""}
                   for i in range(5)]
    T["tahsilatlar"] = [{"id": i + 1, "banka_id": 1 + i % 2, "hesap_adi": T["bankalar"][i % 2]["hesap_adi"],
                         "para_birimi": T["bankalar"][i % 2]["para_birimi"],
                         "tutar": 120_000.0 + i * 15_000 if i % 2 == 0 else 8_000.0 + i * 500,
                         "kaynak": KANALLAR[i % 4][0], "aciklama": "Tahsilat",
                         "tarih": _g(bugun - timedelta(days=i * 4)), "created_at": _zaman(bugun)}
                        for i in range(12)]
    T["kur_gunluk"] = [{"tarih": _g(bugun - timedelta(days=i)), "usd_try": round(KUR - i * 0.03, 4)}
                       for i in range(60)]

    # ── Yönetim: destekler ──
    T["alinan_destekler"] = []
    for ay in range(1, 13):
        y = bugun.year if ay <= bugun.month else bugun.year - 1
        for firma, tur, tutar in (("D-MARKET", "ciro primi", 4200), ("VATAN", "kampanya desteği", 3100),
                                  ("INNO3D", "marka desteği", 5200)):
            T["alinan_destekler"].append({"firma": firma, "tur": tur, "donem": f"{y}-{ay:02d}",
                                          "tutar": tutar + ay * 90, "doviz": "USD", "kategori": "satis",
                                          "fatura_no": f"DS{y}{ay:02d}", "aciklama": "",
                                          "created_at": _zaman(bugun)})

    # ── Depo ──
    T["depo_sevk_log"] = [{"id": i + 1, "sku": URUNLER[i % 12][0], "urun_adi": URUNLER[i % 12][1],
                           "kaynak_depo": "MERKEZ DEPO", "hedef_depo": ["OUTLET DEPO", "SERVIS DEPO", "İKİNCİ EL DEPO"][i % 3],
                           "adet": 2 + i % 7, "kullanici": "ibrahim", "tarih": _g(bugun - timedelta(days=i * 2)),
                           "sevk_tarihi": _g(bugun - timedelta(days=i * 2)), "belge_no": f"SV{i + 1:04d}"}
                          for i in range(14)]
    T["stok_hareketleri"] = [{"id": i + 1, "zaman": _zaman(bugun - timedelta(days=i)), "sku": URUNLER[i % 12][0],
                              "depo": "MERKEZ DEPO", "onceki": 100, "sonraki": 100 - i, "degisim": -i,
                              "tur": "satis", "aciklama": "Satış düşümü", "kaynak": "excel",
                              "kullanici": "ibrahim", "basarili": True} for i in range(1, 15)]

    # ── Teknik servis ──
    T["ts_kayitlar"], T["ts_gecmis"] = [], []
    durum = ["mal kabül", "teknisyende", "tamir edildi", "satışa hazır", "gönderildi", "iade alındı", "hurda"]
    arizalar = ["Görüntü gelmiyor", "Fan sesi", "Açılmıyor", "Ölü piksel", "Okuma hatası", "Kayıt yapmıyor"]
    for i in range(24):
        sku, ad, kat, *_ = URUNLER[[0, 1, 5, 6, 9, 10, 11][i % 7]]
        d = bugun - timedelta(days=i * 5 + 1)
        T["ts_kayitlar"].append({
            "id": i + 1, "servis_form_no": f"TS-{2600 + i}", "arayuz": "web", "stok_kodu": sku, "stok_adi": ad,
            "urun_grubu": kat, "seri_no": f"SN{i:06d}", "ariza": arizalar[i % 6], "detay": "",
            "firma_bilgisi": KANALLAR[i % 4][0], "musteri_adi": f"Müşteri {i + 1}", "mevcut_durum": durum[i % 7],
            "depo": "SERVIS DEPO", "personel": "teknisyen", "mal_kabul_tarihi": _zaman(d),
            "olusturma_tarihi": _zaman(d), "bedelsiz": i % 4 == 0, "fatura_mevcut": True,
            "satis_tarihi": _g(d - timedelta(days=200)), "satis_fiyati": 100.0, "notlar": ""})
        T["ts_gecmis"].append({"id": i + 1, "kayit_id": i + 1, "durum": durum[i % 7], "aciklama": "",
                               "personel": "teknisyen", "tarih": _zaman(d)})

    # ── Ortak: talepler, bildirimler, görevler, ayarlar ──
    T["talepler"] = [{"id": 1, "gonderen": "ibrahim", "konu": "Stok raporu", "mesaj": "Haftalık stok raporu eklensin",
                      "durum": "bekliyor", "olusturma_tarihi": _zaman(bugun - timedelta(days=1)),
                      "kategori": "ozellik", "oncelik": "normal"}]
    T["gorevler"] = [{"id": 1, "baslik": "Ay sonu mutabakatı", "atayan": "ibrahim", "atanan": "ibrahim",
                      "oncelik": "yuksek", "durum": "bekliyor", "bitis_tarihi": _g(bugun + timedelta(days=3)),
                      "olusturma_tarihi": _zaman(bugun)}]
    T["sistem_ayarlari"] = [{"anahtar": "duyuru_aktif", "deger": "false"}]

    for ad, satirlar in T.items():
        if ad not in _ID_YOK:
            for i, s in enumerate(satirlar):
                s.setdefault("id", i + 1)
        tablolar[ad] = satirlar
    return tablolar
