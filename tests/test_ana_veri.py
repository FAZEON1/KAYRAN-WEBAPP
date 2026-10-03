# -*- coding: utf-8 -*-
"""shared/ana_veri — kategori/marka tek kaynak (Ekim 2026, entegrasyon Faz 1)."""

KURAL = ["Araç Kamerası", "Ekran Kartı", "Monitör", "Kablo/Konnektör", "CPU Soğutucu"]


def test_kategori_anahtari_yazim_farklarini_esitler():
    from shared.ana_veri import kategori_anahtar as a
    assert a("MONİTÖR") == a("MONITÖR") == a("monitör") == a(" Monitör ")
    assert a("KABLO / KONNEKTÖR") == a("Kablo/Konnektör") == a("kablo konnektör")
    assert a("Monitör") != a("Ekran Kartı") and a("") == ""


def test_kategori_ad_tek_yazim():
    from shared.ana_veri import kategori_ad
    assert kategori_ad("EKRAN KARTI", KURAL) == "Ekran Kartı"
    assert kategori_ad("MONITÖR", KURAL) == "Monitör"                # noktasız I'lı kayıt da
    assert kategori_ad("cpu soğutucu", KURAL) == "CPU Soğutucu"
    assert kategori_ad("KASA", KURAL) == "Kasa"                      # listede yok → baş harf büyük
    assert kategori_ad("İŞLEMCİ", ()) == "İşlemci" and kategori_ad("  ", KURAL) == ""


def test_kategori_secenekleri_ekran_karti_hic_ithal_edilmese_de_var():
    """Ekran görüntüsündeki hata: İthalat listesi yalnız eski ithalat kalemlerinden
    geliyordu. Havuz kural listesini + kartları + ithalatı birleştirir, tekrarsız."""
    from shared.ana_veri import kategori_secenekleri
    ithalat = ["ARAÇ KAMERASI", "CPU SOĞUTUCU", "KABLO/KONNEKTÖR", "KASA", "MICRO SD KART", "MONİTÖR", "MONITÖR"]
    kart = ["monitör", "kasa", "anti virüs"]
    s = kategori_secenekleri(kart, ithalat, kural_liste=KURAL)
    assert "Ekran Kartı" in s
    assert s.count("Monitör") == 1 and "MONİTÖR" not in s and "monitör" not in s
    assert "Kasa" in s and "Anti virüs" in s
    assert sum(1 for x in s if "sd kart" in x.lower()) == 1          # MICRO SD KART tek giriş


def test_gercek_kural_listesiyle_micro_sd_dogru_yazilir():
    """Tamamı büyük 'MICRO SD KART' Türkçe küçültmede 'Mıcro' olurdu; kural listesindeki
    'Micro SD Kart' bunu çözer (varsayılan kural listesi = kayranpm.database)."""
    from shared.ana_veri import kategori_secenekleri, kategori_ad_haritasi, kategori_ad
    from kayranpm.database import KATEGORI_LISTE
    s = kategori_secenekleri(["MICRO SD KART", "ANTİ VİRÜS"], kural_liste=KATEGORI_LISTE)
    assert "Micro SD Kart" in s and "Anti Virüs" in s and not any("Mıcro" in x for x in s)
    assert kategori_ad("MICRO SD KART", harita=kategori_ad_haritasi(kural_liste=KATEGORI_LISTE)) == "Micro SD Kart"
    assert len(s) == len({x.lower() for x in s})


def test_kayit_degeri_mevcut_yazimi_korur():
    """İthalat masraf dağıtımı adın BİREBİR eşleşmesine dayanır: 'Monitör' seçilip
    dosyada 'MONİTÖR' grubu varsa aynen 'MONİTÖR' yazılmalı, yeni grup açılmamalı."""
    from shared.ana_veri import kayit_degeri, tr_buyuk_harf
    mevcut = ["MONİTÖR", "KASA"]
    assert kayit_degeri("Monitör", mevcut, tr_buyuk_harf) == "MONİTÖR"
    assert kayit_degeri("Ekran Kartı", mevcut, tr_buyuk_harf) == "EKRAN KARTI"
    assert kayit_degeri("Micro sd kart", ["MICRO SD KART"], tr_buyuk_harf) == "MICRO SD KART"
    assert kayit_degeri("", mevcut, tr_buyuk_harf) == ""


def test_tr_buyuk_harf():
    from shared.ana_veri import tr_buyuk_harf
    assert tr_buyuk_harf("Monitör") == "MONİTÖR" and tr_buyuk_harf("Araç kamerası") == "ARAÇ KAMERASI"


def test_marka_tek_yazim_ve_secenek():
    from shared.ana_veri import marka_ad, marka_anahtar, marka_secenekleri
    k = ["FAZEON", "Mio", "INNO3D"]
    assert marka_anahtar("Fazeon") == marka_anahtar("FAZEON") and marka_anahtar("MIO") == marka_anahtar("Mio")
    assert marka_ad("fazeon", k) == "FAZEON" and marka_ad("MIO", k) == "Mio" and marka_ad("kaspersky", k) == "KASPERSKY"
    assert marka_secenekleri(["Fazeon", "FAZEON", "nzxt", "Kaspersky"], kural_liste=k) == \
        ["FAZEON", "INNO3D", "KASPERSKY", "Mio", "NZXT"]


def test_varsayilan_kural_listesi_kayranpm_den():
    from shared.ana_veri import kategori_ad, marka_ad
    assert kategori_ad("EKRAN KARTI") == "Ekran Kartı" and marka_ad("MIO") == "Mio"


def test_tamami_buyuk_yazimda_karisik_yazim_tercih_edilir():
    from shared.ana_veri import kategori_ad_haritasi, kategori_anahtar
    h = kategori_ad_haritasi(["MICRO SD KART"], ["Micro SD kart"], kural_liste=[])
    assert h[kategori_anahtar("micro sd kart")] == "Micro SD kart"


def test_kural_listesi_micro_sd_ve_anti_virus_iceriyor():
    """Verideki iki gerçek kategori kural listesine girdi: ekranda tek yazım +
    ürün adından öneri (Toplu Kategori)."""
    from kayranpm.database import kategori_oner, KATEGORI_LISTE
    assert "Micro SD Kart" in KATEGORI_LISTE and "Anti Virüs" in KATEGORI_LISTE
    assert kategori_oner("Kingston 64GB MicroSD Hafıza Kartı") == "Micro SD Kart"
    assert kategori_oner("KASPERSKY TOTAL SECURITY 1 KULLANICI") == "Anti Virüs"
    assert kategori_oner("Samsung 1TB NVMe SSD") == "SSD"


# ═══════════════════════════════════════════════════════════
#  Tek kaynak koruması — ekranlar ana_veri'den okumaya devam etsin
# ═══════════════════════════════════════════════════════════
import pathlib
import re

KOK = pathlib.Path(__file__).resolve().parent.parent


def _oku(yol):
    return (KOK / yol).read_text(encoding="utf-8")


def test_ithalat_kategori_secenekleri_havuzdan():
    """Ekran görüntüsündeki hata: İthalat kategori listesi get_kategoriler()'den (yalnız eski
    ithalat kalemleri) geliyordu, Ekran Kartı yoktu. Seçenekler havuzdan, kayıt kayit_degeri ile."""
    s = _oku("ithalat/main.py")
    assert s.count("_kat_havuz = get_kategori_havuzu()") == 2
    assert "_kat_havuz = get_kategoriler()" not in s
    assert s.count("kayit_degeri(") >= 2
    # Yeni kategori Python .upper() ile yazılmasın ('monitör' → noktasız 'MONITÖR')
    assert 'placeholder="yeni kategori").strip().upper()' not in s
    assert 'label_visibility="collapsed").strip().upper()' not in s


def test_ekranlar_tek_yazim_kullaniyor():
    zorunlu = {
        "ithalat/main.py": "kategori_ad",
        "kayranpm/urun_hesap.py": "kategori_ad",
        "kayranpm/genel_hesap.py": "kategori_ad",
        "kayranpm/genel_bakis.py": "kategori_ad",
        "kayranpm/stok_karti.py": "kategori_ad",
        "kayranpm/kampanya.py": "kategori_ad",
        "kayranpm/kampanya_hesap.py": "kategori_anahtar",
        "kayranpm/ref_ekran.py": "get_kategori_havuzu",
        "kayranpm/main.py": "kategori_anahtar",
        "kayranpm/rapor.py": "kategori_ad",
        "satis/satislar_ekran.py": "kategori_ad",
        "satis/main.py": "kategori_anahtar",
        "kayranpm/musteri_hesap.py": "shared.ana_veri",
    }
    eksik = [y for y, ad in zorunlu.items() if ad not in _oku(y)]
    assert not eksik, f"ana_veri bağlantısı kaybolmuş (eski sürüm mü yüklendi?): {eksik}"


def test_kategori_yazimi_capitalize_ile_yapilmiyor():
    """.capitalize() 'cpu soğutucu' → 'Cpu soğutucu', 'İŞLEMCİ' → 'İşlemci̇' yapar; tek yazım değil."""
    for y in ("kayranpm/kampanya.py", "kayranpm/ref_ekran.py"):
        assert not re.search(r'get\("kategori"\).*\.capitalize\(\)', _oku(y)), y


# ═══════════════════════════════════════════════════════════
#  Ürün adı — kart adı tek kaynak (Faz 4b)
# ═══════════════════════════════════════════════════════════
def test_urun_ad_kart_adi_oncelikli():
    from shared.ana_veri import urun_ad
    h = {"X24F165S": "FAZEON 24 INÇ MONITÖR", "K1": "KASA K1"}
    assert urun_ad("Fazeon X24F165S", "fazeon monitor 24 hepsiburada", harita=h) == "FAZEON 24 INÇ MONITÖR"
    assert urun_ad(" x24f165s ", "", harita=h) == "FAZEON 24 INÇ MONITÖR"
    assert urun_ad("YOK1", "Satırdaki Ad", harita=h) == "SATIRDAKI AD"      # kart yok → satır adı, BÜYÜK
    assert urun_ad("YOK2", None, harita=h) == "" and urun_ad(None, "", harita={}) == ""


def test_ekranlar_urun_adini_karttan_aliyor():
    zorunlu = {"satis/satislar_ekran.py": 3, "satis/main.py": 8, "depo/main.py": 1, "depo/bekleyen_ekran.py": 1,
               "ithalat/main.py": 1, "kayranpm/musteri_ekran.py": 3, "kayranpm/kampanya.py": 1}
    eksik = {y: n for y, n in zorunlu.items() if len(re.findall(r"\b_?urun_ad\(", _oku(y))) < n}
    assert not eksik, f"Ürün adı yeniden satırdan basılıyor (eski sürüm mü yüklendi?): {eksik}"
