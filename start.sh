#!/usr/bin/env bash
# ==============================================================================
# NOC Automation — Start script for Linux and macOS (bash & zsh)
#
# Sets up backend virtualenv + pip dependencies if needed,
# installs frontend npm packages if needed, and runs both servers concurrently.
# ==============================================================================

set -e

# Resolve repository root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$SCRIPT_DIR"

# If run without an interactive terminal (e.g. clicked in GUI file manager),
# automatically spawn a terminal window so the user can track logs and stop with Ctrl+C.
if [ ! -t 1 ] && [ -z "$NOC_IN_TERMINAL" ]; then
    export NOC_IN_TERMINAL=1
    for term in konsole alacritty kitty gnome-terminal xfce4-terminal x-terminal-emulator xterm; do
        if command -v "$term" >/dev/null 2>&1; then
            case "$term" in
                konsole)
                    exec "$term" -e bash "$0" "$@"
                    ;;
                alacritty)
                    exec "$term" -e bash "$0" "$@"
                    ;;
                kitty)
                    exec "$term" bash "$0" "$@"
                    ;;
                gnome-terminal)
                    exec "$term" -- bash "$0" "$@"
                    ;;
                *)
                    exec "$term" -e bash "$0" "$@"
                    ;;
            esac
        fi
    done
fi

BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"

echo "=================================================="
echo " Starting NOC Automation (Backend & Frontend)"
echo "=================================================="

# ------------------------------------------------------------------------------
# 1. Check & Setup Python Virtual Environment (Backend)
# ------------------------------------------------------------------------------
echo ""
echo "[1/4] Checking Python environment..."

# Find python3 or python
if command -v python3 >/dev/null 2>&1; then
    SYSTEM_PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
    SYSTEM_PYTHON="python"
else
    echo "ERROR: Neither 'python3' nor 'python' was found in PATH."
    echo "Please install Python 3.9+ from https://www.python.org/"
    exit 1
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

# Create venv if not present
if [ ! -d "$VENV_DIR" ] || [ ! -f "$VENV_PYTHON" ]; then
    echo "  -> Virtual environment not found at backend/.venv. Creating..."
    "$SYSTEM_PYTHON" -m venv "$VENV_DIR"
    echo "  -> Virtual environment created successfully."
fi

# Check if required packages are installed
echo "[2/4] Checking backend dependencies..."
if ! "$VENV_PYTHON" -c "import fastapi, uvicorn, aiosqlite, pydantic, pydantic_settings" >/dev/null 2>&1; then
    echo "  -> Required packages missing. Installing from backend/requirements.txt..."
    "$VENV_PIP" install --upgrade pip
    "$VENV_PIP" install -r "$BACKEND_DIR/requirements.txt"
    echo "  -> Backend dependencies installed successfully."
else
    echo "  -> Backend dependencies already installed."
fi

# ------------------------------------------------------------------------------
# 2. Check & Setup Node Modules (Frontend)
# ------------------------------------------------------------------------------
echo ""
echo "[3/4] Checking Node.js and frontend dependencies..."

if ! command -v npm >/dev/null 2>&1; then
    echo "ERROR: 'npm' was not found in PATH."
    echo "Please install Node.js from https://nodejs.org/"
    exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "  -> node_modules not found in frontend/. Running 'npm install'..."
    (cd "$FRONTEND_DIR" && npm install)
    echo "  -> Frontend dependencies installed successfully."
else
    echo "  -> Frontend node_modules already present."
fi

# ------------------------------------------------------------------------------
# 3. Launch Backend and Frontend Concurrently
# ------------------------------------------------------------------------------
echo ""
echo "[4/4] Launching Backend and Frontend..."
echo "  -> Backend:  http://localhost:8000 (API & Docs at /docs)"
echo "  -> Frontend: http://localhost:5173"
echo "  -> Press Ctrl+C to stop both servers."
echo "=================================================="
echo ""

# Cleanup trap to kill child processes on Ctrl+C (SIGINT) or exit
cleanup() {
    echo ""
    echo "Stopping servers..."
    if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    wait 2>/dev/null || true
    echo "All servers stopped."
    exit 0
}

trap cleanup INT TERM EXIT

# Start backend
(
    cd "$BACKEND_DIR"
    exec "$VENV_PYTHON" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
) &
BACKEND_PID=$!

# Start frontend
(
    cd "$FRONTEND_DIR"
    exec npm run dev
) &
FRONTEND_PID=$!

# Wait for both background processes
wait
