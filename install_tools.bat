@echo off
setlocal enabledelayedexpansion

:: ==============================================================================
:: MIDI Goblin Tool Installer (Windows)
:: ==============================================================================
:: Automatically sets up Python pip packages (esptool, pyserial) for flashing.
:: ==============================================================================

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo ========================================================
echo  MIDI Goblin Tools Setup (Windows)
echo ========================================================
echo.

:: Detect Python executable
set "PYTHON_CMD="

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=python"
) else (
    where py >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        set "PYTHON_CMD=py -3"
    )
)

if "%PYTHON_CMD%"=="" (
    echo [!] Python 3 was not found in your system PATH.
    echo.
    echo Checking if Windows Package Manager (winget) is available...
    where winget >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo [INFO] winget is available! You can install Python automatically by running:
        echo        winget install Python.Python.3.12
        echo.
        set /p INSTALL_PY="Would you like to install Python now using winget? (Y/N): "
        if /i "!INSTALL_PY!"=="Y" (
            winget install Python.Python.3.12
            echo.
            echo Note: You must close and reopen this terminal (or window) after
            echo installing Python so your system PATH environment updates.
            goto :finish
        )
    )
    echo Please install Python 3 manually:
    echo 1. Download from https://www.python.org/downloads/
    echo 2. Check the box "Add python.exe to PATH" during installation!
    echo.
    goto :finish
)

echo [1/3] Found Python: %PYTHON_CMD%
%PYTHON_CMD% --version

echo.
echo [2/3] Installing / Upgrading pip, esptool, and pyserial...
%PYTHON_CMD% -m pip install --upgrade pip
%PYTHON_CMD% -m pip install --upgrade esptool pyserial

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Installation encountered an issue. Trying with --user flag...
    %PYTHON_CMD% -m pip install --user --upgrade esptool pyserial
)

echo.
echo [3/3] Verifying esptool installation...
%PYTHON_CMD% -m esptool version
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo  SUCCESS: Flashing tools are installed and ready!
    echo ========================================================
    echo.
    echo Next steps:
    echo  1. Connect your MIDI Goblin via USB.
    echo  2. Double-click "flash.bat" (or run "python flash.py").
    echo.
    echo Note for Windows users:
    echo  If your device COM port is not recognized, install the driver
    echo  for your USB-UART chip:
    echo  - CP2102: Silicon Labs CP210x Universal Windows Driver
    echo  - CH340 / CH341: WCH CH341SER Driver
    echo.
) else (
    echo.
    echo [!] esptool verification failed. Please ensure Python and pip are working properly.
)

:finish
pause
