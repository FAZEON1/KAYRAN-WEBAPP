# KAYRAN yeni uygulama (ön yüz)

Next.js (React + TypeScript). Bütün veri `../api` (FastAPI) üzerinden gelir; tarayıcı yalnız bu siteyle konuşur,
`/api/*` istekleri sunucu tarafında API'ye aktarılır (`next.config.ts`). Tasarım dili:
https://claude.ai/artifact/QeMhUiHWNK1sYnAtsRjkzW

## Yerelde

```
cd web && npm ci
API_URL=http://127.0.0.1:8000 npm run dev      # API ayrıca: uvicorn api.main:app (depo kökünden)
npm run denetle && npm test && npm run build   # CI'nın "Yeni uygulama" işiyle aynı
```

## Kurallar

- Renk, yazı tipi, boşluk yalnız `app/globals.css` belirteçlerinden; ekranda emoji yok, ikon `bilesen/Ikon.tsx`.
  Yeni ikon: `scripts/ikonlari-uret.mjs` LISTE'ye ekle ve çalıştır.
- Sayı dili `lib/bicim.ts` (1.234,56 · %31,1) — eski uygulamayla aynı.
- Bir sayfa yeni uygulamaya taşınınca `api/menu.py` → `YENI_SAYFALAR`'a eklenir; menü oraya yönlendirir.
- İş kuralı (paçal, ödeme, stok…) burada YAZILMAZ: API'deki mevcut Python kodundan gelir.
