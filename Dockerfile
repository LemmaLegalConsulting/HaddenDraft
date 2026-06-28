# Stage 1: Build Frontend
FROM node:22-slim AS frontend
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

# Set permissions for start script
RUN chmod +x /app/start.sh

# Expose HTTP port
EXPOSE 80

CMD ["/app/start.sh"]
