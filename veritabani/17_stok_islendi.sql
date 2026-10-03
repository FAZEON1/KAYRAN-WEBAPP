-- 17 · İthalat dosyası stok işlenme kaydı (Ekim 2026)
--
-- SORUN: Uygulama, 'Teslim Alındı' dosyanın kalemlerinin depoya işlenip işlenmediğini
-- ithalat_dosyalari.stok_islendi alanında tutuyordu — ama bu sütun canlıda HİÇ oluşturulmamıştı
-- (kod "sütun yoksa sessiz devam" ediyordu). Sonuçları:
--   • 'Teslim Alındı'dan geri alınan dosyanın stoğu düşülmüyor, yeniden teslimde ikinci kez giriyordu;
--   • teslim alınmış dosyada adet düzeltmesi stoğa yansımıyordu;
--   • "stoğa girmemiş" listesi 129 dosyanın hepsini gösteriyordu (yanlış alarm).
--
-- ANLAMI: true = stok depoda (uygulamaya göre), false = işlenmedi / geri çekildi,
-- boş = bilinmiyor (bu sütundan önce teslim alınmış dosya).
-- MEVCUT KAYITLARA DOKUNULMAZ: eski dosyalar boş kalır; stoklarının nasıl girdiği (uygulama /
-- Excel) bilinmediği için toplu "işlendi" yazılmaz. Kaydı boş dosya geri alınırken stoğa
-- dokunulmaz ve "depoda" işaretlenir → yeniden teslimde çift giriş olmaz.
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır. Çalıştırılmadan
-- önce uygulama bugünkü gibi çalışır.

ALTER TABLE ithalat_dosyalari ADD COLUMN IF NOT EXISTS stok_islendi boolean;

-- GERİ ALMA: ALTER TABLE ithalat_dosyalari DROP COLUMN IF EXISTS stok_islendi;
