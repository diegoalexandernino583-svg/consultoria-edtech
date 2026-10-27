@echo off
title Centro de Comando EdTech - Plataforma Visual
color 0B
echo =====================================================================
echo    CENTRO DE COMANDO EDTECH - PLATAFORMA VISUAL v2.0
echo =====================================================================
echo.
echo  Iniciando con TRIPLE CONECTIVIDAD:
echo.
echo    [1] Acceso Local (Esta PC):       http://localhost:8080
echo    [2] Acceso Red Local (Misma Wi-Fi): Disponible para dispositivos cercanos
echo    [3] Acceso Global Internet HTTPS:   Tunel Cloudflare activo (Enlace mundial)
echo.
echo  Conectando con Azure SQL Database y activando enlace mundial...
echo.

cd /d "%~dp0..\.."
python app_visual.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Probando con py launcher de Windows...
    py -3 app_visual.py
)

pause
