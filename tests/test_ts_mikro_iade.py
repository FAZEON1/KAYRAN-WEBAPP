# -*- coding: utf-8 -*-
"""Teknik servis / iade yeniden düzen (22.10.2026).

Kullanıcı: "Serdar abi her iade faturası işlediğinde bu arayüze düşsün; bir faturada 5 + 1 adet varsa 6 kayıt alt alta
… ilk aşama 'iade faturası işlendi', ekranda 'mal kabul bekleniyor' … açıklamasız ya da 'hasar' yazanlar 'teslim
alınmayan hasarlı ürünler' … G5F123 yazılırsa o kayda bağlansın … satıldı benden kalksın, Mikro'daki satıştan seri
no ile yakalansın … teknik servis depo hareketleri Kayran stoğuna işlenmesin, Excel ile Mikro'da transfer ederim …
her arayüze geçişte ilk standart hâl."
"""
from datetime import date
from pathlib import Path

import pytest

from teknikservis import mikro_iade as I
from teknikservis import mikro_satis as S
from teknikservis import ts_hesap as H
from teknikservis import ts_masasi as M

KOK = Path(__file__).resolve().parent.parent


def _r(guid, adet, tutar, aciklama="", tarih="2026-10-22", cari="120.01.003", sku="X24F165S", sira=7, **k):
    return dict({"sth_guid": guid, "sth_tarih": tarih + "T00:00:00", "sth_tip": 0, "sth_normal_iade": 1,
                 "sth_cari_kodu": cari, "sth_miktar": adet, "sth_tutar": tutar, "sth_iskonto": 0,
                 "sth_alt_doviz_kuru": 40, "sth_har_doviz_kuru": 1, "sth_evrakno_seri": "IAD", "sth_evrakno_sira": sira,
                 "sth_stok_kod": sku, "sth_giris_depo_no": 9, "sth_aciklama": aciklama}, **k)


SATIR = [
    _r("A", 5, 10000, "Seri No:W2505W03643"),                     # 5 adet → 5 birim, 50 $/adet
    _r("B", 1, 2000, "", sku="K100"),                              # açıklamasız → hasarlı
    _r("C", 1, 2000, "G5F 123 ekran arızası", sku="K100"),          # teknik servis iadesi
    _r("D", 3120, 99999, "toplu stok iadesi"),                     # toplu (> 20)
    _r("E", 1, 2000, "", tarih="2026-10-21"),                       # başlangıçtan önce
    _r("F", 1, 2000, "", cari="320.02.070"),                        # tedarikçi
    _r("G", 1, 2000, "", sth_normal_iade=0),                        # iade değil
]


def test_birimler_her_adet_ayri_satir():
    b = I.birimler(SATIR, "2026-10-22", unvan={"120.01.003": "EERA"}, depo_adi={9: "İADE DEPO"})
    assert [x["anahtar"] for x in b] == ["a#1", "a#2", "a#3", "a#4", "a#5", "b#1", "c#1"]
    a1 = b[0]
    assert a1["birim_usd"] == pytest.approx(50.0) and a1["fatura_no"] == "IAD7" and a1["cari"] == "EERA"
    assert a1["seri_onerisi"] == "W2505W03643" and a1["hasarli"] is False and a1["depo"] == "İADE DEPO"
    assert a1["adet_sira"] == "1/5" and b[4]["adet_sira"] == "5/5"
    assert b[5]["hasarli"] is True                       # açıklama yok
    assert b[6]["g5f"] == "G5F00123" and b[6]["hasarli"] is False


def test_g5f_hasar_seri():
    assert I.g5f_no("g5f-00123") == "G5F00123" and I.g5f_no("G5F55500032") == "G5F00032" and I.g5f_no("yok") is None
    assert I.hasarli_mi("") and I.hasarli_mi("Kargo HASARLI geldi") and I.hasarli_mi("Teslim alınmayan hasarlı ürünler")
    assert not I.hasarli_mi("ekran çizik, seri no: AB12")
    assert I.seri_onerisi("seri no: ab-1234 kutusuz") == "AB-1234" and I.seri_onerisi("açıklama") == ""


def test_plan_g5f_eslesir_islenmis_atlanir():
    b = I.birimler(SATIR, "2026-10-22")
    kayit = [{"id": 1, "servis_form_no": "G5F00123", "mikro_iade_anahtar": None},
             {"id": 2, "servis_form_no": "G5F00200", "mikro_iade_anahtar": "a#1"}]
    p = I.plan_yap(b, kayit)
    assert [x["anahtar"] for x in p["yeni"]] == ["a#2", "a#3", "a#4", "a#5", "b#1"]
    assert [(k["id"], x["anahtar"]) for k, x in p["eslesen"]] == [(1, "c#1")]
    # bağlanan kayıt artık işlenmiş sayılır: ikinci turda yeni kayıt / eşleşme yok
    kayit[0]["mikro_iade_anahtar"] = "c#1"
    kayit += [{"id": 10 + i, "servis_form_no": f"G5F{300 + i:05d}", "mikro_iade_anahtar": x["anahtar"]}
              for i, x in enumerate(p["yeni"])]
    assert I.plan_yap(b, kayit) == {"yeni": [], "eslesen": []}


def test_yeni_kayit_ilk_asama_fatura_islendi():
    b = I.birimler(SATIR, "2026-10-22", unvan={"120.01.003": "EERA"})[5]
    k = I.yeni_kayit(b, "G5F00818", "KLAVYE")
    assert k["mevcut_durum"] == "iade faturası işlendi" and k["arayuz"] == "iade" and k["servis_form_no"] == "G5F00818"
    assert k["hasarli_teslim"] is True and k["iade_fiyat"] == pytest.approx(50.0) and k["iade_pb"] == "USD"
    assert "mal_kabul_tarihi" not in k                   # fiziksel kabulde yazılır
    assert "açıklama yok" in I.gecmis_metni(b)


def test_masa_bekleyen_ve_hasarli_grubu_ust_bant():
    bugun = date(2026, 12, 1)
    kay = [{"id": 1, "mevcut_durum": "iade faturası işlendi", "iade_fatura_tarihi": "2026-10-22",
            "iade_fatura_no": "IAD7", "iade_aciklama": "Seri No:W25", "servis_form_no": "G5F00818"},
           {"id": 2, "mevcut_durum": "iade faturası işlendi", "iade_fatura_tarihi": "2026-11-25", "hasarli_teslim": True,
            "servis_form_no": "G5F00819"},
           {"id": 3, "mevcut_durum": "mal kabül", "mikro_iade_anahtar": "x#1", "servis_form_no": "G5F00820"},
           {"id": 4, "mevcut_durum": "teknisyende", "servis_form_no": "G5F00700"}]
    v = M.kayit_masa_verisi(kay, {3: 2, 4: 1}, bugun=bugun)
    s = {r["id"]: r for r in v["satirlar"]}
    assert [r["id"] for r in v["satirlar"]][:2] == [1, 2]
    assert s[1]["sla_grup"] == M.BEKLEYEN_GRUP and s[2]["sla_grup"] == M.HASARLI_GRUP
    assert s[1]["durum_m"] == "mal kabul bekleniyor"
    assert s[2]["durum_m"] == "mal kabul bekleniyor (teslim alınmayan hasarlı ürünler)"
    assert s[1]["_durum"]["renk"] == "kirmizi" and s[2]["_durum"]["renk"] == "amber"      # 40 gün / 6 gün
    assert "açıklama: Seri No:W25" in s[1]["urun_alt"] and "fatura IAD7" in s[1]["urun_alt"]
    assert s[3]["_durum"]["renk"] == "mor"                                                 # Mikro'dan, mal kabul edildi
    assert {g["k"] for g in v["gorunumler"]} >= {"bekl", "hasar"}
    oz = {o["k"]: o["dg"] for o in v["ozet"]}
    assert oz == {"bekleyen": "2", "hasarli": "1", "gecikmis": "1"}
    assert I.gecikme_mesaji(kay, bugun).startswith("Teknik Servis › İade: 1 ürün 30 günden uzun")
    assert I.gecikme_mesaji(kay, date(2026, 11, 1)) is None


def test_otomatik_satildi_seri_no_ile():
    kay = [{"id": 1, "servis_form_no": "G5F1", "stok_kodu": "X24", "seri_no": "w25 05", "depo": "outlet",
            "mevcut_durum": "satışa hazır", "depo_tarihi": "2026-10-20"},
           {"id": 2, "servis_form_no": "G5F2", "stok_kodu": "X24", "seri_no": "OLD1", "depo": "ikinci el",
            "mevcut_durum": "satışa hazır", "depo_tarihi": "2026-10-20"},           # satış depodan önce
           {"id": 3, "servis_form_no": "G5F3", "stok_kodu": "X24", "seri_no": "W2505", "depo": "merkez",
            "mevcut_durum": "gönderildi", "depo_tarihi": "2026-10-20"},             # satış deposu değil
           {"id": 4, "servis_form_no": "G5F4", "stok_kodu": "X24", "seri_no": "SAT1", "depo": "iade",
            "mevcut_durum": "satıldı", "depo_tarihi": "2026-10-20"}]                # zaten satıldı
    seri = {"W2505": [{"chz_guid": "g1", "chz_stok_kodu": "X24", "chz_st_tarih": "2026-10-21T00:00:00",
                       "chz_st_cari_kodu": "120.01.003", "chz_st_evr_seri": "G5F26", "chz_st_evr_sira": 2525,
                       "chz_st_fiati_alt": 61.5}],
            "OLD1": [{"chz_guid": "g2", "chz_stok_kodu": "X24", "chz_st_tarih": "2026-10-01T00:00:00",
                      "chz_st_cari_kodu": "120.01.003", "chz_st_evr_seri": "G5F26", "chz_st_evr_sira": 1}],
            "SAT1": [{"chz_guid": "g3", "chz_st_tarih": "2026-10-21", "chz_st_cari_kodu": "120.01.003"}]}
    es = S.eslesmeler(kay, seri, {"120.01.003": "EERA BİLGİSAYAR"})
    assert [(k["id"], a) for k, a in es] == [(1, {"satis_firma": "EERA BİLGİSAYAR", "satis_fiyati": 61.5,
                                                  "satis_tarihi": "2026-10-21", "satis_fatura_no": "G5F26-2525",
                                                  "bedelsiz": False})]
    assert "G5F26-2525" in S.gecmis_metni(es[0][1])


def test_transfer_listesi_tarih_araligi():
    kay = [{"servis_form_no": "G5F2", "stok_kodu": "X24", "seri_no": "S2", "depo": "outlet", "depo_tarihi": "2026-10-21T10:00",
            "giris_depo": "TEKNİK DEPO"},
           {"servis_form_no": "G5F1", "stok_kodu": "X24", "seri_no": "S1", "depo": "ikinci el", "depo_tarihi": "2026-10-20"},
           {"servis_form_no": "G5F3", "depo": "outlet", "depo_tarihi": "2026-09-01"},
           {"servis_form_no": "G5F4", "depo": "", "depo_tarihi": "2026-10-20"}]
    t = H.transfer_listesi(kay, date(2026, 10, 15), date(2026, 10, 22), lambda k: k.get("giris_depo") or "İADE DEPO",
                           {"outlet": "OUTLET DEPO", "ikinci el": "İKİNCİ EL DEPO"}.get)
    assert [(r["Servis no"], r["Transfer tarihi"], r["Kaynak depo"], r["Hedef depo"]) for r in t] == [
        ("G5F1", "20.10.2026", "İADE DEPO", "İKİNCİ EL DEPO"), ("G5F2", "21.10.2026", "TEKNİK DEPO", "OUTLET DEPO")]


def test_sayfa_girisi_sifirlanacak_anahtarlar():
    from teknikservis import ts_ekran as E
    assert E.sifirlanacak_mi("_ts_depo_secili") and E.sifirlanacak_mi("depo_filtre_coklu")
    assert E.sifirlanacak_mi("ts_masa_iade") and E.sifirlanacak_mi("_koru_depo_ara")
    assert not E.sifirlanacak_mi("ts_sayfa") and not E.sifirlanacak_mi("_ts_bilgi") and not E.sifirlanacak_mi("mk_seri")


def test_ekran_ve_esitleme_baglantilari():
    import otonom.mikro_esitle as ES
    assert ("İade faturaları → teknik servis", "teknikservis.mikro_iade", "otomatik") in ES.ISLER
    assert ("Teknik servis satıldı", "teknikservis.mikro_satis", "otomatik") in ES.ISLER
    a = (KOK / "araclar" / "mikro_aktarici" / "mikro_kayran.py").read_text(encoding="utf-8")
    i = a.index('"tablo": "mikro_alim_satir"')
    assert "sth_aciklama" in a[i:i + 1200]
    m = (KOK / "teknikservis" / "main.py").read_text(encoding="utf-8")
    assert 'st.popover("💰 Satıldı"' not in m and "_iade_mal_kabul_formu(kayit)" in m
    assert '"Son kullanıcı (S.K.)"' in m and "mikro_cariler()" in m and "_transfer_listesi_dugmesi(kayitlar)" in m
    st_ = (KOK / "teknikservis" / "stok.py").read_text(encoding="utf-8")
    assert "if mikro_yonetir():" in st_[st_.index("def _uygula("):]
    sql = (KOK / "veritabani" / "55_ts_mikro_iade.sql").read_text(encoding="utf-8")
    assert "mikro_iade_anahtar text" in sql and "sth_aciklama text" in sql
