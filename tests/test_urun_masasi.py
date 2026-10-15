# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Tüm Ürünler liste masası (Ekim 2026, ortak masa shared/masa.py).

Masanın tanımı eski listeyle aynı rakamları taşır (urun_hesap.urun_satiri; özet bandı main.py'deki eski
kartlarla aynı toplamlar), varsayılan sıra eski listenin ilk sıralaması (stok yaşı, en eski önce), süzgeç
alanları eski filtrelerle aynı değerler. Satıra tıklama bugünkü sayfa içi ayrıntıyı açar (B.sec("pm_urun")),
"Excel / PDF hazırla" seçilen SKU'ları dışa aktarmaya yazar.
"""
import pytest

from kayranpm import urun_masasi as M
from kayranpm.urun_hesap import urun_filtrele_sirala, urun_satiri
from shared.masa import istek_al
from shared.tasarim import tr_sayi


def _u(sku, **k):
    d = {"sku": sku, "urun_adi": f"{sku} ürün", "kategori": "ssd", "marka": "FAZEON", "bizim_stok": 10,
         "stok_gun": 30, "stok_renk": "yesil", "risk_skor": 10, "ithalat_dosya_sayisi": 1, "fob_price": 80,
         "final_cost_price": 100, "satis_fiyati": 120, "stok_degeri_fcp": 1000.4, "stok_degeri_satis": 1200.6,
         "toplam_stok": 10, "kanal_stok": 0, "firma_stoklari": {}}
    d.update(k)
    return d


URUNLER = [
    _u("A-1", stok_gun=200, stok_renk="kirmizi", bizim_stok=5, toplam_stok=5, zincir_stok=17,
       firma_stoklari={"VATAN": 12}, kanal_stok=12, stok_degeri_fcp=123456.78),
    _u("B-2", stok_gun=10, satis_fiyati=90, kategori="monitör", marka="MIO"),                # zararına
    _u("C-3", stok_gun=75, stok_renk="sari", eol=True, ithalat_dosya_sayisi=0, satis_fiyati=0, marka=""),
    _u("D-4", stok_gun=75, stok_renk="yok", risk_skor=88.5),
]
FIRMA = {"VATAN": "VATAN BİLGİSAYAR"}.get


def _veri(dar=False):
    return M.masa_verisi(URUNLER, dar=dar, firma_ad=lambda k: FIRMA(k, k))


def test_ozet_eski_kartlarla_ayni_toplam():
    v = _veri()
    d = {k["k"]: k for k in v["ozet"]}
    assert d["urun"]["dg"] == "4"
    assert d["stok"]["dg"] == f"{tr_sayi(5 + 10 + 10 + 10)} adet" and d["stok"]["al"] == "Merkez + Happy Life · kanallarda 12"
    fcp = sum(u["stok_degeri_fcp"] for u in URUNLER)                  # eski: f"${tr_sayi(toplam)}" (kuruşsuz)
    assert d["maliyet"]["dg"] == f"${tr_sayi(fcp)}" == "$126.458"
    assert d["satis"]["dg"] == f"${tr_sayi(sum(u['stok_degeri_satis'] for u in URUNLER))}"


def test_sira_eski_listenin_varsayilan_siralamasi():
    v = _veri()
    eski = urun_filtrele_sirala([urun_satiri(u) for u in URUNLER], sira="_stok_yas", azalan=True)
    assert [s["id"] for s in v["satirlar"]] == [r["SKU"] for r in eski] == ["A-1", "C-3", "D-4", "B-2"]


def test_satir_rakamlari_eski_satirla_ayni():
    from kayranpm.urunler_ekran import _usd                       # eski satırın biçimi ("&#36;" = "$")
    v = _veri()
    r = {s["id"]: s for s in v["satirlar"]}
    eski = {x["SKU"]: x for x in (urun_satiri(u) for u in URUNLER)}
    a = r["A-1"]
    assert a["fiyat_m"] == f"{_usd(100)} → {_usd(120)}".replace("&#36;", "$") == "$100,00 → $120,00"
    assert a["marj_m"] == f"%{tr_sayi(abs(eski['A-1']['Net Marj (%)']), 1)}" == "%16,7" and a["marj_alt"] == "marj"
    assert a["kar_m"] == "$20,00" and a["mal_m"] == "%25,0" and a["stok_m"] == "5"
    assert a["stok_alt"] == "kanal dahil 17" and a["alt"] == f"VATAN BİLGİSAYAR 12 · {eski['A-1']['Kategori']} · FAZEON"
    assert a["_durum"] == {"ad": "200 gün", "renk": "kirmizi"} and a["yas__s"] == 200
    b = r["B-2"]
    assert b["zarar"] and b["marj_alt"] == "zarar" and b["marj_renk"] == "kirmizi" and b["kar_m"] == "-$10,00"
    assert b["marj_m"] == "%11,1" and b["marj_m__s"] < 0
    c = r["C-3"]                                           # ithalatı yok, satış fiyatı yok
    assert c["fiyat_m"] == "fiyat yok" and c["marj_m"] == "" and c["kar_m__s"] is None and c["_soluk"]
    assert c["alt"].endswith("EOL") and c["_durum"]["renk"] == "amber"
    assert r["D-4"]["_durum"] == {} and r["D-4"]["risk"] == tr_sayi(88.5) and r["D-4"]["risk__s"] == 88.5


def test_suzgecler_eski_filtrelerle_ayni():
    v = _veri()
    katlar = sorted({urun_satiri(u)["Kategori"] for u in URUNLER}, key=str.lower)   # eski filtre seçenekleri
    assert [o["k"] for o in v["secimler"][0]["secenekler"]] == katlar and len(katlar) == 2
    markalar = sorted({urun_satiri(u)["Marka"] for u in URUNLER} - {""}, key=str.lower)
    assert [o["k"] for o in v["secimler"][1]["secenekler"]] == markalar and len(markalar) == 2
    assert v["anahtarlar"][0]["ad"] == "Yalnız zararına satılanlar (1)"
    from shared.masa import kosul_uyar
    assert [s["id"] for s in v["satirlar"] if kosul_uyar(s, v["anahtarlar"][0]["f"])] == ["B-2"]
    assert v["ara"]["alanlar"] == ["sku", "ad"] and v["tik"] == "ac"


def test_dar_masa_az_sutun_ozet_ve_aktarma_yok():
    v = _veri(dar=True)
    assert [c["alan"] for c in v["sutunlar"]] == ["ad", "mus_m", "marj_m"]   # Stok sütunu müşteri stoğu (Ekim 2026)
    assert v["ozet"] == [] and [i["k"] for i in v["islemler"]] == ["ac"]
    assert v["anahtarlar"][0]["ad"] == "Zararına (1)"


def test_istek_dogrulama():
    v = _veri()
    t, h = istek_al(v, {"islem": "ac", "ids": ["B-2"]})
    assert h is None and t["ids"] == ["B-2"]
    t, h = istek_al(v, {"islem": "aktar", "ids": ["A-1", "C-3"]})
    assert h is None and t["ids"] == ["A-1", "C-3"]
    for istek, parca in [({"islem": "ac", "ids": ["YOK"]}, "bulunamadı"), ({"islem": "ac", "ids": ["A-1", "B-2"]}, "tek"),
                         ({"islem": "sil", "ids": ["A-1"]}, "Bilinmeyen"), ({"islem": "ac", "ids": []}, "seçilmedi")]:
        t, h = istek_al(v, istek)
        assert t is None and parca in h
    t, h = istek_al(_veri(dar=True), {"islem": "aktar", "ids": ["A-1"]})        # dar masada dışa aktarma yok
    assert t is None and "Bilinmeyen" in h


def test_yurut_ayrinti_ve_disa_aktarma(monkeypatch):
    from shared import bilesen as B
    cagri = []
    monkeypatch.setattr(B, "sec", lambda *a: cagri.append(a))
    v, ss = _veri(), {}
    yurut = M.yurutucu(state=ss)
    s = yurut(istek_al(v, {"islem": "ac", "ids": ["C-3"]})[0])
    assert cagri == [("pm_urun", "C-3")] and s == {"ok": True, "sessiz": True, "onbellek": False}
    s = yurut(istek_al(v, {"islem": "aktar", "ids": ["B-2", "A-1"]})[0])
    assert ss == {M.AKTAR_KEY: ["B-2", "A-1"]} and s["ok"] and s["onbellek"] is False
    assert [r["SKU"] for r in M.aktarilacak(URUNLER, ss[M.AKTAR_KEY])] == ["A-1", "B-2"]     # varsayılan sırada
    assert len(M.aktarilacak(URUNLER)) == 4


@pytest.mark.parametrize("satir", [[], [_u("Z", urun_adi=None, kategori=None, marka=None, satis_fiyati=None,
                                                final_cost_price=None, stok_gun=None, bizim_stok=None)]])
def test_bos_ve_bozuk_veri_cokmez(satir):
    v = M.masa_verisi(satir, firma_ad=str)
    assert len(v["satirlar"]) == len(satir)
    if satir:
        assert v["satirlar"][0]["ad"] == "Z" and v["satirlar"][0]["fiyat_m"] == "fiyat yok"


def test_csv_bayt_excel_bicimi():
    from kayranpm.masa_ortak import csv_bayt
    b = csv_bayt([{"A": "x;y", "B": 1234.5, "C": 3, "_gizli": 1}, {"A": None, "B": 2.0, "C": True}])
    assert b.startswith("﻿".encode("utf-8"))
    assert b.decode("utf-8")[1:].split("\r\n") == ["A;B;C", '"x;y";1234,5;3', ";2;evet"]


def test_musteri_suzgeci_yalniz_stoku_olan_musteriler():
    """Müşteri süzgeci (Ekim 2026, kullanıcı isteği): ürünün stoğu olan müşteriler — satırın alt yazısındaki firmalar.
    Firma stokları her firmayı 0 adetle de taşıyabilir; 0 olan firma eşleşmez."""
    urunler = URUNLER + [_u("E-5", firma_stoklari={"VATAN": 0, "EERA": 4}, kanal_stok=4)]
    v = M.masa_verisi(urunler, firma_ad=lambda k: FIRMA(k, k))
    r = {s["id"]: s for s in v["satirlar"]}
    assert r["A-1"].get("mus") == ["VATAN BİLGİSAYAR"] and r["E-5"].get("mus") == ["EERA"] and r["B-2"].get("mus") == []
    sec = v["secimler"][2]
    assert sec["alan"] == "mus" and sec["ad"] == "Tüm müşteriler"
    assert [o["k"] for o in sec["secenekler"]] == ["EERA", "VATAN BİLGİSAYAR"]
    # masa liste alanını "içerir" ile süzer (shared/masa.py JS); dar masada da aynı süzgeç
    assert M.masa_verisi(urunler, dar=True, firma_ad=lambda k: FIRMA(k, k))["secimler"][2]["alan"] == "mus"
