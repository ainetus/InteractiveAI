@echo off
echo ======================================================
echo  InteractiveAI Railway - Checking prerequisites...
echo ======================================================
echo.

REM Check Docker
docker --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [MISSING] Docker Desktop is not installed.
    echo          Please install it from: https://www.docker.com/products/docker-desktop
    echo          Then restart this script.
    start https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
) ELSE (
    echo [OK] Docker found.
)

REM Check Python 3.10
python --version 2>&1 | findstr /C:"3.10" >nul
IF %ERRORLEVEL% NEQ 0 (
    echo [MISSING] Python 3.10 not found.
    echo          Opening download page...
    echo          IMPORTANT: Check "Add Python to PATH" during install!
    start https://www.python.org/downloads/release/python-31011/
    echo          After installing Python 3.10, restart this script.
    pause
    exit /b 1
) ELSE (
    echo [OK] Python 3.10 found.
)

REM Check Node.js
node --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [MISSING] Node.js not found.
    echo          Opening download page...
    start https://nodejs.org/
    echo          After installing Node.js, restart this script.
    pause
    exit /b 1
) ELSE (
    echo [OK] Node.js found.
)

echo.
echo All prerequisites found. Starting installation...
echo.
REM ============================================================
REM InteractiveAI Railway - One-time installation
REM Double-click to run. Requires Python 3.10 and Node.js.
REM ============================================================

SET SCRIPT_DIR=%~dp0
SET RAILWAY_DIR=%SCRIPT_DIR%usecases_examples\Railway
SET ZWL_DIR=%SCRIPT_DIR%flatland-hmi-hack4rail\frontend

echo ======================================================
echo  InteractiveAI Railway - Installation
echo ======================================================

REM 1. Python virtual environment
echo.
echo [1/3] Setting up Python environment...
cd /d "%RAILWAY_DIR%"

IF NOT EXIST ".venv" (
    python -m venv .venv
    echo       Virtual environment created.
) ELSE (
    echo       Virtual environment already exists, skipping.
)

call .venv\Scripts\activate.bat
pip install -r requirements.txt
echo       Python dependencies installed.

REM 2. Node dependencies
echo.
echo [2/3] Installing Angular ZWL dependencies...
cd /d "%ZWL_DIR%"
call npm install --silent
echo       Node dependencies installed.

REM 3. Docker check
echo.
echo [3/3] Checking Docker...
docker --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo       ERROR: Docker not found. Please install Docker Desktop.
    echo       https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)
echo       Docker found.

echo.
echo ======================================================
echo  Installation complete!
echo  Run start.bat to launch the application.
echo ======================================================
pause
