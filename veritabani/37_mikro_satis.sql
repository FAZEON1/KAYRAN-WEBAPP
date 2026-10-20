-- ════════════════════════════════════════════════════════════════════
-- 37 · Mikro satış ve iadeleri otomatik (Ekim 2026)
--
-- İSTEK (kullanıcı): "Bundan sonra tüm satışlar, iadeler API'den otomatik güncel gelsin."
--   Karar: 01.07.2026'dan itibaren satışların ve iadelerin tek kaynağı Mikro faturaları.
--
-- 1) mikro_satis_satir : aktarıcının (araclar/mikro_aktarici) çektiği satış ve satış iadesi
--    faturalarının ürün satırları (STOK_HAREKETLERI ⋈ fatura başlığı). Yalnız aktarıcı yazar.
-- 2) iadeler.belge_no  : Mikro iade faturasının numarası (eşitleme o faturanın satırlarını tanır).
-- 3) mikro_esitleme_durum : açık mı, başlangıç tarihi, son çalışma ve özeti (tek satır).
-- 4) mikro_esitleme_arsiv : eşitlemenin sildiği HER satış / iade satırının tam hâli (geri dönüş için).
-- 5) mikro_esitle_uygula(p) : uygulamanın (satis/mikro_esitle.py) hazırladığı planı TEK İŞLEMDE yazar.
--    Silinenler önce arşive yazılır. Aynı anda iki eşitleme çalışmaz (advisory lock). Bir faturanın
--    satırları eklenmeden önce o faturanın eski satırları silinir → iki kez çalışsa da çift kayıt olmaz.
--    STOK DEĞİŞMEZ: satış / iade silme-ekleme stok hareketi yazmaz (stok G5F sayımı + stok defterinden).
--
-- Tekrar çalıştırmak zararsızdır. Yalnız service_role erişir.
-- GERİ ALMA: DROP FUNCTION mikro_esitle_uygula(jsonb); DROP TABLE mikro_satis_satir, mikro_esitleme_durum;
--   (arşiv tablosu silinen satırları tutar; geri yazmadan silmeyin). ALTER TABLE iadeler DROP COLUMN belge_no;
-- ════════════════════════════════════════════════════════════════════

-- Aktarıcının daha önce canlıda elle kurulmuş tabloları (şemada kayıtlı olsun; canlıda var, değişmez)
CREATE TABLE IF NOT EXISTS public.mikro_senk_durum (
    tablo text PRIMARY KEY, son_cekim timestamptz, son_kayit_sayisi integer, son_hata text,
    guncelleme timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.mikro_cari_bakiye (
    cari_kod text NOT NULL, doviz integer NOT NULL, cari_unvan1 text, bakiye numeric,
    senk_zamani timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (cari_kod, doviz)
);
CREATE TABLE IF NOT EXISTS public.mikro_fatura (
    cha_guid uuid PRIMARY KEY, cha_evrak_tip integer, cha_tarihi timestamp, cha_evrakno_seri text,
    cha_evrakno_sira integer, cha_kod text, cha_meblag numeric, cha_d_cins integer, cha_d_kur numeric,
    cha_normal_iade integer, cha_lastup_date timestamp, senk_zamani timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.mikro_satis_satir (
    sth_guid          uuid PRIMARY KEY,
    sth_fat_uid       uuid,
    sth_tarih         timestamp,
    sth_tip           integer,
    sth_evraktip      integer,
    sth_normal_iade   integer,
    sth_stok_kod      text,
    sto_isim          text,
    sth_cari_kodu     text,
    cari_unvan1       text,
    sth_miktar        numeric,
    sth_tutar         numeric,
    sth_iskonto       numeric,
    sth_vergi         numeric,
    sth_alt_doviz_kuru numeric,
    sth_giris_depo_no integer,
    sth_cikis_depo_no integer,
    giris_depo_adi    text,
    cikis_depo_adi    text,
    cha_evrak_tip     integer,
    cha_normal_iade   integer,
    cha_evrakno_seri  text,
    cha_evrakno_sira  integer,
    cha_tarihi        timestamp,
    cha_d_cins        integer,
    cha_d_kur         numeric,
    sth_lastup_date   timestamp,
    cha_lastup_date   timestamp,
    senk_zamani       timestamptz
);
CREATE INDEX IF NOT EXISTS mikro_satis_satir_tarih_idx ON public.mikro_satis_satir (cha_tarihi);

ALTER TABLE public.iadeler ADD COLUMN IF NOT EXISTS belge_no text;

CREATE TABLE IF NOT EXISTS public.mikro_esitleme_durum (
    id          integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    acik        boolean NOT NULL DEFAULT false,
    baslangic   date NOT NULL DEFAULT DATE '2026-07-01',
    acan        text NOT NULL DEFAULT '',
    son_calisma timestamptz,
    son_ozet    jsonb
);
INSERT INTO public.mikro_esitleme_durum (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.mikro_esitleme_arsiv (
    id      bigserial PRIMARY KEY,
    zaman   timestamptz NOT NULL DEFAULT now(),
    tablo   text NOT NULL,
    satir   jsonb NOT NULL,
    neden   text NOT NULL DEFAULT ''
);

-- p: {sil_satis_id:[id], fatura_nolar:[no], ekle_satis:[satır], sil_iade_id:[id], iade_belgeler:[no],
--     ekle_iade:[satır], baslangic:'2026-07-01', ozet:{...}}
-- Döner: {silinen_satis, eklenen_satis, silinen_iade, eklenen_iade}
CREATE OR REPLACE FUNCTION public.mikro_esitle_uygula(p jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
DECLARE
    v_bas  date := COALESCE((p ->> 'baslangic')::date, DATE '2026-07-01');
    v_ss   integer := 0;
    v_es   integer := 0;
    v_si   integer := 0;
    v_ei   integer := 0;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext('mikro_esitle_uygula'));

    -- Satışlar: Mikro dışı kaynaklı satırlar (kimlikle) + yeniden yazılacak faturaların eski satırları
    WITH sil AS (
        DELETE FROM satislar s
         WHERE s.tarih >= v_bas
           AND (s.id IN (SELECT (x)::bigint FROM jsonb_array_elements_text(COALESCE(p -> 'sil_satis_id', '[]')) x)
                OR s.siparis_no IN (SELECT x FROM jsonb_array_elements_text(COALESCE(p -> 'fatura_nolar', '[]')) x))
        RETURNING s.*
    ), ars AS (
        INSERT INTO mikro_esitleme_arsiv (tablo, satir, neden)
        SELECT 'satislar', to_jsonb(sil), 'mikro_esitleme' FROM sil RETURNING 1
    )
    SELECT count(*) INTO v_ss FROM ars;

    INSERT INTO satislar (tarih, kanal, sku, urun_adi, adet, birim_satis, birim_maliyet,
                          birim_firma_destek, birim_ek_destek, siparis_no, notlar)
    SELECT r.tarih, r.kanal, r.sku, r.urun_adi, r.adet, r.birim_satis, r.birim_maliyet,
           COALESCE(r.birim_firma_destek, 0), COALESCE(r.birim_ek_destek, 0), r.siparis_no, r.notlar
      FROM jsonb_populate_recordset(NULL::satislar, COALESCE(p -> 'ekle_satis', '[]')) r
     WHERE r.tarih >= v_bas;
    GET DIAGNOSTICS v_es = ROW_COUNT;

    -- İadeler: Excel'den gelen satırlar (kimlikle) + yeniden yazılacak Mikro iade faturalarının eskileri
    WITH sil AS (
        DELETE FROM iadeler i
         WHERE i.tarih >= v_bas::text          -- iadeler.tarih metin (YYYY-MM-DD)
           AND (i.id IN (SELECT (x)::bigint FROM jsonb_array_elements_text(COALESCE(p -> 'sil_iade_id', '[]')) x)
                OR (i.kaynak = 'mikro'
                    AND i.belge_no IN (SELECT x FROM jsonb_array_elements_text(COALESCE(p -> 'iade_belgeler', '[]')) x)))
        RETURNING i.*
    ), ars AS (
        INSERT INTO mikro_esitleme_arsiv (tablo, satir, neden)
        SELECT 'iadeler', to_jsonb(sil), 'mikro_esitleme' FROM sil RETURNING 1
    )
    SELECT count(*) INTO v_si FROM ars;

    INSERT INTO iadeler (tarih, kanal, sku, urun_adi, iade_adet, iade_brut, iade_iskonto, iade_masraf,
                         iade_net, donem_bas, donem_bit, depo, kaynak, belge_no)
    SELECT r.tarih, r.kanal, r.sku, r.urun_adi, r.iade_adet, r.iade_brut, r.iade_iskonto,
           COALESCE(r.iade_masraf, 0), r.iade_net, r.donem_bas, r.donem_bit, r.depo, 'mikro', r.belge_no
      FROM jsonb_populate_recordset(NULL::iadeler, COALESCE(p -> 'ekle_iade', '[]')) r
     WHERE r.tarih >= v_bas::text;
    GET DIAGNOSTICS v_ei = ROW_COUNT;

    UPDATE mikro_esitleme_durum
       SET son_calisma = now(),
           son_ozet = COALESCE(p -> 'ozet', '{}'::jsonb)
                      || jsonb_build_object('silinen_satis', v_ss, 'eklenen_satis', v_es,
                                            'silinen_iade', v_si, 'eklenen_iade', v_ei)
     WHERE id = 1;

    RETURN jsonb_build_object('silinen_satis', v_ss, 'eklenen_satis', v_es,
                              'silinen_iade', v_si, 'eklenen_iade', v_ei);
END $fn$;

ALTER TABLE public.mikro_senk_durum ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mikro_cari_bakiye ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mikro_fatura ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mikro_satis_satir ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mikro_esitleme_durum ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mikro_esitleme_arsiv ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON FUNCTION public.mikro_esitle_uygula(jsonb) FROM PUBLIC;
DO $g$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON public.mikro_satis_satir, public.mikro_esitleme_durum, public.mikro_esitleme_arsiv FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON public.mikro_satis_satir, public.mikro_esitleme_durum, public.mikro_esitleme_arsiv
            FROM authenticated;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.mikro_satis_satir, public.mikro_esitleme_durum,
            public.mikro_esitleme_arsiv, public.mikro_senk_durum, public.mikro_cari_bakiye, public.mikro_fatura
            TO service_role;
        GRANT USAGE, SELECT ON SEQUENCE public.mikro_esitleme_arsiv_id_seq TO service_role;
        GRANT EXECUTE ON FUNCTION public.mikro_esitle_uygula(jsonb) TO service_role;
    END IF;
END
$g$;

NOTIFY pgrst, 'reload schema';
