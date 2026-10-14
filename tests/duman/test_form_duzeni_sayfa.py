# -*- coding: utf-8 -*-
"""Sayfa testi · giriş formları yeni düzen (Ekim 2026): Türkçe yazılan tutar ("12,50") kayda doğru sayı olarak
gider; sağdaki özet paneli çizilir. Yalnız gerçek Streamlit kuruluyken çalışır (CI: "Sayfa testi")."""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_ithalat_depo_masasi_sayfa import _ac  # noqa: E402
from test_dosya_kapisi import _sorunlar  # noqa: E402


def test_yeni_ithalat_turkce_fob_kayda_gider(monkeypatch):
    at, db = _ac(monkeypatch, "ithalat", "ith_sayfa", "➕  Yeni İthalat")
    assert not _sorunlar(at), _sorunlar(at)
    assert any("Dosya özeti" in str(m.value) for m in at.markdown)
    urun = at.selectbox(key="m_urun_0_0")
    sku = urun.options[1]
    urun.select(sku).run()
    at.number_input(key="m_adet_0_0").set_value(40).run()
    at.text_input(key="m_fob_0_0").input("12,50").run()
    at.text_input(key="m_indirim_0").input("1.000,00").run()
    at.text_input(key="m_dosya_no_0").input("ITH-TEST-1").run()
    assert any("500,00 USD" in str(m.value) or "500 USD" in str(m.value) for m in at.markdown), \
        [str(m.value)[:200] for m in at.markdown if "Dosya özeti" in str(m.value)]
    at.button(key="m_kaydet_0").click().run()
    assert not _sorunlar(at), _sorunlar(at)
    dos = [d for d in db.TABLOLAR.get("ithalat_dosyalari", []) if d.get("dosya_no") == "ITH-TEST-1"]
    assert dos, "dosya kaydedilmedi"
    kal = [k for k in db.TABLOLAR.get("ithalat_kalemleri", []) if k.get("dosya_id") == dos[0].get("id")]
    assert [(k["sku"], float(k["adet"]), float(k["birim_fob"])) for k in kal] == [(sku, 40.0, 12.5)]
    assert float(dos[0].get("fatura_indirim") or 0) == 1000.0


def test_yurtici_alis_ozet_ve_turkce_masraf(monkeypatch):
    at, _db = _ac(monkeypatch, "kayranpm", "pm_sayfa", "💵  Yurt İçi Alış")
    assert not _sorunlar(at), _sorunlar(at)
    nak = [t for t in at.text_input if t.key and t.key.startswith("yi_yeni_m_")][0]
    nak.input("1.250,75").run()
    assert not _sorunlar(at), _sorunlar(at)
    oz = " ".join(str(m.value) for m in at.markdown if "Alım özeti" in str(m.value))
    assert "Alım özeti" in oz and "1.250,75" in oz, oz[:400]
