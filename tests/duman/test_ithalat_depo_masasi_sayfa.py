# -*- coding: utf-8 -*-
"""Sayfa testi · İthalat ve Depo liste masaları (Ekim 2026): örnek veriyle sayfa çökmeden açılır, ortak
masa (kayran_masa) satırlarıyla çizilir; masadan istenen ayrıntı (İthalat detay penceresi, Bekleyen sevk
sayfa içi detayı) eski akışla açılır. Yalnız gerçek Streamlit kuruluyken çalışır (CI: "Sayfa testi")."""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_dosya_kapisi import _sorunlar  # noqa: E402
from test_odeme_masasi_sayfa import _bilesen_verisi  # noqa: E402
from test_sayfalar import BETIK, SURE  # noqa: E402


def _ac(monkeypatch, modul, anahtar, sayfa, durum=None):
    monkeypatch.setenv("DUMAN_ONBELLEK_TEMIZLE", "1")
    import sahte_db
    import ornek_veri
    from streamlit.testing.v1 import AppTest
    sahte_db.TABLOLAR.clear()          # bileşen kaydı her testten önce sıfırlanır (tests/duman/conftest.py)
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    ornek_veri.doldur(sahte_db.TABLOLAR)
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = modul
    at.session_state[anahtar] = sayfa
    for k, v in (durum or {}).items():
        at.session_state[k] = v
    at.run()
    return at, sahte_db


def test_gecmis_ithalatlar_masasi(monkeypatch):
    at, db = _ac(monkeypatch, "ithalat", "ith_sayfa", "📋  Geçmiş İthalatlar")
    assert not _sorunlar(at), _sorunlar(at)
    assert "ith_gorunum" not in at.session_state, "eski Akış/Liste görünüm düğmesi çizilmemeli"
    veri = _bilesen_verisi(at.main, [])
    assert veri, "ithalat masası çizilmedi"
    v = veri[0]
    ithalat = [d for d in db.TABLOLAR["ithalat_dosyalari"] if d.get("alim_turu") == "ithalat"]
    assert len(v["satirlar"]) == len(ithalat) == 8                 # yurt içi alışlar listede yok (ithalat_mi)
    assert {k["k"] for k in v["ozet"]} == {"yolda", "mal", "masraf", "oran"}
    assert {i["k"] for i in v["islemler"]} == {"ac", "teslim", "depo", "takip"}
    assert all(s["mal_m"].startswith("$") for s in v["satirlar"])
    assert sum(1 for s in v["satirlar"] if s["asama"] != "Teslim Alındı") == 3


def test_gecmis_ithalatlar_masadan_ayrinti_penceresi(monkeypatch):
    """Masadaki "Ayrıntı" B.detay_ac("ith", id) yazar; sayfa aynı çalıştırmada bugünkü pencereyi açar."""
    at, _db = _ac(monkeypatch, "ithalat", "ith_sayfa", "📋  Geçmiş İthalatlar", {"_ith_sec": 2, "_ith_ac": True})
    assert not _sorunlar(at), _sorunlar(at)
    assert "_ith_ac" not in at.session_state                       # istek tüketildi
    metin = " ".join(str(m.value) for m in at.markdown)
    assert "PI-2602" in metin, "detay penceresi açılmadı"


def test_gecmis_ithalatlar_toplu_islem_gorunumu(monkeypatch):
    at, _db = _ac(monkeypatch, "ithalat", "ith_sayfa", "📋  Geçmiş İthalatlar", {"ith_gorunum_masa": "Toplu işlem"})
    assert not _sorunlar(at), _sorunlar(at)
    assert not _bilesen_verisi(at.main, []), "Toplu işlem görünümünde masa çizilmez"
    assert "ith_sort" in at.session_state                          # eski çoklu seçim tablosu


def test_masraf_detaylari_masasi(monkeypatch):
    at, _db = _ac(monkeypatch, "ithalat", "ith_sayfa", "💸  Masraf Detayları")
    assert not _sorunlar(at), _sorunlar(at)
    veri = _bilesen_verisi(at.main, [])
    assert veri and len(veri[0]["satirlar"]) >= 8 * 5
    assert veri[0]["islemler"] == []
    assert any(b.label == "CSV indir" for b in at.get("download_button"))


def test_depo_stok_masasi(monkeypatch):
    at, _db = _ac(monkeypatch, "depo", "depo_sayfa", "🏬 Depo Stok", {"dpo_icerik_depo": "MERKEZ DEPO"})
    assert not _sorunlar(at), _sorunlar(at)
    veri = _bilesen_verisi(at.main, [])
    assert veri and veri[0]["satirlar"], "depo stok masası çizilmedi"
    adetler = [s["adet"] for s in veri[0]["satirlar"]]
    assert adetler == sorted(adetler, reverse=True)                # liste_hazirla sırası (adet çoktan aza)


def test_bekleyen_sevk_masasi(monkeypatch):
    at, _db = _ac(monkeypatch, "depo", "depo_sayfa", "📦 Bekleyen Sevk Takibi")
    assert not _sorunlar(at), _sorunlar(at)
    veri = _bilesen_verisi(at.main, [])
    assert veri, "bekleyen sevk masası çizilmedi"
    v = veri[0]
    assert [s["firma"] for s in v["satirlar"]] == ["ÖRNEK BİLGİSAYAR", "VATAN", "EERA", "MONDAY"]
    assert [s["bek"] for s in v["satirlar"]] == [70, 50, 25, 0]
    assert {i["k"] for i in v["islemler"]} == {"dus", "ac", "sil"}
    assert "mt_h_firma" in at.session_state                        # tüm sevk hareketleri tablosu duruyor


def test_bekleyen_sevk_sayfa_ici_detay(monkeypatch):
    at, _db = _ac(monkeypatch, "depo", "depo_sayfa", "📦 Bekleyen Sevk Takibi", {"_dpo_mt_secili": 1})
    assert not _sorunlar(at), _sorunlar(at)
    assert not _bilesen_verisi(at.main, []), "detay açıkken masa çizilmez"
    assert any(b.label == "Düşümü kaydet" for b in at.button)


@pytest.mark.parametrize("modul, anahtar, sayfa", [
    ("ithalat", "ith_sayfa", "📋  Geçmiş İthalatlar"), ("ithalat", "ith_sayfa", "💸  Masraf Detayları"),
    ("depo", "depo_sayfa", "🏬 Depo Stok"), ("depo", "depo_sayfa", "📦 Bekleyen Sevk Takibi")])
def test_bayrak_kapaliyken_eski_ekran(monkeypatch, modul, anahtar, sayfa):
    """Geri alma yolu: bayrak False → eski ekran örnek veriyle çökmeden açılır, masa çizilmez."""
    import depo.bekleyen_ekran
    import depo.main
    import ithalat.main
    monkeypatch.setattr(ithalat.main, "ITHALAT_MASASI_YENI", False)
    monkeypatch.setattr(depo.main, "DEPO_STOK_MASASI_YENI", False)
    monkeypatch.setattr(depo.bekleyen_ekran, "BEKLEYEN_MASASI_YENI", False)
    at, _db = _ac(monkeypatch, modul, anahtar, sayfa)
    assert not _sorunlar(at), _sorunlar(at)
    assert not _bilesen_verisi(at.main, []), "bayrak kapalıyken masa çizilmemeli"
