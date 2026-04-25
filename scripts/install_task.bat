@echo off
chcp 65001 >nul 2>&1
title ALPHAEDGE - Installation Taches Planifiees
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║        Installation des taches planifiees ALPHAEDGE         ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: ── Verifier les droits admin ──
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Droits administrateur requis. Relance en tant qu^'admin...
    powershell -Command "Start-Process ^'%~f0^' -Verb RunAs"
    exit /b
)

:: ── Variables ──
set "TASK_IB=ALPHAEDGE_IBGateway"
set "TASK_BOT=ALPHAEDGE_Bot"
set "PROJECT_DIR=C:\Users\averr\AlphaEdge"
set "IBGATEWAY_LAUNCHER=%PROJECT_DIR%\scripts\launch_ibgateway.bat"
set "BOT_START_SCRIPT=%PROJECT_DIR%\scripts\start_alphaedge.ps1"
set "PYTHON_EXE=C:\Users\averr\AlphaEdge\.venv\Scripts\pythonw.exe"
set "LOG_DIR=C:\Users\averr\AlphaEdge\alphaedge\logs"

:: ── Verifications prealables ──
if not exist "%IBGATEWAY_LAUNCHER%" (
    echo [ERREUR] Launcher IB Gateway introuvable : %IBGATEWAY_LAUNCHER%
    pause ^& exit /b 1
)
if not exist "%BOT_START_SCRIPT%" (
    echo [ERREUR] Script bot introuvable : %BOT_START_SCRIPT%
    pause ^& exit /b 1
)
if not exist "%PYTHON_EXE%" (
    echo [ERREUR] Python venv introuvable : %PYTHON_EXE%
    pause ^& exit /b 1
)

:: ── Creer le dossier logs ──
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:: ── Supprimer les anciennes taches si elles existent ──
schtasks /query /tn "%TASK_IB%" >nul 2>&1
if %errorlevel% equ 0 (
    echo [*] Suppression ancienne tache %TASK_IB%...
    schtasks /delete /tn "%TASK_IB%" /f >nul 2>&1
)
schtasks /query /tn "%TASK_BOT%" >nul 2>&1
if %errorlevel% equ 0 (
    echo [*] Suppression ancienne tache %TASK_BOT%...
    schtasks /delete /tn "%TASK_BOT%" /f >nul 2>&1
)

:: ════════════════════════════════════════════════════════════
:: TACHE 1 : IB Gateway — demarrage au login
:: ════════════════════════════════════════════════════════════
echo [*] Creation tache %TASK_IB%...

(
echo ^<?xml version="1.0" encoding="UTF-16"?^>
echo ^<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"^>
echo   ^<RegistrationInfo^>
echo     ^<Description^>IB Gateway paper trading ^(port 4002^) auto-start^</Description^>
echo   ^</RegistrationInfo^>
echo   ^<Triggers^>
echo     ^<LogonTrigger^>
echo       ^<Enabled^>true^</Enabled^>
echo     ^</LogonTrigger^>
echo   ^</Triggers^>
echo   ^<Principals^>
echo     ^<Principal id="Author"^>
echo       ^<LogonType^>InteractiveToken^</LogonType^>
echo       ^<RunLevel^>HighestAvailable^</RunLevel^>
echo     ^</Principal^>
echo   ^</Principals^>
echo   ^<Settings^>
echo     ^<MultipleInstancesPolicy^>IgnoreNew^</MultipleInstancesPolicy^>
echo     ^<DisallowStartIfOnBatteries^>false^</DisallowStartIfOnBatteries^>
echo     ^<StopIfGoingOnBatteries^>false^</StopIfGoingOnBatteries^>
echo     ^<AllowHardTerminate^>true^</AllowHardTerminate^>
echo     ^<StartWhenAvailable^>true^</StartWhenAvailable^>
echo     ^<RunOnlyIfNetworkAvailable^>true^</RunOnlyIfNetworkAvailable^>
echo     ^<AllowStartOnDemand^>true^</AllowStartOnDemand^>
echo     ^<Enabled^>true^</Enabled^>
echo     ^<Hidden^>false^</Hidden^>
echo     ^<RunOnlyIfIdle^>false^</RunOnlyIfIdle^>
echo     ^<WakeToRun^>false^</WakeToRun^>
echo     ^<ExecutionTimeLimit^>PT0S^</ExecutionTimeLimit^>
echo     ^<Priority^>7^</Priority^>
echo     ^<RestartOnFailure^>
echo       ^<Interval^>PT2M^</Interval^>
echo       ^<Count^>10^</Count^>
echo     ^</RestartOnFailure^>
echo   ^</Settings^>
echo   ^<Actions Context="Author"^>
echo     ^<Exec^>
echo       ^<Command^>cmd.exe^</Command^>
echo       ^<Arguments^>/c "%PROJECT_DIR%\scripts\launch_ibgateway.bat"^</Arguments^>
echo       ^<WorkingDirectory^>%PROJECT_DIR%\scripts^</WorkingDirectory^>
echo     ^</Exec^>
echo   ^</Actions^>
echo ^</Task^>
) > "%TEMP%\alphaedge_ibgateway.xml"

schtasks /create /tn "%TASK_IB%" /xml "%TEMP%\alphaedge_ibgateway.xml" /f
if %errorlevel% neq 0 (
    echo [ERREUR] Impossible de creer la tache %TASK_IB% !
    pause ^& exit /b 1
)
echo [OK] Tache %TASK_IB% creee.

:: ════════════════════════════════════════════════════════════
:: TACHE 2 : Bot ALPHAEDGE — login + lundi 15h00 heure locale
:: (relance automatique apres le shutdown weekend du vendredi)
:: ════════════════════════════════════════════════════════════
echo [*] Creation tache %TASK_BOT%...

(
echo ^<?xml version="1.0" encoding="UTF-16"?^>
echo ^<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"^>
echo   ^<RegistrationInfo^>
echo     ^<Description^>ALPHAEDGE Bot paper trading — login + lundi 15h00 auto-start^</Description^>
echo   ^</RegistrationInfo^>
echo   ^<Triggers^>
echo     ^<LogonTrigger^>
echo       ^<Enabled^>true^</Enabled^>
echo       ^<Delay^>PT1M30S^</Delay^>
echo     ^</LogonTrigger^>
echo     ^<CalendarTrigger^>
echo       ^<StartBoundary^>2026-04-27T15:00:00^</StartBoundary^>
echo       ^<Enabled^>true^</Enabled^>
echo       ^<ScheduleByWeek^>
echo         ^<WeeksInterval^>1^</WeeksInterval^>
echo         ^<DaysOfWeek^>
echo           ^<Monday /^>
echo         ^</DaysOfWeek^>
echo       ^</ScheduleByWeek^>
echo     ^</CalendarTrigger^>
echo   ^</Triggers^>
echo   ^<Principals^>
echo     ^<Principal id="Author"^>
echo       ^<LogonType^>InteractiveToken^</LogonType^>
echo       ^<RunLevel^>HighestAvailable^</RunLevel^>
echo     ^</Principal^>
echo   ^</Principals^>
echo   ^<Settings^>
echo     ^<MultipleInstancesPolicy^>IgnoreNew^</MultipleInstancesPolicy^>
echo     ^<DisallowStartIfOnBatteries^>false^</DisallowStartIfOnBatteries^>
echo     ^<StopIfGoingOnBatteries^>false^</StopIfGoingOnBatteries^>
echo     ^<AllowHardTerminate^>true^</AllowHardTerminate^>
echo     ^<StartWhenAvailable^>true^</StartWhenAvailable^>
echo     ^<RunOnlyIfNetworkAvailable^>true^</RunOnlyIfNetworkAvailable^>
echo     ^<AllowStartOnDemand^>true^</AllowStartOnDemand^>
echo     ^<Enabled^>true^</Enabled^>
echo     ^<Hidden^>false^</Hidden^>
echo     ^<RunOnlyIfIdle^>false^</RunOnlyIfIdle^>
echo     ^<WakeToRun^>false^</WakeToRun^>
echo     ^<ExecutionTimeLimit^>PT0S^</ExecutionTimeLimit^>
echo     ^<Priority^>7^</Priority^>
echo     ^<RestartOnFailure^>
echo       ^<Interval^>PT5M^</Interval^>
echo       ^<Count^>999^</Count^>
echo     ^</RestartOnFailure^>
echo   ^</Settings^>
echo   ^<Actions Context="Author"^>
echo     ^<Exec^>
echo       ^<Command^>powershell.exe^</Command^>
echo       ^<Arguments^>-ExecutionPolicy Bypass -File "%BOT_START_SCRIPT%"^</Arguments^>
echo       ^<WorkingDirectory^>%PROJECT_DIR%^</WorkingDirectory^>
echo     ^</Exec^>
echo   ^</Actions^>
echo ^</Task^>
) > "%TEMP%\alphaedge_bot.xml"

schtasks /create /tn "%TASK_BOT%" /xml "%TEMP%\alphaedge_bot.xml" /f
if %errorlevel% neq 0 (
    echo [ERREUR] Impossible de creer la tache %TASK_BOT% !
    pause ^& exit /b 1
)
echo [OK] Tache %TASK_BOT% creee.

:: ── Demarrage immediat ──
echo.
echo [*] Demarrage IB Gateway...
schtasks /run /tn "%TASK_IB%"
echo [*] Bot demarrera dans 90s automatiquement.

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                    Installation reussie !                    ║
echo ╠══════════════════════════════════════════════════════════════╣
echo ║  ALPHAEDGE_IBGateway  →  demarre au login                   ║
echo ║  ALPHAEDGE_Bot        →  demarre 90s apres le login          ║
echo ║                        +  chaque lundi a 15h00 heure locale  ║
echo ║                           (relance apres shutdown weekend)    ║
echo ║                                                              ║
echo ║  Utilisez manage_task.bat pour gerer les taches              ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
del "%TEMP%\alphaedge_ibgateway.xml" >nul 2>&1
del "%TEMP%\alphaedge_bot.xml" >nul 2>&1
pause