# -*- coding: utf-8 -*-
"""Sayfa testi · Hesap Makinesi › Gökhan Yavuz primi (Ekim 2026): Ayhan sekmesi yok; geçmiş ödemenin not
düğmesi "Ödeme notları" penceresini açar, eski notlar görünür. Yalnız gerçek Streamlit kuruluyken çalışır."""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_dosya_kapisi import _sorunlar  # noqa: E402
from test_sayfalar import BETIK, SURE  # noqa: E402


def test_gokhan_odeme_notu_penceresi(monkeypatch):
    import sahte_db
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("DUMAN_ONBELLEK_TEMIZLE", "1")
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    sahte_db.TABLOLAR["prim_gecmis"] = [
        {"id": 5, "kisi": "gokhan_yavuz", "donem": "Q2 2026", "toplam_prim": 193200.0, "odeme_tarihi": "2026-07-10",
         "notlar": "Q2 ödemesi\n14.10.2026 · ibrahim: Banka: Örnek TL"}]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    for k, v in {"giris_yapildi": True, "aktif_kullanici": sahte_db.KULLANICI, "aktif_uygulama": "hesap_makinesi",
                 "hm_sekme": "prim_gokhan"}.items():
        at.session_state[k] = v
    at.run()
    assert not _sorunlar(at), _sorunlar(at)
    assert "prim_ayhan" not in at.segmented_control(key="hm_sekme").options
    assert any("(+1 not)" in str(m.value) for m in at.markdown)               # son not + kaç not daha
    at.button(key="gy_not_5").click().run()
    assert not _sorunlar(at), _sorunlar(at)
    assert at.text_area(key="gy_yeni_not_5") is not None
    assert any("Banka: Örnek TL" in str(m.value) for m in at.markdown)
    assert at.button(key="gy_not_kaydet_5").disabled                           # boş not eklenmez
