# -*- coding: utf-8 -*-
"""Mikro bağlantısı sağlığı (shared/mikro_saglik.py, otonom/mikro_esitle.py, aktarıcı tetiği; Ekim 2026).

Kullanıcı: "Sağlık paneli, Telegram uyarısı ve eşitlemenin aktarımın hemen ardından çalışması."
21.10.2026'nın iki olayı: (1) satış eşitlemesi 16:26–18:51 arası "yeni veri yok" diyerek yazmadı; sebep
yalnız günlükteki "OkumaTutarsiz: kopya kayıt" uyarısındaydı; (2) GitHub'ın saatlik işi kendi zamanında hiç
çalışmadı (02:00'lık gece yedeği her gün 06:51–08:48'de çalışıyor)."""
import importlib.util
import logging
import re
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

S = pytest.importorskip("shared.mikro_saglik")
KOK = Path(__file__).resolve().parent.parent
SIMDI = datetime(2026, 10, 21, 18, 35, tzinfo=timezone.utc)


def _senk(dk_once, hata=None, tablo="mikro_satis_satir"):
    t = (SIMDI - timedelta(minutes=dk_once)).isoformat()
    return {"tablo": tablo, "son_cekim": t, "son_hata": hata, "guncelleme": t}


def _kodlar(s):
    return sorted(x["kod"] for x in s)


def test_aktarici_yaziyorsa_sorun_yok():
    assert S.sorunlar([_senk(9)], [], {"acik": False}, SIMDI) == []


def test_aktarici_45_dakikadir_yazmadiysa_kritik():
    s = S.sorunlar([_senk(50)], [], {}, SIMDI)
    assert _kodlar(s) == ["aktarici_durdu"] and s[0]["seviye"] == S.KRITIK
    assert "50 dk" in s[0]["metin"]
    assert _kodlar(S.sorunlar([], None, {}, SIMDI)) == ["aktarici_yok"]


def test_tablo_okunamadiysa_uyari():
    s = S.sorunlar([_senk(5), _senk(5, "HTTP 500", tablo="mikro_serino")], [], {}, SIMDI)
    assert _kodlar(s) == ["aktarici_hata"] and "mikro_serino" in s[0]["metin"]


def test_21_10_olayi_satis_eşitlemesi_uyari_verip_yazmadi():
    """Son tur: satış 'UYARI OkumaTutarsiz' → koruma devrede sorunu; Mikro'dan gelmiş satış verisi 2 saattir
    satışlara yazılmadı → kritik."""
    tur = [{"ad": "Satış / iade", "durum": "uyari", "metin": "UYARI satis.mikro_esitle.otomatik: OkumaTutarsiz"},
           {"ad": "Depo stoğu", "durum": "yazdi", "metin": "tamam: 0"}]
    satis = {"acik": True, "son_calisma": "2026-10-21T16:26:55+00:00", "son_veri": "2026-10-21T18:26:05+00:00"}
    s = S.sorunlar([_senk(9)], tur, satis, SIMDI + timedelta(minutes=25))
    assert _kodlar(s) == ["esitleme_uyari", "satis_geride"]
    assert "Satış / iade" in next(x for x in s if x["kod"] == "esitleme_uyari")["metin"]
    # yeni gelen veri henüz 30 dakikayı doldurmadıysa "geride" denmez (aktarımdan hemen sonra eşitleme sürüyor)
    assert "satis_geride" not in _kodlar(S.sorunlar([_senk(9)], [], satis, SIMDI))
    # eşitleme kapalıysa satış geride sayılmaz
    assert S.sorunlar([_senk(-170)], [], dict(satis, acik=False), SIMDI + timedelta(hours=3)) == []


def test_eşitleme_hatasi_kritik():
    s = S.sorunlar([_senk(5)], [{"ad": "Gider tablosu", "durum": "hata", "metin": "HATA KeyError"}], {}, SIMDI)
    assert _kodlar(s) == ["esitleme_hata"] and s[0]["seviye"] == S.KRITIK


def test_is_durumu():
    assert [S.is_durumu(m) for m in ("tamam: 3", "yeni veri yok / kapalı", "UYARI x", "HATA y")] == \
        ["yazdi", "yok", "uyari", "hata"]


def test_bildirim_yeni_sorunda_hemen_surerken_6_saatte_bir_duzelince_bir_kez():
    sorun = [{"kod": "aktarici_durdu", "seviye": S.KRITIK, "metin": "Aktarıcı durdu"}]
    m, d = S.bildirim_karari(sorun, {}, SIMDI)
    assert m and "Aktarıcı durdu" in m and "KRİTİK" in m and d["kodlar"] == ["aktarici_durdu"]
    m2, d2 = S.bildirim_karari(sorun, d, SIMDI + timedelta(hours=2))
    assert m2 is None and d2 == d
    m3, _ = S.bildirim_karari(sorun, d, SIMDI + timedelta(hours=6, minutes=1))
    assert m3 and "sürüyor" in m3
    m4, d4 = S.bildirim_karari([], d, SIMDI + timedelta(hours=7))
    assert m4 and "düzeldi" in m4 and d4["kodlar"] == []
    m5, d5 = S.bildirim_karari([], d4, SIMDI + timedelta(hours=8))
    assert m5 is None and d5 == d4
    # hiç sorun olmamışsa durum yazılmaz (her turda ayar yazmasın)
    assert S.bildirim_karari([], {}, SIMDI) == (None, {})


def test_denetle_ve_bildir_telegrama_bir_kez_yazar(monkeypatch):
    ayar, giden, gunluk = {}, [], []
    D = pytest.importorskip("kayranacc.database")
    monkeypatch.setattr(D, "get_ayar", lambda k, v=None: ayar.get(k, v))
    monkeypatch.setattr(D, "set_ayar", lambda k, v: ayar.__setitem__(k, v) or True)
    monkeypatch.setattr(S, "senk_oku", lambda: [_senk(120)])
    monkeypatch.setattr(S, "satis_durumu", lambda: {"acik": False})
    monkeypatch.setattr(S, "gunluk_yaz", lambda *a, **k: gunluk.append(a))
    gonder = lambda m: (giden.append(m), (True, "ok"))[1]   # noqa: E731
    S.denetle_ve_bildir([], simdi=SIMDI, gonder=gonder)
    S.denetle_ve_bildir([], simdi=SIMDI + timedelta(minutes=15), gonder=gonder)
    assert len(giden) == 1 and "veri gelmiyor" in giden[0]
    assert len(gunluk) == 2 and ayar[S.BILDIRIM_ANAHTAR]["kodlar"] == ["aktarici_durdu"]


def _otonom():
    spec = importlib.util.spec_from_file_location("otonom_mikro_esitle_saglik", KOK / "otonom" / "mikro_esitle.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_yutulan_uyari_sonucta_gorunur(monkeypatch):
    """21.10: satış otomatik() kopya okumayı sessiz() ile günlüğe yazıp None döndü; iş 'yeni veri yok' göründü.
    Artık turda yutulan uyarı sonuca 'UYARI …' olarak çıkar (sağlık denetimi bunu sorun sayar)."""
    from shared.kayit import sessiz
    sahte = types.ModuleType("sahte_saglik")

    def uyarili():
        sessiz("satis.mikro_esitle.otomatik", RuntimeError("OkumaTutarsiz: kopya kayıt: 5660"))
        return None
    sahte.uyarili = uyarili
    sahte.bos = lambda: None
    monkeypatch.setitem(sys.modules, "sahte_saglik", sahte)
    logging.getLogger("kayran").setLevel(logging.WARNING)
    out = _otonom().calistir((("Satış", "sahte_saglik", "uyarili"), ("Boş", "sahte_saglik", "bos")))
    assert out[0][1].startswith("UYARI") and "OkumaTutarsiz" in out[0][1]
    assert out[1] == ("Boş", "yeni veri yok / kapalı")


def _aktarici(monkeypatch):
    if importlib.util.find_spec("requests") is None:          # CI'da requests yok: aktarıcı yalnız içe aktarılır
        sahte = types.ModuleType("requests")
        sahte.Session = object
        sahte.Response = object
        sahte.RequestException = Exception
        monkeypatch.setitem(sys.modules, "requests", sahte)
    spec = importlib.util.spec_from_file_location("mikro_kayran_saglik",
                                                  KOK / "araclar" / "mikro_aktarici" / "mikro_kayran.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_aktarici_yeni_veri_gelince_eşitlemeyi_baslatir(monkeypatch):
    mk = _aktarici(monkeypatch)
    assert mk.tetik_nedeni({"mikro_satis_satir": 0, "mikro_siparis": 0}, False) == ""
    assert mk.tetik_nedeni({"mikro_satis_satir": 3, "mikro_siparis": 0}, False) == "yeni_veri:mikro_satis_satir"
    assert mk.tetik_nedeni({}, True) == "tam_aktarim"
    kod = (KOK / "araclar" / "mikro_aktarici" / "mikro_kayran.py").read_text(encoding="utf-8")
    bir_kez = kod[kod.index("if args.bir_kez:"):kod.index("tam = args.tam")]
    assert "sb.esitlemeyi_baslat(neden)" in bir_kez
    assert "/mikro-tetik" in kod
    assert not re.search(mk.YAZAN_UC_DESENI, kod)


def test_tetik_zinciri_ayni_olay_adini_kullanir():
    """aktarıcı → mikro-tetik (repository_dispatch: mikro_esitle) → iş akışı; zamanlayıcı → kontrol modu."""
    is_akisi = (KOK / ".github" / "workflows" / "mikro-esitle.yml").read_text(encoding="utf-8")
    fonk = (KOK / "veritabani" / "fonksiyonlar" / "mikro-tetik" / "index.ts").read_text(encoding="utf-8")
    sql = (KOK / "veritabani" / "49_mikro_saglik.sql").read_text(encoding="utf-8")
    assert "repository_dispatch:" in is_akisi and "types: [mikro_esitle]" in is_akisi
    assert 'event_type: "mikro_esitle"' in fonk
    assert "TELEGRAM_BOT_TOKEN" in is_akisi and "TELEGRAM_CHAT_ID" in is_akisi
    assert "cagiranYetkili" in fonk and 'mod === "kontrol"' in fonk
    assert "functions/v1/mikro-tetik" in sql and '"mod": "kontrol"' in sql and "cron.schedule" in sql
    # GitHub'ın zamanlayıcısı yalnız yedek: saatlik değil
    assert '"14 * * * *"' not in is_akisi


def test_sayfa_sistem_menusunde():
    from shared.gezinme import SISTEM, sayfa_grubu
    assert "mikro_baglanti" in {k for k, *_ in SISTEM}
    assert "mikro_baglanti" in [k for k, _ in sayfa_grubu("mikro_baglanti")[1]]
    app = (KOK / "app.py").read_text(encoding="utf-8")
    assert 'elif aktif == "mikro_baglanti":' in app
