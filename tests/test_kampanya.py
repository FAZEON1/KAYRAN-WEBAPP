# -*- coding: utf-8 -*-
"""Kampanya Takip (Ekim 2026 yeniden tasarım) — hesap katmanı ve ekran kuralları.

Eski ekranda bulunan hatalar:
  • üst özet 'pacal_maliyet' (ürün listesinde olmayan alan) okuyordu → Net Kâr hep $0
  • net marj iki farklı tanımla (kâr/satış · kâr/net satış)
  • "Toplam Destek Verilen" yalnız ek desteği topluyordu
  • süresi dolan kampanya "aktif" listesinde kalıyordu, hatırlatma yoktu
  • detay penceresi açılırken veritabanına paçal yazıyordu
  • geçmiş kampanya kartının HTML'i yarımdı (net kâr görünmüyordu)
"""
import ast
from datetime import date
from pathlib import Path

from kayranpm import kampanya_hesap as H

KOK = Path(__file__).resolve().parent.parent
B = date(2026, 10, 1)


def _k(**kw):
    k = {"id": 1, "kampanya_adi": "X", "firma": "HB", "baslangic_tarihi": "2026-09-24",
         "bitis_tarihi": "2026-10-14", "durum": "aktif"}
    k.update(kw)
    return k


def _u(sku="A", satis=119, fd=8, ed=3, adet=142, pacal=86.4):
    return {"sku": sku, "satis_fiyati": satis, "birim_firma_destek": fd, "birim_ek_destek": ed,
            "satilan_adet": adet, "pacal_maliyet": pacal}


def test_tek_formul_birim_kar_ve_marj():
    h = H.urun_hesap(_u())
    assert h["destek"] == 11 and h["net_satis"] == 108
    assert round(h["net_kar"], 2) == 21.6                    # (119 − 11) − 86,40
    assert round(h["marj"], 1) == 20.0                       # 21,60 / 108
    assert round(h["t_net"], 2) == round(21.6 * 142, 2)


def test_destek_toplami_firma_ve_ek_birlikte():
    o = H.kampanya_ozet(_k(), [_u(adet=10)])
    assert o["destek"] == 110 and o["firma_destek"] == 80 and o["ek_destek"] == 30


def test_pacal_kayitta_yoksa_guncel_kullanilir_ama_yazilmaz():
    h = H.urun_hesap(_u(pacal=0), guncel_pacal=86.4)
    assert h["pacal"] == 86.4 and h["pacal_guncelden"]
    h2 = H.urun_hesap(_u(pacal=0), guncel_pacal=0)
    assert h2["net_kar"] is None and h2["eksik_pacal"]


def test_spiff_net_kardan_duser():
    k = _k(spiff_tl=41200, spiff_kur=41.2)                   # $1.000
    o = H.kampanya_ozet(k, [_u(adet=100)])
    assert round(H.spiff_usd(k)) == 1000
    assert round(o["net"], 2) == round(21.6 * 100 - 1000, 2)


def test_durum_tarihten_hesaplanir():
    assert H.durum(_k(), B) == "suruyor"
    assert H.durum(_k(baslangic_tarihi="2026-10-20", bitis_tarihi="2026-11-15"), B) == "yaklasan"
    assert H.durum(_k(baslangic_tarihi="2026-09-01", bitis_tarihi="2026-09-28"), B) == "bekliyor"
    assert H.durum(_k(durum="kapali", bitis_tarihi="2026-09-28"), B) == "kapali"


def test_zaman_cizgisi():
    oran, kalan, gun = H.zaman(_k(), B)
    assert gun == 21 and kalan == 13 and 0.3 < oran < 0.4


def test_filtre_ve_siralama_dikkat_isteyen_ustte():
    ks = [_k(id=1), _k(id=2, baslangic_tarihi="2026-09-01", bitis_tarihi="2026-09-28"),
          _k(id=3, durum="kapali"), _k(id=4, firma="VATAN", baslangic_tarihi="2026-10-20",
                                       bitis_tarihi="2026-11-15")]
    assert [k["id"] for k in H.filtrele(ks, B)] == [2, 1, 4, 3]
    assert [k["id"] for k in H.filtrele(ks, B, firma="VATAN")] == [4]
    assert [k["id"] for k in H.filtrele(ks, B, durum_sec="kapali")] == [3]


def test_ekran_eski_hatali_alani_okumaz_ve_okurken_yazmaz():
    src = (KOK / "kayranpm/kampanya.py").read_text(encoding="utf-8")
    assert 'get("pacal_maliyet")' not in src.split("def _sekme_islemler")[0].replace(
        'u.get("pacal_maliyet", 0)', "")                     # yalnız kopyalarken okunur
    agac = ast.parse(src)
    for fn in (n for n in ast.walk(agac) if isinstance(n, ast.FunctionDef)
               and n.name in ("render", "_kart_html", "_detay_dialog", "_veri")):
        govde = ast.get_source_segment(src, fn)
        assert ".update(" not in govde and ".insert(" not in govde, fn.name


def test_kayranpm_eski_kampanya_blogu_kalkti():
    pm = (KOK / "kayranpm/main.py").read_text(encoding="utf-8")
    assert "from .kampanya import render as _kampanya_ekrani" in pm
    assert "_kampanya_detay_dialog" not in pm and "rows_ku" not in pm
