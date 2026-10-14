-- ════════════════════════════════════════════════════════════════════
-- KAYRAN — Şirket kimliği ve kişiye bağlı roller (Ekim 2026)
--
-- Supabase → SQL Editor → tamamını yapıştır → Run. Tekrar çalıştırılabilir.
-- Yeni tablo YOK: mevcut kullanici_yetkileri.ozel dizisine rol etiketi eklenir,
-- sistem_ayarlari'na şirket kimliği anahtarları yazılır.
--
-- KURULMASA DA davranış aynıdır: shared/sirket_ayar.py etiketi taşıyan kimseyi
-- bulamazsa sistem_ayarlari'na, o da yoksa koddaki bugünkü değerlere düşer.
-- Bu betik bugünkü kişileri yeni rollere atar — sonuç yine bugünküyle aynıdır;
-- farkı, bundan sonra rolü Kullanıcı yönetimi ekranından başkasına verebilmektir.
--
-- Rol etiketleri:
--   kar_gorur          kâr/marj her yerde + ana sayfa finans kartları
--   talep_onaylar      talebi Claude'a gönderir; PR maillerinin varsayılan alıcısı
--   yonetici           ana sayfa "Yönetici araçları", yükleme gecikmesi kopyası
--   marj_uyari_alir    zararına satış e-postası
--   yukleme_sorumlusu:<kaynak>   dönemsel yükleme sorumlusu (Veri güncelliği →
--                      Takvim ayarları'nda sorumlu kayıtlıysa o kazanır)
-- ════════════════════════════════════════════════════════════════════

-- Rol atamaları: yalnız satırı olan kullanıcıya, etiket YOKSA eklenir (idempotent).
-- Her atama ayrı UPDATE: tek UPDATE ... FROM aynı satıra birden çok eşleşmede yalnız birini uygular.
UPDATE kullanici_yetkileri SET ozel = array_append(coalesce(ozel, '{}'::text[]), 'kar_gorur'), guncelleyen = 'kurulum_32', guncelleme = now()
    WHERE kullanici = 'ibrahim' AND NOT ('kar_gorur' = ANY(coalesce(ozel, '{}'::text[])));
UPDATE kullanici_yetkileri SET ozel = array_append(coalesce(ozel, '{}'::text[]), 'talep_onaylar'), guncelleyen = 'kurulum_32', guncelleme = now()
    WHERE kullanici = 'ibrahim' AND NOT ('talep_onaylar' = ANY(coalesce(ozel, '{}'::text[])));
UPDATE kullanici_yetkileri SET ozel = array_append(coalesce(ozel, '{}'::text[]), 'yonetici'), guncelleyen = 'kurulum_32', guncelleme = now()
    WHERE kullanici = 'ibrahim' AND NOT ('yonetici' = ANY(coalesce(ozel, '{}'::text[])));
UPDATE kullanici_yetkileri SET ozel = array_append(coalesce(ozel, '{}'::text[]), 'marj_uyari_alir'), guncelleyen = 'kurulum_32', guncelleme = now()
    WHERE kullanici = 'ibrahim' AND NOT ('marj_uyari_alir' = ANY(coalesce(ozel, '{}'::text[])));
UPDATE kullanici_yetkileri SET ozel = array_append(coalesce(ozel, '{}'::text[]), 'marj_uyari_alir'), guncelleyen = 'kurulum_32', guncelleme = now()
    WHERE kullanici = 'korkut' AND NOT ('marj_uyari_alir' = ANY(coalesce(ozel, '{}'::text[])));
UPDATE kullanici_yetkileri SET ozel = array_append(coalesce(ozel, '{}'::text[]), 'marj_uyari_alir'), guncelleyen = 'kurulum_32', guncelleme = now()
    WHERE kullanici = 'serkan' AND NOT ('marj_uyari_alir' = ANY(coalesce(ozel, '{}'::text[])));
UPDATE kullanici_yetkileri SET ozel = array_append(coalesce(ozel, '{}'::text[]), 'yukleme_sorumlusu:musteri_haftalik'), guncelleyen = 'kurulum_32', guncelleme = now()
    WHERE kullanici = 'derya' AND NOT ('yukleme_sorumlusu:musteri_haftalik' = ANY(coalesce(ozel, '{}'::text[])));
UPDATE kullanici_yetkileri SET ozel = array_append(coalesce(ozel, '{}'::text[]), 'yukleme_sorumlusu:aktif_stok'), guncelleyen = 'kurulum_32', guncelleme = now()
    WHERE kullanici = 'serdar' AND NOT ('yukleme_sorumlusu:aktif_stok' = ANY(coalesce(ozel, '{}'::text[])));
UPDATE kullanici_yetkileri SET ozel = array_append(coalesce(ozel, '{}'::text[]), 'yukleme_sorumlusu:aktif_ithalat'), guncelleyen = 'kurulum_32', guncelleme = now()
    WHERE kullanici = 'serdar' AND NOT ('yukleme_sorumlusu:aktif_ithalat' = ANY(coalesce(ozel, '{}'::text[])));
UPDATE kullanici_yetkileri SET ozel = array_append(coalesce(ozel, '{}'::text[]), 'yukleme_sorumlusu:aktif_cari'), guncelleyen = 'kurulum_32', guncelleme = now()
    WHERE kullanici = 'serdar' AND NOT ('yukleme_sorumlusu:aktif_cari' = ANY(coalesce(ozel, '{}'::text[])));
UPDATE kullanici_yetkileri SET ozel = array_append(coalesce(ozel, '{}'::text[]), 'yukleme_sorumlusu:odeme_listesi'), guncelleyen = 'kurulum_32', guncelleme = now()
    WHERE kullanici = 'serdar' AND NOT ('yukleme_sorumlusu:odeme_listesi' = ANY(coalesce(ozel, '{}'::text[])));
UPDATE kullanici_yetkileri SET ozel = array_append(coalesce(ozel, '{}'::text[]), 'yukleme_sorumlusu:gider_tablosu'), guncelleyen = 'kurulum_32', guncelleme = now()
    WHERE kullanici = 'serdar' AND NOT ('yukleme_sorumlusu:gider_tablosu' = ANY(coalesce(ozel, '{}'::text[])));
UPDATE kullanici_yetkileri SET ozel = array_append(coalesce(ozel, '{}'::text[]), 'yukleme_sorumlusu:happylife'), guncelleyen = 'kurulum_32', guncelleme = now()
    WHERE kullanici = 'samet' AND NOT ('yukleme_sorumlusu:happylife' = ANY(coalesce(ozel, '{}'::text[])));
UPDATE kullanici_yetkileri SET ozel = array_append(coalesce(ozel, '{}'::text[]), 'yukleme_sorumlusu:g5f_sayim'), guncelleyen = 'kurulum_32', guncelleme = now()
    WHERE kullanici = 'gokhan' AND NOT ('yukleme_sorumlusu:g5f_sayim' = ANY(coalesce(ozel, '{}'::text[])));

-- Şirket kimliği (değer JSON metni — kayranacc.database.get_ayar json.loads ile okur).
-- ON CONFLICT DO NOTHING: ekrandan / elle değiştirilmiş değeri EZMEZ.
INSERT INTO sistem_ayarlari (anahtar, deger, guncelleme_tarihi) VALUES
    ('sirket_ad',                 '"KAYRAN ELEKTRONİK"', now()),
    ('sirket_kisa_ad',            '"KAYRAN"', now()),
    ('sirket_talep_eposta',       '"ibrahim.kayran@g5fteknoloji.com"', now()),
    ('sirket_yonetici_kullanici', '"ibrahim"', now())
ON CONFLICT (anahtar) DO NOTHING;

-- KONTROL:
--   SELECT kullanici, ozel FROM kullanici_yetkileri ORDER BY kullanici;
--   SELECT anahtar, deger FROM sistem_ayarlari WHERE anahtar LIKE 'sirket_%';
--
-- GERİ ALMA (rol etiketleri kalkınca kod varsayılana döner; davranış yine aynı):
--   UPDATE kullanici_yetkileri SET ozel = array(
--       SELECT x FROM unnest(ozel) x
--       WHERE x NOT IN ('kar_gorur','talep_onaylar','yonetici','marj_uyari_alir')
--         AND x NOT LIKE 'yukleme_sorumlusu:%');
--   DELETE FROM sistem_ayarlari WHERE anahtar IN
--       ('sirket_ad','sirket_kisa_ad','sirket_talep_eposta','sirket_yonetici_kullanici');
