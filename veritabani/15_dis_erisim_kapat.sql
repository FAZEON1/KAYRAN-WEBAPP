-- 15 · Herkese açık (anon) anahtarın erişimini kapat (Ekim 2026)
--
-- BULGU (canlı veritabanında doğrulandı): Supabase'in herkese açık anahtarıyla
--   • 18 tablo "allow_all" kuralı yüzünden OKUNABİLİYOR, DEĞİŞTİRİLEBİLİYOR, SİLİNEBİLİYORDU
--     (urunler — maliyetler dahil —, firma_stok, kampanyalar, prim_gecmis, sistem_ayarlari, …);
--   • satış kâr görünümleri (v_satis_pnl, v_destek_donem) ve özet tablolar (mv_gunluk_pnl,
--     mv_kanal_ay_pnl) okunabiliyordu (görünümler sahibinin yetkisiyle çalıştığı için RLS'yi aşıyordu);
--   • iki SECURITY DEFINER fonksiyon dışarıdan çağrılabiliyordu.
-- Uygulama, gece yedeği ve GitHub işleri YETKİLİ anahtarla (service_role) bağlanır — son 24 saatte
-- herkese açık anahtarla gelen istek yok. service_role RLS'ye takılmaz; bu dosya ona dokunmaz.
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır.

-- 1) Tablo / görünüm / özet tablo / sıra: herkese açık rollerden tüm yetkiler geri
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;

-- 2) İleride açılacak tablolar da otomatik açık olmasın (Supabase varsayılanı açıyordu)
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM anon, authenticated;

-- 3) Görünümler sorgulayanın yetkisiyle çalışsın (sahibinin yetkisiyle RLS'yi aşmasın)
ALTER VIEW IF EXISTS v_satis_pnl SET (security_invoker = on);
ALTER VIEW IF EXISTS v_destek_donem SET (security_invoker = on);

-- 4) SECURITY DEFINER fonksiyonlar yalnız yetkili anahtarla
DO $do$
BEGIN
    IF to_regprocedure('public.mv_gunluk_pnl_tazele()') IS NOT NULL THEN
        ALTER FUNCTION public.mv_gunluk_pnl_tazele() SET search_path = public;
        REVOKE ALL ON FUNCTION public.mv_gunluk_pnl_tazele() FROM PUBLIC, anon, authenticated;
        GRANT EXECUTE ON FUNCTION public.mv_gunluk_pnl_tazele() TO service_role;
    END IF;
    IF to_regprocedure('public.veri_surumu_artir()') IS NOT NULL THEN
        REVOKE ALL ON FUNCTION public.veri_surumu_artir() FROM PUBLIC, anon, authenticated;
        GRANT EXECUTE ON FUNCTION public.veri_surumu_artir() TO service_role;
    END IF;
END $do$;

-- 5) "Herkese izin" (USING true) kuralları: yetkiler kapalıyken etkisiz, ama biri yetkiyi yanlışlıkla
--    geri açarsa tablo yine kapalı kalsın diye silinir. service_role RLS'ye takılmaz.
DO $do$
DECLARE r record;
BEGIN
    FOR r IN SELECT * FROM (VALUES
        ('bildirim_ayarlari', 'allow_all_bildirim_ayarlari'),
        ('bildirimler', 'allow_all_bl'),
        ('firma_stok', 'allow_all_firma_stok'),
        ('gorevler', 'allow_all_gorevler'),
        ('hm_urun_karliligi', 'hm_karliligi_all'),
        ('kampanya_urunler', 'allow_all_kampanya_urunler'),
        ('kampanyalar', 'allow_all_kampanyalar'),
        ('kullanici_durum', 'allow_all'),
        ('prim_gecmis', 'service_role_full_access'),
        ('satin_alma_gecmisi', 'allow_all_satin_alma_gecmisi'),
        ('siparis_onerileri', 'allow_all_siparis_onerileri'),
        ('sistem_ayarlari', 'allow_all_sa'),
        ('sku_eslesme', 'allow_all_sku_eslesme'),
        ('stok_yas', 'allow_all_stok_yas'),
        ('talepler', 'allow_all_talepler'),
        ('urunler', 'allow_all_urunler'),
        ('veri_surumu', 'allow_all_veri_surumu'),
        ('yoldaki_urunler', 'allow_all_yoldaki_urunler')) v(tablo, kural)
    LOOP
        IF to_regclass('public.' || r.tablo) IS NOT NULL THEN
            EXECUTE format('DROP POLICY IF EXISTS %I ON %I', r.kural, r.tablo);
        END IF;
    END LOOP;
END $do$;

-- GERİ ALMA (gerekirse ayrı çalıştırın — erişimi YENİDEN AÇAR):
-- GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated;
-- (kurallar: CREATE POLICY <ad> ON <tablo> FOR ALL TO public USING (true) WITH CHECK (true);)
-- ALTER VIEW v_satis_pnl SET (security_invoker = off); ALTER VIEW v_destek_donem SET (security_invoker = off);
