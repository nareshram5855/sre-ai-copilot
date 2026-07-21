#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
INFRA_DIR="/Users/shivapriya/Downloads/infra-platform"
FRONTEND_DIR="$INFRA_DIR/ui/frontend"
PATCHES_DIR="$REPO_DIR/stackport-patches"

# ── 1. Apply latest patches ────────────────────────────────────────────────────
echo "→ Applying stackport patches..."
cp "$PATCHES_DIR/pages/Architect.jsx"           "$FRONTEND_DIR/src/pages/Architect.jsx"
cp "$PATCHES_DIR/pages/Blueprints.jsx"          "$FRONTEND_DIR/src/pages/Blueprints.jsx"
cp "$PATCHES_DIR/pages/Deploy.jsx"              "$FRONTEND_DIR/src/pages/Deploy.jsx"
cp "$PATCHES_DIR/pages/MyTeam.jsx"              "$FRONTEND_DIR/src/pages/MyTeam.jsx"
cp "$PATCHES_DIR/pages/Pipelines.jsx"           "$FRONTEND_DIR/src/pages/Pipelines.jsx"
cp "$PATCHES_DIR/components/layout/AppShell.jsx" "$FRONTEND_DIR/src/components/layout/AppShell.jsx"
cp "$PATCHES_DIR/components/layout/Sidebar.jsx"  "$FRONTEND_DIR/src/components/layout/Sidebar.jsx"
echo "   Patches applied."

# ── 2. Start FastAPI backend on port 8081 ─────────────────────────────────────
echo "→ Starting backend on :8081..."
cd "$REPO_DIR"
PYTHONPATH="$REPO_DIR" uvicorn backend.main:app --host 127.0.0.1 --port 8081 --reload &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"

# ── 3. Start Vite dev server on port 5174 ─────────────────────────────────────
echo "→ Starting Stackport frontend on :5174..."
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!
echo "   Frontend PID: $FRONTEND_PID"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Stackport UI  →  http://localhost:5174"
echo "   (Vite auto-picks next port if 5174 is busy)"
echo " Backend API   →  http://localhost:8081"
echo " Press Ctrl+C to stop both"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Wait and clean up both on Ctrl+C
trap "echo ''; echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
