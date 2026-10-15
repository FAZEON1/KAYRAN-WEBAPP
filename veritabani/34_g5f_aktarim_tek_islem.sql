-- ════════════════════════════════════════════════════════════════════
-- 34 · G5F (Excel/Mikro) stok aktarımı tek işlemde (Ekim 2026)
--
-- SORUN: Aktarım her ürünü ayrı istekle güncelliyordu (oku → yaz → stok defteri → stok_yas), sonra
--   Excel'de olmayan ürünleri ayrı ayrı sıfırlıyordu. Arada bağlantı koparsa ürünlerin bir kısmı yeni
--   sayımla, kalanı eski sayımla kalıyordu; stok defteri de ürün güncellemesinden ayrı yazılıyordu.
-- ÇÖZÜM: Bütün ürünler + Excel'de olmayanların sıfırlanması + stok defteri + stok_yas TEK İŞLEMDE.
--   Ya hepsi ya hiçbiri. Ürün satırları baştan, sabit sırayla kilitlenir.
--
-- HESAP KURALLARI BUGÜNKÜYLE BİREBİR AYNI (kayranpm/database.upsert_g5f_stok + excel_islemler senkron):
--   · Var olan kart : bizim_stok, depo_kirilim, guncelleme_tarihi yazılır; ad yalnız kartta boşsa
--                     Excel'deki adla doldurulur. Fiyat / kategori / marka DOKUNULMAZ.
--   · Yeni kart     : uygulamanın hazırladığı kart satırı eklenir (yeni_kart).
--   · Defter        : değişen her depo için bir satır (shared/stok_defteri.fark: depo adına göre sıralı,
--                     |önce − sonra| > 1e-9), tür 'aktarim' / 'sifirlama'.
--   · stok_yas      : (sku, bugün) yazılır (bugünkü upsert ile aynı).
--   · Hangi kartın güncelleneceği, hangisinin sıfırlanacağı, satılabilir stok uygulamada hesaplanır
--     (SKU eşleştirme Python'daki normalize_sku ile) ve buraya hazır gelir.
--
-- Uygulama bu fonksiyonu önce dener; YOKSA bugünkü yoldan (ürün ürün) devam eder — aynı sonuç.
-- Fonksiyon var ama işlem reddedilirse hiçbir şey yazılmaz, kullanıcı açık hata görür.
--
-- Ön koşul: 29_atomik_stok.sql (kayran_strip, kayran_sayi, kayran_defter_yaz, kayran_ekle).
-- Tekrar çalıştırmak zararsızdır (CREATE OR REPLACE). Yalnız service_role çağırabilir.
-- ════════════════════════════════════════════════════════════════════

-- Stok defteri: iki kırılım arasındaki farkı yaz (shared/stok_defteri.yaz_fark)
CREATE OR REPLACE FUNCTION kayran_defter_fark(p_sku text, p_eski jsonb, p_yeni jsonb, p_tur text,
                                              p_aciklama text, p_ortam jsonb)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
DECLARE
    d   text;
    a   double precision;
    b   double precision;
    e   jsonb := CASE WHEN jsonb_typeof(p_eski) = 'object' THEN p_eski ELSE '{}'::jsonb END;
    y   jsonb := CASE WHEN jsonb_typeof(p_yeni) = 'object' THEN p_yeni ELSE '{}'::jsonb END;
BEGIN
    FOR d IN SELECT k FROM (SELECT jsonb_object_keys(e) AS k UNION SELECT jsonb_object_keys(y)) s
             ORDER BY k COLLATE "C" LOOP
        a := kayran_sayi(e -> d);
        b := kayran_sayi(y -> d);
        IF abs(a - b) > 1e-9 THEN
            PERFORM kayran_defter_yaz(p_sku, d, a, b, p_tur, p_aciklama, true, '', p_ortam);
        END IF;
    END LOOP;
END $fn$;

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
            ON CONFLICT (sku) DO UPDATE SET ilk_gorulen_tarih = excluded.ilk_gorulen_tarih;
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

DO $g$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION g5f_stok_aktar(jsonb, jsonb, jsonb) FROM anon;
        REVOKE ALL ON FUNCTION kayran_defter_fark(text, jsonb, jsonb, text, text, jsonb) FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON FUNCTION g5f_stok_aktar(jsonb, jsonb, jsonb) FROM authenticated;
        REVOKE ALL ON FUNCTION kayran_defter_fark(text, jsonb, jsonb, text, text, jsonb) FROM authenticated;
    END IF;
    REVOKE ALL ON FUNCTION g5f_stok_aktar(jsonb, jsonb, jsonb) FROM PUBLIC;
    REVOKE ALL ON FUNCTION kayran_defter_fark(text, jsonb, jsonb, text, text, jsonb) FROM PUBLIC;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT EXECUTE ON FUNCTION g5f_stok_aktar(jsonb, jsonb, jsonb) TO service_role;
        GRANT EXECUTE ON FUNCTION kayran_defter_fark(text, jsonb, jsonb, text, text, jsonb) TO service_role;
    END IF;
END
$g$;

NOTIFY pgrst, 'reload schema';

-- KONTROL:  SELECT proname FROM pg_proc WHERE proname IN ('g5f_stok_aktar', 'kayran_defter_fark');
-- GERİ ALMA (uygulama kendiliğinden bugünkü ürün ürün yola döner):
--   DROP FUNCTION IF EXISTS g5f_stok_aktar(jsonb, jsonb, jsonb);
--   DROP FUNCTION IF EXISTS kayran_defter_fark(text, jsonb, jsonb, text, text, jsonb);
