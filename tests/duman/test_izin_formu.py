# -*- coding: utf-8 -*-
"""Sayfa testi: izin formu ve yıllık izin kayıt belgesi PDF olarak üretilir (reportlab, logo, Türkçe font);
İzinler sayfasındaki "İzin formu" düğmesi belgeyi hazırlayıp indirme düğmesine döner."""
from datetime import date

import pytest

pytest.importorskip("reportlab")
pytest.importorskip("streamlit.testing.v1")

from test_izin_sayfa import _ac, _veri  # noqa: E402

SIRKET = {"unvan": "G5F TEKNOLOJİ SANAYİ TİCARET ANONİM ŞİRKETİ", "adres": "Ümraniye/İstanbul",
          "vkn": "3881881884", "tel": "0216 466 28 88"}


def _sayfa_sayisi(pdf):
    return pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages")


def test_pdfler_uretilir():
    from shared.izin_belge import izin_formu_pdf, kayit_belgesi_pdf
    v = _veri()
    ali = next(p for p in v["personel"] if p["kod"] == "ali")
    tal = [t for t in v["izin_talepleri"] if t["personel"] == "ali"]
    for t in tal:
        pdf = izin_formu_pdf(t, ali, tal, date.today(), sirket=SIRKET)
        assert pdf[:5] == b"%PDF-" and _sayfa_sayisi(pdf) == 1 and b"/Subtype /Image" in pdf    # logo
    kb = kayit_belgesi_pdf(ali, tal, date.today(), sirket=SIRKET)
    assert kb[:5] == b"%PDF-" and _sayfa_sayisi(kb) == 1
    # çok kayıtlı belge sayfalara bölünür ve hata vermez
    cok = [dict(tal[0], id=100 + i, durum="onaylandi", baslangic=f"2026-0{1 + i % 9}-0{1 + i % 8}",
                bitis=f"2026-0{1 + i % 9}-0{1 + i % 8}") for i in range(40)]
    assert _sayfa_sayisi(kayit_belgesi_pdf(ali, cok, date.today(), sirket=SIRKET)) >= 2


def test_sevk_fisinde_logo():
    from depo.belge import sevk_fisi_pdf
    pdf = sevk_fisi_pdf({"firma": "EERA", "sku": "X1", "urun_adi": "Monitör"}, {"adet": 2, "fis_no": "KYR-2026-00001"},
                        sirket=SIRKET)
    assert pdf[:5] == b"%PDF-" and b"/Subtype /Image" in pdf


def test_form_dugmesi_sayfada():
    at = _ac(kullanici="ali")
    at.button(key="izn_pdf_2_onaylandi_h").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    at = _ac(bolum="Personel")
    assert not at.exception
