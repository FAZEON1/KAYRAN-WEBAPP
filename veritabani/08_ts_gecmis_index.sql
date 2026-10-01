-- 08 · Teknik Servis — ts_gecmis dizini (Ekim 2026)
--
-- Teknik Servis / İade / Depolar listeleri SLA'yı artık tek toplu sorguyla
-- hesaplıyor: ts_gecmis'ten kayıt numarasına ve duruma göre süzüp tarihe göre
-- sıralı okur. Bu dizin o sorguyu ve kayıt detayındaki işlem geçmişini hızlandırır.
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır
-- (IF NOT EXISTS); veri değiştirmez.
-- Çalıştırılmasa da uygulama aynen çalışır, yalnız biraz daha yavaş olur.

CREATE INDEX IF NOT EXISTS ts_gecmis_kayit_tarih_idx
    ON ts_gecmis (kayit_id, tarih);
