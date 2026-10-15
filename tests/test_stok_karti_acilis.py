# -*- coding: utf-8 -*-
"""Stok kartı açılışı (Ekim 2026): tek kaynak + Ctrl+K penceresinde ürünler.

Kullanıcı bildirimi: "SKU açıkken başka bir kod aradığımızda pencere açılıp kapanıyor, bazen açmıyor."
Kök neden: kartı yedi yer kendi başına açıyordu; kart içinden geçiş yalnız Ürün Yönetimi'nde okunan bir
bayrağa (_stok_gec_sku) yazıyordu; paletten açılan kart parçacık içinde çiziliyordu. Artık açık kart oturumda
tek anahtarda, pencereyi yalnız app.py çizer."""
import ast
import sys
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))


def _anahtar(s):
    from shared.utils import sku_anahtar
    return sku_anahtar(s)


# ── Tek kaynak ──────────────────────────────────────────────────────
def test_ac_kapat_son_acilanlar(monkeypatch):
    import kayranpm.stok_karti as K
    ss = {}
    monkeypatch.setattr(K.st, "session_state", ss, raising=False)
    K.ac(" X24F182S ")
    K.ac("X27F182S")
    K.ac("X24F182S")
    assert K.acik_sku() == "X24F182S" and ss[K.SON_ANAHTAR] == ["X24F182S", "X27F182S"]
    K.kapat()
    assert K.acik_sku() is None and ss[K.SON_ANAHTAR] == ["X24F182S", "X27F182S"]


def test_kart_icinden_gecis_acik_karti_degistirir_kutu_sifirlanir(monkeypatch):
    """Eskiden seçim eski ürünün anahtarında kalıyordu (o ürün yeniden açılınca kart başka ürüne atlıyordu)."""
    import kayranpm.stok_karti as K
    ss = {K.ACIK_ANAHTAR: "X24F182S", "stok_gec_kutu": "X27F182S  ·  27\" 180HZ"}
    monkeypatch.setattr(K.st, "session_state", ss, raising=False)
    K._gec_sec("stok_gec_kutu", {"X27F182S  ·  27\" 180HZ": "X27F182S"})
    assert K.acik_sku() == "X27F182S" and ss["stok_gec_kutu"] is None


def test_karti_yalniz_tek_yer_cizer():
    """goster (pencere) yalnız stok_karti.acik_karti_ciz'den çağrılır; açan her yer ac / ac_ve_ciz der.
    Eski kod: yedi yer goster'i doğrudan çağırıyor, kart içi geçiş _stok_gec_sku bayrağına yazıyordu."""
    dogrudan, bayrak = [], []
    for p in KOK.rglob("*.py"):
        rel = p.relative_to(KOK).as_posix()
        if rel.startswith(("tests/", ".venv", "web/", "api/")) or "/." in rel:
            continue
        kod = p.read_text(encoding="utf-8")
        if "_stok_gec_sku" in kod.replace("# ", "") and "session_state" in kod and \
                any("_stok_gec_sku" in ln and not ln.lstrip().startswith("#") for ln in kod.splitlines()):
            bayrak.append(rel)
        try:
            agac = ast.parse(kod)
        except SyntaxError:
            continue
        for n in ast.walk(agac):
            if isinstance(n, ast.ImportFrom) and (n.module or "").endswith("stok_karti") and \
                    any(a.name == "goster" for a in n.names):
                dogrudan.append(rel)
    assert dogrudan == [], f"stok kartı penceresini doğrudan açan yer var: {dogrudan}"
    assert bayrak == [], f"eski geçiş bayrağı (_stok_gec_sku) kullanılıyor: {bayrak}"
    app = (KOK / "app.py").read_text(encoding="utf-8")
    assert "acik_karti_ciz()" in app
    k = (KOK / "kayranpm" / "stok_karti.py").read_text(encoding="utf-8")
    assert '@st.dialog("📦 Stok Kartı", width="large", on_dismiss=kapat)' in k   # X / Esc / dışarı tık → kapanır


def test_palet_kart_parcacik_icinde_acmaz():
    p = (KOK / "shared" / "palet.py").read_text(encoding="utf-8")
    g = p[p.index("def git(oge_id):"):p.index("@st.fragment")]
    assert "ac_ve_ciz(h[\"stok_karti\"])" in g and "goster(" not in g


# ── Ctrl+K penceresindeki ürün satırları ─────────────────────────────
def test_ozet_satirlari_kart_kurali():
    from kayranpm.stok_karti_palet import ozet_satirlari
    bugun = date(2026, 10, 15)
    urunler = [{"sku": "X24F167S", "urun_adi": "24\" 165Hz", "bizim_stok": 480},
               {"sku": "X27F182S", "urun_adi": "27\" 180Hz", "bizim_stok": 1480},
               {"sku": "F3ABQ", "urun_adi": "Kasa", "bizim_stok": 12},
               {"sku": "BOS", "urun_adi": "", "bizim_stok": 0},
               {"sku": "Mio MiVue J30", "urun_adi": "Kamera", "bizim_stok": 90}]
    satislar = [{"sku": "x24f167s", "adet": 900, "tarih": "2026-09-01"},
                {"sku": "X24F167S", "adet": 900, "tarih": "2026-07-01"},          # 90 günden eski: sayılmaz
                {"sku": "X27F182S", "adet": 90, "tarih": "2026-10-01"},
                {"sku": "MIO MIVUE J30", "adet": 9, "tarih": "2026-10-10"}]
    yolda = {"X27F182S": 500}
    r = {x["sku"]: x for x in ozet_satirlari(urunler, satislar, yolda, bugun, 135, _anahtar)}
    assert (r["X24F167S"]["gun"], r["X24F167S"]["durum"]) == (48, "siparis")      # 480 / (900/90)
    assert (r["X27F182S"]["gun"], r["X27F182S"]["durum"]) == (1480, "yeter")       # 1980 > 1 × 135
    assert (r["F3ABQ"]["gun"], r["F3ABQ"]["durum"]) == (None, "satissiz")
    assert r["BOS"]["durum"] == "yok"
    assert (r["Mio MiVue J30"]["gun"], r["Mio MiVue J30"]["durum"]) == (900, "yeter")   # SKU yazımından bağımsız


def test_palet_urun_kipi_ve_kutu():
    p = (KOK / "shared" / "palet.py").read_text(encoding="utf-8")
    assert '"urunler": urunler, "son": son' in p                      # ürünler tarayıcıya bir kez gider
    assert '"Son açılanlar"' in p and "Sipariş zamanı gelenler" in p and '"Ürünler · " + tr(ul.length) + " sonuç"' in p
    assert 'class="tetik"' in p                                         # üst şeritte "Stok kartı" düğmesi


# ── Görünüm: taslak "A"nın birebir değerleri (Ekim 2026) ──────────────
def _css():
    from shared import palet
    return palet._CSS.replace("\n", ""), ""


def test_pencere_taslak_degerleri():
    """Kullanıcı: "fontlar, renkler, her şey birebir aynı olsun". Eski pencere 620px, yuzey1 zemin, Inter,
    küçük harfli grup başlığı, düz satır vurgusuydu."""
    c, _ = _css()
    assert '--sk-govde:"Source Sans 3"' in c and '--sk-mono:"JetBrains Mono"' in c
    assert ".kutu{width:min(560px,100%)" in c and "background:var(--k-yuzey3)" in c and "border-radius:14px" in c
    assert "box-shadow:0 20px 50px -20px rgba(2,6,23,.7)" in c
    assert ".ust{display:flex;align-items:center;gap:10px;padding:13px 14px" in c
    assert ".grup{font-size:11px;letter-spacing:.08em;text-transform:uppercase" in c
    assert ".og{display:grid;grid-template-columns:auto minmax(0,1fr) auto auto;gap:10px;align-items:center;padding:7px 8px" in c
    assert ".og.s{background:color-mix(in srgb,var(--k-mor) 14%,transparent);outline:1px solid color-mix(in srgb,var(--k-mor) 35%,transparent)}" in c
    assert ".cip{font-size:11.5px;font-weight:600;padding:1px 7px;border-radius:999px" in c
    assert ".sku{font-family:var(--sk-mono);font-weight:500;font-size:12.5px" in c
    assert "border-bottom-width:2px" in c                                        # tuş çipleri
    assert ".tetik{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--k-kenar2);border-radius:999px;" in c
    assert "padding:5px 10px 5px 8px" in c and "background:var(--k-yuzey2)" in c


def test_fontlar_ve_surum_yenileme():
    """Eski sürümün düğmesi tarayıcıda kalıyordu (yalnız ilk çizimde kuruluyordu): yeni düğme görünmedi."""
    from shared import palet
    for js in (palet._JS,):
        assert "fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&family=JetBrains+Mono:wght@500" in js
        assert "//FONT//" not in js and "//SVG//" not in js
    assert 'if (P.kok && P.surum !== SURUM){ try { P.kok.remove(); } catch (e) {} P.kok = null; }' in palet._JS
    assert 'lang="tr"' in palet._JS                                        # BÜYÜK HARF Türkçe (i → İ)
    assert "kartı aç" in palet._JS and "yeni sekmede" in palet._JS and 'u.searchParams.set("kart", o.sku)' in palet._JS


def test_yeni_sekme_adresi_karti_acar(monkeypatch):
    import kayranpm.stok_karti as K

    class _Q(dict):
        def get(self, k, v=None):
            return dict.get(self, k, v)
    ss, q = {}, _Q(kart="X24F182S", s="satis")
    monkeypatch.setattr(K.st, "session_state", ss, raising=False)
    monkeypatch.setattr(K.st, "query_params", q, raising=False)
    monkeypatch.setattr(K, "goster", lambda *a, **k: None)
    K.acik_karti_ciz()
    assert K.acik_sku() == "X24F182S" and "kart" not in q and q["s"] == "satis"
