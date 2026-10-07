# -*- coding: utf-8 -*-
"""Ortak ekran bileşenleri (modül yenileme projesi, Adım 0).

Kampanya Takip ve Ref No'da aynı kalıplar (tamamı tıklanan kart/satır, filtre
düğmesi, ay başlığı, çip, onaylı silme, detay penceresi akışı) ayrı ayrı
yazılmıştı. Artık shared/bilesen.py + tasarim.ORTAK_BILESEN_CSS tek kaynak;
yenilenen her sayfa bunları kullanır.
"""
import ast
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
YENI = ["kayranpm/kampanya.py", "kayranpm/ref_ekran.py"]


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


def test_bilesenler_tanimli():
    agac = ast.parse(_oku("shared/bilesen.py"))
    adlar = {n.name for n in agac.body if isinstance(n, ast.FunctionDef)}
    assert {"tiklanir", "baslik_eylem", "filtre", "grup_basligi", "cip", "meta", "onayli_sil",
            "detay_ac", "detay_istendi", "yenile"} <= adlar


def test_ortak_css_cekirdekte():
    src = _oku("shared/tasarim.py")
    assert "ORTAK_BILESEN_CSS" in src.split("def cekirdek_css", 1)[1]
    for sinif in ('st-key-tk_kart_', 'st-key-tk_satir_', 'st-key-tk_ray_', ".k-grup", ".k-cip", ".k-meta"):
        assert sinif in src, sinif


def test_yeni_ekranlar_ortak_bilesen_kullanir_kopya_css_yok():
    for y in YENI:
        src = _oku(y)
        assert "from shared import bilesen as B" in src and "B.tiklanir(" in src, y
        assert "B.filtre(" in src and "B.onayli_sil(" in src and "B.detay_istendi(" in src, y
        # Tıklanır kap kuralı (görünmez düğmeyi kaba yayan) artık sayfada tekrar yazılmaz
        assert "position:absolute !important;inset:0" not in src, y
        assert ".popover(f\"Filtre" not in src, y


def test_onayli_sil_dugmesi_kirmizi_anahtar():
    """DUGME_CSS anahtarında '_sil' geçen düğmeyi kırmızı çizer."""
    src = _oku("shared/bilesen.py")
    assert 'key=f"{key}_sil"' in src and "disabled=not onay" in src


def test_ipuclu_dugmeler_de_ortak_stili_alir():
    """help= verilen düğme bir ipucu kabına sarılır; '> button' ona ulaşmıyordu
    (birincil düğmeler dolgusuz görünüyordu). Seçici alt öğeyi de kapsar ve ona
    bağlı özel kurallar en az aynı özgüllükte, SONRA yazılır."""
    src = _oku("shared/tasarim.py")
    d = src[src.index("_D = ("):src.index("_SIL = (")]
    assert 'button[data-testid^="stBaseButton"]' in d and "> button" not in d.split("')")[0][-30:]
    # Tıklanır kap kuralı ORTAK_BILESEN_CSS'te, DUGME_CSS'ten sonra basılır
    cek = src.split("def cekirdek_css", 1)[1]
    assert cek.index("DUGME_CSS") < cek.index("ORTAK_BILESEN_CSS")
    # Dönem seçicinin okları da help= taşır (ipucu kabına sarılı): kuralı alt öğe seçicisiyle,
    # _D'den yüksek özgüllükle ORTAK_BILESEN_CSS'te (Ekim 2026: [‹][dönem ▾][›] tek parça grup)
    assert ':is(.stButton,.stPopover) button[data-testid][data-testid]' in src
    assert '[class*="st-key-k_donem_"][class*="st-key-k_donem_"][class*="st-key-k_donem_"]' in src
