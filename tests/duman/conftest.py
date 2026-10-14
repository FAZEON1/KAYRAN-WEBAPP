# -*- coding: utf-8 -*-
"""Sayfa testleri ortak düzeni.

Her AppTest yeni bir Streamlit çalışma zamanı kurar ve bileşen kaydı (components v2) onunla birlikte
sıfırlanır; shared/masa.py ve shared/tablo.py ise bileşen nesnesini modülde saklar. Aynı süreçte ikinci bir
sayfa testi saklı nesneyi kullanınca "Component 'kayran_masa' is not registered" ile çöker (canlıda tek
çalışma zamanı olduğu için görülmez). Her testten önce saklı nesne bırakılır; bileşen o testin çalışma
zamanında yeniden kaydedilir."""
import sys

import pytest


@pytest.fixture(autouse=True)
def _bilesen_kaydini_sifirla():
    for ad in ("shared.masa", "shared.tablo"):
        m = sys.modules.get(ad)
        if m is not None and hasattr(m, "_BILESEN"):
            m._BILESEN = None
    yield
