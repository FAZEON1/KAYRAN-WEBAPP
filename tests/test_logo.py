# -*- coding: utf-8 -*-
"""Kurumsal logo (Ekim 2026, seçenek 03 "Modüler ızgara"): 3×3 karelik K.
Tek kaynak shared.tasarim.kayran_logo_svg; giriş ekranı, sol menü ve sekme
simgesi (page_icon) bunu kullanır."""
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _kareler(svg):
    return re.findall(r'<rect x="(\d+)" y="(\d+)" width="12" height="12" rx="3" fill="(#[0-9A-F]{6})"', svg)


def test_logo_k_izgarasi():
    from shared.tasarim import kayran_logo_svg
    svg = kayran_logo_svg()
    kare = {(int(x), int(y)): r for x, y, r in _kareler(svg)}
    assert len(kare) == 9
    # K: sol sütun dolu, orta kehribar, sağ üst ve sağ alt dolu; kalanlar sönük
    dolu = {(10, 10), (10, 26), (10, 42), (42, 10), (42, 42)}
    assert {k for k, r in kare.items() if r == "#FFFFFF"} == dolu
    assert kare[(26, 26)] == "#F5A524"
    assert {k for k, r in kare.items() if r == "#263042"} == {(26, 10), (26, 42), (42, 26)}
    assert 'fill="#111827"' in svg


def test_logo_boyut_ve_erisilebilirlik():
    from shared.tasarim import kayran_logo_svg
    assert 'width="28" height="28"' in kayran_logo_svg(28)
    assert 'aria-hidden="true"' in kayran_logo_svg()
    assert 'role="img" aria-label="KAYRAN"' in kayran_logo_svg(64, etiket=True)
    # page_icon olarak verilir: Streamlit '<svg ' ile başlayan metni SVG sayar
    assert kayran_logo_svg(64).startswith("<svg ")


def test_uygulama_logoyu_kullanir():
    a = (KOK / "app.py").read_text(encoding="utf-8")
    assert 'page_icon="🏢"' not in a
    assert re.search(r"page_icon=kayran_logo_svg\(", a)
    assert "818CF8\"/><stop" not in a          # eski degrade logo kalmadı
    assert "KAYRAN_LOGO_SVG = kayran_logo_svg(" in a
    assert "KAYRAN_LOGO_BIG = kayran_logo_svg(" in a


def test_logo_veri_adresi():
    """CSS arka planı için: aynı SVG, data: adresi olarak (tek kaynak)."""
    from urllib.parse import unquote
    from shared.tasarim import kayran_logo_svg, kayran_logo_uri
    u = kayran_logo_uri(28)
    assert u.startswith("data:image/svg+xml,")
    assert unquote(u[len("data:image/svg+xml,"):]) == kayran_logo_svg(28)


def test_logo_ust_seritte_ana_sayfa_dugmesi():
    """Kenar çubuğu kalkınca (Eki 2026) logo uygulama içinden kaybolmuştu. Yeri: üst şeridin sol
    başı — ana sayfa düğmesi logodur (tıklayınca ana sayfa), adı ipucu ve ekran okuyucuda kalır."""
    a = (KOK / "app.py").read_text(encoding="utf-8")
    g = a[a.index("def ust_navigasyon"):a.index("\ndef ", a.index("def ust_navigasyon") + 10)]
    assert "kayran_logo_uri(" in g and ".st-key-top_anasayfa" in g
    assert '("Ana Sayfa", "anasayfa"' in g          # düğme ve adı duruyor (ipucu / erişilebilirlik)
