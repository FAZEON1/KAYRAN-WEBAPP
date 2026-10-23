# -*- coding: utf-8 -*-
"""Talepler #44, #45, #46 (23.10.2026; kullanıcı: "evet yap").

#45 Korkut: "Yönetim paneline konulan satış ciroları, iadeler düşülmüş olarak olmalıdır." Toplam ciro netti; kanal
    ve ürün kırılımı brüt kalıyordu (toplamla tutmuyordu). Patron panosu (ana sayfa) cirosu tamamen brüttü.
#44 Korkut: aylık satış cirosu grafiği, altında Fazeon / Others marka dağılımı.
#46 Serkan: "ASEL depo ile devam etmediğimiz için kapatılsın."
"""
from datetime import date
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent


class _Kaynak:
    """pnl_topla sahte kaynağı: VATAN 1.000 $ satış, 100 $ iade (40 $ iade kârı); EERA'da satışsız 20 $ iade."""

    def satis(self, bas, bit):
        return ({"ciro": 1500.0, "maliyet": 900.0},
                {"VATAN BILGISAYAR ANONIM SIRKETI ": {"ciro": 1000.0, "destek": 0.0, "net_kar": 300.0, "adet": 10},
                 "EERA": {"ciro": 500.0, "destek": 0.0, "net_kar": 100.0, "adet": 5}},
                {"Fazeon X24F165S": {"urun_adi": "FAZEON X24", "ciro": 1500.0, "destek": 0.0, "net_kar": 400.0,
                                     "adet": 15}})

    def iade(self, bas, bit):
        return {"i_tutar": 120.0, "i_kar": 48.0}

    def iade_kirilim(self, bas, bit):
        isat = [{"sku": "X24F165S", "urun_adi": "FAZEON X24", "i_adet": 1, "i_tutar": 100.0, "i_kar": 40.0},
                {"sku": "ESKI1", "urun_adi": "ESKİ ÜRÜN", "i_adet": 1, "i_tutar": 20.0, "i_kar": 8.0},
                {"sku": "YOK", "i_adet": 0, "i_tutar": 0.0, "i_kar": 0.0}]
        ikan = {"120.01.003 VATAN BİLGİSAYAR": {"i_tutar": 100.0, "i_kar": 40.0, "i_adet": 1},
                "D-MARKET": {"i_tutar": 20.0, "i_kar": 8.0, "i_adet": 1}}
        return isat, ikan

    def destekler(self, bas, bit):
        return []

    def gider_kat(self, yil):
        return {}

    def alinan(self, bas, bit):
        return 0.0

    def kur_haritasi(self, bas, bit):
        return {}

    def yedek_kur(self):
        return 40.0


def _pnl():
    from yonetim_hesap import pnl_topla
    return pnl_topla(2026, "Eylül", "2026-09-01", "2026-09-30", _Kaynak(), bugun=date(2026, 10, 20))


def test_45_kanal_ve_urun_kirilimi_iade_dusulmus_toplamla_tutar():
    r = _pnl()
    assert r["ciro"] == pytest.approx(1380.0)
    assert sum(v["ciro"] for v in r["kanal"].values()) == pytest.approx(r["ciro"])     # eskiden 1.500 (brüt)
    assert sum(v["ciro"] for v in r["urun"].values()) == pytest.approx(r["ciro"])
    assert r["kanal"]["VATAN BILGISAYAR ANONIM SIRKETI "]["ciro"] == 900.0 and r["kanal"]["VATAN BILGISAYAR ANONIM SIRKETI "]["net_kar"] == 260.0
    assert r["kanal"]["VATAN BILGISAYAR ANONIM SIRKETI "]["adet"] == 9 and r["kanal"]["D-MARKET"]["ciro"] == -20.0
    assert len(r["kanal"]) == 3                       # Mikro iadesi '120.01.003 VATAN BİLGİSAYAR' satış kanalına düştü
    assert r["urun"]["Fazeon X24F165S"]["ciro"] == 1400.0       # 'X24F165S' iadesi kart yazımlı satıra düştü
    assert r["urun"]["ESKI1"]["ciro"] == -20.0 and "YOK" not in r["urun"]


def test_45_kirilim_okunamazsa_eksiklerde_kirilim_brut():
    class K(_Kaynak):
        def iade_kirilim(self, bas, bit):
            raise RuntimeError("x")
    from yonetim_hesap import pnl_topla
    r = pnl_topla(2026, "Eylül", "2026-09-01", "2026-09-30", K(), bugun=date(2026, 10, 20))
    assert r["kanal"]["VATAN BILGISAYAR ANONIM SIRKETI "]["ciro"] == 1000.0 and any("İade kırılımı" in e for e in r["eksikler"])


def test_45_patron_panosu_iade_dusulmus():
    from shared.patron import iade_satirlari, ozet, kanal_payi
    sat = [{"tarih": "2026-10-01", "kanal": "VATAN", "ciro": 1000.0, "net_kar": 300.0, "destek": 0.0, "adet": 10}]
    iad = iade_satirlari([{"tarih": "2026-10-02T00:00:00", "kanal": "120.01.003 VATAN", "sku": "Fazeon X24F165S",
                           "iade_net": 100.0, "iade_adet": 1}, {"iade_net": 0, "iade_adet": 0}],
                         {"X24F165S": 60.0})
    assert iad == [{"tarih": "2026-10-02", "kanal": "VATAN", "ciro": -100.0, "net_kar": -40.0, "destek": 0.0,
                    "adet": -1}]
    o = ozet(sat + iad)
    assert o["ciro"] == 900.0 and o["net_kar"] == 260.0 and o["adet"] == 9
    assert kanal_payi(sat + iad)[0][1] == 900.0
    p = (KOK / "shared" / "patron.py").read_text(encoding="utf-8")
    assert "_satis_satirlari(bas_iso, bit_iso) + _iade_satirlari(bas_iso, bit_iso)" in p


def test_44_marka_ciro_fazeon_others():
    from yonetim_pano import marka_ciro, fazeon_mu
    urun = {"Fazeon X24F165S": {"ciro": 700.0, "urun_adi": "X24"}, "MIO J30": {"ciro": 200.0, "urun_adi": "MIO"},
            "KARTSIZ": {"ciro": 50.0, "urun_adi": "FAZEON F1 KASA"}, "ESKI1": {"ciro": -20.0, "urun_adi": ""}}
    harita = {"X24F165S": "FAZEON", "MIO J30": "Mio"}
    assert fazeon_mu("X24F165S", "", harita) and not fazeon_mu("MIO J30", "FAZEON yazsa da", harita)
    assert marka_ciro(urun, 930.0, harita) == {"Fazeon": 750.0, "Others": 180.0}
    y = (KOK / "yonetim.py").read_text(encoding="utf-8")
    assert "_aylik_ciro(trend)" in y and 'o["marka"] = marka_ciro(' in y


def test_46_asel_depo_kapali():
    from kayranpm.database import acik_depolar, KAPALI_DEPOLAR
    assert "ASEL DEPO" in KAPALI_DEPOLAR
    assert acik_depolar(["MERKEZ DEPO", "ASEL DEPO", "Asel"], {"MERKEZ DEPO": 5}) == ["MERKEZ DEPO"]
    assert acik_depolar(["ASEL DEPO"], {"ASEL DEPO": 3}) == ["ASEL DEPO"]          # stoğu kalırsa çıkarılabilsin
    from teknikservis.stok import MAL_KABUL_DEPOLAR, giris_depo_coz
    assert "ASEL DEPO" not in MAL_KABUL_DEPOLAR and giris_depo_coz("asel") is None
    for yol, ad in (("satis/main.py", "IADE_DEPOLAR = ["), ("ithalat/main.py", "DEPO_SECENEKLER = [")):
        m = (KOK / yol).read_text(encoding="utf-8")
        satir = m[m.index(ad):].split("\n")[0]
        assert "ASEL" not in satir.split("#")[0], yol


def test_45_satis_pnl_firma_kirilimi_mikro_iadesi_firmasina_duser():
    """Kullanıcı (23.10.2026): "Satış › Kâr / P&L'deki kanal tablosunda da iadeleri düzelt". Mikro iadesinde kanal
    '120.01.003 VATAN …' (cari kodu + ünvan): firma kırılımı (ikan) ve firma süzgeci iadeyi bulamıyordu."""
    import tests.test_satis_pnl as T
    mikro = [{"kanal": "120.01.003 VATAN", "sku": "K1", "iade_net": 50, "iade_adet": 1}]
    P = T._p(T.Sahte(iadeler=mikro, iade_kanal={"120.01.003 VATAN": {"i_tutar": 50.0, "i_kar": 20.0}}))
    assert P["ikan"] == {"VATAN": {"i_tutar": 50.0, "i_kar": 20.0, "i_adet": 1}}
    F = T._p(T.Sahte(iadeler=mikro), kanal="VATAN")                     # firma süzgeci: iade düşer
    assert F["itop"]["i_tutar"] == 50.0 and F["net_ciro"] == 450.0
    assert F["ikan"] == {"VATAN": {"i_tutar": 50.0, "i_kar": 20.0, "i_adet": 1}}
    m = (KOK / "satis" / "main.py").read_text(encoding="utf-8")
    assert '"Ciro": _nc,' in m and "_kanal_t.setdefault(_kn," in m
