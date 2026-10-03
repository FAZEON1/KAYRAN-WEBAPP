# -*- coding: utf-8 -*-
"""Destek dönem görünümü (veritabani/16_destek_donem.sql) ↔ yedek Python hesabı, Ekim 2026.

ref_kayitlari.aylik 47 kayıtta METİN olarak saklıydı; v_destek_donem patlıyor, Yönetim P&L her
açılışta yedek Python hesabına (get_tum_ref_tutarlari + get_tum_butce_harcamalari) düşüyordu.
Görünüm düzeltildi ve YEDEK HESAPLA BİREBİR AYNI sonucu verecek şekilde yazıldı (kullanıcı onayı:
rakam değişmesin). Yazma yerleri artık dağılımı NESNE yazar; mevcut kayıtlara dokunulmaz.
"""
import json
import os
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest

import kayranpm.ref_no as R

KOK = Path(__file__).resolve().parent.parent


def test_aylik_nesne():
    assert R._aylik_nesne('{"2025-03": 200.0}') == {"2025-03": 200.0}
    assert R._aylik_nesne("") == {} and R._aylik_nesne("  ") == {} and R._aylik_nesne("bozuk") == {}
    assert R._aylik_nesne({"2025-04": 1}) == {"2025-04": 1}
    assert R._aylik_nesne('[1, 2]') == {}


def test_yazma_yerleri_metin_yazmiyor():
    for f in ("kayranpm/ref_no.py", "kayranpm/ref_ekran.py"):
        src = (KOK / f).read_text(encoding="utf-8")
        assert "json.dumps({f\"" not in src and "_json.dumps({f\"" not in src, f


def test_gorunum_suzgeci_aralik_kesisimi():
    src = (KOK / "kayranpm" / "ref_no.py").read_text(encoding="utf-8")
    i = src.index("def get_destek_donem(")
    g = src[i:i + 1500]
    assert '.lte("donem_bas", str(bitis)[:10])' in g and '.gte("donem_bit", str(baslangic)[:10])' in g


# ── Gerçek PostgreSQL'de görünüm ↔ Python (yalnız yerelde; CI'da atlanır) ─
REF = [  # id, firma_id, tutar, doviz, durum, yil, tarih, aylik (jsonb ham)
    (1, 1, 150, "USD", "beklemede", 2025, None, {"2025-03": 100, "2025-04": 50}),
    (2, 1, 7500, "TL", "beklemede", 2025, None, json.dumps({"2025-06": 7500.0})),          # metin
    (3, 2, 100, "USD", "paylasildi", 2025, "2025-07-02", json.dumps({"2025-07": 90})),    # metin + artık 10
    (4, 2, 300, "USD", "beklemede", 2026, None, ""),                                       # boş metin
    (5, 3, 40, "USD", "beklemede", None, "2025-09-10", None),                              # yalnız tarih
    (6, 3, 999, "USD", "iptal", 2025, None, {"2025-05": 999}),                             # iptal
    (7, 3, 0, "USD", "beklemede", 2025, None, {}),                                         # tutar 0
    (8, 1, 70, "USD", "beklemede", 2025, None, {"2025-02": 80}),                           # dağılım > tutar
    (9, 1, 25, "USD", "beklemede", 2025, None, "bozuk"),                                   # bozuk metin
    (10, 2, 60, "", "beklemede", None, None, {"2026-01": 60}),                             # döviz boş
    (11, 2, 33, "USD", "beklemede", None, None, None),                                     # dönemsiz → yok
]
BUTCE = [  # id, firma_id, tur, yon, tutar, doviz, fatura_tarih
    (1, 1, "SELLOUT", "harcama", 200, "USD", "2025-03-20"),
    (2, 1, "BÜTÇE", "", 50000, "USD", "2025-01-05"),
    (3, 1, "Butce", "harcama", 10, "USD", "2025-02-01"),
    (4, 2, "X", " Giriş ", 70, "USD", "2025-03-03"),
    (5, 2, "SELLOUT", "harcama", -30, "TL", "2025-04-02"),
    (6, 2, "", None, 15, None, "2026-02-14"),
    (7, 2, "MARKETING", "harcama", 5, "USD", None),
]
DONEMLER = [("2025-01-01", "2025-12-31"), ("2025-03-01", "2025-03-31"), ("2025-03-15", "2025-04-10"),
            ("2026-01-01", "2026-10-03"), ("2025-07-01", "2025-09-30"), ("2000-01-01", "2100-12-31"),
            ("2024-01-01", "2024-12-31")]


class _Q:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *a, **k):
        return self

    def gte(self, c, v):
        return _Q([r for r in self.rows if r.get(c) is not None and str(r[c]) >= v])

    def lte(self, c, v):
        return _Q([r for r in self.rows if r.get(c) is not None and str(r[c]) <= v])

    def execute(self):
        return type("S", (), {"data": self.rows})()


@pytest.mark.skipif(not os.environ.get("KAYRAN_TEST_PG") or not shutil.which("psql"),
                    reason="KAYRAN_TEST_PG (psql bağlantı dizesi) yok")
def test_gorunum_yedek_python_hesabiyla_birebir(monkeypatch):
    pg = os.environ["KAYRAN_TEST_PG"]

    def q(sql):
        r = subprocess.run(["psql", pg, "-v", "ON_ERROR_STOP=1", "-qAt", "-c", sql], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return r.stdout.strip()

    def lit(v):
        if v is None:
            return "NULL"
        if isinstance(v, (int, float)):
            return str(v)
        return "'" + str(v).replace("'", "''") + "'"

    def jlit(v):
        return "NULL" if v is None else lit(json.dumps(v)) + "::jsonb"

    for r_ in ("anon", "authenticated", "service_role"):
        q(f"do $$begin if not exists(select 1 from pg_roles where rolname='{r_}') then create role {r_}; end if; end$$")
    q("drop view if exists v_destek_donem")
    q("drop table if exists ref_kayitlari, ref_butce cascade")
    q("create table ref_kayitlari (id bigint primary key, firma_id bigint, tutar numeric, doviz text, durum text, "
      "yil integer, tarih date, aylik jsonb, kategori text, kategori_tutar jsonb, ref_no text)")
    q("create table ref_butce (id bigint primary key, firma_id bigint, tur text, yon text, tutar numeric, doviz text, "
      "fatura_tarih date, marka text, ref_no text)")
    for i, f, t, d, du, y, ta, a in REF:
        q(f"insert into ref_kayitlari (id, firma_id, tutar, doviz, durum, yil, tarih, aylik) values "
          f"({i}, {f}, {t}, {lit(d)}, {lit(du)}, {lit(y)}, {lit(ta)}, {jlit(a)})")
    for i, f, tu, yo, t, d, ft in BUTCE:
        q(f"insert into ref_butce (id, firma_id, tur, yon, tutar, doviz, fatura_tarih) values "
          f"({i}, {f}, {lit(tu)}, {lit(yo)}, {t}, {lit(d)}, {lit(ft)})")
    r = subprocess.run(["psql", pg, "-v", "ON_ERROR_STOP=1", "-q", "-f", str(KOK / "veritabani" / "16_destek_donem.sql")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

    # Python hesabı aynı satırları PostgREST'in döndüreceği biçimde okusun
    tablolar = {t: json.loads(q(f"select coalesce(json_agg(x), '[]') from {t} x")) for t in ("ref_kayitlari", "ref_butce")}
    assert any(isinstance(x["aylik"], str) for x in tablolar["ref_kayitlari"])            # metin saklama gerçekten var
    monkeypatch.setattr(R, "get_client", lambda: type("C", (), {"table": lambda s, t: _Q(tablolar[t])})())

    def anahtar(tur, doviz, tarih, tutar):
        return ((tur or "Diğer").strip() or "Diğer", str(doviz or "USD").strip().upper() or "USD",
                str(tarih or "")[:10], round(float(tutar), 4))

    for b, e in DONEMLER:
        py = [dict(h, donem=h.get("fatura_tarih")) for h in R.get_tum_butce_harcamalari(b, e)]
        py += [dict(x, tur="Ref No") for x in R.get_tum_ref_tutarlari(b, e)]
        py_c = Counter(anahtar(h.get("tur"), h.get("doviz"), h.get("donem") or h.get("tarih"), h["tutar"]) for h in py)
        gor = json.loads(q(f"select coalesce(json_agg(v), '[]') from v_destek_donem v "
                           f"where donem_bas <= '{e}' and donem_bit >= '{b}'"))
        gor_c = Counter(anahtar(v["tur"], v["doviz"], v["donem"], v["tutar"]) for v in gor)
        assert gor_c == py_c, (b, e, gor_c - py_c, py_c - gor_c)
    assert q("select count(*) from v_destek_donem") != "0"
