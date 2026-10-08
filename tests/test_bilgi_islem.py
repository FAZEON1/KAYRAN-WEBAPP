# -*- coding: utf-8 -*-
"""Bilgi işlem elemanı (Ekim 2026): ölçüm, rapor, otomatik birleştirme kapısı.

Kullanıcı kararı: gece çalışan eleman küçük düzeltmeleri kendisi birleştirsin. Karar elemana
bırakılmaz; GitHub'daki kapı (shared/bt_hesap.kapi_karari) kuralları denetler.
"""
import os
import sys
from pathlib import Path

import pytest

from shared import bt_hesap as H

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "otonom"))


def _o(modul, sayfa, ms, hata=False, zaman="2026-10-07T10:00:00+00:00"):
    return {"modul": modul, "sayfa": sayfa, "ms": ms, "hata": hata, "zaman": zaman}


# ── Hesaplar ────────────────────────────────────────────────────────
def test_sure_ozeti_ortanca_ve_p90():
    oz = H.sure_ozeti([_o("satis", "satislar", m) for m in (100, 200, 300, 400, 5000)]
                      + [_o("satis", "satislar", 250, hata=True)])
    assert oz[("satis", "satislar")] == {"adet": 6, "p50": 300, "p90": 5000, "hata": 1}


def test_karsilastir_yavaslayan_once_az_olcum_atlanir():
    once = {("a", ""): {"adet": 10, "p50": 1000, "p90": 1, "hata": 0},
            ("b", ""): {"adet": 10, "p50": 1000, "p90": 1, "hata": 0},
            ("c", ""): {"adet": 2, "p50": 1000, "p90": 1, "hata": 0}}
    sonra = {("a", ""): {"adet": 10, "p50": 1500, "p90": 1, "hata": 0},
             ("b", ""): {"adet": 10, "p50": 800, "p90": 1, "hata": 0},
             ("c", ""): {"adet": 10, "p50": 9000, "p90": 1, "hata": 0}}
    r = H.karsilastir(once, sonra)
    assert [(x["modul"], x["fark_yuzde"]) for x in r] == [("a", 50.0), ("b", -20.0)]


def test_hata_ozeti_en_sik_once_son_mesaj():
    r = H.hata_ozeti([{"yer": "x", "mesaj": "eski", "zaman": "2026-10-01"},
                      {"yer": "x", "mesaj": "yeni", "zaman": "2026-10-05"},
                      {"yer": "y", "mesaj": "m", "zaman": "2026-10-03"}])
    assert r[0] == {"yer": "x", "adet": 2, "son": "2026-10-05", "mesaj": "yeni"} and r[1]["yer"] == "y"


def test_gunluk_seri_ve_iyilestirme_farki():
    s = H.gunluk_seri([_o("a", "", 100, zaman="2026-10-06T09:00"), _o("a", "", 300, zaman="2026-10-06T10:00"),
                       _o("a", "", 50, zaman="2026-10-07T09:00")], [{"zaman": "2026-10-07T11:00"}])
    assert s == [{"gun": "2026-10-06", "p50": 300, "adet": 2, "hata": 0},
                 {"gun": "2026-10-07", "p50": 50, "adet": 1, "hata": 1}]
    r = H.iyilestirme_satiri({"zaman": "2026-10-07T03:00", "baslik": "B", "once": 3200, "sonra": 1900,
                              "birim": "ms", "durum": "birlesti"})
    assert r["fark_yuzde"] == -40.6 and r["zaman"] == "2026-10-07"


# ── Otomatik birleştirme kapısı ─────────────────────────────────────
KUCUK = [{"filename": "kayranpm/urunler_ekran.py", "additions": 12, "deletions": 4}]


def _kapi(dosyalar=KUCUK, dal="claude/kind-x", etiket=("bt-otomatik",), yesil=True,
          baslik="Bilgi işlem: Ürünler sayfası önbellek"):
    return H.kapi_karari(dosyalar, dal, etiket, yesil, baslik)


def test_kapi_kurala_uyan_kucuk_duzeltmeyi_gecirir():
    assert _kapi() == (True, [])


@pytest.mark.parametrize("kw, parca", [
    ({"etiket": ()}, "etiketi yok"),
    ({"baslik": "Talep #12: x"}, "başlık"),
    ({"dal": "main"}, "dal"),
    ({"yesil": False}, "testler"),
    ({"dosyalar": [{"filename": f"shared/a{i}.py", "additions": 1, "deletions": 0} for i in range(7)]}, "7 dosya"),
    ({"dosyalar": [{"filename": "shared/tablo.py", "additions": 150, "deletions": 60}]}, "210 satır"),
    ({"dosyalar": [{"filename": "satis/database.py", "additions": 2, "deletions": 1}]}, "database.py"),
    ({"dosyalar": [{"filename": "satis/pnl_hesap.py", "additions": 2, "deletions": 1}]}, "korunan"),
    ({"dosyalar": [{"filename": "otonom/bt_kapi.py", "additions": 2, "deletions": 1}]}, "otonom/"),
    ({"dosyalar": [{"filename": ".github/workflows/bt-birlestir.yml", "additions": 2, "deletions": 1}]}, ".github/"),
    ({"dosyalar": [{"filename": "CLAUDE.md", "additions": 1, "deletions": 0}]}, "claude.md"),
    ({"dosyalar": [{"filename": "kayranacc/main.py", "additions": 1, "deletions": 0},
                   {"filename": "veritabani/24_x.sql", "additions": 9, "deletions": 0}]}, "veritabani/"),
    ({"dosyalar": [{"filename": "shared/yetki.py", "additions": 1, "deletions": 0}]}, "yetki"),
])
def test_kapi_engeller(kw, parca):
    ok, sebep = _kapi(**kw)
    assert not ok and any(parca in s for s in sebep), sebep


def test_kapi_testlerin_son_kosusuna_bakar():
    import bt_kapi
    k = [{"name": "pytest", "status": "completed", "conclusion": "failure", "started_at": "2026-10-07T01:00"},
         {"name": "pytest", "status": "completed", "conclusion": "success", "started_at": "2026-10-07T02:00"},
         {"name": "Sayfa testi", "status": "completed", "conclusion": "success", "started_at": "2026-10-07T02:00"}]
    assert bt_kapi.testler_yesil(k)
    assert not bt_kapi.testler_yesil(k[:2])                            # sayfa testi yok
    assert not bt_kapi.testler_yesil(k + [{"name": "Sayfa testi", "status": "in_progress",
                                           "started_at": "2026-10-07T03:00"}])


# ── Veritabanı aracı sınırları ──────────────────────────────────────
def test_bt_db_yalniz_izinli_tablolar(monkeypatch):
    import bt_db
    monkeypatch.setenv("SUPABASE_URL", "http://yok.invalid")
    monkeypatch.setenv("SUPABASE_KEY", "x")
    with pytest.raises(ValueError):
        bt_db._istek("GET", "satislar")
    with pytest.raises(ValueError):
        bt_db._istek("DELETE", "hata_kayitlari", "id=eq.1")


def test_bt_db_rapor_satiri_dogrulanir():
    import bt_db
    r = bt_db.rapor_satiri(["--tur", "iyilestirme", "--baslik", "Bilgi işlem: x", "--once", "3200",
                            "--birim", "ms", "--durum", "acik"])
    assert r == {"tur": "iyilestirme", "baslik": "Bilgi işlem: x", "once": 3200.0, "birim": "ms", "durum": "acik"}
    with pytest.raises(ValueError):
        bt_db.rapor_satiri(["--tur", "sil", "--baslik", "x"])
    with pytest.raises(ValueError):
        bt_db.rapor_satiri(["--tur", "oneri", "--baslik", "x", "--durum", "birlestir"])
    assert bt_db._konumsal(["satis", "--gun", "7", "satislar"]) == ["satis", "satislar"]


# ── Ölçüm ──────────────────────────────────────────────────────────
def test_alt_sayfa_kodu_ve_kayit_hata_firlatmaz(monkeypatch):
    from shared import bt_olcum
    from shared.gezinme import MODULLER
    m = next(m for m in MODULLER if m.get("anahtar") and m.get("sayfalar"))
    sec, kod = m["sayfalar"][0][0], m["sayfalar"][0][1]
    assert bt_olcum.alt_sayfa(m["kod"], {m["anahtar"]: sec}) == kod
    assert bt_olcum.alt_sayfa("anasayfa", {}) == ""
    import shared.auth as A
    monkeypatch.setattr(A, "_get_supabase", lambda: (_ for _ in ()).throw(RuntimeError("bağlantı yok")))
    bt_olcum.kaydet("satis", "x", 123.4)                     # istisna fırlatmaz


def test_baglantilar_yerinde():
    app = (KOK / "app.py").read_text(encoding="utf-8")
    assert "_bto.kaydet(aktif, _bto.alt_sayfa(aktif, st.session_state)" in app
    # Serkan Ekip modülünde (üst şerit, yalnız yöneticiler); eski bilgi_islem adresi oraya yönlenir
    assert 'elif aktif == "ekip":' in app and 'if aktif == "bilgi_islem":' in app
    from shared.gezinme import MODULLER
    ekip = next(m for m in MODULLER if m["kod"] == "ekip")
    assert ekip["ozel"] == "kullanici_yonetimi" and "Serkan" in [s[0] for s in ekip["sayfalar"]]
    yml = (KOK / ".github/workflows/bt-birlestir.yml").read_text(encoding="utf-8")
    assert "ref: main" in yml and "python otonom/bt_kapi.py" in yml
    gorev = (KOK / "otonom/bt_gorevi.md").read_text(encoding="utf-8")
    assert f"`{H.BASLIK_ONEKI} <kısa konu>`" in gorev and f"`{H.ETIKET}`" in gorev
    assert "bilgi işlem elemanı" in (KOK / "CLAUDE.md").read_text(encoding="utf-8")
    assert os.path.exists(KOK / "veritabani/23_bilgi_islem.sql")


@pytest.mark.parametrize("betik", ["otonom/bt_db.py", "otonom/bt_kapi.py"])
def test_betikler_streamlitsiz_yuklenir(betik):
    """Gece görevi ve GitHub kapısı Streamlit'siz ortamda çalışır; `shared` paketi içe aktarılınca
    Streamlit yüklendiği için betikler bt_hesap'ı dosyadan yüklemeli (ilk kurulumda bu yüzden açılmıyordu)."""
    import subprocess
    kod = ("import sys, importlib.util as u; sys.modules['streamlit'] = None; "
           f"s = u.spec_from_file_location('b', {str(KOK / betik)!r}); m = u.module_from_spec(s); "
           "s.loader.exec_module(m); print('TAMAM')")
    r = subprocess.run([sys.executable, "-c", kod], capture_output=True, text=True, timeout=60)
    assert r.stdout.strip() == "TAMAM", r.stderr[-800:]



# ── Serkan: öğrenme ve haftalık karne ──────────────────────────────
def test_karne_son_otuz_gunu_sayar():
    from datetime import datetime, timezone
    simdi = datetime(2026, 10, 30, tzinfo=timezone.utc)
    r = [{"zaman": "2026-10-20", "tur": "iyilestirme", "durum": "otomatik_birlesti", "once": 1000, "sonra": 700},
         {"zaman": "2026-10-21", "tur": "iyilestirme", "durum": "reddedildi"},
         {"zaman": "2026-10-22", "tur": "iyilestirme", "durum": "birlesti", "once": 10, "sonra": 12},
         {"zaman": "2026-10-23", "tur": "ogrenme"}, {"zaman": "2026-10-24", "tur": "oneri"},
         {"zaman": "2026-08-01", "tur": "iyilestirme", "durum": "birlesti", "once": 1, "sonra": 9}]
    k = H.karne(r, 30, simdi)
    assert k["iyilestirme"] == 3 and k["durum"] == {"otomatik_birlesti": 1, "reddedildi": 1, "birlesti": 1}
    assert k["olculen"] == 2 and k["ortalama_fark_yuzde"] == -5.0 and k["kotulesen"] == 1
    assert (k["ogrenme"], k["oneri"]) == (1, 1)


def test_ogrenme_ve_gelisim_kaydi_yazilabilir():
    import bt_db
    assert {"ogrenme", "gelisim"} <= bt_db.TURLER
    assert bt_db.rapor_satiri(["--tur", "ogrenme", "--baslik", "Hafta sonu ölçümü az"])["tur"] == "ogrenme"


def test_serkan_talimati_kendini_gelistirme_sinirlari():
    g = (KOK / "otonom/bt_gorevi.md").read_text(encoding="utf-8")
    assert "Sen **Serkan**'sın" in g and "## 7. Öğren" in g and "## 8. Haftalık karne" in g
    assert "`ogrendiklerim`" in g and "Bilgi işlem: Serkan kendini geliştiriyor" in g
    assert "Bu PR'a `bt-otomatik` etiketi EKLEME" in g
    # Kendi PR'ı otonom/ altında: kapı onu asla otomatik birleştirmez
    ok, sebep = H.kapi_karari([{"filename": "otonom/bt_gorevi.md", "additions": 5, "deletions": 1}],
                              "claude/x", ["bt-otomatik"], True, "Bilgi işlem: Serkan kendini geliştiriyor — x")
    assert not ok and any("otonom/" in s for s in sebep)
