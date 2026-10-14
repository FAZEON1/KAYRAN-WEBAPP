# -*- coding: utf-8 -*-
"""Salt-okur liste masası (shared/masa_liste.py, Ekim 2026): kalan eski st.dataframe listeleri ortak masaya.
Biçim (1.234,56 · ₺ · $ · %), sıralama anahtarı, süzgeç, arama, özet toplamı ve sayfaların geçişi."""
import re
import sys
from io import BytesIO
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

try:
    from shared.masa_liste import bicim, ciz, excel_bayt, kolon, veri  # noqa: E402
except ImportError:          # eski kodda modül yok: testler bu yüzden değil, aşağıdaki iddialarla kızarsın
    bicim = ciz = excel_bayt = veri = None

    def kolon(ad, tur="metin", **kw):
        return dict(kw, ad=ad, tur=tur)

KOL = [kolon("Ürün", ana=True, alt="SKU"), kolon("SKU", genis=True, dar="gizle"), kolon("Tarih", "tarih"),
       kolon("Firma", secim=True), kolon("Adet", "adet"), kolon("Tutar", "usd"), kolon("TL", "tl"),
       kolon("Oran", "yuzde"), kolon("Durum", "durum", secim=True)]
SAT = [{"Ürün": "SSD 512", "SKU": "FZ-1", "Tarih": "2026-10-14", "Firma": "VATAN", "Adet": 1234, "Tutar": 1234.5,
        "TL": 99.9, "Oran": 31.06, "Durum": ("Ödendi", "yesil")},
       {"Ürün": "Monitör", "SKU": "FZ-2", "Tarih": None, "Firma": "EERA", "Adet": None, "Tutar": -7,
        "TL": "", "Oran": None, "Durum": "Bekliyor"}]


def test_bicimler_turkce_ve_siralama_ham():
    assert bicim is not None, "shared.masa_liste yok"
    assert bicim("adet", 1234) == ("1.234", 1234.0)
    assert bicim("usd", 1234.5) == ("$1.234,50", 1234.5) and bicim("usd", -7)[0] == "-$7,00"
    assert bicim("tl", 99.9) == ("₺99,90", 99.9) and bicim("yuzde", 31.06) == ("%31,1", 31.06)
    assert bicim("sayi", 2.5, 1) == ("2,5", 2.5)
    assert bicim("tarih", "2026-10-14") == ("14.10.2026", "2026-10-14")
    assert bicim("adet", None) == ("", None) and bicim("tarih", "") == ("", None)
    assert bicim("metin", ("14.10.2026 15:30", "2026-10-14T12:30")) == ("14.10.2026 15:30", "2026-10-14T12:30")


def test_veri_sutunlar_satirlar_suzgec_arama():
    assert veri is not None, "shared.masa_liste yok"
    v = veri(SAT, KOL, toplam=["Adet", "Tutar"])
    s = {c["ad"]: c for c in v["sutunlar"]}
    assert s["Ürün"]["tip"] == "ana" and s["Ürün"]["alt"] == s["SKU"]["alan"] and s["Ürün"]["dar"] == "ana"
    assert s["Adet"]["sag"] and s["Adet"]["dar"] == "sag" and s["Tarih"]["dar"] == "alt"
    assert "dar" not in s["SKU"] and s["SKU"]["genis"] and s["Durum"]["tip"] == "durum"
    r0, r1 = v["satirlar"]
    a = {c["ad"]: c["alan"] for c in v["sutunlar"]}
    assert r0[a["Adet"]] == "1.234" and r0[a["Adet"] + "__s"] == 1234.0 and r0[a["Tarih"]] == "14.10.2026"
    assert r1[a["Adet"]] == "" and r1[a["Adet"] + "__s"] is None          # boş: masa "—", sıralamada sonda
    assert r0["_durum"] == {"ad": "Ödendi", "renk": "yesil"} and r1["_durum"] == {"ad": "Bekliyor", "renk": "soluk"}
    assert r0["_baslik"] == "SSD 512" and r0["_alt"] == "FZ-1" and ["Tutar", "$1.234,50"] in r0["_detay"]
    sec = {x["ad"]: [o["k"] for o in x["secenekler"]] for x in v["secimler"]}
    assert sec == {"Tüm firma": ["EERA", "VATAN"], "Tüm durum": ["Bekliyor", "Ödendi"]}
    assert set(v["ara"]["alanlar"]) == {a["Ürün"], a["SKU"], a["Firma"]}
    # tek kart sayfa boyu uzamasın: kayıt sayısı + toplamlar (eski tablonun TOPLAM satırı)
    assert [(k["et"], k["dg"]) for k in v["ozet"]] == [("Kayıt", "2"), ("Toplam adet", "1.234"),
                                                      ("Toplam tutar", "$1.227,50")]
    assert v["islemler"] == [] and v["gorunumler"][0]["f"] == []


def test_gizli_sutun_cizilmez_ama_aranir_ve_ayrintida():
    assert veri is not None, "shared.masa_liste yok"
    v = veri([{"Ürün": "SSD", "SKU": "FZ-1"}], [kolon("Ürün", ana=True, alt="SKU"), kolon("SKU", gizli=True)])
    assert [c["ad"] for c in v["sutunlar"]] == ["Ürün"] and v["sutunlar"][0]["alt"] == "k1"
    assert "k1" in v["ara"]["alanlar"] and ["SKU", "FZ-1"] in v["satirlar"][0]["_detay"]


def test_tek_degerli_sutunda_secim_cikmaz():
    assert veri is not None, "shared.masa_liste yok"
    v = veri([{"Ad": "a", "Depo": "MERKEZ"}, {"Ad": "b", "Depo": "MERKEZ"}], [kolon("Ad"), kolon("Depo", secim=True)])
    assert v["secimler"] == []


def test_excel_ham_sayi_ve_bicimli_tarih():
    assert veri is not None, "shared.masa_liste yok"
    import pandas as pd
    df = pd.read_excel(BytesIO(excel_bayt(SAT, KOL)))
    assert list(df.columns) == [k["ad"] for k in KOL]
    assert df.loc[0, "Adet"] == 1234 and df.loc[0, "Tarih"] == "14.10.2026" and df.loc[0, "Durum"] == "Ödendi"


def test_ciz_masaya_anahtarla_gider(monkeypatch):
    assert ciz is not None, "shared.masa_liste yok"
    from shared import masa as M
    gelen = {}
    monkeypatch.setattr(M, "masa", lambda v, key: gelen.update(v=v, key=key))
    ciz(SAT, KOL, "deneme_masa")
    assert gelen["key"] == "deneme_masa" and len(gelen["v"]["satirlar"]) == 2


# Sayfalar: eski tablo yerine masa (ekrandaki listeler; düzenlenebilir tablolar ve Excel önizlemeleri kalır)
GECENLER = {
    "kayranacc/cari_ekstre.py": ("cari_ekstre_masa", "cari_yas_masa_"),
    "depo/main.py": ("dpo_son_sevk_masa", "hl_ozet_masa_", "hl_detay_masa_"),
    "depo/bekleyen_ekran.py": ("mt_hareket_masa", "mt_kayit_hrk_"),
    "yonetim.py": ("audit_masa",),
    "satis/main.py": ("iade_sku_masa", "iade_firma_masa", "iade_sku_firma_masa"),
    "app.py": ("sk_basarisiz", "sk_hareket", "sk_hatalar"),
    "kayranacc/edefter.py": ("edf_plan_masa", "edf_kebir_masa_", "edf_mizan_masa"),
    "teknikservis/main.py": ("ts_kat_ozet_masa",),
    "kayranpm/genel_bakis.py": ("pm_kat_ozet_masa",),
    "shared/bt_ekran.py": ("bt_yavas_masa", "bt_ogren_masa"),
}


def test_sayfalar_masaya_gecti():
    for yol, anahtarlar in GECENLER.items():
        s = (KOK / yol).read_text(encoding="utf-8")
        for a in anahtarlar:
            assert f'"{a}' in s, (yol, a)
    # eski tablo çağrıları kalktı
    assert "st.dataframe(df, hide_index=True" not in (KOK / "kayranacc/cari_ekstre.py").read_text(encoding="utf-8")
    assert "st.dataframe(" not in (KOK / "kayranacc/cari_ekstre.py").read_text(encoding="utf-8")
    assert "st.dataframe(_gdf" not in (KOK / "depo/main.py").read_text(encoding="utf-8")
    assert not re.search(r"st\.dataframe\(_(ozet|detay)_df", (KOK / "depo/main.py").read_text(encoding="utf-8"))
    assert "st.dataframe(" not in (KOK / "depo/bekleyen_ekran.py").read_text(encoding="utf-8")
    y = (KOK / "yonetim.py").read_text(encoding="utf-8")
    assert 'key="audit_kul"' not in y            # kullanıcı süzgeci masanın çipinde
    a = (KOK / "app.py").read_text(encoding="utf-8")
    assert "st.dataframe(_tablo(rows)" not in a
    e = (KOK / "kayranacc/edefter.py").read_text(encoding="utf-8")
    assert "st.dataframe(_pdf" not in e and "st.dataframe(_kdf2" not in e and "st.dataframe(_mdf" not in e


def test_iade_kar_sutunu_yetkiye_bagli():
    s = (KOK / "satis/main.py").read_text(encoding="utf-8")
    assert '+ ([_mk("Satış kârı", "usd", genis=True)] if _kar_ok() else [])' in s
