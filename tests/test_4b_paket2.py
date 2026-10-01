# -*- coding: utf-8 -*-
"""Aşama 4b · Paket 2 — Ürün Yön. (3) · İthalat (1) · Teknik Servis (1) tabloları
ortak araca taşındı; hiçbir modülde elle yazılmış <table> kalmadı."""
import pandas as pd
from pathlib import Path

from shared.tasarim import _tr_tam, df_tablo_html, tablo_html

KOK = Path(__file__).resolve().parent.parent


def test_tam_bicim_yuvarlamaz():
    assert _tr_tam(1234) == "1.234" and _tr_tam(1234.5) == "1.234,5"
    assert _tr_tam(1234.5678) == "1.234,5678" and _tr_tam(-0.5) == "-0,5"
    assert _tr_tam(12.345, 2) == "12,35" and _tr_tam("x") == ""


def test_df_tablo_html_kolon_tipleri():
    df = pd.DataFrame([{"SKU": "A", "Birim FOB": 12.3456, "% Maliyet": 6.4, "Adet": 3, "Kâr": -2.0, "Durum": "bekliyor", "Ad": "x" * 50}])
    h = df_tablo_html(df, para=["Birim FOB"], yuzde=["% Maliyet"], kar=["Kâr"], sol=["SKU"],
                      kisa={"Ad": 10}, tam=True, satir_vurgu=("Durum", {"bekliyor": "amber"}))
    assert '<td class="sag sayi">12,3456</td>' in h          # tam=True: yuvarlama yok
    assert "%6,40" in h and '<td class="sag sayi">3</td>' in h
    assert "color:var(--k-kirmizi)" in h and "-$2,00" in h    # kâr eksi → kırmızı
    assert 'data-vurgu="amber"' in h and '<td class="kisa">' in h
    # tam=False: sayılar en çok 2 hane, para akıllı
    h2 = df_tablo_html(df, para=["Birim FOB"], gizle=["Ad"])
    assert "12,3456" in h2 and "Ad</th>" not in h2
    assert "Gösterilecek veri yok" in df_tablo_html(pd.DataFrame())


def test_moduller_ortak_tabloya_tasindi():
    for m in ("ithalat/main.py", "kayranpm/main.py", "teknikservis/main.py", "kayranacc/main.py"):
        kod = (KOK / m).read_text(encoding="utf-8")
        assert "<table" not in kod and "</table>" not in kod, m
    pm = (KOK / "kayranpm/main.py").read_text(encoding="utf-8")
    assert "def _pf(" not in pm                                        # metin geri ayrıştırma yok
    # Kampanya tablosu Ekim 2026'da kayranpm/kampanya.py'ye taşındı: düzenlenebilir
    # tablo (st.data_editor) ham sayılarla çalışır; hesap kampanya_hesap.py'de.
    km = (KOK / "kayranpm/kampanya.py").read_text(encoding="utf-8")
    assert "<table" not in km and "def _pf(" not in km and "H.urun_hesap(" in km
    assert "df_tablo_html(" in pm and pm.count("tablo_html(") >= 2
    assert "satir_durum" in pm and '"rk-grn": "yesil"' in pm           # eski durum adları kabul
    it = (KOK / "ithalat/main.py").read_text(encoding="utf-8")
    assert "df_tablo_html(df, para=para, yuzde=yuzde, sol=sol, kisa=kisalt, tam=True)" in it
    ts = (KOK / "teknikservis/main.py").read_text(encoding="utf-8")
    assert "Servis listesi: ortak tablo_html" in ts and "Ham(_sla_chip(k))" in ts


def test_kampanya_urun_tablosu_ham_sayi():
    """Eski kontrol (rows_ku metin alanları) kampanya ekranı yenilenince anlamını
    yitirdi. Yerine: düzenlenebilir tablo ham sayı tutar, biçimi sütun verir."""
    km = (KOK / "kayranpm/kampanya.py").read_text(encoding="utf-8")
    assert '"Satış": h["satis"]' in km and 'format="dollar"' in km

def test_ts_tarih_gg_aa_yyyy():
    import types, sys
    sys.modules.setdefault("supabase", types.SimpleNamespace(create_client=lambda *a, **k: None, Client=object))
    from teknikservis.main import _tarih_kisa
    assert _tarih_kisa("2026-09-30T00:00:00") == "30.09.2026"
    assert _tarih_kisa("2026-09-30T14:05:00") == "30.09.2026 14:05"
    assert _tarih_kisa("") == "—"
