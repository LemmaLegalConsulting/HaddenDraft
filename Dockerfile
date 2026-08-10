# Stage 1: Build Frontend
FROM node:24-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Build Backend & Setup Server
FROM python:3.12-slim
WORKDIR /app

# Install system dependencies including Nginx
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev nginx \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy all project files
COPY . .

# Copy compiled frontend from Stage 1
COPY --from=frontend /app/frontend/dist /app/frontend/dist

# Configure Nginx
COPY nginx.conf /etc/nginx/sites-available/default

# Set permissions for entrypoint scripts
RUN chmod +x /app/start.sh /app/docker/bootstrap.sh /app/docker/web.sh

# Collect Django's static files at build time. They are the same for every
# replica and depend only on the code, so baking them in keeps startup fast and
# keeps replicas from racing to write the same directory. Settings are only
# imported here, and no database is configured during the build.
RUN cd /app/backend \
    && DJANGO_DEBUG=true POSTGRES_HOST= python manage.py collectstatic --noinput

# Expose HTTP port
EXPOSE 80

CMD ["/app/start.sh"]
