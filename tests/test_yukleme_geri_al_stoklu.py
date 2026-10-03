# -*- coding: utf-8 -*-
"""Stok değiştiren yüklemelerin geri alınması (Ekim 2026; shared/yukleme_gecmisi.py,
veritabani/14_yukleme_satir_geri_al.sql).

Sipariş Excel'i, Mikro dökümü, iade Excel'i, G5F sayımı, teknik servis toplu mal kabul ve İthalat
satın alma raporu artık geri alınabilir: satırlar tek veritabanı işleminde, stok etkisi yüklemenin
koduyla işaretli hareketlerden ürün + depo bazında TERS uygulanarak. Stok adımı yarıda kalırsa
'Tekrar dene' yalnız kalanı uygular. Sonradan işlem görmüş kayıt (servis kaydı, masraf girilmiş
ithalat dosyası) varsa geri alma engellenir.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import shared.stok_defteri as SD
import shared.yukleme_gecmisi as Y

KOK = Path(__file__).resolve().parent.parent


# ── Kayit: bağlam, geri alınabilirlik ───────────────────────────────
def test_stok_baglami_aktif_kaydi_ve_stok_kodunu_kurar():
    k = Y.Kayit("siparis_excel", "s.xlsx")
    assert Y.aktif() is None and SD.aktif_yukleme() == ""
    with k.stok():
        assert Y.aktif() is k and SD.aktif_yukleme() == k.kod
    assert Y.aktif() is None and SD.aktif_yukleme() == ""


def test_stok_baglami_hatada_da_kapanir():
    k = Y.Kayit("g5f_sayim")
    with pytest.raises(RuntimeError):
        with k.stok():
            raise RuntimeError("x")
    assert Y.aktif() is None and SD.aktif_yukleme() == ""


def test_stoklu_tur_satirsiz_da_geri_alinabilir():
    assert Y.Kayit("g5f_sayim").geri_alinabilir                 # yalnız stok etkisi var
    assert Y.Kayit("siparis_excel").geri_alinabilir
    assert not Y.Kayit("havuz_butce").geri_alinabilir           # satırsız, stoksuz → geri alacak bir şey yok
    assert not Y.Kayit("ref_excel").geri_alinabilir
    k = Y.Kayit("iade_excel")
    k.iptal("eski iadeler okunamadı")
    assert not k.geri_alinabilir


def test_kayit_kod_ve_kontrol_yazilir(monkeypatch):
    out = []
    monkeypatch.setattr(Y, "kaydet", lambda *a, **kw: out.append((a, kw)) or 1)
    k = Y.Kayit("toplu_mal_kabul", "tmk.xlsx")
    k.eklenen("ts_kayitlar", [{"id": 4}], beklenen=1)
    k.kontrol("ts_kayitlar", 4, mevcut_durum="mal kabül", _gecmis_sayisi=1)
    k.kaydet(1)
    a, kw = out[0]
    assert kw["kod"] == k.kod and kw["geri_alinabilir"] is True
    assert a[4]["_kontrol"] == [{"tablo": "ts_kayitlar", "id": 4,
                                 "alanlar": {"mevcut_durum": "mal kabül", "_gecmis_sayisi": 1}}]


# ── Engel kuralı ────────────────────────────────────────────────────
def _k(i, zaman, tur="siparis_excel", anahtarlar=("satislar:FAT-1",), durum="aktif", kod="abc"):
    return {"id": i, "tur": tur, "zaman": zaman, "anahtarlar": list(anahtarlar), "durum": durum,
            "kullanici": "derya", "geri_alinabilir": True, "kod": kod, "dosya_adi": f"d{i}.xlsx"}


def test_isaretsiz_stoklu_yukleme_geri_alinamaz():
    e = Y.geri_alma_engeli(_k(1, "2026-10-01T10:00:00+00:00", kod=None), [], "derya")
    assert "stok işaretlemesinden önce" in e


def test_farkli_turde_ayni_tablo_dilimi_engeller():
    # Sipariş Excel'iyle girilen FAT-1, sonra Mikro dökümüyle yeniden yazıldı → önce Mikro geri alınmalı
    eski = _k(1, "2026-10-01T10:00:00+00:00")
    yeni = _k(2, "2026-10-02T10:00:00+00:00", tur="mikro_fatura")
    assert "Önce onu geri al" in Y.geri_alma_engeli(eski, [eski, yeni], "derya")
    assert Y.geri_alma_engeli(yeni, [eski, yeni], "derya") == ""


def test_farkli_turde_iki_noktasiz_anahtar_engellemez():
    # 'TL' gibi tür içi dilim adları türler arasında çakışma sayılmaz
    eski = _k(1, "2026-10-01T10:00:00+00:00", tur="cek_listesi", anahtarlar=("TL",), kod="")
    yeni = _k(2, "2026-10-02T10:00:00+00:00", tur="musteri_haftalik", anahtarlar=("TL",))
    assert Y.geri_alma_engeli(eski, [eski, yeni], "derya") == ""


def test_sonraki_g5f_sayimi_oncekini_engeller():
    eski = _k(1, "2026-10-01T10:00:00+00:00", tur="g5f_sayim", anahtarlar=("g5f",))
    yeni = _k(2, "2026-10-02T10:00:00+00:00", tur="g5f_sayim", anahtarlar=("g5f",))
    assert "Önce onu geri al" in Y.geri_alma_engeli(eski, [eski, yeni], "derya")


def test_yarim_kalan_geri_alma_tekrar_denenebilir():
    k = _k(1, "2026-10-01T10:00:00+00:00", durum="geri_aliniyor")
    assert Y.geri_alma_engeli(k, [k], "derya") == ""


# ── Kontrol farkı ───────────────────────────────────────────────────
def _kontrollu(**alanlar):
    return {"degisiklik": {"_kontrol": [{"tablo": "ithalat_dosyalari", "id": 9, "alanlar": alanlar}]}}


def test_kontrol_ayni_deger_farkli_yazim_engellemez():
    k = _kontrollu(durum="", masraflar={"navlun": 1200}, kur=34.5)
    simdi = {"durum": None, "masraflar": {"navlun": 1200.0}, "kur": "34.5"}
    assert Y.kontrol_farki(k, lambda t, i, a: simdi) == ""


def test_kontrol_sonradan_masraf_girildiyse_engeller():
    k = _kontrollu(masraflar={"navlun": 1200})
    e = Y.kontrol_farki(k, lambda t, i, a: {"masraflar": {"navlun": 1200, "gumruk": 300}})
    assert "masraflar" in e and "engellendi" in e


def test_kontrol_satir_silinmisse_engeller():
    assert "silinmiş" in Y.kontrol_farki(_kontrollu(kur=1), lambda t, i, a: None)


def test_kontrol_servis_kaydi_islem_gorduyse_engeller():
    k = {"degisiklik": {"_kontrol": [{"tablo": "ts_kayitlar", "id": 4,
                                      "alanlar": {"mevcut_durum": "mal kabül", "_gecmis_sayisi": 1}}]}}
    assert Y.kontrol_farki(k, lambda t, i, a: {"mevcut_durum": "mal kabül", "_gecmis_sayisi": 1}) == ""
    assert "_gecmis_sayisi" in Y.kontrol_farki(k, lambda t, i, a: {"mevcut_durum": "mal kabül",
                                                                   "_gecmis_sayisi": 2})
    assert "mevcut_durum" in Y.kontrol_farki(k, lambda t, i, a: {"mevcut_durum": "tamir",
                                                                 "_gecmis_sayisi": 1})


def test_onizleme_ozel_anahtarlari_gostermez():
    k = {"degisiklik": {"satislar": {"eklenen": [1, 2], "onceki": []}, "_kontrol": [{}]}}
    assert Y.onizleme(k) == {"satislar": (2, 0)}


# ── Stok net etkisi ────────────────────────────────────────────────
def test_stok_net_kismi_ters_cevirmeden_sonra_kalan():
    h = [{"sku": "A", "depo": "Merkez", "degisim": -3}, {"sku": "A", "depo": "MERKEZ DEPO", "degisim": -2},
         {"sku": "B", "depo": "MERKEZ DEPO", "degisim": 4},
         {"sku": "B", "depo": "MERKEZ DEPO", "degisim": -4},           # kod:geri — B tamamlanmış
         {"sku": "C", "depo": "HAPPY LIFE", "degisim": 9, "basarili": False}]   # başarısız hareket sayılmaz
    kanon = lambda d: "MERKEZ DEPO" if d.lower().startswith("merkez") else d  # noqa: E731
    assert Y.stok_net(h, kanon) == {("A", "MERKEZ DEPO"): -5.0}


# ── Geri alma akışı (sahte veritabanı) ─────────────────────────────
class _Q:
    def __init__(self, db, t):
        self.db, self.t, self.f, self.upd = db, t, [], None

    def select(self, *a, **k):
        return self

    def eq(self, c, v):
        self.f.append((c, lambda x, v=v: x == v))
        return self

    def in_(self, c, vs):
        self.f.append((c, lambda x, vs=tuple(vs): x in vs))
        return self

    def update(self, d):
        self.upd = d
        return self

    def execute(self):
        rows = self.db.setdefault(self.t, [])
        uy = [r for r in rows if all(p(r.get(c)) for c, p in self.f)]
        if self.upd is not None:
            for r in uy:
                r.update(self.upd)
        return type("R", (), {"data": [dict(r) for r in uy]})()


class _RPC:
    def __init__(self, sb, ad, p):
        self.sb, self.ad, self.p = sb, ad, p

    def execute(self):
        self.sb.rpc_cagri.append((self.ad, self.p))
        if self.sb.rpc_hata:
            raise RuntimeError(self.sb.rpc_hata)
        k = next(r for r in self.sb.db["yuklemeler"] if r["id"] == self.p["p_id"])
        assert k["durum"] == "geri_aliniyor"
        k["silinen"] = {"satislar": []}
        return type("R", (), {"data": {"silinen": 2, "geri_yazilan": 1}})()


class _SB:
    def __init__(self, db, rpc_hata=None):
        self.db, self.rpc_hata, self.rpc_cagri = db, rpc_hata, []

    def table(self, t):
        return _Q(self.db, t)

    def rpc(self, ad, p):
        return _RPC(self, ad, p)


@pytest.fixture
def ortam(monkeypatch):
    """Sahte veritabanı + sahte tek stok kapısı. stok_hatali: bu SKU'lar atlanır (yarım kalma)."""
    import kayranpm.database as PM
    import shared.hata_log as HL
    db = {
        "yuklemeler": [{"id": 1, "tur": "siparis_excel", "zaman": "2026-10-01T10:00:00+00:00",
                        "durum": "aktif", "kullanici": "derya", "geri_alinabilir": True, "kod": "k1",
                        "anahtarlar": ["satislar:FAT-1"], "dosya_adi": "s.xlsx", "silinen": None,
                        "degisiklik": {"satislar": {"eklenen": [11, 12], "onceki": [{"id": 5}]}}}],
        "stok_hareketleri": [
            {"sku": "A", "depo": "MERKEZ DEPO", "degisim": -3, "yukleme_kodu": "k1"},
            {"sku": "B", "depo": "HAPPY LIFE", "degisim": -1, "yukleme_kodu": "k1"},
            {"sku": "A", "depo": "MERKEZ DEPO", "degisim": -7, "yukleme_kodu": None},   # başka hareket
        ],
    }
    sb = _SB(db)
    durum = {"hatali": set(), "cagri": []}

    def coklu(h, depo, aciklama=""):
        durum["cagri"].append((dict(h), depo, SD.aktif_yukleme()))
        atl = []
        for sku, v in h.items():
            if sku in durum["hatali"]:
                atl.append(sku)
                continue
            db["stok_hareketleri"].append({"sku": sku, "depo": depo, "degisim": v,
                                           "yukleme_kodu": SD.aktif_yukleme()})
        return {}, atl

    monkeypatch.setattr(Y, "_ham", lambda: sb)
    monkeypatch.setattr(PM, "stok_hareket_coklu", coklu)
    monkeypatch.setattr(PM, "depo_kanonik", lambda d: d)
    monkeypatch.setattr(HL, "kaydet", lambda *a, **k: True)
    return sb, db, durum


def test_geri_al_satir_ve_stok_tamamlanir(ortam):
    sb, db, durum = ortam
    ok, m = Y.geri_al(1, "derya")
    assert ok, m
    assert "2 satır silindi" in m and "stok etkisi ters çevrildi" in m
    assert sb.rpc_cagri == [("yukleme_satir_geri_al", {"p_id": 1})]
    assert sorted(durum["cagri"], key=lambda c: c[1]) == [({"B": 1.0}, "HAPPY LIFE", "k1:geri"),
                                                          ({"A": 3.0}, "MERKEZ DEPO", "k1:geri")]
    assert db["yuklemeler"][0]["durum"] == "geri_alindi"


def test_geri_al_satir_adimi_patlarsa_sahiplenme_birakilir_stoka_dokunulmaz(ortam):
    sb, db, durum = ortam
    sb.rpc_hata = 'duplicate key value violates unique constraint "satislar_pkey" (23505)'
    ok, m = Y.geri_al(1, "derya")
    assert not ok and "çakışıyor" in m and "Hiçbir şey değişmedi" in m
    assert db["yuklemeler"][0]["durum"] == "aktif" and durum["cagri"] == []


def test_geri_al_stok_yarim_kalirsa_tekrar_dene_yalniz_kalani_uygular(ortam):
    sb, db, durum = ortam
    durum["hatali"] = {"B"}
    ok, m = Y.geri_al(1, "derya")
    assert not ok and "YARIM" in m and "B" in m
    assert db["yuklemeler"][0]["durum"] == "geri_aliniyor"
    # Tekrar dene: satır adımı tekrarlanmaz (silinen dolu), yalnız B uygulanır
    durum["hatali"], durum["cagri"] = set(), []
    ok, m = Y.geri_al(1, "derya")
    assert ok, m
    assert len(sb.rpc_cagri) == 1
    assert durum["cagri"] == [({"B": 1.0}, "HAPPY LIFE", "k1:geri")]
    assert db["yuklemeler"][0]["durum"] == "geri_alindi"
    assert Y.stok_net([h for h in db["stok_hareketleri"] if h["yukleme_kodu"] in ("k1", "k1:geri")]) == {}


def test_geri_al_kontrol_farki_engeller(ortam):
    sb, db, durum = ortam
    db["yuklemeler"][0]["degisiklik"]["_kontrol"] = [{"tablo": "ts_kayitlar", "id": 4,
                                                     "alanlar": {"mevcut_durum": "mal kabül"}}]
    db["ts_kayitlar"] = [{"id": 4, "mevcut_durum": "tamir"}]
    ok, m = Y.geri_al(1, "derya")
    assert not ok and "değiştirilmiş" in m
    assert db["yuklemeler"][0]["durum"] == "aktif" and sb.rpc_cagri == [] and durum["cagri"] == []


def test_g5f_sayimi_yalniz_stok_ters_cevrilir(ortam):
    sb, db, durum = ortam
    db["yuklemeler"][0].update({"tur": "g5f_sayim", "anahtarlar": ["g5f"], "degisiklik": {}})
    ok, m = Y.geri_al(1, "derya")
    assert ok, m
    assert sb.rpc_cagri == [] and "satır" not in m and len(durum["cagri"]) == 2


def test_baskasi_sahiplendiyse_ikinci_geri_alma_durur(ortam, monkeypatch):
    sb, db, durum = ortam
    gercek = _Q.execute

    def yarisan(self):   # okumadan sonra, sahiplenmeden önce başka biri sahiplenmiş
        if self.upd is not None and self.upd.get("durum") == "geri_aliniyor":
            db["yuklemeler"][0]["durum"] = "geri_aliniyor"
        return gercek(self)
    monkeypatch.setattr(_Q, "execute", yarisan)
    ok, m = Y.geri_al(1, "derya")
    assert not ok and "başka biri" in m and sb.rpc_cagri == []


# ── Yazma yollarının bildirimi ──────────────────────────────────────
class _YQ(_Q):
    """Ekleme / silme de yapan sahte sorgu (satış, iade, servis)."""
    def __init__(self, db, t):
        super().__init__(db, t)
        self.ins, self.sil = None, False

    def insert(self, rows):
        self.ins = rows if isinstance(rows, list) else [rows]
        return self

    def delete(self):
        self.sil = True
        return self

    def execute(self):
        rows = self.db.setdefault(self.t, [])
        if self.ins is not None:
            out = []
            for r in self.ins:
                self.db["_id"] = self.db.get("_id", 100) + 1
                out.append(dict(r, id=self.db["_id"]))
            rows.extend(out)
            return type("R", (), {"data": out})()
        uy = [r for r in rows if all(p(r.get(c)) for c, p in self.f)]
        if self.sil:
            self.db[self.t] = [r for r in rows if r not in uy]
        return type("R", (), {"data": [dict(r) for r in uy]})()


class _YDB:
    def __init__(self, db):
        self.db = db

    def table(self, t):
        return _YQ(self.db, t)


def test_siparis_ustune_yaz_eski_satirlari_ve_yeni_kimlikleri_bildirir(monkeypatch):
    import satis.database as S
    db = {"satislar": [{"id": 5, "siparis_no": "FAT-1", "sku": "A", "adet": 2},
                       {"id": 6, "siparis_no": "FAT-9", "sku": "B", "adet": 1}]}
    monkeypatch.setattr(S, "_get_client", lambda: _YDB(db))
    monkeypatch.setattr(S, "get_pacal_map", lambda: {"A": 10.0})
    for ad in ("_stok_uygula", "_stok_akilli_dus", "_temizle"):
        monkeypatch.setattr(S, ad, lambda *a, **k: None)
    k = Y.Kayit("siparis_excel", "s.xlsx")
    with k.stok():
        r = S.ice_aktar_satislar([{"tarih": "2026-10-01", "kanal": "VATAN", "siparis_no": "FAT-1",
                                   "sku": "A", "adet": 3, "birim_satis": 20}], temizle_once=True)
    assert r["eklendi"] == 1
    assert k.anahtarlar == ["satislar:FAT-1"]
    assert [x["id"] for x in k.degisiklik["satislar"]["onceki"]] == [5]
    assert k.degisiklik["satislar"]["eklenen"] == [101] and k.geri_alinabilir


def test_yukleme_disinda_satis_bildirmez(monkeypatch):
    import satis.database as S
    db = {"satislar": []}
    monkeypatch.setattr(S, "_get_client", lambda: _YDB(db))
    monkeypatch.setattr(S, "get_pacal_map", lambda: {})
    for ad in ("_stok_uygula", "_stok_akilli_dus", "_temizle"):
        monkeypatch.setattr(S, ad, lambda *a, **k: None)
    r = S.ice_aktar_satislar([{"tarih": "2026-10-01", "siparis_no": "F", "sku": "A", "adet": 1}],
                             atla_mevcut=False)
    assert r["eklendi"] == 1 and Y.aktif() is None


def test_iade_temizle_eski_iadeleri_tam_bildirir(monkeypatch):
    import satis.database as S
    db = {"iadeler": [{"id": 7, "tarih": "2026-09-30", "sku": "A", "iade_adet": 1, "depo": "MERKEZ DEPO",
                       "iade_net": 50}]}
    monkeypatch.setattr(S, "_get_client", lambda: _YDB(db))
    monkeypatch.setattr(S, "_kart_sku_haritasi", lambda: {})
    monkeypatch.setattr(S, "_kart_sku", lambda s, h: str(s or ""))
    monkeypatch.setattr(S, "_stok_uygula_depolu", lambda *a, **k: None)
    monkeypatch.setattr(S, "_temizle", lambda: None)
    k = Y.Kayit("iade_excel", "i.xlsx")
    with k.stok():
        r = S.ice_aktar_iadeler([{"sku": "A", "iade_adet": 2}, {"sku": "B", "iade_adet": 1}],
                                "2026-09-30", temizle_once=True)
    assert r["eklendi"] == 2
    assert k.anahtarlar == ["iadeler:2026-09-30"]
    assert k.degisiklik["iadeler"]["onceki"][0]["iade_net"] == 50          # TAM satır (yalnız sku/adet değil)
    assert len(k.degisiklik["iadeler"]["eklenen"]) == 2 and k.geri_alinabilir


def test_servis_kaydi_kontrol_ile_bildirilir(monkeypatch):
    import teknikservis.database as T
    db = {"ts_kayitlar": []}
    monkeypatch.setattr(T, "get_client", lambda: _YDB(db))
    monkeypatch.setattr(T, "_cache_temizle", lambda: None)
    k = Y.Kayit("toplu_mal_kabul", "tmk.xlsx")
    with k.stok():
        ok, _, _ = T.ekle_kayit({"seri_no": "S1"}, "derya")
    assert ok
    kid = k.degisiklik["ts_kayitlar"]["eklenen"][0]
    assert k.degisiklik["_kontrol"] == [{"tablo": "ts_kayitlar", "id": kid,
                                         "alanlar": {"mevcut_durum": "mal kabül", "_gecmis_sayisi": 1}}]


def test_ithalat_bildirimi_yeni_ve_guncellenen_dosya():
    import ithalat.database as I
    yeni = Y.Kayit("ithalat_rapor", "r.xlsx")
    with yeni.stok():
        I._yukleme_bildir(41, {"durum": "Yolda", "masraflar": {"navlun": 5}, "kur": 34})
    assert yeni.anahtarlar == ["ithalat:41"] and yeni.degisiklik["ithalat_dosyalari"]["eklenen"] == [41]
    assert yeni.degisiklik["_kontrol"][0]["alanlar"] == {"durum": "Yolda", "masraflar": {"navlun": 5}, "kur": 34}
    gun = Y.Kayit("ithalat_rapor", "r.xlsx")
    with gun.stok():
        I._yukleme_bildir(41, {"durum": ""}, eski_baslik={"id": 41, "dosya_no": "D1"},
                          eski_kalemler=[{"id": 1, "dosya_id": 41}])
    assert gun.degisiklik["ithalat_dosyalari"]["onceki"] == [{"id": 41, "dosya_no": "D1"}]
    assert gun.degisiklik["ithalat_kalemleri"]["onceki"] == [{"id": 1, "dosya_id": 41}]
    I._yukleme_bildir(41, {})                 # yükleme dışında: hiçbir şey yapmaz, patlamaz


def test_ithalat_ve_servis_yuklemeleri_baglam_icinde():
    ith = (KOK / "ithalat" / "main.py").read_text(encoding="utf-8")
    assert '_YKayit("ithalat_rapor", up.name)' in ith and "with _yk_ith.stok():" in ith
    ts = (KOK / "teknikservis" / "main.py").read_text(encoding="utf-8")
    g = ts[ts.index("with _yk_ts.stok():"):]
    assert g.index("ekle_kayit(") < g.index("mal_kabul_girisi(") < g.index("if _okk:\n                                _ok_s")


# ── SQL 14 gerçek PostgreSQL'de (yalnız yerelde; CI'da atlanır) ────
@pytest.mark.skipif(not os.environ.get("KAYRAN_TEST_PG") or not shutil.which("psql"),
                    reason="KAYRAN_TEST_PG (psql bağlantı dizesi) yok")
def test_sql_satir_geri_al():
    pg = os.environ["KAYRAN_TEST_PG"]

    def q(sql):
        return subprocess.run(["psql", pg, "-v", "ON_ERROR_STOP=1", "-qAt", "-c", sql],
                              capture_output=True, text=True)
    q("drop table if exists yuklemeler, satislar, ithalat_kalemleri, ithalat_dosyalari, ts_gecmis, "
      "ts_kayitlar, iadeler, firma_stok, ref_butce, happylife_stok, cekler, stok_hareketleri cascade")
    q("create table stok_hareketleri (id serial primary key, sku text)")
    q("create table satislar (id serial primary key, siparis_no text, sku text, adet int)")
    q("create table iadeler (id bigint generated always as identity primary key, tarih date, sku text)")
    q("create table ithalat_dosyalari (id bigint generated always as identity primary key, dosya_no text, "
      "masraflar jsonb)")
    q("create table ithalat_kalemleri (id bigint generated by default as identity primary key, "
      "dosya_id bigint references ithalat_dosyalari(id) on delete cascade, sku text)")
    q("create table ts_kayitlar (id bigint generated by default as identity primary key, seri_no text)")
    q("create table ts_gecmis (id serial primary key, kayit_id bigint references ts_kayitlar(id) on delete cascade)")
    for t in ("firma_stok", "happylife_stok", "cekler", "ref_butce"):
        q(f"create table {t} (id serial primary key)")
    for f in ("12_yuklemeler.sql", "13_yukleme_kodu.sql", "14_yukleme_satir_geri_al.sql"):
        r = subprocess.run(["psql", pg, "-v", "ON_ERROR_STOP=1", "-q", "-f", str(KOK / "veritabani" / f)],
                           capture_output=True, text=True)
        assert r.returncode == 0, (f, r.stderr)
    # Mevcut: FAT-1 eski satırı (5) silinip yerine 20 yazıldı; ithalat dosyası 3 güncellendi
    # (eski başlık + eski kalem 30 geri gelecek, yeni kalem 31 gidecek); servis kaydı 8 eklendi.
    q("insert into satislar (id, siparis_no, sku, adet) values (20, 'FAT-1', 'A', 3), (21, 'FAT-2', 'B', 1)")
    q("insert into ithalat_dosyalari (id, dosya_no, masraflar) overriding system value values "
      "(3, 'D3-yeni', '{}')")
    q("insert into ithalat_kalemleri (id, dosya_id, sku) values (31, 3, 'YENI')")
    q("insert into ts_kayitlar (id, seri_no) values (8, 'S8')")
    q("insert into ts_gecmis (kayit_id) values (8)")
    q("""insert into yuklemeler (tur, geri_alinabilir, durum, degisiklik) values ('siparis_excel', true,
      'geri_aliniyor', '{"satislar": {"eklenen": [20], "onceki": [{"id": 5, "siparis_no": "FAT-1", "sku": "A",
        "adet": 2}]}, "_kontrol": [{"tablo": "satislar", "id": 20, "alanlar": {}}]}')""")
    q("""insert into yuklemeler (tur, geri_alinabilir, durum, degisiklik) values ('ithalat_rapor', true,
      'geri_aliniyor', '{"ithalat_dosyalari": {"eklenen": [3], "onceki": [{"id": 3, "dosya_no": "D3-eski",
        "masraflar": {"navlun": 5}}]}, "ithalat_kalemleri": {"eklenen": [], "onceki": [{"id": 30,
        "dosya_id": 3, "sku": "ESKI"}]}}')""")
    q("""insert into yuklemeler (tur, geri_alinabilir, durum, degisiklik) values ('toplu_mal_kabul', true,
      'geri_aliniyor', '{"ts_kayitlar": {"eklenen": [8], "onceki": []}}')""")
    r = q("select yukleme_satir_geri_al(1)")
    assert r.returncode == 0 and '"silinen": 1' in r.stdout, r.stderr
    assert q("select string_agg(id||siparis_no||adet, ',' order by id) from satislar").stdout.strip() == "5FAT-12,21FAT-21"
    assert '"zaten": true' in q("select yukleme_satir_geri_al(1)").stdout          # ikinci kez: dokunmaz
    assert q("select count(*) from satislar").stdout.strip() == "2"
    r = q("select yukleme_satir_geri_al(2)")
    assert r.returncode == 0, r.stderr
    assert q("select dosya_no||masraflar::text from ithalat_dosyalari").stdout.strip() == 'D3-eski{"navlun": 5}'
    assert q("select string_agg(id||sku, ',') from ithalat_kalemleri").stdout.strip() == "30ESKI"
    r = q("select yukleme_satir_geri_al(3)")
    assert r.returncode == 0, r.stderr
    assert q("select count(*) from ts_kayitlar").stdout.strip() == "0"
    assert q("select count(*) from ts_gecmis").stdout.strip() == "0"              # zincirleme
    # Sahiplenilmemiş (aktif) kayıt çalışmaz; izin verilmeyen tablo reddedilir
    q("""insert into yuklemeler (tur, geri_alinabilir, degisiklik) values ('siparis_excel', true,
      '{"satislar": {"eklenen": [21]}}')""")
    assert "geri alma durumunda değil" in q("select yukleme_satir_geri_al(4)").stderr
    q("""insert into yuklemeler (tur, geri_alinabilir, durum, degisiklik) values ('x', true, 'geri_aliniyor',
      '{"urunler": {"eklenen": [1]}}')""")
    assert "izin verilmeyen" in q("select yukleme_satir_geri_al(5)").stderr
    # Yarıda hata → hiçbir şey değişmez (eski satır kimliği şu an dolu)
    q("""insert into yuklemeler (tur, geri_alinabilir, durum, degisiklik) values ('siparis_excel', true,
      'geri_aliniyor', '{"satislar": {"eklenen": [21], "onceki": [{"id": 5, "siparis_no": "X"}]}}')""")
    assert q("select yukleme_satir_geri_al(6)").returncode != 0
    assert q("select count(*) from satislar where id = 21").stdout.strip() == "1"
    assert q("select silinen is null from yuklemeler where id = 6").stdout.strip() == "t"
