-- ════════════════════════════════════════════════════════════════════
-- 54 · Mikro stok maliyeti (Ekim 2026)
--
-- İSTEK (kullanıcı, 22.10.2026): "Mikro'da ürünlerin maliyeti, paçalı vs neyse programda da ona göre revize
--   olsun. Mikro'daki veriler baz alınsın, oradaki datalar hep doğrudur."
-- mikro_stok_maliyet: aktarıcının STOK_HAREKETLERI_OZET kopyası, stok × mali yıl × hareket cinsi toplamı
--   (giriş / çıkış miktarı ve Mikro'nun maliyet tutarları: ana = TL, alt = alternatif döviz, belge = fatura değeri).
--   Yalnız aktarıcı yazar (her turda tam çekilir); uygulama okur (kayranpm/mikro_maliyet.py).
--
-- GERİ ALMA: DROP TABLE mikro_stok_maliyet;
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.mikro_stok_maliyet (
    stok_kod text NOT NULL, yil integer NOT NULL, hareket_cins integer NOT NULL,
    giris numeric, giris_iade numeric, cikis numeric, cikis_iade numeric,
    ana_giris numeric, ana_giris_iade numeric, ana_cikis numeric, ana_cikis_iade numeric,
    alt_giris numeric, alt_giris_iade numeric, alt_cikis numeric, alt_cikis_iade numeric,
    belge_ana_giris numeric, belge_alt_giris numeric,
    senk_zamani timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (stok_kod, yil, hareket_cins)
);

DO $g$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['mikro_stok_maliyet'] LOOP
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
