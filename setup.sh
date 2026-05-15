#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# setup.sh — one-shot setup for tg_queue_mgmt
# Works on: Debian/Ubuntu, Arch, Fedora/RHEL, WSL (all distros)
# ─────────────────────────────────────────────────────────────
set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

info()  { echo -e "${GREEN}[setup]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC}  $*"; }
error() { echo -e "${RED}[error]${NC} $*" >&2; exit 1; }

# ── 1. Detect Python 3 ───────────────────────────────────────
PYTHON=""
for candidate in python3 python3.12 python3.11 python3.10 python3.9; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done
[[ -z "$PYTHON" ]] && error "Python 3 not found. Install it first (see README)."
info "Using Python: $($PYTHON --version)"

# ── 2. Ensure python3-venv / python3-full is available ───────
if ! $PYTHON -c "import venv" &>/dev/null; then
    warn "venv module missing. Trying to install it..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq
        sudo apt-get install -y python3-venv python3-full
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3-virtualenv
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm python-virtualenv
    else
        error "Cannot install venv automatically. Please install python3-venv manually."
    fi
fi

# ── 3. Create virtual environment ────────────────────────────
if [[ ! -d venv ]]; then
    info "Creating virtual environment at ./venv ..."
    $PYTHON -m venv venv
else
    info "Virtual environment already exists, skipping creation."
fi

# ── 4. Activate and install dependencies ─────────────────────
info "Activating venv and installing requirements..."
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt

# ── 5. Create .env from example if not present ───────────────
if [[ ! -f .env ]]; then
    cp .env.example .env
    warn ".env created from .env.example — please edit it and set BOT_TOKEN and ADMIN_IDS"
else
    info ".env already exists, skipping."
fi

echo ""
info "✅ Setup complete!"
echo -e "  Next steps:"
echo -e "    1. Edit .env and set your BOT_TOKEN and ADMIN_IDS"
echo -e "    2. Run: ${GREEN}./run.sh${NC}"
echo ""
