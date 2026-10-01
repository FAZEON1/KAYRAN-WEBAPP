# -*- coding: utf-8 -*-
"""Muhasebe yenileme — Paket 1 (Ekim 2026): Genel Bakış · Bu Hafta · Ertelenen.

Bulunan hatalar:
  1. Genel Bakış "Hafta sonu kalan" kartının HTML'i yarımdı (iki yerde tırnak
     ve '>' eksik) — kartın rakamı hiç görünmüyordu
  2. Bu Hafta gün başlıklarında ay adı İngilizce (strftime %B → "September")
  3. Ertelemeler yalnız tarayıcı oturumunda tutuluyordu (çıkışta kayboluyordu)
  4. odeme_vade_guncelle: önbellek temizleme hata bloğunun İÇİNDE kalmıştı
     (başarılı ötelemeden sonra eski vade görünüyordu); hata sessizce yutuluyordu
  5. "Ödendi" banka seçilmeden basılabiliyordu → bakiye sessizce düşülmüyordu
  6. Bu Hafta ile Genel Bakış hafta sonu tahminini FARKLI kurla hesaplıyordu
"""
import ast
from datetime import date
from pathlib import Path

from kayranacc import odeme_hesap as H

KOK = Path(__file__).resolve().parent.parent
B = date(2026, 10, 1)


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


def _o(i, vade, tl=None, usd=None, durum="bekliyor", kat="diger"):
    return {"id": i, "firma": f"F{i}", "vade": vade, "tutar_tl": tl, "tutar_usd": usd, "durum": durum, "kategori": kat}


O = [_o(1, "2026-09-28", tl=1000, durum="odendi"), _o(2, "2026-09-29", tl=500),
     _o(3, "2026-10-01", usd=100), _o(4, "2026-10-02", tl=200, kat="cek")]
BANKA = [{"para_birimi": "TL", "bakiye": 10000}, {"para_birimi": "USD", "bakiye": 999}]


def test_ozet_ve_hafta_sonu_formulu():
    oz = H.ozet(O, BANKA, 40, B)
    assert oz["tl"] == 1700 and oz["odendi_tl"] == 1000 and oz["bekleyen_tl"] == 700 and oz["bekleyen_usd"] == 100
    assert [o["id"] for o in oz["gecikmis"]] == [2] and [o["id"] for o in oz["bugun"]] == [3]
    assert oz["hafta_sonu_tl"] == 10000 - 700 - 100 * 40          # Genel Bakış ile aynı formül


def test_vade_durumu():
    assert [H.vade_durumu(o, B) for o in O] == ["odendi", "gecikmis", "bugun", "yarin"]
    assert H.vade_durumu(_o(9, None), B) == "tarihsiz"


def test_gun_basligi_turkce():
    assert H.gun_basligi("2026-09-28", B) == "Pazartesi, 28 Eylül"
    assert H.gun_basligi("2026-10-01", B) == "Bugün · Perşembe, 1 Ekim"
    assert H.gun_basligi("2026-09-30", B) == "Dün · Çarşamba, 30 Eylül"
    assert H.gun_basligi("2027-01-04", B).endswith("Ocak 2027")
    assert "September" not in H.gun_basligi("2026-09-28", B)


def test_gunlere_bol_once_bekleyen_sonra_oncelik():
    liste = [_o(1, "2026-10-01", tl=5, durum="odendi"), _o(2, "2026-10-01", tl=5, kat="diger"),
             _o(3, "2026-10-01", tl=5, kat="cek")]
    (gun, g), = H.gunlere_bol(liste, {"cek": 1, "diger": 13})
    assert gun == "2026-10-01" and [o["id"] for o in g] == [3, 2, 1]


def test_1_genel_bakis_karti_tamam():
    src = _oku("kayranacc/main.py")
    assert "trenk('kirmizi')}\n                <div class=\"kart-label\">" not in src     # eski yarım etiket
    assert '''trenk('kirmizi')}">₺{fmt(abs(hafta_sonu_tl))}</div>''' in src


def test_3_4_vade_ertele_kalici_ve_onbellek():
    src = _oku("kayranacc/database.py")
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "odeme_vade_guncelle")
    g = ast.get_source_segment(src, fn)
    assert "ertele=False" in g and '"ertelendi_sayisi"' in g and '"orijinal_vade"' in g
    assert "kaydet(" in g and "return False" in g                     # hata yutulmaz
    son = fn.body[-2:]                                                 # başarılı yolda önbellek temizlenir
    assert any("_cache_temizle" in ast.unparse(x) for x in son)
    assert (KOK / "veritabani/07_odeme_erteleme.sql").read_text(encoding="utf-8").count("IF NOT EXISTS") == 3


def test_5_odendi_banka_secimi_acik_karar():
    src = _oku("kayranacc/odeme_ekran.py")
    assert "index=None" in src and "_BANKASIZ" in src and "disabled=bsec is None" in src


def test_6_ayni_kur_kaynagi():
    assert "render_bu_hafta(KATEGORILER, export_excel, get_kur())" in _oku("kayranacc/main.py")
    assert "get_kur" not in _oku("kayranacc/odeme_ekran.py").split("def render_bu_hafta")[0].split("from .database")[1]


def test_ertelenenler_kalici_kayittan():
    m = _oku("kayranacc/main.py")
    assert "from .odeme_ekran import render_ertelenenler" in m
    assert 'st.session_state.get("ertelemeler", {})' not in m.split('elif sayfa == "⏳ Ertelenen Ödemeler":')[1][:600]
