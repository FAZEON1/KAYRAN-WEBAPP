# -*- coding: utf-8 -*-
"""Sayfa testi · Muhasebe liste sayfaları ortak liste masasında (Ekim 2026): Ertelenen ödemeler, Ödenenler &
Geçmiş (üç görünüm), Gelenler geçmişi, Firma çekleri, Banka bakiyeleri. Örnek veriyle sayfa çökmeden açılır,
masa bileşeni satırlarla çizilir, eski ekranın parçaları (tıklanır satır/kart, sekmeli tablo) çizilmez.
Yalnız gerçek Streamlit kuruluyken çalışır (CI: "Sayfa testi")."""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_dosya_kapisi import _sorunlar  # noqa: E402
from test_odeme_masasi_sayfa import _bilesen_verisi  # noqa: E402
from test_sayfalar import BETIK, SURE  # noqa: E402


def _ac(monkeypatch, sayfa, durum=None):
    monkeypatch.setenv("DUMAN_ONBELLEK_TEMIZLE", "1")
    import sahte_db
    import ornek_veri
    from streamlit.testing.v1 import AppTest
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    ornek_veri.doldur(sahte_db.TABLOLAR)
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = "kayranacc"
    at.session_state["acc_sayfa"] = sayfa
    for k, v in (durum or {}).items():
        at.session_state[k] = v
    at.run()
    assert not _sorunlar(at), _sorunlar(at)
    return at


def _masa(at):
    veri = _bilesen_verisi(at.main, [])
    assert len(veri) == 1 and veri[0], "liste masası çizilmedi"
    return veri[0]


def _eski_tiklanir_yok(at, on_ek):
    """Eski ekranın satır başına tıklanır düğmeleri (B.tiklanir → tkb_<tur>_<anahtar>) çizilmez."""
    eski = [b.key for b in at.button if str(b.key or "").startswith(("tkb_satir_" + on_ek, "tkb_kart_" + on_ek))]
    assert not eski, eski


def test_ertelenen_odemeler_masasi(monkeypatch):
    at = _ac(monkeypatch, "⏳ Ertelenen Ödemeler")
    v = _masa(at)
    assert len(v["satirlar"]) >= 10 and {k["k"] for k in v["ozet"]} == {"ert", "bek", "en_cok"}
    assert all(set(s) >= {"id", "firma", "durum", "kez_m", "simdi_m", "tl", "usd"} for s in v["satirlar"])
    assert {i["k"] for i in v["islemler"]} >= {"ode", "otele", "duzenle", "sil", "geri_al"}
    assert v["bankalar"] and v["salt"] is False
    _eski_tiklanir_yok(at, "ert")


@pytest.mark.parametrize("gorunum, anahtar, en_az", [
    ("Bu hafta ödenenler", "gecod", 1), ("Geçmiş haftalar", "gech", 1), ("Çek arşivi", "geccek", 5)])
def test_odenenler_ve_gecmis_uc_gorunum(monkeypatch, gorunum, anahtar, en_az):
    at = _ac(monkeypatch, "🕐 Ödenenler & Geçmiş", {"gec_gorunum": gorunum})
    v = _masa(at)
    assert len(v["satirlar"]) >= en_az
    if gorunum == "Bu hafta ödenenler":
        # Mikro ödeme listesi (varsayılan açık): ödendi bilgisi Mikro'dan, "Geri al" yok (22.10.2026)
        assert v["islemler"] == []
    else:
        assert v["islemler"]
    _eski_tiklanir_yok(at, anahtar)
    if gorunum == "Çek arşivi":
        assert "gec_cek_ara" not in at.session_state                  # arama masanın içinde
        assert {k["k"] for k in v["ozet"]} == {"adet", "meblag", "kalan"}
    if gorunum == "Geçmiş haftalar":
        assert v["satirlar"][0]["aktif"] is True and v["satirlar"][0]["_durum"]["ad"] == "Aktif"


def test_gelenler_gecmisi_masasi(monkeypatch):
    at = _ac(monkeypatch, "💵 Gelenler Geçmişi")
    v = _masa(at)
    assert len(v["satirlar"]) == 12 and {k["k"] for k in v["ozet"]} >= {"tl", "usd", "adet"}
    assert {i["k"] for i in v["islemler"]} == {"duzenle", "geri_al"}
    assert "gel_ara" not in at.session_state and "gel_daha" not in [b.key for b in at.button]
    _eski_tiklanir_yok(at, "gel")


def test_firma_cekleri_masasi(monkeypatch):
    at = _ac(monkeypatch, "📋 Firma Çekleri")
    v = _masa(at)
    assert len(v["satirlar"]) == 5 and v["islemler"] == []
    assert {k["k"] for k in v["ozet"]} == {"meblag", "odenen", "kalan"}
    assert not at.tabs, "eski TL/USD sekmeleri çizilmemeli"


def test_banka_bakiyeleri_masasi(monkeypatch):
    at = _ac(monkeypatch, "🏦 Banka Bakiyeleri")
    v = _masa(at)
    assert len(v["satirlar"]) == 4 and v["tik"] == "ac"
    assert [k["et"] for k in v["ozet"]][:2] == ["Toplam TL", "Toplam USD"]
    assert at.button(key="bnk_tahsilat") is not None                  # başlık eylemleri yerinde
    _eski_tiklanir_yok(at, "bnk")


@pytest.mark.parametrize("sayfa, durum, modul, bayrak, eski_dugme", [
    ("🕐 Ödenenler & Geçmiş", {"gec_gorunum": "Bu hafta ödenenler"}, "kayranacc.gecmis_ekran", "GECMIS_MASASI_YENI",
     "tkb_satir_gecod"),
    ("🕐 Ödenenler & Geçmiş", {"gec_gorunum": "Geçmiş haftalar"}, "kayranacc.gecmis_ekran", "GECMIS_MASASI_YENI",
     "tkb_kart_gech"),
    ("🕐 Ödenenler & Geçmiş", {"gec_gorunum": "Çek arşivi"}, "kayranacc.gecmis_ekran", "GECMIS_MASASI_YENI",
     "tkb_satir_geccek"),
    ("💵 Gelenler Geçmişi", {}, "kayranacc.gelen_ekran", "GELENLER_MASASI_YENI", "tkb_satir_gel"),
    ("📋 Firma Çekleri", {}, "kayranacc.cek_ekran", "FIRMA_CEKLERI_MASASI_YENI", None),
    ("🏦 Banka Bakiyeleri", {}, "kayranacc.banka_ekran", "BANKA_MASASI_YENI", "tkb_kart_bnk"),
])
def test_bayrak_kapaliyken_eski_ekran_aynen(monkeypatch, sayfa, durum, modul, bayrak, eski_dugme):
    """Geri alma yolu: sayfanın bayrağı False → eski ekran çizilir, masa çizilmez."""
    import importlib
    at = _ac(monkeypatch, sayfa, durum)
    monkeypatch.setattr(importlib.import_module(modul), bayrak, False)
    at.run()
    assert not _sorunlar(at), _sorunlar(at)
    assert not _bilesen_verisi(at.main, []), "bayrak kapalıyken masa çizilmemeli"
    if eski_dugme:
        assert any(str(b.key or "").startswith(eski_dugme) for b in at.button), eski_dugme
    else:
        assert at.tabs, "eski TL/USD sekmeleri"
