-- ════════════════════════════════════════════════════════════════════
-- 44 · mikro_siparis şemada kayıtlı olsun (Ekim 2026, siparişler Mikro'dan)
--
-- Aktarıcının ilk sürümünden beri canlıda olan tablo (Mikro SIPARISLER; sip_tip 0 müşteri siparişi,
-- 1 tedarikçi siparişi; aktarıcı 15 dakikada bir artımlı, gece tam çeker). Uygulama artık okuyor:
-- açık müşteri siparişi bekleyen satış olur (satis/mikro_esitle.siparis_kayitlari), tedarikçi siparişleri
-- İthalat › Tedarikçi siparişleri'nde görünür. Canlıda var: bu dosya hiçbir şeyi değiştirmez (IF NOT EXISTS).
-- GERİ ALMA: gerekmez.
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.mikro_siparis (
    sip_guid uuid PRIMARY KEY, sip_tip integer, sip_cins integer, sip_tarih timestamp, sip_teslim_tarih timestamp,
    sip_evrakno_seri text, sip_evrakno_sira integer, sip_satirno integer, sip_musteri_kod text, sip_stok_kod text,
    sip_miktar numeric, sip_teslim_miktar numeric, kalan numeric, sip_b_fiyat numeric, sip_tutar numeric,
    sip_doviz_cinsi integer, sip_depono integer, sip_kapat_fl boolean, sip_lastup_date timestamp,
    senk_zamani timestamptz NOT NULL DEFAULT now()
);
