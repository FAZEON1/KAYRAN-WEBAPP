-- ════════════════════════════════════════════════════════════════════
-- BAYİ PORTALI — Faz 1 · Veritabanı Şeması (Supabase / Postgres)
-- ════════════════════════════════════════════════════════════════════
-- Bu dosyayı Supabase > SQL Editor'de bir kez çalıştırın.
--
-- İçerik:
--   1) bayi_kullanicilar   — bayi giriş hesapları (cari'ye bağlı)
--   2) bayi_giris_denemeleri — bayi tarafı brute-force kilidi
--
-- NOT: Cari bakiye verisi AYRI bir tabloda tutulmaz. Kaynak, "Toplam Aktifler"
--      sayfasına yüklenen Cari Alacaklar Excel'idir; satır detayı mevcut
--      `aktif_excel_verileri` tablosuna `dosya_tipi='cari_detay'` anahtarıyla
--      yazılır (bkz. kayranacc/main.py yükleme akışı). Portal onu okur.
-- ════════════════════════════════════════════════════════════════════


-- ── 1) Bayi kullanıcıları ───────────────────────────────────────────
-- Bir bayi = bir cari. cari_kod bakiye eşleşmesi için (cari_detay.kod),
-- cari_unvan servis kayıtları eşleşmesi için (ts_kayitlar.firma_bilgisi).
CREATE TABLE IF NOT EXISTS bayi_kullanicilar (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kullanici_adi     TEXT        NOT NULL UNIQUE,   -- giriş adı (küçük harf, benzersiz)
    sifre_hash        TEXT        NOT NULL,          -- pbkdf2:sha256:... (shared.auth formatı)
    cari_kod          TEXT,                          -- muhasebe cari kodu (bakiye eşleşmesi)
    cari_unvan        TEXT        NOT NULL,          -- tam cari unvan (servis eşleşmesi)
    ad_soyad          TEXT,                          -- yetkili kişi
    email             TEXT,
    telefon           TEXT,
    aktif             BOOLEAN     NOT NULL DEFAULT TRUE,
    olusturma_tarihi  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    son_giris         TIMESTAMPTZ,
    notlar            TEXT
);

CREATE INDEX IF NOT EXISTS ix_bayi_kullanicilar_cari_kod
    ON bayi_kullanicilar (cari_kod);
CREATE INDEX IF NOT EXISTS ix_bayi_kullanicilar_aktif
    ON bayi_kullanicilar (aktif);


-- ── 2) Bayi giriş denemeleri (brute-force kilidi) ───────────────────
-- shared.auth'taki giris_denemeleri ile aynı mantık; personel tablosundan
-- ayrı tutulur ki bayi ve personel kilitleri karışmasın.
CREATE TABLE IF NOT EXISTS bayi_giris_denemeleri (
    kullanici_adi   TEXT PRIMARY KEY,
    basarisiz_sayi  INTEGER     NOT NULL DEFAULT 0,
    son_deneme      TIMESTAMPTZ,
    kilit_bitis     TIMESTAMPTZ
);
