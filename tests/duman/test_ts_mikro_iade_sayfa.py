# -*- coding: utf-8 -*-
"""Sayfa testi · Teknik Servis › İade, Mikro'dan gelen iade faturası (22.10.2026): 'mal kabul bekleniyor' kayıtları
masada en üstte, 30 günü geçen için üst uyarı; kaydın Durum Güncelle penceresi mal kabul formu (seri no açıklamadan
hazır), kaydedince durum 'mal kabül' ve liste; başka sayfaya geçip dönünce açık ayrıntı kapanır.
Yalnız gerçek Streamlit kuruluyken çalışır (CI: "Sayfa testi")."""
from datetime import date, timedelta

import pytest

pytest.importorskip("streamlit.testing.v1")

from test_dosya_kapisi import _sorunlar  # noqa: E402
from test_odeme_masasi_sayfa import _bilesen_verisi  # noqa: E402
from test_sayfalar import BETIK, SURE  # noqa: E402


def _kayitlar():
    eski = str(date.today() - timedelta(days=40))
    yeni = str(date.today() - timedelta(days=2))
    ortak = {"arayuz": "iade", "mevcut_durum": "iade faturası işlendi", "stok_kodu": "X24F165S",
             "firma_bilgisi": "EERA BİLGİSAYAR", "iade_fatura_no": "IAD7", "fatura_mevcut": True}
    return [dict(ortak, id=501, servis_form_no="G5F00818", iade_fatura_tarihi=eski, olusturma_tarihi=eski,
                 iade_aciklama="Seri No:W2505W03643", mikro_iade_anahtar="a#1"),
            dict(ortak, id=502, servis_form_no="G5F00819", iade_fatura_tarihi=yeni, olusturma_tarihi=yeni,
                 iade_aciklama="", hasarli_teslim=True, mikro_iade_anahtar="b#1")]


def _ac(monkeypatch, ek=None):
    monkeypatch.setenv("DUMAN_ONBELLEK_TEMIZLE", "1")
    import sahte_db
    from streamlit.testing.v1 import AppTest
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    sahte_db.TABLOLAR["ts_kayitlar"] = _kayitlar()
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    for k, v in dict({"giris_yapildi": True, "aktif_kullanici": sahte_db.KULLANICI, "aktif_uygulama": "teknikservis",
                      "ts_sayfa": "↩️  İade"}, **(ek or {})).items():
        at.session_state[k] = v
    at.run()
    assert not _sorunlar(at), _sorunlar(at)
    return at, sahte_db


def test_bekleyenler_ustte_ve_uyari(monkeypatch):
    at, _db = _ac(monkeypatch)
    v = _bilesen_verisi(at.main, [])[0]
    assert [r["sfn"] for r in v["satirlar"]][:2] == ["G5F00818", "G5F00819"]
    assert v["satirlar"][0]["durum_m"] == "mal kabul bekleniyor"
    assert v["satirlar"][1]["durum_m"] == "mal kabul bekleniyor (teslim alınmayan hasarlı ürünler)"
    assert {o["k"]: o["dg"] for o in v["ozet"]} == {"bekleyen": "2", "hasarli": "1", "gecikmis": "1"}
    assert any("30 günden uzun süredir mal kabul bekliyor" in w.value for w in at.warning)


def test_durum_guncelle_mal_kabul_formu(monkeypatch):
    at, db = _ac(monkeypatch, {"_ts_iade_secili": 501})
    at.button(key="btn_ts_durum").click().run()
    assert not _sorunlar(at), _sorunlar(at)
    assert at.text_input(key="ts_imk_seri_501").value == "W2505W03643"       # muhasebe açıklamasından
    assert not any(getattr(s, "key", "") == "ts_yd_501" for s in at.selectbox)   # durum listesi yerine mal kabul
    at.selectbox(key="ts_imk_sevk_501").select("Firma sevkiyat")
    at.text_input(key="ts_imk_irs_501").input("IRS-1")
    at.session_state["_ts_durum_ac"] = 501           # AppTest tam yeniler: pencereyi yeniden aç
    at.button(key="FormSubmitter:ts_imk_501-Mal kabul et").click().run()
    assert not _sorunlar(at), _sorunlar(at)
    # sahte veritabanı update'i bellekte uygulamaz; yazılan geçmiş satırı kaydın 'mal kabül'e geçtiğini gösterir
    g = [r for r in db.TABLOLAR.get("ts_gecmis", []) if r["kayit_id"] == 501]
    assert [(r["durum"], r["aciklama"]) for r in g] == [("mal kabül", "Mal kabul yapıldı (iade faturası IAD7)")]
    assert "_ts_iade_secili" not in at.session_state                        # listeye döndü


def test_sayfa_degisince_ayrinti_kapanir(monkeypatch):
    at, _db = _ac(monkeypatch, {"_ts_iade_secili": 501})
    assert "ts_iade_geri" in {getattr(b, "key", None) for b in at.button}
    at.session_state["ts_sayfa"] = "📦  Depolar"
    at.run()
    at.session_state["ts_sayfa"] = "↩️  İade"
    at.run()
    assert not _sorunlar(at), _sorunlar(at)
    assert "_ts_iade_secili" not in at.session_state and _bilesen_verisi(at.main, [])
