@echo off
REM Gorev Zamanlayicisi bunu calistirir (pencere acmaz, beklemez). Cikti aktarim.log'a eklenir.
REM   zamanli.bat       -> 15 dakikalik artimli aktarim
REM   zamanli.bat tam   -> gecelik tam aktarim
cd /d "%~dp0"
if not exist ayarlar.bat (
    echo %date% %time% ayarlar.bat yok >> aktarim.log
    exit /b 1
)
call ayarlar.bat
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
if /i "%1"=="tam" (
    %PY% mikro_kayran.py --tam --bir-kez >> aktarim.log 2>&1
) else (
    %PY% mikro_kayran.py --bir-kez >> aktarim.log 2>&1
)
