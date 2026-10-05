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
if ! python3.10 --version &>/dev/null && ! python3 --version 2>&1 | grep -q "3.10"; then
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

# Python venv
echo ""
echo "[1/2] Setting up Python environment..."
cd "$RAILWAY_DIR"
if [ ! -d ".venv" ]; then
    python3.10 -m venv .venv 2>/dev/null || python3 -m venv .venv
    echo "      Virtual environment created."
else
    echo "      Virtual environment already exists, skipping."
fi
source .venv/bin/activate
pip install -r requirements.txt
echo "      Python dependencies installed."

# Node
echo ""
echo "[2/2] Installing Angular ZWL dependencies..."
cd "$ZWL_DIR"
npm install
echo "      Node dependencies installed."

echo ""
echo "======================================================"
echo " Installation complete!"
echo " Run ./start.sh to launch the application."
echo "======================================================"
