# -*- coding: utf-8 -*-
"""Mikro → satışlar / iadeler otomatik eşitleme (satis/mikro_esitle.py, Ekim 2026).

Kullanıcı: "Bundan sonra tüm satışlar, iadeler API'den otomatik güncel gelsin." Karar: 01.07.2026'dan
itibaren tek kaynak Mikro faturaları. Rakamlar canlı veriyle doğrulandı: Haziran faturası G5F26-1788
(3 × X27F241S) KDV dahil 450 $ = 3 × 125 × 1,20; uygulamadaki birim fiyat 125 $ (KDV hariç)."""
from pathlib import Path

import pytest

M = pytest.importorskip("satis.mikro_esitle")
KOK = Path(__file__).resolve().parent.parent


def _s(no_sira, sku, adet, tutar, kur=46.0, tarih="2026-09-16", cari="120.01.003",
       unvan="VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI", tip=63, iade=0, isk=0.0, doviz=1, alt=0,
       depo="İADE DEPO"):
    return {"sth_guid": f"g-{no_sira}-{sku}-{adet}", "cha_evrak_tip": tip, "cha_normal_iade": iade,
            "cha_evrakno_seri": "G5F26", "cha_evrakno_sira": no_sira, "cha_tarihi": tarih + " 00:00:00",
            "cha_d_cins": doviz, "cha_d_kur": kur if doviz == 1 else 1, "sth_alt_doviz_kuru": alt,
            "sth_stok_kod": sku, "sto_isim": f"{sku} adı", "sth_cari_kodu": cari, "cari_unvan1": unvan,
            "sth_miktar": adet, "sth_tutar": tutar, "sth_iskonto": isk, "giris_depo_adi": depo}


VATAN = "VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI"


def test_fatura_no_eski_excel_bicimi():
    assert M.fatura_no("G5F26", 2525) == "G5F26-2525"
    assert M.fatura_no("G5F26", "1788.0") == "G5F26-1788"


def test_kur_ve_net_fiyat():
    """Mikro satır tutarı FATURANIN DÖVİZİNDE (canlı veri, Ekim 2026: Ocak–Haziran'daki 1.501 $ faturanın hepsi
    eski Excel kaydıyla birebir). $ faturada (tutar − iskonto) / adet; TL faturada o günün $ faturalarının
    kuruyla (yoksa en yakın önceki gün)."""
    k = M.mikro_kayitlari([_s(1788, "X27F241S", 3, 375, kur=46.0857, tarih="2026-07-15")])
    r = k["satis"]["G5F26-1788"][0]
    assert r["birim_satis"] == pytest.approx(125.0) and r["adet"] == 3 and r["kanal"] == VATAN
    assert r["siparis_no"] == "G5F26-1788" and r["tarih"] == "2026-07-15"
    # TL fatura: aynı günün $ faturasının kuru (46), iskonto düşülür
    k2 = M.mikro_kayitlari([_s(5, "A", 2, 1000, isk=80, doviz=0, tarih="2026-09-16"),
                            _s(4, "B", 1, 10, kur=46.0, tarih="2026-09-16")])
    assert k2["satis"]["G5F26-5"][0]["birim_satis"] == pytest.approx(920 / 46 / 2, abs=1e-4)
    # o gün $ fatura yoksa en yakın önceki gün; hiç yoksa alınmaz
    k3 = M.mikro_kayitlari([_s(6, "A", 1, 480, doviz=0, tarih="2026-09-20"), _s(4, "B", 1, 10, kur=48.0)])
    assert k3["satis"]["G5F26-6"][0]["birim_satis"] == pytest.approx(10.0)
    k4 = M.mikro_kayitlari([_s(6, "A", 1, 1000, doviz=0, alt=1)])
    assert not k4["satis"] and k4["atlanan"]["kursuz"] == 1
    # SKU kart yazımına (Excel içe aktarmayla aynı kural)
    k5 = M.mikro_kayitlari([_s(7, "Fazeon X24F200", 6, 90)])
    assert k5["satis"]["G5F26-7"][0]["sku"] == "X24F200" and k5["satis"]["G5F26-7"][0]["birim_satis"] == 15


def test_bedelsiz_alis_iadesi_ve_eski_tarih_alinmaz():
    k = M.mikro_kayitlari([
        _s(7, "A", 1, 0),                                  # bedelsiz değişim (teknik servis yazıyor)
        _s(8, "B", 1, 500, tip=63, iade=1),                # alış iadesi
        _s(9, "C", 1, 500, tarih="2026-06-30"),            # başlangıçtan önce
    ])
    assert not k["satis"] and not k["iade"] and k["atlanan"] == {"bedelsiz": 1}


def test_satis_iadesi_iadelere_gider():
    k = M.mikro_kayitlari([_s(31, "X24F200", 1, 120, tip=0, iade=1, cari="120.02.005", unvan="EERA",
                              tarih="2026-08-01")])
    r = k["iade"]["G5F26-31"][0]
    assert r["kanal"] == "120.02.005 EERA" and r["iade_adet"] == 1 and r["iade_net"] == pytest.approx(120)
    assert r["belge_no"] == "G5F26-31" and r["donem_bas"] == r["donem_bit"] == "2026-08-01"
    assert k["iade_cari"] == {"120.02.005"}


def _sat(id_, tarih, kanal, sku, adet, fiyat, maliyet, no, notlar=""):
    return {"id": id_, "tarih": tarih, "kanal": kanal, "sku": sku, "adet": adet, "birim_satis": fiyat,
            "birim_maliyet": maliyet, "siparis_no": no, "notlar": notlar}


def test_siparis_excel_satirlari_fatura_tarihine_kadar_degisir():
    mikro = [_s(2525, "X27F241S", 3, 375, tarih="2026-09-16")]
    satislar = [
        _sat(1, "2026-09-10", VATAN, "X27F241S", 3, 125, 85, "151"),       # faturalı firma, faturadan önce → değişir
        _sat(2, "2026-09-20", VATAN, "X27F241S", 2, 125, 85, "160"),       # son faturadan SONRA → kalır (faturası gelmedi)
        _sat(3, "2026-09-12", "Sk Değişim (G5F00756)", "X27F241S", 1, 0, 80, "G5F00477",
             "TEKNİK SERVİS / 2.EL · G5F00477"),                              # teknik servis → kalır
        _sat(4, "2026-09-11", "BAŞKA FİRMA", "Y", 1, 10, 5, "x"),          # Mikro'da faturası olmayan firma → kalır
    ]
    p = M.plan_yap(mikro, satislar, [], pacal_fn=lambda s: 99.0)
    assert p["yuk"]["sil_satis_id"] == [1]
    yeni = p["yuk"]["ekle_satis"]
    assert len(yeni) == 1 and yeni[0]["siparis_no"] == "G5F26-2525"
    assert yeni[0]["birim_maliyet"] == pytest.approx(85)        # maliyet değiştirilen eski satırdan, paçal değil
    eyl = next(o for o in p["ozet"] if o["ay"] == "2026-09")
    assert eyl["adet_once"] == 7 and eyl["adet_sonra"] == 7
    assert eyl["kar_once"] == pytest.approx(3 * 40 + 2 * 40 + (0 - 80) + 5) == eyl["kar_sonra"]


def test_degismeyen_fatura_yeniden_yazilmaz_degisen_yazilir():
    mikro = [_s(10, "A", 2, 100), _s(11, "B", 1, 70)]
    satislar = [_sat(5, "2026-09-16", VATAN, "A", 2, 50, 30, "G5F26-10", "Mikro · Cari kodu: 120.01.003"),
                _sat(6, "2026-09-16", VATAN, "B", 1, 60, 40, "G5F26-11", "Mikro · Cari kodu: 120.01.003")]
    p = M.plan_yap(mikro, satislar, [], pacal_fn=lambda s: 0.0)
    assert p["yuk"]["fatura_nolar"] == ["G5F26-11"]              # fiyat değişti (60 → 70)
    assert [k["siparis_no"] for k in p["yuk"]["ekle_satis"]] == ["G5F26-11"]
    assert p["yuk"]["ekle_satis"][0]["birim_maliyet"] == pytest.approx(40)   # aynı faturanın önceki maliyeti
    assert p["yuk"]["sil_satis_id"] == []
    p2 = M.plan_yap(mikro[:1], satislar[:1], [], pacal_fn=lambda s: 0.0)
    assert not p2["degisiklik_var"]


def test_iptal_fatura_silinir_satirsiz_fatura_korunur():
    satislar = [_sat(7, "2026-09-16", VATAN, "A", 1, 50, 30, "G5F26-20", "Mikro · Cari kodu: 120.01.003"),
                _sat(8, "2026-09-16", VATAN, "B", 1, 50, 30, "G5F26-21", "Mikro · Cari kodu: 120.01.003")]
    basliklar = [{"fatura_no": "G5F26-21", "tarih": "2026-09-16", "kanal": VATAN, "tutar": 60, "doviz": "$"}]
    p = M.plan_yap([], satislar, [], basliklar=basliklar)
    assert p["yuk"]["fatura_nolar"] == ["G5F26-20"]           # Mikro'da yok → iptal
    assert [b["fatura_no"] for b in p["hizmet_faturalari"]] == ["G5F26-21"]   # satırsız: dokunulmaz, listelenir


def test_excel_iadeleri_mikro_iadeleriyle_degisir():
    mikro = [_s(31, "X24F200", 1, 120, tip=0, iade=1, cari="120.02.005", unvan="EERA", tarih="2026-08-01")]
    iadeler = [{"id": 9, "tarih": "2026-09-30", "kanal": "120.02.005 EERA", "sku": "X24F200", "iade_adet": 1,
                "iade_net": 120, "kaynak": "excel"},
               {"id": 10, "tarih": "2026-09-30", "kanal": "120.09.999 BAŞKA", "sku": "Z", "iade_adet": 1,
                "iade_net": 5, "kaynak": "excel"},
               {"id": 11, "tarih": "2026-09-30", "kanal": "120.02.005 EERA", "sku": "Q", "iade_adet": 1,
                "iade_net": 7, "kaynak": "manuel"}]
    p = M.plan_yap(mikro, [], iadeler)
    assert p["yuk"]["sil_iade_id"] == [9]
    assert [r["belge_no"] for r in p["yuk"]["ekle_iade"]] == ["G5F26-31"]
    p2 = M.plan_yap(mikro, [], [dict(p["yuk"]["ekle_iade"][0], id=12, kaynak="mikro")])
    assert not p2["degisiklik_var"]


def test_aktarici_bos_sonucu_satir_sanmaz(monkeypatch):
    """Ekim 2026 ilk otomatik tur: yeni kayıt yokken Mikro [{"SQLResult1": []}] döndü; aktarıcı sarmalayıcıyı
    satır sanıp yazmaya çalıştı ("Could not find the 'sqlresult1' column")."""
    import importlib.util
    import sys
    import types
    if importlib.util.find_spec("requests") is None:
        sahte = types.ModuleType("requests")
        sahte.Session, sahte.RequestException, sahte.Response = object, Exception, object
        monkeypatch.setitem(sys.modules, "requests", sahte)
    spec = importlib.util.spec_from_file_location("mk_bos_test", KOK / "araclar/mikro_aktarici/mikro_kayran.py")
    mk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mk)
    assert mk._kayitlari_bul([{"SQLResult1": []}]) == []
    assert mk._kayitlari_bul([{"SQLResult1": [{"a": 1}]}]) == [{"a": 1}]
    assert mk._kayitlari_bul({"result": [{"StatusCode": 200, "Data": [{"SQLResult1": []}]}]}) == []
    assert "satis_satir" in getattr(mk, "SORGULAR", {}) and mk.SORGULAR["satis_satir"]["tablo"] == "mikro_satis_satir"


def test_veritabani_fonksiyonu_stoga_dokunmaz_ve_arsivler():
    sql = (KOK / "veritabani/37_mikro_satis.sql").read_text(encoding="utf-8")
    govde = sql.split("CREATE OR REPLACE FUNCTION public.mikro_esitle_uygula", 1)[1].split("$fn$;", 1)[0]
    assert "pg_advisory_xact_lock" in govde and govde.count("INSERT INTO mikro_esitleme_arsiv") == 2
    assert "stok" not in govde.lower().replace("stoğu", "")


def test_aktarici_kod_degisince_yeniden_yayinlanir():
    """#228'den sonra görüldü: kod 'süreç başına bir kez' yayınlanıyordu; Streamlit Cloud birleştirmeden sonra
    süreci yeniden başlatmadığı için yeni aktarıcı sürümü hiç gönderilmedi. Artık dosya özeti değişince yayınlanır."""
    app = (KOK / "app.py").read_text(encoding="utf-8")
    govde = app.split("def _mikro_esitle_dene():", 1)[1].split("\ndef ", 1)[0]
    assert "aktarici_ozeti()" in govde and '_s.get("yayin") != _ozet' in govde
    assert 'if not _s["yayin"]' not in govde
    import hashlib
    kod = (KOK / "araclar/mikro_aktarici/mikro_kayran.py").read_text(encoding="utf-8")
    assert M.aktarici_ozeti() == hashlib.sha256(kod.encode("utf-8")).hexdigest()


# ── Satış eşitlemesi açıkken Dosya kapısındaki satış dökümü / iade Excel'i kaydedilmez (Ekim 2026) ──
class _KayitYolu:
    """Gövde dosyayı okumaya / kaydetmeye kalkarsa test kırmızı olur (kapı kapalı olmalıydı)."""
    name = "dokum.xlsx"

    def __getattr__(self, ad):
        raise AssertionError(f"satış eşitlemesi açıkken dosya işlendi: {ad}")


def _acik_esitleme(monkeypatch):
    import sys
    import types
    sahte = types.ModuleType("satis.mikro_esitle")
    sahte.acik_mi = lambda: True
    monkeypatch.setitem(sys.modules, "satis.mikro_esitle", sahte)


@pytest.mark.parametrize("govde", ["kapi_mikro_fatura", "kapi_iade"])
def test_satis_esitlemesi_acikken_kapi_kaydetmez(monkeypatch, govde):
    SM = pytest.importorskip("satis.main")
    from shared import yukleme_takvimi as Y
    _acik_esitleme(monkeypatch)
    bilgi = []
    monkeypatch.setattr(SM.st, "info", lambda m, *a, **k: bilgi.append(m), raising=False)

    class _Yer:
        def markdown(self, *a, **k):
            return None
    monkeypatch.setattr(SM.st, "empty", lambda: _Yer(), raising=False)
    monkeypatch.setattr(Y, "serit", lambda *a, **k: None)
    assert getattr(SM, govde)(_KayitYolu(), _KayitYolu()) is None
    assert bilgi and "Mikro" in bilgi[0] and "kaydedilmez" in bilgi[0]


def test_satis_esitlemesi_acikken_satis_dokumu_hatirlatmasi_cikmaz(monkeypatch):
    from shared import yukleme_takvimi as Y
    _acik_esitleme(monkeypatch)
    # satis_dokumu varsayılan olarak takip dışı; ayarlardan açılmış olsa bile Mikro varken hatırlatma çıkmaz
    monkeypatch.setattr(Y, "_ayar", lambda anahtar, varsayilan: (
        {"satis_dokumu": {"aktif": True}} if anahtar == Y.AYAR_ANAHTAR else varsayilan))
    monkeypatch.setattr(Y, "_OKUYUCU", {})
    anahtarlar = {d["anahtar"] for d in Y.durumlar()}
    assert "satis_dokumu" not in anahtarlar
    assert "satis_dokumu" in Y._mikro_kapsadigi()
    assert "musteri_haftalik" in anahtarlar          # Mikro'dan gelmeyen kaynak kalır


def test_acik_mi_durumdan(monkeypatch):
    monkeypatch.setattr(M, "durum", lambda: {"acik": True})
    assert M.acik_mi() is True
    monkeypatch.setattr(M, "durum", lambda: None)      # tablo yok / okunamadı → kapalı (yükleme açık kalır)
    assert M.acik_mi() is False
