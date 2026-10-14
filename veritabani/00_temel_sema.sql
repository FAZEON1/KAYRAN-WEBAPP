-- ════════════════════════════════════════════════════════════════════
-- 00 · KAYRAN temel şema — veritabanını repodan sıfırdan kurmak için
--
-- Kaynak: canlı Supabase projesinin public şeması, 14.10.2026'da katalogdan
-- (information_schema / pg_catalog) SALT OKUNUR sorgularla çıkarıldı:
-- 68 tablo, 32 sıra (serial), 2 görünüm, 2 özet tablo (materialized view),
-- 4 fonksiyon, 9 tetikleyici, 11 yabancı anahtar, 4 CHECK, 59 indeks,
-- tüm tablolarda RLS açık (politika yok), anon/authenticated yetkisiz.
--
-- Tekrar çalıştırılabilir: IF NOT EXISTS / CREATE OR REPLACE / koşullu DO.
-- Var olan tabloya kolon EKLEMEZ, var olan veriye DOKUNMAZ.
--
-- Kullanım: boş bir veritabanında `python veritabani/uygula.py --uygula`
-- (bu dosya önce, sonra 04_… sırayla). Canlıda zaten kurulu olduğundan
-- canlıda çalıştırılmaz; yalnız kayda geçirilir (bkz. veritabani/BENIOKU.md).
--
-- Not: 04_…28_ dosyalarının eklediği her şey burada zaten var (canlının
-- bugünkü hâli). O dosyalar bu dosyadan sonra çalışınca hiçbir şey
-- değiştirmez (IF NOT EXISTS), yalnız başlangıç verisi ekleyenler (04) ekler.
-- ════════════════════════════════════════════════════════════════════

SET client_min_messages = warning;
SET search_path = public;

-- ─── 0) Supabase rolleri (düz Postgres'te yoksa oluştur) ───────────────
-- Supabase'te bu roller hazırdır; dokunulmaz.
DO $roller$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role NOLOGIN NOINHERIT BYPASSRLS;
    END IF;
END
$roller$;

-- Şema kullanım izni yalnız service_role'e (Supabase'te anon/authenticated'da zaten var;
-- tablolarda yetkileri olmadığı için bir şey göremezler — bkz. bölüm 10).
GRANT USAGE ON SCHEMA public TO service_role;

-- Supabase dosya deposu (storage) yalnız düz Postgres'te yoksa: 24_sirket_belgeleri.sql
-- storage.buckets'a kova ekler. Supabase'te bu şema hazırdır; aşağısı orada hiçbir şey yapmaz.
DO $depo$
BEGIN
    IF to_regclass('storage.buckets') IS NULL THEN
        CREATE SCHEMA IF NOT EXISTS storage;
        CREATE TABLE storage.buckets (
            id text PRIMARY KEY,
            name text NOT NULL,
            owner uuid,
            created_at timestamptz DEFAULT now(),
            updated_at timestamptz DEFAULT now(),
            public boolean DEFAULT false,
            file_size_limit bigint,
            allowed_mime_types text[]
        );
        CREATE TABLE storage.objects (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            bucket_id text REFERENCES storage.buckets(id),
            name text,
            created_at timestamptz DEFAULT now()
        );
    END IF;
END
$depo$;

-- ─── 1) Sıralar (serial kolonların) ────────────────────────────────────
CREATE SEQUENCE IF NOT EXISTS public.aktif_excel_verileri_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.aktif_manuel_kalemler_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.asistan_rapor_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.bankalar_id_seq AS integer;
CREATE SEQUENCE IF NOT EXISTS public.bildirim_ayarlari_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.bildirimler_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.bt_olcum_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.bt_rapor_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.cekler_id_seq AS integer;
CREATE SEQUENCE IF NOT EXISTS public.cop_kutusu_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.firma_stok_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.gorevler_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.gumruk_sorgulari_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.gunluk_giris_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.haftalar_id_seq AS integer;
CREATE SEQUENCE IF NOT EXISTS public.hata_kayitlari_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.hm_urun_karliligi_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.izin_talepleri_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.kampanya_urunler_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.kampanyalar_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.kullanici_durum_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.kullanici_sifreler_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.odemeler_id_seq AS integer;
CREATE SEQUENCE IF NOT EXISTS public.prim_gecmis_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.satin_alma_gecmisi_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.satislar_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.siparis_onerileri_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.sirket_belgeleri_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.soru_kayitlari_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.stok_hareketleri_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.talepler_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS public.virmanlar_id_seq AS bigint;

-- ─── 2) Tablolar (alfabetik) ───────────────────────────────────────────

-- Tek seferlik yedek tabloları (kanal birleştirme / Ekim 2026 temizliği).
-- Uygulama okumaz; canlıyla birebir olsun diye burada.
CREATE TABLE IF NOT EXISTS public._kanal_birlestirme_yedek (
    satis_id bigint NOT NULL,
    eski_kanal text NOT NULL,
    yedek_zamani timestamp with time zone DEFAULT now(),
    CONSTRAINT _kanal_birlestirme_yedek_pkey PRIMARY KEY (satis_id)
);

CREATE TABLE IF NOT EXISTS public._temizlik_yedek_202610 (
    id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
    tablo text NOT NULL,
    anahtar text NOT NULL,
    alan text NOT NULL,
    eski text,
    yeni text,
    satir jsonb NOT NULL,
    yedek_zamani timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT _temizlik_yedek_202610_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.aktif_excel_verileri (
    id bigint DEFAULT nextval('aktif_excel_verileri_id_seq'::regclass) NOT NULL,
    kullanici text NOT NULL,
    dosya_tipi text NOT NULL,
    veri_json text NOT NULL,
    olusturuldu timestamp with time zone DEFAULT now(),
    CONSTRAINT aktif_excel_verileri_pkey PRIMARY KEY (id),
    CONSTRAINT aktif_excel_verileri_kullanici_dosya_tipi_key UNIQUE (kullanici, dosya_tipi)
);

CREATE TABLE IF NOT EXISTS public.aktif_manuel_kalemler (
    id bigint DEFAULT nextval('aktif_manuel_kalemler_id_seq'::regclass) NOT NULL,
    kullanici text NOT NULL,
    aciklama text NOT NULL,
    tutar numeric(18,2) NOT NULL,
    para_birimi text DEFAULT 'USD'::text,
    tip text DEFAULT 'ekle'::text,
    olusturuldu timestamp with time zone DEFAULT now(),
    CONSTRAINT aktif_manuel_kalemler_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.alinan_destekler (
    id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
    firma text,
    tur text,
    donem text,
    tutar numeric,
    doviz text DEFAULT 'USD'::text,
    fatura_no text,
    aciklama text,
    created_at timestamp with time zone DEFAULT now(),
    kategori text,
    CONSTRAINT alinan_destekler_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.asistan_rapor (
    id bigint DEFAULT nextval('asistan_rapor_id_seq'::regclass) NOT NULL,
    zaman timestamp with time zone DEFAULT now() NOT NULL,
    asistan text NOT NULL,
    baslik text NOT NULL,
    ozet text,
    icerik text,
    telegram_gonderildi boolean DEFAULT false NOT NULL,
    CONSTRAINT asistan_rapor_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.audit_log (
    id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
    zaman timestamp without time zone,
    kullanici text,
    modul text,
    islem text,
    tablo text,
    kayit_id text,
    detay text,
    CONSTRAINT audit_log_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.bankalar (
    id integer DEFAULT nextval('bankalar_id_seq'::regclass) NOT NULL,
    hesap_adi text NOT NULL,
    para_birimi text DEFAULT 'TL'::text,
    bakiye numeric(18,2) DEFAULT 0,
    CONSTRAINT bankalar_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.bayi_giris_denemeleri (
    kullanici_adi text NOT NULL,
    basarisiz_sayi integer DEFAULT 0 NOT NULL,
    son_deneme timestamp with time zone,
    kilit_bitis timestamp with time zone,
    CONSTRAINT bayi_giris_denemeleri_pkey PRIMARY KEY (kullanici_adi)
);

CREATE TABLE IF NOT EXISTS public.bayi_kullanicilar (
    id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
    kullanici_adi text NOT NULL,
    sifre_hash text NOT NULL,
    cari_kod text,
    cari_unvan text NOT NULL,
    ad_soyad text,
    email text,
    telefon text,
    aktif boolean DEFAULT true NOT NULL,
    olusturma_tarihi timestamp with time zone DEFAULT now() NOT NULL,
    son_giris timestamp with time zone,
    notlar text,
    CONSTRAINT bayi_kullanicilar_pkey PRIMARY KEY (id),
    CONSTRAINT bayi_kullanicilar_kullanici_adi_key UNIQUE (kullanici_adi)
);

CREATE TABLE IF NOT EXISTS public.bildirim_ayarlari (
    id bigint DEFAULT nextval('bildirim_ayarlari_id_seq'::regclass) NOT NULL,
    email text DEFAULT ''::text NOT NULL,
    smtp_server text DEFAULT ''::text NOT NULL,
    smtp_port integer DEFAULT 587 NOT NULL,
    smtp_user text DEFAULT ''::text NOT NULL,
    smtp_password text DEFAULT ''::text NOT NULL,
    aktif boolean DEFAULT false NOT NULL,
    CONSTRAINT bildirim_ayarlari_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.bildirimler (
    id bigint DEFAULT nextval('bildirimler_id_seq'::regclass) NOT NULL,
    gonderen text DEFAULT 'ibrahim'::text NOT NULL,
    alici text NOT NULL,
    mesaj text NOT NULL,
    okundu boolean DEFAULT false,
    olusturma_tarihi timestamp with time zone DEFAULT now(),
    CONSTRAINT bildirimler_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.bt_olcum (
    id bigint DEFAULT nextval('bt_olcum_id_seq'::regclass) NOT NULL,
    zaman timestamp with time zone DEFAULT now() NOT NULL,
    modul text NOT NULL,
    sayfa text,
    ms integer NOT NULL,
    hata boolean DEFAULT false NOT NULL,
    kullanici text,
    CONSTRAINT bt_olcum_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.bt_rapor (
    id bigint DEFAULT nextval('bt_rapor_id_seq'::regclass) NOT NULL,
    zaman timestamp with time zone DEFAULT now() NOT NULL,
    tur text NOT NULL,
    baslik text NOT NULL,
    ozet text,
    durum text,
    pr_url text,
    olcut text,
    once numeric,
    sonra numeric,
    birim text,
    ayrinti jsonb,
    CONSTRAINT bt_rapor_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.cekler (
    id integer DEFAULT nextval('cekler_id_seq'::regclass) NOT NULL,
    ref_no text,
    vade text,
    meblagh numeric(18,2),
    kalan numeric(18,2),
    alici text,
    para_birimi text DEFAULT 'TL'::text,
    durum text DEFAULT 'Bekliyor'::text,
    cek_no text,
    tarih text,
    odenen numeric(18,2) DEFAULT 0,
    ch_kodu text,
    ch_ismi text,
    banka text,
    sube text,
    hesap_no text,
    CONSTRAINT cekler_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.cop_kutusu (
    id bigint DEFAULT nextval('cop_kutusu_id_seq'::regclass) NOT NULL,
    grup text NOT NULL,
    tablo text NOT NULL,
    modul text,
    silen text,
    zaman timestamp with time zone DEFAULT now() NOT NULL,
    adet integer DEFAULT 0 NOT NULL,
    satirlar jsonb NOT NULL,
    geri_alindi boolean DEFAULT false NOT NULL,
    geri_alan text,
    geri_alma_zamani timestamp with time zone,
    CONSTRAINT cop_kutusu_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.depo_manuel_takip (
    id bigint GENERATED BY DEFAULT AS IDENTITY NOT NULL,
    firma text,
    sku text,
    urun_adi text,
    fatura_adet integer DEFAULT 0,
    sevk_edilen integer DEFAULT 0,
    hareketler jsonb DEFAULT '[]'::jsonb,
    notlar text DEFAULT ''::text,
    olusturma timestamp without time zone DEFAULT now(),
    firma_adres text DEFAULT ''::text,
    firma_vd text DEFAULT ''::text,
    firma_vkn text DEFAULT ''::text,
    CONSTRAINT depo_manuel_takip_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.depo_sevk_log (
    id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
    sku text,
    urun_adi text,
    kaynak_depo text,
    hedef_depo text,
    adet integer,
    kullanici text,
    tarih text,
    sevk_tarihi text,
    belge_no text,
    CONSTRAINT depo_sevk_log_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.edefter_ayarlar (
    id bigint NOT NULL,
    vkn text DEFAULT ''::text,
    unvan text DEFAULT ''::text,
    telefon text DEFAULT ''::text,
    faks text DEFAULT ''::text,
    eposta text DEFAULT ''::text,
    adres_bina text DEFAULT ''::text,
    adres_cadde text DEFAULT ''::text,
    adres_cadde2 text DEFAULT ''::text,
    adres_il text DEFAULT ''::text,
    adres_posta text DEFAULT ''::text,
    adres_ulke text DEFAULT 'Türkiye'::text,
    website text DEFAULT ''::text,
    nace_kodu text DEFAULT ''::text,
    mali_yil_baslangic text DEFAULT ''::text,
    mali_yil_bitis text DEFAULT ''::text,
    smmm_ad text DEFAULT ''::text,
    smmm_bina text DEFAULT ''::text,
    smmm_cadde text DEFAULT ''::text,
    smmm_il text DEFAULT ''::text,
    program_ad text DEFAULT 'KAYRAN e-Defter'::text,
    program_versiyon text DEFAULT '1.0'::text,
    sube_kodu text DEFAULT ''::text,
    CONSTRAINT edefter_ayarlar_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.edefter_donem_kilit (
    id bigint GENERATED BY DEFAULT AS IDENTITY NOT NULL,
    donem text NOT NULL,
    personel text DEFAULT ''::text,
    kilit_tarihi date DEFAULT now(),
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT edefter_donem_kilit_pkey PRIMARY KEY (id),
    CONSTRAINT edefter_donem_kilit_donem_key UNIQUE (donem)
);

CREATE TABLE IF NOT EXISTS public.edefter_fis_satirlari (
    id bigint GENERATED BY DEFAULT AS IDENTITY NOT NULL,
    fis_id bigint NOT NULL,
    sira integer NOT NULL,
    hesap_kodu text NOT NULL,
    hesap_adi text DEFAULT ''::text,
    aciklama text DEFAULT ''::text,
    borc numeric(18,2) DEFAULT 0,
    alacak numeric(18,2) DEFAULT 0,
    CONSTRAINT edefter_fis_satirlari_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.edefter_fisler (
    id bigint GENERATED BY DEFAULT AS IDENTITY NOT NULL,
    tarih date NOT NULL,
    tur text DEFAULT 'Mahsup'::text,
    aciklama text DEFAULT ''::text,
    belge_no text DEFAULT ''::text,
    yevmiye_madde_no integer NOT NULL,
    toplam numeric(18,2) DEFAULT 0,
    personel text DEFAULT ''::text,
    kilitli boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT edefter_fisler_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.edefter_hesap_plani (
    id bigint GENERATED BY DEFAULT AS IDENTITY NOT NULL,
    kod text NOT NULL,
    ad text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT edefter_hesap_plani_pkey PRIMARY KEY (id),
    CONSTRAINT edefter_hesap_plani_kod_key UNIQUE (kod)
);

-- Not: canlıda aynı (firma, sku, yukleme_tarihi) üzerinde bir de fazlalık
-- firma_stok_firma_sku_yukleme_tarihi_key kısıtı var; aynı işi gördüğü için
-- burada yazılmadı (Postgres aynı CREATE TABLE içinde ikizi zaten oluşturmaz).
CREATE TABLE IF NOT EXISTS public.firma_stok (
    id bigint DEFAULT nextval('firma_stok_id_seq'::regclass) NOT NULL,
    firma text NOT NULL,
    sku text NOT NULL,
    urun_adi text DEFAULT ''::text NOT NULL,
    stok_miktari integer DEFAULT 0 NOT NULL,
    haftalik_satis integer DEFAULT 0 NOT NULL,
    yukleme_tarihi date NOT NULL,
    stok_magaza integer DEFAULT 0,
    satis_magaza integer DEFAULT 0,
    CONSTRAINT firma_stok_pkey PRIMARY KEY (id),
    CONSTRAINT firma_stok_firma_sku_tarih_uniq UNIQUE (firma, sku, yukleme_tarihi)
);

CREATE TABLE IF NOT EXISTS public.giris_denemeleri (
    kullanici_adi text NOT NULL,
    basarisiz_sayi integer DEFAULT 0,
    son_deneme timestamp without time zone,
    kilit_bitis timestamp without time zone,
    CONSTRAINT giris_denemeleri_pkey PRIMARY KEY (kullanici_adi)
);

CREATE TABLE IF NOT EXISTS public.gorevler (
    id bigint DEFAULT nextval('gorevler_id_seq'::regclass) NOT NULL,
    baslik text NOT NULL,
    aciklama text DEFAULT ''::text,
    atayan text DEFAULT 'ibrahim'::text NOT NULL,
    atanan text NOT NULL,
    oncelik text DEFAULT 'normal'::text NOT NULL,
    durum text DEFAULT 'bekliyor'::text NOT NULL,
    bitis_tarihi date,
    tamamlanma_tarihi timestamp with time zone,
    olusturma_tarihi timestamp with time zone DEFAULT now(),
    guncelleme_tarihi timestamp with time zone DEFAULT now(),
    CONSTRAINT gorevler_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.gumruk_sorgulari (
    id bigint DEFAULT nextval('gumruk_sorgulari_id_seq'::regclass) NOT NULL,
    zaman timestamp with time zone DEFAULT now() NOT NULL,
    kullanici text,
    urun text NOT NULL,
    mense text,
    birim_fiyat numeric,
    para text DEFAULT 'USD'::text NOT NULL,
    adet numeric,
    navlun numeric,
    sigorta numeric,
    notu text,
    durum text DEFAULT 'bekliyor'::text NOT NULL,
    sonuc jsonb,
    ozet text,
    guncelleme timestamp with time zone,
    CONSTRAINT gumruk_sorgulari_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.gunluk_giris (
    id bigint DEFAULT nextval('gunluk_giris_id_seq'::regclass) NOT NULL,
    kullanici_adi text NOT NULL,
    tarih date NOT NULL,
    olusturma_tarihi timestamp with time zone DEFAULT now(),
    CONSTRAINT gunluk_giris_pkey PRIMARY KEY (id),
    CONSTRAINT gunluk_giris_kullanici_adi_tarih_key UNIQUE (kullanici_adi, tarih)
);

CREATE TABLE IF NOT EXISTS public.haftalar (
    id integer DEFAULT nextval('haftalar_id_seq'::regclass) NOT NULL,
    hafta_adi text NOT NULL,
    yuklendi_tarih text,
    aktif integer DEFAULT 0,
    CONSTRAINT haftalar_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.happylife_stok (
    id bigint GENERATED BY DEFAULT AS IDENTITY NOT NULL,
    rapor_tarihi date NOT NULL,
    sku text NOT NULL,
    sku_tanim text DEFAULT ''::text,
    giris_tarihi date,
    palet_etiketi text DEFAULT ''::text,
    miktar numeric DEFAULT 0,
    birim text DEFAULT ''::text,
    miktar2 numeric DEFAULT 0,
    birim2 text DEFAULT ''::text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT happylife_stok_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.hata_kayitlari (
    id bigint DEFAULT nextval('hata_kayitlari_id_seq'::regclass) NOT NULL,
    zaman timestamp with time zone DEFAULT now() NOT NULL,
    yer text,
    tur text,
    mesaj text,
    ayrinti text,
    kullanici text,
    kritik boolean DEFAULT false NOT NULL,
    CONSTRAINT hata_kayitlari_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.hm_urun_karliligi (
    id bigint DEFAULT nextval('hm_urun_karliligi_id_seq'::regclass) NOT NULL,
    kullanici text NOT NULL,
    urun_adi text DEFAULT ''::text,
    alis_fiyati numeric(12,4) DEFAULT 0 NOT NULL,
    masraflar numeric(12,4) DEFAULT 0 NOT NULL,
    toplam_maliyet numeric(12,4) DEFAULT 0 NOT NULL,
    senaryolar jsonb DEFAULT '[]'::jsonb,
    notlar text DEFAULT ''::text,
    olusturma_tarihi timestamp with time zone DEFAULT now(),
    CONSTRAINT hm_urun_karliligi_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.iadeler (
    id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
    tarih text,
    kanal text,
    sku text,
    urun_adi text,
    iade_adet integer DEFAULT 0,
    iade_brut numeric DEFAULT 0,
    iade_iskonto numeric DEFAULT 0,
    iade_masraf numeric DEFAULT 0,
    iade_net numeric DEFAULT 0,
    donem_bas date,
    donem_bit date,
    depo text,
    kaynak text DEFAULT 'excel'::text,
    CONSTRAINT iadeler_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.ithalat_dosyalari (
    id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
    dosya_no text NOT NULL,
    tarih date,
    tedarikci text DEFAULT ''::text,
    mense_ulke text DEFAULT ''::text,
    doviz text DEFAULT 'USD'::text,
    kur numeric DEFAULT 1,
    navlun numeric DEFAULT 0,
    gumruk numeric DEFAULT 0,
    sigorta numeric DEFAULT 0,
    nakliye numeric DEFAULT 0,
    diger numeric DEFAULT 0,
    notlar text DEFAULT ''::text,
    olusturma_tarihi timestamp with time zone DEFAULT now(),
    masraflar jsonb DEFAULT '{}'::jsonb,
    pi_no text DEFAULT ''::text,
    ithalat_takip_no text DEFAULT ''::text,
    durum text DEFAULT ''::text,
    tahmini_varis date,
    fatura_indirim numeric DEFAULT 0,
    teslim_tarihi date,
    teslim_deposu text DEFAULT ''::text,
    teslim_sekli text DEFAULT ''::text,
    sas_no text DEFAULT ''::text,
    grup_masraf_atama jsonb,
    grup_cbm jsonb DEFAULT '{}'::jsonb,
    masraf_grup_dagilim jsonb DEFAULT '{}'::jsonb,
    stok_islendi boolean,
    alim_turu text,
    CONSTRAINT ithalat_dosyalari_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.ithalat_kalemleri (
    id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
    dosya_id bigint,
    sku text NOT NULL,
    urun_adi text DEFAULT ''::text,
    adet numeric DEFAULT 0,
    birim_fob numeric DEFAULT 0,
    olusturma_tarihi timestamp with time zone DEFAULT now(),
    urun_grubu text,
    CONSTRAINT ithalat_kalemleri_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.izin_talepleri (
    id bigint DEFAULT nextval('izin_talepleri_id_seq'::regclass) NOT NULL,
    personel text NOT NULL,
    tur text NOT NULL,
    baslangic date NOT NULL,
    bitis date NOT NULL,
    yarim_gun boolean DEFAULT false NOT NULL,
    gun numeric(6,1) NOT NULL,
    yol_izni smallint DEFAULT 0 NOT NULL,
    izin_adresi text,
    takvim_gunu integer NOT NULL,
    aciklama text,
    durum text DEFAULT 'bekliyor'::text NOT NULL,
    talep_eden text,
    talep_zamani timestamp with time zone DEFAULT now() NOT NULL,
    karar_veren text,
    karar_zamani timestamp with time zone,
    karar_notu text,
    iptal_eden text,
    iptal_zamani timestamp with time zone,
    CONSTRAINT izin_talepleri_pkey PRIMARY KEY (id),
    CONSTRAINT izin_talepleri_check CHECK ((bitis >= baslangic)),
    CONSTRAINT izin_talepleri_durum_check CHECK ((durum = ANY (ARRAY['bekliyor'::text, 'onaylandi'::text, 'reddedildi'::text, 'iptal'::text]))),
    CONSTRAINT izin_talepleri_yol_izni_check CHECK (((yol_izni >= 0) AND (yol_izni <= 4)))
);

CREATE TABLE IF NOT EXISTS public.kampanya_urunler (
    id bigint DEFAULT nextval('kampanya_urunler_id_seq'::regclass) NOT NULL,
    kampanya_id bigint NOT NULL,
    sku text NOT NULL,
    urun_adi text DEFAULT ''::text NOT NULL,
    pacal_maliyet numeric(10,2) DEFAULT 0 NOT NULL,
    satis_fiyati numeric(10,2) DEFAULT 0 NOT NULL,
    birim_firma_destek numeric(10,2) DEFAULT 0 NOT NULL,
    birim_ek_destek numeric(10,2) DEFAULT 0 NOT NULL,
    satilan_adet integer DEFAULT 0 NOT NULL,
    notlar text DEFAULT ''::text NOT NULL,
    CONSTRAINT kampanya_urunler_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.kampanyalar (
    id bigint DEFAULT nextval('kampanyalar_id_seq'::regclass) NOT NULL,
    kampanya_adi text DEFAULT ''::text NOT NULL,
    firma text DEFAULT ''::text NOT NULL,
    baslangic_tarihi date,
    bitis_tarihi date,
    durum text DEFAULT 'aktif'::text NOT NULL,
    notlar text DEFAULT ''::text NOT NULL,
    olusturma_tarihi date,
    kategori text DEFAULT ''::text,
    kampanya_turu text DEFAULT ''::text,
    spiff_tl numeric DEFAULT 0,
    spiff_kur numeric DEFAULT 0,
    spiff_fatura boolean DEFAULT false,
    CONSTRAINT kampanyalar_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.kullanici_durum (
    id bigint DEFAULT nextval('kullanici_durum_id_seq'::regclass) NOT NULL,
    kullanici_adi text NOT NULL,
    son_aktivite timestamp with time zone DEFAULT now(),
    CONSTRAINT kullanici_durum_pkey PRIMARY KEY (id),
    CONSTRAINT kullanici_durum_kullanici_adi_key UNIQUE (kullanici_adi)
);

CREATE TABLE IF NOT EXISTS public.kullanici_sifreler (
    id bigint DEFAULT nextval('kullanici_sifreler_id_seq'::regclass) NOT NULL,
    kullanici_adi text NOT NULL,
    sifre_hash text NOT NULL,
    guncelleme_tarihi timestamp with time zone DEFAULT now(),
    CONSTRAINT kullanici_sifreler_pkey PRIMARY KEY (id),
    CONSTRAINT kullanici_sifreler_kullanici_adi_key UNIQUE (kullanici_adi)
);

CREATE TABLE IF NOT EXISTS public.kullanici_tercih (
    kullanici text NOT NULL,
    tema text DEFAULT 'koyu'::text NOT NULL,
    guncelleme timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT kullanici_tercih_pkey PRIMARY KEY (kullanici),
    CONSTRAINT kullanici_tercih_tema_check CHECK ((tema = ANY (ARRAY['koyu'::text, 'acik'::text])))
);

CREATE TABLE IF NOT EXISTS public.kullanici_yetkileri (
    kullanici text NOT NULL,
    moduller text[] DEFAULT '{}'::text[] NOT NULL,
    ozel text[] DEFAULT '{}'::text[] NOT NULL,
    salt_okur boolean DEFAULT false NOT NULL,
    aktif boolean DEFAULT true NOT NULL,
    guncelleyen text,
    guncelleme timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT kullanici_yetkileri_pkey PRIMARY KEY (kullanici)
);

CREATE TABLE IF NOT EXISTS public.kur_gunluk (
    tarih text NOT NULL,
    usd_try numeric NOT NULL,
    CONSTRAINT kur_gunluk_pkey PRIMARY KEY (tarih)
);

CREATE TABLE IF NOT EXISTS public.odemeler (
    id integer DEFAULT nextval('odemeler_id_seq'::regclass) NOT NULL,
    hafta_id integer,
    firma text NOT NULL,
    aciklama text,
    cari_banka text,
    vade text,
    tutar_tl numeric(18,2),
    tutar_usd numeric(18,2),
    kategori text DEFAULT 'diger'::text,
    manuel integer DEFAULT 0,
    durum text DEFAULT 'bekliyor'::text,
    odendi_tarih text,
    orijinal_vade date,
    ertelendi_sayisi integer DEFAULT 0,
    son_erteleme_tarih date,
    banka_id bigint,
    CONSTRAINT odemeler_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.personel (
    kod text NOT NULL,
    ad text NOT NULL,
    sicil_no text,
    departman text,
    ise_giris date,
    dogum_tarihi date,
    devir_tarihi date,
    devir_gun numeric(6,1),
    cikis_tarihi date,
    notu text,
    guncelleme timestamp with time zone DEFAULT now(),
    eposta text,
    bilgi_zamani timestamp with time zone,
    CONSTRAINT personel_pkey PRIMARY KEY (kod)
);

CREATE TABLE IF NOT EXISTS public.pm_ayarlar (
    anahtar text NOT NULL,
    deger text,
    CONSTRAINT pm_ayarlar_pkey PRIMARY KEY (anahtar)
);

CREATE TABLE IF NOT EXISTS public.prim_gecmis (
    id bigint DEFAULT nextval('prim_gecmis_id_seq'::regclass) NOT NULL,
    kisi text NOT NULL,
    donem text NOT NULL,
    toplam_prim double precision NOT NULL,
    odeme_tarihi date NOT NULL,
    notlar text DEFAULT ''::text,
    olusturma_tarihi timestamp with time zone DEFAULT now(),
    CONSTRAINT prim_gecmis_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.ref_butce (
    id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
    firma_id bigint,
    tur text DEFAULT ''::text,
    yon text DEFAULT 'harcama'::text,
    aciklama text DEFAULT ''::text,
    marka text DEFAULT ''::text,
    tutar numeric DEFAULT 0,
    doviz text DEFAULT 'USD'::text,
    fatura_no text DEFAULT ''::text,
    fatura_tarih date,
    ref_no text DEFAULT ''::text,
    kisi text DEFAULT ''::text,
    olusturma_tarihi timestamp with time zone DEFAULT now(),
    CONSTRAINT ref_butce_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.ref_firmalar (
    id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
    firma_adi text NOT NULL,
    firma_kodu text NOT NULL,
    olusturma_tarihi timestamp with time zone DEFAULT now(),
    CONSTRAINT ref_firmalar_pkey PRIMARY KEY (id),
    CONSTRAINT ref_firmalar_firma_adi_key UNIQUE (firma_adi)
);

CREATE TABLE IF NOT EXISTS public.ref_kayitlari (
    id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
    firma_id bigint,
    sira_no integer DEFAULT 0 NOT NULL,
    ref_no text NOT NULL,
    aciklama text DEFAULT ''::text,
    durum text DEFAULT 'beklemede'::text,
    yil integer,
    tarih date,
    paylasim_tarihi date,
    olusturma_tarihi timestamp with time zone DEFAULT now(),
    ay text DEFAULT ''::text,
    kategori text DEFAULT ''::text,
    tutar numeric DEFAULT 0,
    doviz text DEFAULT 'USD'::text,
    aylik jsonb DEFAULT '{}'::jsonb,
    kategori_tutar jsonb DEFAULT '{}'::jsonb,
    CONSTRAINT ref_kayitlari_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.satin_alma_gecmisi (
    id bigint DEFAULT nextval('satin_alma_gecmisi_id_seq'::regclass) NOT NULL,
    sku text NOT NULL,
    urun_adi text DEFAULT ''::text NOT NULL,
    tedarikci text DEFAULT ''::text NOT NULL,
    satin_alma_tarihi date,
    adet integer DEFAULT 0 NOT NULL,
    alis_fiyati numeric(10,2) DEFAULT 0 NOT NULL,
    maliyet_yuzdesi numeric(10,2) DEFAULT 0 NOT NULL,
    toplam_maliyet numeric(12,2) DEFAULT 0 NOT NULL,
    notlar text DEFAULT ''::text NOT NULL,
    kayit_tarihi date,
    CONSTRAINT satin_alma_gecmisi_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.satislar (
    id bigint DEFAULT nextval('satislar_id_seq'::regclass) NOT NULL,
    tarih date,
    kanal text,
    sku text,
    urun_adi text,
    adet integer DEFAULT 0,
    birim_satis numeric DEFAULT 0,
    birim_maliyet numeric DEFAULT 0,
    birim_firma_destek numeric DEFAULT 0,
    birim_ek_destek numeric DEFAULT 0,
    kampanya_id bigint,
    notlar text DEFAULT ''::text,
    olusturma_tarihi timestamp with time zone DEFAULT now(),
    siparis_no text DEFAULT ''::text,
    CONSTRAINT satislar_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.siparis_onerileri (
    id bigint DEFAULT nextval('siparis_onerileri_id_seq'::regclass) NOT NULL,
    firma text DEFAULT ''::text NOT NULL,
    sku text NOT NULL,
    urun_adi text DEFAULT ''::text NOT NULL,
    oneri_miktari integer DEFAULT 0 NOT NULL,
    durum text DEFAULT 'bekliyor'::text NOT NULL,
    olusturma_tarihi date,
    onay_tarihi date,
    CONSTRAINT siparis_onerileri_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.sirket_belgeleri (
    id bigint DEFAULT nextval('sirket_belgeleri_id_seq'::regclass) NOT NULL,
    zaman timestamp with time zone DEFAULT now() NOT NULL,
    tur text NOT NULL,
    ad text NOT NULL,
    yol text NOT NULL,
    boyut bigint,
    mime text,
    belge_tarihi date,
    bitis_tarihi date,
    notu text,
    yukleyen text,
    CONSTRAINT sirket_belgeleri_pkey PRIMARY KEY (id),
    CONSTRAINT sirket_belgeleri_yol_key UNIQUE (yol)
);

-- Not: canlıda anahtar üzerinde PK'nin yanında fazlalık bir
-- sistem_ayarlari_anahtar_key UNIQUE kısıtı da var; PK aynı işi görür, yazılmadı.
CREATE TABLE IF NOT EXISTS public.sistem_ayarlari (
    anahtar text NOT NULL,
    deger text DEFAULT ''::text NOT NULL,
    guncelleme_tarihi timestamp with time zone DEFAULT now(),
    CONSTRAINT sistem_ayarlari_pkey PRIMARY KEY (anahtar)
);

CREATE TABLE IF NOT EXISTS public.sku_eslesme (
    dis_kod text NOT NULL,
    kart_sku text NOT NULL,
    onaylayan text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sku_eslesme_pkey PRIMARY KEY (dis_kod)
);

CREATE TABLE IF NOT EXISTS public.soru_kayitlari (
    id bigint DEFAULT nextval('soru_kayitlari_id_seq'::regclass) NOT NULL,
    kullanici text,
    metin text NOT NULL,
    anlasildi boolean DEFAULT false NOT NULL,
    konu text,
    olusturma timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT soru_kayitlari_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.stok_hareketleri (
    id bigint DEFAULT nextval('stok_hareketleri_id_seq'::regclass) NOT NULL,
    zaman timestamp with time zone DEFAULT now() NOT NULL,
    sku text NOT NULL,
    depo text,
    onceki numeric,
    sonraki numeric,
    degisim numeric,
    tur text,
    aciklama text,
    kaynak text,
    kullanici text,
    basarili boolean DEFAULT true NOT NULL,
    hata text,
    yukleme_kodu text,
    CONSTRAINT stok_hareketleri_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.stok_yas (
    sku text NOT NULL,
    ilk_gorulen_tarih date,
    CONSTRAINT stok_yas_pkey PRIMARY KEY (sku)
);

CREATE TABLE IF NOT EXISTS public.tahsilatlar (
    id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
    banka_id bigint,
    hesap_adi text,
    para_birimi text,
    tutar numeric,
    kaynak text,
    aciklama text,
    tarih date,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT tahsilatlar_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.talepler (
    id bigint DEFAULT nextval('talepler_id_seq'::regclass) NOT NULL,
    gonderen text DEFAULT ''::text NOT NULL,
    konu text DEFAULT ''::text NOT NULL,
    mesaj text DEFAULT ''::text NOT NULL,
    durum text DEFAULT 'bekliyor'::text NOT NULL,
    olusturma_tarihi timestamp with time zone DEFAULT now(),
    cevap text,
    kategori text,
    oncelik text,
    claude_durum text,
    claude_onay_notu text,
    claude_onaylayan text,
    claude_onay_tarihi timestamp with time zone,
    claude_not text,
    claude_pr_url text,
    claude_guncelleme timestamp with time zone,
    CONSTRAINT talepler_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.ts_gecmis (
    id bigint GENERATED BY DEFAULT AS IDENTITY NOT NULL,
    kayit_id bigint,
    durum text,
    aciklama text,
    personel text,
    tarih timestamp with time zone DEFAULT now(),
    CONSTRAINT ts_gecmis_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.ts_kayitlar (
    id bigint GENERATED BY DEFAULT AS IDENTITY NOT NULL,
    servis_form_no text,
    arayuz text,
    stok_kodu text,
    ean text,
    urun_grubu text,
    stok_adi text,
    seri_no text,
    ariza text,
    detay text,
    firma_bilgisi text,
    sevk_kargo_bilgisi text,
    musteri_adi text,
    musteri_mail text,
    musteri_tel text,
    musteri_adres text,
    icerik_durumu text,
    fiziksel_durum text,
    fatura_no text,
    irsaliye_no text,
    firma_servis_form_no text,
    mevcut_durum text DEFAULT 'mal kabül'::text,
    depo text,
    personel text,
    gorsel_url text,
    yapilan_islem text,
    test_sureci text,
    degisim_stok_kodu text,
    degisim_stok_adi text,
    degisim_seri_no text,
    satis_firma text,
    satis_tarihi date,
    satis_fiyati numeric DEFAULT 0,
    bedelsiz boolean DEFAULT false,
    mal_kabul_tarihi timestamp with time zone,
    olusturma_tarihi timestamp with time zone DEFAULT now(),
    notlar text,
    fatura_mevcut boolean DEFAULT true,
    depo_aciklama text DEFAULT ''::text,
    degisim_depo text DEFAULT ''::text,
    eksik_icerik text DEFAULT ''::text,
    depo_tarihi text,
    gelis_kargo_no text,
    gidis_kargo_no text,
    gidis_sevk_sekli text,
    ariza_sonucu text,
    giris_depo text,
    iade_net numeric(14,4),
    iade_fiyat numeric(14,4),
    iade_pb text,
    iade_kur numeric(10,4),
    iade_id bigint,
    CONSTRAINT ts_kayitlar_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.urunler (
    sku text NOT NULL,
    urun_adi text DEFAULT ''::text NOT NULL,
    kategori text DEFAULT ''::text NOT NULL,
    marka text DEFAULT ''::text NOT NULL,
    satis_fiyati numeric(10,2) DEFAULT 0 NOT NULL,
    alis_fiyati numeric(10,2) DEFAULT 0 NOT NULL,
    hedef_kar_marji numeric(10,2) DEFAULT 0 NOT NULL,
    ozellikler text DEFAULT ''::text NOT NULL,
    bizim_stok integer DEFAULT 0 NOT NULL,
    trendyol_stok integer DEFAULT 0 NOT NULL,
    ilk_giris_tarihi date,
    guncelleme_tarihi date,
    satis_fiyat_listesi jsonb DEFAULT '{}'::jsonb,
    eol boolean DEFAULT false,
    depo_kirilim jsonb DEFAULT '{}'::jsonb,
    barkod text DEFAULT ''::text,
    CONSTRAINT urunler_pkey PRIMARY KEY (sku)
);

CREATE TABLE IF NOT EXISTS public.veri_surumu (
    tablo text NOT NULL,
    surum bigint DEFAULT 0 NOT NULL,
    degisti timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT veri_surumu_pkey PRIMARY KEY (tablo)
);

CREATE TABLE IF NOT EXISTS public.virmanlar (
    id bigint DEFAULT nextval('virmanlar_id_seq'::regclass) NOT NULL,
    kaynak_banka_id bigint,
    hedef_banka_id bigint,
    kaynak_hesap_adi text,
    hedef_hesap_adi text,
    kaynak_para_birimi text,
    hedef_para_birimi text,
    tutar numeric(18,2),
    hedef_tutar numeric(18,2),
    kur_kullanilan numeric(10,4),
    aciklama text,
    tarih date DEFAULT CURRENT_DATE,
    olusturuldu timestamp with time zone DEFAULT now(),
    CONSTRAINT virmanlar_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.yoldaki_urunler (
    sku text NOT NULL,
    urun_adi text DEFAULT ''::text NOT NULL,
    yoldaki_miktar integer DEFAULT 0 NOT NULL,
    tahmini_varis_tarihi text DEFAULT ''::text NOT NULL,
    yoldaki_tedarikci text DEFAULT ''::text NOT NULL,
    yukleme_tarihi date,
    CONSTRAINT yoldaki_urunler_pkey PRIMARY KEY (sku)
);

CREATE TABLE IF NOT EXISTS public.yuklemeler (
    id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
    tur text NOT NULL,
    anahtarlar jsonb DEFAULT '[]'::jsonb NOT NULL,
    dosya_adi text,
    kullanici text,
    zaman timestamp with time zone DEFAULT now() NOT NULL,
    satir_sayisi integer DEFAULT 0 NOT NULL,
    geri_alinabilir boolean DEFAULT false NOT NULL,
    degisiklik jsonb DEFAULT '{}'::jsonb NOT NULL,
    durum text DEFAULT 'aktif'::text NOT NULL,
    geri_alan text,
    geri_alma_zamani timestamp with time zone,
    silinen jsonb,
    kod text,
    CONSTRAINT yuklemeler_pkey PRIMARY KEY (id)
);

-- Sıraları kolonlarına bağla (tablo silinince sıra da silinsin)
ALTER SEQUENCE public.aktif_excel_verileri_id_seq OWNED BY public.aktif_excel_verileri.id;
ALTER SEQUENCE public.aktif_manuel_kalemler_id_seq OWNED BY public.aktif_manuel_kalemler.id;
ALTER SEQUENCE public.asistan_rapor_id_seq OWNED BY public.asistan_rapor.id;
ALTER SEQUENCE public.bankalar_id_seq OWNED BY public.bankalar.id;
ALTER SEQUENCE public.bildirim_ayarlari_id_seq OWNED BY public.bildirim_ayarlari.id;
ALTER SEQUENCE public.bildirimler_id_seq OWNED BY public.bildirimler.id;
ALTER SEQUENCE public.bt_olcum_id_seq OWNED BY public.bt_olcum.id;
ALTER SEQUENCE public.bt_rapor_id_seq OWNED BY public.bt_rapor.id;
ALTER SEQUENCE public.cekler_id_seq OWNED BY public.cekler.id;
ALTER SEQUENCE public.cop_kutusu_id_seq OWNED BY public.cop_kutusu.id;
ALTER SEQUENCE public.firma_stok_id_seq OWNED BY public.firma_stok.id;
ALTER SEQUENCE public.gorevler_id_seq OWNED BY public.gorevler.id;
ALTER SEQUENCE public.gumruk_sorgulari_id_seq OWNED BY public.gumruk_sorgulari.id;
ALTER SEQUENCE public.gunluk_giris_id_seq OWNED BY public.gunluk_giris.id;
ALTER SEQUENCE public.haftalar_id_seq OWNED BY public.haftalar.id;
ALTER SEQUENCE public.hata_kayitlari_id_seq OWNED BY public.hata_kayitlari.id;
ALTER SEQUENCE public.hm_urun_karliligi_id_seq OWNED BY public.hm_urun_karliligi.id;
ALTER SEQUENCE public.izin_talepleri_id_seq OWNED BY public.izin_talepleri.id;
ALTER SEQUENCE public.kampanya_urunler_id_seq OWNED BY public.kampanya_urunler.id;
ALTER SEQUENCE public.kampanyalar_id_seq OWNED BY public.kampanyalar.id;
ALTER SEQUENCE public.kullanici_durum_id_seq OWNED BY public.kullanici_durum.id;
ALTER SEQUENCE public.kullanici_sifreler_id_seq OWNED BY public.kullanici_sifreler.id;
ALTER SEQUENCE public.odemeler_id_seq OWNED BY public.odemeler.id;
ALTER SEQUENCE public.prim_gecmis_id_seq OWNED BY public.prim_gecmis.id;
ALTER SEQUENCE public.satin_alma_gecmisi_id_seq OWNED BY public.satin_alma_gecmisi.id;
ALTER SEQUENCE public.satislar_id_seq OWNED BY public.satislar.id;
ALTER SEQUENCE public.siparis_onerileri_id_seq OWNED BY public.siparis_onerileri.id;
ALTER SEQUENCE public.sirket_belgeleri_id_seq OWNED BY public.sirket_belgeleri.id;
ALTER SEQUENCE public.soru_kayitlari_id_seq OWNED BY public.soru_kayitlari.id;
ALTER SEQUENCE public.stok_hareketleri_id_seq OWNED BY public.stok_hareketleri.id;
ALTER SEQUENCE public.talepler_id_seq OWNED BY public.talepler.id;
ALTER SEQUENCE public.virmanlar_id_seq OWNED BY public.virmanlar.id;

-- ─── 3) Yabancı anahtarlar (canlıdaki 11 kısıt) ────────────────────────
-- ALTER TABLE … ADD CONSTRAINT'in IF NOT EXISTS'i yok; adla denetlenir.
DO $fk$
DECLARE
    r record;
BEGIN
    FOR r IN SELECT * FROM (VALUES
        ('edefter_fis_satirlari', 'edefter_fis_satirlari_fis_id_fkey',
         'FOREIGN KEY (fis_id) REFERENCES public.edefter_fisler(id) ON DELETE CASCADE'),
        ('ithalat_kalemleri', 'ithalat_kalemleri_dosya_id_fkey',
         'FOREIGN KEY (dosya_id) REFERENCES public.ithalat_dosyalari(id) ON DELETE CASCADE'),
        ('izin_talepleri', 'izin_talepleri_personel_fkey',
         'FOREIGN KEY (personel) REFERENCES public.personel(kod) ON UPDATE CASCADE'),
        ('kampanya_urunler', 'kampanya_urunler_kampanya_id_fkey',
         'FOREIGN KEY (kampanya_id) REFERENCES public.kampanyalar(id) ON DELETE CASCADE'),
        ('odemeler', 'odemeler_hafta_id_fkey',
         'FOREIGN KEY (hafta_id) REFERENCES public.haftalar(id) ON DELETE CASCADE'),
        ('ref_butce', 'ref_butce_firma_id_fkey',
         'FOREIGN KEY (firma_id) REFERENCES public.ref_firmalar(id) ON DELETE CASCADE'),
        ('ref_kayitlari', 'ref_kayitlari_firma_id_fkey',
         'FOREIGN KEY (firma_id) REFERENCES public.ref_firmalar(id) ON DELETE CASCADE'),
        ('tahsilatlar', 'tahsilatlar_banka_id_fkey',
         'FOREIGN KEY (banka_id) REFERENCES public.bankalar(id)'),
        ('ts_gecmis', 'ts_gecmis_kayit_id_fkey',
         'FOREIGN KEY (kayit_id) REFERENCES public.ts_kayitlar(id) ON DELETE CASCADE'),
        ('virmanlar', 'virmanlar_hedef_banka_id_fkey',
         'FOREIGN KEY (hedef_banka_id) REFERENCES public.bankalar(id) ON DELETE SET NULL'),
        ('virmanlar', 'virmanlar_kaynak_banka_id_fkey',
         'FOREIGN KEY (kaynak_banka_id) REFERENCES public.bankalar(id) ON DELETE SET NULL')
    ) AS v(tablo, ad, tanim)
    LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_constraint
                       WHERE conname = r.ad AND conrelid = format('public.%I', r.tablo)::regclass) THEN
            EXECUTE format('ALTER TABLE public.%I ADD CONSTRAINT %I %s', r.tablo, r.ad, r.tanim);
        END IF;
    END LOOP;
END
$fk$;

-- ─── 4) İndeksler (kısıtlara bağlı olmayanlar) ─────────────────────────
CREATE INDEX IF NOT EXISTS asistan_rapor_zaman_idx ON public.asistan_rapor USING btree (zaman DESC);
CREATE INDEX IF NOT EXISTS bt_olcum_zaman_idx ON public.bt_olcum USING btree (zaman DESC);
CREATE INDEX IF NOT EXISTS bt_rapor_zaman_idx ON public.bt_rapor USING btree (zaman DESC);
CREATE INDEX IF NOT EXISTS cop_kutusu_silen_idx ON public.cop_kutusu USING btree (silen);
CREATE INDEX IF NOT EXISTS cop_kutusu_zaman_idx ON public.cop_kutusu USING btree (zaman DESC);
CREATE INDEX IF NOT EXISTS gumruk_sorgulari_durum_idx ON public.gumruk_sorgulari USING btree (durum, zaman);
CREATE INDEX IF NOT EXISTS hata_kayitlari_zaman_idx ON public.hata_kayitlari USING btree (zaman DESC);
CREATE INDEX IF NOT EXISTS idx_audit_islem ON public.audit_log USING btree (islem);
CREATE INDEX IF NOT EXISTS idx_audit_kullanici ON public.audit_log USING btree (kullanici);
CREATE INDEX IF NOT EXISTS idx_audit_modul ON public.audit_log USING btree (modul);
CREATE INDEX IF NOT EXISTS idx_audit_zaman ON public.audit_log USING btree (zaman DESC);
CREATE INDEX IF NOT EXISTS idx_edf_fis_madde ON public.edefter_fisler USING btree (yevmiye_madde_no);
CREATE INDEX IF NOT EXISTS idx_edf_fis_tarih ON public.edefter_fisler USING btree (tarih);
CREATE INDEX IF NOT EXISTS idx_edf_sat_fis ON public.edefter_fis_satirlari USING btree (fis_id);
CREATE INDEX IF NOT EXISTS idx_edf_sat_hesap ON public.edefter_fis_satirlari USING btree (hesap_kodu);
CREATE INDEX IF NOT EXISTS idx_gunluk_giris_kullanici ON public.gunluk_giris USING btree (kullanici_adi);
CREATE INDEX IF NOT EXISTS idx_gunluk_giris_tarih ON public.gunluk_giris USING btree (tarih);
CREATE INDEX IF NOT EXISTS idx_hl_rapor ON public.happylife_stok USING btree (rapor_tarihi);
CREATE INDEX IF NOT EXISTS idx_hl_sku ON public.happylife_stok USING btree (sku);
CREATE INDEX IF NOT EXISTS idx_hm_urun_karliligi_kullanici ON public.hm_urun_karliligi USING btree (kullanici);
CREATE INDEX IF NOT EXISTS idx_hm_urun_karliligi_tarih ON public.hm_urun_karliligi USING btree (olusturma_tarihi DESC);
CREATE INDEX IF NOT EXISTS idx_ithalat_kalem_dosya ON public.ithalat_kalemleri USING btree (dosya_id);
CREATE INDEX IF NOT EXISTS idx_ithalat_kalem_sku ON public.ithalat_kalemleri USING btree (sku);
CREATE INDEX IF NOT EXISTS ix_bayi_kullanicilar_aktif ON public.bayi_kullanicilar USING btree (aktif);
CREATE INDEX IF NOT EXISTS ix_bayi_kullanicilar_cari_kod ON public.bayi_kullanicilar USING btree (cari_kod);
CREATE INDEX IF NOT EXISTS ix_ref_butce_firma ON public.ref_butce USING btree (firma_id);
CREATE INDEX IF NOT EXISTS ix_ref_butce_ref ON public.ref_butce USING btree (ref_no);
CREATE INDEX IF NOT EXISTS ix_ref_kayitlari_firma ON public.ref_kayitlari USING btree (firma_id);
CREATE INDEX IF NOT EXISTS izin_talepleri_durum_idx ON public.izin_talepleri USING btree (durum);
CREATE INDEX IF NOT EXISTS izin_talepleri_personel_idx ON public.izin_talepleri USING btree (personel, baslangic);
CREATE INDEX IF NOT EXISTS sirket_belgeleri_tur_idx ON public.sirket_belgeleri USING btree (tur);
CREATE INDEX IF NOT EXISTS soru_kayitlari_olusturma_idx ON public.soru_kayitlari USING btree (olusturma DESC);
CREATE INDEX IF NOT EXISTS stok_hareketleri_basarisiz_idx ON public.stok_hareketleri USING btree (zaman DESC) WHERE (basarili = false);
CREATE INDEX IF NOT EXISTS stok_hareketleri_sku_zaman_idx ON public.stok_hareketleri USING btree (sku, zaman DESC);
CREATE INDEX IF NOT EXISTS stok_hareketleri_yukleme_idx ON public.stok_hareketleri USING btree (yukleme_kodu) WHERE (yukleme_kodu IS NOT NULL);
CREATE INDEX IF NOT EXISTS stok_hareketleri_zaman_idx ON public.stok_hareketleri USING btree (zaman DESC);
CREATE INDEX IF NOT EXISTS talepler_durum_idx ON public.talepler USING btree (durum);
CREATE INDEX IF NOT EXISTS ts_gecmis_kayit_idx ON public.ts_gecmis USING btree (kayit_id);
CREATE INDEX IF NOT EXISTS ts_gecmis_kayit_tarih_idx ON public.ts_gecmis USING btree (kayit_id, tarih);
CREATE INDEX IF NOT EXISTS ts_kayitlar_arayuz_idx ON public.ts_kayitlar USING btree (arayuz);
CREATE INDEX IF NOT EXISTS ts_kayitlar_depo_idx ON public.ts_kayitlar USING btree (depo);
CREATE INDEX IF NOT EXISTS ts_kayitlar_irsaliye_no_idx ON public.ts_kayitlar USING btree (irsaliye_no);
CREATE INDEX IF NOT EXISTS yuklemeler_kod_idx ON public.yuklemeler USING btree (kod);
CREATE INDEX IF NOT EXISTS yuklemeler_tur_idx ON public.yuklemeler USING btree (tur, durum);
CREATE INDEX IF NOT EXISTS yuklemeler_zaman_idx ON public.yuklemeler USING btree (zaman DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_ref_kayitlari_firma_ref ON public.ref_kayitlari USING btree (firma_id, ref_no);

-- ─── 5) Görünümler ve özet tablolar ────────────────────────────────────
-- Görünümler sorgulayanın yetkisiyle çalışır (security_invoker) — RLS'yi aşmaz.
CREATE OR REPLACE VIEW public.v_satis_pnl WITH (security_invoker = on) AS
 SELECT
        CASE
            WHEN COALESCE(tarih::text, ''::text) ~ '^\d{4}-\d{2}-\d{2}'::text THEN "substring"(tarih::text, 1, 10)::date
            ELSE NULL::date
        END AS tarih,
    COALESCE(NULLIF(TRIM(BOTH FROM kanal), ''::text), '—'::text) AS kanal,
    COALESCE(NULLIF(TRIM(BOTH FROM sku), ''::text), '—'::text) AS sku,
    max(COALESCE(urun_adi, ''::text)) AS urun_adi,
    sum(COALESCE(adet, 0)) AS adet,
    sum(COALESCE(adet, 0)::numeric * COALESCE(birim_satis, 0::numeric)) AS ciro,
    sum(COALESCE(adet, 0)::numeric * COALESCE(birim_maliyet, 0::numeric)) AS maliyet,
    sum(COALESCE(adet, 0)::numeric * (COALESCE(birim_firma_destek, 0::numeric) + COALESCE(birim_ek_destek, 0::numeric))) AS destek,
    sum(COALESCE(adet, 0)::numeric * (COALESCE(birim_satis, 0::numeric) - COALESCE(birim_firma_destek, 0::numeric) - COALESCE(birim_ek_destek, 0::numeric) - COALESCE(birim_maliyet, 0::numeric))) AS net_kar
   FROM satislar s
  GROUP BY (
        CASE
            WHEN COALESCE(tarih::text, ''::text) ~ '^\d{4}-\d{2}-\d{2}'::text THEN "substring"(tarih::text, 1, 10)::date
            ELSE NULL::date
        END), (COALESCE(NULLIF(TRIM(BOTH FROM kanal), ''::text), '—'::text)), (COALESCE(NULLIF(TRIM(BOTH FROM sku), ''::text), '—'::text));

CREATE OR REPLACE VIEW public.v_destek_donem WITH (security_invoker = on) AS
 WITH ref AS (
         SELECT r.id,
            r.firma_id,
            r.tutar,
            r.yil,
            r.tarih,
            COALESCE(NULLIF(TRIM(BOTH FROM r.doviz), ''::text), 'USD'::text) AS doviz,
                CASE
                    WHEN jsonb_typeof(r.aylik) = 'object'::text THEN r.aylik
                    WHEN jsonb_typeof(r.aylik) = 'string'::text AND (r.aylik #>> '{}'::text[]) ~ '^\s*\{.*\}\s*$'::text THEN (r.aylik #>> '{}'::text[])::jsonb
                    ELSE '{}'::jsonb
                END AS aj
           FROM ref_kayitlari r
          WHERE lower(COALESCE(r.durum, ''::text)) <> 'iptal'::text
        ), ref_aylik AS (
         SELECT ref.id,
            ref.firma_id,
            ref.doviz,
            to_date(k.key || '-01'::text, 'YYYY-MM-DD'::text) AS donem,
            k.value::numeric AS tutar
           FROM ref
             CROSS JOIN LATERAL jsonb_each_text(
                CASE
                    WHEN jsonb_typeof(ref.aj) = 'object'::text THEN ref.aj
                    ELSE '{}'::jsonb
                END) k(key, value)
          WHERE k.key ~ '^\d{4}-\d{2}$'::text AND k.value ~ '^\d+(\.\d+)?$'::text AND k.value::numeric > 0::numeric
        ), ref_toplam AS (
         SELECT ref.id,
            sum(k.value::numeric) AS aylik_toplam
           FROM ref
             CROSS JOIN LATERAL jsonb_each_text(
                CASE
                    WHEN jsonb_typeof(ref.aj) = 'object'::text THEN ref.aj
                    ELSE '{}'::jsonb
                END) k(key, value)
          WHERE k.value ~ '^\d+(\.\d+)?$'::text AND k.value::numeric > 0::numeric
          GROUP BY ref.id
        ), ref_artik AS (
         SELECT ref.id,
            ref.firma_id,
            ref.doviz,
                CASE
                    WHEN TRIM(BOTH FROM COALESCE(ref.yil::text, ''::text)) ~ '^\d{4}$'::text THEN to_date(TRIM(BOTH FROM ref.yil::text) || '-01-01'::text, 'YYYY-MM-DD'::text)
                    ELSE NULL::date
                END AS yil_bas,
                CASE
                    WHEN COALESCE(ref.tarih::text, ''::text) ~ '^\d{4}-\d{2}-\d{2}'::text THEN "substring"(ref.tarih::text, 1, 10)::date
                    ELSE NULL::date
                END AS tarih_gun,
                CASE
                    WHEN ref.aj <> '{}'::jsonb THEN COALESCE(ref.tutar, 0::numeric) - COALESCE(t.aylik_toplam, 0::numeric)
                    ELSE COALESCE(ref.tutar, 0::numeric)
                END AS tutar,
            ref.aj <> '{}'::jsonb AS dagilimli
           FROM ref
             LEFT JOIN ref_toplam t ON t.id = ref.id
        ), havuz AS (
         SELECT b.firma_id,
            COALESCE(NULLIF(TRIM(BOTH FROM b.doviz), ''::text), 'USD'::text) AS doviz,
            COALESCE(NULLIF(TRIM(BOTH FROM b.tur), ''::text), 'Diğer'::text) AS tur,
                CASE
                    WHEN COALESCE(b.fatura_tarih::text, ''::text) ~ '^\d{4}-\d{2}-\d{2}'::text THEN "substring"(b.fatura_tarih::text, 1, 10)::date
                    ELSE NULL::date
                END AS donem,
            COALESCE(b.tutar, 0::numeric) AS tutar
           FROM ref_butce b
          WHERE (lower(TRIM(BOTH FROM COALESCE(b.yon, ''::text))) <> ALL (ARRAY['giris'::text, 'giriş'::text])) AND upper(translate(COALESCE(b.tur, ''::text), 'İıŞşĞğÜüÖöÇç'::text, 'IISSGGUUOOCC'::text)) <> 'BUTCE'::text
        )
 SELECT 'ref'::text AS kaynak,
    'Ref No'::text AS tur,
    ref_aylik.firma_id,
    ref_aylik.doviz,
    ref_aylik.donem,
    ref_aylik.tutar,
    ref_aylik.donem AS donem_bas,
    ref_aylik.donem + 27 AS donem_bit
   FROM ref_aylik
UNION ALL
 SELECT 'ref'::text AS kaynak,
    'Ref No'::text AS tur,
    ref_artik.firma_id,
    ref_artik.doviz,
    COALESCE(ref_artik.yil_bas, ref_artik.tarih_gun) AS donem,
    ref_artik.tutar,
    COALESCE(ref_artik.yil_bas, ref_artik.tarih_gun) AS donem_bas,
        CASE
            WHEN ref_artik.yil_bas IS NOT NULL THEN (ref_artik.yil_bas + '1 year'::interval - '1 day'::interval)::date
            ELSE ref_artik.tarih_gun
        END AS donem_bit
   FROM ref_artik
  WHERE COALESCE(ref_artik.yil_bas, ref_artik.tarih_gun) IS NOT NULL AND
        CASE
            WHEN ref_artik.dagilimli THEN ref_artik.tutar > 0.005
            ELSE ref_artik.tutar > 0::numeric
        END
UNION ALL
 SELECT 'havuz'::text AS kaynak,
    havuz.tur,
    havuz.firma_id,
    havuz.doviz,
    havuz.donem,
    havuz.tutar,
    havuz.donem AS donem_bas,
    havuz.donem AS donem_bit
   FROM havuz
  WHERE havuz.donem IS NOT NULL;

CREATE MATERIALIZED VIEW IF NOT EXISTS public.mv_gunluk_pnl AS
 SELECT tarih,
    sum(adet) AS adet,
    sum(ciro) AS ciro,
    sum(maliyet) AS cogs,
    sum(destek) AS destek,
    sum(net_kar) AS net_kar
   FROM v_satis_pnl
  WHERE tarih IS NOT NULL
  GROUP BY tarih
  ORDER BY tarih;

CREATE MATERIALIZED VIEW IF NOT EXISTS public.mv_kanal_ay_pnl AS
 SELECT date_trunc('month'::text, tarih::timestamp with time zone)::date AS ay,
    kanal,
    sum(adet) AS adet,
    sum(ciro) AS ciro,
    sum(net_kar) AS net_kar
   FROM v_satis_pnl
  WHERE tarih IS NOT NULL
  GROUP BY (date_trunc('month'::text, tarih::timestamp with time zone)::date), kanal;

-- CONCURRENTLY tazeleme için gerekli tekil indeksler
CREATE UNIQUE INDEX IF NOT EXISTS mv_gunluk_pnl_tarih_idx ON public.mv_gunluk_pnl USING btree (tarih);
CREATE UNIQUE INDEX IF NOT EXISTS mv_kanal_ay_pnl_idx ON public.mv_kanal_ay_pnl USING btree (ay, kanal);

-- ─── 6) Fonksiyonlar ───────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.mv_gunluk_pnl_tazele()
 RETURNS text
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_gunluk_pnl;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_kanal_ay_pnl;
    RETURN 'ok: ' || now()::text;
EXCEPTION WHEN OTHERS THEN
    REFRESH MATERIALIZED VIEW mv_gunluk_pnl;
    REFRESH MATERIALIZED VIEW mv_kanal_ay_pnl;
    RETURN 'ok (full): ' || now()::text;
END;
$function$;

CREATE OR REPLACE FUNCTION public.veri_surumu_artir()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$ BEGIN INSERT INTO veri_surumu (tablo, surum, degisti) VALUES (TG_TABLE_NAME, 1, now()) ON CONFLICT (tablo) DO UPDATE SET surum = veri_surumu.surum + 1, degisti = now(); RETURN NULL; END $function$;

CREATE OR REPLACE FUNCTION public.yukleme_geri_al(p_id bigint, p_kullanici text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
    k        record;
    t        text;
    d        jsonb;
    n_sil    integer := 0;
    n_yaz    integer := 0;
    n        integer;
    v_silinen jsonb := '{}'::jsonb;
    satirlar jsonb;
BEGIN
    SELECT * INTO k FROM yuklemeler WHERE id = p_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'yükleme bulunamadı: %', p_id; END IF;
    IF k.durum <> 'aktif' THEN RAISE EXCEPTION 'yükleme zaten geri alınmış'; END IF;
    IF NOT k.geri_alinabilir THEN RAISE EXCEPTION 'bu yükleme geri alınamaz'; END IF;
    FOR t, d IN SELECT * FROM jsonb_each(k.degisiklik) LOOP
        IF t NOT IN ('firma_stok', 'happylife_stok', 'cekler', 'ref_butce') THEN
            RAISE EXCEPTION 'izin verilmeyen tablo: %', t;
        END IF;
        EXECUTE format('WITH s AS (DELETE FROM %I WHERE id IN (SELECT (x)::bigint FROM jsonb_array_elements_text($1) x) RETURNING *) '
                       'SELECT coalesce(jsonb_agg(to_jsonb(s)), ''[]''::jsonb) FROM s', t)
            INTO satirlar USING coalesce(d->'eklenen', '[]'::jsonb);
        n_sil := n_sil + jsonb_array_length(satirlar);
        v_silinen := v_silinen || jsonb_build_object(t, satirlar);
        IF jsonb_array_length(coalesce(d->'onceki', '[]'::jsonb)) > 0 THEN
            EXECUTE format('INSERT INTO %I OVERRIDING SYSTEM VALUE SELECT * FROM jsonb_populate_recordset(NULL::%I, $1)', t, t)
                USING d->'onceki';
            GET DIAGNOSTICS n = ROW_COUNT;
            n_yaz := n_yaz + n;
        END IF;
    END LOOP;
    UPDATE yuklemeler SET durum = 'geri_alindi', geri_alan = p_kullanici, geri_alma_zamani = now(),
           silinen = v_silinen WHERE id = p_id;
    RETURN jsonb_build_object('silinen', n_sil, 'geri_yazilan', n_yaz);
END $function$;

CREATE OR REPLACE FUNCTION public.yukleme_satir_geri_al(p_id bigint)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
    k         record;
    t         text;
    d         jsonb;
    n_sil     integer := 0;
    n_yaz     integer := 0;
    n         integer;
    v_silinen jsonb := '{}'::jsonb;
    satirlar  jsonb;
    sil_sira  text[] := ARRAY['ithalat_kalemleri', 'satislar', 'iadeler', 'firma_stok',
                              'happylife_stok', 'cekler', 'ref_butce', 'ithalat_dosyalari', 'ts_kayitlar'];
    yaz_sira  text[] := ARRAY['ithalat_dosyalari', 'ts_kayitlar', 'satislar', 'iadeler', 'firma_stok',
                              'happylife_stok', 'cekler', 'ref_butce', 'ithalat_kalemleri'];
BEGIN
    SELECT * INTO k FROM yuklemeler WHERE id = p_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'yükleme bulunamadı: %', p_id; END IF;
    IF k.durum <> 'geri_aliniyor' THEN RAISE EXCEPTION 'yükleme geri alma durumunda değil: %', k.durum; END IF;
    IF NOT k.geri_alinabilir THEN RAISE EXCEPTION 'bu yükleme geri alınamaz'; END IF;
    IF k.silinen IS NOT NULL THEN
        RETURN jsonb_build_object('silinen', 0, 'geri_yazilan', 0, 'zaten', true);
    END IF;
    FOR t IN SELECT jsonb_object_keys(k.degisiklik) LOOP
        IF t NOT LIKE '\_%' AND NOT (t = ANY (sil_sira)) THEN
            RAISE EXCEPTION 'izin verilmeyen tablo: %', t;
        END IF;
    END LOOP;
    FOREACH t IN ARRAY sil_sira LOOP
        d := k.degisiklik -> t;
        CONTINUE WHEN d IS NULL;
        EXECUTE format('WITH s AS (DELETE FROM %I WHERE id IN (SELECT (x)::bigint FROM jsonb_array_elements_text($1) x) RETURNING *) '
                       'SELECT coalesce(jsonb_agg(to_jsonb(s)), ''[]''::jsonb) FROM s', t)
            INTO satirlar USING coalesce(d -> 'eklenen', '[]'::jsonb);
        n_sil := n_sil + jsonb_array_length(satirlar);
        v_silinen := v_silinen || jsonb_build_object(t, satirlar);
    END LOOP;
    FOREACH t IN ARRAY yaz_sira LOOP
        d := k.degisiklik -> t;
        CONTINUE WHEN d IS NULL OR jsonb_array_length(coalesce(d -> 'onceki', '[]'::jsonb)) = 0;
        EXECUTE format('INSERT INTO %I OVERRIDING SYSTEM VALUE SELECT * FROM jsonb_populate_recordset(NULL::%I, $1)', t, t)
            USING d -> 'onceki';
        GET DIAGNOSTICS n = ROW_COUNT;
        n_yaz := n_yaz + n;
    END LOOP;
    UPDATE yuklemeler SET silinen = v_silinen WHERE id = p_id;
    RETURN jsonb_build_object('silinen', n_sil, 'geri_yazilan', n_yaz);
END $function$;

-- ─── 7) Tetikleyiciler: önbellek sürüm sayacı (11_ / 22_) ──────────────
CREATE OR REPLACE TRIGGER veri_surumu_trg AFTER INSERT OR DELETE OR UPDATE OR TRUNCATE ON public.firma_stok FOR EACH STATEMENT EXECUTE FUNCTION veri_surumu_artir();
CREATE OR REPLACE TRIGGER veri_surumu_trg AFTER INSERT OR DELETE OR UPDATE OR TRUNCATE ON public.iadeler FOR EACH STATEMENT EXECUTE FUNCTION veri_surumu_artir();
CREATE OR REPLACE TRIGGER veri_surumu_trg AFTER INSERT OR DELETE OR UPDATE OR TRUNCATE ON public.ithalat_dosyalari FOR EACH STATEMENT EXECUTE FUNCTION veri_surumu_artir();
CREATE OR REPLACE TRIGGER veri_surumu_trg AFTER INSERT OR DELETE OR UPDATE OR TRUNCATE ON public.ithalat_kalemleri FOR EACH STATEMENT EXECUTE FUNCTION veri_surumu_artir();
CREATE OR REPLACE TRIGGER veri_surumu_trg AFTER INSERT OR DELETE OR UPDATE OR TRUNCATE ON public.pm_ayarlar FOR EACH STATEMENT EXECUTE FUNCTION veri_surumu_artir();
CREATE OR REPLACE TRIGGER veri_surumu_trg AFTER INSERT OR DELETE OR UPDATE OR TRUNCATE ON public.satislar FOR EACH STATEMENT EXECUTE FUNCTION veri_surumu_artir();
CREATE OR REPLACE TRIGGER veri_surumu_trg AFTER INSERT OR DELETE OR UPDATE OR TRUNCATE ON public.stok_yas FOR EACH STATEMENT EXECUTE FUNCTION veri_surumu_artir();
CREATE OR REPLACE TRIGGER veri_surumu_trg AFTER INSERT OR DELETE OR UPDATE OR TRUNCATE ON public.urunler FOR EACH STATEMENT EXECUTE FUNCTION veri_surumu_artir();
CREATE OR REPLACE TRIGGER veri_surumu_trg AFTER INSERT OR DELETE OR UPDATE OR TRUNCATE ON public.yoldaki_urunler FOR EACH STATEMENT EXECUTE FUNCTION veri_surumu_artir();

-- ─── 8) Açıklamalar ────────────────────────────────────────────────────
COMMENT ON TABLE public.hata_kayitlari IS 'Sessizce yutulan hataların kaydı — para/stok yollarındakiler kritik';
COMMENT ON TABLE public.kullanici_yetkileri IS 'Kullanıcı modül ve özel yetkileri — 👥 Kullanıcı Yönetimi ekranından yönetilir';
COMMENT ON TABLE public.stok_hareketleri IS 'Stok hareket defteri — her depo_kirilim değişimi ve başarısız deneme';
COMMENT ON COLUMN public.kullanici_yetkileri.aktif IS 'false ise giriş yapamaz (Secrets''ta tanımlı olsa bile)';
COMMENT ON COLUMN public.kullanici_yetkileri.moduller IS 'kayranacc, kayranpm, depo, ithalat, teknikservis, satis, hesap_makinesi';
COMMENT ON COLUMN public.kullanici_yetkileri.ozel IS 'yonetim, patron_panel, toplam_aktifler, talep_yonetici, kullanici_yonetimi';
COMMENT ON COLUMN public.kullanici_yetkileri.salt_okur IS 'true ise tüm modülleri görür, hiçbir veriyi değiştiremez';
COMMENT ON COLUMN public.talepler.kategori IS 'Hata bildirimi / Yeni özellik / İyileştirme / Soru / Rapor / Diğer';
COMMENT ON COLUMN public.talepler.oncelik IS 'Düşük / Normal / Yüksek / Acil';
COMMENT ON COLUMN public.ts_kayitlar.gelis_kargo_no IS 'Mal kabulde girilen, ürünün bize geldiği kargo takip no';
COMMENT ON COLUMN public.ts_kayitlar.gidis_kargo_no IS 'Gönderildi durumunda girilen, ürünün geri gönderildiği kargo takip no';
COMMENT ON COLUMN public.ts_kayitlar.gidis_sevk_sekli IS 'Gönderim sevk/teslim şekli (Kargo, Firma sevkiyat, ...)';
COMMENT ON COLUMN public.ts_kayitlar.irsaliye_no IS 'Ürünün gönderildiği sevk irsaliyesi numarası (TS-YYYY-NNNNN)';

-- ─── 9) Satır güvenliği (RLS) ──────────────────────────────────────────
-- Canlıda her tabloda RLS AÇIK ve hiç politika YOK: anon/authenticated hiçbir
-- satırı göremez. Uygulama service_role ile bağlanır (RLS'ye takılmaz).
DO $rls$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        '_kanal_birlestirme_yedek', '_temizlik_yedek_202610', 'aktif_excel_verileri',
        'aktif_manuel_kalemler', 'alinan_destekler', 'asistan_rapor', 'audit_log', 'bankalar',
        'bayi_giris_denemeleri', 'bayi_kullanicilar', 'bildirim_ayarlari', 'bildirimler',
        'bt_olcum', 'bt_rapor', 'cekler', 'cop_kutusu', 'depo_manuel_takip', 'depo_sevk_log',
        'edefter_ayarlar', 'edefter_donem_kilit', 'edefter_fis_satirlari', 'edefter_fisler',
        'edefter_hesap_plani', 'firma_stok', 'giris_denemeleri', 'gorevler', 'gumruk_sorgulari',
        'gunluk_giris', 'haftalar', 'happylife_stok', 'hata_kayitlari', 'hm_urun_karliligi',
        'iadeler', 'ithalat_dosyalari', 'ithalat_kalemleri', 'izin_talepleri', 'kampanya_urunler',
        'kampanyalar', 'kullanici_durum', 'kullanici_sifreler', 'kullanici_tercih',
        'kullanici_yetkileri', 'kur_gunluk', 'odemeler', 'personel', 'pm_ayarlar', 'prim_gecmis',
        'ref_butce', 'ref_firmalar', 'ref_kayitlari', 'satin_alma_gecmisi', 'satislar',
        'siparis_onerileri', 'sirket_belgeleri', 'sistem_ayarlari', 'sku_eslesme',
        'soru_kayitlari', 'stok_hareketleri', 'stok_yas', 'tahsilatlar', 'talepler', 'ts_gecmis',
        'ts_kayitlar', 'urunler', 'veri_surumu', 'virmanlar', 'yoldaki_urunler', 'yuklemeler'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    END LOOP;
END
$rls$;

-- ─── 10) Yetkiler (15_dis_erisim_kapat ile aynı sonuç) ──────────────────
-- Herkese açık (anon) ve oturum açmış (authenticated) rollerin hiçbir yetkisi yok;
-- yalnız service_role (uygulama, gece yedeği, GitHub işleri).
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC, anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO service_role;

-- İleride açılacak nesneler de kendiliğinden açık olmasın
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO service_role;
