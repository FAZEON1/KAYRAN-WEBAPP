# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Genel Bakış yeniden tasarım + Talep düğmesi üst menüde (Ekim 2026).

Genel Bakış eskiden yalnız "acil sipariş" ve "30 gün içinde" listelerini
gösteriyordu; dashboard_hesapla()'nın ürettiği eğilim, ölü stok, yoldaki ürün,
kâr durumu, kanal stokları kullanılmıyordu. Yeni sayfa: sayı kartları ·
yapılacaklar (öncelikli gruplar) · satış eğilimi · stok sağlığı · kategori ·
kanal · yoldakiler · kampanyalar. Hesaplar kayranpm/genel_hesap.py'de.

Talep: sağ alttaki yüzen düğme Streamlit Cloud'un "Manage app" rozetinin
arkasında kalıyordu → üst menünün en sağına taşındı.
"""
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


def _u(sku, **kw):
    r = {"sku": sku, "urun_adi": f"Ürün {sku}", "kategori": "monitör", "toplam_stok": 100, "bizim_stok": 60,
         "ithalat_final": 10.0, "toplam_haftalik_satis": 10, "ortalama_haftalik_satis": 10.0,
         "siparis_durum": "normal", "stok_bitis_gun": 70, "oneri_miktar": 0, "olu_stok_durum": "normal",
         "olu_stok_mesaj": "", "kar_durum": "normal", "kar_marji": 20.0, "yol_renk": "yok", "yol_miktar": 0,
         "yol_varis": "", "yol_mesaj": "", "trend_yon": "stabil", "trend_yuzdesi": 0.0, "eol": False,
         "firma_detay": [{"firma": "VATAN", "stok": 40, "satis": 10}]}
    r.update(kw)
    return r


ROWS = [
    _u("A", siparis_durum="acil", stok_bitis_gun=12, oneri_miktar=300, yol_miktar=200, yol_varis="2026-10-12",
       yol_renk="sari", yol_mesaj="Gecikme riski! Stok 12g'de biter, varış 20g sonra"),
    _u("B", siparis_durum="acil", stok_bitis_gun=5, oneri_miktar=100),
    _u("C", olu_stok_durum="olu", olu_stok_mesaj="🪦 ÖLÜSTOK: 6 haftadır satış yok, 300 günlük stok",
       stok_bitis_gun=None, toplam_haftalik_satis=0, ortalama_haftalik_satis=0, kategori="kasa", bizim_stok=90),
    _u("D", kar_durum="zarar", kar_marji=-12.5, trend_yon="yukseliyor", trend_yuzdesi=40.0, kategori="Kasa"),
    _u("E", kar_durum="alis_yok", kar_marji=None, trend_yon="dusuyor", trend_yuzdesi=-30.0,
       yol_miktar=50, yol_varis="2026-10-05"),
    _u("F", siparis_durum="eol", eol=True, stok_bitis_gun=3),
]


# ── Sayı kartları ───────────────────────────────────────────────────
def test_kpi():
    from kayranpm.genel_hesap import kpi
    seri = [(date(2026, 9, 21), 80), (date(2026, 9, 28), 100)]
    k = kpi(ROWS, seri, date(2026, 10, 2))
    assert k["stok"] == 600 and k["hafta_satis"] == 100 and k["onceki_satis"] == 80
    assert k["degisim"] == 25.0
    assert k["kapsama_hafta"] == 6.0                                     # 600 / 100
    assert k["stok_degeri"] == 60 * 10 * 5 + 90 * 10                    # G5F stok × paçal
    assert k["yolda"] == 250 and k["en_yakin_varis"] == date(2026, 10, 5)
    assert k["acil"] == 2 and k["olu"] == 1                              # EOL acil sayılmaz


def test_kpi_bos_seri():
    from kayranpm.genel_hesap import kpi
    k = kpi(ROWS, [], date(2026, 10, 2))
    assert k["hafta_satis"] is None and k["degisim"] is None and k["kapsama_hafta"] is None


# ── Yapılacaklar ────────────────────────────────────────────────────
def test_yapilacaklar_gruplari_ve_sira():
    from kayranpm.genel_hesap import yapilacaklar
    g = {x["anahtar"]: x for x in yapilacaklar(ROWS)}
    assert list(g) == ["stok_bitiyor", "yol_risk", "olu_yavas", "zarar", "eksik_veri"]
    assert [r["sku"] for r, _ in g["stok_bitiyor"]["urunler"]] == ["B", "A"]   # en kısa süre önce; EOL yok
    assert "5 günde biter" in g["stok_bitiyor"]["urunler"][0][1]
    assert [r["sku"] for r, _ in g["olu_yavas"]["urunler"]] == ["C"]
    assert "ÖLÜSTOK" not in g["olu_yavas"]["urunler"][0][1]              # büyük harf / emoji temiz
    assert "%12,5" in g["zarar"]["urunler"][0][1]
    assert [r["sku"] for r, _ in g["eksik_veri"]["urunler"]] == ["E"]
    assert g["stok_bitiyor"]["hedef"] == "📦  Sipariş Önerisi"


def test_bos_grup_listelenmez():
    from kayranpm.genel_hesap import yapilacaklar
    assert [x["anahtar"] for x in yapilacaklar([_u("Z")])] == []


# ── Dağılımlar ──────────────────────────────────────────────────────
def test_kapsama_dagilimi():
    from kayranpm.genel_hesap import kapsama_dagilimi
    d = {e: (n, s) for e, n, s in kapsama_dagilimi(ROWS)}
    assert d["0–30 gün"][0] == 3                                         # A, B, F
    assert d["61–135 gün"][0] == 2                                       # D, E (70)
    assert d["Satış yok"][0] == 1                                        # C


def test_kategori_ozeti_birlesir():
    from kayranpm.genel_hesap import kategori_ozeti
    k = {r["Kategori"]: r for r in kategori_ozeti(ROWS)}
    assert set(k) == {"Monitör", "Kasa"}                                 # "kasa" ve "Kasa" tek satır
    assert k["Kasa"]["Ürün"] == 2 and k["Kasa"]["Ölü / yavaş"] == 1
    assert k["Monitör"]["Acil"] == 2


def test_kanal_ozeti():
    from kayranpm.genel_hesap import kanal_ozeti
    k = {r["kanal"]: r for r in kanal_ozeti(ROWS)}
    assert k["VATAN"]["stok"] == 240 and k["VATAN"]["satis"] == 60
    assert k["G5F depo"]["stok"] == 60 * 5 + 90


def test_haftalik_seri_ve_sku_filtresi():
    from kayranpm.genel_hesap import haftalik_seri
    fr = [{"yukleme_tarihi": "2026-09-22", "sku": "A", "haftalik_satis": 5, "satis_magaza": 1},
          {"yukleme_tarihi": "2026-09-24", "sku": "B", "haftalik_satis": 4},
          {"yukleme_tarihi": "2026-09-29", "sku": "A", "haftalik_satis": 7},
          {"yukleme_tarihi": "2026-09-29", "sku": "X", "haftalik_satis": 100}]
    s = haftalik_seri(fr, {"A", "B"}, date(2026, 10, 2), n=3)
    assert s == [(date(2026, 9, 14), 0), (date(2026, 9, 21), 10), (date(2026, 9, 28), 7)]


def test_trend_listeleri():
    from kayranpm.genel_hesap import trend_listeleri
    yuk, dus = trend_listeleri(ROWS)
    assert [r["sku"] for r in yuk] == ["D"] and [r["sku"] for r in dus] == ["E"]


def test_yaklasan_varislar():
    from kayranpm.genel_hesap import yaklasan_varislar
    assert [r["sku"] for r in yaklasan_varislar(ROWS, date(2026, 10, 2))] == ["E", "A"]


# ── Ekran ───────────────────────────────────────────────────────────
def test_sayfa_yeni_ekrana_bagli():
    m = _oku("kayranpm/main.py")
    a = m.index('if sayfa == "📊  Dashboard":')
    g = m[a:m.index('elif sayfa == "📋  Tüm Ürünler":')]
    assert "genel_bakis" in g and "acil_items_list" not in g
    e = _oku("kayranpm/genel_bakis.py")
    assert "dashboard_filtrele(" in e                                    # filtre her bölüme
    assert "urun_etiketi(" in e and "B.tiklanir(" in e
    assert "serit(\"musteri_haftalik\")" in e or "musteri_haftalik" in e  # veri tazeliği
    assert "st.stop()" not in e and "uppercase" not in e


# ── Talep düğmesi ───────────────────────────────────────────────────
def test_talep_ust_menude_yuzen_dugme_yok():
    a = _oku("app.py")
    assert ".st-key-fab_talep{position:fixed" not in a
    assert 'key="fab_talep"' not in a
    nav = a[a.index('with st.container(key="ustnav"):'):]
    nav = nav[:nav.index("\ndef ", 1)]
    assert "_talep_dugmesi(" in nav


def test_kategori_sutunlari_para_sayilmaz():
    """'Haftalık satış' adlı sütun ortak tabloda PARA sayılıyordu (adetler $ ile görünürdü)."""
    from shared.tasarim import _tablo_kolon_tipi
    from kayranpm.genel_hesap import kategori_ozeti
    for k in kategori_ozeti(ROWS)[0]:
        assert _tablo_kolon_tipi(k) != "para", k


def test_talep_merkezinde_tanimsiz_ad_yok():
    """Düğme taşınırken pencerenin 'Gelen Talepler (N)' başlığı silinen _acik'i
    kullanıyordu (pyflakes yakaladı) — yönetici pencereyi açınca hata alırdı."""
    a = _oku("app.py")
    g = a[a.index("def _talep_merkezi("):a.index("def _talep_ac_isaretle(")]
    assert "_acik" in g and g.index("_acik = 0") < g.index("Gelen Talepler")


def test_stok_tukendi_metni():
    from kayranpm.genel_hesap import yapilacaklar
    g = yapilacaklar([_u("Z", siparis_durum="acil", stok_bitis_gun=0)])
    assert g[0]["urunler"][0][1].startswith("stok tükendi")              # "0 günde biter" değil
