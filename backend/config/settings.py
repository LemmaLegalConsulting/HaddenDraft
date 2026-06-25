import os
from pathlib import Path


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
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1", "testserver"])
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]
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
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "apps.core.middleware.DevCorsMiddleware",
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
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/New_York"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "media/"
MEDIA_ROOT = REPO_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL") or os.environ.get("OPENAI_MISTRAL_MODEL", "gpt-4.1-mini")
AI_DRAFTING_ENABLED = env_bool("AI_DRAFTING_ENABLED", bool(OPENAI_API_KEY))
CASE_ACTION_MODEL = os.environ.get("CASE_ACTION_MODEL", OPENAI_MODEL)
DOCUMENT_TEXT_EXTRACTOR = os.environ.get("DOCUMENT_TEXT_EXTRACTOR", "stdlib")

LEGALSERVER_BASE_URL = os.environ.get("LEGALSERVER_BASE_URL", "")
LEGALSERVER_API_TOKEN = os.environ.get("LEGALSERVER_API_TOKEN", "")
LEGALSERVER_MATTERS_PATH = os.environ.get("LEGALSERVER_MATTERS_PATH", "/api/v1/matters")
LEGALSERVER_MATTER_DOCUMENTS_PATH = os.environ.get(
    "LEGALSERVER_MATTER_DOCUMENTS_PATH", "/api/v1/matters/{matter_id}/documents"
)
LEGALSERVER_USER_FILTER_PARAM = os.environ.get("LEGALSERVER_USER_FILTER_PARAM", "assigned_user_email")
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
