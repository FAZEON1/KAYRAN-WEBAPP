# -*- coding: utf-8 -*-
"""'KANAL' kaldırıldı — her firma kendi adıyla (Ekim 2026, kullanıcı kararı).

Kurallar (kullanıcı, 3 Ekim):
  1) Yüklemede firma adı Muhasebe cari listesinde eşleşirse CARİ ADIYLA kaydedilir; eşleşmezse
     yükleme durur, hiçbir şey yazılmaz (yazım hatası yeni firma açmasın).
  2) Hangi firmaya ait olduğu belli olmayan eski 'KANAL' kayıtları DİĞER olarak kalır.
  3) MONDAY'in cari adı 'MONDAY BİLİŞİM SANAYİ VE TİCARET ANONİM ŞİRKETİ' (revize; ilk 'TEKNOKLİK - MONDAY').
"""
import pandas as pd
import pytest

CARILER = ["AYKON BİLGİSAYAR LTD. ŞTİ.", "TEKNOSA İÇ VE DIŞ TİC. A.Ş.", "TEKNOSA SERVİS A.Ş.",
           "D-MARKET ELEKTRONİK HİZMETLER VE TİCARET A.Ş."]


# ── Ortak fonksiyonlar (shared.utils) ────────────────────────────────
def test_firma_kanonik_ve_sirala():
    from shared.utils import firma_kanonik, firma_sirala
    assert firma_kanonik("KANAL") == firma_kanonik("kanal ") == firma_kanonik("DİĞER") == "DIGER"
    assert firma_kanonik(" itopya") == "ITOPYA" and firma_kanonik("AYKON  LTD") == "AYKON LTD"
    assert firma_sirala(["DIGER", "Zeta Ltd", "VATAN", "KANAL", "AYKON LTD", "ITOPYA", "MONDAY", "HB"]) == \
        ["ITOPYA", "HB", "VATAN", "MONDAY", "AYKON LTD", "Zeta Ltd", "DIGER"]


def test_gorunen_ad_kanal_yok_monday_teknoklik():
    from shared.utils import firma_gorunen_ad, FIRMA_KODLARI_DIGER
    assert firma_gorunen_ad("KANAL") == firma_gorunen_ad("DIGER") == "DİĞER"
    assert firma_gorunen_ad("MONDAY", kisa=False) == "MONDAY BİLİŞİM SANAYİ VE TİCARET ANONİM ŞİRKETİ"
    assert firma_gorunen_ad("MONDAY") == "MONDAY BİLİŞİM"              # kısa biçim (ünvan ekleri atılır)
    assert "KANAL" not in FIRMA_KODLARI_DIGER
    assert firma_gorunen_ad("AYKON BİLGİSAYAR LTD. ŞTİ.", kisa=False) == "AYKON BİLGİSAYAR LTD. ŞTİ."


def test_cari_eslestir():
    from shared.utils import cari_eslestir
    assert cari_eslestir("aykon bilgisayar ltd. şti.", CARILER) == "AYKON BİLGİSAYAR LTD. ŞTİ."   # birebir
    assert cari_eslestir("AYKON", CARILER) == "AYKON BİLGİSAYAR LTD. ŞTİ."                        # tek aday
    assert cari_eslestir("TEKNOSA", CARILER) is None          # iki cari uyuyor → sorulmalı
    assert cari_eslestir("AYKN", CARILER) is None and cari_eslestir("", CARILER) is None


# ── Yükleme: firma çözümü ────────────────────────────────────────────
@pytest.mark.parametrize("ham,beklenen", [
    ("ITOPYA", "ITOPYA"), ("EERA", "ITOPYA"), ("Hepsiburada", "HB"), ("D-MARKET", "HB"),
    ("KANAL", "DIGER"), ("Diğer", "DIGER"), ("MONDAY BİLİŞİM SANAYİ VE TİCARET ANONİM ŞİRKETİ", "MONDAY"), ("Monday Bilişim", "MONDAY"),
    ("Monday", "MONDAY"), ("TEKNOKLİK - MONDAY", None),
    ("Aykon", "AYKON BİLGİSAYAR LTD. ŞTİ."), ("Teknosa", None), ("Bilinmeyen Ltd", None)])
def test_firma_coz(ham, beklenen):
    from kayranpm.excel_islemler import _firma_coz
    assert _firma_coz(ham, CARILER) == beklenen


def _birlesik_excel(tmp_path, firmalar):
    df = pd.DataFrame([{"FİRMA ADI": f, "KATEGORİ": "MONİTÖR", "MARKA": "FAZEON", "STOK KODU": f"X{i}",
                        "STOK ADI": "ürün", "STOK": 5, "STOK-MAĞAZA": 0, "SATIŞ": 1, "SATIŞ-MAĞAZA": 0}
                       for i, f in enumerate(firmalar)])
    yol = tmp_path / "firma.xlsx"
    df.to_excel(yol, index=False)
    return str(yol)


def test_birlesik_yukleme_taninmayan_firmada_hic_yazmaz(tmp_path, monkeypatch):
    import kayranpm.excel_islemler as X
    yazilan = []
    monkeypatch.setattr(X, "upsert_firma_stok", lambda *a, **k: yazilan.append(a))
    monkeypatch.setattr(X, "_cari_listesi", lambda: CARILER)
    ok, mesaj = X.excel_yukle_firma_birlesik(_birlesik_excel(tmp_path, ["VATAN", "Bilinmeyen Ltd"]))
    assert ok is False and "Bilinmeyen Ltd" in mesaj and yazilan == []


def test_birlesik_yukleme_yeni_cari_ve_kanal(tmp_path, monkeypatch):
    import kayranpm.excel_islemler as X
    yazilan = []
    monkeypatch.setattr(X, "upsert_firma_stok", lambda firma, sku, *a, **k: yazilan.append((firma, sku)))
    monkeypatch.setattr(X, "_cari_listesi", lambda: CARILER)
    ok, _ = X.excel_yukle_firma_birlesik(_birlesik_excel(tmp_path, ["Aykon", "KANAL", "Monday Bilişim Sanayi ve Ticaret Anonim Şirketi"]))
    assert ok is True
    assert {f for f, _ in yazilan} == {"AYKON BİLGİSAYAR LTD. ŞTİ.", "DIGER", "MONDAY"}   # 'KANAL' yazılmaz


# ── Okuma: eski KANAL kayıtları DİĞER ────────────────────────────────
def test_kanal_stoklari_eski_kanal_digere_katilir():
    from kayranpm.stok_hesap import kanal_stoklari
    rows = [{"firma": "KANAL", "sku": "A", "stok_miktari": 3, "yukleme_tarihi": "2026-09-28"},
            {"firma": "DIGER", "sku": "A", "stok_miktari": 2, "yukleme_tarihi": "2026-09-28"},
            {"firma": "AYKON BİLGİSAYAR LTD. ŞTİ.", "sku": "A", "stok_miktari": 7, "yukleme_tarihi": "2026-09-21"}]
    k = kanal_stoklari(rows)
    assert "KANAL" not in k and k["DIGER"]["A"] == 5 and k["AYKON BİLGİSAYAR LTD. ŞTİ."]["A"] == 7


def test_kampanya_diger_suzgeci_yalniz_firmasi_belli_olmayan():
    from datetime import date
    from kayranpm.kampanya_hesap import filtrele, firma_secenekleri
    kamps = [{"id": 1, "firma": "KANAL"}, {"id": 2, "firma": "DİĞER"}, {"id": 3, "firma": "AYKON BİLGİSAYAR LTD. ŞTİ."},
             {"id": 4, "firma": "HB"}]
    ids = lambda f: {k["id"] for k in filtrele(kamps, date(2026, 10, 3), firma=f)}
    assert ids("DİĞER") == {1, 2}                                  # yeni cari DİĞER'e düşmez
    assert ids("AYKON BİLGİSAYAR LTD. ŞTİ.") == {3} and ids("HB") == {4}
    s = firma_secenekleri(["AYKON BİLGİSAYAR LTD. ŞTİ.", "KANAL"])
    assert "KANAL" not in s and s[-1] == "DİĞER" and "AYKON BİLGİSAYAR LTD. ŞTİ." in s


def test_kanal_hicbir_listede_yok():
    import pathlib
    kok = pathlib.Path(__file__).resolve().parent.parent
    from kayranpm import excel_islemler as X
    assert "KANAL" not in X.FIRMA_LISTESI
    sat = (kok / "satis" / "database.py").read_text(encoding="utf-8")
    assert '"MONDAY", "KANAL"' not in sat


# ── Bayat modül koruması ─────────────────────────────────────────────
def test_modul_tazele(tmp_path):
    import types
    from shared.modul_tazele import tazelenmeli, proje_modullerini_sil
    kok = str(tmp_path)
    (tmp_path / "shared").mkdir()
    h = ImportError("cannot import name 'urun_ad'", name="shared.ana_veri", path=str(tmp_path / "shared" / "ana_veri.py"))
    assert tazelenmeli(h, kok) is True
    assert tazelenmeli(ValueError("x"), kok) is False
    assert tazelenmeli(ImportError("x", name="pandas", path="/usr/lib/pandas/__init__.py"), kok) is False
    m_proje = types.ModuleType("shared.ana_veri"); m_proje.__file__ = str(tmp_path / "shared" / "ana_veri.py")
    m_dis = types.ModuleType("pandas"); m_dis.__file__ = "/usr/lib/pandas/__init__.py"
    mods = {"shared.ana_veri": m_proje, "pandas": m_dis, "__main__": m_proje}
    assert proje_modullerini_sil(mods, kok) == ["shared.ana_veri"] and set(mods) == {"pandas", "__main__"}


def _proje_dosyasindan_hata(tmp_path, govde):
    """tmp_path/kayranpm/ekran.py içinde 'govde'yi çalıştırıp çıkan hatayı döndürür."""
    import importlib.util
    (tmp_path / "kayranpm").mkdir(exist_ok=True)
    p = tmp_path / "kayranpm" / "ekran.py"
    p.write_text("def f(a):\n    return a\n\ndef calis(mod):\n    " + govde + "\n", encoding="utf-8")
    spec = importlib.util.spec_from_file_location("kayranpm_ekran_test", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    hesap = __import__("types").ModuleType("kayranpm.musteri_hesap")
    hesap.__file__ = str(tmp_path / "kayranpm" / "musteri_hesap.py")
    try:
        m.calis(hesap)
    except Exception as e:  # noqa: BLE001
        return e
    raise AssertionError("hata çıkmadı")


def test_modul_tazele_bayat_imza_ve_ad(tmp_path):
    """Yeni ekran, bellekte eski kalan fonksiyonu yeni parametreyle çağırırsa TypeError çıkar
    (3 Ekim Müşteri Satışları hatasının muhtemel sebebi); koruma yalnız ImportError'a bakıyordu."""
    from shared.modul_tazele import tazelenmeli
    kok = str(tmp_path)
    assert tazelenmeli(_proje_dosyasindan_hata(tmp_path, "return f(1, eslesme={})"), kok) is True
    assert tazelenmeli(_proje_dosyasindan_hata(tmp_path, "return f()"), kok) is True
    assert tazelenmeli(_proje_dosyasindan_hata(tmp_path, "return mod.meta_hazirla"), kok) is True


def test_modul_tazele_gercek_hatada_tazelemez(tmp_path):
    from shared.modul_tazele import tazelenmeli
    kok = str(tmp_path)
    assert tazelenmeli(_proje_dosyasindan_hata(tmp_path, "return 'a' + 1"), kok) is False      # tür hatası, imza değil
    assert tazelenmeli(_proje_dosyasindan_hata(tmp_path, "return None.x"), kok) is False      # modül değil
    try:
        int(x=1)                                                                               # proje dışı çağrı
    except TypeError as e:
        assert tazelenmeli(e, kok) is False
    import pandas
    assert tazelenmeli(AttributeError("x", name="yok", obj=pandas), kok) is False             # proje dışı modül


def test_app_hata_kartindan_once_tazeler():
    import pathlib
    a = (pathlib.Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
    i, j = a.index("from shared.modul_tazele import"), a.index("_global_hata_kart(ad, hata)")
    assert i < j and 'st.session_state.get("_modul_tazelendi")' in a
