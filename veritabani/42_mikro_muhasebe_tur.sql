-- ════════════════════════════════════════════════════════════════════
-- 42 · Mikro muhasebe fiş türü (Ekim 2026)
--
-- SORUN: Mikro'nun yıl sonu kapanış fişi Aralık'ta 6xx/7xx hesaplarını sıfırlıyor (canlı 2025 Aralık gider
--   hesapları: borç 21.179.807,31 · alacak 63.071.734,60). mikro_muhasebe_ay fiş türünü ayırmadığı için gider
--   tablosu (kayranacc/mikro_gider.py) yalnız 2026'dan; 2026 Aralık'ı da kapanışla sıfır görünecekti.
-- ÇÖZÜM: aktarıcı iki sorgu daha çeker (araclar/mikro_aktarici/mikro_kayran.py):
--   muhasebe_tur    → mikro_muhasebe_tur: ay × fiş türü dağılımı (kapanış türünü doğrulamak için; küçük)
--   muhasebe_ay_tur → mikro_muhasebe_ay_tur: ay × hesap × fiş türü toplamı (gider tablosu kapanışı ayıklar)
--   fis_tur boşsa -1. mikro_muhasebe_ay olduğu gibi kalır.
--
-- Tablolar yalnız aktarıcının kopyası (kaynak Mikro). Yalnız service_role.
-- GERİ ALMA: DROP TABLE mikro_muhasebe_tur, mikro_muhasebe_ay_tur;
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.mikro_muhasebe_tur (
    yil integer NOT NULL, ay integer NOT NULL, fis_tur integer NOT NULL, satir integer, borc numeric,
    alacak numeric, gider_borc numeric, gider_alacak numeric,
    senk_zamani timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (yil, ay, fis_tur)
);

CREATE TABLE IF NOT EXISTS public.mikro_muhasebe_ay_tur (
    yil integer NOT NULL, ay integer NOT NULL, hesap_kod text NOT NULL, fis_tur integer NOT NULL,
    borc numeric, alacak numeric, satir integer,
    senk_zamani timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (yil, ay, hesap_kod, fis_tur)
);

DO $g$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['mikro_muhasebe_tur','mikro_muhasebe_ay_tur'] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
            EXECUTE format('REVOKE ALL ON public.%I FROM anon', t);
        END IF;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
            EXECUTE format('REVOKE ALL ON public.%I FROM authenticated', t);
        END IF;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO service_role', t);
        END IF;
    END LOOP;
END
$g$;

NOTIFY pgrst, 'reload schema';
