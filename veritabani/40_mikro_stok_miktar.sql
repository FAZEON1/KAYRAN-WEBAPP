-- ════════════════════════════════════════════════════════════════════
-- 40 · mikro_stok_miktar şemada kayıtlı olsun (Ekim 2026, Mikro adım 2)
--
-- Aktarıcının ilk sürümünden beri canlıda olan tablo (Mikro'da her ürünün depo depo miktarı; aktarıcı
-- her turda tam çeker). Uygulama artık okuyor (kayranpm/mikro_stok.py: depo stoğu Mikro'dan), o yüzden
-- tanımı burada. Canlıda var: bu dosya hiçbir şeyi değiştirmez (IF NOT EXISTS).
-- GERİ ALMA: gerekmez.
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.mikro_stok_miktar (
    sto_kod text NOT NULL, depo integer NOT NULL, sto_isim text, sto_birim1_ad text, miktar numeric,
    senk_zamani timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (sto_kod, depo)
);
