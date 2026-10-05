@echo off
IF "%1"=="" ( cd /d "%~dp0" )

SET SCRIPT_DIR=%~dp0
SET RAILWAY_DIR=%SCRIPT_DIR%usecases_examples\Railway
SET ZWL_DIR=%SCRIPT_DIR%flatland-hmi-hack4rail\frontend

echo ======================================================
echo  InteractiveAI Railway - Starting...
echo ======================================================

REM Step 1: Docker
echo.
echo [1/4] Starting Docker services...
SET USER_ID=1000
SET USER_GID=1000
SET SPRING_PROFILES_ACTIVE=docker
SET VITE_RAILWAY_SIMU=http://localhost:5001

docker compose -f "%SCRIPT_DIR%config\dev\cab-standalone\docker-compose.yml" -f "%SCRIPT_DIR%config\dev\cab-standalone\docker-compose-hub.yml" up -d
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker failed to start. Is Docker Desktop running?
    pause
    exit /b 1
)

echo       Waiting 25 seconds for services to initialize...
timeout /t 25 /nobreak >nul

REM Step 2: MongoDB perimeter
echo.
echo [2/4] Configuring database...
docker exec cab-standalone-mongodb-1 mongo operator-fabric -u root -p password --authenticationDatabase admin --eval "db.perimeter.updateOne({_id:'cabProcess'},{$set:{process:'cabProcess',stateRights:[{state:'messageState',right:'ReceiveAndWrite'}]}},{upsert:true}); db.group.updateOne({_id:'Planner'},{$addToSet:{perimeters:'cabProcess'}}); db.group.updateOne({_id:'Dispatcher'},{$addToSet:{perimeters:'cabProcess'}}); print('done')"

REM Step 3: Load business config (works with or without Git Bash)
echo.
echo [3/4] Loading business configuration...
WHERE bash >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    bash "%SCRIPT_DIR%resources/loadTestConf.sh"
) ELSE (
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%setup_config.ps1"
)
echo       Configuration loaded.

REM Step 4: Flask and Angular
echo.
echo [4/4] Starting Railway brain and ZWL frontend...
start "Flask Railway Brain" cmd /k "cd /d "%RAILWAY_DIR%" && "%RAILWAY_DIR%\.venv\Scripts\python.exe" app.py"
timeout /t 3 /nobreak >nul
start "Angular ZWL" cmd /k "cd /d "%ZWL_DIR%" && npm start"

echo.
echo ======================================================
echo  Startup complete! Opening browser in 15 seconds...
echo  Login: railway_user / test
echo ======================================================
timeout /t 15 /nobreak >nul
start http://localhost:3200
pause
