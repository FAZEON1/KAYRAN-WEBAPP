# -*- coding: utf-8 -*-
"""Sayfa testi · Muhasebe › Bu hafta ödeme masası (Ekim 2026): örnek veriyle sayfa çökmeden açılır, masa
bileşeni çizilir ve ekrana giden veri odeme_hesap ile aynı rakamları taşır. Eski ekranın parçaları (görünüm
düğmesi, satır başına tıklanır kap) çizilmez. Yalnız gerçek Streamlit kuruluyken çalışır (CI: "Sayfa testi")."""
import json

import pytest

pytest.importorskip("streamlit.testing.v1")

from test_dosya_kapisi import _sorunlar  # noqa: E402
from test_sayfalar import BETIK, SURE  # noqa: E402


def _bilesen_verisi(dugum, out):
    """Ağaçtaki ödeme masası bileşeninin (components v2) verisi."""
    for c in getattr(dugum, "children", {}).values():
        p = getattr(c, "proto", None)
        bc = getattr(p, "bidi_component", None) if p is not None else None
        if bc is None and p is not None and hasattr(p, "component_name") and hasattr(p, "json"):
            bc = p
        if bc is not None and str(getattr(bc, "component_name", "")).endswith("kayran_masa"):
            out.append(json.loads(bc.json) if bc.json else None)
        _bilesen_verisi(c, out)
    return out


def test_bu_hafta_odeme_masasi_ornek_veriyle(monkeypatch):
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
    at.session_state["acc_sayfa"] = "💳 Bu Hafta"
    at.run()
    assert not _sorunlar(at), _sorunlar(at)
    assert "od_gorunum" not in at.session_state, "eski ekranın görünüm düğmesi çizilmemeli"
    veri = _bilesen_verisi(at.main, [])
    assert veri, "ödeme masası bileşeni çizilmedi"
    v = veri[0]
    assert v and len(v["satirlar"]) >= 10 and {k["k"] for k in v["ozet"]} == {"bugun", "gecikmis", "kalan", "hafta_sonu"}
    assert all(set(o) >= {"id", "firma", "durum", "tl_m", "usd_m", "gun"} for o in v["satirlar"])
    assert v["bankalar"] and v["salt"] is False
