@echo off
cd /d "%~dp0"

SET RAILWAY_DIR=%~dp0usecases_examples\Railway
SET ZWL_DIR=%~dp0flatland-hmi-hack4rail\frontend

echo ======================================================
echo  InteractiveAI Railway - Starting...
echo ======================================================

REM Create .env in repo root — docker compose auto-reads this for variable substitution
(
echo CONFIG_PATH=./config/dev/cab-standalone
echo USER_ID=1000
echo USER_GID=1000
echo SPRING_PROFILES_ACTIVE=docker
echo VITE_RAILWAY_SIMU=http://localhost:5001
echo RL_AGENT_API_URL=http://host.docker.internal:5123/api/v1/recommendation
echo RL_AGENT_API_TOKEN=
echo VITE_POWERGRID_SIMU=
echo VITE_ATM_SIMU=
echo VITE_COGNITIVE_TOKEN=
) > "%~dp0.env"

REM Check if already running
docker ps --filter "name=frontend" --filter "status=running" --format "{{.Names}}" 2>nul | findstr "frontend" >nul
IF %ERRORLEVEL% EQU 0 (
    echo       Services already running - skipping Docker startup.
    goto START_APP
)

REM Step 1: Docker
echo.
echo [1/4] Starting Docker services...

docker compose -f "%~dp0config\dev\cab-standalone\docker-compose.yml" -f "%~dp0config\dev\cab-standalone\docker-compose-hub.yml" up -d
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

REM Step 3: Business config and perimeters
echo.
echo [3/4] Loading business configuration...
powershell -ExecutionPolicy Bypass -File "%~dp0setup_config.ps1"
WHERE bash >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    bash "%~dp0resources/loadTestConf.sh" >nul 2>&1
)
echo       Configuration loaded.

:START_APP
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
