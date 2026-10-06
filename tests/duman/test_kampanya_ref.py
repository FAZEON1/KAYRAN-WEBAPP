# -*- coding: utf-8 -*-
"""Sayfa testi · Kampanya kapanınca otomatik Ref No (Ekim 2026): gerçek Streamlit'te Kampanya Takip
penceresinden "Kampanyayı kapat" → Ref No Takip'e kampanyanın desteğiyle ref açılır, ikinci kapatmada
yeni ref açılmaz. Yalnız gerçek Streamlit kuruluyken çalışır (CI: "Sayfa testi")."""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_dosya_kapisi import _sorunlar  # noqa: E402
from test_sayfalar import BETIK, SURE  # noqa: E402

KID = 7
TABLOLAR = {
    "kampanyalar": [{"id": KID, "kampanya_adi": "AĞUSTOS EK DESTEK", "firma": "VATAN", "durum": "aktif",
                     "baslangic_tarihi": "2026-08-01", "bitis_tarihi": "2026-08-31", "kategori": "monitör",
                     "kampanya_turu": "Sellout", "spiff_tl": 0, "spiff_kur": 0, "notlar": "",
                     "olusturma_tarihi": "2026-08-01"}],
    "kampanya_urunler": [
        {"id": 1, "kampanya_id": KID, "sku": "X24F165S", "urun_adi": "Monitör A", "pacal_maliyet": 80,
         "satis_fiyati": 120, "birim_firma_destek": 5, "birim_ek_destek": 1, "satilan_adet": 100},
        {"id": 2, "kampanya_id": KID, "sku": "VG27AQ", "urun_adi": "Monitör B", "pacal_maliyet": 200,
         "satis_fiyati": 260, "birim_firma_destek": 12, "birim_ek_destek": 0, "satilan_adet": 13}],
    "ref_firmalar": [{"id": 3, "firma_adi": "VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI",
                      "firma_kodu": "VTN"}],
    "ref_kayitlari": [],
}


def _pencere():
    import sahte_db
    from streamlit.testing.v1 import AppTest
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    for t, rows in TABLOLAR.items():
        sahte_db.TABLOLAR[t] = [dict(r) for r in rows]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = "kayranpm"
    at.session_state["pm_sayfa"] = "🎯  Kampanya Takip"
    at.session_state["_kmp_sec"] = KID
    at.session_state["_kmp_ac"] = True
    at.run()
    return at, sahte_db


def _kapat(at):
    """AppTest pencereyi yalnız açılış bayrağıyla çizer (tarayıcıda pencere açık kalır): düğmeye
    basılan çalışmada da pencere çizilsin."""
    at.session_state["_kmp_sec"] = KID
    at.session_state["_kmp_ac"] = True
    at.button(key=f"kmp_kapat_{KID}").click().run()


def test_kampanya_kapaninca_ref_acilir_ikinci_kez_acilmaz():
    at, db = _pencere()
    assert not _sorunlar(at), _sorunlar(at)
    assert any("Kapatınca Ref No Takip'e açılacak" in c.value and "$756,00" in c.value for c in at.caption)
    _kapat(at)
    assert not _sorunlar(at), _sorunlar(at)
    refler = db.TABLOLAR["ref_kayitlari"]
    assert len(refler) == 1
    r = refler[0]
    assert (r["firma_id"], r["ref_no"], float(r["tutar"]), r["doviz"], r["durum"]) == \
        (3, "FZVTNRF" + str(r["yil"]) + "001", 756.0, "USD", "beklemede")
    assert r["aciklama"] == f"AĞUSTOS EK DESTEK · Kampanya #{KID}" and r.get("aylik") == {"2026-08": 756.0}
    # Yeniden açılıp kapatılsa da ikinci ref açılmaz (sahte veritabanı update'i işlemez: kampanya açık
    # kalır, aynı pencereden yeniden kapatılır)
    at.session_state["_kmp_sec"] = KID
    at.session_state["_kmp_ac"] = True
    at.run()
    assert any("ref'i zaten var" in c.value for c in at.caption)
    _kapat(at)
    assert not _sorunlar(at), _sorunlar(at)
    assert len(db.TABLOLAR["ref_kayitlari"]) == 1
