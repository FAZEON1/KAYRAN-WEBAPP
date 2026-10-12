-- 28 · İade faturası birim fiyatı (Ekim 2026)
--
-- Teknik servis iade mal kabulünde iade faturasındaki KDV hariç birim fiyat girilir (USD ya da TL).
-- TL, iade (mal kabul) gününün kuruyla USD'ye çevrilir; raporlar USD okur (iade_net, iadeler.iade_net).
-- Fatura sonradan gelirse kayıt detayından girilir; bağlı iadeler satırı (iade_id) birlikte güncellenir.
--
-- Kolonlar yoksa uygulama onlarsız yazar (teknikservis.database._YENI_KOLONLAR).
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır.

ALTER TABLE ts_kayitlar ADD COLUMN IF NOT EXISTS iade_fiyat numeric(14,4);  -- faturadaki birim fiyat (asıl para birimi)
ALTER TABLE ts_kayitlar ADD COLUMN IF NOT EXISTS iade_pb    text;           -- 'USD' | 'TL'
ALTER TABLE ts_kayitlar ADD COLUMN IF NOT EXISTS iade_kur   numeric(10,4);  -- TL ise kullanılan USD kuru
ALTER TABLE ts_kayitlar ADD COLUMN IF NOT EXISTS iade_id    bigint;         -- bağlı iadeler.id (manuel iade)

-- GERİ ALMA:
-- ALTER TABLE ts_kayitlar DROP COLUMN IF EXISTS iade_fiyat, DROP COLUMN IF EXISTS iade_pb,
--   DROP COLUMN IF EXISTS iade_kur, DROP COLUMN IF EXISTS iade_id;
