# -*- coding: utf-8 -*-
"""Haftalık yaşlı stok maili ve stok yaşı istisna kategorileri (Ekim 2026).

Kullanıcı listesi: tüm kategoriler İbrahim, Serkan, Korkut; ekran kartı, monitör, mouse pad ayrıca
Derya; diğerleri ayrıca Gökhan. Yedek parça satış için değil: stok yaşı listelerinde, Excel'de ve
mailde görünmez. Mail yalnız pazartesi, kişi başına tek mail + Excel eki, yaşlı stoğu olmayana yok.
"""
from datetime import date, datetime

import kayranpm.stok_yasi as Y

BUGUN = date(2026, 10, 5)                 # pazartesi


def test_varsayilan_alicilar_kullanici_listesiyle_ayni():
    a = Y.ayar_birlestir({})
    for kat in ("ekran kartı", "MONİTÖR", "Mouse Pad"):
        assert sorted(Y.kategori_sorumlulari(kat, a)) == ["derya", "ibrahim", "korkut", "serkan"], kat
    for kat in ("kasa", "CPU Soğutucu", "ssd", "araç kamerası", "", "yeni bir kategori"):
        assert sorted(Y.kategori_sorumlulari(kat, a)) == ["gokhan", "ibrahim", "korkut", "serkan"], kat
    assert Y.haric_mi("YEDEK PARÇA", a) and Y.haric_mi("yedek parça", a) and not Y.haric_mi("kasa", a)
    assert a["esik_gun"] == 90


def test_kayitli_ayar_birlesir_bozuk_alan_yok_sayilir():
    a = Y.ayar_birlestir({"esik_gun": "abc", "haric_kategoriler": ["kasa"], "sorumlular": {"kasa": ["Kemal"]}})
    assert a["esik_gun"] == 90 and a["haric_kategoriler"] == ["kasa"]
    assert Y.kategori_sorumlulari("Kasa", a) == ["kemal"]
    assert Y.ayar_birlestir("bozuk")["haric_kategoriler"] == ["yedek parça"]


def _bizim():
    o1, k1 = Y.urun_yasi(100, [{"tarih": "2026-01-10", "adet": 60, "belge": "D1", "tur": "ithalat"},
                               {"tarih": "2026-09-20", "adet": 40, "belge": "D2", "tur": "ithalat"}], BUGUN)
    o2, k2 = Y.urun_yasi(30, [{"tarih": "2026-05-01", "adet": 30, "belge": "D3", "tur": "ithalat"}], BUGUN)
    o3, k3 = Y.urun_yasi(5, [{"tarih": "2026-09-30", "adet": 5, "belge": "D4", "tur": "ithalat"}], BUGUN)
    return {"MON1": (o1, k1, {"sku": "MON1", "urun_adi": "Monitör 1", "kategori": "Monitör"}),
            "KAS1": (o2, k2, {"sku": "KAS1", "urun_adi": "Kasa 1", "kategori": "kasa"}),
            "YENI": (o3, k3, {"sku": "YENI", "urun_adi": "Yeni", "kategori": "kasa"})}


def test_yasli_satirlar_ve_kisi_dagitimi():
    r = Y.yasli_satirlar(_bizim(), {"MON1": 100.0, "KAS1": 50.0}, BUGUN, 90)
    assert [(x["SKU"], x["90+ gün adet"], x["180+ gün adet"], x["Yaşlı değer ($)"]) for x in r] == \
        [("MON1", 60, 60, 6000.0), ("KAS1", 30, 0, 1500.0)]           # KAS1 157 gün; YENI 5 gün: yok
    k = Y.kisi_listeleri(r, Y.ayar_birlestir({}))
    assert [x["SKU"] for x in k["derya"]] == ["MON1"] and [x["SKU"] for x in k["gokhan"]] == ["KAS1"]
    assert [x["SKU"] for x in k["ibrahim"]] == ["MON1", "KAS1"] and "kemal" not in k


def test_mail_govdesi_ve_excel_eki():
    import email
    from shared.eposta import mesaj_olustur
    r = Y.yasli_satirlar(_bizim(), {"MON1": 100.0, "KAS1": 50.0}, BUGUN, 90)
    h = Y.mail_html(r, 90, BUGUN)
    assert "Yaşlı stok · 05.10.2026" in h and "2 ürün · 90 adet" in h and "#fef2f2" in h
    xb = Y.excel_bytes({"Yaşlı stok": r})
    m = email.message_from_string(mesaj_olustur("a@b.com", ["c@d.com"], "k", h,
                                                ekler=[("yasli.xlsx", xb, "application/vnd.ms-excel")]).as_string())
    assert m.get_content_type() == "multipart/mixed"
    ekler = [p for p in m.walk() if p.get_filename()]
    assert [p.get_filename() for p in ekler] == ["yasli.xlsx"] and ekler[0].get_payload(decode=True) == xb
    assert any(p.get_content_type() == "text/plain" for p in m.walk())


def test_hesapla_yedek_parcayi_listelemez(monkeypatch):
    import kayranpm.database as D
    monkeypatch.setattr(D, "_hepsi", lambda *a, **k: [
        {"sku": "YP1", "urun_adi": "Yedek", "kategori": "Yedek Parça", "bizim_stok": 50},
        {"sku": "MON1", "urun_adi": "Monitör", "kategori": "monitör", "bizim_stok": 10}])
    monkeypatch.setattr(Y, "_bizim_partiler_oku", lambda: {"YP1": [{"tarih": "2025-01-01", "adet": 50}],
                                                           "MON1": [{"tarih": "2026-09-01", "adet": 10}]})
    monkeypatch.setattr(Y, "_musteri_oku", lambda: ({"VATAN": {"YP1": 7, "MON1": 3}}, {}))
    monkeypatch.setattr(Y, "ayar_oku", lambda: Y.ayar_birlestir({}))
    if hasattr(Y.hesapla, "clear"):
        Y.hesapla.clear()
    v = getattr(Y.hesapla, "__wrapped__", Y.hesapla)()
    assert set(v["bizim"]) == {"MON1"} and set(v["musteri"]["VATAN"]) == {"MON1"}


def _betik(monkeypatch, gun, gonderilen, son=None):
    import shared.utils as U
    import shared.eposta as E
    import kayranacc.database as K
    import satis.database as S
    import otonom.yasli_stok_mail as M
    monkeypatch.setattr(U, "tr_now", lambda: datetime(gun.year, gun.month, gun.day, 8, 0))
    monkeypatch.setattr(Y, "hesapla", lambda: {"bizim": _bizim(), "musteri": {}, "bugun": gun,
                                                "ayar": Y.ayar_birlestir({})})
    monkeypatch.setattr(S, "get_pacal_map", lambda: {"MON1": 100.0, "KAS1": 50.0})
    monkeypatch.setattr(E, "adresler", lambda: {k: f"{k}@g5f.com" for k in
                                                ("ibrahim", "serkan", "korkut", "derya", "gokhan")})
    monkeypatch.setattr(E, "ayarlar", lambda: {"host": "h", "port": 587, "user": "u", "pass": "p"})
    monkeypatch.setattr(E, "gonder", lambda alici, konu, html, cc=None, ekler=None:
                        (gonderilen.append((alici[0], konu, [e[0] for e in ekler or []])), (True, "ok"))[1])
    kayit = {"son": dict(son or {})}
    monkeypatch.setattr(K, "get_ayar", lambda anahtar, v=None: kayit["son"])
    monkeypatch.setattr(K, "set_ayar", lambda anahtar, deger: kayit.update(son=dict(deger)) or True)
    monkeypatch.delenv("YASLI_STOK_ZORLA", raising=False)
    M.main()
    return kayit["son"]


def test_betik_pazartesi_herkese_kendi_listesi(monkeypatch):
    g = []
    son = _betik(monkeypatch, BUGUN, g)
    assert sorted(x[0] for x in g) == ["derya@g5f.com", "gokhan@g5f.com", "ibrahim@g5f.com",
                                       "korkut@g5f.com", "serkan@g5f.com"]
    derya = next(x for x in g if x[0].startswith("derya"))
    assert "(1 ürün)" in derya[1] and derya[2] == ["yasli_stok_2026-10-05.xlsx"]
    assert son["ibrahim"] == "2026-10-05"
    g2 = []
    _betik(monkeypatch, BUGUN, g2, son=son)                     # aynı gün ikinci çalıştırma
    assert g2 == []


def test_betik_pazartesi_degilse_gondermez(monkeypatch):
    g = []
    _betik(monkeypatch, date(2026, 10, 6), g)
    assert g == []


def test_is_akisinda_adim_ve_excel_paketi():
    from pathlib import Path
    w = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "telegram-brifing.yml").read_text(
        encoding="utf-8")
    assert "python otonom/yasli_stok_mail.py" in w and "openpyxl" in w and "yasli_stok_zorla" in w
