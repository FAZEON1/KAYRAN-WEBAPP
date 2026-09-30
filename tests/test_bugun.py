# -*- coding: utf-8 -*-
"""D2 · Ana sayfa 'Bugün' paneli."""
import sys
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from shared import bugun as B  # noqa: E402

BUGUN = date(2026, 9, 30)


def _o(vade, durum="bekliyor", tl=0, usd=0, firma="X"):
    return {"vade": vade, "durum": durum, "tutar_tl": tl, "tutar_usd": usd, "firma": firma}


def test_odeme_gruplari():
    m = B.maddeler_odeme([
        _o("2026-09-28", tl=1000, firma="A"), _o("2026-09-29", usd=10, firma="B"),
        _o("2026-09-30", tl=500, firma="C"),
        _o("2026-10-01", tl=1, firma="D"),
        _o("2026-10-05", tl=1),                        # sonra → görünmez
        _o("2026-09-01", durum="odendi", tl=9999),     # ödenmiş → görünmez
        _o("", tl=5), _o("bozuk", tl=5),               # vadesiz/bozuk → görünmez
    ], BUGUN, kur=40)
    d = {x["anahtar"]: x for x in m}
    assert set(d) == {"odeme_gecmis", "odeme_bugun", "odeme_yarin"}
    assert d["odeme_gecmis"]["sayi"] == 2 and d["odeme_gecmis"]["oncelik"] == "kritik"
    assert "₺1.400" in d["odeme_gecmis"]["detay"]          # 1000 + 10*40
    assert d["odeme_bugun"]["oncelik"] == "uyari"
    assert d["odeme_yarin"]["oncelik"] == "bilgi"


def test_odeme_yoksa_madde_yok():
    assert B.maddeler_odeme([], BUGUN) == []
    assert B.maddeler_odeme(None, BUGUN) == []


def test_acil_siparis_en_yakin_once():
    m = B.maddeler_acil_siparis([
        {"sku": "UZAK", "siparis_durum": "acil", "stok_bitis_gun": 20},
        {"sku": "YAKIN", "siparis_durum": "acil", "stok_bitis_gun": 2},
        {"sku": "NORMAL", "siparis_durum": "planlama"},
    ])
    assert len(m) == 1 and m[0]["sayi"] == 2
    assert m[0]["detay"].index("YAKIN") < m[0]["detay"].index("UZAK")


def test_stok_hatasi_son_7_gun():
    m = B.maddeler_stok_hatasi([
        {"sku": "A", "zaman": "2026-09-29T10:00"},
        {"sku": "B", "zaman": "2026-09-10T10:00"},    # eski → sayılmaz
    ], "2026-09-30")
    assert m[0]["sayi"] == 1 and m[0]["oncelik"] == "kritik"
    assert B.maddeler_stok_hatasi([], "2026-09-30") == []


def test_talep_tamamlanan_sayilmaz():
    m = B.maddeler_talep([{"konu": "a", "durum": "yeni"}, {"konu": "b", "durum": "tamamlandi"}])
    assert m[0]["sayi"] == 1


def test_siralama_kritik_once():
    m = B.sirala([B._madde("bilgi", "x", "", 9, "a", "1"),
                  B._madde("kritik", "y", "", 1, "a", "2"),
                  B._madde("uyari", "z", "", 5, "a", "3")])
    assert [x["oncelik"] for x in m] == ["kritik", "uyari", "bilgi"]


def test_satir_html_kacirir():
    h = B.satir_html(B._madde("kritik", "<b>x</b>", "<script>", 1, "a", "1"))
    assert "<script>" not in h and "<b>x</b>" not in h


def test_topla_hic_yetki_yoksa_bos_ve_cokmez():
    assert B.topla({}, False, False) == []


def test_anasayfa_bugun_paneli_ve_dekor_temizligi():
    src = (KOK / "app.py").read_text(encoding="utf-8")
    bas = src.index("def anasayfa():")
    govde = src[bas:src.index("\ndef ", bas + 10)]
    assert "_bugun_panel(aktif_kullanici, yetkiler)" in govde
    for dekor in ("get_gunun_sozu", "get_mola_ipucu", "tarafından geliştirildi",
                  "Tüm servisler aktif", "Bir modüle geçmek için kartına tıkla"):
        assert dekor not in govde, dekor
    # Kur kaydı (tarihsel kur için) ana sayfada KALMALI
    assert "kur_kaydet(tr_today(), _dv[\"USD\"])" in govde
    # Net Kâr Patron Panosu'yla tekrar etmesin
    assert "if _finans_gor and not _patron_gor:" in govde
