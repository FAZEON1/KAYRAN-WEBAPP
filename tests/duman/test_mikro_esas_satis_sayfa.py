# -*- coding: utf-8 -*-
"""Sayfa testi · Mikro esas (kullanıcı, 22.10.2026): satış eşitlemesi açıkken Satış Girişi'nde elle sipariş ve
yeni kanal, İade'de elle iade düğmesi gösterilmez; açıklama Mikro'yu söyler. Kapalıyken düğmeler yerinde.
Yalnız gerçek Streamlit kuruluyken çalışır (CI: "Sayfa testi")."""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_dosya_kapisi import _sorunlar  # noqa: E402
from test_sayfalar import BETIK, SURE  # noqa: E402

SAYFALAR = [("🧾 Satış Girişi", {"sg_manuel_btn", "sg_kanal_btn"}), ("↩️ İade", {"btn_sat_miade"})]


def _ac(sayfa, acik):
    import sahte_db
    from streamlit.testing.v1 import AppTest
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    sahte_db.TABLOLAR["mikro_esitleme_durum"] = [{"id": 1, "acik": acik, "baslangic": "2026-07-01"}]
    sahte_db.TABLOLAR["urunler"] = [{"sku": "X24F200", "urun_adi": "MONİTÖR", "alis_fiyati": 40,
                                     "bizim_stok": 3, "depo_kirilim": {"MERKEZ DEPO": 3}}]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = "satis"
    at.session_state["satis_sayfa"] = sayfa
    at.run()
    assert not _sorunlar(at), _sorunlar(at)
    return at


@pytest.mark.parametrize("sayfa, dugmeler", SAYFALAR)
def test_mikro_acikken_elle_giris_dugmeleri_yok(sayfa, dugmeler):
    at = _ac(sayfa, True)
    anahtarlar = {b.key for b in at.button}
    assert not (dugmeler & anahtarlar), anahtarlar
    metin = " ".join(str(m.value) for m in list(at.markdown) + list(at.caption))
    assert "Mikro" in metin


@pytest.mark.parametrize("sayfa, dugmeler", SAYFALAR)
def test_mikro_kapaliyken_dugmeler_yerinde(sayfa, dugmeler):
    at = _ac(sayfa, False)
    assert dugmeler <= {b.key for b in at.button}
