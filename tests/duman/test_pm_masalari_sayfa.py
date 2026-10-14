# -*- coding: utf-8 -*-
"""Sayfa testi · Ürün Yönetimi liste masaları (Ekim 2026): Tüm ürünler, Kampanya takip, Sipariş önerisi,
Ref No takibi (+ alınan destekler), Yurt içi alış (kayıtlı alımlar), Stok yaşı (tüm ürünler) örnek veriyle
çökmeden açılır, ortak masa bileşeni (kayran_masa) satırlarla çizilir, eski listenin parçaları çizilmez.
Yalnız gerçek Streamlit kuruluyken çalışır (CI: "Sayfa testi")."""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_dosya_kapisi import _sorunlar  # noqa: E402
from test_odeme_masasi_sayfa import _bilesen_verisi  # noqa: E402
from test_sayfalar import BETIK, SURE  # noqa: E402


def _ac(monkeypatch, sayfa, **durum):
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
    at.session_state["aktif_uygulama"] = "kayranpm"
    at.session_state["pm_sayfa"] = sayfa
    for k, v in durum.items():
        at.session_state[k] = v
    at.run()
    assert not _sorunlar(at), _sorunlar(at)
    assert at.session_state["pm_sayfa"] == sayfa
    return at


def _masalar(at):
    return [v for v in _bilesen_verisi(at.main, []) if v]


def _yok(at, *anahtarlar):
    for k in anahtarlar:
        assert k not in at.session_state, f"eski listenin parçası çizildi: {k}"


def test_tum_urunler_masasi(monkeypatch):
    at = _ac(monkeypatch, "📋  Tüm Ürünler")
    _yok(at, "pm_ul_ara", "pm_ul_sira", "pm_ul_zarar")
    m = _masalar(at)
    assert len(m) == 1, "ürün masası çizilmedi"
    v = m[0]
    assert len(v["satirlar"]) >= 10 and {k["k"] for k in v["ozet"]} == {"urun", "stok", "maliyet", "satis"}
    assert v["tik"] == "ac" and {i["k"] for i in v["islemler"]} == {"ac", "aktar"}
    assert all({"id", "sku", "ad", "stok_m", "fiyat_m", "yas"} <= set(s) for s in v["satirlar"])
    assert [b for b in at.get("download_button") if "pm_ul_xlsx" in str(b.proto.id)], "Excel düğmesi yok"


def test_tum_urunler_ayrinti_yaninda_dar_masa(monkeypatch):
    at = _ac(monkeypatch, "📋  Tüm Ürünler", _pm_urun_secili="FZ-SSD-512")
    m = _masalar(at)
    assert len(m) == 1 and not m[0]["ozet"] and len(m[0]["sutunlar"]) == 3, "ayrıntı yanında dar masa yok"
    assert any("FZ-SSD-512" in str(x.value) for x in at.markdown), "sayfa içi ayrıntı çizilmedi"
    assert at.button(key="btn_urun_duz") is not None                     # eski düzenleme paneli yerinde


def test_kampanya_masasi(monkeypatch):
    at = _ac(monkeypatch, "🎯  Kampanya Takip")
    _yok(at, "kmp_gorunum", "kmp_ara")
    m = _masalar(at)
    assert len(m) == 1
    v = m[0]
    assert len(v["satirlar"]) == 4 and [g["k"] for g in v["gorunumler"]] == ["guncel", "bekliyor", "kapali", "tumu"]
    assert {k["k"] for k in v["ozet"]} == {"suruyor", "bekliyor", "destek", "net"}
    assert at.button(key="kmp_yeni_btn") is not None


def test_siparis_masalari(monkeypatch):
    at = _ac(monkeypatch, "📦  Sipariş Önerisi")
    assert not [k for k in at.session_state if str(k).startswith(("sp_miktar_", "sp_onay_", "sp_red_"))]
    m = _masalar(at)
    kayit = [v for v in m if {i["k"] for i in v["islemler"]} == {"onayla", "reddet"}]
    assert kayit and len(kayit[0]["satirlar"]) == 4 and kayit[0]["gorunumler"][0]["k"] == "bekleyen"
    oneri = [v for v in m if {i["k"] for i in v["islemler"]} == {"ekle"}]
    for v in oneri:                                   # öneri listesi örnek veride boş olabilir
        assert v["satirlar"] and all(s["oneri_v"] >= 1 for s in v["satirlar"])


def test_ref_no_masasi(monkeypatch):
    at = _ac(monkeypatch, "🔖  Ref No Takibi")
    _yok(at, "ref_durum_sec", "ref_ara")
    m = _masalar(at)
    assert len(m) == 1
    v = m[0]
    assert len(v["satirlar"]) == 5 and {i["k"] for i in v["islemler"]} == {"paylas", "bekle", "iptal", "ac"}
    assert v["grup"]["alan"] == "donem_ad" and {k["k"] for k in v["ozet"]} == {"beklemede", "paylasildi", "toplam"}


def test_ref_no_alinan_destekler_masasi(monkeypatch):
    at = _ac(monkeypatch, "🔖  Ref No Takibi", ref_gorunum="Alınan destekler")
    _yok(at, "ad2_ara")
    m = _masalar(at)
    assert len(m) == 1 and len(m[0]["satirlar"]) >= 3 and [i["k"] for i in m[0]["islemler"]] == ["sil"]


def test_yurtici_kayitli_alimlar_masasi(monkeypatch):
    at = _ac(monkeypatch, "💵  Yurt İçi Alış")
    m = _masalar(at)
    assert len(m) == 1 and len(m[0]["satirlar"]) == 3
    assert {i["k"] for i in m[0]["islemler"]} == {"duzenle", "sil"}
    at2 = _ac(monkeypatch, "💵  Yurt İçi Alış", yi_masa_sec=20)       # Düzenle → bugünkü form masanın altında
    assert at2.button(key="yi_duz_20_kaydet") is not None


def test_stok_yasi_masasi(monkeypatch):
    at = _ac(monkeypatch, "Stok Yaşı")
    m = _masalar(at)
    assert len(m) == 1 and m[0]["satirlar"] and m[0]["islemler"] == []
    assert all(s["_detay"] for s in m[0]["satirlar"])
