# -*- coding: utf-8 -*-
"""Hatasız bayat modül (shared/modul_tazele.bayatlari_tazele, Ekim 2026).

Güncelleme birleşti, kod doğruydu ama canlı uygulama bellekteki ESKİ modülle çalışıp eski mesajı
gösteriyordu (stok kartı, PR #118); hata çıkmadığı için eski koruma devreye girmiyordu. Artık her
çalıştırmada proje dosyalarının zamanına bakılır, değişen varsa proje modülleri yeniden yüklenir.
"""
import importlib
import os
import sys
from pathlib import Path

from shared.modul_tazele import bayatlari_tazele, degisen_moduller

KOK = Path(__file__).resolve().parent.parent


def _yaz(yol, metin, zaman):
    yol.write_text(metin, encoding="utf-8")
    os.utime(yol, (zaman, zaman))


def test_degisen_dosya_tum_proje_modullerini_yeniden_yukletir(tmp_path, monkeypatch):
    paket = tmp_path / "bayatpaket"
    paket.mkdir()
    _yaz(paket / "__init__.py", "", 1_000)
    _yaz(paket / "kart.py", 'MESAJ = "eski"\n', 1_000)
    _yaz(paket / "ekran.py", "from bayatpaket.kart import MESAJ\n", 1_000)
    monkeypatch.syspath_prepend(str(tmp_path))
    for ad in [a for a in sys.modules if a.startswith("bayatpaket")]:
        sys.modules.pop(ad)
    ekran = importlib.import_module("bayatpaket.ekran")
    assert ekran.MESAJ == "eski"
    kayit = {}
    assert bayatlari_tazele(sys.modules, str(tmp_path), kayit) == []        # ilk görüş: kayıt
    assert set(kayit) >= {"bayatpaket", "bayatpaket.kart", "bayatpaket.ekran"}
    _yaz(paket / "kart.py", 'MESAJ = "yeni"\n', 2_000)                        # güncelleme geldi
    importlib.invalidate_caches()
    silinen = bayatlari_tazele(sys.modules, str(tmp_path), kayit)
    assert set(silinen) >= {"bayatpaket.kart", "bayatpaket.ekran"}        # içe aktaranlar da gider
    assert importlib.import_module("bayatpaket.ekran").MESAJ == "yeni"
    assert bayatlari_tazele(sys.modules, str(tmp_path), kayit) == []        # değişiklik yoksa dokunmaz


def test_proje_disi_modullere_dokunmaz(tmp_path):
    kayit = {}
    assert degisen_moduller({"os": os, "json": importlib.import_module("json"), "__main__": None},
                            str(tmp_path), kayit) == [] and kayit == {}


def test_app_her_seyden_once_tazeler():
    a = (KOK / "app.py").read_text(encoding="utf-8")
    i = a.index("_bayatlari_tazele(_sys_bt.modules")
    assert i < a.index("from shared.tasarim import renk as trenk")
    assert "_kayran_modul_zaman" in a
    assert a.rindex("_yuklenenleri_kaydet(") > a.rindex("main()")          # çalıştırma sonunda kayıt


def test_yuklendikten_sonra_ilk_kayittan_once_gelen_guncelleme_kacmaz(tmp_path, monkeypatch):
    from shared.modul_tazele import yuklenenleri_kaydet
    paket = tmp_path / "bayatiki"
    paket.mkdir()
    _yaz(paket / "__init__.py", "", 1_000)
    _yaz(paket / "m.py", "X = 1\n", 1_000)
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("bayatiki.m", None)
    sys.modules.pop("bayatiki", None)
    kayit = {}
    bayatlari_tazele(sys.modules, str(tmp_path), kayit)                      # 1. çalıştırma başı
    assert importlib.import_module("bayatiki.m").X == 1                     # çalıştırmada yüklendi
    yuklenenleri_kaydet(sys.modules, str(tmp_path), kayit)                  # 1. çalıştırma sonu
    _yaz(paket / "m.py", "X = 2\n", 2_000)                                   # arada güncelleme
    importlib.invalidate_caches()
    assert "bayatiki.m" in bayatlari_tazele(sys.modules, str(tmp_path), kayit)
    assert importlib.import_module("bayatiki.m").X == 2
