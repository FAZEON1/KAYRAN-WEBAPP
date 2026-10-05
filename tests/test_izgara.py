# -*- coding: utf-8 -*-
"""Streamlit ızgarasının ortak görünümü (shared/izgara.py, Ekim 2026).

Düzenlenebilir tablolarda birim fiyatlar "$149,0000" görünüyordu: Streamlit ondalık sayısını
"adım"dan alıyor (0,0001 → 4 hane). Adım görünümden kalkar, "$149,00" yazılır; düzenlenen
hücre kayıtta yine 4 haneye yuvarlanır, dokunulmayan hücre aynen kalır. Ürün adı sütunu geniş,
SKU dar değil, satırlar 40 px ve ekranların verdiği sabit yükseklik buna göre büyür.
Tarayıcıda (tr-TR, Streamlit 1.65) eski / yeni yan yana denendi.
"""
from pathlib import Path

import pandas as pd

import shared.izgara as I

KOK = Path(__file__).resolve().parent.parent


def _nc(label, **tc):
    """st.column_config.NumberColumn'un ürettiği sözlük (sahte streamlit'te de çalışsın)."""
    return {"label": label, "width": tc.pop("width", None), "disabled": None, "pinned": None,
            "type_config": {"type": "number", "format": tc.get("format"), "step": tc.get("step"),
                            "min_value": tc.get("min_value")}}


def _siparis_df():
    return pd.DataFrame([{"SKU": "F25A850BBM", "Ürün": "FAZEON F25 850W", "Adet": 4, "Birim satış": 149.0,
                          "Birim maliyet": 93.98021, "Kâr": 220.08, "Marj %": 36.9, "Sil": False},
                         {"SKU": "F15A750BM", "Ürün": "FAZEON F15 750W", "Adet": 1, "Birim satış": 95.0,
                          "Birim maliyet": 55.8051, "Kâr": 39.19, "Marj %": 41.3, "Sil": False}])


def _siparis_cfg():
    return {"SKU": {"label": "SKU", "width": "small", "type_config": {"type": "text"}},
            "Ürün": {"label": "Ürün", "width": "medium", "type_config": {"type": "text"}},
            "Adet": _nc("Adet", format="localized", step=1, min_value=0),
            "Birim satış": _nc("Birim satış", format="dollar", step=0.0001, min_value=0.0),
            "Birim maliyet": _nc("Birim maliyet", format="dollar", step=0.0001, min_value=0.0),
            "Kâr": _nc("Kâr", format="dollar", step=0.01),
            "Marj %": _nc("Marj %", format="localized", step=0.1)}


# ── Para: küçük adım görünümden kalkar, hassasiyet kayıtta korunur ──
def test_birim_fiyat_dort_hane_gostermez_ama_kayitta_korunur():
    cfg, yuvarla = I.izgara_ayar(_siparis_df(), _siparis_cfg(), duzenleme=True)
    assert cfg["Birim satış"]["type_config"]["step"] is None          # "$149,00" (dört hane değil)
    assert cfg["Birim satış"]["type_config"]["format"] == "dollar"
    assert cfg["Birim satış"]["type_config"]["min_value"] == 0.0      # diğer ayarlar aynen
    assert yuvarla == {"Birim satış": 4, "Birim maliyet": 4}


def test_para_disi_adimlar_ve_iki_haneli_para_aynen():
    cfg, _ = I.izgara_ayar(_siparis_df(), _siparis_cfg(), duzenleme=True)
    assert cfg["Adet"]["type_config"]["step"] == 1
    assert cfg["Marj %"]["type_config"]["step"] == 0.1
    assert cfg["Kâr"]["type_config"]["step"] == 0.01


def test_cagiranin_ayari_degismez():
    giren = _siparis_cfg()
    I.izgara_ayar(_siparis_df(), giren, duzenleme=True)
    assert giren["Birim satış"]["type_config"]["step"] == 0.0001 and giren["SKU"]["width"] == "small"


def test_salt_okunur_tabloda_yuvarlama_yok():
    cfg, yuvarla = I.izgara_ayar(_siparis_df(), _siparis_cfg(), duzenleme=False)
    assert cfg["Birim satış"]["type_config"]["step"] is None and yuvarla == {}


# ── Kayıt: yalnız düzenlenen hücre yuvarlanır ──────────────────────
def test_duzenlenen_hucre_eski_hassasiyete_yuvarlanir_dokunulmayan_aynen():
    girdi = _siparis_df()
    cikti = girdi.copy()
    cikti.loc[1, "Birim satış"] = 96.123456                  # kullanıcı girdi (adım yokken yuvarlanmaz)
    sonuc = I.izgara_sonuc(girdi, cikti, {"Birim satış": 4, "Birim maliyet": 4})
    assert sonuc.loc[1, "Birim satış"] == 96.1235
    assert sonuc.loc[0, "Birim maliyet"] == 93.98021          # 5 haneli eski değer: dokunulmadı
    assert sonuc.loc[0, "Birim satış"] == 149.0
    assert girdi.loc[1, "Birim satış"] == 95.0                 # girdi değişmedi
    # kayıt yolu "değişti mi"yi str ile karşılaştırıyor (satislar_ekran): dokunulmayan satır değişmiş sayılmaz
    assert all(str(sonuc.loc[0, c]) == str(girdi.loc[0, c]) for c in girdi.columns)


def test_yeni_eklenen_satir_da_yuvarlanir():
    girdi = _siparis_df()
    cikti = pd.concat([girdi, pd.DataFrame([{"SKU": "X", "Birim satış": 1.234567}], index=[5])])
    sonuc = I.izgara_sonuc(girdi, cikti, {"Birim satış": 4})
    assert sonuc.loc[5, "Birim satış"] == 1.2346


def test_dataframe_olmayan_sonuc_aynen():
    assert I.izgara_sonuc([{"a": 1}], [{"a": 1.23456}], {"a": 2}) == [{"a": 1.23456}]


# ── Genişlik ────────────────────────────────────────────────────────
def test_sku_ve_urun_genisler_ama_daraltilmaz():
    cfg, _ = I.izgara_ayar(_siparis_df(), _siparis_cfg(), duzenleme=True)
    assert cfg["SKU"]["width"] == "medium" and cfg["Ürün"]["width"] == "large"
    assert not cfg["SKU"].get("pinned")                         # sabit sütun soluk çiziliyordu
    df = pd.DataFrame([{"SKU": "A", "Ürün": "B"}])
    cfg, _ = I.izgara_ayar(df, {"SKU": {"width": "large"}, "Ürün": {"width": 120}})
    assert cfg["SKU"]["width"] == "large" and cfg["Ürün"]["width"] == 120


# ── Biçimi verilmemiş sütunlar ──────────────────────────────────────
def test_salt_okunur_bicimsiz_sutunlar_turkce():
    df = pd.DataFrame([{"Ciro": 1234.5, "Stok": 12, "Marj %": 31.123, "Tarih": pd.Timestamp("2026-10-03"),
                        "Not": "x"}])
    cfg, _ = I.izgara_ayar(df, None)
    assert cfg["Ciro"]["type_config"] == {"type": "number", "format": "dollar"}
    assert cfg["Stok"]["type_config"] == {"type": "number", "format": "localized", "step": 1}
    assert cfg["Marj %"]["type_config"] == {"type": "number", "format": "localized", "step": 0.1}
    assert cfg["Tarih"]["type_config"]["format"] == "DD.MM.YYYY"
    assert "Not" not in cfg


def test_duzenlenebilir_bicimsiz_sutunda_adim_yok_para_dolarsiz():
    df = pd.DataFrame([{"Tutar": 1500.0, "Adet": 3, "Marj %": 10.0}])
    cfg, yuvarla = I.izgara_ayar(df, None, duzenleme=True, kilitli=["Marj %"])
    assert cfg["Tutar"]["type_config"] == {"type": "number", "format": "localized"}   # TL olabilir: "$" yok
    assert "Adet" not in cfg                                     # düzenlenen adet: adım girişi yuvarlar
    assert cfg["Marj %"]["type_config"]["step"] == 0.1           # kilitli sütun biçimlenir
    assert yuvarla == {}


def test_gizli_sutun_ve_tabloda_olmayan_ayar_korunur():
    df = pd.DataFrame([{"id": 1, "SKU": "A"}])
    cfg, _ = I.izgara_ayar(df, {"id": None, "_index": {"label": "x"}})
    assert cfg["id"] is None and cfg["_index"] == {"label": "x"}


# ── Satır yüksekliği ────────────────────────────────────────────────
def test_sabit_yukseklik_satir_sayisi_korunarak_buyur():
    kw = I._satir_ayari({"height": 38 + 35 * 5})
    assert kw["row_height"] == 40 and kw["height"] >= 38 + 40 * 5
    assert I._satir_ayari({"height": "auto"})["height"] == "auto"
    kendi = I._satir_ayari({"height": 300, "row_height": 30})
    assert kendi == {"height": 300, "row_height": 30}           # ekranın kendi ayarına dokunulmaz


def test_dataframe_hazirla():
    kw = I.dataframe_hazirla(_siparis_df(), {"column_config": _siparis_cfg(), "height": 440})
    assert kw["row_height"] == 40 and kw["column_config"]["Birim satış"]["type_config"]["step"] is None


# ── Bağlantılar ─────────────────────────────────────────────────────
def test_uygulamaya_bagli_ve_geri_alinabilir():
    import shared.tasarim as T
    assert T.IZGARA_YENI is True
    a = (KOK / "app.py").read_text(encoding="utf-8")
    assert "from shared.izgara import kur as _izgara_kur" in a and "_izgara_kur(st)" in a
    assert "_dataframe_yamasi_kur()" in a                       # st.dataframe yaması (Ekim 2026)
    assert "dataframe_hazirla(data, kw)" in (KOK / "shared" / "dataframe_yamasi.py").read_text(encoding="utf-8")
    src = (KOK / "shared" / "izgara.py").read_text(encoding="utf-8")
    assert "if not IZGARA_YENI:" in src


def test_kur_streamlit_yoksa_patlamaz():
    I.kur(object())
