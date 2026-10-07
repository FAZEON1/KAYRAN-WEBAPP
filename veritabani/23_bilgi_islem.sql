-- 23 · Bilgi işlem elemanı (Ekim 2026)
--
-- bt_olcum : her sayfa açılışının süresi (ms) ve sayfa hatası olup olmadığı. Yavaşlığı ölçmeden
--            iyileştirme kanıtlanamaz; gece çalışan bilgi işlem görevi bu tabloyu okur.
-- bt_rapor : görevin her çalışması, bulduğu sorunlar, açtığı PR'lar ve iyileştirmelerin sonucu
--            (önce ↔ sonra). Bilgi İşlem sayfası (Sistem menüsü) bu tabloyu gösterir.
-- Başka tabloya dokunmaz. Kurulmadan önce uygulama yine çalışır; yalnız ölçüm tutulmaz.
--
-- Supabase → SQL Editor'de BİR KEZ çalıştırın. Tekrar çalıştırmak zararsızdır.

CREATE TABLE IF NOT EXISTS bt_olcum (
    id          bigserial PRIMARY KEY,
    zaman       timestamptz NOT NULL DEFAULT now(),
    modul       text NOT NULL,
    sayfa       text,
    ms          integer NOT NULL,
    hata        boolean NOT NULL DEFAULT false,
    kullanici   text
);
CREATE INDEX IF NOT EXISTS bt_olcum_zaman_idx ON bt_olcum (zaman DESC);

CREATE TABLE IF NOT EXISTS bt_rapor (
    id          bigserial PRIMARY KEY,
    zaman       timestamptz NOT NULL DEFAULT now(),
    tur         text NOT NULL,          -- calisma | iyilestirme | oneri | sonuc
    baslik      text NOT NULL,
    ozet        text,
    durum       text,                   -- acik | otomatik_birlesti | birlesti | reddedildi | oneri | bilgi
    pr_url      text,
    olcut       text,                   -- ör. 'satis/Satışlar sayfa süresi (p50)', 'hata: satis._stok_akilli_dus'
    once        numeric,
    sonra       numeric,
    birim       text,                   -- ms | adet | ...
    ayrinti     jsonb
);
CREATE INDEX IF NOT EXISTS bt_rapor_zaman_idx ON bt_rapor (zaman DESC);

-- İzin kuralı YOK (15_dis_erisim_kapat.sql ile aynı): uygulama ve görev service_role ile bağlanır.
ALTER TABLE bt_olcum ENABLE ROW LEVEL SECURITY;
ALTER TABLE bt_rapor ENABLE ROW LEVEL SECURITY;

-- Ölçüm tablosu büyümesin: 60 günden eski ölçümleri görev siler (otonom/bt_db.py temizle).

-- GERİ ALMA:
--   DROP TABLE IF EXISTS bt_olcum;
--   DROP TABLE IF EXISTS bt_rapor;
