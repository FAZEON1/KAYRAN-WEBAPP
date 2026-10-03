-- 14 · Yükleme geri alma — satır adımı (Ekim 2026)
--
-- Geri alma artık iki adımlı (shared/yukleme_gecmisi.geri_al):
--   1) SATIRLAR (bu fonksiyon, TEK İŞLEM): yüklemenin eklediği satırlar silinir, sildiği /
--      üzerine yazdığı eski satırlar özgün kimlikleriyle geri yazılır — ya hepsi ya hiçbiri.
--   2) STOK (uygulama): yüklemenin işaretli stok hareketleri (stok_hareketleri.yukleme_kodu)
--      ürün + depo bazında TERS uygulanır; yarıda kalırsa tekrar deneme yalnız kalanı uygular.
-- Uygulama kaydı önce 'geri_aliniyor' olarak sahiplenir; bu fonksiyon yalnız o durumda ve
-- satır adımı daha önce yapılmamışsa (silinen IS NULL) çalışır. Kayıt durumunu uygulama bitirir.
--
-- Silme / yazma sırası yabancı anahtarlara göre sabit: ithalat_kalemleri → ithalat_dosyalari
-- (ON DELETE CASCADE). Servis kaydı silinince geçmişi (ts_gecmis) zincirleme silinir.
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır.
-- 12_yuklemeler.sql'deki eski yukleme_geri_al artık kullanılmaz (zararsız, yerinde kalabilir).

CREATE OR REPLACE FUNCTION yukleme_satir_geri_al(p_id bigint) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $fn$
DECLARE
    k         record;
    t         text;
    d         jsonb;
    n_sil     integer := 0;
    n_yaz     integer := 0;
    n         integer;
    v_silinen jsonb := '{}'::jsonb;
    satirlar  jsonb;
    -- izin verilen tablolar, SİLME sırasıyla (bağlı olan önce)
    sil_sira  text[] := ARRAY['ithalat_kalemleri', 'satislar', 'iadeler', 'firma_stok',
                              'happylife_stok', 'cekler', 'ref_butce', 'ithalat_dosyalari', 'ts_kayitlar'];
    -- YAZMA sırası (bağlanılan önce)
    yaz_sira  text[] := ARRAY['ithalat_dosyalari', 'ts_kayitlar', 'satislar', 'iadeler', 'firma_stok',
                              'happylife_stok', 'cekler', 'ref_butce', 'ithalat_kalemleri'];
BEGIN
    SELECT * INTO k FROM yuklemeler WHERE id = p_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'yükleme bulunamadı: %', p_id; END IF;
    IF k.durum <> 'geri_aliniyor' THEN RAISE EXCEPTION 'yükleme geri alma durumunda değil: %', k.durum; END IF;
    IF NOT k.geri_alinabilir THEN RAISE EXCEPTION 'bu yükleme geri alınamaz'; END IF;
    IF k.silinen IS NOT NULL THEN
        RETURN jsonb_build_object('silinen', 0, 'geri_yazilan', 0, 'zaten', true);
    END IF;
    FOR t IN SELECT jsonb_object_keys(k.degisiklik) LOOP
        IF t NOT LIKE '\_%' AND NOT (t = ANY (sil_sira)) THEN
            RAISE EXCEPTION 'izin verilmeyen tablo: %', t;
        END IF;
    END LOOP;
    FOREACH t IN ARRAY sil_sira LOOP
        d := k.degisiklik -> t;
        CONTINUE WHEN d IS NULL;
        EXECUTE format('WITH s AS (DELETE FROM %I WHERE id IN (SELECT (x)::bigint FROM jsonb_array_elements_text($1) x) RETURNING *) '
                       'SELECT coalesce(jsonb_agg(to_jsonb(s)), ''[]''::jsonb) FROM s', t)
            INTO satirlar USING coalesce(d -> 'eklenen', '[]'::jsonb);
        n_sil := n_sil + jsonb_array_length(satirlar);
        v_silinen := v_silinen || jsonb_build_object(t, satirlar);
    END LOOP;
    FOREACH t IN ARRAY yaz_sira LOOP
        d := k.degisiklik -> t;
        CONTINUE WHEN d IS NULL OR jsonb_array_length(coalesce(d -> 'onceki', '[]'::jsonb)) = 0;
        EXECUTE format('INSERT INTO %I OVERRIDING SYSTEM VALUE SELECT * FROM jsonb_populate_recordset(NULL::%I, $1)', t, t)
            USING d -> 'onceki';
        GET DIAGNOSTICS n = ROW_COUNT;
        n_yaz := n_yaz + n;
    END LOOP;
    UPDATE yuklemeler SET silinen = v_silinen WHERE id = p_id;
    RETURN jsonb_build_object('silinen', n_sil, 'geri_yazilan', n_yaz);
END $fn$;

-- Yalnız uygulamanın yetkili anahtarıyla (service_role) çağrılabilir.
REVOKE ALL ON FUNCTION yukleme_satir_geri_al(bigint) FROM PUBLIC;
DO $do$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION yukleme_satir_geri_al(bigint) FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON FUNCTION yukleme_satir_geri_al(bigint) FROM authenticated;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT EXECUTE ON FUNCTION yukleme_satir_geri_al(bigint) TO service_role;
    END IF;
END $do$;

-- GERİ ALMA (gerekirse ayrı çalıştırın):
-- DROP FUNCTION IF EXISTS yukleme_satir_geri_al(bigint);
