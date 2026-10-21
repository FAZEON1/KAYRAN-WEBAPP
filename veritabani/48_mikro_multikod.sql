-- ════════════════════════════════════════════════════════════════════
-- 48 · Mikro müşteri ürün kodları (Ekim 2026)
--
-- İSTEK (kullanıcı): "Olabildiğince az dosya upload / elle giriş; olabilecek tüm veriler Mikro'dan."
--   Haftalık müşteri raporu (Dosya kapısı "musteri_haftalik") müşteriden geldiği için yükleme kalır; rapordaki
--   müşteri kodu (D-market 'HBCV…') bizim SKU'ya Mikro'daki MULTIKOD_TANIMLARI ile bağlanır
--   (kayranpm/mikro_multikod.py). Eşleşme yalnız YENİ yüklemede yapılır; kayıtlı raporlar değişmez.
--
-- mikro_multikod: yalnız aktarıcının kopyası (kaynak Mikro, her turda tam çekilir). Yalnız service_role.
-- firma_stok.musteri_kodu: Mikro eşleşmesiyle bizim SKU'ya çevrilen satırda raporun kendi kodu
--   (ekranda "Mikro kod eşleşmesi"; boşsa satır eskisi gibi raporun koduyla yazılmıştır).
--
-- GERİ ALMA: DROP TABLE mikro_multikod; ALTER TABLE firma_stok DROP COLUMN musteri_kodu;
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.mikro_multikod (
    mcod_guid uuid PRIMARY KEY, mcod_carikodu text, mcod_stokkod text, mcod_caristok_kod text,
    mcod_caristok_ismi text, mcod_tipi integer, mcod_lastup_date timestamp,
    senk_zamani timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS mikro_multikod_cari_idx ON public.mikro_multikod (mcod_carikodu, mcod_caristok_kod);

ALTER TABLE public.firma_stok ADD COLUMN IF NOT EXISTS musteri_kodu text;

DO $g$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['mikro_multikod'] LOOP
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
