# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Sipariş Önerisi liste masaları (Ekim 2026, ortak masa shared/masa.py).

Öneriler: miktar öneriyle gelir (en az 1, eski number_input gibi), "Siparişe ekle" eski düğmeyle AYNI
çağrı: ekle_siparis_onerisi("G5F", sku, ürün adı, miktar). Kayıtlar: Onayla / Reddet yalnız bekleyende,
tek ya da toplu; her kayıt için onayla_siparis / reddet_siparis (eski satır düğmeleri).
"""
import pytest

from kayranpm import siparis_masasi as M
from kayranpm.urun_hesap import bekleyen_haritasi
from shared.masa import istek_al, kosul_uyar

LISTE = [
    {"sku": "A", "urun_adi": "Ürün A", "siparis_durum": "acil", "siparis_mesaj": "ACİL — 20g'de biter",
     "bizim_stok": 12, "ortalama_haftalik_satis": 4.25, "oneri_miktar": 150, "oneri_mesaj": "135 gün + emniyet",
     "firma_detay": [{"firma": "VATAN", "stok": 7}, {"firma": "HB", "stok": 0}]},
    {"sku": "B", "urun_adi": "Ürün B", "siparis_durum": "planlama", "siparis_mesaj": "60 gün içinde",
     "bizim_stok": 300, "ortalama_haftalik_satis": 1, "oneri_miktar": 0},
]
URUN = {"A": {"final_cost_price": 10.5, "satis_fiyati": 15}}
KAYIT = [
    {"id": 11, "sku": "A", "urun_adi": "Ürün A", "oneri_miktari": 50, "durum": "bekliyor",
     "olusturma_tarihi": "2026-10-12T09:30:00"},
    {"id": 12, "sku": "C", "urun_adi": "Ürün C", "oneri_miktari": 20, "durum": "bekliyor", "olusturma_tarihi": "2026-10-11"},
    {"id": 13, "sku": "D", "urun_adi": "Ürün D", "oneri_miktari": 5, "durum": "onaylandi",
     "olusturma_tarihi": "2026-10-01", "onay_tarihi": "2026-10-02T10:00:00"},
]


def _oneri():
    return M.oneri_verisi(LISTE, URUN, bekleyen_haritasi(KAYIT), firma_ad=lambda f: {"VATAN": "VATAN BİL."}.get(f, f))


def test_oneri_satirlari_eski_satirla_ayni():
    v = _oneri()
    d = {k["k"]: k["dg"] for k in v["ozet"]}
    assert d == {"acil": "1", "yaklasıyor": "0", "planlama": "1"}
    a, b = v["satirlar"]
    from shared.tasarim import tr_sayi
    assert a["mesaj"] == "20g'de biter" and a["hafta"] == f"haftalık {tr_sayi(4.25, 1)}"
    assert a["kanal"] == "VATAN BİL. 7" and a["fiyat"] == "paçal $10,50 → satış $15,00"
    assert a["oneri_m"] == "150 adet" and a["oneri_v"] == 150 and a["bek_m"] == "bekliyor · 50 adet"
    assert a["_durum"] == {"ad": "Acil", "renk": "kirmizi"} and a["_not"] == "135 gün + emniyet"
    assert b["oneri_v"] == 1 and b["bek_m"] == "" and b["fiyat"] == ""        # eski kutu en az 1 ile açılırdı
    assert [s["id"] for s in v["satirlar"] if kosul_uyar(s, v["gorunumler"][1]["f"])] == ["A"]


def test_kayit_gorunumleri_ve_metinler():
    v = M.kayit_verisi(KAYIT)
    assert [g["k"] for g in v["gorunumler"]] == ["bekleyen", "sonuclanan", "tumu"]
    r = {s["id"]: s for s in v["satirlar"]}
    assert r[11]["olusturma"] == "12.10.2026 09:30" and r[13]["sonuc"] == "02.10.2026 10:00"
    assert r[13]["_durum"] == {"ad": "Onaylandı", "renk": "yesil"} and r[11]["miktar_m"] == "50 adet"
    v2 = M.kayit_verisi([KAYIT[2]])                       # bekleyen yoksa önce sonuçlananlar
    assert v2["gorunumler"][0]["k"] == "sonuclanan"


def test_istek_dogrulama():
    v = _oneri()
    t, h = istek_al(v, {"islem": "ekle", "ids": ["A"], "degerler": {"miktar": "120"}})
    assert h is None and t["degerler"] == {"miktar": 120.0}
    for istek, parca in [({"islem": "ekle", "ids": ["A"], "degerler": {}}, "gerekli"),
                         ({"islem": "ekle", "ids": ["A"], "degerler": {"miktar": "abc"}}, "sayı"),
                         ({"islem": "ekle", "ids": ["A"], "degerler": {"miktar": 0}}, "sayı"),
                         ({"islem": "ekle", "ids": ["A", "B"], "degerler": {"miktar": 5}}, "tek"),
                         ({"islem": "ekle", "ids": ["Z"], "degerler": {"miktar": 5}}, "bulunamadı")]:
        assert parca in istek_al(v, istek)[1]
    k = M.kayit_verisi(KAYIT)
    t, h = istek_al(k, {"islem": "onayla", "ids": [11, 12]})
    assert h is None and t["ids"] == [11, 12]
    assert "uygun değil" in istek_al(k, {"islem": "reddet", "ids": [11, 13]})[1]    # sonuçlanan yeniden işlenmez


@pytest.fixture
def kayit(monkeypatch):
    import kayranpm.database as D
    k = []
    monkeypatch.setattr(D, "ekle_siparis_onerisi", lambda *a, **kw: k.append(("ekle", a, kw)))
    monkeypatch.setattr(D, "onayla_siparis", lambda *a, **kw: k.append(("onay", a, kw)))
    monkeypatch.setattr(D, "reddet_siparis", lambda *a, **kw: k.append(("red", a, kw)))
    return k


def test_siparise_ekle_eski_cagri(kayit):
    v = _oneri()
    s = M.oneri_yurutucu()(istek_al(v, {"islem": "ekle", "ids": ["A"], "degerler": {"miktar": "120"}})[0])
    assert kayit == [("ekle", ("G5F", "A", "Ürün A", 120), {})] and s["ok"] and "120 adet" in s["mesaj"]
    s = M.oneri_yurutucu()(istek_al(v, {"islem": "ekle", "ids": ["A"], "degerler": {"miktar": "2.5"}})[0])
    assert not s["ok"] and len(kayit) == 1                                   # kesirli adet yazılmaz


def test_onayla_reddet_her_kayit_icin(kayit):
    k = M.kayit_verisi(KAYIT)
    s = M.kayit_yurutucu()(istek_al(k, {"islem": "onayla", "ids": [11, 12]})[0])
    assert kayit == [("onay", (11,), {}), ("onay", (12,), {})] and s == {"ok": True, "mesaj": "2 öneri onaylandı"}
    kayit.clear()
    s = M.kayit_yurutucu()(istek_al(k, {"islem": "reddet", "ids": [12]})[0])
    assert kayit == [("red", (12,), {})] and s["mesaj"] == "Ürün C reddedildi"
