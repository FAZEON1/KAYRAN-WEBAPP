-- 24 · Şirket belgeleri (Ekim 2026)
--
-- Yönetim › Şirket belgeleri: vergi levhası, sicil gazetesi, faaliyet belgesi gibi resmi belgeler.
-- sirket_belgeleri : her yüklenen dosyanın bilgisi (tür, belge tarihi, son geçerlilik, not).
--                    Aynı türde yeni dosya eskisini silmez; ekranda en yenisi "güncel" sayılır.
-- sirket-belgeleri : dosyaların kendisi — Supabase Storage'da GİZLİ alan (herkese açık link yok;
--                    uygulama 10 dakika geçerli imzalı link üretir). Dosya başına 20 MB.
-- Şirket künyesi yeni tablo istemez: sistem_ayarlari 'sirket_kunye' anahtarında (JSON).
-- Başka tabloya dokunmaz. Kurulmadan önce uygulama yine çalışır; sayfa kurulum notu gösterir.
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır.

CREATE TABLE IF NOT EXISTS sirket_belgeleri (
    id            bigserial PRIMARY KEY,
    zaman         timestamptz NOT NULL DEFAULT now(),
    tur           text NOT NULL,          -- Vergi levhası, Ticaret Sicil Gazetesi, ...
    ad            text NOT NULL,          -- yüklenen dosyanın özgün adı
    yol           text NOT NULL UNIQUE,   -- dosya alanındaki yol
    boyut         bigint,
    mime          text,
    belge_tarihi  date,
    bitis_tarihi  date,                   -- son geçerlilik; süresiz belgede boş
    notu          text,
    yukleyen      text
);
CREATE INDEX IF NOT EXISTS sirket_belgeleri_tur_idx ON sirket_belgeleri (tur);

-- İzin kuralı YOK (15_dis_erisim_kapat.sql ile aynı): uygulama service_role ile bağlanır.
ALTER TABLE sirket_belgeleri ENABLE ROW LEVEL SECURITY;

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('sirket-belgeleri', 'sirket-belgeleri', false, 20971520, ARRAY[
    'application/pdf', 'image/jpeg', 'image/png',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword'])
ON CONFLICT (id) DO NOTHING;

-- GERİ ALMA (dosyalar da silinir — önce Şirket belgeleri sayfasından ZIP olarak indirin):
--   DELETE FROM storage.objects WHERE bucket_id = 'sirket-belgeleri';
--   DELETE FROM storage.buckets WHERE id = 'sirket-belgeleri';
--   DROP TABLE IF EXISTS sirket_belgeleri;
