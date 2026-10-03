-- 13 · Stok hareketlerinin yükleme koduyla işaretlenmesi (Ekim 2026)
--
-- Stok değiştiren Excel yüklemelerinin (sipariş Excel'i, Mikro dökümü, iade Excel'i, G5F sayımı,
-- teknik servis toplu mal kabul) her stok hareketi o yüklemenin koduyla işaretlenir; yükleme
-- geçmişindeki kayıt da aynı kodu taşır. Böylece bir yüklemenin stok etkisi sonradan TAM olarak
-- bulunup ters çevrilebilir (yükleme geri alma, sonraki adım).
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır. Mevcut kayıtlara
-- dokunmaz (eski hareketler işaretsiz kalır). Çalıştırılmadan önce de program çalışır: hareketler
-- işaretsiz yazılır.

ALTER TABLE stok_hareketleri ADD COLUMN IF NOT EXISTS yukleme_kodu text;
CREATE INDEX IF NOT EXISTS stok_hareketleri_yukleme_idx ON stok_hareketleri (yukleme_kodu)
    WHERE yukleme_kodu IS NOT NULL;

ALTER TABLE yuklemeler ADD COLUMN IF NOT EXISTS kod text;
CREATE INDEX IF NOT EXISTS yuklemeler_kod_idx ON yuklemeler (kod);

-- GERİ ALMA (gerekirse ayrı çalıştırın):
-- DROP INDEX IF EXISTS stok_hareketleri_yukleme_idx;
-- ALTER TABLE stok_hareketleri DROP COLUMN IF EXISTS yukleme_kodu;
-- DROP INDEX IF EXISTS yuklemeler_kod_idx;
-- ALTER TABLE yuklemeler DROP COLUMN IF EXISTS kod;
