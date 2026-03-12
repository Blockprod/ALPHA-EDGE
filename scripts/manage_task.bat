@echo off
chcp 65001 >nul 2>&1
setlocal

set "TASK_IB=ALPHAEDGE_IBGateway"
set "TASK_BOT=ALPHAEDGE_Bot"
set "LOG_DIR=C:\Users\averr\AlphaEdge\alphaedge\logs"
set "PROJECT_DIR=C:\Users\averr\AlphaEdge"
set "PYTHON_EXE=C:\Users\averr\AlphaEdge\.venv\Scripts\python.exe"

:MENU
cls
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║             ALPHAEDGE — Gestion des tâches                  ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: Afficher le statut des deux tâches
call :STATUS_INLINE %TASK_IB%  IB_STATUS
call :STATUS_INLINE %TASK_BOT% BOT_STATUS

echo   IB Gateway  : %IB_STATUS%
echo   Bot         : %BOT_STATUS%
echo.
echo   ──────────────────────────────────────────────
echo   1. Statut détaillé des tâches
echo   2. Démarrer IB Gateway + Bot
echo   3. Arrêter le bot
echo   4. Arrêter IB Gateway
echo   5. Voir les dernières lignes du log
echo   6. Suivre le log en temps réel (Ctrl+C pour sortir)
echo   7. Lancer le bot en mode console (paper)
echo   8. Ouvrir le Planificateur de tâches Windows
echo   9. Quitter
echo.
set /p CHOICE=Votre choix [1-9] :

if "%CHOICE%"=="1" goto OPT_STATUS
if "%CHOICE%"=="2" goto OPT_START
if "%CHOICE%"=="3" goto OPT_STOP_BOT
if "%CHOICE%"=="4" goto OPT_STOP_IB
if "%CHOICE%"=="5" goto OPT_LOG
if "%CHOICE%"=="6" goto OPT_TAIL
if "%CHOICE%"=="7" goto OPT_CONSOLE
if "%CHOICE%"=="8" goto OPT_TASKSCHD
if "%CHOICE%"=="9" goto END
goto MENU

:OPT_STATUS
cls
echo.
echo ══ Statut IB Gateway ══════════════════════════════════════════
schtasks /query /tn "%TASK_IB%" /v /fo list 2>nul || echo   [!] Tâche introuvable
echo.
echo ══ Statut Bot ══════════════════════════════════════════════════
schtasks /query /tn "%TASK_BOT%" /v /fo list 2>nul || echo   [!] Tâche introuvable
echo.
pause
goto MENU

:OPT_START
echo.
echo [*] Démarrage IB Gateway...
schtasks /run /tn "%TASK_IB%"
if %errorlevel% neq 0 (
    echo [ERREUR] Impossible de démarrer la tâche %TASK_IB%.
    echo          Avez-vous exécuté install_task.bat ^(en admin^) ?
) else (
    echo [OK] IB Gateway démarré.
)
timeout /t 5 >nul
echo [*] Démarrage Bot...
schtasks /run /tn "%TASK_BOT%"
if %errorlevel% neq 0 (
    echo [ERREUR] Impossible de démarrer la tâche %TASK_BOT%.
) else (
    echo [OK] Bot démarré.
)
pause
goto MENU

:OPT_STOP_BOT
echo.
echo [*] Arrêt du bot...
schtasks /end /tn "%TASK_BOT%" >nul 2>&1
echo [OK] Signal d'arrêt envoyé au bot.
pause
goto MENU

:OPT_STOP_IB
echo.
echo [!] Attention : arrêter IB Gateway coupera aussi le bot.
set /p CONFIRM=Confirmer ? (o/N) :
if /i "%CONFIRM%"=="o" (
    schtasks /end /tn "%TASK_BOT%" >nul 2>&1
    schtasks /end /tn "%TASK_IB%" >nul 2>&1
    echo [OK] IB Gateway et Bot arrêtés.
) else (
    echo Annulé.
)
pause
goto MENU

:OPT_LOG
cls
echo.
echo ══ Dernières lignes de log ═══════════════════════════════════
for /f "delims=" %%F in ('dir /b /o-d "%LOG_DIR%\*.log" 2^>nul') do (
    echo [Fichier: %%F]
    powershell -Command "Get-Content '%LOG_DIR%\%%F' -Tail 40 -ErrorAction SilentlyContinue"
    goto :OPT_LOG_DONE
)
echo [!] Aucun log trouvé dans %LOG_DIR%
:OPT_LOG_DONE
echo.
pause
goto MENU

:OPT_TAIL
cls
echo Ctrl+C pour revenir au menu.
echo ══════════════════════════════════════════════════════════════
for /f "delims=" %%F in ('dir /b /o-d "%LOG_DIR%\*.log" 2^>nul') do (
    powershell -Command "Get-Content '%LOG_DIR%\%%F' -Tail 20 -Wait -ErrorAction SilentlyContinue"
    goto :OPT_TAIL_DONE
)
echo [!] Aucun log pour l'instant. Le bot est-il démarré ?
pause
:OPT_TAIL_DONE
goto MENU

:OPT_CONSOLE
cls
echo [*] Lancement du bot en mode console (paper)...
echo     Ctrl+C pour arrêter.
echo.
cd /d "%PROJECT_DIR%"
"%PYTHON_EXE%" -m alphaedge.engine.strategy --mode paper
echo.
echo [*] Bot arrêté.
pause
goto MENU

:OPT_TASKSCHD
start taskschd.msc
goto MENU

:STATUS_INLINE
:: %1 = task name, %2 = variable to set result
schtasks /query /tn "%~1" /fo csv >nul 2>&1
if %errorlevel% neq 0 (
    set "%~2=[NON INSTALLÉE]"
    goto :eof
)
for /f "tokens=4 delims=," %%S in ('schtasks /query /tn "%~1" /fo csv ^| findstr /v "TaskName"') do (
    set "%~2=%%~S"
    goto :eof
)
set "%~2=[inconnu]"
goto :eof

:END
endlocal
