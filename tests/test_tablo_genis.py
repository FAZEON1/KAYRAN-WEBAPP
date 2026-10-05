# -*- coding: utf-8 -*-
"""Geniş tablolar tek bakışta (Ekim 2026). Arıza oranı (12 sütun) ve Stok yaşı (13 sütun)
tabloları sağa kaydırmadan okunamıyordu: başlıklar tek satıra zorlandığı için "Son kullanıcıya
ulaşan" gibi bir başlık 3 haneli sayının sütununu 150–190 px'e genişletiyordu; ürün adı "…" ile
kesiliyor, sade görünümde sabit kalan sütun görünmeyen SKU olduğu için ürün sütunu kayıyordu."""
import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from shared import tablo as TB  # noqa: E402


def _kural(secici):
    m = re.search(r"(?:^|[\n}])" + re.escape(secici) + r"\{([^}]*)\}", TB._CSS)   # kendi başına duran kural
    return m.group(1) if m else ""


def test_sayi_basliklari_iki_satira_sarilir():
    k = _kural("th.sag")
    assert "white-space:normal" in k, k
    # sayı HÜCRELERİ tek satırda kalır (1.234 bölünmez)
    assert "white-space:nowrap" in _kural("td.sag")


def test_urun_adi_kesilmez_iki_satira_sarilir():
    k = _kural(".adm")
    assert "-webkit-line-clamp:2" in k and "white-space:normal" in k, k
    assert "min-width:" in k                       # ad sütunu sayılara yenilip daralmaz
    assert '<span class="adm">' in TB._JS


def test_sade_gorunumde_urun_sutunu_yapisik():
    assert "position:sticky" in _kural(".yapis") and "left:0" in _kural(".yapis")
    assert '"yapis"' in TB._JS or "yapis" in TB._JS
    # yapışık sütun yalnız solunda görünür sütun yoksa (SKU gizli) — iki sütun üst üste binmez
    assert "YAPIS" in TB._JS


def test_tasan_tabloda_devam_golgesi():
    assert ".kap.devam" in TB._CSS
    assert 'classList.toggle("devam"' in TB._JS


def test_tam_ekran_dugmesi_ve_esc():
    assert ".kt.tam" in TB._CSS and "position:fixed" in _kural(".kt.tam")
    assert 'aria-label="Tam ekran"' in TB._JS
    assert '"Escape"' in TB._JS
    # tam ekranda tablo yüksekliği sınırı kalkar
    assert "max-height:none" in _kural(".kt.tam .kap")
