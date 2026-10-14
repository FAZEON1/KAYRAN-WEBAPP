"""Kayıtlı şema değişikliği (migration) uygulayıcı.

veritabani/NN_ad.sql dosyalarını numara sırasıyla uygular ve her birini
`sema_gecmisi(dosya, sha256, uygulama_zamani, uygulayan)` tablosuna yazar.

- Varsayılan KURU çalışır: yalnız ne uygulanacağını listeler, hiçbir şey yazmaz.
- `--uygula` ile gerçekten uygular; her dosya kendi işleminde (transaction):
  dosya hata verirse o dosya geri alınır, sonrakiler çalışmaz.
- Daha önce uygulanmış dosya atlanır. İçeriği (sha256) kayıttan sonra
  değişmişse UYARI verilir, yeniden uygulanmaz.
- `--isaretle`: dosyaları ÇALIŞTIRMADAN "uygulanmış" diye kaydeder (canlıda
  elle kurulmuş eski dosyaları kayda geçirmek için). `--kadar NN` ile sınırlanır.
- İlk satırlarında `-- UYGULA: HAYIR` yazan dosya (ör. öneri dosyaları) hiç
  uygulanmaz, listede "öneri" diye görünür.
- Bağlantı `DATABASE_URL` ortam değişkeninden (psycopg 3). Adres canlı Supabase
  projesini gösteriyorsa `--canli` bayrağı olmadan HİÇBİR kipte çalışmaz.

Örnekler:
    python veritabani/uygula.py                    # kuru: plan
    python veritabani/uygula.py --uygula           # yerel/yeni veritabanına kur
    python veritabani/uygula.py --canli            # canlı için plan (yazmaz)
    python veritabani/uygula.py --canli --isaretle --kadar 28 --uygula
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
DOSYA_DESENI = re.compile(r"^(\d{2,})_[0-9A-Za-z_\-]+\.sql$")
UYGULAMA_YOK = re.compile(r"^\s*--\s*UYGULA\s*:\s*HAYIR\b", re.IGNORECASE | re.MULTILINE)
CANLI_IPUCLARI = ("qspwlqegoeudifxxrxcj", "supabase.co", "supabase.com")

GECMIS_DDL = """
CREATE TABLE IF NOT EXISTS public.sema_gecmisi (
    dosya           text PRIMARY KEY,
    sha256          text NOT NULL,
    uygulama_zamani timestamptz NOT NULL DEFAULT now(),
    uygulayan       text
);
ALTER TABLE public.sema_gecmisi ENABLE ROW LEVEL SECURITY;
DO $g$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON public.sema_gecmisi FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON public.sema_gecmisi FROM authenticated;
    END IF;
END
$g$;
"""
GECMIS_VAR_MI = "SELECT to_regclass('public.sema_gecmisi') IS NOT NULL"
GECMIS_OKU = "SELECT dosya, sha256 FROM public.sema_gecmisi"
GECMIS_YAZ = ("INSERT INTO public.sema_gecmisi (dosya, sha256, uygulayan) VALUES (%s, %s, %s) "
              "ON CONFLICT (dosya) DO NOTHING")

# Plan durumları
UYGULANACAK = "uygulanacak"
UYGULANMIS = "uygulanmış"
DEGISMIS = "DEĞİŞMİŞ"
ONERI = "öneri"


@dataclass
class Adim:
    dosya: str
    yol: Path
    sha256: str
    durum: str


def dosyalari_bul(klasor: Path = KLASOR) -> list[Path]:
    """NN_ad.sql dosyaları; numaraya (sayı olarak), sonra ada göre sıralı."""
    bulunan = [p for p in Path(klasor).iterdir() if p.is_file() and DOSYA_DESENI.match(p.name)]
    return sorted(bulunan, key=lambda p: (int(DOSYA_DESENI.match(p.name).group(1)), p.name))


def dosya_sha(yol: Path) -> str:
    return hashlib.sha256(Path(yol).read_bytes()).hexdigest()


def numara(dosya: str) -> int:
    return int(DOSYA_DESENI.match(dosya).group(1))


def oneri_mi(yol: Path) -> bool:
    bas = Path(yol).read_text(encoding="utf-8-sig", errors="replace")[:2000]
    return bool(UYGULAMA_YOK.search(bas))


def plan_yap(dosyalar: list[Path], gecmis: dict[str, str], kadar: int | None = None) -> list[Adim]:
    plan = []
    for yol in dosyalar:
        if kadar is not None and numara(yol.name) > kadar:
            continue
        sha = dosya_sha(yol)
        if yol.name in gecmis:
            durum = UYGULANMIS if gecmis[yol.name] == sha else DEGISMIS
        elif oneri_mi(yol):
            durum = ONERI
        else:
            durum = UYGULANACAK
        plan.append(Adim(yol.name, yol, sha, durum))
    return plan


def canli_mi(url: str) -> bool:
    k = (url or "").lower()
    return any(i in k for i in CANLI_IPUCLARI)


def gecmisi_oku(conn) -> dict[str, str]:
    """Kayıt tablosu yoksa boş döner (tabloyu OLUŞTURMAZ)."""
    var = conn.execute(GECMIS_VAR_MI).fetchone()[0]
    if not var:
        return {}
    return {d: s for d, s in conn.execute(GECMIS_OKU).fetchall()}


def plani_yaz(plan: list[Adim], cikti=print) -> None:
    if not plan:
        cikti("Uygulanacak dosya yok.")
        return
    for a in plan:
        cikti(f"  {a.durum:<12} {a.dosya}  {a.sha256[:12]}")
    for a in plan:
        if a.durum == DEGISMIS:
            cikti(f"UYARI: {a.dosya} uygulandıktan sonra değişmiş (sha farklı). Yeniden "
                  f"UYGULANMAZ; değişikliği yeni numaralı bir dosyaya taşıyın.")


def uygula(conn, plan: list[Adim], uygulayan: str, isaretle: bool = False, cikti=print) -> list[str]:
    """Bekleyen adımları uygular (ya da yalnız kaydeder). Uygulananların adlarını döndürür."""
    bekleyen = [a for a in plan if a.durum == UYGULANACAK]
    if not bekleyen:
        return []
    with conn.transaction():
        conn.execute(GECMIS_DDL)
    yapilan = []
    for a in bekleyen:
        sql = a.yol.read_text(encoding="utf-8-sig")
        try:
            with conn.transaction():
                if not isaretle:
                    conn.execute(sql)
                conn.execute(GECMIS_YAZ, (a.dosya, a.sha256, uygulayan))
        except Exception as e:  # dosya kendi işleminde geri alındı
            cikti(f"HATA: {a.dosya} uygulanamadı, geri alındı; sonrakiler çalıştırılmadı.\n  {e}")
            raise
        cikti(("kaydedildi  " if isaretle else "uygulandı   ") + a.dosya)
        yapilan.append(a.dosya)
    return yapilan


def _baglan(url: str):
    import psycopg  # yalnız gerçek bağlantıda gerekir
    return psycopg.connect(url, autocommit=True)


def main(argv: list[str] | None = None, baglan=_baglan, ortam=os.environ, cikti=print) -> int:
    ap = argparse.ArgumentParser(description="veritabani/NN_*.sql dosyalarını kayıtlı olarak uygular.")
    kip = ap.add_mutually_exclusive_group()
    kip.add_argument("--kuru", action="store_true", help="(varsayılan) yalnız listele, yazma")
    kip.add_argument("--uygula", action="store_true", help="gerçekten uygula")
    ap.add_argument("--isaretle", action="store_true",
                    help="dosyaları çalıştırmadan uygulanmış diye kaydet (--uygula ile)")
    ap.add_argument("--kadar", type=int, default=None, help="yalnız bu numaraya kadar olan dosyalar")
    ap.add_argument("--canli", action="store_true", help="canlı Supabase projesine karşı çalışmaya izin ver")
    ap.add_argument("--uygulayan", default=None, help="kayda yazılacak ad (varsayılan: sistem kullanıcısı)")
    ap.add_argument("--klasor", default=str(KLASOR), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    dosyalar = dosyalari_bul(Path(a.klasor))
    url = ortam.get("DATABASE_URL", "")

    if url and canli_mi(url) and not a.canli:
        cikti("DURDU: DATABASE_URL canlı Supabase projesini gösteriyor. Bilerek çalıştırıyorsanız "
              "--canli ekleyin (önce kuru: --canli tek başına yalnız listeler).")
        return 2

    if not url:
        if a.uygula:
            cikti("DURDU: DATABASE_URL tanımlı değil.")
            return 2
        cikti("DATABASE_URL yok — geçmiş okunamadı; tüm dosyalar listeleniyor (kuru).")
        plani_yaz(plan_yap(dosyalar, {}, a.kadar), cikti)
        return 0

    conn = baglan(url)
    try:
        plan = plan_yap(dosyalar, gecmisi_oku(conn), a.kadar)
        cikti(("UYGULAMA" if a.uygula else "KURU ÇALIŞMA (hiçbir şey yazılmaz)")
              + (" — yalnız işaretleme" if a.isaretle else "")
              + (" — CANLI" if canli_mi(url) else ""))
        plani_yaz(plan, cikti)
        if not a.uygula:
            n = sum(1 for x in plan if x.durum == UYGULANACAK)
            cikti(f"{n} dosya uygulanmayı bekliyor. Uygulamak için --uygula ekleyin.")
            return 0
        kim = a.uygulayan or ortam.get("UYGULAYAN") or getpass.getuser()
        try:
            yapilan = uygula(conn, plan, kim, isaretle=a.isaretle, cikti=cikti)
        except Exception:
            return 1
        cikti(f"Bitti: {len(yapilan)} dosya.")
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
