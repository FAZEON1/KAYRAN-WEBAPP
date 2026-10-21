-- ════════════════════════════════════════════════════════════════════
-- 38 · Mikro keşfi + aktarıcının kendini güncellemesi (Ekim 2026)
--
-- İSTEK (kullanıcı): "Olabildiğince az dosya upload / elle giriş; olabilecek tüm veriler Mikro'dan."
--   Adım 0: Mikro'da hangi veri var? Aktarıcı günde bir kez tabloları, satır sayılarını, dolu tabloların
--   kolonlarını, depo / banka / kasa listelerini ve hareket türü dağılımlarını okuyup mikro_kesif'e yazar.
--   Kullanıcı: "sunucuya bir daha dosya taşımayayım" → aktarıcının güncel kodu mikro_aktarici_surum'da;
--   aktarıcı her tur başında sürüm farklıysa kendini günceller (araclar/mikro_aktarici/mikro_kayran.py:
--   kendini_guncelle — özet tutmalı, kod derlenmeli, Mikro'ya yazan uç içermemeli).
--   Kodu yalnız uygulama yazar (service_role; satis/mikro_esitle.aktarici_yayinla, depodaki dosyadan).
--
-- Tekrar çalıştırmak zararsızdır. Yalnız service_role erişir.
-- GERİ ALMA: DROP TABLE mikro_kesif, mikro_aktarici_surum;
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.mikro_kesif (
    anahtar text PRIMARY KEY,
    veri    jsonb,
    hata    text,
    zaman   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.mikro_aktarici_surum (
    id      integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    kod     text NOT NULL,
    sha256  text NOT NULL,
    yayin   timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.mikro_kesif ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mikro_aktarici_surum ENABLE ROW LEVEL SECURITY;
DO $g$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON public.mikro_kesif, public.mikro_aktarici_surum FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON public.mikro_kesif, public.mikro_aktarici_surum FROM authenticated;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.mikro_kesif, public.mikro_aktarici_surum TO service_role;
    END IF;
END
$g$;

NOTIFY pgrst, 'reload schema';
