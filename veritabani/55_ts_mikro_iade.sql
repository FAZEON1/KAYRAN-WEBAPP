-- ════════════════════════════════════════════════════════════════════
-- 55 · Mikro iade faturası → Teknik Servis İade arayüzü (Ekim 2026)
--
-- İSTEK (kullanıcı, 22.10.2026): "Serdar abi her iade faturası işlediğinde bu arayüze düşsün … her adet alt alta,
--   G5F belge no otomatik, ilk aşama 'iade faturası işlendi' … satıldı benden tamamen kalksın, Mikro'daki satıştan
--   seri no ile yakalansın."
-- ts_kayitlar  mikro_iade_anahtar  Mikro satır guid + adet sırası (aynı birim ikinci kez açılmaz)
--              iade_fatura_no / _tarihi / iade_aciklama / iade_cari_kodu  Serdar'ın girdiği fatura bilgisi
--              hasarli_teslim  açıklamasız ya da 'hasar' / 'teslim alınmayan' → teslim alınmayan hasarlı ürün
--              son_kullanici   mal kabulde S.K. işareti (EERA + mağaza seçiliyken de)
--              satis_fatura_no Mikro satış faturası (otomatik satıldı; teknikservis/mikro_satis.py)
-- mikro_alim_satir.sth_aciklama  satır açıklaması (aktarıcı alim_satir sorgusu)
--
-- GERİ ALMA:
--   DROP INDEX IF EXISTS ts_kayitlar_mikro_iade_anahtar_uq;
--   ALTER TABLE ts_kayitlar DROP COLUMN mikro_iade_anahtar, DROP COLUMN iade_fatura_no, DROP COLUMN iade_fatura_tarihi,
--     DROP COLUMN iade_aciklama, DROP COLUMN iade_cari_kodu, DROP COLUMN hasarli_teslim, DROP COLUMN son_kullanici,
--     DROP COLUMN satis_fatura_no;
--   ALTER TABLE mikro_alim_satir DROP COLUMN sth_aciklama;
-- ════════════════════════════════════════════════════════════════════

ALTER TABLE public.ts_kayitlar
    ADD COLUMN IF NOT EXISTS mikro_iade_anahtar text,
    ADD COLUMN IF NOT EXISTS iade_fatura_no text,
    ADD COLUMN IF NOT EXISTS iade_fatura_tarihi date,
    ADD COLUMN IF NOT EXISTS iade_aciklama text,
    ADD COLUMN IF NOT EXISTS iade_cari_kodu text,
    ADD COLUMN IF NOT EXISTS hasarli_teslim boolean,
    ADD COLUMN IF NOT EXISTS son_kullanici boolean,
    ADD COLUMN IF NOT EXISTS satis_fatura_no text;

CREATE UNIQUE INDEX IF NOT EXISTS ts_kayitlar_mikro_iade_anahtar_uq
    ON public.ts_kayitlar (mikro_iade_anahtar) WHERE mikro_iade_anahtar IS NOT NULL;

ALTER TABLE public.mikro_alim_satir ADD COLUMN IF NOT EXISTS sth_aciklama text;
