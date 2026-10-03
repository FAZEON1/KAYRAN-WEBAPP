# -*- coding: utf-8 -*-
"""Grafik dili (Ekim 2026): ortak Plotly düzeni ve renk kuralı.

Renk yalnız anlam taşır: ana seri ana renk (mor), ikinci seri nötr (soluk), ortalama/eğilim
silik kesikli; yeşil / kırmızı / amber yalnız işaret (eksi gün, ödenen / bekleyen).
İstisna: kategori halkası (renkler kategoriyi ayırır)."""
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
DOSYALAR = ("kayranacc/main.py", "shared/patron.py", "satis/main.py", "kayranpm/genel_bakis.py")


def test_ortak_duzen():
    import plotly.graph_objects as go
    from shared.grafik import duzen
    from shared.tasarim import renk
    f = duzen(go.Figure(), yukseklik=240, yaxis=dict(tickprefix="$"))
    L = f.layout
    assert L.paper_bgcolor == "rgba(0,0,0,0)" and L.plot_bgcolor == "rgba(0,0,0,0)"
    assert L.separators == ",." and L.height == 240 and "Inter" in L.font.family
    assert L.hoverlabel.bgcolor == renk("yuzey2") and L.yaxis.zeroline is False
    assert L.yaxis.gridcolor == renk("kenar") and L.xaxis.showgrid is False
    assert L.yaxis.tickprefix == "$"                              # grafiğe özel ayar korunur


def test_renk_rolleri():
    from shared.grafik import rol
    from shared.tasarim import renk
    assert rol("ana") == renk("mor") and rol("ikincil") == renk("soluk")
    assert rol("kotu") == renk("kirmizi") and rol("iyi") == renk("yesil")


def test_eksi_degerler_kirmizi():
    from shared.grafik import isaretli, rol
    assert isaretli([5, -2, 0], "ana") == [rol("ana"), rol("kotu"), rol("ana")]


def test_saydam():
    from shared.grafik import saydam
    assert saydam("#818CF8", 0.1) == "rgba(129,140,248,0.1)"


def test_grafikler_ortak_gosterimde():
    for d in DOSYALAR:
        s = (KOK / d).read_text(encoding="utf-8")
        assert "st.plotly_chart(" not in s, d
        assert "rgba(99,102,241" not in s, d                       # elle renk (açık temada değişmiyordu)


def test_halka_orta_yazisi_cumle_duzeninde():
    s = (KOK / "kayranacc/main.py").read_text(encoding="utf-8")
    assert ">TOPLAM</span>" not in s and ">ÖDENEN (TUTAR)</span>" not in s


def test_halka_yuzdesi_turkce():
    import plotly.graph_objects as go
    from shared.grafik import halka
    f = halka(go.Figure(go.Pie(labels=["Ödendi", "Bekliyor"], values=[39.4, 60.6])), "Ödenen", "%39")
    assert list(f.data[0].text) == ["%39,4", "%60,6"] and f.data[0].textinfo == "text"
