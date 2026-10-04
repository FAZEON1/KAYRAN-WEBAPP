-- 18 · Alım türü: yurt içi satın alma ve yerli üretim (Ekim 2026)
--
-- Yurt içinden alınan ya da yerli üretilen ürünlerin alımları ithalat dosyalarıyla AYNI yerde
-- tutulur (ithalat_dosyalari + ithalat_kalemleri); bu sütun türünü söyler:
--   boş / 'ithalat'  → ithalat (mevcut bütün kayıtlar; dokunulmaz)
--   'yurtici'        → yurt içi satın alma
--   'yerli'          → yerli üretim
-- Böylece paçal maliyet, Kâr/P&L, stok kartı alımları, Model sorgu ve FIFO stok yaşı bu
-- alımları kendiliğinden kullanır (hesap tek yerde). İthalat listeleri yalnız ithalatı gösterir;
-- yurt içi alımlar Ürün Yönetimi › Yurt içi alış sayfasında.
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır. Çalıştırılmadan
-- önce Yurt içi alış sayfası kayıt yapmaz (uyarı gösterir); diğer her şey bugünkü gibi çalışır.

ALTER TABLE ithalat_dosyalari ADD COLUMN IF NOT EXISTS alim_turu text;

-- GERİ ALMA: önce yurt içi kayıtlar silinmeli (yoksa ithalat sayılırlar), sonra
--   ALTER TABLE ithalat_dosyalari DROP COLUMN IF EXISTS alim_turu;
