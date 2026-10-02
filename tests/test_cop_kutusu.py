# -*- coding: utf-8 -*-
"""Çöp kutusu (Ekim 2026): silinen kayıtlar 30 gün saklanır, tek tıkla geri alınır.

Merkezi sarmalayıcı (shared/audit.py) her silmede, Supabase'in döndürdüğü silinen
satırları cop_kutusu tablosuna yazar. Birleştirme ve sil-yeniden-yaz işlemleri
(Excel yeniden yüklemeleri vb.) `with cop_kutusu_kapali():` ile dışarıda tutulur —
yoksa kutu her yüklemede dolar, geri alınınca veri ikilenirdi.
"""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


class _Y:
    def __init__(self, data):
        self.data = data


class _Q:
    def __init__(self, sb, t):
        self.sb, self.t, self.op, self.v, self.f = sb, t, "select", None, []

    def __getattr__(self, n):
        return lambda *a, **k: self

    def select(self, *a, **k):
        self.op = "select"
        return self

    def insert(self, v):
        self.op, self.v = "insert", v
        return self

    def update(self, v):
        self.op, self.v = "update", v
        return self

    def delete(self, *a, **k):
        self.op = "delete"
        return self

    def eq(self, a, v):
        self.f.append((a, v))
        return self

    def in_(self, a, vs):
        self.f.append((a, ("IN", list(vs))))
        return self

    def _uy(self, r):
        for a, v in self.f:
            if isinstance(v, tuple) and v and v[0] == "IN":
                if r.get(a) not in v[1]:
                    return False
            elif r.get(a) != v:
                return False
        return True

    def execute(self):
        rows = self.sb.db.setdefault(self.t, [])
        if self.op == "insert":
            yeni = self.v if isinstance(self.v, list) else [self.v]
            for r in yeni:
                if "id" in r and any(x.get("id") == r["id"] for x in rows):
                    raise RuntimeError("duplicate key value violates unique constraint")
            rows.extend(dict(r) for r in yeni)
            self.sb.log.append(("insert", self.t, len(yeni)))
            return _Y(yeni)
        if self.op == "delete":
            sil = [r for r in rows if self._uy(r)]
            self.sb.db[self.t] = [r for r in rows if not self._uy(r)]
            return _Y(sil)
        if self.op == "update":
            for r in rows:
                if self._uy(r):
                    r.update(self.v)
            return _Y([])
        return _Y([dict(r) for r in rows if self._uy(r)])


class _SB:
    def __init__(self, db=None):
        self.db, self.log = db or {}, []

    def table(self, t):
        return _Q(self, t)


def _baglan(monkeypatch, db=None):
    from shared import cop_kutusu as C
    from shared import audit as A
    sb = _SB(db)
    monkeypatch.setattr(C, "_ham", lambda: sb)
    monkeypatch.setattr(A, "_aktif_kullanici", lambda: "serdar")
    monkeypatch.setattr(A, "log_yaz", lambda *a, **k: None)
    monkeypatch.setattr(A, "salt_okur_mu", lambda: False)
    return sb, A.wrap_client(sb, "Muhasebe")


# ── Saklama ─────────────────────────────────────────────────────────
def test_silme_cop_kutusuna_yazilir(monkeypatch):
    sb, cli = _baglan(monkeypatch, {"odemeler": [{"id": 7, "firma": "ACME", "tutar": 1500}]})
    cli.table("odemeler").delete().eq("id", 7).execute()
    assert sb.db["odemeler"] == []
    k = sb.db["cop_kutusu"]
    assert len(k) == 1 and k[0]["tablo"] == "odemeler" and k[0]["silen"] == "serdar"
    assert k[0]["satirlar"] == [{"id": 7, "firma": "ACME", "tutar": 1500}] and k[0]["adet"] == 1


def test_kapali_blokta_ve_haric_tabloda_yazilmaz(monkeypatch):
    from shared.cop_kutusu import cop_kutusu_kapali
    sb, cli = _baglan(monkeypatch, {"firma_stok": [{"id": 1}], "aktif_excel_verileri": [{"id": 2}]})
    with cop_kutusu_kapali():
        cli.table("firma_stok").delete().eq("id", 1).execute()
    cli.table("aktif_excel_verileri").delete().eq("id", 2).execute()
    assert not sb.db.get("cop_kutusu")


def test_cop_kutusu_hatasi_silmeyi_engellemez(monkeypatch):
    from shared import cop_kutusu as C
    sb, cli = _baglan(monkeypatch, {"odemeler": [{"id": 7}]})
    monkeypatch.setattr(C, "_ham", lambda: (_ for _ in ()).throw(RuntimeError("tablo yok")))
    cli.table("odemeler").delete().eq("id", 7).execute()
    assert sb.db["odemeler"] == []


def test_buyuk_silme_parcalanir(monkeypatch):
    sb, cli = _baglan(monkeypatch, {"firma_stok": [{"id": i} for i in range(1200)]})
    cli.table("firma_stok").delete().eq("x", None).execute()
    k = sb.db["cop_kutusu"]
    assert [x["adet"] for x in k] == [500, 500, 200] and len({x["grup"] for x in k}) == 1


# ── Gruplama ve geri alma ───────────────────────────────────────────
def _kayit(id_, tablo, sn, satirlar, silen="serdar"):
    z = datetime(2026, 10, 2, 14, 5, 0, tzinfo=timezone.utc) + timedelta(seconds=sn)
    return {"id": id_, "grup": f"g{id_}", "tablo": tablo, "modul": "Teknik Servis", "silen": silen,
            "zaman": z.isoformat(), "adet": len(satirlar), "satirlar": satirlar, "geri_alindi": False}


def test_islemlere_grupla():
    from shared.cop_kutusu import islemlere_grupla
    k = [_kayit(1, "ts_gecmis", 0, [{"id": 11, "kayit_id": 5}, {"id": 12, "kayit_id": 5}]),
         _kayit(2, "ts_kayitlar", 1, [{"id": 5, "servis_form_no": "G5F00058"}]),
         _kayit(3, "odemeler", 300, [{"id": 7}]),
         _kayit(4, "odemeler", 2, [{"id": 8}], silen="gokhan")]
    g = islemlere_grupla(k)
    assert len(g) == 3
    ts = next(x for x in g if "ts_kayitlar" in x["tablolar"])
    assert [p["id"] for p in ts["parcalar"]] == [1, 2] and ts["adet"] == 3


def test_geri_al_ters_sirada_ve_isaretler(monkeypatch):
    from shared import cop_kutusu as C
    sb = _SB({"cop_kutusu": [_kayit(1, "ts_gecmis", 0, [{"id": 11, "kayit_id": 5}]),
                             _kayit(2, "ts_kayitlar", 1, [{"id": 5}])]})
    monkeypatch.setattr(C, "_ham", lambda: sb)
    islem = C.islemlere_grupla(sb.db["cop_kutusu"])[0]
    ok, mesaj = C.geri_al(islem, "ibrahim")
    assert ok, mesaj
    assert [x[1] for x in sb.log if x[0] == "insert"] == ["ts_kayitlar", "ts_gecmis"]   # önce ana kayıt
    assert all(r["geri_alindi"] for r in sb.db["cop_kutusu"])


def test_geri_al_cakisma_ustune_yazmaz(monkeypatch):
    from shared import cop_kutusu as C
    sb = _SB({"odemeler": [{"id": 7, "firma": "YENİ"}], "cop_kutusu": [_kayit(1, "odemeler", 0, [{"id": 7, "firma": "ESKİ"}])]})
    monkeypatch.setattr(C, "_ham", lambda: sb)
    ok, mesaj = C.geri_al(C.islemlere_grupla(sb.db["cop_kutusu"])[0], "ibrahim")
    assert not ok and "zaten" in mesaj and sb.db["odemeler"] == [{"id": 7, "firma": "YENİ"}]
    assert sb.db["cop_kutusu"][0]["geri_alindi"] is False


def test_ozet_ve_kalan_gun():
    from shared.cop_kutusu import ozet, kalan_gun
    assert "G5F00058" in ozet("ts_kayitlar", [{"id": 5, "servis_form_no": "G5F00058"}])
    assert "ACME" in ozet("odemeler", [{"id": 7, "firma": "ACME", "tutar": 1500}])
    assert ozet("odemeler", [{"id": i} for i in range(4)]).startswith("4 satır")
    z = datetime(2026, 10, 2, tzinfo=timezone.utc).isoformat()
    assert kalan_gun(z, datetime(2026, 10, 12, tzinfo=timezone.utc)) == 20


# ── Kapsam: hangi silmeler dışarıda ─────────────────────────────────
HARIC = [("satis/database.py", "def ice_aktar_iadeler("), ("depo/main.py", "def hl_kaydet("),
         ("ithalat/database.py", "def ekle_dosya("), ("ithalat/database.py", "def guncelle_dosya("),
         ("kayranpm/excel_islemler.py", "def excel_yukle_haftalik_stok_satis("),
         ("kayranpm/database.py", "def sku_fazeon_temizle_uygula("),
         ("kayranpm/database.py", "def mukerrer_sku_birlestir("),
         ("kayranpm/ref_no.py", "def butce_excel_ice_aktar("),
         ("kayranacc/edefter.py", "def edf_donem_kilit_ac("), ("kayranacc/edefter.py", "def edf_fis_ekle("),
         ("kayranacc/edefter.py", "def edf_ayar_kaydet("), ("kayranacc/database.py", "def cek_ekle_bulk("),
         ("kayranpm/database.py", "def upsert_firma_stok("), ("kayranpm/ref_no.py", "def _senkronize_firmalar(")]
DAHIL = [("satis/database.py", "def sil_satis("), ("kayranacc/database.py", "def odeme_sil("),
         ("teknikservis/database.py", "def sil_kayit("), ("ithalat/database.py", "def sil_dosya("),
         ("kayranpm/database.py", "def sil_firma_stok_tarihi("), ("hesap_makinesi/main.py", "def prim_sil(")]


def _govde(y, bas):
    s = _oku(y)
    g = s[s.index(bas):]
    m = re.search(r"\n(def |class |@)", g[1:])
    return g[:m.start() + 1] if m else g


def test_birlestirme_ve_yeniden_yazma_disarida():
    for y, fn in HARIC:
        g = _govde(y, fn)
        if ".delete()" in g:
            assert "cop_kutusu_kapali()" in g, (y, fn)


def test_kullanici_silmeleri_iceride():
    for y, fn in DAHIL:
        assert "cop_kutusu_kapali" not in _govde(y, fn), (y, fn)


def test_sql_yedek_ve_sayfa():
    s = _oku("veritabani/09_cop_kutusu.sql")
    assert "CREATE TABLE IF NOT EXISTS cop_kutusu" in s and re.search(r"satirlar\s+jsonb", s)
    import yonetim as Y
    assert "cop_kutusu" in Y.YEDEK_HARIC
    a = _oku("app.py")
    assert '"cop_kutusu"' in a and "from shared.cop_kutusu import sayfa" in a
    c = _oku("shared/cop_kutusu.py")
    assert "silen=None if yonetici else" in c                         # herkes kendi sildiğini görür


def test_ref_butce_kaydet_sil_hata_tanimli():
    """Ref No bütçe düzenlemede _sil_hata hiç oluşturulmuyordu: her kaydetmede NameError
    (silme akışını incelerken pyflakes yakaladı)."""
    s = _oku("kayranpm/ref_no.py")
    g = s[s.index('key=f"butce_save_{fid}"'):]
    g = g[:g.index("st.rerun()")]
    assert g.index("_sil_hata = []") < g.index("not _sil_hata") and "_sil_hata.append(" in g


def test_zaman_istanbul_saatiyle():
    from shared.cop_kutusu import yerel_zaman
    assert yerel_zaman("2026-10-02T13:19:00+00:00") == "02.10.2026 16:19"     # UTC+3
    assert yerel_zaman("2026-10-01T22:30:00+00:00") == "02.10.2026 01:30"     # gün de değişir
