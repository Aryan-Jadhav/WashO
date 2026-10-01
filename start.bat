@echo off
REM ==================================================================
REM  Start WashO: double-click this file.
REM  It checks the database, applies new database changes, starts the
REM  website and opens it in your browser. Close the window to stop.
REM  (Run setup.bat once first on a new computer.)
REM ==================================================================
setlocal
cd /d "%~dp0"
title WashO
set "PY=venv\Scripts\python.exe"
set "URL=http://127.0.0.1:8000/"

echo.
echo ================ Starting WashO ================
echo.

REM --- 1. Is the project set up? -------------------------------------
if not exist "%PY%" (
    echo   ERROR: The virtual environment "venv" was not found.
    echo   Please double-click setup.bat first, then start WashO again.
    goto :fail
)
if not exist ".env" (
    echo   ERROR: The settings file ".env" was not found.
    echo   Please double-click setup.bat first, then start WashO again.
    goto :fail
)

REM --- 2. Is WashO already running? -----------------------------------
netstat -ano | findstr /R /C:"127\.0\.0\.1:8000 .*LISTENING" >nul
if not errorlevel 1 (
    echo   WashO already seems to be running ^(port 8000 is in use^).
    echo   Opening it in your browser ...
    if not "%WASHO_NO_BROWSER%"=="1" start "" "%URL%"
    echo.
    echo   If the page does not load, close the other WashO window and try again.
    goto :fail
)

REM --- 3. Is PostgreSQL running and reachable? -------------------------
echo [1/3] Checking the database ...
"%PY%" scripts\check_db.py >nul 2>&1
if errorlevel 1 (
    echo.
    echo   ERROR: Can't connect to the PostgreSQL database.
    echo.
    echo   Most likely PostgreSQL is not running. To start it:
    echo     1. Press Windows key + R, type  services.msc  and press Enter.
    echo     2. Find "postgresql-x64-18" ^(or -17^) in the list.
    echo     3. Right-click it and choose Start.
    echo   Then double-click start.bat again.
    echo.
    echo   Details:
    "%PY%" scripts\check_db.py
    goto :fail
)
echo   Database OK.

REM --- 4. Apply any new database changes ------------------------------
echo [2/3] Applying database updates ...
"%PY%" manage.py migrate --noinput
if errorlevel 1 (
    echo   ERROR: Database update ^(migrate^) failed. See the message above.
    goto :fail
)

REM --- 5. Open the browser once the server answers, then run the server --
echo [3/3] Starting the website ...
start "" /b "%PY%" scripts\open_browser.py "%URL%"

echo.
echo ===============================================================
echo    WashO is running.  Close this window to stop it.
echo    Website:  %URL%
echo    Admin:    %URL%admin/
echo ===============================================================
echo.
"%PY%" manage.py runserver 127.0.0.1:8000
REM runserver only returns here if it crashed or could not start.
echo.
echo   ERROR: The WashO server stopped unexpectedly. See the message above.
goto :fail

:fail
echo.
pause
exit /b 1
