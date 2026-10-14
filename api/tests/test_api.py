# -*- coding: utf-8 -*-
"""Yeni uygulama API'si (Faz 0): giriş, kilit, oturum, yetkiye göre menü."""
import time

import pytest

from api import oturum, uyum

ANAHTAR = "a" * 40


# ── Uyum katmanı ─────────────────────────────────────────────────────
def test_gizli_ayarlar_ortamdan():
    s = uyum.gizli_ayarlar({"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "gizli",
                            "KULLANICILAR_JSON": '{"serdar": "pbkdf2$1$a$b"}'})
    assert s["supabase"]["url"] == "https://x.supabase.co" and s["supabase"]["service_role_key"] == "gizli"
    assert s["kullanicilar"] == {"serdar": "pbkdf2$1$a$b"}
    assert uyum.gizli_ayarlar({"KULLANICILAR_JSON": "bozuk"})["kullanicilar"] == {}
    with pytest.raises(KeyError):
        uyum.gizli_ayarlar({})["supabase"]


def test_onbellek_sureli_ve_temizlenir(monkeypatch):
    st = uyum.modul()
    sayac = []

    @st.cache_data(ttl=60, show_spinner=False)
    def oku(x):
        sayac.append(x)
        return x * 2

    assert oku(2) == 4 and oku(2) == 4 and sayac == [2]
    oku.clear()
    assert oku(2) == 4 and sayac == [2, 2]
    t = [1000.0]
    monkeypatch.setattr(uyum.time, "monotonic", lambda: t[0])
    oku.clear()
    oku(3)
    t[0] += 61
    oku(3)
    assert sayac[-2:] == [3, 3]                      # süre doldu → yeniden okundu
    assert st.markdown("x") is None and st.herhangi_bir_sey(1, a=2) is None


# ── Oturum belirteci ─────────────────────────────────────────────────
def test_belirtec_gidis_donus():
    b = oturum.uret("ibrahim", ANAHTAR, simdi=1_000_000)
    assert oturum.coz(b, ANAHTAR, simdi=1_000_100) == "ibrahim"


@pytest.mark.parametrize("bozma", ["imza", "govde", "anahtar", "sure", "bos"])
def test_belirtec_reddedilir(bozma):
    b = oturum.uret("ibrahim", ANAHTAR, simdi=1_000_000)
    govde, imza = b.split(".")
    if bozma == "imza":
        b = govde + "." + ("A" if imza[0] != "A" else "B") + imza[1:]
    elif bozma == "govde":
        b = oturum.uret("serdar", ANAHTAR, simdi=1_000_000).split(".")[0] + "." + imza
    elif bozma == "anahtar":
        assert oturum.coz(b, "b" * 40, simdi=1_000_100) is None
        return
    elif bozma == "sure":
        assert oturum.coz(b, ANAHTAR, simdi=1_000_000 + oturum.SURE_SN + 1) is None
        return
    else:
        b = ""
    assert oturum.coz(b, ANAHTAR, simdi=1_000_100) is None


def test_kisa_anahtarla_oturum_acilmaz():
    with pytest.raises(ValueError):
        oturum.uret("ibrahim", "kisa")
    assert oturum.coz(oturum.uret("ibrahim", ANAHTAR), "") is None


# ── Giriş ────────────────────────────────────────────────────────────
def test_dogru_sifre_httponly_cerez(ortam):
    r = ortam["istemci"].post("/giris", json={"kullanici": "ibrahim", "sifre": "dogru-sifre"})
    assert r.status_code == 200 and r.json() == {"kullanici": "ibrahim"}
    cerez = r.headers["set-cookie"]
    assert cerez.startswith(oturum.CEREZ + "=") and "HttpOnly" in cerez and "samesite=lax" in cerez.lower()
    assert ortam["basarili"] == ["ibrahim"] and not ortam["basarisiz"]


def test_canlida_cerez_yalniz_https(ortam, monkeypatch):
    import api.main as M
    monkeypatch.setattr(M, "GELISTIRME", False)
    r = ortam["istemci"].post("/giris", json={"kullanici": "ibrahim", "sifre": "dogru-sifre"})
    assert "Secure" in r.headers["set-cookie"]


def test_sifresi_yalniz_gizli_ayarda_olan_kullanici(ortam):
    """6 aktif kullanıcının şifresi veritabanında değil, eski uygulamanın gizli ayarında (Ekim 2026)."""
    r = ortam["istemci"].post("/giris", json={"kullanici": "serdar", "sifre": "serdar-sifre"})
    assert r.status_code == 200


def test_yanlis_sifre_sayac_ve_mesaj(ortam):
    c = ortam["istemci"]
    for i in range(1, 4):
        r = c.post("/giris", json={"kullanici": "ibrahim", "sifre": "yanlis"})
        assert r.status_code == 401 and "set-cookie" not in r.headers
    assert ortam["basarisiz"]["ibrahim"] == 3
    assert "2 deneme hakkınız kaldı" in r.json()["detail"]
    c.post("/giris", json={"kullanici": "ibrahim", "sifre": "yanlis"})
    r = c.post("/giris", json={"kullanici": "ibrahim", "sifre": "yanlis"})
    assert r.status_code == 429 and "1 dakika kilitlendi" in r.json()["detail"]


def test_kilitli_hesap_dogru_sifreyle_de_giremez(ortam):
    ortam["kilitli"].add("ibrahim")
    r = ortam["istemci"].post("/giris", json={"kullanici": "ibrahim", "sifre": "dogru-sifre"})
    assert r.status_code == 429 and "1 dk 15 sn" in r.json()["detail"] and not ortam["basarili"]


@pytest.mark.parametrize("kullanici, sifre", [("pasif", "x"), ("yok", "dogru-sifre"), ("", "x"), ("ibrahim", "")])
def test_giris_reddi(ortam, kullanici, sifre):
    r = ortam["istemci"].post("/giris", json={"kullanici": kullanici, "sifre": sifre})
    assert r.status_code in (400, 401) and "set-cookie" not in r.headers


def test_anahtar_yoksa_giris_kapali(ortam, monkeypatch):
    monkeypatch.setenv("OTURUM_ANAHTARI", "")
    r = ortam["istemci"].post("/giris", json={"kullanici": "ibrahim", "sifre": "dogru-sifre"})
    assert r.status_code == 503 and not ortam["basarili"]


# ── /ben: kullanıcı, yetki, menü ─────────────────────────────────────
def _giris(ortam, k="ibrahim", s="dogru-sifre"):
    c = ortam["istemci"]
    assert c.post("/giris", json={"kullanici": k, "sifre": s}).status_code == 200
    return c


def test_oturumsuz_ben_401(ortam):
    assert ortam["istemci"].get("/ben").status_code == 401


def test_ben_menu_yetkiye_gore(ortam):
    v = _giris(ortam).get("/ben").json()
    assert v["kullanici"] == "ibrahim" and v["ozel"] == ["kar"] and v["moduller"]["kayranacc"] is True
    kodlar = [m["kod"] for m in v["menu"]]
    assert kodlar[0] == "anasayfa" and "kayranacc" in kodlar
    assert "satis" not in kodlar and "yonetim" not in kodlar and "ekip" not in kodlar
    acc = next(m for m in v["menu"] if m["kod"] == "kayranacc")
    bu = next(s for s in acc["sayfalar"] if s["kod"] == "bu_hafta")
    assert bu["ad"] == "Bu hafta" and bu["grup"] == "Ödemeler"
    assert bu["eski"] == "https://kayran.streamlit.app/?s=kayranacc&p=bu_hafta" and bu["yeni"] is False
    # sayfalar grup sırasıyla: aynı grup başlığı iki kez çıkmaz
    gruplar = [p["grup"] for p in acc["sayfalar"]]
    assert gruplar == sorted(gruplar, key=gruplar.index), gruplar
    assert gruplar[:2] == ["Genel bakış", "Ödemeler"]
    # Toplam aktifler koşullu sayfa: özel yetki yok → görünmez
    assert "toplam_aktifler" not in [s["kod"] for s in acc["sayfalar"]]


def test_kar_yetkisi_pnl_sayfasini_acar(ortam):
    ortam["tablo"]["serdar"]["ozel"] = []
    v = _giris(ortam, "serdar", "serdar-sifre").get("/ben").json()
    satis = next(m for m in v["menu"] if m["kod"] == "satis")
    assert "pnl" not in [s["kod"] for s in satis["sayfalar"]]
    ortam["tablo"]["serdar"]["ozel"] = ["kar"]
    v = ortam["istemci"].get("/ben").json()
    assert "pnl" in [s["kod"] for s in next(m for m in v["menu"] if m["kod"] == "satis")["sayfalar"]]


def test_pasife_alinan_kullanici_oturumu_duser(ortam):
    c = _giris(ortam)
    assert c.get("/ben").status_code == 200
    ortam["tablo"]["ibrahim"]["aktif"] = False
    assert c.get("/ben").status_code == 401


def test_yetki_tablosu_okunamazsa_kimseye_yetki_yok(ortam, monkeypatch):
    import shared.yetki as Y
    c = _giris(ortam, "serdar", "serdar-sifre")
    monkeypatch.setattr(Y, "yetki_tablosu", lambda: None)
    v = c.get("/ben").json()
    assert not any(v["moduller"].values()) and [m["kod"] for m in v["menu"]] == ["anasayfa"]


def test_cikis_cerezi_siler(ortam):
    c = _giris(ortam)
    r = c.post("/cikis")
    assert r.status_code == 200 and oturum.CEREZ in r.headers["set-cookie"] and "Max-Age=0" in r.headers["set-cookie"]
    assert c.get("/ben").status_code == 401


def test_sahte_cerezle_giris_olmaz(ortam):
    c = ortam["istemci"]
    c.cookies.set(oturum.CEREZ, oturum.uret("ibrahim", "z" * 40))
    assert c.get("/ben").status_code == 401
    c.cookies.set(oturum.CEREZ, oturum.uret("ibrahim", "t" * 48, simdi=time.time() - oturum.SURE_SN - 5))
    assert c.get("/ben").status_code == 401


def test_belgeler_canlida_kapali(monkeypatch):
    """Canlıda /belgeler ve /openapi.json kapalı (API yüzeyi dışarıya anlatılmaz)."""
    import importlib
    import api.main as M
    monkeypatch.setenv("ORTAM", "")
    try:
        M2 = importlib.reload(M)
        from fastapi.testclient import TestClient
        c = TestClient(M2.app)
        assert c.get("/belgeler").status_code == 404 and c.get("/openapi.json").status_code == 404
        assert c.get("/saglik").json() == {"durum": "ayakta"}
    finally:
        monkeypatch.setenv("ORTAM", "gelistirme")
        importlib.reload(M)


def test_menu_ikonlari_on_yuzde_var():
    """API'nin gönderdiği modül ikonları ön yüze gömülü olmalı (web/lib/ikonlar.ts; yoksa yedek ikon çıkar)."""
    from pathlib import Path
    from shared.gezinme import MODULLER
    ikonlar = (Path(__file__).resolve().parents[2] / "web" / "lib" / "ikonlar.ts").read_text(encoding="utf-8")
    eksik = [m["ikon"] for m in MODULLER if f'"{m["ikon"]}":' not in ikonlar]
    assert not eksik, f"web/scripts/ikonlari-uret.mjs LISTE'ye ekle: {eksik}"
