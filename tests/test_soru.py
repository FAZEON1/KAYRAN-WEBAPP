# -*- coding: utf-8 -*-
"""Soru kutusu (Ekim 2026): Türkçe soru → parçalar → mevcut hesaplardan cevap.

İki şey denetlenir:
1. Çözümleyici: örnek sorular doğru parçalara ayrılıyor (dönem, firma, kategori, marka, ölçü,
   kırılım, sıra). Ad listeleri veriden gelir; burada sahte bir sözlük var.
2. Cevap: rakam yeniden hesaplanmıyor — P&L / stok yaşı / arıza / kampanya fonksiyonlarının
   verdiği sayı birebir aynı. Yetki ve kâr gizleme kuralları geçerli.
"""
from datetime import date

import pytest

BUGUN = date(2026, 10, 4)

SOZLUK = {
    "firmalar": {"D-MARKET ELEKTRONİK HİZMETLER": ["D-MARKET ELEKTRONİK HİZMETLER VE TİCARET A.Ş."],
                 "EERA BİLGİSAYAR": ["EERA BİLGİSAYAR LTD. ŞTİ. USD", "EERA BİLGİSAYAR LTD. ŞTİ."],
                 "VATAN BİLGİSAYAR": ["VATAN BİLGİSAYAR A.Ş."]},
    "kategoriler": ["MONİTÖR", "KASA", "KLAVYE", "MOUSE", "KULAKLIK", "OYUNCU KOLTUĞU", "SSD", "DİĞER"],
    "markalar": ["FAZEON", "ASUS", "MIO", "KASPERSKY"],
    "skular": {"X27F330UDP": "X27F330UDP", "K1": "K1"},
}


def _c(metin):
    from shared.soru import coz
    return coz(metin, SOZLUK, BUGUN)


# ── 1. Çözümleyici ──────────────────────────────────────────────────
@pytest.mark.parametrize("metin, beklenen", [
    ("Geçen ay D-MARKET'te en çok kâr bıraktıran 5 monitör",
     dict(tip="satis", olcu="net_kar", kirilim="urun", firma="D-MARKET ELEKTRONİK HİZMETLER", kategori="MONİTÖR",
          sira="azalan", limit=5, donem=("2026-09-01", "2026-09-30"))),
    ("hepsiburada eylül cirosu", dict(tip="satis", olcu="ciro", firma="D-MARKET ELEKTRONİK HİZMETLER",
                                       donem=("2026-09-01", "2026-09-30"), kirilim=None)),
    ("HB geçen hafta kaç adet sattık", dict(tip="satis", olcu="adet", donem=("2026-09-21", "2026-09-27"))),
    ("itopya q3 kâr", dict(tip="satis", olcu="net_kar", firma="EERA BİLGİSAYAR", donem=("2026-07-01", "2026-09-30"))),
    ("vatanda bu ay ne sattık", dict(tip="satis", firma="VATAN BİLGİSAYAR", donem=("2026-10-01", "2026-10-04"))),
    ("Bu yıl firmalara göre ciro", dict(tip="satis", olcu="ciro", kirilim="firma", limit=None,
                                        donem=("2026-01-01", "2026-10-04"))),
    ("en az kâr bırakan firmalar", dict(tip="satis", kirilim="firma", sira="artan", donem_varsayilan=True)),
    ("2025 en çok satan 10 ürün", dict(tip="satis", olcu="adet", kirilim="urun", limit=10,
                                        donem=("2025-01-01", "2025-12-31"))),
    ("son 90 gün en çok satılan klavyeler", dict(tip="satis", olcu="adet", kategori="KLAVYE", kirilim="urun",
                                                  donem=("2026-07-07", "2026-10-04"))),
    ("Fazeon kasaların marjı", dict(tip="satis", olcu="marj", kategori="KASA", marka="FAZEON")),
    ("oyuncu koltuğu satışları", dict(tip="satis", kategori="OYUNCU KOLTUĞU")),
    ("kategorilere göre net kâr geçen yıl", dict(tip="satis", kirilim="kategori", donem=("2025-01-01", "2025-12-31"))),
    ("markalara göre ciro 2. çeyrek", dict(tip="satis", kirilim="marka", donem=("2026-04-01", "2026-06-30"))),
    ("bu yıl aylık net kâr", dict(tip="seyir", olcu="net_kar", kirilim="ay")),
    ("asus ay ay ciro", dict(tip="seyir", olcu="ciro", marka="ASUS")),
    ("Bu çeyrek en çok iade edilen ürünler", dict(tip="iade", kirilim="urun", donem=("2026-10-01", "2026-10-04"))),
    ("geçen ay iadeler", dict(tip="iade", donem=("2026-09-01", "2026-09-30"))),
    ("120 günü geçen stok", dict(tip="yasli_stok", esik=120)),
    ("stokta 120 günü geçen ürünlerin maliyeti", dict(tip="yasli_stok", esik=120)),
    ("yaşlı stok", dict(tip="yasli_stok", esik=90)),
    ("monitör stoğu ne kadar", dict(tip="stok", kategori="MONİTÖR")),
    ("kategorilere göre stok", dict(tip="stok", kirilim="kategori")),
    ("bu çeyrek arıza oranı en yüksek 10 model", dict(tip="ariza", kirilim="urun", limit=10, sira="azalan")),
    ("markalara göre arıza oranı", dict(tip="ariza", kirilim="marka")),
    ("süren kampanyalar", dict(tip="kampanya", kampanya_durum="suruyor")),
    ("D-MARKET kapanmayı bekleyen kampanyalar", dict(tip="kampanya", kampanya_durum="bekliyor",
                                                     firma="D-MARKET ELEKTRONİK HİZMETLER")),
    ("vadesi geçen ödemeler", dict(tip="odeme", kapsam="gecikmis")),
    ("bu hafta ne ödeyeceğiz", dict(tip="odeme", kapsam="hafta")),
    ("bugün ödenecekler", dict(tip="odeme", kapsam="bugun")),
    ("bekleyen çekler", dict(tip="cek")),
    ("X27F330UDP", dict(tip="urun", sku="X27F330UDP")),
])
def test_cozumleyici(metin, beklenen):
    n = _c(metin)
    for k, v in beklenen.items():
        if k == "donem":
            assert (str(n["donem"]["bas"]), str(n["donem"]["bit"])) == v, (metin, n["donem"])
        else:
            assert n[k] == v, (metin, k, n[k])


@pytest.mark.parametrize("metin", ["kargo ne zaman gelir", "merhaba", "", "toplantı saat kaçta"])
def test_anlasilmayan(metin):
    assert _c(metin)["tip"] is None


def test_turkce_harf_ve_ek_toleransi():
    from shared.soru import sade
    assert sade("D-MARKET'te MONİTÖRLER İçin") == "d-market te monitorler icin"
    assert _c("MONİTÖRLERDE en çok kâr")["kategori"] == "MONİTÖR"
    assert _c("monitorlerde en cok kar")["kategori"] == "MONİTÖR"


@pytest.mark.parametrize("metin, kat", [
    ("bu yıl araç kameraları cirosu", "Araç kamerası"), ("ekran kartlarının kârı", "Ekran kartı"),
    ("cpu soğutucular en çok satan", "CPU soğutucu"), ("ssdler stok", "SSD"), ("ram stoğu", "RAM"),
    ("kasaların marjı", "Kasa"), ("mouse pad satışları", "Mouse pad"),
])
def test_gercek_kategori_adlari_cekimli(metin, kat):
    from shared.soru import coz
    s = dict(SOZLUK, kategoriler=["Kasa", "Monitör", "Ekran kartı", "Araç kamerası", "CPU soğutucu", "SSD",
                                  "RAM", "Mouse pad", "Ekran koruyucu", "Diğer"])
    assert coz(metin, s, BUGUN)["kategori"] == kat


def test_siradan_kelime_kategori_sanilmaz():
    # 'DİĞER' kategori adı ama sıradan kelime: "diğer firmalar" kategori süzgeci kurmamalı
    assert _c("diğer firmalara göre ciro")["kategori"] is None


def test_ayni_ilk_kelimeli_cariler_birlikte():
    from shared.soru import coz
    s = dict(SOZLUK, firmalar={"EERA BİLGİSAYAR": ["EERA BİLGİSAYAR LTD. ŞTİ."],
                               "EERA ELEKTRONİK": ["EERA ELEKTRONİK TİCARET A.Ş."],
                               "TEKNİK SERVİS / 2.EL": ["TEKNİK SERVİS / 2.EL"],
                               "MONİTÖR DÜNYASI": ["MONİTÖR DÜNYASI LTD."]})
    n = coz("eera bu yıl ciro", s, BUGUN)
    assert sorted(n["kanallar"]) == ["EERA BİLGİSAYAR LTD. ŞTİ.", "EERA ELEKTRONİK TİCARET A.Ş."]
    assert coz("teknik servis iadeleri", s, BUGUN)["firma"] is None        # sıradan kelime
    n = coz("monitör satışları", s, BUGUN)
    assert n["firma"] is None and n["kategori"] == "MONİTÖR"                # kategori adı firma sanılmaz


def test_parcalar_okunur():
    from shared.soru import parcalar
    p = dict(parcalar(_c("Geçen ay D-MARKET'te en çok kâr bıraktıran 5 monitör")))
    assert p["Konu"] == "Satış" and p["Ölçü"] == "Net kâr" and p["Dönem"] == "Eylül 2026"
    assert p["Kategori"] == "MONİTÖR" and p["Sıra"] == "En yüksek 5"
    assert "varsayılan" in dict(parcalar(_c("en çok satan ürünler")))["Dönem"]


# ── 2. Cevap: aynı fonksiyon, aynı sayı ─────────────────────────────
SAT = [
    {"tarih": "2026-09-05", "kanal": "VATAN BİLGİSAYAR A.Ş.", "sku": "K1", "urun_adi": "Kasa", "adet": 10,
     "birim_satis": 50, "birim_maliyet": 30, "birim_firma_destek": 0, "birim_ek_destek": 0},
    {"tarih": "2026-09-10", "kanal": "EERA BİLGİSAYAR LTD. ŞTİ.", "sku": "F1", "urun_adi": "Fan", "adet": 20,
     "birim_satis": 10, "birim_maliyet": 6, "birim_firma_destek": 1, "birim_ek_destek": 0},
    {"tarih": "2026-09-12", "kanal": "EERA BİLGİSAYAR LTD. ŞTİ. USD", "sku": "M1", "urun_adi": "Monitör", "adet": 5,
     "birim_satis": 200, "birim_maliyet": 150, "birim_firma_destek": 10, "birim_ek_destek": 0},
]
IADE = [{"kanal": "VATAN BİLGİSAYAR A.Ş.", "sku": "K1", "iade_net": 50, "iade_adet": 1}]
KARTLAR = {"K1": {"sku": "K1", "urun_adi": "Oyun kasası", "kategori": "KASA", "marka": "FAZEON", "bizim_stok": 7},
           "F1": {"sku": "F1", "urun_adi": "Fan", "kategori": "FAN", "marka": "ASUS", "bizim_stok": 0},
           "M1": {"sku": "M1", "urun_adi": "Monitör 27", "kategori": "MONİTÖR", "marka": "FAZEON", "bizim_stok": 3}}
PACAL = {"K1": 30.0, "F1": 6.0, "M1": 150.0}


class SahteKaynak:
    """satis.pnl_hesap.Kaynak yerine (test_satis_pnl ile aynı biçim)."""
    def satislar(self, bas, bit): return SAT
    def katmap(self): return {k: v["kategori"] for k, v in KARTLAR.items()}
    def iade_ozet(self, bas, bit): return ([{"sku": "K1", "i_adet": 1, "i_tutar": 50.0, "i_kar": 20.0}],
                                           {"i_tutar": 50.0, "i_kar": 20.0, "i_adet": 1})
    def iade_kanal(self, bas, bit): return {"VATAN BİLGİSAYAR A.Ş.": {"i_tutar": 50.0, "i_kar": 20.0}}
    def iadeler(self, bas, bit): return IADE
    def pacal(self): return PACAL
    def ref_tutarlari(self, bas, bit): return [{"tutar": 100, "doviz": "USD", "tarih": "2026-09-03"}]
    def alinan(self, bas, bit): return 40.0
    def alinan_kirilim(self, bas, bit): return ({}, {}, 0.0)
    def ref_kirilim(self, bas, bit): return {"kategori": {}, "dagitilmayan": []}
    def kur_haritasi(self, bas, bit): return {}
    def yedek_kur(self): return 40.0


class SahteVeri:
    def pnl(self, bas, bit, kanal, kat):
        from satis.pnl_hesap import satis_pnl
        return satis_pnl(bas, bit, kanal or "Tümü", kat or "Tümü", SahteKaynak())

    def satislar(self, bas, bit): return SAT
    def iadeler(self, bas, bit): return IADE
    def pacal(self): return PACAL
    def kartlar(self): return KARTLAR

    def stok_yasi(self):
        oz = {"stok": 7, "en_eski_gun": 200, "en_eski_tarih": "2026-03-18"}
        return {"bizim": {"K1": (oz, [{"tarih": "2026-03-18", "kalan": 5}, {"tarih": "2026-09-20", "kalan": 2}],
                                 KARTLAR["K1"])}, "bugun": BUGUN}

    def ariza(self, bas, bit):
        return {"satirlar": [
            {"SKU": "K1", "Ürün": "Oyun kasası", "Kategori": "KASA", "Marka": "FAZEON", "Son kullanıcıya ulaşan": 100,
             "Servise gelen": 4, "Arızalı": 3, "Arıza oranı (%)": 3.0},
            {"SKU": "M1", "Ürün": "Monitör 27", "Kategori": "MONİTÖR", "Marka": "FAZEON", "Son kullanıcıya ulaşan": 50,
             "Servise gelen": 6, "Arızalı": 5, "Arıza oranı (%)": 10.0},
            {"SKU": "F1", "Ürün": "Fan", "Kategori": "FAN", "Marka": "ASUS", "Son kullanıcıya ulaşan": 80,
             "Servise gelen": 0, "Arızalı": 0, "Arıza oranı (%)": 0.0}]}

    def kampanyalar(self):
        k = [{"id": 1, "kampanya_adi": "Eylül monitör", "firma": "HB", "baslangic_tarihi": "2026-09-01",
              "bitis_tarihi": "2026-12-31", "durum": "aktif", "kategori": "MONİTÖR"},
             {"id": 2, "kampanya_adi": "Yaz kasa", "firma": "VATAN", "baslangic_tarihi": "2026-06-01",
              "bitis_tarihi": "2026-08-31", "durum": "aktif", "kategori": "KASA"}]
        ku = {1: [{"sku": "M1", "satis_fiyati": 200, "birim_firma_destek": 10, "birim_ek_destek": 0,
                   "satilan_adet": 5, "pacal_maliyet": 150}],
              2: [{"sku": "K1", "satis_fiyati": 50, "birim_firma_destek": 0, "birim_ek_destek": 0,
                   "satilan_adet": 10, "pacal_maliyet": 30}]}
        return k, ku, PACAL

    def odemeler(self, kapsam):
        return [{"firma": "AYKON", "vade": "2026-09-30", "tutar_tl": 1000, "tutar_usd": 0, "durum": "bekliyor"},
                {"firma": "BANKA", "vade": "2026-10-04", "tutar_tl": 0, "tutar_usd": 300, "durum": "bekliyor"},
                {"firma": "ESKI", "vade": "2026-09-01", "tutar_tl": 999, "tutar_usd": 0, "durum": "odendi"}]

    def cekler(self):
        return [{"ch_ismi": "AYKON", "vade": "2026-11-01", "meblagh": 5000, "odenen": 0, "kalan": 5000,
                 "durum": "Bekliyor", "_pb": "TL"},
                {"ch_ismi": "ESKI", "vade": "2026-08-01", "meblagh": 100, "odenen": 100, "kalan": 0,
                 "durum": "Ödendi", "_pb": "TL"}]


TAM = {"satis": True, "kayranpm": True, "teknikservis": True, "kayranacc": True, "kar": True}


def _cevap(metin, izin=None):
    from shared.soru_cevap import cevapla
    return cevapla(_c(metin), TAM if izin is None else izin, SahteVeri())


def _kart(c, etiket):
    return next(k["deger"] for k in c["kartlar"] if k["etiket"] == etiket)


def test_satis_toplami_pnl_karti_ile_ayni():
    from satis.pnl_hesap import satis_pnl
    from shared.tasarim import para
    P = satis_pnl(date(2026, 9, 1), date(2026, 9, 30), "Tümü", "Tümü", SahteKaynak())
    c = _cevap("geçen ay net kâr")
    assert _kart(c, "Net kâr") == para(P["nihai"])          # iade, Ref No, alınan destek dahil
    assert _kart(c, "Net ciro") == para(P["net_ciro"])
    assert c["hedef"] == "satis/pnl"


def test_firma_iki_carisi_toplanir():
    """EERA'nın TL ve USD carisi ayrı kanal adı; firma sorusu ikisini birlikte alır."""
    from satis.pnl_hesap import satis_pnl
    from shared.tasarim import para
    t = sum(satis_pnl(date(2026, 9, 1), date(2026, 9, 30), k, "Tümü", SahteKaynak())["nihai"]
            for k in SOZLUK["firmalar"]["EERA BİLGİSAYAR"])
    assert _kart(_cevap("eera geçen ay kâr"), "Net kâr") == para(t)


def test_urun_siralamasi_iade_dusulmus():
    c = _cevap("geçen ay en çok kâr bıraktıran ürünler")
    r = {x["SKU"]: x for x in c["satirlar"]}
    # K1: 10×(50−30)=200 satış kârı − iade kârı (50 − 1×30 = 20) = 180
    assert r["K1"]["Net kâr ($)"] == pytest.approx(180)
    assert r["K1"]["Adet"] == 9 and r["K1"]["Net ciro ($)"] == pytest.approx(450)
    assert r["K1"]["Ürün"] == "OYUN KASASI"                     # kartın adı (shared.ana_veri.urun_ad)
    assert [x["SKU"] for x in c["satirlar"]] == ["M1", "K1", "F1"]   # 200 > 180 > 60


def test_kategori_ve_marka_suzgeci():
    c = _cevap("geçen ay fazeon monitörlerin kârı")
    assert _kart(c, "Net kâr") == "$200"                       # yalnız M1: 5×(200−10−150)


def test_kar_yetkisi_yoksa_ciro_gosterilir():
    izin = dict(TAM, kar=False)
    c = _cevap("geçen ay en çok kâr bıraktıran ürünler", izin)
    assert all("Net kâr ($)" not in r and "Marj (%)" not in r for r in c["satirlar"])
    assert not any(k["etiket"] in ("Net kâr", "Net marj") for k in c["kartlar"])
    assert any("yetkili" in u for u in c["uyarilar"])


def test_modul_yetkisi_yoksa_cevap_yok():
    c = _cevap("vadesi geçen ödemeler", dict(TAM, kayranacc=False))
    assert c["yetki"] and "Muhasebe" in c["yetki"] and not c["satirlar"]


def test_yasli_stok_stok_yasi_hesabiyla_ayni():
    from kayranpm.stok_yasi import yasli_satirlar
    v = SahteVeri()
    h = v.stok_yasi()
    beklenen = yasli_satirlar(h["bizim"], PACAL, BUGUN, 120)
    c = _cevap("120 günü geçen stok")
    assert c["satirlar"][0]["120+ gün adet"] == beklenen[0]["120+ gün adet"] == 5
    assert _kart(c, "Yaşlı değer") == "$150"


def test_ariza_sirasi_ve_suzgec():
    c = _cevap("bu çeyrek arıza oranı en yüksek modeller")
    assert [r["SKU"] for r in c["satirlar"]] == ["M1", "K1"]   # servise gelmeyen F1 listede yok
    c = _cevap("markalara göre arıza oranı")
    assert c["satirlar"][0]["Marka"] == "FAZEON"


def test_kampanya_durum_ve_firma():
    c = _cevap("süren kampanyalar")
    assert [r["Kampanya"] for r in c["satirlar"]] == ["Eylül monitör"]
    assert c["satirlar"][0]["Net ($)"] == pytest.approx(200)   # 5 × (200 − 10 − 150)


def test_odeme_ve_cek():
    c = _cevap("vadesi geçen ödemeler")
    assert [r["Firma"] for r in c["satirlar"]] == ["AYKON"]
    c = _cevap("bekleyen ödemeler")
    assert len(c["satirlar"]) == 2 and _kart(c, "Toplam USD") == "$300"
    c = _cevap("bekleyen çekler")
    assert [r["Firma"] for r in c["satirlar"]] == ["AYKON"] and _kart(c, "Kalan TL") == "₺5.000"


def test_soru_kutusu_salt_okur():
    """Cevap katmanı hiçbir tabloya yazmaz (insert/update/delete/upsert yok)."""
    from pathlib import Path
    kod = (Path(__file__).resolve().parent.parent / "shared" / "soru_cevap.py").read_text(encoding="utf-8")
    for yasak in (".insert(", ".update(", ".delete(", ".upsert("):
        assert yasak not in kod


def test_baglanti_noktalari():
    from pathlib import Path
    kok = Path(__file__).resolve().parent.parent
    app = (kok / "app.py").read_text(encoding="utf-8")
    assert 'elif aktif == "soru":' in app and "anlasilir_mi(terim)" in app
    assert '"soru:" + q.strip()' in (kok / "shared" / "palet.py").read_text(encoding="utf-8")
    from shared.gezinme import hedef
    assert hedef("sistem/soru") == {"modul": "soru", "anahtar": None, "secenek": None}
