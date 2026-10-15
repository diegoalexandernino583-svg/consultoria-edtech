@echo off
title Centro de Mando EdTech - Servidor Publico con Tunel Seguro
color 0b
echo ======================================================================
echo    CENTRO DE MANDO EDTECH - SERVIDOR Y TUNEL PUBLICO GLOBAL
echo ======================================================================
echo.
cd /d "%~dp0"

echo [*] Verificando servidor en segundo plano...
netstat -ano | findstr :8080 >nul
if errorlevel 1 (
    echo [+] Iniciando backend FastAPI en puerto 8080...
    start /b python app_visual.py
    timeout /t 4 >nul
) else (
    echo [i] Backend de Python ya se encuentra escuchando en el puerto 8080.
)

echo [*] Comprobando tunel Cloudflare...
tasklist /fi "imagename eq cloudflared.exe" | findstr /i "cloudflared.exe" >nul
if errorlevel 1 (
    echo [+] Conectando tunel Cloudflare a Internet...
    start /b "" "%~dp0cloudflared.exe" tunnel --url http://127.0.0.1:8080 --logfile "%~dp0cloudflared_tunnel.log"
    timeout /t 5 >nul
) else (
    echo [i] Tunel Cloudflare ya se encuentra activo y conectado a Internet.
)

echo.
echo ======================================================================
echo  INFORMACION DE ACCESO GLOBAL:
echo ======================================================================
type "%~dp0ENLACE_PUBLICO.txt"
echo.
pause
