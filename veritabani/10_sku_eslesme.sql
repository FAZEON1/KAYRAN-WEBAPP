-- 10 · SKU eşleme tablosu (Ekim 2026)
--
-- Müşteri raporundaki kod (ör. pazaryeri kodu HBCV…) ile stok kartı arasındaki ONAYLI
-- bağlantılar. Satırları yalnız kullanıcı yazar (Ürün Yönetimi › Müşteri Satışları ›
-- Kart eşleşmesi bekleyenler); program tahminle bu tabloya hiçbir şey yazmaz.
-- Kendisi kart SKU'su olan bir kod (F11PA650BWM) başka bir karta (F11PA650BBM) eşlenemez;
-- bu kural uygulamada denetlenir (kayranpm.musteri_hesap.eslesme_dogrula).
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır.
-- Çalıştırılmadan önce de program çalışır: yalnız eşleme kaydedilemez.

CREATE TABLE IF NOT EXISTS sku_eslesme (
    dis_kod    text PRIMARY KEY,                 -- rapordaki kod, sku_anahtar ile normalize
    kart_sku   text        NOT NULL,             -- urunler.sku
    onaylayan  text,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE sku_eslesme DISABLE ROW LEVEL SECURITY;
