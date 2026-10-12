-- 27 · Mal kabulde giriş deposu seçimi (Ekim 2026)
--
-- Teknik servis mal kabulünde (manuel form ve toplu Excel) ürünün girdiği depo seçilir:
-- İADE DEPO (varsayılan), MERKEZ DEPO, HAPPY LIFE, TEKNİK DEPO, ASEL DEPO. Müşteriden alınan iade
-- doğrudan satılacaksa MERKEZ / HAPPY LIFE seçilir; ürün satılabilir stoğa girer.
-- İade türündeki kabul, Satış › İade'ye manuel iade olarak da yazılır (iadeler, kaynak='manuel');
-- iade_net P&L'deki iade düşümü için (boş = 0). Aylık iade Excel'i görevi kaldırıldı.
--
-- Kolonlar yoksa uygulama onlarsız yazar (teknikservis.database._YENI_KOLONLAR) — giriş deposu
-- o zaman kaydedilmez, stok yine seçilen depoya işlenir. Supabase → SQL Editor'de BİR KEZ çalıştırın.

ALTER TABLE ts_kayitlar ADD COLUMN IF NOT EXISTS giris_depo text;          -- kanonik depo adı
ALTER TABLE ts_kayitlar ADD COLUMN IF NOT EXISTS iade_net   numeric(14,4); -- iade net tutarı ($)

-- GERİ ALMA:
-- ALTER TABLE ts_kayitlar DROP COLUMN IF EXISTS giris_depo, DROP COLUMN IF EXISTS iade_net;
