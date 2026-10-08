# -*- coding: utf-8 -*-
"""Rol bazlı ana sayfa ve telefona kurulum (Ekim 2026): Bugün paneline teknik servis / ithalat / depo işleri,
Kısayollarım, uygulama simgesi ve manifest."""
import json
from datetime import date
from pathlib import Path

from shared import bugun as G

KOK = Path(__file__).resolve().parent.parent
BUGUN = date(2026, 10, 8)


def test_teknik_servis_yedi_gunu_gecenler():
    k = [{"mevcut_durum": "mal kabül", "mal_kabul_tarihi": "2026-09-20T10:00:00+00:00", "stok_adi": "Monitör A"},
         {"mevcut_durum": "mal kabül", "mal_kabul_tarihi": "2026-10-05", "stok_adi": "Yeni"},          # 3 gün
         {"mevcut_durum": "Teknisyende", "mal_kabul_tarihi": None, "olusturma_tarihi": "2026-09-30",
          "stok_adi": "Klavye"},
         {"mevcut_durum": "satışa hazır", "mal_kabul_tarihi": "2026-01-01", "stok_adi": "Eski ama bitti"}]
    m = G.maddeler_teknik_servis(k, BUGUN)
    assert [(x["baslik"], x["sayi"], x["hedef"]) for x in m] == [
        ("Mal kabulde 7 günü geçen cihaz", 1, "teknikservis/servis"),
        ("Teknisyende 7 günü geçen cihaz", 1, "teknikservis/servis")]
    assert m[0]["detay"].startswith("En eskisi 18 gündür bekliyor · Monitör A")


def test_ithalat_gecikmis_ve_yakin():
    d = [{"dosya_no": "IT-1", "durum": "Antrepoda", "tahmini_varis": "2026-09-01"},
         {"dosya_no": "IT-2", "durum": "Gümrükte", "tahmini_varis": "2026-10-12"},
         {"dosya_no": "IT-3", "durum": "Teslim Alındı", "tahmini_varis": "2026-09-01"},
         {"dosya_no": "IT-4", "durum": "Antrepoda", "tahmini_varis": "2026-12-01"},
         {"dosya_no": "IT-5", "durum": "Antrepoda", "tahmini_varis": None}]
    m = G.maddeler_ithalat(d, BUGUN)
    assert [(x["baslik"], x["sayi"], x["oncelik"]) for x in m] == [
        ("Tahmini varışı geçmiş ithalat", 1, "uyari"), ("7 gün içinde gelecek ithalat", 1, "bilgi")]
    assert "IT-1" in m[0]["detay"] and "Antrepoda" in m[0]["detay"] and m[1]["hedef"] == "ithalat/gecmis"


def test_depo_sevk_acik():
    t = [{"firma": "EERA", "fatura_adet": 10, "sevk_edilen": 4}, {"firma": "X", "fatura_adet": 5, "sevk_edilen": 5},
         {"firma": "Y", "fatura_adet": None, "sevk_edilen": None}]
    m = G.maddeler_depo_sevk(t)
    assert len(m) == 1 and m[0]["sayi"] == 1 and m[0]["detay"] == "EERA" and m[0]["hedef"] == "depo/bekleyen"
    assert G.maddeler_depo_sevk([]) == []


def test_bugun_yetkiye_gore_okur(monkeypatch):
    okunan = []
    monkeypatch.setattr(G, "_oku", lambda tablo, *a, **k: okunan.append(tablo) or [])
    G.topla({"teknikservis": True})
    assert "ts_kayitlar" in okunan and "ithalat_dosyalari" not in okunan and "depo_manuel_takip" not in okunan


def test_bugun_hedefi_sayfayi_acar():
    app = (KOK / "app.py").read_text(encoding="utf-8")
    assert 'args=tuple(str(_m["hedef"]).split("/", 1))' in app
    from shared.gezinme import secenek_kodundan
    for h in ("teknikservis/servis", "ithalat/gecmis", "depo/bekleyen"):
        assert secenek_kodundan(*h.split("/")), h


# ── Kısayollarım ────────────────────────────────────────────────────
def test_kisayollar_en_cok_acilan_ve_yetkili():
    from shared.kisayol import sec
    o = ([{"modul": "satis", "sayfa": "satislar"}] * 5 + [{"modul": "anasayfa", "sayfa": ""}] * 9
         + [{"modul": "kayranacc", "sayfa": "bu_hafta"}] * 3 + [{"modul": "depo", "sayfa": "stok"}] * 4
         + [{"modul": "soru", "sayfa": ""}] * 2 + [{"modul": "bilinmeyen", "sayfa": "x"}] * 8)
    k = sec(o, lambda m: m != "kayranacc")
    assert [x["etiket"] for x in k] == ["Satış · Satışlar", "Depo · Depo stok", "Soru sor"]
    assert k[0]["sayfa"] == "satislar" and k[2]["sayfa"] is None and k[0]["adet"] == 5
    assert sec([], lambda m: True) == []


def test_kisayollar_en_fazla_alti():
    from shared.kisayol import sec
    from shared.gezinme import secenekler, sayfa_kodu
    o = [{"modul": "kayranpm", "sayfa": sayfa_kodu("kayranpm", s)} for s in secenekler("kayranpm")]
    assert len(sec(o, lambda m: True)) == 6


# ── Telefona kurulum ────────────────────────────────────────────────
def test_manifest_ve_simgeler():
    m = json.loads((KOK / "static/manifest.json").read_text(encoding="utf-8"))
    assert m["display"] == "standalone" and m["short_name"] == "KAYRAN" and m["lang"] == "tr"
    for i in m["icons"]:
        p = KOK / "static" / i["src"]
        assert p.exists() and p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", i["src"]
    assert (KOK / "static/apple-touch-icon.png").exists()
    cfg = (KOK / ".streamlit/config.toml").read_text(encoding="utf-8")
    assert "[server]" in cfg and "enableStaticServing = true" in cfg


def test_kurulum_betigi():
    from shared.pwa import kurulum_betigi
    b = kurulum_betigi()
    assert b.startswith("<script>") and b.endswith("</script>")
    for parca in ("rel:'manifest'", "manifest.json", "apple-touch-icon.png", "apple-mobile-web-app-capable",
                  "theme-color", "app/static/", "getElementById('kayran-manifest')", "window.top"):
        assert parca in b, parca
    app = (KOK / "app.py").read_text(encoding="utf-8")
    assert "+ _pwa_betigi(), height=0)" in app and 'key="nav_telefon"' in app
