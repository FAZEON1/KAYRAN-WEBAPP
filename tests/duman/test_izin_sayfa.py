# -*- coding: utf-8 -*-
"""Sayfa testi, ÖRNEK VERİYLE: kişi menüsü › İzinler (Ekim 2026). Yönetici bütün bölümleri, çalışan yalnız
kendi izinlerini ve takvimi görür; talep formu gün sayısını hesaplayıp kaydeder; onay düğmesi çalışır."""
from datetime import date, timedelta

import pytest

pytest.importorskip("streamlit.testing.v1")

from test_sayfalar import BETIK, SURE  # noqa: E402


def _pzt(hafta=2):
    """Bugünden en az `hafta` hafta sonraki Pazartesi (tatile denk gelmeyen sabit bir aralık için)."""
    g = date.today() + timedelta(weeks=hafta)
    return g - timedelta(days=g.weekday())


def _veri():
    import sahte_db
    p = _pzt(3)
    return {
        "kullanici_yetkileri": [dict(r) for r in sahte_db.YETKI]
        + [{"id": 2, "kullanici": "ali", "moduller": ["depo"], "ozel": [], "salt_okur": False, "aktif": True}],
        "personel": [
            {"kod": sahte_db.KULLANICI, "ad": "İbrahim Kayran", "departman": "Yönetim", "ise_giris": "2018-01-02"},
            {"kod": "ali", "ad": "Ali Veli", "departman": "Depo", "ise_giris": "2021-03-15",
             "dogum_tarihi": "1990-05-05", "devir_tarihi": "2025-12-31", "devir_gun": 6.5},
            {"kod": "eski", "ad": "Eski Çalışan", "ise_giris": "2015-01-01", "cikis_tarihi": "2024-01-31"},
        ],
        "izin_talepleri": [
            {"id": 1, "personel": "ali", "tur": "yillik", "baslangic": p.isoformat(),
             "bitis": (p + timedelta(days=4)).isoformat(), "yarim_gun": False, "gun": 5, "takvim_gunu": 5,
             "durum": "bekliyor", "talep_eden": "ali", "talep_zamani": "2026-10-01T10:00:00+03:00",
             "aciklama": "Aile ziyareti"},
            {"id": 2, "personel": "ali", "tur": "rapor", "baslangic": date.today().isoformat(),
             "bitis": date.today().isoformat(), "yarim_gun": False, "gun": 1, "takvim_gunu": 1,
             "durum": "onaylandi", "talep_eden": "ali", "karar_veren": sahte_db.KULLANICI},
        ],
    }


def _ac(kullanici=None, bolum=None, tablolar=None):
    import sahte_db
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    st.cache_data.clear()
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR.update(tablolar if tablolar is not None else _veri())
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = kullanici or sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = "izin"
    if bolum:
        at.session_state["izin_bolum"] = bolum
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _metin(at):
    return " ".join(str(m.value) for m in at.markdown) + " " + " ".join(str(c.value) for c in at.caption)


@pytest.mark.parametrize("bolum", ["İzinlerim", "Onay", "Takvim", "Rapor", "Personel", "Ayarlar"])
def test_yonetici_bolumleri(bolum):
    at = _ac(bolum=bolum)
    m = _metin(at)
    assert "1 izin talebi onay bekliyor" in m
    if bolum == "Onay":
        assert "Ali Veli" in m and "Yıllık izin" in m and "Aile ziyareti" in m
        from shared import izin_hesap as H
        ali = next(x for x in _veri()["personel"] if x["kod"] == "ali")
        k = H.bakiye(ali, [], date.today())["kullanilabilir"]          # devir 6,5 + devirden sonra doğan haklar
        assert f"Kalan {H.tr_gun(k)} → onaylanırsa {H.tr_gun(k - 5)}" in m
    if bolum == "Takvim":
        assert "izn-tbl" in m and "Ali Veli" in m and "Eski Çalışan" not in m
    if bolum == "Rapor":
        assert "İzin bakiyeleri" in m
    if bolum == "Personel":
        assert "Kart aç / düzenle" in m


def test_talep_gonder_gun_sayisini_yazar():
    import sahte_db
    at = _ac()
    p = _pzt(6)
    at.selectbox(key="izn_k_0_tur").set_value("yillik")
    at.date_input(key="izn_k_0_bas").set_value(p)
    at.date_input(key="izn_k_0_bit").set_value(p + timedelta(days=6))       # Pzt–Pzr: 5 iş günü
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    from shared.izin_hesap import izin_gunu
    beklenen = izin_gunu(p, p + timedelta(days=6))
    at.button(key="izn_k_0_gonder").click().run()
    assert not at.exception, [e.value for e in at.exception]
    yeni = [t for t in sahte_db.TABLOLAR["izin_talepleri"] if t.get("personel") == sahte_db.KULLANICI]
    assert len(yeni) == 1 and yeni[0]["gun"] == beklenen and yeni[0]["takvim_gunu"] == 7
    assert yeni[0]["durum"] == "bekliyor" and yeni[0]["talep_eden"] == sahte_db.KULLANICI


def test_onay_dugmesi():
    at = _ac(bolum="Onay")
    at.button(key="izn_on_1").click().run()
    assert not at.exception, [e.value for e in at.exception]


def test_calisan_yalniz_kendini_gorur():
    at = _ac(kullanici="ali")
    sec = at.button_group(key="izin_bolum")
    assert [str(o) for o in sec.options] == ["İzinlerim", "Takvim"]
    m = _metin(at)
    assert "onay bekliyor (Onay bölümü)" not in m and "Aile ziyareti" in m
    assert "Talebi geri çek" in [b.label for b in at.button]
    at = _ac(kullanici="ali", bolum="Takvim")
    m = _metin(at)
    assert "Sağlık raporu" not in m and "İzinli" in m                       # tür gizli


def test_bos_veri():
    import sahte_db
    at = _ac(tablolar={"kullanici_yetkileri": [dict(r) for r in sahte_db.YETKI]})
    m = _metin(at)
    assert "Personel kartın henüz açılmamış" in m


def _kart_kaydet(at, kod):
    at.selectbox(key="izn_per_sec").set_value(kod).run()
    at.date_input(key=f"izn_per_{kod}_giris").set_value(date(2020, 5, 4)).run()
    at.button(key=f"izn_per_{kod}_kaydet").click().run()
    assert not at.exception, [e.value for e in at.exception]


def test_kart_ilk_kayitta_bilgilendirme_gider(monkeypatch):
    import sahte_db
    import shared.eposta as E
    giden = []
    monkeypatch.setattr(E, "gonder", lambda alicilar, konu, html, **k: giden.append((alicilar, konu, k)) or (True, "ok"))
    monkeypatch.setattr(E, "adresler", lambda: {"veli": "veli@g5fteknoloji.com"})
    v = _veri()
    v["kullanici_yetkileri"].append({"id": 3, "kullanici": "veli", "moduller": [], "ozel": [], "salt_okur": False,
                                     "aktif": True})
    at = _ac(bolum="Personel", tablolar=v)
    _kart_kaydet(at, "veli")
    assert len(giden) == 1 and giden[0][0] == ["veli@g5fteknoloji.com"]
    assert giden[0][1] == "[G5F] Personel izin kartınız açıldı" and giden[0][2]["gomulu"][0][0] == "g5f-logo"
    kart = [p for p in sahte_db.TABLOLAR["personel"] if p["kod"] == "veli"][-1]
    assert kart["eposta"] is None                       # kayıtlı adres karta kopyalanmaz, sorulmaz da
    assert "bilgilendirme e-postası gönderildi" in " ".join(str(m.value) for m in at.markdown)
    at.selectbox(key="izn_per_sec").set_value("veli").run()
    assert not [t for t in at.text_input if t.key == "izn_per_veli_eposta"]


def test_bilgilendirilmis_kartta_tekrar_gitmez(monkeypatch):
    import shared.eposta as E
    giden = []
    monkeypatch.setattr(E, "gonder", lambda *a, **k: giden.append(a) or (True, "ok"))
    monkeypatch.setattr(E, "adresler", lambda: {"ali": "ali@g5fteknoloji.com"})
    v = _veri()
    for p in v["personel"]:
        if p["kod"] == "ali":
            p["bilgi_zamani"] = "2026-10-01T10:00:00+03:00"
    at = _ac(bolum="Personel", tablolar=v)
    at.selectbox(key="izn_per_sec").set_value("ali").run()
    assert "Bilgilendirmeyi tekrar gönder" in [b.label for b in at.button]
    # (sahte veritabanında upsert yeni satır ekler; gerçek tabloda bilgi_zamani yerinde kalır)
    _kart_kaydet(at, "ali")
    assert giden == []


def test_adres_yoksa_gitmez(monkeypatch):
    import shared.eposta as E
    giden = []
    monkeypatch.setattr(E, "gonder", lambda *a, **k: giden.append(a) or (True, "ok"))
    monkeypatch.setattr(E, "adresler", lambda: {})
    at = _ac(bolum="Personel")
    _kart_kaydet(at, "ali")
    assert giden == [] and "Kayıtlı e-posta adresi olmadığı için" in " ".join(str(m.value) for m in at.markdown)


def test_personel_yetkilisi_onay_veremez_ve_haric_listesi():
    """izin_yonetimi (Serdar gibi): Personel ve Rapor var, Onay yok; Ayarlar'da seçilen kullanıcılar (ortaklar)
    'kart yok' listesine girmez."""
    v = _veri()
    v["kullanici_yetkileri"] += [
        {"id": 5, "kullanici": "serdar", "moduller": ["depo"], "ozel": ["izin_yonetimi"], "salt_okur": False,
         "aktif": True},
        {"id": 6, "kullanici": "ahmet", "moduller": [], "ozel": ["yonetim"], "salt_okur": False, "aktif": True}]
    v["sistem_ayarlari"] = [{"anahtar": "izin_ayar", "deger": '{"cumartesi": false, "haric": ["ahmet"]}'}]
    at = _ac(kullanici="serdar", bolum="Personel", tablolar=v)
    assert [str(o) for o in at.button_group(key="izin_bolum").options] == [
        "İzinlerim", "Takvim", "Rapor", "Personel", "Ayarlar"]
    secenek = at.selectbox(key="izn_per_sec").options
    assert not any("Ahmet" in str(o) for o in secenek) and any("Serdar" in str(o) for o in secenek)
    at = _ac(kullanici="serdar", bolum="Rapor", tablolar=v)
    assert "İptal et" not in [b.label for b in at.button]              # onaylı izni iptal de onay yetkisi ister


def test_eposta_sorulmaz():
    """Kullanıcı kararı: e-posta alanı yok; yalnız Kullanıcı yönetimindeki kayıtlı adrese gider."""
    at = _ac(bolum="Personel")
    at.selectbox(key="izn_per_sec").set_value("ali").run()
    assert not [t for t in at.text_input if "eposta" in str(t.key)]
    assert "Kayıtlı e-posta adresi yok; bilgilendirme e-postası gönderilmez." in " ".join(str(c.value) for c in at.caption)
