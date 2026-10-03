# -*- coding: utf-8 -*-
"""Yükleme geçmişi ve geri alma (shared/yukleme_gecmisi.py, veritabani/12_yuklemeler.sql).

Excel yüklemeleri doğrudan kayıtların üzerine yazıyordu; yanlış dosyada tek çare gece
yedeğiydi, kimin neyi yüklediği görünmüyordu. Artık her yükleme geçmişe yazılır; dört
dilim-değiştiren yükleme (haftalık müşteri raporu, Happy Life, çek listesi, havuz bütçe)
eski satırları ve eklenen kimlikleri saklar, tek işlemde geri alınır.
"""
import ast
import os
import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

import shared.yukleme_gecmisi as Y

KOK = Path(__file__).resolve().parent.parent


# ── Kayit ───────────────────────────────────────────────────────────
@pytest.fixture
def yazilan(monkeypatch):
    out = []
    monkeypatch.setattr(Y, "kaydet", lambda tur, n, dosya="", anahtarlar=(), degisiklik=None, kod="":
                        out.append({"tur": tur, "n": n, "dosya": dosya, "anahtarlar": list(anahtarlar),
                                    "degisiklik": degisiklik, "kod": kod}) or 1)
    return out


def test_kayit_geri_alinabilir_yukleme(yazilan):
    k = Y.Kayit("musteri_haftalik", "hafta.xlsx")
    k.anahtar("VATAN", "2026-09-27")
    k.anahtar("VATAN", "2026-09-27")                      # tekrar → bir kez
    k.onceki("firma_stok", [{"id": 1, "sku": "A"}])
    k.eklenen("firma_stok", [{"id": 7}, {"id": 8}], beklenen=2)
    k.kaydet(2)
    y = yazilan[0]
    assert y["anahtarlar"] == ["VATAN|2026-09-27"] and y["dosya"] == "hafta.xlsx"
    assert y["degisiklik"] == {"firma_stok": {"eklenen": [7, 8], "onceki": [{"id": 1, "sku": "A"}]}}


def test_kimlik_eksikse_geri_alinamaz(yazilan):
    k = Y.Kayit("musteri_haftalik")
    k.eklenen("firma_stok", [{"id": 7}], beklenen=2)       # 2 satır gönderildi, 1 kimlik döndü
    k.kaydet(2)
    assert yazilan[0]["degisiklik"] is None


def test_iptal_ve_gecmis_turu_geri_alinamaz(yazilan):
    k = Y.Kayit("happylife")
    k.eklenen("happylife_stok", [{"id": 1}], beklenen=1)
    k.iptal("satır satır yazıldı")
    k.kaydet(1)
    k2 = Y.Kayit("g5f_sayim")
    k2.eklenen("urunler", [{"id": 1}])
    k2.kaydet(1)
    assert yazilan[0]["degisiklik"] is None and yazilan[1]["degisiklik"] is None


def test_kaydet_hata_firlatmaz(monkeypatch):
    def patla():
        raise RuntimeError("tablo yok")
    monkeypatch.setattr(Y, "_ham", patla)
    import shared.hata_log as HL
    monkeypatch.setattr(HL, "kaydet", lambda *a, **k: True)
    assert Y.kaydet("happylife", 3, "x.xlsx") is None


# ── Geri alma kuralı ────────────────────────────────────────────────
def _k(i, zaman, anahtar="VATAN|2026-09-27", durum="aktif", kul="derya", geri=True, tur="musteri_haftalik"):
    return {"id": i, "tur": tur, "zaman": zaman, "anahtarlar": [anahtar], "durum": durum,
            "kullanici": kul, "geri_alinabilir": geri, "dosya_adi": f"d{i}.xlsx"}


def test_sonraki_yukleme_ayni_dilimdeyse_engeller():
    eski, yeni = _k(1, "2026-10-01T10:00:00+00:00"), _k(2, "2026-10-02T10:00:00+00:00")
    e = Y.geri_alma_engeli(eski, [eski, yeni], "derya")
    assert "Önce onu geri al" in e
    assert Y.geri_alma_engeli(yeni, [eski, yeni], "derya") == ""


def test_baska_dilim_ya_da_geri_alinmis_sonraki_engellemez():
    eski = _k(1, "2026-10-01T10:00:00+00:00")
    baska = _k(2, "2026-10-02T10:00:00+00:00", anahtar="HB|2026-09-27")
    geri = _k(3, "2026-10-03T10:00:00+00:00", durum="geri_alindi")
    assert Y.geri_alma_engeli(eski, [eski, baska, geri], "derya") == ""


def test_kisi_kurali():
    k = _k(1, "2026-10-01T10:00:00+00:00", kul="derya")
    assert "kendi yüklemeni" in Y.geri_alma_engeli(k, [k], "ibrahim")
    assert Y.geri_alma_engeli(k, [k], "ibrahim", yonetici=True) == ""


def test_geri_alinmis_ve_gecmis_turu_engellenir():
    assert "zaten geri alınmış" in Y.geri_alma_engeli(_k(1, "x", durum="geri_alindi"), [], "derya")
    assert "geri alınamaz" in Y.geri_alma_engeli(_k(1, "x", geri=False), [], "derya")


def test_onizleme():
    k = {"degisiklik": {"firma_stok": {"eklenen": [1, 2, 3], "onceki": [{"id": 9}]}}}
    assert Y.onizleme(k) == {"firma_stok": (3, 1)}


# ── Kapsam: 16 yükleme yolu, tablo listeleri ────────────────────────
def _tur_cagrilari():
    """Kod içinde Kayit("tur") ya da kaydet("tur", ...) çağrılarındaki türler."""
    out = set()
    for p in KOK.rglob("*.py"):
        if any(x in p.parts for x in ("tests", ".git", ".venv", "__pycache__")) or p.name == "yukleme_gecmisi.py":
            continue
        src = p.read_text(encoding="utf-8")
        if "yukleme_gecmisi" not in src:
            continue
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.Call) and n.args and isinstance(n.args[0], ast.Constant) \
                    and isinstance(n.args[0].value, str) and ast.unparse(n.func) in ("_YKayit", "_yg_kaydet"):
                out.add(n.args[0].value)
    return out


def test_her_yukleme_turu_kodda_kullaniliyor():
    kullanilan = _tur_cagrilari()
    assert kullanilan == set(Y.TURLER), (set(Y.TURLER) - kullanilan, kullanilan - set(Y.TURLER))
    assert len(Y.TURLER) == 16


def test_sql_izin_listesi_ayni():
    sql = (KOK / "veritabani" / "12_yuklemeler.sql").read_text(encoding="utf-8")
    izin = re.search(r"IF t NOT IN \(([^)]+)\)", sql).group(1)
    assert set(re.findall(r"'(\w+)'", izin)) == set(Y.GERI_ALINABILIR.values())


def test_sayfa_baglantilari():
    a = (KOK / "app.py").read_text(encoding="utf-8")
    assert 'args=("yukleme_gecmisi",)' in a and 'elif aktif == "yukleme_gecmisi":' in a


# ── Geri alınabilir yolların kaydı (sahte veritabanı) ──────────────
class _Q:
    def __init__(self, db, t):
        self.db, self.t, self.f, self.ins, self.sil = db, t, {}, None, False

    def select(self, *a, **k):
        return self

    def eq(self, c, v):
        self.f[c] = v
        return self

    def delete(self):
        self.sil = True
        return self

    def insert(self, rows):
        self.ins = rows if isinstance(rows, list) else [rows]
        return self

    def execute(self):
        rows = self.db.setdefault(self.t, [])
        uy = [r for r in rows if all(r.get(c) == v for c, v in self.f.items())]
        if self.ins is not None:
            out = []
            for r in self.ins:
                self.db["_id"] = self.db.get("_id", 100) + 1
                out.append(dict(r, id=self.db["_id"]))
            rows.extend(out)
            return type("R", (), {"data": out})()
        if self.sil:
            self.db[self.t] = [r for r in rows if r not in uy]
            return type("R", (), {"data": uy})()
        return type("R", (), {"data": [dict(r) for r in uy]})()


class _DB:
    def __init__(self, tablolar):
        self.v = {k: [dict(r) for r in v] for k, v in tablolar.items()}

    def table(self, t):
        return _Q(self.v, t)


def test_happylife_eski_gunu_ve_yeni_kimlikleri_saklar(monkeypatch, yazilan):
    import depo.main as D
    db = _DB({"happylife_stok": [{"id": 5, "rapor_tarihi": "2026-10-03", "miktar": 1}]})
    monkeypatch.setattr(D, "get_client", lambda: db)
    ok, _ = D.hl_kaydet([{"miktar": 7}, {"miktar": 8}], "2026-10-03", dosya_adi="hl.xlsx")
    assert ok
    y = yazilan[0]
    assert y["tur"] == "happylife" and y["anahtarlar"] == ["2026-10-03"] and y["dosya"] == "hl.xlsx"
    assert y["degisiklik"]["happylife_stok"]["onceki"] == [{"id": 5, "rapor_tarihi": "2026-10-03", "miktar": 1}]
    assert y["degisiklik"]["happylife_stok"]["eklenen"] == [101, 102]


def test_cek_listesi_tl_usd_tek_kayit(monkeypatch, yazilan):
    import kayranacc.database as K
    db = _DB({"cekler": [{"id": 1, "para_birimi": "TL", "cek_no": "eski"}]})
    monkeypatch.setattr(K, "get_client", lambda: db)
    monkeypatch.setattr(K, "_cache_temizle", lambda: None, raising=False)
    k = Y.Kayit("cek_listesi", "cek.xlsx")
    K.cek_ekle_bulk([{"cek_no": "T1", "para_birimi": "TL"}], "TL", yukleme=k)
    K.cek_ekle_bulk([{"cek_no": "U1", "para_birimi": "USD"}], "USD", yukleme=k)
    k.kaydet(2)
    y = yazilan[0]
    assert y["anahtarlar"] == ["TL", "USD"]
    assert [r["cek_no"] for r in y["degisiklik"]["cekler"]["onceki"]] == ["eski"]
    assert len(y["degisiklik"]["cekler"]["eklenen"]) == 2


def test_havuz_butce_temizle_ile_onceki_saklanir(monkeypatch, yazilan):
    import kayranpm.ref_no as R
    db = _DB({"ref_butce": [{"id": 3, "firma_id": 7, "tur": "BÜTÇE", "tutar": 100}]})
    monkeypatch.setattr(R, "get_client", lambda: db)
    monkeypatch.setattr(R, "_cache_temizle", lambda: None)
    df = pd.DataFrame([["BÜTÇE", "FAZEON", "x", 500, None, "USD", "F1", None, None, "", ""]])
    ok, _, n = R.butce_excel_ice_aktar(7, df, temizle=True, dosya_adi="butce.xlsx")
    assert ok and n == 1
    y = yazilan[0]
    assert y["tur"] == "havuz_butce" and y["anahtarlar"] == ["7"]
    assert y["degisiklik"]["ref_butce"]["onceki"][0]["id"] == 3
    assert len(y["degisiklik"]["ref_butce"]["eklenen"]) == 1


def test_haftalik_musteri_yuklemesi_kaynakta_kayit_tutar():
    src = (KOK / "kayranpm" / "excel_islemler.py").read_text(encoding="utf-8")
    g = src[src.index("def excel_yukle_haftalik_stok_satis("):src.index("def excel_yukle_stok_kartlari(")]
    assert '_YKayit("musteri_haftalik", dosya_adi)' in g
    assert g.index('_yk.onceki("firma_stok"') < g.index('table("firma_stok").delete()')   # silmeden ÖNCE oku
    assert "_yk.eklenen(" in g and "_yk.iptal(" in g and "_yk.kaydet(" in g


# ── SQL fonksiyonu gerçek PostgreSQL'de (yalnız yerelde; CI'da atlanır) ─
@pytest.mark.skipif(not os.environ.get("KAYRAN_TEST_PG") or not shutil.which("psql"),
                    reason="KAYRAN_TEST_PG (psql bağlantı dizesi) yok")
def test_sql_geri_alma_tek_islem():
    pg = os.environ["KAYRAN_TEST_PG"]

    def q(sql):
        return subprocess.run(["psql", pg, "-v", "ON_ERROR_STOP=1", "-qAt", "-c", sql],
                              capture_output=True, text=True)
    q("drop table if exists yuklemeler, firma_stok, ref_butce, happylife_stok, cekler cascade")
    q("create table firma_stok (id serial primary key, firma text, sku text, stok_miktari int, "
      "yukleme_tarihi date, unique (firma, sku, yukleme_tarihi))")
    q("create table ref_butce (id bigint generated always as identity primary key, firma_id int, tutar numeric)")
    q("create table happylife_stok (id bigint generated by default as identity primary key, rapor_tarihi date)")
    q("create table cekler (id serial primary key, para_birimi text)")
    r = subprocess.run(["psql", pg, "-v", "ON_ERROR_STOP=1", "-q", "-f",
                        str(KOK / "veritabani" / "12_yuklemeler.sql")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    q("insert into firma_stok (id, firma, sku, stok_miktari, yukleme_tarihi) values "
      "(50, 'VATAN', 'B', 99, '2026-09-27')")
    q("insert into ref_butce (firma_id, tutar) values (7, 555)")
    q("""insert into yuklemeler (tur, geri_alinabilir, degisiklik) values ('musteri_haftalik', true,
      '{"firma_stok": {"eklenen": [50], "onceki": [{"id": 1, "firma": "VATAN", "sku": "A", "stok_miktari": 10,
        "yukleme_tarihi": "2026-09-27"}]},
        "ref_butce": {"eklenen": [1], "onceki": [{"id": 9, "firma_id": 7, "tutar": 100}]}}')""")
    assert '"silinen": 2' in q("select yukleme_geri_al(1, 'ibrahim')").stdout
    assert q("select string_agg(id||sku||stok_miktari, ',') from firma_stok").stdout.strip() == "1A10"
    assert q("select string_agg(id||':'||tutar, ',') from ref_butce").stdout.strip() == "9:100"
    assert q("select durum||geri_alan from yuklemeler").stdout.strip() == "geri_alindiibrahim"
    assert q("select yukleme_geri_al(1, 'x')").returncode != 0                 # ikinci kez olmaz
    # yarıda hata → HİÇBİR ŞEY değişmez
    assert q("insert into firma_stok (id, firma, sku, stok_miktari, yukleme_tarihi) values "
             "(60, 'HB', 'Z', 1, '2026-09-27')").returncode == 0
    q("""insert into yuklemeler (tur, geri_alinabilir, degisiklik) values ('musteri_haftalik', true,
      '{"firma_stok": {"eklenen": [1], "onceki": [{"id": 77, "firma": "HB", "sku": "Z", "stok_miktari": 3,
        "yukleme_tarihi": "2026-09-27"}]}}')""")
    assert q("select yukleme_geri_al(2, 'x')").returncode != 0
    assert q("select count(*) from firma_stok where id = 1").stdout.strip() == "1"
    assert q("select durum from yuklemeler where id = 2").stdout.strip() == "aktif"
    # izin verilmeyen tablo
    q("""insert into yuklemeler (tur, geri_alinabilir, degisiklik) values ('x', true, '{"urunler": {"eklenen": [1]}}')""")
    assert "izin verilmeyen" in q("select yukleme_geri_al(3, 'x')").stderr
