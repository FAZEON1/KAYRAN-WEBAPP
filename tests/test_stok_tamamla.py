# -*- coding: utf-8 -*-
"""Sipariş yüklemede eksik stoğu başka depodan tamamlama (Ekim 2026).

Eskiden yalnız "Yetersiz stok" uyarısı vardı ve kalan, satırın deposunu eksiye düşürüyordu.
Şimdi stoğu olan diğer depolar gösterilir; kullanıcı seçer, stok o depolardan düşer.
"""
from pathlib import Path

from satis import stok_tamamla as T

KOK = Path(__file__).resolve().parent.parent
DAG = {"X24F240P": {"MERKEZ DEPO": 5, "HAPPY LIFE": 12, "İADE DEPO": 2},
       "X27F300": {"MERKEZ DEPO": 40}}


def test_eksik_urun_ve_secenekler():
    e = T.eksikler({"MERKEZ DEPO": {"X24F240P": 8, "X27F300": 10}}, DAG.get)
    assert len(e) == 1
    assert e[0] == {"hedef": "MERKEZ DEPO", "sku": "X24F240P", "gerek": 8.0, "mevcut": 5.0, "eksik": 3.0,
                    "secenekler": [("HAPPY LIFE", 12.0), ("İADE DEPO", 2.0)]}


def test_secilen_sirayla_mevcut_kadar_alinir():
    sec = [("HAPPY LIFE", 12.0), ("İADE DEPO", 2.0)]
    assert T.dagit(3, ["İADE DEPO", "HAPPY LIFE"], sec) == ([("İADE DEPO", 2.0), ("HAPPY LIFE", 1.0)], 0)
    assert T.dagit(20, ["İADE DEPO"], sec) == ([("İADE DEPO", 2.0)], 18.0)
    assert T.dagit(3, [], sec) == ([], 3.0)


def test_stok_dusumu_plani_uygulanir():
    gruplu = {"MERKEZ DEPO": {"X24F240P": 8, "X27F300": 10}}
    plan = {("MERKEZ DEPO", "X24F240P"): [("HAPPY LIFE", 3.0)]}
    assert T.uygula(gruplu, plan) == {"MERKEZ DEPO": {"X24F240P": 5.0, "X27F300": 10},
                                      "HAPPY LIFE": {"X24F240P": 3.0}}
    assert gruplu == {"MERKEZ DEPO": {"X24F240P": 8, "X27F300": 10}}       # girdi değişmez


def test_atlanan_satirin_plani_tasinmaz():
    """Satır zaten kayıtlıysa (atlandı) düşülecek adet yok; plan o adedi aşamaz."""
    plan = {("MERKEZ DEPO", "X24F240P"): [("HAPPY LIFE", 3.0)]}
    assert T.uygula({"MERKEZ DEPO": {"X24F240P": 2}}, plan) == {"HAPPY LIFE": {"X24F240P": 2.0}}
    assert T.uygula({"MERKEZ DEPO": {"X27F300": 4}}, plan) == {"MERKEZ DEPO": {"X27F300": 4}}


def test_sku_yazimi_farkli_olsa_da_eslesir():
    plan = {("MERKEZ DEPO", "fazeon x24f240p"): [("HAPPY LIFE", 1.0)]}
    norm = lambda s: s.upper().replace("FAZEON ", "")  # noqa: E731
    assert T.uygula({"MERKEZ DEPO": {"X24F240P": 2}}, plan, norm) == \
        {"MERKEZ DEPO": {"X24F240P": 1.0}, "HAPPY LIFE": {"X24F240P": 1.0}}


def test_yukleme_plani_kayda_ve_stoga_ulasir():
    m = (KOK / "satis/main.py").read_text(encoding="utf-8")
    assert m.count("_sg_depo_sec(kapi.anahtar(") == 2 and "_plan_v)" in m and "_plan_k)" in m
    assert "tamamla=_plan or None" in m
    d = (KOK / "satis/database.py").read_text(encoding="utf-8")
    i = d.index("_tamamla_uygula(_depo_gruplu, tamamla")
    assert i < d.index("_stok_akilli_dus(_hrk, _d)", i)


def test_ice_aktarimda_stok_secilen_depodan_duser(monkeypatch):
    import satis.database as SD
    dusulen = []

    class _Q:
        def insert(self, r):
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    monkeypatch.setattr(SD, "_get_client", lambda: type("C", (), {"table": lambda self, t: _Q()})())
    monkeypatch.setattr(SD, "get_pacal_map", lambda: {})
    monkeypatch.setattr(SD, "get_mevcut_satis_anahtarlari", lambda: set())
    monkeypatch.setattr(SD, "_temizle", lambda: None)
    monkeypatch.setattr(SD, "_marj_uyarisi_gonder", lambda *a, **k: None)
    monkeypatch.setattr(SD, "_aktif_yukleme", lambda: None)
    monkeypatch.setattr(SD, "_stok_akilli_dus", lambda h, d: dusulen.append((d, dict(h))))
    satir = {"tarih": "2026-10-07", "kanal": "VATAN", "siparis_no": "V1", "sku": "X24F240P", "adet": 8,
             "birim_satis": 100, "depo": "MERKEZ DEPO"}
    SD.ice_aktar_satislar([satir], tamamla={("MERKEZ DEPO", "X24F240P"): [("HAPPY LIFE", 3.0)]})
    assert sorted(dusulen) == [("HAPPY LIFE", {"X24F240P": 3.0}), ("MERKEZ DEPO", {"X24F240P": 5.0})]
