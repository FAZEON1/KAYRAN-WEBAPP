-- UYGULA: HAYIR
-- ════════════════════════════════════════════════════════════════════
-- 31 · Veri bütünlüğü ÖNERİSİ — UYGULANMAYACAK
--
-- Bu dosya bir öneri listesidir; uygula.py ilk satırdaki "UYGULA: HAYIR"
-- işareti yüzünden onu hiç çalıştırmaz. Kullanıcı onayıyla, madde madde,
-- ayrı numaralı bir dosyaya taşınarak kurulur.
--
-- Her maddenin önünde canlıda kaç satırın kısıtı bozacağını sayan SELECT var.
-- Sayımlar 14.10.2026'da canlıda salt okunur çalıştırıldı (yalnız sayı döner,
-- kişisel veri dönmez); sonuçlar "-- canlı:" satırlarında. Kurmadan önce
-- sayımları YENİDEN çalıştırın: yetim/bozuk satır varsa önce o düzeltilir.
--
-- Kurulum iki adımlı (tabloyu uzun süre kilitlememek için):
--   1) ADD CONSTRAINT … NOT VALID   — yalnız yeni/değişen satırları denetler, anında biter
--   2) VALIDATE CONSTRAINT …         — eski satırları tarar; yazmaları kilitlemez
-- NOT NULL için: önce CHECK (kolon IS NOT NULL) NOT VALID + VALIDATE, sonra
-- SET NOT NULL (Postgres doğrulanmış CHECK'i görüp tabloyu yeniden taramaz), sonra CHECK silinir.
--
-- Rakam değiştirmez: hiçbir satırı güncellemez/silmez; yalnız gelecekte
-- bozuk kayıt yazılmasını engeller. RİSK: kod bir yolda bu kurala uymayan
-- satır yazıyorsa o işlem hata verir — her madde için kod tarafı not edildi.
-- ════════════════════════════════════════════════════════════════════

-- ─── A) Canlıda ZATEN VAR olan yabancı anahtarlar (bilgi) ──────────────
-- Görevdeki "tek foreign key var" bulgusu canlıda doğru değil: 11 tane var
-- (00_temel_sema.sql, bölüm 3). Bunlar için bir şey yapmaya gerek yok:
--   edefter_fis_satirlari.fis_id   → edefter_fisler(id)     ON DELETE CASCADE
--   ithalat_kalemleri.dosya_id     → ithalat_dosyalari(id)  ON DELETE CASCADE
--   izin_talepleri.personel        → personel(kod)          ON UPDATE CASCADE
--   kampanya_urunler.kampanya_id   → kampanyalar(id)        ON DELETE CASCADE
--   odemeler.hafta_id              → haftalar(id)           ON DELETE CASCADE
--   ref_butce.firma_id             → ref_firmalar(id)       ON DELETE CASCADE
--   ref_kayitlari.firma_id         → ref_firmalar(id)       ON DELETE CASCADE
--   tahsilatlar.banka_id           → bankalar(id)
--   ts_gecmis.kayit_id             → ts_kayitlar(id)        ON DELETE CASCADE
--   virmanlar.hedef_banka_id       → bankalar(id)           ON DELETE SET NULL
--   virmanlar.kaynak_banka_id      → bankalar(id)           ON DELETE SET NULL

-- ─── B) Önerilen yabancı anahtarlar ────────────────────────────────────

-- B1) satislar.kampanya_id → kampanyalar(id)
-- canlı: 15.819 satış, kampanya_id dolu 0, yetim 0
SELECT count(*) AS yetim FROM satislar s
 WHERE s.kampanya_id IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM kampanyalar k WHERE k.id = s.kampanya_id);
-- Kampanya silinince satış kalır, bağı boşalır (SET NULL): satış rakamı değişmez.
ALTER TABLE satislar ADD CONSTRAINT satislar_kampanya_id_fkey
    FOREIGN KEY (kampanya_id) REFERENCES kampanyalar(id) ON DELETE SET NULL NOT VALID;
ALTER TABLE satislar VALIDATE CONSTRAINT satislar_kampanya_id_fkey;
CREATE INDEX IF NOT EXISTS satislar_kampanya_id_idx ON satislar (kampanya_id) WHERE kampanya_id IS NOT NULL;

-- B2) ts_kayitlar.iade_id → iadeler(id)
-- canlı: 789 kayıt, iade_id dolu 0, yetim 0
SELECT count(*) AS yetim FROM ts_kayitlar t
 WHERE t.iade_id IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM iadeler i WHERE i.id = t.iade_id);
-- DİKKAT: yükleme geri alma (yukleme_satir_geri_al) iadeler satırını silip aynı
-- id ile geri yazar; SET NULL bu sırada ts_kayitlar bağını kalıcı boşaltır.
-- Kurmadan önce geri alma akışında ts_kayitlar.iade_id'nin korunması ele alınmalı.
ALTER TABLE ts_kayitlar ADD CONSTRAINT ts_kayitlar_iade_id_fkey
    FOREIGN KEY (iade_id) REFERENCES iadeler(id) ON DELETE SET NULL NOT VALID;
ALTER TABLE ts_kayitlar VALIDATE CONSTRAINT ts_kayitlar_iade_id_fkey;
CREATE INDEX IF NOT EXISTS ts_kayitlar_iade_id_idx ON ts_kayitlar (iade_id) WHERE iade_id IS NOT NULL;

-- B3) odemeler.banka_id → bankalar(id)   (bankalar.id integer, banka_id bigint: FK'ye engel değil)
-- canlı: 1.960 ödeme, banka_id dolu 272, yetim 0
SELECT count(*) AS yetim FROM odemeler o
 WHERE o.banka_id IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM bankalar b WHERE b.id = o.banka_id);
ALTER TABLE odemeler ADD CONSTRAINT odemeler_banka_id_fkey
    FOREIGN KEY (banka_id) REFERENCES bankalar(id) ON DELETE SET NULL NOT VALID;
ALTER TABLE odemeler VALIDATE CONSTRAINT odemeler_banka_id_fkey;
CREATE INDEX IF NOT EXISTS odemeler_banka_id_idx ON odemeler (banka_id) WHERE banka_id IS NOT NULL;

-- B4) edefter_fis_satirlari.hesap_kodu → edefter_hesap_plani(kod)  (kod UNIQUE)
-- canlı: 0 fiş satırı (e-Defter henüz kullanılmıyor), yetim 0
SELECT count(*) AS yetim FROM edefter_fis_satirlari f
 WHERE NOT EXISTS (SELECT 1 FROM edefter_hesap_plani h WHERE h.kod = f.hesap_kodu);
-- Hesap planında olmayan koda fiş yazılamaz; hesap kodu değişirse fişler izler.
ALTER TABLE edefter_fis_satirlari ADD CONSTRAINT edefter_fis_satirlari_hesap_kodu_fkey
    FOREIGN KEY (hesap_kodu) REFERENCES edefter_hesap_plani(kod) ON UPDATE CASCADE NOT VALID;
ALTER TABLE edefter_fis_satirlari VALIDATE CONSTRAINT edefter_fis_satirlari_hesap_kodu_fkey;

-- B5) Var olan FK'lerin indeksi olmayan kolonları (silme/CASCADE'de tam tarama olmasın)
CREATE INDEX IF NOT EXISTS kampanya_urunler_kampanya_id_idx ON kampanya_urunler (kampanya_id);
CREATE INDEX IF NOT EXISTS odemeler_hafta_id_idx ON odemeler (hafta_id);
CREATE INDEX IF NOT EXISTS tahsilatlar_banka_id_idx ON tahsilatlar (banka_id);

-- ─── C) ÖNERİLMEYEN: SKU → urunler(sku) ────────────────────────────────
-- SKU'lar farklı yazımlarla gelir (shared.utils.sku_anahtar birleştirir; pazaryeri
-- kodları vb.) ve kartı olmayan ürün satılabilir. Birebir eşleşen FK işleri bozar.
-- canlı: satislar 113 / 15.819 satırın SKU'su urunler'de birebir yok;
--        iadeler 0 / 601, ithalat_kalemleri 0 / 599, kampanya_urunler 0 / 333.
SELECT count(*) AS kartsiz FROM satislar s
 WHERE s.sku IS NOT NULL AND NOT EXISTS (SELECT 1 FROM urunler u WHERE u.sku = s.sku);

-- ─── D) NOT NULL önerileri ─────────────────────────────────────────────
-- canlı (boş sayısı): satislar tarih 0, sku 0 (boş metin dahil), kanal 0, adet 0;
--   iadeler sku 0; ithalat_kalemleri dosya_id 0; ts_gecmis kayit_id 0;
--   odemeler hafta_id 0; tahsilatlar banka_id 0; ref_kayitlari firma_id 0.
-- (virmanlar.*_banka_id ÖNERİLMEZ: FK'leri ON DELETE SET NULL, NOT NULL ile çelişir.)
SELECT
    (SELECT count(*) FROM satislar WHERE tarih IS NULL)              AS satislar_tarih,
    (SELECT count(*) FROM satislar WHERE sku IS NULL)                AS satislar_sku,
    (SELECT count(*) FROM satislar WHERE kanal IS NULL)              AS satislar_kanal,
    (SELECT count(*) FROM satislar WHERE adet IS NULL)               AS satislar_adet,
    (SELECT count(*) FROM iadeler WHERE sku IS NULL)                 AS iadeler_sku,
    (SELECT count(*) FROM ithalat_kalemleri WHERE dosya_id IS NULL)  AS kalem_dosya,
    (SELECT count(*) FROM ts_gecmis WHERE kayit_id IS NULL)          AS ts_gecmis_kayit,
    (SELECT count(*) FROM odemeler WHERE hafta_id IS NULL)           AS odemeler_hafta,
    (SELECT count(*) FROM tahsilatlar WHERE banka_id IS NULL)        AS tahsilat_banka,
    (SELECT count(*) FROM ref_kayitlari WHERE firma_id IS NULL)      AS ref_firma;

-- Örnek kalıp (her kolon için aynı üç adım):
ALTER TABLE satislar ADD CONSTRAINT satislar_tarih_nn CHECK (tarih IS NOT NULL) NOT VALID;
ALTER TABLE satislar VALIDATE CONSTRAINT satislar_tarih_nn;
ALTER TABLE satislar ALTER COLUMN tarih SET NOT NULL;
ALTER TABLE satislar DROP CONSTRAINT satislar_tarih_nn;

ALTER TABLE satislar ADD CONSTRAINT satislar_sku_nn CHECK (sku IS NOT NULL) NOT VALID;
ALTER TABLE satislar VALIDATE CONSTRAINT satislar_sku_nn;
ALTER TABLE satislar ALTER COLUMN sku SET NOT NULL;
ALTER TABLE satislar DROP CONSTRAINT satislar_sku_nn;

ALTER TABLE satislar ADD CONSTRAINT satislar_kanal_nn CHECK (kanal IS NOT NULL) NOT VALID;
ALTER TABLE satislar VALIDATE CONSTRAINT satislar_kanal_nn;
ALTER TABLE satislar ALTER COLUMN kanal SET NOT NULL;
ALTER TABLE satislar DROP CONSTRAINT satislar_kanal_nn;

ALTER TABLE satislar ADD CONSTRAINT satislar_adet_nn CHECK (adet IS NOT NULL) NOT VALID;
ALTER TABLE satislar VALIDATE CONSTRAINT satislar_adet_nn;
ALTER TABLE satislar ALTER COLUMN adet SET NOT NULL;
ALTER TABLE satislar DROP CONSTRAINT satislar_adet_nn;

ALTER TABLE iadeler ADD CONSTRAINT iadeler_sku_nn CHECK (sku IS NOT NULL) NOT VALID;
ALTER TABLE iadeler VALIDATE CONSTRAINT iadeler_sku_nn;
ALTER TABLE iadeler ALTER COLUMN sku SET NOT NULL;
ALTER TABLE iadeler DROP CONSTRAINT iadeler_sku_nn;

ALTER TABLE ithalat_kalemleri ADD CONSTRAINT ithalat_kalemleri_dosya_id_nn CHECK (dosya_id IS NOT NULL) NOT VALID;
ALTER TABLE ithalat_kalemleri VALIDATE CONSTRAINT ithalat_kalemleri_dosya_id_nn;
ALTER TABLE ithalat_kalemleri ALTER COLUMN dosya_id SET NOT NULL;
ALTER TABLE ithalat_kalemleri DROP CONSTRAINT ithalat_kalemleri_dosya_id_nn;

ALTER TABLE ts_gecmis ADD CONSTRAINT ts_gecmis_kayit_id_nn CHECK (kayit_id IS NOT NULL) NOT VALID;
ALTER TABLE ts_gecmis VALIDATE CONSTRAINT ts_gecmis_kayit_id_nn;
ALTER TABLE ts_gecmis ALTER COLUMN kayit_id SET NOT NULL;
ALTER TABLE ts_gecmis DROP CONSTRAINT ts_gecmis_kayit_id_nn;

ALTER TABLE odemeler ADD CONSTRAINT odemeler_hafta_id_nn CHECK (hafta_id IS NOT NULL) NOT VALID;
ALTER TABLE odemeler VALIDATE CONSTRAINT odemeler_hafta_id_nn;
ALTER TABLE odemeler ALTER COLUMN hafta_id SET NOT NULL;
ALTER TABLE odemeler DROP CONSTRAINT odemeler_hafta_id_nn;

ALTER TABLE tahsilatlar ADD CONSTRAINT tahsilatlar_banka_id_nn CHECK (banka_id IS NOT NULL) NOT VALID;
ALTER TABLE tahsilatlar VALIDATE CONSTRAINT tahsilatlar_banka_id_nn;
ALTER TABLE tahsilatlar ALTER COLUMN banka_id SET NOT NULL;
ALTER TABLE tahsilatlar DROP CONSTRAINT tahsilatlar_banka_id_nn;

ALTER TABLE ref_kayitlari ADD CONSTRAINT ref_kayitlari_firma_id_nn CHECK (firma_id IS NOT NULL) NOT VALID;
ALTER TABLE ref_kayitlari VALIDATE CONSTRAINT ref_kayitlari_firma_id_nn;
ALTER TABLE ref_kayitlari ALTER COLUMN firma_id SET NOT NULL;
ALTER TABLE ref_kayitlari DROP CONSTRAINT ref_kayitlari_firma_id_nn;

-- ─── E) CHECK önerileri (değer aralığı) ────────────────────────────────
-- canlı (kuralı bozan satır): satislar adet<0: 0, birim_satis<0: 0, birim_maliyet<0: 0;
--   iadeler iade_adet<0: 0; ithalat_kalemleri adet<0: 0, birim_fob<0: 0;
--   ithalat_dosyalari kur<=0: 0 (kur boş: 0); cekler meblagh<0: 0.
-- ÖNERİLMEYEN: firma_stok.haftalik_satis >= 0 — canlıda 50 satır eksi (iade haftası), meşru.
-- ÖNERİLMEYEN: urunler.bizim_stok >= 0 — canlıda 0 eksi ama stok düzeltmeleri
--   geçici eksiye düşebilir; atomik stok işi (29_) bitmeden kural konmamalı.
SELECT
    (SELECT count(*) FROM satislar WHERE adet < 0 OR birim_satis < 0 OR birim_maliyet < 0) AS satislar,
    (SELECT count(*) FROM iadeler WHERE iade_adet < 0)                                     AS iadeler,
    (SELECT count(*) FROM ithalat_kalemleri WHERE adet < 0 OR birim_fob < 0)               AS kalemler,
    (SELECT count(*) FROM ithalat_dosyalari WHERE kur IS NOT NULL AND kur <= 0)            AS dosyalar,
    (SELECT count(*) FROM cekler WHERE meblagh < 0)                                        AS cekler;

ALTER TABLE satislar ADD CONSTRAINT satislar_adet_eksi_degil CHECK (adet >= 0) NOT VALID;
ALTER TABLE satislar VALIDATE CONSTRAINT satislar_adet_eksi_degil;
ALTER TABLE satislar ADD CONSTRAINT satislar_birim_eksi_degil
    CHECK (birim_satis >= 0 AND birim_maliyet >= 0) NOT VALID;
ALTER TABLE satislar VALIDATE CONSTRAINT satislar_birim_eksi_degil;

ALTER TABLE iadeler ADD CONSTRAINT iadeler_adet_eksi_degil CHECK (iade_adet >= 0) NOT VALID;
ALTER TABLE iadeler VALIDATE CONSTRAINT iadeler_adet_eksi_degil;

ALTER TABLE ithalat_kalemleri ADD CONSTRAINT ithalat_kalemleri_eksi_degil
    CHECK (adet >= 0 AND birim_fob >= 0) NOT VALID;
ALTER TABLE ithalat_kalemleri VALIDATE CONSTRAINT ithalat_kalemleri_eksi_degil;

ALTER TABLE ithalat_dosyalari ADD CONSTRAINT ithalat_dosyalari_kur_pozitif CHECK (kur > 0) NOT VALID;
ALTER TABLE ithalat_dosyalari VALIDATE CONSTRAINT ithalat_dosyalari_kur_pozitif;

ALTER TABLE cekler ADD CONSTRAINT cekler_meblag_eksi_degil CHECK (meblagh >= 0) NOT VALID;
ALTER TABLE cekler VALIDATE CONSTRAINT cekler_meblag_eksi_degil;

-- Durum alanları: yalnız kodun yazdığı değerler
-- canlı: odemeler.durum {bekliyor: 1.557, odendi: 403}; yuklemeler.durum {aktif: 25}
-- Kod: kayranacc yalnız 'bekliyor'/'odendi' yazar; shared/yukleme_gecmisi.py
--      'aktif'/'geri_aliniyor'/'geri_alindi' yazar. Yeni durum eklenirse kural da güncellenmeli.
SELECT
    (SELECT count(*) FROM odemeler WHERE durum IS NOT NULL AND durum NOT IN ('bekliyor', 'odendi')) AS odemeler,
    (SELECT count(*) FROM yuklemeler WHERE durum NOT IN ('aktif', 'geri_aliniyor', 'geri_alindi')) AS yuklemeler;

ALTER TABLE odemeler ADD CONSTRAINT odemeler_durum_check
    CHECK (durum IN ('bekliyor', 'odendi')) NOT VALID;
ALTER TABLE odemeler VALIDATE CONSTRAINT odemeler_durum_check;

ALTER TABLE yuklemeler ADD CONSTRAINT yuklemeler_durum_check
    CHECK (durum IN ('aktif', 'geri_aliniyor', 'geri_alindi')) NOT VALID;
ALTER TABLE yuklemeler VALIDATE CONSTRAINT yuklemeler_durum_check;

-- ─── F) Fazlalık kısıtlar (temizlik önerisi) ───────────────────────────
-- firma_stok'ta aynı (firma, sku, yukleme_tarihi) için iki UNIQUE, sistem_ayarlari'nda
-- PK'nin yanında aynı kolona UNIQUE var: her yazımda iki indeks güncellenir.
-- ALTER TABLE firma_stok DROP CONSTRAINT firma_stok_firma_sku_yukleme_tarihi_key;
-- ALTER TABLE sistem_ayarlari DROP CONSTRAINT sistem_ayarlari_anahtar_key;
-- (Kod upsert'te on_conflict="firma,sku,yukleme_tarihi" kullanıyorsa diğer UNIQUE yeterli.)
