-- ════════════════════════════════════════════════════════════════════
-- 39 · Mikro muhasebe ham verisi (Ekim 2026, Mikro adım 1)
--
-- İSTEK (kullanıcı): "Olabildiğince az dosya upload / elle giriş; olabilecek tüm veriler Mikro'dan."
--   Adım 1 (muhasebe): banka / kasa bakiyeleri, çekler, cari alacaklar, gider. Aktarıcı ham veriyi
--   aynen çeker; bakiye ve eşleme formülleri uygulamada eski Excel değerleriyle karşılaştırılarak kurulur
--   (sunucuya her denemede dokunmamak için). Keşifte görülen kolon adları ve tipleri.
--
-- Tablolar yalnız aktarıcının kopyası (kaynak Mikro, her gece baştan çekilir). Yalnız service_role.
-- GERİ ALMA: DROP TABLE mikro_cari_hareket, mikro_cari_kart, mikro_banka_kart, mikro_kasa_kart,
--            mikro_depo_kart, mikro_cek, mikro_muhasebe_ay, mikro_hesap_plani;
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.mikro_cari_hareket (
    cha_guid uuid PRIMARY KEY, cha_evrak_tip integer, cha_evrakno_seri text, cha_evrakno_sira integer,
    cha_satir_no integer, cha_tarihi timestamp, cha_tip integer, cha_cinsi integer, cha_normal_iade integer,
    cha_cari_cins integer, cha_kod text, cha_ciro_cari_kodu text, cha_d_cins integer, cha_d_kur numeric,
    cha_altd_kur numeric, cha_karsidcinsi integer, cha_karsid_kur numeric, cha_meblag numeric, cha_vade integer,
    cha_aciklama text, cha_belge_no text, cha_eximkodu text, cha_srmrkkodu text, cha_kasa_hizmet integer,
    cha_kasa_hizkod text, cha_trefno text, cha_sntck_poz integer, cha_lastup_date timestamp,
    senk_zamani timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS mikro_cari_hareket_kod_idx ON public.mikro_cari_hareket (cha_cari_cins, cha_kod);

CREATE TABLE IF NOT EXISTS public.mikro_cari_kart (
    cari_kod text PRIMARY KEY, cari_unvan1 text, cari_doviz_cinsi integer, cari_muh_kod text,
    cari_grup_kodu text, cari_sektor_kodu text, cari_lastup_date timestamp,
    senk_zamani timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.mikro_banka_kart (
    ban_kod text PRIMARY KEY, ban_ismi text, ban_sube text, ban_doviz_cinsi integer, ban_hesap_tip integer,
    ban_muh_kod text, senk_zamani timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.mikro_kasa_kart (
    kas_kod text PRIMARY KEY, kas_isim text, kas_doviz_cinsi integer, kas_tip integer,
    senk_zamani timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.mikro_depo_kart (
    dep_no integer PRIMARY KEY, dep_adi text, senk_zamani timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.mikro_cek (
    sck_guid uuid PRIMARY KEY, sck_tip integer, sck_refno text, sck_no text, sck_vade timestamp, sck_tutar numeric,
    sck_doviz integer, sck_doviz_kur numeric, sck_odenen numeric, sck_borclu text, sck_sonpoz integer,
    sck_sahip_cari_cins integer, sck_sahip_cari_kodu text, sck_nerede_cari_cins integer, sck_nerede_cari_kodu text,
    sck_bankano text, sck_banka_adres1 text, sck_sube_adres2 text, sck_hesapno_sehir text,
    sck_duzen_tarih timestamp, sck_son_hareket_tarihi timestamp, sck_lastup_date timestamp,
    senk_zamani timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.mikro_muhasebe_ay (
    yil integer NOT NULL, ay integer NOT NULL, hesap_kod text NOT NULL, borc numeric, alacak numeric, satir integer,
    senk_zamani timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (yil, ay, hesap_kod)
);
CREATE TABLE IF NOT EXISTS public.mikro_hesap_plani (
    muh_hesap_kod text PRIMARY KEY, muh_hesap_isim1 text, senk_zamani timestamptz NOT NULL DEFAULT now()
);

DO $g$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['mikro_cari_hareket','mikro_cari_kart','mikro_banka_kart','mikro_kasa_kart',
                             'mikro_depo_kart','mikro_cek','mikro_muhasebe_ay','mikro_hesap_plani'] LOOP
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
