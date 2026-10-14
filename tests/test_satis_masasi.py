# -*- coding: utf-8 -*-
"""Satış listeleri ortak masada (Ekim 2026, tüm program yeni tasarım — satis/satis_masasi.py).

Satışlar (sipariş + kalem görünümü), Satış girişi › son siparişler ve İade kayıtları: masanın tanımı eski
ekranla aynı rakamları taşır (özet kartı aynı metin, satırda tam tutar), kâr gizliyken kâr/marj tarayıcıya
gitmez, istek ortak doğrulamadan (shared.masa.istek_al) geçer ve BUGÜNKÜ fonksiyonlara gider
(sipariş penceresi B.detay_ac("sip", …), silme sil_iade(int(id)))."""
import sys
from datetime import date
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from satis import satis_masasi as M  # noqa: E402
from satis import satis_hesap as H  # noqa: E402
from satis.database import satir_kar  # noqa: E402
from shared import masa  # noqa: E402

BUGUN = date(2026, 10, 14)
D_MARKET = "D-MARKET ELEKTRONİK HİZMETLER VE TİCARET ANONİM ŞİRKETİ"
EERA = "EERA ELEKTRONİK TİCARET VE BİLİŞİM HİZMETLERİ ANONİM ŞİRKETİ"


def _s(i, sno, tarih, kanal, sku, adet, bsat, bmal, destek=0.0):
    return {"id": i, "siparis_no": sno, "tarih": tarih, "kanal": kanal, "sku": sku, "urun_adi": f"{sku} ürün",
            "adet": adet, "birim_satis": bsat, "birim_maliyet": bmal, "birim_firma_destek": destek,
            "birim_ek_destek": 0}


KALEM = [
    _s(1, "SP1", "2026-10-14", D_MARKET, "FZ-SSD-512", 10, 34.9, 25.1),
    _s(2, "SP1", "2026-10-14", D_MARKET, "AGI-RAM-16", 4, 26.0, 18.2, destek=1.3),
    _s(3, "SP2", "2026-10-13", EERA, "IN3-4060", 2, 309.0, 0),                      # maliyetsiz
    _s(4, "", "2026-10-13", EERA, "XS-PAD-XL", 3, 6.5, 3.1),                          # sipariş no yok
    _s(5, "SP3", "2026-10-10", D_MARKET, "IN3-4070S", 150, 589.0, 512.0),
]
SIP = H.siparis_grupla(KALEM, satir_kar)


# ── Biçim ───────────────────────────────────────────────────────────
def test_bicimler_eski_ekranla_ayni():
    from satis import satislar_ekran as SE
    for v in (0, 12.5, 1234.567, -98765.4, 1_170_000):
        assert M.usd_tam(v) == SE._usd_tam(v)
        assert M.usd_kisa(v) == SE._usd(v)
    assert M.usd_birim(7.29384) == "$7,2938" and M.usd_birim(12.5) == "$12,50" and M.usd_birim(1234) == "$1.234,00"
    assert M.usd_tam(1234.567) == "$1.234,57" and M.usd_kisa(1_170_000) == "$1,17M"


# ── Sipariş masası ──────────────────────────────────────────────────
def test_siparis_ozeti_eski_kpi_kartlariyla_ayni():
    t = H.toplam(SIP)
    oz = {k["k"]: k for k in M.siparis_ozeti(SIP, kar_ok=True)}
    assert list(oz) == ["siparis", "adet", "ciro", "kar"]
    assert oz["siparis"]["dg"] == "4" and oz["siparis"]["al"] == "5 kalem" and oz["siparis"]["renk"] == "mor"
    assert oz["adet"]["dg"] == "169"
    assert oz["ciro"]["dg"] == M.usd_kisa(t["ciro"]) == "$89.440" and oz["ciro"]["ipucu"] == M.usd_tam(t["ciro"])
    assert oz["ciro"]["al"] == f"destek {M.usd_kisa(t['destek'])}"                 # destek var
    assert oz["kar"]["dg"] == M.usd_kisa(t["net_kar"]) and oz["kar"]["renk"] == "yesil"
    assert oz["kar"]["al"].startswith("net marj %") and "maliyet $" in oz["kar"]["al"]


def test_siparis_satirlari_sira_grup_ve_tutar():
    v = M.siparis_masa_verisi(SIP, kar_ok=True, bugun=BUGUN)
    r = v["satirlar"]
    assert [x["id"] for x in r] == ["SP1", "SP2", "#kalem-4", "SP3"]            # en yeni üstte; numarasız → #kalem-id
    assert [x["gun"] for x in r] == ["Bugün", "Dün", "Dün", "10 Ekim, Cumartesi"]
    sp1 = r[0]
    assert sp1["sno_alt"] == "2 kalem · 14 adet" and sp1["firma"] == "D-MARKET ELEKTRONİK HİZMETLER"
    assert sp1["ciro_m"] == "$453,00" and sp1["ciro_m__s"] == pytest.approx(453.0)
    assert sp1["urunler"] == "FZ-SSD-512, AGI-RAM-16"
    assert r[1]["_durum"] == {"ad": "1 maliyetsiz", "renk": "amber"} and "_durum" not in sp1
    assert r[2]["sno"] == "Sipariş no yok"
    assert r[3]["ciro_m"] == "$88.350,00" and r[3]["kar_m"] == "$11.550,00" and r[3]["marj_m"] == "%13,1"
    assert v["grup"]["alan"] == "gun" and v["tik"] == "ac" and v["islemler"][0]["okuma"]
    assert [c["alan"] for c in v["sutunlar"]] == ["sno", "firma", "ciro_m", "kar_m", "maliyetsiz"]


def test_kar_gizliyken_kar_tarayiciya_gitmez():
    v = M.siparis_masa_verisi(SIP, kar_ok=False, bugun=BUGUN)
    assert [k["k"] for k in v["ozet"]] == ["siparis", "adet", "ciro"]
    assert not any(k in x for x in v["satirlar"] for k in ("kar_m", "marj_m", "_durum"))
    assert [c["alan"] for c in v["sutunlar"]] == ["sno", "firma", "ciro_m"]
    k = M.kalem_masa_verisi(KALEM, {}, False, satir_kar)
    assert not any(a in x for x in k["satirlar"] for a in ("kar_m", "marj_m", "bmal_m"))
    assert "kar_m" not in [c["alan"] for c in k["sutunlar"]]


def test_son_siparisler_ozetsiz():
    v = M.siparis_masa_verisi(SIP, kar_ok=True, ozet=False, bugun=BUGUN)
    assert v["ozet"] == [] and len(v["satirlar"]) == 4


def test_kalem_masasi_sayilari(monkeypatch):
    import shared.ana_veri as AV
    monkeypatch.setattr(AV, "urun_ad", lambda sku, yedek="": f"KART {sku}")
    monkeypatch.setattr(AV, "kategori_ad", lambda k: {"ssd": "SSD"}.get(k, ""))
    v = M.kalem_masa_verisi(KALEM, {"FZ-SSD-512": "ssd"}, True, satir_kar)
    r = {x["id"]: x for x in v["satirlar"]}
    assert r[1]["tarih_m"] == "14.10.2026" and r[1]["urun"] == "KART FZ-SSD-512" and r[1]["kategori"] == "SSD"
    assert r[1]["urun_alt"] == "FZ-SSD-512 · SSD" and r[2]["urun_alt"] == "AGI-RAM-16"
    assert r[1]["bsat_m"] == "$34,90" and r[1]["ciro_m"] == "$349,00" and r[1]["bmal_m"] == "maliyet $25,10"
    assert r[1]["kar_m"] == "$98,00" and r[1]["marj_m"] == "%28,1"
    assert r[4]["sip"] == "#kalem-4" and r[1]["sip"] == "SP1"
    assert r[5]["adet_m"] == "150" and r[5]["ciro_m"] == "$88.350,00"


# ── İstek → bugünkü fonksiyon ───────────────────────────────────────
def test_siparis_tiki_bugunku_pencereyi_ister(monkeypatch):
    import shared.bilesen as B
    acilan = []
    monkeypatch.setattr(B, "detay_ac", lambda on_ek, d: acilan.append((on_ek, d)))
    v = M.siparis_masa_verisi(SIP, kar_ok=True, bugun=BUGUN)
    t, h = masa.istek_al(v, {"islem": "ac", "ids": ["#kalem-4"]})
    assert h is None
    s = M.siparis_yurutucu()(t)
    assert acilan == [("sip", "#kalem-4")] and s["yenileme"] is False and s["sessiz"] is True
    # kalem satırı → kalemin siparişi
    k = M.kalem_masa_verisi(KALEM, {}, True, satir_kar)
    t, h = masa.istek_al(k, {"islem": "ac", "ids": [2]})
    M.siparis_yurutucu()(t)
    assert acilan[-1] == ("sip", "SP1")


@pytest.mark.parametrize("istek, parca", [
    ({"islem": "sil", "ids": ["SP1"]}, "Bilinmeyen"),                 # sipariş masasında silme yok
    ({"islem": "ac", "ids": ["SP9"]}, "bulunamadı"),
    ({"islem": "ac", "ids": ["SP1", "SP2"]}, "tek kayıt"),
])
def test_siparis_masasi_gecersiz_istek(istek, parca):
    t, h = masa.istek_al(M.siparis_masa_verisi(SIP, kar_ok=True, bugun=BUGUN), istek)
    assert t is None and parca in h


# ── İade kayıtları ──────────────────────────────────────────────────
IADE = [
    {"id": 7, "tarih": "2026-10-11", "kanal": D_MARKET, "sku": "FZ-SSD-512", "urun_adi": "Fazeon 512", "iade_adet": 2,
     "iade_net": 115.5, "depo": "İADE DEPO", "kaynak": "excel"},
    {"id": 9, "tarih": "2026-10-11", "kanal": "", "sku": "AGI-RAM-16", "urun_adi": "", "iade_adet": 1,
     "iade_net": 1240.25, "depo": "MERKEZ DEPO", "kaynak": "manuel"},
    {"id": 3, "tarih": "2026-09-02", "kanal": EERA, "sku": "IN3-4060", "urun_adi": "Inno3D", "iade_adet": 1,
     "iade_net": 300, "depo": "İADE DEPO", "kaynak": "excel"},
]


def test_iade_masasi_sira_grup_ayrinti():
    v = M.iade_masa_verisi(IADE, bugun=BUGUN)
    r = v["satirlar"]
    assert [x["id"] for x in r] == [9, 7, 3]                              # tarih, sonra id — yeni üstte
    assert [x["ay"] for x in r] == ["Ekim 2026", "Ekim 2026", "Eylül 2026"]
    assert r[0]["urun"] == "AGI-RAM-16" and r[0]["alt"] == "cari belirsiz · MERKEZ DEPO · manuel"
    assert r[1]["urun"] == "FZ-SSD-512 · Fazeon 512" and r[1]["tarih_m"] == "11 Ekim, Pazar"
    assert r[0]["net_m"] == "$1.240,25" and r[0]["_buyuk"] == "$1.240,25" and r[0]["_buyuk_alt"] == "1 adet"
    assert dict(r[1]["_detay"]) == {"Tarih": "11.10.2026", "Firma / cari": "D-MARKET ELEKTRONİK HİZMETLER",
                                    "Adet": "2", "İade net": "$115,50", "Giren depo": "İADE DEPO", "Kaynak": "excel"}
    assert v["grup"] == {"alan": "ay", "birim": "iade", "toplamlar": [{"alan": "net", "on": "$"}]}
    sec = {s["alan"]: [o["k"] for o in s["secenekler"]] for s in v["secimler"]}
    assert sec["depo"] == ["MERKEZ DEPO", "İADE DEPO"] and sec["kaynak"] == ["excel", "manuel"]
    assert sec["kanal"] == [D_MARKET, EERA]


def test_iade_silme_onayli_ve_sil_iade_cagirir(monkeypatch):
    import satis.database as D
    silinen = []
    monkeypatch.setattr(D, "sil_iade", lambda i: silinen.append(i) or True)
    v = M.iade_masa_verisi(IADE, bugun=BUGUN)
    t, h = masa.istek_al(v, {"islem": "sil", "ids": [7]})
    assert t is None and "gerekli" in h                                   # onaysız silinmez
    t, h = masa.istek_al(v, {"islem": "sil", "ids": [7], "degerler": {"onay": True}})
    assert h is None
    s = M.iade_yurutucu()(t)
    assert silinen == [7] and isinstance(silinen[0], int) and s == {"ok": True, "mesaj": "İade kaydı silindi"}
    monkeypatch.setattr(D, "sil_iade", lambda i: False)
    assert M.iade_yurutucu()(t)["ok"] is False


def test_iade_salt_okurda_silinmez():
    v = M.iade_masa_verisi(IADE, salt=True, bugun=BUGUN)
    t, h = masa.istek_al(v, {"islem": "sil", "ids": [7], "degerler": {"onay": True}})
    assert t is None and "Salt-okur" in h
    t, h = masa.istek_al(v, {"islem": "sil", "ids": [7, 9], "degerler": {"onay": True}})
    assert t is None


# ── Ekran bağlantısı ────────────────────────────────────────────────
def test_ekranlar_bayrakla_masaya_bagli():
    se = (KOK / "satis/satislar_ekran.py").read_text(encoding="utf-8")
    mn = (KOK / "satis/main.py").read_text(encoding="utf-8")
    assert "SATISLAR_MASASI_YENI = True" in se and "IADE_MASASI_YENI = True" in mn
    assert "if SATISLAR_MASASI_YENI:\n        return siparis_masasi(" in se          # Satış girişi de aynı liste
    assert "return _satislar_masa(siparisler, ham, gor, bas, bit," in se
    i = se.index("def _satislar_masa(")
    blok = se[i:se.index("\ndef ", i + 10)]
    assert "_indir(kalemler, bas, bit, firma)" in blok and "siparis_detay_kontrol()" in blok   # indirme + pencere aynen
    assert "SM.iade_masa_verisi(kayitlar" in mn and "SM.iade_yurutucu()" in mn
    # eski yol duruyor
    assert "B.tiklanir(f\"{anahtar}_{_anahtar_temiz(k)}\"" in se and "def _kalem_tablosu(" in se
    assert "_iade_detay_dialog(r)" in mn
