#!/bin/bash
# Serve the application: nginx for the built frontend and static assets,
# gunicorn for Django behind it. Nothing here writes to the database or the
# content library, so this is safe to run in as many replicas as needed.
set -Eeuo pipefail

cd /app/backend

# MEDIA_ROOT is a mounted share in production and may come up empty.
mkdir -p /app/media

NGINX_PID=""
GUNICORN_PID=""

# Forward container termination to both processes so a revision swap drains
# cleanly instead of leaving one of them to be killed.
terminate() {
  [ -n "$NGINX_PID" ] && kill -TERM "$NGINX_PID" 2>/dev/null
  [ -n "$GUNICORN_PID" ] && kill -TERM "$GUNICORN_PID" 2>/dev/null
  return 0
}
trap terminate TERM INT

nginx -g "daemon off;" &
NGINX_PID=$!

gunicorn config.wsgi:application \
  --bind 127.0.0.1:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --access-logfile - \
  --error-logfile - &
GUNICORN_PID=$!

# Whichever process exits first takes the container down, so a dead gunicorn
# is not masked by an nginx that keeps answering the health probe.
EXIT_CODE=0
wait -n "$NGINX_PID" "$GUNICORN_PID" || EXIT_CODE=$?
terminate
wait 2>/dev/null || true
exit "$EXIT_CODE"
