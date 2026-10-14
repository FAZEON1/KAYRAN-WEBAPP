# -*- coding: utf-8 -*-
"""Sayfa testi, ÖRNEK VERİYLE: stok kartı penceresi yeni tasarım (kayranpm/stok_karti_yeni.py, Ekim 2026).
Gerçek Streamlit'te hatasız çizilir: kimlik, özet bandı, sekmeler (sayılarıyla), stok nerede / durum / son
hareketler / haftalık satış, satış masası; STOK_KARTI_YENI = False eski pencereyi getirir."""
import os

import pytest

pytest.importorskip("streamlit.testing.v1")

from test_sayfalar import SURE  # noqa: E402

BETIK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stok_karti_betik.py")


def _ac(sku):
    import ornek_veri
    import sahte_db
    from streamlit.testing.v1 import AppTest
    sahte_db.TABLOLAR.clear()
    ornek_veri.doldur(sahte_db.TABLOLAR)
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    os.environ["KARNE_SKU"] = sku
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.run()
    return at


def _sorun(at):
    return [e.value for e in at.exception] + list(at.session_state["_duman_hatalar"]
                                                  if "_duman_hatalar" in at.session_state else [])


def test_yeni_pencere_cizilir():
    at = _ac("FZ-SSD-512")
    assert not _sorun(at), _sorun(at)
    html = " ".join(str(m.value) for m in at.markdown)
    for parca in ('class="skn-sku">FZ-SSD-512<', 'class="skn-bant"', "Satılabilir stok", "Stok nerede",
                  "Son hareketler", "Haftalık satış", 'class="skn-kanal"'):
        assert parca in html, parca
    etiketler = [t.label for t in at.tabs]
    assert etiketler[0] == "Özet" and etiketler[2].startswith("Satışlar :gray[") and "Stok yaşı" in etiketler
    assert any(c.key and c.key.startswith("stok_gec_") for c in at.selectbox)                # başka ürün aç
    assert "📦" not in html and "🔍" not in html


def test_eski_pencere_anahtarla_gelir(monkeypatch):
    from kayranpm import stok_karti
    monkeypatch.setattr(stok_karti, "STOK_KARTI_YENI", False)
    at = _ac("FZ-SSD-512")
    assert not _sorun(at), _sorun(at)
    html = " ".join(str(m.value) for m in at.markdown)
    assert 'class="skn-bant"' not in html and "border-left:3px solid var(--k-mor)" in html   # eski başlık şeridi
    assert any(t.label.endswith("Stok Hareketleri") for t in at.tabs)                     # eski sekme adı
