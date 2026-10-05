# -*- coding: utf-8 -*-
"""st.dataframe yaması her çalışmada GÜNCEL kodla kurulur (Ekim 2026).

Canlıda stok kartı · Satışlar'daki "Kanal / Firma Kırılımı" tablosu görünmüyordu: yama Streamlit'in
sınıfına yazılıp süreç boyunca kalıyor, app.py "zaten yamalı" deyip yenisini kurmuyordu. Kod
güncellense de canlı süreç ilk açılıştaki ESKİ yamayı (tabloyu pencere yerine arkadaki sayfaya
çizen) kullanmaya devam ediyordu.
"""
import pandas as pd
import pytest

from shared import dataframe_yamasi as Y


class _DG:
    def dataframe(self, data=None, *a, **kw):
        _DG.asil_cagri += 1
        return "asil"


def _taze():
    _DG.asil_cagri = 0
    _DG.dataframe = _DG.__dict__.get("_ilk", _DG.dataframe)
    _DG._ilk = _DG.dataframe
    kok = _DG()

    class _St:
        dataframe = _DG.dataframe.__get__(kok, _DG)
    return kok, _St


def _eski_yama(orij):
    """Ekim 2026 öncesi app.py'nin kurduğu yama: asıl fonksiyon modül değişkeninde, tablo kök kaba."""
    ns = {"_ORIJ_DATAFRAME": orij}
    exec("def _akilli(self, data=None, *a, **kw):\n"
         "    return ('eski', _ORIJ_DATAFRAME(self, data, *a, **kw))\n", ns)
    ns["_akilli"]._kayran_yamali = True
    return ns["_akilli"]


@pytest.fixture
def cizilen(monkeypatch):
    import shared.tasarim as T
    kayit = []
    monkeypatch.setattr(T, "tablo_sirali", lambda satirlar, kap=None, **k: kayit.append(kap))
    return kayit


def test_eski_yama_bellekte_kalsa_da_guncel_yama_kurulur(cizilen):
    kok, st = _taze()
    _DG.dataframe = _eski_yama(_DG._ilk)              # canlı süreçte kalmış eski yama
    st.dataframe = _DG.dataframe.__get__(kok, _DG)
    assert Y.kur(st, _DG)
    assert getattr(_DG.dataframe, "_kayran_orij") is _DG._ilk
    sonuc = _DG().dataframe(object())                  # ortak tabloya uymayan veri → asıl fonksiyon
    assert sonuc == "asil" and _DG.asil_cagri == 1     # eski yama aradan çıktı, özyineleme yok


def test_her_calismada_yeniden_kurulur_katman_birikmez(cizilen):
    kok, st = _taze()
    for _ in range(5):                                 # app.py her etkileşimde baştan çalışır
        assert Y.kur(st, _DG)
    assert Y.asil_fonksiyon(_DG.dataframe) is _DG._ilk
    _DG().dataframe(object())
    assert _DG.asil_cagri == 1


def test_kok_kaptaki_tablo_bulundugu_yere_cizilir(cizilen):
    """Modül düzeyi st.dataframe (kök kap) → kap=None: pencere içindeyse pencereye çizilir."""
    kok, st = _taze()
    Y.kur(st, _DG)
    df = pd.DataFrame({"Kanal/Firma": ["VATAN"], "Adet": [3]})
    st.dataframe(df)
    kolon = _DG()
    kolon.dataframe(df)
    assert cizilen == [None, kolon]


def test_asil_bulunamazsa_kurulmaz():
    class _Bozuk:
        def dataframe(self):
            pass
    _Bozuk.dataframe._kayran_yamali = True
    assert Y.kur(type("S", (), {"dataframe": None}), _Bozuk) is False


def test_app_yamayi_her_calismada_kurar():
    from pathlib import Path
    a = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
    assert "_dataframe_yamasi_kur()" in a and "raise RuntimeError(\"zaten yamalı\")" not in a
