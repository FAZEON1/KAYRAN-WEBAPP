# -*- coding: utf-8 -*-
"""Sade tablo — düzenlenebilir (shared/duzenle.py) ve salt okunur (shared/tablo.py), Ekim 2026.

Kullanıcı "I" tasarımını renklendirmesiz seçti: ürün adının altında SKU, başlık bandı yok, ferah
satır, birim maliyet soluk, kâr / marj / ciro renksiz. Streamlit'in düzenleme tablosu (tuvale
çizildiği için) bu görünümü veremiyordu; st.data_editor kendi tablomuza yönlendirilir, ekranların
kodu değişmez. Dönüş ve oturum durumu st.data_editor ile aynı biçimde (kayıt yolları aynen çalışır).
Tarayıcıda (Streamlit 1.65, Chromium, koyu tema, 1400 / 390 px) düzeltme, onay, seçim, tarih,
satır ekle / sil denendi.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

import shared.duzenle as Z
import shared.tablo as TB

KOK = Path(__file__).resolve().parent.parent


def _nc(**tc):
    return {"label": tc.pop("label", None), "disabled": tc.pop("disabled", None), "required": tc.pop("required", None),
            "default": tc.pop("default", None), "width": tc.pop("width", None),
            "type_config": dict(type=tc.pop("type", "number"), **tc)}


def _siparis():
    df = pd.DataFrame([{"_id": 100, "SKU": "F25A850BBM", "Ürün": "FAZEON F25", "Adet": 4, "Birim satış": 149.0,
                        "Birim maliyet": 93.98021, "Kâr": 220.08, "Sil": False},
                       {"_id": 101, "SKU": "F15A750BM", "Ürün": "FAZEON F15", "Adet": 1, "Birim satış": 95.0,
                        "Birim maliyet": 55.8051, "Kâr": 39.19, "Sil": False}]).set_index("_id")
    cfg = {"SKU": {"label": "SKU", "type_config": {"type": "text"}},
           "Adet": _nc(min_value=0, step=1, format="localized"),
           "Birim satış": _nc(format="dollar", step=0.0001, min_value=0.0),
           "Birim maliyet": _nc(format="dollar", step=0.0001, min_value=0.0),
           "Kâr": _nc(format="dollar", step=0.01),
           "Sil": {"label": "Sil", "type_config": {"type": "checkbox"}}}
    return df, cfg


def _veri(**kw):
    df, cfg = _siparis()
    return Z.duzenle_veri(df, cfg, disabled=["SKU", "Ürün", "Kâr"], hide_index=True, **kw)


# ── Hazırlık ────────────────────────────────────────────────────────
def test_sutunlar_turler_ve_kilit():
    v = _veri()
    k = {x["ad"]: x for x in v["kolonlar"]}
    assert [k[a]["tur"] for a in ("SKU", "Adet", "Birim satış", "Sil")] == ["text", "number", "number", "checkbox"]
    assert k["SKU"]["kilit"] and k["Kâr"]["kilit"] and not k["Adet"]["kilit"]
    assert k["Birim maliyet"]["soluk"] and not k["Birim satış"]["soluk"]
    assert v["index"] is None                                   # hide_index=True


def test_para_iki_hane_kayit_adim_hassasiyetinde():
    k = {x["ad"]: x for x in _veri()["kolonlar"]}
    assert k["Birim satış"]["bicim"]["on"] == "$" and k["Birim satış"]["bicim"]["ond"] == 2   # "$149,00"
    assert k["Birim satış"]["adim_ond"] == 4                     # girilen değer 4 haneye yuvarlanır (eskisi gibi)
    assert k["Adet"]["bicim"]["ond"] == 0 and k["Adet"]["tam"]


def test_urun_altinda_sku_yalniz_ikisi_de_kilitliyse():
    assert _veri()["birlesik"] == {"ad": 1, "sku": 0}
    df, cfg = _siparis()
    assert Z.duzenle_veri(df, cfg, disabled=["Ürün"])["birlesik"] is None   # SKU düzenlenebilir → kendi sütununda


def test_ham_degerler_json_ve_imza():
    v = _veri()
    assert v["satirlar"][0]["v"][:4] == ["F25A850BBM", "FAZEON F25", 4, 149]
    json.dumps(v)                                                # bileşene gidebilir
    df, cfg = _siparis()
    df2 = df.copy()
    df2.iloc[0, 2] = 5
    assert Z.duzenle_veri(df2, cfg)["imza"] != v["imza"]


def test_gizli_sutun_sira_ve_bilinmeyen_tur():
    df, cfg = _siparis()
    v = Z.duzenle_veri(df, dict(cfg, Kâr=None), column_order=["Ürün", "Adet", "Kâr"])
    assert [k["ad"] for k in v["kolonlar"]] == ["Ürün", "Adet"]
    assert Z.duzenle_veri(df, dict(cfg, Adet={"type_config": {"type": "link"}})) is None


def test_printf_bicimi_turkce():
    df = pd.DataFrame([{"Marj": 31.25, "Fiyat": 1234.5}])
    v = Z.duzenle_veri(df, {"Marj": _nc(format="%.1f%%"), "Fiyat": _nc(format="$%.2f")})
    k = {x["ad"]: x["bicim"] for x in v["kolonlar"]}
    assert k["Marj"] == {"on": "", "son": "%", "ond": 1, "en_cok": 4}
    assert k["Fiyat"]["on"] == "$" and k["Fiyat"]["ond"] == 2


# ── Düzenlemelerin uygulanması (st.data_editor ile aynı dönüş) ──────
def test_duzenlenen_hucre_yuvarlanir_dokunulmayan_aynen():
    df, _ = _siparis()
    kol = _veri()["kolonlar"]
    out = Z.uygula(df, {"edited_rows": {"1": {"Birim satış": 96.123456, "Adet": 3}, "0": {"Sil": True}}}, kol)
    assert out.loc[101, "Birim satış"] == 96.1235 and out.loc[101, "Adet"] == 3
    assert str(out.loc[101, "Adet"]) == "3"                        # tam sayı sütunu tam kalır
    assert bool(out.loc[100, "Sil"]) is True
    assert out.loc[100, "Birim maliyet"] == 93.98021              # 5 hane: dokunulmadı
    assert str(out.loc[100, "Birim satış"]) == str(df.loc[100, "Birim satış"])   # kayıt yolu değişmiş saymaz
    assert df.loc[101, "Adet"] == 1                              # girdi değişmedi


def test_kilitli_sutun_disaridan_degistirilemez():
    df, _ = _siparis()
    out = Z.uygula(df, {"edited_rows": {"0": {"Kâr": 999}}}, _veri()["kolonlar"])
    assert out.loc[100, "Kâr"] == 220.08


def test_satir_sil_ve_ekle():
    df = pd.DataFrame([{"SKU": "A", "Adet": 1.0, "Sil": False}, {"SKU": "B", "Adet": 2.0, "Sil": False}])
    cfg = {"Adet": _nc(min_value=0, step=1), "Sil": {"type_config": {"type": "checkbox"}, "default": False}}
    v = Z.duzenle_veri(df, cfg, num_rows="dynamic")
    assert v["ekle"] and v["sil"]
    out = Z.uygula(df, {"deleted_rows": [0], "added_rows": [{"SKU": "C", "Adet": 5}]}, v["kolonlar"])
    assert list(out["SKU"]) == ["B", "C"] and list(out.index) == [1, 2]
    assert out.iloc[1]["Adet"] == 5 and not bool(out.iloc[1]["Sil"])


def test_tarih_secim_ve_bos_deger():
    df = pd.DataFrame([{"Yön": "giris", "Tarih": pd.Timestamp("2026-10-01"), "Tutar": 10.0},
                       {"Yön": "harcama", "Tarih": pd.NaT, "Tutar": 20.0}])
    cfg = {"Yön": {"type_config": {"type": "selectbox", "options": ["giris", "harcama"]}, "required": True},
           "Tarih": {"type_config": {"type": "date"}}}
    v = Z.duzenle_veri(df, cfg)
    assert v["satirlar"][1]["v"][1] is None and v["satirlar"][0]["v"][1] == "2026-10-01"
    out = Z.uygula(df, {"edited_rows": {"1": {"Tarih": "2026-10-05", "Yön": "giris"}, "0": {"Tarih": None}}},
                   v["kolonlar"])
    assert out.loc[1, "Tarih"] == pd.Timestamp("2026-10-05") and pd.isna(out.loc[0, "Tarih"])
    assert out.loc[1, "Yön"] == "giris"


def test_bos_durum_ayni_nesne():
    df, _ = _siparis()
    assert Z.uygula(df, {}, _veri()["kolonlar"]) is df


# ── Veri değişince eski durum geçersiz ──────────────────────────────
def test_eski_durum_veri_degisince_yok_sayilir():
    eski = {"edited_rows": {"0": {"Adet": 9}}, "added_rows": [{"SKU": "X"}], "deleted_rows": []}
    bayat = {a: Z._js(v) for a, v in eski.items()}
    assert Z.gecerli_durum(eski, bayat) == {}
    # kullanıcı yeni veride yalnız bir hücre düzeltti: eski eklenen satır HÂLÂ yok sayılmalı
    yeni = dict(eski, edited_rows={"1": {"Adet": 2}})
    assert Z.gecerli_durum(yeni, bayat) == {"edited_rows": {"1": {"Adet": 2}}}
    assert Z.gecerli_durum(eski, None) == {k: v for k, v in eski.items()}


# ── Yönlendirme ─────────────────────────────────────────────────────
def test_destekli_mi():
    df, cfg = _siparis()
    assert Z.destekli_mi(df, {"column_config": cfg, "key": "k", "hide_index": True, "disabled": ["SKU"],
                              "use_container_width": True, "height": 300, "num_rows": "fixed"})
    assert not Z.destekli_mi(df, {"column_config": cfg, "on_change": lambda: None})        # bilinmeyen ayar
    assert not Z.destekli_mi([{"a": 1}], {})                                              # DataFrame değil
    assert not Z.destekli_mi(pd.DataFrame({"a": range(Z.AZAMI_SATIR + 1)}), {})            # çok uzun


def test_uygulamadaki_tum_duzenleyiciler_destekli_ayar_kullaniyor():
    """16 st.data_editor çağrısı yalnız desteklenen anahtar kelimeleri ve sütun türlerini kullanıyor
    (aksi hâlde o ekran sessizce eski tabloda kalırdı)."""
    import ast
    import re
    kotu = []
    for p in KOK.rglob("*.py"):
        if any(x in p.parts for x in ("tests", ".git", ".venv")):
            continue
        src = p.read_text(encoding="utf-8")
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "data_editor":
                for k in n.keywords:
                    if k.arg not in Z._DESTEKLI_ARG:
                        kotu.append(f"{p.name}:{n.lineno} {k.arg}")
                seg = ast.get_source_segment(src, n) or ""
                for t in re.findall(r"column_config\.(\w+)", seg):
                    if t not in ("TextColumn", "NumberColumn", "CheckboxColumn", "SelectboxColumn", "DateColumn"):
                        kotu.append(f"{p.name}:{n.lineno} {t}")
    assert not kotu, kotu


def test_data_editor_yonlendirmesi_ve_geri_alma():
    src = (KOK / "shared" / "izgara.py").read_text(encoding="utf-8")
    assert "if TABLO_SADE and not a:" in src and "_dz.destekli_mi(data, kw)" in src
    assert 'kok_mu = self is getattr(_st, "_main", None)' in src    # sütun içinde çizim sütunda kalsın
    import shared.tasarim as T
    assert T.TABLO_SADE is True


# ── Salt okunur ortak tablo ─────────────────────────────────────────
def test_ortak_tablo_sade_bilgisi():
    v = TB.tablo_veri([{"SKU": "A1", "Ürün": "X", "Birim maliyet": 2.5, "Kâr": 1.0, "Marj %": 30.0}])
    assert v["sade"] and v["birlesik"] == {"ad": 1, "sku": 0} and v["soluk"] == [2]
    assert TB.sade_ek(["Ürün", "Toplam maliyet"])["soluk"] == []


def test_ortak_tablo_sade_renksiz_marj_js():
    assert "if (k.rozet && r.rz[j] && !D.sade)" in TB._JS                 # marj rozeti boyanmaz
    assert '"gizli"' in TB._JS and "BIR.sku" in TB._JS                    # SKU ürün altında


# ── JavaScript sözdizimi (node varsa) ───────────────────────────────
@pytest.mark.skipif(not shutil.which("node"), reason="node yok")
@pytest.mark.parametrize("js", [Z._JS, TB._JS], ids=["duzenle", "tablo"])
def test_js_sozdizimi(tmp_path, js):
    f = tmp_path / "b.mjs"
    f.write_text(js, encoding="utf-8")
    r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
