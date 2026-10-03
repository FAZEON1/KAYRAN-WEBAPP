# -*- coding: utf-8 -*-
"""Sayfa testi (duman testi) — her modülün her sayfası çökmeden açılıyor mu? (Ekim 2026)

Uygulama gerçek Streamlit'le (streamlit.testing AppTest), bellekteki BOŞ bir sahte veritabanıyla
(tests/duman/sahte_db.py) ve tam yetkili bir kullanıcıyla açılır; shared/gezinme.MODULLER'deki
her sayfa ve hesap sayfaları tek tek çizilir. Yakalanmamış hata YA DA uygulamanın kendi yakalayıp
hata kaydına yazdığı sayfa çökmesi testi kırar — canlıda "cannot import name", ad hatası, imza
uyuşmazlığı, boş veride çökme gibi sorunlar PR aşamasında görünür.

Yalnız gerçek Streamlit kuruluyken çalışır (CI'da ayrı iş: .github/workflows/testler.yml →
"Sayfa testi"). Normal test işinde sahte streamlit olduğu için atlanır.
"""
import os
import sys

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

BURASI = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(os.path.dirname(BURASI))
BETIK = os.path.join(BURASI, "uygulama.py")
SURE = int(os.environ.get("DUMAN_SURE", "60"))
if BURASI not in sys.path:
    sys.path.insert(0, BURASI)
if KOK not in sys.path:
    sys.path.insert(0, KOK)

from shared.gezinme import MODULLER, SISTEM  # noqa: E402


def _sayfalar():
    out = [("anasayfa", None, None), ("arama", None, None)]
    for m in MODULLER:
        if m["kod"] == "anasayfa":
            continue
        if not m.get("sayfalar"):
            out.append((m["kod"], None, None))
            continue
        for secenek, kod, _ad, _kosul in m["sayfalar"]:
            out.append((m["kod"], m["anahtar"], (secenek, kod)))
    for kod, *_ in SISTEM:
        out.append((kod, None, None))
    return out


SAYFALAR = _sayfalar()


def _kimlik(p):
    mod, _, s = p
    return f"{mod}/{s[1]}" if s else mod


def _ac(mod, anahtar, secenek):
    import sahte_db
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = mod
    if anahtar:
        at.session_state[anahtar] = secenek
    at.run()
    return at


@pytest.mark.parametrize("sayfa", SAYFALAR, ids=[_kimlik(p) for p in SAYFALAR])
def test_sayfa_cokmeden_acilir(sayfa):
    mod, anahtar, s = sayfa
    at = _ac(mod, anahtar, s[0] if s else None)
    sorunlar = [f"yakalanmamış: {e.value}" for e in at.exception]
    sorunlar += [h for h in (at.session_state["_duman_hatalar"] if "_duman_hatalar" in at.session_state else [])]
    sorunlar += [f"ekranda: {m.value[:200]}" for m in at.markdown if "Uygulamasında Bir Sorun Oluştu" in str(m.value)]
    assert not sorunlar, "\n".join(sorunlar)
    if s:                                            # gerçekten o sayfa açıldı mı (menü seçimi tuttu mu)
        assert at.session_state[anahtar] == s[0]
    assert at.session_state["aktif_uygulama"] == mod, "yetki reddi ya da yönlendirme"


def test_sayfa_listesi_dolu():
    """Kayıt defterinden okunan sayfa sayısı makul — liste boş gelip test sessizce bir şey denemesin."""
    assert len(SAYFALAR) >= 40
