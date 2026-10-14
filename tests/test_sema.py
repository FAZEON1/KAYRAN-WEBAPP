# -*- coding: utf-8 -*-
"""Veritabanı şeması repodan kurulabilir mi + kayıtlı migration (veritabani/uygula.py).

1) Kodun kullandığı her tablo/görünüm 00_temel_sema.sql'de (ya da sonradan eklenen
   numaralı bir dosyada) tanımlı; 04_…28_ dosyalarının yarattığı her tablo 00'da var.
2) 00_temel_sema.sql tekrar çalıştırılabilir yazılmış (IF NOT EXISTS / OR REPLACE),
   veri değiştiren komut içermiyor, her tablosunda RLS açık.
3) uygula.py: kuru kipte hiçbir şey yazmaz; numara sırası; sha kaydı/uyarısı;
   canlı adres --canli olmadan reddedilir; öneri dosyası uygulanmaz (sahte bağlantıyla).
4) (İsteğe bağlı, yalnız yerelde) KAYRAN_TEST_PG varsa 00 + tüm dosyalar gerçek boş
   Postgres'te çalıştırılır.
"""
import contextlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
VT = KOK / "veritabani"
TEMEL = VT / "00_temel_sema.sql"

_spec = importlib.util.spec_from_file_location("veritabani_uygula", VT / "uygula.py")
U = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = U          # dataclass modülü sys.modules'ta arar
_spec.loader.exec_module(U)

# Kodda adı geçen ama canlıda OLMAYAN tablolar (bilinen hata; düzeltilince buradan silinmeli).
BILINEN_EKSIK = set()   # kayranpm/ref_no.py "ref_no" → ref_kayitlari düzeltildi (Eki 2026)


# ─── yardımcılar ─────────────────────────────────────────────────────────
def _govdesiz(sql):
    """$etiket$ … $etiket$ gövdelerini (fonksiyon/DO) çıkarır: üst düzey komutlar kalır."""
    return re.sub(r"\$(\w*)\$.*?\$\1\$", "$$", sql, flags=re.S)


def _yorumsuz(sql):
    return re.sub(r"--[^\n]*", "", sql)


_TANIM = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:MATERIALIZED\s+)?(?:TABLE|VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?:public\.)?\"?([A-Za-z_][A-Za-z0-9_]*)\"?", re.I)
_FONK = re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?:public\.)?([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.I)


def _tanimlar(yol, desen=_TANIM):
    return set(desen.findall(_yorumsuz(Path(yol).read_text(encoding="utf-8-sig"))))


def _numarali(en_cok=None):
    for p in U.dosyalari_bul(VT):
        if p.name == TEMEL.name or U.oneri_mi(p):
            continue
        if en_cok is not None and U.numara(p.name) > en_cok:
            continue
        yield p


def _kod_dosyalari():
    atla = {"tests", ".git", ".venv", "venv", "__pycache__", ".claude", "node_modules"}
    for k, dizinler, dosyalar in os.walk(KOK):
        dizinler[:] = [d for d in dizinler if d not in atla]
        for f in dosyalar:
            if f.endswith(".py"):
                yield Path(k) / f


_KOD_DESENLERI = (
    re.compile(r"\.(?:table|from_)\(\s*[\"']([a-z_][a-z0-9_]*)[\"']"),
    re.compile(r"^\s*[A-Z_]*TABLO[A-Z_]*\s*=\s*[\"']([a-z_][a-z0-9_]*)[\"']", re.M),
    re.compile(r"\b_hepsi\(\s*[\"']([a-z_][a-z0-9_]*)[\"']"),
    re.compile(r"rest/v1/([a-z_][a-z0-9_]*)"),
)


def _koddaki_tablolar():
    adlar = {}
    for p in _kod_dosyalari():
        metin = p.read_text(encoding="utf-8", errors="replace")
        for d in _KOD_DESENLERI:
            for ad in d.findall(metin):
                adlar.setdefault(ad, p.relative_to(KOK).as_posix())
    return adlar


def _koddaki_rpcler():
    adlar = {}
    for p in _kod_dosyalari():
        for ad in re.findall(r"\.rpc\(\s*[\"']([a-z_][a-z0-9_]*)[\"']",
                             p.read_text(encoding="utf-8", errors="replace")):
            adlar.setdefault(ad, p.relative_to(KOK).as_posix())
    return adlar


# ─── 1) Kod ↔ şema ───────────────────────────────────────────────────────
def test_kodun_kullandigi_her_tablo_semada_tanimli():
    tanimli = _tanimlar(TEMEL)
    for p in _numarali():                      # 29_ ve sonrası (diğer işlerin yeni tabloları)
        tanimli |= _tanimlar(p)
    kod = _koddaki_tablolar()
    assert len(kod) >= 40, f"tarama bozuk: yalnız {len(kod)} tablo adı bulundu"
    eksik = {ad: yer for ad, yer in kod.items() if ad not in tanimli and ad not in BILINEN_EKSIK}
    assert not eksik, f"şemada tanımı olmayan tablolar (ad: ilk geçtiği dosya): {eksik}"


def test_bilinen_eksik_listesi_guncel():
    """Bilinen hata düzeltilince (ya da tablo eklenince) liste temizlensin."""
    kod = _koddaki_tablolar()
    tanimli = _tanimlar(TEMEL)
    assert BILINEN_EKSIK <= set(kod), f"artık kodda geçmiyor, listeden silin: {BILINEN_EKSIK - set(kod)}"
    assert not (BILINEN_EKSIK & tanimli)


def test_kodun_cagirdigi_fonksiyonlar_tanimli():
    tanimli = _tanimlar(TEMEL, _FONK)
    for p in _numarali():
        tanimli |= _tanimlar(p, _FONK)
    eksik = {ad: yer for ad, yer in _koddaki_rpcler().items() if ad not in tanimli}
    assert not eksik, eksik


def test_eski_dosyalarin_tablolari_temelde_var():
    """04_…28_ dosyalarının yarattığı her tablo/görünüm 00'da da var (00 eksiksiz)."""
    temel = _tanimlar(TEMEL)
    for p in _numarali(en_cok=28):
        eksik = _tanimlar(p) - temel
        assert not eksik, f"{p.name}: {eksik}"


def test_temel_sema_canli_sayilari():
    """Canlıdan çıkarılan nesne sayıları (14.10.2026): 68 tablo, 2 görünüm, 2 özet, 4 fonksiyon."""
    s = _yorumsuz(TEMEL.read_text(encoding="utf-8"))
    assert len(re.findall(r"CREATE TABLE IF NOT EXISTS public\.", s)) == 68
    assert len(re.findall(r"CREATE OR REPLACE VIEW public\.", s)) == 2
    assert len(re.findall(r"CREATE MATERIALIZED VIEW IF NOT EXISTS public\.", s)) == 2
    assert len(_FONK.findall(s)) == 4
    assert len(re.findall(r"CREATE OR REPLACE TRIGGER veri_surumu_trg", s)) == 9
    assert len(re.findall(r"FOREIGN KEY", s)) == 11
    for t in ("satislar", "urunler", "odemeler", "iadeler", "cekler", "edefter_fisler",
              "edefter_fis_satirlari", "audit_log", "kullanici_sifreler", "ithalat_dosyalari"):
        assert t in _tanimlar(TEMEL), t


# ─── 2) 00 tekrar çalıştırılabilir ve güvenli ────────────────────────────
def test_temel_sema_tekrar_calistirilabilir_yazilmis():
    ust = _govdesiz(_yorumsuz(TEMEL.read_text(encoding="utf-8")))
    komutlar = [k.strip() for k in ust.split(";") if k.strip()]
    for k in komutlar:
        bas = " ".join(k.split()[:4]).upper()
        if bas.startswith("CREATE TABLE") or bas.startswith("CREATE SEQUENCE") \
                or bas.startswith("CREATE INDEX") or bas.startswith("CREATE UNIQUE INDEX") \
                or bas.startswith("CREATE MATERIALIZED"):
            assert "IF NOT EXISTS" in k.upper(), k[:80]
        elif bas.startswith("CREATE"):
            assert bas.startswith("CREATE OR REPLACE"), k[:80]
        assert not re.match(r"(DROP|DELETE|TRUNCATE|UPDATE|INSERT)\b", k, re.I), k[:80]


def test_temel_semada_her_tablo_rls_listesinde():
    s = TEMEL.read_text(encoding="utf-8")
    tablolar = set(re.findall(r"CREATE TABLE IF NOT EXISTS public\.([a-z0-9_]+)", s))
    blok = s[s.index("DO $rls$"):s.index("$rls$;")]
    listede = set(re.findall(r"'([a-z0-9_]+)'", blok))
    assert tablolar == listede
    assert "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated" in s


def test_oneri_dosyasi_uygulanmaz():
    oneri = VT / "31_butunluk_onerisi.sql"
    assert U.oneri_mi(oneri)
    assert not U.oneri_mi(TEMEL)
    plan = U.plan_yap(U.dosyalari_bul(VT), {})
    durum = {a.dosya: a.durum for a in plan}
    assert durum["31_butunluk_onerisi.sql"] == U.ONERI
    assert durum["00_temel_sema.sql"] == U.UYGULANACAK
    assert [a.dosya for a in plan][0] == "00_temel_sema.sql"


# ─── 3) uygula.py sahte bağlantıyla ──────────────────────────────────────
class SahteImlec:
    def __init__(self, satirlar):
        self._s = satirlar

    def fetchone(self):
        return self._s[0] if self._s else None

    def fetchall(self):
        return list(self._s)


class SahteBaglanti:
    """sema_gecmisi'ni bellekte tutar; çalıştırılan dosya metinlerini kaydeder."""

    def __init__(self, gecmis=None, patlat=None):
        self.tablo_var = gecmis is not None
        self.gecmis = dict(gecmis or {})
        self.kayit_kim = {}
        self.calisan = []          # uygulanan SQL dosyası metinleri
        self.ddl = 0               # sema_gecmisi oluşturma sayısı
        self.patlat = patlat       # bu metni içeren SQL hata versin
        self.kapandi = False

    def execute(self, sql, params=None):
        if sql == U.GECMIS_VAR_MI:
            return SahteImlec([(self.tablo_var,)])
        if sql == U.GECMIS_OKU:
            assert self.tablo_var
            return SahteImlec(list(self.gecmis.items()))
        if sql == U.GECMIS_DDL:
            self.ddl += 1
            self.tablo_var = True
            return SahteImlec([])
        if sql == U.GECMIS_YAZ:
            dosya, sha, kim = params
            self.gecmis.setdefault(dosya, sha)
            self.kayit_kim[dosya] = kim
            return SahteImlec([])
        if self.patlat and self.patlat in sql:
            raise RuntimeError("sözdizimi hatası (sahte)")
        self.calisan.append(sql)
        return SahteImlec([])

    @contextlib.contextmanager
    def transaction(self):
        once = (dict(self.gecmis), list(self.calisan))
        try:
            yield
        except Exception:
            self.gecmis, self.calisan = once      # geri al
            raise

    def close(self):
        self.kapandi = True


@pytest.fixture
def klasor(tmp_path):
    (tmp_path / "00_temel.sql").write_text("-- temel\nSELECT 'T0';\n", encoding="utf-8")
    (tmp_path / "99_dokuz.sql").write_text("SELECT 'T99';\n", encoding="utf-8")
    (tmp_path / "100_yuz.sql").write_text("SELECT 'T100';\n", encoding="utf-8")
    (tmp_path / "05_bes.sql").write_text("SELECT 'T5';\n", encoding="utf-8")
    (tmp_path / "31_oneri.sql").write_text("-- UYGULA: HAYIR\nALTER TABLE x ADD y;\n", encoding="utf-8")
    (tmp_path / "BENIOKU.md").write_text("x", encoding="utf-8")
    (tmp_path / "taslak.sql").write_text("SELECT 'TASLAK';", encoding="utf-8")
    (tmp_path / "uygula.py").write_text("", encoding="utf-8")
    return tmp_path


def _calistir(klasor, argv, baglanti, url="postgresql://127.0.0.1:5432/deneme"):
    cikti, cagri = [], []

    def baglan(u):
        cagri.append(u)
        return baglanti
    ortam = {"DATABASE_URL": url} if url else {}
    kod = U.main(list(argv) + ["--klasor", str(klasor)], baglan=baglan, ortam=ortam, cikti=cikti.append)
    return kod, "\n".join(cikti), cagri


def test_sira_sayisal_ve_desene_uymayanlar_atlanir(klasor):
    adlar = [p.name for p in U.dosyalari_bul(klasor)]
    assert adlar == ["00_temel.sql", "05_bes.sql", "31_oneri.sql", "99_dokuz.sql", "100_yuz.sql"]


def test_kuru_kip_hicbir_sey_yazmaz(klasor):
    b = SahteBaglanti(gecmis=None)            # kayıt tablosu yok
    kod, cikti, cagri = _calistir(klasor, [], b)
    assert kod == 0 and cagri
    assert b.calisan == [] and b.ddl == 0 and b.gecmis == {} and not b.tablo_var
    assert "KURU" in cikti and "4 dosya uygulanmayı bekliyor" in cikti
    assert "öneri" in cikti and "31_oneri.sql" in cikti
    assert b.kapandi
    # açıkça --kuru da aynı
    kod, _, _ = _calistir(klasor, ["--kuru"], b)
    assert kod == 0 and b.calisan == [] and b.ddl == 0


def test_uygula_sirayla_calistirir_ve_kaydeder(klasor):
    b = SahteBaglanti(gecmis=None)
    kod, cikti, _ = _calistir(klasor, ["--uygula", "--uygulayan", "deneme"], b)
    assert kod == 0, cikti
    assert [re.search(r"'(T\d+)'", s).group(1) for s in b.calisan] == ["T0", "T5", "T99", "T100"]
    assert b.ddl == 1
    assert set(b.gecmis) == {"00_temel.sql", "05_bes.sql", "99_dokuz.sql", "100_yuz.sql"}
    assert b.gecmis["05_bes.sql"] == U.dosya_sha(klasor / "05_bes.sql")
    assert set(b.kayit_kim.values()) == {"deneme"}
    assert "31_oneri.sql" not in b.gecmis

    # ikinci çalıştırma: hepsi atlanır
    b.calisan.clear()
    kod, cikti, _ = _calistir(klasor, ["--uygula"], b)
    assert kod == 0 and b.calisan == [] and "Bitti: 0 dosya" in cikti


def test_yalniz_yeni_dosya_uygulanir(klasor):
    b = SahteBaglanti(gecmis={"00_temel.sql": U.dosya_sha(klasor / "00_temel.sql"),
                              "05_bes.sql": U.dosya_sha(klasor / "05_bes.sql")})
    kod, _, _ = _calistir(klasor, ["--uygula"], b)
    assert kod == 0
    assert [re.search(r"'(T\d+)'", s).group(1) for s in b.calisan] == ["T99", "T100"]


def test_sha_degismisse_uyarir_yeniden_uygulamaz(klasor):
    b = SahteBaglanti(gecmis={"05_bes.sql": "0" * 64})
    kod, cikti, _ = _calistir(klasor, ["--uygula"], b)
    assert kod == 0
    assert "UYARI: 05_bes.sql" in cikti and U.DEGISMIS in cikti
    assert not any("'T5'" in s for s in b.calisan)
    assert b.gecmis["05_bes.sql"] == "0" * 64          # kayıt ezilmez


def test_hata_veren_dosya_geri_alinir_sonrakiler_calismaz(klasor):
    b = SahteBaglanti(gecmis=None, patlat="'T99'")
    kod, cikti, _ = _calistir(klasor, ["--uygula"], b)
    assert kod == 1 and "HATA: 99_dokuz.sql" in cikti
    assert set(b.gecmis) == {"00_temel.sql", "05_bes.sql"}
    assert not any("'T100'" in s for s in b.calisan)


def test_isaretle_calistirmadan_kaydeder(klasor):
    b = SahteBaglanti(gecmis=None)
    kod, _, _ = _calistir(klasor, ["--uygula", "--isaretle", "--kadar", "5"], b)
    assert kod == 0
    assert b.calisan == []
    assert set(b.gecmis) == {"00_temel.sql", "05_bes.sql"}


@pytest.mark.parametrize("url", [
    "postgresql://postgres:x@db.qspwlqegoeudifxxrxcj.supabase.co:5432/postgres",
    "postgresql://postgres.qspwlqegoeudifxxrxcj:x@aws-0-eu-central-1.pooler.supabase.com:6543/postgres",
])
@pytest.mark.parametrize("argv", [[], ["--uygula"], ["--uygula", "--isaretle"]])
def test_canli_adres_canli_bayragi_olmadan_reddedilir(klasor, url, argv):
    b = SahteBaglanti(gecmis=None)
    kod, cikti, cagri = _calistir(klasor, argv, b, url=url)
    assert kod == 2 and cagri == [] and "DURDU" in cikti


def test_canli_bayragiyla_kuru_yine_yazmaz(klasor):
    b = SahteBaglanti(gecmis=None)
    kod, cikti, cagri = _calistir(klasor, ["--canli"], b,
                                  url="postgresql://x@db.qspwlqegoeudifxxrxcj.supabase.co/postgres")
    assert kod == 0 and cagri and "CANLI" in cikti
    assert b.calisan == [] and b.ddl == 0


def test_baglanti_yoksa_kuru_listeler_uygula_durur(klasor):
    kod, cikti, _ = _calistir(klasor, [], SahteBaglanti(), url=None)
    assert kod == 0 and "100_yuz.sql" in cikti
    kod, cikti, _ = _calistir(klasor, ["--uygula"], SahteBaglanti(), url=None)
    assert kod == 2 and "DURDU" in cikti


def test_canli_mi():
    assert U.canli_mi("postgresql://u@db.qspwlqegoeudifxxrxcj.supabase.co/postgres")
    assert not U.canli_mi("postgresql://postgres@127.0.0.1:5432/kayran")
    assert not U.canli_mi("")


# ─── 4) Gerçek boş Postgres (yalnız yerelde; CI'da atlanır) ──────────────
@pytest.mark.skipif(not os.environ.get("KAYRAN_TEST_PG") or not shutil.which("psql"),
                    reason="KAYRAN_TEST_PG (psql bağlantı dizesi) yok")
def test_bos_postgreste_sifirdan_kurulum():
    pg = os.environ["KAYRAN_TEST_PG"]
    ad = "sema_" + uuid.uuid4().hex[:8]

    def psql(*a, db=None):
        hedef = pg if db is None else re.sub(r"/[^/?]*(\?|$)", f"/{db}\\1", pg, count=1) \
            if "://" in pg else f"{pg} dbname={db}"
        return subprocess.run(["psql", hedef, "-v", "ON_ERROR_STOP=1", "-qAt", *a],
                              capture_output=True, text=True)
    assert psql("-c", f"create database {ad}").returncode == 0
    try:
        for f in [TEMEL, TEMEL, *_numarali()]:      # 00 iki kez: tekrar çalıştırılabilir
            r = psql("-f", str(f), db=ad)
            assert r.returncode == 0, (f.name, r.stderr)
        r = psql("-c", "select count(*) from pg_tables where schemaname='public' and rowsecurity", db=ad)
        assert int(r.stdout.strip()) >= 68
    finally:
        psql("-c", f"drop database if exists {ad}")
