# -*- coding: utf-8 -*-
"""Teknik servis kayıtları ↔ depo stoğu (depo/ts_mutabakat.py, Ekim 2026)."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from depo import ts_mutabakat as T  # noqa: E402

SAT = {"MERKEZ DEPO", "HAPPY LIFE"}
BUGUN = date(2026, 10, 15)


def _k(i, sku, durum, depo="", arayuz="iade", giris="", depo_tarihi=None, kabul="2026-07-01T10:00:00+00:00"):
    return {"id": i, "servis_form_no": f"F{i}", "arayuz": arayuz, "stok_kodu": sku, "stok_adi": f"Ad {sku}",
            "mevcut_durum": durum, "depo": depo, "giris_depo": giris, "depo_tarihi": depo_tarihi,
            "mal_kabul_tarihi": kabul, "personel": "ali"}


def _anahtar(s):
    from shared.utils import sku_anahtar
    return sku_anahtar(s)


def test_konum_kayit_deposu_yoksa_arayuzun_varsayilani():
    assert T.konum(_k(1, "A", "satışa hazır", depo="ikinci el")) == "İKİNCİ EL DEPO"
    assert T.konum(_k(2, "A", "mal kabül", arayuz="iade")) == "İADE DEPO"
    assert T.konum(_k(3, "A", "mal kabül", arayuz="teknik")) == "TEKNİK DEPO"
    assert T.konum(_k(4, "A", "mal kabül", arayuz="iade", giris="merkez")) == "MERKEZ DEPO"
    assert T.konum(_k(5, "A", "satışa hazır", depo="teknik servis", arayuz=None)) == "TEKNİK DEPO"


def test_acik_kayitlar_kapali_durum_atlanir_tarih_depoya_giris():
    acik = T.acik_kayitlar([_k(1, "A", "satıldı", depo="outlet"), _k(2, "A", "gönderildi"),
                            _k(3, "A", "iptal"),
                            _k(4, "A", "satışa hazır", depo="outlet", depo_tarihi="2026-08-06"),
                            _k(5, "B", "teknisyende", arayuz="teknik")], T.konum)
    assert [(k["id"], k["depo"], k["tarih"]) for k in acik] == [(4, "OUTLET DEPO", "2026-08-06"),
                                                                 (5, "TEKNİK DEPO", "2026-07-01")]


def test_karsilastir_ve_ozet():
    acik = T.acik_kayitlar([_k(i, "X24", "satışa hazır", depo="ikinci el") for i in range(5)]
                           + [_k(9, "K1", "teknisyende", arayuz="teknik"),
                              _k(10, "M", "satışa hazır", depo="merkez")], T.konum)
    stok = {("İKİNCİ EL DEPO", "X24"): 2, ("İKİNCİ EL DEPO", "Y"): 3, ("TEKNİK DEPO", "K1"): 1,
            ("OUTLET DEPO", "Z"): 4, ("MERKEZ DEPO", "M"): 50}
    fark = T.karsilastir(acik, stok, _anahtar, SAT)
    assert [(r["depo"], r["sku"], r["kayit"], r["stok"], r["fark"]) for r in fark] == [
        ("İKİNCİ EL DEPO", "X24", 5, 2, -3), ("İKİNCİ EL DEPO", "Y", 0, 3, 3)]   # outlet'te kayıt yok; merkez dışarıda
    oz = {o["depo"]: o for o in T.depo_ozeti(acik, stok, SAT)}
    assert (oz["İKİNCİ EL DEPO"]["kayit"], oz["İKİNCİ EL DEPO"]["stok"], oz["İKİNCİ EL DEPO"]["fark"]) == (5, 5, 0)
    assert set(oz) == {"İKİNCİ EL DEPO", "TEKNİK DEPO"}


def test_uzun_bekleyenler_yalniz_islemdeki_kayitlar():
    acik = T.acik_kayitlar([_k(1, "A", "teknisyende", kabul="2026-07-10"),
                            _k(2, "A", "mal kabül", kabul="2026-10-01"),
                            _k(3, "A", "satışa hazır", depo="outlet", kabul="2026-06-01"),
                            _k(4, "A", "iade alındı", arayuz="teknik", kabul="2026-08-01")], T.konum)
    b = T.uzun_bekleyenler(acik, BUGUN)
    assert [(k["id"], k["gun"]) for k in b] == [(1, 97), (4, 75)]


def test_ts_partileri_iade_ve_satilabilir_haric():
    acik = T.acik_kayitlar([_k(1, "A", "satışa hazır", depo="outlet", depo_tarihi="2026-08-06"),
                            _k(2, "A", "mal kabül", arayuz="iade"),
                            _k(3, "A", "satışa hazır", depo="merkez")], T.konum)
    assert T.ts_partileri(acik, SAT) == [{"depo": "OUTLET DEPO", "sku": "A", "tarih": "2026-08-06", "adet": 1}]


def test_satilamayan_yasi_servis_kaydindan_defterdeki_servis_satiri_cift_sayilmaz():
    """Teknik depoda 3 adet; 2 servis kaydı (Temmuz) + servisin kendi defter satırı (+1, Ekim) → defter
    satırı atlanır, kayıtlar parti olur; kalan 1 adet 'giriş kaydı yok'."""
    from depo import satilamayan as S
    from kayranpm.database import depo_dagilimi, depo_kanonik
    acik = T.acik_kayitlar([_k(1, "K1", "teknisyende", arayuz="teknik", kabul="2026-07-10"),
                            _k(2, "K1", "teknisyende", arayuz="teknik", kabul="2026-07-20")], T.konum)
    pm = S.partiler([], [{"sku": "K1", "depo": "TEKNİK DEPO", "degisim": 1, "tur": "giris",
                          "zaman": "2026-10-02T09:00", "basarili": True, "kaynak": "teknikservis/stok.py:_uygula"}],
                    depo_kanonik, _anahtar, ts_partiler=T.ts_partileri(acik, SAT))
    r, = S.satirlar([{"sku": "K1", "depo_kirilim": {"TEKNİK DEPO": 3}}], pm, BUGUN,
                    kirilim=lambda dk: depo_dagilimi(dk)[0], satilabilir=SAT, anahtar=_anahtar,
                    birim=lambda s: 0, ad=lambda s, y: y or s)
    assert (r["kayitsiz"], r["en_eski_tarih"]) == (1, "2026-07-10")
