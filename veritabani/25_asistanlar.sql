-- 25 · Asistanlar: Telegram soru-cevap, pazar araştırmacısı, gümrük danışmanı (Ekim 2026)
--
-- asistan_rapor     : zamanlanmış asistanların raporları (şimdilik pazar araştırmacısı). Sabah brifingi
--                     yeni raporun özetini Telegram'a ekler, sonra telegram_gonderildi = true yapar.
-- gumruk_sorgulari  : İthalat › Gümrük danışmanı. Kullanıcı ürünü yazar (durum 'bekliyor'); claude.ai'deki
--                     gümrük görevi araştırıp sonucu yazar ('tamam'). Sonuç ÖNERİDİR, müşavirle teyit edilir.
-- sistem_ayarlari   : 'telegram_webhook_gizli' — Telegram'ın her mesajla gönderdiği gizli değer. Supabase'deki
--                     telegram-webhook fonksiyonu bununla gerçek Telegram isteğini ayırır. Burada üretilir;
--                     kimsenin elle yazması gerekmez. 'telegram_kullanicilar' ekrandan dolar.
-- Başka tabloya dokunmaz.
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır.

CREATE TABLE IF NOT EXISTS asistan_rapor (
    id                   bigserial PRIMARY KEY,
    zaman                timestamptz NOT NULL DEFAULT now(),
    asistan              text NOT NULL,          -- pazar
    baslik               text NOT NULL,
    ozet                 text,                   -- Telegram'a giden 3-5 satır
    icerik               text,                   -- tam rapor (markdown)
    telegram_gonderildi  boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS asistan_rapor_zaman_idx ON asistan_rapor (zaman DESC);

CREATE TABLE IF NOT EXISTS gumruk_sorgulari (
    id            bigserial PRIMARY KEY,
    zaman         timestamptz NOT NULL DEFAULT now(),
    kullanici     text,
    urun          text NOT NULL,                 -- ürün adı / model / kısa tarif
    mense         text,                          -- menşe ülke
    birim_fiyat   numeric,                       -- FOB birim fiyat
    para          text NOT NULL DEFAULT 'USD',
    adet          numeric,
    navlun        numeric,                       -- toplam navlun (varsa)
    sigorta       numeric,                       -- toplam sigorta (varsa)
    notu          text,
    durum         text NOT NULL DEFAULT 'bekliyor',   -- bekliyor | calisiyor | tamam | hata
    sonuc         jsonb,                         -- {gtip, gtip_aciklama, oranlar{...}, belgeler[], uyarilar[], kaynaklar[]}
    ozet          text,
    guncelleme    timestamptz
);
CREATE INDEX IF NOT EXISTS gumruk_sorgulari_durum_idx ON gumruk_sorgulari (durum, zaman);

-- İzin kuralı YOK (15_dis_erisim_kapat.sql ile aynı): uygulama, görevler ve fonksiyon service_role ile bağlanır.
ALTER TABLE asistan_rapor ENABLE ROW LEVEL SECURITY;
ALTER TABLE gumruk_sorgulari ENABLE ROW LEVEL SECURITY;

INSERT INTO sistem_ayarlari (anahtar, deger, guncelleme_tarihi)
VALUES ('telegram_webhook_gizli', replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', ''), now())
ON CONFLICT (anahtar) DO NOTHING;

-- GERİ ALMA:
--   DROP TABLE IF EXISTS asistan_rapor;
--   DROP TABLE IF EXISTS gumruk_sorgulari;
--   DELETE FROM sistem_ayarlari WHERE anahtar IN ('telegram_webhook_gizli', 'telegram_kullanicilar');
