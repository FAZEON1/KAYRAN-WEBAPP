@echo off
REM Iki zamanlanmis gorev kurar (sag tik -> Yonetici olarak calistir):
REM   KAYRAN Mikro aktarim     -> 15 dakikada bir, son aktarimdan bu yana degisenler
REM   KAYRAN Mikro tam aktarim -> her gece 03:00, her sey bastan
REM Gorevler SYSTEM hesabiyla calisir: oturum kapaliyken de calisir.
cd /d "%~dp0"
schtasks /Create /TN "KAYRAN Mikro aktarim" /TR "\"%~dp0zamanli.bat\"" /SC MINUTE /MO 15 /RU SYSTEM /RL HIGHEST /F
schtasks /Create /TN "KAYRAN Mikro tam aktarim" /TR "\"%~dp0zamanli.bat\" tam" /SC DAILY /ST 03:00 /RU SYSTEM /RL HIGHEST /F
echo.
echo Kurulan gorevler:
schtasks /Query /TN "KAYRAN Mikro aktarim"
schtasks /Query /TN "KAYRAN Mikro tam aktarim"
pause
