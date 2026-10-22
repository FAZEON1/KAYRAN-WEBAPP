# -*- coding: utf-8 -*-
"""Kullanıcı (22.10.2026, Banka bakiyeleri ekran görüntüsüyle): "Artık buradaki tahsilata ihtiyaç yok, zaten
Mikro'dan gelecek bu datalar. Daha önce de söyledim ama atlamışsın; artık datalar Mikro'dan gelecekse bu gibi her
şeyi kaldır."

Eskiden düğmeler duruyor, pencere açılınca yalnız "Mikro'ya girilir" notu çıkıyordu — üstelik canlıda not bile
çıkmıyordu: mikro_muhasebe.otomatik() turun başında okuduğu durumu geri yazıp uygula()'nın kaydettiği
bagli_bankalar'ı her turda siliyordu, hiçbir hesap "Mikro'ya bağlı" sayılmıyor, tahsilat / virman formu açılıyordu.
"""
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _oku(yol):
    return (KOK / yol).read_text(encoding="utf-8")


# ── Kök hata: bağlı hesap listesi her turda siliniyordu ─────────────
def test_otomatik_bagli_bankalari_silmez(monkeypatch):
    from kayranacc import mikro_muhasebe as MM
    import satis.mikro_esitle as SE
    kayit = {"d": {"acik": True, "son_calisma": "2026-10-22T10:00"}}
    monkeypatch.setattr(MM, "durum", lambda: dict(kayit["d"]))
    monkeypatch.setattr(MM, "_durum_yaz", lambda d: kayit.__setitem__("d", dict(d)))
    monkeypatch.setattr(MM, "son_aktarim", lambda: "2026-10-22T11:00")
    monkeypatch.setattr(SE, "aktarim_suruyor", lambda: False)
    monkeypatch.setattr(MM, "plan_hazirla", lambda: {})

    def _uygula(_plan):
        d = MM.durum()
        d["bagli_bankalar"] = [3, 4, 5]
        MM._durum_yaz(d)
        return {"banka": 0}
    monkeypatch.setattr(MM, "uygula", _uygula)
    MM.otomatik()
    assert kayit["d"]["bagli_bankalar"] == [3, 4, 5]            # eski kod: anahtar yok (silinmiş)
    assert kayit["d"]["son_calisma"] == "2026-10-22T11:00"


# ── Banka bakiyeleri: düğme yok, hesap penceresinde yalnız Mikro hareketleri ──
def test_banka_basliginda_dugme_yok_mikro_acikken():
    s = _oku("kayranacc/main.py")
    i = s.index("def _sayfa_banka_bakiyeleri(")
    blok = s[i:i + 2500]
    assert "_elle_yok = elle_giris_kapali()" in blok and "eylemler=[] if _elle_yok else [" in blok
    b = _oku("kayranacc/banka_ekran.py")
    j = b.index("def _banka_dialog(")
    assert "if elle_giris_kapali():\n        _mikro_hareketleri(b, pb)" in b[j:j + 900]


def test_elle_giris_kapali_muhasebe_eslemesine_bakar(monkeypatch):
    from kayranacc import banka_ekran as BE, mikro_muhasebe as MM
    monkeypatch.setattr(MM, "acik_mi", lambda: True)
    assert BE.elle_giris_kapali()
    monkeypatch.setattr(MM, "acik_mi", lambda: False)
    assert not BE.elle_giris_kapali()


# ── Listeler: Mikro kaynaklıysa yalnız okuma işlemleri ──────────────
def test_yalniz_okuma_ve_gecmis_ekranlari():
    from kayranacc import muhasebe_masalari as M
    v = M.haftalar_verisi([{"id": 1, "hafta_adi": "H1"}], {1: {}}, 1)
    assert [i["k"] for i in M.yalniz_okuma(v, True)["islemler"]] == ["ac"]     # aktif yap / sil yok
    assert len(M.yalniz_okuma(v, False)["islemler"]) == 3
    g = _oku("kayranacc/gecmis_ekran.py")
    assert "_mikro_odeme()), \"gec_odenen_masasi\"" in g
    assert "MM.yalniz_okuma(MM.cek_arsivi_verisi(" in g and "not _mikro_cek()" in g
    assert "if st.session_state.get(\"salt_okur\") or _mikro_odeme():" in g
    assert "elle_giris_kapali()), \"gelen_masasi\"" in _oku("kayranacc/gelen_ekran.py")


def test_ertelenende_mikro_satirinda_ode_yok():
    from kayranacc import muhasebe_masalari as M
    from kayranacc.mikro_odeme_oto import mikro_idleri_tum
    odm = [dict(id=7, firma="UPS", vade="2026-10-20", orijinal_vade="2026-10-13", tutar_tl=1000, tutar_usd=0,
                kategori="cari", durum="bekliyor", ertelendi_sayisi=1)]
    banka = [{"id": 1, "hesap_adi": "YKB TL", "para_birimi": "TL", "bakiye": 5000}]
    v = M.ertelenen_verisi(odm, banka, {"cari": {"label": "Cari"}}, 49.6, date(2026, 10, 22), mikro_idler={7})
    assert v["satirlar"][0]["mikro"]
    ode = next(i for i in v["islemler"] if i["k"] == "ode")
    assert ["mikro", "ne", True] in ode["f"]                              # eski kod: Mikro satırında Öde açıktı
    d = {"haftalar": {"12": {"esleme": {"a": {"id": 7}}}, "13": {"esleme": {"b": {"id": "9"}}}}}
    assert mikro_idleri_tum(d) == {7, 9}


# ── Satış: Mikro iadesinde "İadeyi sil" yok ─────────────────────────
def test_mikro_iadesinde_sil_yok():
    from satis.satis_masasi import iade_masa_verisi
    k = [{"id": 1, "tarih": "2026-10-10", "kaynak": "mikro", "sku": "X", "iade_adet": 1, "iade_net": 10},
         {"id": 2, "tarih": "2026-10-10", "kaynak": "elle", "sku": "Y", "iade_adet": 1, "iade_net": 10},
         {"id": 3, "tarih": "2025-03-01", "kaynak": "mikro", "sku": "Z", "iade_adet": 1, "iade_net": 10}]
    v = iade_masa_verisi(k, esitleme=(True, "2026-01-01"))
    m = {s["id"]: s["mikro"] for s in v["satirlar"]}
    assert m == {1: True, 2: False, 3: False}
    assert ["mikro", "ne", True] in v["islemler"][0]["f"]


# ── İthalat: Mikro'ya bağlı dosyada teslim / depo ata yok ───────────
def test_ithalat_mikro_bagli_dosya():
    from ithalat.ithalat_masasi import masa_verisi
    d = [{"id": 1, "mikro_kodu": "ITH26-5", "durum": "Yolda", "tarih": "2026-09-01"},
         {"id": 2, "mikro_kodu": "", "durum": "Yolda", "tarih": "2026-09-02"}]
    h = {"net_mal_bedeli": 100, "toplam_masraf": 5, "maliyet_yuzde": 5, "kalem_sayisi": 1}
    v = masa_verisi(d, {x["id"]: (x, [], h) for x in d}, date(2026, 10, 22), depolar=[], mikro_acik=True)
    m = {s["id"]: s["mikro"] for s in v["satirlar"]}
    assert m == {1: True, 2: False}
    isl = {i["k"]: i for i in v["islemler"]}
    assert ["mikro", "ne", True] in isl["teslim"]["f"] and ["mikro", "ne", True] in isl["depo"]["f"]
    s = _oku("ithalat/main.py")
    assert "if not _mikro_d and st.button(\"Bu ithalatı sil\"" in s
    assert "elif st.toggle(\"✏️ Düzenle — masraf kalemleri · ürün · adet · FOB\"" in s
    assert "and not _mikro_bagli(d)]" in s


# ── Palet, ürün kartı, yurt içi, teknik servis ──────────────────────
def test_palet_mikro_kisayollari_gizler(monkeypatch):
    from shared import gezinme as G
    monkeypatch.setattr(G, "_mikro_kapali_islemler", lambda: {"satis/giris", "depo/sevk"})
    og = G.palet_ogeleri({"satis": True, "depo": True}, set(), "x", lambda *_: True)
    ids = {o["id"] for o in og if o["tur"] == "islem"}
    assert "satis/giris" not in ids and "depo/sevk" not in ids
    monkeypatch.setattr(G, "_mikro_kapali_islemler", lambda: set())
    ids = {o["id"] for o in G.palet_ogeleri({"satis": True, "depo": True}, set(), "x", lambda *_: True)
           if o["tur"] == "islem"}
    assert {"satis/giris", "depo/sevk"} <= ids


def test_kart_sil_yurtici_stok_ts_iade_fiyati():
    k = _oku("kayranpm/main.py")
    assert "if mikro_karti_mi(_sec_sku):" in k and "def mikro_karti_mi(sku):" in k
    y = _oku("kayranpm/yurtici_ekran.py")
    assert 'if mikro_kapsar("g5f_sayim"):' in y and "stok = H.STOK_VAR" in y
    t = _oku("teknikservis/main.py")
    i = t.index('if _iade_mikro or kayit.get("mikro_iade_anahtar"):')
    assert 'with st.popover("İade faturası fiyatını gir / düzelt"' in t[i:i + 400]


# ── İkinci tur (22.10.2026): "Yurt içi alış tamamen kaldırılsın; Ref No'daki alınan destek 'Yeni kayıt'
#    kaldırılsın; teknik servis toplu satış formu kalksın." ─────────
def test_yurtici_alis_menuden_kalkti():
    from shared.gezinme import hedef, secenekler
    assert "💵  Yurt İçi Alış" not in secenekler("kayranpm") and not hedef("kayranpm/maliyet")
    assert '"💵  Yurt İçi Alış"' not in _oku("kayranpm/main.py")


def test_alinan_destek_yeni_kayit_yok():
    r = _oku("kayranpm/ref_ekran.py")
    assert 'key="ad2_yeni"' not in r and r.count("_ad_yeni_dialog(") == 1          # yalnız tanım, çağıran yok


def test_ts_toplu_satis_yok():
    from teknikservis import ts_masasi as M
    v = M.depo_masa_verisi([], [], [], date(2026, 10, 22), lambda k: "")
    assert "sat" not in {i["k"] for i in v["islemler"]}
    t = _oku("teknikservis/main.py")
    assert "_toplu_satis_formu(_satilabilir, st.rerun)" not in t and "_dlg_toplu_satis([" not in t
