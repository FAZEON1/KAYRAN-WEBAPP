# -*- coding: utf-8 -*-
"""Para haritası (Ekim 2026, Yönetim › Para haritası): sermaye şu an nerede bekliyor?

Kullanıcı kararı: depodaki stok paçal ile (KDV'siz), Stok yaşı ile aynı yaş grupları. Para birimi
kuralları mevcut ekranlardan: banka EUR × 1,08 (Banka bakiyeleri), cari EUR × 1,10 (Toplam
Aktifler). Borç = cari borç + verilen çekler (Toplam Aktifler ile aynı); bekleyen ödemeler bilgi.
"""
from pathlib import Path

import pytest

import yonetim_para as P

KOK = Path(__file__).resolve().parent.parent
KUR = 40.0

V = {
    "ithalat": {"Üretimde": 1000, "Yolda": 5000, "Gümrükte": 700, "Antrepoda": 300, "Teslim Alındı": 9999},
    "depo": {"0–30 gün": 4000, "31–60 gün": 1000, "61–90 gün": 500, "91–180 gün": 2000, "180+ gün": 3000,
             "Giriş kaydı yok": 100},
    "alacak": {"usd": 6000, "tl": 40000, "eur": 1000},
    "borc": {"usd": 2000, "tl": 0, "eur": 0},
    "banka": [{"para_birimi": "USD", "bakiye": 1500}, {"para_birimi": "TL", "bakiye": 80000},
              {"para_birimi": "EUR", "bakiye": 100}],
    "cek": (20000.0, 500.0),
    "odeme": (4000.0, 300.0),
    "alacak_tarih": "2026-10-01",
}


def _b(h, ad):
    return next(x["tutar"] for x in h["varlik"] + h["borc"] if x["ad"] == ad)


def test_asamalar_ve_tutarlar():
    h = P.harita(V, KUR)
    assert _b(h, "Üretimde") == 1000 and _b(h, "Yolda") == 5000
    assert _b(h, "Gümrük / antrepo") == 1000                      # gümrükte + antrepoda
    assert all(x["ad"] != "Teslim Alındı" for x in h["varlik"])    # teslim alınan depodadır
    assert _b(h, "Depoda · 0–90 gün") == 5500 and _b(h, "Depoda · 91–180 gün") == 2000
    assert _b(h, "Depoda · 180+ gün") == 3000 and _b(h, "Depoda · giriş kaydı yok") == 100
    assert _b(h, "Müşteri alacağı") == pytest.approx(6000 + 40000 / KUR + 1000 * 1.10)   # Toplam Aktifler kuralı
    assert _b(h, "Banka") == pytest.approx(1500 + 80000 / KUR + 100 * 1.08)              # Banka ekranı kuralı
    assert _b(h, "Cari borç") == 2000 and _b(h, "Verilen çekler") == pytest.approx(500 + 20000 / KUR)


def test_toplamlar_net_ve_pay():
    h = P.harita(V, KUR)
    tv = 7000 + 10600 + (6000 + 1000 + 1100) + (1500 + 2000 + 108)
    assert h["toplam_varlik"] == pytest.approx(tv)
    assert h["toplam_borc"] == pytest.approx(2000 + 1000)
    assert h["net"] == pytest.approx(tv - 3000)
    assert h["mal_pay"] == pytest.approx((7000 + 10600) / tv * 100)
    assert h["depo"] == 10600 and h["yasli"] == 3000
    assert h["bekleyen_odeme"] == pytest.approx(300 + 4000 / KUR)   # bilgi; borca eklenmez


def test_kur_yoksa_tl_sayilmaz_ve_yazilir():
    h = P.harita(V, None)
    assert _b(h, "Banka") == pytest.approx(1500 + 108) and _b(h, "Müşteri alacağı") == pytest.approx(7100)
    assert any("kur" in e for e in h["eksik"])


def test_cari_excel_yoksa_not():
    h = P.harita(dict(V, alacak=None, borc=None), KUR)
    assert _b(h, "Müşteri alacağı") == 0 and any("cari Excel" in e for e in h["eksik"])
    assert all(x["ad"] != "Cari borç" for x in h["borc"])


def test_ozet_cumlesi():
    s = P.ozet_cumlesi(P.harita(V, KUR))
    assert "mal olarak bekliyor" in s and "180 günü geçmiş" in s and "%28" in s     # 3.000 / 10.600


def test_cubuk_orantili():
    h = P.harita(V, KUR)
    c = P.cubuk_html(h["varlik"], h["toplam_varlik"])
    assert c.count("<i ") == 9 and f"width:{5000 / h['toplam_varlik'] * 100:.3f}%" in c
    assert P.cubuk_html([], 0) == ""


def test_bos_veri_cokmez():
    h = P.harita({}, None)
    assert h["toplam_varlik"] == 0 and P.ozet_cumlesi(h) == "Henüz gösterilecek tutar yok."


def test_yonetimde_kar_gizlemeden_once_ve_salt_okur():
    y = (KOK / "yonetim.py").read_text(encoding="utf-8")
    assert y.index('if _bolum == "Para haritası":') < y.index("if not kar_gorunur():")
    kod = (KOK / "yonetim_para.py").read_text(encoding="utf-8")
    for yasak in (".table(", "get_client(", "set_ayar(", ".insert(", ".delete("):
        assert yasak not in kod, yasak
