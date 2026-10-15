# -*- coding: utf-8 -*-
"""Mikro → KAYRAN aktarıcı (araclar/mikro_aktarici, Ekim 2026).

Kullanıcı kararı: sunucu 10.0.1.11'de çalışır, 15 dakikada bir artımlı, gecede bir tam aktarım, Python 3.11+.
Aktarıcı Mikro'ya hiçbir şey yazmaz: yalnız SqlVeriOkuV2 (SELECT) kullanır."""
import importlib.util
import re
import sys
import types
from pathlib import Path

import pytest

KLASOR = Path(__file__).resolve().parent.parent / "araclar" / "mikro_aktarici"


@pytest.fixture()
def mk(monkeypatch, tmp_path):
    if importlib.util.find_spec("requests") is None:   # CI'da requests kurulu olmayabilir: modül yalnız içe aktarılır
        sahte = types.ModuleType("requests")
        sahte.Session = object
        sahte.RequestException = Exception
        sahte.Response = object
        monkeypatch.setitem(sys.modules, "requests", sahte)
    spec = importlib.util.spec_from_file_location("mikro_kayran_test", KLASOR / "mikro_kayran.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "KILIT", str(tmp_path / "aktarim.kilit"), raising=False)
    return m


def test_mikroya_yalniz_okuma(mk):
    """Bütün sorgular SELECT; yazan bir Mikro uç noktası (Kaydet / Sil / Guncelle) çağrılmaz."""
    for ad, t in mk.SORGULAR.items():
        sql = " ".join(t["sql"].split()).upper()
        assert sql.startswith("SELECT "), ad
        assert not re.search(r"\b(UPDATE|DELETE|INSERT|MERGE|DROP|ALTER|EXEC|TRUNCATE)\b", sql), ad
    kod = (KLASOR / "mikro_kayran.py").read_text(encoding="utf-8")
    assert mk.MikroIstemci.SQL_ENDPOINT.endswith("/SqlVeriOkuV2")
    assert not re.search(r"(Kaydet|Sil|Guncelle|Duzelt)V\d", kod)


def test_zamanlama_kullanici_karari(mk):
    assert getattr(mk, "ARALIK_SN", 120) == 900                        # 15 dakika (eskiden 120 sn)
    gorev = (KLASOR / "gorev_kur.bat").read_text(encoding="ascii")
    assert "/SC MINUTE /MO 15" in gorev
    assert '/SC DAILY /ST 03:00' in gorev and 'zamanli.bat\\" tam"' in gorev
    z = (KLASOR / "zamanli.bat").read_text(encoding="ascii")
    assert "--tam --bir-kez" in z and "mikro_kayran.py --bir-kez" in z and "pause" not in z
    assert "localhost:8094" in (KLASOR / "ayarlar_ornek.bat").read_text(encoding="ascii")   # sunucuda çalışır


def test_python_surum_ve_saat_dilimi(mk):
    kod = (KLASOR / "mikro_kayran.py").read_text(encoding="utf-8")
    assert "if sys.version_info < (3, 11):" in kod
    # Windows'ta tzdata yoksa ZoneInfo çöker: sabit +03:00'e düşer
    assert mk.TZ.utcoffset(mk.datetime(2026, 7, 1)).total_seconds() == 3 * 3600
    assert mk.TZ.utcoffset(mk.datetime(2026, 1, 1)).total_seconds() == 3 * 3600


def test_kilit_ust_uste_binmez(mk):
    assert hasattr(mk, "kilit_al"), "kilit yok: 15 dakikalık tur ile gecelik tam aktarım üst üste biner"
    assert mk.kilit_al() is True
    assert mk.kilit_al() is False             # 15 dakikalık tur, gecelik tam aktarım sürerken atlanır
    mk.kilit_birak()
    assert mk.kilit_al() is True
    mk.kilit_birak()


def test_bos_ayar_ve_yer_tutucu(mk):
    assert hasattr(mk, "_bos_mu"), "yer tutucu (<...>) dolu sayılıyordu"
    assert mk._bos_mu("") and mk._bos_mu(None) and mk._bos_mu("<Mikro ApiKey>")
    assert not mk._bos_mu("abc123")
    a = dict(mk.AYARLAR, api_key="<Mikro ApiKey>", firma_kodu="G5F", kullanici="api", sifre="x")
    with pytest.raises(mk.MikroHata, match="api_key"):
        mk.MikroIstemci(a)


def test_gizli_ayar_depoda_yok():
    gi = (KLASOR.parent.parent / ".gitignore").read_text(encoding="utf-8")
    assert "araclar/mikro_aktarici/ayarlar.bat" in gi
    ornek = (KLASOR / "ayarlar_ornek.bat").read_text(encoding="ascii")
    for satir in re.findall(r'^set "(\w+)=(.*)"', ornek, re.M):
        ad, deger = satir
        if ad in ("MIKRO_API_KEY", "MIKRO_KULLANICI", "MIKRO_SIFRE", "SUPABASE_SERVICE_KEY", "MIKRO_FIRMA_KODU"):
            assert deger.startswith("<") and deger.endswith(">"), ad
    assert not (KLASOR / "ayarlar.bat").exists()
