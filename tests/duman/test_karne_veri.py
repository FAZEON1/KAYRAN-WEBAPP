# -*- coding: utf-8 -*-
"""Sayfa testi, ÖRNEK VERİYLE: stok kartı › Analiz › ürün karnesi (Ekim 2026).
Gerçek Streamlit'te çizilmeli, hata çıkmamalı, not ve öneri görünmeli. Hesap doğruluğu
tests/test_urun_karnesi.py'de. Yalnız gerçek Streamlit kuruluyken çalışır (CI: "Sayfa testi")."""
import os

import pytest

pytest.importorskip("streamlit.testing.v1")

from test_sayfalar import SURE  # noqa: E402
from test_stok_yasi_veri import VERI, _sorunlar  # noqa: E402

BETIK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stok_karti_betik.py")


def _ac(sku):
    import sahte_db
    from streamlit.testing.v1 import AppTest
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    for t, rows in VERI.items():
        sahte_db.TABLOLAR[t] = [dict(r) for r in rows]
    os.environ["KARNE_SKU"] = sku
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.run()
    return at


@pytest.mark.parametrize("sku", ["X24F165S", "FAZE1", "YOK123"])
def test_karne_cizilir(sku):
    at = _ac(sku)
    assert not _sorunlar(at), _sorunlar(at)
    html = " ".join(str(m.value) for m in at.markdown)
    if sku == "YOK123":
        assert "Karne için yeterli veri yok" in html
    else:
        assert 'class="uk-not"' in html and "Ürün karnesi" in html
