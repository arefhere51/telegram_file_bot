#!/usr/bin/env bash
set -euo pipefail

# ============================================================
#  Telegram File Bot - One-line Installer
#  Usage:
#    bash <(curl -Ls https://raw.githubusercontent.com/YOUR_USER/telegram_file_bot/main/install.sh)
# ============================================================

REPO_URL="${REPO_URL:-https://github.com/arefhere51/telegram_file_bot.git}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/telegram_file_bot}"
SERVICE_NAME="telegram-file-bot"
PYTHON_MIN="3.10"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

MODE="auto"
NO_START=0
SKIP_WIZARD=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode) [[ $# -ge 2 ]] || err "--mode requires a value"; MODE="$2"; shift 2 ;;
        --no-start) NO_START=1; shift ;;
        --skip-wizard) SKIP_WIZARD=1; shift ;;
        --help|-h)
            echo "Usage: install.sh [--mode auto|systemd|foreground] [--no-start] [--skip-wizard]"
            exit 0
            ;;
        *) err "Unknown option: $1" ;;
    esac
done

echo ""
echo "=========================================="
echo "  Telegram File Bot Installer"
echo "=========================================="
echo ""

# Detect environment
has_systemd() {
    command -v systemctl >/dev/null 2>&1 && [[ "$(ps -p 1 -o comm= 2>/dev/null || true)" == "systemd" ]]
}

if [[ ! "$MODE" =~ ^(auto|systemd|foreground)$ ]]; then
    err "Invalid mode: $MODE (use auto, systemd, or foreground)"
fi

if [[ "$MODE" == "auto" ]]; then
    if has_systemd; then
        MODE="systemd"
    else
        MODE="foreground"
    fi
fi
info "Run mode: $MODE"

# Check Python
if ! command -v python3 >/dev/null 2>&1; then
    err "python3 not found. Please install Python $PYTHON_MIN+"
fi
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
info "Python version: $PY_VER"
if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    err "Python 3.10 or newer is required"
fi

# Install system packages if possible
if command -v apt-get >/dev/null 2>&1; then
    info "Installing system dependencies..."
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        python3-venv python3-pip git curl > /dev/null || true
fi

# Clone or update
if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull --ff-only || warn "git pull failed, continuing with existing code"
else
    info "Cloning repository..."
    # If running from local (for testing), copy instead of clone
    if [[ -f "$(dirname "$0")/main.py" ]]; then
        info "Local source detected, copying files..."
        mkdir -p "$INSTALL_DIR"
        cp -a "$(dirname "$0")/." "$INSTALL_DIR/"
    else
        git clone --depth 1 "$REPO_URL" "$INSTALL_DIR" || err "Failed to clone repo. Set REPO_URL env var."
    fi
    cd "$INSTALL_DIR"
fi

# Virtualenv
info "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
ok "Dependencies installed"

# Wizard
if [[ $SKIP_WIZARD -eq 0 ]]; then
    echo ""
    echo "---- Configuration Wizard ----"
    echo ""

    if [[ ! -f .env ]]; then
        cp .env.example .env
    fi

    # API_ID
    read -rp "Enter Telegram API_ID (from https://my.telegram.org): " INPUT_API_ID
    [[ -n "$INPUT_API_ID" ]] || err "API_ID is required"

    # API_HASH
    read -rp "Enter Telegram API_HASH: " INPUT_API_HASH
    [[ -n "$INPUT_API_HASH" ]] || err "API_HASH is required"

    # BOT_TOKEN
    read -rsp "Paste BotFather token (hidden): " INPUT_BOT_TOKEN
    echo ""
    [[ -n "$INPUT_BOT_TOKEN" ]] || err "BOT_TOKEN is required"

    # ADMIN_IDS
    read -rp "Enter numeric Telegram user ID(s), comma-separated: " INPUT_ADMINS
    [[ -n "$INPUT_ADMINS" ]] || err "At least one admin ID is required"

    # PUBLIC_BASE_URL
    DEFAULT_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
    read -rp "Public base URL for download links [http://${DEFAULT_IP}:14141]: " INPUT_PUBLIC
    INPUT_PUBLIC="${INPUT_PUBLIC:-http://${DEFAULT_IP}:14141}"

    read -rp "Panel username: " INPUT_PANEL_USER
    [[ -n "$INPUT_PANEL_USER" ]] || err "Panel username is required"
    read -rsp "Panel password (at least 16 characters): " INPUT_PANEL_PASS
    echo ""
    [[ ${#INPUT_PANEL_PASS} -ge 16 ]] || err "Panel password must be at least 16 characters"

    # Write .env
    umask 077
    cat > .env <<EOF
API_ID=${INPUT_API_ID}
API_HASH=${INPUT_API_HASH}
BOT_TOKEN=${INPUT_BOT_TOKEN}
ADMIN_IDS=${INPUT_ADMINS}
PANEL_USERNAME=${INPUT_PANEL_USER}
PANEL_PASSWORD=${INPUT_PANEL_PASS}
WEB_HOST=0.0.0.0
WEB_PORT=14141
PUBLIC_BASE_URL=${INPUT_PUBLIC}
DATA_DIR=./data
MAX_FILE_SIZE_GB=2
AUTO_DELETE_DAYS=0
EOF
    ok "Configuration saved to .env"
else
    [[ -f .env ]] || err ".env not found and --skip-wizard was used"
fi

# Create data dir
mkdir -p data/files

if [[ $NO_START -eq 1 ]]; then
    ok "Installation complete (not started)."
    echo "To start manually: cd $INSTALL_DIR && source venv/bin/activate && python main.py"
    exit 0
fi

if [[ "$MODE" == "systemd" ]]; then
    info "Installing systemd service..."
    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Telegram File Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable "$SERVICE_NAME"
    sudo systemctl restart "$SERVICE_NAME"
    ok "Service installed and started"
    echo ""
    echo "Useful commands:"
    echo "  systemctl status $SERVICE_NAME"
    echo "  journalctl -u $SERVICE_NAME -f"
    echo "  systemctl restart $SERVICE_NAME"
else
    info "Starting in foreground mode..."
    echo ""
    echo "Bot + Web panel are starting..."
    echo "Web panel: http://0.0.0.0:14141"
    echo "Press Ctrl+C to stop"
    echo ""
    exec "$INSTALL_DIR/venv/bin/python" main.py
fi

echo ""
ok "Done!"
echo "Web panel → http://YOUR_IP:14141"
echo "Send a large file to your bot in Telegram."
