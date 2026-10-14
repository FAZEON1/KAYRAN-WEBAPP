# -*- coding: utf-8 -*-
"""Ürün yüzü ve paketleme (Ekim 2026): "bitmemiş ürün" izlenimi veren ekran metinleri kalktı,
sürüm tek kaynakta, README / CHANGELOG / pyproject / requirements.lock var, tek seferlik betikler
araclar/ altında. İşlev ve rakamlar değişmedi — burada yalnız yüz ve paket denetlenir."""
import ast
import re
import tomllib
from pathlib import Path

from shared import gezinme as G

KOK = Path(__file__).resolve().parent.parent


def _oku(p):
    return (KOK / p).read_text(encoding="utf-8")


def _ekran_metinleri(dosya):
    """Dosyadaki docstring olmayan string sabitleri (ekrana gidebilecek metin) — tek metin."""
    t = ast.parse(_oku(dosya))
    doc = set()
    for n in ast.walk(t):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and n.body \
                and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant):
            doc.add(id(n.body[0].value))
    return "\n".join(n.value for n in ast.walk(t)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc)


# ── 1) Eski KAYRANTS&W "YAKINDA SİZLERLE" sayfası → var olan modüllere yönlendirme ──────────
def _fonksiyon(ad):
    t = ast.parse(_oku("app.py"))
    return next(n for n in t.body if isinstance(n, ast.FunctionDef) and n.name == ad)


class _Kol:
    def __init__(self, kayit):
        self.kayit = kayit

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def button(self, etiket, **kw):
        self.kayit.append((etiket, kw.get("on_click"), kw.get("args")))
        return False


class _St:
    def __init__(self):
        self.metin, self.dugmeler, self.session_state = [], [], {"aktif_kullanici": "ali"}

    def markdown(self, m, **_k):
        self.metin.append(m)

    def columns(self, n, **_k):
        return [_Kol(self.dugmeler) for _ in range(n if isinstance(n, int) else len(n))]

    def button(self, etiket, **kw):
        self.dugmeler.append((etiket, kw.get("on_click"), kw.get("args")))
        return False

    def rerun(self):
        pass


def _yakinda_calistir(yetkiler):
    fn = _fonksiyon("kayrantsw_yakinda")
    st = _St()

    def _git(*a):
        pass
    ns = {"st": st, "k_mesaj": lambda tur, m: f"<{tur}>{m}", "portal_css": lambda: "",
          "kullanici_yetkileri": lambda k: dict(yetkiler), "_sayfaya_git": _git}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "app.py", "exec"), ns)
    ns["kayrantsw_yakinda"]()
    return st, _git


def test_yakinda_sayfasi_yok():
    a = _oku("app.py")
    assert "YAKINDA SİZLERLE</span>" not in a and "takipte kalın" not in a


def test_eski_tsw_adresi_modullere_yonlendirir():
    st, git = _yakinda_calistir({"depo": True, "teknikservis": True})
    hedefler = [(e, args) for e, oc, args in st.dugmeler if oc is git]
    assert hedefler == [("Depo", ("depo",)), ("Teknik servis", ("teknikservis",)), ("Ana sayfa", ("anasayfa",))]
    assert "yakında" not in " ".join(st.metin).lower()


def test_eski_tsw_adresi_yetkisiz_modulu_gostermez():
    st, git = _yakinda_calistir({"depo": False, "teknikservis": True})
    assert [args for _e, oc, args in st.dugmeler if oc is git] == [("teknikservis",), ("anasayfa",)]


# ── 2) e-Defter: iç faz dili yok, mali mühür açıklaması var ─────────────────────────────────
def test_edefter_ekraninda_faz_dili_yok():
    m = _ekran_metinleri("kayranacc/edefter.py")
    assert not re.search(r"Faz \d", m), re.findall(r".{0,40}Faz \d.{0,40}", m)
    assert "(aktif)" not in m
    assert "GİB'e yükleme için mali mühür gerekir" in m


# ── 3) Geliştirici sayfaları yalnız yöneticiye ──────────────────────────────────────────────
GELISTIRICI = ("tasarim_rehberi", "sistem_kayitlari", "degisiklik_gunlugu", "yedekleme")


def test_gelistirici_sayfalari_yetkiye_bagli():
    oz = {k: o for k, _a, _i, o in G.SISTEM}
    for k in GELISTIRICI:
        assert oz[k] == "kullanici_yonetimi", k


def test_paletin_gelistirici_sayfalarini_yalniz_yonetici_gorur():
    def ids(ozel):
        return {o["id"] for o in G.palet_ogeleri({"satis": True}, ozel, "ali", lambda *_: True)}
    normal, yonetici = ids(set()), ids({"kullanici_yonetimi"})
    for k in GELISTIRICI:
        assert f"sistem/{k}" not in normal and f"sistem/{k}" in yonetici, k
    assert "sistem/sifre_degistir" in normal


def test_kisi_menusunde_sistem_grubu_yonetici_kosullu():
    a = _oku("app.py")
    menu = a[a.index("def _kisi_menu_icerik("):a.index("def _arama_kutusu(")]
    assert '    if _yonetici:\n        _grup_dugmesi("Sistem")' in menu
    # sayfanın kendisi de yetki ister (adresle açılsa bile)
    rehber = a[a.index('elif aktif == "tasarim_rehberi":'):][:300]
    kayit = a[a.index("def sistem_kayitlari("):][:400]
    for govde in (rehber, kayit):
        assert 'ozel_yetki(' in govde and '"kullanici_yonetimi"' in govde


def test_sayfa_testi_listesi_degismedi():
    """tests/duman sayfa listesini MODULLER + SISTEM'den alır; geliştirici sayfaları listede kalır."""
    kodlar = {k for k, *_ in G.SISTEM}
    assert set(GELISTIRICI) <= kodlar


# ── 4) Bağlantı hatası mesajı: doğru ve sakin ───────────────────────────────────────────────
def test_baglanti_hatasi_metni():
    a = _oku("app.py")
    blok = a[a.index('if not st.session_state.get("_db_saglik_ok"):'):]
    blok = blok[:blok.index('st.session_state.pop("_db_saglik_ok", None)')]
    assert "uyku" not in blok.lower() and "Streamlit Cloud" not in blok
    assert "Veritabanına şu an ulaşılamıyor" in blok and "Birkaç saniye sonra" in blok
    assert 'button("Yeniden Dene"' in blok and "db_yeniden_baglan" in blok


# ── 5) Sürüm tek kaynak ─────────────────────────────────────────────────────────────────────
def test_surum_tek_kaynak():
    from shared.surum import SURUM, surum_etiketi
    assert re.fullmatch(r"\d+\.\d+\.\d+", SURUM)
    assert surum_etiketi() == f"Sürüm {SURUM}"
    py = tomllib.loads(_oku("pyproject.toml"))
    assert py["project"]["version"] == SURUM
    ilk = next(s for s in _oku("CHANGELOG.md").splitlines() if s.startswith("## ["))
    assert ilk.startswith(f"## [{SURUM}]")


def test_surum_ekranda():
    a = _oku("app.py")
    alt = a[a.index('<div class="k-ana-alt">') - 300:a.index('<div class="k-ana-alt">') + 300]
    assert "surum_etiketi" in alt and "_surum_etiketi()" in alt


# ── 6) Paket dosyaları ──────────────────────────────────────────────────────────────────────
def test_readme():
    r = _oku("README.md")
    for parca in ("veritabani/BENIOKU.md", "python -m pytest -q", "pytest duman", "[supabase]",
                  "CHANGELOG.md", "streamlit run app.py"):
        assert parca in r, parca
    # sır yok: anahtar adları var, değer yok
    assert not re.search(r"eyJ[A-Za-z0-9_-]{10,}|https://[a-z0-9]+\.supabase\.co|pbkdf2:sha256:\d", r)


def test_pyproject_ruff_dar_ve_ci_disinda():
    py = tomllib.loads(_oku("pyproject.toml"))
    assert py["tool"]["ruff"]["lint"]["select"] == ["F"]
    assert "build-system" not in py                       # paket olarak kurulmaz
    assert "pytest" not in py.get("tool", {})             # CI'daki pytest toplaması değişmez
    for f in py["tool"]["ruff"]["lint"]["per-file-ignores"]:
        assert (KOK / f).exists(), f
    assert "ruff" not in _oku(".github/workflows/testler.yml")


def test_requirements_lock_her_paketi_sabitler():
    istek = [re.split(r"[<>=!~ ;#\[]", s.strip(), maxsplit=1)[0].lower()
             for s in _oku("requirements.txt").splitlines() if s.strip() and not s.startswith("#")]
    kilit = {s.split("==")[0].strip().lower(): s.split("==")[1].split()[0]
             for s in _oku("requirements.lock").splitlines() if "==" in s and not s.startswith("#")}
    for p in istek:
        assert p in kilit, p


def test_requirements_lock_araliklara_uyar():
    from packaging.requirements import Requirement
    kilit = {s.split("==")[0].strip().lower(): s.split("==")[1].split()[0]
             for s in _oku("requirements.lock").splitlines() if "==" in s and not s.startswith("#")}
    for s in _oku("requirements.txt").splitlines():
        s = s.split("#")[0].strip()
        if not s:
            continue
        r = Requirement(s)
        assert r.specifier.contains(kilit[r.name.lower()], prereleases=True), (r, kilit[r.name.lower()])


# ── 7) Kök temizliği ────────────────────────────────────────────────────────────────────────
def test_tek_seferlik_betikler_araclarda():
    for ad in ("migrate_passwords.py", "ref_kalem_doldur.sql"):
        assert not (KOK / ad).exists(), ad
        assert (KOK / "araclar" / ad).exists(), ad
    m = _oku("araclar/migrate_passwords.py")
    assert "os.path.dirname(os.path.dirname(os.path.abspath(__file__)))" in m   # proje kökü yolda
    wf = "".join(p.read_text(encoding="utf-8") for p in (KOK / ".github" / "workflows").glob("*.yml"))
    assert "migrate_passwords" not in wf and "ref_kalem_doldur" not in wf
