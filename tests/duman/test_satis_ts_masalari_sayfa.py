# -*- coding: utf-8 -*-
"""Sayfa testi · Satış ve Teknik servis liste masaları (Ekim 2026): örnek veriyle sayfa çökmeden açılır,
ortak masa bileşeni (kayran_masa) satırlarla çizilir, eski listenin parçaları çizilmez ve başlık/indirme
düğmeleri yerinde kalır. Yalnız gerçek Streamlit kuruluyken çalışır (CI: "Sayfa testi")."""
from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("streamlit.testing.v1")

from test_dosya_kapisi import _sorunlar  # noqa: E402
from test_odeme_masasi_sayfa import _bilesen_verisi  # noqa: E402
from test_sayfalar import BETIK, SURE  # noqa: E402


def _ts_ek(tablolar):
    """Örnek veride teknik servis kayıtları 'web' arayüzlü ve hepsi depoda; liste sayfaları için arayüzü
    teknik / iade olan, bir kısmı henüz depoya girmemiş kayıtlar eklenir (yalnız bu testte)."""
    bugun = date.today()
    durum = ["mal kabül", "teknisyende", "tamir edildi", "gönderildi", "satışa hazır", "satıldı"]
    for i in range(12):
        d = bugun - timedelta(days=3 + i * 4)
        bitti = durum[i % 6] in ("satışa hazır", "satıldı")
        tablolar["ts_kayitlar"].append({
            "id": 100 + i, "servis_form_no": f"G5F{900 + i:05d}", "arayuz": "teknik" if i % 2 == 0 else "iade",
            "stok_kodu": f"FZ-MON-{i}", "stok_adi": f"Fazeon monitör {i}", "urun_grubu": "monitör",
            "seri_no": f"SNX{i:04d}", "firma_bilgisi": "VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI",
            "musteri_adi": f"Müşteri {i}", "mevcut_durum": durum[i % 6], "sonuc_durumu": "sorunsuz" if i == 3 else "",
            "depo": "outlet" if bitti else "", "depo_tarihi": datetime(d.year, d.month, d.day, 9).isoformat() if bitti else "",
            "mal_kabul_tarihi": datetime(d.year, d.month, d.day, 10).isoformat(), "fatura_mevcut": i % 3 != 0,
            "satis_fiyati": 80.0 if durum[i % 6] == "satıldı" else None, "personel": "teknisyen"})


def _ac(monkeypatch, uygulama, anahtar, sayfa, ts=False, ek=None):
    monkeypatch.setenv("DUMAN_ONBELLEK_TEMIZLE", "1")
    import sahte_db
    import ornek_veri
    from streamlit.testing.v1 import AppTest
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    ornek_veri.doldur(sahte_db.TABLOLAR)
    if ts:
        _ts_ek(sahte_db.TABLOLAR)
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = uygulama
    at.session_state[anahtar] = sayfa
    for k, v in (ek or {}).items():
        at.session_state[k] = v
    at.run()
    assert not _sorunlar(at), _sorunlar(at)
    return at


def _anahtarlar(at):
    out = set()
    for kind in ("button", "download_button", "text_input", "multiselect", "toggle", "segmented_control"):
        try:
            out |= {getattr(w, "key", None) for w in getattr(at, kind)}
        except Exception:  # noqa: BLE001 — sürümde olmayan öğe türü
            pass
    return out


def test_satislar_siparis_masasi(monkeypatch):
    at = _ac(monkeypatch, "satis", "satis_sayfa", "📋 Satışlar")
    veri = _bilesen_verisi(at.main, [])
    assert veri, "Satışlar masası çizilmedi"
    v = veri[0]
    assert len(v["satirlar"]) >= 5 and v["tik"] == "ac" and v["grup"]["alan"] == "gun"
    assert [k["k"] for k in v["ozet"]][:3] == ["siparis", "adet", "ciro"]
    assert all({"id", "sno", "firma", "ciro_m"} <= set(r) for r in v["satirlar"])
    assert not any(str(k).startswith("tkb_satir_sat_") for k in _anahtarlar(at)), "eski tıklanır satırlar çizilmemeli"
    a = _anahtarlar(at)
    assert {"sat_ara", "sat_hayalet_btn"} <= a and {"l_dl_xlsx", "l_dl_csv"} <= a     # araç çubuğu + indirme yerinde


def test_satislar_kalem_masasi(monkeypatch):
    at = _ac(monkeypatch, "satis", "satis_sayfa", "📋 Satışlar", ek={"sat_gorunum": "Kalem"})
    veri = _bilesen_verisi(at.main, [])
    assert veri and len(veri[0]["satirlar"]) >= 5 and "bsat_m" in veri[0]["satirlar"][0]
    assert "sat_kalem_tablo" not in _anahtarlar(at)


def test_satis_girisi_son_siparisler_masasi(monkeypatch):
    at = _ac(monkeypatch, "satis", "satis_sayfa", "🧾 Satış Girişi")
    veri = _bilesen_verisi(at.main, [])
    assert veri, "son siparişler masası çizilmedi"
    assert veri[0]["ozet"] == [] and len(veri[0]["satirlar"]) >= 1


def test_iade_kayitlari_masasi(monkeypatch):
    at = _ac(monkeypatch, "satis", "satis_sayfa", "↩️ İade")
    veri = _bilesen_verisi(at.main, [])
    assert veri, "iade kayıtları masası çizilmedi"
    v = veri[-1]
    assert len(v["satirlar"]) >= 5 and v["islemler"][0]["k"] == "sil" and v["grup"]["alan"] == "ay"
    assert not any(str(k).startswith("tkb_satir_iade") for k in _anahtarlar(at))
    assert "btn_sat_miade" in _anahtarlar(at)                                        # manuel iade yerinde


@pytest.mark.parametrize("sayfa, arayuz", [("🔧  Teknik Servis", "teknik"), ("↩️  İade", "iade")])
def test_teknik_servis_listesi_masasi(monkeypatch, sayfa, arayuz):
    at = _ac(monkeypatch, "teknikservis", "ts_sayfa", sayfa, ts=True)
    veri = _bilesen_verisi(at.main, [])
    assert veri, "teknik servis masası çizilmedi"
    v = veri[0]
    assert len(v["satirlar"]) >= 3 and v["gorunumler"][0]["ad"] == "Aktif (bitmemiş)" and v["tik"] == "ac"
    assert all(r["_durum"]["renk"] in ("kirmizi", "amber", "yesil", "silik") for r in v["satirlar"])
    a = _anahtarlar(at)
    assert f"ts_durf_{arayuz}" not in at.session_state and f"ts_depdahil_{arayuz}" in a
    assert f"ts_rapor_{arayuz}" in a


def test_teknik_servis_satira_tiklaninca_kontrol_paneli(monkeypatch):
    """Masa satır tıklaması ts_ekran.sec çağırır; o durumda sayfa bugünkü kontrol panelini çizer."""
    at = _ac(monkeypatch, "teknikservis", "ts_sayfa", "🔧  Teknik Servis", ts=True, ek={"_ts_teknik_secili": 100})
    assert not _bilesen_verisi(at.main, []), "ayrıntı açıkken liste çizilmemeli"
    assert "ts_teknik_geri" in _anahtarlar(at)


def test_depolar_masasi(monkeypatch):
    at = _ac(monkeypatch, "teknikservis", "ts_sayfa", "📦  Depolar", ts=True)
    veri = _bilesen_verisi(at.main, [])
    assert veri, "depolar masası çizilmedi"
    v = veri[0]
    assert len(v["satirlar"]) >= 5 and {k["k"] for k in v["ozet"]} == {"bugun", "hafta", "ay", "aktif", "toplam"}
    assert {i["k"] for i in v["islemler"]} == {"ac", "excel"}            # Toplu sat kalktı (22.10.2026)
    a = _anahtarlar(at)
    assert "depo_excel" in a and "depo_filtre_coklu" in a and "ts_toplu_btn" not in a


# Toplu Satış kaldırıldı (kullanıcı, 22.10.2026: satış Mikro'daki faturadan).
