# -*- coding: utf-8 -*-
"""Sol menü daralt/genişlet düğmesi (app.py, enjekte betik) — 01.10.2026.

Sorun: menüsü boş bir sayfaya (Streamlit boş sidebar'ı KALDIRIR) geçip dönünce
düğme sola atlıyor ve menünün ÜSTÜNDE takılı kalıyordu (ölçüm: kenardan 273 px).
Nedenler: (1) izleyiciler ilk görülen, sonra sayfadan kalkan menüye bağlı kalıyordu;
(2) her rerun'da betik "düğme var" deyip hiçbir şey yapmadan çıkıyordu;
(3) 'left' geçiş animasyonu küçük farklarda bile kaydırıyordu.
Davranış önizlemede playwright ile sınandı (boş↔dolu↔uzun, daralt/genişlet, resize).
"""
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _betik():
    s = (KOK / "app.py").read_text(encoding="utf-8")
    i = s.index("# ── SIDEBAR AÇ/KAPAT + tema temizliği: TEK enjekte script")
    return s[i:s.index("# ── TIKLA-YAZ:", i)]


def test_rerunda_yeniden_baglanir():
    b = _betik()
    assert "if (doc.getElementById('kayran-sb-toggle')) return;" not in b
    assert "if (w.__kayranSbYenile) w.__kayranSbYenile();" in b
    assert "w.__kayranSbYenile = function () { bagla(); konumla(); };" in b


def test_yeni_menuye_baglanir_ve_her_degisimde_konumlar():
    b = _betik()
    assert "sb === w.__kayranSbIzlenen" in b                # aynı menüyse yeniden bağlama
    i = b.index("w.__kayranSbMO = new w.MutationObserver(")
    govde = b[i:i + 500]
    assert "bagla();" in govde and "konumla();" in govde


def test_menu_yoksa_gizli_ve_kayma_yok():
    b = _betik()
    assert "const gizle = !sb || dialogAcik();" in b
    assert "transition:left" not in b                       # konum kaymaz, yerine oturur
    assert "#FBBF24" not in b and "stroke=\"currentColor\"" in b   # sade, tema renkli
