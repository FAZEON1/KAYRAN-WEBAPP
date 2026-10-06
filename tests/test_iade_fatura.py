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


def test_donem_disi_faturalar_alinmaz_her_iade_kendi_fatura_tarihinde():
    """İadeler dönem sonuna (30.09) yığılınca İade sayfasının ay filtresi Ağustos'u boş, Eylül'ü dolu
    gösteriyordu; aylık P&L de aynı. Satırlar fatura tarihine göre ayrı kalır."""
    from satis.main import iade_fatura_ozetle, iade_fatura_satirlari
    kalemler = iade_fatura_satirlari(_dosya()[2])[0]
    satir, disari = iade_fatura_ozetle(kalemler, date(2026, 7, 25), date(2026, 9, 30))
    assert [x["fatura_no"] for x in disari] == ["ITF-1"]                     # 24.07 önceki partide
    assert sorted((x["tarih"], x["sku"], x["iade_adet"], x["iade_net"], x["depo"]) for x in satir) == sorted([
        ("2026-08-05", SKULAR[0], 2, 240.0, "İADE DEPO"), ("2026-08-05", SKULAR[1], 1, 250.0, "İADE DEPO"),
        ("2026-09-30", SKULAR[0], 1, 120.0, "İADE DEPO")])


def test_ayni_gun_ayni_sku_cari_depo_toplanir():
    from satis.main import iade_fatura_ozetle
    k = [{"tarih": date(2026, 8, 5), "fatura_no": f"F{i}", "sku": "A", "urun_adi": "", "kanal": "X",
          "iade_adet": 1, "iade_net": 10.0, "depo": "İADE DEPO"} for i in range(3)]
    satir, _ = iade_fatura_ozetle(k)
    assert [(x["tarih"], x["iade_adet"], x["iade_net"]) for x in satir] == [("2026-08-05", 3, 30.0)]


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


def test_manuel_avans_ayni_sku_cari_toplamindan_bir_kez_dusulur():
    """Aynı SKU + cari iki farklı fatura tarihinde: 2 adetlik manuel avans iki satırdan ayrı ayrı
    düşülseydi 4 adet eksik yazılırdı."""
    from satis.database import iade_fark_plani
    satir = [{"tarih": "2026-08-05", "sku": "A", "kanal": "X", "iade_adet": 3, "iade_net": 30},
             {"tarih": "2026-09-10", "sku": "A", "kanal": "X", "iade_adet": 2, "iade_net": 20}]
    plan, uyus = iade_fark_plani(satir, {("A", "X"): {"adet": 2, "depo": None}})
    assert uyus == [] and [(p["tarih"], p["iade_adet"], p["iade_net"]) for p in plan] == [
        ("2026-08-05", 1, 10.0), ("2026-09-10", 2, 20.0)]
    plan, uyus = iade_fark_plani(satir, {("A", "X"): {"adet": 9}})
    assert plan == [] and uyus == [{"sku": "A", "kanal": "X", "manuel": 9, "excel": 5}]


# ── Kayıt: satır tarihi + parti dönem sonuyla tanınır ───────────────
class _DB:
    """iadeler tablosu: select (eq), insert, delete (in_)."""

    def __init__(self, satirlar):
        self.satirlar = [dict(r) for r in satirlar]
        self._suz, self._yaz, self._sil = [], None, None

    def table(self, _ad):
        self._suz, self._yaz, self._sil = [], None, None
        return self

    def select(self, *_):
        return self

    def eq(self, k, v):
        self._suz.append(lambda r: str(r.get(k)) == str(v))
        return self

    def in_(self, k, vs):
        self._suz.append(lambda r: r.get(k) in vs)
        return self

    def insert(self, rows):
        self._yaz = rows
        return self

    def delete(self):
        self._sil = True
        return self

    def execute(self):
        if self._yaz is not None:
            out = []
            for r in self._yaz:
                r = dict(r, id=1000 + len(self.satirlar))
                self.satirlar.append(r)
                out.append(r)
            return type("R", (), {"data": out})()
        sec = [r for r in self.satirlar if all(f(r) for f in self._suz)]
        if self._sil:
            self.satirlar = [r for r in self.satirlar if r not in sec]
            return type("R", (), {"data": []})()
        return type("R", (), {"data": [dict(r) for r in sec]})()


def _ortam(monkeypatch, satirlar):
    import satis.database as sdb
    db, stok = _DB(satirlar), []
    monkeypatch.setattr(sdb, "_get_client", lambda: db)
    monkeypatch.setattr(sdb, "_temizle", lambda: None)
    monkeypatch.setattr(sdb, "_kart_sku_haritasi", lambda: {})
    monkeypatch.setattr(sdb, "_kart_sku", lambda s, h=None: s)
    monkeypatch.setattr(sdb, "_stok_uygula_depolu", lambda m, yon=-1: stok.append((yon, list(m))))
    return sdb, db, stok


ESKI = [  # 24.07 partisi (eski özet: hepsi dönem sonunda) + başka partinin 30.09 faturası + manuel
    {"id": 1, "tarih": "2026-07-24", "sku": "A", "iade_adet": 5, "donem_bas": "2026-07-01",
     "donem_bit": "2026-07-24", "kaynak": "excel"},
    {"id": 2, "tarih": "2026-09-30", "sku": "B", "iade_adet": 1, "donem_bas": "2026-09-01",
     "donem_bit": "2026-10-31", "kaynak": "excel"},
]


def test_satir_fatura_tarihiyle_parti_donem_sonuyla_yazilir(monkeypatch):
    sdb, db, _ = _ortam(monkeypatch, ESKI)
    r = sdb.ice_aktar_iadeler([{"tarih": "2026-08-05", "sku": "A", "kanal": "X", "iade_adet": 2, "depo": "İADE DEPO"},
                               {"sku": "C", "kanal": "X", "iade_adet": 1}], "2026-09-30",
                              donem_bas="2026-07-25")
    assert r["eklendi"] == 2
    yeni = [x for x in db.satirlar if x["id"] >= 1000]
    assert [(x["tarih"], x["donem_bas"], x["donem_bit"], x["depo"]) for x in yeni] == [
        ("2026-08-05", "2026-07-25", "2026-09-30", "İADE DEPO"),
        ("2026-09-30", "2026-07-25", "2026-09-30", "MERKEZ DEPO")]          # tarihsiz satır: dönem sonu


def test_ayni_donem_sonlu_parti_tumuyle_silinir_digerleri_kalir(monkeypatch):
    """Tekrar yüklemede eski parti (farklı fatura tarihlerinde) silinir; aynı gündeki BAŞKA partinin
    satırı kalır. Eskiden yalnız dönem sonu tarihli satırlar silinirdi: Ağustos satırları mükerrer kalırdı."""
    eski = ESKI + [{"id": 3, "tarih": "2026-08-05", "sku": "A", "iade_adet": 2, "donem_bas": "2026-07-25",
                    "donem_bit": "2026-09-30", "kaynak": "excel", "depo": "İADE DEPO"}]
    sdb, db, stok = _ortam(monkeypatch, eski)
    sdb.ice_aktar_iadeler([{"tarih": "2026-08-05", "sku": "A", "kanal": "X", "iade_adet": 2}], "2026-09-30",
                          temizle_once=True, donem_bas="2026-07-25")
    assert sorted(x["id"] for x in db.satirlar) == [1, 2, 1000 + 2]
    assert stok[0] == (-1, [("A", 2, "İADE DEPO")])                          # silinen partinin stoğu geri


def test_partiler_donem_sonuna_gore(monkeypatch):
    eski = ESKI + [{"id": 3, "tarih": "2026-08-05", "sku": "A", "iade_adet": 2, "donem_bas": "2026-07-25",
                    "donem_bit": "2026-09-30", "kaynak": "excel"},
                   {"id": 4, "tarih": "2026-09-12", "sku": "A", "iade_adet": 3, "donem_bas": "2026-07-25",
                    "donem_bit": "2026-09-30", "kaynak": "excel"}]
    sdb, _, _ = _ortam(monkeypatch, eski)
    p = {x["tarih"]: (x["satir"], x["adet"]) for x in sdb.get_iade_partileri()}
    assert p == {"2026-07-24": (1, 5), "2026-10-31": (1, 1), "2026-09-30": (2, 5)}
    assert [x["tarih"] for x in sdb.iade_cakisma_bul("2026-09-01", "2026-09-30")] == ["2026-09-30", "2026-10-31"]
