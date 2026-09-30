-- ════════════════════════════════════════════════════════════════════
-- KAYRAN — Kullanıcı yetkileri tablosu (A4)
--
-- Supabase → SQL Editor → tamamını yapıştır → Run.
-- Güvenli, tekrar çalıştırılabilir. Mevcut hiçbir tabloya dokunmaz.
--
-- Başlangıç verisi, koddaki GÜNCEL sabit listelerden otomatik üretildi —
-- herkesin yetkisi bugünküyle birebir aynı başlar. Sonrası 👥 Kullanıcı
-- Yönetimi ekranından yönetilir.
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS kullanici_yetkileri (
    kullanici    text PRIMARY KEY,
    moduller     text[]      NOT NULL DEFAULT '{}',
    ozel         text[]      NOT NULL DEFAULT '{}',
    salt_okur    boolean     NOT NULL DEFAULT false,
    aktif        boolean     NOT NULL DEFAULT true,
    guncelleyen  text,
    guncelleme   timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  kullanici_yetkileri IS 'Kullanıcı modül ve özel yetkileri — 👥 Kullanıcı Yönetimi ekranından yönetilir';
COMMENT ON COLUMN kullanici_yetkileri.moduller  IS 'kayranacc, kayranpm, depo, ithalat, teknikservis, satis, hesap_makinesi';
COMMENT ON COLUMN kullanici_yetkileri.ozel      IS 'yonetim, patron_panel, toplam_aktifler, talep_yonetici, kullanici_yonetimi';
COMMENT ON COLUMN kullanici_yetkileri.salt_okur IS 'true ise tüm modülleri görür, hiçbir veriyi değiştiremez';
COMMENT ON COLUMN kullanici_yetkileri.aktif     IS 'false ise giriş yapamaz (Secrets''ta tanımlı olsa bile)';

-- Başlangıç verisi (16 kullanıcı). ON CONFLICT DO NOTHING:
-- tekrar çalıştırılırsa ekrandan yapılmış değişiklikleri EZMEZ.
INSERT INTO kullanici_yetkileri (kullanici, moduller, ozel, salt_okur, aktif) VALUES
  ('ahmet', '{}'::text[], ARRAY['yonetim']::text[], true, true),
  ('berkay', ARRAY['depo','teknikservis']::text[], '{}'::text[], false, true),
  ('caglar', ARRAY['depo','ithalat','kayranacc','kayranpm','satis']::text[], ARRAY['yonetim']::text[], false, true),
  ('cem', ARRAY['ithalat','kayranacc','teknikservis']::text[], ARRAY['toplam_aktifler','yonetim']::text[], false, true),
  ('derman', ARRAY['kayranacc']::text[], ARRAY['toplam_aktifler']::text[], false, true),
  ('derya', ARRAY['depo','ithalat','kayranpm','satis','teknikservis']::text[], '{}'::text[], false, true),
  ('gokhan', ARRAY['depo','ithalat','kayranpm','satis','teknikservis']::text[], '{}'::text[], false, true),
  ('ibrahim', ARRAY['depo','hesap_makinesi','ithalat','kayranacc','kayranpm','satis','teknikservis']::text[], ARRAY['kullanici_yonetimi','patron_panel','talep_yonetici','toplam_aktifler','yonetim']::text[], false, true),
  ('kemal', ARRAY['ithalat']::text[], '{}'::text[], false, true),
  ('korkut', ARRAY['depo','ithalat','kayranacc','kayranpm','satis','teknikservis']::text[], ARRAY['yonetim']::text[], false, true),
  ('pamuk', ARRAY['ithalat','kayranacc','teknikservis']::text[], ARRAY['toplam_aktifler']::text[], false, true),
  ('samet', ARRAY['depo','teknikservis']::text[], '{}'::text[], false, true),
  ('selcuk', ARRAY['depo']::text[], '{}'::text[], false, true),
  ('serdar', ARRAY['depo','ithalat','kayranacc','teknikservis']::text[], ARRAY['toplam_aktifler']::text[], false, true),
  ('serkan', ARRAY['depo','ithalat','kayranacc','kayranpm','satis','teknikservis']::text[], ARRAY['yonetim']::text[], false, true),
  ('yilmaz', ARRAY['kayranacc']::text[], ARRAY['toplam_aktifler']::text[], false, true)
ON CONFLICT (kullanici) DO NOTHING;

-- ── Kontrol ──
SELECT kullanici, array_length(moduller,1) AS modul_sayisi, ozel, salt_okur, aktif
FROM kullanici_yetkileri ORDER BY kullanici;
