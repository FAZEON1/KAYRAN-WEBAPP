# -*- coding: utf-8 -*-
"""Takılı ipucu kutuları ve pencere üstünde kalan menü düğmesi (Ekim 2026).

Kullanıcı ekranı: Sipariş penceresinin üstünde "Muhasebe", "Depo", "Satış" ipucu kutuları ve
kenar çubuğu daralt/genişlet düğmesi duruyordu. Tarayıcıda (Playwright) yeniden üretildi:
üst menüde üç modül gezildikten sonra üç ipucu da görünür kalıyor, pencere açılınca onun
üstünde çiziliyordu. Bu testler düzeltmenin yerinde durduğunu denetler."""
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def test_ipucu_bekcisi_kurulu():
    import shared.ipucu as I
    js = I._JS
    # yalnız hedefi etkin (fare üstünde / klavye odağında) olan ipucu görünür
    assert 'stTooltipContent' in js and 'stTooltipHoverTarget' in js
    assert ":hover" in js and ":focus-visible" in js
    # düğüm silinmez, yalnız gizlenir (Streamlit'in kendi düğümü)
    assert "visibility" in js and ".remove()" not in js
    app = (KOK / "app.py").read_text(encoding="utf-8")
    assert "from shared.ipucu import kur as _ipucu_kur" in app and "_ipucu_kur()" in app


def test_pencere_acikken_menu_dugmesi_gizli():
    app = (KOK / "app.py").read_text(encoding="utf-8")
    assert 'body:has(div[data-testid="stDialog"]) #kayran-sb-toggle{display:none !important;}' in app
