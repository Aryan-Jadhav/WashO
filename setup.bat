@echo off
REM ==================================================================
REM  WashO one-time setup for a Windows computer.
REM  Double-click this file, or run "setup.bat" in the project folder.
REM  It is safe to run again: steps that are already done are skipped.
REM ==================================================================
setlocal
cd /d "%~dp0"
echo.
echo ============ WashO setup ============
echo.

REM --- 1. Find a supported Python (3.12, 3.13 or 3.14) ----------------
echo [1/6] Looking for Python 3.12 - 3.14 ...
set "PY="
for %%V in (3.14 3.13 3.12) do (
    if not defined PY (
        py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
    )
)
if not defined PY (
    python -c "import sys" >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo   ERROR: Python was not found.
    echo   Install Python 3.12, 3.13 or 3.14 from https://www.python.org/downloads/
    echo   and tick "Add python.exe to PATH" in the installer. Then run setup.bat again.
    goto :fail
)
%PY% -c "import sys; sys.exit(0 if (3, 12) <= sys.version_info[:2] <= (3, 14) else 1)"
if errorlevel 1 (
    echo   ERROR: This Python version is not supported:
    %PY% --version
    echo   Please install Python 3.12, 3.13 or 3.14 and run setup.bat again.
    goto :fail
)
for /f "delims=" %%P in ('%PY% --version') do echo   Found %%P  ^(using "%PY%"^)

REM --- 2. Create the virtual environment -------------------------------
echo.
echo [2/6] Creating virtual environment "venv" ...
if exist "venv\Scripts\python.exe" (
    REM A venv copied from another computer does not work - detect and rebuild it.
    "venv\Scripts\python.exe" -c "import sys" >nul 2>&1
    if errorlevel 1 (
        echo   Existing venv is broken ^(probably copied from another PC^). Rebuilding ...
        rmdir /s /q venv
    ) else (
        echo   venv already exists - skipping.
    )
)
if not exist "venv\Scripts\python.exe" (
    %PY% -m venv venv
    if errorlevel 1 ( echo   ERROR: could not create venv. & goto :fail )
    echo   venv created.
)

REM --- 3. Install the exact package versions ---------------------------
echo.
echo [3/6] Installing packages from requirements.txt (needs internet) ...
"venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
"venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
if errorlevel 1 ( echo   ERROR: package installation failed. Check your internet connection. & goto :fail )
echo   Packages installed.

REM --- 4. Create .env from the template ---------------------------------
echo.
echo [4/6] Preparing the .env settings file ...
"venv\Scripts\python.exe" scripts\make_env.py
findstr /C:"PUT_YOUR_DB_PASSWORD_HERE" .env >nul
if not errorlevel 1 (
    echo.
    echo   ACTION NEEDED: open the file ".env" in Notepad and replace
    echo   PUT_YOUR_DB_PASSWORD_HERE with the password of the PostgreSQL user washo_user.
    echo   Save it, then run setup.bat again.
    goto :fail
)

REM --- 5. Check the database connection ---------------------------------
echo.
echo [5/6] Checking the PostgreSQL connection ...
"venv\Scripts\python.exe" scripts\check_db.py
if errorlevel 1 (
    echo   Fix the problem above ^(see README: "Run on a new computer"^), then run setup.bat again.
    goto :fail
)

REM --- 6. Create / update the database tables ---------------------------
echo.
echo [6/6] Applying database migrations ...
"venv\Scripts\python.exe" manage.py migrate
if errorlevel 1 ( echo   ERROR: migrations failed. & goto :fail )

REM (Phase 8 will add: load demo data with "manage.py seed_demo")

echo.
echo ============ Setup complete ============
echo  Next steps:
echo    1. Create your admin login (once):  venv\Scripts\python manage.py createsuperuser
echo    2. Start the website:              venv\Scripts\python manage.py runserver
echo    3. Open http://127.0.0.1:8000 in your browser.
echo.
pause
exit /b 0

:fail
echo.
echo ============ Setup stopped ============
pause
exit /b 1
