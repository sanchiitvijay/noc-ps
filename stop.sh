#!/usr/bin/env bash
# ==============================================================================
# NOC Automation — Stop script for Linux and macOS
#
# Stops all running backend (port 8000 / uvicorn) and frontend (port 5173 / vite)
# processes, as well as any start.sh runner.
# ==============================================================================

echo "=================================================="
echo " Stopping NOC Automation (Backend & Frontend)"
echo "=================================================="

# 1. Stop processes listening on port 8000 and 5173
if command -v fuser >/dev/null 2>&1; then
    echo "Freeing port 8000 (Backend)..."
    fuser -k 8000/tcp 2>/dev/null || true
    echo "Freeing port 5173 (Frontend)..."
    fuser -k 5173/tcp 2>/dev/null || true
elif command -v lsof >/dev/null 2>&1; then
    echo "Stopping processes on ports 8000 and 5173..."
    for pid in $(lsof -ti :8000 -ti :5173 2>/dev/null); do
        kill -9 "$pid" 2>/dev/null || true
    done
fi

# 2. Stop any remaining uvicorn/vite/start.sh background instances
pkill -f "uvicorn main:app" 2>/dev/null || true
pkill -f "node.*vite" 2>/dev/null || true
pkill -f "start\.sh" 2>/dev/null || true

echo "=================================================="
echo " All NOC servers have been stopped."
echo "=================================================="
