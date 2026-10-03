# -*- coding: utf-8 -*-
"""İkonlar 2. adım (Ekim 2026): ekrana doğrudan yazılan metinlerdeki emoji temizlendi;
kalanların sayısı yalnız AZALABİLİR (cırcır). Yeni ekran kodu emoji yerine
:material/ikon: ya da shared.tasarim.ikon_html kullanmalı."""
import json
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _oku(p):
    return (KOK / p).read_text(encoding="utf-8")


def _say():
    import importlib.util
    sp = importlib.util.spec_from_file_location("emoji_say", KOK / "tests" / "emoji_say.py")
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def test_emoji_sayisi_artmaz():
    say = _say().say
    taban = json.loads(_oku("tests/emoji_taban.json"))
    simdi = say()
    artan = {f: (taban.get(f, 0), n) for f, n in simdi.items() if n > taban.get(f, 0)}
    assert not artan, ("Ekranda görünen emoji eklendi (taban → şimdi): " + str(artan)
                       + " — emoji yerine :material/ikon: kullan. Bilerek azalttıysan tests/emoji_taban.json'u düşür.")


def test_ornek_metinler_temiz():
    a = _oku("app.py")
    assert "**📦 Ürünler" not in a and "**Ürünler (" in a
    s = _oku("satis/main.py")
    assert "**📦 Siparişler**" not in s and "**Siparişler** — kalem" in s


def test_durum_noktalari_korunur():
    """🔴 / 🟢 renkle anlam taşır; temizlenmedi (ikon karşılığı 3. adımda)."""
    K = _say().KOK
    toplam = sum(p.read_text(encoding="utf-8").count("🟢") for p in K.rglob("*.py")
                 if "tests" not in p.parts and "pycache" not in str(p))
    assert toplam > 0


# ── Sık kullanılan ekranlarda görünen emojiler (tarayıcı taramasıyla bulundu) ──
def test_grup_basligi_emojiyi_ikona_cevirir():
    from shared.bilesen import grup_basligi
    h = grup_basligi("📤 Dışa aktar", "Excel")
    assert "📤" not in h and "k-ikon" in h and "outbox" in h and "Dışa aktar" in h


def test_grup_basligi_emojisiz_ayni():
    from shared.bilesen import grup_basligi
    assert grup_basligi("Firma kırılımı", "x") == ('<div class="k-grup"><b>Firma kırılımı</b>'
                                                   '<span>x</span><i></i></div>')


def test_bugun_sorumlu_kisi_ikonu():
    from shared.bugun import satir_html
    h = satir_html({"oncelik": "kritik", "baslik": "Müşteri dosyası yüklenmedi · 👤 Derya", "detay": "x",
                    "sayi": 1, "hedef": "kayranpm", "anahtar": "a"})
    assert "👤" not in h and "person" in h and "Derya" in h


def test_yukleme_takvimi_seridi_ikonlu():
    src = _oku("shared/yukleme_takvimi.py")
    assert '{"⏰" if d["seviye"] != "guncel" else "🗓"}' not in src


def test_veri_sagligi_satiri():
    src = _oku("kayranpm/main.py")
    assert "🩺 <b>Veri sağlığı" not in src and "🏷️/💲" not in src


def test_talep_ust_satiri_ikonlu():
    src = _oku("app.py")
    assert 'f"👤 {_t.get(\'gonderen\')' not in src and ":material/person:" in src


def test_yukleme_karti_sorumlu_ikonu():
    src = _oku("shared/yukleme_takvimi.py")
    assert 'margin-top:4px">👤 {' not in src


def test_ithalat_bos_mesaji_yeni_sekme_adi():
    assert "'➕ Yeni İthalat' sayfasından" not in _oku("ithalat/main.py")
