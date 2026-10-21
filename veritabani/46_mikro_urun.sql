-- ════════════════════════════════════════════════════════════════════
-- 46 · Mikro ürün kartları, barkodlar, satış fiyat listeleri (Ekim 2026)
--
-- İSTEK (kullanıcı): "Mikro'da yeni ürün açılınca programa da gelsin. Stok kartları Mikro'da bazı modellerde
--   'Fazeon X...' diye başlıyor; Fazeon olmasın, kodun önünde sadece kod olsun."
--   Aktarıcı (araclar/mikro_aktarici/mikro_kayran.py: stok_kart, stok_barkod, satis_fiyat, fiyat_liste) Mikro'daki
--   kartları, barkodları ve satış fiyat listelerini her turda tam çeker. Uygulamaya yazım kayranpm/mikro_urun.py'de:
--   yeni kart açılır (SKU shared.utils.sku_anahtar ile), mevcut kartta yalnız BOŞ alanlar dolar; fiyat listesi
--   kullanıcı onayından sonra. Garanti / GTİP / ölçü uygulama tablosuna yazılmaz, stok kartında buradan okunur.
--
-- Tablolar yalnız aktarıcının kopyası (kaynak Mikro). Yalnız service_role.
-- GERİ ALMA: DROP TABLE mikro_stok_kart, mikro_stok_barkod, mikro_satis_fiyat, mikro_fiyat_liste;
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.mikro_stok_kart (
    sto_kod text PRIMARY KEY, sto_isim text, sto_kisa_ismi text, sto_yabanci_isim text, sto_marka_kodu text,
    sto_kategori_kodu text, sto_anagrup_kod text, anagrup_isim text, sto_altgrup_kod text, altgrup_isim text,
    sto_model_kodu text, sto_uretici_kodu text, sto_garanti_sure integer, sto_garanti_sure_tipi integer,
    sto_gtipno text, sto_mensei text, sto_birim1_ad text, sto_birim1_agirlik numeric, sto_birim1_en numeric,
    sto_birim1_boy numeric, sto_birim1_yukseklik numeric, sto_pasif integer, sto_satis_dursun integer,
    sto_create_date timestamp, sto_lastup_date timestamp, senk_zamani timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.mikro_stok_barkod (
    bar_guid uuid PRIMARY KEY, bar_kodu text, bar_stokkodu text, bar_barkodtipi integer, bar_birimpntr integer,
    bar_master integer, bar_lastup_date timestamp, senk_zamani timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS mikro_stok_barkod_stok_idx ON public.mikro_stok_barkod (bar_stokkodu);

CREATE TABLE IF NOT EXISTS public.mikro_satis_fiyat (
    sfiyat_guid uuid PRIMARY KEY, sfiyat_stokkod text, sfiyat_listesirano integer, sfiyat_deposirano integer,
    sfiyat_odemeplan integer, sfiyat_birim_pntr integer, sfiyat_fiyati numeric, sfiyat_doviz integer,
    sfiyat_lastup_date timestamp, senk_zamani timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS mikro_satis_fiyat_stok_idx ON public.mikro_satis_fiyat (sfiyat_stokkod);

CREATE TABLE IF NOT EXISTS public.mikro_fiyat_liste (
    sfl_sirano integer PRIMARY KEY, sfl_aciklama text, sfl_kdvdahil integer, sfl_doviz_uygulama integer,
    sfl_sabit_doviz integer, sfl_ilktarih timestamp, sfl_sontarih timestamp, sfl_lastup_date timestamp,
    senk_zamani timestamptz NOT NULL DEFAULT now()
);

DO $g$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['mikro_stok_kart','mikro_stok_barkod','mikro_satis_fiyat','mikro_fiyat_liste'] LOOP
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
