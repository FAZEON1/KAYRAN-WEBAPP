# -*- coding: utf-8 -*-
"""Mikro'nun karşıladığı ekran parçaları (kullanıcı kararı 22.10.2026): silinmez, ilgili Mikro eşitlemesi
AÇIKKEN ekrandan kalkar; eşitleme kapalıysa (ya da durumu okunamazsa) eski yol aynen çalışır.

- Dosya kapısı: tür listesi / seçim / otomatik tanıma / boş şablonlar (shared.dosya_kapisi.mikro_kapsar).
- Yükleme takvimi: hatırlatma ve takvim ayarları tablosu (shared.yukleme_takvimi, aynı tek kaynak).
- Ürün yönetimi: ürün düzenlemedeki G5F stok alanı ve upsert_urun'un stok yazımı (kayranpm.mikro_stok).
"""
import sys
import types

import pytest

from kapi_ornekleri import ORNEKLER

# Mikro'nun karşıladığı tür → eşitleme modülü (görevdeki liste)
BEKLENEN = {
    "siparis_vatan": "satis.mikro_esitle", "siparis_itopya": "satis.mikro_esitle",
    "mikro_fatura": "satis.mikro_esitle", "iade_excel": "satis.mikro_esitle",
    "ithalat_rapor": "ithalat.mikro_ithalat", "g5f_sayim": "kayranpm.mikro_stok",
    "gider_tablosu": "kayranacc.mikro_gider", "aktif_stok": "kayranacc.mikro_stok_degeri",
    "aktif_ithalat": "kayranacc.mikro_muhasebe", "aktif_cari": "kayranacc.mikro_muhasebe",
    "cek_listesi": "kayranacc.mikro_muhasebe",
}
KALACAK = ["musteri_haftalik", "kampanya_sablon", "ref_excel", "odeme_listesi", "toplu_mal_kabul", "happylife",
           "alinan_destek"]
MODULLER = sorted(set(BEKLENEN.values()) | {"kayranpm.mikro_depo"})
TAM_YETKI = {"satis": True, "kayranacc": True, "kayranpm": True, "ithalat": True, "depo": True,
             "teknikservis": True, "yonetim": True, "kar": True, "toplam_aktifler": True}


def _esitleme(monkeypatch, acik=()):
    """Eşitleme modüllerinin yerine durumu verilen sahteleri koyar (acik: açık modüller; geri kalan kapalı)."""
    for m in MODULLER:
        sahte = types.ModuleType(m)
        sahte.acik_mi = (lambda a=(m in acik): a)
        monkeypatch.setitem(sys.modules, m, sahte)


class _Yuklenen:
    def __init__(self, ad, veri):
        self.name, self._v = ad, veri

    def getvalue(self):
        return self._v


# ── Dosya kapısı ─────────────────────────────────────────────────────
def test_mikro_turleri_listesi():
    from shared.dosya_kapisi import MIKRO_ESITLEME, TURLER
    assert MIKRO_ESITLEME == BEKLENEN
    assert set(MIKRO_ESITLEME) <= set(TURLER)
    assert not set(KALACAK) & set(MIKRO_ESITLEME)          # palet etiketi Mikro'da yok: Happy Life kalır


@pytest.mark.parametrize("tur", sorted(BEKLENEN))
def test_mikro_kapsar_esitlemeye_gore(monkeypatch, tur):
    from shared.dosya_kapisi import mikro_kapsar
    _esitleme(monkeypatch)
    assert not mikro_kapsar(tur)
    _esitleme(monkeypatch, acik={BEKLENEN[tur]})
    assert mikro_kapsar(tur)


@pytest.mark.parametrize("tur", KALACAK)
def test_kalacak_turler_hep_gorunur(monkeypatch, tur):
    from shared.dosya_kapisi import mikro_kapsar, secilebilir_turler
    _esitleme(monkeypatch, acik=set(MODULLER))
    assert not mikro_kapsar(tur)
    assert tur in secilebilir_turler(TAM_YETKI)


def test_okuma_hatasinda_kapi_acik_kalir(monkeypatch):
    from shared.dosya_kapisi import mikro_kapsar
    _esitleme(monkeypatch)

    def _patla():
        raise RuntimeError("bağlantı yok")
    sys.modules["kayranpm.mikro_stok"].acik_mi = _patla
    assert mikro_kapsar("g5f_sayim") is False


def test_ithalat_varsayilan_acik_ama_okunamazsa_kapali(monkeypatch):
    """ithalat.mikro_ithalat.acik_mi okuma hatasında da 'açık' der (durum() {} döner); kapı açık kalmalı."""
    import ithalat.mikro_ithalat as MI
    import kayranacc.database as KD
    from shared.dosya_kapisi import mikro_kapsar

    def _patla(_a):
        raise RuntimeError("bağlantı yok")
    monkeypatch.setattr(KD, "_ayar_ham", _patla)
    assert MI.acik_mi() is True                         # modülün kendi kuralı
    assert mikro_kapsar("ithalat_rapor") is False
    monkeypatch.setattr(KD, "_ayar_ham", lambda a: None)
    monkeypatch.setattr(MI, "durum", lambda: {})
    assert mikro_kapsar("ithalat_rapor") is True         # okundu, ayar yok → varsayılan açık
    monkeypatch.setattr(MI, "durum", lambda: {"acik": False})
    assert mikro_kapsar("ithalat_rapor") is False


def test_secim_listesi_mikro_acikken_gizler(monkeypatch):
    from shared.dosya_kapisi import izinli, izinli_turler, secilebilir_turler
    _esitleme(monkeypatch)
    assert secilebilir_turler(TAM_YETKI) == izinli_turler(TAM_YETKI)          # kapalı: eski liste
    _esitleme(monkeypatch, acik={"satis.mikro_esitle", "kayranacc.mikro_muhasebe"})
    s = secilebilir_turler(TAM_YETKI)
    for t in ("siparis_vatan", "siparis_itopya", "mikro_fatura", "iade_excel", "aktif_cari", "aktif_ithalat",
              "cek_listesi"):
        assert t not in s
        assert izinli(t, TAM_YETKI)                     # yetki değişmez; yalnız seçimden kalkar
    assert {"g5f_sayim", "gider_tablosu", "aktif_stok", "ithalat_rapor", "odeme_listesi"} <= set(s)


@pytest.mark.parametrize("tur", sorted(BEKLENEN))
def test_mikro_acikken_birakilan_dosya_listeye_girmez(monkeypatch, tur):
    import streamlit as st
    from shared import dosya_kapisi as dk
    monkeypatch.setattr(st, "session_state", {})
    _esitleme(monkeypatch, acik={BEKLENEN[tur]})
    ad, veri = ORNEKLER[tur]()
    dk.dosyalari_ekle([_Yuklenen(ad, veri)], TAM_YETKI)
    assert st.session_state["_kapi_dosyalar"] == []
    assert st.session_state["_kapi_mikro_not"] == [
        f"{ad}: Bu dosyanın verisi artık Mikro'dan geliyor; yüklemeye gerek yok."]
    assert "_kapi_aktif" not in st.session_state


@pytest.mark.parametrize("tur", sorted(BEKLENEN))
def test_mikro_kapaliyken_eski_yol(monkeypatch, tur):
    import streamlit as st
    from shared import dosya_kapisi as dk
    monkeypatch.setattr(st, "session_state", {})
    _esitleme(monkeypatch)
    ad, veri = ORNEKLER[tur]()
    dk.dosyalari_ekle([_Yuklenen(ad, veri)], TAM_YETKI)
    d = st.session_state["_kapi_dosyalar"]
    assert len(d) == 1 and d[0]["secim"] == tur
    assert st.session_state["_kapi_aktif"] == d[0]["id"]          # tek ve kesin: doğrudan açılır
    assert "_kapi_mikro_not" not in st.session_state


def test_sablonlar_mikro_acikken_gizlenir(monkeypatch):
    from shared.dosya_kapisi import SABLONLAR, gorunen_sablonlar
    _esitleme(monkeypatch)
    assert gorunen_sablonlar(TAM_YETKI) == SABLONLAR
    _esitleme(monkeypatch, acik={"satis.mikro_esitle", "ithalat.mikro_ithalat"})
    adlar = [s[0] for s in gorunen_sablonlar(TAM_YETKI)]
    assert adlar == ["Haftalık ödeme listesi örneği", "Kampanya şablonu", "Alınan destekler şablonu",
                     "Toplu mal kabul şablonu"]


# ── Yükleme takvimi ──────────────────────────────────────────────────
def test_takvim_mikro_kaynaklari_tek_kaynaktan(monkeypatch):
    from shared import yukleme_takvimi as Y
    _esitleme(monkeypatch)
    assert Y._mikro_kapsadigi() == set()
    kaynak, mikro = Y.ayar_kaynaklari()
    assert kaynak == Y.KAYNAKLAR and mikro == []
    _esitleme(monkeypatch, acik=set(MODULLER))
    assert Y._mikro_kapsadigi() == {"aktif_cari", "aktif_ithalat", "aktif_stok", "gider_tablosu", "g5f_sayim",
                                    "satis_dokumu", "happylife"}
    kaynak, mikro = Y.ayar_kaynaklari()
    assert [k["anahtar"] for k in kaynak] == ["musteri_haftalik", "odeme_listesi"]
    assert "G5F stok sayımı" in mikro and "Aylık gider tablosu" in mikro


def test_takvim_ayarlari_mikro_kaynaklarini_korur():
    """Tablo Mikro kaynaklarını göstermez; kayıt eski ayarlarını silmemeli (app.py eski ayarla birleştirir)."""
    from pathlib import Path
    a = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
    assert "_yt_kaynak, _yt_mikro = _yt.ayar_kaynaklari()" in a
    assert "for k in _yt_kaynak])" in a and "for k in _yt.KAYNAKLAR])" not in a
    assert "_yt.ayar_kaydet({**(_ay if isinstance(_ay, dict) else {}), **{" in a


# ── Ürün yönetimi ────────────────────────────────────────────────────
class _Tablo:
    def __init__(self, yazilan):
        self.yazilan = yazilan

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def upsert(self, veri, **k):
        self.yazilan.append(dict(veri))
        return self

    def execute(self):
        return types.SimpleNamespace(data=[])


def _upsert(monkeypatch, mikro_acik):
    import kayranpm.database as D
    yazilan = []
    sb = types.SimpleNamespace(table=lambda ad: _Tablo(yazilan))
    monkeypatch.setattr(D, "get_client", lambda: sb)
    monkeypatch.setattr(D, "get_today", lambda: "2026-10-22")
    monkeypatch.setattr(D, "stok_yas_ilk_gorulen", lambda *a, **k: None)
    monkeypatch.setattr(D, "_cache_temizle", lambda: None)
    _esitleme(monkeypatch, acik={"kayranpm.mikro_stok"} if mikro_acik else ())
    D.upsert_urun("X24F165S", "Monitör", "monitör", "FAZEON", 120.0, 80.0, 0, "", 37, 0, eol=False)
    assert len(yazilan) == 1
    return yazilan[0]


def test_upsert_urun_mikro_acikken_stok_yazmaz(monkeypatch):
    y = _upsert(monkeypatch, True)
    assert "bizim_stok" not in y
    assert (y["urun_adi"], y["satis_fiyati"], y["alis_fiyati"], y["eol"]) == ("Monitör", 120.0, 80.0, False)


def test_upsert_urun_mikro_kapaliyken_stok_yazar(monkeypatch):
    assert _upsert(monkeypatch, False)["bizim_stok"] == 37


def test_stok_mikrodan(monkeypatch):
    from kayranpm.main import stok_mikrodan
    _esitleme(monkeypatch)
    assert stok_mikrodan() is False
    _esitleme(monkeypatch, acik={"kayranpm.mikro_stok"})
    assert stok_mikrodan() is True


def test_urun_ekrani_metinleri_mikroya_gore():
    from pathlib import Path
    s = (Path(__file__).resolve().parent.parent / "kayranpm" / "main.py").read_text(encoding="utf-8")
    assert 'STOK_MIKRO_NOTU = "Depo stoğu Mikro\'dan gelir (15 dakikada bir)"' in s
    assert "_stok_mk = stok_mikrodan()" in s
    assert 'STOK_MIKRO_NOTU if _stok_mk else "G5F sayımını yeniden yükle"' in s
    i = s.index("with fc4:")
    blok = s[i:s.index("# ── YURT İÇİ ALIM MALİYETİ", i)]
    assert "if _stok_mk:" in blok and "disabled=True" in blok and "Stok Mikro'dan gelir" in blok


@pytest.mark.parametrize("mod, durum_mu", [("kayranpm.mikro_stok_ekran", True), ("kayranpm.mikro_urun_ekran", True),
                                           ("kayranpm.mikro_depo_ekran", False)])
def test_ilk_onay_kutusu_acikken_yalniz_not(monkeypatch, mod, durum_mu):
    import importlib
    E = importlib.import_module(mod)
    yazilan = []
    monkeypatch.setattr(E.st, "caption", lambda m, *a, **k: yazilan.append(m), raising=False)

    def _yok(*a, **k):
        raise AssertionError("açıkken onay kutusu çizilmemeli")
    monkeypatch.setattr(E.st, "expander", _yok, raising=False)
    if durum_mu:
        monkeypatch.setattr(E.M, "durum", lambda: {"acik": True})
    else:
        monkeypatch.setattr(E.M, "acik_mi", lambda: True)
    E.ilk_onay_kutusu()
    assert len(yazilan) == 1 and "Mikro" in yazilan[0]
