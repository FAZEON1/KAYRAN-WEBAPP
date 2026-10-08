-- 26 · Çalışan izinleri (Ekim 2026)
--
-- Kişi menüsü › İzinler: yıllık izin, mazeret izinleri, rapor, ücretsiz izin; onay, bakiye, takvim, bordro dökümü.
-- personel        : kişi kartı. kod = programdaki kullanıcı adı (programa girmeyen çalışan için kısa ad).
--                   devir_tarihi / devir_gun: programa geçerken o tarihteki kalan yıllık izin (bordrodan).
-- izin_talepleri  : talep ve karar. gun = izinden düşen iş günü, talep anında hesaplanıp yazılır
--                   (hafta sonu, resmi tatil ve arife yarım günü düşülmüş). Silinmez; iptal edilir.
-- Ayar yeni tablo istemez: sistem_ayarlari 'izin_ayar' (JSON, {"cumartesi": false}).
-- Başka tabloya dokunmaz. Kurulmadan önce uygulama yine çalışır; sayfa kurulum notu gösterir.
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır.

CREATE TABLE IF NOT EXISTS personel (
    kod           text PRIMARY KEY,
    ad            text NOT NULL,
    departman     text,
    ise_giris     date,
    dogum_tarihi  date,
    devir_tarihi  date,
    devir_gun     numeric(6,1),
    cikis_tarihi  date,
    notu          text,
    guncelleme    timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS izin_talepleri (
    id            bigserial PRIMARY KEY,
    personel      text NOT NULL REFERENCES personel (kod) ON UPDATE CASCADE,
    tur           text NOT NULL,
    baslangic     date NOT NULL,
    bitis         date NOT NULL,
    yarim_gun     boolean NOT NULL DEFAULT false,
    gun           numeric(6,1) NOT NULL,
    takvim_gunu   integer NOT NULL,
    aciklama      text,
    durum         text NOT NULL DEFAULT 'bekliyor'
                  CHECK (durum IN ('bekliyor', 'onaylandi', 'reddedildi', 'iptal')),
    talep_eden    text,
    talep_zamani  timestamptz NOT NULL DEFAULT now(),
    karar_veren   text,
    karar_zamani  timestamptz,
    karar_notu    text,
    iptal_eden    text,
    iptal_zamani  timestamptz,
    CHECK (bitis >= baslangic)
);
CREATE INDEX IF NOT EXISTS izin_talepleri_personel_idx ON izin_talepleri (personel, baslangic);
CREATE INDEX IF NOT EXISTS izin_talepleri_durum_idx ON izin_talepleri (durum);

-- İzin kuralı YOK (15_dis_erisim_kapat.sql ile aynı): uygulama service_role ile bağlanır.
ALTER TABLE personel ENABLE ROW LEVEL SECURITY;
ALTER TABLE izin_talepleri ENABLE ROW LEVEL SECURITY;

-- GERİ ALMA (bütün izin kayıtları silinir — önce İzinler › Rapor'dan Excel alın):
--   DROP TABLE IF EXISTS izin_talepleri;
--   DROP TABLE IF EXISTS personel;
--   DELETE FROM sistem_ayarlari WHERE anahtar = 'izin_ayar';
