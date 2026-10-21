# -*- coding: utf-8 -*-
"""Toplam Aktifler · Mikro defter kalemleri ve satış maliyeti (kayranacc/mikro_aktif.py, Ekim 2026).

Kullanıcı: "Toplam aktifler upload olmadan Mikro'dan; kargo, depolama vs. masrafları düşsün" (seçenek A: satış
destek bedelleri hariç) ve "aynı masraf farklı şekilde programa yükleniyorsa 2 defa yüklenmesin".
Canlı (21.10.2026, kur 49,6): kasa 21.504 $, avanslar 55.798 $, KDV −65.948 $, vergi −11.600 $, SGK −11.924 $,
tahakkuk −25.329 $; satış maliyeti oranı %1,96 (lojistik 103.157 $ + KK komisyonu 30.616 $ + teknik servis
11.008 $ + depolama 9.965 $ + kargo 6.237 $ … ÷ net satış 8,27 M $)."""
import datetime
import importlib.util
import json
from pathlib import Path

import pytest

try:
    from kayranacc import mikro_aktif as M
except ImportError:          # eski kodda modül yok: hesap testleri atlanır, sayfa / pano / tur testleri kırmızı
    M = None
_M_gerek = pytest.mark.skipif(M is None, reason="kayranacc.mikro_aktif yok")
KOK = Path(__file__).resolve().parent.parent


def _r(kod, borc=0.0, alacak=0.0, yil=2026, ay=5):
    return {"yil": yil, "ay": ay, "hesap_kod": kod, "borc": borc, "alacak": alacak}


ADLAR = {"760.03.005": "LOJİSTİK VE NAKLİYE GİDERLERİ", "770.03.018": "KARGO VE POSTA GİDERLERİ",
         "760.03.013": "DEPOLAMA GİDERLERİ", "780.79.007": "KREDİ KARTI TAHSİLATLARI KOMİSYONLARI",
         "760.04.019": "FAZEON KASA SATIŞ DESTEK BEDELİ", "770.01.001": "İŞÇİ ÜCRET GİDERLERİ",
         "760.03.011": "TEKNİK SERVİS BEDELİ ANLAŞMASI"}
BUGUN = datetime.date(2026, 10, 21)


@pytest.mark.parametrize("kod", ["102.01.001", "103.01", "120.01.005", "340.01.001", "153.01", "159.01.002",
                                 "320.50.005", "320.50"])
@_M_gerek
def test_toplam_aktiflerin_kendi_hesaplari_defter_kalemine_girmez(kod):
    """Banka, çek, cari, ithalat avansı ve stok zaten Toplam Aktifler'de: ikinci kez sayılmamalı."""
    assert M.kalem_bul(kod) is None


@_M_gerek
def test_kapsanan_onekler_hicbir_kalemle_cakismaz():
    for ad, onek, haric in M.DEFTER_KALEMLERI:
        for k in M.KAPSANAN:
            assert not (M.onek_uyar(k, onek) and not M.onek_uyar(k, haric)), (ad, k)
            assert not any(M.onek_uyar(o, (k,)) for o in onek), (ad, k)


@_M_gerek
def test_defter_kalemleri_isaretli_bakiye():
    s = [_r("100.001", 1_066_589), _r("195.01.006", 1000), _r("196.01.002", 500, 100),
         _r("191.01.001", 8_000), _r("391.01.001", 0, 13_000), _r("190.001", 1_500),
         _r("361.01.001", 100, 600), _r("320.01.001", 0, 400), _r("320.50.005", 900_000),
         _r("102.01.001", 5_000_000), _r("320", 10)]
    k = {x["ad"]: x for x in M.defter_kalemleri(s)}
    assert k["Kasa"]["tl"] == pytest.approx(1_066_589)
    assert k["İş ve personel avansları"]["tl"] == pytest.approx(1400)
    assert k["KDV (indirilecek − hesaplanan)"]["tl"] == pytest.approx(-3500)
    assert k["Ödenecek SGK"]["tl"] == pytest.approx(-500)
    assert k["Yurt içi satıcılar"]["tl"] == pytest.approx(-390)            # 320.50 (ithalat avansı) hariç
    assert "320.50.005" not in k["Yurt içi satıcılar"]["hesaplar"]
    assert sum(x["tl"] for x in k.values()) == pytest.approx(1_066_589 + 1400 - 3500 - 500 - 390)


@_M_gerek
def test_satis_maliyeti_orani_secenek_a():
    """Kargo / lojistik / depolama / KK komisyonu / teknik servis; satış destek ve işçilik HARİÇ.
    İçinde bulunulan ay (Ekim, yarım) ve Aralık (yıl sonu kapanışı) alınmaz; 12 aydan eski ay alınmaz."""
    s = [_r("600.01.001", 0, 1_000_000), _r("610.01", 50_000), _r("760.03.005", 10_000),
         _r("770.03.018", 2_000), _r("760.03.013", 1_000), _r("780.79.007", 3_000), _r("760.03.011", 1_500),
         _r("760.04.019", 90_000), _r("770.01.001", 40_000),
         _r("600.01.001", 0, 500_000, ay=10), _r("760.03.005", 99_000, ay=10),            # bu ay: yarım
         _r("760.03.005", 0, 80_000, yil=2025, ay=12), _r("600.01.001", 900, 0, yil=2025, ay=12),   # kapanış
         _r("760.03.005", 7_777, yil=2025, ay=9)]                                          # 12 aydan eski
    o = M.satis_maliyeti_orani(s, ADLAR, BUGUN)
    assert o["satis_tl"] == pytest.approx(950_000)
    assert o["masraf_tl"] == pytest.approx(17_500)
    assert o["oran"] == pytest.approx(17_500 / 950_000, rel=1e-5)
    assert {x["kod"] for x in o["kalemler"]} == {"760.03.005", "770.03.018", "760.03.013", "780.79.007", "760.03.011"}


@_M_gerek
def test_turkce_i_hesap_adiyla_eslesir():
    """Canlı: tr_buyuk 'İ'yi 'I'ya indiriyor; ham 'LOJİSTİK' kelimesi eşleşmeyince lojistik (oranın büyük kısmı)
    dışarıda kalıyordu (%0,20 yerine %1,96)."""
    s = [_r("600.01.001", 0, 100_000), _r("760.03.005", 1_000)]
    assert M.satis_maliyeti_orani(s, {"760.03.005": "Lojistik ve nakliye giderleri"}, BUGUN)["masraf_tl"] == 1_000


def _kayit():
    s = [_r("361.01.001", 0, 4960), _r("100.001", 9920), _r("600.01.001", 0, 100_000), _r("770.03.018", 2_000)]
    return M.kayit_yap(s, ADLAR, BUGUN)


@_M_gerek
def test_usd_ozeti():
    o = M.usd_ozeti(_kayit(), 49.6, 885_291.4)
    assert o["arti"] == pytest.approx(200.0) and o["eksi"] == pytest.approx(100.0)
    assert o["oran"] == pytest.approx(0.02)
    assert o["satis_maliyeti_usd"] == pytest.approx(885_291.4 * 0.02, abs=0.01)


@_M_gerek
def test_ayni_kalem_elle_de_girildiyse_iki_kez_sayilmaz():
    manuel = [{"id": 4, "aciklama": "EERA HAVUZ BÜTÇE", "tutar": 119000, "tip": "ekle"},
              {"id": 7, "aciklama": "Eylül SGK primi", "tutar": 4960, "para_birimi": "TL", "tip": "cikar"},
              {"id": 8, "aciklama": "Kargo firması borcu", "tutar": 300, "tip": "cikar"},
              {"id": 9, "aciklama": "KDV borcu", "tutar": 50, "tip": "cikar"}]       # KDV kalemi boş: sayılır
    c = M.manuel_cakisan(manuel, _kayit())
    assert c == {7: "Ödenecek SGK", 8: "Satış maliyeti"}
    assert M.cakisan_etki(manuel, c, 49.6) == pytest.approx(-100 - 300)


def test_toplam_aktifler_mikro_kalemlerini_ve_cakisani_hesaba_katar():
    """Sayfanın toplamı: + defter artı − defter eksi − satış maliyeti; Mikro'dan da gelen manuel kalem atlanır."""
    kaynak = (KOK / "kayranacc" / "main.py").read_text(encoding="utf-8")
    govde = kaynak.split("def _sayfa_toplam_aktifler", 1)[1].split("\ndef ", 1)[0]
    formul = govde.split("toplam_aktif = (", 1)[1].split(")", 1)[0]
    assert '+ _ma["arti"]' in formul and '- _ma["eksi"]' in formul and '- _ma["satis_maliyeti_usd"]' in formul
    assert "in _ma_cak:" in govde.split("manuel_ekle_toplam = 0.0", 1)[1].split("toplam_aktif = (", 1)[0]
    assert '"satis_maliyeti"' in govde                        # Yönetim panosuna giden kayıtta da


@_M_gerek
def test_otomatik_kapaliyken_yazmaz_acikken_bir_kez_yazar(monkeypatch):
    import kayranacc.database as db
    import satis.mikro_esitle as se
    ayar = {}
    monkeypatch.setattr(db, "get_ayar", lambda k, v=None: ayar.get(k, v))
    monkeypatch.setattr(db, "set_ayar", lambda k, v: ayar.__setitem__(k, v) or True)
    monkeypatch.setattr(M, "son_aktarim", lambda: "2026-10-21 20:11:07")
    monkeypatch.setattr(se, "aktarim_suruyor", lambda: False)
    monkeypatch.setattr(M, "plan_hazirla", lambda: {"bos": False, "once": None, "kayit": {"kalemler": []}})
    yazilan = []
    monkeypatch.setattr(db, "aktif_excel_kaydet", lambda k, t, v: yazilan.append((t, v)) or True)
    assert M.otomatik() is None and not yazilan
    M.ac("ibrahim")
    assert M.otomatik() and yazilan == [("mikro_defter", {"kalemler": []})]
    assert M.otomatik() is None and len(yazilan) == 1


def test_esitleme_turlarina_eklendi():
    app = (KOK / "app.py").read_text(encoding="utf-8")
    assert "kayranacc.mikro_aktif" in app.split("def _mikro_esitle_dene", 1)[1].split("\ndef ", 1)[0]
    spec = importlib.util.spec_from_file_location("otonom_mikro_esitle_aktif", KOK / "otonom" / "mikro_esitle.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    adlar = [m for _a, m, _f in mod.ISLER]
    assert adlar.index("kayranacc.mikro_aktif") > adlar.index("kayranacc.mikro_stok_degeri")


def test_yonetim_panosu_yeni_kalemleri_gosterir():
    import yonetim
    renk = {"metin": "#000", "yesil": "#0a0", "kirmizi": "#a00", "mor2": "#a0a"}
    h = yonetim._toplam_aktif_html({"toplam": 1, "kur": 49.6, "defter_eksi": 128777.5, "satis_maliyeti": 17323.4}, renk)
    assert "Satış maliyeti" in h and "KDV, vergi, SGK" in h
    json.dumps(h)
