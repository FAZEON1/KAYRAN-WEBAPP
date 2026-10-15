@echo off
REM Mikro -> KAYRAN aktarici ayarlari (ORNEK)
REM 1) Bu dosyayi ayni klasore "ayarlar.bat" adiyla kopyalayin.
REM 2) ayarlar.bat icinde < > arasindaki degerleri doldurun.
REM 3) ayarlar.bat'i kimseyle paylasmayin, e-postaya / sohbete yapistirmayin.
REM    Supabase anahtari veritabaninin tamamina erisir.
REM Degerler tirnak icinde kalsin. Sifrede % isareti varsa %% yazin.

set "MIKRO_URL=http://localhost:8094"
set "MIKRO_API_KEY=<Mikro ApiKey>"
set "MIKRO_FIRMA_KODU=<Mikro firma kodu>"
set "MIKRO_KULLANICI=<Mikro kullanici kodu>"
set "MIKRO_SIFRE=<Mikro sifresi>"
set "MIKRO_CALISMA_YILI=2026"

set "SUPABASE_URL=https://qspwlqegoeudifxxrxcj.supabase.co"
set "SUPABASE_SERVICE_KEY=<Supabase secret anahtari>"
