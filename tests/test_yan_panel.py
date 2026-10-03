# -*- coding: utf-8 -*-
"""Yan panel (Ekim 2026) — seçilmiş okuma pencereleri sağdan açılan tam boy panel.

Yalnız CSS: pencere içine görünmez bir işaret basılır, :has() o pencereyi sağa alır.
Formlar (ekle / düzenle / sil) ortada kalır. Liste arkada görünür ama panel açıkken
kilitli (Streamlit'in pencere kilidi bilerek kaldırılmadı).
"""
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent

PANEL = [  # (dosya, pencere başlığı parçası, genişlik)
    ("satis/main.py", "Firma Sipariş Geçmişi", "orta"),
    ("kayranpm/stok_karti.py", "📦 Stok Kartı", "genis"),
    ("kayranpm/ref_no.py", "🔎 Ref No Detayı", "orta"),
    ("kayranpm/ref_ekran.py", '"Ref no detayı"', "orta"),
    ("kayranpm/ref_no.py", "🔎 Alınan Destek Detayı", "orta"),
    ("kayranpm/kampanya.py", '"Kampanya detayı"', "orta"),
    ("satis/satislar_ekran.py", '@st.dialog("Sipariş"', "orta"),
    ("kayranacc/gecmis_ekran.py", '"Ödenmiş ödeme"', "dar"),
    ("kayranacc/gecmis_ekran.py", '@st.dialog("Çek"', "dar"),
    ("satis/main.py", '"İade kaydı"', "dar"),
]
ORTADA = [("kayranacc/odeme_ekran.py", '@st.dialog("Ödeme"'),
          ("ithalat/main.py", "İthalat Dosyası — Detay")]


def _govde(dosya, parca):
    """Dekoratörün altındaki pencere fonksiyonunun gövdesi (iç içe tanımlar dahil)."""
    import ast
    src = (KOK / dosya).read_text(encoding="utf-8")
    satir = src[:src.index(parca)].count("\n") + 1
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef)
              and any(d.lineno == satir for d in n.decorator_list))
    return ast.get_source_segment(src, fn)


def test_isaret_html():
    from shared.tasarim import panel_isareti
    assert panel_isareti("genis") == '<style class="k-panel k-panel-genis"></style>'
    assert panel_isareti() == '<style class="k-panel k-panel-orta"></style>'


def test_css_yalniz_isaretli_pencereyi_saga_alir():
    from shared.tasarim import cekirdek_css
    css = cekirdek_css()
    assert '[data-testid="stDialog"]:has(.k-panel) [role="dialog"]' in css
    i = css.index('[data-testid="stDialog"]:has(.k-panel) [role="dialog"]')
    assert "background:var(--k-yuzey1)" in css[i:i + 700]          # saydam zemin içeriği sayfaya bindiriyordu
    for g, px in (("dar", 520), ("orta", 680), ("genis", 860)):
        assert f":has(.k-panel-{g})" in css and f"{px}px" in css


def test_secilen_pencereler_panel():
    for dosya, parca, g in PANEL:
        assert f'yan_panel("{g}")' in _govde(dosya, parca), (dosya, parca)


def test_formlar_ortada():
    for dosya, parca in ORTADA:
        assert "yan_panel(" not in _govde(dosya, parca), (dosya, parca)


def test_geri_alma_anahtari_tek_satir():
    src = (KOK / "shared" / "tasarim.py").read_text(encoding="utf-8")
    assert len(re.findall(r"^YAN_PANEL = (True|False)\s", src, re.M)) == 1
