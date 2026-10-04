-- 20 · Teknik servis arıza sonucu (Ekim 2026)
--
-- Arıza oranı (Teknik Servis › Arıza oranı) bu alandan hesaplanır. Teknisyen durum güncellerken
-- seçer (teknik / iade kaydı işlem görmüş duruma geçerken zorunlu):
--   Arıza doğrulandı · Arıza bulunamadı (NTF) · Fiziksel / kargo hasarı · Sağlam iade (cayma) · Eksik parça
-- Alanı boş kayıtlarda (bugüne kadarki bütün kayıtlar) sonuç metinden TAHMİN edilir; kayda yazılmaz.
-- Mevcut kayıtlara dokunulmaz.
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır. Kurulmadan önce seçilen
-- sonuç kaydedilemez (durum güncellemesi yine olur), sayfa tahminle çalışır.

ALTER TABLE ts_kayitlar ADD COLUMN IF NOT EXISTS ariza_sonucu text;

-- GERİ ALMA:
--   ALTER TABLE ts_kayitlar DROP COLUMN IF EXISTS ariza_sonucu;
