# -*- coding: utf-8 -*-
"""Görünüm cilası (Ekim 2026, kullanıcı onayı A — karşılaştırma sayfası
https://claude.ai/artifact/B3Pr95sc4wQYKExm5xbNSA):

1. Görünmez yardımcı bileşenler ve telefon menüsü kabı sayfada boşluk kaplamaz.
2. Sekmeli sayfada başlık sekmedeki adla görünür; Muhasebe'de başlık seçicilerle aynı satıra yazılır.
3. Büyük kartlarda 1.000 ve üstü tutar kuruşsuz; tam tutar üzerine gelince (title) görünür.
4. Ana sayfa › Bugün: teknik servis maddesinde ürün kartının adı (BÜYÜK harf kararı), tekrar eden ad bir kez.
"""
import sys
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from shared import tasarim as T  # noqa: E402


# ── 3. Kart rakamları ────────────────────────────────────────────────
def _kart(deger):
    return T.kart_hucresi({"etiket": "Nakit açığı", "deger": deger})


def test_buyuk_tutarda_kurus_yok_tam_tutar_ipucunda():
    h = _kart("₺4.109.380,82")
    assert '<span class="k-deger">₺4.109.381</span>' in h
    assert 'title="₺4.109.380,82"' in h


def test_yuvarlama_ve_isaret():
    assert '<span class="k-deger">$98.641</span>' in _kart("$98.640,76")
    assert '<span class="k-deger">-₺1.235</span>' in _kart("-₺1.234,50")
    assert '<span class="k-deger">₺1.000</span>' in _kart("₺1.000,49")
    assert '<span class="k-deger">1.235 ₺</span>' in _kart("1.234,56 ₺")
    assert '<span class="k-deger">₺12.346</span>' in _kart("₺12345,6")


def test_kucuk_tutar_ve_para_olmayan_deger_aynen():
    for d in ("₺999,50", "$12,34", "4 / 20", "3 ödeme", "%16,7", "38,5000", "$1.234,5678",
              "<b>₺1.234,56</b>", "566", "1.401"):
        h = _kart(d)
        assert f'<span class="k-deger">{d}</span>' in h, d
        assert "title=" not in h, d


def test_kartin_kendi_ipucu_korunur():
    h = T.kart_hucresi({"etiket": "X", "deger": "₺2.500,10", "ipucu": "açıklama"})
    assert 'title="açıklama"' in h and '<span class="k-deger">₺2.500</span>' in h


# ── 2. Başlık: sekmedeki ad ──────────────────────────────────────────
def test_sekmeli_sayfada_baslik_sekme_adiyla(monkeypatch):
    import streamlit as st
    monkeypatch.setitem(st.session_state, "_k_aktif_sekme", "Bu hafta")
    h = T.baslik("💳 Muhasebe", "Bu Hafta", aciklama="12.10.2026 Güncel Ödeme Listesi")
    assert "k-baslik-sekme" in h and '<span class="k-baslik-ad">Bu hafta</span>' in h
    monkeypatch.setitem(st.session_state, "_k_aktif_sekme", "Raporlar ve bildirim")
    assert '<span class="k-baslik-ad">Raporlar ve bildirim</span>' in T.baslik("📄 Muhasebe", "Raporlar & Bildirim")
    # Sayfanın içindeki ara başlık sekme adına uymaz → olduğu gibi (yalnız açıklaması görünür)
    ara = T.baslik("🔔", "Bildirim Ayarları", aciklama="e-posta")
    assert "k-baslik-sekme" not in ara and "Bildirim Ayarları" in ara


def test_sekme_yoksa_baslik_aynen(monkeypatch):
    import streamlit as st
    monkeypatch.delitem(st.session_state, "_k_aktif_sekme", raising=False)
    h = T.baslik("💳 Muhasebe", "Bu Hafta")
    assert "k-baslik-sekme" not in h and '<span class="k-baslik-ad">Bu Hafta</span>' in h


def test_sayfa_menusu_aktif_sekmeyi_yazar(monkeypatch):
    import streamlit as st
    from shared import gezinme as G
    monkeypatch.setattr(st, "radio", lambda *a, **k: "💳 Bu Hafta", raising=False)
    monkeypatch.setattr(G, "_serit", lambda: None)
    monkeypatch.delitem(st.session_state, "_k_aktif_sekme", raising=False)
    G.sayfa_menusu("Sayfa", G.secenekler("kayranacc"), modul="kayranacc", key="acc_sayfa")
    assert st.session_state.get("_k_aktif_sekme") == "Bu hafta"


def test_css_sekme_basligini_gosterir_ara_basligi_gizler():
    a = (KOK / "app.py").read_text(encoding="utf-8")
    assert ".k-baslik:not(.k-baslik-sekme)" in a
    assert ".k-baslik-sekme .k-baslik-ad" in a


# ── 2b. Muhasebe başlık yuvası ───────────────────────────────────────
class _Kap:
    def __init__(self):
        self.yazilan = []

    def markdown(self, metin, **_):
        self.yazilan.append(metin)


def test_baslik_yuvasi_ilk_basligi_alir(monkeypatch):
    import streamlit as st
    from shared import bilesen as B
    disari = []
    monkeypatch.setattr(st, "markdown", lambda m, **_: disari.append(m))
    kap = _Kap()
    B.baslik_yuvasi_kur(kap)
    B.baslik_yuvasi_ac()
    B.baslik_yaz("<baslik>")
    B.baslik_yaz("<ara baslik>")             # yuva bir kez kullanılır; ara başlık yerinde kalır
    assert kap.yazilan == ["<baslik>"] and disari == ["<ara baslik>"]
    B.baslik_yuvasi_kur(None)                 # başka modül: yuva yok → başlık yerinde
    B.baslik_yuvasi_ac()
    B.baslik_yaz("<x>")
    assert disari[-1] == "<x>" and kap.yazilan == ["<baslik>"]


# ── 1. Görünmez parçaların boşluğu ───────────────────────────────────
def test_gorunmez_parcalar_akistan_cikar():
    css = T.cekirdek_css()
    for parca in (".st-key-kayran_ceviri", ".st-key-kayran_ipucu", '> meta:first-child'):
        assert parca in css, parca
    a = (KOK / "app.py").read_text(encoding="utf-8")
    assert '[data-testid="stLayoutWrapper"]:has(> .st-key-alt_menu)' in a
    assert '[data-testid="stElementContainer"]:has(.k-mobil-ust)' in a


# ── 4. Ana sayfa › Bugün: ürün adı ───────────────────────────────────
def test_teknik_servis_maddesi_kart_adi_buyuk_harf_tekrarsiz(monkeypatch):
    from shared import bugun as BG, ana_veri
    from shared.utils import sku_anahtar
    monkeypatch.setattr(ana_veri, "get_urun_ad_haritasi",
                        lambda: {sku_anahtar("FZ-SSD-1TB"): "FAZEON HIZLI 1 TB NVME SSD"})
    k = [{"mevcut_durum": "Mal kabül", "mal_kabul_tarihi": "2026-09-01", "stok_kodu": "FZ-SSD-512",
          "stok_adi": "Fazeon Hızlı 512 GB NVMe SSD"} for _ in range(3)]
    k.append({"mevcut_durum": "Mal kabül", "mal_kabul_tarihi": "2026-09-02", "stok_kodu": "FZ-SSD-1TB",
              "stok_adi": "Fazeon 1TB eski ad"})
    m = BG.maddeler_teknik_servis(k, date(2026, 9, 30))
    assert len(m) == 1
    d = m[0]["detay"]
    assert d.endswith("FAZEON HIZLI 512 GB NVME SSD (3), FAZEON HIZLI 1 TB NVME SSD"), d
    assert m[0]["sayi"] == 4


# ── Hafta adı: str.title() Türkçe 'İ'yi bozuyordu ───────────────────
def test_hafta_etiketi_noktasiz_i_bozulmaz():
    from kayranacc.odeme_hesap import hafta_etiketi
    e = hafta_etiketi("12.10.2026 GÜNCEL ÖDEME LİSTESİ")
    assert e == "12.10.2026 güncel ödeme listesi" and "̇" not in e
    assert hafta_etiketi("13.10.2026 İthalat Ödemeleri") == "13.10.2026 İthalat Ödemeleri"
    assert hafta_etiketi(None) == ""
