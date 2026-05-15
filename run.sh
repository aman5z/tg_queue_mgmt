#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# run.sh — start the bot + web server
# ─────────────────────────────────────────────────────────────────
set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

# Always resolve and cd to the project root (where this script lives)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -d venv ]]; then
    echo -e "${RED}[error]${NC} Virtual environment not found. Run ./setup.sh first."
    exit 1
fi

if [[ ! -f .env ]]; then
    echo -e "${RED}[error]${NC} .env file not found. Copy .env.example to .env and fill in your values."
    exit 1
fi

# Read PORT from .env (default 8000)
PORT=$(grep -E '^PORT=' .env | cut -d= -f2 | tr -d ' ')
PORT="${PORT:-8000}"

# Auto-kill anything already using that port
PIDS=$(lsof -ti :"$PORT" 2>/dev/null || true)
if [[ -n "$PIDS" ]]; then
    echo -e "${YELLOW}[run]${NC} Port $PORT in use (PIDs: $PIDS) — killing..."
    echo "$PIDS" | xargs kill -9 2>/dev/null || true
    sleep 1
fi

echo -e "${GREEN}[run]${NC} Activating venv..."
source venv/bin/activate

# Ensure project root is in PYTHONPATH so that 'db', 'web', 'bot' are importable
export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"

echo -e "${GREEN}[run]${NC} Starting tg_queue_mgmt on port $PORT (project root: $SCRIPT_DIR)..."
exec python bot/main.py
