# -*- coding: utf-8 -*-
"""Küçük gösterim düzeltmeleri (30.09.2026) — geri gelmesinler.

- Firma Çekleri: vadesi geçmiş ödenmemiş çek kırmızı satır olmalı. Eskiden
  vade_durumu() sonucu ("gecmis") bugünün tarih metniyle karşılaştırılıyordu,
  koşul hiç tutmuyordu. Renkli satırlar Muhasebe'nin zebra kuralını (!important)
  ezebilmeli, yoksa yeşil/kırmızı hiç görünmüyor.
- Muhasebe tarihleri GG.AA.YYYY (eskiden 12-12-2025 / 2026-05-31).
- Ana sayfa ciro grafiği: 6,8K (eskiden 6.8K).
- e-Defter fiş tablosunda boş "Hesap" hücresi "None" yazmamalı.
"""
import ast
import re
import textwrap
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _oku(p):
    return (KOK / p).read_text(encoding="utf-8")


def test_gecikmis_cek_kirmizi_satir():
    kod = _oku("kayranacc/main.py")
    assert 'vd_raw < str(__import__("datetime").date.today())' not in kod
    i = kod.index("def cek_tablo(")
    blok = kod[i:kod.index("tab1, tab2 = st.tabs(", i)]
    # vade_durumu() sonucuyla karşılaştırılır; satır vurgusu ortak tabloya verilir
    assert 'row["_vd"] == "gecmis"' in blok and 'return "kirmizi"' in blok
    assert 'row["_vd"] == "bugun"' in blok and 'return "amber"' in blok
    assert 'if row["_odendi"]:' in blok and 'return "yesil"' in blok
    assert "tablo_html(" in blok and "vurgu=_vurgu" in blok


def test_muhasebe_tarih_bicimi():
    kod = _oku("kayranacc/main.py")
    assert 'strftime("%d-%m-%Y")' not in kod
    assert 'return d.strftime("%d.%m.%Y")' in kod
    # Nakit Akış tablosu hücresi TR tarih
    assert '"Tarih": row["Tarih"] if row["Tarih"] == "TOPLAM" else fmt_tarih(row["Tarih"])' in kod
    # Gelenler Geçmişi (Ekim 2026: kayranacc/gelen_ekran.py): tarih Türkçe gün
    # adıyla yazılır ("30 Eylül, Çar"), ay adı AY listesinden — İngilizce strftime yok.
    g = _oku("kayranacc/gelen_ekran.py")
    assert "strftime" not in g and 'f"{d.day} {AY[d.month]}, {GUN_KISA[d.weekday()]}"' in g


def test_ciro_grafigi_tr_ondalik():
    """Ekim 2026: patron panosu grafiği shared/patron.py'de (plotly). Nokta üstü kısaltılmış
    etiketler (eski _kfmt: '6,8K') kalabalık yaptığı için kaldırıldı; eksen ve üzerine
    gelme kutusu Türkçe biçimli olmalı."""
    from datetime import date
    from shared.patron import _grafik
    fg = _grafik([(date(2026, 9, 1), 6800.5, 1234.0), (date(2026, 9, 2), 44200.0, -50.0)])
    assert fg.layout.separators == ",."                                # 6.800 / 6,8
    hov = list(fg.data[0].customdata)
    assert "ciro $6.800" in hov[0] and "net kâr $1.234" in hov[0] and "01.09 Sal" in hov[0]


def test_edefter_bos_hesap_none_yazmaz():
    kod = _oku("kayranacc/edefter.py")
    assert '{"Hesap": None, "Açıklama": ""' not in kod
    assert '{"Hesap": "", "Açıklama": ""' in kod
