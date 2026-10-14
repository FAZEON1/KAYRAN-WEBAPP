# -*- coding: utf-8 -*-
"""Davranış kilidi — Satış kârı ve P&L (satis.database + satis.pnl_hesap.satis_pnl).

satir_kar / ozet_hesapla: ciro, maliyet, firma desteği + ek destek, net kâr, marj, kanal kırılımı.
iade_satis_net_ozet / iade_kanal_ozet: iade düşümü (iade kârı = iade net − adet × paçal).
satis_pnl: bütün zincir — satışlar ve iadeler SAHTE VERİTABANINDAN okunur (gerçek okuma
fonksiyonları), paçal sabit harita, Ref No / alınan destek sabit değer.

Örnek dönem: 01.09.2026 – 30.09.2026. Tutarlar USD.
"""
import pytest

PACAL = {"X24": 80.0, "K1": 18.0}

SATISLAR = [
    # ciro 1.200 · maliyet 800 · destek 10×(5+2) = 70 · net 1.200−70−800 = 330
    {"id": 1, "tarih": "2026-09-02", "kanal": "VATAN", "sku": "X24", "urun_adi": "Monitör 24", "adet": 10,
     "birim_satis": 120, "birim_maliyet": 80, "birim_firma_destek": 5, "birim_ek_destek": 2, "siparis_no": "A1"},
    # eski yazım 'Fazeon X24' · ciro 590 · maliyet 400 · destek 0 · net 190
    {"id": 2, "tarih": "2026-09-05", "kanal": "VATAN", "sku": "Fazeon X24", "urun_adi": "Monitör 24", "adet": 5,
     "birim_satis": 118, "birim_maliyet": 80, "birim_firma_destek": 0, "birim_ek_destek": None, "siparis_no": "A2"},
    # ciro 600 · maliyet 360 · destek 20×(2+1) = 60 · net 180
    {"id": 3, "tarih": "2026-09-10", "kanal": "EERA", "sku": "K1", "urun_adi": "Kasa", "adet": 20,
     "birim_satis": 30, "birim_maliyet": 18, "birim_firma_destek": 2, "birim_ek_destek": 1, "siparis_no": "B1"},
    # sınır günü (30.09 dahil), adet metin '3' · ciro 90 · maliyet 54 · net 36
    {"id": 4, "tarih": "2026-09-30", "kanal": "EERA", "sku": "K1", "urun_adi": "Kasa", "adet": "3",
     "birim_satis": 30, "birim_maliyet": 18, "birim_firma_destek": 0, "birim_ek_destek": 0, "siparis_no": "B2"},
    # dönem DIŞI (31.08) — hiçbir toplama girmez
    {"id": 5, "tarih": "2026-08-31", "kanal": "VATAN", "sku": "X24", "urun_adi": "Monitör 24", "adet": 100,
     "birim_satis": 120, "birim_maliyet": 80, "birim_firma_destek": 0, "birim_ek_destek": 0, "siparis_no": "A0"},
]
IADELER = [
    # 'Fazeon X24' iadesi → kartın yazımı X24 ; kâr etkisi 230 − 2×80 = 70
    {"id": 1, "tarih": "2026-09-12", "kanal": "VATAN", "sku": "Fazeon X24", "urun_adi": "", "iade_adet": 2,
     "iade_net": 230},
    # küçük harf 'k1' → K1 ; 28 − 1×18 = 10
    {"id": 2, "tarih": "2026-09-15", "kanal": "EERA", "sku": "k1", "urun_adi": "Kasa", "iade_adet": 1,
     "iade_net": 28},
    {"id": 3, "tarih": "2026-10-01", "kanal": "VATAN", "sku": "X24", "urun_adi": "", "iade_adet": 50,
     "iade_net": 5000},
]
URUNLER = [{"sku": "X24", "urun_adi": "Monitör 24", "kategori": "Monitör", "marka": "FAZEON"},
           {"sku": "K1", "urun_adi": "Kasa", "kategori": "KASA", "marka": "FAZEON"}]


@pytest.fixture
def veri(sahte_db, monkeypatch):
    import kayranpm.database as pdb
    import satis.database as sdb
    db = sahte_db(satislar=SATISLAR, iadeler=IADELER, urunler=URUNLER)
    monkeypatch.setattr(sdb, "_get_client", lambda: db)
    monkeypatch.setattr(pdb, "get_client", lambda: db)
    monkeypatch.setattr(sdb, "get_pacal_map", lambda: dict(PACAL))
    return db


class Kaynak:
    """Gerçek satış/iade okumaları + sabit Ref No / alınan destek."""

    def __init__(self, ref=None, kmap=None, yedek=0.0, alinan=0.0, alinan_kat=None, ref_kat=None):
        self.ref, self.kmap, self.yedek, self.al = ref or [], kmap or {}, yedek, alinan
        self.al_kat, self.ref_kat = alinan_kat or {}, ref_kat or {}

    def satislar(self, b, e):
        from satis.database import get_satislar_yalin
        return get_satislar_yalin(b, e)

    def katmap(self):
        from satis.database import get_sku_kategori
        return get_sku_kategori()

    def iade_ozet(self, b, e):
        from satis.database import iade_satis_net_ozet
        return iade_satis_net_ozet(b, e)

    def iade_kanal(self, b, e):
        from satis.database import iade_kanal_ozet
        return iade_kanal_ozet(b, e)

    def iadeler(self, b, e):
        from satis.database import get_iadeler
        return get_iadeler(b, e)

    def pacal(self):
        from satis.database import get_pacal_map
        return get_pacal_map()

    def ref_tutarlari(self, b, e): return self.ref
    def alinan(self, b, e): return self.al
    def alinan_kirilim(self, b, e): return ({}, self.al_kat, 0.0)
    def ref_kirilim(self, b, e): return {"kategori": self.ref_kat, "dagitilmayan": []}
    def kur_haritasi(self, b, e): return self.kmap
    def yedek_kur(self): return self.yedek


def _pnl(kaynak, kanal="Tümü", kat="Tümü"):
    from satis.pnl_hesap import satis_pnl
    return satis_pnl("2026-09-01", "2026-09-30", kanal, kat, kaynak)


# ── Satır ve özet ─────────────────────────────────────────────────────
def test_satir_kar_destekler_net_satistan_duser():
    """12 × adet 1; maliyet 5,10; firma desteği 2 + ek destek 1:
       net satış 12−3 = 9 ; net kâr 9−5,10 = 3,90 ; marj 3,90/9 = %43,33.
       Destek net satıştan büyükse marj 0 (negatif net satışta bölme yok)."""
    from satis.database import satir_kar
    k = satir_kar({"adet": 1, "birim_satis": 12, "birim_maliyet": 5.10, "birim_firma_destek": 2,
                   "birim_ek_destek": 1})
    assert k == pytest.approx({"adet": 1, "ciro": 12, "maliyet": 5.1, "destek": 3, "net_satis": 9,
                               "net_kar": 3.9, "marj": 43.3333}, rel=1e-4)
    z = satir_kar({"adet": "2", "birim_satis": "10", "birim_maliyet": 4, "birim_firma_destek": 12})
    assert (z["net_satis"], z["net_kar"], z["marj"]) == (-4.0, -12.0, 0.0)


def test_ozet_toplam_ve_kanal_kirilimi(veri):
    """Dönem içi 4 satır: ciro 1.200+590+600+90 = 2.480 ; maliyet 800+400+360+54 = 1.614
       destek 70+0+60+0 = 130 ; net kâr 330+190+180+36 = 736 ; adet 38
       marj = 736 / (2.480−130) = 736 / 2.350 = %31,32
       VATAN: ciro 1.790, destek 70, net 520, adet 15 ; EERA: ciro 690, destek 60, net 216, adet 23"""
    from satis.database import get_satislar_yalin, ozet_hesapla
    top, kanal, _ = ozet_hesapla(get_satislar_yalin("2026-09-01", "2026-09-30"))
    assert top == pytest.approx({"ciro": 2480, "maliyet": 1614, "destek": 130, "net_kar": 736, "adet": 38,
                                 "marj": 736 / 2350 * 100})
    assert kanal["VATAN"] == pytest.approx({"ciro": 1790, "destek": 70, "net_kar": 520, "adet": 15})
    assert kanal["EERA"] == pytest.approx({"ciro": 690, "destek": 60, "net_kar": 216, "adet": 23})


def test_iade_satis_net_ozeti_sku_yazimlari_birlesik(veri):
    """SKU kartın yazımına iner: 'Fazeon X24' satış/iade + 'X24' → tek X24 satırı ; 'k1' → K1.
       X24: s_adet 15, s_ciro 1.790, s_kar 520 ; i_adet 2, i_tutar 230, i_kar 230−2×80 = 70
            net_adet 13, net_ciro 1.560, net_kar 450
       K1 : s 23 / 690 / 216 ; i 1 / 28 / 28−18 = 10 ; net 22 / 662 / 206
       Toplam: i_tutar 258, i_kar 80, net_kar 656. Ekim iadesi (5.000) dönem dışı."""
    from satis.database import iade_satis_net_ozet
    satir, top = iade_satis_net_ozet("2026-09-01", "2026-09-30")
    s = {r["sku"]: r for r in satir}
    assert set(s) == {"X24", "K1"}
    assert {k: s["X24"][k] for k in ("s_adet", "s_ciro", "s_kar", "i_adet", "i_tutar", "i_kar",
                                     "net_adet", "net_ciro", "net_kar")} == pytest.approx(
        {"s_adet": 15, "s_ciro": 1790, "s_kar": 520, "i_adet": 2, "i_tutar": 230, "i_kar": 70,
         "net_adet": 13, "net_ciro": 1560, "net_kar": 450})
    assert (s["K1"]["i_kar"], s["K1"]["net_kar"]) == pytest.approx((10, 206))
    assert top == pytest.approx({"s_adet": 38, "s_ciro": 2480, "s_kar": 736, "i_adet": 3, "i_tutar": 258,
                                 "i_kar": 80, "net_adet": 35, "net_ciro": 2222, "net_kar": 656})


def test_iade_kanal_ozeti(veri):
    """VATAN: 230 / 230−2×80 = 70 ; EERA: 28 / 10. Paçal araması kanonik SKU ile ('k1' → K1)."""
    from satis.database import iade_kanal_ozet
    r = iade_kanal_ozet("2026-09-01", "2026-09-30")
    assert set(r) == {"VATAN", "EERA"}
    assert r["VATAN"] == pytest.approx({"i_tutar": 230, "i_kar": 70})
    assert r["EERA"] == pytest.approx({"i_tutar": 28, "i_kar": 10})


# ── satis_pnl ─────────────────────────────────────────────────────────
def test_pnl_suzgecsiz_zincir(veri):
    """net ciro = 2.480 − 258 = 2.222 ; net kâr = 736 − 80 = 656 ; net satış = 2.480 − 130 − 258 = 2.092
       Ref No: 4.100 TL ÷ 41 (03.09 kuru) = 100 + 50 USD = 150 ; alınan destek +40
       nihai = 656 − 150 + 40 = 546 ; nihai marj = 546 / 2.092 = %26,10 ; net marj 656/2.092 = %31,36"""
    r = _pnl(Kaynak(ref=[{"tutar": 4100, "doviz": "TL", "tarih": "2026-09-03"},
                         {"tutar": 50, "doviz": "USD", "tarih": "2026-09-20"}],
                    kmap={"2026-09-03": 41.0}, alinan=40.0))
    assert r["eksikler"] == []
    assert (r["net_ciro"], r["net_kar"], r["net_satis"]) == pytest.approx((2222, 656, 2092))
    assert (r["ref_usd"], r["ref_g"], r["alinan_usd"]) == pytest.approx((150, 150, 40))
    assert r["nihai"] == pytest.approx(546)
    assert r["nihai_marj"] == pytest.approx(546 / 2092 * 100)
    assert r["net_marj"] == pytest.approx(656 / 2092 * 100)
    assert r["ikan"]["VATAN"]["i_kar"] == pytest.approx(70)


def test_pnl_firma_suzgeci(veri):
    """Firma VATAN: satış 1.790 ciro, 70 destek, 520 net kâr, 15 adet.
       İade yalnız VATAN: 230, kâr etkisi 70, 2 adet → net adet 13.
       Süzgeçliyken alınan destek ve Ref No toplamı EKLENMEZ: nihai = 520 − 70 = 450 ;
       net satış = 1.790 − 70 − 230 = 1.490."""
    r = _pnl(Kaynak(ref=[{"tutar": 50, "doviz": "USD"}], alinan=40.0), kanal="VATAN")
    assert r["itop"]["i_tutar"] == pytest.approx(230) and r["itop"]["i_kar"] == pytest.approx(70)
    assert (r["itop"]["i_adet"], r["itop"]["net_adet"]) == (2, 13)
    assert (r["alinan_usd"], r["ref_g"]) == (0.0, 0.0)
    assert (r["net_satis"], r["nihai"]) == pytest.approx((1490, 450))


def test_pnl_kategori_suzgeci_yazim_farki(veri):
    """Kategori süzgeci 'kasa' (kartta 'KASA') → K1 satırları: ciro 690, destek 60, net 216.
       İade 'k1' (28, kâr etkisi 10). Kategori desteği 'Kasa' 12,5 (yazımdan bağımsız eşleşir),
       Ref No kategori payı 'KASA' 7.
       nihai = (216 − 10) − 7 + 12,5 = 211,5 ; net satış = 690 − 60 − 28 = 602."""
    r = _pnl(Kaynak(alinan_kat={"Kasa": 12.5, "MONİTÖR": 99.0}, ref_kat={"KASA": 7.0, "Monitör": 3.0}),
             kat="kasa")
    assert r["top"]["ciro"] == pytest.approx(690)
    assert (r["kat_destek"], r["ref_kat"], r["ref_g"]) == pytest.approx((12.5, 7.0, 7.0))
    assert r["nihai"] == pytest.approx(211.5)
    assert r["net_satis"] == pytest.approx(602)


def test_pnl_bos_donem(veri):
    """Sınır: süzgece uyan satış yoksa 'bos' (sıfır kâr uydurulmaz)."""
    assert _pnl(Kaynak(), kanal="TEKNOSA")["bos"] is True
