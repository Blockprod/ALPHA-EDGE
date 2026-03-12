@echo off
chcp 65001 >nul 2>&1
title ALPHAEDGE - Désinstallation
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║        Désinstallation des tâches planifiées ALPHAEDGE      ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: ── Vérifier les droits admin ──
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Droits administrateur requis. Relance en tant qu'admin...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

set "TASK_IB=ALPHAEDGE_IBGateway"
set "TASK_BOT=ALPHAEDGE_Bot"

echo [!] Cette opération va arrêter et supprimer les tâches suivantes :
echo     - %TASK_IB%
echo     - %TASK_BOT%
echo.
set /p CONFIRM=Confirmer la désinstallation ? (o/N) :
if /i not "%CONFIRM%"=="o" (
    echo Annulé.
    pause & exit /b 0
)

echo.
echo [*] Arrêt du bot...
schtasks /end /tn "%TASK_BOT%" >nul 2>&1

echo [*] Arrêt IB Gateway...
schtasks /end /tn "%TASK_IB%" >nul 2>&1

timeout /t 2 >nul

echo [*] Suppression tâche %TASK_BOT%...
schtasks /delete /tn "%TASK_BOT%" /f >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Tâche %TASK_BOT% supprimée.
) else (
    echo [INFO] Tâche %TASK_BOT% déjà absente ou non trouvée.
)

echo [*] Suppression tâche %TASK_IB%...
schtasks /delete /tn "%TASK_IB%" /f >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Tâche %TASK_IB% supprimée.
) else (
    echo [INFO] Tâche %TASK_IB% déjà absente ou non trouvée.
)

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║              Désinstallation terminée.                       ║
echo ║  IB Gateway et le bot ne démarreront plus automatiquement.  ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
pause
