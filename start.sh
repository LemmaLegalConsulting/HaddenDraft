#!/bin/bash
set -e

# Change to backend directory to run manage.py commands
cd /app/backend

# Run ingest document templates
python manage.py ingest_document_templates

# Run migrations
python manage.py migrate

# Collect static files for Django admin
python manage.py collectstatic --noinput

# Start Nginx in background
nginx -g "daemon off;" &

# Start Django backend in foreground
exec gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3
