-- ════════════════════════════════════════════════════════════════════
-- 51 · Mikro aktarıcısı: çalışan sürüm + iptal yansıması sayacı (Ekim 2026)
--
-- 1) mikro_aktarici_surum: aktarıcı her turda BELLEKTE çalışan kodunun sha256 özetini, zamanı ve sürüm
--    durumunu yazar (araclar/mikro_aktarici/mikro_kayran.py: surum_bildir / surum_yaz). Kendini güncellediği
--    turda "yeni kod yazıldı; bu tur eski kodla çalışıyor, yeni kod bir sonraki turda devreye girer" yazar.
--    Yayındaki sürüm (sha256) ile calisan_sha256 aynıysa sunucu güncel koddadır. Satırı yalnız günceller
--    (PATCH id=1); kod / sha256 / yayin kolonlarını uygulama yazar (satis/mikro_esitle.aktarici_yayinla).
-- 2) mikro_senk_durum.son_silinen: artımlı turda, Mikro'da son çekimden beri iptal edilip Supabase kopyasından
--    silinen satır sayısı (iptalleri_yansit). Mikro'ya yalnız SELECT atılır.
--
-- Uygulama sırası: bu dosya kod yayınından ÖNCE uygulanmalı. Uygulanmazsa aktarıcı çalışmaya devam eder,
-- yalnız bu alanları yazamaz (günlüğe uyarı düşer).
-- Tekrar çalıştırmak zararsızdır.
-- GERİ ALMA: ALTER TABLE mikro_aktarici_surum DROP COLUMN calisan_sha256, DROP COLUMN calisan_zaman,
--   DROP COLUMN calisan_durum; ALTER TABLE mikro_senk_durum DROP COLUMN son_silinen;
-- ════════════════════════════════════════════════════════════════════

ALTER TABLE public.mikro_aktarici_surum ADD COLUMN IF NOT EXISTS calisan_sha256 text;
ALTER TABLE public.mikro_aktarici_surum ADD COLUMN IF NOT EXISTS calisan_zaman timestamptz;
ALTER TABLE public.mikro_aktarici_surum ADD COLUMN IF NOT EXISTS calisan_durum text;

ALTER TABLE public.mikro_senk_durum ADD COLUMN IF NOT EXISTS son_silinen integer;

NOTIFY pgrst, 'reload schema';
