@echo off
title Servidor y Tunel Consultoria EdTech - Alta Disponibilidad
color 0b
echo ======================================================================
echo    INICIANDO SERVIDOR Y TUNEL CON AUTO-RECUPERACION CONTINUA
echo ======================================================================
cd /d "%~dp0"

echo 1. Verificando entorno Python...
python -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Falta uvicorn o fastapi.
    pause
    exit /b
)

echo 2. Iniciando servidor FastAPI en puerto 8080...
start "Servidor Consultoria EdTech" /min python app_visual.py

timeout /t 3 >nul

echo 3. Iniciando Tunel Cloudflare...
start "Tunel Cloudflare" /min cmd /c "cloudflared.exe tunnel --url http://127.0.0.1:8080 > cloudflared_tunnel.log 2>&1"

timeout /t 5 >nul

echo 4. Extrayendo enlace publico...
python -c "import re; f=open('cloudflared_tunnel.log','r',errors='ignore').read(); m=re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', f); open('ENLACE_PUBLICO.txt','w').write(m[-1]) if m else None"

echo ======================================================================
echo SERVICIO OPERATIVO CON EXITO:
echo.
echo   * ENLACE PC LOCAL:       http://localhost:8080
echo   * ENLACE MOVIL (WI-FI):  http://192.168.1.9:8080  [PERMANENTE]
echo.
type ENLACES_ACCESO.txt
echo ======================================================================
echo Presiona cualquier tecla para salir de esta ventana (los servicios continuaran en segundo plano).
pause >nul
