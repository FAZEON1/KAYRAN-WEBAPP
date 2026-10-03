-- 16 · Destek dönem görünümü (v_destek_donem) — düzeltme (Ekim 2026)
--
-- SORUN: ref_kayitlari.aylik 47 kayıtta nesne değil METİN olarak saklıydı ('{"2025-03": 200.0}'
-- metni; Ref ekleme / düzenleme json.dumps ile yazıyordu). Görünüm jsonb_each_text'te patlıyor,
-- Yönetim P&L her açılışta yedek Python hesabına (kayranpm/ref_no.get_tum_ref_tutarlari) düşüyordu.
-- KAYITLARA DOKUNULMAZ (okumada çözülür): metin ise açılır, boş metin / bozuk metin = dağılım yok.
--
-- AYNI SONUÇ: görünüm yedek Python hesabıyla BİREBİR aynı kuralı izler (tests/test_destek_donem.py):
--   • aylık dağılım: her ay o ayın 1–28'i aralığı; seçilen dönemle KESİŞEN aylar dahil;
--   • dağılımın toplamı Ref tutarından azsa artık: planlama yılı varsa o yılın tamamı, yoksa tarih;
--   • dağılımı olmayan Ref: planlama yılı varsa yılın tamamı, yoksa tarih;
--   • havuz bütçe: harcamalar (giriş ve BÜTÇE türü hariç), fatura tarihiyle.
-- Bunun için her satır geçerli olduğu aralığı taşır: donem_bas, donem_bit. Uygulama
-- (get_destek_donem) "aralık seçilen dönemle kesişiyor mu" diye süzer. donem: kur tarihi (eskisi gibi).
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır. Görünüm okunamazsa
-- uygulama yedek Python hesabına düşer (bugünkü hâl) — yanlış rakam riski yok.

-- Eski sütunlar (kaynak, tur, firma_id, doviz, donem, tutar) aynı sırada; yeni ikisi sona eklenir →
-- yerinde güncellenir (silmeye gerek yok).
CREATE OR REPLACE VIEW v_destek_donem WITH (security_invoker = on) AS
WITH ref AS (
    SELECT r.id, r.firma_id, r.tutar, r.yil, r.tarih,
           COALESCE(NULLIF(TRIM(BOTH FROM r.doviz), ''), 'USD') AS doviz,
           CASE
               WHEN jsonb_typeof(r.aylik) = 'object' THEN r.aylik
               WHEN jsonb_typeof(r.aylik) = 'string' AND (r.aylik #>> '{}') ~ '^\s*\{.*\}\s*$'
                    THEN (r.aylik #>> '{}')::jsonb
               ELSE '{}'::jsonb
           END AS aj
      FROM ref_kayitlari r
     WHERE lower(COALESCE(r.durum, '')) <> 'iptal'
), ref_aylik AS (
    SELECT ref.id, ref.firma_id, ref.doviz,
           to_date(k.key || '-01', 'YYYY-MM-DD') AS donem,
           (k.value)::numeric AS tutar
      FROM ref
      CROSS JOIN LATERAL jsonb_each_text(CASE WHEN jsonb_typeof(ref.aj) = 'object' THEN ref.aj ELSE '{}'::jsonb END) k(key, value)
     WHERE k.key ~ '^\d{4}-\d{2}$' AND k.value ~ '^\d+(\.\d+)?$' AND (k.value)::numeric > 0
), ref_toplam AS (   -- Python gibi: ay yazımına bakmadan dağılımdaki bütün pozitif değerler
    SELECT ref.id, sum((k.value)::numeric) AS aylik_toplam
      FROM ref
      CROSS JOIN LATERAL jsonb_each_text(CASE WHEN jsonb_typeof(ref.aj) = 'object' THEN ref.aj ELSE '{}'::jsonb END) k(key, value)
     WHERE k.value ~ '^\d+(\.\d+)?$' AND (k.value)::numeric > 0
     GROUP BY ref.id
), ref_artik AS (
    SELECT ref.id, ref.firma_id, ref.doviz,
           CASE WHEN TRIM(BOTH FROM COALESCE(ref.yil::text, '')) ~ '^\d{4}$'
                THEN to_date(TRIM(BOTH FROM ref.yil::text) || '-01-01', 'YYYY-MM-DD') END AS yil_bas,
           CASE WHEN COALESCE(ref.tarih::text, '') ~ '^\d{4}-\d{2}-\d{2}'
                THEN substring(ref.tarih::text, 1, 10)::date END AS tarih_gun,
           CASE WHEN ref.aj <> '{}'::jsonb
                THEN COALESCE(ref.tutar, 0) - COALESCE(t.aylik_toplam, 0)
                ELSE COALESCE(ref.tutar, 0) END AS tutar,
           ref.aj <> '{}'::jsonb AS dagilimli
      FROM ref LEFT JOIN ref_toplam t ON t.id = ref.id
), havuz AS (
    SELECT b.firma_id,
           COALESCE(NULLIF(TRIM(BOTH FROM b.doviz), ''), 'USD') AS doviz,
           COALESCE(NULLIF(TRIM(BOTH FROM b.tur), ''), 'Diğer') AS tur,
           CASE WHEN COALESCE(b.fatura_tarih::text, '') ~ '^\d{4}-\d{2}-\d{2}'
                THEN substring(b.fatura_tarih::text, 1, 10)::date END AS donem,
           COALESCE(b.tutar, 0) AS tutar
      FROM ref_butce b
     WHERE lower(TRIM(BOTH FROM COALESCE(b.yon, ''))) NOT IN ('giris', 'giriş')
       AND upper(translate(COALESCE(b.tur, ''), 'İıŞşĞğÜüÖöÇç', 'IISSGGUUOOCC')) <> 'BUTCE'
)
SELECT 'ref'::text AS kaynak, 'Ref No'::text AS tur, firma_id, doviz, donem, tutar,
       donem AS donem_bas, donem + 27 AS donem_bit
  FROM ref_aylik
UNION ALL
SELECT 'ref', 'Ref No', firma_id, doviz, COALESCE(yil_bas, tarih_gun), tutar,
       COALESCE(yil_bas, tarih_gun),
       CASE WHEN yil_bas IS NOT NULL THEN (yil_bas + interval '1 year' - interval '1 day')::date ELSE tarih_gun END
  FROM ref_artik
 WHERE COALESCE(yil_bas, tarih_gun) IS NOT NULL
   AND CASE WHEN dagilimli THEN tutar > 0.005 ELSE tutar > 0 END
UNION ALL
SELECT 'havuz', tur, firma_id, doviz, donem, tutar, donem, donem
  FROM havuz
 WHERE donem IS NOT NULL;

-- Yalnız uygulamanın yetkili anahtarı (15_dis_erisim_kapat.sql ile aynı kural)
REVOKE ALL ON v_destek_donem FROM anon, authenticated;
GRANT SELECT ON v_destek_donem TO service_role;

-- GERİ ALMA: DROP VIEW IF EXISTS v_destek_donem;  (uygulama yedek Python hesabına düşer)
