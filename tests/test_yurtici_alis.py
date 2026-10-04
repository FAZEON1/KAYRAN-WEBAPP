# -*- coding: utf-8 -*-
"""Yurt içi alış / yerli üretim (Ekim 2026).

Alımlar ithalat dosyalarıyla aynı tablolarda, ithalat_dosyalari.alim_turu ile tutulur
(veritabani/18): paçal, stok kartı alımları, Model sorgu ve FIFO stok yaşı onları kendiliğinden
kullanır; İthalat listeleri yalnız ithalatı gösterir. "Mal zaten depoda" seçeneği stoğa dokunmaz.
"""
from pathlib import Path

import pytest

import ithalat.database as I
import kayranpm.yurtici_hesap as H
from test_teslim_stok import _stok, sahte_ortam

KOK = Path(__file__).resolve().parent.parent


@pytest.fixture
def ortam(monkeypatch):
    return sahte_ortam(monkeypatch)


# ── Saf: maliyet, doğrulama, kayıt alanları ─────────────────────────
def test_tl_alim_usd_birim_maliyet_masraf_payiyla():
    h = H.maliyet_hesapla([{"sku": "FAZE1", "adet": 100, "fiyat": 40}, {"sku": "FAZE2", "adet": 50, "fiyat": 80}],
                          {"nakliye": 400, "diger": 0}, "TL", 40)
    assert h["mal_bedeli"] == 8000 and h["masraf"] == 400 and round(h["oran"], 6) == 5.0
    assert [(r["sku"], round(r["birim_usd"], 4), round(r["maliyet_usd"], 4)) for r in h["satirlar"]] == \
        [("FAZE1", 1.0, 1.05), ("FAZE2", 2.0, 2.1)]
    u = H.maliyet_hesapla([{"sku": "A", "adet": 2, "fiyat": 3}], {}, "USD", 0)
    assert u["satirlar"][0]["maliyet_usd"] == 3


def test_dogrula_eksikleri_soyler():
    tam = {"tur": "yurtici", "alis_tarihi": "2026-07-01", "giris_tarihi": "2026-07-03", "depo": "MERKEZ DEPO",
           "para": "TL", "kur": 40, "kalemler": [{"sku": "FAZE1", "adet": 10, "fiyat": 5}], "masraflar": {}}
    assert H.dogrula(tam, ["FAZE1"]) == []
    h = H.dogrula(dict(tam, giris_tarihi="2026-06-01", kur=0, depo="İADE DEPO",
                       kalemler=[{"sku": "YOK", "adet": 0, "fiyat": 0}, {"sku": None, "adet": None, "fiyat": None}]),
                  ["FAZE1"])
    assert any("önce olamaz" in x for x in h) and any("kur" in x for x in h)
    assert any("Teslim deposu" in x for x in h) and any("YOK: ürün kartı yok" in x for x in h)
    assert any("adet" in x for x in h) and any("birim fiyat" in x for x in h)
    assert any("En az bir kalem" in x for x in H.dogrula(dict(tam, kalemler=[]), ["FAZE1"]))


def test_kayit_argumanlari_ve_formdan_geri_donus():
    f = {"tur": "yerli", "belge": "", "firma": " Atölye ", "alis_tarihi": "2026-07-01", "giris_tarihi": "2026-07-03",
         "depo": "HAPPY LIFE", "para": "TL", "kur": 40, "not": "",
         "kalemler": [{"sku": "FAZE1", "adet": 100, "fiyat": 40}, {"sku": "", "adet": 0, "fiyat": 0}],
         "masraflar": {"nakliye": 400, "diger": 0}}
    a = H.kayit_argumanlari(f, ad_bul={"FAZE1": "Mouse pad"}.get)
    assert a["dosya_no"] == "YU-20260701" and a["tedarikci"] == "Atölye" and a["alim_turu"] == "yerli"
    assert a["kalemler"] == [{"sku": "FAZE1", "urun_adi": "Mouse pad", "adet": 100, "birim_fob": 1.0}]
    assert a["masraflar"] == {"nakliye": 10.0} and a["doviz"] == "TL" and a["kur"] == 40
    assert a["teslim_tarihi"] == "2026-07-03" and a["teslim_deposu"] == "HAPPY LIFE"
    d = {"alim_turu": "yerli", "dosya_no": "YU-20260701", "tedarikci": "Atölye", "tarih": "2026-07-01",
         "teslim_tarihi": "2026-07-03", "teslim_deposu": "HAPPY LIFE", "doviz": "TL", "kur": 40,
         "masraflar": {"nakliye": 10.0}}
    v = H.formdan(d, [{"sku": "FAZE1", "adet": 100, "birim_fob": 1.0}])
    assert v["kalemler"] == [{"sku": "FAZE1", "adet": 100, "fiyat": 40.0}] and v["masraflar"]["nakliye"] == 400.0
    assert v["giris_tarihi"] == "2026-07-03" and v["para"] == "TL"


# ── Kayıt ve stok ───────────────────────────────────────────────────
def _ekle(stok_ekle, tur="yurtici"):
    return I.ekle_dosya("YI-1", "2026-07-01", "Firma", "", "TL", 40, {"nakliye": 10.0}, "",
                        [{"sku": "FAZE1", "adet": 100, "birim_fob": 1.0}], durum="Teslim Alındı",
                        teslim_tarihi="2026-07-03", teslim_deposu="MERKEZ DEPO", alim_turu=tur, stok_ekle=stok_ekle)


def test_yeni_alim_stoga_eklenir_silinince_geri_cekilir(ortam):
    db = ortam([], [])
    ok, _m = _ekle(True)
    d = db.tablolar["ithalat_dosyalari"][0]
    assert ok and d["alim_turu"] == "yurtici" and d["stok_islendi"] is True
    assert _stok(ortam.hareket) == {"FAZE1": 100}
    ok, msg = I.yurtici_sil(d["id"])
    assert ok and "geri çekildi" in msg and _stok(ortam.hareket) == {}
    assert db.tablolar["ithalat_dosyalari"] == [] and db.tablolar["ithalat_kalemleri"] == []


def test_mal_zaten_depoda_stoga_dokunmaz(ortam):
    db = ortam([], [])
    ok, _m = _ekle(False)
    d = db.tablolar["ithalat_dosyalari"][0]
    assert ok and ortam.hareket == [] and "stok_islendi" not in d
    assert I.teslim_stok_kayitsiz() == [] and I.teslim_stok_bekleyenler() == []   # Veri sağlığı notuna girmez
    ok, msg = I.yurtici_sil(d["id"])
    assert ok and "dokunulmadı" in msg and ortam.hareket == []


def test_ithalat_dosyasi_yurtici_sil_ile_silinmez(ortam):
    db = ortam([{"id": 7, "dosya_no": "D7", "durum": "Teslim Alındı"}], [])
    ok, msg = I.yurtici_sil(7)
    assert not ok and "İthalat" in msg and len(db.tablolar["ithalat_dosyalari"]) == 1


def test_alim_turu_okuma():
    assert I.alim_turu({}) == "ithalat" and I.alim_turu({"alim_turu": " YURTICI "}) == "yurtici"
    assert I.alim_turu({"alim_turu": "bilinmeyen"}) == "ithalat"
    assert I.ithalat_mi({"alim_turu": None}) and not I.ithalat_mi({"alim_turu": "yerli"})


def test_alim_turu_opsiyonel_kolon_degil():
    """Sütun yoksa sessizce düşüp alımı İTHALAT diye yazmasın: hata versin."""
    assert "alim_turu" not in I._OPSIYONEL_KOLONLAR


# ── Paçal ve listeler ───────────────────────────────────────────────
def test_yurtici_alim_pacala_girer(ortam):
    ortam([{"id": 1, "dosya_no": "YI-1", "durum": "Teslim Alındı", "teslim_tarihi": "2026-07-03",
            "tarih": "2026-07-01", "alim_turu": "yurtici", "masraflar": {"nakliye": 10.0}}],
          [{"dosya_id": 1, "sku": "FAZE1", "adet": 100, "birim_fob": 1.0}])
    if hasattr(I._parti_satirlari_hesapla, "clear"):
        I._parti_satirlari_hesapla.clear()
    oz = I.get_sku_maliyet_ozet()
    assert round(oz["FAZE1"]["pacal_final"], 4) == 1.1        # 1 $ + %10 nakliye


def test_ithalat_listeleri_yalniz_ithalat():
    s = (KOK / "ithalat" / "main.py").read_text(encoding="utf-8")
    for fn in ("def _gecmis_ithalatlar(", "def _masraf_detaylari("):
        g = s[s.index(fn):]
        g = g[:g.index("\ndef ", 1)]
        assert "if ithalat_mi(d)]" in g, fn


def test_tum_urunler_stok_yasi_yalniz_depoya_giren(monkeypatch):
    """Tüm Ürünler 'Stok yaşı': antrepodaki dosyanın belge tarihi parti sayılmaz; anahtar sku_anahtar."""
    import kayranpm.analitik as A
    dos = [{"id": 1, "durum": "Teslim Alındı", "teslim_tarihi": "2026-05-02", "tarih": "2026-03-01"},
           {"id": 2, "durum": "Antrepoda", "teslim_tarihi": None, "tarih": "2025-12-01"}]
    kal = [{"dosya_id": 1, "sku": "Fazeon X24", "adet": 10}, {"dosya_id": 2, "sku": "X24", "adet": 50}]
    monkeypatch.setattr(I, "get_dosyalar", lambda: dos)
    monkeypatch.setattr(I, "get_tum_kalemler", lambda: kal)
    p = A._ithalat_partiler_map()
    assert [(x["tarih"], x["adet"]) for x in p["X24"]] == [("2026-05-02", 10)]


def test_menu_ve_sayfalar():
    from shared.gezinme import MODULLER, hedef
    from shared.tasarim import menu_etiketi
    pm = next(m for m in MODULLER if m["kod"] == "kayranpm")
    adlar = {s[1]: s[0] for s in pm["sayfalar"]}
    assert adlar["maliyet"] == "💵  Yurt İçi Alış" and adlar["stok_yasi"] == "Stok Yaşı"
    assert menu_etiketi("Stok Yaşı") == ":material/hourglass_bottom: Stok Yaşı"
    assert hedef("kayranpm/stok_yasi") and hedef("kayranpm/maliyet")
    m = (KOK / "kayranpm" / "main.py").read_text(encoding="utf-8")
    assert 'elif sayfa == "Stok Yaşı":' in m and "yurtici_ekran import goster" in m
    k = (KOK / "kayranpm" / "stok_karti.py").read_text(encoding="utf-8")
    assert "kart_bolumu(sku)" in k


def test_sql_dosyasi():
    s = (KOK / "veritabani" / "18_alim_turu.sql").read_text(encoding="utf-8").lower()
    assert "add column if not exists alim_turu text" in s and "update " not in s
