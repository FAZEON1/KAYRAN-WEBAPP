# -*- coding: utf-8 -*-
"""Sayfa testi · kalan eski tablolar yeni masada (shared/masa_liste.py, Ekim 2026): örnek veriyle sayfa
çökmeden açılır, salt-okur liste masası satırlarıyla çizilir, rakamlar biçimli gider (1.234 · ₺ · $).
Yalnız gerçek Streamlit kuruluyken çalışır (CI: "Sayfa testi")."""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_ithalat_depo_masasi_sayfa import _ac  # noqa: E402
from test_dosya_kapisi import _sorunlar  # noqa: E402
from test_odeme_masasi_sayfa import _bilesen_verisi  # noqa: E402


def _masa(at, onek):
    assert not _sorunlar(at), _sorunlar(at)
    veri = _bilesen_verisi(at.main, [])
    bul = [v for v in veri if str(v.get("anahtar", "")).startswith(onek)]
    assert bul, (onek, [v.get("anahtar") for v in veri])
    return bul[0]


def _sutun(v, ad):
    return next(c["alan"] for c in v["sutunlar"] if c["ad"] == ad)


def test_son_sevkler(monkeypatch):
    at, db = _ac(monkeypatch, "depo", "depo_sayfa", "🚚 Depolar Arası Sevk")
    v = _masa(at, "dpo_son_sevk_masa")
    assert len(v["satirlar"]) == min(50, len(db.TABLOLAR["depo_sevk_log"]))
    adet = _sutun(v, "Adet")
    assert all(isinstance(s[adet + "__s"], float) for s in v["satirlar"])
    assert [k["et"] for k in v["ozet"]] == ["Kayıt", "Toplam adet"] and v["ozet"][0]["dg"] == str(len(v["satirlar"]))
    assert "SKU" not in [c["ad"] for c in v["sutunlar"]]           # ürün adının altında yazar, ayrı sütun değil


def test_cari_ekstre(monkeypatch):
    at, _db = _ac(monkeypatch, "kayranacc", "acc_sayfa", "🧾 Cari Ekstre")
    v = _masa(at, "cari_ekstre_masa")
    assert v["satirlar"] and all(s["_durum"]["ad"] in ("Ödendi", "Bekliyor") for s in v["satirlar"])
    tl = _sutun(v, "Tutar (TL)")
    assert any(s[tl].startswith("₺") for s in v["satirlar"])


def test_iade_kirilimi(monkeypatch):
    at, _db = _ac(monkeypatch, "satis", "satis_sayfa", "↩️ İade")
    v = _masa(at, "iade_sku_firma_masa")
    assert v["satirlar"] and v["ozet"][2]["dg"].startswith("$")


def test_sistem_kayitlari(monkeypatch):
    at, _db = _ac(monkeypatch, "sistem_kayitlari", "_yok", None)
    v = _masa(at, "sk_hareket")
    z = _sutun(v, "Zaman")
    assert v["satirlar"] and all(s[z + "__s"] for s in v["satirlar"])       # yerel saatle gösterilir, ham zamanla sıralanır
