-- 07 · Ödeme ertelemeleri KALICI olsun (Ekim 2026)
--
-- Önce: "Ertelenen Ödemeler" sayfası yalnız tarayıcı oturumundaki listeyi
-- gösteriyordu; çıkış yapınca ya da başka cihazdan girince geçmiş kayboluyordu.
-- Şimdi: vade ötelenince ödemenin İLK vadesi, kaç kez ertelendiği ve son
-- erteleme zamanı ödeme kaydının kendisinde tutulur.
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır.
-- Çalıştırılmadan önce de program çalışır (yalnız erteleme geçmişi tutulmaz).

ALTER TABLE odemeler ADD COLUMN IF NOT EXISTS orijinal_vade date;
ALTER TABLE odemeler ADD COLUMN IF NOT EXISTS ertelendi_sayisi integer NOT NULL DEFAULT 0;
ALTER TABLE odemeler ADD COLUMN IF NOT EXISTS son_erteleme_tarih timestamptz;
