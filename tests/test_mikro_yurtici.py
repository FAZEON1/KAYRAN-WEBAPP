# -*- coding: utf-8 -*-
"""Mikro → yurt içi alışlar (kayranpm/mikro_yurtici.py, 22.10.2026).

Kullanıcı: "Mikro'ya giren yurt içi alımlar artık programa direkt yansısın … Mikro'daki veriler baz alınsın."
Canlı örnek: NİHAT YILMAZ NYE-25 (Faze3 10.060 adet 707.449,38 TL, kur 42,62) + iki değer farkı faturası
(13.846,89 ve 10.000 TL, sth_cins 9) → Faze3 birim 1,7045 $ (eski elle kayıt 1,65 $).
"""
from pathlib import Path

import pytest

from kayranpm import mikro_yurtici as Y

KOK = Path(__file__).resolve().parent.parent


def _r(sku, tarih, adet, tutar, kur, uid, cari="320.02.070", cins=0, seri="NYE", sira=1, **k):
    return dict({"sth_stok_kod": sku, "sth_tarih": tarih + "T00:00:00", "sth_miktar": adet, "sth_tutar": tutar,
                 "sth_iskonto": 0, "sth_masraf": 0, "sth_alt_doviz_kuru": kur, "sth_har_doviz_kuru": 1,
                 "sth_har_doviz_cinsi": 0, "sth_fat_uid": uid, "sth_cari_kodu": cari, "sth_cins": cins,
                 "sth_tip": 0, "sth_normal_iade": 0, "sth_evrakno_seri": seri, "sth_evrakno_sira": sira,
                 "sth_giris_depo_no": 1, "sth_exim_kodu": None, "sth_bagli_ithalat_kodu": None}, **k)


SATIR = [
    _r("Faze3", "2025-12-11", 10060, 707449.38, 42.62, "u25", sira=25),
    _r("Faze1", "2026-01-06", 5400, 139320, 43, "u1"),
    _r("Faze2", "2026-01-06", 3200, 185760, 43, "u1"),
    _r("Faze3", "2026-02-10", 1, 13846.89, 43.5182, "u2", cins=9, sira=2),          # değer farkı
    _r("Faze3", "2026-02-10", 1, 10000, 43.5182, "u3", cins=9, sira=3),
    _r("Faze1", "2026-02-10", 1, 5000, 43.5182, "u3", cins=9, sira=3),
    # sayılmayanlar
    _r("X24", "2026-03-01", 10, 5000, 44, "i1", cari="320.50.101"),                   # yurt dışı (ithalat)
    _r("N506", "2026-10-01", 1, 0, 48.9, "00000000-0000-0000-0000-000000000000", cari="320.02.017"),  # tutarsız
    _r("KST1", "2026-05-01", 5, 800, 45, "iade", sth_normal_iade=1),                   # iade
    _r("ABC", "2026-05-02", 5, 800, 45, "120x", cari="120.01.003"),                     # müşteri
    _r("ABC", "2026-05-03", 5, 800, 45, "exim", sth_exim_kodu="INNO-17"),               # ithalata bağlı
]
KART = {"FAZE1": "FAZE1", "FAZE2": "FAZE2", "FAZE3": "FAZE3"}


def _kart(k):
    from shared.utils import sku_anahtar
    return KART.get(sku_anahtar(k)) or k


def test_alimlar_ve_deger_farki():
    m = Y.mikro_alimlari(SATIR, _kart, {"320.02.070": "NİHAT YILMAZ"}, {1: "MERKEZ DEPO"})
    assert [x["dosya"]["dosya_no"] for x in m] == ["NYE-25", "NYE-1"]                    # yalnız 2 gerçek alış
    d25, d1 = m[0], m[1]
    assert d25["dosya"]["mikro_kodu"] == "YI:u25" and d25["dosya"]["alim_turu"] == "yurtici"
    assert d25["dosya"]["tedarikci"] == "NİHAT YILMAZ" and d25["dosya"]["teslim_deposu"] == "MERKEZ DEPO"
    assert d25["dosya"]["durum"] == "Teslim Alındı" and d25["dosya"]["stok_islendi"] is True
    f3 = d25["kalemler"][0]
    assert f3["sku"] == "FAZE3" and f3["adet"] == 10060                                 # değer farkı adet eklemez
    beklenen = (707449.38 / 42.62 + 13846.89 / 43.5182 + 10000 / 43.5182) / 10060
    assert f3["birim_fob"] == pytest.approx(round(beklenen, 4))
    assert f3["birim_fob"] == pytest.approx(1.7045, abs=1e-4)
    k = {x["sku"]: x for x in d1["kalemler"]}
    assert k["FAZE1"]["birim_fob"] == pytest.approx(round((139320 / 43 + 5000 / 43.5182) / 5400, 4))
    assert k["FAZE2"]["birim_fob"] == pytest.approx(1.35)


def test_plan_elle_kayit_yerine_mikro_ve_degisiklik():
    m = Y.mikro_alimlari(SATIR, _kart)
    elle = {"id": 611, "dosya_no": "NYE2026000000001", "alim_turu": "yurtici", "tarih": "2026-01-06",
            "mikro_kodu": None}
    yerli = {"id": 700, "dosya_no": "YU-1", "alim_turu": "yerli", "tarih": "2026-01-06", "mikro_kodu": None}
    eski = {"id": 9, "dosya_no": "ESKI", "alim_turu": "yurtici", "tarih": "2024-06-01", "mikro_kodu": None}
    p = Y.plan_yap(m, [elle, yerli, eski], {})
    assert Y.plan_ozeti(p) == {"yeni": 2, "guncellenen": 0, "silinen": 1}
    assert p["sil"][0]["id"] == 611                                  # yerli üretim ve 2025 öncesi dokunulmaz
    var = [dict(x["dosya"], id=i) for i, x in enumerate(m, 1)]
    kal = {i: x["kalemler"] for i, x in enumerate(m, 1)}
    assert Y.plan_ozeti(Y.plan_yap(m, var, kal)) == {"yeni": 0, "guncellenen": 0, "silinen": 0}   # değişiklik yok
    kal[1] = [dict(kal[1][0], birim_fob=1.65)]
    g = Y.plan_yap(m, var, kal)["guncelle"]
    assert len(g) == 1 and g[0]["kalem_degisti"] and g[0]["id"] == 1
    assert Y.plan_yap(m[1:], var, kal)["sil"] == [{"id": 1, "dosya_no": "NYE-25", "neden": "Mikro'da yok"}]


def test_esitleme_turunda_ve_aktarici_maliyet_sorgusu():
    import otonom.mikro_esitle as E
    assert ("Yurt içi alışlar", "kayranpm.mikro_yurtici", "otomatik") in E.ISLER
    a = (KOK / "araclar" / "mikro_aktarici" / "mikro_kayran.py").read_text(encoding="utf-8")
    assert '"tablo": "mikro_stok_maliyet"' in a and "FROM STOK_HAREKETLERI_OZET" in a
    import re
    assert not re.search(r"(Kaydet|Sil|Guncelle|Duzelt)V\d", a.replace('r"V\\d"', ""))   # yalnız okur
    s = (KOK / "veritabani" / "54_mikro_stok_maliyet.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS public.mikro_stok_maliyet" in s
