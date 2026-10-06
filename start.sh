#!/bin/bash
# ============================================================
# InteractiveAI Railway — Startup script
# Run this every time you want to use the application.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAILWAY_DIR="$SCRIPT_DIR/usecases_examples/Railway"
ZWL_DIR="$SCRIPT_DIR/flatland-hmi-hack4rail/frontend"

echo "======================================================"
echo " InteractiveAI Railway — Starting..."
echo "======================================================"

# Check if already running
if docker ps --filter "name=frontend" --filter "status=running" --format "{{.Names}}" 2>/dev/null | grep -q "frontend"; then
    echo "      Services already running - skipping Docker startup."
else

# Step 1: Docker
echo ""
echo "[1/4] Starting Docker services..."
export USER_ID=1000
export USER_GID=1000
export SPRING_PROFILES_ACTIVE=docker
export VITE_RAILWAY_SIMU=http://localhost:5001
export CONFIG_PATH="$SCRIPT_DIR/config/dev/cab-standalone"
export RL_AGENT_API_URL=http://host.docker.internal:5123/api/v1/recommendation
export RL_AGENT_API_TOKEN=
export VITE_POWERGRID_SIMU=
export VITE_ATM_SIMU=
export VITE_COGNITIVE_TOKEN=

docker compose \
    --env-file "$SCRIPT_DIR/config/dev/cab-standalone/.env" \
    -f "$SCRIPT_DIR/config/dev/cab-standalone/docker-compose.yml" \
    -f "$SCRIPT_DIR/config/dev/cab-standalone/docker-compose-hub.yml" \
    up -d

if [ $? -ne 0 ]; then
    echo "ERROR: Docker failed. Is Docker running?"
    exit 1
fi

echo "      Waiting 25 seconds for services to initialize..."
sleep 25

# Step 2: MongoDB perimeter
echo ""
echo "[2/4] Configuring database..."
docker exec cab-standalone-mongodb-1 mongo operator-fabric \
    -u root -p password --authenticationDatabase admin \
    --eval 'db.perimeter.updateOne({_id:"cabProcess"},{$set:{process:"cabProcess",stateRights:[{state:"messageState",right:"ReceiveAndWrite"}]}},{upsert:true}); db.group.updateOne({_id:"Planner"},{$addToSet:{perimeters:"cabProcess"}}); db.group.updateOne({_id:"Dispatcher"},{$addToSet:{perimeters:"cabProcess"}}); print("done")' \
    2>/dev/null | grep -E "done|error"

# Step 3: Business config
echo ""
echo "[3/4] Loading business configuration..."
cd "$SCRIPT_DIR"

# Create .env file for Docker Compose
cat > config/dev/cab-standalone/.env << 'ENV'
CONFIG_PATH=./config/dev/cab-standalone
USER_ID=1000
USER_GID=1000
SPRING_PROFILES_ACTIVE=docker
VITE_RAILWAY_SIMU=http://localhost:5001
RL_AGENT_API_URL=http://host.docker.internal:5123/api/v1/recommendation
RL_AGENT_API_TOKEN=
VITE_POWERGRID_SIMU=
VITE_ATM_SIMU=
VITE_COGNITIVE_TOKEN=
ENV

# Load bundle and assign perimeters via API
TOKEN=$(curl -s -X POST "http://localhost:3200/auth/token"     -d "username=admin&password=test&grant_type=password&client_id=opfab-client"     | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

if [ -n "$TOKEN" ]; then
    cd resources/bundles/cab-bundle
    tar -czf /tmp/cab-bundle.tar.gz .
    cd "$SCRIPT_DIR"
    curl -s -X POST "http://localhost:3200/businessconfig/processes"         -H "Authorization: Bearer $TOKEN"         -F "file=@/tmp/cab-bundle.tar.gz;type=application/gzip" > /dev/null
    curl -s -X PUT "http://localhost:3200/users/groups/Dispatcher/perimeters"         -H "Authorization: Bearer $TOKEN"         -H "Content-Type: application/json"         -d '["cabProcess"]' > /dev/null
    curl -s -X PUT "http://localhost:3200/users/groups/Planner/perimeters"         -H "Authorization: Bearer $TOKEN"         -H "Content-Type: application/json"         -d '["cabProcess"]' > /dev/null
    echo "      Business config loaded and perimeters assigned."
else
    echo "      WARNING: Could not get auth token. Run setup_config manually if cards don'''t appear."
fi

# Also try loadTestConf.sh for full config
bash resources/loadTestConf.sh > /dev/null 2>&1 || true

fi

# Step 4: Flask and Angular in background
echo ""
echo "[4/4] Starting Railway brain and ZWL frontend..."

# Detect terminal emulator for new windows
if command -v gnome-terminal &>/dev/null; then
    gnome-terminal --title="Flask Railway Brain" -- bash -c "cd '$RAILWAY_DIR' && source .venv/bin/activate && python app.py; read -p 'Press enter to close'"
    sleep 2
    gnome-terminal --title="Angular ZWL" -- bash -c "cd '$ZWL_DIR' && npm start; read -p 'Press enter to close'"
elif command -v xterm &>/dev/null; then
    xterm -title "Flask Railway Brain" -e bash -c "cd '$RAILWAY_DIR' && source .venv/bin/activate && python app.py; read -p 'Press enter'" &
    sleep 2
    xterm -title "Angular ZWL" -e bash -c "cd '$ZWL_DIR' && npm start; read -p 'Press enter'" &
else
    # No GUI terminal — run in background, log to files
    cd "$RAILWAY_DIR" && source .venv/bin/activate
    nohup python app.py > "$SCRIPT_DIR/flask.log" 2>&1 &
    echo "      Flask started (logs: flask.log)"
    nohup bash -c "cd '$ZWL_DIR' && npm start" > "$SCRIPT_DIR/angular.log" 2>&1 &
    echo "      Angular started (logs: angular.log)"
fi

echo ""
echo "      Waiting 15 seconds for Angular to start..."
sleep 15

# Open browser
if command -v xdg-open &>/dev/null; then
    xdg-open http://localhost:3200
elif command -v open &>/dev/null; then
    open http://localhost:3200  # macOS
fi

echo ""
echo "======================================================"
echo " Startup complete!"
echo ""
echo " Browser: http://localhost:3200"
echo " Login:   railway_user / test"
echo "======================================================"
