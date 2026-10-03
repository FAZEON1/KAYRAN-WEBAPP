# -*- coding: utf-8 -*-
"""Gezinme yenileme (Ekim 2026) — 1. paket: sayfa kayıt defteri + komut paleti + adres çubuğu."""
import ast
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _g():
    from shared import gezinme
    return gezinme


# ── Kayıt defteri ───────────────────────────────────────────────────
def test_modul_sayfa_listeleri_kayit_defterinden():
    """Modüllerin menü seçenekleri kayıt defteriyle AYNI kalmalı; elle liste yazılırsa
    palet ve adres çubuğu o sayfayı bulamaz."""
    g = _g()
    beklenen = {"kayranpm": ("kayranpm/main.py", 8), "depo": ("depo/main.py", 5),
                "ithalat": ("ithalat/main.py", 4), "teknikservis": ("teknikservis/main.py", 6),
                "satis": ("satis/main.py", 5), "kayranacc": ("kayranacc/main.py", 13)}
    for mod, (dosya, n) in beklenen.items():
        assert len(g.secenekler(mod)) == n, mod
        src = (KOK / dosya).read_text(encoding="utf-8")
        assert f'secenekler("{mod}")' in src, dosya


def test_secenek_metinleri_modul_kodunda_birebir():
    """Modüller sayfayı metin karşılaştırmasıyla seçer (sayfa == "📋  Tüm Ürünler").
    Kayıt defterindeki metin tek boşlukla bile farklıysa o sayfa açılmaz."""
    g = _g()
    dosya = {"kayranpm": "kayranpm/main.py", "depo": "depo/main.py", "ithalat": "ithalat/main.py",
             "teknikservis": "teknikservis/main.py", "satis": "satis/main.py", "kayranacc": "kayranacc/main.py"}
    for mod, d in dosya.items():
        src = (KOK / d).read_text(encoding="utf-8")
        ss = g.secenekler(mod)
        for sec in ss[:-1]:                    # son seçenek çoğu modülde else dalıyla açılır
            assert f'"{sec}"' in src, (mod, sec)


def test_her_modul_menusunun_anahtari_var():
    """Muhasebe menüsünün anahtarı yoktu → palet/adres çubuğu sayfaya gidemezdi."""
    g = _g()
    for m in g.MODULLER:
        if m.get("sayfalar"):
            assert m.get("anahtar"), m["kod"]
    src = (KOK / "kayranacc" / "main.py").read_text(encoding="utf-8")
    t = ast.parse(src)
    radyolar = [n for n in ast.walk(t) if isinstance(n, ast.Call)
                and (getattr(n.func, "attr", "") == "radio" or getattr(n.func, "id", "") == "sayfa_menusu")
                and any(k.arg == "label_visibility" for k in n.keywords)]
    assert any(any(k.arg == "key" and getattr(k.value, "value", None) == "acc_sayfa" for k in r.keywords)
               for r in radyolar)


def test_sayfa_kodlari_essiz_ve_url_dostu():
    import re
    g = _g()
    for m in g.MODULLER:
        kodlar = [s[1] for s in m.get("sayfalar", [])]
        assert len(kodlar) == len(set(kodlar)), m["kod"]
        assert all(re.fullmatch(r"[a-z0-9_]+", k) for k in kodlar), kodlar


def test_url_kodu_gidis_donus():
    g = _g()
    assert g.sayfa_kodu("kayranpm", "📋  Tüm Ürünler") == "tum_urunler"
    assert g.secenek_kodundan("kayranpm", "tum_urunler") == "📋  Tüm Ürünler"
    assert g.secenek_kodundan("kayranpm", "yok_boyle") is None
    assert g.sayfa_kodu("anasayfa", None) is None


# ── Palet öğeleri ───────────────────────────────────────────────────
def _hep(kosul, kullanici):
    return True


def test_palet_yetkiye_gore_suzer():
    g = _g()
    yet = {"kayranpm": True, "satis": True, "kayranacc": False}
    o = g.palet_ogeleri(yet, ozel=set(), kullanici="derya", kosul=_hep)
    idler = {x["id"] for x in o}
    assert "kayranpm/tum_urunler" in idler and "satis/pnl" in idler
    assert not any(i.startswith("kayranacc/") for i in idler)
    assert "sistem/cop_kutusu" in idler                    # herkes
    assert "sistem/kullanici_yonetimi" not in idler        # özel yetki


def test_palet_kosullu_sayfa():
    g = _g()
    yet = {"satis": True}
    o = g.palet_ogeleri(yet, ozel=set(), kullanici="derya", kosul=lambda k, u: k != "kar")
    assert "satis/pnl" not in {x["id"] for x in o}


def test_palet_ogesi_alanlari():
    g = _g()
    o = g.palet_ogeleri({"kayranpm": True}, ozel=set(), kullanici="x", kosul=_hep)
    t = next(x for x in o if x["id"] == "kayranpm/tum_urunler")
    assert t["ad"] == "Tüm ürünler" and t["yol"] == "Ürün yönetimi" and t["ikon"] and t["tur"] == "sayfa"
    assert "tum urunler" in t["ara"]                       # Türkçe harfsiz arama da tutar


def test_islemler_var():
    g = _g()
    o = g.palet_ogeleri({"satis": True, "ithalat": True}, ozel=set(), kullanici="x", kosul=_hep)
    islem = {x["ad"] for x in o if x["tur"] == "islem"}
    assert "Yeni satış girişi" in islem and "Yeni ithalat" in islem


# ── Hedef çözümü ────────────────────────────────────────────────────
def test_hedef_sayfa():
    g = _g()
    h = g.hedef("kayranpm/tum_urunler")
    assert h == {"modul": "kayranpm", "anahtar": "pm_sayfa", "secenek": "📋  Tüm Ürünler"}
    assert g.hedef("sistem/cop_kutusu") == {"modul": "cop_kutusu", "anahtar": None, "secenek": None}
    assert g.hedef("anasayfa") == {"modul": "anasayfa", "anahtar": None, "secenek": None}
    assert g.hedef("uydurma/sayfa") is None


def test_arama_sonuclari_ogeye_doner():
    g = _g()
    s = {"urunler": [{"sku": "FZ-K100", "urun_adi": "Fazeon K100 Kasa"}],
         "cariler": [{"firma_adi": "VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI", "firma_kodu": "120.01"}],
         "satislar": [{"id": 5, "tarih": "2026-09-01", "kanal": "VATAN", "siparis_no": "S1", "sku": "FZ-K100"}]}
    o = g.arama_ogeleri(s)
    u = next(x for x in o if x["tur"] == "urun")
    assert u["id"] == "urun:FZ-K100" and "Fazeon K100 Kasa" in u["ad"]
    c = next(x for x in o if x["tur"] == "cari")
    assert c["ad"] == "Vatan Bilgisayar A.Ş." and c["id"] == "kayranacc/cari_ekstre"
    assert any(x["id"] == "satis/satislar" for x in o)
    assert g.hedef("urun:FZ-K100") == {"stok_karti": "FZ-K100"}


# ── Bağlantılar ─────────────────────────────────────────────────────
def test_ust_menude_palet_arama_dugmesi_yok():
    src = (KOK / "app.py").read_text(encoding="utf-8")
    g = src[src.index("def ust_navigasyon"):]
    g = g[:g.index("\ndef ", 10)]
    assert '("Arama", "arama"' not in g
    assert "_palet_ciz(" in g
    assert "from shared.palet import palet" in src


def test_ctrl_k_paleti_acar():
    src = (KOK / "app.py").read_text(encoding="utf-8")
    assert "__kayranPaletAc" in src


def test_adres_cubugunda_sayfa():
    src = (KOK / "app.py").read_text(encoding="utf-8")
    assert "adres_yaz(" in src and "adres_oku(" in src


# ── 2. paket: sayfa menüsü üstte (geri alınabilir) ──────────────────
MENU_MODULLERI = {"kayranpm": "kayranpm/main.py", "depo": "depo/main.py", "ithalat": "ithalat/main.py",
                  "teknikservis": "teknikservis/main.py", "satis": "satis/main.py", "kayranacc": "kayranacc/main.py"}


def test_geri_alma_anahtari_tek_satir():
    """Beğenilmezse GitHub web düzenleyicisinde tek satır: MENU_UST = False."""
    src = (KOK / "shared" / "gezinme.py").read_text(encoding="utf-8")
    import re
    assert len(re.findall(r"^MENU_UST = (True|False)\s", src, re.M)) == 1


def test_moduller_ortak_menuyu_kullanir():
    for mod, d in MENU_MODULLERI.items():
        src = (KOK / d).read_text(encoding="utf-8")
        assert "sayfa_menusu(" in src and f'modul="{mod}"' in src, d
        t = ast.parse(src)
        for n in ast.walk(t):
            if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "radio" and n.args \
                    and isinstance(n.args[0], ast.Constant) and n.args[0].value == "Sayfa":
                raise AssertionError(f"{d}: sayfa menüsü hâlâ doğrudan st.radio")


def test_sekme_adlari_kayit_defterinden():
    g = _g()
    assert g.sekme_adi("kayranpm", "📋  Tüm Ürünler") == "Tüm ürünler"
    assert g.sekme_adi("satis", "📊 Kâr / P&L") == "Kâr / P&L"
    assert g.sekme_adi("yok", "🧾 Bilinmeyen") == "Bilinmeyen"      # kayıtta yoksa ikon/emoji atılır


def test_menu_kapaliyken_kenar_cubugu(monkeypatch):
    """MENU_UST = False → eskisi gibi çağıranın yerine (kenar çubuğu) çizilir."""
    import streamlit as st
    g = _g()
    cagri = {}

    def sahte_radio(etiket, secenekler, **kw):
        cagri.update(kw, etiket=etiket)
        return secenekler[0]
    monkeypatch.setattr(st, "radio", sahte_radio, raising=False)
    monkeypatch.setattr(g, "MENU_UST", False)
    assert g.sayfa_menusu("Sayfa", ["a", "b"], key="k", modul="depo", label_visibility="collapsed") == "a"
    assert cagri["key"] == "k" and cagri["label_visibility"] == "collapsed" and "horizontal" not in cagri


def test_app_seridi_kurar():
    src = (KOK / "app.py").read_text(encoding="utf-8")
    assert 'key="sayfa_seridi"' in src and "serit_kur(" in src
    assert ".st-key-sayfa_seridi" in src


# ── 3. paket: çok sayfalı modülde iki katlı sekme (grup + sayfa) ────
SEKME_SINIRI = 8


def test_cok_sayfali_modul_gruplanmis():
    """8'den fazla sayfa tek satıra sığmaz (Muhasebe 13 sayfa kesiliyordu)."""
    g = _g()
    for m in g.MODULLER:
        if len(m.get("sayfalar") or []) > SEKME_SINIRI:
            assert m.get("gruplar"), m["kod"]


def test_her_sayfa_tek_grupta():
    g = _g()
    for m in g.MODULLER:
        if not m.get("gruplar"):
            continue
        kodlar = [s[1] for s in m["sayfalar"]]
        gruptaki = [k for _, _, ks in m["gruplar"] for k in ks]
        assert sorted(gruptaki) == sorted(kodlar), m["kod"]
        assert len(m["gruplar"]) <= 6


def test_muhasebe_gruplari():
    g = _g()
    y = g.grup_yapisi("kayranacc", g.secenekler("kayranacc"))
    assert [a for a, _ in y] == ["Genel bakış", "Ödemeler", "Nakit", "Cari", "Veri ve raporlar"]
    assert dict(y)["Ödemeler"] == ["💳 Bu Hafta", "📋 Firma Çekleri", "⏳ Ertelenen Ödemeler", "🕐 Ödenenler & Geçmiş"]


def test_yetkisiz_sayfa_gruptan_duser():
    """Toplam aktifler yetkisi yoksa modül o sayfayı listeden çıkarır; grup boşalmaz."""
    g = _g()
    sec = [s for s in g.secenekler("kayranacc") if s != "💰 Toplam Aktifler"]
    y = dict(g.grup_yapisi("kayranacc", sec))
    assert "💰 Toplam Aktifler" not in y["Nakit"] and len(y["Nakit"]) == 3


def test_bos_grup_gosterilmez():
    g = _g()
    y = g.grup_yapisi("kayranacc", ["📊 Dashboard", "🧾 Cari Ekstre"])
    assert [a for a, _ in y] == ["Genel bakış", "Cari"]


def test_sayfanin_grubu():
    g = _g()
    assert g.grup_adi("kayranacc", "🧾 Cari Ekstre") == "Cari"
    assert g.grup_adi("kayranacc", "💸 Nakit Akış") == "Nakit"
    assert g.grup_adi("kayranpm", "📋  Tüm Ürünler") is None      # gruplanmamış modül
