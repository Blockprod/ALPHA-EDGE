@echo off
REM ── Weekend guard ── Do not launch IB Gateway on Saturday/Sunday
REM    Market closed: Friday evening to Sunday evening
for /f "tokens=2 delims==" %%a in ('wmic path win32_localtime get dayofweek /value 2^>nul ^| find "="') do set "DOW=%%a"
if "%DOW%"=="0" exit /b 0
if "%DOW%"=="6" exit /b 0

REM ── Weekday: launch IB Gateway ──
start "" "C:\Jts\ibgateway\1044\ibgateway.exe"
