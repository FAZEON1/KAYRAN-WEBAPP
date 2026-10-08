# -*- coding: utf-8 -*-
"""Aşama 4 · Açık/koyu tema — altyapı ve renklerin temaya taşınması."""
import glob
import re
import sys
import types
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from shared import tasarim as T  # noqa: E402


def _oku(p):
    return (KOK / p).read_text(encoding="utf-8")


def _sahte_st(tema):
    st = types.ModuleType("streamlit")
    st.session_state = {"tema": tema}
    return st


def test_renk_sozlugu_temaya_gore_cevap_verir(monkeypatch):
    monkeypatch.setitem(sys.modules, "streamlit", _sahte_st("koyu"))
    assert T.RENK["metin"] == "#E2E8F0" and T.renk("metin") == "#E2E8F0"
    monkeypatch.setitem(sys.modules, "streamlit", _sahte_st("acik"))
    assert T.RENK["metin"] == "#0F172A" and T.renk("metin") == "#0F172A"
    assert T.RENK.get("yok", "-") == "-"
    # ham palet (items) her zaman koyu — tema_degiskenleri bunu bekler
    assert dict(T.RENK.items())["metin"] == "#E2E8F0"
    assert T.aktif_tema() == "acik"
    assert "--k-metin:#0F172A" in T.cekirdek_css()


def test_ikinci_tasarim_dosyasi_yok():
    """shared/ui.py tasarim.py'ye katıldı (Eki 2026); renk ve bileşen tek kaynaktan."""
    assert not (KOK / "shared" / "ui.py").exists()
    kaynaklar = [p for p in KOK.rglob("*.py") if ".venv" not in p.parts and "tests" not in p.parts]
    assert not [p for p in kaynaklar if re.search(r"from shared\.ui import|from shared import ui\b", p.read_text(encoding="utf-8"))]


def test_karisim():
    assert T.karisim("mor", 15) == "color-mix(in srgb,var(--k-mor) 15%,transparent)"


def test_config_acik_tema_paletle_ayni():
    import tomllib
    cfg = tomllib.loads(_oku(".streamlit/config.toml"))
    acik = cfg["theme"]["light"]
    assert acik["backgroundColor"].upper() == T.RENK_ACIK["yuzey0"].upper()
    assert acik["secondaryBackgroundColor"].upper() == T.RENK_ACIK["yuzey1"].upper()
    assert acik["textColor"].upper() == T.RENK_ACIK["metin"].upper()
    assert acik["primaryColor"].upper() == T.RENK_ACIK["mor"].upper()
    assert cfg["theme"]["base"] == "dark"                 # varsayılan koyu kalır


def test_tema_secimi_bagli():
    src = _oku("app.py")
    # Seçici her çizimde güncel temayı gösterir; değişiklik on_change ile yazılır (menü iki yerde çizilir)
    assert 'st.segmented_control("Görünüm", ["Koyu", "Açık"], key=_tema_anahtar, on_change=_tema_degis' in src
    assert 'st.session_state[_tema_anahtar] = "Açık" if _aktif_tema() == "acik" else "Koyu"' in src
    assert "stActiveTheme-'+w.location.pathname+'-v2'" in src   # Streamlit tarafı eşitlenir
    assert "from shared.tercih import tema_oku" in src
    assert 'w.localStorage.removeItem("kayran-tema")' not in src  # eski temizlik kaldırıldı
    assert (KOK / "veritabani" / "06_kullanici_tercih.sql").exists()


def test_tercih_tablo_yokken_cokmez():
    from shared import tercih
    assert tercih.tema_oku("") == "koyu"
    assert tercih.tema_yaz("", "acik") is False
    assert tercih.tema_yaz("x", "mavi") is False


EKRAN_HARIC = {"shared/tasarim.py", "kayranacc/bildirim.py", "kayranacc/rapor.py", "kayranpm/rapor.py",
               "kayranacc/excel_islemler.py", "kayranpm/excel_islemler.py", "kayranacc/aktif_excel.py",
               "depo/belge.py", "teknikservis/irsaliye.py", "teknikservis/database.py",
               "telegram_brifing.py", "gunluk.py", "migrate_passwords.py"}


def _ekran_dosyalari():
    for f in glob.glob(str(KOK / "**" / "*.py"), recursive=True):
        r = str(Path(f).relative_to(KOK)).replace("\\", "/")
        if r.split("/")[0] in ("tests", "bekleyen", "otonom", "deploy") or r in EKRAN_HARIC:
            continue
        yield r


def test_sabit_renkler_geri_gelmedi():
    """Ekran dosyalarındaki sabit renk kodu sayısı düşürüldü (1.750 → ~60).
    Kalanlar (97): varsayılan parametreler, modül sabitleri (RENK paleti,
    KART_PALET), marka gradyanları, e-posta ve JS içindekiler.
    Yeni kod var(--k-…) / trenk("…") / RENK["…"] kullanmalı."""
    n = sum(len(re.findall(r"#[0-9A-Fa-f]{6}(?![0-9A-Za-z_])", _oku(f))) for f in _ekran_dosyalari())
    assert n <= 100, n


def test_svg_ozniteliginde_degisken_yok():
    """SVG fill/stroke ÖZNİTELİĞİ var() anlamaz; style içinde olmalı."""
    for f in _ekran_dosyalari():
        assert not re.search(r'(fill|stroke|stop-color)="var\(', _oku(f)), f
        assert not re.search(r'(fill|stroke|stop-color)=trenk\(', _oku(f)), f


def test_trenk_takma_adi_golgelenmiyor():
    """renk() 'trenk' adıyla alınır; modüllerde 'renk' yerel değişkeni çok."""
    for f in _ekran_dosyalari():
        s = _oku(f)
        if re.search(r'trenk\("[a-z0-9]+"\)', s):
            assert "import renk as trenk" in s, f
            assert not re.search(r"^\s*trenk\s*=", s, re.M), f
