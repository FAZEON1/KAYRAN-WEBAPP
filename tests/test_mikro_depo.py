# -*- coding: utf-8 -*-
"""Mikro depo hareketleri → Happy Life, stok yaşı, satılamayan stok (kayranpm/mikro_depo.py, Ekim 2026).

Depo numaraları / adları ve hareket kodları Mikro'daki gibi (mikro_kesif 21.10.2026): sth_tip 0 giriş, 1 çıkış,
2 depolar arası sevk; sth_cins 12 ithalat (evraktip 13), 6 sevk (evraktip 2), 10 sayım, 9 değer farkı; iade
girişi cins 0 evraktip 3 normal_iade 1. İthalatın bir kısmı doğrudan Happy Life'a (depo 4) giriyor, bir kısmı
Merkez'e ya da ALY ANTREPO'ya, oradan sevkle Happy Life'a."""
import re
import sys
import types
from datetime import date
from pathlib import Path

from kayranpm import mikro_depo as M

KOK = Path(__file__).resolve().parent.parent
DEPOLAR = {1: "Merkez depo", 2: "ASEL DEPO", 3: "SERVİS DEPO", 4: "HAPPY LİFE", 8: "ALY ANTREPO ",
           9: "İADE DEPO "}
BUGUN = date(2026, 10, 21)
SKU = "FAZEON X27F182S"


def _h(tarih, tip, cins, evraktip, miktar, giris=0, cikis=0, iade=0, exim=None, iptal=False, seri="IRS",
       sira=1, sku=SKU):
    return {"sth_guid": f"g{tarih}{tip}{cins}{giris}{cikis}{miktar}", "sth_tarih": f"{tarih}T00:00:00",
            "sth_tip": tip, "sth_cins": cins, "sth_evraktip": evraktip, "sth_normal_iade": iade,
            "sth_evrakno_seri": seri, "sth_evrakno_sira": sira, "sth_stok_kod": sku, "sth_miktar": miktar,
            "sth_giris_depo_no": giris, "sth_cikis_depo_no": cikis, "sth_exim_kodu": exim, "sth_iptal": iptal}


HAREKET = [
    _h("2026-02-24", 0, 12, 13, 1500, giris=4, exim="VANEX-010"),          # ithalat doğrudan Happy Life'a
    _h("2026-03-10", 0, 12, 13, 800, giris=1, exim="VANEX-012"),           # ithalat Merkez'e
    _h("2026-05-05", 2, 6, 2, 300, giris=4, cikis=1, sira=7),              # Merkez → Happy Life sevk
    _h("2026-06-01", 0, 12, 13, 1000, giris=8, exim="VANEX-015"),          # ithalat antrepoya
    _h("2026-07-01", 2, 6, 2, 1000, giris=4, cikis=8, sira=9),             # antrepo → Happy Life sevk
    _h("2026-08-01", 1, 0, 1, 1200, cikis=4, sira=21),                      # Happy Life'tan satış
    _h("2026-08-15", 0, 9, 3, 40, giris=1),                                 # değer farkı: mal hareketi değil
    _h("2026-09-01", 0, 12, 13, 999, giris=4, iptal=True),                  # iptal edilmiş giriş
    _h("2026-09-01", 0, 0, 3, 5, giris=9, iade=1, sira=33),                 # satış iadesi İADE DEPO'ya
    _h("2025-11-14", 0, 10, 12, 3, giris=1, sira=2),                        # sayım fazlası Merkez'e
]
# mikro_stok_miktar: HL 1500 + 300 + 1000 − 1200 = 1600 · Merkez 800 − 300 + 3 = 503 · İade 5
STOK = [{"sto_kod": SKU, "sto_isim": "FAZEON 27 MONITOR", "depo": 4, "miktar": 1600},
        {"sto_kod": SKU, "depo": 1, "miktar": 503}, {"sto_kod": SKU, "depo": 9, "miktar": 5}]


def _har():
    return M.hareketler(HAREKET, DEPOLAR)


def test_hareketler_iptal_deger_farki_atlanir_depo_ve_sku_ortak_kurala_gore():
    h = _har()
    assert len(h) == 8                                     # değer farkı ve iptal satırı yok
    assert {x["sku"] for x in h} == {"X27F182S"}            # "FAZEON X27F182S" = X27F182S
    sevk = [x for x in h if x["tur"] == "sevk"]
    assert [(x["cikis"], x["giris"]) for x in sevk] == [("MERKEZ DEPO", "HAPPY LIFE"), ("ALY ANTREPO", "HAPPY LIFE")]
    assert [x["tur"] for x in h if x["giris"] == "İADE DEPO"] == ["iade"]
    assert [x["tur"] for x in h if x["giris"] == "MERKEZ DEPO"] == ["sayim", "ithalat"]
    assert h[0]["tarih"] == "2025-11-14"                   # eski → yeni
    assert next(x for x in h if x["tarih"] == "2026-02-24")["belge"] == "VANEX-010"
    assert next(x for x in h if x["tarih"] == "2026-08-01")["belge"] == "IRS-21"


def test_happy_life_giris_tarihi_depoya_girdigi_gun_fifo():
    """Happy Life'taki yaş (kira): malın Happy Life'a girdiği gün. Merkez'den sevk edilen mal sevk gününden,
    antrepodan gelen sevk gününden yaşlanır. 1.600 adet elde: en yeni 1.000 (01.07) + 300 (05.05) + 300 (24.02)."""
    from kayranpm.mikro_stok import kirilim_yap
    kir, adlar = kirilim_yap(STOK, DEPOLAR)
    y = M.depo_yaslari(M.depo_partileri(_har()), kir, BUGUN)
    oz, kal = y[("HAPPY LIFE", "X27F182S")]
    assert [(k["tarih"], k["kalan"], k["tur"], k["kaynak"]) for k in kal] == [
        ("2026-02-24", 300, "ithalat", ""), ("2026-05-05", 300, "sevk", "MERKEZ DEPO"),
        ("2026-07-01", 1000, "sevk", "ALY ANTREPO")]
    assert oz["stok"] == 1600 and oz["kapsanmayan"] == 0 and oz["en_eski_gun"] == 239
    satir = M.depo_ozet_satirlari(y, "HAPPY LIFE", adlar)
    assert satir == [{"sku": "X27F182S", "ad": "FAZEON 27 MONITOR", "stok": 1600, "parti": 3,
                      "ort_gun": round((300 * 239 + 300 * 169 + 1000 * 112) / 1600), "en_eski_gun": 239,
                      "en_eski_tarih": "2026-02-24", "en_yeni_gun": 112, "kayitsiz": 0}]
    pr = M.depo_parti_satirlari(y, "HAPPY LIFE", BUGUN, adlar)
    assert [(r["giris_tarihi"], r["yas"], r["kalan"], r["tur"], r["belge"]) for r in pr] == [
        ("2026-02-24", 239, 300, "İthalat", "VANEX-010"), ("2026-05-05", 169, 300, "Depo sevki", "IRS-7"),
        ("2026-07-01", 112, 1000, "Depo sevki", "IRS-9")]
    t = M.toplam(satir)
    assert t["stok"] == 1600 and t["en_eski_gun"] == 239 and t["cesit"] == 1


def test_satilabilir_havuz_ic_sevk_yasi_sifirlamaz():
    """Stok yaşı: Merkez + Happy Life tek havuz. Merkez → Happy Life sevki yeni parti değil (mal 10.03'te
    girdi); antrepodan sevk partidir (antrepodaki ithalat girişi değil); iade ve sayım fazlası parti değil."""
    p = M.havuz_partileri(_har(), {"MERKEZ DEPO", "HAPPY LIFE"})
    assert [(x["tarih"], x["adet"], x["depo"]) for x in sorted(p["X27F182S"], key=lambda x: x["tarih"])] == [
        ("2026-02-24", 1500, "HAPPY LIFE"), ("2026-03-10", 800, "MERKEZ DEPO"), ("2026-07-01", 1000, "HAPPY LIFE")]
    from kayranpm.stok_yasi import urun_yasi
    oz, kal = urun_yasi(1600 + 503, p["X27F182S"], BUGUN)
    assert [(k["tarih"], k["kalan"]) for k in kal] == [("2026-02-24", 303), ("2026-03-10", 800), ("2026-07-01", 1000)]


def test_asel_eski_satilabilir_depo():
    """ASEL DEPO 2025'te satılabilir depoydu: oraya ithalat partidir, oradan Merkez'e sevk yeni parti değil."""
    h = M.hareketler([_h("2025-04-01", 0, 12, 13, 500, giris=2, exim="VANEX-003"),
                      _h("2026-03-01", 2, 6, 2, 500, giris=1, cikis=2)], DEPOLAR)
    p = M.havuz_partileri(h, {"MERKEZ DEPO", "HAPPY LIFE"})
    assert [(x["tarih"], x["adet"]) for x in p["X27F182S"]] == [("2025-04-01", 500)]


def test_bos_veri_bos_sonuc():
    assert M.hareketler([], DEPOLAR) == [] and M.depo_partileri([]) == {} and M.havuz_partileri([], set()) == {}
    assert M.depo_yaslari({}, {}, BUGUN) == {} and M.depo_ozet_satirlari({}, "HAPPY LIFE") == []
    assert M.toplam([]) == {"cesit": 0, "stok": 0, "kayitsiz": 0, "ort_gun": None, "en_eski_gun": None}
    assert M.uygula({"bos": True}) is False and M.uygula(None) is False


def test_mikroda_kaydi_olmayan_stok_kayitsiz():
    from kayranpm.mikro_stok import kirilim_yap
    kir, _ = kirilim_yap([{"sto_kod": "N50602", "depo": 4, "miktar": 40}], DEPOLAR)
    oz, kal = M.depo_yaslari({}, kir, BUGUN)[("HAPPY LIFE", "N50602")]
    assert kal == [] and oz["kapsanmayan"] == 40 and oz["en_eski_gun"] is None


def test_excel_karsilastirma_sku_yazimi_birlesir():
    excel = [{"sku": "X27F182S", "sku_tanim": "FAZEON 27", "giris_tarihi": "2026-03-02", "miktar2": 1200},
             {"sku": "X27F182S", "sku_tanim": "FAZEON 27", "giris_tarihi": "2026-02-24", "miktar2": 1105},
             {"sku": "A5120TRA", "sku_tanim": "PAD", "giris_tarihi": "2026-04-01", "miktar2": 1200}]
    mk = [{"sku": "X27F182S", "ad": "FAZEON 27 MONITOR", "stok": 1479, "en_eski_tarih": "2026-02-24",
           "en_eski_gun": 239}]
    r = {x["sku"]: x for x in M.excel_karsilastir(excel, mk, BUGUN)}
    assert r["X27F182S"]["excel_adet"] == 2305 and r["X27F182S"]["mikro_adet"] == 1479
    assert r["X27F182S"]["excel_en_eski"] == "2026-02-24" and r["X27F182S"]["excel_yas"] == 239
    assert r["A5120TRA"]["mikro_adet"] == 0 and r["A5120TRA"]["mikro_en_eski"] == ""


def test_yas_karsilastir_yalniz_degisenler():
    stok = {"X27F182S": 2103, "FAZE3": 10}
    eski = {"X27F182S": [{"tarih": "2026-07-20", "adet": 3000}], "FAZE3": [{"tarih": "2026-10-01", "adet": 50}]}
    yeni = {"X27F182S": [{"tarih": "2026-03-10", "adet": 2103}], "FAZE3": [{"tarih": "2026-10-01", "adet": 50}]}
    k = M.yas_karsilastir(stok, eski, yeni, BUGUN)
    assert [u["sku"] for u in k["urunler"]] == ["X27F182S"]
    assert k["urunler"][0]["ort_once"] == 93 and k["urunler"][0]["ort_sonra"] == 225
    assert k["once"]["stok"] == k["sonra"]["stok"] == 2113


# ── Bağlantılar: eski kodda bu davranışlar yoktu (doğru sebepten kırmızı) ──
def _sahte_mikro(monkeypatch, acik=True, havuz=None, depo=None):
    sahte = types.ModuleType("kayranpm.mikro_depo")
    sahte.acik_mi = lambda: acik
    sahte.havuz_partileri_oku = lambda: havuz
    sahte.depo_partileri_oku = lambda: depo
    monkeypatch.setitem(sys.modules, "kayranpm.mikro_depo", sahte)
    import kayranpm
    monkeypatch.setattr(kayranpm, "mikro_depo", sahte, raising=False)


def _alim_dosyalari(monkeypatch):
    import ithalat.database as ID
    monkeypatch.setattr(ID, "get_dosyalar", lambda *a, **k: [
        {"id": 1, "durum": "Teslim Alındı", "teslim_tarihi": "2026-07-20", "dosya_no": "VANEX-015"}])
    monkeypatch.setattr(ID, "get_tum_kalemler", lambda *a, **k: [{"dosya_id": 1, "sku": "X27F182S", "adet": 3000}])


def test_stok_yasi_mikro_acikken_partiler_mikrodan(monkeypatch):
    from kayranpm import stok_yasi as Y
    _alim_dosyalari(monkeypatch)
    mikro = {"X27F182S": [{"tarih": "2026-03-10", "adet": 800, "belge": "VANEX-012", "tur": "ithalat"}]}
    _sahte_mikro(monkeypatch, acik=True, havuz=mikro)
    assert Y._bizim_partiler_oku() == mikro
    _sahte_mikro(monkeypatch, acik=False, havuz=mikro)          # kapalı: alım dosyaları
    assert Y._bizim_partiler_oku()["X27F182S"][0]["tarih"] == "2026-07-20"
    _sahte_mikro(monkeypatch, acik=True, havuz=None)            # açık ama Mikro verisi yok: alım dosyaları
    assert Y._bizim_partiler_oku()["X27F182S"][0]["tarih"] == "2026-07-20"


def test_satilamayan_mikro_acikken_bekleme_mikrodan(monkeypatch):
    """Satılamayan stok: stok defteri 30.09.2026'da başladığı için iade deposundaki mal 'giriş kaydı yok'tu;
    Mikro açıkken depoya giriş tarihi Mikro'dan."""
    import kayranpm.database as KD
    import satis.database as SD
    from depo import satilamayan as S
    from depo import ts_mutabakat as T
    monkeypatch.setattr(KD, "_hepsi", lambda t, *a, **k: (
        [{"sku": "X27F182S", "urun_adi": "FAZEON 27", "depo_kirilim": {"İADE DEPO": 5, "MERKEZ DEPO": 503}}]
        if t == "urunler" else []))
    monkeypatch.setattr(SD, "get_iadeler", lambda *a, **k: [])
    monkeypatch.setattr(SD, "get_pacal_map", lambda *a, **k: {"X27F182S": 100.0})
    monkeypatch.setattr(T, "acik_oku", lambda *a, **k: [])
    _sahte_mikro(monkeypatch, acik=True, depo={("İADE DEPO", "X27F182S"): [
        {"tarih": "2026-06-01", "adet": 5, "belge": "IRS-33", "tur": "iade"}]})
    rows, ozet, _m = S.hesapla(BUGUN)
    assert [(r["depo"], r["en_eski_tarih"], r["kayitsiz"], r["yasli"]) for r in rows] == [
        ("İADE DEPO", "2026-06-01", 0, 5)]


def test_mikro_acikken_happylife_hatirlatmasi_cikmaz(monkeypatch):
    from shared import yukleme_takvimi as YT
    _sahte_mikro(monkeypatch, acik=True)
    monkeypatch.setattr(YT, "_ayar", lambda anahtar, varsayilan: varsayilan)
    monkeypatch.setattr(YT, "_OKUYUCU", {})
    assert "happylife" not in {d["anahtar"] for d in YT.durumlar()}
    _sahte_mikro(monkeypatch, acik=False)
    assert "happylife" in {d["anahtar"] for d in YT.durumlar()}


def test_aktarici_sorgusu_ve_goc_ayni_kolonlar(monkeypatch):
    """Aktarıcı (araclar/mikro_aktarici) 'depo_hareket' sorgusunun kolonları 43 numaralı göçteki tabloyla birebir;
    eksik kolon olursa Supabase upsert'i bütün turu düşürür. Yalnız SELECT."""
    import importlib.util
    if importlib.util.find_spec("requests") is None:   # CI'da requests olmayabilir: modül yalnız içe aktarılır
        sahte = types.ModuleType("requests")
        sahte.Session, sahte.RequestException, sahte.Response = object, Exception, object
        monkeypatch.setitem(sys.modules, "requests", sahte)
    spec = importlib.util.spec_from_file_location("mikro_kayran_dh", KOK / "araclar" / "mikro_aktarici" /
                                                  "mikro_kayran.py")
    mk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mk)
    assert "depo_hareket" in mk.SORGULAR, "aktarıcıda depo hareketi sorgusu yok"
    t = mk.SORGULAR["depo_hareket"]
    assert t["tablo"] == M.TABLO and t["anahtar"] == "sth_guid" and t["artimli"]
    sql = " ".join(t["sql"].split())
    assert sql.startswith("SELECT ") and "{SON}" in sql and "sth_lastup_date" in sql
    assert "sth_iptal=0" not in sql.replace(" ", "")              # iptal sonradan güncellensin
    secilen = {c.strip().lower() for c in sql[len("SELECT "):sql.index(" FROM ")].split(",")}
    goc = (KOK / "veritabani" / "43_mikro_depo_hareket.sql").read_text(encoding="utf-8")
    i = goc.index("TABLE IF NOT EXISTS public.mikro_depo_hareket (")
    govde = goc[i:goc.index(");", i)]
    kolon = {m.group(1) for m in re.finditer(r"(\w+) (?:uuid|timestamp|integer|text|numeric|boolean|timestamptz)",
                                             govde)} - {"senk_zamani"}
    assert secilen == kolon
    assert set(M.KOLONLAR.split(",")) <= kolon                    # uygulamanın okuduğu kolonlar tabloda var
    assert "sth_iptal" in mk.BOOL_KOLONLAR
    from shared.yedek_tablolari import HARIC
    assert M.TABLO in HARIC
