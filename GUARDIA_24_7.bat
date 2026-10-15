@echo off
title GUARDIA 24/7 - CENTRO DE COMANDO EDTECH
color 0A
echo ======================================================================
echo    ESCUDO DE ALTA DISPONIBILIDAD 24/7 - CONSULTORIA EDTECH
echo ======================================================================
echo  Vigilando continuamente en segundo plano:
echo   [OK] Servidor Backend FastAPI (app_visual.py)
echo   [OK] Firewall WAF de Inspeccion Profunda
echo   [OK] Tunel Mundial HTTPS Cloudflare Edge
echo.
echo  Si algun servicio sufre interrupcion, sera reiniciado en segundos.
echo  Minimiza esta ventana para mantener la operacion activa 24/7.
echo ======================================================================
echo.
powershell.exe -ExecutionPolicy Bypass -NoProfile -File "%~dp0GUARDIA_24_7.ps1"
pause
