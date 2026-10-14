# -*- coding: utf-8 -*-
"""Giriş formları yeni düzen (Ekim 2026, onaylı taslak): Satış girişi, Yurt içi alış, Yeni ithalat.
Türkçe sayı kutusu ("1.234,56"), sağdaki özet paneli, telefonda altta sabit özet; hesap ve kayıt aynı."""
import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))


def _F():
    p = KOK / "shared" / "form.py"
    assert p.exists(), "shared/form.py yok"
    from shared import form
    return form


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


def test_turkce_sayi_okunur():
    F = _F()
    oku = F.tr_sayi_oku
    assert oku("1.234,56") == 1234.56 and oku("1234,56") == 1234.56 and oku("26") == 26.0
    assert oku("26.5") == 26.5 and oku("41.2000") == 41.2 and oku("0.125") == 0.125     # nokta ondalık
    assert oku("1.234") == 1234.0 and oku("1.234.567") == 1234567.0                     # Türkçe binlik
    assert oku("$79,00") == 79.0 and oku(" 1 234,5 ") == 1234.5 and oku("") is None and oku(None) is None
    for kotu in ("abc", "1,2,3", "12a"):
        try:
            oku(kotu)
        except ValueError:
            continue
        raise AssertionError(kotu)


def test_turkce_sayi_yazilir():
    F = _F()
    assert F.tr_sayi_yaz(26) == "26,00" and F.tr_sayi_yaz(41.2, 4) == "41,2000"
    assert F.tr_sayi_yaz(1234.5) == "1.234,50" and F.tr_sayi_yaz(None) == ""


def test_ozet_paneli():
    F = _F()
    h = F.ozet_paneli("Sipariş özeti", [("Ciro", "$1.244,00"), ("<b>", "x")],
                      vurgu=("Net kâr", "$165,87", "yesil"), uyarilar=["1 kalemde marj düşük"])
    assert 'class="kf-ozet"' in h and "Sipariş özeti" in h and "$1.244,00" in h
    assert "&lt;b&gt;" in h                                                   # kaçışlı
    assert 'class="kf-sat kf-buyuk"' in h and "var(--k-yesil)" in h and 'class="kf-uyari"' in h


def test_telefonda_ozet_altta_sabit():
    c = _F().css()
    tel = c[c.index("@media (max-width: 640px)"):]
    assert '[data-testid="stColumn"]:has([class*="st-key-kf_ozet_"]){position:sticky;bottom:0' in tel
    # pencere kutusu overflow:hidden; yalnız formun penceresinde açılır (yoksa sticky çalışmıyordu)
    assert '[data-testid="stDialog"] div[data-rac]:has([class*="st-key-kf_ozet_"]){overflow:visible !important}' in tel
    assert '[class*="st-key-kf_ikincil_"]{display:none}' in tel


def test_satis_penceresi_yeni_duzen():
    s = _oku("satis/main.py")
    assert '@st.dialog("Yeni satış", width="large")' in s, "yeni satış penceresi yok"
    blok = s[s.index('@st.dialog("Yeni satış", width="large")'):s.index("# ── Açılış: bugünün özeti")]
    assert 'h1, h2, h3, h4 = st.columns([2.2, 1.15, 1.1, 1.3])' in blok          # belge bilgileri tek satır
    assert 'sol, sag = st.columns([2.75, 1], gap="medium")' in blok and 'st.container(key="kf_ozet_satis")' in blok
    assert '_F.sayi_kutusu("Birim satış $", "s_bsat"' in blok and "number_input(\"Birim Satış" not in blok
    assert "bu fiyatla brüt marj" in blok and "_kar_acik" in blok              # kâr yetkisi yoksa marj yok
    assert "s_tarih_degistir" not in blok                                    # tarih kutusu doğrudan
    # kayıt ve kontroller aynı
    for parca in ("ekle_siparis(g_tarih, g_kanal, sipno, g_not, gecerli)", "zararina_mi(", "gecerli_sku(",
                  "canli_stok(", "siparis_no_var_mi(", "kampanya_destek_bul(_sku, g_kanal, str(g_tarih))"):
        assert parca in blok, parca


def test_yurtici_yeni_duzen():
    y = _oku("kayranpm/yurtici_ekran.py")
    assert "    with sol:" in y, "yurt içi alış iki sütunlu değil"
    assert 'st.container(key="kf_ozet_yurtici")' in y and 'F.ozet_paneli("Alım özeti"' in y
    assert 'F.sayi_kutusu("Kur (TL / USD)"' in y and "F.sayi_kutusu(ad, f\"{on}_m_{slug}\"" in y
    assert 'number_input("Kur (TL / USD)"' not in y and '"Alım türü"' not in y
    # stok seçimi solda (telefonda alttaki sabit çubukta gizlenmesin)
    sol = y[y.index("    with sol:"):y.index('    with sag, st.container(key="kf_ozet_yurtici"):')]
    assert 'st.radio("Stok", [H.STOK_EKLE, H.STOK_VAR], key="yi_yeni_stok"' in sol
    assert "stok_ekle=(stok == H.STOK_EKLE)" in y


def test_ithalat_yeni_duzen():
    s = _oku("ithalat/main.py")
    blok = s[s.index("def _yeni_ithalat():"):s.index("def sablon_ithalat():")]
    assert 'sekme1, _sag = st.columns([2.75, 1], gap="medium")' in blok
    assert 'st.container(key="kf_ozet_ithalat")' in blok and '_F.ozet_paneli("Dosya özeti"' in blok
    assert '_F.sayi_kutusu("fob", f"m_fob_{i}_{_fv}"' in blok and 'f"m_indirim_{_fv}"' in blok
    assert not re.search(r'number_input\(\s*"fob"', blok)
    assert "fatura_indirim=m_indirim" in blok and "ekle_dosya(dosya_no.strip(), tarih, tedarikci" in blok
