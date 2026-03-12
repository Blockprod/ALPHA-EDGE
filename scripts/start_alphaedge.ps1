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
Write-Log "Waiting 90s for IB Gateway to finish initialising..."
Start-Sleep -Seconds 90

# Verify IB Gateway is reachable (TCP port 4002)
$maxRetries = 10
$retryDelay = 15
$connected  = $false
for ($i = 1; $i -le $maxRetries; $i++) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", 4002)
        $tcp.Close()
        Write-Log "IB Gateway port 4002 reachable (attempt $i/$maxRetries)"
        $connected = $true
        break
    } catch {
        Write-Log "Port 4002 not ready yet (attempt $i/$maxRetries) — waiting ${retryDelay}s"
        Start-Sleep -Seconds $retryDelay
    }
}

if (-not $connected) {
    Write-Log "ERROR: IB Gateway port 4002 unreachable after $maxRetries attempts — aborting"
    exit 1
}

Write-Log "Starting ALPHAEDGE paper trading bot..."
Set-Location $ProjectDir

& $VenvPython -m alphaedge.engine.strategy --mode paper *>> $LogFile

Write-Log "ALPHAEDGE process exited (code $LASTEXITCODE)"
