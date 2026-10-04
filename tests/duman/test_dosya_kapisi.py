# -*- coding: utf-8 -*-
"""Sayfa testi · Dosya kapısı (Ekim 2026): her yükleme türü gerçek Streamlit'te, kapının İÇİNDE.

Bütün Excel yüklemeleri tek pencereye (shared/dosya_kapisi) taşındı. Birim testler pencereyi
sahte streamlit'le (st.dialog = düz fonksiyon) çalıştırdığı için "pencere içinde pencere" gibi
hataları göremez; burada her türün örnek dosyası (tests/kapi_ornekleri.py) kapıya konur, uygulama
gerçek Streamlit'le açılır, akış çizilir ve kayıt düğmesine basılır. Yakalanmamış hata, uygulamanın
yakalayıp kaydettiği hata ya da kaydın kapıya sonuç olarak dönmemesi testi kırar.
Yalnız gerçek Streamlit kuruluyken çalışır (CI: "Sayfa testi").
"""
import os
import sys

import pytest

pytest.importorskip("streamlit.testing.v1")

from test_sayfalar import BETIK, SURE  # noqa: E402
from test_stok_yasi_veri import VERI  # noqa: E402

_TESTLER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TESTLER not in sys.path:
    sys.path.insert(0, _TESTLER)
from kapi_ornekleri import ORNEKLER  # noqa: E402

# Kayıt düğmesinin dosyaya özgü anahtarı (kapi.anahtar(...)) ve kayıt öncesi işaretlenecek onaylar
KAYDET = {
    "siparis_vatan": "sg_kaydet_vatan", "siparis_itopya": "sg_kaydet", "mikro_fatura": "satis_ice_btn",
    "iade_excel": "iade_excel_btn", "ithalat_rapor": "ith_excel_import", "happylife": "hl_kaydet_btn",
    "toplu_mal_kabul": "tmk_kaydet", "kampanya_sablon": "kmp_o_olustur", "g5f_sayim": "g5f_depo_btn",
    "ref_excel": "ref_imp_btn", "alinan_destek": "ad2_imp", "gider_tablosu": "gider_kaydet",
    "aktif_cari": "aktif_cari_kaydet", "aktif_ithalat": "aktif_ithalat_kaydet", "aktif_stok": "aktif_stok_kaydet",
    "musteri_haftalik": "mhs_hss_btn", "odeme_listesi": "odeme_yukle", "cek_listesi": "cek_kaydet",
}
ID = "t1"


def _anahtar(ad):
    return f"{ad}__kp{ID}"


def _kapida(tur, ad=None, veri=None, adaylar=None, tablolar=None):
    import sahte_db
    from streamlit.testing.v1 import AppTest
    os.environ["DUMAN_ONBELLEK_TEMIZLE"] = "1"
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    for t, rows in VERI.items():
        sahte_db.TABLOLAR[t] = [dict(r) for r in rows]
    sahte_db.TABLOLAR["ref_firmalar"] = [{"id": 7, "firma_adi": "VATAN", "firma_kodu": "VT"}]
    for t, rows in (tablolar or {}).items():
        sahte_db.TABLOLAR[t] = [dict(r) for r in rows]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = "anasayfa"
    if veri is None:
        ad, veri = ORNEKLER[tur]()
    if adaylar is None:
        adaylar = [{"tur": tur, "guven": "kesin", "gerekce": "test"}]
    at.session_state["_kapi_acik"] = True
    at.session_state["_kapi_dosyalar"] = [{"id": ID, "ad": ad, "veri": veri, "secim": tur, "adaylar": adaylar}]
    at.session_state["_kapi_aktif"] = ID
    try:
        at.run()
    finally:
        os.environ.pop("DUMAN_ONBELLEK_TEMIZLE", None)
    return at


def _sorunlar(at):
    s = [f"yakalanmamış: {e.value}" for e in at.exception]
    s += list(at.session_state["_duman_hatalar"]) if "_duman_hatalar" in at.session_state else []
    s += [f"hata kutusu: {m.value[:200]}" for m in at.error]
    return s


@pytest.mark.parametrize("tur", sorted(ORNEKLER))
def test_kapida_akis_ve_kayit(tur, ad=None, veri=None):
    at = _kapida(tur, ad=ad, veri=veri)
    assert not _sorunlar(at), _sorunlar(at)
    # Zorunlu seçimler: firma (EERA şablonu, ref)
    if tur == "siparis_itopya":
        at.selectbox(key=_anahtar("sg_kanal")).select_index(0).run()
        at.text_input(key=_anahtar("sg_sno")).input("S-1").run()
    if tur == "ref_excel":
        at.selectbox(key=_anahtar("ref_firma")).select_index(0).run()
    for onay in ("cek_onay", "odeme_ayni_onay", "iade_cakisma_onay", "satis_ice_onay", "tmk_muk_ok"):
        if any(c.key == _anahtar(onay) for c in at.checkbox):
            at.checkbox(key=_anahtar(onay)).check().run()
    assert not _sorunlar(at), _sorunlar(at)
    dugme = [b for b in at.button if b.key == _anahtar(KAYDET[tur])]
    assert dugme, (tur, "kayıt düğmesi yok", [b.key for b in at.button])
    assert not dugme[0].disabled, (tur, "kayıt düğmesi pasif")
    dugme[0].click().run()
    assert not _sorunlar(at), _sorunlar(at)
    sonuc = at.session_state["_kapi_sonuc"] if "_kapi_sonuc" in at.session_state else None
    assert sonuc and sonuc["mesaj"], (tur, "kayıt sonucu kapıya dönmedi")
    assert at.session_state["_kapi_acik"]                     # sonuç kapıda gösterilir
    assert not at.session_state["_kapi_dosyalar"]             # işlenen dosya listeden düştü


def _uygulama(mod="anasayfa", **durum):
    import sahte_db
    from streamlit.testing.v1 import AppTest
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = mod
    for k, v in durum.items():
        at.session_state[k] = v
    at.run()
    return at


def test_ust_menu_dugmesi_kapiyi_acar_baska_pencereyle_cakismaz():
    """Bir çalışmada tek pencere: Talep Merkezi / mal kabul penceresinin bekleyen bayrağı varken de
    kapı açılır ("Only one dialog" hatası yok)."""
    at = _uygulama("teknikservis", ts_sayfa="📥  Mal Kabül")
    assert not _sorunlar(at), _sorunlar(at)
    dugme = [b for b in at.button if b.key == "ust_dosya"]
    assert dugme, "üst menüde Dosya düğmesi yok"
    at.session_state["_mk_dialog_ac"] = True
    at.session_state["_talep_ac"] = True
    dugme[0].click().run()
    assert not _sorunlar(at), _sorunlar(at)
    assert at.session_state["_kapi_acik"]
    assert "_mk_dialog_ac" not in at.session_state and "_talep_ac" not in at.session_state
    assert any("bırakın ya da seçin" in str(u.label) for u in at.get("file_uploader")), "kapı penceresi çizilmedi"


def test_liste_tur_secimi_ve_kapat():
    """Birden çok dosya: liste görünür; tanınmayan dosyada tür seçilir; Kapat kapıyı temizler."""
    ad1, v1 = ORNEKLER["siparis_vatan"]()
    dosyalar = [{"id": "a1", "ad": ad1, "veri": v1, "secim": "siparis_vatan",
                 "adaylar": [{"tur": "siparis_vatan", "guven": "kesin", "gerekce": "test"}]},
                {"id": "a2", "ad": "bilinmeyen.xlsx", "veri": b"", "secim": None, "adaylar": []}]
    at = _uygulama(_kapi_acik=True, _kapi_dosyalar=dosyalar)
    assert not _sorunlar(at), _sorunlar(at)
    assert [b.key for b in at.button if b.key and b.key.startswith("kapi_ac_")] == ["kapi_ac_a1", "kapi_ac_a2"]
    assert [b for b in at.button if b.key == "kapi_ac_a2"][0].disabled      # tür seçilmeden açılmaz
    at.selectbox(key="kapi_tur_a2").select("odeme_listesi").run()
    assert not [b for b in at.button if b.key == "kapi_ac_a2"][0].disabled
    [b for b in at.button if b.key == "kapi_ac_a1"][0].click().run()
    assert not _sorunlar(at), _sorunlar(at)
    assert at.session_state["_kapi_aktif"] == "a1"
    [b for b in at.button if b.key == "kapi_geri"][0].click().run()
    assert "_kapi_aktif" not in at.session_state


def test_sonuc_ekrani_kapat():
    at = _uygulama(_kapi_acik=True, _kapi_dosyalar=[], _kapi_sonuc={"mesaj": "3 kalem kaydedildi.", "tablo": [],
                                                                    "uyari": False, "ayrinti": "", "dosya": "x"})
    assert not _sorunlar(at), _sorunlar(at)
    assert any("3 kalem kaydedildi." in str(m.value) for m in at.success)
    [b for b in at.button if b.key == "kapi_kapat"][0].click().run()
    assert not _sorunlar(at), _sorunlar(at)
    assert "_kapi_acik" not in at.session_state and "_kapi_sonuc" not in at.session_state


def _alt_dugumler(n):
    yield n
    ch = getattr(n, "children", None)
    if isinstance(ch, dict):
        for c in ch.values():
            yield from _alt_dugumler(c)


def test_pencere_icindeki_tablo_pencerede_cizilir():
    """st.dataframe (kısa tablo → shared.tablo bileşeni) kök sayfa kabına yazılıyordu: pencere içindeki
    önizleme tabloları pencerede değil arkadaki sayfada çıkıyordu (kapıdaki her önizleme kayboluyordu)."""
    at = _kapida("cek_listesi")
    assert not _sorunlar(at), _sorunlar(at)
    pencere = [n for n in _alt_dugumler(at._tree) if getattr(n, "type", None) == "dialog"]
    assert pencere, "pencere yok"
    assert any(getattr(n, "type", None) == "bidi_component" for n in _alt_dugumler(pencere[0])), \
        "önizleme tablosu pencerenin içinde değil"
