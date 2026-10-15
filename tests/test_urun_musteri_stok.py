# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Tüm ürünler: ana stok sütunu MÜŞTERİ stoğu (Ekim 2026, kullanıcı isteği).

Eskiden sütun G5F (bizim depo) stoğunu gösteriyordu; müşteri stokları yalnız ürün adının altında küçük
yazıdaydı. Artık sütun müşteri stoğu: müşteri süzgeci boşken bütün müşterilerin toplamı, bir müşteri
seçiliyken (ör. VATAN) yalnız o müşterinin stoğu — sıralama da ona göre. G5F stoğu altta küçük yazıda kalır."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

KOK = Path(__file__).resolve().parent.parent


def _satir():
    from kayranpm import urun_masasi as M
    r = {"SKU": "X27F182S", "Ürün Adı": "FAZEON X27F182S", "Kategori": "Monitör", "Marka": "FAZEON",
         "G5F Depo": 1480, "Kanal dahil": 1931, "_kanal_stok": [("VATAN", 436), ("MONDAY", 15), ("EERA", 0)],
         "_stok_yas": 40, "_stok_renk": "yesil"}
    ad = {"VATAN": "VATAN BILGISAYAR", "MONDAY": "MONDAY BİLİŞİM", "EERA": "EERA ELEKTRONİK"}.get
    return M._satir(r, ad)


def test_satir_musteri_stogu_toplam_ve_musteri_bazinda():
    s = _satir()
    assert s.get("mus_m") == "451" and s.get("mus_m__s") == 451            # 436 + 15 (0 adetli müşteri sayılmaz)
    assert s.get("mus_stok") == {"VATAN BILGISAYAR": 436, "MONDAY BİLİŞİM": 15}
    assert s.get("mus_alt") == "G5F 1.480"


def test_ana_sutun_musteri_stogu_secime_gore():
    from kayranpm import urun_masasi as M
    v = M.masa_verisi([], firma_ad=lambda k: k)
    sut = {c["alan"]: c for c in v["sutunlar"]}
    assert "stok_m" not in sut, "ana sütun hâlâ G5F stoğu"
    c = sut["mus_m"]
    assert c["ad"] == "Müşteri stoğu" and c["alt"] == "mus_alt"
    assert c["secime_gore"] == {"secim": "mus", "harita": "mus_stok"}
    dar = {c["alan"]: c for c in M.masa_verisi([], dar=True, firma_ad=lambda k: k)["sutunlar"]}
    assert dar["mus_m"]["secime_gore"] == {"secim": "mus", "harita": "mus_stok"}


def test_masa_secime_gore_hucre_ve_siralama():
    js = (KOK / "shared" / "masa.py").read_text(encoding="utf-8")
    assert "secime_gore" in js and "const secDeg = " in js
    assert "const sd = secDeg(c, r)" in js                      # hücre seçili müşterinin değerini gösterir
    assert "secDeg(sk, x)" in js                                # sıralama da seçili müşteriye göre
