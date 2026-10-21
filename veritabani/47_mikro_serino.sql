-- ════════════════════════════════════════════════════════════════════
-- 47 · Mikro seri numarası tanımları (Ekim 2026, teknik servis)
--
-- İSTEK (kullanıcı): seri no bilgisi dosya yükleme / elle giriş yerine Mikro'dan.
--   Aktarıcının "serino" sorgusu Mikro STOK_SERINO_TANIMLARI'nı aynen çeker (artımlı, chz_lastup_date ile; gece
--   tam aktarım). Teknik servis mal kabulü seri no'dan stok kodu, kime satıldığı, satış belgesi ve garanti
--   bitişini gösterir (teknikservis/mikro_serino.py). Tablo yoksa ekran eski davranışına döner.
--   seri_anahtar: aramada kullanılan kural (boşluksuz, BÜYÜK harf) — uygulamadaki seri_anahtar() ile aynı.
--
-- Tablo yalnız aktarıcının kopyası (kaynak Mikro). Yalnız service_role.
-- GERİ ALMA: DROP TABLE mikro_serino;
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.mikro_serino (
    chz_guid uuid PRIMARY KEY, chz_serino text, chz_stok_kodu text, sto_isim text, chz_iptal integer,
    chz_lotno text, chz_uretim_tarihi timestamp, chz_aciklama1 text,
    chz_al_tarih timestamp, chz_al_evr_seri text, chz_al_evr_sira integer, chz_al_cari_kodu text,
    chz_al_fiati_ana numeric, chz_al_fiati_alt numeric, chz_al_fiati_orj numeric,
    chz_st_tarih timestamp, chz_st_evr_seri text, chz_st_evr_sira integer, chz_st_cari_kodu text,
    chz_st_fiati_ana numeric, chz_st_fiati_alt numeric, chz_st_fiati_orj numeric,
    chz_grn_bas_tarihi timestamp, chz_grn_bit_tarihi timestamp,
    chz_musteri_garanti_baslangic timestamp, chz_musteri_garanti_bitis timestamp,
    chz_create_date timestamp, chz_lastup_date timestamp,
    senk_zamani timestamptz NOT NULL DEFAULT now(),
    seri_anahtar text GENERATED ALWAYS AS (upper(regexp_replace(coalesce(chz_serino, ''), '\s', '', 'g'))) STORED
);
CREATE INDEX IF NOT EXISTS mikro_serino_anahtar_idx ON public.mikro_serino (seri_anahtar);
CREATE INDEX IF NOT EXISTS mikro_serino_stok_idx ON public.mikro_serino (chz_stok_kodu);

DO $g$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['mikro_serino'] LOOP
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
