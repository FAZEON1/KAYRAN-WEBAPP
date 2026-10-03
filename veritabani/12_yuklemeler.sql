-- 12 · Yükleme geçmişi ve geri alma (Ekim 2026)
--
-- Her Excel yüklemesi bir satır: kim, ne zaman, hangi dosya, kaç satır. Geri alınabilir
-- yüklemelerde ayrıca: eklenen satırların kimlikleri + üzerine yazılan / silinen eski
-- satırların TAM hâli (degisiklik). Geri alma tek veritabanı işleminde yapılır
-- (yukleme_geri_al): eklenenler silinir, eskiler özgün kimlikleriyle geri yazılır —
-- ya hepsi olur ya hiçbiri. Kural ve ekran: shared/yukleme_gecmisi.py.
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır.
-- Çalıştırılmadan önce de program çalışır: yüklemeler eskisi gibi yapılır, yalnız
-- geçmişe yazılmaz ve geri alınamaz.

CREATE TABLE IF NOT EXISTS yuklemeler (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tur              text        NOT NULL,              -- yükleme türü (shared.yukleme_gecmisi.TURLER)
    anahtarlar       jsonb       NOT NULL DEFAULT '[]', -- etkilediği dilimler ('VATAN|2026-09-27' gibi)
    dosya_adi        text,
    kullanici        text,
    zaman            timestamptz NOT NULL DEFAULT now(),
    satir_sayisi     integer     NOT NULL DEFAULT 0,
    geri_alinabilir  boolean     NOT NULL DEFAULT false,
    degisiklik       jsonb       NOT NULL DEFAULT '{}', -- {tablo: {"eklenen": [id], "onceki": [satır]}}
    durum            text        NOT NULL DEFAULT 'aktif',   -- aktif | geri_alindi
    geri_alan        text,
    geri_alma_zamani timestamptz,
    silinen          jsonb                              -- geri almada silinen satırların tam hâli
);
CREATE INDEX IF NOT EXISTS yuklemeler_zaman_idx ON yuklemeler (zaman DESC);
CREATE INDEX IF NOT EXISTS yuklemeler_tur_idx ON yuklemeler (tur, durum);
-- RLS açık, izin kuralı YOK: uygulama service_role anahtarıyla bağlanır (RLS'ye takılmaz);
-- herkese açık (anon) anahtarla bu tablo okunamaz / yazılamaz.
ALTER TABLE yuklemeler ENABLE ROW LEVEL SECURITY;

-- Geri alma: TEK İŞLEM. Yalnız izin verilen tablolarda çalışır; kayıt 'aktif' değilse durur.
-- Döner: {"silinen": n, "geri_yazilan": m}
CREATE OR REPLACE FUNCTION yukleme_geri_al(p_id bigint, p_kullanici text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $fn$
DECLARE
    k        record;
    t        text;
    d        jsonb;
    n_sil    integer := 0;
    n_yaz    integer := 0;
    n        integer;
    v_silinen jsonb := '{}'::jsonb;
    satirlar jsonb;
BEGIN
    SELECT * INTO k FROM yuklemeler WHERE id = p_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'yükleme bulunamadı: %', p_id; END IF;
    IF k.durum <> 'aktif' THEN RAISE EXCEPTION 'yükleme zaten geri alınmış'; END IF;
    IF NOT k.geri_alinabilir THEN RAISE EXCEPTION 'bu yükleme geri alınamaz'; END IF;
    FOR t, d IN SELECT * FROM jsonb_each(k.degisiklik) LOOP
        IF t NOT IN ('firma_stok', 'happylife_stok', 'cekler', 'ref_butce') THEN
            RAISE EXCEPTION 'izin verilmeyen tablo: %', t;
        END IF;
        EXECUTE format('WITH s AS (DELETE FROM %I WHERE id IN (SELECT (x)::bigint FROM jsonb_array_elements_text($1) x) RETURNING *) '
                       'SELECT coalesce(jsonb_agg(to_jsonb(s)), ''[]''::jsonb) FROM s', t)
            INTO satirlar USING coalesce(d->'eklenen', '[]'::jsonb);
        n_sil := n_sil + jsonb_array_length(satirlar);
        v_silinen := v_silinen || jsonb_build_object(t, satirlar);
        IF jsonb_array_length(coalesce(d->'onceki', '[]'::jsonb)) > 0 THEN
            EXECUTE format('INSERT INTO %I OVERRIDING SYSTEM VALUE SELECT * FROM jsonb_populate_recordset(NULL::%I, $1)', t, t)
                USING d->'onceki';
            GET DIAGNOSTICS n = ROW_COUNT;
            n_yaz := n_yaz + n;
        END IF;
    END LOOP;
    UPDATE yuklemeler SET durum = 'geri_alindi', geri_alan = p_kullanici, geri_alma_zamani = now(),
           silinen = v_silinen WHERE id = p_id;
    RETURN jsonb_build_object('silinen', n_sil, 'geri_yazilan', n_yaz);
END $fn$;

-- Geri alma fonksiyonu yalnız uygulamanın yetkili anahtarıyla (service_role) çağrılabilir;
-- Supabase varsayılanı anon / authenticated rollerine de açar, kapatılır.
REVOKE ALL ON FUNCTION yukleme_geri_al(bigint, text) FROM PUBLIC;
DO $do$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION yukleme_geri_al(bigint, text) FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON FUNCTION yukleme_geri_al(bigint, text) FROM authenticated;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT EXECUTE ON FUNCTION yukleme_geri_al(bigint, text) TO service_role;
    END IF;
END $do$;

-- GERİ ALMA (gerekirse ayrı çalıştırın):
-- DROP FUNCTION IF EXISTS yukleme_geri_al(bigint, text);
-- DROP TABLE IF EXISTS yuklemeler;
