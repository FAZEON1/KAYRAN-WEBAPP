# -*- coding: utf-8 -*-
"""Tarayıcı taraması (tests/tarayici, Ekim 2026): her sayfa gerçek tarayıcıda bilgisayar + telefon boyutunda
açılır; CI'da "Testler" iş akışının bir işi (Serkan'ın otomatik birleştirmesi de bu taramayı bekler).
Burada taramanın saf kısmı ve iş akışı tanımı denetlenir; taramanın kendisi CI'da çalışır."""
import importlib.util
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
TARA = KOK / "tests" / "tarayici" / "tara.py"


def _tara():
    assert TARA.exists(), "tests/tarayici/tara.py yok"
    spec = importlib.util.spec_from_file_location("tarayici_tara", TARA)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_sayfa_listesi_menudeki_her_sayfa_ve_sistem():
    T = _tara()
    from shared.gezinme import MODULLER, SISTEM
    s = T.sayfa_listesi()
    adlar = [x[3] for x in s]
    assert len(adlar) == len(set(adlar)) and adlar[0] == "anasayfa"
    beklenen = sum(len(m.get("sayfalar") or [None]) for m in MODULLER if m["kod"] != "anasayfa") + len(SISTEM) + 1
    assert len(s) == beklenen
    assert ("depo", "depo_sayfa", "🚚 Depolar Arası Sevk", "depo/sevk") in s
    assert ("sistem_kayitlari", None, None, "sistem/sistem_kayitlari") in s


def test_adres_kodlanir():
    T = _tara()
    assert T.adres("http://localhost:8601/", "satis", "satis_sayfa", "↩️ İade") == \
        "http://localhost:8601/?mod=satis&anahtar=satis_sayfa&sec=%E2%86%A9%EF%B8%8F%20%C4%B0ade"
    assert T.adres("http://x", "anasayfa", None, None) == "http://x/?mod=anasayfa"


def test_sorunlar_gurultu_ve_izin_duser():
    T = _tara()
    ham = {"hata": [], "ust": [], "tasma": False, "kaymiyor": [300], "zaman": False,
           "konsol": ["Failed to load resource: 404", "GET /favicon.ico", "JS: TypeError: x is null"]}
    assert T.sorunlari_ayikla("a/b", "pc", ham, izinli={}) == {"kaymiyor": [300], "konsol": ["JS: TypeError: x is null"]}
    assert T.sorunlari_ayikla("a/b", "pc", ham, izinli={("a/b", "pc", "kaymiyor"): "gerekçe"}) == \
        {"konsol": ["JS: TypeError: x is null"]}
    assert T.sorunlari_ayikla("a/b", "tel", {"konsol": ["net::ERR_FAILED"]}, izinli={}) == {}
    assert T.sorunlari_ayikla("a/b", "pc", {"konsol": ["Client Error: Download Button fetch error - Failed"]},
                              izinli={}) == {}
    assert T.IZINLI == {}, "izin listesi boş tutulur; eklenecekse gerekçesiyle ve kullanıcıya söyleyerek"


def test_rapor_okunur():
    T = _tara()
    r = T.rapor([("a", "pc", {}), ("b/c", "tel", {"tasma": True})])
    assert r.splitlines() == ["2 sayfa açıldı, 1 sorunlu.", "  b/c [tel]: tasma: True"]


def test_vitrin_ornek_veri_ve_giris():
    p = KOK / "tests" / "tarayici" / "vitrin.py"
    assert p.exists(), "tests/tarayici/vitrin.py yok"
    v = p.read_text(encoding="utf-8")
    assert "sahte_db.kur()" in v and "ornek_veri.doldur(" in v and 'st.session_state["giris_yapildi"] = True' in v
    assert 'runpy.run_path(os.path.join(KOK, "app.py")' in v


def test_is_akisinda_tarayici_isi():
    y = (KOK / ".github" / "workflows" / "testler.yml").read_text(encoding="utf-8")
    assert "name: Testler" in y and "  tarayici:\n    name: Tarayıcı taraması" in y
    is_ = y.split("  tarayici:\n", 1)[1]
    assert "python -m playwright install --with-deps chromium" in is_
    assert "streamlit run tests/tarayici/vitrin.py --server.port 8601" in is_
    assert "python tests/tarayici/tara.py --cihaz pc tel" in is_
    assert "actions/upload-artifact@v4" in is_ and "if: always()" in is_
    # sahte bağlantı bilgisi yalnız CI makinesine yazılır; gerçek anahtar yok
    assert 'key = "sahte"' in is_ and "secrets." not in is_.replace(".streamlit/secrets.toml", "")
    b = (KOK / ".github" / "workflows" / "bt-birlestir.yml").read_text(encoding="utf-8")
    assert 'workflows: ["Testler"]' in b        # otomatik birleştirme tüm Testler işlerini (tarama dahil) bekler
