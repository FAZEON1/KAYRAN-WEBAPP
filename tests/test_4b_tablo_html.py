# -*- coding: utf-8 -*-
"""Aşama 4b — ORTAK tablo (shared.tasarim.tablo_html).

Modüllerdeki elle yazılmış <table> HTML'leri bu araca taşınıyor; her tablo
aynı başlık, zebra, sayı hizası, rozet ve satır vurgusu kuralını paylaşır.
Paket 1: Muhasebe (Takvim · Nakit Akış · Firma Çekleri · Ödenenler).
Paket 2: Ürün Yön. (3) · İthalat (1) · Teknik Servis (1) — henüz taşınmadı.
"""
import re
from pathlib import Path

from shared.tasarim import Ham, kisalt, renkli, rozet_html, tablo_html

KOK = Path(__file__).resolve().parent.parent


def test_bos_tablo_mesaj():
    assert "Gösterilecek veri yok" in tablo_html(["A"], [])
    assert "<table" not in tablo_html(["A"], [], bos_mesaj="Çek yok")


def test_para_adet_oran_bicimi_ve_hiza():
    h = tablo_html([("Tutar", "para", "₺"), ("Adet", "adet"), ("Marj", "oran"), "Ad"],
                   [{"Tutar": 1234.5, "Adet": 1500, "Marj": 12.345, "Ad": "x"}])
    assert "₺1.234,50" in h and ">1.500<" in h and "%12,35" in h
    assert h.count('class="sag sayi"') == 3            # sayılar sağa, mono
    assert '<th class="sag">Tutar</th>' in h and "<th>Ad</th>" in h


def test_negatif_kirmizi_bos_hucre_ve_kacis():
    h = tablo_html([("Tutar", "para", "$"), "Ad"], [{"Tutar": -5, "Ad": "<b>x</b>"}, {"Tutar": None, "Ad": ""}])
    assert 'class="sag sayi neg">-$5,00' in h
    assert "&lt;b&gt;x&lt;/b&gt;" in h and "<b>x</b>" not in h   # DB'den gelen HTML çalışmaz
    assert h.count('class="silik">—') == 1 and 'class="sag silik">—' in h


def test_ham_rozet_renkli_kisalt_kacis_uygulanmaz():
    h = tablo_html(["D"], [{"D": rozet_html("ÖDENDİ", "yesil")}, {"D": renkli("a", "mavi", kalin=True)},
                           {"D": kisalt("x" * 60, 10)}, {"D": Ham("<i>ham</i>")}])
    assert 'class="k-rz" style="--r:var(--k-yesil)">ÖDENDİ' in h
    assert "font-weight:700;white-space:nowrap;color:var(--k-mavi)" in h
    assert 'title="' + "x" * 60 + '"' in h and ("x" * 9 + "…") in h
    assert '<td class="kisa">' in h                                 # kısaltma hücreye uygulanır
    assert "<i>ham</i>" in h
    assert "k-mor" in rozet_html("x", "olmayan-renk")        # bilinmeyen renk → mor


def test_vurgu_ve_toplam():
    h = tablo_html(["A", ("T", "para", "₺")], [{"A": "a", "T": 1}, {"A": "b", "T": 2}],
                   toplam={"A": "Σ", "T": 3},
                   vurgu=lambda r: "kirmizi" if r["A"] == "b" else "yok")
    assert h.count("data-vurgu=") == 1 and 'data-vurgu="kirmizi" style="--v:var(--k-kirmizi)"' in h
    assert "<tfoot><tr><td>Σ</td>" in h and "₺3,00" in h
    assert 'style="max-height:300px"' in tablo_html(["A"], [{"A": 1}], yukseklik=300)
    assert '<table class="k-tb sik">' in tablo_html(["A"], [{"A": 1}], sik=True)    # dar düzen


def test_tablo_css_tema_degiskenli():
    t = (KOK / "shared/tasarim.py").read_text(encoding="utf-8")
    i = t.index(".k-tbw{"); css = t[i:t.index('"""', i)]
    assert not re.search(r"#[0-9A-Fa-f]{3,6}\b", css)                # sabit renk yok
    assert "position:sticky;top:0" in css                      # yapışkan başlık
    assert "tr[data-vurgu] td{background:color-mix(in srgb,var(--v)" in css


def test_muhasebe_tablolari_ortak_araca_tasindi():
    kod = (KOK / "kayranacc/main.py").read_text(encoding="utf-8")
    assert "<table" not in kod and "</table>" not in kod and "<tbody" not in kod
    assert kod.count("tablo_html(") >= 3
    for isaret in ("def render_takvim_tablosu", "Nakit Akış tablosu: ortak tablo_html",
                   "Firma Çekleri tablosu: ortak tablo_html"):
        assert isaret in kod, isaret
    # Ödenenler (Ekim 2026): kayranacc/gecmis_ekran.py — tablo yerine ortak tıklanır
    # satırlar (shared/bilesen.tiklanir); elle yazılmış <table> yok.
    g = (KOK / "kayranacc/gecmis_ekran.py").read_text(encoding="utf-8")
    assert "<table" not in g and "B.tiklanir(" in g
    # Ödenenler: eskiden satır zemini yazı rengiyle (trenk("metin")) boyanıyordu
    assert 'bg = trenk("metin") if idx2 % 2 == 0' not in kod
