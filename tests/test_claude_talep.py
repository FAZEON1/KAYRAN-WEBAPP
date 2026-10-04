# -*- coding: utf-8 -*-
"""Talepten Claude'a onaylı geliştirme akışı (Ekim 2026, seçenek A: tek onay).

Onaycı "Claude'a gönder" der → zamanlanmış Claude görevi kodlar, "Talep #<id>: ..." başlıklı PR açar
→ iş akışı talebi günceller, mail atar (PR hazır → onaycı; yayında → talep sahibi).
"""
from datetime import datetime
from pathlib import Path

import shared.claude_talep as C

KOK = Path(__file__).resolve().parent.parent
SIMDI = datetime(2026, 10, 5, 10, 0)


class _Tablo:
    def __init__(self, db, hata=None):
        self.db, self.hata, self._g, self._id = db, hata, None, None

    def select(self, *_):
        return self

    def update(self, g):
        self._g = g
        return self

    def eq(self, _a, v):
        self._id = v
        return self

    def execute(self):
        if self.hata:
            raise self.hata
        if self._g is not None:
            self.db.guncel.append((self._id, dict(self._g)))
            self.db.satirlar.get(self._id, {}).update(self._g)
            return type("R", (), {"data": []})()
        return type("R", (), {"data": [dict(self.db.satirlar[self._id])] if self._id in self.db.satirlar else []})()


class _Db:
    def __init__(self, satirlar=None, hata=None):
        self.satirlar, self.hata, self.guncel = satirlar or {}, hata, []

    def table(self, ad):
        assert ad == "talepler"
        return _Tablo(self, self.hata)


def test_yalniz_onayci_gonderir():
    assert C.onaylayabilir_mi("ibrahim") and C.onaylayabilir_mi(" Ibrahim ")
    assert not C.onaylayabilir_mi("serkan") and not C.onaylayabilir_mi("")
    assert C.onaylayabilir_mi("serkan", lambda k, ad: k == "serkan" and ad == "claude_onay")
    assert not C.onaylayabilir_mi("serkan", lambda k, ad: 1 / 0)


def test_hangi_durumda_yeniden_gonderilir():
    for d in (None, "", "soru", "hata", "kapandi"):
        assert C.gonderilebilir_mi({"claude_durum": d}), d
    for d in ("onaylandi", "calisiyor", "pr_hazir", "yayinda"):
        assert not C.gonderilebilir_mi({"claude_durum": d}), d
    assert C.etiket({}) == "" and C.etiket({"claude_durum": "pr_hazir"}) == "PR hazır, onay bekliyor"


def test_onaya_gonder_kaydi_ve_sql_eksik_uyarisi():
    db = _Db({7: {"id": 7}})
    ok, _ = C.onaya_gonder(db, 7, "Ibrahim", "  yalnız satışta  ", SIMDI)
    assert ok and db.guncel == [(7, {"claude_durum": "onaylandi", "claude_onay_notu": "yalnız satışta",
                                     "claude_onaylayan": "ibrahim", "claude_onay_tarihi": SIMDI.isoformat(),
                                     "claude_guncelleme": SIMDI.isoformat(), "claude_not": "",
                                     "durum": "inceleniyor"})]
    ok, msj = C.onaya_gonder(_Db(hata=Exception("column talepler.claude_durum does not exist")), 7, "ibrahim", "",
                             SIMDI)
    assert not ok and "19_talep_claude.sql" in msj


def test_pr_basligindan_talep_ve_durum_gecisleri():
    assert C.baslik_talep_id("Talep #42: Satış filtresi") == 42
    assert C.baslik_talep_id("talep # 7 - x") == 7 and C.baslik_talep_id("Haftalık mail") is None
    u = "https://github.com/x/y/pull/1"
    assert C.pr_guncellemesi("opened", False, u, SIMDI)["claude_durum"] == "pr_hazir"
    b = C.pr_guncellemesi("closed", True, u, SIMDI)
    assert b["claude_durum"] == "yayinda" and b["durum"] == "tamamlandi"
    assert C.pr_guncellemesi("closed", False, u, SIMDI)["claude_durum"] == "kapandi"
    assert C.pr_guncellemesi("synchronize", False, u, SIMDI) is None


def test_mail_alicilari():
    t = {"id": 5, "konu": "Filtre", "gonderen": "Serkan", "claude_onaylayan": "ibrahim"}
    assert [m[0] for m in C.pr_mailleri(t, "pr_hazir", "u")] == ["ibrahim"]
    assert [m[0] for m in C.pr_mailleri(t, "yayinda", "u")] == ["serkan", "ibrahim"]
    assert [m[0] for m in C.pr_mailleri(dict(t, gonderen="Ibrahim"), "yayinda", "u")] == ["ibrahim"]
    assert [m[0] for m in C.pr_mailleri(t, "kapandi", "u")] == ["ibrahim"]


def _betik(monkeypatch, db, olay, birlesti, baslik="Talep #5: Filtre"):
    import shared.eposta as E
    import shared.utils as U
    import kayranpm.database as K
    import otonom.talep_pr as T
    giden = []
    monkeypatch.setattr(K, "get_client", lambda: db)
    monkeypatch.setattr(U, "tr_now", lambda: SIMDI)
    monkeypatch.setattr(E, "ayarlar", lambda: {"host": "h", "port": 587, "user": "u", "pass": "p"})
    monkeypatch.setattr(E, "adresler", lambda: {"ibrahim": "i@g5f.com", "serkan": "s@g5f.com"})
    monkeypatch.setattr(E, "gonder", lambda a, k, h, cc=None, ekler=None: (giden.append((a[0], k)), (True, "ok"))[1])
    for k, v in {"PR_BASLIK": baslik, "PR_OLAY": olay, "PR_BIRLESTI": birlesti,
                 "PR_URL": "https://github.com/x/y/pull/9"}.items():
        monkeypatch.setenv(k, v)
    T.main()
    return giden


def test_betik_pr_acilinca_ve_birlesince(monkeypatch):
    db = _Db({5: {"id": 5, "konu": "Filtre", "gonderen": "Serkan", "claude_onaylayan": "ibrahim",
                  "claude_durum": "calisiyor"}})
    g = _betik(monkeypatch, db, "opened", "false")
    assert db.satirlar[5]["claude_durum"] == "pr_hazir" and db.satirlar[5]["claude_pr_url"].endswith("/9")
    assert g == [("i@g5f.com", "[KAYRAN Talep] PR hazır · Filtre")]
    g = _betik(monkeypatch, db, "closed", "true")
    assert db.satirlar[5]["claude_durum"] == "yayinda" and db.satirlar[5]["durum"] == "tamamlandi"
    assert [x[0] for x in g] == ["s@g5f.com", "i@g5f.com"]


def test_betik_talep_basligi_yoksa_dokunmaz(monkeypatch):
    db = _Db({5: {"id": 5}})
    assert _betik(monkeypatch, db, "opened", "false", baslik="Haftalık yaşlı stok maili") == []
    assert db.guncel == []


def test_is_akisi_talimat_ve_ekran():
    w = (KOK / ".github" / "workflows" / "talep-pr.yml").read_text(encoding="utf-8")
    assert "python otonom/talep_pr.py" in w and "contains(github.event.pull_request.title, 'Talep #')" in w
    assert "PR_BASLIK: ${{ github.event.pull_request.title }}" in w and "ref: main" in w
    g = (KOK / "otonom" / "claude_talep_gorevi.md").read_text(encoding="utf-8")
    for kural in ("Talep #<id>: <kısa konu>", "claude_durum='calisiyor'", "Rakam değiştiren",
                  "main'e push", "Onaylı talep yok."):
        assert kural in g, kural
    a = (KOK / "app.py").read_text(encoding="utf-8")
    assert "_claude_bolumu(_t, _kul)" in a and "C.onaylayabilir_mi(kul, ozel_yetki)" in a
    s = (KOK / "veritabani" / "19_talep_claude.sql").read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS claude_durum" in s and "claude_pr_url" in s
