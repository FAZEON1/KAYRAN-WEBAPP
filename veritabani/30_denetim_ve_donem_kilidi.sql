-- 30 · Denetim izi koruması ve muhasebe dönem kilidi veritabanında (Ekim 2026)
--
-- (a) audit_log EKLE-YALNIZ olur: UPDATE / DELETE / TRUNCATE reddedilir. service_role da
--     takılır (tetikleyici rol ayırmaz). Bakım (ör. çok eski kayıtları arşivleme) için aynı
--     işlem (transaction) içinde açık bypass:
--         BEGIN;
--         SELECT set_config('kayran.denetim_bakim', 'on', true);   -- yalnız bu işlem için
--         DELETE FROM audit_log WHERE zaman < '2025-01-01';
--         COMMIT;
--
-- (b) e-Defter dönem kilidi: edefter_donem_kilit'teki dönemlere (donem = 'YYYY-MM',
--     kayranacc/edefter.py edf_donem_kilitle: f"{yil}-{ay:02d}"; fişin dönemi = tarih'in ilk
--     7 karakteri, edefter.py _tarih_kilitli_mi) ait edefter_fisler ve edefter_fis_satirlari
--     satırlarına INSERT / UPDATE / DELETE reddedilir. Uygulama bunu zaten ekranda denetliyor;
--     bu, ekranı atlayan yazımlara (başka sayfa, betik, elle SQL) karşı ikinci kilit.
--     İzin verilen tek güncelleme: yalnız 'kilitli' sütununun değişmesi — edf_donem_kilitle
--     önce kilidi yazar, sonra o ayın fişlerini kilitli=true işaretler; bu adım takılmasın.
--     Kilit açma (edefter_donem_kilit'ten silme) serbesttir; açılan döneme yazım yine serbest.
--     Bakım bypass'ı: SELECT set_config('kayran.donem_bakim', 'on', true);
--
-- Uygulama bu nesnelere bağlı DEĞİL: kurulmazsa kod bugünkü gibi çalışır. Tablolar yoksa
-- ilgili bölüm atlanır. Supabase → SQL Editor'de çalıştırın; tekrar çalıştırmak zararsızdır.
-- Geri alma: dosyanın sonundaki GERİ ALMA bloğu.

-- ── (a) audit_log: ekle-yalnız ────────────────────────────────────────
CREATE OR REPLACE FUNCTION kayran_denetim_degismez()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF coalesce(current_setting('kayran.denetim_bakim', true), '') = 'on' THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;                      -- TRUNCATE (deyim düzeyi) için dönüş değeri yok sayılır
    END IF;
    RAISE EXCEPTION 'audit_log değiştirilemez/silinemez (%). Bakım için: set_config(''kayran.denetim_bakim'',''on'',true)', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$;

DO $$
BEGIN
    IF to_regclass('public.audit_log') IS NOT NULL THEN
        DROP TRIGGER IF EXISTS audit_log_degismez ON public.audit_log;
        CREATE TRIGGER audit_log_degismez
            BEFORE UPDATE OR DELETE ON public.audit_log
            FOR EACH ROW EXECUTE FUNCTION kayran_denetim_degismez();
        DROP TRIGGER IF EXISTS audit_log_bosaltilamaz ON public.audit_log;
        CREATE TRIGGER audit_log_bosaltilamaz
            BEFORE TRUNCATE ON public.audit_log
            FOR EACH STATEMENT EXECUTE FUNCTION kayran_denetim_degismez();
    ELSE
        RAISE NOTICE 'audit_log tablosu yok — (a) atlandı';
    END IF;
END $$;

-- ── (b) e-Defter dönem kilidi ─────────────────────────────────────────
CREATE OR REPLACE FUNCTION kayran_donem_kilitli_mi(p_tarih text)
RETURNS boolean
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    -- plpgsql: gövde ilk çağrıda derlenir; tablo henüz yoksa kurulum yine geçer
    IF p_tarih IS NULL OR to_regclass('public.edefter_donem_kilit') IS NULL THEN
        RETURN false;
    END IF;
    RETURN EXISTS (SELECT 1 FROM public.edefter_donem_kilit k
                   WHERE k.donem::text = left(p_tarih, 7));
END;
$$;

CREATE OR REPLACE FUNCTION kayran_edefter_fis_kilit()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF coalesce(current_setting('kayran.donem_bakim', true), '') = 'on' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;
    IF TG_OP = 'UPDATE'
       AND (to_jsonb(NEW) - 'kilitli') = (to_jsonb(OLD) - 'kilitli') THEN
        RETURN NEW;                      -- yalnız kilitli işareti değişiyor (dönem kilitleme adımı)
    END IF;
    IF TG_OP IN ('UPDATE', 'DELETE') AND kayran_donem_kilitli_mi(OLD.tarih::text) THEN
        RAISE EXCEPTION '% dönemi kilitli — fiş değiştirilemez/silinemez', left(OLD.tarih::text, 7)
            USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') AND kayran_donem_kilitli_mi(NEW.tarih::text) THEN
        RAISE EXCEPTION '% dönemi kilitli — bu aya fiş eklenemez/taşınamaz', left(NEW.tarih::text, 7)
            USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION kayran_edefter_satir_kilit()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_eski text;
    v_yeni text;
BEGIN
    IF coalesce(current_setting('kayran.donem_bakim', true), '') = 'on' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        SELECT f.tarih::text INTO v_eski FROM public.edefter_fisler f WHERE f.id = OLD.fis_id;
        IF kayran_donem_kilitli_mi(v_eski) THEN
            RAISE EXCEPTION '% dönemi kilitli — fiş satırı değiştirilemez/silinemez', left(v_eski, 7)
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        SELECT f.tarih::text INTO v_yeni FROM public.edefter_fisler f WHERE f.id = NEW.fis_id;
        IF kayran_donem_kilitli_mi(v_yeni) THEN
            RAISE EXCEPTION '% dönemi kilitli — bu döneme fiş satırı eklenemez', left(v_yeni, 7)
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;

DO $$
BEGIN
    IF to_regclass('public.edefter_donem_kilit') IS NULL
       OR to_regclass('public.edefter_fisler') IS NULL THEN
        RAISE NOTICE 'edefter tabloları yok — (b) atlandı';
        RETURN;
    END IF;
    DROP TRIGGER IF EXISTS edefter_fisler_donem_kilidi ON public.edefter_fisler;
    CREATE TRIGGER edefter_fisler_donem_kilidi
        BEFORE INSERT OR UPDATE OR DELETE ON public.edefter_fisler
        FOR EACH ROW EXECUTE FUNCTION kayran_edefter_fis_kilit();
    IF to_regclass('public.edefter_fis_satirlari') IS NOT NULL THEN
        DROP TRIGGER IF EXISTS edefter_fis_satirlari_donem_kilidi ON public.edefter_fis_satirlari;
        CREATE TRIGGER edefter_fis_satirlari_donem_kilidi
            BEFORE INSERT OR UPDATE OR DELETE ON public.edefter_fis_satirlari
            FOR EACH ROW EXECUTE FUNCTION kayran_edefter_satir_kilit();
    END IF;
END $$;

-- ── Kurulum sonrası kontrol (salt okur) ───────────────────────────────
-- SELECT tgname, tgrelid::regclass FROM pg_trigger
--  WHERE tgname IN ('audit_log_degismez', 'audit_log_bosaltilamaz',
--                   'edefter_fisler_donem_kilidi', 'edefter_fis_satirlari_donem_kilidi');

-- ══ GERİ ALMA ═════════════════════════════════════════════════════════
-- Aşağıdaki satırların başındaki "-- " kaldırılıp çalıştırılırsa her şey kurulum öncesine döner
-- (veriye dokunmaz; yalnız tetikleyiciler ve fonksiyonlar silinir).
-- DROP TRIGGER IF EXISTS audit_log_degismez ON public.audit_log;
-- DROP TRIGGER IF EXISTS audit_log_bosaltilamaz ON public.audit_log;
-- DROP TRIGGER IF EXISTS edefter_fisler_donem_kilidi ON public.edefter_fisler;
-- DROP TRIGGER IF EXISTS edefter_fis_satirlari_donem_kilidi ON public.edefter_fis_satirlari;
-- DROP FUNCTION IF EXISTS kayran_edefter_satir_kilit();
-- DROP FUNCTION IF EXISTS kayran_edefter_fis_kilit();
-- DROP FUNCTION IF EXISTS kayran_donem_kilitli_mi(text);
-- DROP FUNCTION IF EXISTS kayran_denetim_degismez();
