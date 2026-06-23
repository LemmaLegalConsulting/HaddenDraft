#!/usr/bin/env bash
# -------------------------------------------------
# run_all.sh – start Vite (frontend) and Django (backend)
# -------------------------------------------------
# Both Vite and Django provide their own hot‑reload/watch mechanisms.
# This script simply launches them side‑by‑side and shuts them down
# together when you interrupt (Ctrl‑C).

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---- Start Django ------------------------------------------------
cd "$PROJECT_ROOT/backend"
if [ -d "$PROJECT_ROOT/.venv" ]; then
  echo "📦 Activating virtual environment..."
  source "$PROJECT_ROOT/.venv/bin/activate"
fi
python manage.py runserver 127.0.0.1:8000 &
DJANGO_PID=$!

echo "✅ Django dev server running on http://127.0.0.1:8000 (PID $DJANGO_PID)"

# ---- Start Vite --------------------------------------------------
cd "$PROJECT_ROOT/frontend"
# Ensure node modules are present (no‑op if already installed)
npm ci > /dev/null 2>&1 || npm install
npm run dev &
VITE_PID=$!

echo "✅ Vite dev server running on http://localhost:5173 (PID $VITE_PID)"

# -------------------------------------------------
# Graceful shutdown: kill both processes on SIGINT/SIGTERM
# -------------------------------------------------
cleanup() {
  echo ""
  echo "🛑 Stopping servers..."
  kill $DJANGO_PID $VITE_PID 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM EXIT

# Wait for either process to exit (unlikely unless an error occurs)
wait -n
cleanup
