# -*- coding: utf-8 -*-
"""Hesap sayfaları görünüm düzeltmeleri (Ekim 2026): rakamlar aynı, yalnız görünüm.
Nakit akış tek eksenli iki grafik · Yönetim sayfa başlığı · P&L kartları aynı boy · Toplam aktifler emojisiz ·
Ürün yönetimi kategori özeti yarım sütuna sığar."""
import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


def _nakit_blogu():
    s = _oku("kayranacc/main.py")
    return s[s.index('def _sayfa_nakit_akis('):s.index("# 5) FİRMA ÇEKLERİ")]


def test_nakit_akis_tek_eksen_iki_grafik():
    b = _nakit_blogu()
    # iki ölçek üst üste yok (çizginin hangi eksene ait olduğu okunmuyordu)
    assert "yaxis2" not in b and "overlaying" not in b
    assert 'key="nakit_akis_bakiye"' in b and 'key="nakit_akis_grafik"' in b
    assert "fig.add_hline(y=0" in b                                   # eksiye düşüş sıfır çizgisiyle görünür
    assert "_ilk_eksi = next((x for x, v in zip(_x, _kal) if v < 0), None)" in b
    # rakamlar aynı kaynaktan: tablo satırlarından (hesap değişmedi)
    assert '_gun_tl = df_grafik["Günlük TL (₺)"].fillna(0)' in b and '_kalan = df_grafik["TL Bakiye Kalan (₺)"]' in b
    assert "kalan = banka_tl - kum_tl - (kum_usd * kur)" in b


def test_yonetim_basligi_secili_bolum():
    y = _oku("yonetim.py")
    assert 'Yönetim", "Yönetim panosu"' not in y
    assert y.count('baslik(":material/monitoring: Yönetim", _bolum or "Özet"') == 2


def test_yonetim_basligi_sekme_adiyla_gorunur(monkeypatch):
    from shared import tasarim as T
    monkeypatch.setattr(T, "_aktif_sekme", lambda: "Ay kapanışı")
    h = T.baslik(":material/monitoring: Yönetim", "Ay kapanışı", aciklama="x")
    assert 'class="k-baslik k-baslik-sekme"' in h                 # app.py CSS'i yalnız bu sınıfta adı gösterir


def test_pnl_karti_alt_satiri_tek_satir():
    import yonetim
    h = yonetim._hucre("Giderler", "$0", "işletme (TL→USD)")
    assert "white-space:nowrap;overflow:hidden;text-overflow:ellipsis" in h


def test_toplam_aktifler_emojisiz():
    """Toplam aktifler dökümü (Yönetim panosu; Muhasebe sayfası 22.10.2026'da kalktı) emojisiz."""
    s = _oku("yonetim.py")
    blok = s[s.index("def _toplam_aktif_html"):s.index("def _veri_durumu")]
    assert not re.search("[\U0001F300-\U0001FAFF☀-➿]", blok), blok
    assert '("Banka (USD eşd.)", snap.get("banka", 0), "+")' in blok and '("Çekler", snap.get("cek", 0), "−")' in blok
    assert not re.search("[\U0001F300-\U0001FAFF☀-➿]", _oku("kayranacc/toplam_aktif_ekran.py"))


def test_pm_kategori_ozeti_yarim_sutuna_sigar():
    g = _oku("kayranpm/genel_bakis.py")
    blok = g[g.index('_bolum("Kategori özeti"'):g.index('"pm_kat_ozet_masa"')]
    assert '_mk("Ürün", "adet", gizli=True)' in blok and '_mk("Acil", "adet", gizli=True)' in blok
    assert '_mk("Ölü / yavaş", "adet", gizli=True)' in blok
    # görünen sütun genişlikleri (ana sütun 150px) yarım sütuna (~470px) sığar
    genis = [int(x) for x in re.findall(r'gen="(\d+)px"', blok)]
    assert 150 + sum(genis) <= 470, genis
