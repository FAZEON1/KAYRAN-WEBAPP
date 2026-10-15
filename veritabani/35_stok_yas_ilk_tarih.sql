-- ════════════════════════════════════════════════════════════════════
-- 35 · Stok yaşı "ilk görülme" tarihi korunur (Ekim 2026)
--
-- SORUN: stok_yas.ilk_gorulen_tarih (ürünün ilk görüldüğü gün) her ürün kaydında ve her G5F
--   aktarımında BUGÜNÜN tarihiyle eziliyordu. 13.10.2026 aktarımı 116 ürünün tarihini 13 Ekim yaptı.
--   Stok kartındaki "İlk görülme" ve alım partisi olmayan ürünün yedek stok yaşı bu tarihi kullanır.
-- ÇÖZÜM:
--   1) g5f_stok_aktar (34) stok_yas'a yalnız kaydı olmayan ürün için yazar (ON CONFLICT DO NOTHING).
--      Uygulamadaki diğer yazımlar da aynı kurala geçti (kayranpm.database.stok_yas_ilk_gorulen).
--   2) Bir kerelik onarım: tarihi, ürün kartının açılış tarihinden (urunler.ilk_giris_tarihi — kart
--      açılınca yazılır, sonra hiç değişmez) DAHA YENİ olan kayıtlar kartın açılış tarihine çekilir.
--      Yalnız tarihi geriye alır; daha eskiyi asla yenilemez. Tekrar çalıştırmak zararsızdır.
--
-- Ön koşul: 34_g5f_aktarim_tek_islem.sql.
-- ════════════════════════════════════════════════════════════════════

-- p_urunler : [{sku, urun_adi, bizim_stok, depo_kirilim, yeni_kart (kart yoksa eklenecek satır)}]
-- p_sifirla : [sku, ...]  Excel'de olmayan, kırılımı sıfırlanacak kartlar
-- p_ortam   : {kaynak, kullanici, yukleme_kodu, bugun}
-- Döner     : {guncellenen, yeni, sifirlanan}
CREATE OR REPLACE FUNCTION g5f_stok_aktar(p_urunler jsonb, p_sifirla jsonb, p_ortam jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
DECLARE
    u        jsonb;
    s        text;
    v_sku    text;
    v_var    boolean;
    v_eski   jsonb;
    v_ad     text;
    v_yeni   jsonb;
    n_guncel integer := 0;
    n_yeni   integer := 0;
    n_sifir  integer := 0;
    v_tarih  urunler.guncelleme_tarihi%TYPE;
    v_yas    boolean := to_regclass('public.stok_yas') IS NOT NULL;
BEGIN
    v_tarih := (jsonb_populate_record(NULL::urunler,
                jsonb_build_object('guncelleme_tarihi', p_ortam ->> 'bugun'))).guncelleme_tarihi;
    -- Kilitlenmeyi (deadlock) önlemek için bütün kartlar baştan, sabit sırayla kilitlenir.
    PERFORM 1 FROM urunler
     WHERE sku IN (SELECT x ->> 'sku' FROM jsonb_array_elements(coalesce(p_urunler, '[]'::jsonb)) x
                   UNION SELECT jsonb_array_elements_text(coalesce(p_sifirla, '[]'::jsonb)))
     ORDER BY sku FOR UPDATE;

    FOR u IN SELECT value FROM jsonb_array_elements(coalesce(p_urunler, '[]'::jsonb)) LOOP
        v_sku  := u ->> 'sku';
        CONTINUE WHEN coalesce(v_sku, '') = '';
        v_yeni := coalesce(u -> 'depo_kirilim', '{}'::jsonb);
        v_var  := false;
        SELECT true, depo_kirilim, urun_adi INTO v_var, v_eski, v_ad FROM urunler WHERE sku = v_sku;
        IF coalesce(v_var, false) THEN
            UPDATE urunler
               SET bizim_stok = (u ->> 'bizim_stok')::integer, depo_kirilim = v_yeni,
                   guncelleme_tarihi = v_tarih,
                   urun_adi = CASE WHEN kayran_strip(coalesce(v_ad, '')) = '' AND coalesce(u ->> 'urun_adi', '') <> ''
                                   THEN u ->> 'urun_adi' ELSE urun_adi END
             WHERE sku = v_sku;
            PERFORM kayran_defter_fark(v_sku, v_eski, v_yeni, 'aktarim', 'Excel/G5F stok aktarımı', p_ortam);
            n_guncel := n_guncel + 1;
        ELSE
            PERFORM kayran_ekle('urunler', jsonb_build_array(u -> 'yeni_kart'), NULL);
            PERFORM kayran_defter_fark(v_sku, '{}'::jsonb, v_yeni, 'aktarim',
                                       'Excel/G5F stok aktarımı · yeni kart', p_ortam);
            n_yeni := n_yeni + 1;
        END IF;
        IF v_yas THEN
            INSERT INTO stok_yas (sku, ilk_gorulen_tarih)
            VALUES (v_sku, (p_ortam ->> 'bugun')::date)
            ON CONFLICT (sku) DO NOTHING;               -- ilk görülme tarihi korunur (35)
        END IF;
    END LOOP;

    -- BİREBİR SENKRON: Excel'de olmayan kartların eski kırılımı sıfırlanır.
    FOR s IN SELECT jsonb_array_elements_text(coalesce(p_sifirla, '[]'::jsonb)) LOOP
        v_var := false;
        SELECT true, depo_kirilim INTO v_var, v_eski FROM urunler WHERE sku = s;
        CONTINUE WHEN NOT coalesce(v_var, false);
        UPDATE urunler SET depo_kirilim = '{}'::jsonb, bizim_stok = 0 WHERE sku = s;
        PERFORM kayran_defter_fark(s, v_eski, '{}'::jsonb, 'sifirlama',
                                   'Excel''de yok — birebir senkron sıfırlama', p_ortam);
        n_sifir := n_sifir + 1;
    END LOOP;

    RETURN jsonb_build_object('guncellenen', n_guncel, 'yeni', n_yeni, 'sifirlanan', n_sifir);
END $fn$;

-- 2) Bir kerelik onarım (canlıda 14.10.2026 itibarıyla 135 kayıt)
UPDATE stok_yas y
   SET ilk_gorulen_tarih = u.ilk_giris_tarihi
  FROM urunler u
 WHERE u.sku = y.sku
   AND u.ilk_giris_tarihi IS NOT NULL
   AND (y.ilk_gorulen_tarih IS NULL OR u.ilk_giris_tarihi < y.ilk_gorulen_tarih);

NOTIFY pgrst, 'reload schema';

-- KONTROL:  SELECT ilk_gorulen_tarih, count(*) FROM stok_yas GROUP BY 1 ORDER BY 1 DESC;
-- GERİ ALMA: fonksiyon için 34_g5f_aktarim_tek_islem.sql yeniden çalıştırılır. Onarılan tarihlerin
--   önceki değerleri (hepsi aktarım günleri) gece yedeğindedir (stok_yas).
