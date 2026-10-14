# -*- coding: utf-8 -*-
"""Ortak liste masası (shared/masa.py): koşul kuralı ve tarayıcıdan gelen isteğin genel doğrulanması.
Tarayıcıdan gelen hiçbir değere güvenilmez: işlem tanımda, kimlik listede, satır işlemin koşulunda,
alan türü/seçeneği/zorunluluğu tanıma uygun olmalı."""
import sys
from datetime import date
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from shared import masa as M  # noqa: E402

VERI = {
    "satirlar": [
        {"id": 1, "durum": "bekliyor", "tl": 100.0, "_baslik": "A"},
        {"id": 2, "durum": "bekliyor", "tl": 50.0, "_baslik": "B"},
        {"id": 3, "durum": "odendi", "tl": 70.0, "_baslik": "C"},
        {"id": "SKU-1", "durum": "bekliyor", "tl": 0, "_baslik": "D"},
    ],
    "islemler": [
        {"k": "ode", "ad": "Öde", "f": [["durum", "ne", "odendi"]], "toplu": {"ad": "Seçilenleri öde", "alanlar": ["banka"]},
         "alanlar": [{"ad": "banka", "tip": "secim", "zorunlu": True, "secenekler": [{"k": 1, "ad": "Garanti"}, {"k": "_yok", "ad": "Düşme"}]},
                     {"ad": "tl", "tip": "sayi", "en_cok_alan": "tl"}]},
        {"k": "otele", "ad": "Ötele", "f": [["durum", "ne", "odendi"]],
         "alanlar": [{"ad": "vade", "tip": "tarih"}, {"ad": "gun", "tip": "gizli", "sayi": True, "en_az": 1, "en_cok": 366}]},
        {"k": "duzenle", "ad": "Düzenle", "alanlar": [{"ad": "ack", "tip": "metin", "en_uzun": 5}]},
        {"k": "sil", "ad": "Sil", "alanlar": [{"ad": "onay", "tip": "onay", "zorunlu": True}]},
        {"k": "geri", "ad": "Geri al", "f": [["durum", "eq", "odendi"]]},
        {"k": "geri2", "ad": "Geri al", "coklu": True},
        {"k": "ac", "ad": "Aç", "okuma": True},
    ],
}


@pytest.mark.parametrize("satir, f, beklenen", [
    ({"a": 1}, [["a", "eq", 1]], True), ({"a": 1}, [["a", "ne", 1]], False),
    ({"a": "x"}, [["a", "in", ["x", "y"]]], True), ({"a": "z"}, [["a", "nin", ["x"]]], True),
    ({"a": 5}, [["a", "gt", 0]], True), ({"a": 0}, [["a", "gt", 0]], False), ({"a": None}, [["a", "gt", 0]], False),
    ({"a": -1}, [["a", "lt", 0]], True), ({"a": "x"}, [["a", "var", None]], True), ({"a": ""}, [["a", "yok", None]], True),
    ({"a": 1, "b": 2}, [["a", "eq", 1], ["b", "eq", 3]], False), ({}, [], True), ({}, None, True),
])
def test_kosul(satir, f, beklenen):
    assert M.kosul_uyar(satir, f) is beklenen


def test_gecerli_tek_ve_toplu():
    t, h = M.istek_al(VERI, {"islem": "ode", "ids": [1], "degerler": {"banka": "1", "tl": "60"}})
    assert h is None and t["ids"] == [1] and t["degerler"] == {"banka": 1, "tl": 60.0} and t["satirlar"][0]["_baslik"] == "A"
    t, h = M.istek_al(VERI, {"islem": "ode", "ids": [1, 2, 2], "degerler": {"banka": "_yok"}})
    assert h is None and t["ids"] == [1, 2] and t["degerler"] == {"banka": "_yok"}
    t, h = M.istek_al(VERI, {"islem": "otele", "ids": [1], "degerler": {"gun": 7}})
    assert h is None and t["degerler"] == {"gun": 7.0}
    t, h = M.istek_al(VERI, {"islem": "otele", "ids": [2], "degerler": {"vade": "2026-10-30"}})
    assert t["degerler"] == {"vade": date(2026, 10, 30)}
    t, h = M.istek_al(VERI, {"islem": "duzenle", "ids": ["SKU-1"], "degerler": {"ack": "  uzun metin  "}})
    assert h is None and t["degerler"] == {"ack": "uzun "}                      # kırpılır, en_uzun
    t, h = M.istek_al(VERI, {"islem": "sil", "ids": [2], "degerler": {"onay": True}})
    assert h is None


@pytest.mark.parametrize("istek, parca", [
    ({"islem": "uydur", "ids": [1]}, "Bilinmeyen"),
    ({"islem": "ode", "ids": []}, "seçilmedi"),
    ({"islem": "ode", "ids": [99], "degerler": {"banka": 1}}, "bulunamadı"),
    ({"islem": "ode", "ids": [True], "degerler": {"banka": 1}}, "bulunamadı"),
    ({"islem": "ode", "ids": [3], "degerler": {"banka": 1}}, "uygun değil"),           # ödenmiş satır
    ({"islem": "ode", "ids": [1]}, "gerekli"),                                          # banka zorunlu
    ({"islem": "ode", "ids": [1], "degerler": {"banka": 99}}, "listeden"),
    ({"islem": "ode", "ids": [1], "degerler": {"banka": 1, "tl": "101"}}, "aşamaz"),
    ({"islem": "ode", "ids": [1], "degerler": {"banka": 1, "tl": "-5"}}, "geçerli"),
    ({"islem": "ode", "ids": [1], "degerler": {"banka": 1, "tl": "abc"}}, "geçerli"),
    ({"islem": "otele", "ids": [1, 2], "degerler": {"gun": 7}}, "tek kayıt"),          # toplu değil
    ({"islem": "otele", "ids": [1], "degerler": {"gun": 0}}, "geçerli"),
    ({"islem": "otele", "ids": [1], "degerler": {"gun": 400}}, "en çok"),
    ({"islem": "otele", "ids": [1], "degerler": {"vade": "30.10.2026"}}, "tarih"),
    ({"islem": "sil", "ids": [1], "degerler": {"onay": "evet"}}, "onay"),
    ({"islem": "sil", "ids": [1]}, "gerekli"),
    ({"islem": "geri", "ids": [1]}, "uygun değil"),
    (None, "Bilinmeyen"),
])
def test_gecersiz(istek, parca):
    t, h = M.istek_al(VERI, istek)
    assert t is None and parca in h, h


def test_salt_okur_yalniz_okuma_islemleri():
    v = dict(VERI, salt=True)
    t, h = M.istek_al(v, {"islem": "ode", "ids": [1], "degerler": {"banka": 1}})
    assert t is None and "Salt-okur" in h
    t, h = M.istek_al(v, {"islem": "ac", "ids": [1]})
    assert h is None and t["islem"] == "ac"


def test_veri_jsonlanir():
    assert M._jsonlanir({"t": date(2026, 10, 14), "n": [1, 2]}) == {"t": "2026-10-14", "n": [1, 2]}


def test_bilesen_tek_kez_kaydedilir_ve_metinleri_kacirir():
    """JS her değeri e() ile kaçırır (firma adında < > olabilir); innerHTML'e ham veri girmez."""
    js = M._JS
    assert "const e = s =>" in js and "${e(" in js
    assert "${r._baslik}" not in js and "${x[c.alan]}" not in js


def test_coklu_islem_cubukta_degil_ama_birden_cok_kimlik_alir():
    t, h = M.istek_al(VERI, {"islem": "geri2", "ids": [1, 3]})
    assert h is None and t["ids"] == [1, 3]


def test_ozet_bandi_butun_kart_seritlerinde():
    """Tüm program yeni tasarım: kpi_serit / metrik_satiri kartları tek bant (ödeme masasıyla aynı görünüm)."""
    from shared import tasarim as T
    css = T.cekirdek_css()
    assert ".k-grid:has(> .k-kart.k-yeni){gap:1px;background:var(--k-kenar)" in css
    assert ".k-grid > .k-kart.k-yeni{border:0;border-radius:0" in css
    assert 'class="k-grid"' in T.kpi_serit([{"etiket": "A", "deger": "1"}])
