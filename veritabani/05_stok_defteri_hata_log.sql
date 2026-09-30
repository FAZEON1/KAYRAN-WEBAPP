-- ════════════════════════════════════════════════════════════════════
-- KAYRAN — Stok hareket defteri + hata kaydı (B5 / B6)
--
-- Supabase → SQL Editor → tamamını yapıştır → Run.
-- Güvenli, tekrar çalıştırılabilir. Mevcut hiçbir tabloya dokunmaz.
--
-- Kod bu tablolar YOKKEN de çalışır (kayıt sessizce atlanır); tablolar
-- oluşturulduğu andan itibaren kayıt tutmaya başlar.
-- ════════════════════════════════════════════════════════════════════

-- ── Stok hareket defteri ────────────────────────────────────────────
-- Her stok değişimi bir satır: satış, iade, teknik servis, sevk, Excel
-- aktarımı, sıfırlama. BAŞARISIZ denemeler de (basarili=false + hata).
CREATE TABLE IF NOT EXISTS stok_hareketleri (
    id         bigserial PRIMARY KEY,
    zaman      timestamptz NOT NULL DEFAULT now(),
    sku        text        NOT NULL,
    depo       text,
    onceki     numeric,
    sonraki    numeric,
    degisim    numeric,
    tur        text,        -- cikis | giris | sevk | aktarim | sifirlama | hata
    aciklama   text,
    kaynak     text,        -- işlemi başlatan kod: 'satis/database.py:_stok_uygula_depolu'
    kullanici  text,
    basarili   boolean     NOT NULL DEFAULT true,
    hata       text
);

CREATE INDEX IF NOT EXISTS stok_hareketleri_sku_zaman_idx
    ON stok_hareketleri (sku, zaman DESC);
CREATE INDEX IF NOT EXISTS stok_hareketleri_zaman_idx
    ON stok_hareketleri (zaman DESC);
CREATE INDEX IF NOT EXISTS stok_hareketleri_basarisiz_idx
    ON stok_hareketleri (zaman DESC) WHERE basarili = false;

COMMENT ON TABLE stok_hareketleri IS
    'Stok hareket defteri — her depo_kirilim değişimi ve başarısız deneme';


-- ── Hata kaydı ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hata_kayitlari (
    id         bigserial PRIMARY KEY,
    zaman      timestamptz NOT NULL DEFAULT now(),
    yer        text,        -- 'kayranpm.stok_hareket_coklu' gibi
    tur        text,        -- istisna sınıfı
    mesaj      text,
    ayrinti    text,        -- traceback
    kullanici  text,
    kritik     boolean     NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS hata_kayitlari_zaman_idx ON hata_kayitlari (zaman DESC);

COMMENT ON TABLE hata_kayitlari IS
    'Sessizce yutulan hataların kaydı — para/stok yollarındakiler kritik';


-- ── Kontrol ──
SELECT table_name FROM information_schema.tables
WHERE table_name IN ('stok_hareketleri', 'hata_kayitlari');
