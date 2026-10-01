@echo off
REM ==================================================================
REM  Puts a "WashO" shortcut on your Desktop that runs start.bat.
REM  Run it once (double-click). Safe to run again: it just replaces it.
REM ==================================================================
setlocal
cd /d "%~dp0"

REM Desktop path is asked from Windows, so it also works when the Desktop is in OneDrive.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$desk = [Environment]::GetFolderPath('Desktop');" ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desk 'WashO.lnk'));" ^
  "$s.TargetPath = Join-Path '%~dp0' 'start.bat';" ^
  "$s.WorkingDirectory = '%~dp0';" ^
  "$s.Description = 'Start the WashO laundry website';" ^
  "$s.IconLocation = \"$env:SystemRoot\System32\shell32.dll,13\";" ^
  "$s.Save();" ^
  "Write-Host ('  Shortcut created: ' + (Join-Path $desk 'WashO.lnk'))"

if errorlevel 1 (
    echo   ERROR: Could not create the shortcut.
) else (
    echo   Double-click "WashO" on your Desktop to start the website.
)
echo.
pause
