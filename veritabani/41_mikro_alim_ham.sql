-- ════════════════════════════════════════════════════════════════════
-- 41 · Mikro alım ham verisi (Ekim 2026, Mikro adım 3a)
--
-- İSTEK (kullanıcı): "Olabildiğince az dosya upload / elle giriş; olabilecek tüm veriler Mikro'dan."
--   Adım 3 (alımlar): ithalat dosyaları, ürün satırları, masraflar, yurt içi alımlar. Aktarıcı ham veriyi aynen
--   çeker; dosya ↔ uygulama eşleşmesi ve paçal karşılaştırması uygulamada, kullanıcı onayından ÖNCE salt okunur.
--   Ürün satırı ithalat dosyasına sth_exim_kodu (= ith_kodu, ör. VANEX-015) ile bağlı.
--
-- Tablolar yalnız aktarıcının kopyası (kaynak Mikro). Yalnız service_role.
-- GERİ ALMA: DROP TABLE mikro_ithalat_dosya, mikro_alim_satir;
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.mikro_ithalat_dosya (
    ith_kodu text PRIMARY KEY, ith_ismi text, ith_satici text, ith_dovizcinsi integer, ith_teslimsekli text,
    ith_odemesekli text, ith_ggb_tarihi timestamp, ith_ggb_no text, ith_serbest_dolasim_tarihi timestamp,
    ith_create_date timestamp, ith_lastup_date timestamp, senk_zamani timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.mikro_alim_satir (
    sth_guid uuid PRIMARY KEY, sth_tarih timestamp, sth_tip integer, sth_cins integer, sth_evraktip integer,
    sth_normal_iade integer, sth_evrakno_seri text, sth_evrakno_sira integer, sth_stok_kod text, sth_cari_kodu text,
    sth_miktar numeric, sth_tutar numeric, sth_iskonto numeric, sth_masraf numeric, sth_har_doviz_cinsi integer,
    sth_har_doviz_kuru numeric, sth_alt_doviz_kuru numeric, sth_giris_depo_no integer, sth_exim_kodu text,
    sth_bagli_ithalat_kodu text, sth_fat_uid uuid, sth_lastup_date timestamp,
    senk_zamani timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS mikro_alim_satir_exim_idx ON public.mikro_alim_satir (sth_exim_kodu);

DO $g$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['mikro_ithalat_dosya','mikro_alim_satir'] LOOP
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
