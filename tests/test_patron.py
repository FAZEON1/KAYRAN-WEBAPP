# -*- coding: utf-8 -*-
"""Patron panosu yeniden tasarım (Ekim 2026).

Eski panoda: kartlar canlı satış görünümünden (v_satis_pnl), grafik gece tazelenen
ayrı bir özet tablodan (mv_gunluk_pnl) besleniyordu — rakamlar tutmuyordu; grafik
yalnız satış olan günleri eşit aralıkla çiziyordu (zaman ekseni yanlış, tarih yok);
"bu ay" ayın ilk günlerinde 2 günü kıyassız gösteriyordu; tarih sunucu (UTC) günüydü.
Yeni pano: tek kaynak, önceki dönemin aynı gün sayısıyla kıyas, takvim günlü grafik,
kanal payı, tıklanır veri kalitesi. Hesaplar shared/patron.py'de.
"""
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


def _P():
    from shared import patron
    return patron


def test_donem_bu_ay_onceki_ayin_ayni_gunleri():
    P = _P()
    d = P.donem_araligi("Bu ay", date(2026, 10, 2))
    assert (d["bas"], d["bit"]) == (date(2026, 10, 1), date(2026, 10, 2))
    assert (d["onceki_bas"], d["onceki_bit"]) == (date(2026, 9, 1), date(2026, 9, 2))
    d = P.donem_araligi("Bu ay", date(2026, 3, 31))                      # Şubat 28 gün
    assert d["onceki_bit"] == date(2026, 2, 28)
    d = P.donem_araligi("Bu ay", date(2026, 1, 15))
    assert (d["onceki_bas"], d["onceki_bit"]) == (date(2025, 12, 1), date(2025, 12, 15))


def test_donem_son_30_ve_ceyrek():
    P = _P()
    d = P.donem_araligi("Son 30 gün", date(2026, 10, 2))
    assert (d["bas"], d["onceki_bas"], d["onceki_bit"]) == (date(2026, 9, 3), date(2026, 8, 4), date(2026, 9, 2))
    d = P.donem_araligi("Bu çeyrek", date(2026, 11, 15))
    assert (d["bas"], d["onceki_bas"], d["onceki_bit"]) == (date(2026, 10, 1), date(2026, 7, 1), date(2026, 8, 15))


ROWS = [
    {"tarih": "2026-09-01", "kanal": "VATAN", "ciro": 1000, "destek": 0, "net_kar": 200, "adet": 2},
    {"tarih": "2026-09-02", "kanal": "HB", "ciro": 500, "destek": 0, "net_kar": 50, "adet": 1},
    {"tarih": "2026-10-01", "kanal": "VATAN", "ciro": 1200, "destek": 100, "net_kar": 330, "adet": 3},
    {"tarih": "2026-10-02", "kanal": "HB", "ciro": 600, "destek": 0, "net_kar": 60, "adet": 1},
]


def test_ozet_ve_kiyas():
    P = _P()
    o = P.ozet([r for r in ROWS if r["tarih"] >= "2026-10-01"])
    assert o["ciro"] == 1800 and o["net_kar"] == 390
    assert round(o["marj"], 2) == round(390 / 1700 * 100, 2)              # net kâr ÷ (ciro − destek)
    assert P.degisim(1800, 1500) == 20.0 and P.degisim(10, 0) is None


def test_gunluk_seri_bos_gunler_sifir():
    P = _P()
    s = P.gunluk_seri(ROWS, date(2026, 9, 1), date(2026, 9, 5))
    assert [x[0] for x in s] == [date(2026, 9, i) for i in range(1, 6)]   # her takvim günü
    assert [x[1] for x in s] == [1000, 500, 0, 0, 0]
    assert P.hareketli_ort([1, 2, 3, 4], 2) == [1.0, 1.5, 2.5, 3.5]


def test_kanal_payi_ilk_n_ve_diger():
    P = _P()
    rows = [{"kanal": k, "ciro": c} for k, c in (("A", 50), ("B", 30), ("C", 15), ("D", 5))]
    k = P.kanal_payi(rows, n=2)
    assert [x[0] for x in k] == ["A", "B", "Diğer"] and k[-1][1] == 20 and k[0][2] == 50.0


def test_kart_turkce_rakam_ve_kiyas():
    P = _P()
    h = P.kart_html("Ciro", 678033, 600000, "para", [1, 2, 3], "mor")
    assert "678.033" in h and "678,033" not in h and "%13" in h and "▲" in h
    h = P.kart_html("Marj", 30.94, 32.14, "yuzde", [], "yesil")
    assert "%30,9" in h and "1,2 puan" in h and "▼" in h
    assert "önceki dönemde satış yok" in P.kart_html("Ciro", 5, 0, "para", [], "mor")


def test_ana_sayfa_yeni_panoyu_kullanir():
    a = _oku("app.py")
    g = a[a.index("# ─── PATRON PANOSU"):a.index("# ─── İŞ KPI KARTLARI")]
    assert "from shared.patron import render" in g and "patron_panosu_html" not in g
    u = _oku("shared/tasarim.py")
    p0 = _oku("shared/patron.py")
    assert "def patron_panosu_html" not in u and "get_gunluk_pnl" not in p0 and 'table("mv_gunluk_pnl")' not in p0
    p = _oku("shared/patron.py")
    assert "get_satis_pnl_view(" in p and "tr_today" in p and "st.fragment" in p
    assert "segmented_control(" in p and "uppercase" not in p


def test_kanal_payi_gorunen_ada_gore_birlesir():
    """ITOPYA ve EERA aynı görünen ada ('EERA') eşlenince kanal payında iki ayrı satır oluyordu."""
    P = _P()
    rows = [{"kanal": "ITOPYA", "ciro": 60}, {"kanal": "EERA", "ciro": 40}, {"kanal": "VATAN", "ciro": 100}]
    k = P.kanal_payi(rows, ad_fn=lambda x: "EERA" if x in ("ITOPYA", "EERA") else x)
    assert [(a, c) for a, c, _ in k] == [("EERA", 100), ("VATAN", 100)] or \
           [(a, c) for a, c, _ in k] == [("VATAN", 100), ("EERA", 100)]
