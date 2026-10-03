# -*- coding: utf-8 -*-
"""Müşteri Satışları (Ekim 2026): dört kırılım (müşteri / marka / ürün / kategori),
yan yana liste + detay. Stok TOPLANMAZ: her (müşteri, SKU) için aralıktaki SON rapor
(eskiden 40 haftalık aralıkta 40 raporun stoğu üst üste ekleniyordu)."""
import pytest

R = [  # 2 hafta · VATAN: K100, F12 · EERA: K100
    {"firma": "VATAN", "sku": "K100", "urun_adi": "Kasa", "haftalik_satis": 10, "satis_magaza": 2,
     "stok_miktari": 100, "stok_magaza": 0, "yukleme_tarihi": "2026-09-21"},
    {"firma": "VATAN", "sku": "K100", "urun_adi": "Kasa", "haftalik_satis": 20, "satis_magaza": 0,
     "stok_miktari": 80, "stok_magaza": 0, "yukleme_tarihi": "2026-09-28"},
    {"firma": "VATAN", "sku": "F12", "urun_adi": "Fan", "haftalik_satis": 5, "satis_magaza": 0,
     "stok_miktari": 30, "stok_magaza": 5, "yukleme_tarihi": "2026-09-28"},
    {"firma": "EERA", "sku": "K100", "urun_adi": "Kasa", "haftalik_satis": 3, "satis_magaza": 0,
     "stok_miktari": 40, "stok_magaza": 0, "yukleme_tarihi": "2026-09-21"},
]
META = {"K100": {"marka": "Fazeon", "kategori": "Kasa"}, "F12": {"marka": "", "kategori": ""}}
AD = {"VATAN": "VATAN BİLGİSAYAR SANAYİ VE TİCARET A.Ş.", "EERA": "EERA ELEKTRONİK LTD. ŞTİ."}


def _g(k, rows=R):
    from kayranpm.musteri_hesap import grupla
    return {x["anahtar"]: x for x in grupla(rows, k, META, ad_fn=lambda c: AD.get(c, c))}


def test_musteri_kirilimi_ve_tam_cari_adi():
    g = _g("musteri")
    assert g["VATAN"]["ad"] == AD["VATAN"] and g["VATAN"]["satis"] == 37 and g["EERA"]["satis"] == 3
    assert g["VATAN"]["stok"] == 80 + 35          # K100 son rapor 80 (100 + 80 DEĞİL) + F12 35
    assert g["EERA"]["stok"] == 40
    assert g["VATAN"]["pay"] == pytest.approx(37 / 40 * 100)


def test_haftalik_ortalama_kapsama_seri():
    g = _g("musteri")
    assert g["VATAN"]["haftalik_ort"] == pytest.approx(37 / 2)            # aralıkta 2 hafta
    assert g["VATAN"]["kapsama"] == pytest.approx(115 / (37 / 2))
    assert g["VATAN"]["seri"] == [12, 25]


def test_marka_kategori_bos_olanlar():
    m, k = _g("marka"), _g("kategori")
    assert m["Fazeon"]["satis"] == 35 and m["Markasız"]["satis"] == 5
    assert k["Kasa"]["satis"] == 35 and k["Kategorisiz"]["satis"] == 5


def test_urun_kirilimi_tum_musterilerin_son_stoklari():
    u = _g("urun")
    assert u["K100"]["satis"] == 35 and u["K100"]["stok"] == 80 + 40 and u["K100"]["urun_adi"] == "Kasa"


def test_siralama_satisa_gore():
    from kayranpm.musteri_hesap import grupla
    assert [x["anahtar"] for x in grupla(R, "musteri", META)] == ["VATAN", "EERA"]


def test_detay_alt_kirilim():
    from kayranpm.musteri_hesap import detay, ALT
    assert ALT == {"musteri": "urun", "urun": "musteri", "marka": "urun", "kategori": "urun"}
    d = {x["anahtar"]: x for x in detay(R, "musteri", "VATAN", META)}
    assert set(d) == {"K100", "F12"} and d["K100"]["satis"] == 32 and d["K100"]["stok"] == 80
    d2 = {x["anahtar"]: x for x in detay(R, "urun", "K100", META, ad_fn=lambda c: AD.get(c, c))}
    assert d2["EERA"]["ad"] == AD["EERA"] and d2["EERA"]["stok"] == 40
    d3 = detay(R, "marka", "Fazeon", META)
    assert [x["anahtar"] for x in d3] == ["K100"]


def test_ozet():
    from kayranpm.musteri_hesap import ozet
    o = ozet(R)
    assert o["satis"] == 40 and o["stok"] == 80 + 35 + 40 and o["hafta"] == 2
    assert o["haftalik_ort"] == 20 and o["kapsama"] == pytest.approx(155 / 20)
    assert ozet([])["satis"] == 0 and ozet([])["kapsama"] is None


def test_sayfa_yeni_ekrana_bagli():
    from pathlib import Path
    s = (Path(__file__).resolve().parent.parent / "kayranpm/main.py").read_text(encoding="utf-8")
    i = s.index('elif sayfa == "📈  Müşteri Satışları":')
    g = s[i:s.index('elif sayfa == "🎯  Kampanya Takip":')]
    assert "musteri_ekran" in g and "Ham detay" not in g and "_df['Stok'].sum()" not in g
    e = (Path(__file__).resolve().parent.parent / "kayranpm/musteri_ekran.py").read_text(encoding="utf-8")
    for ad in ("Müşteri", "Marka", "Ürün", "Kategori"):
        assert f'"{ad}"' in e
    assert "kalici=True" in e


# ═══════════════════════════════════════════════════════════
#  meta_hazirla — kategori stok kartından (Ekim 2026)
#  Eskiden meta HAM SKU ile aranıyordu: rapor 'Fazeon X24F165S' yazınca kart
#  ('X24F165S') bulunamıyor, ürün 'Kategorisiz' görünüyordu.
# ═══════════════════════════════════════════════════════════

KARTLAR = {
    "X24F165S": {"marka": "FAZEON", "kategori": "MONİTÖR", "urun_adi": "Fazeon 24 inç 165Hz Monitör"},
    "K100":     {"marka": "Fazeon", "kategori": "kasa", "urun_adi": "Fazeon K100 Kasa"},
    "F12":      {"marka": "", "kategori": "", "urun_adi": "Fazeon 120mm RGB FAN"},
    "AV1":      {"marka": "Kaspersky", "kategori": "Anti Virüs", "urun_adi": "Kaspersky Total Security"},
    "KBL1":     {"marka": "X", "kategori": "KABLO/KONNEKTÖR", "urun_adi": "Kablo"},
}


def _mh(rows, oner=True):
    from shared.utils import sku_anahtar
    from kayranpm.database import kategori_oner, KATEGORI_LISTE
    from kayranpm.musteri_hesap import meta_hazirla
    return meta_hazirla(rows, KARTLAR, sku_fn=sku_anahtar, oner=kategori_oner if oner else None,
                        kategori_liste=KATEGORI_LISTE)


def _r(sku, ad="", satis=1):
    return {"firma": "VATAN", "sku": sku, "urun_adi": ad, "haftalik_satis": satis,
            "stok_miktari": 0, "yukleme_tarihi": "2026-09-28"}


def test_birebir_sku_karttan_kategori_alir():
    m = _mh([_r("K100")])
    assert m["K100"]["kategori"] == "Kasa" and m["K100"]["kategori_kaynak"] == "kart"
    assert m["K100"]["kart_sku"] == "K100"


def test_onekli_ve_kucuk_harf_sku_karti_bulur():
    m = _mh([_r("Fazeon X24F165S"), _r(" x24f165s ")])
    for k in ("Fazeon X24F165S", "x24f165s"):
        assert m[k]["kategori"] == "Monitör" and m[k]["marka"] == "FAZEON"
        assert m[k]["kart_sku"] == "X24F165S"


def test_sku_parcasi_karti_bulur():
    m = _mh([_r("X24F165S-SIYAH")])
    assert m["X24F165S-SIYAH"]["kart_sku"] == "X24F165S"


def test_kisa_parca_yanlis_eslesmez():
    """≥5 karakter kuralı: kısa kodlar (ör. 'F12') başka bir SKU'nun parçası diye yanlış karta bağlanmaz."""
    m = _mh([_r("ABC F12")], oner=False)
    assert m["ABC F12"]["kart_sku"] == ""


def test_sku_tutmazsa_urun_adi_ile_bulur():
    m = _mh([_r("VTN-998877", "KASPERSKY  total security")])
    assert m["VTN-998877"]["kart_sku"] == "AV1" and m["VTN-998877"]["kategori"] == "Anti Virüs"   # kural listesinde (Faz 1)


def test_kartta_kategori_bossa_addan_tahmin():
    m = _mh([_r("F12")])
    assert m["F12"]["kategori"] == "Fan" and m["F12"]["kategori_kaynak"] == "tahmin"


def test_kart_hic_yoksa_rapor_adindan_tahmin():
    m = _mh([_r("YENI1", "Gaming Mouse Pad XL")])
    assert m["YENI1"]["kategori"] == "Mouse Pad" and m["YENI1"]["kategori_kaynak"] == "tahmin"


def test_hicbir_yol_tutmazsa_kategorisiz_kalir():
    from kayranpm.musteri_hesap import grupla
    rows = [_r("ZZZ999", "Tanımsız ürün")]
    m = _mh(rows)
    assert m["ZZZ999"]["kategori"] == "" and m["ZZZ999"]["kategori_kaynak"] == ""
    assert grupla(rows, "kategori", m)[0]["anahtar"] == "Kategorisiz"


def test_yazim_farklari_tek_kategoride_birlesir():
    from kayranpm.musteri_hesap import grupla, kategori_etiketi
    from kayranpm.database import KATEGORI_LISTE
    assert kategori_etiketi("KABLO/KONNEKTÖR", KATEGORI_LISTE) == "Kablo/Konnektör"
    assert kategori_etiketi("İŞLEMCİ") == "İşlemci"
    kartlar = {"A1": {"kategori": "MONİTÖR"}, "A2": {"kategori": "monitör"}, "A3": {"kategori": "Monitör"}}
    from kayranpm.musteri_hesap import meta_hazirla
    rows = [_r("A1", satis=1), _r("A2", satis=2), _r("A3", satis=3)]
    g = grupla(rows, "kategori", meta_hazirla(rows, kartlar, kategori_liste=KATEGORI_LISTE))
    assert [(x["anahtar"], x["satis"]) for x in g] == [("Monitör", 6)]


def test_kategori_kirilimi_onekli_skuyu_dogru_gruba_koyar():
    from kayranpm.musteri_hesap import grupla
    rows = [_r("Fazeon X24F165S", satis=4), _r("X24F165S", satis=6), _r("K100", satis=1)]
    g = {x["anahtar"]: x["satis"] for x in grupla(rows, "kategori", _mh(rows))}
    assert g == {"Monitör": 10, "Kasa": 1}


# ═══════════════════════════════════════════════════════════
#  Markasız (Ekim 2026, 2. tur) — pazaryeri kodu SKU olarak geliyor
#  Hepsiburada raporunda SKU 'HBCV0000G0F6K6', model kodu yalnız ADDA:
#  'Fazeon 23.8' X24F180 …'. Kart SKU'su da adı da tutmadığı için ürün
#  'Markasız' + 'Kategorisiz' kalıyordu (ekranda 278 adet).
# ═══════════════════════════════════════════════════════════

KARTLAR2 = {
    "X24F180":  {"marka": "FAZEON", "kategori": "monitör", "urun_adi": "FAZEON X24F180 23.8 MONİTÖR"},
    "X27F300S": {"marka": "Fazeon", "kategori": "Monitör", "urun_adi": "Fazeon X27F300 Siyah"},
    "X27F300B": {"marka": "Fazeon", "kategori": "Monitör", "urun_adi": "Fazeon X27F300 Beyaz"},
    "X32F240S": {"marka": "", "kategori": "", "urun_adi": "X32F240S"},
    "AB12345":  {"marka": "Mio", "kategori": "Araç Kamerası", "urun_adi": "Mio A"},
    "AB12399":  {"marka": "NZXT", "kategori": "Kasa", "urun_adi": "NZXT B"},
}


def _mh2(rows):
    from shared.utils import sku_anahtar
    from kayranpm.database import kategori_oner, marka_oner, KATEGORI_LISTE, MARKA_KURALLAR
    from kayranpm.musteri_hesap import meta_hazirla
    return meta_hazirla(rows, KARTLAR2, sku_fn=sku_anahtar, oner=kategori_oner, kategori_liste=KATEGORI_LISTE,
                        marka_oner=marka_oner, marka_liste=[m for m, _ in MARKA_KURALLAR])


def test_pazaryeri_kodu_adindaki_model_koduyla_eslesir():
    m = _mh2([_r("HBCV0000G0F6K6", "Fazeon 23.8' X24F180 FHD 180Hz Monitör")])["HBCV0000G0F6K6"]
    assert m["kart_sku"] == "X24F180" and m["marka"] == "FAZEON" and m["kategori"] == "Monitör"
    assert m["marka_kaynak"] == "kart"


def test_adda_renk_eki_olmayan_model_tek_markaya_cikiyorsa_eslesir():
    """'X27F300' → X27F300S ve X27F300B; ikisi de Fazeon/Monitör → belirsizlik zararsız."""
    m = _mh2([_r("HBCV00007TAN7S", "FAZEON X27F300 27 inç")])["HBCV00007TAN7S"]
    assert m["marka"] == "FAZEON" and m["kategori"] == "Monitör"


def test_onek_adaylari_farkli_markaya_cikiyorsa_eslesmez():
    """'AB123' iki farklı markalı karta uyuyor → tahmine düşer, yanlış karta bağlanmaz."""
    m = _mh2([_r("HB1", "Ürün AB123 xx")])["HB1"]
    assert m["kart_sku"] == "" and m["marka"] != "Mio" and m["marka"] != "NZXT"


def test_kartta_marka_bossa_addan_tahmin():
    m = _mh2([_r("HBCV0000EIYXVR", "Fazeon X32F240S 32 inç")])["HBCV0000EIYXVR"]
    assert m["kart_sku"] == "X32F240S"
    assert m["marka"] == "FAZEON" and m["marka_kaynak"] == "tahmin"


def test_kart_yoksa_marka_addan_tahmin():
    m = _mh2([_r("HB-YOK", "INNO3D GeForce RTX 4060")])["HB-YOK"]
    assert m["marka"] == "INNO3D" and m["marka_kaynak"] == "tahmin" and m["kategori"] == "Ekran Kartı"


def test_marka_yazimlari_tek_satirda_birlesir():
    from kayranpm.musteri_hesap import grupla, marka_etiketi
    assert marka_etiketi("fazeon", ["FAZEON", "Mio"]) == "FAZEON"
    assert marka_etiketi("MIO", ["FAZEON", "Mio"]) == "Mio"
    assert marka_etiketi("kaspersky") == "KASPERSKY"
    rows = [_r("X27F300S", satis=2), _r("X24F180", satis=3)]
    g = grupla(rows, "marka", _mh2(rows))
    assert [(x["anahtar"], x["satis"]) for x in g] == [("FAZEON", 5)]


def test_urun_gorunumu_kaldirildi_detay_duruyor():
    """'Ürün' seçeneği kalktı; marka/kategori detayında ürün listesi sürüyor."""
    import pathlib, re
    s = (pathlib.Path(__file__).resolve().parent.parent / "kayranpm" / "musteri_ekran.py").read_text(encoding="utf-8")
    gor = re.search(r"^GORUNUM = (\{.*\})$", s, re.M).group(1)
    assert "Ürün" not in gor and "Marka" in gor and "Kategori" in gor
    from kayranpm.musteri_hesap import ALT
    assert ALT["marka"] == "urun" and ALT["kategori"] == "urun"
