# -*- coding: utf-8 -*-
"""Hızlandırma (Ekim 2026, yeni görünümden sonra): ölçümle bulunan üç neden.
1) Sunucu ↔ tarayıcı mesajları sıkıştırılmıyordu (masa verisi MB'larca). 2) Masa görünüm durumunu sunucuya
yazıyordu: her çip / tuş / sıralama tüm sayfayı yeniden çalıştırıyordu (tests/test_masa.py). 3) Odakta olmayan sayı
kutusu tekerleği yutuyordu: formlu sayfalar ve telefonda Hesap makinesi aşağı kaymıyordu."""
import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))


def test_websocket_sikistirmasi_acik():
    c = (KOK / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    server = c.split("[server]", 1)[1].split("\n[", 1)[0]
    assert re.search(r"^enableWebsocketCompression\s*=\s*true\s*$", server, re.M)


def test_sayi_kutusu_tekerlegi_sayfayi_kaydirir():
    from shared import palet
    js = palet._JS
    assert "if (!window.__kayranTeker){" in js                                   # pencereye bir kez
    assert 'window.addEventListener("wheel", ev => {' in js and "{capture: true, passive: false}" in js
    # yalnız odakta OLMAYAN sayı kutusu: yazarken (odakta) davranış değişmez
    assert "if (!t || t === document.activeElement) return;" in js
    assert 'input[type="number"], [data-testid="stNumberInput"] input' in js
    # kutuyu içeren kaydırılabilir alan (açık pencere dahil), yoksa sayfa
    assert "kap.scrollBy({top: ev.deltaY, left: ev.deltaX});" in js and '[data-testid="stMain"]' in js


def test_masa_suzme_siralama_sunucuya_gitmez():
    from shared import masa
    assert 'setStateValue("durum"' not in masa._JS and "sessionStorage.setItem(DK" in masa._JS
