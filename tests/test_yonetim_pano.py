# -*- coding: utf-8 -*-
"""Yönetim panosu yenileme (Ekim 2026, görünüm B: P&L akışı önde) — yonetim_pano.py.

Rakam değişmez: dönem toplamları yine yonetim_hesap.pnl_topla'dan. Yeni olanlar kıyas dönemleri
(önceki dönem, geçen yılın aynı dönemi), 12 aylık trend ayları, tablo satırları, küçük trend SVG.
"""
from datetime import date
from pathlib import Path

import yonetim_pano as P

KOK = Path(__file__).resolve().parent.parent
BUGUN = date(2026, 10, 4)


def test_donem_araligi_ve_gider_aylari():
    assert P.donem_araligi(2026, "Şubat") == ("2026-02-01", "2026-02-28", (1, 2))
    assert P.donem_araligi(2024, "Şubat") == ("2024-02-01", "2024-02-29", (1, 2))
    assert P.donem_araligi(2026, "Q3") == ("2026-07-01", "2026-09-30", (6, 9))
    assert P.donem_araligi(2025, "Tüm Yıl", BUGUN) == ("2025-01-01", "2025-12-31", (0, 12))
    assert P.donem_araligi(2026, "Tüm Yıl", BUGUN) == ("2026-01-01", "2026-10-04", (0, 10))


def test_kiyas_donemleri():
    k = P.kiyas_donemleri(2026, "Ocak", BUGUN)
    assert [(x[0], x[2], x[3], x[4], x[5]) for x in k] == [
        ("onceki", 2025, "Aralık", "2025-12-01", "2025-12-31"), ("gecen", 2025, "Ocak", "2025-01-01", "2025-01-31")]
    k = P.kiyas_donemleri(2026, "Q1", BUGUN)
    assert [(x[0], x[2], x[3]) for x in k] == [("onceki", 2025, "Q4"), ("gecen", 2025, "Q1")]
    # İçinde bulunulan yılın tamamı → geçen yılın AYNI gününe kadar, aynı gider aylarıyla
    k = P.kiyas_donemleri(2026, "Tüm Yıl", BUGUN)
    assert [(x[0], x[4], x[5], x[6]) for x in k] == [("gecen", "2025-01-01", "2025-10-04", (0, 10))]
    k = P.kiyas_donemleri(2024, "Tüm Yıl", BUGUN)
    assert [(x[4], x[5], x[6]) for x in k] == [("2023-01-01", "2023-12-31", (0, 12))]


def test_trend_aylari_donem_sonunda_biter_gelecege_tasmaz():
    t = P.trend_aylari(2026, "Eylül", BUGUN)
    assert len(t) == 12 and t[0] == (2025, 9) and t[-1] == (2026, 8)
    assert P.trend_aylari(2026, "Tüm Yıl", BUGUN)[-1] == (2026, 9)           # Ekim (içinde bulunulan)
    assert P.trend_aylari(2026, "Aralık", BUGUN)[-1] == (2026, 9)
    assert P.trend_aylari(2025, "Q2", BUGUN)[-1] == (2025, 5)


def test_degisim():
    assert P.degisim(110, 100) == {"oran": 10.0, "iyi": True}
    assert P.degisim(90, 100, tersi=True) == {"oran": -10.0, "iyi": True}       # maliyet düştü: iyi
    assert P.degisim(-50, -100)["oran"] == 50.0 and P.degisim(-50, -100)["iyi"]  # zarar azaldı
    assert P.degisim(5, 0) is None and P.degisim(5, None) is None


def test_tablo_satirlari():
    k = P.kanal_satirlari({"VATAN": {"ciro": 1000, "net_kar": 100, "adet": 10},
                           "EERA": {"ciro": 3000, "net_kar": 300, "adet": 20}})
    assert [x["Kanal"] for x in k] == ["EERA", "VATAN"] and k[0]["Kâr payı (%)"] == 75.0 and k[1]["Marj (%)"] == 10.0
    u = P.urun_satirlari({"A": {"urun_adi": "Ürün A", "ciro": 100, "net_kar": -5, "adet": 1},
                          "B": {"urun_adi": "Ürün B", "ciro": 50, "net_kar": 10, "adet": 2}})
    assert [x["SKU"] for x in u] == ["B", "A"]
    d = P.destek_satirlari({"SELLOUT": 300, "Ref No": 100})
    assert d[0] == {"_id": "SELLOUT", "Tür": "SELLOUT", "Tutar ($)": 300.0, "Pay (%)": 75.0}
    g, top = P.gider_satirlari({"Sabit": [10] * 12, "Değişken": [5] * 6})
    assert g[-1]["Kategori"] == "Toplam" and g[-1]["Ocak"] == 15 and g[-1]["Aralık"] == 10
    assert g[-1]["Yıllık"] == 150 and top[0] == 15
    p = P.pnl_satirlari({"ciro": 900, "cogs": 540, "brut": 360, "destek": 150, "gider": 200, "alinan": 25,
                         "net_kar": 35}, [("Ağustos", {"ciro": 800, "net_kar": 20})])
    assert p[0] == {"Hesap": "Ciro", "Tutar ($)": 900.0, "Ağustos tutarı ($)": 800.0} and p[-1]["Tutar ($)"] == 35.0
    # shared.tablo sütun adından biçim çıkarır: metin sütunu sayı, tutar sütunu para sayılmamalı
    from shared.tasarim import _tablo_kolon_tipi
    assert _tablo_kolon_tipi("Hesap") is None and _tablo_kolon_tipi("Tür") is None
    assert {_tablo_kolon_tipi(k) for k in p[0] if k != "Hesap"} == {"para"}


def test_gider_usd_ayin_kuruyla():
    """USD gider tablosu: her ay o ayın kuruyla (ayın 15'i, yoksa güncel kur) — P&L ile aynı kural."""
    kmap = {"2026-01-15": 36.0, "2026-01-20": 99.0, "2026-02-15": 40.0}   # Şubat 15 var, Mart yok
    kur = P.ay_kurlari(2026, kmap, 45.0)
    assert kur[:3] == [36.0, 40.0, 45.0] and kur[11] == 45.0
    assert P.ay_kurlari(2026, kmap, 0)[2] is None          # güncel kur da yoksa None
    kat = {"Sabit": [3600, 4000, 900] + [0] * 9, "Değişken": [360, 0, 0] + [0] * 9}
    rows, top, eksik = P.gider_usd_satirlari(kat, kur)
    assert rows[0]["Ocak"] == 100.0 and rows[0]["Şubat"] == 100.0 and rows[0]["Mart"] == 20.0
    assert rows[1]["Ocak"] == 10.0 and rows[-1]["Kategori"] == "Toplam" and rows[-1]["Ocak"] == 110.0
    assert rows[-1]["Yıllık"] == 230.0 and top[0] == 110.0 and eksik == []
    # kuru olmayan ay: 0 yazılır, eksik listesine düşer; tutarı 0 olan ay eksik sayılmaz
    rows, _, eksik = P.gider_usd_satirlari(kat, [36.0, None, None] + [None] * 9)
    assert rows[0]["Şubat"] == 0.0 and eksik == ["Şubat", "Mart"]


def test_kucuk_trend_svg():
    s = P.kucuk_trend_svg([1, 3, 2], ["Oca", "Şub", "Mar"], "yesil", lambda v: f"${v:g}")
    assert s.startswith("<svg") and "var(--k-yesil)" in s and "<title>Mar: $2</title>" in s
    assert s.count("<circle") == 3 and P.kucuk_trend_svg([5], ["Oca"]) == ""
    assert "NaN" not in P.kucuk_trend_svg([4, 4, 4], ["a", "b", "c"])           # düz seri: sıfıra bölme yok


def test_pnl_topla_aylar_gider_ayini_sinirlar():
    """Yılbaşından bugüne kıyası: geçen yılın yalnız aynı ayları (Ekim–Aralık gideri girmesin)."""
    from yonetim_hesap import pnl_topla

    class K:
        def satis(self, b, t): return {"ciro": 0, "maliyet": 0}, {}, {}
        def iade(self, b, t): return {}
        def kur_haritasi(self, b, t): return {}
        def yedek_kur(self): return 10.0
        def destekler(self, b, t): return []
        def gider_kat(self, y): return {"Sabit": [100.0] * 12}
        def alinan(self, b, t): return 0
    tam = pnl_topla(2025, "Tüm Yıl", "2025-01-01", "2025-10-04", K(), bugun=BUGUN)
    sinirli = pnl_topla(2025, "Tüm Yıl", "2025-01-01", "2025-10-04", K(), bugun=BUGUN, aylar=(0, 10))
    assert tam["gider_tl"] == 1200 and sinirli["gider_tl"] == 1000 and sinirli["gider"] == 100


def test_ekran_yapisi():
    y = (KOK / "yonetim.py").read_text(encoding="utf-8")
    from shared.gezinme import secenekler
    assert secenekler("yonetim") == ["Özet", "Para haritası", "Kanal ve ürün", "Destekler ve giderler",
                                     "Ay kapanışı"]          # Şirket belgeleri / Sistem: kişi menüsünde
    assert 'sayfa_menusu("Bölüm", secenekler("yonetim"), modul="yonetim", key="yon_sayfa"' in y
    for f in ("def _ozet(", "def _kanal_urun(", "def _destek_gider(", "def _ay_kapanis(", "def _audit_render(", "def _yedek_render(",
              "def _trend(", "add_script_run_ctx"):
        assert f in y, f
    # Gider yükleme penceresi Ekim 2026'da Dosya kapısına taşındı (kapi_gider, düz fonksiyon)
    assert "@st.dialog" not in y and "def kapi_gider(dosya, kapi)" in y
    assert "excel_bytes(" in y and '"Kanallar": krows' in y
    # rakamlar tek hesaptan: kıyaslar da pnl_topla
    assert "pnl_topla(yil, donem, bas, bit, _PnlKaynak(kur), bugun=_bugun(), aylar=tuple(aylar))" in y
