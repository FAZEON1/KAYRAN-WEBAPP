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
