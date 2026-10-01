# -*- coding: utf-8 -*-
"""Ref No Takibi (Ekim 2026 yeniden tasarım) — hesap katmanı ve ekran kuralları.

Eski ekranda:
  • "Toplam Tutar" farklı para birimlerini yan yana yazıp en büyük SAYIYI öne
    çıkarıyordu (₺1,5M büyük, $177K küçük) — gerçek toplam görünmüyordu;
  • liste firma adına göre sıralıydı (tüm VATAN önce), aylık iş akışı kayboluyordu;
  • "Görünen N kaydı sil" ONAYSIZ siliyordu;
  • EUR/USD kuru her çizimde internetten çekiliyordu (6 sn zaman aşımı).
"""
import ast
import json
from pathlib import Path

from kayranpm import ref_hesap as R

KOK = Path(__file__).resolve().parent.parent


def _r(i=1, d="beklemede", tutar=1000, dv="USD", ay="2026-09", **kw):
    x = {"id": i, "ref_no": f"FZVTNRF2026{i:03d}", "durum": d, "tutar": tutar, "doviz": dv,
         "aylik": json.dumps({ay: tutar}) if ay else "", "aciklama": "EYLÜL SELLOUT", "kategori": "MONİTÖR"}
    x.update(kw)
    return x


def test_usd_karsiligi_ve_cevrilemeyenler_ayri():
    t = R.toplam([_r(1), _r(2, tutar=41240, dv="TL"), _r(3, tutar=1000, dv="EUR")], eur_usd=1.1, usd_try=41.24)
    assert round(t["usd"], 2) == round(1000 + 1000 + 1100, 2)
    assert t["cevrilmeyen"] == {}
    t2 = R.toplam([_r(1), _r(2, tutar=41240, dv="TL")], eur_usd=1.1, usd_try=None)
    assert t2["usd"] == 1000 and t2["cevrilmeyen"] == {"TL": 41240}    # sessizce yanlış toplam yok


def test_donem_ve_gruplama_en_yeni_ay_ustte():
    g = R.grupla([_r(1, ay="2026-07"), _r(2, ay="2026-09"), _r(3, ay="2026-09"), _r(4, ay="", tarih="")])
    assert [d for d, _ in g] == ["2026-09", "2026-07", ""]
    assert [x["id"] for x in g[0][1]] == [3, 2]                        # grup içinde ref no büyükten
    assert R.donem_adi("2026-09") == "Eylül 2026" and R.donem_adi("") == "Dönemsiz"


def test_cok_ayli_donem_metni():
    r = _r(aylik=json.dumps({"2026-08": 1, "2026-10": 1}))
    assert R.donem_metni(r) == "Ağustos – Ekim 2026"


def test_filtre():
    rs = [_r(1), _r(2, d="paylasildi"), _r(3, kategori="KASA", ay="2025-12")]
    assert [x["id"] for x in R.filtrele(rs, "beklemede")] == [1, 3]
    assert [x["id"] for x in R.filtrele(rs, kategori="KASA")] == [3]
    assert [x["id"] for x in R.filtrele(rs, yil="2025")] == [3]
    assert [x["id"] for x in R.filtrele(rs, ara="fzvtnrf2026002")] == [2]


def test_firma_ozeti_bekleyen_sayisi():
    rs = [_r(1, _fid=1), _r(2, d="paylasildi", _fid=1), _r(3, _fid=2)]
    assert R.firma_ozet(rs) == {1: {"adet": 2, "beklemede": 1}, 2: {"adet": 1, "beklemede": 1}}


def test_ref_no_render_yeni_ekrana_gider():
    src = (KOK / "kayranpm/ref_no.py").read_text(encoding="utf-8")
    g = src[src.index("def render():"):src.index("def _render_eski():")]
    assert "from .ref_ekran import render" in g


def test_toplu_sil_onayli():
    src = (KOK / "kayranpm/ref_no.py").read_text(encoding="utf-8")
    g = src[src.index("def _dlg_ref_toplu_sil"):]
    g = g[:g.index("st.button(\"Toplu Sil\"")]
    assert "_onay_g = st.checkbox(" in g and "not _onay_g" in g


def test_eur_kuru_onbellekli():
    agac = ast.parse((KOK / "kayranpm/ref_no.py").read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(agac) if isinstance(n, ast.FunctionDef) and n.name == "_eur_usd_kur")
    assert any("cache_data" in ast.unparse(d) for d in fn.decorator_list)


def test_ekran_silmeleri_onayli():
    """Ref ve alınan destek silme ortak onaylı düğmeyle (shared/bilesen.onayli_sil);
    firma silme onay kutusu işaretlenmeden pasif."""
    src = (KOK / "kayranpm/ref_ekran.py").read_text(encoding="utf-8")
    assert 'B.onayli_sil(f"Evet, {r.get(\'ref_no\')} kaydını sil", key=f"ref_{rid}"' in src
    assert 'B.onayli_sil("Evet, bu kaydı sil", key=f"ad2_{r[\'id\']}"' in src
    assert "disabled=not onay or (adet and not refsil)" in src
