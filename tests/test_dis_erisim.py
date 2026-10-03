# -*- coding: utf-8 -*-
"""Herkese açık (anon) anahtarın erişimi kapalı (veritabani/15_dis_erisim_kapat.sql, Ekim 2026).

Canlıda bulundu: 18 tablo "allow_all" kuralıyla herkese açık anahtara okunur / değiştirilir /
silinir durumdaydı (ürünler ve maliyetler dahil); satış kâr görünümleri sahibinin yetkisiyle
çalışıp RLS'yi aşıyordu. Uygulama, gece yedeği ve GitHub işleri service_role ile bağlanır
(istek kayıtlarında doğrulandı); bu yüzden herkese açık rollerin bütün yetkileri geri alındı.
Bu test, ileride eklenecek bir SQL dosyasının kapıyı yeniden açmasını engeller.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
SQL = KOK / "veritabani" / "15_dis_erisim_kapat.sql"


def _kod(metin):
    """Yorum satırları atılmış SQL."""
    return "\n".join(s for s in metin.splitlines() if not s.strip().startswith("--"))


def test_kapatma_dosyasi_tum_yetkileri_geri_aliyor():
    s = _kod(SQL.read_text(encoding="utf-8"))
    assert "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;" in s
    assert "REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;" in s
    assert "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;" in s
    for v in ("v_satis_pnl", "v_destek_donem"):
        assert f"ALTER VIEW IF EXISTS {v} SET (security_invoker = on);" in s
    assert "GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;" in s     # uygulama etkilenmez


def test_hicbir_sql_dosyasi_herkese_yetki_vermiyor():
    kotu = []
    for f in sorted((KOK / "veritabani").glob("*.sql")):
        s = _kod(f.read_text(encoding="utf-8"))
        for m in re.finditer(r"GRANT[^;]*\bTO\b[^;]*;", s, re.I | re.S):
            if re.search(r"\b(anon|authenticated|public)\b", m.group(0).split(" TO ", 1)[-1], re.I):
                kotu.append(f"{f.name}: {m.group(0)[:80]}")
        for m in re.finditer(r"CREATE POLICY[^;]*;", s, re.I | re.S):
            if re.search(r"USING\s*\(\s*true\s*\)", m.group(0), re.I):
                kotu.append(f"{f.name}: {m.group(0)[:80]}")
    assert not kotu, kotu


# ── Gerçek PostgreSQL'de (yalnız yerelde; CI'da atlanır) ───────────
@pytest.mark.skipif(not os.environ.get("KAYRAN_TEST_PG") or not shutil.which("psql"),
                    reason="KAYRAN_TEST_PG (psql bağlantı dizesi) yok")
def test_sql_anon_kapali_service_role_acik():
    pg = os.environ["KAYRAN_TEST_PG"]

    def q(sql, rol=None):
        on = f"set role {rol}; " if rol else ""
        return subprocess.run(["psql", pg, "-v", "ON_ERROR_STOP=1", "-qAt", "-c", on + sql],
                              capture_output=True, text=True)
    for r in ("anon", "authenticated", "service_role"):
        q(f"do $$begin if not exists(select 1 from pg_roles where rolname='{r}') then create role {r}; end if; end$$")
    q("alter role service_role bypassrls")
    q("drop table if exists urunler, satislar cascade")
    q("create table urunler (id serial primary key, maliyet numeric)")
    q("alter table urunler enable row level security")
    q("create policy allow_all_urunler on urunler for all using (true) with check (true)")
    q("create table satislar (id serial primary key, adet int)")
    q("alter table satislar enable row level security")
    q("insert into urunler (maliyet) values (10)")
    q("insert into satislar (adet) values (3)")
    q("create or replace view v_satis_pnl as select sum(adet) t from satislar")
    q("grant usage on schema public to anon, authenticated, service_role")
    q("grant all on all tables in schema public to anon, authenticated")
    assert q("select count(*) from urunler", "anon").stdout.strip() == "1"          # açık (eski hâl)
    for _ in range(2):                                                                # iki kez: zararsız
        r = subprocess.run(["psql", pg, "-v", "ON_ERROR_STOP=1", "-q", "-f", str(SQL)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    assert "permission denied" in q("select count(*) from urunler", "anon").stderr
    assert "permission denied" in q("delete from urunler", "anon").stderr
    assert "permission denied" in q("select t from v_satis_pnl", "anon").stderr
    assert q("select count(*) from urunler", "service_role").stdout.strip() == "1"
    assert q("select t from v_satis_pnl", "service_role").stdout.strip() == "3"
    assert q("select count(*) from pg_policies where tablename = 'urunler'").stdout.strip() == "0"
