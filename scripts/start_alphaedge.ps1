# ============================================================
# ALPHAEDGE — Auto-start script (appele par install_task.bat)
# Ne pas lancer directement — utiliser manage_task.bat
# ============================================================

$ProjectDir = "C:\Users\averr\AlphaEdge"
$VenvPython = "$ProjectDir\.venv\Scripts\python.exe"
$LogDir     = "$ProjectDir\alphaedge\logs"
$LogFile    = "$LogDir\alphaedge_bot.log"

# Ensure log directory exists
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  $msg" | Tee-Object -FilePath $LogFile -Append
}

Write-Log "=== ALPHAEDGE startup script ==="
Write-Log "Starting ALPHAEDGE bot (gateway health check handled by Python)..."

# Brief pause to let Windows Task Scheduler finish launching IB Gateway
Start-Sleep -Seconds 15

Write-Log "Starting ALPHAEDGE paper trading bot..."
Set-Location $ProjectDir

& $VenvPython -m alphaedge --mode paper *>> $LogFile

Write-Log "ALPHAEDGE process exited (code $LASTEXITCODE)"
