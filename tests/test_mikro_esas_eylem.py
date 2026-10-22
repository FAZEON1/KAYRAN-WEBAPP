# -*- coding: utf-8 -*-
"""Mikro esas — Mikro'dan sonra anlamsız kalan eylemler (kullanıcı kararı, 22.10.2026).

Satış eşitlemesi AÇIKKEN: elle sipariş / yeni kanal / elle iade düğmeleri gösterilmez, Mikro'dan gelen satış
satırı uygulamada düzeltilmez / silinmez, başlangıçtan sonraki Mikro dışı iade (elle, teknik servis mal kabulü)
iadeler tablosuna yazılmaz. Kapalıyken eski davranış aynen (kod yedek kalır)."""
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


def _durum(monkeypatch, acik, baslangic="2026-07-01"):
    import satis.mikro_esitle as ME
    monkeypatch.setattr(ME, "durum", lambda: {"acik": acik, "baslangic": baslangic})


# ── Hangi satış satırı Mikro kaynaklı ─────────────────────────────────
@pytest.mark.parametrize("acik, satir, beklenen", [
    (True, {"tarih": "2026-10-21", "notlar": "Mikro · Cari kodu: 120.01.003", "siparis_no": "G5F26-2525"}, True),
    (True, {"tarih": "2026-10-21", "notlar": "Mikro sipariş · Cari kodu: 120.01.003"}, True),
    (True, {"tarih": "2026-08-01", "notlar": "", "siparis_no": "G5F26-1999"}, True),     # Excel ile gelmiş fatura
    (True, {"tarih": "2026-06-30", "notlar": "", "siparis_no": "S260630-101010"}, False),  # başlangıçtan önce elle
    (True, {"tarih": "2026-06-30", "notlar": "Mikro · Cari kodu: 1"}, True),
    (True, {"tarih": None, "notlar": "", "siparis_no": ""}, False),                      # tarihi bozuk: temizlenebilir
    (False, {"tarih": "2026-10-21", "notlar": "Mikro · Cari kodu: 1"}, False),            # eşitleme kapalı
])
def test_mikro_kaynakli_mi(monkeypatch, acik, satir, beklenen):
    import satis.database as SD
    _durum(monkeypatch, acik)
    assert SD.mikro_kaynakli_mi(satir) is beklenen


class _Sorgu:
    def __init__(self, cli, tablo):
        self.cli, self.tablo, self.filtre = cli, tablo, None

    def select(self, *_a):
        return self

    def eq(self, kolon, deger):
        self.filtre = (kolon, deger)
        return self

    def update(self, alanlar):
        self.cli.yazilan.append(("update", alanlar))
        return self

    def delete(self):
        self.cli.yazilan.append(("delete", None))
        return self

    def execute(self):
        class _R:
            pass
        r = _R()
        k, v = self.filtre or (None, None)
        r.data = [s for s in self.cli.satirlar if k is None or s.get(k) == v]
        return r


class _Cli:
    def __init__(self, satirlar):
        self.satirlar, self.yazilan = satirlar, []

    def table(self, ad):
        assert ad == "satislar", ad
        return _Sorgu(self, ad)


MIKRO_SATIR = {"id": 5, "tarih": "2026-10-21", "sku": "A", "adet": 2, "siparis_no": "G5F26-2525",
               "notlar": "Mikro · Cari kodu: 120.01.003"}


def test_mikro_kaynakli_satis_duzeltilmez_silinmez(monkeypatch):
    import satis.database as SD
    _durum(monkeypatch, True)
    cli = _Cli([dict(MIKRO_SATIR)])
    monkeypatch.setattr(SD, "_get_client", lambda: cli)
    monkeypatch.setattr(SD, "_atomik_kayit", lambda *a, **k: pytest.fail("Mikro satırı silindi"))
    monkeypatch.setattr(SD, "_atomik_hazir", lambda c: pytest.fail("Mikro satırı güncellendi"))
    assert SD.guncelle_satis(5, {"adet": 1}) is False
    assert SD.sil_satis(5) is False and SD.sil_siparis("G5F26-2525") is False
    ok, mesaj = SD.guncelle_satis(5, {"adet": 1}, ayrinti=True)
    assert not ok and "Mikro" in mesaj
    ok, mesaj = SD.sil_satis(5, ayrinti=True)
    assert not ok and "Mikro" in mesaj
    ok, mesaj = SD.sil_siparis("G5F26-2525", ayrinti=True)
    assert not ok and "Mikro" in mesaj
    assert cli.yazilan == []


def test_eslesme_kapaliyken_ya_da_eski_elle_satir_eski_davranis(monkeypatch):
    """Kapalıyken Mikro notlu satır da düzeltilir; açıkken başlangıçtan önceki elle satır düzeltilir / silinir."""
    import satis.database as SD
    for acik, satir in ((False, dict(MIKRO_SATIR)),
                        (True, dict(MIKRO_SATIR, tarih="2026-06-10", notlar="", siparis_no="S1"))):
        _durum(monkeypatch, acik)
        cli = _Cli([satir])
        monkeypatch.setattr(SD, "_get_client", lambda: cli)
        monkeypatch.setattr(SD, "_atomik_hazir", lambda c: False)
        monkeypatch.setattr(SD, "_atomik_kayit", lambda *a, **k: None)
        monkeypatch.setattr(SD, "_stok_uygula", lambda *a, **k: None)
        monkeypatch.setattr(SD, "_temizle", lambda: None)
        assert SD.guncelle_satis(5, {"birim_satis": 9}) is True
        assert SD.sil_satis(5) is True
        assert [y[0] for y in cli.yazilan] == ["update", "delete"]


# ── İade: Mikro esasken Mikro dışı iade yazılmaz ──────────────────────
def test_elle_iade_mikro_esasken_yazilmaz(monkeypatch):
    import satis.database as SD
    _durum(monkeypatch, True)
    monkeypatch.setattr(SD, "_get_client", lambda: pytest.fail("Mikro esasken elle iade yazıldı"))
    monkeypatch.setattr(SD, "_ekle_iade", lambda *a, **k: pytest.fail("Mikro esasken elle iade yazıldı"))
    ok, mesaj = SD.ekle_iade("2026-10-21", "VATAN", "A", "", 1, iade_net=10, depo="İADE DEPO", kaynak="manuel")
    assert not ok and "Mikro" in mesaj
    assert SD.ekle_iade("2026-10-21", "V", "A", "", 1, stok_isle=False, kimlik=True)[::2] == (False, None)


def test_elle_iade_baslangictan_once_ya_da_kapaliyken_yazilir(monkeypatch):
    import satis.database as SD
    cagri = []
    monkeypatch.setattr(SD, "_ekle_iade", lambda *a: (cagri.append(a[0]) or (True, "ok", 3)))
    _durum(monkeypatch, True)
    assert SD.ekle_iade("2026-06-30", "V", "A", "", 1)[0]
    _durum(monkeypatch, False)
    assert SD.ekle_iade("2026-10-21", "V", "A", "", 1)[0]
    assert cagri == ["2026-06-30", "2026-10-21"]


def test_teknik_servis_iadesi_mikro_esasken_iadelere_yazilmaz_akis_surer(monkeypatch):
    """Mikro iade faturası zaten geliyor: teknik servisin mal kabulde yazdığı iade de yazılsaydı aynı iade iki kez
    sayılırdı. Servis kaydı sürer (ok=True); stok mal_kabul_girisi'nde ayrı işlenir."""
    import satis.database as SD
    from teknikservis import stok as TS
    _durum(monkeypatch, True)
    monkeypatch.setattr(SD, "ekle_iade", lambda *a, **k: pytest.fail("Mikro esasken TS iadesi iadeler'e yazıldı"))
    k = {"arayuz": "iade", "stok_kodu": "SKU9", "firma_bilgisi": "VATAN", "iade_net": "10"}
    ok, mesaj = TS.iade_kaydi_yaz(k, tarih="2026-10-12")
    assert ok and "Mikro" in mesaj and "iade_id" not in k


def test_teknik_servis_iade_fiyati_mikro_esasken_yalniz_servis_kaydina(monkeypatch):
    import satis.database as SD
    import teknikservis.database as T
    from teknikservis import stok as TS
    _durum(monkeypatch, True)
    yazilan = []
    monkeypatch.setattr(T, "kayit_guncelle", lambda kid, al: (yazilan.append((kid, al)) or True))
    monkeypatch.setattr(SD, "iade_tutar_guncelle", lambda *a: pytest.fail("Mikro esasken iade tutarı değişti"))
    monkeypatch.setattr(SD, "manuel_iade_bul", lambda *a: pytest.fail("Mikro esasken manuel iade arandı"))
    ok, mesaj, al = TS.iade_fiyat_guncelle({"id": 5, "iade_id": 9, "mal_kabul_tarihi": "2026-10-12T10:00"}, 75, "USD")
    assert ok and al["iade_net"] == 75.0 and yazilan == [(5, al)] and "Mikro" in mesaj


# ── Ekran: açıkken düğmeler yok, kapalıyken yedek dal ─────────────────
def test_satis_girisi_ve_iade_dugmeleri_mikro_acikken_yok():
    m = _oku("satis/main.py")
    sg = m.split("def _sayfa_satis_girisi(", 1)[1].split("\ndef ", 1)[0]
    assert "_mikro = _mikro_acik()" in sg and "eylemler=[] if _mikro else" in sg
    assert "SG_MIKRO_ACIKLAMA if _mikro" in sg
    assert 'SG_MIKRO_ACIKLAMA = "Satış ve siparişler Mikro\'dan gelir (15 dakikada bir)."' in m
    iade = m.split("def _sayfa_iade(", 1)[1].split("\ndef ", 1)[0]
    assert "eylemler=[] if _mikro else" in iade and "st.caption(IADE_MIKRO_NOTU)" in iade
    dlg = iade.split("def _dlg_manuel_iade():", 1)[1]
    assert dlg.index("_mem(str(_i_tarih)[:10])") < dlg.index('"İadeyi Kaydet"')


def test_siparis_penceresi_mikro_siparisinde_duzelt_sil_yok():
    s = _oku("satis/satislar_ekran.py")
    d = s.split("def siparis_dialog(", 1)[1].split("\ndef ", 1)[0]
    assert "mikro = any(mikro_kaynakli_mi(s, es) for s in kalemler)" in d
    assert d.index("if mikro:") < d.index("st.data_editor(") < d.index("guncelle_satis(")
    h = s.split("def _hayalet_dialog(", 1)[1]
    assert "silinebilir = [r.get(\"id\") for r in rows if not mikro_kaynakli_mi(r, es)]" in h


def test_ilk_onay_kutusu_acikken_yalniz_kaynak_notu(monkeypatch):
    import sys
    import types
    import satis.mikro_esitle_ekran as E
    yazilan = []
    sahte = types.SimpleNamespace(caption=lambda m: yazilan.append(m),
                                  expander=lambda *a, **k: pytest.fail("açıkken onay kutusu çıktı"))
    monkeypatch.setattr(E, "st", sahte)
    monkeypatch.setattr(E.M, "durum", lambda: {"acik": True, "baslangic": "2026-07-01"})
    monkeypatch.setitem(sys.modules, "shared.kar_gizle", types.SimpleNamespace(kar_gorunur=lambda: False))
    E.ilk_onay_kutusu()
    assert yazilan == ["Satışlar, iadeler ve siparişler Mikro'dan gelir (15 dakikada bir) · 01.07.2026 sonrası."]
