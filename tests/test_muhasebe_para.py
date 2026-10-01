# -*- coding: utf-8 -*-
"""Muhasebe 2. paket (Ekim 2026): Banka Bakiyeleri · Nakit Akış · Firma Çekleri · Gelenler.

Bulunan hatalar:
  • Banka "Sil" düğmesi hesabı ONAYSIZ siliyordu
  • Banka kartlarında bakiye kesiliyordu; her TL hesabın "hafta sonu" tahmini
    haftanın TÜM bekleyenlerini o hesaptan düşüyordu (Kasa TL sahte açık)
  • Nakit Akış ekseni İngilizce + saat çizgili; grafik ipucu '%{tr_sayi(y)}' —
    grafik bunu anlamaz, tutar görünmüyordu (Genel Bakış pastalarında da)
  • Firma Çekleri tablosunda firma ve banka yoktu (hazırlanıp konmuyordu)
  • Gelenler: TL tahsilatlar "$" ile görünüyordu
"""
import ast
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


def test_banka_silme_onayli_ve_formlar_pencerede():
    m = _oku("kayranacc/main.py")
    assert 'st.form_submit_button("Sil", icon=":material/delete:")' not in m      # eski onaysız sil
    assert 'with st.form("banka_ekle")' not in m and 'with st.form("banka_duzenle")' not in m
    e = _oku("kayranacc/banka_ekran.py")
    assert "B.onayli_sil(" in e and "banka_sil(" in e


def test_hafta_sonu_tahmini_toplamda_tek_formul():
    e = _oku("kayranacc/banka_ekran.py")
    assert 'hs = t["TL"] - bekleyen_tl - bekleyen_usd * float(kur or 0)' in e
    assert "def hafta_sonu(" not in e                     # hesap başına sahte tahmin kalktı
    h = _oku("kayranacc/odeme_hesap.py")
    assert '"hafta_sonu_tl": banka_tl - bek_tl - bek_usd * _f(kur)' in h      # Bu Hafta ile aynı


def test_grafik_ipuclarinda_python_fonksiyonu_yok():
    for y in ("kayranacc/main.py",):
        assert "%{tr_sayi" not in _oku(y), y
    m = _oku("kayranacc/main.py")
    assert 'type="category"' in m and "GUN_KISA as _GUN" in m
    assert "for v in (odendi_tutar, bekleyen_tutar)" in m      # 2. pasta kendi verisiyle


def test_gun_kisaltmalari_ayirt_edici():
    import kayranacc.odeme_hesap as H
    assert len(set(H.GUN_KISA)) == 7 and H.GUN_KISA[0] == "Pzt" and H.GUN_KISA[6] == "Paz"


def test_cek_tablosunda_firma_ve_banka():
    m = _oku("kayranacc/main.py")
    assert '"Firma": row.get("C/H İsmi", "") or "—"' in m
    assert '["Ref No", "Firma", "Banka", ("Çek No", "mono")' in m


def test_gelenler_kendi_para_birimiyle():
    g = _oku("kayranacc/gelen_ekran.py")
    assert 'SEMBOL = {"TL": "₺", "TRY": "₺", "USD": "$", "EUR": "€"}' in g
    assert "_para(t.get(\"tutar\"), pb)" in g and "B.onayli_sil(" in g and "tahsilat_geri_al(" in g
    m = _oku("kayranacc/main.py")
    assert "from .gelen_ekran import render_gelenler" in m
    assert '"Tutar": float(t.get("tutar", 0) or 0)' not in m


def test_baslik_eylem_dort_dugmede_kesilmez():
    s = _oku("shared/bilesen.py")
    assert "gen = 1.45 if n > 3 else 1.3" in s
