# ============================================================
# ALPHAEDGE — Enregistrement des tâches planifiées Windows
# LANCER CE SCRIPT EN TANT QU'ADMINISTRATEUR
# Clic droit → "Exécuter avec PowerShell en tant qu'administrateur"
# ============================================================

$IBGatewayExe = "C:\Jts\ibgateway\1044\ibgateway.exe"
$StartScript  = "C:\Users\averr\AlphaEdge\scripts\start_alphaedge.ps1"

# Vérifications préalables
if (-not (Test-Path $IBGatewayExe)) {
    Write-Host "ERREUR: ibgateway.exe introuvable à $IBGatewayExe" -ForegroundColor Red
    Read-Host "Appuie sur Entrée pour quitter"
    exit 1
}
if (-not (Test-Path $StartScript)) {
    Write-Host "ERREUR: start_alphaedge.ps1 introuvable à $StartScript" -ForegroundColor Red
    Read-Host "Appuie sur Entrée pour quitter"
    exit 1
}

# ── Tâche 1 : IB Gateway ──────────────────────────────────────────
$ibAction   = New-ScheduledTaskAction -Execute $IBGatewayExe
$ibTrigger  = New-ScheduledTaskTrigger -AtStartup
$ibSettings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit  (New-TimeSpan -Hours 0) `
    -RestartCount        3 `
    -RestartInterval     (New-TimeSpan -Minutes 2) `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName    "ALPHAEDGE_IBGateway" `
    -Action      $ibAction `
    -Trigger     $ibTrigger `
    -Settings    $ibSettings `
    -RunLevel    Highest `
    -Description "IB Gateway paper trading — auto-start on boot" `
    -Force | Out-Null

Write-Host "OK  Tache creee : ALPHAEDGE_IBGateway" -ForegroundColor Green

# ── Tâche 2 : Bot ALPHAEDGE ──────────────────────────────────────
$botAction   = New-ScheduledTaskAction `
    -Execute  "powershell.exe" `
    -Argument "-NonInteractive -ExecutionPolicy Bypass -File `"$StartScript`""

$botTrigger  = New-ScheduledTaskTrigger -AtStartup
$botSettings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit  (New-TimeSpan -Hours 0) `
    -RestartCount        5 `
    -RestartInterval     (New-TimeSpan -Minutes 5) `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName    "ALPHAEDGE_Bot" `
    -Action      $botAction `
    -Trigger     $botTrigger `
    -Settings    $botSettings `
    -RunLevel    Highest `
    -Description "ALPHAEDGE paper trading bot — auto-start on boot" `
    -Force | Out-Null

Write-Host "OK  Tache creee : ALPHAEDGE_Bot" -ForegroundColor Green

# ── Résumé ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Taches enregistrees ===" -ForegroundColor Cyan
schtasks /query /fo TABLE /tn "ALPHAEDGE_IBGateway"
schtasks /query /fo TABLE /tn "ALPHAEDGE_Bot"

Write-Host ""
Write-Host "Terminé. Les deux taches demarreront automatiquement au prochain reboot." -ForegroundColor Cyan
Read-Host "Appuie sur Entrée pour fermer"
