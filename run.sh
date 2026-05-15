#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# run.sh — start the bot + web server
# ─────────────────────────────────────────────────────────────────
set -e

GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'

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

echo -e "${GREEN}[run]${NC} Activating venv..."
source venv/bin/activate

# Ensure project root is in PYTHONPATH so that 'db', 'web', 'bot' are importable
export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"

echo -e "${GREEN}[run]${NC} Starting tg_queue_mgmt (project root: $SCRIPT_DIR)..."
exec python bot/main.py
