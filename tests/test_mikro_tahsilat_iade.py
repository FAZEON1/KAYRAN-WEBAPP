# -*- coding: utf-8 -*-
"""Kullanıcı (22.10.2026): "1 ve 3 yapalım. 6 oran uygulansın."
1) Tahsilat listesi — Mikro müşteri alacakları (120), canlı (kayranacc/mikro_tahsilat.py). Canlı: VATAN 1.448.465 $
   ve D-Market 533.292 $ "30 GÜN SATIŞ ŞARTLI" planında → gecikmiş sayılmaz; gerçek gecikmiş 60.967 $ + 55.947 TL.
3) Otomatik satış eşitlemesi iade satırlarını da toplu silmez (okuma hatası koruması).
6) İade deposu: Sıddık'a iade deposundan satış yok; oran = iade deposundan çıkan sevklerin gittiği deponun oranıyla
   ağırlıklı (canlı: Merkez 3.330, servis 23, outlet 16, Happy Life 8, ikinci el 7 adet → %99,42)."""
from datetime import date

import pytest

from kayranacc import mikro_odeme as O

try:
    from kayranacc import mikro_tahsilat as T
except ImportError:          # eski kodda yok: tahsilat testleri atlanır; iade sınırı ve iade oranı testleri kırmızı
    T = None
_T = pytest.mark.skipif(T is None, reason="kayranacc.mikro_tahsilat yok")

KART = [{"cari_kod": "120.01.003", "cari_unvan1": "VATAN BILGISAYAR", "cari_doviz_cinsi": 1},
        {"cari_kod": "120.02.009", "cari_unvan1": "SND BİLİŞİM", "cari_doviz_cinsi": 1},
        {"cari_kod": "120.02.022", "cari_unvan1": "GREEN BİLGİSAYAR", "cari_doviz_cinsi": 1}]
PLAN_AD = {2: "30 GÜN SATIŞ ŞARTLI", 6: "30 GÜN VADE"}
PLAN_GUN = {2: 30, 6: 30}


def _h(kod, tip, tutar, tarih, vade=0, evrak=63, aciklama="", guid=None):
    return {"cha_guid": guid or f"{kod}{tarih}{tip}{tutar}", "cha_tip": tip, "cha_cari_cins": 0, "cha_kod": kod,
            "cha_d_cins": 1, "cha_d_kur": 1, "cha_karsidcinsi": 1, "cha_karsid_kur": 1, "cha_meblag": tutar,
            "cha_evrak_tip": evrak, "cha_evrakno_seri": "G5F", "cha_evrakno_sira": 1, "cha_belge_no": None,
            "cha_tarihi": tarih, "cha_vade": vade, "cha_aciklama": aciklama}


HAR = [_h("120.01.003", 0, 1000, "2026-07-01", vade=2),                        # satış şartlı: vadesi 31.07
       _h("120.01.003", 1, 300, "2026-10-20", evrak=34, aciklama="YKB USD - VATAN GELEN"),
       _h("120.02.009", 0, 500, "2026-08-17", vade=6),                         # 30 gün → 16.09: gecikmiş
       _h("120.02.009", 1, 50, "2026-10-01", evrak=0, aciklama="X İADESİ"),    # iade: tahsilat değil
       _h("120.02.022", 0, 223, "2026-10-13", vade=6),                         # 12.11
       _h("120.02.022", 1, 23, "2026-10-21", evrak=33, aciklama="120-340 HESAP VİRMANI")]


def test_musteri_alacagi_kalem_yonu():
    """Müşteri hesabında kalem borç (fatura, cha_tip 0); tahsilat / iade (alacak) en eski vadeden düşer."""
    k = O.acik_kalemler(HAR[:4], KART, PLAN_GUN, onekler=("120",), kalem_tipi=0)
    acik = {r["cari_kod"]: r["acik"] for r in k}
    assert acik == {"120.01.003": 700.0, "120.02.009": 450.0}
    assert {r["cari_kod"]: r["plan"] for r in k} == {"120.01.003": 2, "120.02.009": 6}


@_T
def test_ozet_satis_sartli_gecikmis_sayilmaz():
    k = O.acik_kalemler(HAR, KART, PLAN_GUN, onekler=("120",), kalem_tipi=0)
    s = {r["cari_kod"]: r for r in T.ozet(k, date(2026, 10, 22), PLAN_AD)}
    assert s["120.01.003"]["satisa_bagli"] == 700 and s["120.01.003"]["gecikmis"] == 0
    assert s["120.02.009"]["gecikmis"] == 450 and s["120.02.009"]["gecikme_gun"] == 36
    assert s["120.02.022"]["sonraki"] == [0, 0, 200.0, 0]                      # 12.11: üçüncü hafta (virman düştü)
    t = T.toplamlar(list(s.values()))[1]
    assert t["toplam"] == pytest.approx(700 + 450 + 200) and t["satisa_bagli"] == 700


@_T
def test_son_tahsilatlar_yalniz_havale_ve_pos():
    s = T.son_tahsilatlar(HAR, KART, date(2026, 10, 22))
    assert [(r["cari_kod"], r["tutar"]) for r in s] == [("120.01.003", 300.0)]   # iade ve virman yok


@_T
def test_plan_adi_satis_sartli():
    assert T.satisa_bagli_mi("30 GÜN SATIŞ ŞARTLI") and T.satisa_bagli_mi("60 gün satış şartlı")
    assert not T.satisa_bagli_mi("30 GÜN VADE") and not T.satisa_bagli_mi(None)


def test_tahsilat_sayfasi_menude():
    from shared.gezinme import MODULLER
    acc = next(m for m in MODULLER if m["kod"] == "kayranacc")
    assert "📥 Tahsilat" in [s[0] for s in acc["sayfalar"]]
    assert any("tahsilat" in g[2] for g in acc["gruplar"])


# ── 3) İade silme sınırı ──────────────────────────────────────────
def test_otomatik_tur_iadeleri_toplu_silmez():
    from satis.mikro_esitle import otomatik_guvenli_mi
    assert otomatik_guvenli_mi({"silinecek_satir": 0, "mevcut_satir": 5000, "silinecek_iade": 40,
                                "mevcut_iade": 600})
    assert not otomatik_guvenli_mi({"silinecek_satir": 0, "mevcut_satir": 5000, "silinecek_iade": 590,
                                    "mevcut_iade": 600})


def test_plan_iade_sayilarini_tasir():
    from pathlib import Path
    s = (Path(__file__).resolve().parent.parent / "satis" / "mikro_esitle.py").read_text(encoding="utf-8")
    assert '"silinecek_iade": len(silinen_iade), "mevcut_iade": len(iadeler)' in s


# ── 6) İade deposu oranı ──────────────────────────────────────────
def test_iade_deposu_sevk_agirlikli_oran():
    from kayranacc import mikro_stok_degeri as SD
    assert SD.depo_turu("İADE DEPO ") == "iade" and SD.depo_turu("IADE DEPO") == "iade"
    orn = {"hurda": {"ort": 0.231, "sku": {}}, "outlet": {"ort": 0.976, "sku": {}},
           "ikinci_el": {"ort": 0.788, "sku": {}}}
    sevk = [{"giris": "MERKEZ DEPO", "adet": 3330}, {"giris": "TEKNİK DEPO", "adet": 23},
            {"giris": "OUTLET DEPO", "adet": 16}, {"giris": "HAPPY LIFE", "adet": 8},
            {"giris": "İKİNCİ EL DEPO", "adet": 7}]
    io = SD.iade_orani(sevk, orn)
    assert io["ort"] == pytest.approx(0.9942, abs=1e-4) and io["adet"] == 3384
    assert SD.iade_orani([], orn) is None
    orn["iade"] = io
    d = SD.depo_degerleri([{"sku": "A", "depo_kirilim": {"İADE DEPO": 10, "MERKEZ DEPO": 5}}], {"A": 100.0}, orn)
    assert d["deger"]["İADE DEPO"] == pytest.approx(10 * 100 * 0.9942, abs=0.01)
    assert d["deger"]["MERKEZ DEPO"] == pytest.approx(500)
