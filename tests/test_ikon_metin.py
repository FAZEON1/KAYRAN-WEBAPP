# -*- coding: utf-8 -*-
"""Emoji → ikon, 2. adım (Ekim 2026, merkezi): markdown / açıklama metinleri, başlıklar, anahtarlı kutu
etiketleri ve mesajların İÇİNDEKİ emojiler de süzülür. Durum noktaları (🔴🟢) ve ✓ • ▲ gibi işaretler kalır."""
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from shared import ikon as I  # noqa: E402


def test_ic_temizle_emojiyi_ve_ardindaki_boslugu_atar():
    assert hasattr(I, "ic_temizle"), "ikon.ic_temizle yok"
    assert I.ic_temizle("**📦 Ürünler**") == "**Ürünler**"            # kalın yazı bozulmaz
    assert I.ic_temizle("Stok: 📦 12 adet") == "Stok: 12 adet"
    assert I.ic_temizle("Durum 🟢 aktif ✓ • ▲") == "Durum 🟢 aktif ✓ • ▲"  # anlam taşıyan işaretler kalır
    assert I.ic_temizle("ok → yön · 1.234,56") == "ok → yön · 1.234,56"
    assert I.ic_temizle("⚠️ dikkat") == "dikkat" and I.ic_temizle(None) is None


def test_metin_markdownda_ikon_htmlde_atilir():
    assert hasattr(I, "metin"), "ikon.metin yok"
    assert I.metin("📦 Depo") == ":material/inventory_2: Depo"
    assert I.metin("📦 Depo", html=True) == "Depo"
    assert I.metin("<div>🚧 <b>Faz 1</b></div>", html=True) == "<div><b>Faz 1</b></div>"
    assert I.metin("emojisiz metin") == "emojisiz metin"


def test_mesaj_ve_bildirim_icindeki_emoji_de_gider():
    assert I.mesaj("success", "✅ Kaydedildi 🎉 tamam", None) == ("Kaydedildi tamam", ":material/check_circle:")
    assert I.toast("🗑️ 3 kayıt 📦 silindi", None) == ("3 kayıt silindi", ":material/delete:")


def test_kurulum_metin_ve_etiketleri_sarar():
    s = (KOK / "shared" / "ikon.py").read_text(encoding="utf-8")
    assert 'if not getattr(DG.markdown, "_kayran_ikon2", False):' in s       # canlı süreçte de kurulur
    assert '"markdown", "caption", "title", "header", "subheader") + _ETIKETLI' in s
    for ad in ("selectbox", "text_input", "number_input", "date_input", "radio", "multiselect"):
        assert f'"{ad}"' in s.split("_ETIKETLI = (", 1)[1].split(")", 1)[0], ad
    assert 'if kw.get("key") and isinstance(label, str):' in s               # anahtarsız kutunun kimliği değişmez


def test_tarayici_taramasi_emojiyi_denetler():
    t = (KOK / "tests" / "tarayici" / "tara.py").read_text(encoding="utf-8")
    assert 'ham["emoji"] = await pg.evaluate(_EMOJI_JS)' in t
