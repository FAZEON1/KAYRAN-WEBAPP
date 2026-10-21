-- ════════════════════════════════════════════════════════════════════
-- 52 · Mikro eşitleme turu kilidi (Ekim 2026)
--
-- SORUN (21.10.2026 denetimi): eşitleme turu iki yerden çalışıyor — GitHub işi (otonom/mikro_esitle.py) ve
--   uygulamanın arka plan iş parçacığı (app.py _mikro_esitle_dene; birden çok sunucu örneği / oturum olabilir).
--   Kilit yoktu: iki tur aynı anda çalışırsa çek listesi iki katına çıkabilir (önce ekle, sonra eskileri sil),
--   satış satırı ya da Mikro'dan yeni ithalat dosyası iki kez eklenebilir.
-- ÇÖZÜM: tur başında süreli kilit (shared/mikro_kilit.py). Kilidi alamayan tur atlanır; tur çökerse kilit süresi
--   dolunca (varsayılan 10 dk) kendiliğinden düşer.
--
-- GERİ ALMA: DROP FUNCTION mikro_kilit_al(text, text, integer); DROP FUNCTION mikro_kilit_birak(text, text);
--            DROP TABLE mikro_tur_kilidi;
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.mikro_tur_kilidi (
    ad     text PRIMARY KEY,
    sahip  text NOT NULL,
    bitis  timestamptz NOT NULL,
    alinis timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.mikro_tur_kilidi ENABLE ROW LEVEL SECURITY;

-- Kilidi al: yoksa ya da süresi dolmuşsa (ya da zaten bu sahipteyse) alır ve true döner; değilse false.
CREATE OR REPLACE FUNCTION public.mikro_kilit_al(p_ad text, p_sahip text, p_sn integer DEFAULT 600)
RETURNS boolean LANGUAGE plpgsql SECURITY INVOKER AS $f$
DECLARE
    n integer;
BEGIN
    INSERT INTO public.mikro_tur_kilidi AS k (ad, sahip, bitis, alinis)
    VALUES (p_ad, p_sahip, now() + make_interval(secs => p_sn), now())
    ON CONFLICT (ad) DO UPDATE
        SET sahip = EXCLUDED.sahip, bitis = EXCLUDED.bitis, alinis = EXCLUDED.alinis
        WHERE k.bitis < now() OR k.sahip = EXCLUDED.sahip;
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n > 0;
END
$f$;

-- Kilidi bırak (yalnız sahibi).
CREATE OR REPLACE FUNCTION public.mikro_kilit_birak(p_ad text, p_sahip text)
RETURNS boolean LANGUAGE plpgsql SECURITY INVOKER AS $f$
DECLARE
    n integer;
BEGIN
    UPDATE public.mikro_tur_kilidi SET bitis = now() WHERE ad = p_ad AND sahip = p_sahip;
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n > 0;
END
$f$;

REVOKE ALL ON FUNCTION public.mikro_kilit_al(text, text, integer) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.mikro_kilit_birak(text, text) FROM PUBLIC, anon, authenticated;

NOTIFY pgrst, 'reload schema';
