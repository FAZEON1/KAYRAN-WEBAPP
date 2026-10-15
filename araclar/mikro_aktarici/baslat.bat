@echo off
REM Elle calistirma. Kullanim:
REM   baslat.bat test   -> baglanti + her sorgudan ilk 3 kayit (yalniz okur, Supabase'e yazmaz)
REM   baslat.bat tam    -> her seyi bastan aktar (tek sefer)
REM   baslat.bat        -> son aktarimdan bu yana degisenleri aktar (tek sefer)
cd /d "%~dp0"
if not exist ayarlar.bat (
    echo ayarlar.bat bulunamadi. ayarlar_ornek.bat dosyasini ayarlar.bat adiyla kopyalayip doldurun.
    pause
    exit /b 1
)
call ayarlar.bat
call :python_bul
if /i "%1"=="test" (
    %PY% mikro_kayran.py --test --ham
) else if /i "%1"=="tam" (
    %PY% mikro_kayran.py --tam --bir-kez
) else (
    %PY% mikro_kayran.py --bir-kez
)
pause
exit /b

:python_bul
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
exit /b
