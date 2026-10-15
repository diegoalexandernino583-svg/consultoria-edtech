# =====================================================================
# GUARDIA 24/7 - SISTEMA DE ALTA DISPONIBILIDAD Y AUTO-RECUPERACIÓN
# =====================================================================
$ErrorActionPreference = "SilentlyContinue"
$directorio = "C:\Users\Dieguito\OneDrive\Documentos\consultoria_visual"
$logFile = "$directorio\guardia_24_7.log"
$cloudflaredPath = "C:\Users\Dieguito\AppData\Local\cloudflared.exe"

function Escribir-Log($mensaje) {
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $linea = "[$timestamp] $mensaje"
    Write-Host $linea
    try {
        Add-Content -Path $logFile -Value $linea
    } catch {}
}

Escribir-Log ">>> SERVICIO GUARDIA 24/7 INICIADO - VIGILANCIA PERMANENTE ACTIVA"

while ($true) {
    # 1. Verificar Servidor Web FastAPI (app_visual.py en puerto 8080)
    $puertoActivo = $false
    try {
        $conexion = Test-NetConnection -ComputerName "127.0.0.1" -Port 8080 -WarningAction SilentlyContinue
        if ($conexion.TcpTestSucceeded) {
            $puertoActivo = $true
        }
    } catch {
        $puertoActivo = $false
    }

    if (-not $puertoActivo) {
        Escribir-Log "⚠️ Servidor FastAPI detenido o no responde. Reiniciando de inmediato..."
        Start-Process -FilePath "python" -ArgumentList "app_visual.py" -WorkingDirectory $directorio -WindowStyle Hidden
        Start-Sleep -Seconds 5
        Escribir-Log "✓ Servidor FastAPI reactivado exitosamente."
    }

    # 2. Verificar Cloudflare Tunnel (cloudflared.exe)
    $procesoCf = Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue
    if (-not $procesoCf) {
        if (Test-Path $cloudflaredPath) {
            Escribir-Log "⚠️ Túnel Cloudflare detenido. Reconectando enlace HTTPS público..."
            Start-Process -FilePath $cloudflaredPath -ArgumentList "tunnel --url http://127.0.0.1:8080 --no-autoupdate --logfile C:\Users\Dieguito\AppData\Local\cloudflared_tunnel.log" -WindowStyle Hidden
            Start-Sleep -Seconds 5
            Escribir-Log "✓ Túnel Cloudflare HTTPS reactivado."
        }
    }

    # Esperar 20 segundos antes del siguiente ciclo de monitoreo
    Start-Sleep -Seconds 20
}
