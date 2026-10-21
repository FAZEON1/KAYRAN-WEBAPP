-- ════════════════════════════════════════════════════════════════════
-- 49 · Mikro bağlantısı sağlığı: eşitleme günlüğü + aktarıcı durdu denetimi (Ekim 2026)
--
-- İSTEK (kullanıcı): "Sağlık paneli, Telegram uyarısı ve eşitlemenin aktarımın hemen ardından çalışması."
--   21.10.2026: satış eşitlemesi iki saat sessizce yazmadı; GitHub'ın saatlik işi kendi zamanında hiç
--   çalışmadı (bu depoda zamanlanmış işler saatlerce gecikiyor). Artık aktarıcı yeni veri getirince Supabase
--   fonksiyonu mikro-tetik GitHub işini hemen başlatır (veritabani/fonksiyonlar/mikro-tetik).
--
-- 1) mikro_esitle_gunluk: her eşitleme turunun iş sonuçları ve bulunan sorunlar (shared/mikro_saglik.py yazar,
--    14 gün tutulur). Sistem › Mikro bağlantısı ekranı buradan okur. Yalnız service_role.
-- 2) Zamanlayıcı (pg_cron + pg_net): 30 dakikada bir, aktarıcı 45 dakikadır yazmadıysa mikro-tetik'i "kontrol"
--    moduyla çağırır. Fonksiyon gecikmeyi kendisi doğrular, en fazla 3 saatte bir GitHub işini başlatır; o iş
--    Telegram'a uyarı yazar. Çağrıda anahtar yok (kontrol modu anahtar istemez, yalnız denetler).
--
-- GERİ ALMA: SELECT cron.unschedule('mikro-saglik'); DROP TABLE mikro_esitle_gunluk;
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.mikro_esitle_gunluk (
    id       bigserial PRIMARY KEY,
    zaman    timestamptz NOT NULL DEFAULT now(),
    kaynak   text NOT NULL DEFAULT '',
    isler    jsonb NOT NULL DEFAULT '[]'::jsonb,
    sorunlar jsonb NOT NULL DEFAULT '[]'::jsonb
);
CREATE INDEX IF NOT EXISTS mikro_esitle_gunluk_zaman_idx ON public.mikro_esitle_gunluk (zaman DESC);

DO $g$
BEGIN
    EXECUTE 'ALTER TABLE public.mikro_esitle_gunluk ENABLE ROW LEVEL SECURITY';
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON public.mikro_esitle_gunluk FROM anon';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        EXECUTE 'REVOKE ALL ON public.mikro_esitle_gunluk FROM authenticated';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON public.mikro_esitle_gunluk TO service_role';
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE public.mikro_esitle_gunluk_id_seq TO service_role';
    END IF;
END
$g$;

CREATE EXTENSION IF NOT EXISTS pg_cron;
CREATE EXTENSION IF NOT EXISTS pg_net;

SELECT cron.schedule(
    'mikro-saglik',
    '*/30 * * * *',
    $cron$
    SELECT net.http_post(
        url := 'https://qspwlqegoeudifxxrxcj.supabase.co/functions/v1/mikro-tetik',
        body := '{"mod": "kontrol"}'::jsonb,
        headers := '{"Content-Type": "application/json"}'::jsonb
    )
    WHERE (SELECT max(guncelleme) FROM public.mikro_senk_durum) < now() - interval '45 minutes';
    $cron$
);

NOTIFY pgrst, 'reload schema';
