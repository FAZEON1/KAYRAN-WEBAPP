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


# ── Kendini güncelleme + keşif (Ekim 2026, kullanıcı: "sunucuya bir daha dosya taşımayayım";
#    "olabilecek tüm veriler Mikro'dan" → adım 0: Mikro'da hangi veri var) ──
class _Yanit:
    def __init__(self, veri):
        self._v = veri
        self.ok, self.status_code, self.text = True, 200, ""

    def json(self):
        return self._v


class _SahteSb:
    def __init__(self, surum=None, kesif_zaman=None):
        self.rest, self.yazilan = "x", []
        self._surum, self._kz = surum, kesif_zaman
        sb = self

        class _O:
            def get(self, url, params=None, timeout=None):
                if url.endswith("mikro_aktarici_surum"):
                    return _Yanit([sb._surum] if sb._surum else [])
                return _Yanit([{"zaman": sb._kz}] if sb._kz else [])
        self.oturum = _O()

    def _kontrol(self, r):
        return r

    def upsert(self, tablo, satirlar, anahtar):
        self.yazilan.append((tablo, satirlar))


def _surum(kod):
    import hashlib
    return {"kod": kod, "sha256": hashlib.sha256(kod.encode("utf-8")).hexdigest()}


def test_kendini_gunceller_ve_bozugu_reddeder(mk, tmp_path):
    yol = tmp_path / "mikro_kayran.py"
    yol.write_text("eski", encoding="utf-8")
    yeni = (KLASOR / "mikro_kayran.py").read_text(encoding="utf-8") + "\n# yeni\n"
    assert mk.kendini_guncelle(_SahteSb(_surum(yeni)), str(yol)) is True
    assert yol.read_text(encoding="utf-8") == yeni and (tmp_path / "mikro_kayran.py.yedek").exists()
    assert mk.kendini_guncelle(_SahteSb(_surum(yeni)), str(yol)) is False          # aynı sürüm: dokunmaz
    bozuk = yeni + "\ndef ( :\n"
    assert mk.kendini_guncelle(_SahteSb(_surum(bozuk)), str(yol)) is False         # derlenmiyor
    yazan = yeni + "\nX = 'StokKaydet" + "V2'\n"
    assert mk.kendini_guncelle(_SahteSb(_surum(yazan)), str(yol)) is False         # Mikro'ya yazan uç
    sahte_ozet = dict(_surum(yeni + "#2"), sha256="0" * 64)
    assert mk.kendini_guncelle(_SahteSb(sahte_ozet), str(yol)) is False            # özet tutmuyor
    assert yol.read_text(encoding="utf-8") == yeni
    assert mk.guncelleme_uygun_mu((KLASOR / "mikro_kayran.py").read_text(encoding="utf-8")) == ""


def test_kesif_yalniz_okur_ve_hatayi_ayri_yazar(mk):
    for ad, sql in mk.KESIF_SORGULARI.items():
        s = " ".join(sql.split()).upper()
        assert s.startswith("SELECT "), ad
        assert not re.search(r"\b(UPDATE|DELETE|INSERT|MERGE|DROP|ALTER|EXEC|TRUNCATE)\b", s), ad

    class _Ist:
        def sql_oku(self, sql):
            if "sys.tables" in sql:
                return [{"tablo": "STOKLAR", "satir": 519}, {"tablo": "BOS", "satir": 0}]
            if "KASALAR" in sql:
                raise mk.MikroHata("Invalid object name 'KASALAR'")
            if "INFORMATION_SCHEMA" in sql:
                assert "'STOKLAR'" in sql and "'BOS'" not in sql          # yalnız dolu tablolar
                return [{"tablo": "STOKLAR", "kolon": "sto_kod", "tip": "nvarchar", "sira": 1}]
            return [{"a": 1}]
    sb = _SahteSb()
    sonuc = mk.kesif_yap(_Ist(), sb)
    assert sonuc["kasalar"] and not sonuc["depolar"] and not sonuc["kolonlar"]
    yazilan = {s[0]["anahtar"]: s[0] for t, s in sb.yazilan}
    assert yazilan["kasalar"]["hata"] and yazilan["kasalar"]["veri"] is None
    assert yazilan["kolonlar"]["veri"][0]["kolon"] == "sto_kod"
    assert mk.kesif_gerekli_mi(_SahteSb(kesif_zaman="2000-01-01T00:00:00+03:00")) is True
    assert mk.kesif_gerekli_mi(_SahteSb(kesif_zaman="2999-01-01T00:00:00+03:00")) is False
