-- 19 · Talepten Claude'a: onaylı geliştirme akışı (Ekim 2026)
--
-- Talep Merkezi'nde yönetici (İbrahim) bir talebi "Claude'a gönder" ile onaylar; claude.ai'deki
-- zamanlanmış görev (7 gün 24 saat, saat başı) onaylı talebi alır, kodlar, PR açar. PR'ı
-- birleştirmek yine kullanıcıdadır. Ayrıntı: otonom/claude_talep_gorevi.md, shared/claude_talep.py.
--
--   claude_durum        onaylandi → calisiyor → pr_hazir → yayinda   (ya da soru / hata / kapandi)
--   claude_onay_notu    onaylayanın notu ("şöyle olsun", sorulara cevap)
--   claude_onaylayan    onaylayan kullanıcı
--   claude_onay_tarihi  onay anı
--   claude_not          Claude'un notu (soru, plan, hata sebebi)
--   claude_pr_url       açılan PR
--   claude_guncelleme   son durum değişikliği
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır. Kurulmadan önce
-- "Claude'a gönder" düğmesi uyarı verir; Talep Merkezi'nin geri kalanı bugünkü gibi çalışır.

ALTER TABLE talepler ADD COLUMN IF NOT EXISTS claude_durum text;
ALTER TABLE talepler ADD COLUMN IF NOT EXISTS claude_onay_notu text;
ALTER TABLE talepler ADD COLUMN IF NOT EXISTS claude_onaylayan text;
ALTER TABLE talepler ADD COLUMN IF NOT EXISTS claude_onay_tarihi timestamptz;
ALTER TABLE talepler ADD COLUMN IF NOT EXISTS claude_not text;
ALTER TABLE talepler ADD COLUMN IF NOT EXISTS claude_pr_url text;
ALTER TABLE talepler ADD COLUMN IF NOT EXISTS claude_guncelleme timestamptz;

-- GERİ ALMA:
--   ALTER TABLE talepler DROP COLUMN IF EXISTS claude_durum, DROP COLUMN IF EXISTS claude_onay_notu,
--     DROP COLUMN IF EXISTS claude_onaylayan, DROP COLUMN IF EXISTS claude_onay_tarihi,
--     DROP COLUMN IF EXISTS claude_not, DROP COLUMN IF EXISTS claude_pr_url,
--     DROP COLUMN IF EXISTS claude_guncelleme;
