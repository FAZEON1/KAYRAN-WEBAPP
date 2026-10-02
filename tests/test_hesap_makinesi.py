# -*- coding: utf-8 -*-
"""Hesap Makinesi yenileme (Ekim 2026).

  1. Prim ödeme kaydı onaysız, tek tıkla siliniyordu.
  2. Aynı kişi + dönem iki kez kaydedilebiliyordu (çift tıklama → çift prim).
  4. USD/TL kuru varsayılanı 38'de sabitti → güncel kur.
  5-10. İngilizce sayı biçimi, kaybolan mesaj, ISO tarih, toplamsız geçmiş,
     büyük harf CSS + dış font, sabit "1,5 Maaş" etiketi, çalışmayan kart
     sarmalayıcıları, her tıklamada tam yenilenen sekmeler.
Formüller hesap_makinesi/hm_hesap.py'de (saf, testli); mantık DEĞİŞMEDİ.
"""
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
MAIN = "hesap_makinesi/main.py"


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


# ── Formüller (eski koddaki mantıkla birebir) ───────────────────────
def test_gokhan_prim():
    from hesap_makinesi.hm_hesap import gokhan_prim
    r = gokhan_prim(aylik_maas=115000, baz_kat=1.5, kasa_hedef=30, kasa_gercek=36, kasa_ciro=600,
                    sog_hedef=35, sog_gercek=35, sog_ciro=400, kur=41.5)
    assert r["baz"] == 172500 and round(r["kasa_carpan"], 2) == 1.2 and r["sog_carpan"] == 1.0
    assert round(r["kasa_pay"], 2) == 0.6 and round(r["agirlikli"], 4) == 1.12
    assert round(r["bonus"], 2) == 20700 and round(r["toplam"], 2) == 193200
    assert r["toplam_ciro_tl"] == 1000 * 41.5


def test_gokhan_prim_ciro_yoksa_yari_yari_ve_eksi_bonus_yok():
    from hesap_makinesi.hm_hesap import gokhan_prim
    r = gokhan_prim(100000, 1.5, 30, 15, 0, 35, 0, 0, 40)
    assert r["kasa_pay"] == r["sog_pay"] == 0.5 and r["bonus"] == 0 and r["toplam"] == 150000


def test_ayhan_prim():
    from hesap_makinesi.hm_hesap import ayhan_prim
    r = ayhan_prim(mon_oran=0.05, kasa_oran=1.0, ek_usd=1.0, ssd_oran=0.05, kur=41.5,
                   mon_ciro=100000, kasa_ciro=20000, ssd_ciro=10000, ek_adet=30)
    assert (r["mon"], r["kasa"], r["ek"], r["ssd"]) == (50, 200, 30, 5)
    assert r["toplam_usd"] == 285 and round(r["toplam_tl"], 2) == 11827.5


def test_kirilma_noktasi():
    from hesap_makinesi.hm_hesap import kirilma
    r = kirilma(gider=10000, marj=25, mevcut=30000, ort_fiyat=200, periyot="Aylık")
    assert r["hedef"] == 40000 and r["kalan"] == 10000 and r["ilerleme"] == 75
    assert r["hedef_adet"] == 200 and r["kalan_adet"] == 50 and round(r["gunluk"], 2) == round(10000 / 30, 2)
    assert kirilma(10000, 25, 50000, 0, "Aylık")["asildi"] is True


def test_karlilik():
    from hesap_makinesi.hm_hesap import karlilik
    r = karlilik(alis=100, masraf_tipi="%", masraf=10, satis=150, indirim=20)
    assert round(r["maliyet"], 2) == 110 and round(r["kar"], 2) == 40 and round(r["marj"], 2) == 26.67
    assert r["ind_satis"] == 130 and round(r["ind_kar"], 2) == 20
    assert karlilik(100, "$", 5, 150, 0)["maliyet"] == 105


def test_ayni_donem_tespiti():
    from hesap_makinesi.hm_hesap import donem_var_mi
    g = [{"donem": "Q1 2026"}, {"donem": "Q2 2026"}]
    assert donem_var_mi(g, " q1  2026 ") and not donem_var_mi(g, "Q3 2026")


# ── Ekran ───────────────────────────────────────────────────────────
def test_silme_onayli_ve_kayda_bagli():
    m = _oku(MAIN)
    assert "if sil_id: prim_sil(sil_id)" not in m
    assert "B.onayli_sil(" in m and "key=f\"{pfx}_sil_{rid}\"" in m


def test_ayni_donem_ikinci_kayit_onay_ister():
    m = _oku(MAIN)
    assert "donem_var_mi(" in m and "ikinci kayıt" in m


def test_kur_guncel():
    m = _oku(MAIN)
    assert "value=38.0" not in m and "_guncel_kur()" in m


def test_bicim_ve_temizlik():
    m = _oku(MAIN)
    assert "'${:.2f}'.format" not in m and "'%'+'{:.1f}'" not in m
    assert "Kayit hatasi" not in m and "Silme hatasi" not in m
    assert "uppercase" not in m and "fonts.googleapis" not in m
    assert "1,5 Maaş" not in m                                          # katsayı dinamik
    assert '<div class="prim-card">' not in m and '<div class="hm-card">' not in m
    assert "segmented_control(" in m and "tarih_tr(" in m
    assert "st.success('✅ '+donem" not in m and "st.success('✅ '+ay_d" not in m
    assert "Kar ($)" not in m and "st.stop()" not in m


def test_kart_etiketleri_bozulmaz():
    """Metrik etiketleri cümle düzenine iner: 'SSD&RAM' → 'Ssd&ram' (tarayıcıda görüldü)."""
    import re
    from shared.tasarim import kpi_etiketi
    m = _oku(MAIN)
    for et in re.findall(r'\{"label": f?"([^"{}]+)"', m):
        assert kpi_etiketi(et) == et, et


def test_coklu_dolar_kacisli():
    """'Toplam ciro $1.000 · kasa $600 · soğutucu $400' satırında birden çok "$"
    LaTeX sanılıp metni bozuyordu (tarayıcıda görüldü) → kaçışlı "\\$"."""
    m = _oku(MAIN)
    g = m[m.index('st.caption(f"Toplam ciro'):]
    g = g[:g.index(")\n") + 1]
    assert g.count("_usd_md(") == 3 and "_usd(" not in g
