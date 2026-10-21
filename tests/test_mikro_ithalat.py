# -*- coding: utf-8 -*-
"""Geçmiş İthalatlar Mikro'dan (ithalat/mikro_ithalat.py, Ekim 2026).

Canlı veri (21.10.2026): MASTER-008 Mikro'da tek dosya, uygulamada üç PI (PIFAZ251125-2: 1.500 adet, -4-1: 99, -5:
404 → 2.003 = Mikro). Masraf: navlun 6.200 $ uygulamayla kuruşuna tutuyor, ardiye Mikro'da 4.596 $ / uygulamada
2.227 $, diğer 2.686 $ / 1.171 $ (Mikro'ya sonradan işlenmiş ardiye / nakliye faturası)."""
import pytest

M = pytest.importorskip("ithalat.mikro_ithalat")


def _mdosya(kod="MASTER-008", cari="320.50.005", olusturma="2026-05-15"):
    return {"ith_kodu": kod, "ith_ismi": kod.split("-")[0], "ith_satici": cari, "ith_create_date": olusturma}


def _satir(kod, sku, adet, tutar, tarih="2026-05-15", depo=1, g=None):
    return {"sth_guid": g or f"{kod}-{sku}-{adet}", "sth_exim_kodu": kod, "sth_stok_kod": sku, "sth_miktar": adet,
            "sth_tutar": tutar, "sth_iskonto": 0, "sth_tarih": tarih + " 00:00:00", "sth_giris_depo_no": depo,
            "sth_normal_iade": 0}


def _masraf(kod, ad, tutar, sira):
    return {"cha_guid": f"{kod}-{sira}", "cha_evrak_tip": 95, "cha_cinsi": 5, "cha_eximkodu": kod, "dosya_veya_cari": kod,
            "cha_meblag": tutar, "cha_d_cins": 1, "cha_d_kur": 45.0, "cha_aciklama": ad, "cha_satir_no": sira}


def _fatura(kod, fob):
    return {"cha_guid": f"{kod}-f", "cha_evrak_tip": 0, "cha_cinsi": 29, "cha_eximkodu": kod, "cha_meblag": fob,
            "cha_d_cins": 1, "cha_d_kur": 45.2714, "cha_tarihi": "2026-05-31 00:00:00", "cha_belge_no": "26343100IM00110580"}


UNVAN = {"320.50.005": "SHENZHEN MASTER TECHNOLOGY CO., LTD"}
MASRAF_08 = [("Navlun", 6200), ("Sigorta", 276.44), ("Gümrük vergi ve resimler", 45.86), ("Gümrük Müşavirlik", 858.74),
             ("Ardiye", 4595.72), ("Diğer Çeşitli Giderler", 2686.18)]


def _mikro():
    satir = [_satir("MASTER-008", "X24F182S", 1500, 95040), _satir("MASTER-008", "X27F240S", 404, 115600),
             _satir("MASTER-008", "X27F241S", 99, 9801)]
    cari = [_fatura("MASTER-008", 220441)] + [_masraf("MASTER-008", a, t, i) for i, (a, t) in enumerate(MASRAF_08)]
    return M.mikro_dosyalari([_mdosya()], satir, cari, UNVAN, {1: "Merkez"})


def _app():
    ted = "SHENZHEN MASTER TECHNOLOGY CO., LTD"
    d = [{"id": 1, "dosya_no": "PIFAZ251125-2", "tarih": "2026-05-15", "tedarikci": ted, "durum": "Antrepoda",
          "masraflar": {"navlun": 2673.04, "liman_ardiye": 960.1, "mal_sigortasi": 127.47, "gumruk_musavirligi": 371.19,
                        "liman_depo_nakliye": 161.9, "tahliye_depolama_tasima": 342.84, "igv": 4.44, "damga_vergisi": 15.29}},
         {"id": 2, "dosya_no": "PIFAZ251125-5", "tarih": "2026-05-15", "tedarikci": ted, "durum": "Teslim Alındı",
          "teslim_tarihi": "2026-05-15", "stok_islendi": True,
          "masraflar": {"navlun": 3251.3, "liman_ardiye": 1167.8, "mal_sigortasi": 155.04, "gumruk_musavirligi": 451.49,
                        "liman_depo_nakliye": 196.92, "tahliye_depolama_tasima": 417.01, "igv": 5.4, "damga_vergisi": 18.6}},
         {"id": 3, "dosya_no": "PIFAZ251125-4-1", "tarih": "2026-05-15", "tedarikci": ted, "durum": "Teslim Alındı",
          "teslim_tarihi": "2026-05-15", "stok_islendi": True,
          "masraflar": {"navlun": 275.66, "liman_ardiye": 99.01, "mal_sigortasi": 13.14, "gumruk_musavirligi": 38.27,
                        "liman_depo_nakliye": 16.69, "tahliye_depolama_tasima": 35.35, "igv": 0.46, "damga_vergisi": 1.58}},
         {"id": 4, "dosya_no": "BASKA", "tarih": "2026-03-01", "tedarikci": ted, "durum": "Teslim Alındı",
          "masraflar": {"navlun": 100}}]
    k = {1: [{"sku": "X24F182S", "adet": 1500, "birim_fob": 63.36}],
         2: [{"sku": "X27F240S", "adet": 400, "birim_fob": 289}, {"sku": "X27F240S", "adet": 4, "birim_fob": 0}],
         3: [{"sku": "X27F241S", "adet": 99, "birim_fob": 99}],
         4: [{"sku": "X24F182S", "adet": 700, "birim_fob": 60}]}
    return d, k


def _plan():
    d, k = _app()
    return M.plan_yap(_mikro(), d, k, lambda x: dict(x["masraflar"]),
                      lambda x, kk: sum(i["adet"] * i["birim_fob"] for i in kk))


def test_kategori_bul():
    assert [M.kategori_bul(a) for a, _t in MASRAF_08] == list(M.KATEGORILER)
    assert M.kategori_bul("", 4) == "ardiye" and M.kategori_bul("Bilinmeyen gider") == "diger"


def test_mikro_dosya_ozeti():
    m = _mikro()["MASTER-008"]
    assert m["tedarikci"] == UNVAN["320.50.005"] and m["giris"] == "2026-05-15" and m["depo"] == "Merkez"
    assert m["beyanname"] == "26343100IM00110580" and m["kur"] == pytest.approx(45.2714)
    assert {s: u["adet"] for s, u in m["urunler"].items()} == {"X24F182S": 1500, "X27F240S": 404, "X27F241S": 99}
    assert m["masraf"]["ardiye"] == pytest.approx(4595.72) and m["masraf_var"]


def test_bir_mikro_dosyasi_uc_pi_dosyasina_baglanir():
    """MASTER-008 = PIFAZ251125-2 + -5 + -4-1 (adetler ürün ürün birebir); aynı tedarikçinin başka dosyası (4)
    adetleri tutmadığı için kümeye girmez."""
    plan = _plan()
    assert sorted(plan["eslesme"]["MASTER-008"]) == [1, 2, 3]
    assert plan["ekle"] == [] and plan["eslesmeyen"] == []


def test_masraf_mikro_toplamina_olceklenir_dagilim_korunur():
    plan = _plan()
    yeni = {g["id"]: g["yeni"].get("masraflar") for g in plan["guncelle"]}
    toplam = sum(sum(m.values()) for m in yeni.values())
    assert toplam == pytest.approx(sum(t for _a, t in MASRAF_08), abs=0.05)
    # navlun zaten tutuyordu: değişmez
    assert yeni[1]["navlun"] == pytest.approx(2673.04, abs=0.01)
    # ardiye 2.226,91 → 4.595,72: her PI kendi payıyla ölçeklenir
    oran = 4595.72 / (960.1 + 1167.8 + 99.01)
    assert yeni[1]["liman_ardiye"] == pytest.approx(960.1 * oran, abs=0.01)
    assert yeni[2]["liman_ardiye"] == pytest.approx(1167.8 * oran, abs=0.01)
    # diğer kalemindeki iki alt kalem (nakliye + tahliye) birlikte ölçeklenir, ayrımları korunur
    d_oran = 2686.18 / (161.9 + 342.84 + 196.92 + 417.01 + 16.69 + 35.35)
    assert yeni[3]["tahliye_depolama_tasima"] == pytest.approx(35.35 * d_oran, abs=0.01)


def test_durum_teslim_tarihi_beyanname_mikrodan():
    g = {x["id"]: x["yeni"] for x in _plan()["guncelle"]}
    assert g[1]["durum"] == "Teslim Alındı" and g[1]["stok_islendi"] is True and g[1]["teslim_tarihi"] == "2026-05-15"
    assert "durum" not in g[2] and "stok_islendi" not in g[2]
    assert all(v["mikro_kodu"] == "MASTER-008" and v["mikro_beyanname"] == "26343100IM00110580" for v in g.values())


def test_ikinci_turda_degisiklik_yok():
    """Plan uygulandıktan sonra aynı veriyle yeni plan boş olmalı (her turda yeniden yazmasın)."""
    d, k = _app()
    plan = _plan()
    dm = {x["id"]: x for x in d}
    for g in plan["guncelle"]:
        dm[g["id"]].update(g["yeni"])
    p2 = M.plan_yap(_mikro(), list(dm.values()), k, lambda x: dict(x["masraflar"]),
                    lambda x, kk: sum(i["adet"] * i["birim_fob"] for i in kk))
    assert p2["guncelle"] == []


def test_mikroda_masraf_yoksa_uygulamanin_masrafina_dokunulmaz():
    m = _mikro()
    m["MASTER-008"]["masraf_var"] = False
    d, k = _app()
    p = M.plan_yap(m, d, k, lambda x: dict(x["masraflar"]), lambda x, kk: 1.0)
    assert all("masraflar" not in g["yeni"] for g in p["guncelle"])


def test_uygulamada_olmayan_kalem_varsayilan_alt_kaleme_fob_payiyla():
    m = {"kod": "X", "masraf_var": True, "masraf": dict({k: 0.0 for k in M.KATEGORILER}, gumruk=300.0)}
    h = M.masraf_hedefi(m, [{"id": 1, "masraflar": {"navlun": 10}}, {"id": 2, "masraflar": {}}], {1: 100, 2: 200})
    assert h[1][0] == {"gv": 100.0} and h[2][0] == {"gv": 200.0}       # navlun Mikro'da 0 → kalkar


def test_eslesmeyen_eski_dosya_eklenmez_yeni_acilan_eklenir():
    """Adetleri tutmayan eski Mikro dosyası çift kayıt olmasın diye EKLENMEZ, rapora düşer; uygulamada hiç
    benzeri olmayan ya da bugünden sonra açılan Mikro dosyası eklenir."""
    mdos = [_mdosya("MASTER-011", olusturma="2026-11-02"), _mdosya("MASTER-006", olusturma="2026-02-01")]
    satir = [_satir("MASTER-011", "YENI1", 10, 500, tarih="2026-11-02"),
             _satir("MASTER-006", "X24F182S", 333, 20000, tarih="2026-02-01")]
    m = M.mikro_dosyalari(mdos, satir, [], UNVAN, {})
    d, k = _app()
    p = M.plan_yap(m, d, k, lambda x: dict(x["masraflar"]), lambda x, kk: 1.0)
    assert [y["dosya"]["dosya_no"] for y in p["ekle"]] == ["MASTER-011"]
    y = p["ekle"][0]
    assert y["dosya"]["durum"] == "Teslim Alındı" and y["dosya"]["stok_islendi"] is True
    assert y["kalemler"] == [{"sku": "YENI1", "adet": 10, "birim_fob": 50.0}]
    assert [e["kod"] for e in p["eslesmeyen"]] == ["MASTER-006"]


def test_belirsiz_kume_baglanmaz():
    """İki farklı dosya kümesi aynı adetleri tutuyorsa hiçbiri bağlanmaz (yanlış PI'ya masraf yazılmasın)."""
    ted = "SHENZHEN MASTER TECHNOLOGY CO., LTD"
    d = [{"id": i, "dosya_no": f"P{i}", "tarih": "2026-05-01", "tedarikci": ted, "masraflar": {}} for i in (1, 2)]
    k = {1: [{"sku": "A", "adet": 10, "birim_fob": 1}], 2: [{"sku": "A", "adet": 10, "birim_fob": 1}]}
    m = M.mikro_dosyalari([_mdosya("M-1")], [_satir("M-1", "A", 10, 10)], [], UNVAN, {})
    esl, bel = M.eslestir(m, d, k)
    assert "M-1" not in esl and "M-1" in bel


def test_kayitli_bag_oncelikli():
    d, k = _app()
    d[3]["mikro_kodu"] = "MASTER-008"            # kullanıcı / önceki tur bağlamış
    esl, _ = M.eslestir(_mikro(), d, k)
    assert esl["MASTER-008"] == [4]


def test_varsayilan_acik(monkeypatch):
    """Kullanıcı kararı: onay ekranı yok, kayıt yoksa açık; yalnız {"acik": false} kapatır."""
    monkeypatch.setattr(M, "durum", lambda: {})
    assert M.acik_mi() is True
    monkeypatch.setattr(M, "durum", lambda: {"acik": False})
    assert M.acik_mi() is False


def test_yeni_veri_yoksa_yazmaz(monkeypatch):
    monkeypatch.setattr(M, "durum", lambda: {"son_calisma": "2026-10-21T10:00:00"})
    monkeypatch.setattr(M, "son_aktarim", lambda: "2026-10-21T10:00:00")
    monkeypatch.setattr(M, "plan_hazirla", lambda: pytest.fail("yeni veri yokken plan hazırlandı"))
    assert M.otomatik() is None


def test_esitleme_turlarina_eklendi():
    import importlib.util
    from pathlib import Path
    kok = Path(__file__).resolve().parent.parent
    app = (kok / "app.py").read_text(encoding="utf-8")
    assert "_mod.ISLER" in app.split("def _mikro_esitle_dene", 1)[1].split("\ndef ", 1)[0]
    spec = importlib.util.spec_from_file_location("otonom_mikro_esitle_ith", kok / "otonom" / "mikro_esitle.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert ("ithalat.mikro_ithalat", "otomatik") in {(m, f) for _a, m, f in mod.ISLER}


def test_excel_kapisi_mikro_acikken_kaydetmez():
    """Mikro eşitlemesi açıkken satın alım raporu Excel'i dosya açmaz (aynı ithalat iki kez girmesin)."""
    from pathlib import Path
    kaynak = (Path(__file__).resolve().parent.parent / "ithalat" / "main.py").read_text(encoding="utf-8")
    govde = kaynak.split("def kapi_ithalat_rapor", 1)[1].split("\ndef ", 1)[0]
    once = govde.split("up = dosya", 1)[0]
    assert "_mikro_ithalat_acik()" in once and "return" in once


TESLIM = "Teslim Alındı"


def _ikiz():
    """Canlı MASTER-004 / -005: aynı ürün, aynı adet (3.900 X24F240P), FOB farklı (birim 71 / 70). Uygulamada biri
    tek dosya (11), öteki üç dosya (12+13+14). Eski arama en küçük kümeyi ilk bulduğu için ikisini ters bağlıyordu."""
    ted = "SHENZHEN MASTER TECHNOLOGY CO., LTD"
    d = [{"id": 11, "dosya_no": "PIFAZ251018-1-2-3", "tarih": "2025-10-18", "tedarikci": ted, "durum": TESLIM,
          "teslim_tarihi": "2025-11-20", "masraflar": {}}] + \
        [{"id": i, "dosya_no": f"PIFAZ251018-{i - 11}", "tarih": "2025-10-18", "tedarikci": ted, "durum": TESLIM,
          "teslim_tarihi": "2025-11-25", "masraflar": {}} for i in (12, 13, 14)]
    k = {11: [{"sku": "X24F240P", "adet": 3900, "birim_fob": 70}],
         12: [{"sku": "X24F240P", "adet": 1300, "birim_fob": 71}], 13: [{"sku": "X24F240P", "adet": 1300, "birim_fob": 71}],
         14: [{"sku": "X24F240P", "adet": 1300, "birim_fob": 71}]}
    mdos = [_mdosya("MASTER-004", olusturma="2025-11-01"), _mdosya("MASTER-005", olusturma="2025-11-01")]
    satir = [_satir("MASTER-004", "X24F240P", 3900, 3900 * 71, tarih="2025-11-20"),
             _satir("MASTER-005", "X24F240P", 3900, 3900 * 70, tarih="2025-11-25")]
    return M.mikro_dosyalari(mdos, satir, [], UNVAN, {}), d, k


def test_ayni_adette_fob_dogru_kumeyi_secer():
    m, d, k = _ikiz()
    esl, bel = M.eslestir(m, d, k)
    assert esl == {"MASTER-004": [12, 13, 14], "MASTER-005": [11]} and bel == {}


def test_teslim_alinmis_dosyanin_tarihi_ezilmez():
    """Canlı: 69 eski dosyada Mikro giriş tarihi toplu kayıt günü (2025-10-22); stok yaşı kaymasın."""
    m, d, k = _ikiz()
    p = M.plan_yap(m, d, k, lambda x: dict(x["masraflar"]), lambda x, kk: 1.0)
    assert all("teslim_tarihi" not in g["yeni"] for g in p["guncelle"])
    d[0]["teslim_tarihi"] = None
    p = M.plan_yap(m, d, k, lambda x: dict(x["masraflar"]), lambda x, kk: 1.0)
    assert [g["yeni"]["teslim_tarihi"] for g in p["guncelle"] if g["id"] == 11] == ["2025-11-25"]


def test_belirsiz_ya_da_antrepodaki_ikiz_varken_yeni_dosya_eklenmez():
    """Yeni açılan Mikro dosyası uygulamadaki antrepo dosyasıyla birebir tutmasa da (bedelsiz adet farkı) ekleme yok:
    aynı ürünü taşıyan bağsız antrepo dosyası varsa çift kayıt olurdu."""
    ted = "SHENZHEN MASTER TECHNOLOGY CO., LTD"
    d = [{"id": 1, "dosya_no": "PI-1", "tarih": "2026-10-01", "tedarikci": ted, "durum": "Antrepoda", "masraflar": {}}]
    k = {1: [{"sku": "A", "adet": 100, "birim_fob": 10}]}
    m = M.mikro_dosyalari([_mdosya("MASTER-020", olusturma="2026-11-05")],
                          [_satir("MASTER-020", "A", 105, 1000, tarih="2026-11-05")], [], UNVAN, {})
    p = M.plan_yap(m, d, k, lambda x: dict(x["masraflar"]), lambda x, kk: 1.0)
    assert p["ekle"] == [] and [e["kod"] for e in p["eslesmeyen"]] == ["MASTER-020"]
    d[0]["durum"], d[0]["mikro_kodu"] = TESLIM, "MASTER-019"     # o dosya başka Mikro dosyasına bağlıysa eklenir
    p = M.plan_yap(m, d, k, lambda x: dict(x["masraflar"]), lambda x, kk: 1.0)
    assert [y["dosya"]["dosya_no"] for y in p["ekle"]] == ["MASTER-020"]


def test_bedelsiz_dosya_eklenmez():
    m = M.mikro_dosyalari([_mdosya("LE TUTTI-001")], [_satir("LE TUTTI-001", "RMAFA004", 600, 0)], [], UNVAN, {})
    p = M.plan_yap(m, [], {}, lambda x: {}, lambda x, kk: 0.0)
    assert p["ekle"] == [] and "bedelsiz" in p["eslesmeyen"][0]["sebep"]


def test_kayitli_baga_sonradan_giren_kardes_eklenir():
    """MASTER-009 önce PIFAZ251210-2 ile bağlandı; antrepodaki -1 sonra aynı Mikro dosyasıyla girerse bağa eklenir."""
    ted = "SHENZHEN MASTER TECHNOLOGY CO., LTD"
    d = [{"id": 1, "dosya_no": "PIFAZ251210-2", "tarih": "2025-12-10", "tedarikci": ted, "durum": TESLIM,
          "mikro_kodu": "MASTER-009", "masraflar": {}},
         {"id": 2, "dosya_no": "PIFAZ251210-1", "tarih": "2025-12-10", "tedarikci": ted, "durum": "Antrepoda",
          "masraflar": {}}]
    k = {1: [{"sku": "A", "adet": 100, "birim_fob": 10}], 2: [{"sku": "B", "adet": 50, "birim_fob": 20}]}
    m = M.mikro_dosyalari([_mdosya("MASTER-009", olusturma="2026-01-10")],
                          [_satir("MASTER-009", "A", 100, 1000, tarih="2026-01-10"),
                           _satir("MASTER-009", "B", 50, 1000, tarih="2026-03-01")], [], UNVAN, {})
    esl, _ = M.eslestir(m, d, k)
    assert esl["MASTER-009"] == [1, 2]


def test_kalem_adi_gelmeyen_masrafa_dokunulmaz():
    """Canlıda aktarıcı masraf satırının adını / sırasını henüz getirmiyor; tutarların hepsi 'diğer'e düşüp navlun,
    ardiye gibi kalemleri sıfırlamasın."""
    satir = [_satir("MASTER-008", "X24F182S", 1500, 95040), _satir("MASTER-008", "X27F240S", 404, 115600),
             _satir("MASTER-008", "X27F241S", 99, 9801)]
    cari = [_fatura("MASTER-008", 220441)] + [dict(_masraf("MASTER-008", a, t, i), cha_aciklama=None, cha_satir_no=None)
                                              for i, (a, t) in enumerate(MASRAF_08)]
    m = M.mikro_dosyalari([_mdosya()], satir, cari, UNVAN, {1: "Merkez"})
    d, k = _app()
    p = M.plan_yap(m, d, k, lambda x: dict(x["masraflar"]), lambda x, kk: 1.0)
    assert p["guncelle"] and all("masraflar" not in g["yeni"] for g in p["guncelle"])
