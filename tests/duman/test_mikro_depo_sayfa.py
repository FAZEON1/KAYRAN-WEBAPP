# -*- coding: utf-8 -*-
"""Sayfa testi · Mikro depo hareketleri (Ekim 2026, kayranpm/mikro_depo): Depo › Happy Life ve Stok yaşı.

Kaynak kapalıyken ve aktarıcı veri getirdiyse bir kerelik onay kutusu ve karşılaştırma çizilir; açıkken Happy Life
sayfası stok, giriş tarihi ve yaşı Mikro'dan gösterir. Veri yokken (göç uygulanmadan) kutu hiç çıkmaz. Yalnız
gerçek Streamlit kuruluyken çalışır."""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_sayfalar import BETIK, SURE  # noqa: E402
from test_stok_yasi_veri import VERI, _metin, _sorunlar  # noqa: E402

HL = "🏭 Happy Life Kiralık Depo"


def _h(guid, tarih, tip, cins, miktar, giris=0, cikis=0, exim=None):
    return {"sth_guid": guid, "sth_tarih": f"{tarih}T00:00:00", "sth_tip": tip, "sth_cins": cins,
            "sth_evraktip": 13 if tip == 0 else (2 if tip == 2 else 1), "sth_normal_iade": 0,
            "sth_evrakno_seri": "IRS", "sth_evrakno_sira": 1, "sth_stok_kod": "FAZEON X24F165S", "sth_miktar": miktar,
            "sth_giris_depo_no": giris, "sth_cikis_depo_no": cikis, "sth_exim_kodu": exim, "sth_iptal": False}


MIKRO = {
    "mikro_depo_kart": [{"dep_no": 1, "dep_adi": "Merkez depo"}, {"dep_no": 4, "dep_adi": "HAPPY LİFE"},
                        {"dep_no": 8, "dep_adi": "ALY ANTREPO "}],
    "mikro_stok_miktar": [{"sto_kod": "FAZEON X24F165S", "sto_isim": "FAZEON 24 MONITOR", "depo": 4, "miktar": 20},
                          {"sto_kod": "FAZEON X24F165S", "depo": 1, "miktar": 40}],
    "mikro_depo_hareket": [_h("a", "2026-05-02", 0, 12, 100, giris=1, exim="IT-1"),
                           _h("b", "2026-06-10", 2, 6, 30, giris=4, cikis=1),
                           _h("c", "2026-08-10", 1, 0, 40, cikis=1),
                           _h("d", "2026-09-15", 1, 0, 10, cikis=4)],
    "mikro_senk_durum": [{"tablo": "mikro_depo_hareket", "son_cekim": "2026-10-21T10:00:00+03:00"}],
    "happylife_stok": [{"id": 1, "rapor_tarihi": "2026-07-09", "sku": "X24F165S", "sku_tanim": "FAZEON 24",
                        "giris_tarihi": "2026-06-10", "palet_etiketi": "P1", "miktar": 30, "birim": "Adet",
                        "miktar2": 30, "birim2": "Adet"}],
}


def _ac(uygulama, anahtar, sayfa, acik=None, durum=None):
    """acik: None → durum kaydı yok (varsayılan: AÇIK, kullanıcı kararı 22.10.2026); True / False → kayıt."""
    import os
    import sahte_db
    from streamlit.testing.v1 import AppTest
    os.environ["DUMAN_ONBELLEK_TEMIZLE"] = "1"
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    for t, rows in list(VERI.items()) + list(MIKRO.items()):
        sahte_db.TABLOLAR[t] = [dict(r) for r in rows]
    if acik is not None:
        sahte_db.TABLOLAR["sistem_ayarlari"] = [{"anahtar": "mikro_depo_durum",
                                                 "deger": '{"acik": true}' if acik else '{"acik": false}'}]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    for k, v in dict({"giris_yapildi": True, "aktif_kullanici": sahte_db.KULLANICI, "aktif_uygulama": uygulama,
                      anahtar: sayfa}, **(durum or {})).items():
        at.session_state[k] = v
    try:
        at.run()
    finally:
        os.environ.pop("DUMAN_ONBELLEK_TEMIZLE", None)
    return at


def test_kapaliyken_onay_kutusu_ve_karsilastirma():
    at = _ac("depo", "depo_sayfa", HL, acik=False, durum={"md_goster_hl": True})
    assert not _sorunlar(at), _sorunlar(at)
    assert any("Mikro'dan gelsin" in e.label for e in at.expander)
    m = _metin(at)
    assert "Happy Life" in m and "Stok yaşı" in m
    assert at.button(key="md_ac_hl").disabled                  # onay işareti olmadan açılmaz


@pytest.mark.parametrize("acik", [True, None])                  # None: kayıt yok → varsayılan açık
def test_aciliyken_happy_life_mikrodan(acik):
    """Kullanıcı (22.10.2026): "palet listesine ihtiyacım yok; sadece adet, model ve stok yaşı yeterli"."""
    at = _ac("depo", "depo_sayfa", HL, acik=acik)
    assert not _sorunlar(at), _sorunlar(at)
    m = _metin(at)
    assert "Model, adet ve stok yaşı Mikro'dan" in m
    assert "Elde kalan partiler" not in m and "Palet" not in m
    assert not any("palet" in e.label.lower() for e in at.expander)
    assert not any("Mikro'dan gelsin" in e.label for e in at.expander)


def test_aciliyken_stok_yasi_ve_satilamayan():
    at = _ac("kayranpm", "pm_sayfa", "Stok Yaşı", acik=True)
    assert not _sorunlar(at), _sorunlar(at)
    at = _ac("depo", "depo_sayfa", "Satılamayan stok", acik=True)
    assert not _sorunlar(at), _sorunlar(at)
