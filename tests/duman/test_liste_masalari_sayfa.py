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
    veri = _bilesen_verisi(at._tree, [])          # tüm ağaç: pencere (st.dialog) içi de
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


def test_stok_karti_sekmeleri_masada():
    """Stok kartının eski sekme tabloları (Ekim 2026, ikinci tur): kanal kırılımı ve stok hareketleri masada."""
    from test_stok_karti_yeni_sayfa import _ac as _kart_ac
    at = _kart_ac("FZ-SSD-1TB")
    v = _masa(at, "sk_hareket_FZ-SSD-1TB")
    assert v["satirlar"] and _sutun(v, "Zaman") and _sutun(v, "Değişim")
    i = _masa(at, "sk_iade_detay_FZ-SSD-1TB")          # İade sekmesi (yeni pencerede satışlar kendi masasında)
    assert i["satirlar"] and _sutun(i, "İade Tutarı") and i["ozet"][0]["et"] == "Kayıt"
    assert _masa(at, "sk_partiler_FZ-SSD-1TB")["satirlar"]


def test_sku_hareketleri_tek_listede(monkeypatch):
    at, _db = _ac(monkeypatch, "depo", "depo_sayfa", "🔎 SKU Hareketleri")
    # SKU seçimi: ithalat model listesi varsa seçim kutusu, yoksa SKU yazma kutusu (sayfanın iki yolu)
    try:
        sec = at.selectbox(key="sh_sku_sec")
        sec.select(next(o for o in sec.options if o.startswith("FZ-SSD-1TB"))).run()
    except KeyError:
        at.text_input(key="sh_sku").input("FZ-SSD-1TB").run()
    v = _masa(at, "sh_hareket_masa_")
    turler = {s["_durum"]["ad"] for s in v["satirlar"]}
    assert turler and turler <= {"İthalat", "Satış", "İade"}
