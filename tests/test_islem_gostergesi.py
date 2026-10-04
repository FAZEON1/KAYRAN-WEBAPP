# -*- coding: utf-8 -*-
"""İşlem göstergesi (shared/islem.py, Ekim 2026).

Yavaş açılan sayfa boş görünüyordu; kayıt sürerken sayfa kapatılınca sipariş kaydolmuyordu.
Tarayıcıda doğrulandı (yapay 3 sn yavaşlatmayla): sayfa geçişinde "Yükleniyor…", düğmeyle başlayan
işlemde "İşlem sürüyor — lütfen sayfayı kapatma" + sayfadan ayrılma engeli, bitince "İşlem
tamamlandı" ve engel kalkar; yüklemede ayrılma engeli YOK (kullanıcı kararı A).
"""
import json
from pathlib import Path

import shared.islem as I

KOK = Path(__file__).resolve().parent.parent


def test_ayarlar_js_icine_gomulu():
    js = I._js()
    assert "__AYAR__" not in js
    ayar = json.loads(js[js.index("const A = ") + 10:js.index(";\n  const S")])
    assert ayar["metin"]["islem"] == "İşlem sürüyor — lütfen sayfayı kapatma"
    assert ayar["gecikme"] == 500 and ayar["ara"] >= 300 and ayar["tamam"] == 2000


def test_ayrilma_engeli_yalniz_islemde():
    js = I._JS
    b = js[js.index("function basladi()"):js.index("function bitti()")]
    yuk = b[b.index("} else {"):]
    assert "korumaAc()" in b and "korumaAc()" not in yuk          # yüklemede engel yok
    assert "korumaKapat()" in js[js.index("function bitti()"):]


def test_dugme_ve_dosya_secimi_islem_sayilir():
    assert '[data-testid="stButton"] button' in I.DUGME_SECICI
    assert "stFormSubmitButton" in I.DUGME_SECICI and "stDownloadButton" not in I.DUGME_SECICI
    assert "e.target.type === 'file'" in I._JS


def test_tek_kurulum_ve_sablon_metin_kacisi():
    js = I._JS
    assert "if (window.__kayranIslem) return;" in js
    assert "\\2" not in js                       # şablon metinde sekizlik kaçış JS'i bozuyordu


def test_app_her_calismada_kurar_ve_kap_gizli():
    a = (KOK / "app.py").read_text(encoding="utf-8")
    assert "from shared.islem import kur as _islem_kur" in a and "_islem_kur()" in a
    t = (KOK / "shared" / "tasarim.py").read_text(encoding="utf-8")
    assert ".st-key-kayran_islem_gostergesi" in t


def test_agir_sayfalarda_aciklamali_bekleme():
    for dosya, metin in (("kayranpm/stok_yasi_ekran.py", "Stok yaşı hesaplanıyor"),
                         ("kayranpm/genel_bakis.py", "Genel bakış hazırlanıyor"),
                         ("kayranpm/main.py", "Ürün listesi hazırlanıyor")):
        assert metin in (KOK / dosya).read_text(encoding="utf-8"), dosya
