-- ════════════════════════════════════════════════════════════════════
-- 50 · Geçmiş İthalatlar Mikro'dan (Ekim 2026)
--
-- İSTEK (kullanıcı): "Mikro'dan geçmiş ithalatlar datalarını alıp programa entegre edeceksin" — masraflar,
--   teslim tarihi / durum / beyanname Mikro'dan; uygulamadaki PI dosyaları Mikro dosyasına bağlanır; Mikro'da
--   açılıp uygulamada olmayan dosya eklenir. Kullanıcı onaylı (21.10.2026): karşılaştırma onayı beklemeden
--   otomatik; her değişiklikten önce eski satır mikro_esitleme_arsiv'e yazılır. Hesap: ithalat/mikro_ithalat.py.
--
-- 1) mikro_ithalat: aktarıcının kopyası (canlıda elle kurulmuştu; burada kayıtlı). Masraf satırının adı, sırası,
--    evrak no ve beyanname no kolonları eklendi.
-- 2) ithalat_dosyalari.mikro_kodu (Mikro ithalat dosya kodu, ör. MASTER-008; bir Mikro dosyası birden çok PI
--    dosyasına bağlanabilir) ve mikro_beyanname (gümrük beyannamesi no).
--
-- GERİ ALMA: ALTER TABLE ithalat_dosyalari DROP COLUMN mikro_kodu, DROP COLUMN mikro_beyanname;
--   ALTER TABLE mikro_ithalat DROP COLUMN cha_aciklama, DROP COLUMN cha_satir_no, DROP COLUMN cha_evrakno_seri,
--   DROP COLUMN cha_evrakno_sira, DROP COLUMN cha_belge_no;
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.mikro_ithalat (
    cha_guid uuid PRIMARY KEY, cha_tarihi timestamp, cha_evrak_tip integer, cha_cinsi integer, cha_cari_cins integer,
    dosya_veya_cari text, cha_meblag numeric, cha_d_cins integer, cha_d_kur numeric, cha_eximkodu text,
    cha_lastup_date timestamp, senk_zamani timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.mikro_ithalat ADD COLUMN IF NOT EXISTS cha_aciklama text;
ALTER TABLE public.mikro_ithalat ADD COLUMN IF NOT EXISTS cha_satir_no integer;
ALTER TABLE public.mikro_ithalat ADD COLUMN IF NOT EXISTS cha_evrakno_seri text;
ALTER TABLE public.mikro_ithalat ADD COLUMN IF NOT EXISTS cha_evrakno_sira integer;
ALTER TABLE public.mikro_ithalat ADD COLUMN IF NOT EXISTS cha_belge_no text;
CREATE INDEX IF NOT EXISTS mikro_ithalat_exim_idx ON public.mikro_ithalat (cha_eximkodu);

ALTER TABLE public.ithalat_dosyalari ADD COLUMN IF NOT EXISTS mikro_kodu text;
ALTER TABLE public.ithalat_dosyalari ADD COLUMN IF NOT EXISTS mikro_beyanname text;
CREATE INDEX IF NOT EXISTS ithalat_dosyalari_mikro_kodu_idx ON public.ithalat_dosyalari (mikro_kodu);

NOTIFY pgrst, 'reload schema';
