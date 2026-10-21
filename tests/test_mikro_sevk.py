# -*- coding: utf-8 -*-
"""Depolar arası sevk Mikro'dan (depo/mikro_sevk.py, depo/main.py:_sayfa_sevk — Ekim 2026).

Sorun: Depo stoğu Mikro'dan otomatik yazılıyor (kayranpm.mikro_stok). Depo › Sevk formu yine kendi sevk kaydını
yazıyordu; bir sonraki eşitleme depo kırılımını Mikro'nun rakamıyla baştan yazınca uygulamadaki sevk sessizce
kayboluyordu. Eşitleme açıkken form kayıt yapmaz; sevk geçmişi mikro_depo_hareket'ten (sth_tip 2) gelir.
Depo numaraları ve adları canlıdaki gibi (mikro_depo_kart 21.10.2026)."""
import types

import pytest

DEPOLAR = {1: "Merkez depo", 2: "ASEL DEPO", 3: "SERVİS DEPO", 4: "HAPPY LİFE", 5: "OUTLET", 6: "İKİNCİ EL DEPO",
           7: "PAZARLAMA", 8: "ALY ANTREPO ", 9: "İADE DEPO "}


def _h(guid, tarih, tip, miktar, giris=0, cikis=0, sku="Fazeon X24F165S", sira=204, cins=6, iptal=False):
    return {"sth_guid": guid, "sth_tarih": f"{tarih}T00:00:00", "sth_tip": tip, "sth_cins": cins,
            "sth_evraktip": 2, "sth_normal_iade": 0, "sth_evrakno_seri": None, "sth_evrakno_sira": sira,
            "sth_stok_kod": sku, "sth_miktar": miktar, "sth_giris_depo_no": giris, "sth_cikis_depo_no": cikis,
            "sth_exim_kodu": None, "sth_iptal": iptal}


# ── Sayfa: açıkken form kaydetmez ──────────────────────────────────
class _Rerun(Exception):
    pass


class _St:
    """_sayfa_sevk'in kullandığı Streamlit yüzeyi: "Tümünü Sevk Et" düğmesine basılmış gibi."""
    def __init__(self, ss):
        self.session_state = ss
        self.cache_data = types.SimpleNamespace(clear=lambda: None)
        self.yazilan = []

    def columns(self, spec, **k):
        return [self] * (spec if isinstance(spec, int) else len(spec))

    def selectbox(self, label, options, **k):
        return list(options)[0]

    def button(self, label, key=None, **k):
        return key == "dpo_sevk_hepsi"

    def number_input(self, *a, value=1, **k):
        return value

    def text_input(self, *a, **k):
        return ""

    def date_input(self, *a, value=None, **k):
        return value

    def rerun(self):
        raise _Rerun()

    def container(self):
        return self

    def info(self, m, *a, **k):
        self.yazilan.append(("info", m))

    def warning(self, m, *a, **k):
        self.yazilan.append(("warning", m))

    def __getattr__(self, ad):
        return lambda *a, **k: None


def _sayfa(monkeypatch, mikro_acik):
    import depo.main as M
    import kayranpm.mikro_stok as MS
    sevkler, ekran = [], []
    st = _St({"_dpo_sepet_kaynak": "MERKEZ DEPO", "aktif_kullanici": "test",
              "dpo_sepet": [{"sku": "X24F165S", "urun_adi": "MONITOR", "adet": 2}]})
    monkeypatch.setattr(M, "st", st)
    monkeypatch.setattr(M, "_baslik", lambda *a: None)
    monkeypatch.setattr(MS, "acik_mi", lambda: mikro_acik)
    monkeypatch.setattr(M, "get_depo_ozet", lambda: [{"depo": "MERKEZ DEPO", "adet": 5}])
    monkeypatch.setattr(M, "get_depo_listesi", lambda: ["MERKEZ DEPO", "HAPPY LIFE"])
    monkeypatch.setattr(M, "get_depo_stok", lambda d: [{"sku": "X24F165S", "urun_adi": "MONITOR", "adet": 5}])
    monkeypatch.setattr(M, "get_depo_sevk_gecmisi", lambda n=50: [])
    monkeypatch.setattr(M, "depo_sevk", lambda *a, **k: sevkler.append(a) or (True, "ok"))
    try:                                     # eski kodda modül yok: sayfa formu çizer
        import depo.mikro_sevk as MSV
        monkeypatch.setattr(MSV, "ekran", lambda: ekran.append(1))
    except ImportError:
        pass
    try:
        M._sayfa_sevk()
    except _Rerun:
        pass
    return sevkler, ekran, st


def test_mikro_esitlemesi_acikken_sevk_formu_kayit_yapmaz(monkeypatch):
    sevkler, ekran, st = _sayfa(monkeypatch, mikro_acik=True)
    assert sevkler == [], "Mikro eşitlemesi açıkken uygulamada sevk kaydı yapıldı (bir sonraki eşitleme ezer)"
    assert ekran == [1]                      # yerine Mikro bilgisi + Mikro'daki sevk geçmişi
    assert st.session_state["dpo_sepet"] == [{"sku": "X24F165S", "urun_adi": "MONITOR", "adet": 2}]


def test_mikro_esitlemesi_kapaliyken_eski_davranis(monkeypatch):
    sevkler, ekran, st = _sayfa(monkeypatch, mikro_acik=False)
    assert sevkler == [("X24F165S", "MERKEZ DEPO", "HAPPY LIFE", 2, "test")]
    assert ekran == [] and st.session_state["dpo_sepet"] == []


def test_kayit_serbest():
    from depo.mikro_sevk import kayit_serbest
    assert kayit_serbest(False) is True and kayit_serbest(True) is False


# ── Mikro sevk satırı → görünüm satırı ─────────────────────────────
def test_mikro_sevk_satiri_gorunum_satirina():
    from depo.mikro_sevk import sevk_satirlari
    satir = [
        _h("a1", "2026-10-12", 2, 1, giris=5, cikis=3),                              # SERVİS → OUTLET
        _h("a2", "2026-10-20", 2, 1, giris=4, cikis=9, sku="X24F182S", sira=208),    # İADE → HAPPY LİFE
        _h("a3", "2026-10-13", 1, 7, cikis=1, sira=11, cins=0),                      # satış çıkışı: sevk değil
        _h("a4", "2026-10-14", 0, 9, giris=1, sira=12, cins=12),                     # ithalat girişi: sevk değil
        _h("a5", "2026-10-15", 2, 4, giris=4, cikis=1, iptal=True),                  # iptal edilmiş sevk
        _h("a6", "2026-10-15", 2, 4, giris=4, cikis=1, cins=9),                      # değer farkı
    ]
    adlar = {"X24F165S": "FAZEON 24 INÇ MONITÖR"}
    r = sevk_satirlari(satir, DEPOLAR, adlar.get)
    assert r == [
        {"tarih": "2026-10-20", "evrak": "208", "sku": "X24F182S", "urun": "", "adet": 1.0,
         "cikis": "İADE DEPO", "giris": "HAPPY LIFE"},
        {"tarih": "2026-10-12", "evrak": "204", "sku": "X24F165S", "urun": "FAZEON 24 INÇ MONITÖR", "adet": 1.0,
         "cikis": "TEKNİK DEPO", "giris": "OUTLET DEPO"},
    ]


def test_ozet_ve_mikro_oncesi_uygulama_kayitlari():
    from depo.mikro_sevk import ozet, eski_uygulama_kayitlari
    o = ozet([{"tarih": "2026-10-20", "evrak": "208", "adet": 1.0}, {"tarih": "2026-10-12", "evrak": "204", "adet": 3.0},
              {"tarih": "2026-10-12", "evrak": "204", "adet": 2.0}])
    assert o == {"kalem": 3, "adet": 6.0, "evrak": 2, "ilk": "2026-10-12", "son": "2026-10-20"}
    gec = [{"id": 1, "tarih": "03.07.2025 14:16", "sevk_tarihi": None}, {"id": 2, "sevk_tarihi": "2026-10-20"},
           {"id": 3, "tarih": "2025-03-01T10:00:00"}]
    assert [g["id"] for g in eski_uygulama_kayitlari(gec, "2025-04-04")] == [3]
    assert [g["id"] for g in eski_uygulama_kayitlari(gec, "2025-08-01")] == [1, 3]
    assert [g["id"] for g in eski_uygulama_kayitlari(gec, "")] == [1, 2, 3]       # Mikro'da sevk yok


# ── Okuma: sıralı ve kopya denetimli ───────────────────────────────
class _Q:
    def __init__(self, cli, t):
        self.cli, self.t = cli, t
        cli.zincir.setdefault(t, [])

    def __getattr__(self, ad):
        def f(*a, **k):
            self.cli.zincir[self.t].append((ad,) + a)
            return self
        return f

    def execute(self):
        return types.SimpleNamespace(data=list(self.cli.db.get(self.t, [])))


class _Cli:
    def __init__(self, db):
        self.db, self.zincir = db, {}

    def table(self, t):
        return _Q(self, t)


def test_okuma_sirali_ve_yalniz_sevk():
    from depo.mikro_sevk import sevk_oku
    cli = _Cli({"mikro_depo_hareket": [_h("a1", "2026-10-12", 2, 1, giris=5, cikis=3)],
                "mikro_depo_kart": [{"dep_no": 3, "dep_adi": "SERVİS DEPO"}]})
    satir, depo = sevk_oku(cli)
    assert len(satir) == 1 and depo == {3: "SERVİS DEPO"}
    z = cli.zincir["mikro_depo_hareket"]
    assert ("eq", "sth_tip", 2) in z and ("order", "sth_guid") in z


def test_kopya_okuma_reddedilir():
    from depo.mikro_sevk import sevk_oku
    from satis.mikro_esitle import OkumaTutarsiz
    a = _h("a1", "2026-10-12", 2, 1, giris=5, cikis=3)
    cli = _Cli({"mikro_depo_hareket": [a, dict(a)], "mikro_depo_kart": []})
    with pytest.raises(OkumaTutarsiz):
        sevk_oku(cli)


def test_ekran_tutarsiz_okumada_liste_gostermez(monkeypatch):
    import depo.mikro_sevk as MSV
    import shared.masa_liste as ML
    from satis.mikro_esitle import OkumaTutarsiz
    st = _St({})
    monkeypatch.setitem(__import__("sys").modules, "streamlit", st)
    cizilen = []
    monkeypatch.setattr(ML, "ciz", lambda *a, **k: cizilen.append(a))

    def _tutarsiz():
        raise OkumaTutarsiz("kopya kayıt: a1")
    monkeypatch.setattr(MSV, "sevk_gecmisi", _tutarsiz)
    MSV.ekran()
    assert cizilen == []
    assert [t for t, _ in st.yazilan] == ["info", "warning"] and "tutarlı okunamadı" in st.yazilan[1][1]
