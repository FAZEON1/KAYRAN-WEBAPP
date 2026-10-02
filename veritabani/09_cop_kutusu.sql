-- 09 · Çöp kutusu (Ekim 2026)
--
-- Silinen kayıtlar 30 gün burada saklanır ve uygulamadan tek tıkla geri alınır
-- (kenar çubuğu › Çöp kutusu). Merkezi veritabanı katmanı her silmede silinen
-- satırları buraya yazar; Excel yeniden yüklemeleri ve birleştirmeler yazılmaz.
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır.
-- Çalıştırılmadan önce de program çalışır: silmeler eskisi gibi yapılır, yalnız
-- çöp kutusuna kopyalanmaz.

CREATE TABLE IF NOT EXISTS cop_kutusu (
    id               bigserial PRIMARY KEY,
    grup             text        NOT NULL,              -- aynı silme çağrısının parçaları
    tablo            text        NOT NULL,              -- silindiği tablo
    modul            text,
    silen            text,                              -- kullanıcı adı
    zaman            timestamptz NOT NULL DEFAULT now(),
    adet             integer     NOT NULL DEFAULT 0,
    satirlar         jsonb       NOT NULL,              -- silinen satırlar, tüm sütunlarıyla
    geri_alindi      boolean     NOT NULL DEFAULT false,
    geri_alan        text,
    geri_alma_zamani timestamptz
);

CREATE INDEX IF NOT EXISTS cop_kutusu_zaman_idx ON cop_kutusu (zaman DESC);
CREATE INDEX IF NOT EXISTS cop_kutusu_silen_idx ON cop_kutusu (silen);
