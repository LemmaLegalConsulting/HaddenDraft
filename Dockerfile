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

# Nginx is the only system package the running container needs. gcc and
# libpq-dev used to be installed here for building Python extensions, but every
# pinned dependency ships a manylinux wheel and psycopg[binary] bundles its own
# libpq, so nothing is compiled at install time. Dropping them takes ~200MB off
# the image, which is ~200MB less to pull on a scale-from-zero cold start.
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
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
RUN chmod +x /app/docker/bootstrap.sh /app/docker/web.sh

# Collect Django's static files at build time. They are the same for every
# replica and depend only on the code, so baking them in keeps startup fast and
# keeps replicas from racing to write the same directory. Settings are only
# imported here, and no database is configured during the build.
RUN cd /app/backend \
    && DJANGO_DEBUG=true POSTGRES_HOST= python manage.py collectstatic --noinput

# Bake the bytecode in too. __pycache__ is excluded from the build context, so
# without this every replica compiles the application's own modules on its first
# import — work that is identical on every start and that a cold start pays for
# while someone is waiting on the request that woke the container up.
RUN python -m compileall -q /app/backend /app/scripts || true

# Expose HTTP port
EXPOSE 80

# Serving is the default. Container Apps names the command explicitly for both
# the app and the bootstrap job, so this only decides what a bare `docker run`
# of the image does -- and serving without migrating is the safe answer, since
# bootstrap.sh writes to a database and must run exactly once per deployment.
CMD ["/app/docker/web.sh"]
