# -*- coding: utf-8 -*-
"""Emoji → çizgi ikon, merkezi katman (Ekim 2026) — 1. adım.

Mesaj kutusu, pencere başlığı, sekme, açılır bölüm ve düğme etiketlerinin
başındaki emoji Material ikona çevrilir (tanınmazsa atılır). Markdown/HTML
metinlerine dokunulmaz (2. adım, ekran ekran).
"""
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _i():
    from shared import ikon
    return ikon


# ── Baştaki emojiyi tanıma (dar) ────────────────────────────────────
def test_bas_emoji():
    I = _i()
    assert I.bas_emoji("✅ Kaydedildi") == ("check_circle", "Kaydedildi")
    assert I.bas_emoji("⚠️ Dosya açıldı") == ("warning", "Dosya açıldı")
    assert I.bas_emoji("❌ Hata") == ("cancel", "Hata")
    assert I.bas_emoji("🟢 Tamam") == (None, "Tamam")           # tanınmayan emoji atılır
    assert I.bas_emoji("💾  Veri yedekleme") == ("save", "Veri yedekleme")


def test_emoji_olmayan_dokunulmaz():
    I = _i()
    for m in ("**Kalın** metin", "→ Muhasebe", "-$5 fark", "(not) x", "12 kayıt", "", "• madde"):
        assert I.bas_emoji(m) == (None, m), m


def test_donus_oku_emoji_ama_oklar_degil():
    """↩️ (İade sekmesi) emoji; → ← gibi yön okları metin işaretidir, kalır."""
    I = _i()
    assert I.bas_emoji("↩️ İade") == ("undo", "İade")
    assert I.bas_emoji("→ Muhasebe") == (None, "→ Muhasebe")


def test_yalniz_emoji():
    I = _i()
    assert I.bas_emoji("✅") == ("check_circle", "")


# ── Mesaj kutuları ──────────────────────────────────────────────────
def test_mesaj_varsayilan_ikon():
    I = _i()
    assert I.mesaj("success", "✅ Yedek hazır", None) == ("Yedek hazır", ":material/check_circle:")
    assert I.mesaj("error", "❌ Kayıt başarısız", None) == ("Kayıt başarısız", ":material/error:")
    assert I.mesaj("warning", "Dikkat", None) == ("Dikkat", ":material/warning:")
    assert I.mesaj("info", "Bilgi", None) == ("Bilgi", ":material/info:")


def test_mesaj_verilen_ikon_korunur():
    I = _i()
    assert I.mesaj("warning", "⚠️ x", ":material/schedule:") == ("x", ":material/schedule:")
    assert I.mesaj("info", 123, None) == (123, ":material/info:")       # metin değilse gövdeye dokunma


def test_toast_ikonu_emojiden():
    I = _i()
    assert I.toast("🗑 Silindi", None) == ("Silindi", ":material/delete:")
    assert I.toast("Kaydedildi", "✅") == ("Kaydedildi", ":material/check_circle:")
    assert I.toast("x", None) == ("x", None)


# ── Etiketler ───────────────────────────────────────────────────────
def test_etiket_ikonu():
    I = _i()
    assert I.etiket("🔧 Teknik detay", None) == ("Teknik detay", ":material/build:")
    assert I.etiket("🟢 Durum", None) == ("Durum", None)
    assert I.etiket("📅 Tarih", ":material/event:") == ("Tarih", ":material/event:")
    assert I.etiket("Düz", None) == ("Düz", None)


def test_acilir_bolum_ikon_almaz():
    """Streamlit 1.64'te expander ikonu açma okunun YERİNE geçiyor; ok kaybolmasın
    diye emoji yalnız atılır (tarayıcıda yakalandı)."""
    I = _i()
    assert I.acilir("🔍 Detaylar", None) == ("Detaylar", None)
    assert I.acilir("Düz", None) == ("Düz", None)


def test_sekme_etiketi_markdown_ikon():
    I = _i()
    assert I.sekme("📊 Özet") == ":material/dashboard: Özet"
    assert I.sekme("🟢 Açık") == "Açık"
    assert I.sekme("Düz") == "Düz"


def test_durumlu_bilesen_anahtarsizsa_dokunulmaz():
    I = _i()
    assert I.durumlu("✅ Onaylı", None) == ("✅ Onaylı", None)          # kimliği etiketten → değer korunur
    assert I.durumlu("✅ Onaylı", "onay_1") == ("Onaylı", None)


# ── Bağlantılar ─────────────────────────────────────────────────────
def test_geri_alma_anahtari_tek_satir():
    src = (KOK / "shared" / "tasarim.py").read_text(encoding="utf-8")
    assert len(re.findall(r"^IKON_YENI = (True|False)\s", src, re.M)) == 1


def test_app_ikon_katmanini_kurar():
    src = (KOK / "app.py").read_text(encoding="utf-8")
    assert "from shared.ikon import kur as _ikon_kur" in src and "_ikon_kur(" in src


def test_sik_emojiler_esleniyor():
    """En sık kullanılanlar ikona çevrilmeli, atılmamalı."""
    I = _i()
    for e in "✅⚠❌📦➕📋📅🧾🔒🗑📥📊⏳📤💰🏷✏🔧🔍📄🚢🏬💸⛔💾":
        assert I.bas_emoji(e + " x")[0], e
