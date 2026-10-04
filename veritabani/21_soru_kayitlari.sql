-- 21 · Soru kutusu kayıtları (Ekim 2026)
--
-- Soru sor sayfasında (ve Ctrl+K paletinden) sorulan sorular. Amaç: programın ANLAYAMADIĞI soruları
-- görüp kalıpları genişletmek. Yalnız soru metni, anlaşılıp anlaşılmadığı ve konu yazılır; cevap
-- (rakam) kaydedilmez. Başka tabloya dokunmaz.
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır. Kurulmadan önce
-- soru kutusu yine çalışır; yalnız kayıt tutulmaz.

CREATE TABLE IF NOT EXISTS soru_kayitlari (
    id          bigserial PRIMARY KEY,
    kullanici   text,
    metin       text NOT NULL,
    anlasildi   boolean NOT NULL DEFAULT false,
    konu        text,
    olusturma   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS soru_kayitlari_olusturma_idx ON soru_kayitlari (olusturma DESC);

-- İzin kuralı YOK (15_dis_erisim_kapat.sql ile aynı): uygulama service_role ile bağlanır,
-- RLS'ye takılmaz; herkese açık anahtar bu tabloya erişemez.
ALTER TABLE soru_kayitlari ENABLE ROW LEVEL SECURITY;

-- GERİ ALMA:
--   DROP TABLE IF EXISTS soru_kayitlari;
