# -*- coding: utf-8 -*-
"""Hız çalışması (Ekim 2026) — geri dönüş korumaları.

Ölçüm (her sorguya 150 ms ağ gecikmesi, tek oturum, tıklamadan çizim sonuna):
ana sayfa 1,45 → 0,51 sn · Satış 1,12 → 0,48 · Yönetim 0,87 → 0,40.
Nedenler: (1) menü düğmeleri st.rerun() ile programı İKİ kez çalıştırıyordu,
(2) her tıklamada önbelleksiz sorgular gidiyordu.
"""
import ast
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _oku(yol):
    return (KOK / yol).read_text(encoding="utf-8")


def _fonksiyonlar(yol):
    agac = ast.parse(_oku(yol))
    return {n.name: n for n in ast.walk(agac) if isinstance(n, ast.FunctionDef)}


def _onbellekli(fn):
    return any("cache_data" in ast.unparse(d) or "cache_resource" in ast.unparse(d)
               for d in fn.decorator_list)


def _govde(yol, ad):
    src = _oku(yol)
    return ast.get_source_segment(src, _fonksiyonlar(yol)[ad])


# ── 1. Çift çalışma: sayfa değiştiren düğmeler on_click kullanır ──────────
def test_ust_menu_tek_calismada_sayfa_degistirir():
    g = _govde("app.py", "ust_navigasyon")
    assert "on_click=_sayfaya_git" in g
    assert "st.rerun()" not in g, "üst menü düğmesi st.rerun() ile programı iki kez çalıştırıyor"


def test_ana_sayfa_ve_sol_menu_dugmeleri_on_click():
    src = _oku("app.py")
    # 'aktif_uygulama = X' hemen ardından st.rerun() — eski çift çalışma deseni
    desen = re.compile(r'if [^\n]*\.button\([^\n]*\n(?:[^\n]*\n){0,4}?\s*st\.session_state\.aktif_uygulama = [^\n]+\n\s*st\.rerun\(\)')
    for ad in ("anasayfa", "portal_sidebar", "_bugun_panel"):
        g = _govde("app.py", ad)
        assert not desen.search(g), f"{ad}: düğme → st.rerun() çift çalışma deseni"
        assert "on_click=_sayfaya_git" in g, ad


# ── 2. Satış: kanal listesi önbellekli (ve kanal ekleme hatası) ───────────
def test_satis_kanal_listesi_onbellekli():
    f = _fonksiyonlar("satis/database.py")
    for ad in ("get_kanallar", "_kanallar_satistan", "get_manuel_kanallar"):
        assert _onbellekli(f[ad]), f"{ad} önbelleksiz: her tıklamada satış tablosu indirilir"
    # Dekoratör eskiden yanlış yerde (kanal_kok üstünde) kalmıştı → get_kanallar.clear()
    # AttributeError veriyor, 'Yeni kanal ekle' kaydı yapıp 'Kaydedilemedi' diyordu.
    assert not _onbellekli(f["kanal_kok"])
    tem = _govde("satis/database.py", "_temizle")
    assert "_kanallar_satistan" in tem and "get_manuel_kanallar" in tem
    assert "get_manuel_kanallar.clear()" in _govde("satis/database.py", "_manuel_kanal_yaz")


# ── 3. Muhasebe: ayar ve kur okumaları önbellekli, yazınca tazelenir ─────
def test_ayar_ve_kur_onbellekli_ve_tazelenir():
    f = _fonksiyonlar("kayranacc/database.py")
    for ad in ("_ayar_ham", "get_kur", "get_kur_araligi"):
        assert _onbellekli(f[ad]), ad
    assert "_ayar_ham.clear()" in _govde("kayranacc/database.py", "set_ayar")
    kk = _govde("kayranacc/database.py", "kur_kaydet")
    assert "get_kur.clear()" in kk and "get_kur_araligi.clear()" in kk


# ── 4. Ana sayfa: her tıklamada yazma / sorgu yok ─────────────────────────
def test_ana_sayfa_kur_kaydi_saatte_bir():
    g = _govde("app.py", "anasayfa")
    assert "_kur_kaydi_gerekli()" in g
    assert 'table("kullanici_durum")' not in g, "son giriş sorgusu her çizimde gidiyor"
    assert _onbellekli(_fonksiyonlar("app.py")["get_son_girisler"])


def test_bugun_stok_hatasi_onbellekli():
    g = _govde("shared/bugun.py", "topla")
    assert "_basarisiz_stok_hareketleri()" in g
    assert "gecmis(limit=200" not in g


# ── 5. Arama: yazarken yalnız arama parçası yenilenir ─────────────────────
def test_arama_parca_olarak_calisir():
    f = _fonksiyonlar("app.py")
    assert any("fragment" in ast.unparse(d) for d in f["_arama_parcasi"].decorator_list)
    g = _govde("app.py", "_arama_parcasi")
    assert 'st.rerun(scope="app")' in g, "sonuçtan modüle geçiş tüm sayfayı yenilemeli"
