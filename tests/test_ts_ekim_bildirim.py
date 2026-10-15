# -*- coding: utf-8 -*-
"""Teknik servis bildirimi (Ekim 2026, Berkay): ürün grubu tekrarları, merkezdeki ürünün satış düğmeleri,
depo adları, değişim / iade belgesi."""
import sys
from datetime import date
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from teknikservis import ts_masasi as M  # noqa: E402
from teknikservis import ts_hesap as H  # noqa: E402
from teknikservis.stok import ts_depo_ad  # noqa: E402


def satis_disi_neden(k):
    """Eski kodda kural yoktu: her kayıt (satılmamışsa) satılabilir sayılıyordu."""
    f = getattr(H, "satis_disi_neden", None)
    return f(k) if f else ("satıldı" if k.get("mevcut_durum") == "satıldı" else "")


def _masa(satir, **kw):
    try:
        return M.depo_masa_verisi(satir, satir, DEPOLAR, BUGUN, lambda k: "Depoya transfer", **kw)
    except TypeError:                     # eski imza: grup_ad / depo_ad yok
        return M.depo_masa_verisi(satir, satir, DEPOLAR, BUGUN, lambda k: "Depoya transfer")

BUGUN = date(2026, 10, 15)
DEPOLAR = ["teknik servis", "iade", "outlet", "ikinci el", "hurda", "merkez"]


def _k(i, durum, **x):
    d = {"id": i, "servis_form_no": f"G5F{i:05d}", "arayuz": "teknik", "stok_kodu": f"SK{i}", "stok_adi": f"Ürün {i}",
         "seri_no": f"SN{i}", "firma_bilgisi": "SON KULLANICI", "mevcut_durum": durum,
         "mal_kabul_tarihi": "2026-10-01T10:00:00", "depo_tarihi": "2026-10-12T10:00:00", "fatura_mevcut": True}
    d.update(x)
    return d


# ── 1. Ürün grubu: 'Kasa' / 'kasa' tek seçenek ───────────────────────
@pytest.fixture()
def ts_db(monkeypatch):
    from teknikservis import database as D
    import shared.ana_veri as A
    kayit = [{"urun_grubu": g} for g in ("kasa", "Kasa", "monitör", "Monitör", "Ekran Kartı", "ekran kartı",
                                         "depolama", "Depolama", "cpu soğutucu", "", None)]
    monkeypatch.setattr(D, "get_kayitlar", lambda *a, **k: kayit)
    monkeypatch.setattr(A, "_kategori_kaynaklari", lambda: (["MONİTÖR", "Kasa"], []))
    monkeypatch.setattr(A, "_kural_kategoriler", lambda: ["Monitör", "Kasa", "Ekran Kartı"], raising=False)
    return D


def test_urun_grubu_secenekleri_tekil(ts_db):
    """Canlıda 14 yazım vardı: 'Kasa' 168 + 'kasa' 152, 'Monitör' 277 + 'monitör' 128 ... (15.10.2026)."""
    g = ts_db.ts_urun_gruplari()
    assert hasattr(ts_db, "ts_grup_haritasi"), f"tek yazım haritası yok; seçenekler: {g}"
    from shared.ana_veri import kategori_anahtar
    anahtarlar = [kategori_anahtar(x) for x in g]
    assert len(anahtarlar) == len(set(anahtarlar)), g
    assert "Kasa" in g and "kasa" not in g and "Monitör" in g and "monitör" not in g
    assert "Ekran Kartı" in g and "ekran kartı" not in g
    h = ts_db.ts_grup_haritasi()
    assert ts_db.ts_grup_ad("kasa", h) == "Kasa" and ts_db.ts_grup_ad("MONITÖR", h) == "Monitör"
    assert ts_db.ts_grup_ad("", h) == "" and ts_db.ts_grup_ad(None, h) == ""
    assert set(ts_db.ts_grup_ad(x, h) for x in g) == set(g)          # seçenek = görünen ad


def test_serbest_yeni_grup_kutusu_yok():
    s = (KOK / "teknikservis" / "main.py").read_text(encoding="utf-8")
    assert "Ürün grubu listede yoksa yaz (yeni grup)" not in s     # mal kabul
    assert "➕ Yeni grup…" not in s                                 # evraksız ürün kayıt


def test_depolar_grup_suzgeci_tek_secenek():
    satir = [_k(1, "satışa hazır", depo="outlet", urun_grubu="kasa"),
             _k(2, "satışa hazır", depo="outlet", urun_grubu="Kasa"),
             _k(3, "satışa hazır", depo="outlet", urun_grubu="monitör")]
    harita = {"kasa": "Kasa", "monitor": "Monitör"}
    v = _masa(satir, grup_ad=lambda g: harita.get(g.lower().replace("ö", "o"), g))
    sec = next(s for s in v["secimler"] if s["alan"] == "grup")["secenekler"]
    assert [x["k"] for x in sec] == ["Kasa", "Monitör"]
    assert {x["id"]: x["grup"] for x in v["satirlar"]} == {1: "Kasa", 2: "Kasa", 3: "Monitör"}


# ── 2. Merkez deposundaki ürün Depolar'dan satılmaz ───────────────────
def test_satis_disi_neden():
    assert satis_disi_neden(_k(1, "gönderildi", depo="merkez"))           # G5F00148: merkez + gönderildi
    assert satis_disi_neden(_k(2, "satışa hazır", depo="merkez"))
    assert satis_disi_neden(_k(3, "satıldı", depo="outlet")) == "satıldı"
    assert satis_disi_neden(_k(4, "gönderildi", depo="outlet"))
    assert satis_disi_neden(_k(5, "satışa hazır", depo="outlet")) == ""
    assert satis_disi_neden(_k(6, "iade alındı", depo="teknik servis")) == ""   # G5F00801: değişmedi


def test_merkezdeki_urun_toplu_satista_yok():
    satir = [_k(1, "gönderildi", depo="merkez"), _k(2, "satışa hazır", depo="outlet")]
    v = _masa(satir)
    assert {x["id"]: x["satilabilir"] for x in v["satirlar"]} == {1: False, 2: True}


def test_ayrintida_dugmeler_kapali_kurala_bagli():
    s = (KOK / "teknikservis" / "main.py").read_text(encoding="utf-8")
    d = s[s.index("def _depo_detay(k):"):s.index("        with st.container(border=True):", s.index("def _depo_detay(k):"))]
    assert "_kapali = satis_disi_neden(k)" in d
    assert d.count("if not _kapali:") == 2 and "if not satildi:" not in d       # Satışa Hazır + Satıldı
    assert "_dlg_toplu_satis([k for k in goster if not satis_disi_neden(k)])" in s
    assert '_satilabilir = [k for k in goster if not satis_disi_neden(k)]' in s


# ── 3. Depo adları Depo modülündeki gibi ─────────────────────────────
def test_depo_adlari_depo_modulu_ile_ayni():
    assert [ts_depo_ad(d) for d in DEPOLAR] == ["TEKNİK DEPO", "İADE DEPO", "OUTLET DEPO", "İKİNCİ EL DEPO",
                                                 "HURDA DEPO", "MERKEZ DEPO"]
    satir = [_k(1, "gönderildi", depo="merkez"), _k(2, "satışa hazır", depo="outlet")]
    v = _masa(satir, depo_ad=ts_depo_ad)
    assert {x["id"]: x["depo_ad"] for x in v["satirlar"]} == {1: "MERKEZ DEPO", 2: "OUTLET DEPO"}
    s = (KOK / "teknikservis" / "main.py").read_text(encoding="utf-8")
    assert 'placeholder="Bütün depolar", format_func=_stok.ts_depo_ad' in s


# ── 4. Değişim / İade Belgesi ─────────────────────────────────────────
def _iade_modulu():
    import importlib.util
    assert importlib.util.find_spec("teknikservis.iade_belge"), "değişim / iade belgesi üretilmiyordu"


def test_iade_belgesi_uygunluk_ve_onay_tarihi():
    _iade_modulu()
    from teknikservis.iade_belge import iade_belgesi_uygun, iade_onay_tarihi
    assert iade_belgesi_uygun({"mevcut_durum": "iade alındı"})
    assert iade_belgesi_uygun({"mevcut_durum": "gönderildi", "ariza_sonucu": "iade alındı"})
    assert not iade_belgesi_uygun({"mevcut_durum": "satışa hazır"})
    gecmis = [{"durum": "teknisyende", "tarih": "2026-10-10T09:00:00"},
              {"durum": "iade alındı", "tarih": "2026-10-12T11:00:00"},
              {"durum": "iade alındı", "tarih": "2026-10-13T11:00:00"}]
    assert iade_onay_tarihi({}, gecmis) == date(2026, 10, 12)               # ilk iade satırı
    assert iade_onay_tarihi({"depo_tarihi": "2026-10-09T08:00:00"}, []) == date(2026, 10, 9)


def test_iade_belgesi_metni():
    _iade_modulu()
    from teknikservis.iade_belge import belge_metni, GECERLILIK_GUN
    k = _k(801, "iade alındı", stok_kodu="X24F241S", stok_adi="FAZEON X24F241S 24\" 240Hz",
           seri_no="M2512M02539", musteri_adi="Zeki Öksüz", musteri_tel="0532 000 00 00", ariza="panel hasarlı")
    m = belge_metni(k, {"unvan": "G5F TEKNOLOJİ A.Ş.", "tel": "0212 000 00 00"}, date(2026, 10, 12), BUGUN)
    assert m["baslik"] == "DEĞİŞİM / İADE BELGESİ"
    assert dict(m["ust"]) == {"Referans No": "G5F00801", "Belge Tarihi": "15.10.2026",
                              "İade Onay Tarihi": "12.10.2026"}
    u = dict(m["urun"])
    assert u["İthalatçı Firma"] == "G5F TEKNOLOJİ A.Ş." and u["Seri No"] == "M2512M02539"
    assert u["Ürün Modeli"].startswith("X24F241S — FAZEON") and u["Tüketici Adı"] == "Zeki Öksüz"
    assert str(GECERLILIK_GUN) in m["gecerlilik"] and "(0212 000 00 00)" in m["dikkat"][0]
    assert m["imza"] == ["G5F TEKNOLOJİ A.Ş.", "Teknik Servis"]


def test_iade_belgesi_pdf_uretilir():
    pytest.importorskip("reportlab")
    _iade_modulu()
    from teknikservis.iade_belge import iade_belgesi_pdf
    b = iade_belgesi_pdf(_k(801, "iade alındı", musteri_adi="Zeki Öksüz"),
                         [{"durum": "iade alındı", "tarih": "2026-10-12T11:00:00"}],
                         sirket={"unvan": "G5F TEKNOLOJİ A.Ş."}, bugun=BUGUN)
    assert b[:4] == b"%PDF" and len(b) > 1500


def test_iade_belgesi_dugmesi_iki_ayrintida():
    s = (KOK / "teknikservis" / "main.py").read_text(encoding="utf-8")
    assert '_iade_belgesi_dugmesi(kayit, get_gecmis(kid), f"ts_iade_belge_{kid}")' in s     # teknik servis
    assert '_iade_belgesi_dugmesi(k, _gec, f"depo_iade_belge_{kid}")' in s                 # depolar


# ════ Mailin tamamı (15 madde, 15.10.2026) ════════════════════════════
def _main():
    return (KOK / "teknikservis" / "main.py").read_text(encoding="utf-8")


# 1. İrsaliye sayfası kalktı (irsaliyeler Mikro'dan)
def test_irsaliye_sayfasi_yok():
    g = (KOK / "shared" / "gezinme.py").read_text(encoding="utf-8")
    assert '("🚚  İrsaliye", "irsaliye"' not in g
    assert "def _irsaliye():" not in _main() and '"🚚  İrsaliye"' not in _main()


# 2. Tek arama + takip no / isim
def test_tek_arama_takip_no_isim_ariza():
    kayit = [_k(1, "teknisyende", gelis_kargo_no="KRG123456", musteri_adi="İSMAİL ŞİMŞEK"),
             _k(2, "iade alındı", arayuz="iade", gidis_kargo_no="YK998877", ariza="ekran titriyor"),
             _k(3, "satışa hazır", depo="outlet", musteri_adi="Zeki Öksüz", sevk_kargo_bilgisi="Takip No: 55501")]
    ara = lambda q: [(y, k["id"]) for y, k in getattr(M, "tek_arama", lambda *a: [])(kayit, q, {3})]  # noqa: E731
    assert ara("KRG123456") == [("teknik", 1)]                       # geliş takip no
    assert ara("yk998877") == [("iade", 2)]                          # gidiş takip no, küçük harf
    assert ara("ismail şimşek") == [("teknik", 1)] and ara("ISMAIL") == [("teknik", 1)]   # İ / I / i
    assert ara("titriyor") == [("iade", 2)]                          # müşteri şikâyeti (arıza)
    assert ara("öksüz") == [("depo", 3)] and ara("55501") == [("depo", 3)]
    assert ara("x") == []                                             # en az 2 harf


def test_liste_aramalarinda_takip_no_ve_musteri():
    for alan in ("gelis_kargo_no", "gidis_kargo_no", "ariza", "musteri_adi", "seri_no", "irsaliye_no", "fatura_no"):
        assert alan in M.TS_ARA_ALANLARI and alan in M.DEPO_ARA_ALANLARI, alan
    assert M.ara_uyar({"musteri_adi": "İSMAİL"}, "ismail", ["musteri_adi"])
    js = (KOK / "shared" / "masa.py").read_text(encoding="utf-8")
    assert 'const katla = s => kucuk(s).replace(/ı/g, "i")' in js
    assert "_tek_arama()" in _main() and _main().count("    _tek_arama()") == 2      # TS/İade + Depolar


# 3 · 7. Pazarlama ve yedek parça depoları
def test_pazarlama_ve_yedek_parca_depolari():
    from teknikservis.database import DEPOLAR as D
    assert "pazarlama" in D and "yedek parça" in D
    assert ts_depo_ad("pazarlama") == "PAZARLAMA" and ts_depo_ad("yedek parça") == "YEDEK PARÇA DEPO"
    from kayranpm.database import depo_kanonik
    assert depo_kanonik("Yedek Parça") == "YEDEK PARÇA DEPO" and depo_kanonik("pazarlama deposu") == "PAZARLAMA"


# 5b. İthalat modeli seçilince ürün grubu açılır listeye de gelir
def test_model_secince_grup_listeye_gelir():
    s = _main()
    assert 'st.session_state["mk_grup_sec"] = ts_grup_ad(_grp_oto)' in s
    assert 'st.session_state["ev_grup_sec"] = ts_grup_ad(_g_ev)' in s


# 6. Merkezdeki ürün: 'merkeze aktarıldı', düzeltme / silme yok
def test_merkez_gorunen_durum_ve_kilit():
    gd = getattr(H, "gorunen_durum", lambda k: k.get("mevcut_durum"))
    assert gd(_k(1, "satışa hazır", depo="merkez")) == "merkeze aktarıldı"    # canlıda 5 kayıt böyle
    assert gd(_k(2, "gönderildi", depo="merkez")) == "merkeze aktarıldı"
    assert gd(_k(3, "satışa hazır", depo="outlet")) == "satışa hazır"
    v = _masa([_k(1, "satışa hazır", depo="merkez")])
    assert v["satirlar"][0]["durum"] == "merkeze aktarıldı" and v["satirlar"][0]["hazir"] == 0
    s = _main()
    d = s[s.index("def _depo_detay(k):"):s.index("def run():")]
    assert d.index("if merkezde_mi(k):") < d.index('popover("✏️ Kaydı Düzelt"')


# 8. 'DİĞER' firmada mağaza / müşteri adı zorunlu değil
def test_diger_firmada_magaza_zorunlu_degil():
    s = _main()
    assert 'if not m_adi.strip() and not _diger_firma(_firma_kayit):' in s
    from shared.ana_veri import kategori_anahtar
    assert {kategori_anahtar(x) for x in ("DİĞER", "Diğer", "DIGER")} <= {"diğer", "diger"}


# 9. Evraksız kayıtta depoya göre ilk durum
def test_evraksiz_ilk_durum():
    import teknikservis.database as D
    e = getattr(D, "EVRAKSIZ_DURUM", {"outlet": "satışa hazır", "ikinci el": "satışa hazır", "hurda": "hurda"})
    assert e["outlet"] == e["ikinci el"] == "satışa hazır"
    assert e.get("teknik servis") == e.get("iade") == e.get("hurda") == "teknisyende"


# 10. Ürün notları
def test_urun_notlari():
    import importlib.util
    assert importlib.util.find_spec("teknikservis.urun_notlari"), "ürün notları sayfası yoktu"
    from teknikservis.urun_notlari import not_satiri, notlari_sirala
    assert not_satiri("", "", "Tasarım", "logo", "berkay") == (None, "Önce ürünü (ithalat modeli) seç.")
    assert not_satiri("F21E650BBM", "F21", "Tasarım", "  ", "berkay")[0] is None
    s, h = not_satiri("F21E650BBM", "F21 kasa", "Tasarım", "Manyetik logo ön panelde estetiksiz", "berkay")
    assert h == "" and s["stok_kodu"] == "F21E650BBM" and s["yazan"] == "berkay"
    n = [{"stok_kodu": "F21E650BBM", "olusturma": "2026-10-10"}, {"stok_kodu": "X34F180QP", "olusturma": "2026-10-12"},
         {"stok_kodu": "f21e650bbm", "olusturma": "2026-10-14"}]
    assert [x["olusturma"] for x in notlari_sirala(n, "F21E650BBM")] == ["2026-10-14", "2026-10-10"]
    assert (KOK / "veritabani" / "36_ts_urun_notlari.sql").exists()


# 11 · 14. Servis formu: ad, tek sayfa, 'iade alındı', 'Arıza / Şikâyet'
def test_servis_formu_iade_alindi_ve_ad():
    import teknikservis.database as D
    assert hasattr(D, "form_durumu"), "formda son durum 'iade alındı' gösterilmiyordu"
    g = [{"durum": "mal kabül", "tarih": "2026-10-10"}, {"durum": "iade alındı", "tarih": "2026-10-12"},
         {"durum": "satışa hazır", "tarih": "2026-10-13", "aciklama": "outlet deposuna transfer"},
         {"durum": "satıldı", "tarih": "2026-10-14"}]
    durum, gec = D.form_durumu({"mevcut_durum": "satıldı"}, g)
    assert durum == "iade alındı" and [h["durum"] for h in gec] == ["mal kabül", "iade alındı"]
    assert D.form_durumu({"mevcut_durum": "teknisyende"}, g[:1])[0] == "teknisyende"
    assert _main().count('st.download_button("Servis Formu indir"') == 2 and "PDF Form indir" not in _main()
    assert '("Arıza / Şikâyet", _v("ariza"))' in (KOK / "teknikservis" / "database.py").read_text(encoding="utf-8")


def test_servis_formu_tek_sayfa():
    pytest.importorskip("reportlab")
    import teknikservis.database as D
    k = _k(801, "satıldı", stok_adi="FAZEON X24F241S 24\" 240Hz 0.5ms FAST IPS FHD HDMI*1 +DP*1 RGB GAMING MONITOR",
           ariza="panel hasarlı, sol alt köşede çizgiler ve yanık piksel", icerik_durumu="Kutu orijinal",
           fiziksel_durum="hafif çizik", detay="3 gün kullanılmış", musteri_tel="0532", musteri_mail="a@b.c",
           musteri_adres="Ümraniye / İstanbul", sevk_kargo_bilgisi="Kargo", fatura_no="F1", gelis_kargo_no="K1")
    g = [{"durum": d, "tarih": f"2026-10-1{i}T10:00", "aciklama": "x" * 60, "personel": "berkay"}
         for i, d in enumerate(["mal kabül", "teknisyende", "iade alındı", "satışa hazır", "satıldı"])]
    import re
    b = D.servis_formu_pdf(k, g)
    assert len(re.findall(rb"/Type\s*/Page[^s]", b)) == 1        # imza 2. sayfaya kalıyordu


# 12 · 13. Seri no: stok kartı değiştir ve evraksız kayıtta 'seri no yok'
def test_seri_no_alanlari():
    s = _main()
    d = s[s.index("def _dlg_ts_stok_degis():"):s.index('if st.button("Stok Kartı Değiştir (ürün dönüştürüldü)"')]
    assert 'key=f"sd_sn_{kid}"' in d and 'key=f"sd_snyok_{kid}"' in d and '_alanlar["seri_no"] = _sn' in d
    e = s[s.index("def _evraksiz_kayit"):s.index("def _evraksiz_kayit") + 9000]
    assert 'key="ev_seri_yok"' in e and "_seri = SERI_YOK if _ev_seri_yok else" in e


# 15. Değişim ürünü Depolar'dan: kayıt bedelsiz satıldı + kendi deposundan düşer, MERKEZ'den değil
def test_degisim_depolardan(monkeypatch):
    import teknikservis.stok as S
    assert hasattr(S, "degisim_depodan_ver"), "değişim ürünü Depolar kaydına bağlanmıyordu"
    olay = []
    monkeypatch.setattr(S, "satis_cikisi", lambda k: (olay.append(("cikis", S.ts_depo_ad(k["depo"]))) or (True, "ok")))
    monkeypatch.setattr(S, "satis_kaydi_yaz", lambda k, f, **kw: (olay.append(("satis", f, kw)) or (True, "ok")))
    monkeypatch.setattr(S, "degisim_cikisi", lambda k: (olay.append(("MERKEZ",)) or (True, "ok")))
    dg = []
    sonuc = S.degisim_depodan_ver(_k(756, "iade alındı"), _k(477, "satışa hazır", depo="ikinci el"), "berkay",
                                  lambda *a: dg.append(a) or True, bugun=BUGUN)
    assert all(ok for ok, _ in sonuc)
    assert dg[0][0:2] == (477, "satıldı") and dg[0][4]["satis_firma"] == "S.K. Değişim (G5F00756)"
    assert dg[0][4]["bedelsiz"] is True and dg[0][4]["satis_tarihi"] == "2026-10-15"
    assert olay == [("cikis", "İKİNCİ EL DEPO"),
                    ("satis", 0, {"bedelsiz": True, "cari": "S.K. Değişim (G5F00756)"})]   # MERKEZ yok
    s = _main()
    assert "_stok.degisim_depodan_ver(kayit, _dg_bagli" in s
    assert 'elif yeni_durum == "ürün değişimi" and _onceki != "ürün değişimi":' in s
