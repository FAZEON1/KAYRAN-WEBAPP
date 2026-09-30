-- Kullanıcı tercihleri (şimdilik: görünüm teması). Tekrar çalıştırılabilir.
-- Tablo yokken de program çalışır: tercih okunamazsa koyu tema, yazılamazsa
-- yalnız oturumda tutulur.
CREATE TABLE IF NOT EXISTS kullanici_tercih (
    kullanici   text PRIMARY KEY,
    tema        text NOT NULL DEFAULT 'koyu' CHECK (tema IN ('koyu', 'acik')),
    guncelleme  timestamptz NOT NULL DEFAULT now()
);
