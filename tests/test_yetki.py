# -*- coding: utf-8 -*-
"""
Veritabanı destekli yetki katmanı — shared/yetki.py

Kritik güvenceler:
  1) Tablo yoksa/okunamazsa koddaki SABİT listelere düşülür (kimse kilitlenmez).
  2) Kurulum SQL'indeki başlangıç verisi, sabit listelerle HERKES için
     BİREBİR aynı sonucu verir (geçişte kimsenin yetkisi değişmez).
  3) Pasif kullanıcı giremez; ekrandan açılan kullanıcı Secrets'ta olmadan girer.
"""
import re
from pathlib import Path

import pytest

import shared.yetki as Y

KOK = Path(__file__).resolve().parent.parent


# ── Koddaki sabit listeleri oku (app.py çalıştırılmadan) ──────────────
def _statik():
    src = open(KOK / "app.py", encoding="utf-8").read()
    ns = {}
    exec(src[src.index("KAYRANACC_KULLANICILAR = "):src.index("def salt_okur_mu")], ns)
    exec(re.search(r"^TALEP_YONETICILERI\s*=.*$", src, re.M).group(0), ns)
    exec(re.search(r"^def _statik_yetkiler\(.*?^    \}", src, re.S | re.M).group(0), ns)
    acc = open(KOK / "kayranacc" / "main.py", encoding="utf-8").read()
    exec(re.search(r"^TOPLAM_AKTIFLER_YETKILI\s*=.*$", acc, re.M).group(0), ns)
    ozel = {"yonetim": ns["YONETIM_KULLANICILAR"],
            "patron_panel": ns["PATRON_PANEL_KULLANICILAR"],
            "talep_yonetici": ns["TALEP_YONETICILERI"],
            "kullanici_yonetimi": ns["KULLANICI_YONETIMI_KULLANICILAR"],
            "toplam_aktifler": ns["TOPLAM_AKTIFLER_YETKILI"]}
    return ns["_statik_yetkiler"], ozel, ns["SALT_OKUR_KULLANICILAR"]


# ── Kurulum SQL'indeki başlangıç verisini oku ─────────────────────────
def _seed_tablosu():
    sql = open(KOK / "veritabani" / "04_kullanici_yetkileri.sql", encoding="utf-8").read()
    _i = sql.index("INSERT INTO kullanici_yetkileri")
    blok = sql[_i:sql.index("ON CONFLICT", _i)]
    out = {}
    for m in re.finditer(r"\('(\w+)',\s*(ARRAY\[[^\]]*\]::text\[\]|'\{\}'::text\[\]),\s*"
                         r"(ARRAY\[[^\]]*\]::text\[\]|'\{\}'::text\[\]),\s*(true|false),\s*(true|false)\)",
                         blok):
        dizi = lambda t: re.findall(r"'(\w+)'", t) if t.startswith("ARRAY") else []
        out[m.group(1)] = {"moduller": sorted(dizi(m.group(2))), "ozel": sorted(dizi(m.group(3))),
                           "salt_okur": m.group(4) == "true", "aktif": m.group(5) == "true"}
    return out


@pytest.fixture
def db(monkeypatch):
    """yetki_tablosu'nu verilen sözlükle değiştir."""
    def _kur(tablo):
        monkeypatch.setattr(Y, "yetki_tablosu", lambda: tablo)
    return _kur


# ═══════════════════════════════════════════════════════════════════════
# 1) GÜVENLİK AĞI
# ═══════════════════════════════════════════════════════════════════════
def test_tablo_yoksa_sabit_listeye_duser(db):
    db(None)
    statik = {"kayranacc": True, "satis": False}
    assert Y.moduller("serdar", statik) == statik
    assert Y.ozel_yetki("ibrahim", "yonetim", {"ibrahim"}) is True
    assert Y.ozel_yetki("serdar", "yonetim", {"ibrahim"}) is False
    assert Y.salt_okur("ahmet", {"ahmet"}) is True
    assert Y.kullanici_kaydi("x") == (False, None)


def test_supabase_hata_verirse_none(monkeypatch):
    def patla():
        raise RuntimeError("bağlantı yok")
    monkeypatch.setattr(Y, "_supabase", patla)
    assert Y.yetki_tablosu() is None


# ═══════════════════════════════════════════════════════════════════════
# 2) VERİTABANI MODU
# ═══════════════════════════════════════════════════════════════════════
TABLO = {
    "serdar": {"moduller": ["depo", "kayranacc"], "ozel": ["toplam_aktifler"],
               "salt_okur": False, "aktif": True},
    "ahmet": {"moduller": [], "ozel": ["yonetim"], "salt_okur": True, "aktif": True},
    "eski": {"moduller": ["satis"], "ozel": ["yonetim"], "salt_okur": False, "aktif": False},
}


def test_db_modul_yetkisi(db):
    db(TABLO)
    y = Y.moduller("Serdar", {})                       # büyük/küçük harf duyarsız
    assert y["kayranacc"] and y["depo"]
    assert not y["satis"] and not y["kayranpm"]


def test_db_salt_okur_her_seyi_gorur(db):
    db(TABLO)
    assert all(Y.moduller("ahmet", {}).values())
    assert Y.salt_okur("ahmet", set()) is True


def test_db_pasif_kullanici_hicbir_sey_goremez(db):
    db(TABLO)
    assert not any(Y.moduller("eski", {}).values())
    assert Y.ozel_yetki("eski", "yonetim", set()) is False
    assert "eski" not in Y.aktif_kullanicilar(set())
    assert "eski" not in Y.ozel_sahipleri("yonetim", set())


def test_db_tanimsiz_kullanici_yetkisiz(db):
    db(TABLO)
    assert not any(Y.moduller("yabanci", {"kayranacc": True}).values())


# ═══════════════════════════════════════════════════════════════════════
# 3) GEÇİŞ: başlangıç verisi == sabit listeler (herkes için)
# ═══════════════════════════════════════════════════════════════════════
def test_seed_sabit_listelerle_birebir_ayni(db):
    statik_fn, ozel_statik, salt_statik = _statik()
    seed = _seed_tablosu()
    assert len(seed) >= 10, "SQL'deki başlangıç verisi okunamadı"
    db(seed)
    herkes = set(seed)
    for v in ozel_statik.values():
        herkes |= set(v)
    farklar = []
    for k in sorted(herkes):
        if Y.moduller(k, statik_fn(k)) != statik_fn(k):
            farklar.append(f"{k}: modül — DB {Y.moduller(k, {})} ≠ kod {statik_fn(k)}")
        for ad, kume in ozel_statik.items():
            if Y.ozel_yetki(k, ad, kume) != (k in kume):
                farklar.append(f"{k}: özel '{ad}' farklı")
        if Y.salt_okur(k, salt_statik) != (k in salt_statik):
            farklar.append(f"{k}: salt-okur farklı")
    assert not farklar, "Geçişte yetkisi DEĞİŞECEK kullanıcılar:\n  " + "\n  ".join(farklar)


def test_seed_en_az_bir_kullanici_yoneticisi():
    seed = _seed_tablosu()
    assert any("kullanici_yonetimi" in v["ozel"] and v["aktif"] for v in seed.values())


# ═══════════════════════════════════════════════════════════════════════
# 4) GİRİŞ KONTROLÜ (shared/auth.kullanici_dogrula_v2)
# ═══════════════════════════════════════════════════════════════════════
@pytest.fixture
def giris(monkeypatch):
    import shared.auth as A
    hashler = {"serdar": A.sifre_hash_uret("Yeni1234")}
    monkeypatch.setattr(A, "supabase_sifre_oku", lambda k: hashler.get(k))
    secrets = {"ibrahim": A.sifre_hash_uret("ib1234ab"), "eski": A.sifre_hash_uret("eski1234")}
    return A, secrets


def test_ekrandan_acilan_kullanici_secrets_olmadan_girer(db, giris):
    A, secrets = giris
    db(TABLO)
    assert A.kullanici_dogrula_v2("serdar", "Yeni1234", secrets) is True
    assert A.kullanici_dogrula_v2("serdar", "yanlis99", secrets) is False


def test_pasif_kullanici_secretsta_olsa_bile_giremez(db, giris):
    A, secrets = giris
    db(TABLO)
    assert A.kullanici_dogrula_v2("eski", "eski1234", secrets) is False


def test_tanimsiz_kullanici_giremez(db, giris):
    A, secrets = giris
    db(TABLO)
    assert A.kullanici_dogrula_v2("yabanci", "x", secrets) is False


def test_db_yokken_eski_davranis_aynen_surer(db, giris):
    A, secrets = giris
    db(None)
    assert A.kullanici_dogrula_v2("ibrahim", "ib1234ab", secrets) is True
    assert A.kullanici_dogrula_v2("serdar", "Yeni1234", secrets) is False   # Secrets'ta yok


# ═══════════════════════════════════════════════════════════════════════
# 5) GİRDİ DOĞRULAMA
# ═══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("ad,beklenen", [("serdar", True), ("ali_2", True), ("a", False),
                                        ("şükrü", False), ("ali veli", False), ("x" * 21, False)])
def test_kullanici_adi(ad, beklenen):
    assert Y.kullanici_adi_gecerli_mi(ad) is beklenen


@pytest.mark.parametrize("s,beklenen", [("1234", False), ("abcdefgh", False), ("12345678", False),
                                       ("abcd1234", True), ("Kayran2026", True)])
def test_sifre_kurali(s, beklenen):
    assert Y.sifre_gecerli_mi(s) is beklenen
