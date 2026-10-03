# -*- coding: utf-8 -*-
"""Sayı kartları — tek görünüm, renk yalnız anlam taşıdığında (Ekim 2026)."""
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _t():
    from shared import tasarim
    return tasarim


# ── Renk → anlam ────────────────────────────────────────────────────
def test_renk_anlama_coz():
    T = _t()
    assert T.kart_anlami("kirmizi") == "kotu"
    assert T.kart_anlami(T.RENK["kirmizi"]) == "kotu"           # trenk("kirmizi") hex'i
    assert T.kart_anlami("#EF4444") == "kotu"                   # eski sabit hex
    for r in ("mor", "yesil", "amber", "cyan", "mavi", T.RENK["yesil"], "#10B981", None, ""):
        assert T.kart_anlami(r) is None, r


def test_acik_tema_hexi_de_cozulur():
    T = _t()
    assert T.kart_anlami(T.TEMALAR["acik"]["kirmizi"]) == "kotu"


# ── Değişim rozeti ──────────────────────────────────────────────────
def test_degisim_rozeti():
    T = _t()
    assert T.degisim_rozeti(3, 5) == ("▼ %40,0", "kotu")
    assert T.degisim_rozeti(6, 5) == ("▲ %20,0", "iyi")
    assert T.degisim_rozeti(6, 5, artis_iyi=False) == ("▲ %20,0", "kotu")   # gider artışı
    assert T.degisim_rozeti(5, 5) == ("■ %0,0", None)
    assert T.degisim_rozeti(5, 0) is None and T.degisim_rozeti(5, None) is None


# ── Kart HTML'i ─────────────────────────────────────────────────────
def test_renk_degere_boyanmaz_serit_yok():
    T = _t()
    h = T.kart_hucresi({"etiket": "Stok değeri", "deger": "$1.200", "renk": "amber"})
    assert "border-left-color" not in h and "color:var(--k-amber)" not in h
    assert 'class="k-kart k-yeni"' in h


def test_kirmizi_kotu_anlami_tasir():
    T = _t()
    h = T.kart_hucresi({"etiket": "Gecikmiş", "deger": "4", "renk": "kirmizi"})
    assert "k-kotu" in h


def test_acik_anlam_onceligi():
    T = _t()
    h = T.kart_hucresi({"etiket": "Net kâr", "deger": "$5", "renk": "kirmizi", "anlam": "iyi"})
    assert "k-iyi" in h and "k-kotu" not in h


def test_vurgu_rozet_ve_spark():
    T = _t()
    h = T.kart_hucresi({"etiket": "Haftalık satış", "deger": "3", "vurgu": True,
                        "simdi": 3, "onceki": 5, "seri": [4, 6, 5, 3]})
    assert "k-vurgu" in h and "▼ %40,0" in h and "k-rozet k-kotu" in h and "<svg" in h


def test_etiket_cumle_duzeni_ve_kacis():
    T = _t()
    h = T.kart_hucresi({"etiket": "TOPLAM STOK", "deger": "<b>9</b>"})
    assert "Toplam stok" in h                     # kpi_etiketi: BÜYÜK HARF → cümle düzeni
    assert "<b>9</b>" in h                         # değer HTML olabilir (eski sözleşme), kaçışlanmaz


def test_spark_bos_seride_cizilmez():
    T = _t()
    assert T.spark_svg([]) == "" and T.spark_svg([5]) == ""
    assert T.spark_svg([1, 2, 3]).startswith("<svg")


# ── Bağlantılar ─────────────────────────────────────────────────────
def test_geri_alma_anahtari_tek_satir():
    src = (KOK / "shared" / "tasarim.py").read_text(encoding="utf-8")
    assert len(re.findall(r"^KART_YENI = (True|False)\s", src, re.M)) == 1


def test_ortak_kartlar_yeni_hucreyi_kullanir():
    u = (KOK / "shared" / "utils.py").read_text(encoding="utf-8")
    g = u[u.index("def metrik_satiri"):]
    g = g[:g.index("\ndef ", 10)]
    assert "kart_hucresi(" in g
    t = (KOK / "shared" / "tasarim.py").read_text(encoding="utf-8")
    g = t[t.index("def kpi_serit"):]
    g = g[:g.index("\ndef ", 10)]
    assert "kart_hucresi(" in g


def test_yerel_kartlar_ortak_hucrede():
    for d in ("satis/main.py", "kayranpm/stok_karti.py"):
        src = (KOK / d).read_text(encoding="utf-8")
        g = src[src.index("def _kart("):]
        g = g[:g.index("\ndef ", 10)]
        assert "kart_hucresi(" in g, d
    # Eski çizim yalnız KART_YENI = False iken kalır; yeni yol büyük harf CSS'i kullanmaz
    from shared.tasarim import kart_hucresi
    assert "uppercase" not in kart_hucresi({"etiket": "Bizim stok", "deger": "1"})


def test_sus_kirmizisi_notr():
    """Kırmızı her yerde sorun değil: paçal maliyet, borç, harcama… her durumda
    kırmızı boyanıyordu. anlam='notr' yeni görünümde rengi kaldırır (eski yol aynı)."""
    T = _t()
    assert "k-kotu" not in T.kart_hucresi({"etiket": "Paçal", "deger": "$0", "renk": "kirmizi", "anlam": "notr"})
    for d, metin in (("kayranpm/stok_karti.py", '"Paçal Maliyet"'), ("kayranpm/ref_no.py", '"Toplam Harcama"'),
                     ("kayranacc/main.py", '"label": "Borç"'), ("kayranacc/cari_ekstre.py", '"📤 Açık Borç (TL)"'),
                     ("kayranacc/odeme_ekran.py", '"En çok ertelenen"')):
        src = (KOK / d).read_text(encoding="utf-8")
        i = src.index(metin)
        assert 'anlam="notr"' in src[i:i + 200] or '"anlam": "notr"' in src[i:i + 200], (d, metin)
