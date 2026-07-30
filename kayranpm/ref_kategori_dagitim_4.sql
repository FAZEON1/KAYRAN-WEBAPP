-- KAYRAN — Ref No kategori tutarları (kaynak: REFERANS_NO_TAKİP_4 kopyası)
-- 150 kalem · 5 ref · 'TÜM KATEGORİLERE EŞİT BÖL' → EKRAN KARTI/KASA/MONİTÖR/MOUSEPAD dörde bölündü
-- KASA-SOĞUTUCU ve SOĞUTUCU kendi kategorileri olarak bırakıldı.

-- 1) KONTROL
SELECT ref_no, tutar, doviz, kategori, kategori_tutar
  FROM ref_kayitlari
 WHERE ref_no IN ('FZİTRF2025014', 'FZİTRF2025015', 'FZİTRF2025016', 'FZİTRF2025017', 'FZİTRF2025018');

-- 2) GÜNCELLEME
-- FZİTRF2025014  toplam 99,903.78  →  MONİTÖR 78,263 · KASA 20,720 · EKRAN KARTI 856 · MOUSEPAD 64
UPDATE ref_kayitlari SET kategori_tutar = '{"MONİTÖR": 78262.71, "KASA": 20720.12, "EKRAN KARTI": 856.47, "MOUSEPAD": 64.48}'::jsonb
 WHERE ref_no = 'FZİTRF2025014';

-- FZİTRF2025015  toplam 97,199.59  →  MONİTÖR 66,152 · KASA 27,010 · EKRAN KARTI 2,868 · MOUSEPAD 1,169
UPDATE ref_kayitlari SET kategori_tutar = '{"MONİTÖR": 66152.44, "KASA": 27009.82, "EKRAN KARTI": 2868.17, "MOUSEPAD": 1169.16}'::jsonb
 WHERE ref_no = 'FZİTRF2025015';

-- FZİTRF2025016  toplam 99,997.00  →  MONİTÖR 63,350 · KASA 35,647 · EKRAN KARTI 500 · MOUSEPAD 500
UPDATE ref_kayitlari SET kategori_tutar = '{"MONİTÖR": 63349.7, "KASA": 35647.3, "EKRAN KARTI": 500.0, "MOUSEPAD": 500.0}'::jsonb
 WHERE ref_no = 'FZİTRF2025016';

-- FZİTRF2025017  toplam 100,000.90  →  MONİTÖR 67,738 · KASA 17,625 · KASA-SOĞUTUCU 8,189 · EKRAN KARTI 5,825 · MOUSEPAD 624
UPDATE ref_kayitlari SET kategori_tutar = '{"MONİTÖR": 67737.97, "KASA": 17624.55, "KASA-SOĞUTUCU": 8189.34, "EKRAN KARTI": 5825.0, "MOUSEPAD": 624.04}'::jsonb
 WHERE ref_no = 'FZİTRF2025017';

-- FZİTRF2025018  toplam 62,074.20  →  MONİTÖR 36,969 · KASA 23,767 · MOUSEPAD 1,042 · SOĞUTUCU 296
UPDATE ref_kayitlari SET kategori_tutar = '{"MONİTÖR": 36968.72, "KASA": 23767.05, "MOUSEPAD": 1042.28, "SOĞUTUCU": 296.15}'::jsonb
 WHERE ref_no = 'FZİTRF2025018';

-- 3) DOĞRULA
SELECT ref_no, tutar, kategori_tutar FROM ref_kayitlari
 WHERE ref_no IN ('FZİTRF2025014', 'FZİTRF2025015', 'FZİTRF2025016', 'FZİTRF2025017', 'FZİTRF2025018') ORDER BY ref_no;