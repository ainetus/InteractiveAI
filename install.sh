#!/bin/bash
# ============================================================
# InteractiveAI Railway — One-time installation script
# Run once after cloning the repository.
# ============================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAILWAY_DIR="$SCRIPT_DIR/usecases_examples/Railway"
ZWL_DIR="$SCRIPT_DIR/flatland-hmi-hack4rail/frontend"

echo "======================================================"
echo " InteractiveAI Railway — Checking prerequisites..."
echo "======================================================"
echo ""

# Check Docker
if ! command -v docker &>/dev/null; then
    echo "[MISSING] Docker is not installed."
    echo "          Install from: https://www.docker.com/products/docker-desktop"
    exit 1
fi
echo "[OK] Docker found."

# Check Python 3.10
if python3.10 --version &>/dev/null; then
    PYTHON=python3.10
elif python3 --version 2>&1 | grep -q "3.10"; then
    PYTHON=python3
else
    echo "[MISSING] Python 3.10 not found."
    echo "          Install from: https://www.python.org/downloads/release/python-31011/"
    exit 1
fi
echo "[OK] Python 3.10 found."

# Check Node.js
if ! command -v node &>/dev/null; then
    echo "[MISSING] Node.js not found."
    echo "          Install from: https://nodejs.org/"
    exit 1
fi
echo "[OK] Node.js found."

echo ""
echo "======================================================"
echo " Installing dependencies..."
echo "======================================================"

# 1. Python venv
echo ""
echo "[1/4] Setting up Python environment..."
cd "$RAILWAY_DIR"
if [ ! -d ".venv" ]; then
    $PYTHON -m venv .venv
    echo "      Virtual environment created."
else
    echo "      Virtual environment already exists, skipping."
fi
source .venv/bin/activate
pip install -r requirements.txt
echo "      Python dependencies installed."

# 2. Node dependencies
echo ""
echo "[2/4] Installing Angular ZWL dependencies..."
cd "$ZWL_DIR"
npm install
echo "      Node dependencies installed."

# 3. Create .env file
echo ""
echo "[3/4] Creating Docker environment config..."
cat > "$SCRIPT_DIR/config/dev/cab-standalone/.env" << 'ENV'
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
echo "      .env file created."

# 4. Build Railway frontend
echo ""
echo "[4/4] Building Railway frontend (takes a few minutes)..."
cd "$SCRIPT_DIR"
export CONFIG_PATH="$SCRIPT_DIR/config/dev/cab-standalone"
export USER_ID=1000
export USER_GID=1000
export SPRING_PROFILES_ACTIVE=docker
export VITE_RAILWAY_SIMU=http://localhost:5001

docker compose \
    --env-file config/dev/cab-standalone/.env \
    -f config/dev/cab-standalone/docker-compose.yml \
    build --no-cache frontend

if [ $? -ne 0 ]; then
    echo "      ERROR: Frontend build failed. Check Docker is running."
    exit 1
fi
docker tag cab-standalone-frontend:latest irtsystemx/interactiveai-cab-standalone-frontend:latest
echo "      Frontend built and tagged successfully."

echo ""
echo "======================================================"
echo " Installation complete!"
echo " Run ./start.sh to launch the application."
echo "======================================================"
