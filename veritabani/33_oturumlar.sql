-- ════════════════════════════════════════════════════════════════════
-- 33 · Kalıcı oturum deposu (Ekim 2026)
--
-- SORUN: Oturumlar yalnız sunucu belleğindeydi (shared/oturum.oturum_store). Streamlit yeniden
--   başlayınca (güncelleme, uyku, Reboot) herkes çıkış yapmış oluyordu.
-- ÇÖZÜM: Her oturum bu tabloya da yazılır; bellekte olmayan anahtar buradan okunur.
--   Anahtarın KENDİSİ tutulmaz, SHA-256 özeti tutulur (tok_ozet): tablo okunsa bile oturum
--   ele geçirilemez. ts = son kullanım (epoch saniye); 7 gün kullanılmayan oturum geçersizdir.
--
-- Kurulmasa da program bugünkü gibi çalışır (yalnız bellek). Tekrar çalıştırılabilir.
-- Yalnız uygulamanın yetkili anahtarı (service_role) erişir.
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.oturumlar (
    tok_ozet   text PRIMARY KEY,
    kullanici  text NOT NULL,
    cihaz      text NOT NULL DEFAULT '',
    ts         double precision NOT NULL,
    olusturma  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS oturumlar_kullanici_idx ON public.oturumlar (kullanici);
CREATE INDEX IF NOT EXISTS oturumlar_ts_idx ON public.oturumlar (ts);

ALTER TABLE public.oturumlar ENABLE ROW LEVEL SECURITY;
DO $g$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON public.oturumlar FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON public.oturumlar FROM authenticated;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.oturumlar TO service_role;
    END IF;
END
$g$;

NOTIFY pgrst, 'reload schema';

-- KONTROL:  SELECT kullanici, count(*) FROM oturumlar GROUP BY 1;
-- GERİ ALMA (uygulama kendiliğinden yalnız belleğe döner; açık oturumlar bir sonraki
--   yeniden başlatmada düşer):
--   DROP TABLE IF EXISTS public.oturumlar;
