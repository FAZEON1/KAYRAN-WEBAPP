# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Yurt içi alış › Kayıtlı alımlar liste masası (Ekim 2026, ortak masa shared/masa.py).

Satırlar eski tablonun satırlarıyla aynı hesap (mal = Σ adet × birim_fob, + masraflar; sıra depoya giriş,
yeni üstte). Düzenle bugünkü formu açar (seçim oturuma yazılır); Sil onaylı → ithalat.database.yurtici_sil.
"""
from kayranpm import yurtici_masasi as M
from shared.masa import istek_al, kosul_uyar
from shared.utils import gun_ay_yil

DOS = [
    {"id": 20, "dosya_no": "YI-1", "tarih": "2026-09-01", "teslim_tarihi": "2026-09-03", "tedarikci": "Örnek A.Ş.",
     "alim_turu": "yurtici", "stok_islendi": True, "masraflar": {"nakliye": 12.5}},
    {"id": 21, "dosya_no": "YI-2", "tarih": "2026-10-01", "teslim_tarihi": "2026-10-05", "tedarikci": "Deneme Ltd.",
     "alim_turu": "yerli", "stok_islendi": False, "masraflar": {}},
]
KAL = {20: [{"adet": 10, "birim_fob": 2.5}, {"adet": 4, "birim_fob": 10}], 21: [{"adet": 1.5, "birim_fob": 3}]}


def _masraf(d):
    return d.get("masraflar") or {}


def _tablo():
    return M.tablo_satirlari(DOS, KAL, _masraf, gun_ay_yil)


def test_tablo_satirlari_eski_tabloyla_ayni():
    t = _tablo()
    assert [r["Belge"] for r in t] == ["YI-2", "YI-1"]
    a = t[1]
    assert a["Tutar ($)"] == round(10 * 2.5 + 4 * 10 + 12.5, 2) == 77.5 and a["Adet"] == 14 and a["Kalem"] == 2
    assert a["Depoya giriş"] == "03.09.2026" and a["Stok"] == "eklendi" and a["Tür"] == "Yurt içi satın alma"
    assert t[0]["Stok"] == "zaten depodaydı"


def test_masa_satirlari_ve_suzgec():
    v = M.masa_verisi(_tablo())
    r = {s["id"]: s for s in v["satirlar"]}
    assert r[20]["tutar_m"] == "$77,50" and r[20]["adet_m"] == "14" and r[21]["adet_m"] == "1,50"
    assert r[20]["_durum"] == {"ad": "Stoğa eklendi", "renk": "yesil"} and r[21]["stok"] == "depoda"
    assert r[20]["giris__s"] == "2026-09-03" and r[20]["alis"] == "alış 01.09.2026"
    assert [s["id"] for s in v["satirlar"] if kosul_uyar(s, v["anahtarlar"][0]["f"])] == [20]
    assert [o["k"] for o in v["secimler"][0]["secenekler"]] == ["Deneme Ltd.", "Örnek A.Ş."]


def test_istek_ve_yurut(monkeypatch):
    v = M.masa_verisi(_tablo())
    assert "gerekli" in istek_al(v, {"islem": "sil", "ids": [20], "degerler": {}})[1]
    assert "tek" in istek_al(v, {"islem": "duzenle", "ids": [20, 21]})[1]
    ss = {}
    s = M.yurutucu(state=ss)(istek_al(v, {"islem": "duzenle", "ids": [21]})[0])
    assert ss == {M.SECIM_KEY: 21} and s == {"ok": True, "sessiz": True, "onbellek": False}
    import ithalat.database as I
    c = []
    monkeypatch.setattr(I, "yurtici_sil", lambda i: (c.append(i), (True, "Alım silindi"))[1])
    s = M.yurutucu(state=ss)(istek_al(v, {"islem": "sil", "ids": [20], "degerler": {"onay": True}})[0])
    assert c == [20] and s == {"ok": True, "mesaj": "Alım silindi"}
