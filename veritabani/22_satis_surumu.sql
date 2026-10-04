-- 22 · Satış ve iade sayacı (Ekim 2026, hızlandırma)
--
-- 11_veri_surumu.sql'deki sayaç sistemine satislar ve iadeler eklenir. Bu tablolarda her ekleme /
-- değişiklik / silme / truncate, tablonun sayacını 1 artırır (işlem başına bir kez — satır başına
-- değil). Uygulama (shared/veri_surumu.py, satış grubu) sayaç değişince yalnız satış önbelleklerini
-- temizler; böylece satış verisi 2 dk'da bir değil, YALNIZ değiştiğinde yeniden okunur.
-- Mevcut veriye dokunmaz; yalnız tetikleyici ve sayaç satırı ekler.
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır.
-- Çalıştırılmadan önce de program çalışır: satış önbellekleri eskisi gibi 2 dk'da bir tazelenir.
-- Ön koşul: 11_veri_surumu.sql (veri_surumu tablosu ve veri_surumu_artir fonksiyonu).

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['satislar', 'iadeler'] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS veri_surumu_trg ON %I', t);
        EXECUTE format('CREATE TRIGGER veri_surumu_trg AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE '
                       'ON %I FOR EACH STATEMENT EXECUTE FUNCTION veri_surumu_artir()', t);
        INSERT INTO veri_surumu (tablo) VALUES (t) ON CONFLICT (tablo) DO NOTHING;
    END LOOP;
END $$;

-- GERİ ALMA (gerekirse ayrı çalıştırın; uygulama eski 2 dk davranışına döner):
-- DROP TRIGGER IF EXISTS veri_surumu_trg ON satislar;
-- DROP TRIGGER IF EXISTS veri_surumu_trg ON iadeler;
-- DELETE FROM veri_surumu WHERE tablo IN ('satislar', 'iadeler');
