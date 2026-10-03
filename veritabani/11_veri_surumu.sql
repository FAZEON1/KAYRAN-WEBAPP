-- 11 · Veri sürümü (Ekim 2026)
--
-- Ağır ekran önbelleklerinin (Tüm Ürünler, Genel bakış, paçal) VERİ DEĞİŞİNCE tazelenmesi için.
-- İzlenen tablolarda her ekleme / değişiklik / silme / truncate, o tablonun sayacını 1 artırır
-- (işlem başına bir kez — satır başına değil). Uygulama (shared/veri_surumu.py) sayaçları en
-- fazla 15 sn'de bir okur; değiştiyse ilgili önbellekleri temizler. Değişiklik nereden gelirse
-- gelsin (uygulama, Excel yükleme, gece işi, elle düzeltme) en geç 15 sn'de ekrana yansır.
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır.
-- Çalıştırılmadan önce de program çalışır: önbellekler eskisi gibi 5 dk'da bir tazelenir.
-- Geri almak: dosyanın sonundaki "GERİ ALMA" bloğu.

CREATE TABLE IF NOT EXISTS veri_surumu (
    tablo    text PRIMARY KEY,
    surum    bigint      NOT NULL DEFAULT 0,
    degisti  timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE veri_surumu ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS allow_all_veri_surumu ON veri_surumu;
-- İzin kuralı YOK (Ekim 2026, 15_dis_erisim_kapat.sql): uygulama service_role ile bağlanır,
-- RLS'ye takılmaz; herkese açık anahtar bu tabloya erişemez.

CREATE OR REPLACE FUNCTION veri_surumu_artir() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    INSERT INTO veri_surumu (tablo, surum, degisti) VALUES (TG_TABLE_NAME, 1, now())
    ON CONFLICT (tablo) DO UPDATE SET surum = veri_surumu.surum + 1, degisti = now();
    RETURN NULL;
END $$;

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['urunler', 'firma_stok', 'stok_yas', 'yoldaki_urunler',
                             'ithalat_dosyalari', 'ithalat_kalemleri', 'pm_ayarlar'] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS veri_surumu_trg ON %I', t);
        EXECUTE format('CREATE TRIGGER veri_surumu_trg AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE '
                       'ON %I FOR EACH STATEMENT EXECUTE FUNCTION veri_surumu_artir()', t);
        INSERT INTO veri_surumu (tablo) VALUES (t) ON CONFLICT (tablo) DO NOTHING;
    END LOOP;
END $$;

-- GERİ ALMA (gerekirse ayrı çalıştırın):
-- DO $$ DECLARE t text; BEGIN
--   FOREACH t IN ARRAY ARRAY['urunler','firma_stok','stok_yas','yoldaki_urunler',
--                            'ithalat_dosyalari','ithalat_kalemleri','pm_ayarlar'] LOOP
--     EXECUTE format('DROP TRIGGER IF EXISTS veri_surumu_trg ON %I', t);
--   END LOOP; END $$;
-- DROP FUNCTION IF EXISTS veri_surumu_artir();
-- DROP TABLE IF EXISTS veri_surumu;
