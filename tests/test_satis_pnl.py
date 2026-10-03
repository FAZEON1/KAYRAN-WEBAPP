# -*- coding: utf-8 -*-
"""Satış › Kâr / P&L hesabı tek fonksiyonda (Ekim 2026).

Eskiden sayfanın içinde satır satır yazılıydı: önceki dönemle karşılaştırma
yapılamıyordu, okunamayan kalemler sessizce 0 sayılıyordu ve Ref No'nun TL
tutarları tek kurla (Yönetim ise kaydın tarihindeki kurla) çevriliyordu.
"""
from datetime import date
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent

SAT = [
    {"tarih": "2026-09-05", "kanal": "VATAN", "sku": "K1", "urun_adi": "Kasa", "adet": 10,
     "birim_satis": 50, "birim_maliyet": 30, "birim_firma_destek": 0, "birim_ek_destek": 0},
    {"tarih": "2026-09-10", "kanal": "EERA", "sku": "F1", "urun_adi": "Fan", "adet": 20,
     "birim_satis": 10, "birim_maliyet": 6, "birim_firma_destek": 1, "birim_ek_destek": 0},
]


class Sahte:
    def __init__(self, **kw):
        self.v = dict(satislar=SAT, katmap={"K1": "KASA", "F1": "FAN"},
                      iade_ozet=([{"sku": "K1"}], {"i_tutar": 50.0, "i_kar": 20.0, "i_adet": 1, "net_adet": 29}),
                      iade_kanal={}, iadeler=[{"kanal": "VATAN", "sku": "K1", "iade_net": 50, "iade_adet": 1}],
                      pacal={"K1": 30.0}, ref=[], alinan=0.0, alinan_kirilim=({}, {}, 0.0),
                      ref_kirilim={"kategori": {}, "dagitilmayan": []}, kmap={}, yedek=40.0)
        self.v.update(kw)

    def _al(self, k):
        x = self.v[k]
        if isinstance(x, Exception):
            raise x
        return x

    def satislar(self, bas, bit): return self._al("satislar")
    def katmap(self): return self._al("katmap")
    def iade_ozet(self, bas, bit): return self._al("iade_ozet")
    def iade_kanal(self, bas, bit): return self._al("iade_kanal")
    def iadeler(self, bas, bit): return self._al("iadeler")
    def pacal(self): return self._al("pacal")
    def ref_tutarlari(self, bas, bit): return self._al("ref")
    def alinan(self, bas, bit): return self._al("alinan")
    def alinan_kirilim(self, bas, bit): return self._al("alinan_kirilim")
    def ref_kirilim(self, bas, bit): return self._al("ref_kirilim")
    def kur_haritasi(self, bas, bit): return self._al("kmap")
    def yedek_kur(self): return self._al("yedek")


def _p(kaynak=None, kanal="Tümü", kat="Tümü", **kw):
    from satis.pnl_hesap import satis_pnl
    return satis_pnl("2026-09-01", "2026-09-30", kanal, kat, kaynak or Sahte(**kw))


def _ozet(satislar):
    from satis.database import ozet_hesapla
    return ozet_hesapla(satislar)[0]


# ── Zincir aritmetiği (eski hesapla aynı) ───────────────────────────
def test_net_kar_zinciri():
    r = _p(ref=[{"tutar": 100, "doviz": "USD", "tarih": "2026-09-03"}], alinan=40.0)
    t = _ozet(SAT)
    assert r["net_ciro"] == pytest.approx(t["ciro"] - 50)
    assert r["net_kar"] == pytest.approx(t["net_kar"] - 20)
    assert r["net_satis"] == pytest.approx(t["ciro"] - t["destek"] - 50)
    assert r["ref_g"] == pytest.approx(100) and r["alinan_usd"] == pytest.approx(40)
    assert r["nihai"] == pytest.approx(t["net_kar"] - 20 - 100 + 40)
    assert r["nihai_marj"] == pytest.approx(r["nihai"] / r["net_satis"] * 100)
    assert r["eksikler"] == []


def test_bos_donem():
    assert _p(satislar=[])["bos"] is True


# ── Ref No: tarihli kur (Yönetim ile aynı kural) ───────────────────
def test_ref_tl_kaydin_tarihindeki_kurla():
    r = _p(ref=[{"tutar": 4000, "doviz": "TL", "tarih": "2026-09-03"},
                {"tutar": 4100, "doviz": "TRY", "tarih": "2026-09-20"}],
           kmap={"2026-09-03": 40.0, "2026-09-20": 41.0})
    assert r["ref_usd"] == pytest.approx(100 + 100)


def test_ref_tarihte_kur_yoksa_yedek_kur():
    r = _p(ref=[{"tutar": 4000, "doviz": "TL", "tarih": "2026-09-03"}], kmap={}, yedek=50.0)
    assert r["ref_usd"] == pytest.approx(80)


def test_ref_kur_hic_yoksa_eksiklere_yazilir():
    r = _p(ref=[{"tutar": 4000, "doviz": "TL", "tarih": "2026-09-03"}], kmap={}, yedek=0.0)
    assert r["ref_usd"] == 0 and any("Kur bulunamadı" in e for e in r["eksikler"])


def test_yonetim_ile_ayni_cevirim():
    from yonetim_hesap import tl_usd
    assert tl_usd(4000, "TL", "2026-09-03", {"2026-09-03": 40.0}, 50.0) == pytest.approx(100)
    assert tl_usd(4000, "TL", "2026-09-04", {"2026-09-03": 40.0}, 50.0) == pytest.approx(80)
    assert tl_usd(4000, "TL", "2026-09-04", {}, 0.0) is None
    assert tl_usd(70, "USD", None, {}, 0.0) == 70
    src = (KOK / "yonetim_hesap.py").read_text(encoding="utf-8")
    g = src[src.index("def pnl_topla"):src.index("class Kaynak")]
    assert "tl_usd(" in g


# ── Sessiz sıfır yok ───────────────────────────────────────────────
def test_okunamayan_kalem_eksiklere():
    r = _p(alinan=RuntimeError("bağlantı"), ref=ValueError("x"))
    assert r["alinan_usd"] == 0 and r["ref_usd"] == 0
    assert any("Alınan destek" in e for e in r["eksikler"])
    assert any("Ref No" in e for e in r["eksikler"])


# ── Süzgeçler ───────────────────────────────────────────────────────
def test_firma_suzgeci_iadeyi_yeniden_hesaplar():
    r = _p(kanal="EERA")
    assert r["itop"]["i_tutar"] == 0                        # VATAN'ın iadesi düşmez
    assert r["alinan_usd"] == 0                              # süzgeçliyken genel alınan destek eklenmez
    r2 = _p(kanal="VATAN")
    assert r2["itop"]["i_tutar"] == 50 and r2["itop"]["i_kar"] == pytest.approx(50 - 30)


def test_kategori_suzgeci_kategori_destegi():
    r = _p(kat="KASA", alinan_kirilim=({}, {"KASA": 12.5}, 0.0))
    assert r["kat_destek"] == pytest.approx(12.5)
    t = _ozet([SAT[0]])
    assert r["nihai"] == pytest.approx(t["net_kar"] - 20 + 12.5)


# ── Önceki dönem ────────────────────────────────────────────────────
def test_onceki_donem_esit_uzunlukta():
    from satis.pnl_hesap import onceki_donem
    assert onceki_donem(date(2026, 9, 1), date(2026, 9, 30)) == (date(2026, 8, 2), date(2026, 8, 31))
    assert onceki_donem("2026-01-01", "2026-01-10") == (date(2025, 12, 22), date(2025, 12, 31))


# ── Sayfa bağlantısı ───────────────────────────────────────────────
def test_sayfa_tek_hesabi_kullanir():
    src = (KOK / "satis" / "main.py").read_text(encoding="utf-8")
    assert src.count("satis_pnl(") >= 2                      # dönem + önceki dönem
    assert "get_tum_ref_tutarlari" not in src                # Ref çevrimi artık pnl_hesap'ta
    i = src.index("# ── Üst şerit: yalnız 4 ana gösterge ──")
    g = src[i:i + 1600]
    assert '"onceki"' in g and '"simdi"' in g


# ── Net adet süzgece uyar (eskiden süzgeçsiz toplamı gösteriyordu) ──
def test_net_adet_firma_suzgecinde():
    assert _p(kanal="EERA")["itop"]["net_adet"] == 20            # EERA: 20 adet, iadesi yok
    r = _p(kanal="VATAN")
    assert r["itop"]["i_adet"] == 1 and r["itop"]["net_adet"] == 10 - 1


def test_net_adet_kategori_suzgecinde():
    assert _p(kat="FAN")["itop"]["net_adet"] == 20


# ── Kategori süzgeci yazımdan bağımsız (Ekim 2026, Faz 1 sonrası düzeltme) ──
# Faz 1'de P&L filtresinin seçenekleri tek yazıma ('Kasa') çevrildi; satis_pnl ise
# süzgeci kart yazımıyla ('KASA' / 'kasa') BİREBİR karşılaştırıyordu → filtre boş dönüyordu.
@pytest.mark.parametrize("secim", ["Kasa", "KASA", "kasa"])
def test_kategori_suzgeci_yazimdan_bagimsiz(secim):
    r = _p(kat=secim, katmap={"K1": "kasa", "F1": "FAN"},
           alinan_kirilim=({}, {"KASA": 12.5}, 0.0),
           ref_kirilim={"kategori": {"KASA": 3.0}, "dagitilmayan": []})
    assert not r.get("bos"), "kategori seçimi kart yazımıyla tutmadı, P&L boş döndü"
    t = _ozet([SAT[0]])
    assert r["kat_destek"] == pytest.approx(12.5)
    assert r["nihai"] == pytest.approx(t["net_kar"] - 20 + 12.5 - 3.0)


def test_kategori_destek_anahtari_farkli_yazim():
    """Alınan destek / Ref kırılım anahtarı 'MONITÖR' (noktasız) olsa da 'Monitör' seçimi bulur."""
    r = _p(kat="Monitör", katmap={"K1": "monitör", "F1": "FAN"},
           alinan_kirilim=({}, {"MONITÖR": 5.0}, 0.0),
           ref_kirilim={"kategori": {"MONITÖR": 2.0}, "dagitilmayan": []})
    assert not r.get("bos") and r["kat_destek"] == pytest.approx(5.0)
