# -*- coding: utf-8 -*-
"""Muhasebe · Mikro eşitlemesi açıkken anlamsız kalan ekran parçaları ekrandan kalkar (kullanıcı kararı 22.10.2026).

Silinmez: kod yedek kalır, eşitleme kapatılırsa eski yol geri gelir. Her davranış iki durumda denenir (Mikro açık /
kapalı; durum monkeypatch ile sahte).
  - Toplam Aktifler: Excel durum kartları yerine tek satır kaynak notu; "Yüklenen verileri temizle" yok (Mikro'nun
    yazdığı kaydı da siliyordu); Hesaplama Formülü gerçek kaynak ve çarpanla; ölü `eksikler` listesi yok.
  - Banka: Mikro'ya bağlı hesapta bakiye elle düzeltilmez; banka_guncelle de bakiyeyi yazmaz.
  - Virman / tahsilat / arbitraj: yalnız bağlı hesaplar → "Bu işlem Mikro'ya girilir" notu.
"""
from pathlib import Path

import pytest

import kayranacc.database as db
import kayranacc.mikro_muhasebe as MM

KOK = Path(__file__).resolve().parent.parent
MAIN = (KOK / "kayranacc" / "main.py").read_text(encoding="utf-8")


def _govde(kaynak, imza):
    return kaynak.split(imza, 1)[1].split("\ndef ", 1)[0]


def _durum(monkeypatch, acik, bagli=()):
    monkeypatch.setattr(MM, "durum", lambda: {"acik": acik, "bagli_bankalar": list(bagli)})


# ─── Banka: hangi hesap Mikro'ya bağlı ───

@pytest.mark.parametrize("acik, bagli, idler, beklenen", [
    (True, [1, 2], [1, 2], True),          # hepsi bağlı → Mikro'ya girilir
    (True, [1], [1, 2], False),            # bağlı olmayan hesap var → eski davranış
    (False, [1, 2], [1, 2], False),        # eşitleme kapalı → eski davranış
    (True, [1, 2], [], False),             # hesap yok
    (True, [1], [1, None], True),          # eksik id sayılmaz
])
def test_yalniz_bagli_mi(monkeypatch, acik, bagli, idler, beklenen):
    _durum(monkeypatch, acik, bagli)
    assert MM.yalniz_bagli_mi(idler) is beklenen


def test_mikro_islemi_mi_durum_okunamazsa_eski_davranis(monkeypatch):
    from kayranacc import banka_ekran as BE
    _durum(monkeypatch, True, [5])
    assert BE.mikro_islemi_mi([5]) is True and BE.mikro_islemi_mi([5, 6]) is False

    def _patla(_ids):
        raise RuntimeError("ayar okunamadı")
    monkeypatch.setattr(MM, "yalniz_bagli_mi", _patla)
    assert BE.mikro_islemi_mi([5]) is False


class _Sorgu:
    def __init__(self, kayit):
        self.kayit = kayit

    def update(self, alanlar):
        self.kayit.append(dict(alanlar))
        return self

    def eq(self, *_a):
        return self

    def execute(self):
        return self


class _Istemci:
    def __init__(self):
        self.yazilan = []

    def table(self, ad):
        assert ad == "bankalar"
        return _Sorgu(self.yazilan)


@pytest.mark.parametrize("bagli", [True, False])
def test_banka_guncelle_bagli_hesapta_bakiye_yazmaz(monkeypatch, bagli):
    ist = _Istemci()
    monkeypatch.setattr(db, "get_client", lambda: ist)
    monkeypatch.setattr(db, "_cache_temizle", lambda: None)
    _durum(monkeypatch, True, [7] if bagli else [])
    db.banka_guncelle(7, "YAPI KREDİ - TL", 1234.5, "TL")
    assert len(ist.yazilan) == 1
    alanlar = ist.yazilan[0]
    assert alanlar["hesap_adi"] == "YAPI KREDİ - TL" and alanlar["para_birimi"] == "TL"
    if bagli:
        assert "bakiye" not in alanlar          # bakiyeyi Mikro yazar
    else:
        assert alanlar["bakiye"] == pytest.approx(1234.5)


def test_banka_guncelle_bakiye_verilmezse_dokunmaz(monkeypatch):
    """Ekran bağlı hesapta bakiye alanı göstermez (None gönderir); eskiden None 0 yazardı."""
    ist = _Istemci()
    monkeypatch.setattr(db, "get_client", lambda: ist)
    monkeypatch.setattr(db, "_cache_temizle", lambda: None)
    _durum(monkeypatch, False)
    db.banka_guncelle(7, "KASA", None, "TL")
    assert "bakiye" not in ist.yazilan[0]


def test_banka_penceresi_bagli_hesapta_bakiye_alani_yok():
    kaynak = (KOK / "kayranacc" / "banka_ekran.py").read_text(encoding="utf-8")
    pencere = _govde(kaynak, "def _banka_dialog(")
    duzenle = pencere.split("with t2:", 1)[1].split("with t3:", 1)[0]
    assert "if bakiye_mikrodan(b[\"id\"]):" in duzenle and "Bakiye Mikro'dan gelir" in duzenle
    # not dalı bakiye alanından önce gelir: alan yalnız else dalında
    assert duzenle.index("Bakiye Mikro'dan gelir") < duzenle.index('number_input("Bakiye"')


# ─── Virman / tahsilat / arbitraj ───

@pytest.mark.parametrize("imza, eylem", [
    ("def _dlg_virman():", 'st.button("Virmanı Yap"'),
    ("def _dlg_tahsilat():", 'with st.form("tahsilat_form")'),
    ("def _dlg_arbitraj():", 'st.button("Arbitrajı Gerçekleştir"'),
])
def test_islem_pencereleri_mikro_bagliyken_not_gosterir(imza, eylem):
    """Eylem (düğme / form) ancak mikro_islemi_mi kontrolünden SONRA ve elif / else dalında; geçmiş listesi kalır."""
    govde = MAIN.split(imza, 1)[1].split("@st.dialog", 1)[0]
    assert "mikro_islemi_mi([b" in govde.split(eylem, 1)[0]                     # bütün hesaplar bağlıysa form yok
    once = govde.split(eylem, 1)[0].rsplit("mikro_islemi_mi(", 1)[1]         # seçilen hesap(lar) için ikinci kontrol
    assert "MIKRO_ISLEM_NOTU" in once
    satir = [s for s in govde.split("\n") if eylem in s][0].strip()
    assert satir.startswith("elif ") or satir.startswith("with ")
    if "virman" in imza:
        assert "get_virmanlar(limit=30)" in govde                              # geçmiş virmanlar kalır
    if "tahsilat" in imza:
        assert "get_tahsilatlar(limit=8)" in govde.split("if mikro_islemi_mi([b", 1)[1]


def test_mikro_islem_notu_metni():
    from kayranacc.banka_ekran import MIKRO_ISLEM_NOTU
    assert MIKRO_ISLEM_NOTU == "Bu işlem Mikro'ya girilir; bakiye 15 dakikada güncellenir."


# ─── Toplam Aktifler ───

def test_excel_kartlari_esitleme_acikken_kalkar():
    from kayranacc.mikro_aktif_ekran import excel_kartlari
    assert excel_kartlari(False, False) == ["stok", "ithalat", "cari"]
    assert excel_kartlari(True, False) == ["ithalat", "cari"]
    assert excel_kartlari(False, True) == ["stok"]
    assert excel_kartlari(True, True) == []


def test_kaynak_notu():
    from kayranacc.mikro_aktif_ekran import kaynak_notu
    assert kaynak_notu(True, True) == "Stok, ithalat ödenen ve cari Mikro'dan, 15 dakikada bir."
    assert "Dosya" in kaynak_notu(False, False) and "Mikro" not in kaynak_notu(False, False)
    assert kaynak_notu(True, False).startswith("Stok Mikro'dan") and "cari alacaklar" in kaynak_notu(True, False)
    assert kaynak_notu(False, True).startswith("İthalat ödenen ve cari Mikro'dan")


def test_temizle_dugmesi_yalniz_hepsi_kapaliyken():
    from kayranacc.mikro_aktif_ekran import temizle_gorunur
    assert temizle_gorunur(False, False, False) is True
    for durum in ((True, False, False), (False, True, False), (False, False, True), (True, True, True)):
        assert temizle_gorunur(*durum) is False


def test_formul_metni_mikro_acik_ve_kapali():
    from kayranacc.mikro_aktif_ekran import formul_metni
    from kayranacc.mikro_aktif import stok_carpani
    kapali = formul_metni(False, False, False, stok_carpani(False), 49.6)
    assert "Stok Değeri × 1,20" in kapali and "(%20 KDV dahil)" in kapali
    assert "Cari Excel'inden POZİTİF" in kapali and "İthalat Excel" in kapali
    assert "Mikro" not in kapali and "Satış maliyeti" not in kapali
    acik = formul_metni(True, True, True, stok_carpani(True), 49.6)
    assert "Stok Değeri × 1,00" in acik and "KDV dahil" not in acik and "KDV kaleminde ayrı" in acik
    assert "Excel" not in acik and "Mikro cari hesaplarından" in acik and "Mikro'daki ithalat" in acik
    assert "Mikro defter kalemleri" in acik and "Satış maliyeti" in acik
    assert "**49.6 TL/USD**" in acik


def test_stok_degeri_onay_kutusu_acikken_tekrar_not_yazmaz(monkeypatch):
    """Açıkken kaynak notu Toplam Aktifler'in tek satırında; onay kutusu ikinci not yazmaz. Kapalıyken onay akışı
    yerinde (kod yedek)."""
    from kayranacc import mikro_stok_degeri_ekran as E
    yazilan = []
    monkeypatch.setattr(E.st, "caption", lambda *a, **k: yazilan.append(a), raising=False)
    monkeypatch.setattr(E.M, "durum", lambda: {"acik": True})
    E.ilk_onay_kutusu()
    assert yazilan == []
    kaynak = (KOK / "kayranacc" / "mikro_stok_degeri_ekran.py").read_text(encoding="utf-8")
    assert "Onayla ve otomatik hesabı aç" in _govde(kaynak, "def ilk_onay_kutusu")
