# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Kampanya Takip liste masası (Ekim 2026, ortak masa shared/masa.py).

Özet bandı eski kpi_serit ile aynı hesap ve metin (kampanya_hesap.kampanya_ozet, shared.tasarim.sayi),
sıra kampanya_hesap.filtrele (durum, sonra bitiş), süzgeç anahtarları filtrele ile aynı (firma_kanonik +
DİĞER, kategori_anahtar, başlangıç yılı). Satıra tıklama bugünkü detay penceresini ister (B.detay_ac).
"""
from datetime import date

from kayranpm import kampanya_hesap as H
from kayranpm import kampanya_masasi as M
from shared.masa import istek_al, kosul_uyar
from shared.tasarim import sayi, tr_sayi

BUGUN = date(2026, 10, 14)


def _k(i, ad, firma, bas, bit, durum="aktif", kat="monitör", notlar=""):
    return dict(id=i, kampanya_adi=ad, firma=firma, baslangic_tarihi=bas, bitis_tarihi=bit, durum=durum,
                kategori=kat, kampanya_turu="Sellout", spiff_tl=0, spiff_kur=0, notlar=notlar)


KAMPS = [
    _k(1, "Okula dönüş", "VATAN", "2026-10-01", "2026-10-31"),                       # sürüyor
    _k(2, "Ekran kartı haftası", "HB", "2026-09-01", "2026-09-30", kat="ekran kartı"),  # bekliyor
    _k(3, "Yaz", "KANAL", "2026-06-01", "2026-06-30", durum="kapali"),                # kapalı, DİĞER
    _k(4, "Gelecek", "Örnek Bilgisayar Ltd", "2026-11-01", "2026-11-15", notlar="özel not"),   # yaklaşan
    _k(5, "Geçen yıl", "VATAN", "2025-06-01", "2025-06-30", durum="kapali"),
]
KU = {1: [dict(sku="A", satis_fiyati=120, birim_firma_destek=5, birim_ek_destek=1, satilan_adet=100, pacal_maliyet=80)],
      2: [dict(sku="B", satis_fiyati=300, birim_firma_destek=20, birim_ek_destek=0, satilan_adet=10, pacal_maliyet=0)],
      3: [dict(sku="C", satis_fiyati=50, birim_firma_destek=10, birim_ek_destek=0, satilan_adet=4, pacal_maliyet=60)],
      5: [dict(sku="A", satis_fiyati=100, birim_firma_destek=0, birim_ek_destek=0, satilan_adet=0, pacal_maliyet=80)]}
PACAL = {"B": 250.0}
KATLAR = ["ekran kartı", "monitör"]


def _veri():
    return M.masa_verisi(KAMPS, KU, PACAL, BUGUN, KATLAR, firma_ad=lambda f: f"AD:{f}", kat_ad=str.title,
                         aralik=lambda k: f"{k['baslangic_tarihi']}…", kalan=lambda o: f"kalan {o['kalan']}")


def test_ozet_eski_kpi_ile_ayni():
    v = _veri()
    oz = {k["id"]: H.kampanya_ozet(k, KU.get(k["id"], []), PACAL, BUGUN) for k in KAMPS}
    bu_yil = [oz[k["id"]] for k in KAMPS if k["baslangic_tarihi"].startswith("2026")]
    d = {k["k"]: k for k in v["ozet"]}
    assert d["suruyor"]["dg"] == "1" and d["suruyor"]["al"] == "1 yaklaşan"
    assert d["bekliyor"]["dg"] == "1" and d["bekliyor"]["renk"] == "amber" and d["bekliyor"]["suz"] == "bekliyor"
    destek = sum(o["destek"] for o in bu_yil)
    assert d["destek"]["dg"] == sayi(destek, "$") == "$840" and d["destek"]["ipucu"] == f"${tr_sayi(destek, 2)}"
    net = sum(o["net"] for o in bu_yil if o["adet"] > 0)                    # 100×34 + 10×30 + 4×(−20) = 3.620
    assert net == 3620 and d["net"]["dg"] == sayi(net, "$") and d["net"]["renk"] == "yesil"
    assert d["net"]["al"].startswith("net marj %") and v["say"]["bekliyor"] == 1


def test_sira_ve_satir_metinleri():
    v = _veri()
    assert [s["id"] for s in v["satirlar"]] == [k["id"] for k in H.filtrele(KAMPS, BUGUN)] == [2, 1, 4, 3, 5]
    r = {s["id"]: s for s in v["satirlar"]}
    assert r[1]["net_m"] == "$3.400,00" and r[1]["destek_m"] == "$600,00" and r[1]["adet_m"] == "100 adet"
    assert r[1]["marj_m"] == f"marj %{tr_sayi(3400 / 11400 * 100, 1)}" and r[1]["net_renk"] == "yesil"
    assert r[2]["net_m__s"] == 300.0                             # kayıtta paçal 0 → güncel paçal (250) gösterimde
    assert r[3]["net_m"] == "-$80,00" and r[3]["net_renk"] == "kirmizi" and r[3]["_soluk"]
    assert r[4]["net_m"] == "satış bekleniyor" and r[4]["destek_m"] == "" and r[4]["net_m__s"] is None
    assert r[5]["net_m"] == "adet girilmedi"
    assert r[1]["_durum"] == {"ad": "Sürüyor", "renk": "yesil"} and r[2]["durum__s"] == 0
    assert r[1]["meta"] == "AD:VATAN · Monitör · Sellout" and r[1]["aralik"] == "2026-10-01…"


def test_suzgec_anahtarlari_filtrele_ile_ayni():
    v = _veri()
    sec = {s["alan"]: s for s in v["secimler"]}
    assert [o["k"] for o in sec["firma_s"]["secenekler"]] == ["HB", "VATAN", "Örnek Bilgisayar Ltd", "DİĞER"]
    assert sec["firma_s"]["secenekler"][-1]["ad"] == "DİĞER"
    from shared.ana_veri import kategori_anahtar
    assert [o["k"] for o in sec["kat_s"]["secenekler"]] == [kategori_anahtar(x) for x in KATLAR]
    assert [o["ad"] for o in sec["kat_s"]["secenekler"]] == ["Ekran Kartı", "Monitör"]
    assert [o["k"] for o in sec["yil"]["secenekler"]] == ["2026", "2025"]
    for alan, deger, eski in [("firma_s", "DİĞER", dict(firma="DİĞER")), ("firma_s", "VATAN", dict(firma="VATAN")),
                              ("yil", "2025", dict(yil="2025"))]:
        yeni = [s["id"] for s in v["satirlar"] if str(s[alan]) == deger]
        assert sorted(yeni) == sorted(k["id"] for k in H.filtrele(KAMPS, BUGUN, **eski))
    kat = sec["kat_s"]["secenekler"][0]["k"]
    assert sorted(s["id"] for s in v["satirlar"] if s["kat_s"] == kat) == \
        sorted(k["id"] for k in H.filtrele(KAMPS, BUGUN, kategori="ekran kartı"))
    gor = {g["k"]: g["f"] for g in v["gorunumler"]}
    assert [s["id"] for s in v["satirlar"] if kosul_uyar(s, gor["guncel"])] == [2, 1, 4]
    assert "özel not" in r_ara(v, 4)


def r_ara(v, i):
    return next(s for s in v["satirlar"] if s["id"] == i)["ara_ek"]


def test_istek_ve_yurut(monkeypatch):
    from shared import bilesen as B
    cagri = []
    monkeypatch.setattr(B, "detay_ac", lambda *a: cagri.append(a))
    v = _veri()
    t, h = istek_al(v, {"islem": "ac", "ids": [3]})
    assert h is None
    assert M.yurutucu()(t) == {"ok": True, "yenileme": False, "sessiz": True} and cagri == [("kmp", 3)]
    for istek, parca in [({"islem": "ac", "ids": [99]}, "bulunamadı"), ({"islem": "ac", "ids": [1, 2]}, "tek"),
                         ({"islem": "kapat", "ids": [1]}, "Bilinmeyen")]:
        assert parca in istek_al(v, istek)[1]


def test_bos_liste():
    v = M.masa_verisi([], {}, {}, BUGUN)
    assert v["satirlar"] == [] and v["say"] == {"bekliyor": 0, "suruyor": 0, "yaklasan": 0, "kapali": 0}
