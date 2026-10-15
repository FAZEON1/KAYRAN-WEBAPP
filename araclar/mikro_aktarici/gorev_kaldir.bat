@echo off
REM Zamanlanmis gorevleri kaldirir (geri alma). Yonetici olarak calistirin.
schtasks /Delete /TN "KAYRAN Mikro aktarim" /F
schtasks /Delete /TN "KAYRAN Mikro tam aktarim" /F
pause
