# -*- coding: utf-8 -*-
"""Görünüm birliği (Ekim 2026): 53 sayfa tarandı, genel düzenden ayrılan 20 madde düzeltildi.
Bu testler düzeltmelerin geri gelmemesini denetler."""
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _oku(p):
    return (KOK / p).read_text(encoding="utf-8")


def test_streamlit_ingilizce_kaliplari_turkce():
    import shared.ceviri as C
    assert C.SOZLUK["Upload"] == "Dosya seç" and C.SOZLUK["Choose options"] == "Seç…"
    import re
    d, y = C.KALIPLAR[0]
    assert re.sub(d, y.replace("$", "\\"), "200MB per file • XLSX, XLS") == "Dosya başına en fazla 200 MB • XLSX, XLS"
    assert "from shared.ceviri import kur as _ceviri_kur" in _oku("app.py")


def test_baslik_material_ikon():
    from shared.tasarim import baslik
    h = baslik(":material/monitoring: Yönetim", "Yönetim panosu")
    assert "k-baslik-ikon" in h and "monitoring" in h and ">Yönetim<" in h and ":material/" not in h
    for p, ik in (("yonetim.py", "monitoring"), ("kayranpm/stok_yasi_ekran.py", "hourglass_bottom"),
                  ("teknikservis/ariza_ekran.py", "troubleshoot"), ("shared/yukleme_gecmisi.py", "history"),
                  ("shared/veri_sagligi.py", "health_and_safety")):
        assert f":material/{ik}:" in _oku(p), p


def test_eski_tip_basliklar_gitti():
    a = _oku("app.py")
    for eski in ('st.markdown("## 🧾 Sistem Kayıtları")', 'st.markdown("## 👥 Kullanıcı Yönetimi")',
                 "text-transform:uppercase\">Güvenlik</span>", '"⚠️ Başarısız stok işlemleri"'):
        assert eski not in a, eski
    assert 'placeholder="Modül seç…"' in a


def test_tarih_noktali():
    from shared.utils import gun_ay_yil
    assert gun_ay_yil("2026-07-01") == "01.07.2026"


def test_ortak_css():
    t = _oku("shared/tasarim.py")
    assert ':has(> [data-testid="stColumn"]:first-child .k-baslik):has(button)' in t      # #7 başlık çizgisi
    assert 'div[data-testid="stExpander"] :is([data-baseweb="input"]' in t                  # #11-12 kutusuz alan


def test_sayfaya_ozel():
    assert "sayfa-baslik-cizgi\"></div>'" not in _oku("kayranpm/main.py")                     # #6
    assert "07_odeme_erteleme.sql uygulanmış" not in _oku("kayranacc/odeme_ekran.py")          # #16
    assert '_mrd("Net kâr"' in _oku("satis/main.py") and '"Σ TOPLAM"' not in _oku("satis/main.py")  # #10
    assert 'key="yi_yeni_stok", horizontal=True' in _oku("kayranpm/yurtici_ekran.py")         # #13
    i = _oku("ithalat/main.py")
    assert '"🗑"' not in i and "background: linear-gradient(135deg,var(--k-yuzey3)" not in i  # #18
    assert "_md1, _md2, _ = st.columns" in i                                                  # #17


def test_yonetim_standart_gezinme():
    from shared.gezinme import secenekler
    assert secenekler("yonetim")[0] == "Özet"
    y = _oku("yonetim.py")
    assert 'sidebar_ust("", "Yönetim", "yonetim")' in y and "JetBrains" not in y
    assert "Tüm yıl görünümü" not in y
