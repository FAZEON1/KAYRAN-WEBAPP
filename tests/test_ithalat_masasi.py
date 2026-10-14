# -*- coding: utf-8 -*-
"""İthalat liste masaları (Ekim 2026): Geçmiş ithalatlar ve Masraf detayları ortak masada (shared/masa.py).

Burada: ekrana giden verinin rakamları eski ekranla aynı (dosya_hesapla / masraf_dokumu, eski kpi_serit
formülleri), tarayıcıdan gelen isteğin genel doğrulanması (shared.masa.istek_al) ve her işlemin BUGÜNKÜ
veritabanı fonksiyonunu eski ekrandaki argümanlarla çağırması."""
import sys
from datetime import date
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from ithalat import ithalat_masasi as M  # noqa: E402
from ithalat import database as D  # noqa: E402
from shared import masa as MS  # noqa: E402
from shared.tasarim import tr_sayi  # noqa: E402

BUGUN = date(2026, 10, 14)
DEPOLAR = [{"k": d, "ad": d} for d in ("MERKEZ DEPO", "HAPPY LIFE", "TEKNİK DEPO", "ASEL DEPO")]


def _d(i, tarih, durum, masraf=None, depo="", doviz="USD", **k):
    return dict(id=i, pi_no=f"PI-{i}", dosya_no=f"ITH-{i}", tarih=tarih, tedarikci=f"Tedarikçi {i % 2}",
                durum=durum, teslim_deposu=depo, doviz=doviz, ithalat_takip_no=f"TK{i}" if i != 3 else "",
                masraflar=masraf or {}, alim_turu="ithalat", tahmini_varis="2026-10-20", **k)


DOSYALAR = [
    _d(1, "2026-08-02", "Teslim Alındı", {"navlun": 1200.5, "gumruk_musavirligi": 300}, depo="MERKEZ DEPO",
       teslim_tarihi="2026-09-10"),
    _d(2, "2026-09-15", "Yolda", {"navlun": 800}),
    _d(3, "2026-09-01", "Teslim Alındı", depo=""),                       # masrafsız, deposuz
    _d(4, "2026-10-05", "Gümrükte", {"navlun": 250.25}, doviz="EUR", fatura_indirim=100),
]
KALEMLER = {1: [{"sku": "FZ-SSD-1TB", "adet": 100, "birim_fob": 36.9}, {"sku": "AGI-RAM-16", "adet": 50, "birim_fob": 16.38}],
            2: [{"sku": "IN3-4060", "adet": 20, "birim_fob": 235.8}],
            3: [{"sku": "XS-KASA-M1", "adet": 300, "birim_fob": 27.9}],
            4: [{"sku": "FZ-MON-27Q", "adet": 40, "birim_fob": 127.8}]}


def _hesap():
    return {d["id"]: (d, KALEMLER[d["id"]], D.dosya_hesapla(d, KALEMLER[d["id"]])) for d in DOSYALAR}


def _veri(**k):
    return M.masa_verisi(DOSYALAR, _hesap(), BUGUN, depolar=DEPOLAR, **k)


# ── Ekrana giden veri ────────────────────────────────────────────────
def test_satir_sirasi_gruplari_ve_tutarlar():
    v = _veri()
    r = {s["id"]: s for s in v["satirlar"]}
    assert [s["id"] for s in v["satirlar"]] == [4, 2, 3, 1]              # sipariş tarihi yeniden eskiye
    assert [s["ay"] for s in v["satirlar"]] == ["Ekim 2026", "Eylül 2026", "Eylül 2026", "Ağustos 2026"]
    h = _hesap()
    for i, s in r.items():
        assert s["mal"] == h[i][2]["net_mal_bedeli"] and s["masraf"] == h[i][2]["toplam_masraf"]
        assert s["yuzde"] == h[i][2]["maliyet_yuzde"]
    assert r[1]["mal_m"] == "$4.509,00" and r[1]["masraf_m"] == "$1.500,50"
    assert r[1]["yuzde_m"] == f"%{tr_sayi(1500.5 / 4509 * 100, 2)}"
    assert r[4]["mal_m"] == "€5.012,00" and r[4]["doviz"] == "EUR"       # net (fatura altı indirim düşülmüş)
    assert r[3]["masraf_m"] == "" and r[3]["yuzde_m"] == "masraf yok" and r[3]["masraf_var"] is False
    assert r[3]["depo_eksik"] is True and r[3]["depo_m"] == "SEÇİLMEDİ" and "deposu seçilmedi" in r[3]["_not"]
    assert r[1]["depo_eksik"] is False and r[2]["depo_m"] == ""
    assert r[2]["var"] == "20.10.2026" and r[2]["var_alt"] == "varış 6 gün sonra" and r[2]["var_renk"] == "cyan"
    assert r[1]["var"] == "10.09.2026" and r[1]["var_alt"] == "teslim"
    assert r[1]["_durum"] == {"ad": "Teslim Alındı", "renk": "yesil"} and r[4]["_durum"]["renk"] == "amber"
    assert r[1]["skus"] == "FZ-SSD-1TB AGI-RAM-16" and r[3]["takip"] == ""
    assert r[1]["tarih"] == "02.08.2026" and r[1]["tarih__s"] == "2026-08-02"


def test_ozet_bandi_eski_kpi_formulleriyle_ayni():
    from shared.tasarim import kart_degeri_kisa
    v = _veri()
    h = _hesap()
    toplam_mal = sum(x[2]["net_mal_bedeli"] for x in h.values())
    toplam_masraf = sum(x[2]["toplam_masraf"] for x in h.values())
    yolda_fob = h[2][2]["net_mal_bedeli"] + h[4][2]["net_mal_bedeli"]
    o = {k["k"]: k for k in v["ozet"]}
    assert o["yolda"]["dg"] == "2" and o["yolda"]["suz"] == "yolda"
    assert o["yolda"]["al"] == f"{kart_degeri_kisa('$' + tr_sayi(yolda_fob, 2))[0]} mal bedeli"
    assert o["mal"]["dg"] == "$22.607" and o["mal"]["ipucu"] == f"${tr_sayi(toplam_mal, 2)}"   # kartta kuruş yok
    assert o["masraf"]["dg"] == kart_degeri_kisa(f"${tr_sayi(toplam_masraf, 2)}")[0] == "$2.551"
    assert o["masraf"]["al"] == "1 dosyada masraf bekliyor" and o["masraf"]["suz"] == "masrafsiz"
    assert o["oran"]["dg"] == f"%{tr_sayi(toplam_masraf / toplam_mal * 100, 2)}"


def test_gorunumler_secimler_ve_islemler():
    v = _veri()
    gor = {g["k"]: g for g in v["gorunumler"]}
    uyan = lambda k: [s["id"] for s in v["satirlar"] if MS.kosul_uyar(s, gor[k]["f"])]  # noqa: E731
    assert uyan("yolda") == [4, 2] and uyan("teslim") == [3, 1] and uyan("masrafsiz") == [3]
    assert uyan("deposuz") == [3] and len(uyan("tum")) == 4
    sec = {s["alan"]: s for s in v["secimler"]}
    assert [o["k"] for o in sec["asama"]["secenekler"]] == ["Yolda", "Gümrükte", "Teslim Alındı"]
    assert [o["k"] for o in sec["ted"]["secenekler"]] == ["Tedarikçi 0", "Tedarikçi 1"]
    assert v["ara"]["alanlar"] == ["belge", "takip", "sas", "ted", "skus"]
    assert {i["k"] for i in v["islemler"]} == {"ac", "teslim", "depo", "takip"}
    assert v["grup"]["alan"] == "ay" and v["salt"] is False


def test_depo_secenekleri_main_ile_ayni():
    from ithalat.main import DEPO_SECENEKLER
    v = M.masa_verisi(DOSYALAR, _hesap(), BUGUN)
    teslim = next(i for i in v["islemler"] if i["k"] == "teslim")
    assert [o["k"] for o in teslim["alanlar"][0]["secenekler"]] == DEPO_SECENEKLER[1:]


def test_bos_liste_cokmez():
    v = M.masa_verisi([], {}, BUGUN, depolar=DEPOLAR)
    assert v["satirlar"] == [] and {k["k"] for k in v["ozet"]} == {"yolda", "mal", "masraf", "oran"}


# ── İsteğin genel doğrulanması (shared.masa.istek_al) ────────────────
def test_istek_gecerli():
    v = _veri()
    t, h = MS.istek_al(v, {"islem": "teslim", "ids": [2, 4], "degerler": {"depo": "MERKEZ DEPO"}})
    assert h is None and t["ids"] == [2, 4] and t["degerler"] == {"depo": "MERKEZ DEPO"}
    t, h = MS.istek_al(v, {"islem": "takip", "ids": [1, 3], "degerler": {"takip": " 2026-14 "}})
    assert h is None and t["degerler"] == {"takip": "2026-14"}
    t, h = MS.istek_al(v, {"islem": "depo", "ids": [3], "degerler": {"depo": "ASEL DEPO"}})
    assert h is None
    t, h = MS.istek_al(dict(v, salt=True), {"islem": "ac", "ids": [1]})
    assert h is None and t["islem"] == "ac"                               # salt-okurda ayrıntı açılır


@pytest.mark.parametrize("istek, hata", [
    ({"islem": "teslim", "ids": [1], "degerler": {"depo": "MERKEZ DEPO"}}, "uygun değil"),      # zaten teslim
    ({"islem": "teslim", "ids": [2], "degerler": {"depo": "BAŞKA DEPO"}}, "listeden"),          # depo listede yok
    ({"islem": "teslim", "ids": [2], "degerler": {}}, "gerekli"),                               # depo zorunlu
    ({"islem": "depo", "ids": [1], "degerler": {"depo": "MERKEZ DEPO"}}, "uygun değil"),        # deposu var
    ({"islem": "takip", "ids": [1], "degerler": {"takip": ""}}, "gerekli"),
    ({"islem": "ac", "ids": [1, 2]}, "tek kayıtla"),
    ({"islem": "takip", "ids": [99], "degerler": {"takip": "X"}}, "bulunamadı"),
    ({"islem": "sil", "ids": [1]}, "Bilinmeyen"),
])
def test_istek_reddedilir(istek, hata):
    t, h = MS.istek_al(_veri(), istek)
    assert t is None and hata in h


def test_salt_okurda_yazma_reddedilir():
    t, h = MS.istek_al(_veri(salt=True), {"islem": "takip", "ids": [1], "degerler": {"takip": "X"}})
    assert t is None and "Salt-okur" in h


# ── Yürütme: doğru fonksiyon, eski argümanlar ───────────────────────
@pytest.fixture
def cagrilar(monkeypatch):
    c = []
    monkeypatch.setattr(D, "set_dosya_durum", lambda i, durum: c.append(("durum", i, durum)) or True)
    monkeypatch.setattr(D, "set_dosya_teslim", lambda i, **k: c.append(("teslim", i, k)) or True)
    monkeypatch.setattr(D, "set_dosya_takip_no", lambda i, t: c.append(("takip", i, t)) or True)
    return c


def _yurut(istek):
    v = _veri()
    t, h = MS.istek_al(v, istek)
    assert h is None, h
    return M.yurutucu(DOSYALAR)(t)


def test_teslim_alindi_eski_toplu_islemle_ayni_sira(cagrilar):
    s = _yurut({"islem": "teslim", "ids": [2, 4], "degerler": {"depo": "HAPPY LIFE"}})
    assert cagrilar == [("durum", 2, "Teslim Alındı"), ("teslim", 2, {"teslim_deposu": "HAPPY LIFE"}),
                        ("durum", 4, "Teslim Alındı"), ("teslim", 4, {"teslim_deposu": "HAPPY LIFE"})]
    assert s["ok"] and s["mesaj"] == "2 belge 'Teslim Alındı' olarak işaretlendi. Teslim deposu: HAPPY LIFE."


def test_teslim_durum_yazilamazsa_depo_yazilmaz(monkeypatch, cagrilar):
    monkeypatch.setattr(D, "set_dosya_durum", lambda i, durum: False)
    s = _yurut({"islem": "teslim", "ids": [2], "degerler": {"depo": "MERKEZ DEPO"}})
    assert cagrilar == [] and s["ok"] is False


def test_depo_ata_ve_takip_no(cagrilar):
    s = _yurut({"islem": "depo", "ids": [3], "degerler": {"depo": "TEKNİK DEPO"}})
    assert cagrilar == [("teslim", 3, {"teslim_deposu": "TEKNİK DEPO"})] and "1 dosyaya" in s["mesaj"]
    cagrilar.clear()
    s = _yurut({"islem": "takip", "ids": [1, 2, 3], "degerler": {"takip": "2026-14"}})
    assert cagrilar == [("takip", 1, "2026-14"), ("takip", 2, "2026-14"), ("takip", 3, "2026-14")]
    assert s["mesaj"] == "3 belgeye '2026-14' takip no'su atandı."


def test_ayrinti_eski_pencereyi_ister(cagrilar):
    import streamlit as st
    s = _yurut({"islem": "ac", "ids": [4]})
    assert s == {"ok": True, "mesaj": "", "yenileme": False, "sessiz": True} and cagrilar == []
    assert st.session_state.get("_ith_sec") == 4 and st.session_state.get("_ith_ac") is True
    st.session_state.pop("_ith_sec", None)
    st.session_state.pop("_ith_ac", None)


# ── Masraf detayları ─────────────────────────────────────────────────
def _masraf_satirlari():
    """ithalat/main._masraf_detaylari'nin bugünkü satır kurulumu (masraf_dokumu, % = tutar / brüt FOB)."""
    out = []
    for d in DOSYALAR:
        mb = sum(float(k["adet"]) * float(k["birim_fob"]) for k in KALEMLER[d["id"]])
        for label, tutar in D.masraf_dokumu(d):
            out.append({"Belge No": d["pi_no"], "Takip No": d["ithalat_takip_no"] or "—", "Tarih": d["tarih"],
                        "Tedarikçi": d["tedarikci"], "Masraf Türü": label, "Tutar": float(tutar),
                        "Döviz": d["doviz"], "% (belge)": float(tutar) / mb * 100})
    return out


def test_masraf_masasi():
    sat = _masraf_satirlari()
    v = M.masraf_masa_verisi(sat)
    r = v["satirlar"]
    assert len(r) == 4
    assert [(x["belge"], x["tur"]) for x in r] == sorted((s["Belge No"], s["Masraf Türü"]) for s in sat)
    navlun = next(x for x in r if x["belge"] == "PI-1" and x["tutar"] == 1200.5)
    assert navlun["tutar_m"] == "1.200,50 USD" and navlun["yuzde_m"] == f"%{tr_sayi(1200.5 / 4509 * 100, 2)}"
    assert navlun["grup"] == "PI-1 · USD" and navlun["tarih"] == "02.08.2026"
    o = {k["k"]: k for k in v["ozet"]}
    assert o["toplam"]["dg"] == "2.550,75 karışık" and o["toplam"]["al"] == "farklı para birimleri toplandı"
    assert o["kalem"]["dg"] == "4" and o["kalem"]["al"] == f"{len({s['Masraf Türü'] for s in sat})} farklı tür"
    assert o["belge"]["dg"] == "3"
    assert v["islemler"] == [] and [s["alan"] for s in v["secimler"]] == ["tur", "takip"]
    t, h = MS.istek_al(v, {"islem": "ac", "ids": [1]})
    assert t is None and "Bilinmeyen" in h                                # salt-okur masa


def test_masraf_masasi_tek_doviz_dolar():
    sat = [s for s in _masraf_satirlari() if s["Döviz"] == "USD"]
    o = {k["k"]: k for k in M.masraf_masa_verisi(sat)["ozet"]}
    toplam = sum(s["Tutar"] for s in sat)
    assert o["toplam"]["ipucu"] == f"${tr_sayi(toplam, 2)}" and o["toplam"]["dg"] == "$2.301"
