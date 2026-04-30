@echo off
setlocal

REM ── Weekend guard ── Do not launch IB Gateway on Saturday/Sunday
REM    Market closed: Friday evening to Sunday evening
for /f "tokens=2 delims==" %%a in ('wmic path win32_localtime get dayofweek /value 2^>nul ^| find "="') do set "DOW=%%a"
if "%DOW%"=="0" exit /b 0
if "%DOW%"=="6" exit /b 0

REM ── Already running: skip duplicate launch ──
tasklist /FO CSV /NH | findstr /I /C:"ibgateway.exe" /C:"ibgateway1.exe" >nul
if %errorlevel% equ 0 exit /b 0

set "IBC_LAUNCHER=C:\IBC\StartGatewayAlphaEdge.bat"
set "GATEWAY_DIR=C:\Jts\ibgateway\1044"
set "GATEWAY_EXE=%GATEWAY_DIR%\ibgateway.exe"
set "GATEWAY_EXE_ALT=%GATEWAY_DIR%\ibgateway1.exe"

REM ── Preferred path: IBC launcher handles authentication + daily restart ──
if exist "%IBC_LAUNCHER%" (
	start "" cmd /c "%IBC_LAUNCHER%"
	exit /b 0
)

REM ── Fallback path: direct native executable if IBC is not installed ──
if exist "%GATEWAY_EXE_ALT%" (
	start "" "%GATEWAY_EXE_ALT%"
	exit /b 0
)

if exist "%GATEWAY_EXE%" (
	start "" "%GATEWAY_EXE%"
	exit /b 0
)

echo [ERREUR] Aucun launcher IB Gateway valide trouve.
exit /b 1
