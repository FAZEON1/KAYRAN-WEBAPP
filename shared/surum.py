# -*- coding: utf-8 -*-
"""Programın sürümü — TEK KAYNAK (Ekim 2026).

Ekrandaki "Sürüm x.y.z" (ana sayfa alt bilgisi), pyproject.toml ve CHANGELOG.md bu değere uyar;
sürüm değişince üçü birlikte güncellenir (tests/test_urun_yuzu.py denetler).
Anlamsal sürüm: BÜYÜK.KÜÇÜK.YAMA — kayıtlı veriyi/iş akışını bozan değişiklik BÜYÜK,
yeni özellik KÜÇÜK, düzeltme YAMA.
"""

SURUM = "1.0.0"


def surum_etiketi():
    """Ekranda gösterilen sade metin: 'Sürüm 1.0.0'."""
    return f"Sürüm {SURUM}"
