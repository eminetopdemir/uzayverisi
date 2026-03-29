#!/usr/bin/env bash
# start.sh — Launch backend + frontend together
#
# Usage:  bash start.sh
#
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "🛰️  SatComm Monitor — Starting services"
echo "──────────────────────────────────────────"

# ── Backend (FastAPI) ──
echo "▶  Backend  →  http://localhost:8000"
echo "   API docs  →  http://localhost:8000/docs"
cd "$ROOT"
source .venv/bin/activate
uvicorn backend.main:app --port 8000 --reload &
BACKEND_PID=$!

# ── Frontend (Vite + React) ──
echo "▶  Frontend →  http://localhost:5173"
cd "$ROOT/frontend"
npm run dev -- --host &
FRONTEND_PID=$!

echo ""
echo "✅  Both services started."
echo "   Backend  PID: $BACKEND_PID"
echo "   Frontend PID: $FRONTEND_PID"
echo ""
echo "   Press Ctrl+C to stop both."
echo "──────────────────────────────────────────"

# Wait and propagate Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo ''; echo '🛑 Stopped.'" EXIT
wait $BACKEND_PID $FRONTEND_PID
