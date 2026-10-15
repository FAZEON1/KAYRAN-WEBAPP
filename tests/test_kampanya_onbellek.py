# -*- coding: utf-8 -*-
"""Kampanya yazımı yalnız kampanya önbelleklerini siler (Ekim 2026).

Eskiden her kampanya kaydı st.cache_data.clear() / _cache_temizle çağırıyordu; app.py'deki akıllı
temizlik kayranpm grubunu (kayranpm + satış + depo + ithalat + shared) siliyordu. Ardından tüm ürünler
listesi soğuktan hesaplanıyordu (kampanya sayfası açılışı p50 ~5,2 sn, Serkan ölçümü). Artık yalnız
kampanya verisine bağlı önbellekler silinir."""
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

HEDEF_PM = ["get_kampanyalar", "get_kampanya", "get_kampanya_urunler", "get_tum_kampanya_urunler",
            "get_kampanya_destek_ortalamalari"]


class _Q:
    def __getattr__(self, _ad):
        return lambda *a, **k: self

    def execute(self):
        return types.SimpleNamespace(data=[{"id": 1}])


class _SB:
    def table(self, _t):
        return _Q()


@pytest.fixture
def izle(monkeypatch):
    import kayranpm.database as P
    import satis.database as S
    import kayranpm.urun_karnesi as K
    silinen, genel = [], []
    for ad in HEDEF_PM:
        monkeypatch.setattr(P, ad, types.SimpleNamespace(clear=lambda ad=ad: silinen.append(ad)))
    monkeypatch.setattr(S, "kampanya_destek_bul", types.SimpleNamespace(clear=lambda: silinen.append("kampanya_destek_bul")))
    monkeypatch.setattr(K, "portfoy", types.SimpleNamespace(clear=lambda: silinen.append("portfoy")))
    monkeypatch.setattr(P, "get_client", lambda: _SB())
    monkeypatch.setattr(P.st.cache_data, "clear", lambda: genel.append(1), raising=False)
    return P, silinen, genel


@pytest.mark.parametrize("cagri", [
    lambda P: P.kapat_kampanya(1),
    lambda P: P.sil_kampanya(1),
    lambda P: P.guncelle_kampanya(1, "K", "VATAN", "2026-10-01", "2026-10-31", ""),
    lambda P: P.ekle_kampanya("K", "VATAN", "2026-10-01", "2026-10-31"),
    lambda P: P.ekle_kampanya_urun(1, "X24", "X24", 10, 20, 1, 0),
    lambda P: P.guncelle_kampanya_urun(1, 20, 1, 0, 3),
    lambda P: P.sil_kampanya_urun(1),
])
def test_kampanya_yazimi_yalniz_kampanya_onbellegini_siler(izle, cagri):
    P, silinen, genel = izle
    cagri(P)
    assert genel == [], "bütün önbellek silindi (ürün listesi soğuktan hesaplanır)"
    assert set(silinen) == set(HEDEF_PM) | {"kampanya_destek_bul", "portfoy"}
