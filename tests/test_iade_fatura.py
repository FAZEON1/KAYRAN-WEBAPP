# -*- coding: utf-8 -*-
"""İade: Mikro FATURA BAZLI iade dökümü de yüklenir (Ekim 2026).

Muhasebe iadeleri "İADE RAPORU 24 TEMMUZ-30 EYLÜL" şablonunda verdi: her fatura için başlık satırı,
kalemler, Toplam satırı. Bu dosya kapıda "ödeme listesi (olası)" sanılıyordu, iade okuyucusu da
"'Stok kodu' veya 'İade miktar' kolonu bulunamadı" diyordu. Şimdi tanınır; kalemler SKU + cari + depo
bazında toplanır, dönem dışı faturalar (önceki partide zaten olan günler) alınmaz, depo dosyadan gelir.
"""
from datetime import date
from io import BytesIO

from kapi_ornekleri import SKULAR, iade_fatura
from shared.dosya_tani import tani


def _dosya():
    ad, veri = iade_fatura()
    b = BytesIO(veri)
    b.name = ad
    return ad, veri, b


def test_fatura_bazli_iade_dokumu_iade_olarak_taninir():
    ad, veri, _ = _dosya()
    t = tani(ad, veri)
    assert [x["tur"] for x in t] == ["iade_excel"] and t[0]["guven"] == "kesin"


def test_kalemler_okunur_baslik_toplam_ve_dipnot_atlanir():
    from satis.main import iade_fatura_satirlari
    kalemler, hata, atlanan = iade_fatura_satirlari(_dosya()[2])
    assert hata == "" and atlanan == []
    assert [(k["fatura_no"], k["sku"], k["iade_adet"], k["iade_net"], k["depo"]) for k in kalemler] == [
        ("ITF-1", "Faze2", 23, 80.5, "MERKEZ DEPO"),
        ("VTN-2", SKULAR[0], 2, 240.0, "İADE DEPO"), ("VTN-2", SKULAR[1], 1, 250.0, "İADE DEPO"),
        ("VTN-3", SKULAR[0], 1, 120.0, "İADE DEPO")]
    assert kalemler[1]["kanal"] == "120.01.003 VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI"
    assert kalemler[0]["tarih"] == date(2026, 7, 24)


def test_donem_disi_faturalar_alinmaz_ayni_sku_cari_depo_toplanir():
    from satis.main import iade_fatura_ozetle, iade_fatura_satirlari
    kalemler = iade_fatura_satirlari(_dosya()[2])[0]
    satir, disari = iade_fatura_ozetle(kalemler, date(2026, 7, 25), date(2026, 9, 30))
    assert [x["fatura_no"] for x in disari] == ["ITF-1"]                     # 24.07 önceki partide
    assert sorted((x["sku"], x["iade_adet"], x["iade_net"], x["depo"]) for x in satir) == sorted([
        (SKULAR[0], 3, 360.0, "İADE DEPO"), (SKULAR[1], 1, 250.0, "İADE DEPO")])


def test_usd_olmayan_ve_iade_olmayan_kalem_alinmaz():
    import pandas as pd
    from satis.main import iade_fatura_satirlari
    ad, veri = iade_fatura()
    df = pd.read_excel(BytesIO(veri))
    df.loc[df["Fatura no"].eq("VTN-3") & df["Stok DVZ"].notna(), "Stok DVZ"] = "TL"
    df.loc[df["Fatura no"].eq("ITF-1"), "İ N"] = "Normal"
    b = BytesIO()
    df.to_excel(b, index=False)
    b.seek(0)
    kalemler, _, atlanan = iade_fatura_satirlari(b)
    assert [k["fatura_no"] for k in kalemler] == ["VTN-2", "VTN-2"]
    assert len(atlanan) == 2 and any("TL" in a for a in atlanan) and any("iade değil" in a for a in atlanan)


def test_ozet_rapor_bu_okuyucuya_takilmaz():
    from kapi_ornekleri import iade
    from satis.main import iade_fatura_satirlari
    b = BytesIO(iade()[1])
    assert iade_fatura_satirlari(b)[0] is None


def test_kayit_plani_satirin_deposunu_korur():
    """Plan, manuel eşleşmesi olmayan satırın deposunu siliyordu: hepsi tek seçilen depoya giriyordu."""
    from satis.database import iade_fark_plani
    plan, _ = iade_fark_plani([{"sku": "A", "kanal": "X", "iade_adet": 3, "iade_net": 30, "depo": "İADE DEPO"},
                               {"sku": "B", "kanal": "X", "iade_adet": 1, "iade_net": 10}], {})
    assert [p["depo"] for p in plan] == ["İADE DEPO", None]
    plan, _ = iade_fark_plani([{"sku": "A", "kanal": "X", "iade_adet": 3, "depo": "İADE DEPO"}],
                              {("A", "X"): {"adet": 1, "depo": "TEKNİK DEPO"}})
    assert plan[0]["depo"] == "TEKNİK DEPO" and plan[0]["iade_adet"] == 2         # manuel eşleşme önce
