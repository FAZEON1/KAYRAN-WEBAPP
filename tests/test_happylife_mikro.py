# -*- coding: utf-8 -*-
"""Happy Life ve stok yaşı Mikro'dan, varsayılan açık (kayranpm/mikro_depo.py, 22.10.2026).

Kullanıcı: "Happy life palet listesi ihtiyacım yok. Sadece adet model ve stok yaşı yeterli. Upload görevini iptal
edelim, Mikro'dan gelen datalarla yazalım artık. Bu upload görevleri kaldırılmadıysa kaldırılsın."
Canlı (22.10.2026): Mikro depo kaynağı hiç açılmamıştı (bir kerelik onay bekliyordu); hareket tablosu 20.657 satır,
sayfasız okunursa ilk 1.000'de kalınıyor ve Happy Life stoğunun 13.604 / 14.225 adedi "giriş kaydı yok" çıkıyordu.
Sayfalı okumayla 14 modelin hepsinin giriş tarihi var (ağırlıklı ort. 114 gün, en eski 175 gün)."""
from pathlib import Path

import pytest

from kayranpm import mikro_depo as MD

KOK = Path(__file__).resolve().parent.parent


def test_varsayilan_acik_yalniz_acik_false_kapatir(monkeypatch):
    for d, beklenen in (({}, True), ({"acik": True}, True), ({"acik": False}, False)):
        monkeypatch.setattr(MD, "durum", lambda d=d: d)
        assert MD.acik_mi() is beklenen, d


class _Q:
    def __init__(self, satirlar):
        self.s, self.r = list(satirlar), None

    def select(self, *_a):
        return self

    def order(self, k, **_):
        self.s.sort(key=lambda x: str(x.get(k)))
        return self

    def range(self, a, b):
        self.r = (a, b)
        return self

    def execute(self):
        data = self.s[self.r[0]:self.r[1] + 1] if self.r else self.s[:1000]        # Supabase: en çok 1000 satır
        return type("R", (), {"data": data})()


def test_hareketler_sayfali_okunur(monkeypatch):
    har = [{"sth_guid": f"g{i:05d}", "sth_tarih": "2026-06-19", "sth_tip": 0, "sth_cins": 12, "sth_miktar": 1,
            "sth_stok_kod": "FAZEON A2120TRA", "sth_giris_depo_no": 4} for i in range(2500)]
    stok = [{"sto_kod": f"S{i:04d}", "sto_isim": "x", "depo": 4, "miktar": 1} for i in range(1200)]
    tablolar = {"mikro_depo_hareket": har, "mikro_stok_miktar": stok,
                "mikro_depo_kart": [{"dep_no": 4, "dep_adi": "HAPPY LIFE"}]}
    monkeypatch.setattr(MD, "_cli", lambda: type("C", (), {"table": lambda s, t: _Q(tablolar[t])})())
    h, depo, st = MD.veri_oku()
    assert len(h) == 2500 and len(st) == 1200 and depo == {4: "HAPPY LIFE"}


def test_happy_life_exceli_mikro_acikken_kaydedilmez():
    s = (KOK / "depo" / "main.py").read_text(encoding="utf-8")
    govde = s.split("def kapi_happylife", 1)[1].split("\ndef ", 1)[0]
    acik = govde.split("if _md_acik():", 1)[1].split("\n    from ", 1)[0]
    assert "return" in acik and "checkbox" not in acik                     # "palet listesi olarak kaydet" yok


def test_happy_life_sayfasi_model_adet_yas():
    s = (KOK / "kayranpm" / "mikro_depo_ekran.py").read_text(encoding="utf-8")
    govde = s.split("def hl_sayfasi", 1)[1].split("\ndef ", 1)[0]
    for kolon in ('"Model"', '"Adet"', '"Stok yaşı (gün)"'):
        assert kolon in govde, kolon
    assert "Elde kalan partiler" not in govde and "depo_parti_satirlari" not in govde
    sayfa = (KOK / "depo" / "main.py").read_text(encoding="utf-8").split("def _sayfa_happylife", 1)[1] \
        .split("\ndef ", 1)[0]
    assert "expander" not in sayfa and "_hl_excel_goster()" in sayfa.split("if _md_sayfa():", 1)[1]   # Excel yalnız yedekte


def test_yukleme_gorevi_yalniz_mikro_disi_kaynaklarda():
    import shared.yetki as Y
    roller = [r for r in Y.OZEL if r.startswith("yukleme_sorumlusu:")]
    assert roller == ["yukleme_sorumlusu:musteri_haftalik"]


@pytest.mark.parametrize("tur", ["happylife", "odeme_listesi"])
def test_kapi_mikro_listesinde(tur):
    from shared.dosya_kapisi import MIKRO_ESITLEME, _VARSAYILAN_ACIK
    assert MIKRO_ESITLEME[tur] in _VARSAYILAN_ACIK
