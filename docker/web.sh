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

# --preload imports Django once in the master and forks the workers from it,
# instead of every worker importing it separately. On a 1-vCPU replica those
# imports otherwise contend for the same core, so this is most of a second off
# the time a cold-started replica takes to answer its first request.
#
# --threads because most of a request's time here is spent waiting on the model
# provider or LegalServer, not computing. With three single-threaded workers,
# three advocates waiting on a plan or a draft held every worker, and everyone
# else's page loads queued behind them -- a 13 ms request took 3.8 s under
# three 7 s research answers, and nginx cuts a queued request off at 60 s.
# Threads let a waiting request give up the worker. Each thread may hold its
# own database connection (CONN_MAX_AGE), so workers x threads x replicas must
# stay under the server's max_connections: 3 x 4 x 3 = 36.
gunicorn config.wsgi:application \
  --bind 127.0.0.1:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --preload \
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
