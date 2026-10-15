-- ════════════════════════════════════════════════════════════════════
-- 36 · Teknik servis ürün notları (Ekim 2026)
--
-- İSTEK (teknik servis): ithalat modeli seçilip ürün hakkında not eklenebilsin; notlar herkese açık.
--   Arıza eğilimleri (ör. 34/49 inç panel sorunları), tasarım ve kullanıcı deneyimi gözlemleri,
--   eleştiriler (ör. F21 kasada ön paneldeki manyetik logonun yeri).
-- Tablo yalnız notları tutar; başka hiçbir tabloya dokunmaz. Tekrar çalıştırılabilir.
-- Yalnız uygulamanın yetkili anahtarı (service_role) erişir.
-- GERİ ALMA: DROP TABLE public.ts_urun_notlari;
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.ts_urun_notlari (
    id          bigserial PRIMARY KEY,
    stok_kodu   text NOT NULL,
    urun_adi    text NOT NULL DEFAULT '',
    konu        text NOT NULL DEFAULT '',
    not_metni   text NOT NULL,
    yazan       text NOT NULL DEFAULT '',
    olusturma   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ts_urun_notlari_stok_idx ON public.ts_urun_notlari (stok_kodu);

ALTER TABLE public.ts_urun_notlari ENABLE ROW LEVEL SECURITY;
DO $g$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON public.ts_urun_notlari FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON public.ts_urun_notlari FROM authenticated;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.ts_urun_notlari TO service_role;
        GRANT USAGE, SELECT ON SEQUENCE public.ts_urun_notlari_id_seq TO service_role;
    END IF;
END
$g$;

NOTIFY pgrst, 'reload schema';
