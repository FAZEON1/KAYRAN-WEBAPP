-- 29 · Atomik stok yazımı (Ekim 2026)
--
-- SORUN: Satış / iade / sevk kaydı ve stok düşümü ayrı isteklerdi. Uygulama ürün kartının
--   depo_kirilim'ini (jsonb) Python'da okuyup değiştirip geri yazıyordu; kilit yoktu. İki kişi aynı
--   anda aynı ürünü satınca birinin düşümü kayboluyordu (kayıp güncelleme). Satış kaydedilip stok
--   adımı hata verirse satış yazılı, stok düşülmemiş kalıyordu.
-- ÇÖZÜM: Kayıt + stok + stok defteri (stok_hareketleri) TEK İŞLEMDE, ürün satırı SELECT … FOR UPDATE
--   ile kilitlenerek yazılır. Ya hepsi ya hiçbiri.
--
-- HESAP KURALLARI BUGÜNKÜYLE BİREBİR AYNI (kayranpm/database.py):
--   · stok_hareket_coklu : depo_kirilim[depo] = önceki + değişim (eksiye düşebilir; depo yoksa 0'dan
--                          başlar), |sonuç| < 1e-9 → 0, bizim_stok = satılabilir depoların (MERKEZ DEPO +
--                          HAPPY LIFE, adlar depo_kanonik ile) tam sayı toplamı. Kart yoksa hareket
--                          uygulanmaz, deftere basarili=false 'ürün kartı yok — stok işlenmedi' yazılır.
--   · depo_sevk          : kırılım kanonikleştirilir (_kirilim_kanonik), kaynakta yeterli stok yoksa red.
--   · SKU eşleşmesi      : uygulama her hareket için aday yazımları (girilen, BÜYÜK harf, kartın yazımı —
--                          kart_sku_coz) sırayla gönderir; burada ilk bulunan kart kilitlenir.
--   · depo adı           : kayran_depo_kanonik = kayranpm.database.depo_kanonik'in SQL karşılığı.
--
-- Uygulama bu fonksiyonları önce dener; YOKSA (dosya kurulmamışsa) bugünkü yoldan devam eder — aynı
-- sonuç. Fonksiyon var ama işlem reddedilirse (ör. yetersiz stokla sevk, veritabanı hatası) hiçbir şey
-- yazılmaz ve kullanıcıya açık hata gösterilir.
--
-- Ön koşul: 05_stok_defteri_hata_log.sql + 13_yukleme_kodu.sql (stok_hareketleri.yukleme_kodu).
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır (CREATE OR REPLACE).
-- Fonksiyonlar çağıranın yetkisiyle çalışır (SECURITY INVOKER); yalnız service_role çağırabilir.

-- ── Yardımcılar ─────────────────────────────────────────────────────

-- Python str.strip()
CREATE OR REPLACE FUNCTION kayran_strip(p text) RETURNS text
LANGUAGE sql IMMUTABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    SELECT regexp_replace(coalesce(p, ''), '^\s+|\s+$', '', 'g')
$$;

-- kayranpm.database.depo_kanonik
CREATE OR REPLACE FUNCTION kayran_depo_kanonik(p text) RETURNS text
LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
DECLARE
    n text;
    m jsonb := '{
        "MERKEZ DEPO": "MERKEZ DEPO", "MERKEZDEPO": "MERKEZ DEPO", "MERKEZ": "MERKEZ DEPO",
        "HAPPY LIFE": "HAPPY LIFE", "HAPPYLIFE": "HAPPY LIFE", "HAPPY": "HAPPY LIFE",
        "ASEL DEPO": "ASEL DEPO", "ASELDEPO": "ASEL DEPO", "ASEL": "ASEL DEPO",
        "TEKNIK DEPO": "TEKNİK DEPO", "TEKNIKDEPO": "TEKNİK DEPO", "TEKNIK": "TEKNİK DEPO",
        "SERVIS DEPO": "TEKNİK DEPO", "SERVISDEPO": "TEKNİK DEPO",
        "SERVIS": "TEKNİK DEPO", "TEKNIK SERVIS": "TEKNİK DEPO",
        "IADE DEPO": "İADE DEPO", "IADEDEPO": "İADE DEPO", "IADE": "İADE DEPO",
        "OUTLET DEPO": "OUTLET DEPO", "OUTLETDEPO": "OUTLET DEPO", "OUTLET": "OUTLET DEPO",
        "IKINCI EL DEPO": "İKİNCİ EL DEPO", "IKINCI EL": "İKİNCİ EL DEPO",
        "IKINCIEL": "İKİNCİ EL DEPO", "2.EL": "İKİNCİ EL DEPO", "2 EL": "İKİNCİ EL DEPO",
        "HURDA DEPO": "HURDA DEPO", "HURDADEPO": "HURDA DEPO", "HURDA": "HURDA DEPO"
    }';
BEGIN
    n := translate(upper(kayran_strip(p)), 'İŞĞÜÖÇ', 'ISGUOC');
    n := kayran_strip(regexp_replace(n, '\s+', ' ', 'g'));
    RETURN coalesce(m ->> n, m ->> replace(n, ' ', ''), n);
END $fn$;

-- Python float(v or 0)
CREATE OR REPLACE FUNCTION kayran_sayi(v jsonb) RETURNS double precision
LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
BEGIN
    IF v IS NULL THEN RETURN 0; END IF;
    CASE jsonb_typeof(v)
        WHEN 'number'  THEN RETURN v::double precision;
        WHEN 'null'    THEN RETURN 0;
        WHEN 'boolean' THEN RETURN CASE WHEN v = 'true'::jsonb THEN 1 ELSE 0 END;
        WHEN 'string'  THEN
            IF v #>> '{}' = '' THEN RETURN 0; END IF;
            RETURN kayran_strip(v #>> '{}')::double precision;
        ELSE
            IF v IN ('{}'::jsonb, '[]'::jsonb) THEN RETURN 0; END IF;
            RAISE EXCEPTION 'sayı değil: %', v;
    END CASE;
END $fn$;

-- Python int(v or 0) (bizim_stok toplamı)
CREATE OR REPLACE FUNCTION kayran_tam(v jsonb) RETURNS bigint
LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
BEGIN
    IF v IS NULL THEN RETURN 0; END IF;
    CASE jsonb_typeof(v)
        WHEN 'number'  THEN RETURN trunc(v::numeric)::bigint;
        WHEN 'null'    THEN RETURN 0;
        WHEN 'boolean' THEN RETURN CASE WHEN v = 'true'::jsonb THEN 1 ELSE 0 END;
        WHEN 'string'  THEN
            IF v #>> '{}' = '' THEN RETURN 0; END IF;
            RETURN kayran_strip(v #>> '{}')::bigint;
        ELSE
            IF v IN ('{}'::jsonb, '[]'::jsonb) THEN RETURN 0; END IF;
            RAISE EXCEPTION 'tam sayı değil: %', v;
    END CASE;
END $fn$;

-- kayranpm.database._bizim_stok_hesapla
CREATE OR REPLACE FUNCTION kayran_bizim_stok(p_dk jsonb) RETURNS integer
LANGUAGE sql IMMUTABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    SELECT coalesce(sum(kayran_tam(e.value)), 0)::integer
    FROM jsonb_each(CASE WHEN jsonb_typeof(p_dk) = 'object' THEN p_dk ELSE '{}'::jsonb END) e
    WHERE kayran_depo_kanonik(e.key) IN ('MERKEZ DEPO', 'HAPPY LIFE')
$$;

-- Python json.dumps(float): tam sayı değer '4.0', diğerleri en kısa gösterim
CREATE OR REPLACE FUNCTION kayran_float_json(v double precision) RETURNS jsonb
LANGUAGE sql IMMUTABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    SELECT CASE WHEN v = trunc(v) AND abs(v) < 1e15 THEN to_jsonb(round(v::numeric, 1))
                ELSE to_jsonb(v) END
$$;

-- Python f"{delta:+g}"
CREATE OR REPLACE FUNCTION kayran_g(v double precision) RETURNS text
LANGUAGE sql IMMUTABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    SELECT CASE WHEN v >= 0 THEN '+' ELSE '' END || trim_scale(round(v::numeric, 6))::text
$$;

-- Stok defteri satırı (shared/stok_defteri.yaz ile aynı alanlar ve kısaltmalar)
CREATE OR REPLACE FUNCTION kayran_defter_yaz(p_sku text, p_depo text, p_once double precision,
                                             p_sonra double precision, p_tur text, p_aciklama text,
                                             p_basarili boolean, p_hata text, p_ortam jsonb)
RETURNS void LANGUAGE sql SECURITY INVOKER SET search_path = public, pg_temp AS $$
    INSERT INTO stok_hareketleri (sku, depo, onceki, sonraki, degisim, tur, aciklama, kaynak,
                                  kullanici, basarili, hata, yukleme_kodu)
    VALUES (left(coalesce(p_sku, ''), 80), left(coalesce(p_depo, ''), 60), p_once, p_sonra,
            p_sonra - p_once, left(coalesce(p_tur, ''), 30), left(coalesce(p_aciklama, ''), 300),
            left(coalesce(p_ortam ->> 'kaynak', ''), 120), left(coalesce(p_ortam ->> 'kullanici', ''), 40),
            p_basarili, left(coalesce(p_hata, ''), 500), nullif(p_ortam ->> 'yukleme_kodu', ''))
$$;

-- Tablodan türetilen hareket kalemi (silme / düzenleme). p_aday: {sku: [aday yazımlar]} — uygulama
-- kart_sku_coz ile hazırlar; listede olmayan SKU için girilen + BÜYÜK harf yazımı denenir.
CREATE OR REPLACE FUNCTION kayran_kalem(p_sku text, p_depo text, p_delta double precision, p_aday jsonb)
RETURNS jsonb LANGUAGE sql IMMUTABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    SELECT jsonb_build_object(
        'sku', p_sku,
        'adaylar', coalesce(p_aday -> p_sku,
                            CASE WHEN p_sku = upper(p_sku) THEN jsonb_build_array(p_sku)
                                 ELSE jsonb_build_array(p_sku, upper(p_sku)) END),
        'depo', kayran_depo_kanonik(coalesce(nullif(kayran_strip(p_depo), ''), 'MERKEZ DEPO')),
        'delta', p_delta, 'aciklama', '',
        'hata_aciklama', kayran_g(p_delta) || ' uygulanamadı')
$$;

-- Tabloya satır ekle (yalnız gönderilen kolonlar; p_opsiyonel'deki kolon tabloda yoksa atlanır —
-- uygulamanın 'kolon henüz yoksa eski biçimde yaz' davranışı). Eklenen satırları döner.
CREATE OR REPLACE FUNCTION kayran_ekle(p_tablo text, p_satirlar jsonb, p_opsiyonel text[])
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
DECLARE
    v_cols text;
    v_out  jsonb;
BEGIN
    IF p_satirlar IS NULL OR jsonb_array_length(p_satirlar) = 0 THEN RETURN '[]'::jsonb; END IF;
    SELECT string_agg(quote_ident(s.k), ', ' ORDER BY s.ilk) INTO v_cols
    FROM (SELECT k, min(o) AS ilk
          FROM jsonb_array_elements(p_satirlar) WITH ORDINALITY r(v, o), jsonb_object_keys(r.v) k
          GROUP BY k) s
    WHERE NOT (s.k = ANY (coalesce(p_opsiyonel, '{}'::text[])))
       OR EXISTS (SELECT 1 FROM pg_attribute a
                  WHERE a.attrelid = to_regclass('public.' || quote_ident(p_tablo))
                    AND a.attname = s.k AND a.attnum > 0 AND NOT a.attisdropped);
    IF v_cols IS NULL THEN RETURN '[]'::jsonb; END IF;
    EXECUTE format('WITH e AS (INSERT INTO %I (%s) SELECT %s FROM jsonb_populate_recordset(NULL::%I, $1) '
                   'RETURNING *) SELECT coalesce(jsonb_agg(to_jsonb(e)), ''[]''::jsonb) FROM e',
                   p_tablo, v_cols, v_cols, p_tablo)
        INTO v_out USING p_satirlar;
    RETURN v_out;
END $fn$;

-- ── Çekirdek: hareketleri kilitli uygula ───────────────────────────
-- p_hareketler: [{sku, adaylar[], depo (kanonik), delta, aciklama, hata_aciklama, kart_ac, kart_ad}]
-- p_ortam     : {kaynak, kullanici, yukleme_kodu, bugun}
-- Döner: {uygulanan, atlanan[]}  (atlanan = kartı olmadığı için uygulanmayan SKU'lar)
CREATE OR REPLACE FUNCTION kayran_stok_uygula_ic(p_hareketler jsonb, p_ortam jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
DECLARE
    h       jsonb;
    c       text;
    v_sku   text;
    v_depo  text;
    v_delta double precision;
    v_kart  text;
    v_dk    jsonb;
    v_once  double precision;
    v_sonra double precision;
    v_j     jsonb;
    n_uyg   integer := 0;
    v_atl   jsonb := '[]'::jsonb;
    v_tarih urunler.guncelleme_tarihi%TYPE;
BEGIN
    v_tarih := (jsonb_populate_record(NULL::urunler,
                jsonb_build_object('guncelleme_tarihi', p_ortam ->> 'bugun'))).guncelleme_tarihi;
    -- Kilitlenmeyi (deadlock) önlemek için bütün aday kartlar baştan, sabit sırayla kilitlenir.
    PERFORM 1 FROM urunler
     WHERE sku IN (SELECT jsonb_array_elements_text(x -> 'adaylar')
                   FROM jsonb_array_elements(coalesce(p_hareketler, '[]'::jsonb)) x)
     ORDER BY sku FOR UPDATE;

    FOR h IN SELECT value FROM jsonb_array_elements(coalesce(p_hareketler, '[]'::jsonb)) LOOP
        v_sku   := h ->> 'sku';
        v_depo  := h ->> 'depo';
        v_delta := (h ->> 'delta')::double precision;
        CONTINUE WHEN coalesce(v_sku, '') = '' OR v_delta IS NULL OR v_delta = 0;

        v_kart := NULL;
        v_dk := NULL;
        FOR c IN SELECT a.v FROM jsonb_array_elements_text(coalesce(h -> 'adaylar', jsonb_build_array(v_sku)))
                                 WITH ORDINALITY a(v, o) ORDER BY a.o LOOP
            SELECT u.sku, u.depo_kirilim INTO v_kart, v_dk FROM urunler u WHERE u.sku = c LIMIT 1 FOR UPDATE;
            EXIT WHEN v_kart IS NOT NULL;
        END LOOP;

        IF v_kart IS NULL THEN
            IF coalesce((h ->> 'kart_ac')::boolean, false) THEN
                INSERT INTO urunler (sku, urun_adi, depo_kirilim, bizim_stok)
                VALUES (v_sku, left(coalesce(h ->> 'kart_ad', ''), 200), '{}'::jsonb, 0);
                v_kart := v_sku;
                v_dk := '{}'::jsonb;
            ELSE
                PERFORM kayran_defter_yaz(v_sku, v_depo, 0, 0, 'hata',
                    coalesce(h ->> 'hata_aciklama', kayran_g(v_delta) || ' uygulanamadı'),
                    false, 'ürün kartı yok — stok işlenmedi', p_ortam);
                v_atl := v_atl || to_jsonb(v_sku);
                CONTINUE;
            END IF;
        END IF;

        IF v_dk IS NULL OR jsonb_typeof(v_dk) <> 'object' THEN v_dk := '{}'::jsonb; END IF;
        v_once  := kayran_sayi(v_dk -> v_depo);
        v_sonra := v_once + v_delta;
        IF abs(v_sonra) < 1e-9 THEN
            v_sonra := 0;
            v_j := '0'::jsonb;
        ELSE
            v_j := kayran_float_json(v_sonra);
        END IF;
        v_dk := v_dk || jsonb_build_object(v_depo, v_j);
        UPDATE urunler
           SET depo_kirilim = v_dk, bizim_stok = kayran_bizim_stok(v_dk), guncelleme_tarihi = v_tarih
         WHERE sku = v_kart;
        n_uyg := n_uyg + 1;
        PERFORM kayran_defter_yaz(v_kart, v_depo, v_once, v_sonra,
                                  CASE WHEN v_delta < 0 THEN 'cikis' ELSE 'giris' END,
                                  coalesce(h ->> 'aciklama', ''), true, '', p_ortam);
    END LOOP;
    RETURN jsonb_build_object('uygulanan', n_uyg, 'atlanan', v_atl);
END $fn$;

-- Silinen satırların stok karşılığı (bugünkü sırayla):
--   satislar → SKU başına toplam adet MERKEZ DEPO'ya geri (+)   [sil_satis / sil_siparis(ler)]
--   iadeler  → girdiği depodan geri düşülür (−)                  [sil_iade / iade partisi temizliği]
CREATE OR REPLACE FUNCTION kayran_silinen_hareketler(p_tablo text, p_silinen jsonb, p_aday jsonb)
RETURNS jsonb LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    WITH r AS (
        SELECT o,
               kayran_strip(coalesce(v ->> 'sku', '')) AS sku,
               CASE WHEN p_tablo = 'satislar' THEN round(kayran_sayi(v -> 'adet'))
                    ELSE round(kayran_sayi(v -> 'iade_adet')) END AS adet,
               CASE WHEN p_tablo = 'satislar' THEN 'MERKEZ DEPO'
                    ELSE coalesce(nullif(kayran_strip(coalesce(nullif(v ->> 'depo', ''), 'MERKEZ DEPO')), ''),
                                  'MERKEZ DEPO') END AS depo
        FROM jsonb_array_elements(coalesce(p_silinen, '[]'::jsonb)) WITH ORDINALITY t(v, o)
    ), g AS (
        SELECT depo, sku, sum(adet) AS adet, min(o) AS ilk,
               min(min(o)) OVER (PARTITION BY depo) AS depo_ilk
        FROM r WHERE sku <> '' AND adet <> 0
        GROUP BY depo, sku
    )
    SELECT coalesce(jsonb_agg(kayran_kalem(sku, depo,
                                           CASE WHEN p_tablo = 'satislar' THEN adet ELSE -adet END, p_aday)
                              ORDER BY depo_ilk, ilk), '[]'::jsonb)
    FROM g WHERE adet <> 0
$$;

-- ── Uygulamanın çağırdığı fonksiyonlar ──────────────────────────────

-- 1) Yalnız stok hareketi (stok_hareket_coklu): ithalat teslimi, teknik servis, Excel satış düşümü…
CREATE OR REPLACE FUNCTION stok_uygula(p_hareketler jsonb, p_ortam jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
BEGIN
    RETURN kayran_stok_uygula_ic(p_hareketler, p_ortam);
END $fn$;

-- 2) Satış / iade kaydı + stok, tek işlem. Sıra: (varsa) sil → ekle → stok (silinenlerin karşılığı,
--    sonra gönderilen hareketler).
--    p_sil: {"kolon": "id" | "siparis_no", "degerler": [...]}  (siparis_no yalnız satislar için)
CREATE OR REPLACE FUNCTION kayit_stok_islem(p_tablo text, p_sil jsonb, p_satirlar jsonb, p_hareketler jsonb,
                                            p_aday jsonb, p_ortam jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
DECLARE
    v_silinen jsonb := '[]'::jsonb;
    v_eklenen jsonb := '[]'::jsonb;
    v_hrk     jsonb := '[]'::jsonb;
    v_kolon   text;
    v_stok    jsonb;
BEGIN
    IF p_tablo NOT IN ('satislar', 'iadeler') THEN
        RAISE EXCEPTION 'izin verilmeyen tablo: %', p_tablo;
    END IF;
    IF p_sil IS NOT NULL AND jsonb_typeof(p_sil -> 'degerler') = 'array'
       AND jsonb_array_length(p_sil -> 'degerler') > 0 THEN
        v_kolon := p_sil ->> 'kolon';
        IF v_kolon = 'id' THEN
            EXECUTE format('WITH d AS (DELETE FROM %I WHERE id = ANY ($1) RETURNING *) '
                           'SELECT coalesce(jsonb_agg(to_jsonb(d) ORDER BY d.id), ''[]''::jsonb) FROM d', p_tablo)
                INTO v_silinen
                USING (SELECT array_agg(x::bigint) FROM jsonb_array_elements_text(p_sil -> 'degerler') x);
        ELSIF v_kolon = 'siparis_no' AND p_tablo = 'satislar' THEN
            WITH d AS (DELETE FROM satislar
                        WHERE siparis_no = ANY (SELECT jsonb_array_elements_text(p_sil -> 'degerler'))
                        RETURNING *)
            SELECT coalesce(jsonb_agg(to_jsonb(d) ORDER BY d.id), '[]'::jsonb) INTO v_silinen FROM d;
        ELSE
            RAISE EXCEPTION 'izin verilmeyen silme kolonu: %', v_kolon;
        END IF;
        v_hrk := kayran_silinen_hareketler(p_tablo, v_silinen, p_aday);
    END IF;
    v_eklenen := kayran_ekle(p_tablo, p_satirlar,
                             CASE WHEN p_tablo = 'iadeler'
                                  THEN ARRAY['donem_bas', 'donem_bit', 'depo', 'kaynak'] ELSE NULL END);
    v_stok := kayran_stok_uygula_ic(v_hrk || coalesce(p_hareketler, '[]'::jsonb), p_ortam);
    RETURN jsonb_build_object('silinen', v_silinen, 'eklenen', v_eklenen,
                              'uygulanan', v_stok -> 'uygulanan', 'atlanan', v_stok -> 'atlanan');
END $fn$;

-- 3) Satış düzenleme (guncelle_satis): adet/SKU değiştiyse eskisi MERKEZ DEPO'ya geri, yenisi düşülür.
--    p_yeni_sku / p_yeni_adet: alanlar'da varsa uygulamanın hesapladığı değer (strip / int(round)).
CREATE OR REPLACE FUNCTION satis_guncelle_stok(p_id bigint, p_alanlar jsonb, p_stoklu boolean,
                                               p_yeni_sku text, p_yeni_adet bigint, p_aday jsonb, p_ortam jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
DECLARE
    v_eski   jsonb;
    v_cols   text;
    e_sku    text;
    e_adet   bigint;
    y_sku    text;
    y_adet   bigint;
    v_hrk    jsonb := '[]'::jsonb;
    v_stok   jsonb := '{"uygulanan": 0, "atlanan": []}'::jsonb;
    v_n      integer;
BEGIN
    IF p_stoklu THEN
        SELECT to_jsonb(s) INTO v_eski FROM satislar s WHERE s.id = p_id FOR UPDATE;
    END IF;
    SELECT string_agg(quote_ident(k), ', ') INTO v_cols FROM jsonb_object_keys(p_alanlar) k;
    IF v_cols IS NULL THEN
        RAISE EXCEPTION 'güncellenecek alan yok';
    END IF;
    EXECUTE format('UPDATE satislar SET (%s) = (SELECT %s FROM jsonb_populate_record(NULL::satislar, $1)) '
                   'WHERE id = $2', v_cols, v_cols)
        USING p_alanlar, p_id;
    GET DIAGNOSTICS v_n = ROW_COUNT;
    IF v_eski IS NOT NULL THEN
        e_sku  := kayran_strip(coalesce(v_eski ->> 'sku', ''));
        e_adet := round(kayran_sayi(v_eski -> 'adet'));
        y_sku  := CASE WHEN p_alanlar ? 'sku' THEN coalesce(p_yeni_sku, '') ELSE e_sku END;
        y_adet := CASE WHEN p_alanlar ? 'adet' THEN coalesce(p_yeni_adet, 0) ELSE e_adet END;
        IF e_sku IS DISTINCT FROM y_sku OR e_adet IS DISTINCT FROM y_adet THEN
            IF e_sku <> '' AND e_adet <> 0 THEN
                v_hrk := v_hrk || kayran_kalem(e_sku, 'MERKEZ DEPO', e_adet, p_aday);
            END IF;
            IF y_sku <> '' AND y_adet <> 0 THEN
                v_hrk := v_hrk || kayran_kalem(y_sku, 'MERKEZ DEPO', -y_adet, p_aday);
            END IF;
            v_stok := kayran_stok_uygula_ic(v_hrk, p_ortam);
        END IF;
    END IF;
    RETURN jsonb_build_object('guncellenen', v_n, 'uygulanan', v_stok -> 'uygulanan',
                              'atlanan', v_stok -> 'atlanan');
END $fn$;

-- 4) Depolar arası sevk (depo_sevk). p_kaynak / p_hedef uygulamada depo_kanonik'ten geçmiş gelir.
--    İş kuralı hataları bugünkü mesajlarla, ERRCODE P0001 ile döner (uygulama başına '❌ ' ekler).
--    p_log: depo_sevk_log satırı (sku/urun_adi burada eklenir); yazılamazsa sevk yine geçerlidir.
CREATE OR REPLACE FUNCTION depo_sevk_islem(p_sku text, p_kaynak text, p_hedef text, p_adet bigint,
                                           p_aciklama text, p_log jsonb, p_ortam jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
DECLARE
    v_ham   jsonb;
    v_ad    text;
    v_yeni  jsonb := '{}'::jsonb;
    e       record;
    v_k     text;
    v_m     bigint;
    v_mev   bigint;
    d       text;
    a       double precision;
    b       double precision;
    v_tarih urunler.guncelleme_tarihi%TYPE;
BEGIN
    SELECT u.depo_kirilim, u.urun_adi INTO v_ham, v_ad FROM urunler u WHERE u.sku = p_sku LIMIT 1 FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'Ürün bulunamadı: ' || coalesce(p_sku, '');
    END IF;
    -- Python: dk = u.get("depo_kirilim") or {}
    IF v_ham IS NULL OR v_ham IN ('null'::jsonb, '[]'::jsonb, '""'::jsonb, '0'::jsonb, 'false'::jsonb) THEN
        v_ham := '{}'::jsonb;
    END IF;
    IF jsonb_typeof(v_ham) <> 'object' THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001',
            MESSAGE = 'Bu ürünün depo kırılımı yok (önce G5F stok yükleyin).';
    END IF;
    -- _kirilim_kanonik: adlar kanonik, aynı depolar toplanır, değerler int(float(m or 0)) (bozuk → 0)
    FOR e IN SELECT key, value FROM jsonb_each(v_ham) LOOP
        v_k := kayran_depo_kanonik(e.key);
        BEGIN
            v_m := trunc(kayran_sayi(e.value))::bigint;
        EXCEPTION WHEN others THEN
            v_m := 0;
        END;
        v_yeni := v_yeni || jsonb_build_object(v_k, coalesce((v_yeni ->> v_k)::bigint, 0) + v_m);
    END LOOP;
    -- _sevk_uygula
    IF coalesce(p_adet, 0) <= 0 THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'Adet 0''dan büyük olmalı.';
    END IF;
    IF kayran_strip(p_kaynak) = '' OR kayran_strip(p_hedef) = '' THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'Kaynak ve hedef depo seçilmeli.';
    END IF;
    IF p_kaynak = p_hedef THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'Kaynak ve hedef depo aynı olamaz.';
    END IF;
    v_mev := coalesce((v_yeni ->> p_kaynak)::bigint, 0);
    IF v_mev < p_adet THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001',
            MESSAGE = format('Yetersiz stok: ''%s'' deposunda %s adet var, %s taşınamaz.', p_kaynak, v_mev, p_adet);
    END IF;
    v_yeni := v_yeni || jsonb_build_object(p_kaynak, v_mev - p_adet);
    v_yeni := v_yeni || jsonb_build_object(p_hedef, coalesce((v_yeni ->> p_hedef)::bigint, 0) + p_adet);
    v_tarih := (jsonb_populate_record(NULL::urunler,
                jsonb_build_object('guncelleme_tarihi', p_ortam ->> 'bugun'))).guncelleme_tarihi;
    UPDATE urunler SET depo_kirilim = v_yeni, bizim_stok = kayran_bizim_stok(v_yeni), guncelleme_tarihi = v_tarih
     WHERE sku = p_sku;
    -- Defter: stok_defteri.yaz_fark (ham kırılım ↔ yeni kırılım, depo adına göre sıralı)
    FOR d IN SELECT k FROM (SELECT jsonb_object_keys(v_ham) AS k UNION SELECT jsonb_object_keys(v_yeni)) s
             ORDER BY k COLLATE "C" LOOP
        BEGIN
            a := kayran_sayi(v_ham -> d);
        EXCEPTION WHEN others THEN
            a := 0;
        END;
        b := kayran_sayi(v_yeni -> d);
        IF abs(a - b) > 1e-9 THEN
            PERFORM kayran_defter_yaz(p_sku, d, a, b, 'sevk', p_aciklama, true, '', p_ortam);
        END IF;
    END LOOP;
    -- Sevk geçmişi (yazılamazsa sevk yine geçerli — bugünkü davranış)
    IF p_log IS NOT NULL THEN
        BEGIN
            PERFORM kayran_ekle('depo_sevk_log',
                                jsonb_build_array(jsonb_build_object('sku', p_sku, 'urun_adi', v_ad) || p_log),
                                ARRAY['sevk_tarihi', 'belge_no']);
        EXCEPTION WHEN others THEN
            NULL;
        END;
    END IF;
    RETURN jsonb_build_object('sku', p_sku, 'depo_kirilim', v_yeni);
END $fn$;

-- ── Yetki: yalnız uygulamanın yetkili anahtarı (service_role) ──────
DO $do$
DECLARE
    f text;
BEGIN
    FOREACH f IN ARRAY ARRAY[
        'kayran_strip(text)', 'kayran_depo_kanonik(text)', 'kayran_sayi(jsonb)', 'kayran_tam(jsonb)',
        'kayran_bizim_stok(jsonb)', 'kayran_float_json(double precision)', 'kayran_g(double precision)',
        'kayran_defter_yaz(text,text,double precision,double precision,text,text,boolean,text,jsonb)',
        'kayran_kalem(text,text,double precision,jsonb)', 'kayran_ekle(text,jsonb,text[])',
        'kayran_stok_uygula_ic(jsonb,jsonb)', 'kayran_silinen_hareketler(text,jsonb,jsonb)',
        'stok_uygula(jsonb,jsonb)', 'kayit_stok_islem(text,jsonb,jsonb,jsonb,jsonb,jsonb)',
        'satis_guncelle_stok(bigint,jsonb,boolean,text,bigint,jsonb,jsonb)',
        'depo_sevk_islem(text,text,text,bigint,text,jsonb,jsonb)'
    ] LOOP
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', f);
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
            EXECUTE format('REVOKE ALL ON FUNCTION %s FROM anon', f);
        END IF;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
            EXECUTE format('REVOKE ALL ON FUNCTION %s FROM authenticated', f);
        END IF;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
            EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role', f);
        END IF;
    END LOOP;
END $do$;

-- PostgREST yeni fonksiyonları görsün
NOTIFY pgrst, 'reload schema';

-- ── Kontrol ──
-- SELECT kayran_depo_kanonik(' merkez '), kayran_bizim_stok('{"MERKEZ": 3, "Happy Life": 2, "ASEL": 9}');
--   → MERKEZ DEPO | 5

-- GERİ ALMA (gerekirse ayrı çalıştırın; uygulama kendiliğinden bugünkü yola döner):
-- DROP FUNCTION IF EXISTS depo_sevk_islem(text,text,text,bigint,text,jsonb,jsonb);
-- DROP FUNCTION IF EXISTS satis_guncelle_stok(bigint,jsonb,boolean,text,bigint,jsonb,jsonb);
-- DROP FUNCTION IF EXISTS kayit_stok_islem(text,jsonb,jsonb,jsonb,jsonb,jsonb);
-- DROP FUNCTION IF EXISTS stok_uygula(jsonb,jsonb);
-- DROP FUNCTION IF EXISTS kayran_silinen_hareketler(text,jsonb,jsonb);
-- DROP FUNCTION IF EXISTS kayran_stok_uygula_ic(jsonb,jsonb);
-- DROP FUNCTION IF EXISTS kayran_ekle(text,jsonb,text[]);
-- DROP FUNCTION IF EXISTS kayran_kalem(text,text,double precision,jsonb);
-- DROP FUNCTION IF EXISTS kayran_defter_yaz(text,text,double precision,double precision,text,text,boolean,text,jsonb);
-- DROP FUNCTION IF EXISTS kayran_g(double precision);
-- DROP FUNCTION IF EXISTS kayran_float_json(double precision);
-- DROP FUNCTION IF EXISTS kayran_bizim_stok(jsonb);
-- DROP FUNCTION IF EXISTS kayran_tam(jsonb);
-- DROP FUNCTION IF EXISTS kayran_sayi(jsonb);
-- DROP FUNCTION IF EXISTS kayran_depo_kanonik(text);
-- DROP FUNCTION IF EXISTS kayran_strip(text);
-- NOTIFY pgrst, 'reload schema';
