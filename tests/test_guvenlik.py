# -*- coding: utf-8 -*-
"""Giriş / oturum / denetim izi / dönem kilidi güvenlik açıkları (Ekim 2026).

  1) Düz metin saklı şifre (DB ya da Secrets) KABUL EDİLMEZ; pbkdf2 aynen çalışır.
  2) Kaba kuvvet kilidi: veritabanı okunamaz/yazılamazsa süreç içi bellek sayacı sınırlar
     (eskiden sınırsız deneme serbestti). Yalnız hatalı deneyen kullanıcı kilitlenir.
  3) Oturum: URL'deki mevcut anahtarlar (eski kodla üretilmiş) geçerli kalır — kimse atılmaz;
     yeni anahtar aynı biçimde üretilir. Sunucu sırrında koda yazılı sabit değer yok.
  4) Denetim izi: giriş başarı/başarısızlık, şifre ve yetki değişikliği audit_log'a düşer;
     şifre ve hash ASLA yazılmaz.
  5) 30_denetim_ve_donem_kilidi.sql: tekrar çalıştırılabilir, bypass ayarı ve GERİ ALMA var.
"""
import re
import time
import types
from pathlib import Path

import pytest

import shared.audit as AU
import shared.auth as A
import shared.oturum as O
import shared.yetki as Y

KOK = Path(__file__).resolve().parent.parent


# ═══════════════════════════════════════════════════════════════════════
# Sahte veritabanı ve denetim kaydı yakalayıcı
# ═══════════════════════════════════════════════════════════════════════
class _Sorgu:
    def __init__(self, db, tablo):
        self.db, self.tablo, self.islem, self.veri, self.filtre = db, tablo, "select", None, {}

    def select(self, *a, **k):
        return self

    def eq(self, c, v):
        self.filtre[c] = v
        return self

    def limit(self, *a):
        return self

    def insert(self, veri, **k):
        self.islem, self.veri = "insert", veri
        return self

    def upsert(self, veri, **k):
        self.islem, self.veri = "upsert", veri
        return self

    def execute(self):
        if self.db.hata_oku and self.islem == "select":
            raise ConnectionError("db okunamadı")
        if self.db.hata_yaz and self.islem != "select":
            raise ConnectionError("db yazılamadı")
        t = self.db.tablolar.setdefault(self.tablo, {})
        if self.islem == "select":
            k = self.filtre.get("kullanici_adi")
            return types.SimpleNamespace(data=[dict(t[k])] if k in t else [])
        anahtar = self.veri.get("kullanici_adi")
        t.setdefault(anahtar, {}).update(self.veri)
        return types.SimpleNamespace(data=[self.veri])


class _SahteDB:
    def __init__(self, hata_oku=False, hata_yaz=False):
        self.tablolar, self.hata_oku, self.hata_yaz = {}, hata_oku, hata_yaz

    def table(self, ad):
        return _Sorgu(self, ad)


class _AuditYakala:
    """shared.audit._raw_client yerine: audit_log insert'lerini listeye toplar."""
    def __init__(self):
        self.satirlar = []

    def table(self, ad):
        yak = self

        class _T:
            def insert(self, veri):
                assert ad == "audit_log"
                yak.satirlar.append(dict(veri))
                return self

            def execute(self):
                return types.SimpleNamespace(data=[])
        return _T()


@pytest.fixture
def denetim(monkeypatch):
    y = _AuditYakala()
    monkeypatch.setattr(AU, "_raw_client", lambda: y)
    return y


@pytest.fixture
def bellek_temiz(monkeypatch):
    d = {}
    monkeypatch.setattr(A, "_BF_BELLEK", d, raising=False)   # eski kodda yok → iddia kızarır
    return d


# ═══════════════════════════════════════════════════════════════════════
# 1) DÜZ METİN ŞİFRE REDDİ
# ═══════════════════════════════════════════════════════════════════════
def test_duz_metin_saklanan_sifre_reddedilir():
    # Eski kod: "Geçiş dönemi" yolu düz metni düz metinle karşılaştırıp True dönüyordu.
    assert A.sifre_dogrula("Kayran2026", "Kayran2026") is False
    assert A.sifre_dogrula("", "") is False


def test_secrets_listesinde_duz_metin_kabul_edilmez():
    assert A.kullanici_dogrula("ali", "ali12345", {"ali": "ali12345"}) is False


def test_v2_duz_metin_kayitla_giris_yok(monkeypatch, denetim):
    monkeypatch.setattr(Y, "kullanici_kaydi", lambda k: (False, None))
    monkeypatch.setattr(A, "supabase_sifre_oku", lambda k: "Duz12345")
    assert A.kullanici_dogrula_v2("ali", "Duz12345", {"ali": "Duz12345"}) is False
    monkeypatch.setattr(A, "supabase_sifre_oku", lambda k: None)
    assert A.kullanici_dogrula_v2("ali", "Duz12345", {"ali": "Duz12345"}) is False


def test_pbkdf2_hash_aynen_calisir(monkeypatch):
    h = A.sifre_hash_uret("Kayran2026", iterasyon=1000)
    assert A.sifre_dogrula("Kayran2026", h) is True
    assert A.sifre_dogrula("kayran2026", h) is False
    monkeypatch.setattr(Y, "kullanici_kaydi", lambda k: (False, None))
    monkeypatch.setattr(A, "supabase_sifre_oku", lambda k: None)
    assert A.kullanici_dogrula_v2("ali", "Kayran2026", {"ali": h}) is True


# ═══════════════════════════════════════════════════════════════════════
# 2) KABA KUVVET: DB HATASINDA BELLEK SINIRI
# ═══════════════════════════════════════════════════════════════════════
def _bes_hata(kim):
    son = None
    for _ in range(A._BF_ESIK):
        son = A.giris_basarisiz(kim)
    return son


def test_db_okunamazken_bes_hatadan_sonra_kilit(monkeypatch, bellek_temiz, denetim):
    monkeypatch.setattr(A, "_get_supabase", lambda: _SahteDB(hata_oku=True, hata_yaz=True))
    assert A.giris_kontrol("serdar") == (True, 0)
    sayi, kilit = _bes_hata("serdar")
    assert sayi == 5 and kilit == 60                      # eski kod: (0, 0)
    izin, kalan = A.giris_kontrol("Serdar ")              # aynı kullanıcı, farklı yazım
    assert izin is False and 0 < kalan <= 60              # eski kod: (True, 0) — sınırsız
    # Başkası etkilenmez
    assert A.giris_kontrol("ibrahim") == (True, 0)


def test_db_baglantisi_yokken_de_sinir_var(monkeypatch, bellek_temiz, denetim):
    monkeypatch.setattr(A, "_get_supabase", lambda: None)
    _bes_hata("ali")
    assert A.giris_kontrol("ali")[0] is False
    assert A.giris_kontrol("veli")[0] is True


def test_basarili_giris_bellegi_sifirlar(monkeypatch, bellek_temiz, denetim):
    monkeypatch.setattr(A, "_get_supabase", lambda: None)
    for _ in range(4):
        A.giris_basarisiz("ali")
    A.giris_basarili("ali")
    assert A.giris_basarisiz("ali") == (1, 0)


def test_ceza_basamaklari_db_ile_ayni(monkeypatch, bellek_temiz, denetim):
    monkeypatch.setattr(A, "_get_supabase", lambda: None)
    sonuc = [A.giris_basarisiz("ali")[1] for _ in range(10)]
    assert sonuc == [0, 0, 0, 0, 60, 120, 300, 600, 900, 900]


def test_db_okunuyor_ama_yazilamiyorsa_bellek_karar_verir(monkeypatch, bellek_temiz, denetim):
    monkeypatch.setattr(A, "_get_supabase", lambda: _SahteDB(hata_yaz=True))
    _bes_hata("ali")
    assert A.giris_kontrol("ali")[0] is False


def test_db_calisirken_davranis_aynen(monkeypatch, bellek_temiz, denetim):
    db = _SahteDB()
    monkeypatch.setattr(A, "_get_supabase", lambda: db)
    assert [A.giris_basarisiz("ali") for _ in range(5)][-1] == (5, 60)
    assert db.tablolar["giris_denemeleri"]["ali"]["basarisiz_sayi"] == 5
    assert A.giris_kontrol("ali")[0] is False
    A.giris_basarili("ali")
    assert db.tablolar["giris_denemeleri"]["ali"]["basarisiz_sayi"] == 0
    assert A.giris_kontrol("ali") == (True, 0)


def test_db_kilidi_elle_acilinca_bellek_engellemez(monkeypatch, bellek_temiz, denetim):
    """DB sağlıklıyken bellek sayacı DB'nin önüne geçmez (yönetici kilidi DB'den açabilir)."""
    db = _SahteDB()
    monkeypatch.setattr(A, "_get_supabase", lambda: db)
    _bes_hata("ali")
    db.tablolar["giris_denemeleri"]["ali"].update(basarisiz_sayi=0, kilit_bitis=None)
    assert A.giris_kontrol("ali") == (True, 0)


def test_bellek_sinirsiz_buyumez(monkeypatch, bellek_temiz, denetim):
    monkeypatch.setattr(A, "_get_supabase", lambda: None)
    monkeypatch.setattr(A, "_BF_BELLEK_SINIR", 50, raising=False)
    for i in range(200):
        A.giris_basarisiz(f"k{i}")
    assert 0 < len(bellek_temiz) <= 50


# ═══════════════════════════════════════════════════════════════════════
# 3) OTURUM: ESKİ ANAHTAR KABUL, YENİ ÜRETİM, SABİT SIR YOK
# ═══════════════════════════════════════════════════════════════════════
@pytest.fixture
def depo(monkeypatch):
    d = {}
    monkeypatch.setattr(O, "oturum_store", lambda: d)
    return d


def _eski_kodla_uret(depo, kullanici, cihaz, ts):
    """origin/main app.py _oturum_ac'ın depoya yazdığı kayıt (birebir)."""
    import secrets as _sec
    tok = _sec.token_urlsafe(24)
    depo[tok] = {"u": kullanici, "cihaz": cihaz, "ts": ts}
    return tok


def test_eski_kodla_uretilmis_oturum_gecerli_kalir(depo, monkeypatch):
    simdi = time.time()
    tok = _eski_kodla_uret(depo, "serdar", "imza1", simdi - 6 * 86400)
    # Sunucu sırrı değişse de (yeni secrets) anahtar geçerli: geçerlilik depodaki kayıtta
    monkeypatch.setattr(O, "st", types.SimpleNamespace(secrets={"oturum": {"secret": "yeni"}}))
    assert O.oturum_dogrula(tok, "imza1", simdi=simdi) == "serdar"
    assert depo[tok]["ts"] == simdi                       # süre kaydı


def test_suresi_dolan_ve_baska_tarayicidaki_anahtar(depo):
    simdi = time.time()
    eski = _eski_kodla_uret(depo, "serdar", "imza1", simdi - 7 * 86400 - 1)
    assert O.oturum_dogrula(eski, "imza1", simdi=simdi) is None
    tok = _eski_kodla_uret(depo, "serdar", "imza1", simdi)
    assert O.oturum_dogrula(tok, "imza2", simdi=simdi) is None
    assert tok not in depo                                # link paylaşımı → yakıldı
    tok2 = _eski_kodla_uret(depo, "serdar", "imza1", simdi)
    assert O.oturum_dogrula(tok2, "", simdi=simdi) is None
    assert O.oturum_dogrula("", "imza1") is None
    assert O.oturum_dogrula("yok-boyle-anahtar", "imza1") is None


def test_yeni_anahtar_ayni_bicimde_uretilir(depo):
    tok = O.oturum_olustur("ibrahim", "imzaX")
    assert re.fullmatch(r"[A-Za-z0-9_-]{32}", tok)       # token_urlsafe(24)
    assert set(depo[tok]) == {"u", "cihaz", "ts"} and depo[tok]["u"] == "ibrahim"
    assert O.oturum_dogrula(tok, "imzaX") == "ibrahim"
    assert O.oturum_olustur("ibrahim", "imzaX") != tok


def _sirli(monkeypatch, secrets):
    monkeypatch.setattr(O, "st", types.SimpleNamespace(secrets=secrets))
    return O.oturum_anahtari()


def test_oturum_anahtari_kaynaklari(monkeypatch):
    assert _sirli(monkeypatch, {"oturum": {"secret": "S3cr3t"},
                                "supabase": {"service_role_key": "srk"}}) == "S3cr3t"
    tureyen = _sirli(monkeypatch, {"supabase": {"service_role_key": "srk", "key": "anon"}})
    assert tureyen and len(tureyen) == 64 and "srk" not in tureyen
    assert tureyen == _sirli(monkeypatch, {"supabase": {"service_role_key": "srk"}})
    assert tureyen != _sirli(monkeypatch, {"supabase": {"service_role_key": "baska"}})
    # Yalnız public (anon) anahtar ya da hiçbir şey → sır YOK (sabit değere düşmez)
    assert _sirli(monkeypatch, {"supabase": {"key": "anon"}}) is None
    assert _sirli(monkeypatch, {}) is None


def test_sabit_oturum_anahtari_kodda_kalmadi():
    for p in list(KOK.glob("*.py")) + list(KOK.glob("*/*.py")):
        if ".venv" in p.parts or p.name == "test_guvenlik.py":
            continue
        assert "kayran-oturum-varsayilan-anahtar" not in p.read_text(encoding="utf-8"), p
    app = (KOK / "app.py").read_text(encoding="utf-8")
    assert "def _oturum_token" not in app and "_oturum_token(" not in app
    govde = re.search(r"^def _oturum_secret\(.*?(?=^def |^if )", app, re.S | re.M).group(0)
    assert 'st.secrets["supabase"]["key"]' not in govde
    assert "oturum_anahtari" in govde


def test_app_oturumu_tek_kaynaktan_dogrular():
    app = (KOK / "app.py").read_text(encoding="utf-8")
    assert "oturum_dogrula(_qt, _cihaz_imzasi())" in app
    assert "oturum_olustur(kullanici, _cihaz_imzasi())" in app


# ═══════════════════════════════════════════════════════════════════════
# 4) DENETİM İZİ — ŞİFRE/HASH ASLA YAZILMAZ
# ═══════════════════════════════════════════════════════════════════════
def _yazilan_metin(denetim):
    return " | ".join(str(v) for s in denetim.satirlar for v in s.values())


def test_giris_basari_ve_basarisizlik_kaydi(monkeypatch, bellek_temiz, denetim):
    monkeypatch.setattr(A, "_get_supabase", lambda: _SahteDB())
    A.giris_basarisiz("Serdar")
    A.giris_basarili("serdar")
    islemler = [(s["islem"], s["kullanici"], s["modul"]) for s in denetim.satirlar]
    assert ("giris_hatali", "serdar", "guvenlik") in islemler
    assert ("giris", "serdar", "guvenlik") in islemler


def test_kilitli_giris_denemesi_kaydi(monkeypatch, bellek_temiz, denetim):
    monkeypatch.setattr(A, "_get_supabase", lambda: None)
    _bes_hata("ali")
    A.giris_kontrol("ali")
    assert any(s["islem"] == "giris_engellendi" for s in denetim.satirlar)


def test_sifre_degisikligi_kaydi_hash_icermez(monkeypatch, denetim):
    db = _SahteDB()
    monkeypatch.setattr(A, "_get_supabase", lambda: db)
    h = A.sifre_hash_uret("Gizli12345", iterasyon=1000)
    assert A.supabase_sifre_kaydet("serdar", h) is True
    s = [x for x in denetim.satirlar if x["islem"] == "sifre_degisti"]
    assert len(s) == 1 and s[0]["kayit_id"] == "serdar" and s[0]["tablo"] == "kullanici_sifreler"
    metin = _yazilan_metin(denetim)
    assert "pbkdf2" not in metin and h.split("$")[-1] not in metin and "Gizli12345" not in metin


def test_sifre_yazilamazsa_kayit_yok(monkeypatch, denetim):
    monkeypatch.setattr(A, "_get_supabase", lambda: _SahteDB(hata_yaz=True))
    assert A.supabase_sifre_kaydet("serdar", "pbkdf2:sha256:1$aa$bb") is False
    assert not denetim.satirlar


def test_sarmalanmis_istemci_gizli_alanlari_maskeler(denetim):
    """Biri kullanici_sifreler'i wrap_client'tan geçirse bile hash loga düşmez."""
    class _B:
        def upsert(self, *a, **k):
            return self

        def execute(self, *a, **k):
            return types.SimpleNamespace(data=[])

    class _C:
        def table(self, ad):
            return _B()
    sb = AU.wrap_client(_C(), "test")
    sb.table("kullanici_sifreler").upsert(
        {"kullanici_adi": "serdar", "sifre_hash": "pbkdf2:sha256:260000$aa$bb"}).execute()
    metin = _yazilan_metin(denetim)
    assert "kullanici_adi=serdar" in metin and "sifre_hash=***" in metin
    assert "pbkdf2" not in metin and "aa$bb" not in metin


def test_guvenlik_kaydi_gizli_alanlari_ve_serbest_metni_temizler(denetim):
    AU.guvenlik_kaydi("deneme", kullanici="ali", hedef="pbkdf2:sha256:1$x$y",
                      detay={"sifre": "Duz123", "token": "abc", "parola": "p", "deneme": 3})
    AU.log_yaz("ekle", "t", detay="eski=pbkdf2:sha256:1$aa$bb, ad=x")
    metin = _yazilan_metin(denetim)
    for gizli in ("Duz123", "abc", "=p", "pbkdf2", "$aa$bb"):
        assert gizli not in metin
    assert "deneme=3" in metin and "ad=x" in metin


def test_yetki_degisikligi_kaydi(denetim):
    AU.yetki_degisikligi_kaydet("serdar", moduller=["satis", "depo"], ozel=[], salt_okur=False,
                                aktif=True, guncelleyen="ibrahim")
    s = denetim.satirlar[-1]
    assert (s["islem"], s["tablo"], s["kayit_id"], s["kullanici"], s["modul"]) == (
        "yetki_degisti", "kullanici_yetkileri", "serdar", "ibrahim", "guvenlik")
    assert s["detay"] == "moduller=depo,satis; ozel=; salt_okur=False; aktif=True"


def test_denetim_yazilamazsa_akis_bozulmaz(monkeypatch, bellek_temiz):
    def _patla():
        raise ConnectionError("audit yok")
    monkeypatch.setattr(AU, "_raw_client", _patla)
    monkeypatch.setattr(A, "_get_supabase", lambda: _SahteDB())
    assert A.giris_basarisiz("ali") == (1, 0)
    A.giris_basarili("ali")
    assert A.supabase_sifre_kaydet("ali", "pbkdf2:sha256:1$aa$bb") is True
    AU.yetki_degisikligi_kaydet("ali", aktif=False)


# ═══════════════════════════════════════════════════════════════════════
# 5) SQL DOSYASI (kurulmadı; yapı denetimi)
# ═══════════════════════════════════════════════════════════════════════
SQL = KOK / "veritabani" / "30_denetim_ve_donem_kilidi.sql"


def _sql_kod():
    """Yorum satırları atılmış SQL."""
    return "\n".join(l for l in SQL.read_text(encoding="utf-8").splitlines()
                     if not l.lstrip().startswith("--"))


def test_sql_tekrar_calistirilabilir_ve_geri_alinabilir():
    tam = SQL.read_text(encoding="utf-8")
    kod = _sql_kod()
    for tg in ("audit_log_degismez", "audit_log_bosaltilamaz",
               "edefter_fisler_donem_kilidi", "edefter_fis_satirlari_donem_kilidi"):
        assert f"DROP TRIGGER IF EXISTS {tg}" in kod          # tekrar çalıştırılabilir
        assert f"CREATE TRIGGER {tg}" in kod
        assert f"-- DROP TRIGGER IF EXISTS {tg}" in tam       # GERİ ALMA bloğu
    assert "GERİ ALMA" in tam
    assert kod.count("CREATE OR REPLACE FUNCTION") == 4
    assert "CREATE TABLE" not in kod and "DROP TABLE" not in kod
    assert not re.search(r"^\s*(DELETE|UPDATE|INSERT|TRUNCATE)\b", kod, re.M | re.I)


def test_sql_bypass_ve_kurallar():
    kod = _sql_kod()
    assert "current_setting('kayran.denetim_bakim', true)" in kod
    assert "current_setting('kayran.donem_bakim', true)" in kod
    assert "BEFORE UPDATE OR DELETE ON public.audit_log" in kod
    assert "BEFORE TRUNCATE ON public.audit_log" in kod
    assert kod.count("BEFORE INSERT OR UPDATE OR DELETE") == 2
    # Dönem biçimi edefter.py ile aynı: 'YYYY-MM' = tarihin ilk 7 karakteri
    assert "left(p_tarih, 7)" in kod
    # Dönem kilitleme adımı (yalnız 'kilitli' sütunu güncellenir) takılmamalı
    assert "(to_jsonb(NEW) - 'kilitli') = (to_jsonb(OLD) - 'kilitli')" in kod
    # Tablolar yoksa kurulum atlar
    assert "to_regclass('public.audit_log') IS NOT NULL" in kod
    assert "to_regclass('public.edefter_fisler') IS NULL" in kod


def test_sql_donem_bicimi_edefter_ile_ayni():
    src = (KOK / "kayranacc" / "edefter.py").read_text(encoding="utf-8")
    assert 'donem = f"{int(yil)}-{int(ay):02d}"' in src
    assert "str(tarih or \"\")[:7]" in src
