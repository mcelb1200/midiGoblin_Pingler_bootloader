@echo off
setlocal

:: Resolve directory where this batch file lives
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

:: Check if python is available
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python flash.py %*
    goto :end
)

:: Check if py launcher is available
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3 flash.py %*
    goto :end
)

echo ========================================================
echo  MIDI Goblin Dual Consolidated Firmware Flasher
echo ========================================================
echo.
echo [ERROR] Python 3 was not found in your system PATH.
echo Please install Python 3 from https://www.python.org/
echo (Ensure "Add Python to PATH" is checked during installation)
echo.
pause
exit /b 1

:end
if %ERRORLEVEL% NEQ 0 (
    pause
)
