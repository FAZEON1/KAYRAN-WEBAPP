# -*- coding: utf-8 -*-
"""Telefonda sabit alt menü (Ekim 2026): Ana sayfa · Modüller · Ara · Talep · Ben; üst şerit telefonda gizli."""
import ast
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
APP = (KOK / "app.py").read_text(encoding="utf-8")


def _govde(ad):
    agac = ast.parse(APP)
    d = next(n for n in agac.body if isinstance(n, ast.FunctionDef) and n.name == ad)
    return ast.get_source_segment(APP, d)


def test_bes_dugme_sirali():
    g = _govde("_alt_menu")
    sira = [g.index(x) for x in ('"Ana sayfa", key="alt_anasayfa"', 'st.popover("Modüller"', '"Ara", key="alt_ara"',
                                 '"Talep", key="alt_talep"', 'st.popover("Ben"')]
    assert sira == sorted(sira)
    assert 'on_click=_talep_ac_isaretle' in g and '_kisi_menu_icerik("_alt")' in g
    assert 'with st.container(key="alt_menu", horizontal=True)' in g


def test_moduller_yalniz_yetkili():
    g = _govde("_alt_menu")
    assert 'ozel_yetki(ak, "yonetim")' in g and 'ozel_yetki(ak, "kullanici_yonetimi")' in g
    assert 'bool(yet.get(kod))' in g


def test_yalniz_telefonda_ve_ust_serit_gizli():
    css = re.search(r'ALT_MENU_CSS = """(.*?)"""', APP, re.S).group(1)
    masa, tel = css.split("@media (max-width:640px){", 1)
    assert "html body .st-key-alt_menu, html body .k-mobil-ust{display:none !important;}" in masa
    assert "html body .st-key-ustnav{display:none !important;}" in tel
    assert "position:fixed !important" in tel and "env(safe-area-inset-bottom" in tel
    assert "padding-bottom:110px !important" in tel                  # içerik menünün altında kalmaz
    # Sağ altta Streamlit Cloud rozeti (uygulama dışı, gizlenemez): hücreler sola, sağda 112px boşluk
    assert "padding:4px 112px calc(8px + env(safe-area-inset-bottom,0px)) 4px !important" in tel
    assert "_alt_menu()" in APP and "_mobil_ust()" in APP


def test_kisi_menusu_iki_yerde_anahtar_cakismaz():
    g = _govde("_kisi_menu_icerik")
    anahtarlar = re.findall(r'key="([a-z_]+)"(?! \+ ek)', g)
    assert anahtarlar == [], anahtarlar                              # hepsi + ek almalı
    assert 'key=_tema_anahtar' in g


def test_genel_dugme_stili_alt_menuye_karismaz():
    from shared import tasarim as T
    assert ":not(.st-key-alt_menu *)" in T.DUGME_CSS and ":not(.st-key-alt_menu *)" in T.MOBIL_CSS
