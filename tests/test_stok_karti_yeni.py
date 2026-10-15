# -*- coding: utf-8 -*-
"""Stok kartı yeni tasarım (kayranpm/stok_karti_yeni.py, Ekim 2026): gösterim düzenleyicileri bugünkü
hesaplardan gelen değerleri doğru dağıtır; kurallar Analiz sekmesiyle aynı; pencere yapısı korunur."""
import re
import sys
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from kayranpm import stok_karti_yeni as Y  # noqa: E402
from shared.masa import istek_al  # noqa: E402

BUGUN = date(2026, 10, 14)            # çarşamba
FA = lambda k: {"D-MARKET ELEKTRONİK": "D-MARKET"}.get(k, k or "")   # noqa: E731


def test_haftalik_seri_pazartesiden_ve_bu_hafta_dahil():
    s = [{"tarih": "2026-10-12", "adet": 5}, {"tarih": "2026-10-14", "adet": 3},     # bu hafta (12.10 pzt)
         {"tarih": "2026-10-11", "adet": 7},                                         # geçen hafta (pazar)
         {"tarih": "2026-07-01", "adet": 99}, {"tarih": "bozuk", "adet": 1}]         # 12 haftadan eski / bozuk
    seri = Y.haftalik_seri(s, BUGUN)
    assert len(seri) == 12 and seri[-1] == (date(2026, 10, 12), 8.0) and seri[-2] == (date(2026, 10, 5), 7.0)
    assert sum(a for _, a in seri) == 15.0 and seri[0][0] == date(2026, 7, 27)


def test_son_hareketler_en_yeniden_ve_turleriyle():
    o = Y.son_hareketler(
        satislar=[{"tarih": "2026-10-14", "kanal": "D-MARKET ELEKTRONİK", "adet": 16, "siparis_no": "SP1"},
                  {"tarih": "2026-09-01", "kanal": "EERA", "adet": 2}],
        iadeler=[{"tarih": "2026-10-13", "kanal": "VATAN", "iade_adet": 1}],
        alimlar=[{"tarih": "2026-06-07", "adet": 300, "belge_no": "PI-2", "tedarikci": "Shenzhen", "final_birim": 2.38}],
        yolda_rows=[{"yoldaki_miktar": 100, "tahmini_varis_tarihi": "2026-10-26", "yoldaki_tedarikci": "Taipei"},
                    {"yoldaki_miktar": 0}],
        firma_ad=FA, bugun=BUGUN, n=4)
    assert [x["tur"] for x in o] == ["yolda", "satis", "iade", "satis"]
    assert o[1] == {"tur": "satis", "baslik": "Satış · D-MARKET 16 adet", "alt": "bugün · SP1"}
    assert o[2]["alt"] == "dün · stoğa döndü" and o[0]["alt"] == "26.10.2026 · Taipei · varış 26.10.2026"


def test_durum_uyarilari_analizle_ayni_esikler():
    # yeniden sipariş noktası = günlük hız × tedarik süresi; stok + yolda altına inince uyarı (Analiz ile aynı)
    u = Y.durum_uyarilari(toplam_stok=200, yolda_adet=100, gunluk_hiz=2.6, uretim_suresi=135, pacal=2.4, liste=5,
                          satis_var=True)
    assert [x["baslik"] for x in u] == ["Sipariş zamanı", "Marj sağlıklı"] and "%52,0" in u[1]["alt"]
    u = Y.durum_uyarilari(500, 0, 2.6, 135, 2.4, 5, True)
    assert [x["baslik"] for x in u] == ["Marj sağlıklı"]
    assert Y.durum_uyarilari(10, 0, 0, 135, 4.6, 5, True)[0]["baslik"] == "Düşük marj"          # %8 < %10
    assert Y.durum_uyarilari(10, 0, 0, 135, 5, 5, True)[0]["tur"] == "kotu"                      # liste ≤ paçal
    assert Y.durum_uyarilari(10, 0, 0, 135, 0, 0, False)[0]["baslik"] == "Hareketsiz stok"
    assert Y.durum_uyarilari(0, 0, 0, 135, 0, 0, False) == []


def test_stok_yerleri_satilabilir_once_ve_firmanin_son_raporu():
    y = Y.stok_yerleri({"OUTLET DEPO": 24, "MERKEZ DEPO": 192, "HAPPY LIFE": 48, "BOŞ": 0},
                       [{"firma": "EERA", "yukleme_tarihi": "2026-09-29", "stok_miktari": 250, "haftalik_satis": 3},
                        {"firma": "EERA", "yukleme_tarihi": "2026-10-06", "stok_miktari": 240, "haftalik_satis": 4},
                        {"firma": "D-MARKET ELEKTRONİK", "yukleme_tarihi": "2026-10-06", "stok_miktari": 420}],
                       FA)
    assert y["depolar"] == [("MERKEZ DEPO", 192.0, True), ("HAPPY LIFE", 48.0, True), ("OUTLET DEPO", 24.0, False)]
    assert y["musteriler"] == [("D-MARKET", 420.0, 0.0, "2026-10-06"), ("EERA", 240.0, 4.0, "2026-10-06")]


def _kar(s):
    return {"adet": s["adet"], "ciro": s["adet"] * s["birim_satis"], "net_kar": s["adet"] * 2.6, "marj": 52.0}


def test_satis_masasi_aylara_gruplu_firma_kartlari_ve_istek():
    satislar = [{"tarih": "2026-10-14", "kanal": "D-MARKET ELEKTRONİK", "adet": 16, "birim_satis": 5, "siparis_no": "SP1"},
                {"tarih": "2026-09-28", "kanal": "D-MARKET ELEKTRONİK", "adet": 24, "birim_satis": 5, "siparis_no": "SP2"},
                {"tarih": "2026-05-02", "kanal": "EERA", "adet": 10, "birim_satis": 4.8, "siparis_no": ""}]
    v, kartlar = Y.satis_masa_verisi(satislar, _kar, FA, BUGUN)
    r = v["satirlar"]
    assert [x["ay"] for x in r] == ["Ekim 2026", "Eylül 2026", "Mayıs 2026"]
    assert [x["bu_ay"] for x in r] == [True, False, False] and [x["son90"] for x in r] == [True, True, False]
    assert r[0]["firma"] == "D-MARKET" and r[0]["firma_tam"] == "D-MARKET ELEKTRONİK" and r[2]["firma_tam"] == ""
    assert r[0]["kar_m"] == "$41,60" and r[0]["marj_m"] == "%52,0" and r[2]["siparis"] == "—"
    assert [(k["ad"], k["adet"]) for k in kartlar] == [("D-MARKET", 40.0), ("EERA", 10.0)]
    assert v["tik"] == "ac" and v["grup"]["alan"] == "ay"
    t, h = istek_al(v, {"islem": "ac", "ids": [1]})                 # satıra tıklama → ayrıntı (salt-okurda da)
    assert h is None and t["satirlar"][0]["siparis"] == "SP2"
    t, h = istek_al(dict(v, salt=True), {"islem": "ac", "ids": [2]})
    assert h is None


def test_pencere_yapisi_ve_geri_donus():
    s = (KOK / "kayranpm" / "stok_karti.py").read_text(encoding="utf-8")
    assert "STOK_KARTI_YENI = True" in s
    # pencere dekoratörü goster'e bağlı (başka fonksiyon araya girerse pencere boş açılır)
    assert re.search(r'@st\.dialog\("[^"]*Stok Kartı", width="large", on_dismiss=kapat\)\ndef goster\(sku=None\):', s)
    # yeni görünüm hesap yapmaz: goster'in değerleri ve sekme gövdeleri verilir; eski görünüm aynı gövdeleri kullanır
    assert "_yeni_ciz(sku, dict(" in s and '"analiz": _govde_analiz' in s
    assert "for _t, _g in zip((t2, t3, t4, t5, t6, t7, t8), (_govde_alimlar, _govde_satislar" in s
    y = (KOK / "kayranpm" / "stok_karti_yeni.py").read_text(encoding="utf-8")
    for yasak in (".table(", "get_client(", "get_pacal_map", ".execute("):
        assert yasak not in y, yasak
    # pencere içinden satır ayrıntısı: sayfa yeniden çalışmaz (pencere kapanmasın)
    assert '"yenileme": False' in y


def test_ortak_sekme_govdelerinde_emoji_yok():
    s = (KOK / "kayranpm" / "stok_karti.py").read_text(encoding="utf-8")
    govde = s[s.index("    def _govde_alimlar():"):s.index("    # Yeni tasarım (Ekim 2026")]
    assert not re.search("[\U0001F300-\U0001FAFF☀-➿]", govde)
    assert not re.search("[\U0001F300-\U0001FAFF☀-➿]", (KOK / "kayranpm" / "stok_karti_yeni.py").read_text(encoding="utf-8"))
