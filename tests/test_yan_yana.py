# -*- coding: utf-8 -*-
"""Liste ve detay yan yana (Ekim 2026) — Tüm Ürünler.

Geniş ekranda liste solda, detay sağda (pencere yok, her şey tıklanabilir).
900 px altında liste CSS ile gizlenir; eskisi gibi detay + "Listeye dön".
"""
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _oku(p):
    return (KOK / p).read_text(encoding="utf-8")


def _tum_urunler_detay():
    s = _oku("kayranpm/main.py")
    i = s.index('elif sayfa == "📋  Tüm Ürünler":')
    j = s.index('elif sayfa == "💵  Yurt İçi Alış":')
    g = s[i:j]
    return g[g.index("B.koru("):]                       # detay dalı


def test_geri_alma_anahtari_tek_satir():
    assert len(re.findall(r"^YAN_YANA = (True|False)\s", _oku("shared/tasarim.py"), re.M)) == 1


def test_detay_dalinda_iki_sutun_ve_dar_liste():
    g = _tum_urunler_detay()
    assert "YAN_YANA" in g and "st.columns(" in g
    assert 'key="pm_liste_sol"' in g and "liste(urun_data, dar=True" in g
    assert 'key="pm_detay_sag"' in g


def test_dar_ekranda_liste_gizli_kapat_dugmesi_genis_ekranda():
    css = _oku("kayranpm/urunler_ekran.py")
    assert "YAN_YANA_CSS" in css
    from kayranpm.urunler_ekran import YAN_YANA_CSS
    assert "@media (max-width:900px)" in YAN_YANA_CSS and ".st-key-pm_liste_sol" in YAN_YANA_CSS
    assert ".st-key-pm_urun_kapat" in YAN_YANA_CSS and ".st-key-pm_urun_geri" in YAN_YANA_CSS


def test_dar_listede_disa_aktarma_yok_secili_vurgulu():
    src = _oku("kayranpm/urunler_ekran.py")
    g = src[src.index("def liste("):]
    g = g[:g.index("\ndef ", 10)]
    assert "dar=False" in g and "and not dar" in g          # Excel/PDF yalnız tam listede
    s2 = src[src.index("def _satir("):src.index("def liste(")]
    assert "pu-sr secili" in s2 or "secili" in s2
    from kayranpm.urunler_ekran import SATIR_CSS
    assert ".pu-sr.secili" in SATIR_CSS


# ── Ortak yardımcı + Depo › Bekleyen sevk takibi ───────────────────
def test_ortak_yan_yana_css():
    from shared.bilesen import yan_yana_css
    c = yan_yana_css("dpo_mt")
    assert ".st-key-dpo_mt_liste_sol" in c and ".st-key-dpo_mt_kapat" in c and ".st-key-dpo_mt_geri" in c
    assert "@media (max-width:900px)" in c
    assert ".st-key-pm_liste_sol" in yan_yana_css("pm_urun", liste_key="pm_liste_sol")


def test_tum_urunler_ortak_css_kullanir():
    assert "yan_yana_css(" in _oku("kayranpm/urunler_ekran.py")


def test_bekleyen_sevk_yan_yana():
    s = _oku("depo/bekleyen_ekran.py")
    r = s[s.index("def render("):]
    assert "YAN_YANA" in r and "st.columns(" in r and '_liste_sol"' in r and "dar=True" in r
    d = s[s.index("def _detay("):s.index("def render(")]
    assert "B.kapat(ON_EK)" in d


def test_bekleyen_dar_listede_suzgec_ezilmez_hareket_tablosu_yok():
    s = _oku("depo/bekleyen_ekran.py")
    g = s[s.index("def _liste("):s.index("def _tum_hareketler(")]
    assert "dar=False" in g and "if not dar:\n        B.geri_yukle(FILTRE_KEYS)" in g
    assert "if not dar:\n        _tum_hareketler(mt)" in g
