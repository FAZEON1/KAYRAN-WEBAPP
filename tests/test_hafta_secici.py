# -*- coding: utf-8 -*-
"""Muhasebe üst satırındaki hafta düğmesi (Ekim 2026): tek tıkla hafta değişir."""
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def test_hafta_secenekleri_en_yeni_once_ve_aktif_isaretli():
    from kayranacc.odeme_hesap import hafta_secenekleri
    h = [{"id": 7, "hafta_adi": "05.10.2026 GÜNCEL ÖDEME LİSTESİ", "yuklendi_tarih": "05.10.2026"},
         {"id": 8, "hafta_adi": "12.10.2026 GÜNCEL ÖDEME LİSTESİ"}, {"id": 6, "hafta_adi": ""}]
    s = hafta_secenekleri(h, 8)
    assert [(x["id"], x["aktif"]) for x in s] == [(8, True), (7, False), (6, False)]
    assert s[1]["yuklendi"] == "05.10.2026" and s[2]["ad"] == "Hafta 6"


def test_hafta_secenekleri_sinir_ve_eski_aktif():
    from kayranacc.odeme_hesap import hafta_secenekleri
    h = [{"id": i, "hafta_adi": f"H{i}"} for i in range(1, 21)]
    s = hafta_secenekleri(h, 2, sinir=5)
    assert [x["id"] for x in s] == [2, 20, 19, 18, 17, 16]       # aktif eski hafta listede kalır
    assert hafta_secenekleri([], None) == []


def test_ust_satir_hafta_dugmesi():
    m = (KOK / "kayranacc/main.py").read_text(encoding="utf-8")
    assert "_hafta_secici(hafta)" in m and 'key=f"acc_hafta_{h[\'id\']}"' in m
    assert "hafta_aktif_yap(h[\"id\"])" in m
