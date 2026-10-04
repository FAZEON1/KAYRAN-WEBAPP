# -*- coding: utf-8 -*-
"""Sayfa testi, ÖRNEK VERİYLE: Soru sor sayfası (Ekim 2026).

Her soru türü gerçek Streamlit'te, küçük bir örnek veriyle (test_stok_yasi_veri.VERI) sorulur;
cevap hesaplanırken ya da çizilirken hata çıkmamalı. Rakamların doğruluğu tests/test_soru.py'de.
Yalnız gerçek Streamlit kuruluyken çalışır (CI: "Sayfa testi").
"""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_sayfalar import BETIK, SURE  # noqa: E402
from test_stok_yasi_veri import VERI, _sorunlar, _metin  # noqa: E402

SORULAR = [
    "bu yıl en çok kâr bıraktıran 5 ürün",
    "vatan bu yıl ciro",
    "bu yıl firmalara göre ciro",
    "bu yıl kategorilere göre net kâr",
    "bu yıl aylık ciro",
    "bu yıl en çok iade edilen ürünler",
    "monitör stoğu ne kadar",
    "kategorilere göre stok",
    "90 günü geçen stok",
    "bu yıl arıza oranı en yüksek modeller",
    "süren kampanyalar",
    "vadesi geçen ödemeler",
    "bekleyen çekler",
    "toplantı saat kaçta",             # anlaşılmayan: uyarı, hata yok
]


def _ac(soru):
    import os
    import sahte_db
    from streamlit.testing.v1 import AppTest
    os.environ["DUMAN_ONBELLEK_TEMIZLE"] = "1"
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    for t, rows in VERI.items():
        sahte_db.TABLOLAR[t] = [dict(r) for r in rows]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = "soru"
    at.session_state["_soru_bekleyen"] = soru
    try:
        at.run()
    finally:
        os.environ.pop("DUMAN_ONBELLEK_TEMIZLE", None)
    return at


@pytest.mark.parametrize("soru", SORULAR)
def test_soru_cevaplanir(soru):
    at = _ac(soru)
    assert not _sorunlar(at), _sorunlar(at)
    assert at.session_state["aktif_uygulama"] == "soru"
    m = _metin(at)
    if soru == "toplantı saat kaçta":
        assert "anlayamadım" in m
    else:
        assert "Kaynak:" in m or any(x in m for x in ("yok.", "yetkiniz yok")), m[:500]


def test_satis_cevabi_rakam_gosterir():
    # Dönem başka sayfa testlerinin (boş veriyle) önbelleğe aldığı aralıklardan farklı olsun
    at = _ac("vatan son 200 gün ciro")
    m = _metin(at)
    assert "Net ciro" in m and "$4.800" in m         # 40 adet × 120 $ (örnek veri)
