# -*- coding: utf-8 -*-
"""Kişi menüsü sadeleşti (Ekim 2026): Yönetim'in "Şirket belgeleri" ve "Sistem" sayfaları kişi menüsüne
taşındı; benzer sayfalar tek düğmede toplandı (Verilerim, Sistem) ve sayfanın üstündeki seçiciyle gezilir."""
from pathlib import Path

from shared import gezinme as G

KOK = Path(__file__).resolve().parent.parent
APP = (KOK / "app.py").read_text(encoding="utf-8")


def _menu():
    return APP[APP.index("def _kisi_menu_icerik("):APP.index("def _arama_kutusu(")]


def test_yonetimden_tasindi():
    assert "Şirket belgeleri" not in G.secenekler("yonetim") and "Sistem" not in G.secenekler("yonetim")
    oz = {k: o for k, _a, _i, o in G.SISTEM}
    assert oz["sirket_belgeleri"] == "yonetim"
    assert oz["degisiklik_gunlugu"] == oz["yedekleme"] == "kullanici_yonetimi"
    # eski Yönetim adresi yeni yere gider
    assert G.YONETIM_TASINAN == {"Şirket belgeleri": "sirket_belgeleri", "Sistem": "degisiklik_gunlugu"}
    assert "_tasinan.get(st.session_state.get(\"yon_sayfa\"))" in APP
    for kod in ("sirket_belgeleri", "degisiklik_gunlugu", "yedekleme"):
        assert f'elif aktif == "{kod}":' in APP, kod
        assert G.hedef(f"sistem/{kod}") == {"modul": kod, "anahtar": None, "secenek": None}


def test_gruplar():
    kodlar = {k for k, *_ in G.SISTEM}
    for ad, _ikon, uyeler in G.SAYFA_GRUPLARI:
        assert set(uyeler) <= kodlar, ad
    assert G.sayfa_grubu("cop_kutusu") == ("Verilerim", [("yukleme_gecmisi", "Yükleme geçmişi"),
                                                         ("cop_kutusu", "Çöp kutusu"),
                                                         ("veri_sagligi", "Veri sağlığı")])
    assert [k for k, _ in G.sayfa_grubu("yedekleme")[1]] == ["degisiklik_gunlugu", "sistem_kayitlari",
                                                              "yedekleme", "tasarim_rehberi"]
    assert G.sayfa_grubu("soru") is None and G.sayfa_grubu("kullanici_yonetimi") is None


def test_menu_kisa():
    m = _menu()
    # gruptaki sayfaların tek tek düğmesi menüde yok
    for eski in ('"Çöp kutusu"', '"Yükleme geçmişi"', '"Veri sağlığı"', '"Sistem Kayıtları"', '"Tasarım Rehberi"'):
        assert eski not in m, eski
    assert '_grup_dugmesi("Verilerim")' in m and '_grup_dugmesi("Sistem")' in m
    assert '"Şirket belgeleri"' in m and 'ozel_yetki(aktif_kullanici, "yonetim")' in m
    # düğme tanımları (eskiden 10; taşınan iki sayfayla 12 olacaktı)
    assert m.count("st.button(") <= 8


def test_grup_seridi_sayfanin_ustunde():
    assert "_grup_seridi(aktif)" in APP
    g = APP[APP.index("def _grup_seridi("):APP.index("def _kisi_menu_icerik(")]
    assert "st.segmented_control(" in g and "on_change=_degis" in g and "ozel_yetki(ak, _ozel[k])" in g
