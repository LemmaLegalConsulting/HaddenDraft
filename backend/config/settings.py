import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BASE_DIR.parent


def load_dotenv(path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name, default):
    value = os.environ.get(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


load_dotenv(REPO_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
if not DEBUG and SECRET_KEY in {"", "change-me", "dev-only-change-me"}:
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY to a unique secret before running with DJANGO_DEBUG=false.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1", "testserver"])
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", DEV_ORIGINS if DEBUG else [])
CORS_ALLOWED_ORIGINS = env_list("DJANGO_CORS_ALLOWED_ORIGINS", DEV_ORIGINS if DEBUG else [])
FRONTEND_SITE_URL = os.environ.get("FRONTEND_SITE_URL", "http://localhost:5173")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.matters",
    "apps.sources",
    "apps.templates_app",
    "apps.drafting",
    "apps.facts",
    "apps.issues",
    "apps.rules",
    "apps.ai",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    *( ["apps.core.middleware.DevCorsMiddleware"] if DEBUG else [] ),
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    *(
        ["django.contrib.auth.middleware.RemoteUserMiddleware"]
        if env_bool("ENABLE_REMOTE_USER_AUTH", False)
        else []
    ),
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "django.contrib.auth.backends.RemoteUserBackend",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"

if os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "agentic_housing"),
            "USER": os.environ.get("POSTGRES_USER", "agentic_housing"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ["POSTGRES_HOST"],
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": int(os.environ.get("POSTGRES_CONN_MAX_AGE", "60")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [] if DEBUG else [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/New_York"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = REPO_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", not DEBUG)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = env_bool("DJANGO_CSRF_COOKIE_HTTPONLY", False)
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
SECURE_REFERRER_POLICY = os.environ.get("DJANGO_SECURE_REFERRER_POLICY", "same-origin")
X_FRAME_OPTIONS = "DENY"

OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL") or os.environ.get("OPENAI_MISTRAL_MODEL", "gpt-5.4-mini")
AI_DRAFTING_ENABLED = env_bool("AI_DRAFTING_ENABLED", bool(OPENAI_API_KEY))
CASE_ACTION_MODEL = os.environ.get("CASE_ACTION_MODEL", OPENAI_MODEL)
PROMPT_CATALOG_DIR = Path(os.environ.get("PROMPT_CATALOG_DIR", REPO_DIR / "prompts"))
CONTENT_LIBRARY_DIR = Path(os.environ.get("CONTENT_LIBRARY_DIR", REPO_DIR / "content"))
if not CONTENT_LIBRARY_DIR.is_absolute():
    CONTENT_LIBRARY_DIR = REPO_DIR / CONTENT_LIBRARY_DIR
DOCUMENT_TEXT_EXTRACTOR = os.environ.get("DOCUMENT_TEXT_EXTRACTOR", "stdlib")
# Fallback only. Administrators can override it in Organization settings, and
# users can choose a personal default in their profile.
DEFAULT_JURISDICTION = os.environ.get("DEFAULT_JURISDICTION", "Ohio")

LEGALSERVER_BASE_URL = os.environ.get("LEGALSERVER_BASE_URL", "")
LEGALSERVER_API_TOKEN = os.environ.get("LEGALSERVER_API_TOKEN", "")
LEGALSERVER_API_USERNAME = os.environ.get("LEGALSERVER_API_USERNAME", "")
LEGALSERVER_API_PASSWORD = os.environ.get("LEGALSERVER_API_PASSWORD", "")
LEGALSERVER_MATTERS_PATH = os.environ.get("LEGALSERVER_MATTERS_PATH", "/api/v2/matters")
LEGALSERVER_MATTERS_RESULTS = os.environ.get("LEGALSERVER_MATTERS_RESULTS", "full")
LEGALSERVER_MATTER_DOCUMENTS_PATH = os.environ.get(
    "LEGALSERVER_MATTER_DOCUMENTS_PATH", "/api/v1/matters/{matter_id}/documents"
)
LEGALSERVER_USERS_PATH = os.environ.get("LEGALSERVER_USERS_PATH", "/api/v1/users")
LEGALSERVER_USER_FILTER_PARAM = os.environ.get("LEGALSERVER_USER_FILTER_PARAM", "")
LEGALSERVER_AUTO_MAP_OFFICE365_EMAIL = env_bool("LEGALSERVER_AUTO_MAP_OFFICE365_EMAIL", True)
LEGALSERVER_REQUIRE_OFFICE365_EMAIL_MATCH = env_bool("LEGALSERVER_REQUIRE_OFFICE365_EMAIL_MATCH", True)
LEGALSERVER_SUPERUSER_GROUPS = env_list("LEGALSERVER_SUPERUSER_GROUPS", ["LegalServer Superusers"])
LEGALSERVER_SUPERUSER_ROLES = env_list(
    "LEGALSERVER_SUPERUSER_ROLES",
    ["admin", "administrator", "superuser", "super user", "site administrator"],
)
ENABLE_DEMO_MATTERS = env_bool("ENABLE_DEMO_MATTERS", False)

SHAREPOINT_SITE_ID = os.environ.get("SHAREPOINT_SITE_ID", "")
SHAREPOINT_DRIVE_ID = os.environ.get("SHAREPOINT_DRIVE_ID", "")
SHAREPOINT_ACCESS_TOKEN = os.environ.get("SHAREPOINT_ACCESS_TOKEN", "")
SHAREPOINT_CASE_FOLDER_TEMPLATE = os.environ.get("SHAREPOINT_CASE_FOLDER_TEMPLATE", "Cases/{matter_id}")

OFFICE365_TENANT_ID = os.environ.get("OFFICE365_TENANT_ID", "")
OFFICE365_CLIENT_ID = os.environ.get("OFFICE365_CLIENT_ID", "")
OFFICE365_CLIENT_SECRET = os.environ.get("OFFICE365_CLIENT_SECRET", "")
OFFICE365_REDIRECT_URI = os.environ.get("OFFICE365_REDIRECT_URI", "http://localhost:5173/api/auth/office365/callback/")
OFFICE365_SCOPES = os.environ.get(
    "OFFICE365_SCOPES",
    "openid profile email offline_access User.Read Sites.Read.All Files.Read.All",
)
