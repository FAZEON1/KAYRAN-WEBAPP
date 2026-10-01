# -*- coding: utf-8 -*-
"""D3 (renk/ikon/grafik) + D4 (tablolar) — geri alınmasınlar diye."""
import ast
import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from shared.tasarim import (GRAFIK_PALET, EMOJI_IKON, menu_etiketi,  # noqa: E402
                            urun_etiketi)
from shared.utils import firma_kisa_ad  # noqa: E402


def _oku(p):
    return (KOK / p).read_text(encoding="utf-8")


# ── D4 · ürün etiketi ────────────────────────────────────────────────
def test_urun_etiketi_sku_her_zaman_gorunur():
    uzun = "FAZEON F14 PLUS 14 INÇ DİZÜSTÜ BİLGİSAYAR İNTEL CORE 16GB 512GB SSD GRİ"
    a = urun_etiketi(uzun, "F14P-512G")
    b = urun_etiketi(uzun.replace("GRİ", "SİYAH"), "F14P-512S")
    assert "F14P-512G" in a and "F14P-512S" in b
    assert a != b                          # iki satır artık ayırt edilir
    assert uzun in a                       # ad Python'da KESİLMİYOR (CSS kısaltır)
    assert "text-overflow:ellipsis" in a and "title=" in a


def test_urun_etiketi_html_kacirir():
    h = urun_etiketi('<b>"X"</b>', "S<1>")
    assert "<b>" not in h and "S&lt;1&gt;" in h


def test_acil_siparis_listesi_urun_etiketi_kullanir():
    src = _oku("kayranpm/main.py")
    bas = src.index("acil_items_list = []")
    govde = src[bas:src.index("st.markdown(pencere_grid(", bas)]
    assert govde.count("urun_etiketi(") == 2
    assert "[:46]" not in govde


# ── D4 · firma adları ────────────────────────────────────────────────
def test_firma_kisa_ad():
    assert firma_kisa_ad("EERA BİLGİSAYAR SANAYİ VE TİCARET LİMİTED ŞİRKETİ USD") == "EERA BİLGİSAYAR · USD"
    assert firma_kisa_ad("D-MARKET ELEKTRONİK HİZMETLER VE TİCARET A.Ş.") == "D-MARKET ELEKTRONİK HİZMETLER"
    assert firma_kisa_ad("VATAN BİLGİSAYAR SAN. VE TİC. A.Ş. (TL)") == "VATAN BİLGİSAYAR · TL"
    assert firma_kisa_ad("MONDAY") == "MONDAY"
    assert firma_kisa_ad("") == ""


def test_firma_eslestirme_tam_ad_kullanir():
    """Kampanya şablonundaki firma adı TAM cari adıyla eşleştirilir;
    kısa ad kullanılırsa eşleşme sessizce bozulur."""
    # Excel şablonu akışı Ekim 2026'da kayranpm/kampanya.py'ye taşındı (birebir)
    assert "firma_gorunen_ad(_c, kisa=False)" in _oku("kayranpm/kampanya.py")


# ── D3 · grafik renkleri ─────────────────────────────────────────────
def test_grafik_paleti_tekrarsiz():
    assert len(GRAFIK_PALET) == len(set(p.upper() for p in GRAFIK_PALET)) >= 13


def test_muhasebe_kategorileri_farkli_renkte():
    src = _oku("kayranacc/main.py")
    bas = src.index("    KATEGORILER = {")
    blok = src[bas:src.index("    }\n", bas)]
    idx = re.findall(r'"renk":\s*_GP\[(\d+)\]', blok)
    assert len(idx) == 13 and len(set(idx)) == 13


def test_odeme_durumu_halkasi_tutarla_tutarli():
    """Halka tutara göre çizilir; ortadaki yüzde de tutar olmalı
    (eskiden adetti: halka yarı doluyken ortada %0 yazıyordu)."""
    src = _oku("kayranacc/main.py")
    assert "ÖDENEN (TUTAR)" in src
    assert "_odenen_pct = round(odendi_tutar / _durum_toplam * 100)" in src
    assert "TAMAMLANAN</span>" not in src


def test_dusuk_kontrastli_gri_geri_gelmedi():
    """Koyu zeminde okunmayan griler (#64748B vb.) ekran dosyalarından
    kaldırıldı; tasarım tonları #7B8AA0 / #94A3B8 kullanılır."""
    ekran = ["app.py", "yonetim.py", "hesap_makinesi/main.py", "ithalat/main.py",
             "kayranacc/main.py", "kayranpm/main.py", "kayranpm/ref_no.py",
             "kayranpm/stok_karti.py", "satis/main.py", "shared/kar_gizle.py",
             "shared/ui.py", "teknikservis/main.py", "depo/main.py"]
    for p in ekran:
        bul = re.findall(r"#(64748B|6B7280|7C8AA0|8B97A8|8B98B8)\b", _oku(p), re.I)
        assert not bul, f"{p}: {bul}"


# ── D3 · menü ikon dili ──────────────────────────────────────────────
MENU_DOSYALARI = ["depo/main.py", "kayranacc/main.py", "kayranpm/main.py",
                  "satis/main.py", "ithalat/main.py", "teknikservis/main.py"]


def test_sidebar_menuleri_ikon_dili_kullanir():
    for p in MENU_DOSYALARI:
        src = _oku(p)
        assert "format_func=_me" in src and "menu_etiketi as _me" in src, p


def _menu_secenekleri(src):
    """Dosyadaki sidebar sayfa listelerinin seçenek metinleri."""
    agac = ast.parse(src)
    listeler = []
    for n in ast.walk(agac):
        if (isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "radio"
                and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == "Sayfa"
                and len(n.args) > 1 and isinstance(n.args[1], ast.List)):
            listeler.append(n.args[1])
        hedef = getattr(n, "targets", None) or ([n.target] if isinstance(n, ast.AugAssign) else [])
        if any(getattr(t, "id", "") in ("tum_sayfalar", "_sayfalar") for t in hedef) \
                and isinstance(n.value, ast.List):
            listeler.append(n.value)
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "append" \
                and getattr(n.func.value, "id", "") == "_sayfalar":
            listeler.append(ast.List(elts=n.args))
    return [e.value for l in listeler for e in l.elts
            if isinstance(e, ast.Constant) and isinstance(e.value, str)]


def test_tum_menu_emojileri_ikona_donusur():
    """Menülerdeki her seçeneğin emojisi EMOJI_IKON'da olmalı; yoksa ikon
    yerine çıplak metin görünür ve menü karışık durur."""
    toplam = 0
    for p in MENU_DOSYALARI:
        secenekler = _menu_secenekleri(_oku(p))
        assert secenekler, f"{p}: sayfa listesi bulunamadı"
        for sec in secenekler:
            assert menu_etiketi(sec).startswith(":material/"), (p, sec)
        toplam += len(secenekler)
    assert toplam >= 40
    assert menu_etiketi("↩️  İade") == ":material/undo: İade"
    assert menu_etiketi("⭐ Bilinmeyen") == "Bilinmeyen"


def test_hesap_dugmeleri_material_ikon():
    src = _oku("app.py")
    for ik in (":material/key:", ":material/group:", ":material/receipt_long:"):
        assert ik in src
    assert '"🔑 Şifremi Değiştir"' not in src


def test_menu_ikonlari_yazi_tipi_ezilmiyor():
    """Muhasebe sidebar'ı her öğeye Inter dayatıyor; :material/..: ikonları
    için daha özgül bir istisna olmazsa ikon yerine 'dashboard' gibi düz
    metin görünür (canlıda yaşandı)."""
    src = _oku("app.py")
    assert 'html body span[translate="no"][aria-label$=" icon"]' in src
    kural = src[src.index('html body span[translate="no"]'):]
    assert 'Material Symbols Rounded' in kural[:600]


def test_dugmelerde_emoji_yok():
    """Sayfa içindeki düğmeler tek ikon dilinde: emoji yerine icon=":material/..:".
    Ok/kapat işaretleri (◀ ▶ ‹ › ✕) tipografik sayılır, serbest.
    ` (Markdown satır içi kod — SKU'yu mono göstermek için) emoji değil, serbest."""
    import glob as _g
    bas = re.compile(r"\.(?:button|form_submit_button|download_button)\(\s*f?([\"'])([^\"']*)\1")
    kotu = []
    for f in _g.glob(str(KOK / "**" / "*.py"), recursive=True):
        if any(p in f.replace("\\", "/") for p in ("/tests/", "/bekleyen/", "/otonom/", "/deploy/")):
            continue
        for m in bas.finditer(open(f, encoding="utf-8").read()):
            et = m.group(2)
            if et and not (et[0].isalnum() or et[0] in " ←→✓✖-+%$₺#.◀▶‹›✕({“‘«`"):
                kotu.append(f"{Path(f).relative_to(KOK)}: {et[:30]}")
    assert not kotu, kotu[:10]
