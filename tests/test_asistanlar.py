# -*- coding: utf-8 -*-
"""Asistanlar (Ekim 2026): Telegram soru-cevap, pazar araştırmacısı, gümrük danışmanı."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from shared import asistan_hesap as H

KOK = Path(__file__).resolve().parent.parent


# ── Telegram ────────────────────────────────────────────────────────
def test_kimlik_ve_komut():
    assert H.kimlik_kullanici({"123": "Ibrahim "}, 123) == "ibrahim"
    assert H.kimlik_kullanici({"123": "ibrahim"}, "999") is None
    assert H.kimlik_kullanici(None, "1") is None
    assert H.komut("/start") == "start" and H.komut("/yardim@KayranBot ek") == "yardim"
    assert H.komut("geçen ay satış") == ""


def test_telegram_yanit_kart_satir_ve_kacis():
    c = {"baslik": "Satış · Eylül 2026", "kartlar": [{"etiket": "Ciro", "deger": "$12.345", "alt": "40 sipariş"}],
         "satirlar": [{"Ürün": f"Monitör <{i}>", "Adet": i, "Ciro ($)": 1234.5} for i in range(12)],
         "kaynak": "satis_pnl", "uyarilar": [], "bos": None, "yetki": None}
    m = H.telegram_yanit(c)
    assert m.startswith("<b>Satış · Eylül 2026</b>")
    assert "Ciro: <b>$12.345</b> <i>(40 sipariş)</i>" in m
    assert "1. Monitör &lt;0&gt; · Adet 0 · Ciro ($) 1.234,50" in m
    assert "10. Monitör &lt;9&gt;" in m and "11. " not in m and "2 satır daha" in m
    assert "Kaynak: satis_pnl" in m


def test_telegram_yanit_yetki_bos_ve_uzunluk():
    assert "yetkiniz yok" in H.telegram_yanit({"baslik": "Ödemeler", "yetki": "Bu modüle yetkiniz yok."})
    assert H.telegram_yanit({"baslik": "Stok", "bos": "Stoğu olan ürün yok."}).endswith("Stoğu olan ürün yok.")
    uzun = {"baslik": "X", "kartlar": [{"etiket": "a" * 500, "deger": "1"}] * 20}
    assert len(H.telegram_yanit(uzun)) <= H.TELEGRAM_SINIR + 2
    assert H.telegram_yanit(None) == ""


def test_yardim_tanimsiz_hesaba_kimligini_soyler():
    m = H.yardim_metni(["a"], 555, None)
    assert "<code>555</code>" in m and "Asistanlar" in m
    assert "Örnekler" in H.yardim_metni(["geçen ay satış"], 555, "ibrahim")


def test_kar_gorunur_kullanici():
    from shared.kar_gizle import kar_gorunur_kullanici
    assert kar_gorunur_kullanici("Ibrahim") and not kar_gorunur_kullanici("depocu")


# ── Telegram betiği (GitHub'da çalışır) ─────────────────────────────
def _betik(monkeypatch, harita, cevap="CEVAP"):
    sys.path.insert(0, str(KOK / "otonom"))
    import telegram_soru as T
    giden = []
    monkeypatch.setattr(T, "ayar", lambda a, v=None: json.dumps(harita) if a == T.KULLANICI_ANAHTAR else v)
    monkeypatch.setattr(T, "gonder", lambda c, m, y=None: giden.append((c, m)))
    monkeypatch.setattr(T, "cevap_uret", lambda metin, kul: f"{cevap}:{kul}:{metin}")
    return T, giden


def test_tanimsiz_hesap_soru_cevap_almaz(monkeypatch):
    T, giden = _betik(monkeypatch, {"1": "ibrahim"})
    T.isle({"chat_id": 9, "kimlik": 777, "metin": "geçen ay ödemeler"})
    assert len(giden) == 1 and "<code>777</code>" in giden[0][1] and "CEVAP" not in giden[0][1]


def test_tanimli_hesap_kendi_kullanicisiyla_cevaplanir(monkeypatch):
    T, giden = _betik(monkeypatch, {"777": "ayse"})
    T.isle({"chat_id": 9, "kimlik": 777, "metin": "geçen ay satış"})
    assert giden == [(9, "CEVAP:ayse:geçen ay satış")]
    T.isle({"chat_id": 9, "kimlik": 777, "metin": "/yardim"})
    assert "Örnekler" in giden[-1][1]


def test_is_akisi_kullanici_metnini_komuta_yazmaz():
    y = (KOK / ".github/workflows/telegram-soru.yml").read_text(encoding="utf-8")
    assert "PAYLOAD: ${{ toJson(github.event.client_payload) }}" in y
    assert "client_payload.metin" not in y and "concurrency:" not in y.split("# concurrency")[0]
    ts = (KOK / "veritabani/fonksiyonlar/telegram-webhook/index.ts").read_text(encoding="utf-8")
    assert "X-Telegram-Bot-Api-Secret-Token" in ts and 'status: 401' in ts


# ── Gümrük danışmanı ────────────────────────────────────────────────
def test_sonuc_dogrula():
    s, h = H.sonuc_dogrula({"gtip": "8528.52.91.00.00", "gtip_aciklama": " monitör ",
                            "oranlar": {"gumruk_vergisi": "0", "ilave_gumruk_vergisi": "%20", "kdv": 20},
                            "belgeler": ["CE", ""], "guven": "Yüksek"})
    assert h == [] and s["gtip"] == "852852910000" and s["oranlar"]["ilave_gumruk_vergisi"] == 20
    assert s["belgeler"] == ["CE"] and s["guven"] == "yüksek" and s["gtip_aciklama"] == "monitör"
    _, h = H.sonuc_dogrula({"gtip": "8528", "oranlar": {"gumruk_vergisi": 140, "kdv": 20}})
    assert any("gtip" in x for x in h) and any("gumruk_vergisi" in x for x in h) and any("ilave" in x for x in h)
    assert H.sonuc_dogrula([])[1]


def test_vergi_hesabi():
    v = H.vergi_hesabi({"birim_fiyat": 100, "adet": 50, "navlun": 400, "sigorta": 100},
                       {"gumruk_vergisi": 4, "ilave_gumruk_vergisi": 20, "kdv": 20})
    # CIF 5.500; GV 220; İGV 1.100; KDV (5.500+220+1.100)·%20 = 1.364
    assert v["cif"] == 5500 and v["gumruk_vergisi"] == 220 and v["ilave_gumruk_vergisi"] == 1100
    assert v["kdv"] == 1364 and v["maliyet_kdv_haric"] == 6820 and v["birim_maliyet_kdv_haric"] == 136.4
    assert H.vergi_hesabi({"birim_fiyat": 100}, {}) is None


def test_gumruk_rutin_ayari_ayri_bolumden():
    from shared.claude_talep import rutin_ayari_coz
    sec = {"gumruk_rutin": {"url": "trig_01Abc", "token": "sk-ant-x"}}
    ayar, sorun = rutin_ayari_coz(sec, bolum="gumruk_rutin")
    assert ayar["url"].endswith("/routines/trig_01Abc/fire") and sorun == ""
    # Talep akışı gümrük bölümünü yanlış yazılmış [claude_rutin] sanmaz
    assert rutin_ayari_coz(sec) == (None, "rutin ayarı yok")


# ── Pazar araştırmacısı ─────────────────────────────────────────────
def test_pazar_ozeti():
    sat = [{"sku": "ab 1", "adet": 2, "birim_satis": 100, "kanal": "D-MARKET"},
           {"sku": "AB1", "adet": 1, "birim_satis": 130, "kanal": "EERA"},
           {"sku": "X9", "adet": 10, "birim_satis": 5, "kanal": "D-MARKET"},
           {"sku": "Y", "adet": 0, "birim_satis": 999}]
    ur = [{"sku": "AB1", "urun_adi": "Monitör 27", "kategori": "Monitör", "marka": "Z", "bizim_stok": 7}]
    o = H.pazar_ozeti(sat, ur)
    assert o["urunler"][0] == {"sku": "ab 1", "ad": "Monitör 27", "kategori": "Monitör", "marka": "Z", "adet": 3,
                               "ciro": 330.0, "ort_fiyat": 110.0, "kanal_sayisi": 2, "stok": 7.0}
    assert [k["kategori"] for k in o["kategoriler"]] == ["Monitör", "Diğer"] and len(o["urunler"]) == 2


def test_brifing_blogu():
    assert H.brifing_blogu([]) == ""
    b = H.brifing_blogu([{"baslik": "6-12 Ekim", "ozet": "Panel fiyatı arttı & navlun düştü"}])
    assert "Pazar raporu · 6-12 Ekim" in b and "&amp;" in b and "Asistanlar" in b


# ── Görev aracı ─────────────────────────────────────────────────────
def test_asistan_db_streamlitsiz_yuklenir_ve_sinirli():
    kod = ("import sys; sys.modules['streamlit'] = None; sys.path.insert(0, 'otonom'); import asistan_db as A\n"
           "import os; os.environ['SUPABASE_URL']='http://x'; os.environ['SUPABASE_KEY']='k'\n"
           "for args in (('PATCH','satislar'), ('GET','kullanici_sifreler'), ('DELETE','gumruk_sorgulari')):\n"
           "    try:\n        A._istek(*args); print('GECTI', args)\n"
           "    except ValueError: pass\n"
           "print('TAMAM')")
    r = subprocess.run([sys.executable, "-c", kod], cwd=KOK, capture_output=True, text=True, timeout=60)
    assert r.stdout.strip() == "TAMAM", r.stdout + r.stderr


@pytest.mark.parametrize("dosya", ["otonom/pazar_gorevi.md", "otonom/gumruk_gorevi.md"])
def test_gorev_talimati_aracla_uyumlu(dosya):
    t = (KOK / dosya).read_text(encoding="utf-8")
    import re
    komutlar = set(re.findall(r"asistan_db\.py ([a-z-]+)", t))
    kaynak = (KOK / "otonom/asistan_db.py").read_text(encoding="utf-8")
    assert komutlar and all(f'k == "{k}"' in kaynak for k in komutlar), komutlar
