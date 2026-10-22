-- ════════════════════════════════════════════════════════════════════
-- 53 · Ref No kalemleri (Ekim 2026)
--
-- SORUN (talep #36, 22.10.2026): Ref No Takip › Kalemler bölümü her ref'te boş. Kod kalem listesini
--   ref_kayitlari.kalemler (jsonb) sütununa yazıyor (kayranpm/ref_no.py kalemleri_yaz) ama sütun canlıda hiç
--   eklenmemişti: yazma sessizce yalnız toplamları güncelliyor, kalemler kayboluyordu. Kampanyadan açılan
--   ref'lerde ürün bazında düzeltme yapılamıyordu.
-- ÇÖZÜM: sütun eklenir (boş başlar; mevcut tutar / aylık / kategori_tutar değişmez).
--
-- GERİ ALMA: ALTER TABLE public.ref_kayitlari DROP COLUMN kalemler;
-- ════════════════════════════════════════════════════════════════════

ALTER TABLE public.ref_kayitlari ADD COLUMN IF NOT EXISTS kalemler jsonb;
