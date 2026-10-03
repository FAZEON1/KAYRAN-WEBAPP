# -*- coding: utf-8 -*-
"""Tabloların 4. adımı (Ekim 2026): düzenlenebilir tablolarda (data_editor) sayılar Türkçe.

Tarayıcıda (tr-TR) ölçüldü: "dollar" → $1.234.567,89 (TR, 2 hane) · "localized" → TR,
hane sayısı step'ten (step=0.0001 → 7,2938; step yoksa en çok 3 hane) · "%.2f" / "$%.2f" /
"%.1f%%" / biçimsiz → İngilizce. Hane kuralı: tests/test_sayi_dil.py."""
import ast
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _sutunlar(dosya, sutun):
    """Tabloyu SÜTUN ADIYLA bulur (satır numarasıyla bulmak kırılgandı: dosya kısalınca kaydı)."""
    src = (KOK / dosya).read_text(encoding="utf-8")
    t = ast.parse(src)
    ed = next(n for n in ast.walk(t) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "data_editor"
              and f'"{sutun}"' in (ast.get_source_segment(src, n) or ""))
    out = {}
    for k in ed.keywords:
        if k.arg == "column_config" and isinstance(k.value, ast.Dict):
            for anahtar, deger in zip(k.value.keys, k.value.values):
                out[ast.literal_eval(anahtar)] = ast.get_source_segment(src, deger)
    return out


def test_urun_yonetimi_toplu_fiyat():
    s = _sutunlar("kayranpm/main.py", "Satış ($)")
    assert 'format="dollar"' in s["Satış ($)"] and "step=0.01" in s["Satış ($)"]   # step=1 → "$6" (kuruş kayboluyordu)
    assert 'format="localized"' in s["Marj %"] and "step=0.1" in s["Marj %"]


def test_satis_girisi_adet():
    src = (KOK / "satis/main.py").read_text(encoding="utf-8")
    assert 'NumberColumn("Adet", min_value=0, step=1, format="localized")' in src


def test_marka_kategori_ata_ciro_kar_sayi():
    s = _sutunlar("satis/main.py", "Kategori")
    assert "NumberColumn" in s["Ciro"] and 'format="dollar"' in s["Ciro"]
    assert "NumberColumn" in s["Kâr"] and 'format="dollar"' in s["Kâr"]
    assert 'format="localized"' in s["Adet"] and "step=1" in s["Adet"]


def test_dollar_sutunlari_kurus_gosterir():
    """"dollar" hane sayısını step'ten alır; step yoksa "$33,25" → "$33" (tarayıcıda görüldü)."""
    import re
    kotu = []
    for d in ("kayranpm/main.py", "satis/main.py", "satis/satislar_ekran.py"):
        src = (KOK / d).read_text(encoding="utf-8")
        for m in re.finditer(r"NumberColumn\(([^()]*(?:\([^()]*\)[^()]*)*)\)", src):
            if 'format="dollar"' in m.group(1) and not re.search(r"\bstep\s*=", m.group(1)):
                kotu.append(f"{d}: {m.group(1)[:50]}")
    assert not kotu, kotu
