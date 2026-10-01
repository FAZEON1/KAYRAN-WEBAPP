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
    # Gelenler Geçmişi: metin değil gerçek tarih (tablo_kolonlari GG.AA.YYYY basar)
    assert '"Tarih": str(t.get("tarih", ""))[:10]' not in kod
    assert '"Tarih": _pd.to_datetime(str(t.get("tarih", ""))[:10], errors="coerce")' in kod


def test_ciro_grafigi_tr_ondalik():
    """_kfmt ana sayfa fonksiyonunun İÇİNDE; kaynaktan ast ile çıkarıp çalıştır."""
    kaynak = _oku("shared/ui.py")
    fn = next(d for d in ast.walk(ast.parse(kaynak))
              if isinstance(d, ast.FunctionDef) and d.name == "_kfmt")
    ns = {}
    exec("from shared.tasarim import tr_sayi\n" + textwrap.dedent(ast.get_source_segment(kaynak, fn)), ns)
    f = ns["_kfmt"]
    assert f(6800) == "6,8K"
    assert f(44200) == "44,2K"
    assert f(2000) == "2K"
    assert f(980) == "980"


def test_edefter_bos_hesap_none_yazmaz():
    kod = _oku("kayranacc/edefter.py")
    assert '{"Hesap": None, "Açıklama": ""' not in kod
    assert '{"Hesap": "", "Açıklama": ""' in kod
