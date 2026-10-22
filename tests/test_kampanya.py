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


# ── Müşteri satışı (otomatik, yalnız gösterim — 22.10.2026) ──────────
# Kullanıcı: "Açık kampanyalarda satılan miktarlar ayrı bir sütunda ilgili firma için kampanyadaki modellere
# otomatik gösterilsin ama ben kampanya kapat / kaydet demeden bu adetler bir işlem yapmasın."
def _rap(firma, sku, tarih, satis, magaza=0, ad=""):
    return {"firma": firma, "sku": sku, "urun_adi": ad, "haftalik_satis": satis, "satis_magaza": magaza,
            "yukleme_tarihi": tarih}


def test_musteri_satisi_firma_tarih_ve_kod_haritasi():
    kamp = {"firma": "VATAN", "baslangic_tarihi": "2026-10-01", "bitis_tarihi": "2026-10-31", "durum": "aktif"}
    rap = [_rap("VATAN", "X24F182S", "2026-10-04", 100, 5),
           _rap("VATAN", "Fazeon X24F182S", "2026-10-11", 20),
           _rap("VATAN", "X24F182S", "2026-09-27", 999),             # kampanyadan önceki rapor
           _rap("ITOPYA", "X24F182S", "2026-10-04", 777),            # başka firma
           _rap("VATAN", "HBCV0000G0F6K6", "2026-10-18", 7)]          # pazaryeri kodu → kart
    m = H.musteri_satisi(kamp, rap, date(2026, 10, 22), {"HBCV0000G0F6K6": "X27F300"})
    assert m == {"X24F182S": 125, "X27F300": 7}
    assert H.musteri_satisi(dict(kamp, durum="kapali"), rap, date(2026, 10, 22)) is None
    assert H.musteri_satisi(dict(kamp, firma="KANAL"), rap, date(2026, 10, 22)) is None     # DİĞER: firma belli değil


def test_musteri_satisi_kayda_ve_hesaba_girmez():
    s = (KOK / "kayranpm" / "kampanya.py").read_text(encoding="utf-8")
    i = s.index("def _sekme_urunler(")
    blok = s[i:s.index("def _kaydet_urunler(")]
    assert '"Müşteri satışı", "Net kâr/adet"' in blok                         # düzenlenemez sütun
    assert 'for c in ("Satış", "Firma desteği", "Ek destek", "Satılan", "Not")' in blok   # değişiklik sayılmaz
    k = s[s.index("def _kaydet_urunler("):s.index("def _sekme_bilgiler(")]
    assert "Müşteri satışı" not in k
    u = {"satis_fiyati": 100, "birim_firma_destek": 5, "satilan_adet": 0, "pacal_maliyet": 80}
    assert H.urun_hesap(dict(u, **{"Müşteri satışı": 50}))["adet"] == 0


def test_rapor_haftalari_eksik_ve_yarim_hafta():
    # Canlı (22.10.2026): Eylül'de 6 ve 20 Eylül haftalarının raporu hiçbir müşteri için yüklenmemiş;
    # 14–21 Eylül kampanyası tam eksik haftaya düştüğü için 0 görünüyordu.
    rap = [_rap("HB", "X", "2026-09-13", 5), _rap("HB", "X", "2026-09-27", 5), _rap("VATAN", "X", "2026-09-20", 5)]
    kamp = {"firma": "HB", "baslangic_tarihi": "2026-09-01", "bitis_tarihi": "2026-09-30"}
    h = H.rapor_haftalari(kamp, rap, date(2026, 10, 22))
    assert h == {"var": ["2026-09-13", "2026-09-27"], "eksik": ["2026-09-06", "2026-09-20"], "yarim": True}
    h = H.rapor_haftalari(dict(kamp, baslangic_tarihi="2026-09-14", bitis_tarihi="2026-09-20"), rap, date(2026, 10, 22))
    assert h == {"var": [], "eksik": ["2026-09-20"], "yarim": False}
    h = H.rapor_haftalari(dict(kamp, baslangic_tarihi="2026-10-01", bitis_tarihi="2026-10-31"), rap, date(2026, 10, 12))
    assert h["eksik"] == ["2026-10-04", "2026-10-11"]                       # bugünden sonraki pazarlar beklenmez


def test_rapor_yoksa_sutun_bos_ve_not():
    s = (KOK / "kayranpm" / "kampanya.py").read_text(encoding="utf-8")
    assert 'oto.get(sku_anahtar(u.get("sku")), 0) if haftalar["var"] else None' in s
    assert "_hafta_notu(haftalar)" in s and "Eksik rapor:" in s
