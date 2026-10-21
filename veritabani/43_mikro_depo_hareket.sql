-- ════════════════════════════════════════════════════════════════════
-- 43 · Mikro depo hareketleri (Ekim 2026, Mikro adım 4: Happy Life ve stok yaşı)
--
-- İSTEK (kullanıcı): "Happy Life stok raporu — ürünler ithal edilip Happy depoya yerleştirildikten sonra
--   otomatik stok yaşına kadar tüm datalar Mikro'dan alınsın."
--   Aktarıcının "depo_hareket" sorgusu Mikro STOK_HAREKETLERI'nden 2025'ten beri bir depoya giren ya da
--   depodan çıkan bütün hareketleri (giriş, çıkış, depolar arası sevk) aynen çeker. Depoya giriş tarihi ve
--   FIFO partileri uygulamada hesaplanır (kayranpm/mikro_depo.py); kullanıcı onayından ÖNCE salt okunur.
--   sth_iptal de çekilir: sonradan iptal edilen hareket artımlı turda güncellenir, uygulama onu saymaz.
--
-- Tablo yalnız aktarıcının kopyası (kaynak Mikro). Yalnız service_role.
-- GERİ ALMA: DROP TABLE mikro_depo_hareket;
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.mikro_depo_hareket (
    sth_guid uuid PRIMARY KEY, sth_tarih timestamp, sth_tip integer, sth_cins integer, sth_evraktip integer,
    sth_normal_iade integer, sth_evrakno_seri text, sth_evrakno_sira integer, sth_stok_kod text,
    sth_miktar numeric, sth_giris_depo_no integer, sth_cikis_depo_no integer, sth_cari_kodu text,
    sth_exim_kodu text, sth_parti_kodu text, sth_iptal boolean, sth_lastup_date timestamp,
    senk_zamani timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS mikro_depo_hareket_stok_idx ON public.mikro_depo_hareket (sth_stok_kod);

DO $g$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['mikro_depo_hareket'] LOOP
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
